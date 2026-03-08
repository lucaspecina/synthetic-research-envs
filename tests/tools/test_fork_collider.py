"""Tests for fork-collider template."""

from __future__ import annotations

import pytest

from sreg.models.world import NodeType
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.world_check import WorldCheckTool
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


def _gen(seed=42, num_nodes=6, edge_strength=0.7):
    config = WorldGenConfig(
        template_family="fork_collider",
        seed=seed,
        num_nodes=num_nodes,
        edge_strength=edge_strength,
    )
    return WorldGenTool().generate(config)


def test_generate_fork_collider_world():
    world = _gen()
    assert world.template_family == "fork_collider"
    assert len(world.nodes) == 6


def test_fork_collider_has_correct_node_types():
    world = _gen()
    types = {n.type for n in world.nodes}
    assert NodeType.LATENT in types
    assert NodeType.OBSERVABLE in types
    assert NodeType.TARGET in types

    latent = [n for n in world.nodes if n.type == NodeType.LATENT]
    target = [n for n in world.nodes if n.type == NodeType.TARGET]
    assert len(latent) == 1
    assert len(target) == 1


def test_fork_collider_has_collider_node():
    """There should be a node named 'collider'."""
    world = _gen()
    names = [n.name for n in world.nodes]
    assert "collider" in names


def test_fork_collider_has_branches():
    """There should be at least 2 branch nodes."""
    world = _gen()
    branches = [n for n in world.nodes if n.name.startswith("branch_")]
    assert len(branches) >= 2


def test_fork_structure():
    """Latent parent should have edges to branches (fork)."""
    world = _gen()
    latent_names = [n.name for n in world.nodes if n.type == NodeType.LATENT]
    branch_names = [n.name for n in world.nodes if n.name.startswith("branch_")]

    # Each branch should have a latent parent
    for branch in branch_names:
        parents = [e.from_node for e in world.edges if e.to_node == branch]
        assert any(p in latent_names for p in parents), (
            f"Branch {branch} has no latent parent. Parents: {parents}"
        )


def test_collider_structure():
    """All branches should be parents of the collider node."""
    world = _gen()
    branch_names = [n.name for n in world.nodes if n.name.startswith("branch_")]
    collider_parents = [e.from_node for e in world.edges if e.to_node == "collider"]

    for branch in branch_names:
        assert branch in collider_parents, (
            f"Branch {branch} is not a parent of collider. Collider parents: {collider_parents}"
        )


def test_target_is_downstream_of_collider():
    """There should be a path from collider to target_outcome."""
    world = _gen()
    # Build adjacency
    children: dict[str, list[str]] = {n.name: [] for n in world.nodes}
    for e in world.edges:
        children[e.from_node].append(e.to_node)

    # BFS from collider
    visited = set()
    queue = ["collider"]
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        queue.extend(children[node])

    assert "target_outcome" in visited, "target_outcome not reachable from collider"


def test_fork_collider_passes_validation():
    world = _gen()
    check = WorldCheckTool().check(world)
    assert check.passed, f"Validation failed: {check.failures}"


def test_fork_collider_deterministic():
    w1 = _gen(seed=99)
    w2 = _gen(seed=99)
    assert w1.model_dump() == w2.model_dump()


def test_fork_collider_different_seeds():
    w1 = _gen(seed=0)
    w2 = _gen(seed=1)
    assert w1.cpds[0].table != w2.cpds[0].table


def test_fork_collider_cpds_sum_to_one():
    world = _gen()
    for cpd in world.cpds:
        for col_idx in range(len(cpd.table[0])):
            col_sum = sum(row[col_idx] for row in cpd.table)
            assert abs(col_sum - 1.0) < 1e-6, f"CPD {cpd.node} col {col_idx} sums to {col_sum}"


def test_fork_collider_teacher_solves():
    """Teacher should achieve reasonable accuracy on fork-collider worlds."""
    world = _gen(edge_strength=0.8)
    solver = ExactBayesSolver(world)

    correct = 0
    total = 20
    for seed in range(total):
        true_state = solver.sample_state(seed=seed)
        target = "target_outcome"
        true_val = true_state[target]

        obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
        evidence = {node: true_state[node] for node in obs_nodes}

        posterior = solver.posterior(target, evidence)
        predicted = max(posterior, key=posterior.get)
        if predicted == true_val:
            correct += 1

    accuracy = correct / total
    assert accuracy >= 0.6, f"Teacher accuracy {accuracy:.0%} too low on fork-collider"


def test_fork_collider_100_worlds_valid():
    """Generate 100 fork-collider worlds and validate all pass."""
    checker = WorldCheckTool()
    for seed in range(100):
        world = _gen(seed=seed)
        check = checker.check(world)
        assert check.passed, f"Seed {seed} failed: {check.failures}"


def test_fork_collider_different_sizes():
    for n in [5, 6, 7, 8, 10]:
        world = _gen(num_nodes=n)
        assert len(world.nodes) == n


def test_fork_collider_min_nodes_enforced():
    """Should raise ValueError if num_nodes < num_latent + 4."""
    with pytest.raises(ValueError, match="fork_collider needs at least"):
        _gen(num_nodes=4)


def test_fork_collider_with_mediators():
    """With enough nodes, mediators should appear between collider and target."""
    world = _gen(num_nodes=8)
    mediator_names = [n.name for n in world.nodes if n.name.startswith("mediator_")]
    assert len(mediator_names) >= 1, "Expected mediators with 8 nodes"

    # Mediator should be between collider and target in the chain
    chain_from_collider = []
    children: dict[str, list[str]] = {n.name: [] for n in world.nodes}
    for e in world.edges:
        children[e.from_node].append(e.to_node)

    # Walk from collider to target
    node = "collider"
    while node != "target_outcome":
        next_nodes = [c for c in children[node] if c != "collider"]
        if not next_nodes:
            break
        chain_from_collider.append(next_nodes[0])
        node = next_nodes[0]

    for m in mediator_names:
        assert m in chain_from_collider, f"Mediator {m} not in chain from collider to target"
