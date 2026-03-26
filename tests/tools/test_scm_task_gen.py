"""Tests for SCMTaskGenTool — task generation from SCMWorld + SCMSolver."""

from __future__ import annotations

import pytest

from sreg.models.task import TaskSpec, TaskType
from sreg.tools.scm_task_gen import SCMTaskGenTool
from sreg.tools.verifier import VerifierTool
from sreg.world.scm import SCMWorld, VariableMeta

# ------------------------------------------------------------------
# Test worlds
# ------------------------------------------------------------------


def _linear_chain() -> SCMWorld:
    """A -> B -> C. Simple chain, good for most task types."""
    return SCMWorld(
        id="test-linear",
        graph={"A": [], "B": ["A"], "C": ["B"]},
        equations={
            "A": lambda p, rng: rng.normal(0, 1),
            "B": lambda p, rng: 2 * p["A"] + rng.normal(0, 1),
            "C": lambda p, rng: 0.5 * p["B"] + rng.normal(0, 0.5),
        },
    )


def _confounder_world() -> SCMWorld:
    """C -> A -> Y, C -> Y, A -> D.

    C confounds A->Y. D is a descendant of A.
    - Should condition on C: YES (blocks backdoor A <- C -> Y)
    - Should condition on D: NO (descendant of treatment)
    """
    return SCMWorld(
        id="test-confounder",
        graph={
            "C": [],
            "A": ["C"],
            "Y": ["A", "C"],
            "D": ["A"],
        },
        equations={
            "C": lambda p, rng: rng.normal(0, 1),
            "A": lambda p, rng: p["C"] + rng.normal(0, 1),
            "Y": lambda p, rng: 0.5 * p["A"] + 0.3 * p["C"] + rng.normal(0, 1),
            "D": lambda p, rng: p["A"] + rng.normal(0, 0.5),
        },
    )


def _with_latent() -> SCMWorld:
    """L (latent) -> A, L -> B, A -> C.

    L is unobserved. We can infer L from observations of A and B.
    """
    return SCMWorld(
        id="test-latent",
        graph={"L": [], "A": ["L"], "B": ["L"], "C": ["A"]},
        equations={
            "L": lambda p, rng: rng.normal(0, 1),
            "A": lambda p, rng: 2 * p["L"] + rng.normal(0, 0.5),
            "B": lambda p, rng: p["L"] + rng.normal(0, 0.5),
            "C": lambda p, rng: 0.5 * p["A"] + rng.normal(0, 1),
        },
        latent_variables={"L"},
    )


def _independent() -> SCMWorld:
    """A and B are independent. For testing IG = ~0."""
    return SCMWorld(
        id="test-independent",
        graph={"A": [], "B": []},
        equations={
            "A": lambda p, rng: rng.normal(0, 1),
            "B": lambda p, rng: rng.normal(5, 2),
        },
    )


# ------------------------------------------------------------------
# SCMWorld extensions
# ------------------------------------------------------------------


class TestSCMWorldExtensions:
    """Test id, latent_variables, and get_all_backdoor_adjustment_sets."""

    def test_id_field(self):
        world = _linear_chain()
        assert world.id == "test-linear"

    def test_default_id_empty(self):
        world = SCMWorld(
            graph={"A": []},
            equations={"A": lambda p, rng: rng.normal(0, 1)},
        )
        assert world.id == ""

    def test_latent_variables_field(self):
        world = _with_latent()
        assert world.latent_variables == {"L"}

    def test_observable_variables(self):
        world = _with_latent()
        obs = world.observable_variables
        assert "L" not in obs
        assert set(obs) == {"A", "B", "C"}

    def test_latent_validation_fails(self):
        with pytest.raises(ValueError, match="Latent variables not in graph"):
            SCMWorld(
                graph={"A": []},
                equations={"A": lambda p, rng: 0.0},
                latent_variables={"Z"},
            )

    def test_backdoor_no_confounding(self):
        """A -> B -> C. No backdoor path from A to C, empty set valid."""
        world = _linear_chain()
        sets = world.get_all_backdoor_adjustment_sets("A", "C")
        assert frozenset() in sets

    def test_backdoor_with_confounding(self):
        """C -> A -> Y, C -> Y. C confounds A->Y. Adjustment set = {C}."""
        world = _confounder_world()
        sets = world.get_all_backdoor_adjustment_sets("A", "Y")
        assert len(sets) >= 1
        # {C} should be a valid minimal set
        assert any(frozenset({"C"}) == s or frozenset({"C"}).issubset(s) for s in sets)

    def test_backdoor_not_identifiable(self):
        """L (latent) -> A, L -> Y. No observable confounder adjustment."""
        world = SCMWorld(
            id="test-unid",
            graph={"L": [], "A": ["L"], "Y": ["L", "A"]},
            equations={
                "L": lambda p, rng: rng.normal(0, 1),
                "A": lambda p, rng: p["L"] + rng.normal(0, 1),
                "Y": lambda p, rng: p["A"] + p["L"] + rng.normal(0, 1),
            },
        )
        sets = world.get_all_backdoor_adjustment_sets("A", "Y")
        # L is the only valid adjustment variable but it might not
        # satisfy the criterion depending on graph structure
        # The key test is that it doesn't crash
        assert isinstance(sets, list)


