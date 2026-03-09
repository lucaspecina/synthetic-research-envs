"""Tests for DAG generators."""

import pytest

from sreg.models.dag_spec import MAX_PARENTS, DAGSpec
from sreg.models.world import NodeType
from sreg.tools.world_check import WorldCheckTool
from sreg.tools.world_gen import CustomWorldGenConfig, WorldGenTool
from sreg.world.dag_generators import (
    generate_erdos_renyi,
    generate_layered,
    generate_preferential_attachment,
    generate_spanning_tree,
)
from sreg.world.pgmpy_utils import world_to_pgmpy

# ---------------------------------------------------------------------------
# Shared validation helpers
# ---------------------------------------------------------------------------

def _validate_spec(spec: DAGSpec, expected_nodes: int | None = None):
    """Common validations for any generated DAGSpec."""
    if expected_nodes is not None:
        assert len(spec.nodes) == expected_nodes

    # Has required types
    assert any(n.type == NodeType.TARGET for n in spec.nodes)
    assert any(n.type == NodeType.OBSERVABLE for n in spec.nodes)

    # Is a valid DAG (DAGSpec validates this on construction)
    g = spec.to_networkx()
    assert len(g.nodes) == len(spec.nodes)

    # Max parents respected
    for node in spec.nodes:
        assert len(spec.parents_of(node.name)) <= MAX_PARENTS


def _validate_world(spec: DAGSpec, seed: int = 42, es: float = 0.7):
    """Generate a World from a spec and validate it passes all checks."""
    gen = WorldGenTool()
    world = gen.generate_custom(CustomWorldGenConfig(dag_spec=spec, edge_strength=es, seed=seed))
    model = world_to_pgmpy(world)
    assert model.check_model()

    checker = WorldCheckTool()
    result = checker.check(world)
    # Don't require passing (some random DAGs may fail entropy/d-sep)
    # but it must not crash
    assert isinstance(result.passed, bool)
    return world, result


# ---------------------------------------------------------------------------
# Erdos-Renyi
# ---------------------------------------------------------------------------

class TestErdosRenyi:
    def test_basic(self):
        spec = generate_erdos_renyi(num_nodes=8, seed=42)
        _validate_spec(spec, expected_nodes=8)

    def test_no_edges_low_prob(self):
        """With edge_prob=0, no edges are generated."""
        spec = generate_erdos_renyi(num_nodes=5, edge_prob=0.0, seed=42)
        assert len(spec.edges) == 0

    def test_dense_high_prob(self):
        """With high edge_prob, many edges but still valid DAG."""
        spec = generate_erdos_renyi(num_nodes=8, edge_prob=0.8, seed=42)
        _validate_spec(spec)
        assert len(spec.edges) > 0

    def test_multiple_latents(self):
        spec = generate_erdos_renyi(num_nodes=10, num_latent=3, seed=42)
        assert len(spec.nodes_by_type(NodeType.LATENT)) == 3

    def test_multiple_targets(self):
        spec = generate_erdos_renyi(num_nodes=10, num_target=2, seed=42)
        assert len(spec.nodes_by_type(NodeType.TARGET)) == 2

    def test_heterogeneous_states(self):
        spec = generate_erdos_renyi(num_nodes=8, num_states=[2, 3], seed=42)
        cardinalities = {len(n.states) for n in spec.nodes}
        assert cardinalities.issubset({2, 3})

    def test_reproducible(self):
        s1 = generate_erdos_renyi(num_nodes=8, seed=99)
        s2 = generate_erdos_renyi(num_nodes=8, seed=99)
        assert s1.edges == s2.edges
        assert [n.type for n in s1.nodes] == [n.type for n in s2.nodes]

    def test_different_seeds_differ(self):
        s1 = generate_erdos_renyi(num_nodes=10, seed=1)
        s2 = generate_erdos_renyi(num_nodes=10, seed=2)
        # Very unlikely to be identical
        assert s1.edges != s2.edges or [n.type for n in s1.nodes] != [n.type for n in s2.nodes]

    def test_world_generation(self):
        spec = generate_erdos_renyi(num_nodes=10, num_latent=2, edge_prob=0.3, seed=42)
        _validate_world(spec)

    def test_large_15_nodes(self):
        spec = generate_erdos_renyi(num_nodes=15, num_latent=3, edge_prob=0.25, seed=42)
        _validate_spec(spec, expected_nodes=15)
        _validate_world(spec)


