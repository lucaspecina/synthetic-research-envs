"""Tests for EpisodeRunner — the environment interface."""

import pytest

from sreg.env.episode import EpisodeRunner
from sreg.models.episode import Action, ActionDef, ActionType, Episode
from sreg.models.world import NodeType
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool
from sreg.tools.verifier import VerifierTool
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


@pytest.fixture
def world():
    gen = WorldGenTool()
    return gen.generate(WorldGenConfig(seed=42, num_nodes=6, edge_strength=0.7))


@pytest.fixture
def solver(world):
    return ExactBayesSolver(world)


@pytest.fixture
def true_state(solver):
    return solver.sample_state(seed=99)


@pytest.fixture
def episode(world, true_state):
    tool = EpisodeGenTool()
    return tool.generate(world, EpisodeGenConfig(budget=5, seed=0))


@pytest.fixture
def runner(world, episode, true_state):
    return EpisodeRunner(world, episode, true_state)


# --- Basic interaction ---


def test_observe_returns_observation(runner, episode):
    node = episode.available_nodes[0]
    action = Action(type=ActionType.OBSERVE, node=node)
    result = runner.step(action)

    assert result.observation is not None
    assert result.observation.node == node
    assert result.remaining_budget == 4


def test_observe_reduces_budget(runner, episode):
    node = episode.available_nodes[0]
    action = Action(type=ActionType.OBSERVE, node=node)
    runner.step(action)

    assert runner.budget_remaining == 4


def test_observe_adds_to_evidence(runner, episode, true_state):
    node = episode.available_nodes[0]
    action = Action(type=ActionType.OBSERVE, node=node)
    runner.step(action)

    assert node in runner.evidence
    assert runner.evidence[node] == true_state[node]


def test_query_distribution(runner):
    action = Action(type=ActionType.QUERY_DISTRIBUTION, node="target_outcome")
    result = runner.step(action)

    assert result.distribution is not None
    assert abs(sum(result.distribution.values()) - 1.0) < 1e-6
    assert result.remaining_budget == 5  # query doesn't cost budget


def test_submit_ends_episode(runner):
    action = Action(type=ActionType.SUBMIT, answer={"low": 0.3, "medium": 0.3, "high": 0.4})
    runner.step(action)

    assert runner.is_finished


def test_cannot_act_after_submit(runner):
    runner.step(Action(type=ActionType.SUBMIT, answer={"low": 1.0}))
    with pytest.raises(RuntimeError, match="already finished"):
        runner.step(Action(type=ActionType.OBSERVE, node="indicator_1"))


def test_cannot_observe_already_observed(runner, episode):
    node = episode.available_nodes[0]
    action = Action(type=ActionType.OBSERVE, node=node)
    runner.step(action)

    with pytest.raises(ValueError, match="already been observed"):
        runner.step(action)


def test_cannot_observe_unavailable_node(runner):
    with pytest.raises(ValueError, match="not available"):
        runner.step(Action(type=ActionType.OBSERVE, node="hidden_cause"))


def test_true_posterior_updates_with_evidence(runner, episode):
    prior = runner.true_posterior("target_outcome")

    node = episode.available_nodes[0]
    runner.step(Action(type=ActionType.OBSERVE, node=node))
    posterior = runner.true_posterior("target_outcome")

    assert prior != posterior


# --- End-to-end: teacher as agent ---


def test_teacher_end_to_end(world):
    """Full end-to-end test: teacher plays through episode, scores are correct."""
    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=42)

    ep_tool = EpisodeGenTool()
    episode = ep_tool.generate(world, EpisodeGenConfig(budget=5, seed=0))

    runner = EpisodeRunner(world, episode, true_state)
    obs_nodes = list(episode.available_nodes)
    evidence: dict[str, str] = {}

    # Teacher plays optimally
    for _ in range(min(episode.budget, len(obs_nodes))):
        available = [n for n in obs_nodes if n not in evidence]
        if not available:
            break

        output = solver.optimal_action("target_outcome", evidence, available)
        if output.recommended_action is None:
            break

        result = runner.step(output.recommended_action)
        evidence[result.observation.node] = result.observation.state

    # Submit final answer
    final_posterior = runner.true_posterior("target_outcome")
    runner.step(
        Action(type=ActionType.SUBMIT, answer=final_posterior, confidence=0.95)
    )

    # Verify scoring
    verifier = VerifierTool()
    score = verifier.score(
        agent_posterior=final_posterior,
        true_posterior=final_posterior,
        budget_used=len(evidence),
        budget_total=episode.budget,
    )

    # Teacher submitting true posterior should get perfect KL score
    assert score.functional_score < 1e-6
    assert runner.is_finished


