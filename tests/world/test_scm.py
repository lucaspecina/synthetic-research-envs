"""Tests for SCMWorld: structural equations, sampling, do-calculus, scoring."""

from __future__ import annotations

import numpy as np
import pytest

from sreg.world.scm import (
    SCMWorld,
    VariableMeta,
    kl_divergence_gaussian,
    kl_divergence_histogram,
    wasserstein_distance,
)

# ------------------------------------------------------------------
# Fixtures: reusable worlds
# ------------------------------------------------------------------


def _linear_3node() -> SCMWorld:
    """A -> B -> C, linear Gaussian. Analytically tractable."""
    return SCMWorld(
        graph={
            "A": [],
            "B": ["A"],
            "C": ["B"],
        },
        equations={
            "A": lambda p, rng: rng.normal(5.0, 1.0),
            "B": lambda p, rng: 2.0 + 0.8 * p["A"] + rng.normal(0, 0.7),
            "C": lambda p, rng: 1.0 + 0.6 * p["B"] + rng.normal(0, 0.5),
        },
    )


def _collider_3node() -> SCMWorld:
    """A -> C <- B. Classic collider structure."""
    return SCMWorld(
        graph={
            "A": [],
            "B": [],
            "C": ["A", "B"],
        },
        equations={
            "A": lambda p, rng: rng.normal(0, 1),
            "B": lambda p, rng: rng.normal(0, 1),
            "C": lambda p, rng: 0.5 * p["A"] + 0.5 * p["B"] + rng.normal(0, 0.3),
        },
    )


def _confounder_3node() -> SCMWorld:
    """A <- Z -> B. Z confounds A and B."""
    return SCMWorld(
        graph={
            "Z": [],
            "A": ["Z"],
            "B": ["Z"],
        },
        equations={
            "Z": lambda p, rng: rng.normal(0, 1),
            "A": lambda p, rng: 0.7 * p["Z"] + rng.normal(0, 0.5),
            "B": lambda p, rng: 0.9 * p["Z"] + rng.normal(0, 0.5),
        },
    )


def _nonlinear_5node() -> SCMWorld:
    """5-node world with nonlinear equations (threshold + sigmoid)."""

    def sigmoid(x: float) -> float:
        return 1.0 / (1.0 + np.exp(-x))

    return SCMWorld(
        graph={
            "load": [],
            "fitness": [],
            "exercise": ["load", "fitness"],
            "temperature": ["exercise"],
            "risk": ["temperature"],
        },
        equations={
            "load": lambda p, rng: rng.uniform(2, 15),
            "fitness": lambda p, rng: rng.normal(50, 10),
            "exercise": lambda p, rng: (
                min(p["load"] * 0.7 + p["fitness"] * 0.01, 10) + rng.normal(0, 0.5)
            ),
            "temperature": lambda p, rng: (
                36.5
                + (
                    2.0 * np.sqrt(max(p["exercise"] - 7, 0))
                    if p["exercise"] > 7
                    else 0.3 * p["exercise"]
                )
                + rng.normal(0, 0.3)
            ),
            "risk": lambda p, rng: sigmoid(p["temperature"] - 39) + rng.normal(0, 0.02),
        },
        variable_meta={
            "load": VariableMeta(unit="hours/week", range=(2, 15)),
            "fitness": VariableMeta(unit="VO2max mL/kg/min", range=(20, 80)),
            "exercise": VariableMeta(unit="intensity 0-10", range=(0, 10)),
            "temperature": VariableMeta(unit="celsius", range=(36, 42)),
            "risk": VariableMeta(unit="probability", range=(0, 1)),
        },
    )


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


class TestValidation:
    def test_cycle_raises(self):
        with pytest.raises(ValueError, match="cycles"):
            SCMWorld(
                graph={"A": ["B"], "B": ["A"]},
                equations={
                    "A": lambda p, rng: 0,
                    "B": lambda p, rng: 0,
                },
            )

    def test_missing_equation_raises(self):
        with pytest.raises(ValueError, match="without equations"):
            SCMWorld(
                graph={"A": [], "B": ["A"]},
                equations={"A": lambda p, rng: 0},
            )

    def test_unknown_parent_raises(self):
        with pytest.raises(ValueError, match="unknown variables"):
            SCMWorld(
                graph={"A": ["NONEXISTENT"]},
                equations={"A": lambda p, rng: 0},
            )