# ------------------------------------------------------------------
# Task generation tests
# ------------------------------------------------------------------


class TestInferTarget:
    def test_generates_task(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        assert task.type == TaskType.INFER_TARGET
        assert task.target_node == "C"
        assert task.world_id == "test-linear"
        assert task.scoring_method == "kl_divergence"

    def test_correct_answer_is_histogram(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        # Keys should be bin ranges like "[x.xx, y.yy)"
        for key in task.correct_answer:
            assert key.startswith("[")
            assert "," in key

        # Values should sum to ~1.0
        total = sum(task.correct_answer.values())
        assert abs(total - 1.0) < 0.01

    def test_question_mentions_bins(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        # Question should reference the bin ranges
        assert "[" in task.question
        assert "C" in task.question


class TestNextBestObservation:
    def test_generates_task(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.NEXT_BEST_OBSERVATION, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        assert task.type == TaskType.NEXT_BEST_OBSERVATION
        assert task.scoring_method == "info_gain_ratio"

    def test_ig_ranking_has_positive_values(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.NEXT_BEST_OBSERVATION, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        # At least one node should have IG > 0 (B is connected to C)
        assert any(v > 0 for v in task.correct_answer.values())

    def test_given_evidence_are_strings(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.NEXT_BEST_OBSERVATION, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        # given_evidence values should be string-formatted floats
        for v in task.given_evidence.values():
            assert isinstance(v, str)
            float(v)  # should be parseable


class TestHypothesisSelection:
    def test_generates_task(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.HYPOTHESIS_SELECTION, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        assert task.type == TaskType.HYPOTHESIS_SELECTION
        assert task.scoring_method == "hypothesis_accuracy"

    def test_has_four_hypotheses(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.HYPOTHESIS_SELECTION, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        assert len(task.hypotheses) == 4
        assert set(task.hypotheses.keys()) == {"A", "B", "C", "D"}

    def test_kl_scores_have_zero(self):
        """One hypothesis should be the true posterior (KL=0)."""
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.HYPOTHESIS_SELECTION, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        # The correct hypothesis has KL=0 (or very close)
        min_kl = min(task.correct_answer.values())
        assert min_kl < 0.01


class TestCausalEffect:
    def test_generates_task(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.CAUSAL_EFFECT, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        assert task.type == TaskType.CAUSAL_EFFECT
        assert task.scoring_method == "kl_divergence"

    def test_correct_answer_is_histogram(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.CAUSAL_EFFECT, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        total = sum(task.correct_answer.values())
        assert abs(total - 1.0) < 0.01

    def test_intervention_is_string_float(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.CAUSAL_EFFECT, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        assert len(task.intervention) == 1
        for v in task.intervention.values():
            float(v)  # parseable as float

    def test_hint_respected(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.CAUSAL_EFFECT,
            target_node="C",
            max_budget=5,
            intervention_node="A",
        )
        task = gen.generate(world, spec, seed=42)
        assert "A" in task.intervention


class TestBestIntervention:
    def test_generates_task(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.BEST_INTERVENTION, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        assert task.type == TaskType.BEST_INTERVENTION
        assert task.scoring_method == "intervention_effect_ratio"

    def test_effects_are_probabilities(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.BEST_INTERVENTION, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        for v in task.correct_answer.values():
            assert 0.0 <= v <= 1.0

    def test_keys_have_low_high(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.BEST_INTERVENTION, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        for key in task.correct_answer:
            _, label = key.split(":", 1)
            assert label in ("low", "high")


class TestCompareInterventions:
    def test_generates_task(self):
        world = _confounder_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.COMPARE_INTERVENTIONS, target_node="Y", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        assert task.type == TaskType.COMPARE_INTERVENTIONS
        assert task.scoring_method == "compare_interventions"
        assert len(task.correct_answer) == 2

    def test_scoring_compatible(self):
        """VerifierTool.score_compare_interventions should work."""
        world = _confounder_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.COMPARE_INTERVENTIONS, target_node="Y", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        verifier = VerifierTool()
        keys = list(task.correct_answer.keys())
        effects = task.correct_answer

        # Agent picks the better one
        better = "A" if effects[keys[0]] >= effects[keys[1]] else "B"
        score = verifier.score_compare_interventions(better, effects)
        assert score == 1.0


class TestShouldCondition:
    def test_generates_task(self):
        world = _confounder_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.SHOULD_CONDITION, target_node="Y", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        assert task.type == TaskType.SHOULD_CONDITION
        assert task.scoring_method == "should_condition"

    def test_answer_yes_or_no(self):
        world = _confounder_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.SHOULD_CONDITION, target_node="Y", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        assert set(task.correct_answer.keys()).issubset({"yes", "no"})

    def test_confounder_yes(self):
        """Conditioning on confounder C should be 'yes' for A->Y."""
        world = _confounder_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.SHOULD_CONDITION,
            target_node="Y",
            max_budget=5,
            intervention_node="A",
            condition_variable="C",
        )
        task = gen.generate(world, spec, seed=42)
        assert "yes" in task.correct_answer

    def test_descendant_no(self):
        """Conditioning on descendant D should be 'no' for A->Y."""
        world = _confounder_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.SHOULD_CONDITION,
            target_node="Y",
            max_budget=5,
            intervention_node="A",
            condition_variable="D",
        )
        task = gen.generate(world, spec, seed=42)
        assert "no" in task.correct_answer


class TestAdjustmentSet:
    def test_generates_task(self):
        world = _confounder_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.ADJUSTMENT_SET, target_node="Y", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        assert task.type == TaskType.ADJUSTMENT_SET
        assert task.scoring_method == "adjustment_set_match"

    def test_confounded_has_valid_set(self):
        """For A->Y with confounder C, adjustment set should include C."""
        world = _confounder_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.ADJUSTMENT_SET,
            target_node="Y",
            max_budget=5,
            intervention_node="A",
        )
        task = gen.generate(world, spec, seed=42)

        # Should have a valid set containing C
        assert any("C" in k for k in task.correct_answer.keys())


class TestInferLatentCause:
    def test_generates_task(self):
        world = _with_latent()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.INFER_LATENT_CAUSE, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        assert task.type == TaskType.INFER_LATENT_CAUSE
        assert task.target_node == "L"  # should pick the latent node
        assert task.scoring_method == "kl_divergence"

    def test_correct_answer_is_histogram(self):
        world = _with_latent()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.INFER_LATENT_CAUSE, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        total = sum(task.correct_answer.values())
        assert abs(total - 1.0) < 0.01

    def test_no_latent_raises(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.INFER_LATENT_CAUSE, target_node="C", max_budget=5)
        with pytest.raises(ValueError, match="no latent"):
            gen.generate(world, spec, seed=42)


class TestGenerateAll:
    def test_generates_bundle(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        bundle = gen.generate_all(world, target_node="C", seed=42)

        assert bundle.world_id == "test-linear"
        assert bundle.target_node == "C"
        assert TaskType.INFER_TARGET in bundle.tasks
        assert TaskType.NEXT_BEST_OBSERVATION in bundle.tasks
        assert TaskType.HYPOTHESIS_SELECTION in bundle.tasks


class TestScoringCompatibility:
    """Verify generated tasks can be scored by VerifierTool."""

    def test_kl_divergence_on_histogram(self):
        """VerifierTool.kl_divergence works with bin-range keys."""
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        verifier = VerifierTool()
        # Perfect answer = itself
        kl = verifier.kl_divergence(task.correct_answer, task.correct_answer)
        assert kl < 0.001

        # Uniform answer should have higher KL
        n_bins = len(task.correct_answer)
        uniform = {k: 1.0 / n_bins for k in task.correct_answer}
        kl_uniform = verifier.kl_divergence(uniform, task.correct_answer)
        assert kl_uniform > 0.0

    def test_nbo_scoring(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.NEXT_BEST_OBSERVATION, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        verifier = VerifierTool()
        best_node = max(task.correct_answer, key=task.correct_answer.get)
        score = verifier.score_nbo(best_node, task.correct_answer)
        assert score == 1.0

    def test_best_intervention_scoring(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.BEST_INTERVENTION, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)

        verifier = VerifierTool()
        best_key = max(task.correct_answer, key=task.correct_answer.get)
        node, state = best_key.split(":", 1)
        score = verifier.score_best_intervention(node, state, task.correct_answer)
        assert score == 1.0


class TestCrossTaskConsistency:
    """Cross-task checks within the same world."""

    def test_infer_target_and_causal_effect_use_same_bins(self):
        """Both distribution tasks should use compatible bin formats."""
        world = _linear_chain()
        gen = SCMTaskGenTool()

        infer = gen.generate(
            world,
            TaskSpec(type=TaskType.INFER_TARGET, target_node="C", max_budget=5),
            seed=42,
        )
        causal = gen.generate(
            world,
            TaskSpec(type=TaskType.CAUSAL_EFFECT, target_node="C", max_budget=5),
            seed=42,
        )

        # Both should have bin-range keys
        for key in infer.correct_answer:
            assert key.startswith("[")
        for key in causal.correct_answer:
            assert key.startswith("[")

    def test_all_nine_types_generate(self):
        """All 9 eval types should generate without errors."""
        world = _confounder_world()
        world_latent = _with_latent()
        gen = SCMTaskGenTool()

        # Types that work with the confounder world
        for tt in [
            TaskType.INFER_TARGET,
            TaskType.NEXT_BEST_OBSERVATION,
            TaskType.HYPOTHESIS_SELECTION,
            TaskType.CAUSAL_EFFECT,
            TaskType.BEST_INTERVENTION,
            TaskType.COMPARE_INTERVENTIONS,
            TaskType.SHOULD_CONDITION,
            TaskType.ADJUSTMENT_SET,
        ]:
            spec = TaskSpec(type=tt, target_node="Y", max_budget=5)
            task = gen.generate(world, spec, seed=42)
            assert task.type == tt, f"Failed for {tt}"

        # Latent cause needs latent variables
        spec = TaskSpec(type=TaskType.INFER_LATENT_CAUSE, target_node="C", max_budget=5)
        task = gen.generate(world_latent, spec, seed=42)
        assert task.type == TaskType.INFER_LATENT_CAUSE


# ------------------------------------------------------------------
# Test worlds for new primitives
# ------------------------------------------------------------------


def _mediation_world() -> SCMWorld:
    """T -> M -> Y + T -> Y. Partial mediation."""
    return SCMWorld(
        id="test-mediation",
        graph={"T": [], "M": ["T"], "Y": ["T", "M"]},
        equations={
            "T": lambda p, rng: rng.normal(10, 2),
            "M": lambda p, rng: 1.0 * p["T"] + rng.normal(0, 0.5),
            "Y": lambda p, rng: 0.5 * p["T"] + 1.0 * p["M"] + rng.normal(0, 0.5),
        },
    )


def _interaction_world() -> SCMWorld:
    """T -> Y, Z -> Y with interaction: Y = T * Z + noise."""
    return SCMWorld(
        id="test-interaction",
        graph={"T": [], "Z": [], "Y": ["T", "Z"]},
        equations={
            "T": lambda p, rng: rng.normal(5, 1),
            "Z": lambda p, rng: rng.normal(3, 1),
            "Y": lambda p, rng: p["T"] * p["Z"] + rng.normal(0, 0.5),
        },
    )


# ------------------------------------------------------------------
# ATE
# ------------------------------------------------------------------


class TestATE:
    def test_generates_task(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.ATE, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)
        assert task.type == TaskType.ATE
        assert task.scoring_method == "numeric_relative_error"

    def test_correct_answer_has_value_key(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.ATE, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)
        assert "value" in task.correct_answer
        assert isinstance(task.correct_answer["value"], float)

    def test_estimand_populated(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.ATE, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)
        assert task.estimand["type"] == "ate"
        assert "treatment" in task.estimand
        assert "outcome" in task.estimand
        assert isinstance(task.estimand["v_low"], float)
        assert isinstance(task.estimand["v_high"], float)

    def test_question_is_natural(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.ATE, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)
        assert "Submit" not in task.question
        assert "->" not in task.question

    def test_respects_intervention_node_hint(self):
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.ATE, target_node="C", max_budget=5,
            intervention_node="A",
        )
        task = gen.generate(world, spec, seed=42)
        assert "A" in task.intervention


# ------------------------------------------------------------------
# Mediation
# ------------------------------------------------------------------


class TestMediation:
    def test_generates_task(self):
        world = _mediation_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.MEDIATION, target_node="Y", max_budget=5,
            intervention_node="T", condition_variable="M",
        )
        task = gen.generate(world, spec, seed=42)
        assert task.type == TaskType.MEDIATION
        assert task.scoring_method == "numeric_relative_error"

    def test_fraction_bounded(self):
        world = _mediation_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.MEDIATION, target_node="Y", max_budget=5,
            intervention_node="T", condition_variable="M",
        )
        task = gen.generate(world, spec, seed=42)
        frac = task.correct_answer["value"]
        assert 0.0 <= frac <= 1.0

    def test_estimand_populated(self):
        world = _mediation_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.MEDIATION, target_node="Y", max_budget=5,
            intervention_node="T", condition_variable="M",
        )
        task = gen.generate(world, spec, seed=42)
        assert task.estimand["type"] == "mediation"
        assert task.estimand["mediator"] == "M"
        assert task.estimand["treatment"] == "T"
        assert task.estimand["outcome"] == "Y"

    def test_question_is_natural(self):
        world = _mediation_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.MEDIATION, target_node="Y", max_budget=5,
            intervention_node="T", condition_variable="M",
        )
        task = gen.generate(world, spec, seed=42)
        assert "Submit" not in task.question
        assert "between 0 and 1" not in task.question

    def test_raises_without_mediator(self):
        """Independent world has no directed paths."""
        world = _independent()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.MEDIATION, target_node="B", max_budget=5)
        with pytest.raises(ValueError, match="No mediator"):
            gen.generate(world, spec, seed=42)


# ------------------------------------------------------------------
# Interaction
# ------------------------------------------------------------------


class TestInteraction:
    def test_generates_task(self):
        world = _interaction_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.INTERACTION, target_node="Y", max_budget=5,
            intervention_node="T", condition_variable="Z",
        )
        task = gen.generate(world, spec, seed=42)
        assert task.type == TaskType.INTERACTION
        assert task.scoring_method == "should_condition"

    def test_correct_answer_is_yes_or_no(self):
        world = _interaction_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.INTERACTION, target_node="Y", max_budget=5,
            intervention_node="T", condition_variable="Z",
        )
        task = gen.generate(world, spec, seed=42)
        assert set(task.correct_answer.keys()).issubset({"yes", "no"})

    def test_estimand_populated(self):
        world = _interaction_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.INTERACTION, target_node="Y", max_budget=5,
            intervention_node="T", condition_variable="Z",
        )
        task = gen.generate(world, spec, seed=42)
        assert task.estimand["type"] == "interaction"
        assert task.estimand["modifier"] == "Z"
        assert task.estimand["treatment"] == "T"

    def test_respects_hints(self):
        world = _interaction_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.INTERACTION, target_node="Y", max_budget=5,
            intervention_node="T", condition_variable="Z",
        )
        task = gen.generate(world, spec, seed=42)
        assert "T" in task.intervention
        assert task.intervention["T"] == "Z"


# ------------------------------------------------------------------
# _semantic_name threshold
# ------------------------------------------------------------------


class TestSemanticName:
    def test_short_description_used(self):
        """Descriptions under 45 chars and <=6 words are used."""
        world = SCMWorld(
            id="test-sem",
            graph={"X": [], "Y": ["X"]},
            equations={
                "X": lambda p, rng: rng.normal(0, 1),
                "Y": lambda p, rng: p["X"] + rng.normal(0, 1),
            },
            variable_meta={"X": VariableMeta(description="birth weight", unit="kg")},
        )
        name = SCMTaskGenTool._semantic_name(world, "X")
        assert name == "birth weight"

    def test_long_description_rejected(self):
        """Descriptions >=45 chars fall back to node_id with spaces."""
        world = SCMWorld(
            id="test-sem",
            graph={"fixture_density": [], "Y": ["fixture_density"]},
            equations={
                "fixture_density": lambda p, rng: rng.normal(0, 1),
                "Y": lambda p, rng: p["fixture_density"] + rng.normal(0, 1),
            },
            variable_meta={
                "fixture_density": VariableMeta(
                    description=(
                        "Density of competitive fixtures faced by a "
                        "club over recent match windows"
                    ),
                ),
            },
        )
        name = SCMTaskGenTool._semantic_name(world, "fixture_density")
        assert name == "fixture density"  # fallback, not the 70-char description

    def test_too_many_words_rejected(self):
        """Descriptions with >6 words fall back even if under 45 chars."""
        world = SCMWorld(
            id="test-sem",
            graph={"X": [], "Y": ["X"]},
            equations={
                "X": lambda p, rng: rng.normal(0, 1),
                "Y": lambda p, rng: p["X"] + rng.normal(0, 1),
            },
            variable_meta={
                "X": VariableMeta(description="a b c d e f g"),  # 7 words, 13 chars
            },
        )
        name = SCMTaskGenTool._semantic_name(world, "X")
        assert name == "X"  # fallback to node_id (no underscore)

    def test_no_meta_uses_node_id(self):
        world = _linear_chain()
        name = SCMTaskGenTool._semantic_name(world, "A")
        assert name == "A"


# ------------------------------------------------------------------
# _sanitize_question_text
# ------------------------------------------------------------------


class TestSanitizeQuestionText:
    def test_known_node_ids_replaced(self):
        """Snake_case node_ids in the world are replaced with spaces."""
        world = SCMWorld(
            id="test-san",
            graph={"birth_weight": [], "maternal_smoking": ["birth_weight"]},
            equations={
                "birth_weight": lambda p, rng: rng.normal(3, 0.5),
                "maternal_smoking": lambda p, rng: rng.normal(0, 1),
            },
        )
        text = "What is the effect of maternal_smoking on birth_weight?"
        result = SCMTaskGenTool._sanitize_question_text(text, world)
        assert "maternal_smoking" not in result
        assert "birth_weight" not in result
        assert "maternal smoking" in result
        assert "birth weight" in result

    def test_unknown_snake_case_also_sanitized(self):
        """Snake_case tokens not in the world are caught by generic fallback."""
        world = _linear_chain()  # only has A, B, C (no underscores)
        text = "The p_value suggests sample_size matters."
        result = SCMTaskGenTool._sanitize_question_text(text, world)
        assert "p_value" not in result
        assert "p value" in result
        assert "sample_size" not in result
        assert "sample size" in result

    def test_no_false_positives_on_normal_text(self):
        """Normal text without snake_case passes through unchanged."""
        world = _linear_chain()
        text = "How does variable A affect the outcome?"
        result = SCMTaskGenTool._sanitize_question_text(text, world)
        assert result == text

    def test_longer_node_id_matched_first(self):
        """Longer node_ids are replaced before shorter overlapping ones."""
        world = SCMWorld(
            id="test-san",
            graph={"air_quality": [], "air_quality_index": ["air_quality"]},
            equations={
                "air_quality": lambda p, rng: rng.normal(50, 10),
                "air_quality_index": lambda p, rng: p["air_quality"] * 2,
            },
        )
        text = "Check the air_quality_index and air_quality."
        result = SCMTaskGenTool._sanitize_question_text(text, world)
        assert "air quality index" in result
        assert "air quality" in result
        assert "_" not in result


# ------------------------------------------------------------------
# ATE template phrasing
# ------------------------------------------------------------------


class TestATETemplate:
    def test_no_shifted_phrasing(self):
        """ATE template should not contain the old mechanical phrasing."""
        world = _linear_chain()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.ATE, target_node="C", max_budget=5)
        task = gen.generate(world, spec, seed=42)
        assert "shifted from a low" not in task.question
        assert "What fraction of the causal" not in task.question

    def test_template_rotation(self):
        """Different seeds produce different phrasings."""
        world = _linear_chain()
        gen = SCMTaskGenTool()
        questions = set()
        for s in range(6):
            spec = TaskSpec(type=TaskType.ATE, target_node="C", max_budget=5)
            task = gen.generate(world, spec, seed=s)
            questions.add(task.question)
        assert len(questions) >= 2, "Templates should rotate across seeds"


class TestMediationTemplate:
    def test_no_textbook_phrasing(self):
        """Mediation template should sound like a researcher, not a textbook."""
        world = _mediation_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.MEDIATION, target_node="Y", max_budget=5,
            intervention_node="T", condition_variable="M",
        )
        task = gen.generate(world, spec, seed=42)
        assert "What fraction of the causal effect" not in task.question
        assert "proportion of the total effect" not in task.question


class TestInteractionTemplate:
    def test_no_textbook_phrasing(self):
        """Interaction template should sound like a researcher."""
        world = _interaction_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.INTERACTION, target_node="Y", max_budget=5,
            intervention_node="T", condition_variable="Z",
        )
        task = gen.generate(world, spec, seed=42)
        assert "In other words" not in task.question