def test_teacher_accuracy_via_runner():
    """Teacher reaches >90% MAP accuracy running through EpisodeRunner.

    This is the key validation for Phase 4: same result as Phase 3
    but through the full environment interface.
    """
    gen = WorldGenTool()
    correct = 0
    total = 0

    for world_seed in range(20):
        config = WorldGenConfig(seed=world_seed, num_nodes=6, edge_strength=0.7)
        world = gen.generate(config)
        solver = ExactBayesSolver(world)

        for ep_seed in range(5):
            true_state = solver.sample_state(seed=world_seed * 1000 + ep_seed)

            ep_tool = EpisodeGenTool()
            episode = ep_tool.generate(world, EpisodeGenConfig(budget=5, seed=ep_seed))
            runner = EpisodeRunner(world, episode, true_state)

            obs_nodes = list(episode.available_nodes)
            evidence: dict[str, str] = {}

            for _ in range(min(episode.budget, len(obs_nodes))):
                available = [n for n in obs_nodes if n not in evidence]
                if not available:
                    break
                output = solver.optimal_action("target_outcome", evidence, available)
                if output.recommended_action is None:
                    break
                result = runner.step(output.recommended_action)
                evidence[result.observation.node] = result.observation.state

            final_posterior = runner.true_posterior("target_outcome")
            map_state = max(final_posterior, key=final_posterior.get)

            if map_state == true_state["target_outcome"]:
                correct += 1
            total += 1

    accuracy = correct / total
    assert accuracy > 0.90, f"Teacher accuracy {accuracy:.1%} ({correct}/{total}) below 90%"


# --- Rich actions: multi-node and compound actions ---


def _make_rich_episode(world, true_state):
    """Create an episode with rich action definitions."""
    obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
    # Create a compound action from first 2 observable nodes
    compound_nodes = obs_nodes[:2]
    individual_nodes = obs_nodes[2:]

    action_defs = [
        ActionDef(
            id="field_survey",
            action_type="observe",
            nodes=compound_nodes,
            cost=2,
        ),
    ]
    # Individual actions
    for n in individual_nodes:
        action_defs.append(
            ActionDef(id=f"measure_{n}", action_type="observe", nodes=[n], cost=1)
        )

    node_costs = {}
    for n in compound_nodes:
        node_costs[n] = 2
    for n in individual_nodes:
        node_costs[n] = 1

    return Episode(
        id="ep-rich-test",
        world_id=world.id,
        budget=5,
        initial_evidence=[],
        available_nodes=obs_nodes,
        node_costs=node_costs,
        action_defs=action_defs,
        steps=[],
    )


def test_compound_observe_reveals_multiple_nodes(world, true_state):
    episode = _make_rich_episode(world, true_state)
    runner = EpisodeRunner(world, episode, true_state)
    compound_nodes = episode.action_defs[0].nodes

    result = runner.step(Action(type=ActionType.OBSERVE, action_id="field_survey"))

    # First node in observation, rest in extra_observations
    assert result.observation is not None
    assert result.observation.node == compound_nodes[0]
    assert len(result.extra_observations) == len(compound_nodes) - 1
    assert result.extra_observations[0].node == compound_nodes[1]


def test_compound_observe_deducts_correct_cost(world, true_state):
    episode = _make_rich_episode(world, true_state)
    runner = EpisodeRunner(world, episode, true_state)

    runner.step(Action(type=ActionType.OBSERVE, action_id="field_survey"))
    assert runner.budget_remaining == 3  # 5 - 2 = 3


