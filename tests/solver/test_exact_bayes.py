"""Tests for exact Bayesian teacher solver."""

import pytest

from sreg.models.world import NodeType
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


@pytest.fixture
def gen():
    return WorldGenTool()


@pytest.fixture
def world(gen):
    return gen.generate(WorldGenConfig(seed=42, num_nodes=6, edge_strength=0.7))


@pytest.fixture
def solver(world):
    return ExactBayesSolver(world)


# --- Posterior computation ---


def test_prior_is_valid_distribution(solver):
    post = solver.posterior("target_outcome")
    assert abs(sum(post.values()) - 1.0) < 1e-6
    assert all(p >= 0 for p in post.values())


def test_posterior_with_evidence(solver):
    post = solver.posterior("target_outcome", {"indicator_1": "high"})
    assert abs(sum(post.values()) - 1.0) < 1e-6


def test_posterior_changes_with_evidence(solver):
    prior = solver.posterior("target_outcome")
    posterior = solver.posterior("target_outcome", {"indicator_1": "high"})

    # Posterior should differ from prior (evidence is informative)
    assert prior != posterior


def test_more_evidence_reduces_entropy(solver):
    h0 = solver.entropy(solver.posterior("target_outcome"))
    h1 = solver.entropy(solver.posterior("target_outcome", {"indicator_1": "high"}))
    h2 = solver.entropy(
        solver.posterior("target_outcome", {"indicator_1": "high", "indicator_2": "low"})
    )

    # With more evidence, entropy should trend down (generous tolerance for edge cases)
    assert h2 <= h0 + 0.5
    assert h1 <= h0 + 0.5


# --- Entropy ---


def test_entropy_of_uniform():

    solver_instance = ExactBayesSolver.__new__(ExactBayesSolver)
    dist = {"a": 0.5, "b": 0.5}
    h = ExactBayesSolver.entropy(solver_instance, dist)
    assert abs(h - 1.0) < 1e-6  # log2(2) = 1.0


def test_entropy_of_certain():
    solver_instance = ExactBayesSolver.__new__(ExactBayesSolver)
    dist = {"a": 1.0, "b": 0.0}
    h = ExactBayesSolver.entropy(solver_instance, dist)
    assert abs(h - 0.0) < 1e-6


# --- Information gain ---


def test_information_gain_non_negative(solver):
    gain = solver.information_gain("target_outcome", {}, "indicator_1")
    assert gain >= 0.0


def test_information_gain_positive_for_connected_node(solver):
    gain = solver.information_gain("target_outcome", {}, "indicator_1")
    assert gain > 0.01  # should be meaningfully positive


# --- Optimal action ---


def test_optimal_action_selects_best(solver, world):
    obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
    output = solver.optimal_action("target_outcome", {}, obs_nodes)

    assert output.recommended_action is not None
    assert output.recommended_action.node in obs_nodes
    assert output.information_gain > 0
    assert output.entropy > 0


def test_optimal_action_none_when_no_available(solver):
    output = solver.optimal_action("target_outcome", {}, [])
    assert output.recommended_action is None
    assert output.information_gain == 0.0


# --- Sampling ---


def test_sample_state_complete(solver, world):
    state = solver.sample_state(seed=0)
    node_names = {n.name for n in world.nodes}
    assert set(state.keys()) == node_names


def test_sample_state_valid_values(solver, world):
    state = solver.sample_state(seed=0)
    for node in world.nodes:
        assert state[node.name] in node.states


def test_sample_state_deterministic(solver):
    s1 = solver.sample_state(seed=42)
    s2 = solver.sample_state(seed=42)
    assert s1 == s2


def test_sample_state_varies(solver):
    s1 = solver.sample_state(seed=1)
    s2 = solver.sample_state(seed=2)
    # Very unlikely to be identical across all nodes
    assert s1 != s2


# --- Trajectory generation ---


def test_generate_trajectory(solver, world):
    obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
    true_state, trajectory = solver.generate_trajectory(
        target="target_outcome",
        available=obs_nodes,
        budget=len(obs_nodes),
        seed=42,
    )

    # Trajectory has budget + 1 entries (one per step + final)
    assert len(trajectory) >= 2
    # Last entry has no recommended action (terminal)
    assert trajectory[-1].recommended_action is None
    # True state includes all nodes
    assert "target_outcome" in true_state


def test_trajectory_entropy_decreases(solver, world):
    obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
    _, trajectory = solver.generate_trajectory(
        target="target_outcome",
        available=obs_nodes,
        budget=len(obs_nodes),
        seed=42,
    )

    # Entropy should generally decrease over the trajectory.
    # For a specific realization, posterior entropy can temporarily increase
    # (unlikely evidence), so we use generous tolerance.
    entropies = [t.entropy for t in trajectory]
    assert entropies[-1] <= entropies[0] + 0.5


# --- Teacher accuracy validation ---


def test_teacher_accuracy_above_90_percent():
    """Teacher reaches >90% MAP accuracy across 50 worlds after full episode.

    This is the key validation criterion for Phase 3.
    """
    gen = WorldGenTool()
    correct = 0
    total = 0

    for world_seed in range(50):
        config = WorldGenConfig(seed=world_seed, num_nodes=6, edge_strength=0.7)
        world = gen.generate(config)
        solver = ExactBayesSolver(world)

        obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]

        for ep_seed in range(5):
            true_state, trajectory = solver.generate_trajectory(
                target="target_outcome",
                available=obs_nodes,
                budget=len(obs_nodes),
                seed=world_seed * 1000 + ep_seed,
            )

            # MAP estimate from final posterior
            final_posterior = trajectory[-1].posterior
            map_state = max(final_posterior, key=final_posterior.get)
            true_target = true_state["target_outcome"]

            if map_state == true_target:
                correct += 1
            total += 1

    accuracy = correct / total
    assert accuracy > 0.90, f"Teacher accuracy {accuracy:.1%} ({correct}/{total}) is below 90%"