# ------------------------------------------------------------------
# Entity match checks outcome for compare_interventions
# ------------------------------------------------------------------


class TestEntityMatchCompareInterventions:
    def test_outcome_present_in_question(self):
        """Entity check requires outcome (target) to be mentioned."""
        from sreg.models.task import Task

        world = _linear_chain()
        task = Task(
            id="t1",
            type=TaskType.COMPARE_INTERVENTIONS,
            world_id="test",
            question="Which helps C more: changing A or B?",
            target_node="C",
            available_evidence=["A", "B", "C"],
            correct_answer={"A:high": 0.6, "B:low": 0.4},
            scoring_method="compare_interventions",
            estimand={
                "type": "compare_interventions",
                "option_a": "A",
                "label_a": "high",
                "option_b": "B",
                "label_b": "low",
                "outcome": "C",
            },
        )
        assert SCMTaskGenTool._entities_match_question(
            task.question, task, world=world
        )

    def test_wrong_outcome_rejected(self):
        """If the question mentions a different outcome, check fails."""
        from sreg.models.task import Task

        world = _linear_chain()
        task = Task(
            id="t1",
            type=TaskType.COMPARE_INTERVENTIONS,
            world_id="test",
            question="Which helps A more: changing A or B?",
            target_node="C",
            available_evidence=["A", "B", "C"],
            correct_answer={"A:high": 0.6, "B:low": 0.4},
            scoring_method="compare_interventions",
            estimand={
                "type": "compare_interventions",
                "option_a": "A",
                "label_a": "high",
                "option_b": "B",
                "label_b": "low",
                "outcome": "Z_missing",  # not in question
            },
        )
        assert not SCMTaskGenTool._entities_match_question(
            task.question, task, world=world
        )


