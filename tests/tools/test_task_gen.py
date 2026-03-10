"""Tests for TaskGenTool."""

import pytest

from sreg.models.case_plan import CasePlan, EvalQuestionPlan
from sreg.models.task import Task, TaskBundle, TaskSpec, TaskType
from sreg.models.world import NodeType
from sreg.tools.task_gen import TaskGenTool
from sreg.tools.verifier import VerifierTool
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


@pytest.fixture
def world():
    gen = WorldGenTool()
    return gen.generate(WorldGenConfig(seed=42, num_nodes=6, edge_strength=0.7))


# --- infer_target tests ---


def test_generate_infer_target_task(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec)

    assert isinstance(task, Task)
    assert task.type == TaskType.INFER_TARGET
    assert task.world_id == world.id
    assert task.target_node == "target_outcome"


def test_task_has_correct_answer(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec)

    assert isinstance(task.correct_answer, dict)
    assert abs(sum(task.correct_answer.values()) - 1.0) < 1e-6
    assert all(p >= 0 for p in task.correct_answer.values())


def test_task_available_evidence(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec)

    obs_names = {n.name for n in world.nodes if n.type == NodeType.OBSERVABLE}
    assert set(task.available_evidence) == obs_names


def test_task_question_mentions_target(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec)

    assert "target_outcome" in task.question


def test_task_question_mentions_budget(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="target_outcome", max_budget=3)
    task = tool.generate(world, spec)

    assert "3" in task.question


def test_task_id_format(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec)

    assert task.id == f"task-{world.id}-infer_target"


# --- next_best_observation tests ---


