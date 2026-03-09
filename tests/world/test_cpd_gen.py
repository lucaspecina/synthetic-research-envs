"""Tests for generic CPD generation utility."""

import numpy as np
import pytest

from sreg.models.world import CPD, NodeType
from sreg.world.cpd_gen import (
    STATE_LABELS,
    generate_child_cpd,
    generate_cpds_for_dag,
    generate_root_cpd,
)
from sreg.world.templates.latent_preference import LatentPreferenceTemplate


# ---------------------------------------------------------------------------
# generate_root_cpd
# ---------------------------------------------------------------------------

class TestRootCPD:
    def test_shape(self):
        rng = np.random.default_rng(42)
        table = generate_root_cpd(3, rng)
        assert len(table) == 3
        assert all(len(row) == 1 for row in table)

    def test_sums_to_one(self):
        rng = np.random.default_rng(42)
        table = generate_root_cpd(3, rng)
        total = sum(row[0] for row in table)
        assert abs(total - 1.0) < 1e-10

    def test_non_uniform(self):
        """Root CPDs should not be perfectly uniform."""
        rng = np.random.default_rng(42)
        table = generate_root_cpd(3, rng)
        probs = [row[0] for row in table]
        assert not all(abs(p - 1 / 3) < 0.01 for p in probs)

    def test_different_cardinalities(self):
        for n in [2, 3, 4, 5]:
            rng = np.random.default_rng(123)
            table = generate_root_cpd(n, rng)
            assert len(table) == n
            total = sum(row[0] for row in table)
            assert abs(total - 1.0) < 1e-10

    def test_reproducible(self):
        t1 = generate_root_cpd(3, np.random.default_rng(99))
        t2 = generate_root_cpd(3, np.random.default_rng(99))
        assert t1 == t2


# ---------------------------------------------------------------------------
# generate_child_cpd
# ---------------------------------------------------------------------------

class TestChildCPD:
    def test_shape_one_parent(self):
        rng = np.random.default_rng(42)
        table = generate_child_cpd(3, [3], 0.7, rng)
        assert len(table) == 3
        assert all(len(row) == 3 for row in table)

    def test_shape_two_parents(self):
        rng = np.random.default_rng(42)
        table = generate_child_cpd(3, [3, 3], 0.7, rng)
        assert len(table) == 3
        assert all(len(row) == 9 for row in table)

    def test_columns_sum_to_one(self):
        rng = np.random.default_rng(42)
        table = generate_child_cpd(3, [3, 3], 0.7, rng)
        for col in range(9):
            col_sum = sum(table[row][col] for row in range(3))
            assert abs(col_sum - 1.0) < 1e-10

    def test_high_edge_strength_peaked(self):
        """With edge_strength=1.0, distributions should be very peaked."""
        rng = np.random.default_rng(42)
        table = generate_child_cpd(3, [3], 1.0, rng)
        for col in range(3):
            col_probs = [table[row][col] for row in range(3)]
            assert max(col_probs) > 0.8

    def test_low_edge_strength_flatter(self):
        """With edge_strength=0.0, distributions should be more uniform."""
        rng = np.random.default_rng(42)
        table = generate_child_cpd(3, [3], 0.0, rng)
        for col in range(3):
            col_probs = [table[row][col] for row in range(3)]
            assert max(col_probs) < 0.8

    def test_heterogeneous_parents(self):
        """Parents with different cardinalities."""
        rng = np.random.default_rng(42)
        # Parent with 2 states, parent with 3 states -> 6 combos
        table = generate_child_cpd(3, [2, 3], 0.7, rng)
        assert len(table) == 3
        assert all(len(row) == 6 for row in table)
        for col in range(6):
            col_sum = sum(table[row][col] for row in range(3))
            assert abs(col_sum - 1.0) < 1e-10

    def test_child_fewer_states_than_parent(self):
        """Child has 2 states, parent has 3 states."""
        rng = np.random.default_rng(42)
        table = generate_child_cpd(2, [3], 0.7, rng)
        assert len(table) == 2
        assert all(len(row) == 3 for row in table)

    def test_four_parents(self):
        """4 parents with 2 states each = 16 combos."""
        rng = np.random.default_rng(42)
        table = generate_child_cpd(3, [2, 2, 2, 2], 0.7, rng)
        assert len(table) == 3
        assert all(len(row) == 16 for row in table)

    def test_reproducible(self):
        t1 = generate_child_cpd(3, [3], 0.7, np.random.default_rng(99))
        t2 = generate_child_cpd(3, [3], 0.7, np.random.default_rng(99))
        assert t1 == t2


# ---------------------------------------------------------------------------
# generate_cpds_for_dag
# ---------------------------------------------------------------------------

