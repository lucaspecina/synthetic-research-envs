"""Integration tests for the SCM pipeline: world -> tasks -> problem -> solver dispatch.

Tests the full pipeline wiring WITHOUT LLM calls. Verifies:
1. generate_from_plan() on SCMTaskGenTool
2. SCMProblemBuilder produces valid ResearchProblem
3. AgentSolver._make_solver() dispatches correctly
4. Full pipeline: SCMWorld -> tasks -> problem -> scoring
"""

from __future__ import annotations

import pytest

from sreg.models.case_plan import CasePlan, EvalQuestionPlan
from sreg.models.task import TaskSpec, TaskType
from sreg.tools.scm_problem_builder import SCMProblemBuilder
from sreg.tools.scm_task_gen import SCMTaskGenTool
from sreg.tools.verifier import VerifierTool
from sreg.world.scm import SCMWorld, VariableMeta

# ---- Test worlds ----

def _confounder_world() -> SCMWorld:
    """C -> A -> Y, C -> Y, A -> D. Classic confounder."""
    return SCMWorld(
        id="test_confounded",
        graph={
            "C": [],
            "A": ["C"],
            "Y": ["A", "C"],
            "D": ["A"],
        },
        equations={
            "C": lambda p, rng: rng.normal(10.0, 2.0),
            "A": lambda p, rng: 0.6 * p["C"] + rng.normal(0, 1.0),
            "Y": lambda p, rng: 0.5 * p["A"] + 0.3 * p["C"] + rng.normal(0, 0.5),
            "D": lambda p, rng: 0.4 * p["A"] + rng.normal(0, 0.3),
        },
        variable_meta={
            "C": VariableMeta(unit="mg/L", description="Confounding factor"),
            "A": VariableMeta(unit="units", description="Treatment level"),
            "Y": VariableMeta(unit="score", description="Outcome measure"),
            "D": VariableMeta(unit="units", description="Downstream effect"),
        },
    )


def _with_latent() -> SCMWorld:
    """L -> A, L -> B, A -> C (L is latent)."""
    return SCMWorld(
        id="test_latent",
        graph={"L": [], "A": ["L"], "B": ["L"], "C": ["A"]},
        equations={
            "L": lambda p, rng: rng.normal(3.0, 1.0),
            "A": lambda p, rng: 0.7 * p["L"] + rng.normal(0, 0.5),
            "B": lambda p, rng: 0.5 * p["L"] + rng.normal(0, 0.3),
            "C": lambda p, rng: 1.0 * p["A"] + rng.normal(0, 0.2),
        },
        latent_variables={"L"},
    )


# ---- generate_from_plan() tests ----

