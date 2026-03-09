"""Tests for DAGSpec and DAGNodeSpec models."""

import pytest

from sreg.models.dag_spec import DAGNodeSpec, DAGSpec, MAX_PARENTS
from sreg.models.world import NodeType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simple_spec() -> DAGSpec:
    """Minimal valid DAGSpec: A -> B (observable -> target)."""
    return DAGSpec(
        nodes=[
            DAGNodeSpec(name="A", type=NodeType.OBSERVABLE, states=["low", "high"]),
            DAGNodeSpec(name="B", type=NodeType.TARGET, states=["low", "medium", "high"]),
        ],
        edges=[("A", "B")],
    )


def _diamond_spec() -> DAGSpec:
    """Diamond: latent -> obs1, latent -> obs2, obs1 -> target, obs2 -> target."""
    return DAGSpec(
        nodes=[
            DAGNodeSpec(name="latent", type=NodeType.LATENT, states=["on", "off"]),
            DAGNodeSpec(name="obs1", type=NodeType.OBSERVABLE, states=["low", "high"]),
            DAGNodeSpec(name="obs2", type=NodeType.OBSERVABLE, states=["a", "b", "c"]),
            DAGNodeSpec(name="target", type=NodeType.TARGET, states=["low", "medium", "high"]),
        ],
        edges=[
            ("latent", "obs1"),
            ("latent", "obs2"),
            ("obs1", "target"),
            ("obs2", "target"),
        ],
    )


# ---------------------------------------------------------------------------
# DAGNodeSpec
# ---------------------------------------------------------------------------

class TestDAGNodeSpec:
    def test_basic_creation(self):
        node = DAGNodeSpec(name="temp", type=NodeType.OBSERVABLE, states=["low", "high"])
        assert node.name == "temp"
        assert node.type == NodeType.OBSERVABLE
        assert node.states == ["low", "high"]
        assert node.role is None

    def test_with_role(self):
        node = DAGNodeSpec(
            name="x", type=NodeType.LATENT, states=["a", "b"], role="confounder"
        )
        assert node.role == "confounder"

    def test_min_states(self):
        with pytest.raises(Exception):
            DAGNodeSpec(name="x", type=NodeType.OBSERVABLE, states=["only_one"])

    def test_heterogeneous_states(self):
        """Nodes can have different numbers of states."""
        n2 = DAGNodeSpec(name="binary", type=NodeType.OBSERVABLE, states=["yes", "no"])
        n3 = DAGNodeSpec(name="ternary", type=NodeType.OBSERVABLE, states=["a", "b", "c"])
        n4 = DAGNodeSpec(name="quaternary", type=NodeType.TARGET, states=["w", "x", "y", "z"])
        assert len(n2.states) == 2
        assert len(n3.states) == 3
        assert len(n4.states) == 4


# ---------------------------------------------------------------------------
# DAGSpec — valid cases
# ---------------------------------------------------------------------------

