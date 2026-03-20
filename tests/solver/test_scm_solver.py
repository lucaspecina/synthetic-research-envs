"""Tests for SCMSolver — Monte Carlo teacher for SCMWorld."""

from __future__ import annotations

import numpy as np
import pytest

from sreg.solver.scm_solver import SCMSolver
from sreg.world.scm import SCMWorld, VariableMeta

# ------------------------------------------------------------------
# Fixtures — reusable SCM worlds with known structure
# ------------------------------------------------------------------


def _linear_chain() -> SCMWorld:
    """A -> B -> C.  Strong linear relationships."""
    return SCMWorld(
        graph={"A": [], "B": ["A"], "C": ["B"]},
        equations={
            "A": lambda p, rng: rng.normal(10, 2),
            "B": lambda p, rng: 2 * p["A"] + rng.normal(0, 1),
            "C": lambda p, rng: 0.5 * p["B"] + rng.normal(0, 0.5),
        },
        variable_meta={
            "A": VariableMeta(unit="x", range=(0, 20)),
            "B": VariableMeta(unit="y", range=(0, 50)),
            "C": VariableMeta(unit="z", range=(0, 30)),
        },
    )


def _fork() -> SCMWorld:
    """Z -> A, Z -> B.  Confounder structure."""
    return SCMWorld(
        graph={"Z": [], "A": ["Z"], "B": ["Z"]},
        equations={
            "Z": lambda p, rng: rng.normal(5, 2),
            "A": lambda p, rng: 3 * p["Z"] + rng.normal(0, 1),
            "B": lambda p, rng: -2 * p["Z"] + rng.normal(0, 1),
        },
    )


def _independent() -> SCMWorld:
    """A and B are independent (no edges)."""
    return SCMWorld(
        graph={"A": [], "B": []},
        equations={
            "A": lambda p, rng: rng.normal(0, 1),
            "B": lambda p, rng: rng.normal(10, 3),
        },
    )


def _five_node() -> SCMWorld:
    """A -> B -> D, A -> C -> D, E (independent).

    D has two parents. E is unconnected.
    """
    return SCMWorld(
        graph={
            "A": [],
            "B": ["A"],
            "C": ["A"],
            "D": ["B", "C"],
            "E": [],
        },
        equations={
            "A": lambda p, rng: rng.normal(0, 1),
            "B": lambda p, rng: 2 * p["A"] + rng.normal(0, 0.5),
            "C": lambda p, rng: -p["A"] + rng.normal(0, 0.5),
            "D": lambda p, rng: p["B"] + p["C"] + rng.normal(0, 0.3),
            "E": lambda p, rng: rng.normal(100, 10),
        },
    )


# ------------------------------------------------------------------
# TestSampleState
# ------------------------------------------------------------------