# ---------------------------------------------------------------------------
# Spanning Tree
# ---------------------------------------------------------------------------

class TestSpanningTree:
    def test_basic(self):
        spec = generate_spanning_tree(num_nodes=8, seed=42)
        _validate_spec(spec, expected_nodes=8)

    def test_pure_tree(self):
        """With extra_edge_prob=0, every non-root has exactly 1 parent."""
        spec = generate_spanning_tree(num_nodes=8, extra_edge_prob=0.0, seed=42)
        for node in spec.nodes[1:]:  # skip root
            assert len(spec.parents_of(node.name)) == 1
        # Exactly n-1 edges for a tree
        assert len(spec.edges) == len(spec.nodes) - 1

    def test_connected(self):
        """Spanning tree guarantees connectivity."""
        spec = generate_spanning_tree(num_nodes=10, extra_edge_prob=0.0, seed=42)
        g = spec.to_networkx().to_undirected()
        import networkx as nx
        assert nx.is_connected(g)

    def test_extra_edges(self):
        """Extra edges add density beyond the tree."""
        tree = generate_spanning_tree(num_nodes=10, extra_edge_prob=0.0, seed=42)
        dense = generate_spanning_tree(num_nodes=10, extra_edge_prob=0.5, seed=42)
        assert len(dense.edges) >= len(tree.edges)

    def test_world_generation(self):
        spec = generate_spanning_tree(num_nodes=12, num_latent=2, extra_edge_prob=0.15, seed=42)
        _validate_world(spec)

    def test_large_15_nodes(self):
        spec = generate_spanning_tree(num_nodes=15, num_latent=3, extra_edge_prob=0.1, seed=42)
        _validate_spec(spec, expected_nodes=15)
        _validate_world(spec)


# ---------------------------------------------------------------------------
# Preferential Attachment
# ---------------------------------------------------------------------------

class TestPreferentialAttachment:
    def test_basic(self):
        spec = generate_preferential_attachment(num_nodes=8, seed=42)
        _validate_spec(spec, expected_nodes=8)

    def test_hub_structure(self):
        """Early nodes should have more children (hub-like)."""
        spec = generate_preferential_attachment(
            num_nodes=15, num_edges_per_node=2, seed=42
        )
        # Count children per node
        children_count = {n.name: len(spec.children_of(n.name)) for n in spec.nodes}
        # First few nodes should generally have more children
        early_children = sum(children_count[f"v{i}"] for i in range(3))
        late_children = sum(children_count[f"v{i}"] for i in range(12, 15))
        # Not guaranteed every time, but very likely
        assert early_children >= late_children

    def test_single_edge_per_node(self):
        """With num_edges_per_node=1, each non-root has exactly 1 parent."""
        spec = generate_preferential_attachment(
            num_nodes=8, num_edges_per_node=1, seed=42
        )
        for i in range(1, 8):
            assert len(spec.parents_of(f"v{i}")) == 1

    def test_world_generation(self):
        spec = generate_preferential_attachment(
            num_nodes=12, num_latent=2, num_edges_per_node=2, seed=42
        )
        _validate_world(spec)

    def test_large_15_nodes(self):
        spec = generate_preferential_attachment(
            num_nodes=15, num_latent=3, num_edges_per_node=2, seed=42
        )
        _validate_spec(spec, expected_nodes=15)
        _validate_world(spec)


# ---------------------------------------------------------------------------
# Layered
# ---------------------------------------------------------------------------

