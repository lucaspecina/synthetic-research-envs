"""Tests for SCMProblemBuilder."""

from __future__ import annotations

import numpy as np

from sreg.models.case_plan import CasePlan, EvalQuestionPlan
from sreg.models.task import TaskType
from sreg.tools.scm_problem_builder import SCMProblemBuilder
from sreg.tools.scm_task_gen import SCMTaskGenTool
from sreg.world.scm import SCMWorld, VariableMeta

# ---- Test fixtures ----

def _linear_chain() -> SCMWorld:
    """A -> B -> C (linear chain, no latent)."""
    return SCMWorld(
        id="test_linear",
        graph={"A": [], "B": ["A"], "C": ["B"]},
        equations={
            "A": lambda p, rng: rng.normal(5.0, 1.0),
            "B": lambda p, rng: 0.8 * p["A"] + rng.normal(0, 0.5),
            "C": lambda p, rng: 1.2 * p["B"] + rng.normal(0, 0.3),
        },
        variable_meta={
            "A": VariableMeta(unit="kg", range=(0, 10), description="Weight"),
            "B": VariableMeta(unit="cm", range=(0, 20), description="Length"),
            "C": VariableMeta(unit="m/s", range=(0, 30), description="Speed"),
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


# ---- Tests ----

class TestBuildBasic:
    """Test basic SCMProblemBuilder.build() behavior."""

    def test_builds_research_problem(self):
        world = _linear_chain()
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="C", seed=42)

        assert problem.world_id == "test_linear"
        assert problem.target_node == "C"
        assert len(problem.data_assets) >= 1
        assert len(problem.available_actions) >= 1
        assert problem.budget > 0
        assert problem.research_question

    def test_infers_target_from_tasks(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        from sreg.models.task import TaskSpec
        tasks = [gen.generate(
            world,
            spec=TaskSpec(
                type=TaskType.INFER_TARGET, target_node="C", max_budget=5
            ),
        )]
        builder = SCMProblemBuilder()
        problem = builder.build(world, tasks=tasks, seed=42)
        assert problem.target_node == "C"

    def test_infers_target_from_topo_order(self):
        world = _linear_chain()
        builder = SCMProblemBuilder()
        problem = builder.build(world, seed=42)
        # Last in topo order = C
        assert problem.target_node == "C"

    def test_custom_budget(self):
        world = _linear_chain()
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="C", budget=10, seed=42)
        assert problem.budget == 10


class TestDataGeneration:
    """Test data asset generation."""

    def test_single_dataset(self):
        world = _linear_chain()
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="C", n_rows=100, seed=42)

        assert len(problem.data_assets) == 1
        asset = problem.data_assets[0]
        assert asset.format == "tabular"
        assert asset.num_rows == 100
        assert len(asset.data) == 100
        # Should have all observable variables
        row = asset.data[0]
        assert "A" in row
        assert "B" in row
        assert "C" in row

    def test_multi_dataset(self):
        world = _linear_chain()
        builder = SCMProblemBuilder()
        problem = builder.build(
            world, target="C", n_rows=200, multi_dataset=True, seed=42
        )

        assert len(problem.data_assets) >= 2
        # Each asset should have data
        for asset in problem.data_assets:
            assert len(asset.data) > 0
            assert asset.format == "tabular"

    def test_latent_excluded_from_data(self):
        world = _with_latent()
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="C", seed=42)

        asset = problem.data_assets[0]
        row = asset.data[0]
        assert "L" not in row  # Latent excluded
        assert "A" in row
        assert "B" in row

    def test_data_has_numeric_values(self):
        world = _linear_chain()
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="C", n_rows=50, seed=42)

        asset = problem.data_assets[0]
        for row in asset.data[:5]:
            for key in ["A", "B", "C"]:
                val = row[key]
                # Values should be numeric (float or int), or NaN for missing
                assert isinstance(val, (int, float)) or (
                    isinstance(val, float) and np.isnan(val)
                ), f"Expected numeric, got {type(val)}: {val}"


class TestActions:
    """Test action generation."""

    def test_actions_for_observable_vars(self):
        world = _linear_chain()
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="C", seed=42)

        action_nodes = {a.node for a in problem.available_actions}
        # A and B should be available (C is target, excluded)
        assert "A" in action_nodes
        assert "B" in action_nodes
        assert "C" not in action_nodes

    def test_latent_excluded_from_actions(self):
        world = _with_latent()
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="C", seed=42)

        action_nodes = {a.node for a in problem.available_actions}
        assert "L" not in action_nodes


class TestTargetStates:
    """Test target state (bin range) generation."""

    def test_target_states_from_tasks(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        from sreg.models.task import TaskSpec
        tasks = [gen.generate(
            world,
            spec=TaskSpec(type=TaskType.INFER_TARGET, target_node="C", max_budget=5),
        )]
        builder = SCMProblemBuilder()
        problem = builder.build(world, tasks=tasks, target="C", seed=42)

        # Should use bin ranges from the task
        assert all(s.startswith("[") for s in problem.target_states)
        assert len(problem.target_states) == 5  # default N_BINS

    def test_target_states_fallback(self):
        world = _linear_chain()
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="C", seed=42)

        # Should compute bin ranges on the fly
        assert len(problem.target_states) == 5
        assert all(s.startswith("[") for s in problem.target_states)