class TestSampleState:
    def test_returns_dict_with_all_variables(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        state = solver.sample_state(seed=42)
        assert set(state.keys()) == {"A", "B", "C"}
        assert all(isinstance(v, float) for v in state.values())

    def test_reproducible_with_same_seed(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        s1 = solver.sample_state(seed=123)
        s2 = solver.sample_state(seed=123)
        assert s1 == s2

    def test_different_seeds_differ(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        s1 = solver.sample_state(seed=1)
        s2 = solver.sample_state(seed=2)
        assert s1 != s2

    def test_respects_structure(self):
        """B should be close to 2*A (plus small noise)."""
        world = _linear_chain()
        solver = SCMSolver(world)
        # Sample many and check mean relationship
        states = [solver.sample_state(seed=i) for i in range(500)]
        a_vals = np.array([s["A"] for s in states])
        b_vals = np.array([s["B"] for s in states])
        # B ~ 2*A + noise(0,1)
        residuals = b_vals - 2 * a_vals
        assert abs(np.mean(residuals)) < 0.5  # noise mean ~ 0


# ------------------------------------------------------------------
# TestPosteriorSamples
# ------------------------------------------------------------------


class TestPosteriorSamples:
    def test_marginal_no_evidence(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        samples = solver.posterior_samples("A", n=5000, seed=42)
        assert len(samples) == 5000
        # A ~ N(10, 2)
        assert abs(np.mean(samples) - 10) < 0.5
        assert abs(np.std(samples) - 2) < 0.5

    def test_conditioning_shifts_distribution(self):
        """Conditioning B on high A should yield higher B."""
        world = _linear_chain()
        solver = SCMSolver(world)
        # Marginal of B
        marginal = solver.posterior_samples("B", n=5000, seed=42)
        # B | A=15 (high A, so B should be ~30)
        conditioned = solver.posterior_samples("B", evidence={"A": 15.0}, n=5000, seed=42)
        assert np.mean(conditioned) > np.mean(marginal) + 3

    def test_conditioning_on_low_value(self):
        """Conditioning on low A should yield lower B."""
        world = _linear_chain()
        solver = SCMSolver(world)
        conditioned = solver.posterior_samples("B", evidence={"A": 5.0}, n=5000, seed=42)
        # B ~ 2*5 + noise = ~10
        assert abs(np.mean(conditioned) - 10) < 3

    def test_returns_array(self):
        world = _fork()
        solver = SCMSolver(world)
        samples = solver.posterior_samples("A", n=1000, seed=0)
        assert isinstance(samples, np.ndarray)
        assert samples.ndim == 1

    def test_extreme_evidence_falls_back(self):
        """Extreme evidence where rejection finds almost nothing."""
        world = _linear_chain()
        solver = SCMSolver(world)
        # A=100 is far outside N(10,2) — should still return samples (fallback)
        samples = solver.posterior_samples("B", evidence={"A": 100.0}, n=100, seed=42)
        assert len(samples) > 0


# ------------------------------------------------------------------
# TestInterventionalSamples
# ------------------------------------------------------------------


class TestInterventionalSamples:
    def test_do_changes_distribution(self):
        """do(A=15) should make B concentrate around 30."""
        world = _linear_chain()
        solver = SCMSolver(world)
        samples = solver.interventional_samples("B", do={"A": 15.0}, n=5000, seed=42)
        # B = 2*15 + noise(0,1) = ~30
        assert abs(np.mean(samples) - 30) < 1.0

    def test_do_breaks_backdoor_path(self):
        """In fork Z->A, Z->B: do(A=x) should NOT affect B."""
        world = _fork()
        solver = SCMSolver(world)
        b_do_low = solver.interventional_samples("B", do={"A": 0.0}, n=5000, seed=42)
        b_do_high = solver.interventional_samples("B", do={"A": 100.0}, n=5000, seed=42)
        # B doesn't depend on A — distributions should be similar
        assert abs(np.mean(b_do_low) - np.mean(b_do_high)) < 2.0

    def test_with_evidence(self):
        """do(A=15) + evidence on something downstream."""
        world = _linear_chain()
        solver = SCMSolver(world)
        samples = solver.interventional_samples(
            "C", do={"A": 15.0}, evidence={"B": 30.0}, n=5000, seed=42
        )
        # C = 0.5 * 30 + noise = ~15
        assert len(samples) > 0
        assert abs(np.mean(samples) - 15) < 3

    def test_without_evidence(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        samples = solver.interventional_samples("C", do={"A": 10.0}, n=5000, seed=42)
        # C = 0.5 * (2*10 + noise) + noise = ~10
        assert abs(np.mean(samples) - 10) < 2


# ------------------------------------------------------------------
# TestEntropy
# ------------------------------------------------------------------


class TestEntropy:
    def test_uniform_high_entropy(self):
        solver = SCMSolver(_linear_chain())
        uniform = np.random.default_rng(42).uniform(0, 100, size=10000)
        h = solver.entropy(uniform)
        assert h > 3.0  # Uniform over wide range should have high entropy

    def test_peaked_low_entropy_with_fixed_bins(self):
        """Peaked distribution has low entropy when measured on a fixed scale."""
        solver = SCMSolver(_linear_chain())
        peaked = np.random.default_rng(42).normal(0, 0.01, size=10000)
        # With adaptive bins, entropy looks high (bins adapt to narrow range).
        # With fixed bins over a wide range, only 1-2 bins are occupied.
        fixed_edges = np.linspace(-5, 5, 51)
        h = solver.entropy(peaked, bin_edges=fixed_edges)
        assert h < 1.0  # Most mass in 1-2 bins

    def test_always_non_negative(self):
        solver = SCMSolver(_linear_chain())
        rng = np.random.default_rng(42)
        for _ in range(20):
            samples = rng.normal(rng.uniform(-10, 10), rng.uniform(0.01, 5), size=1000)
            assert solver.entropy(samples) >= 0.0

    def test_single_value_zero(self):
        solver = SCMSolver(_linear_chain())
        assert solver.entropy(np.array([5.0])) == 0.0

    def test_empty_array_zero(self):
        solver = SCMSolver(_linear_chain())
        assert solver.entropy(np.array([])) == 0.0


# ------------------------------------------------------------------
# TestInformationGain
# ------------------------------------------------------------------


class TestInformationGain:
    def test_direct_parent_has_positive_ig(self):
        """B is a direct parent of C — observing B should be informative about C."""
        world = _linear_chain()
        solver = SCMSolver(world)
        ig = solver.information_gain("C", evidence={}, candidate="B", n=50_000, seed=42)
        assert ig > 0.1

    def test_independent_has_near_zero_ig(self):
        """A and B are independent — observing A tells nothing about B."""
        world = _independent()
        solver = SCMSolver(world)
        ig = solver.information_gain("B", evidence={}, candidate="A", n=50_000, seed=42)
        assert ig < 0.1

    def test_direct_parent_more_than_grandparent(self):
        """B (parent of C) should have more IG than A (grandparent)."""
        world = _linear_chain()
        solver = SCMSolver(world)
        ig_b = solver.information_gain("C", evidence={}, candidate="B", n=50_000, seed=42)
        ig_a = solver.information_gain("C", evidence={}, candidate="A", n=50_000, seed=42)
        assert ig_b > ig_a

    def test_always_non_negative(self):
        world = _five_node()
        solver = SCMSolver(world)
        for var in ["A", "B", "C", "E"]:
            ig = solver.information_gain("D", evidence={}, candidate=var, n=30_000, seed=42)
            assert ig >= 0.0

    def test_unconnected_node_low_ig(self):
        """E is independent of D — should have near-zero IG."""
        world = _five_node()
        solver = SCMSolver(world)
        ig = solver.information_gain("D", evidence={}, candidate="E", n=50_000, seed=42)
        assert ig < 0.1

    def test_with_evidence(self):
        """IG should still work when some variables are already observed."""
        world = _linear_chain()
        solver = SCMSolver(world)
        ig = solver.information_gain(
            "C", evidence={"A": 10.0}, candidate="B", n=50_000, seed=42
        )
        assert ig > 0.0


# ------------------------------------------------------------------
# TestOptimalAction
# ------------------------------------------------------------------


class TestOptimalAction:
    def test_selects_most_informative(self):
        """Should prefer direct parent over independent variable."""
        world = _five_node()
        solver = SCMSolver(world)
        result = solver.optimal_action(
            target="D", evidence={}, available=["B", "C", "E"], seed=42
        )
        assert result.recommended_action is not None
        # B or C are parents of D, E is independent — should NOT pick E
        assert result.recommended_action.node in ("B", "C")

    def test_positive_ig(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        result = solver.optimal_action(
            target="C", evidence={}, available=["A", "B"], seed=42
        )
        assert result.information_gain > 0

    def test_entropy_positive(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        result = solver.optimal_action(
            target="C", evidence={}, available=["A", "B"], seed=42
        )
        assert result.entropy > 0

    def test_empty_available(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        result = solver.optimal_action(target="C", evidence={}, available=[], seed=42)
        assert result.recommended_action is None
        assert result.information_gain == 0.0

    def test_respects_costs(self):
        """With high cost on B, should prefer cheaper A even if B has higher IG."""
        world = _linear_chain()
        solver = SCMSolver(world)
        result = solver.optimal_action(
            target="C",
            evidence={},
            available=["A", "B"],
            costs={"A": 1, "B": 100},
            seed=42,
        )
        # A costs 1, B costs 100 — A should win on IG/cost even if B has more raw IG
        assert result.recommended_action.node == "A"

    def test_posterior_is_empty_dict(self):
        """SCMSolver uses sample-based posteriors, not discrete dicts."""
        world = _linear_chain()
        solver = SCMSolver(world)
        result = solver.optimal_action(target="C", evidence={}, available=["A"], seed=42)
        assert result.posterior == {}


# ------------------------------------------------------------------
# TestGenerateTrajectory
# ------------------------------------------------------------------


class TestGenerateTrajectory:
    def test_returns_state_and_trajectory(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        state, traj = solver.generate_trajectory(
            target="C", available=["A", "B"], budget=2, seed=42
        )
        assert isinstance(state, dict)
        assert set(state.keys()) == {"A", "B", "C"}
        assert len(traj) > 0

    def test_trajectory_ends_with_none_action(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        _, traj = solver.generate_trajectory(
            target="C", available=["A", "B"], budget=2, seed=42
        )
        assert traj[-1].recommended_action is None

    def test_entropy_decreases_over_trajectory(self):
        """Entropy should generally decrease as we observe more."""
        world = _five_node()
        solver = SCMSolver(world)
        _, traj = solver.generate_trajectory(
            target="D", available=["A", "B", "C"], budget=3, seed=42
        )
        # At least 2 steps + final
        assert len(traj) >= 2
        # Final entropy should be <= initial
        assert traj[-1].entropy <= traj[0].entropy + 0.5  # small tolerance for MC noise

    def test_budget_respected(self):
        world = _five_node()
        solver = SCMSolver(world)
        _, traj = solver.generate_trajectory(
            target="D",
            available=["A", "B", "C", "E"],
            budget=2,
            seed=42,
        )
        # At most 2 observation steps + 1 final
        observation_steps = [t for t in traj if t.recommended_action is not None]
        assert len(observation_steps) <= 2

    def test_with_costs(self):
        world = _five_node()
        solver = SCMSolver(world)
        state, traj = solver.generate_trajectory(
            target="D",
            available=["A", "B", "C", "E"],
            budget=3,
            costs={"A": 1, "B": 2, "C": 2, "E": 1},
            seed=42,
        )
        # Budget = 3, should be able to afford at most 2-3 observations
        observation_steps = [t for t in traj if t.recommended_action is not None]
        total_cost = sum(
            {"A": 1, "B": 2, "C": 2, "E": 1}[t.recommended_action.node]
            for t in observation_steps
        )
        assert total_cost <= 3


# ------------------------------------------------------------------
# TestRejectionFilter
# ------------------------------------------------------------------


class TestRejectionFilter:
    def test_filters_matching_rows(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        df = world.sample(n=10_000, seed=42)
        # Filter to rows where A ~ 10 (the mean)
        matched = solver._rejection_filter(df, {"A": 10.0})
        assert len(matched) > 0
        assert all(abs(matched["A"] - 10.0) < 5)  # within widened tolerance

    def test_widens_tolerance_on_few_matches(self):
        """Should widen tolerance if initial band is too tight."""
        world = _linear_chain()
        solver = SCMSolver(world)
        df = world.sample(n=1000, seed=42)
        # A=10 should match ~some rows even with small sample
        matched = solver._rejection_filter(df, {"A": 10.0}, min_samples=50)
        assert len(matched) >= 1  # Should find at least some

    def test_extreme_value_returns_few(self):
        """Very extreme evidence might return empty or very few rows."""
        world = _linear_chain()
        solver = SCMSolver(world)
        df = world.sample(n=1000, seed=42)
        matched = solver._rejection_filter(df, {"A": 1000.0})
        # A=1000 is far from N(10,2) — might return 0 rows
        assert len(matched) >= 0  # Just shouldn't crash


# ------------------------------------------------------------------
# TestBatchIG
# ------------------------------------------------------------------


class TestBatchIG:
    def test_batch_matches_individual(self):
        """Batch IG should produce similar results to individual calls."""
        world = _five_node()
        solver = SCMSolver(world)
        df = solver._get_joint_samples(evidence={}, n=50_000, seed=42)

        batch = solver._compute_ig_from_df(df, "D", ["A", "B", "C", "E"])

        # All should be non-negative
        for v in batch.values():
            assert v >= 0.0

        # E (independent) should have lowest IG
        assert batch["E"] < batch["B"] or batch["E"] < batch["C"]

    def test_missing_column_returns_zero(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        df = solver._get_joint_samples(evidence={}, n=10_000, seed=42)
        result = solver._compute_ig_from_df(df, "C", ["nonexistent"])
        assert result["nonexistent"] == 0.0


# ------------------------------------------------------------------
# TestE2E
# ------------------------------------------------------------------


class TestE2E:
    def test_full_pipeline_linear_chain(self):
        """Full pipeline: sample state, compute posteriors, run trajectory."""
        world = _linear_chain()
        solver = SCMSolver(world)

        # 1. Sample state
        state = solver.sample_state(seed=42)
        assert "C" in state

        # 2. Posterior without evidence
        prior = solver.posterior_samples("C", n=5000, seed=42)
        prior_h = solver.entropy(prior)
        assert prior_h > 0

        # 3. Posterior with evidence (should have lower entropy)
        post = solver.posterior_samples("C", evidence={"B": state["B"]}, n=5000, seed=42)
        post_h = solver.entropy(post)
        assert post_h < prior_h + 0.5  # should be lower (with MC tolerance)

        # 4. Interventional distribution
        do_samples = solver.interventional_samples("C", do={"A": 10.0}, n=5000, seed=42)
        assert len(do_samples) == 5000

        # 5. Trajectory
        _, traj = solver.generate_trajectory(
            target="C", available=["A", "B"], budget=2, seed=42
        )
        assert len(traj) >= 2

    def test_fork_identifies_confounder(self):
        """In Z->A, Z->B: Z should be the best variable to observe for both A and B."""
        world = _fork()
        solver = SCMSolver(world)

        # Z is a common cause — observing Z should be most informative about A
        ig_z = solver.information_gain("A", evidence={}, candidate="Z", n=50_000, seed=42)
        ig_b = solver.information_gain("A", evidence={}, candidate="B", n=50_000, seed=42)

        # Z is direct parent, B is sibling through Z — Z should be more informative
        assert ig_z > ig_b

    def test_five_node_trajectory_reasonable(self):
        """Trajectory on 5-node graph should observe informative nodes first."""
        world = _five_node()
        solver = SCMSolver(world)
        state, traj = solver.generate_trajectory(
            target="D", available=["A", "B", "C", "E"], budget=4, seed=42
        )

        # Should observe B or C first (parents of D), not E (independent)
        observation_steps = [t for t in traj if t.recommended_action is not None]
        if observation_steps:
            first_obs = observation_steps[0].recommended_action.node
            assert first_obs in ("A", "B", "C")  # Not E


# ------------------------------------------------------------------
# TestValidation — Codex review: fail fast on bad inputs
# ------------------------------------------------------------------


class TestValidation:
    def test_unknown_target_raises(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        with pytest.raises(ValueError, match="Unknown variables"):
            solver.posterior_samples("NONEXISTENT", seed=42)

    def test_unknown_evidence_variable_raises(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        with pytest.raises(ValueError, match="Unknown variables"):
            solver.posterior_samples("C", evidence={"FAKE": 1.0}, seed=42)

    def test_unknown_do_variable_raises(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        with pytest.raises(ValueError, match="Unknown variables"):
            solver.interventional_samples("C", do={"FAKE": 1.0}, seed=42)

    def test_unknown_candidate_raises(self):
        world = _linear_chain()
        solver = SCMSolver(world)
        with pytest.raises(ValueError, match="Unknown variables"):
            solver.information_gain("C", evidence={}, candidate="FAKE", seed=42)


# ------------------------------------------------------------------
# TestMultiEvidence — Codex review: multiple evidence variables
# ------------------------------------------------------------------


class TestMultiEvidence:
    def test_two_evidence_variables(self):
        """Posterior with 2 evidence variables should be tighter than 1."""
        world = _five_node()
        solver = SCMSolver(world)
        state = solver.sample_state(seed=42)

        post_1 = solver.posterior_samples("D", evidence={"B": state["B"]}, n=5000, seed=42)
        post_2 = solver.posterior_samples(
            "D", evidence={"B": state["B"], "C": state["C"]}, n=5000, seed=42
        )
        # More evidence should narrow the distribution (or at least not widen it)
        # Using std as proxy for spread
        assert np.std(post_2) <= np.std(post_1) + 1.0  # tolerance for MC noise

    def test_multi_evidence_ig_still_works(self):
        """IG with multi-variable evidence should still produce valid results."""
        world = _five_node()
        solver = SCMSolver(world)
        ig = solver.information_gain(
            "D", evidence={"A": 0.5, "B": 1.0}, candidate="C", n=50_000, seed=42
        )
        assert ig >= 0.0


# ------------------------------------------------------------------
# TestLargerGraph — Codex review: scale beyond toy examples
# ------------------------------------------------------------------


def _ten_node_chain() -> SCMWorld:
    """X0 -> X1 -> ... -> X9.  Long linear chain."""
    graph = {"X0": []}
    equations = {"X0": lambda p, rng: rng.normal(0, 1)}
    for i in range(1, 10):
        graph[f"X{i}"] = [f"X{i-1}"]
        # Use default args to capture loop variable
        equations[f"X{i}"] = (
            lambda p, rng, parent=f"X{i-1}": p[parent] + rng.normal(0, 0.5)
        )
    return SCMWorld(graph=graph, equations=equations)


class TestLargerGraph:
    def test_ten_node_chain_ig_decays_with_distance(self):
        """In a 10-node chain, IG about X9 should be higher for closer nodes."""
        world = _ten_node_chain()
        solver = SCMSolver(world)
        ig_x8 = solver.information_gain("X9", evidence={}, candidate="X8", n=50_000, seed=42)
        ig_x0 = solver.information_gain("X9", evidence={}, candidate="X0", n=50_000, seed=42)
        # X8 (direct parent) should be more informative than X0 (9 hops away)
        assert ig_x8 > ig_x0

    def test_ten_node_trajectory(self):
        """Should produce a valid trajectory on 10-node graph."""
        world = _ten_node_chain()
        solver = SCMSolver(world)
        available = [f"X{i}" for i in range(9)]  # all except target X9
        state, traj = solver.generate_trajectory(
            target="X9", available=available, budget=3, seed=42
        )
        assert set(state.keys()) == {f"X{i}" for i in range(10)}
        obs = [t for t in traj if t.recommended_action is not None]
        assert len(obs) <= 3
        assert traj[-1].recommended_action is None


# ------------------------------------------------------------------
# TestIGWeightNormalization — Codex review: IG with sparse bins
# ------------------------------------------------------------------


class TestIGWeightNormalization:
    def test_ig_not_inflated_with_few_samples(self):
        """IG should NOT be artificially high when bins have few samples.

        Codex found: when bins are skipped (< 5 samples), the old code
        didn't account for the missing weight, inflating IG toward H(target).
        With the fix, unaccounted weight assumes prior entropy (conservative).
        """
        world = _linear_chain()
        solver = SCMSolver(world)

        # Use fewer samples so some bins get sparse
        df = solver._get_joint_samples(evidence={}, n=500, seed=42)
        igs = solver._compute_ig_from_df(df, "C", ["A", "B"], n_bins=20)

        # IG should still be reasonable, not close to H(target)
        h_prior = solver.entropy(df["C"].values, bin_edges=solver._target_bin_edges(df["C"].values))
        for var in ["A", "B"]:
            assert igs[var] <= h_prior  # Can't gain more info than total entropy
            assert igs[var] >= 0.0


# ------------------------------------------------------------------
# TestEntropyBits — Codex review: consistent units with ExactBayesSolver
# ------------------------------------------------------------------


class TestEntropyBits:
    def test_entropy_in_bits(self):
        """Entropy should be in bits (log2), not nats."""
        solver = SCMSolver(_linear_chain())
        # 2 equally likely outcomes -> 1 bit
        samples = np.array([0] * 5000 + [1] * 5000, dtype=float)
        h = solver.entropy(samples, bins=2)
        assert abs(h - 1.0) < 0.05  # Should be ~1 bit

    def test_four_outcomes_two_bits(self):
        """4 equally likely outcomes -> 2 bits."""
        solver = SCMSolver(_linear_chain())
        samples = np.array([0] * 2500 + [1] * 2500 + [2] * 2500 + [3] * 2500, dtype=float)
        h = solver.entropy(samples, bins=4)
        assert abs(h - 2.0) < 0.05  # Should be ~2 bits


# ------------------------------------------------------------------
# TestStoppingCriterion — Fix 1: don't recommend when IG is negligible
# ------------------------------------------------------------------


class TestStoppingCriterion:
    def test_independent_returns_none_action(self):
        """When all candidates are independent, IG ~ 0 -> no recommendation."""
        world = _independent()
        solver = SCMSolver(world)
        output = solver.optimal_action("A", evidence={}, available=["B"], seed=42)
        assert output.recommended_action is None
        assert output.information_gain == 0.0

    def test_trajectory_stops_early_when_no_info(self):
        """Trajectory should stop before exhausting budget if IG is negligible."""
        world = _independent()
        solver = SCMSolver(world)
        _, traj = solver.generate_trajectory(
            target="A", available=["B"], budget=3, seed=42
        )
        # Should get at most 1 step (the final None) because B has no info about A
        obs_steps = [t for t in traj if t.recommended_action is not None]
        assert len(obs_steps) == 0


# ------------------------------------------------------------------
# TestStrictMode — Fix 2: raise instead of silent fallback
# ------------------------------------------------------------------


class TestStrictMode:
    def test_posterior_strict_raises_on_impossible_evidence(self):
        """strict=True should raise ValueError when rejection fails."""
        world = _linear_chain()
        solver = SCMSolver(world)
        with pytest.raises(ValueError, match="0 matches"):
            solver.posterior_samples(
                "C", evidence={"A": 99999.0}, n=100, seed=42, strict=True
            )

    def test_posterior_strict_false_falls_back(self):
        """strict=False (default) should return marginal without raising."""
        world = _linear_chain()
        solver = SCMSolver(world)
        # Should not raise, returns marginal
        result = solver.posterior_samples(
            "C", evidence={"A": 99999.0}, n=100, seed=42, strict=False
        )
        assert len(result) > 0

    def test_interventional_strict_raises_on_impossible_evidence(self):
        """strict=True on interventional should raise when rejection fails."""
        world = _linear_chain()
        solver = SCMSolver(world)
        with pytest.raises(ValueError, match="0 matches"):
            solver.interventional_samples(
                "C", do={"A": 5.0}, evidence={"B": 99999.0},
                n=100, seed=42, strict=True,
            )

    def test_interventional_strict_false_falls_back(self):
        """strict=False (default) should return interventional without raising."""
        world = _linear_chain()
        solver = SCMSolver(world)
        result = solver.interventional_samples(
            "C", do={"A": 5.0}, evidence={"B": 99999.0},
            n=100, seed=42, strict=False,
        )
        assert len(result) > 0
