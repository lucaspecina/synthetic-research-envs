"""Tests for world generation tool and latent preference template."""

import pytest

from sreg.models.world import NodeType
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


@pytest.fixture
def gen():
    return WorldGenTool()


def test_generate_default_world(gen):
    config = WorldGenConfig(seed=42)
    world = gen.generate(config)

    assert world.id == "world-000042"
    assert world.seed == 42
    assert world.template_family == "latent_preference"
    assert len(world.nodes) == 6  # default num_nodes
    assert len(world.cpds) == 6


def test_world_has_correct_node_types(gen):
    config = WorldGenConfig(seed=0, num_nodes=6, num_latent=1)
    world = gen.generate(config)

    latent = [n for n in world.nodes if n.type == NodeType.LATENT]
    obs = [n for n in world.nodes if n.type == NodeType.OBSERVABLE]
    target = [n for n in world.nodes if n.type == NodeType.TARGET]

    assert len(latent) == 1
    assert len(obs) == 4  # 6 - 1 latent - 1 target
    assert len(target) == 1
    assert target[0].name == "target_outcome"


def test_world_has_correct_states(gen):
    config = WorldGenConfig(seed=0, num_states=3)
    world = gen.generate(config)

    for node in world.nodes:
        assert node.states == ["low", "medium", "high"]


def test_world_has_binary_states(gen):
    config = WorldGenConfig(seed=0, num_states=2)
    world = gen.generate(config)

    for node in world.nodes:
        assert node.states == ["low", "high"]


def test_world_deterministic_from_seed(gen):
    config = WorldGenConfig(seed=123)
    w1 = gen.generate(config)
    w2 = gen.generate(config)

    assert w1.model_dump() == w2.model_dump()


def test_different_seeds_produce_different_worlds(gen):
    w1 = gen.generate(WorldGenConfig(seed=1))
    w2 = gen.generate(WorldGenConfig(seed=2))

    # CPDs should differ (different random draws)
    assert w1.cpds[0].table != w2.cpds[0].table


def test_world_with_two_latent_nodes(gen):
    config = WorldGenConfig(seed=0, num_nodes=7, num_latent=2)
    world = gen.generate(config)

    latent = [n for n in world.nodes if n.type == NodeType.LATENT]
    assert len(latent) == 2
    assert latent[0].name == "hidden_cause_1"
    assert latent[1].name == "hidden_cause_2"


def test_minimal_world_3_nodes(gen):
    config = WorldGenConfig(seed=0, num_nodes=3, num_latent=1)
    world = gen.generate(config)

    assert len(world.nodes) == 3
    assert len([n for n in world.nodes if n.type == NodeType.OBSERVABLE]) == 1


def test_config_rejects_insufficient_nodes():
    with pytest.raises(ValueError, match="num_nodes"):
        WorldGenConfig(num_nodes=2, num_latent=1)


def test_config_rejects_too_many_latent():
    with pytest.raises(ValueError, match="num_nodes"):
        WorldGenConfig(num_nodes=4, num_latent=3)  # needs at least latent+2


def test_unknown_template(gen):
    config = WorldGenConfig(template_family="nonexistent", seed=0)
    with pytest.raises(ValueError, match="Unknown template"):
        gen.generate(config)


def test_modifier_edge_with_enough_observables(gen):
    config = WorldGenConfig(seed=0, num_nodes=6, num_latent=1)
    world = gen.generate(config)

    # With 4 observables (>= 3), there should be a modifier edge to target
    target_parents = [e.from_node for e in world.edges if e.to_node == "target_outcome"]
    obs_parents = [
        p
        for p in target_parents
        if any(n.name == p and n.type == NodeType.OBSERVABLE for n in world.nodes)
    ]
    assert len(obs_parents) == 1  # one modifier observable


def test_no_modifier_with_few_observables(gen):
    config = WorldGenConfig(seed=0, num_nodes=4, num_latent=1)  # 2 observables
    world = gen.generate(config)

    target_parents = [e.from_node for e in world.edges if e.to_node == "target_outcome"]
    obs_parents = [
        p
        for p in target_parents
        if any(n.name == p and n.type == NodeType.OBSERVABLE for n in world.nodes)
    ]
    assert len(obs_parents) == 0  # no modifier


def test_cpds_sum_to_one(gen):
    config = WorldGenConfig(seed=42)
    world = gen.generate(config)

    for cpd in world.cpds:
        num_cols = len(cpd.table[0])
        for col in range(num_cols):
            col_sum = sum(row[col] for row in cpd.table)
            assert abs(col_sum - 1.0) < 1e-6, f"CPD {cpd.node} col {col} sums to {col_sum}"


def test_serialization_roundtrip(gen):
    config = WorldGenConfig(seed=42)
    world = gen.generate(config)

    from sreg.models.world import World

    json_str = world.model_dump_json()
    restored = World.model_validate_json(json_str)
    assert restored.id == world.id
    assert len(restored.nodes) == len(world.nodes)


def test_generate_100_worlds(gen):
    """Generate 100 worlds and verify all are valid."""
    for seed in range(100):
        config = WorldGenConfig(seed=seed)
        world = gen.generate(config)

        # Basic structural checks
        assert len(world.nodes) == 6
        assert len(world.cpds) == 6
        target = [n for n in world.nodes if n.type == NodeType.TARGET]
        assert len(target) == 1

        # CPDs sum to 1
        for cpd in world.cpds:
            for col in range(len(cpd.table[0])):
                col_sum = sum(row[col] for row in cpd.table)
                assert abs(col_sum - 1.0) < 1e-6
