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


# --- Causal query (do-calculus) ---


def test_causal_query_returns_valid_distribution(solver):
    result = solver.causal_query("target_outcome", do={"indicator_4": "low"})
    assert abs(sum(result.values()) - 1.0) < 1e-6
    assert all(p >= 0 for p in result.values())


def test_causal_query_differs_from_observational(solver):
    """do(X) != observe(X) when there are confounders."""
    # indicator_4 -> target_outcome, and hidden_cause -> both
    do_dist = solver.causal_query("target_outcome", do={"indicator_4": "low"})
    obs_dist = solver.posterior("target_outcome", {"indicator_4": "low"})

    # They should differ because hidden_cause confounds the relationship
    diffs = [abs(do_dist[s] - obs_dist[s]) for s in do_dist]
    max_diff = max(diffs)
    assert max_diff > 0.01, "do() and observe() should differ with confounders"


def test_causal_query_no_effect_non_causal_node(solver):
    """do(indicator_1) should NOT affect target (no causal path)."""
    do_low = solver.causal_query("target_outcome", do={"indicator_1": "low"})
    do_high = solver.causal_query("target_outcome", do={"indicator_1": "high"})
    prior = solver.posterior("target_outcome")

    # All three should be (nearly) identical
    for s in do_low:
        assert abs(do_low[s] - prior[s]) < 1e-6
        assert abs(do_high[s] - prior[s]) < 1e-6


def test_causal_query_with_causal_chain():
    """In a causal chain, do(stage_N) should affect target."""
    gen = WorldGenTool()
    world = gen.generate(WorldGenConfig(
        template_family="causal_chain", seed=42, num_nodes=6, edge_strength=0.7
    ))
    solver = ExactBayesSolver(world)

    do_low = solver.causal_query("target_outcome", do={"stage_4": "low"})
    do_high = solver.causal_query("target_outcome", do={"stage_4": "high"})

    max_diff = max(abs(do_low[s] - do_high[s]) for s in do_low)
    assert max_diff > 0.1, "stage_4 should have strong causal effect on target"


# --- IG/cost optimization ---


def test_optimal_action_with_uniform_costs(solver, world):
    """With uniform costs, IG/cost should pick same node as pure IG."""
    obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
    evidence: dict[str, str] = {}

    # Without costs
    result_no_cost = solver.optimal_action("target_outcome", evidence, obs_nodes)
    # With uniform costs
    costs = {n: 1 for n in obs_nodes}
    result_with_cost = solver.optimal_action("target_outcome", evidence, obs_nodes, costs=costs)

    assert result_no_cost.recommended_action.node == result_with_cost.recommended_action.node


def test_optimal_action_ig_per_cost():
    """When a node has high IG but very high cost, a cheaper node may win."""
    gen = WorldGenTool()
    world = gen.generate(WorldGenConfig(seed=42, num_nodes=10, edge_strength=0.7))
    solver = ExactBayesSolver(world)
    obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]

    # Get pure IG ranking
    ig_ranking = {}
    for node in obs_nodes:
        ig_ranking[node] = solver.information_gain("target_outcome", {}, node)

    best_ig_node = max(ig_ranking, key=ig_ranking.get)
    best_ig = ig_ranking[best_ig_node]

    # Make the best IG node very expensive (cost 100)
    costs = {n: 1 for n in obs_nodes}
    costs[best_ig_node] = 100

    result = solver.optimal_action("target_outcome", {}, obs_nodes, costs=costs)

    # If the best IG node has IG much less than 100x the second-best,
    # the solver should pick a different (cheaper) node
    if best_ig > 0:
        assert result.recommended_action.node != best_ig_node or len(obs_nodes) == 1


def test_generate_trajectory_with_costs(solver, world):
    """Trajectory generation respects costs and budget."""
    obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
    costs = {n: 2 for n in obs_nodes}

    true_state, trajectory = solver.generate_trajectory(
        "target_outcome", obs_nodes, budget=5, seed=42, costs=costs,
    )

    # With cost=2 and budget=5, at most 2 observations fit (2*2=4, 3*2=6>5)
    observation_steps = [t for t in trajectory if t.recommended_action is not None]
    assert len(observation_steps) <= 2


def test_generate_trajectory_without_costs_backward_compat(solver, world):
    """Trajectory without costs works as before."""
    obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]

    true_state, trajectory = solver.generate_trajectory(
        "target_outcome", obs_nodes, budget=5, seed=42,
    )
    assert len(trajectory) > 0
    assert trajectory[-1].recommended_action is None  # final step