# ------------------------------------------------------------------
# _hints_honored for best_intervention (no desired_state needed)
# ------------------------------------------------------------------


class TestHintsHonoredBestIntervention:
    def test_best_intervention_always_honored(self):
        """best_intervention needs no hints — always honored."""
        from sreg.models.case_plan import EvalQuestionPlan
        from sreg.models.task import Task

        task = Task(
            id="t1",
            type=TaskType.BEST_INTERVENTION,
            world_id="test",
            question="Which single change maximizes C?",
            target_node="C",
            available_evidence=["A", "B", "C"],
            correct_answer={"A:high": 0.7, "B:low": 0.3},
            scoring_method="intervention_effect_ratio",
            intervention={"A": "high"},
        )
        plan = EvalQuestionPlan(
            question_text="What's the best lever for C?",
            eval_type=TaskType.BEST_INTERVENTION,
            target_node="C",
            # No desired_state — should still work
        )
        assert SCMTaskGenTool._hints_honored(plan, task)


# ------------------------------------------------------------------
# Quality gates (Paso 2)
# ------------------------------------------------------------------


def _downstream_world() -> SCMWorld:
    """A -> B -> C -> D. D is target, B and C are downstream of A.

    For best_intervention on D: only A, B, C are valid levers (ancestors).
    D itself is the target and should be excluded.
    """
    return SCMWorld(
        id="test-downstream",
        graph={"A": [], "B": ["A"], "C": ["B"], "D": ["C"]},
        equations={
            "A": lambda p, rng: rng.normal(10, 2),
            "B": lambda p, rng: 0.8 * p["A"] + rng.normal(0, 1),
            "C": lambda p, rng: 0.5 * p["B"] + rng.normal(0, 1),
            "D": lambda p, rng: 0.3 * p["C"] + rng.normal(0, 0.5),
        },
    )


