"""Tests for EpisodeGenTool."""

import pytest

from sreg.models.episode import Episode
from sreg.models.world import NodeType
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool
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


def test_generate_episode(world):
    tool = EpisodeGenTool()
    ep = tool.generate(world, EpisodeGenConfig(budget=5, seed=0))

    assert isinstance(ep, Episode)
    assert ep.budget == 5
    assert ep.world_id == world.id
    assert len(ep.steps) == 0
    assert len(ep.initial_evidence) == 0


def test_available_nodes_are_observable(world):
    tool = EpisodeGenTool()
    ep = tool.generate(world, EpisodeGenConfig(budget=5, seed=0))

    obs_names = {n.name for n in world.nodes if n.type == NodeType.OBSERVABLE}
    assert set(ep.available_nodes) == obs_names


def test_node_costs_set(world):
    tool = EpisodeGenTool()
    ep = tool.generate(world, EpisodeGenConfig(budget=5, node_cost=2, seed=0))

    for name, cost in ep.node_costs.items():
        assert cost == 2


def test_initial_evidence(world, true_state):
    tool = EpisodeGenTool()
    ep = tool.generate(
        world,
        EpisodeGenConfig(budget=5, initial_evidence_count=2, seed=0),
        true_state=true_state,
    )

    assert len(ep.initial_evidence) == 2
    for obs in ep.initial_evidence:
        assert obs.state == true_state[obs.node]
        assert obs.node not in ep.available_nodes  # removed from available


def test_initial_evidence_capped_by_available(world, true_state):
    obs_count = sum(1 for n in world.nodes if n.type == NodeType.OBSERVABLE)
    tool = EpisodeGenTool()
    # Request more initial evidence than observables minus 1 (must leave >=1 available)
    ep = tool.generate(
        world,
        EpisodeGenConfig(budget=5, initial_evidence_count=obs_count - 1, seed=0),
        true_state=true_state,
    )

    assert len(ep.initial_evidence) == obs_count - 1
    assert len(ep.available_nodes) >= 1


def test_episode_id_format(world):
    tool = EpisodeGenTool()
    ep = tool.generate(world, EpisodeGenConfig(budget=3, seed=7))
    assert ep.id == f"ep-{world.id}-0007"


def test_no_initial_evidence_without_true_state(world):
    tool = EpisodeGenTool()
    ep = tool.generate(world, EpisodeGenConfig(budget=5, initial_evidence_count=2, seed=0))
    assert len(ep.initial_evidence) == 0
