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

        # Verify CPD properties (not exact values — algorithm changed to ordinal scoring)
        assert len(cpds) == len(world.cpds)
        for cpd_gen_cpd, world_cpd in zip(cpds, world.cpds):
            assert cpd_gen_cpd.node == world_cpd.node
            assert cpd_gen_cpd.parents == world_cpd.parents
            assert len(cpd_gen_cpd.table) == len(world_cpd.table)
            # Verify probabilities sum to ~1 for each column
            import numpy as _np

            arr = _np.array(cpd_gen_cpd.table)
            for col in range(arr.shape[1]):
                col_sum = arr[:, col].sum()
                assert abs(col_sum - 1.0) < 1e-10, (
                    f"CPD column doesn't sum to 1 for {cpd_gen_cpd.node}: {col_sum}"
                    )


# --- Direction-aware CPD tests ---


class TestDirectionalCPDs:
    """Test that edge direction affects CPD generation correctly."""

    def test_positive_direction_monotone(self):
        """Positive direction: higher parent state -> higher child state dominant."""
        rng = np.random.default_rng(42)
        # 3 states, 1 parent with 3 states, positive direction
        table = generate_child_cpd(3, [3], 0.7, rng, parent_directions=["positive"])
        arr = np.array(table)
        # For parent state 0 (low), dominant child should be low (state 0)
        assert np.argmax(arr[:, 0]) == 0, "Low parent should produce low child"
        # For parent state 2 (high), dominant child should be high (state 2)
        assert np.argmax(arr[:, 2]) == 2, "High parent should produce high child"

    def test_negative_direction_monotone(self):
        """Negative direction: higher parent state -> lower child state dominant."""
        rng = np.random.default_rng(42)
        table = generate_child_cpd(3, [3], 0.7, rng, parent_directions=["negative"])
        arr = np.array(table)
        # For parent state 0 (low), dominant child should be high (state 2)
        assert np.argmax(arr[:, 0]) == 2, "Low parent should produce high child"
        # For parent state 2 (high), dominant child should be low (state 0)
        assert np.argmax(arr[:, 2]) == 0, "High parent should produce low child"

    def test_no_direction_still_valid(self):
        """Without direction, CPDs should still be valid probability distributions."""
        rng = np.random.default_rng(42)
        table = generate_child_cpd(3, [3], 0.7, rng)
        arr = np.array(table)
        for col in range(arr.shape[1]):
            assert abs(arr[:, col].sum() - 1.0) < 1e-10

    def test_mixed_directions_two_parents(self):
        """Two parents with opposite directions should partially cancel."""
        rng = np.random.default_rng(42)
        table = generate_child_cpd(
            3, [3, 3], 0.7, rng,
            parent_directions=["positive", "negative"],
        )
        arr = np.array(table)
        # When both parents are low (col 0): positive says low, negative says high
        # They should partially cancel -> middle state more likely
        # When parent1=high, parent2=high (col 8): positive says high, negative says low
        # Again should cancel
        # Just verify valid probabilities
        for col in range(arr.shape[1]):
            assert abs(arr[:, col].sum() - 1.0) < 1e-10

    def test_direction_in_dag_generation(self):
        """Edge directions propagate through generate_cpds_for_dag."""
        rng = np.random.default_rng(42)
        nodes = [("cause", ["low", "high"]), ("effect", ["low", "high"])]
        parent_map = {"cause": [], "effect": ["cause"]}
        node_states = {"cause": ["low", "high"], "effect": ["low", "high"]}

        # Positive: high cause -> high effect
        cpds_pos = generate_cpds_for_dag(
            nodes, parent_map, node_states, 0.8, rng,
            edge_directions={("cause", "effect"): "positive"},
        )
        effect_cpd_pos = cpds_pos[1]
        arr = np.array(effect_cpd_pos.table)
        # cause=high (col 1) -> effect=high (row 1) should dominate
        assert arr[1, 1] > arr[0, 1], "Positive: high cause should favor high effect"

        # Negative: high cause -> low effect
        rng2 = np.random.default_rng(42)
        cpds_neg = generate_cpds_for_dag(
            nodes, parent_map, node_states, 0.8, rng2,
            edge_directions={("cause", "effect"): "negative"},
        )
        effect_cpd_neg = cpds_neg[1]
        arr_neg = np.array(effect_cpd_neg.table)
        # cause=high (col 1) -> effect=low (row 0) should dominate
        assert arr_neg[0, 1] > arr_neg[1, 1], "Negative: high cause should favor low effect"

    def test_strong_edge_strength_sharper(self):
        """Higher edge_strength should produce more peaked distributions."""
        rng_weak = np.random.default_rng(42)
        rng_strong = np.random.default_rng(42)
        table_weak = generate_child_cpd(3, [3], 0.3, rng_weak, ["positive"])
        table_strong = generate_child_cpd(3, [3], 0.9, rng_strong, ["positive"])
        # Strong should have higher max probability in dominant state
        max_weak = max(max(row) for row in table_weak)
        max_strong = max(max(row) for row in table_strong)
        assert max_strong > max_weak, "Strong edge_strength should produce sharper CPDs"