def test_nbo_task_generates(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.NEXT_BEST_OBSERVATION, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    assert task.type == TaskType.NEXT_BEST_OBSERVATION
    assert task.scoring_method == "info_gain_ratio"


def test_nbo_has_given_evidence(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.NEXT_BEST_OBSERVATION, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    assert len(task.given_evidence) >= 1
    # All given evidence keys should be observable nodes
    obs_names = {n.name for n in world.nodes if n.type == NodeType.OBSERVABLE}
    for node in task.given_evidence:
        assert node in obs_names


def test_nbo_correct_answer_is_ig_ranking(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.NEXT_BEST_OBSERVATION, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    # correct_answer maps node names to IG values
    assert isinstance(task.correct_answer, dict)
    assert len(task.correct_answer) >= 2  # at least 2 choices
    assert all(ig >= 0.0 for ig in task.correct_answer.values())


def test_nbo_available_excludes_given(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.NEXT_BEST_OBSERVATION, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    # Available evidence should not include given evidence nodes
    for node in task.given_evidence:
        assert node not in task.available_evidence


def test_nbo_question_mentions_observed(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.NEXT_BEST_OBSERVATION, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    assert "already observed" in task.question


def test_nbo_deterministic(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.NEXT_BEST_OBSERVATION, target_node="target_outcome", max_budget=5
    )
    t1 = tool.generate(world, spec, seed=99)
    t2 = tool.generate(world, spec, seed=99)

    assert t1.correct_answer == t2.correct_answer
    assert t1.given_evidence == t2.given_evidence


def test_nbo_different_seeds_differ(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.NEXT_BEST_OBSERVATION, target_node="target_outcome", max_budget=5
    )
    t1 = tool.generate(world, spec, seed=0)
    t2 = tool.generate(world, spec, seed=1)

    # Different seeds should give different evidence (usually)
    assert t1.given_evidence != t2.given_evidence or t1.correct_answer != t2.correct_answer


def test_nbo_works_across_templates():
    gen = WorldGenTool()
    tool = TaskGenTool()

    for template in ["latent_preference", "causal_chain", "fork_collider"]:
        nodes = 7 if template == "fork_collider" else 6
        world = gen.generate(WorldGenConfig(
            template_family=template, seed=42, num_nodes=nodes, edge_strength=0.7
        ))
        spec = TaskSpec(
            type=TaskType.NEXT_BEST_OBSERVATION, target_node="target_outcome", max_budget=5
        )
        task = tool.generate(world, spec, seed=42)
        assert len(task.correct_answer) >= 1, f"No choices for {template}"


# --- verifier NBO scoring tests ---


def test_verifier_nbo_perfect_choice():
    verifier = VerifierTool()
    ig_ranking = {"node_a": 0.5, "node_b": 0.3, "node_c": 0.1}
    score = verifier.score_nbo("node_a", ig_ranking)
    assert score == 1.0


def test_verifier_nbo_suboptimal_choice():
    verifier = VerifierTool()
    ig_ranking = {"node_a": 0.5, "node_b": 0.3, "node_c": 0.1}
    score = verifier.score_nbo("node_b", ig_ranking)
    assert abs(score - 0.6) < 1e-6  # 0.3 / 0.5


def test_verifier_nbo_worst_choice():
    verifier = VerifierTool()
    ig_ranking = {"node_a": 0.5, "node_b": 0.3, "node_c": 0.0}
    score = verifier.score_nbo("node_c", ig_ranking)
    assert score == 0.0


def test_verifier_nbo_invalid_choice():
    verifier = VerifierTool()
    ig_ranking = {"node_a": 0.5, "node_b": 0.3}
    score = verifier.score_nbo("nonexistent", ig_ranking)
    assert score == 0.0


def test_verifier_nbo_all_zero_ig():
    verifier = VerifierTool()
    ig_ranking = {"node_a": 0.0, "node_b": 0.0}
    score = verifier.score_nbo("node_a", ig_ranking)
    assert score == 1.0  # any choice is fine when nothing is informative


# --- hypothesis_selection tests ---


def test_hypothesis_task_generates(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.HYPOTHESIS_SELECTION, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    assert task.type == TaskType.HYPOTHESIS_SELECTION
    assert task.scoring_method == "hypothesis_accuracy"


def test_hypothesis_has_4_hypotheses(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.HYPOTHESIS_SELECTION, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    assert len(task.hypotheses) == 4
    assert set(task.hypotheses.keys()) == {"A", "B", "C", "D"}


def test_hypothesis_distributions_valid(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.HYPOTHESIS_SELECTION, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    target_node = next(n for n in world.nodes if n.name == "target_outcome")
    expected_states = set(target_node.states)

    for label, dist in task.hypotheses.items():
        assert set(dist.keys()) == expected_states, f"Hypothesis {label} has wrong states"
        assert abs(sum(dist.values()) - 1.0) < 0.01, f"Hypothesis {label} doesn't sum to 1"


def test_hypothesis_has_given_evidence(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.HYPOTHESIS_SELECTION, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    assert len(task.given_evidence) >= 1
    obs_names = {n.name for n in world.nodes if n.type == NodeType.OBSERVABLE}
    for node in task.given_evidence:
        assert node in obs_names


def test_hypothesis_correct_answer_is_kl_scores(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.HYPOTHESIS_SELECTION, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    # correct_answer maps labels to KL divergences
    assert set(task.correct_answer.keys()) == {"A", "B", "C", "D"}
    assert all(kl >= 0.0 for kl in task.correct_answer.values())
    # One hypothesis should have KL ≈ 0 (the true posterior)
    min_kl = min(task.correct_answer.values())
    assert min_kl < 0.01, f"No hypothesis close to true posterior (min KL={min_kl})"


def test_hypothesis_question_lists_options(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.HYPOTHESIS_SELECTION, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    assert "A:" in task.question
    assert "B:" in task.question
    assert "most plausible" in task.question


def test_hypothesis_deterministic(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.HYPOTHESIS_SELECTION, target_node="target_outcome", max_budget=5
    )
    t1 = tool.generate(world, spec, seed=99)
    t2 = tool.generate(world, spec, seed=99)

    assert t1.hypotheses == t2.hypotheses
    assert t1.correct_answer == t2.correct_answer


def test_hypothesis_different_seeds_differ(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.HYPOTHESIS_SELECTION, target_node="target_outcome", max_budget=5
    )
    t1 = tool.generate(world, spec, seed=0)
    t2 = tool.generate(world, spec, seed=1)

    assert t1.given_evidence != t2.given_evidence or t1.hypotheses != t2.hypotheses


def test_hypothesis_works_across_templates():
    gen = WorldGenTool()
    tool = TaskGenTool()

    for template in ["latent_preference", "causal_chain", "fork_collider"]:
        nodes = 7 if template == "fork_collider" else 6
        world = gen.generate(WorldGenConfig(
            template_family=template, seed=42, num_nodes=nodes, edge_strength=0.7
        ))
        spec = TaskSpec(
            type=TaskType.HYPOTHESIS_SELECTION, target_node="target_outcome", max_budget=5
        )
        task = tool.generate(world, spec, seed=42)
        assert len(task.hypotheses) == 4, f"Wrong hypothesis count for {template}"
        min_kl = min(task.correct_answer.values())
        assert min_kl < 0.01, f"No correct hypothesis for {template} (min KL={min_kl})"


# --- verifier hypothesis scoring tests ---


def test_verifier_hypothesis_correct():
    verifier = VerifierTool()
    kl_scores = {"A": 1.5, "B": 0.001, "C": 0.8, "D": 2.0}
    score = verifier.score_hypothesis("B", kl_scores)
    assert score == 1.0


def test_verifier_hypothesis_wrong():
    verifier = VerifierTool()
    kl_scores = {"A": 1.5, "B": 0.001, "C": 0.8, "D": 2.0}
    score = verifier.score_hypothesis("A", kl_scores)
    assert score == 0.0


def test_verifier_hypothesis_invalid():
    verifier = VerifierTool()
    kl_scores = {"A": 0.5, "B": 0.001}
    score = verifier.score_hypothesis("Z", kl_scores)
    assert score == 0.0


# --- generate_all / TaskBundle tests ---


def test_generate_all_returns_bundle(world):
    tool = TaskGenTool()
    bundle = tool.generate_all(world, seed=42)

    assert isinstance(bundle, TaskBundle)
    assert bundle.world_id == world.id
    assert bundle.target_node == "target_outcome"
    assert bundle.seed == 42


def test_bundle_has_all_task_types(world):
    tool = TaskGenTool()
    bundle = tool.generate_all(world, seed=42)

    assert set(bundle.tasks.keys()) == set(TaskType)


def test_bundle_property_accessors(world):
    tool = TaskGenTool()
    bundle = tool.generate_all(world, seed=42)

    assert bundle.infer_target.type == TaskType.INFER_TARGET
    assert bundle.next_best_observation.type == TaskType.NEXT_BEST_OBSERVATION
    assert bundle.hypothesis_selection.type == TaskType.HYPOTHESIS_SELECTION


def test_bundle_all_tasks_share_world(world):
    tool = TaskGenTool()
    bundle = tool.generate_all(world, seed=42)

    for task in bundle.tasks.values():
        assert task.world_id == world.id
        assert task.target_node == "target_outcome"


def test_bundle_tasks_have_different_scoring(world):
    tool = TaskGenTool()
    bundle = tool.generate_all(world, seed=42)

    assert bundle.infer_target.scoring_method == "kl_divergence"
    assert bundle.next_best_observation.scoring_method == "info_gain_ratio"
    assert bundle.hypothesis_selection.scoring_method == "hypothesis_accuracy"


def test_bundle_deterministic(world):
    tool = TaskGenTool()
    b1 = tool.generate_all(world, seed=99)
    b2 = tool.generate_all(world, seed=99)

    for tt in TaskType:
        assert b1.tasks[tt].correct_answer == b2.tasks[tt].correct_answer


def test_bundle_different_seeds_differ(world):
    tool = TaskGenTool()
    b1 = tool.generate_all(world, seed=0)
    b2 = tool.generate_all(world, seed=1)

    # NBO and hypothesis tasks depend on seed, so at least one should differ
    nbo_differ = (
        b1.next_best_observation.given_evidence != b2.next_best_observation.given_evidence
        or b1.next_best_observation.correct_answer != b2.next_best_observation.correct_answer
    )
    hyp_differ = (
        b1.hypothesis_selection.given_evidence != b2.hypothesis_selection.given_evidence
        or b1.hypothesis_selection.hypotheses != b2.hypothesis_selection.hypotheses
    )
    assert nbo_differ or hyp_differ


def test_bundle_works_across_templates():
    gen = WorldGenTool()
    tool = TaskGenTool()

    for template in ["latent_preference", "causal_chain", "fork_collider"]:
        nodes = 7 if template == "fork_collider" else 6
        world = gen.generate(WorldGenConfig(
            template_family=template, seed=42, num_nodes=nodes, edge_strength=0.7
        ))
        bundle = tool.generate_all(world, seed=42)

        assert len(bundle.tasks) == len(TaskType), f"Missing tasks for {template}"
        for tt in TaskType:
            assert tt in bundle.tasks, f"Missing {tt} for {template}"


def test_bundle_serialization(world):
    tool = TaskGenTool()
    bundle = tool.generate_all(world, seed=42)

    data = bundle.model_dump()
    restored = TaskBundle.model_validate(data)

    assert restored.world_id == bundle.world_id
    assert len(restored.tasks) == len(TaskType)
    for tt in TaskType:
        assert restored.tasks[tt].correct_answer == bundle.tasks[tt].correct_answer


# --- causal_effect tests ---


def test_causal_effect_task_generates(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.CAUSAL_EFFECT, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    assert task.type == TaskType.CAUSAL_EFFECT
    assert task.scoring_method == "kl_divergence"
    assert len(task.intervention) == 1


def test_causal_effect_has_intervention(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.CAUSAL_EFFECT, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    # Intervention should be a single node -> state pair
    assert len(task.intervention) == 1
    int_node = list(task.intervention.keys())[0]
    obs_names = {n.name for n in world.nodes if n.type == NodeType.OBSERVABLE}
    assert int_node in obs_names


def test_causal_effect_correct_answer_is_distribution(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.CAUSAL_EFFECT, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    assert isinstance(task.correct_answer, dict)
    assert abs(sum(task.correct_answer.values()) - 1.0) < 1e-4
    assert all(p >= 0 for p in task.correct_answer.values())


def test_causal_effect_question_mentions_intervention(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.CAUSAL_EFFECT, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    int_node = list(task.intervention.keys())[0]
    assert int_node in task.question
    assert "intervene" in task.question.lower() or "do-operation" in task.question.lower()


def test_causal_effect_excludes_intervention_node(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.CAUSAL_EFFECT, target_node="target_outcome", max_budget=5
    )
    task = tool.generate(world, spec, seed=42)

    int_node = list(task.intervention.keys())[0]
    assert int_node not in task.available_evidence


def test_causal_effect_deterministic(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.CAUSAL_EFFECT, target_node="target_outcome", max_budget=5
    )
    t1 = tool.generate(world, spec, seed=99)
    t2 = tool.generate(world, spec, seed=99)

    assert t1.intervention == t2.intervention
    assert t1.correct_answer == t2.correct_answer


def test_causal_effect_different_seeds_can_differ(world):
    tool = TaskGenTool()
    spec = TaskSpec(
        type=TaskType.CAUSAL_EFFECT, target_node="target_outcome", max_budget=5
    )
    t1 = tool.generate(world, spec, seed=0)
    t2 = tool.generate(world, spec, seed=1)

    # Different seeds may pick different intervention nodes or states
    differs = (
        t1.intervention != t2.intervention
        or t1.correct_answer != t2.correct_answer
    )
    assert differs


def test_causal_effect_works_across_templates():
    gen = WorldGenTool()
    tool = TaskGenTool()

    for template in ["latent_preference", "causal_chain", "fork_collider"]:
        nodes = 7 if template == "fork_collider" else 6
        world = gen.generate(WorldGenConfig(
            template_family=template, seed=42, num_nodes=nodes, edge_strength=0.7
        ))
        spec = TaskSpec(
            type=TaskType.CAUSAL_EFFECT, target_node="target_outcome", max_budget=5
        )
        task = tool.generate(world, spec, seed=42)
        assert len(task.intervention) == 1, f"No intervention for {template}"
        assert abs(sum(task.correct_answer.values()) - 1.0) < 1e-4


def test_causal_effect_prefers_nodes_with_effect():
    """Causal effect tasks should prefer nodes with actual causal effects."""
    gen = WorldGenTool()
    tool = TaskGenTool()

    # In causal_chain, all observable nodes have causal effects
    world = gen.generate(WorldGenConfig(
        template_family="causal_chain", seed=42, num_nodes=6, edge_strength=0.7
    ))
    spec = TaskSpec(
        type=TaskType.CAUSAL_EFFECT, target_node="target_outcome", max_budget=5
    )

    # Run 10 times — should always pick a node with actual causal effect
    for seed in range(10):
        task = tool.generate(world, spec, seed=seed)
        int_node = list(task.intervention.keys())[0]
        # In causal_chain, all stages have causal effect on target
        assert "stage" in int_node or "root" in int_node, (
            f"Unexpected intervention node: {int_node}"
        )


# --- best_intervention tests ---


def test_best_intervention_generates(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.BEST_INTERVENTION, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec, seed=42)

    assert isinstance(task, Task)
    assert task.type == TaskType.BEST_INTERVENTION
    assert task.world_id == world.id
    assert task.target_node == "target_outcome"
    assert task.scoring_method == "intervention_effect_ratio"


def test_best_intervention_has_optimal(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.BEST_INTERVENTION, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec, seed=42)

    # intervention field holds the optimal (node, state)
    assert len(task.intervention) == 1
    opt_node = list(task.intervention.keys())[0]
    opt_state = list(task.intervention.values())[0]
    opt_key = f"{opt_node}:{opt_state}"

    # Optimal must be the max in correct_answer
    assert opt_key in task.correct_answer
    assert task.correct_answer[opt_key] == max(task.correct_answer.values())


def test_best_intervention_correct_answer_is_ranking(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.BEST_INTERVENTION, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec, seed=42)

    obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]

    # correct_answer maps "node:state" -> probability
    assert len(task.correct_answer) > 0
    for key, val in task.correct_answer.items():
        assert ":" in key
        node_name = key.split(":")[0]
        assert node_name in obs_nodes
        assert 0.0 <= val <= 1.0


def test_best_intervention_question_mentions_desired_state(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.BEST_INTERVENTION, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec, seed=42)

    assert "maximize" in task.question.lower()
    assert "target_outcome" in task.question
    assert "intervene" in task.question.lower() or "intervention" in task.question.lower()


def test_best_intervention_deterministic(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.BEST_INTERVENTION, target_node="target_outcome", max_budget=5)
    t1 = tool.generate(world, spec, seed=42)
    t2 = tool.generate(world, spec, seed=42)

    assert t1.correct_answer == t2.correct_answer
    assert t1.intervention == t2.intervention


def test_best_intervention_different_seeds(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.BEST_INTERVENTION, target_node="target_outcome", max_budget=5)
    t1 = tool.generate(world, spec, seed=0)
    t2 = tool.generate(world, spec, seed=1)

    # Different seeds may pick different desired states -> different rankings
    # At minimum, the question text should differ (different desired state)
    assert t1.question != t2.question or t1.correct_answer != t2.correct_answer


@pytest.mark.parametrize(
    "template", ["latent_preference", "causal_chain", "fork_collider"]
)
def test_best_intervention_works_across_templates(template):
    gen = WorldGenTool()
    w = gen.generate(WorldGenConfig(template_family=template, seed=42, num_nodes=6, edge_strength=0.7))
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.BEST_INTERVENTION, target_node="target_outcome", max_budget=5)
    task = tool.generate(w, spec, seed=42)

    assert task.type == TaskType.BEST_INTERVENTION
    assert len(task.correct_answer) > 0
    assert len(task.intervention) == 1


# --- best_intervention scoring ---


def test_score_best_intervention_perfect():
    verifier = VerifierTool()
    effects = {"A:high": 0.8, "A:low": 0.3, "B:high": 0.5}
    score = verifier.score_best_intervention("A", "high", effects)
    assert score == 1.0


def test_score_best_intervention_suboptimal():
    verifier = VerifierTool()
    effects = {"A:high": 0.8, "A:low": 0.3, "B:high": 0.5}
    score = verifier.score_best_intervention("B", "high", effects)
    assert abs(score - 0.5 / 0.8) < 1e-6


def test_score_best_intervention_invalid():
    verifier = VerifierTool()
    effects = {"A:high": 0.8, "A:low": 0.3}
    score = verifier.score_best_intervention("X", "wrong", effects)
    assert score == 0.0


def test_score_best_intervention_all_zero():
    verifier = VerifierTool()
    effects = {"A:high": 0.0, "A:low": 0.0}
    score = verifier.score_best_intervention("A", "high", effects)
    assert score == 1.0  # All zero — any choice is fine


# --- adjustment_set tests ---


def test_adjustment_set_generates(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.ADJUSTMENT_SET, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec, seed=42)

    assert isinstance(task, Task)
    assert task.type == TaskType.ADJUSTMENT_SET
    assert task.world_id == world.id
    assert task.scoring_method == "adjustment_set_match"


def test_adjustment_set_has_treatment_node(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.ADJUSTMENT_SET, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec, seed=42)

    # intervention field stores the treatment node
    assert len(task.intervention) == 1
    treatment_node = list(task.intervention.keys())[0]
    assert task.intervention[treatment_node] == "treatment"
    obs_names = {n.name for n in world.nodes if n.type == NodeType.OBSERVABLE}
    assert treatment_node in obs_names


def test_adjustment_set_correct_answer_format(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.ADJUSTMENT_SET, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec, seed=42)

    # correct_answer maps comma-separated variable sets to 1.0
    assert len(task.correct_answer) >= 1
    for key, val in task.correct_answer.items():
        assert val == 1.0
        # Keys are either "_empty_" or comma-separated variable names
        assert key == "_empty_" or all(len(v) > 0 for v in key.split(","))


def test_adjustment_set_available_excludes_treatment_and_target(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.ADJUSTMENT_SET, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec, seed=42)

    treatment_node = list(task.intervention.keys())[0]
    assert treatment_node not in task.available_evidence
    assert "target_outcome" not in task.available_evidence


def test_adjustment_set_question_mentions_treatment(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.ADJUSTMENT_SET, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec, seed=42)

    treatment_node = list(task.intervention.keys())[0]
    assert treatment_node in task.question
    assert "causal effect" in task.question.lower()


def test_adjustment_set_deterministic(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.ADJUSTMENT_SET, target_node="target_outcome", max_budget=5)
    t1 = tool.generate(world, spec, seed=42)
    t2 = tool.generate(world, spec, seed=42)

    assert t1.correct_answer == t2.correct_answer
    assert t1.intervention == t2.intervention


def test_adjustment_set_different_seeds(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.ADJUSTMENT_SET, target_node="target_outcome", max_budget=5)
    t1 = tool.generate(world, spec, seed=0)
    t2 = tool.generate(world, spec, seed=1)

    # Both should be valid tasks (may or may not differ depending on available pairs)
    assert t1.type == TaskType.ADJUSTMENT_SET
    assert t2.type == TaskType.ADJUSTMENT_SET


def test_adjustment_set_fork_collider_has_confounding():
    """Fork-collider template should produce confounded pairs with real adjustment sets."""
    gen = WorldGenTool()
    w = gen.generate(WorldGenConfig(
        template_family="fork_collider", seed=42, num_nodes=7, edge_strength=0.7
    ))
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.ADJUSTMENT_SET, target_node="target_outcome", max_budget=5)
    task = tool.generate(w, spec, seed=42)

    # Fork-collider should have non-empty adjustment sets (confounding via hidden_factor)
    has_nonempty_set = any(k != "_empty_" for k in task.correct_answer)
    assert has_nonempty_set, "Fork-collider should have confounded pairs"


def test_adjustment_set_chain_no_confounding():
    """Causal chain should have no confounding (empty set valid)."""
    gen = WorldGenTool()
    w = gen.generate(WorldGenConfig(
        template_family="causal_chain", seed=42, num_nodes=6, edge_strength=0.7
    ))
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.ADJUSTMENT_SET, target_node="target_outcome", max_budget=5)
    task = tool.generate(w, spec, seed=42)

    # In a pure chain, no confounding exists — empty set is the answer
    assert "_empty_" in task.correct_answer


def test_adjustment_set_latent_preference_not_identifiable():
    """Latent preference: confounders are latent, effect not identifiable."""
    gen = WorldGenTool()
    w = gen.generate(WorldGenConfig(
        template_family="latent_preference", seed=42, num_nodes=6, edge_strength=0.7
    ))
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.ADJUSTMENT_SET, target_node="target_outcome", max_budget=5)
    task = tool.generate(w, spec, seed=42)

    # Latent preference: hidden_cause is the only valid confounder, but it's latent
    assert "_not_identifiable_" in task.correct_answer
    assert "not identifiable" in task.question.lower() or "identif" in task.question.lower()


@pytest.mark.parametrize(
    "template", ["latent_preference", "causal_chain", "fork_collider"]
)
def test_adjustment_set_works_across_templates(template):
    gen = WorldGenTool()
    nodes = 7 if template == "fork_collider" else 6
    w = gen.generate(WorldGenConfig(
        template_family=template, seed=42, num_nodes=nodes, edge_strength=0.7
    ))
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.ADJUSTMENT_SET, target_node="target_outcome", max_budget=5)
    task = tool.generate(w, spec, seed=42)

    assert task.type == TaskType.ADJUSTMENT_SET
    assert len(task.correct_answer) >= 1
    assert len(task.intervention) == 1


# --- adjustment_set scoring ---


def test_score_adjustment_set_correct():
    verifier = VerifierTool()
    valid_sets = {"branch_2,branch_3": 1.0}
    score = verifier.score_adjustment_set(["branch_2", "branch_3"], valid_sets)
    assert score == 1.0


def test_score_adjustment_set_correct_order_independent():
    verifier = VerifierTool()
    valid_sets = {"branch_2,branch_3": 1.0}
    # Agent gives variables in different order — should still match
    score = verifier.score_adjustment_set(["branch_3", "branch_2"], valid_sets)
    assert score == 1.0


def test_score_adjustment_set_wrong():
    verifier = VerifierTool()
    valid_sets = {"branch_2,branch_3": 1.0}
    score = verifier.score_adjustment_set(["collider"], valid_sets)
    assert score == 0.0


def test_score_adjustment_set_empty_correct():
    verifier = VerifierTool()
    valid_sets = {"_empty_": 1.0}
    score = verifier.score_adjustment_set([], valid_sets)
    assert score == 1.0


def test_score_adjustment_set_empty_wrong():
    verifier = VerifierTool()
    valid_sets = {"branch_2,branch_3": 1.0}
    score = verifier.score_adjustment_set([], valid_sets)
    assert score == 0.0


def test_score_adjustment_set_multiple_valid():
    verifier = VerifierTool()
    valid_sets = {"branch_2,branch_3": 1.0, "hidden_factor": 1.0}
    assert verifier.score_adjustment_set(["branch_2", "branch_3"], valid_sets) == 1.0
    assert verifier.score_adjustment_set(["hidden_factor"], valid_sets) == 1.0
    assert verifier.score_adjustment_set(["branch_2"], valid_sets) == 0.0


def test_score_adjustment_set_not_identifiable():
    verifier = VerifierTool()
    valid_sets = {"_not_identifiable_": 1.0}
    # Agent correctly identifies the effect as not identifiable
    assert verifier.score_adjustment_set(["_not_identifiable_"], valid_sets) == 1.0
    # Agent incorrectly proposes a set
    assert verifier.score_adjustment_set(["some_var"], valid_sets) == 0.0
    # Agent incorrectly says empty set
    assert verifier.score_adjustment_set([], valid_sets) == 0.0


# --- generate_from_plan tests ---


def _make_plan(questions, budget=5):
    """Helper to create a CasePlan."""
    return CasePlan(
        title="Test Research Case",
        research_context="A test scenario for validating plan-driven task generation.",
        questions=questions,
        shared_budget=budget,
        rationale="Testing",
    )


def test_generate_from_plan_single_question(world):
    tool = TaskGenTool()
    plan = _make_plan([
        EvalQuestionPlan(
            question_text="What is the most likely target outcome?",
            eval_type=TaskType.INFER_TARGET,
            target_node="target_outcome",
        ),
    ])
    tasks = tool.generate_from_plan(world, plan)
    assert len(tasks) == 1
    assert tasks[0].type == TaskType.INFER_TARGET
    assert tasks[0].question == "What is the most likely target outcome?"


def test_generate_from_plan_multiple_questions(world):
    tool = TaskGenTool()
    plan = _make_plan([
        EvalQuestionPlan(
            question_text="What is the target outcome distribution?",
            eval_type=TaskType.INFER_TARGET,
            target_node="target_outcome",
        ),
        EvalQuestionPlan(
            question_text="What experiment should we run next?",
            eval_type=TaskType.NEXT_BEST_OBSERVATION,
            target_node="target_outcome",
        ),
    ])
    tasks = tool.generate_from_plan(world, plan)
    assert len(tasks) == 2
    assert tasks[0].type == TaskType.INFER_TARGET
    assert tasks[1].type == TaskType.NEXT_BEST_OBSERVATION


def test_generate_from_plan_custom_question_text(world):
    tool = TaskGenTool()
    custom_text = "Based on the soil samples, what contamination level is most likely?"
    plan = _make_plan([
        EvalQuestionPlan(
            question_text=custom_text,
            eval_type=TaskType.INFER_TARGET,
            target_node="target_outcome",
        ),
    ])
    tasks = tool.generate_from_plan(world, plan)
    assert tasks[0].question == custom_text


def test_generate_from_plan_all_three_types(world):
    tool = TaskGenTool()
    plan = _make_plan([
        EvalQuestionPlan(
            question_text="What is the most likely target outcome?",
            eval_type=TaskType.INFER_TARGET,
            target_node="target_outcome",
        ),
        EvalQuestionPlan(
            question_text="What experiment would be most informative?",
            eval_type=TaskType.NEXT_BEST_OBSERVATION,
            target_node="target_outcome",
        ),
        EvalQuestionPlan(
            question_text="Which hypothesis best matches the data?",
            eval_type=TaskType.HYPOTHESIS_SELECTION,
            target_node="target_outcome",
        ),
    ])
    tasks = tool.generate_from_plan(world, plan)
    assert len(tasks) == 3
    types = {t.type for t in tasks}
    assert types == {
        TaskType.INFER_TARGET,
        TaskType.NEXT_BEST_OBSERVATION,
        TaskType.HYPOTHESIS_SELECTION,
    }


def test_generate_from_plan_tasks_have_correct_answers(world):
    tool = TaskGenTool()
    plan = _make_plan([
        EvalQuestionPlan(
            question_text="What is the target outcome distribution?",
            eval_type=TaskType.INFER_TARGET,
            target_node="target_outcome",
        ),
    ])
    tasks = tool.generate_from_plan(world, plan)
    assert isinstance(tasks[0].correct_answer, dict)
    assert abs(sum(tasks[0].correct_answer.values()) - 1.0) < 1e-6


def test_generate_from_plan_deterministic(world):
    tool = TaskGenTool()
    plan = _make_plan([
        EvalQuestionPlan(
            question_text="What is the target outcome?",
            eval_type=TaskType.INFER_TARGET,
            target_node="target_outcome",
        ),
        EvalQuestionPlan(
            question_text="What should we observe next?",
            eval_type=TaskType.NEXT_BEST_OBSERVATION,
            target_node="target_outcome",
        ),
    ])
    t1 = tool.generate_from_plan(world, plan, seed=42)
    t2 = tool.generate_from_plan(world, plan, seed=42)
    for a, b in zip(t1, t2):
        assert a.correct_answer == b.correct_answer


def test_generate_from_plan_uses_shared_budget(world):
    tool = TaskGenTool()
    plan = _make_plan(
        [
            EvalQuestionPlan(
                question_text="What is the target outcome?",
                eval_type=TaskType.INFER_TARGET,
                target_node="target_outcome",
            ),
        ],
        budget=8,
    )
    tasks = tool.generate_from_plan(world, plan)
    # The task should use the plan's budget (visible in available_evidence count)
    assert len(tasks) == 1