class TestGenerateFromPlan:
    """Test SCMTaskGenTool.generate_from_plan()."""

    def test_generates_tasks_from_plan(self):
        world = _confounder_world()
        plan = CasePlan(
            title="Confounder investigation",
            research_context="Investigating the causal effect of A on Y with confounder C.",
            questions=[
                EvalQuestionPlan(
                    question_text="What is the distribution of Y?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="Y",
                ),
                EvalQuestionPlan(
                    question_text="What happens to Y when A is increased?",
                    eval_type=TaskType.CAUSAL_EFFECT,
                    target_node="Y",
                    intervention_node="A",
                ),
            ],
            shared_budget=5,
        )
        gen = SCMTaskGenTool()
        tasks = gen.generate_from_plan(world, plan, seed=42)

        assert len(tasks) == 2
        assert tasks[0].type == TaskType.INFER_TARGET
        assert tasks[1].type == TaskType.CAUSAL_EFFECT

    def test_question_text_override_safe_types(self):
        world = _confounder_world()
        custom_text = "What is the likely outcome score?"
        plan = CasePlan(
            title="Test override",
            research_context="Testing question text override for safe types.",
            questions=[
                EvalQuestionPlan(
                    question_text=custom_text,
                    eval_type=TaskType.INFER_TARGET,
                    target_node="Y",
                ),
            ],
            shared_budget=5,
        )
        gen = SCMTaskGenTool()
        tasks = gen.generate_from_plan(world, plan, seed=42)

        assert tasks[0].question == custom_text

    def test_question_text_override_with_hints(self):
        world = _confounder_world()
        custom_text = "If we set A to a high value, what happens to Y?"
        plan = CasePlan(
            title="Test hint override",
            research_context="Testing question override with intervention hint.",
            questions=[
                EvalQuestionPlan(
                    question_text=custom_text,
                    eval_type=TaskType.CAUSAL_EFFECT,
                    target_node="Y",
                    intervention_node="A",
                ),
            ],
            shared_budget=5,
        )
        gen = SCMTaskGenTool()
        tasks = gen.generate_from_plan(world, plan, seed=42)

        # Hints honored (A is valid intervention node) -> question overridden
        assert tasks[0].question == custom_text

    def test_should_condition_from_plan(self):
        world = _confounder_world()
        plan = CasePlan(
            title="Should condition test",
            research_context="Testing should_condition with confounder.",
            questions=[
                EvalQuestionPlan(
                    question_text="Should we control for C when estimating A -> Y?",
                    eval_type=TaskType.SHOULD_CONDITION,
                    target_node="Y",
                    intervention_node="A",
                    condition_variable="C",
                ),
            ],
            shared_budget=5,
        )
        gen = SCMTaskGenTool()
        tasks = gen.generate_from_plan(world, plan, seed=42)

        assert len(tasks) == 1
        assert tasks[0].type == TaskType.SHOULD_CONDITION
        # C is a valid backdoor variable for A->Y, so answer should be "yes"
        assert "yes" in tasks[0].correct_answer

    def test_adjustment_set_from_plan(self):
        world = _confounder_world()
        plan = CasePlan(
            title="Adjustment set test",
            research_context="Testing adjustment set generation.",
            questions=[
                EvalQuestionPlan(
                    question_text="What variables should we control for?",
                    eval_type=TaskType.ADJUSTMENT_SET,
                    target_node="Y",
                    intervention_node="A",
                ),
            ],
            shared_budget=5,
        )
        gen = SCMTaskGenTool()
        tasks = gen.generate_from_plan(world, plan, seed=42)

        assert len(tasks) == 1
        assert tasks[0].type == TaskType.ADJUSTMENT_SET

    def test_skips_invalid_questions(self):
        world = _confounder_world()
        plan = CasePlan(
            title="Invalid question test",
            research_context="Testing graceful handling of invalid questions.",
            questions=[
                EvalQuestionPlan(
                    question_text="What about the hidden factor?",
                    eval_type=TaskType.INFER_LATENT_CAUSE,
                    target_node="Y",
                ),
                EvalQuestionPlan(
                    question_text="What is the distribution of Y?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="Y",
                ),
            ],
            shared_budget=5,
        )
        gen = SCMTaskGenTool()
        # infer_latent_cause should fail (no latent variables in this world)
        tasks = gen.generate_from_plan(world, plan, seed=42)

        # Should get at least the valid task
        assert len(tasks) >= 1
        assert any(t.type == TaskType.INFER_TARGET for t in tasks)

    def test_all_questions_fail_raises(self):
        world = _confounder_world()
        plan = CasePlan(
            title="All fail test",
            research_context="All questions should fail gracefully.",
            questions=[
                EvalQuestionPlan(
                    question_text="What about the hidden factor?",
                    eval_type=TaskType.INFER_LATENT_CAUSE,
                    target_node="Y",
                ),
            ],
            shared_budget=5,
        )
        gen = SCMTaskGenTool()
        with pytest.raises(ValueError, match="All questions failed"):
            gen.generate_from_plan(world, plan, seed=42)

    def test_infer_latent_cause_from_plan(self):
        world = _with_latent()
        plan = CasePlan(
            title="Latent cause test",
            research_context="Testing latent cause inference.",
            questions=[
                EvalQuestionPlan(
                    question_text="What is the hidden factor L?",
                    eval_type=TaskType.INFER_LATENT_CAUSE,
                    target_node="L",
                ),
            ],
            shared_budget=5,
        )
        gen = SCMTaskGenTool()
        tasks = gen.generate_from_plan(world, plan, seed=42)

        assert len(tasks) == 1
        assert tasks[0].type == TaskType.INFER_LATENT_CAUSE
        assert tasks[0].question == "What is the hidden factor L?"

    def test_multi_type_plan(self):
        """Test a plan with multiple different eval types."""
        world = _confounder_world()
        plan = CasePlan(
            title="Multi-type investigation",
            research_context="Full investigation of the confounder system.",
            questions=[
                EvalQuestionPlan(
                    question_text="What is the distribution of Y?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="Y",
                ),
                EvalQuestionPlan(
                    question_text="Which variable is most informative?",
                    eval_type=TaskType.NEXT_BEST_OBSERVATION,
                    target_node="Y",
                ),
                EvalQuestionPlan(
                    question_text="What is the causal effect of A on Y?",
                    eval_type=TaskType.CAUSAL_EFFECT,
                    target_node="Y",
                    intervention_node="A",
                ),
                EvalQuestionPlan(
                    question_text="Should we control for C?",
                    eval_type=TaskType.SHOULD_CONDITION,
                    target_node="Y",
                    intervention_node="A",
                    condition_variable="C",
                ),
            ],
            shared_budget=5,
        )
        gen = SCMTaskGenTool()
        tasks = gen.generate_from_plan(world, plan, seed=42)

        assert len(tasks) == 4
        types = {t.type for t in tasks}
        assert TaskType.INFER_TARGET in types
        assert TaskType.NEXT_BEST_OBSERVATION in types
        assert TaskType.CAUSAL_EFFECT in types
        assert TaskType.SHOULD_CONDITION in types