class TestDAGSpecValid:
    def test_simple(self):
        spec = _simple_spec()
        assert len(spec.nodes) == 2
        assert len(spec.edges) == 1

    def test_diamond(self):
        spec = _diamond_spec()
        assert len(spec.nodes) == 4
        assert len(spec.edges) == 4

    def test_no_edges(self):
        """A DAGSpec with no edges is valid (disconnected nodes)."""
        spec = DAGSpec(
            nodes=[
                DAGNodeSpec(name="A", type=NodeType.OBSERVABLE, states=["lo", "hi"]),
                DAGNodeSpec(name="B", type=NodeType.TARGET, states=["lo", "hi"]),
            ],
            edges=[],
        )
        assert len(spec.edges) == 0

    def test_chain_10_nodes(self):
        """A chain of 10 nodes is valid."""
        nodes = []
        for i in range(10):
            if i == 0:
                ntype = NodeType.LATENT
            elif i == 9:
                ntype = NodeType.TARGET
            else:
                ntype = NodeType.OBSERVABLE
            nodes.append(DAGNodeSpec(name=f"v{i}", type=ntype, states=["lo", "hi"]))
        edges = [(f"v{i}", f"v{i+1}") for i in range(9)]
        spec = DAGSpec(nodes=nodes, edges=edges)
        assert len(spec.nodes) == 10

    def test_max_parents_at_limit(self):
        """A node with exactly MAX_PARENTS parents is valid."""
        parents = [
            DAGNodeSpec(name=f"p{i}", type=NodeType.OBSERVABLE, states=["lo", "hi"])
            for i in range(MAX_PARENTS)
        ]
        target = DAGNodeSpec(name="target", type=NodeType.TARGET, states=["lo", "hi"])
        edges = [(f"p{i}", "target") for i in range(MAX_PARENTS)]
        spec = DAGSpec(nodes=parents + [target], edges=edges)
        assert len(spec.parents_of("target")) == MAX_PARENTS

    def test_multiple_targets(self):
        """Multiple target nodes are allowed."""
        spec = DAGSpec(
            nodes=[
                DAGNodeSpec(name="A", type=NodeType.OBSERVABLE, states=["lo", "hi"]),
                DAGNodeSpec(name="T1", type=NodeType.TARGET, states=["lo", "hi"]),
                DAGNodeSpec(name="T2", type=NodeType.TARGET, states=["lo", "hi"]),
            ],
            edges=[("A", "T1"), ("A", "T2")],
        )
        assert len(spec.nodes_by_type(NodeType.TARGET)) == 2

    def test_multiple_latents(self):
        """Multiple latent nodes are allowed."""
        spec = DAGSpec(
            nodes=[
                DAGNodeSpec(name="L1", type=NodeType.LATENT, states=["a", "b"]),
                DAGNodeSpec(name="L2", type=NodeType.LATENT, states=["a", "b"]),
                DAGNodeSpec(name="O", type=NodeType.OBSERVABLE, states=["lo", "hi"]),
                DAGNodeSpec(name="T", type=NodeType.TARGET, states=["lo", "hi"]),
            ],
            edges=[("L1", "O"), ("L2", "O"), ("O", "T")],
        )
        assert len(spec.nodes_by_type(NodeType.LATENT)) == 2

    def test_heterogeneous_states(self):
        """Nodes with different numbers of states."""
        spec = DAGSpec(
            nodes=[
                DAGNodeSpec(name="bin", type=NodeType.OBSERVABLE, states=["yes", "no"]),
                DAGNodeSpec(name="tri", type=NodeType.OBSERVABLE, states=["a", "b", "c"]),
                DAGNodeSpec(name="target", type=NodeType.TARGET, states=["w", "x", "y", "z"]),
            ],
            edges=[("bin", "target"), ("tri", "target")],
        )
        assert len(spec.get_node("bin").states) == 2
        assert len(spec.get_node("tri").states) == 3
        assert len(spec.get_node("target").states) == 4


# ---------------------------------------------------------------------------
# DAGSpec — invalid cases
# ---------------------------------------------------------------------------