def _with_descendant_of_target() -> SCMWorld:
    """A -> B -> Y, Y -> D.

    D is a descendant of Y (target).
    Should NOT be offered as a lever.
    """
    return SCMWorld(
        id="test-desc-target",
        graph={"A": [], "B": ["A"], "Y": ["B"], "D": ["Y"]},
        equations={
            "A": lambda p, rng: rng.normal(10, 2),
            "B": lambda p, rng: 0.5 * p["A"] + rng.normal(0, 1),
            "Y": lambda p, rng: 0.3 * p["B"] + rng.normal(0, 1),
            "D": lambda p, rng: 0.8 * p["Y"] + rng.normal(0, 0.5),
        },
    )


def _no_interaction_world() -> SCMWorld:
    """T -> Y, Z -> Y with additive equation (no interaction)."""
    return SCMWorld(
        id="test-no-interaction",
        graph={"T": [], "Z": [], "Y": ["T", "Z"]},
        equations={
            "T": lambda p, rng: rng.normal(5, 1),
            "Z": lambda p, rng: rng.normal(3, 1),
            "Y": lambda p, rng: 2 * p["T"] + 1.5 * p["Z"] + rng.normal(0, 0.5),
        },
    )


def _full_mediation_world() -> SCMWorld:
    """T -> M -> Y (no direct T -> Y path). Mediation = 100%."""
    return SCMWorld(
        id="test-full-mediation",
        graph={"T": [], "M": ["T"], "Y": ["M"]},
        equations={
            "T": lambda p, rng: rng.normal(10, 2),
            "M": lambda p, rng: 1.5 * p["T"] + rng.normal(0, 0.5),
            "Y": lambda p, rng: 0.8 * p["M"] + rng.normal(0, 0.5),
        },
    )