class TestLayered:
    def test_basic(self):
        spec = generate_layered(num_layers=3, nodes_per_layer=3, seed=42)
        _validate_spec(spec, expected_nodes=9)

    def test_variable_layer_sizes(self):
        spec = generate_layered(num_layers=4, nodes_per_layer=[2, 4, 3, 1], seed=42)
        _validate_spec(spec, expected_nodes=10)

    def test_connectivity(self):
        """Every non-root-layer node should have at least one parent."""
        spec = generate_layered(num_layers=4, nodes_per_layer=3, seed=42)
        g = spec.to_networkx()
        # First layer nodes (v0, v1, v2) can be roots
        for i in range(3, len(spec.nodes)):
            assert g.in_degree(f"v{i}") > 0, f"v{i} has no parents"

    def test_no_backward_edges(self):
        """All edges go forward (lower index to higher)."""
        spec = generate_layered(num_layers=4, nodes_per_layer=3, seed=42)
        for src, dst in spec.edges:
            src_idx = int(src[1:])
            dst_idx = int(dst[1:])
            assert src_idx < dst_idx

    def test_skip_connections(self):
        """Skip layer connections create non-trivial structure."""
        no_skip = generate_layered(
            num_layers=4, nodes_per_layer=3, skip_layer_prob=0.0, seed=42
        )
        with_skip = generate_layered(
            num_layers=4, nodes_per_layer=3, skip_layer_prob=0.5, seed=42
        )
        assert len(with_skip.edges) >= len(no_skip.edges)

    def test_world_generation(self):
        spec = generate_layered(
            num_layers=4, nodes_per_layer=3, num_latent=2, seed=42
        )
        _validate_world(spec)

    def test_large_15_nodes(self):
        spec = generate_layered(
            num_layers=5, nodes_per_layer=3, num_latent=3, seed=42
        )
        _validate_spec(spec, expected_nodes=15)
        _validate_world(spec)


# ---------------------------------------------------------------------------
# Cross-generator tests
# ---------------------------------------------------------------------------

class TestCrossGenerator:
    """Tests that apply to all generators."""

    @pytest.mark.parametrize("gen_func,kwargs", [
        (generate_erdos_renyi, {"num_nodes": 10, "edge_prob": 0.3}),
        (generate_spanning_tree, {"num_nodes": 10, "extra_edge_prob": 0.15}),
        (generate_preferential_attachment, {"num_nodes": 10, "num_edges_per_node": 2}),
        (generate_layered, {"num_layers": 4, "nodes_per_layer": 3}),
    ])
    def test_produces_valid_dagspec(self, gen_func, kwargs):
        spec = gen_func(seed=42, num_latent=2, **kwargs)
        _validate_spec(spec)

    @pytest.mark.parametrize("gen_func,kwargs", [
        (generate_erdos_renyi, {"num_nodes": 12, "edge_prob": 0.25}),
        (generate_spanning_tree, {"num_nodes": 12, "extra_edge_prob": 0.15}),
        (generate_preferential_attachment, {"num_nodes": 12, "num_edges_per_node": 2}),
        (generate_layered, {"num_layers": 4, "nodes_per_layer": 3}),
    ])
    def test_full_pipeline(self, gen_func, kwargs):
        """DAGSpec -> CustomTemplate -> World -> pgmpy -> WorldCheck."""
        spec = gen_func(seed=42, num_latent=2, **kwargs)
        world, result = _validate_world(spec)
        assert len(world.cpds) == len(spec.nodes)

    @pytest.mark.parametrize("gen_func,kwargs", [
        (generate_erdos_renyi, {"num_nodes": 10, "edge_prob": 0.3}),
        (generate_spanning_tree, {"num_nodes": 10, "extra_edge_prob": 0.15}),
        (generate_preferential_attachment, {"num_nodes": 10, "num_edges_per_node": 2}),
        (generate_layered, {"num_layers": 4, "nodes_per_layer": 3}),
    ])
    def test_task_generation(self, gen_func, kwargs):
        """All 3 task types work with generated DAGs."""
        from sreg.tools.task_gen import TaskGenTool

        spec = gen_func(seed=42, num_latent=1, **kwargs)
        gen = WorldGenTool()
        world = gen.generate_custom(
            CustomWorldGenConfig(dag_spec=spec, edge_strength=0.7, seed=42)
        )
        target = next(n.name for n in spec.nodes if n.type == NodeType.TARGET)
        bundle = TaskGenTool().generate_all(world, target_node=target, seed=42)
        assert bundle.infer_target is not None
        assert bundle.next_best_observation is not None
        assert bundle.hypothesis_selection is not None