# ------------------------------------------------------------------
# Graph properties
# ------------------------------------------------------------------


class TestGraphProperties:
    def test_variables_topological(self):
        world = _linear_3node()
        assert world.variables == ["A", "B", "C"]

    def test_roots(self):
        world = _collider_3node()
        assert set(world.roots) == {"A", "B"}

    def test_parents(self):
        world = _collider_3node()
        assert world.parents("C") == ["A", "B"]
        assert world.parents("A") == []

    def test_children(self):
        world = _linear_3node()
        assert world.children("A") == ["B"]
        assert world.children("C") == []


# ------------------------------------------------------------------
# D-separation
# ------------------------------------------------------------------


class TestDSeparation:
    def test_chain_unconditional(self):
        """A -> B -> C: A and C are NOT d-separated (unconditionally)."""
        world = _linear_3node()
        assert not world.is_d_separated("A", "C")

    def test_chain_conditioned_on_middle(self):
        """A -> B -> C: A and C ARE d-separated given B."""
        world = _linear_3node()
        assert world.is_d_separated("A", "C", {"B"})

    def test_collider_unconditional(self):
        """A -> C <- B: A and B ARE d-separated (collider blocks path)."""
        world = _collider_3node()
        assert world.is_d_separated("A", "B")

    def test_collider_conditioned(self):
        """A -> C <- B: A and B are NOT d-separated given C (explaining away)."""
        world = _collider_3node()
        assert not world.is_d_separated("A", "B", {"C"})

    def test_confounder(self):
        """A <- Z -> B: A and B are NOT d-separated, but ARE given Z."""
        world = _confounder_3node()
        assert not world.is_d_separated("A", "B")
        assert world.is_d_separated("A", "B", {"Z"})


# ------------------------------------------------------------------
# Sampling
# ------------------------------------------------------------------


class TestSampling:
    def test_sample_shape(self):
        world = _linear_3node()
        df = world.sample(n=100, seed=42)
        assert df.shape == (100, 3)
        assert list(df.columns) == ["A", "B", "C"]

    def test_sample_reproducible(self):
        world = _linear_3node()
        df1 = world.sample(n=50, seed=42)
        df2 = world.sample(n=50, seed=42)
        assert df1.equals(df2)

    def test_sample_different_seeds(self):
        world = _linear_3node()
        df1 = world.sample(n=50, seed=42)
        df2 = world.sample(n=50, seed=99)
        assert not df1.equals(df2)

    def test_linear_gaussian_statistics(self):
        """For A ~ N(5, 1), B = 2 + 0.8*A + N(0, 0.7), verify E[B] ~ 2 + 0.8*5 = 6."""
        world = _linear_3node()
        df = world.sample(n=50_000, seed=42)
        assert abs(df["A"].mean() - 5.0) < 0.1
        assert abs(df["B"].mean() - 6.0) < 0.1

    def test_nonlinear_realistic_ranges(self):
        """Nonlinear world produces values in realistic ranges."""
        world = _nonlinear_5node()
        df = world.sample(n=1000, seed=42)
        assert df["load"].min() >= 1.5  # uniform(2,15) minus some tolerance
        assert df["load"].max() <= 15.5
        assert df["temperature"].mean() > 36  # body temp
        assert df["temperature"].mean() < 42
        assert df["risk"].mean() > 0  # probability
        assert df["risk"].mean() < 1


# ------------------------------------------------------------------
# do-calculus (interventions)
# ------------------------------------------------------------------