class TestDAGSpecInvalid:
    def test_cycle(self):
        with pytest.raises(ValueError, match="cycles"):
            DAGSpec(
                nodes=[
                    DAGNodeSpec(name="A", type=NodeType.OBSERVABLE, states=["lo", "hi"]),
                    DAGNodeSpec(name="B", type=NodeType.TARGET, states=["lo", "hi"]),
                ],
                edges=[("A", "B"), ("B", "A")],
            )

    def test_self_loop(self):
        with pytest.raises(ValueError):
            DAGSpec(
                nodes=[
                    DAGNodeSpec(name="A", type=NodeType.OBSERVABLE, states=["lo", "hi"]),
                    DAGNodeSpec(name="B", type=NodeType.TARGET, states=["lo", "hi"]),
                ],
                edges=[("A", "A"), ("A", "B")],
            )

    def test_no_target(self):
        with pytest.raises(ValueError, match="TARGET"):
            DAGSpec(
                nodes=[
                    DAGNodeSpec(name="A", type=NodeType.OBSERVABLE, states=["lo", "hi"]),
                    DAGNodeSpec(name="B", type=NodeType.OBSERVABLE, states=["lo", "hi"]),
                ],
                edges=[("A", "B")],
            )

    def test_no_observable(self):
        with pytest.raises(ValueError, match="OBSERVABLE"):
            DAGSpec(
                nodes=[
                    DAGNodeSpec(name="A", type=NodeType.LATENT, states=["lo", "hi"]),
                    DAGNodeSpec(name="B", type=NodeType.TARGET, states=["lo", "hi"]),
                ],
                edges=[("A", "B")],
            )

    def test_unknown_edge_source(self):
        with pytest.raises(ValueError, match="unknown node"):
            DAGSpec(
                nodes=[
                    DAGNodeSpec(name="A", type=NodeType.OBSERVABLE, states=["lo", "hi"]),
                    DAGNodeSpec(name="B", type=NodeType.TARGET, states=["lo", "hi"]),
                ],
                edges=[("GHOST", "B")],
            )

    def test_unknown_edge_target(self):
        with pytest.raises(ValueError, match="unknown node"):
            DAGSpec(
                nodes=[
                    DAGNodeSpec(name="A", type=NodeType.OBSERVABLE, states=["lo", "hi"]),
                    DAGNodeSpec(name="B", type=NodeType.TARGET, states=["lo", "hi"]),
                ],
                edges=[("A", "GHOST")],
            )

    def test_duplicate_node_names(self):
        with pytest.raises(ValueError, match="Duplicate"):
            DAGSpec(
                nodes=[
                    DAGNodeSpec(name="A", type=NodeType.OBSERVABLE, states=["lo", "hi"]),
                    DAGNodeSpec(name="A", type=NodeType.TARGET, states=["lo", "hi"]),
                ],
                edges=[],
            )

    def test_too_many_parents(self):
        parents = [
            DAGNodeSpec(name=f"p{i}", type=NodeType.OBSERVABLE, states=["lo", "hi"])
            for i in range(MAX_PARENTS + 1)
        ]
        target = DAGNodeSpec(name="target", type=NodeType.TARGET, states=["lo", "hi"])
        edges = [(f"p{i}", "target") for i in range(MAX_PARENTS + 1)]
        with pytest.raises(ValueError, match="max parents"):
            DAGSpec(nodes=parents + [target], edges=edges)

    def test_too_few_nodes(self):
        with pytest.raises(Exception):
            DAGSpec(
                nodes=[
                    DAGNodeSpec(name="A", type=NodeType.TARGET, states=["lo", "hi"]),
                ],
                edges=[],
            )


# ---------------------------------------------------------------------------
# DAGSpec — convenience methods
# ---------------------------------------------------------------------------

class TestDAGSpecMethods:
    def test_node_names(self):
        spec = _diamond_spec()
        assert spec.node_names() == ["latent", "obs1", "obs2", "target"]

    def test_get_node(self):
        spec = _diamond_spec()
        node = spec.get_node("obs1")
        assert node.type == NodeType.OBSERVABLE

    def test_get_node_missing(self):
        spec = _simple_spec()
        with pytest.raises(KeyError):
            spec.get_node("nonexistent")

    def test_parents_of(self):
        spec = _diamond_spec()
        assert sorted(spec.parents_of("target")) == ["obs1", "obs2"]
        assert spec.parents_of("latent") == []

    def test_children_of(self):
        spec = _diamond_spec()
        assert sorted(spec.children_of("latent")) == ["obs1", "obs2"]
        assert spec.children_of("target") == []

    def test_to_networkx(self):
        spec = _diamond_spec()
        g = spec.to_networkx()
        assert len(g.nodes) == 4
        assert len(g.edges) == 4
        assert g.has_edge("latent", "obs1")

    def test_nodes_by_type(self):
        spec = _diamond_spec()
        assert len(spec.nodes_by_type(NodeType.OBSERVABLE)) == 2
        assert len(spec.nodes_by_type(NodeType.LATENT)) == 1
        assert len(spec.nodes_by_type(NodeType.TARGET)) == 1

    def test_serialization_roundtrip(self):
        """DAGSpec serializes to JSON and back."""
        spec = _diamond_spec()
        data = spec.model_dump()
        restored = DAGSpec(**data)
        assert restored.node_names() == spec.node_names()
        assert restored.edges == spec.edges