class TestManipulabilityGate:
    """Only causal ancestors of target should be offered as levers."""

    def test_manipulable_nodes_returns_ancestors(self):
        world = _downstream_world()
        gen = SCMTaskGenTool()
        levers = gen._manipulable_nodes(world, "D")
        assert "A" in levers
        assert "B" in levers
        assert "C" in levers
        assert "D" not in levers

    def test_descendant_of_target_excluded(self):
        world = _with_descendant_of_target()
        gen = SCMTaskGenTool()
        levers = gen._manipulable_nodes(world, "Y")
        assert "A" in levers
        assert "B" in levers
        assert "D" not in levers  # D is downstream of Y

    def test_best_intervention_excludes_downstream(self):
        world = _with_descendant_of_target()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.BEST_INTERVENTION, target_node="Y", max_budget=5)
        task = gen.generate(world, spec, seed=42)
        # Answer keys should only contain ancestors
        for key in task.correct_answer:
            node = key.split(":")[0]
            assert node in ("A", "B", "_none_"), f"Unexpected lever: {node}"

    def test_compare_interventions_uses_ancestors(self):
        world = _downstream_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.COMPARE_INTERVENTIONS, target_node="D",
            compare_nodes=["A", "B"], max_budget=5,
        )
        task = gen.generate(world, spec, seed=42)
        nodes_in_answer = {k.split(":")[0] for k in task.correct_answer}
        assert "D" not in nodes_in_answer

    def test_compare_needs_two_ancestors(self):
        """World with only 1 ancestor should raise."""
        world = SCMWorld(
            id="test-single-parent",
            graph={"X": [], "Y": ["X"]},
            equations={
                "X": lambda p, rng: rng.normal(0, 1),
                "Y": lambda p, rng: p["X"] + rng.normal(0, 0.5),
            },
        )
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.COMPARE_INTERVENTIONS, target_node="Y", max_budget=5)
        with pytest.raises(ValueError, match="at least 2"):
            gen.generate(world, spec, seed=42)