class TestGenerateCPDsForDAG:
    def test_simple_chain(self):
        nodes = [("A", ["lo", "hi"]), ("B", ["lo", "hi"])]
        parent_map = {"A": [], "B": ["A"]}
        node_states = {"A": ["lo", "hi"], "B": ["lo", "hi"]}
        rng = np.random.default_rng(42)
        cpds = generate_cpds_for_dag(nodes, parent_map, node_states, 0.7, rng)
        assert len(cpds) == 2
        assert cpds[0].node == "A"
        assert cpds[0].parents == []
        assert cpds[1].node == "B"
        assert cpds[1].parents == ["A"]

    def test_heterogeneous_states(self):
        """Nodes with different numbers of states."""
        nodes = [
            ("bin", ["yes", "no"]),
            ("tri", ["a", "b", "c"]),
            ("target", ["lo", "med", "hi"]),
        ]
        parent_map = {"bin": [], "tri": [], "target": ["bin", "tri"]}
        node_states = {"bin": ["yes", "no"], "tri": ["a", "b", "c"], "target": ["lo", "med", "hi"]}
        rng = np.random.default_rng(42)
        cpds = generate_cpds_for_dag(nodes, parent_map, node_states, 0.7, rng)

        assert len(cpds) == 3
        # Target has 2*3=6 parent combos, 3 child states
        target_cpd = cpds[2]
        assert len(target_cpd.table) == 3
        assert all(len(row) == 6 for row in target_cpd.table)

    def test_all_cpds_valid(self):
        """All generated CPDs pass Pydantic validation."""
        nodes = [
            ("root", ["a", "b", "c"]),
            ("mid", ["x", "y"]),
            ("leaf", ["lo", "hi", "mid"]),
        ]
        parent_map = {"root": [], "mid": ["root"], "leaf": ["root", "mid"]}
        node_states = {"root": ["a", "b", "c"], "mid": ["x", "y"], "leaf": ["lo", "hi", "mid"]}
        rng = np.random.default_rng(42)
        cpds = generate_cpds_for_dag(nodes, parent_map, node_states, 0.5, rng)
        # If we got here, all CPDs passed Pydantic validation
        assert len(cpds) == 3
        for cpd in cpds:
            assert isinstance(cpd, CPD)


# ---------------------------------------------------------------------------
# Equivalence with existing templates
# ---------------------------------------------------------------------------

class TestEquivalenceWithTemplates:
    """Verify that cpd_gen produces identical results to the existing templates.

    This is the critical test: given the same seed, structure, and parameters,
    the extracted logic must produce bit-for-bit identical CPDs.
    """

    def test_matches_latent_preference(self):
        """Generate a latent_preference world, then replicate its CPDs with cpd_gen."""
        seed = 42
        num_nodes = 6
        num_latent = 1
        num_states = 3
        edge_strength = 0.7

        # Generate via template
        template = LatentPreferenceTemplate()
        world = template.generate(
            seed=seed,
            num_nodes=num_nodes,
            num_latent=num_latent,
            num_states=num_states,
            edge_strength=edge_strength,
        )

        # Replicate: use cpd_gen with same rng state
        # The template uses rng for: _create_edges (possible), then _create_cpds
        # We need to advance rng in the same way
        rng = np.random.default_rng(seed)
        states = STATE_LABELS[num_states]

        # Replicate node creation (deterministic, no rng)
        nodes_list = world.nodes

        # Replicate edge creation (uses rng for nothing in this template with 1 latent)
        edges_list = world.edges

        # Build parent_map from edges
        parent_map: dict[str, list[str]] = {n.name: [] for n in nodes_list}
        for edge in edges_list:
            parent_map[edge.to_node].append(edge.from_node)

        # Build inputs for cpd_gen
        nodes_tuples = [(n.name, list(n.states)) for n in nodes_list]
        node_states = {n.name: list(n.states) for n in nodes_list}

        cpds = generate_cpds_for_dag(nodes_tuples, parent_map, node_states, edge_strength, rng)

        # Compare CPD tables
        assert len(cpds) == len(world.cpds)
        for cpd_gen_cpd, world_cpd in zip(cpds, world.cpds):
            assert cpd_gen_cpd.node == world_cpd.node
            assert cpd_gen_cpd.parents == world_cpd.parents
            assert len(cpd_gen_cpd.table) == len(world_cpd.table)
            for row_gen, row_world in zip(cpd_gen_cpd.table, world_cpd.table):
                for val_gen, val_world in zip(row_gen, row_world):
                    assert abs(val_gen - val_world) < 1e-15, (
                        f"CPD mismatch for {cpd_gen_cpd.node}: "
                        f"{val_gen} != {val_world}"
                    )