def test_compound_observe_adds_all_nodes_to_evidence(world, true_state):
    episode = _make_rich_episode(world, true_state)
    runner = EpisodeRunner(world, episode, true_state)
    compound_nodes = episode.action_defs[0].nodes

    runner.step(Action(type=ActionType.OBSERVE, action_id="field_survey"))

    for n in compound_nodes:
        assert n in runner.evidence
        assert runner.evidence[n] == true_state[n]


def test_compound_action_cannot_be_used_twice(world, true_state):
    episode = _make_rich_episode(world, true_state)
    runner = EpisodeRunner(world, episode, true_state)

    runner.step(Action(type=ActionType.OBSERVE, action_id="field_survey"))
    with pytest.raises(ValueError, match="already been used"):
        runner.step(Action(type=ActionType.OBSERVE, action_id="field_survey"))


def test_compound_action_budget_check(world, true_state):
    """Compound action that costs more than remaining budget should fail."""
    obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
    episode = Episode(
        id="ep-budget-test",
        world_id=world.id,
        budget=1,  # only 1 budget unit
        initial_evidence=[],
        available_nodes=obs_nodes,
        node_costs={n: 1 for n in obs_nodes},
        action_defs=[
            ActionDef(
                id="expensive_survey",
                action_type="observe",
                nodes=obs_nodes[:2],
                cost=3,
            )
        ],
        steps=[],
    )
    runner = EpisodeRunner(world, episode, true_state)

    with pytest.raises(ValueError, match="Insufficient budget"):
        runner.step(Action(type=ActionType.OBSERVE, action_id="expensive_survey"))


def test_mix_compound_and_individual(world, true_state):
    """Can use compound actions alongside individual single-node observe."""
    episode = _make_rich_episode(world, true_state)
    runner = EpisodeRunner(world, episode, true_state)
    individual_nodes = [ad for ad in episode.action_defs if len(ad.nodes) == 1]

    # Use compound action first
    runner.step(Action(type=ActionType.OBSERVE, action_id="field_survey"))
    assert runner.budget_remaining == 3

    # Then use individual action by node name (legacy mode)
    if individual_nodes:
        node = individual_nodes[0].nodes[0]
        runner.step(Action(type=ActionType.OBSERVE, node=node))
        assert runner.budget_remaining == 2


def test_legacy_mode_still_works_with_empty_action_defs(runner, episode):
    """When action_defs is empty, legacy single-node observe still works."""
    assert len(episode.action_defs) == 0
    node = episode.available_nodes[0]
    result = runner.step(Action(type=ActionType.OBSERVE, node=node))
    assert result.observation.node == node
    assert result.remaining_budget == 4


def test_compound_observe_node_already_observed(world, true_state):
    """Compound action fails if any of its nodes was already observed."""
    episode = _make_rich_episode(world, true_state)
    runner = EpisodeRunner(world, episode, true_state)
    # Observe one of the compound nodes individually first
    compound_node = episode.action_defs[0].nodes[0]
    runner.step(Action(type=ActionType.OBSERVE, node=compound_node))

    with pytest.raises(ValueError, match="already been observed"):
        runner.step(Action(type=ActionType.OBSERVE, action_id="field_survey"))


def test_compound_observe_rejects_non_observe_action_type(world, true_state):
    """Runner rejects action_defs with non-observe action_type (guard for Slice B)."""
    episode = Episode(
        id="guard-test",
        world_id=world.id,
        budget=5,
        initial_evidence=[],
        available_nodes=[n.name for n in world.nodes if n.type == NodeType.OBSERVABLE],
        node_costs={},
        action_defs=[
            ActionDef(
                id="experiment_1",
                action_type="intervene",
                nodes=[world.nodes[1].name],
                cost=2,
            ),
        ],
        steps=[],
    )
    runner = EpisodeRunner(world, episode, true_state)
    with pytest.raises(ValueError, match="not yet supported"):
        runner.step(Action(type=ActionType.OBSERVE, action_id="experiment_1"))