class TestInterventions:
    def test_do_fixes_value(self):
        """do(A=10) should produce A=10 in all samples."""
        world = _linear_3node()
        df = world.sample(n=100, seed=42, do={"A": 10.0})
        assert (df["A"] == 10.0).all()

    def test_do_propagates(self):
        """do(A=10) should shift B: E[B] = 2 + 0.8*10 = 10."""
        world = _linear_3node()
        df = world.sample(n=50_000, seed=42, do={"A": 10.0})
        assert abs(df["B"].mean() - 10.0) < 0.1

    def test_do_vs_observe_different(self):
        """In a confounder: P(B|do(A=x)) != P(B|A=x).

        A <- Z -> B. Observing A=x gives info about Z, which shifts B.
        Intervening do(A=x) cuts the Z->A link, so B is unaffected.
        """
        world = _confounder_3node()
        n = 100_000

        # Interventional: do(A=2), B should still be ~ N(0, sqrt(0.81+0.25))
        do_samples = world.interventional_distribution("B", do={"A": 2.0}, n=n, seed=42)

        # Observational: filter A close to 2. Z is likely ~2/0.7~2.86, so B shifts.
        obs_df = world.sample(n=n, seed=99)
        obs_filtered = obs_df[obs_df["A"].between(1.5, 2.5)]["B"]

        # The means should differ: interventional B is centered near 0,
        # observational B|A~2 is shifted positive (because Z is likely large).
        assert abs(do_samples.mean()) < 0.3  # near 0
        assert obs_filtered.mean() > 1.0  # shifted by confounding

    def test_interventional_distribution_shape(self):
        world = _linear_3node()
        samples = world.interventional_distribution("C", do={"A": 5.0}, n=1000, seed=42)
        assert samples.shape == (1000,)


# ------------------------------------------------------------------
# Adjustment set
# ------------------------------------------------------------------


class TestAdjustmentSet:
    def test_chain_no_adjustment(self):
        """A -> B -> C: no backdoor paths, empty adjustment set."""
        world = _linear_3node()
        adj = world.adjustment_set("A", "C")
        assert adj is not None
        assert len(adj) == 0

    def test_confounder_needs_adjustment(self):
        """A <- Z -> B: must adjust for Z."""
        world = _confounder_3node()
        adj = world.adjustment_set("A", "B")
        assert adj is not None
        assert "Z" in adj


# ------------------------------------------------------------------
# Scoring: KL divergence
# ------------------------------------------------------------------


class TestKLDivergence:
    def test_identical_distributions(self):
        """KL(P || P) ~ 0."""
        rng = np.random.default_rng(42)
        samples = rng.normal(0, 1, size=10_000)
        kl = kl_divergence_histogram(samples, samples)
        assert kl < 0.01

    def test_different_means(self):
        """KL should be positive for different distributions."""
        rng = np.random.default_rng(42)
        p = rng.normal(0, 1, size=10_000)
        q = rng.normal(2, 1, size=10_000)
        kl = kl_divergence_histogram(p, q)
        assert kl > 0.5

    def test_gaussian_closed_form(self):
        """Closed-form KL for Gaussians matches histogram estimate."""
        rng = np.random.default_rng(42)
        mu1, var1 = 0.0, 1.0
        mu2, var2 = 1.0, 2.0

        analytical = kl_divergence_gaussian(mu1, var1, mu2, var2)

        p = rng.normal(mu1, np.sqrt(var1), size=100_000)
        q = rng.normal(mu2, np.sqrt(var2), size=100_000)
        empirical = kl_divergence_histogram(p, q, bins=100)

        # Should be roughly similar (histogram is approximate)
        assert abs(analytical - empirical) < 0.1

    def test_wasserstein_identical(self):
        """Wasserstein(P, P) ~ 0."""
        rng = np.random.default_rng(42)
        samples = rng.normal(0, 1, size=10_000)
        wd = wasserstein_distance(samples, samples)
        assert wd < 0.01

    def test_wasserstein_different(self):
        """Wasserstein should be positive for different distributions."""
        rng = np.random.default_rng(42)
        p = rng.normal(0, 1, size=10_000)
        q = rng.normal(5, 1, size=10_000)
        wd = wasserstein_distance(p, q)
        assert wd > 4.0  # ~5 since means differ by 5


