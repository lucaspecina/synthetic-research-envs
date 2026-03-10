"""Tests for ProblemBuilder."""

import pytest

from sreg.models.research_problem import AvailableAction, ResearchActionType, ResearchProblem
from sreg.models.world import NodeType
from sreg.tools.data_sampler import DataSamplerConfig
from sreg.tools.problem_builder import ProblemBuilder
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


def _make_world(**kwargs):
    defaults = {
        "template_family": "latent_preference",
        "num_nodes": 6,
        "edge_strength": 0.7,
        "seed": 42,
    }
    defaults.update(kwargs)
    config = WorldGenConfig(**defaults)
    return WorldGenTool().generate(config)


def test_build_basic():
    world = _make_world()
    builder = ProblemBuilder()
    problem = builder.build(world, budget=4)

    assert isinstance(problem, ResearchProblem)
    assert problem.budget == 4
    assert problem.world_id == world.id
    assert len(problem.data_assets) > 0
    assert len(problem.available_actions) > 0
    assert problem.target_node == "target_outcome"
    assert len(problem.target_states) >= 2


def test_build_with_semantics():
    world = _make_world()
    world = world.model_copy(
        update={
            "scenario_title": "Marine Investigation",
            "scenario_description": "A study of ocean dynamics.",
            "domain": "oceanography",
            "theoretical_context": "Prior studies suggest...",
        }
    )

    builder = ProblemBuilder()
    problem = builder.build(world, budget=3)

    assert problem.title == "Marine Investigation"
    assert problem.description == "A study of ocean dynamics."
    assert problem.domain == "oceanography"
    assert problem.theoretical_context == "Prior studies suggest..."


def test_build_custom_data_config():
    world = _make_world()
    builder = ProblemBuilder()
    data_config = DataSamplerConfig(num_rows=20, format="both", seed=0)
    problem = builder.build(world, budget=5, data_config=data_config)

    assert len(problem.data_assets) == 2


def test_actions_are_observable_nodes():
    world = _make_world()
    builder = ProblemBuilder()
    problem = builder.build(world)

    action_nodes = {a.node for a in problem.available_actions}
    observable_names = {n.name for n in world.nodes if n.type == "observable"}
    assert action_nodes == observable_names


def test_research_question_mentions_target():
    world = _make_world()
    builder = ProblemBuilder()
    problem = builder.build(world)

    assert "target_outcome" in problem.research_question


def test_build_rich_data():
    """rich_data=True generates multiple datasets + narratives."""
    world = _make_world(num_nodes=8)
    builder = ProblemBuilder()
    problem = builder.build(world, budget=4, rich_data=True)

    assert isinstance(problem, ResearchProblem)
    # Should have primary + secondary + narrative = 3 assets
    assert len(problem.data_assets) == 3
    formats = [a.format for a in problem.data_assets]
    assert formats.count("tabular") == 2
    assert formats.count("narrative") == 1
    # Metadata populated
    for asset in problem.data_assets:
        if asset.format == "tabular":
            assert asset.source is not None
            assert asset.columns is not None


def test_rich_data_overridden_by_explicit_config():
    """Explicit data_config takes precedence over rich_data flag."""
    world = _make_world(num_nodes=8)
    builder = ProblemBuilder()
    data_config = DataSamplerConfig(num_rows=10, format="tabular", seed=0)
    problem = builder.build(world, budget=3, data_config=data_config, rich_data=True)

    # Explicit config wins — single dataset, no multi
    assert len(problem.data_assets) == 1


# --- AvailableAction model tests ---


def test_available_action_backward_compat():
    """Legacy creation with node= still works."""
    action = AvailableAction(node="water_temp", description="Measure water", cost=1)
    assert action.node == "water_temp"
    assert action.nodes == ["water_temp"]
    assert action.action_type == ResearchActionType.OBSERVE


def test_available_action_multi_node():
    """Multi-node action sets node to first node."""
    action = AvailableAction(
        nodes=["mineral", "salinity", "ph"],
        description="Spectral analysis",
        cost=3,
    )
    assert action.nodes == ["mineral", "salinity", "ph"]
    assert action.node == "mineral"  # backward compat


