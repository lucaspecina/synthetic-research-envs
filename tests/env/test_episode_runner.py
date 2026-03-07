"""Tests for EpisodeRunner — the environment interface."""

import pytest

from sreg.env.episode import EpisodeRunner
from sreg.models.episode import Action, ActionType
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