# ------------------------------------------------------------------
# E2E: nonlinear world with causal reasoning
# ------------------------------------------------------------------


class TestNonlinearE2E:
    """End-to-end test with the 5-node heat stroke world."""

    def test_high_exercise_increases_temperature(self):
        """do(exercise=9) should produce higher temperature than do(exercise=3)."""
        world = _nonlinear_5node()
        n = 50_000

        temp_high = world.interventional_distribution(
            "temperature", do={"exercise": 9.0}, n=n, seed=42
        )
        temp_low = world.interventional_distribution(
            "temperature", do={"exercise": 3.0}, n=n, seed=42
        )

        assert temp_high.mean() > temp_low.mean() + 1.0  # clear difference

    def test_high_temperature_increases_risk(self):
        """do(temperature=40) should produce higher risk than do(temperature=37)."""
        world = _nonlinear_5node()
        n = 50_000

        risk_high = world.interventional_distribution(
            "risk", do={"temperature": 40.0}, n=n, seed=42
        )
        risk_low = world.interventional_distribution(
            "risk", do={"temperature": 37.0}, n=n, seed=42
        )

        assert risk_high.mean() > risk_low.mean() + 0.3

    def test_load_does_not_directly_affect_risk(self):
        """Mediator test: load -> exercise -> temperature -> risk.

        Fixing exercise blocks the path from load to risk.
        So do(load=X, exercise=5) should give same risk regardless of load.
        """
        world = _nonlinear_5node()
        n = 50_000

        risk_high_load = world.interventional_distribution(
            "risk", do={"load": 15.0, "exercise": 5.0}, n=n, seed=42
        )
        risk_low_load = world.interventional_distribution(
            "risk", do={"load": 2.0, "exercise": 5.0}, n=n, seed=42
        )

        # Should be essentially the same
        assert abs(risk_high_load.mean() - risk_low_load.mean()) < 0.05

    def test_threshold_effect(self):
        """Temperature equation has threshold at exercise=7.

        Below 7: temp ~ 36.5 + 0.3*exercise (mild).
        Above 7: temp ~ 36.5 + 2*sqrt(exercise-7) (sharp rise).
        """
        world = _nonlinear_5node()
        n = 50_000

        # Just below threshold
        temp_6 = world.interventional_distribution(
            "temperature", do={"exercise": 6.0}, n=n, seed=42
        )
        # Just above threshold
        temp_8 = world.interventional_distribution(
            "temperature", do={"exercise": 8.0}, n=n, seed=42
        )
        # Well above threshold
        temp_10 = world.interventional_distribution(
            "temperature", do={"exercise": 10.0}, n=n, seed=42
        )

        # Below threshold: ~36.5 + 0.3*6 = 38.3
        assert abs(temp_6.mean() - 38.3) < 0.3

        # Above threshold: 36.5 + 2*sqrt(8-7) = 38.5
        assert abs(temp_8.mean() - 38.5) < 0.3

        # Well above: 36.5 + 2*sqrt(10-7) = 36.5 + 3.46 = 39.96
        assert abs(temp_10.mean() - 39.96) < 0.3

    def test_interventional_vs_observational_confounding(self):
        """In the full model, observational correlation between load and risk
        exists (through the causal chain). But intervening on load with fixed
        exercise should eliminate this correlation."""
        world = _nonlinear_5node()
        n = 50_000

        # Observational: high load -> more exercise -> higher temp -> higher risk
        obs = world.sample(n=n, seed=42)
        corr = obs["load"].corr(obs["risk"])
        assert abs(corr) > 0.05  # should be positively correlated

        # Interventional with fixed exercise: breaks the chain
        risk_a = world.interventional_distribution(
            "risk", do={"load": 15.0, "exercise": 5.0}, n=n, seed=42
        )
        risk_b = world.interventional_distribution(
            "risk", do={"load": 2.0, "exercise": 5.0}, n=n, seed=42
        )
        assert abs(risk_a.mean() - risk_b.mean()) < 0.05