# ---- Solver dispatch tests ----

class TestSolverDispatch:
    """Test AgentSolver._make_solver() dispatches correctly."""

    def test_scm_world_creates_scm_solver(self):
        from sreg.agent.agent import AgentSolver
        from sreg.solver.scm_solver import SCMSolver

        world = _confounder_world()
        solver = AgentSolver._make_solver(world)
        assert isinstance(solver, SCMSolver)

    def test_bn_world_creates_exact_bayes(self):
        from sreg.agent.agent import AgentSolver
        from sreg.solver.exact_bayes import ExactBayesSolver

        # Create a minimal discrete BN world
        from sreg.tools.world_gen import WorldGenConfig, WorldGenTool

        gen = WorldGenTool()
        config = WorldGenConfig(num_nodes=4, seed=42)
        world = gen.generate(config)
        solver = AgentSolver._make_solver(world)
        assert isinstance(solver, ExactBayesSolver)


# ---- Scoring compatibility tests ----

class TestScoringCompatibility:
    """Test that SCM tasks score correctly through the existing verifier."""

    def test_kl_scoring_with_bins(self):
        """Verify KL divergence works with bin-range keys."""
        verifier = VerifierTool()

        correct = {
            "[0.00, 2.00)": 0.1,
            "[2.00, 4.00)": 0.3,
            "[4.00, 6.00)": 0.4,
            "[6.00, 8.00)": 0.15,
            "[8.00, 10.00)": 0.05,
        }

        # Perfect match
        score = verifier.score(
            agent_posterior=dict(correct),
            true_posterior=correct,
            budget_used=0,
            budget_total=5,
        )
        assert score.functional_score < 0.01  # KL ~ 0

        # Bad match
        bad = {k: 0.2 for k in correct}
        score_bad = verifier.score(
            agent_posterior=bad,
            true_posterior=correct,
            budget_used=0,
            budget_total=5,
        )
        assert score_bad.functional_score > score.functional_score

    def test_hypothesis_scoring(self):
        """Test hypothesis selection scoring with SCM tasks."""
        verifier = VerifierTool()
        # KL scores: A=0.0 (correct), B=0.5, C=1.0
        correct_answer = {"A": 0.0, "B": 0.5, "C": 1.0}
        score = verifier.score_hypothesis("A", correct_answer)
        assert score == 1.0

        score_wrong = verifier.score_hypothesis("C", correct_answer)
        assert score_wrong == 0.0


# ---- Full pipeline (no LLM) ----

class TestFullPipeline:
    """Test the complete pipeline without LLM calls."""

    def test_world_to_tasks_to_problem(self):
        """SCMWorld -> SCMTaskGenTool -> SCMProblemBuilder -> ResearchProblem."""
        world = _confounder_world()

        # Generate tasks
        gen = SCMTaskGenTool()
        bundle = gen.generate_all(world, target_node="Y", seed=42)
        tasks = list(bundle.tasks.values())

        # Build problem
        builder = SCMProblemBuilder()
        problem = builder.build(world, tasks=tasks, target="Y", seed=42)

        # Verify consistency
        assert problem.target_node == "Y"
        assert len(problem.data_assets) >= 1
        assert len(problem.target_states) == 5

        # Data should be numeric (continuous)
        row = problem.data_assets[0].data[0]
        for key in ["A", "C", "D"]:  # Y may also be there
            if key in row:
                val = row[key]
                assert isinstance(val, (int, float)), f"{key}={val} not numeric"

    def test_plan_to_tasks_to_problem(self):
        """CasePlan -> generate_from_plan -> SCMProblemBuilder."""
        world = _confounder_world()
        plan = CasePlan(
            title="Full pipeline test",
            research_context="Testing the full pipeline from plan to problem.",
            questions=[
                EvalQuestionPlan(
                    question_text="What is the outcome distribution?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="Y",
                ),
                EvalQuestionPlan(
                    question_text="What is the causal effect of A?",
                    eval_type=TaskType.CAUSAL_EFFECT,
                    target_node="Y",
                    intervention_node="A",
                ),
            ],
            shared_budget=5,
        )

        gen = SCMTaskGenTool()
        tasks = gen.generate_from_plan(world, plan, seed=42)

        builder = SCMProblemBuilder()
        problem = builder.build(world, tasks=tasks, target="Y", case_plan=plan, seed=42)

        assert problem.target_node == "Y"
        assert "outcome distribution" in problem.research_question
        assert len(tasks) == 2

        # Verify tasks have correct answers that can be scored
        for task in tasks:
            assert task.correct_answer is not None
            assert len(task.correct_answer) > 0

    def test_scoring_works_end_to_end(self):
        """Generate a task and score a perfect submission."""
        world = _confounder_world()
        gen = SCMTaskGenTool()
        task = gen.generate(
            world,
            TaskSpec(type=TaskType.INFER_TARGET, target_node="Y", max_budget=5),
            seed=42,
        )

        # Submit the correct answer
        verifier = VerifierTool()
        score = verifier.score(
            agent_posterior=dict(task.correct_answer),
            true_posterior=task.correct_answer,
            budget_used=0,
            budget_total=5,
        )
        assert score.functional_score < 0.01  # Perfect match