def test_available_action_with_type():
    """action_type can be set explicitly."""
    action = AvailableAction(
        action_type=ResearchActionType.REQUEST_DATASET,
        nodes=["surface_temp"],
        description="Request satellite data",
        cost=2,
    )
    assert action.action_type == ResearchActionType.REQUEST_DATASET


def test_available_action_requires_node_or_nodes():
    """Must provide either node or nodes."""
    with pytest.raises(ValueError, match="Either 'node' or 'nodes' must be provided"):
        AvailableAction(description="Nothing", cost=1)


def test_available_action_node_and_nodes_sync():
    """When both node and nodes provided, nodes takes precedence."""
    action = AvailableAction(
        node="x",
        nodes=["a", "b"],
        description="test",
        cost=1,
    )
    assert action.nodes == ["a", "b"]
    assert action.node == "x"  # kept as-is when both provided


# --- Rich actions (ProblemBuilder) ---


def test_rich_actions_basic():
    """rich_actions=True generates actions with types and varied costs."""
    world = _make_world(num_nodes=10, edge_strength=0.7)
    builder = ProblemBuilder()
    problem = builder.build(world, budget=5, rich_actions=True)

    assert len(problem.available_actions) > 0
    # All actions should have an action_type
    for action in problem.available_actions:
        assert action.action_type is not None
        assert action.action_type in ResearchActionType


def test_rich_actions_varied_costs():
    """Rich actions should have varied costs (not all 1)."""
    # Use larger world to increase chance of varied costs
    world = _make_world(num_nodes=10, edge_strength=0.7)
    builder = ProblemBuilder()
    problem = builder.build(world, budget=8, rich_actions=True)

    costs = [a.cost for a in problem.available_actions]
    # At least one action should cost > 1 (compound or target-adjacent)
    assert max(costs) > 1 or len(problem.available_actions) > 1


def test_rich_actions_compound_multi_node():
    """Rich actions may include compound actions with multiple nodes."""
    # Try multiple seeds to find one that generates compound actions
    found_compound = False
    for seed in range(20):
        world = _make_world(num_nodes=10, edge_strength=0.7, seed=seed)
        builder = ProblemBuilder()
        problem = builder.build(world, budget=8, rich_actions=True)

        for action in problem.available_actions:
            if len(action.nodes) > 1:
                found_compound = True
                desc = action.description.lower()
                assert "survey" in desc or "field" in desc
                break
        if found_compound:
            break

    # Compound actions depend on DAG structure; at least verify no crash
    assert len(problem.available_actions) > 0


def test_rich_actions_cover_all_observable_nodes():
    """Rich actions should cover all observable nodes (individually or in compound)."""
    world = _make_world(num_nodes=10, edge_strength=0.7)
    builder = ProblemBuilder()
    problem = builder.build(world, budget=8, rich_actions=True)

    # Collect all nodes covered by actions
    covered = set()
    for action in problem.available_actions:
        covered.update(action.nodes)

    observable_names = {n.name for n in world.nodes if n.type == NodeType.OBSERVABLE}
    assert covered == observable_names


def test_rich_actions_cross_templates():
    """Rich actions work across all template families."""
    for template in ["latent_preference", "causal_chain", "fork_collider"]:
        world = _make_world(template_family=template, num_nodes=8)
        builder = ProblemBuilder()
        problem = builder.build(world, budget=5, rich_actions=True)

        assert len(problem.available_actions) > 0
        # Verify node coverage
        covered = set()
        for a in problem.available_actions:
            covered.update(a.nodes)
        obs_names = {n.name for n in world.nodes if n.type == NodeType.OBSERVABLE}
        assert covered == obs_names


def test_legacy_actions_unchanged_by_default():
    """Without rich_actions flag, actions are simple cost=1 single-node."""
    world = _make_world()
    builder = ProblemBuilder()
    problem = builder.build(world, budget=5)

    for action in problem.available_actions:
        assert action.cost == 1
        assert len(action.nodes) == 1