class TestDescription:
    """Test narrative description."""

    def test_description_includes_target(self):
        world = _linear_chain()
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="C", seed=42)
        assert "C" in problem.description

    def test_description_includes_metadata(self):
        world = _linear_chain()
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="C", seed=42)
        # Variable descriptions from metadata
        assert "Weight" in problem.description or "Length" in problem.description

    def test_question_includes_unit(self):
        world = _linear_chain()
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="C", seed=42)
        # C has unit "m/s"
        assert "m/s" in problem.research_question


class TestCasePlanIntegration:
    """Test integration with CasePlan."""

    def test_question_from_case_plan(self):
        """Legacy: without brief, falls back to questions[0].question_text."""
        world = _linear_chain()
        plan = CasePlan(
            title="Test plan",
            research_context="Testing the pipeline integration.",
            questions=[
                EvalQuestionPlan(
                    question_text="What is the distribution of speed given the measurements?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="C",
                ),
            ],
            shared_budget=5,
        )
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="C", case_plan=plan, seed=42)
        assert "distribution of speed" in problem.research_question

    def test_question_from_research_brief(self):
        """Fase 5: research_brief takes priority over questions[0]."""
        world = _linear_chain()
        plan = CasePlan(
            title="Test plan",
            research_context="Testing the brief/eval separation.",
            research_brief=(
                "Investigate the factors that determine the final speed "
                "of objects in this system. Identify which upstream "
                "measurements are most predictive and whether changes "
                "to initial conditions could reliably alter outcomes."
            ),
            deliverables=[
                "Identify the main causal drivers of speed",
                "Evaluate whether weight or length changes are more impactful",
                "Recommend an optimal measurement strategy",
            ],
            questions=[
                EvalQuestionPlan(
                    question_text="What is the distribution of speed?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="C",
                ),
            ],
            shared_budget=5,
        )
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="C", case_plan=plan, seed=42)
        # Brief should be used, not questions[0]
        assert "Investigate the factors" in problem.research_question
        assert "distribution of speed" not in problem.research_question
        # Deliverables should appear
        assert "causal drivers" in problem.research_question
        assert "measurement strategy" in problem.research_question

    def test_brief_without_deliverables(self):
        """Brief without deliverables still works."""
        world = _linear_chain()
        plan = CasePlan(
            title="Test plan",
            research_context="Testing brief without deliverables.",
            research_brief="Investigate the causal chain from weight to speed.",
            questions=[
                EvalQuestionPlan(
                    question_text="What is the distribution of speed?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="C",
                ),
            ],
            shared_budget=5,
        )
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="C", case_plan=plan, seed=42)
        assert "causal chain" in problem.research_question
        assert "Deliverables" not in problem.research_question


    def test_brief_appears_in_solver_prompt(self):
        """Verify the brief flows into the solver prompt correctly."""
        from sreg.agent.prompts import build_case_system_prompt
        from sreg.models.task import Task

        world = _linear_chain()
        plan = CasePlan(
            title="Test plan",
            research_context="Testing brief in solver prompt.",
            research_brief=(
                "Investigate the causal chain from weight to speed. "
                "Determine whether direct manipulation of weight is the "
                "most effective strategy."
            ),
            deliverables=[
                "Identify causal drivers",
                "Recommend interventions",
            ],
            questions=[
                EvalQuestionPlan(
                    question_text="What is the distribution of speed?",
                    eval_type=TaskType.INFER_TARGET,
                    target_node="C",
                ),
            ],
            shared_budget=5,
        )
        builder = SCMProblemBuilder()
        problem = builder.build(world, target="C", case_plan=plan, seed=42)

        # Create a dummy task for the prompt
        task = Task(
            id="test-task",
            type=TaskType.INFER_TARGET,
            world_id="test",
            question="What is the distribution of speed?",
            target_node="C",
            available_evidence=["A", "B"],
            correct_answer={"[0, 5)": 0.3, "[5, 10)": 0.7},
        )

        prompt = build_case_system_prompt(problem, [task])

        # Brief should appear in the prompt
        assert "causal chain from weight to speed" in prompt
        assert "Identify causal drivers" in prompt
        # The prompt should contain the Research Brief section
        assert "Research Brief" in prompt


class TestFullPipeline:
    """Test the full pipeline: SCMWorld -> tasks -> problem."""

    def test_world_to_problem_with_tasks(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        bundle = gen.generate_all(world, target_node="C", seed=42)
        tasks = list(bundle.tasks.values())

        builder = SCMProblemBuilder()
        problem = builder.build(world, tasks=tasks, target="C", seed=42)

        # Verify everything is consistent
        assert problem.target_node == "C"
        assert len(problem.data_assets) >= 1
        assert len(problem.available_actions) >= 1

        # Target states should match task bin ranges
        for task in tasks:
            if task.correct_answer and task.target_node == "C":
                keys = list(task.correct_answer.keys())
                if keys[0].startswith("["):
                    assert problem.target_states == keys
                    break