# ---- Codex-identified edge cases ----

class TestCodexFindings:
    """Tests for edge cases identified by Codex review."""

    def test_solve_single_task_rejects_scm_world(self):
        """solve() should raise NotImplementedError for SCMWorld."""
        from sreg.agent.agent import AgentSolver

        world = _confounder_world()
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="Y", seed=42)

        agent = AgentSolver(model="test", max_iterations=1)
        with pytest.raises(NotImplementedError, match="solve_case"):
            agent.solve(world, problem)

    def test_multi_dataset_description_excludes_latent(self):
        """Multi-dataset descriptions should not mention latent variables."""
        world = _with_latent()
        builder = SCMProblemBuilder()
        problem = builder.build(
            world, target="C", multi_dataset=True, seed=42
        )

        for asset in problem.data_assets:
            # Description should not mention L (latent)
            assert "L" not in asset.columns or []
            # Data rows should not contain L
            if asset.data:
                assert "L" not in asset.data[0]

    def test_infer_latent_cause_respects_target_node(self):
        """_infer_latent_cause_task should use spec.target_node if it's latent."""
        world = SCMWorld(
            id="two_latents",
            graph={
                "L1": [], "L2": [],
                "A": ["L1"], "B": ["L2"], "C": ["A", "B"],
            },
            equations={
                "L1": lambda p, rng: rng.normal(2.0, 1.0),
                "L2": lambda p, rng: rng.normal(5.0, 1.0),
                "A": lambda p, rng: 0.8 * p["L1"] + rng.normal(0, 0.3),
                "B": lambda p, rng: 0.6 * p["L2"] + rng.normal(0, 0.3),
                "C": lambda p, rng: p["A"] + p["B"] + rng.normal(0, 0.2),
            },
            latent_variables={"L1", "L2"},
        )

        gen = SCMTaskGenTool()
        # Ask specifically for L2
        task = gen.generate(
            world,
            TaskSpec(
                type=TaskType.INFER_LATENT_CAUSE,
                target_node="L2",
                max_budget=5,
            ),
            seed=42,
        )
        # Should target L2, not random
        assert task.target_node == "L2"

    def test_infer_latent_cause_plan_targets_correct_latent(self):
        """generate_from_plan with infer_latent_cause targets the specified latent."""
        world = SCMWorld(
            id="two_latents",
            graph={
                "L1": [], "L2": [],
                "A": ["L1"], "B": ["L2"], "C": ["A", "B"],
            },
            equations={
                "L1": lambda p, rng: rng.normal(2.0, 1.0),
                "L2": lambda p, rng: rng.normal(5.0, 1.0),
                "A": lambda p, rng: 0.8 * p["L1"] + rng.normal(0, 0.3),
                "B": lambda p, rng: 0.6 * p["L2"] + rng.normal(0, 0.3),
                "C": lambda p, rng: p["A"] + p["B"] + rng.normal(0, 0.2),
            },
            latent_variables={"L1", "L2"},
        )

        plan = CasePlan(
            title="Two latent test",
            research_context="Testing with two latent variables.",
            questions=[
                EvalQuestionPlan(
                    question_text="What is the value of the second hidden factor?",
                    eval_type=TaskType.INFER_LATENT_CAUSE,
                    target_node="L2",
                ),
            ],
            shared_budget=5,
        )

        gen = SCMTaskGenTool()
        tasks = gen.generate_from_plan(world, plan, seed=42)

        assert len(tasks) == 1
        assert tasks[0].target_node == "L2"
        assert tasks[0].question == "What is the value of the second hidden factor?"
