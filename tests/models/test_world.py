"""Tests for world data models."""

import pytest
from pydantic import ValidationError

from sreg.models.world import CPD, DifficultyProfile, Edge, Node, NodeType, World

# --- Node ---


def test_node_creation():
    node = Node(
        name="thermal_flux",
        type=NodeType.OBSERVABLE,
        description="Measures heat transfer rate",
        states=["low", "medium", "high"],
    )
    assert node.name == "thermal_flux"
    assert node.type == NodeType.OBSERVABLE
    assert len(node.states) == 3


def test_node_requires_at_least_two_states():
    with pytest.raises(ValidationError):
        Node(name="x", type=NodeType.OBSERVABLE, description="bad", states=["only_one"])


def test_node_type_values():
    assert NodeType.OBSERVABLE == "observable"
    assert NodeType.LATENT == "latent"
    assert NodeType.TARGET == "target"


# --- Edge ---


def test_edge_creation():
    edge = Edge(from_node="A", to_node="B", mechanism="A causes B")
    assert edge.from_node == "A"
    assert edge.to_node == "B"


# --- CPD ---


def test_cpd_root_node():
    cpd = CPD(
        node="weather",
        parents=[],
        table=[[0.3], [0.7]],
        state_names={"weather": ["sunny", "rainy"]},
    )
    assert cpd.node == "weather"
    assert len(cpd.parents) == 0


def test_cpd_with_one_parent():
    cpd = CPD(
        node="mood",
        parents=["weather"],
        table=[
            [0.9, 0.4],  # P(happy | sunny), P(happy | rainy)
            [0.1, 0.6],  # P(sad | sunny), P(sad | rainy)
        ],
        state_names={"mood": ["happy", "sad"], "weather": ["sunny", "rainy"]},
    )
    assert cpd.table[0][0] == 0.9


def test_cpd_with_two_parents():
    # Parent combos: (sunny, low), (sunny, high), (rainy, low), (rainy, high)
    cpd = CPD(
        node="activity",
        parents=["weather", "energy"],
        table=[
            [0.8, 0.6, 0.3, 0.2],  # P(outdoor | ...)
            [0.2, 0.4, 0.7, 0.8],  # P(indoor | ...)
        ],
        state_names={
            "activity": ["outdoor", "indoor"],
            "weather": ["sunny", "rainy"],
            "energy": ["low", "high"],
        },
    )
    assert len(cpd.table[0]) == 4


def test_cpd_rejects_wrong_row_count():
    with pytest.raises(ValidationError, match="rows"):
        CPD(
            node="x",
            parents=[],
            table=[[0.3], [0.5], [0.2]],  # 3 rows but only 2 states
            state_names={"x": ["a", "b"]},
        )


def test_cpd_rejects_wrong_column_count():
    with pytest.raises(ValidationError, match="columns"):
        CPD(
            node="x",
            parents=["p"],
            table=[[0.5, 0.5, 0.5], [0.5, 0.5, 0.5]],  # 3 cols but parent has 2 states
            state_names={"x": ["a", "b"], "p": ["s1", "s2"]},
        )


def test_cpd_rejects_probabilities_not_summing_to_one():
    with pytest.raises(ValidationError, match="sums to"):
        CPD(
            node="x",
            parents=[],
            table=[[0.3], [0.3]],  # sums to 0.6
            state_names={"x": ["a", "b"]},
        )


# --- DifficultyProfile ---


def test_difficulty_profile():
    dp = DifficultyProfile(
        level="medium",
        num_nodes=6,
        num_latent=2,
        num_observable=3,
        edge_density=0.4,
        avg_states_per_node=2.5,
    )
    assert dp.level == "medium"
    assert dp.posterior_entropy is None


# --- World ---


def _make_minimal_world(**overrides) -> World:
    """Helper to build a minimal valid world."""
    nodes = overrides.pop(
        "nodes",
        [
            Node(
                name="cause",
                type=NodeType.OBSERVABLE,
                description="The cause",
                states=["low", "high"],
            ),
            Node(
                name="effect",
                type=NodeType.TARGET,
                description="The effect",
                states=["off", "on"],
            ),
        ],
    )
    edges = overrides.pop(
        "edges",
        [Edge(from_node="cause", to_node="effect", mechanism="cause drives effect")],
    )
    cpds = overrides.pop(
        "cpds",
        [
            CPD(
                node="cause",
                parents=[],
                table=[[0.5], [0.5]],
                state_names={"cause": ["low", "high"]},
            ),
            CPD(
                node="effect",
                parents=["cause"],
                table=[[0.9, 0.2], [0.1, 0.8]],
                state_names={"effect": ["off", "on"], "cause": ["low", "high"]},
            ),
        ],
    )
    difficulty = overrides.pop(
        "difficulty",
        DifficultyProfile(
            level="easy",
            num_nodes=2,
            num_latent=0,
            num_observable=1,
            edge_density=1.0,
            avg_states_per_node=2.0,
        ),
    )

    defaults = dict(
        id="world-001",
        seed=42,
        template_family="latent_preference",
        description="A test world",
        nodes=nodes,
        edges=edges,
        cpds=cpds,
        difficulty=difficulty,
    )
    defaults.update(overrides)
    return World(**defaults)


def test_world_creation():
    world = _make_minimal_world()
    assert world.id == "world-001"
    assert len(world.nodes) == 2
    assert len(world.edges) == 1
    assert len(world.cpds) == 2


def test_world_rejects_missing_target():
    with pytest.raises(ValidationError, match="target"):
        _make_minimal_world(
            nodes=[
                Node(name="a", type=NodeType.OBSERVABLE, description="a", states=["x", "y"]),
                Node(name="b", type=NodeType.OBSERVABLE, description="b", states=["x", "y"]),
            ],
            edges=[],
            cpds=[
                CPD(node="a", parents=[], table=[[0.5], [0.5]], state_names={"a": ["x", "y"]}),
                CPD(node="b", parents=[], table=[[0.5], [0.5]], state_names={"b": ["x", "y"]}),
            ],
        )


def test_world_rejects_edge_to_unknown_node():
    with pytest.raises(ValidationError, match="unknown node"):
        _make_minimal_world(
            edges=[Edge(from_node="cause", to_node="ghost", mechanism="broken")],
        )


def test_world_rejects_missing_cpd():
    with pytest.raises(ValidationError, match="without CPDs"):
        _make_minimal_world(
            cpds=[
                CPD(
                    node="cause",
                    parents=[],
                    table=[[0.5], [0.5]],
                    state_names={"cause": ["low", "high"]},
                ),
                # missing CPD for "effect"
            ],
        )


def test_world_serialization_roundtrip():
    world = _make_minimal_world()
    json_str = world.model_dump_json()
    restored = World.model_validate_json(json_str)
    assert restored.id == world.id
    assert len(restored.nodes) == len(world.nodes)
    assert restored.cpds[1].table == world.cpds[1].table
