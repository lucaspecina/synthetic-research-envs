"""Tests for causal chain template."""

from __future__ import annotations

import pytest

from sreg.models.world import NodeType
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.world_check import WorldCheckTool
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


def _gen(seed=42, num_nodes=6, edge_strength=0.7):
    config = WorldGenConfig(
        template_family="causal_chain",
        seed=seed,
        num_nodes=num_nodes,
        edge_strength=edge_strength,
    )
    return WorldGenTool().generate(config)


def test_generate_chain_world():
    world = _gen()
    assert world.template_family == "causal_chain"
    assert len(world.nodes) == 6


def test_chain_has_correct_node_types():
    world = _gen()
    types = {n.type for n in world.nodes}
    assert NodeType.LATENT in types
    assert NodeType.OBSERVABLE in types
    assert NodeType.TARGET in types

    latent = [n for n in world.nodes if n.type == NodeType.LATENT]
    target = [n for n in world.nodes if n.type == NodeType.TARGET]
    assert len(latent) == 1
    assert len(target) == 1


def test_chain_is_linear():
    """Each node (except root) has exactly one parent."""
    world = _gen()
    parent_count: dict[str, int] = {n.name: 0 for n in world.nodes}
    for edge in world.edges:
        parent_count[edge.to_node] += 1

    root = world.nodes[0]
    assert parent_count[root.name] == 0  # Root has no parents

    for node in world.nodes[1:]:
        assert parent_count[node.name] == 1  # All others have exactly 1 parent


def test_chain_edges_are_sequential():
    """Edges follow the chain: node[0]->node[1], node[1]->node[2], ..."""
    world = _gen()
    for i, edge in enumerate(world.edges):
        assert edge.from_node == world.nodes[i].name
        assert edge.to_node == world.nodes[i + 1].name


def test_chain_num_edges():
    world = _gen(num_nodes=6)
    assert len(world.edges) == 5  # N-1 edges for N nodes


def test_chain_passes_validation():
    world = _gen()
    check = WorldCheckTool().check(world)
    assert check.passed, f"Validation failed: {check.failures}"


def test_chain_deterministic():
    w1 = _gen(seed=99)
    w2 = _gen(seed=99)
    assert w1.model_dump() == w2.model_dump()


def test_chain_different_seeds():
    w1 = _gen(seed=0)
    w2 = _gen(seed=1)
    assert w1.cpds[0].table != w2.cpds[0].table


def test_chain_cpds_sum_to_one():
    world = _gen()
    for cpd in world.cpds:
        for col_idx in range(len(cpd.table[0])):
            col_sum = sum(row[col_idx] for row in cpd.table)
            assert abs(col_sum - 1.0) < 1e-6, f"CPD {cpd.node} col {col_idx} sums to {col_sum}"


def test_chain_teacher_solves():
    """Teacher should achieve high accuracy on chain worlds."""
    world = _gen(edge_strength=0.8)
    solver = ExactBayesSolver(world)

    correct = 0
    total = 20
    for seed in range(total):
        true_state = solver.sample_state(seed=seed)
        target = "target_outcome"
        true_val = true_state[target]

        # Observe all observable nodes
        obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
        evidence = {}
        for node in obs_nodes:
            evidence[node] = true_state[node]

        posterior = solver.posterior(target, evidence)
        predicted = max(posterior, key=posterior.get)
        if predicted == true_val:
            correct += 1

    accuracy = correct / total
    assert accuracy >= 0.7, f"Teacher accuracy {accuracy:.0%} too low on chain"


def test_chain_closer_nodes_more_informative():
    """Nodes closer to the target should have higher information gain."""
    world = _gen(seed=42, num_nodes=7, edge_strength=0.7)
    solver = ExactBayesSolver(world)

    obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
    target = "target_outcome"

    # Calculate IG for each observable with no prior evidence
    igs = {}
    for node in obs_nodes:
        ig = solver.information_gain(target, {}, node)
        igs[node] = ig

    # The last observable (closest to target) should generally have highest IG
    # This isn't guaranteed for every seed, but should hold for this one
    last_obs = obs_nodes[-1]
    first_obs = obs_nodes[0]
    assert igs[last_obs] >= igs[first_obs], (
        f"Expected {last_obs} (closer to target) to be more informative than "
        f"{first_obs}, but IG {igs[last_obs]:.4f} < {igs[first_obs]:.4f}"
    )


def test_chain_100_worlds_valid():
    """Generate 100 chain worlds and validate all pass."""
    checker = WorldCheckTool()
    for seed in range(100):
        world = _gen(seed=seed)
        check = checker.check(world)
        assert check.passed, f"Seed {seed} failed: {check.failures}"


def test_chain_different_sizes():
    for n in [3, 4, 5, 6, 8, 10]:
        world = _gen(num_nodes=n)
        assert len(world.nodes) == n
        assert len(world.edges) == n - 1