class TestInteractionGate:
    """Interaction tasks should only be generated when real interaction exists."""

    def test_interaction_found_in_multiplicative_world(self):
        world = _interaction_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.INTERACTION, target_node="Y", max_budget=5,
            intervention_node="T", condition_variable="Z",
        )
        task = gen.generate(world, spec, seed=42)
        assert task.correct_answer == {"yes": 1.0}

    def test_no_interaction_answers_no(self):
        """Purely additive world should generate task with answer 'no'."""
        world = _no_interaction_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.INTERACTION, target_node="Y", max_budget=5,
            intervention_node="T", condition_variable="Z",
        )
        task = gen.generate(world, spec, seed=42)
        assert task.correct_answer == {"no": 1.0}

    def test_no_interaction_without_hints_answers_no(self):
        """Even without hints, additive world should answer 'no'."""
        world = _no_interaction_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.INTERACTION, target_node="Y", max_budget=5)
        task = gen.generate(world, spec, seed=42)
        assert task.correct_answer == {"no": 1.0}


class TestMediationGate:
    """Mediation tasks should only be generated when fraction is non-trivial."""

    def test_partial_mediation_succeeds(self):
        """T -> M -> Y + T -> Y: partial mediation should pass gate."""
        world = _mediation_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.MEDIATION, target_node="Y", max_budget=5,
            intervention_node="T", condition_variable="M",
        )
        task = gen.generate(world, spec, seed=42)
        frac = task.correct_answer["value"]
        assert 0.05 < frac < 0.95, f"Expected partial mediation, got {frac}"

    def test_full_mediation_raises(self):
        """T -> M -> Y (no direct): fraction ~1.0 should be rejected."""
        world = _full_mediation_world()
        gen = SCMTaskGenTool()
        spec = TaskSpec(
            type=TaskType.MEDIATION, target_node="Y", max_budget=5,
            intervention_node="T", condition_variable="M",
        )
        with pytest.raises(ValueError, match="trivial"):
            gen.generate(world, spec, seed=42)

    def test_raises_without_mediator(self):
        """Independent world has no directed paths."""
        world = _independent()
        gen = SCMTaskGenTool()
        spec = TaskSpec(type=TaskType.MEDIATION, target_node="B", max_budget=5)
        with pytest.raises(ValueError, match="No mediator"):
            gen.generate(world, spec, seed=42)
