"""Monte Carlo verification of Suite 2 world analytical ground truth.

For each world, we sample N=100K from the SCM (observational and
interventional) and verify that Monte Carlo estimates match the
analytical derivations documented in worlds.py.

This is a one-time validation test. If it passes, the analytical
facts are trustworthy and can be used as gold for Suite 2.
"""

from __future__ import annotations

import numpy as np
import pytest

from .worlds import ALL_WORLDS


N_SAMPLES = 100_000
SEED = 42


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def sample_observational(world, n: int, seed: int) -> dict[str, np.ndarray]:
    """Sample n observations from the SCM (no intervention)."""
    rng = np.random.default_rng(seed)
    topo = world._topo_order
    data = {var: np.zeros(n) for var in topo}
    for i in range(n):
        vals = {}
        for var in topo:
            parents = {p: vals[p] for p in world.graph[var]}
            vals[var] = world.equations[var](parents, rng)
        for var in topo:
            data[var][i] = vals[var]
    return data


def sample_interventional(
    world,
    interventions: dict[str, float],
    n: int,
    seed: int,
) -> dict[str, np.ndarray]:
    """Sample n observations from the SCM with do(var=value)."""
    rng = np.random.default_rng(seed)
    topo = world._topo_order
    data = {var: np.zeros(n) for var in topo}
    for i in range(n):
        vals = {}
        for var in topo:
            if var in interventions:
                vals[var] = interventions[var]
            else:
                parents = {p: vals[p] for p in world.graph[var]}
                vals[var] = world.equations[var](parents, rng)
        for var in topo:
            data[var][i] = vals[var]
    return data


# ===================================================================
# W1: Comparative Effectiveness — Monte Carlo checks
# ===================================================================

class TestW1MonteCarlo:
    """Verify W1 analytical facts against Monte Carlo."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.world = ALL_WORLDS["w1_comparative_effectiveness"]

    def test_ate_T_to_Y(self):
        """ATE(T->Y) per unit should be ~0.68."""
        data_t1 = sample_interventional(self.world, {"T": 1.0}, N_SAMPLES, SEED)
        data_t0 = sample_interventional(self.world, {"T": 0.0}, N_SAMPLES, SEED + 1)
        ate = np.mean(data_t1["Y"]) - np.mean(data_t0["Y"])
        assert abs(ate - 0.68) < 0.02, f"ATE(T->Y) = {ate:.4f}, expected ~0.68"

    def test_ate_T_to_Y_direct_component(self):
        """Direct effect of T on Y (fixing M) should be ~0.50."""
        # do(T=1, M=0) vs do(T=0, M=0) isolates direct effect
        data_hi = sample_interventional(
            self.world, {"T": 1.0, "M": 0.0}, N_SAMPLES, SEED
        )
        data_lo = sample_interventional(
            self.world, {"T": 0.0, "M": 0.0}, N_SAMPLES, SEED + 1
        )
        direct = np.mean(data_hi["Y"]) - np.mean(data_lo["Y"])
        assert abs(direct - 0.50) < 0.02, f"Direct(T->Y) = {direct:.4f}, expected ~0.50"

    def test_heterogeneity_by_B(self):
        """Effect of T on Y given B should vary: 0.68 + 0.35*b."""
        # At B=+1: expected effect = 1.03
        data_b1_t1 = sample_interventional(
            self.world, {"T": 1.0, "B": 1.0}, N_SAMPLES, SEED
        )
        data_b1_t0 = sample_interventional(
            self.world, {"T": 0.0, "B": 1.0}, N_SAMPLES, SEED + 1
        )
        ate_b1 = np.mean(data_b1_t1["Y"]) - np.mean(data_b1_t0["Y"])
        assert abs(ate_b1 - 1.03) < 0.02, f"ATE at B=1: {ate_b1:.4f}, expected ~1.03"

        # At B=-1: expected effect = 0.33
        data_bm1_t1 = sample_interventional(
            self.world, {"T": 1.0, "B": -1.0}, N_SAMPLES, SEED + 2
        )
        data_bm1_t0 = sample_interventional(
            self.world, {"T": 0.0, "B": -1.0}, N_SAMPLES, SEED + 3
        )
        ate_bm1 = np.mean(data_bm1_t1["Y"]) - np.mean(data_bm1_t0["Y"])
        assert abs(ate_bm1 - 0.33) < 0.02, f"ATE at B=-1: {ate_bm1:.4f}, expected ~0.33"

    def test_total_effect_A_on_Y(self):
        """Total effect of A on Y should be ~-0.106 per unit."""
        data_a1 = sample_interventional(self.world, {"A": 1.0}, N_SAMPLES, SEED)
        data_a0 = sample_interventional(self.world, {"A": 0.0}, N_SAMPLES, SEED + 1)
        total = np.mean(data_a1["Y"]) - np.mean(data_a0["Y"])
        assert abs(total - (-0.106)) < 0.02, (
            f"Total(A->Y) = {total:.4f}, expected ~-0.106"
        )

    def test_ate_T_to_SE(self):
        """ATE(T->SE) per unit should be ~0.70."""
        data_t1 = sample_interventional(self.world, {"T": 1.0}, N_SAMPLES, SEED)
        data_t0 = sample_interventional(self.world, {"T": 0.0}, N_SAMPLES, SEED + 1)
        ate = np.mean(data_t1["SE"]) - np.mean(data_t0["SE"])
        assert abs(ate - 0.70) < 0.02, f"ATE(T->SE) = {ate:.4f}, expected ~0.70"

    def test_mediation_indirect_T_M_Y(self):
        """Indirect effect T->M->Y should be ~0.18."""
        # indirect = total - direct = 0.68 - 0.50 = 0.18
        # Or: do(T=1) vs do(T=0), then subtract direct
        data_t1 = sample_interventional(self.world, {"T": 1.0}, N_SAMPLES, SEED)
        data_t0 = sample_interventional(self.world, {"T": 0.0}, N_SAMPLES, SEED + 1)
        data_t1_m0 = sample_interventional(
            self.world, {"T": 1.0, "M": 0.0}, N_SAMPLES, SEED + 2
        )
        data_t0_m0 = sample_interventional(
            self.world, {"T": 0.0, "M": 0.0}, N_SAMPLES, SEED + 3
        )
        total = np.mean(data_t1["Y"]) - np.mean(data_t0["Y"])
        direct = np.mean(data_t1_m0["Y"]) - np.mean(data_t0_m0["Y"])
        indirect = total - direct
        assert abs(indirect - 0.18) < 0.03, (
            f"Indirect(T->M->Y) = {indirect:.4f}, expected ~0.18"
        )


# ===================================================================
# W2: Observational Epidemiology — Monte Carlo checks
# ===================================================================

class TestW2MonteCarlo:
    """Verify W2 analytical facts against Monte Carlo."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.world = ALL_WORLDS["w2_observational_epidemiology"]

    def test_ate_E_to_D(self):
        """ATE(E->D) per unit should be ~-0.20 (protective)."""
        data_e1 = sample_interventional(self.world, {"E": 1.0}, N_SAMPLES, SEED)
        data_e0 = sample_interventional(self.world, {"E": 0.0}, N_SAMPLES, SEED + 1)
        ate = np.mean(data_e1["D"]) - np.mean(data_e0["D"])
        assert abs(ate - (-0.20)) < 0.02, f"ATE(E->D) = {ate:.4f}, expected ~-0.20"

    def test_simpson_reversal(self):
        """Crude Cov(E,D) should be POSITIVE while ATE is negative."""
        data = sample_observational(self.world, N_SAMPLES, SEED)
        cov_ed = np.cov(data["E"], data["D"])[0, 1]
        assert cov_ed > 0, f"Cov(E,D) = {cov_ed:.4f}, expected > 0 (Simpson's)"
        # Also verify the ATE is indeed negative
        data_e1 = sample_interventional(self.world, {"E": 1.0}, N_SAMPLES, SEED + 1)
        data_e0 = sample_interventional(self.world, {"E": 0.0}, N_SAMPLES, SEED + 2)
        ate = np.mean(data_e1["D"]) - np.mean(data_e0["D"])
        assert ate < 0, f"ATE = {ate:.4f}, expected < 0"

    def test_mediation_decomposition(self):
        """Direct=-0.40, indirect=+0.20, total=-0.20."""
        # Direct: do(E=1,M=0) vs do(E=0,M=0)
        data_e1m0 = sample_interventional(
            self.world, {"E": 1.0, "M": 0.0}, N_SAMPLES, SEED
        )
        data_e0m0 = sample_interventional(
            self.world, {"E": 0.0, "M": 0.0}, N_SAMPLES, SEED + 1
        )
        direct = np.mean(data_e1m0["D"]) - np.mean(data_e0m0["D"])
        assert abs(direct - (-0.40)) < 0.02, (
            f"Direct(E->D) = {direct:.4f}, expected ~-0.40"
        )

        # Total
        data_e1 = sample_interventional(self.world, {"E": 1.0}, N_SAMPLES, SEED + 2)
        data_e0 = sample_interventional(self.world, {"E": 0.0}, N_SAMPLES, SEED + 3)
        total = np.mean(data_e1["D"]) - np.mean(data_e0["D"])
        indirect = total - direct
        assert abs(indirect - 0.20) < 0.03, (
            f"Indirect(E->M->D) = {indirect:.4f}, expected ~+0.20"
        )

    def test_crude_cov_magnitude(self):
        """Crude Cov(E,D) ~ +0.182 (analytical)."""
        data = sample_observational(self.world, N_SAMPLES, SEED)
        cov_ed = np.cov(data["E"], data["D"])[0, 1]
        assert abs(cov_ed - 0.182) < 0.03, (
            f"Cov(E,D) = {cov_ed:.4f}, expected ~0.182"
        )

    def test_I_no_direct_effect_on_D(self):
        """I should affect D ONLY through E (valid instrument)."""
        # do(I=1, E=0) vs do(I=0, E=0): D should be the same
        data_i1e0 = sample_interventional(
            self.world, {"I": 1.0, "E": 0.0}, N_SAMPLES, SEED
        )
        data_i0e0 = sample_interventional(
            self.world, {"I": 0.0, "E": 0.0}, N_SAMPLES, SEED + 1
        )
        diff = np.mean(data_i1e0["D"]) - np.mean(data_i0e0["D"])
        assert abs(diff) < 0.02, (
            f"I->D (fixing E) = {diff:.4f}, expected ~0 (I is instrument)"
        )


# ===================================================================
# W3: Environmental Health — Monte Carlo checks
# ===================================================================

class TestW3MonteCarlo:
    """Verify W3 analytical facts against Monte Carlo."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.world = ALL_WORLDS["w3_environmental_health"]

    def test_temp_to_H_below_threshold(self):
        """Below Temp=0, slope of H w.r.t. Temp should be ~-0.20."""
        # Use two interventional values both < 0
        data_lo = sample_interventional(
            self.world, {"Temp": -1.0}, N_SAMPLES, SEED
        )
        data_hi = sample_interventional(
            self.world, {"Temp": -0.5}, N_SAMPLES, SEED + 1
        )
        slope = (np.mean(data_hi["H"]) - np.mean(data_lo["H"])) / 0.5
        assert abs(slope - (-0.20)) < 0.03, (
            f"Slope(Temp->H, below threshold) = {slope:.4f}, expected ~-0.20"
        )

    def test_temp_to_H_above_threshold(self):
        """Above Temp=0, slope of H w.r.t. Temp should be ~-1.00."""
        data_lo = sample_interventional(
            self.world, {"Temp": 0.5}, N_SAMPLES, SEED
        )
        data_hi = sample_interventional(
            self.world, {"Temp": 1.0}, N_SAMPLES, SEED + 1
        )
        slope = (np.mean(data_hi["H"]) - np.mean(data_lo["H"])) / 0.5
        assert abs(slope - (-1.00)) < 0.03, (
            f"Slope(Temp->H, above threshold) = {slope:.4f}, expected ~-1.00"
        )

    def test_temp_threshold_discontinuity(self):
        """There should be a slope change at Temp=0."""
        # Measure slope just below and just above
        # Below: Temp -0.5 to -0.1
        data_below_lo = sample_interventional(
            self.world, {"Temp": -0.5}, N_SAMPLES, SEED
        )
        data_below_hi = sample_interventional(
            self.world, {"Temp": -0.1}, N_SAMPLES, SEED + 1
        )
        slope_below = (
            (np.mean(data_below_hi["H"]) - np.mean(data_below_lo["H"])) / 0.4
        )

        # Above: Temp 0.1 to 0.5
        data_above_lo = sample_interventional(
            self.world, {"Temp": 0.1}, N_SAMPLES, SEED + 2
        )
        data_above_hi = sample_interventional(
            self.world, {"Temp": 0.5}, N_SAMPLES, SEED + 3
        )
        slope_above = (
            (np.mean(data_above_hi["H"]) - np.mean(data_above_lo["H"])) / 0.4
        )

        # The slope should change by about -0.80 at the threshold
        slope_change = slope_above - slope_below
        assert abs(slope_change - (-0.80)) < 0.05, (
            f"Slope change at threshold = {slope_change:.4f}, expected ~-0.80"
        )

    def test_P_to_H_total_causal(self):
        """True total effect P->H should be ~-0.32 (direct + via W)."""
        # do(P=1, U=0) vs do(P=0, U=0) to remove latent confounding
        data_p1 = sample_interventional(
            self.world, {"P": 1.0, "U": 0.0}, N_SAMPLES, SEED
        )
        data_p0 = sample_interventional(
            self.world, {"P": 0.0, "U": 0.0}, N_SAMPLES, SEED + 1
        )
        ate = np.mean(data_p1["H"]) - np.mean(data_p0["H"])
        assert abs(ate - (-0.32)) < 0.02, (
            f"ATE(P->H, fixing U) = {ate:.4f}, expected ~-0.32"
        )

    def test_P_to_H_confounded_by_U(self):
        """Crude association of P,H differs from causal effect (U confounds)."""
        data = sample_observational(self.world, N_SAMPLES, SEED)
        # Crude regression coefficient of H on P (biased by U)
        cov_ph = np.cov(data["P"], data["H"])[0, 1]
        var_p = np.var(data["P"])
        crude_beta = cov_ph / var_p

        # True ATE is -0.32, but crude beta should be different
        # because U->P (positive) and U->H (positive) creates positive
        # confounding bias. So crude_beta should be LESS negative than -0.32.
        assert crude_beta > -0.32 + 0.05, (
            f"Crude beta(P->H) = {crude_beta:.4f}, should be less negative "
            f"than true ATE=-0.32 due to positive confounding by U"
        )

    def test_windspeed_null_effect(self):
        """WindSpeed should have ZERO effect on H."""
        data_w1 = sample_interventional(
            self.world, {"WindSpeed": 2.0}, N_SAMPLES, SEED
        )
        data_w0 = sample_interventional(
            self.world, {"WindSpeed": -2.0}, N_SAMPLES, SEED + 1
        )
        diff = np.mean(data_w1["H"]) - np.mean(data_w0["H"])
        assert abs(diff) < 0.02, (
            f"Effect(WindSpeed->H) = {diff:.4f}, expected ~0 (null)"
        )

    def test_R_only_indirect_effect(self):
        """R affects H only indirectly (through Temp and P)."""
        # do(R=1, Temp=0, P=0) vs do(R=0, Temp=0, P=0): should be same
        data_r1 = sample_interventional(
            self.world, {"R": 1.0, "Temp": 0.0, "P": 0.0}, N_SAMPLES, SEED
        )
        data_r0 = sample_interventional(
            self.world, {"R": 0.0, "Temp": 0.0, "P": 0.0}, N_SAMPLES, SEED + 1
        )
        diff = np.mean(data_r1["H"]) - np.mean(data_r0["H"])
        assert abs(diff) < 0.02, (
            f"Direct(R->H, fixing Temp+P) = {diff:.4f}, expected ~0"
        )

    def test_tail_risk_high_temp(self):
        """P(H < -1.0 | do(Temp=1.5)) should be substantially higher than
        P(H < -1.0 | do(Temp=-1.0)) — tail risk from high temperature."""
        data_hot = sample_interventional(
            self.world, {"Temp": 1.5}, N_SAMPLES, SEED
        )
        data_cold = sample_interventional(
            self.world, {"Temp": -1.0}, N_SAMPLES, SEED + 1
        )
        p_tail_hot = np.mean(data_hot["H"] < -1.0)
        p_tail_cold = np.mean(data_cold["H"] < -1.0)
        assert p_tail_hot > p_tail_cold + 0.05, (
            f"P(H<-1 | hot)={p_tail_hot:.4f} vs P(H<-1 | cold)={p_tail_cold:.4f}; "
            f"high temp should produce much more tail risk"
        )


# ===================================================================
# ADDITIONAL TESTS (recommended by Codex review)
# ===================================================================

class TestW1VarianceEffect:
    """W1: The B*T interaction makes Var(Y|do(T)) depend on T.

    Under do(T=t): the term 0.35*B*T contributes 0.35^2 * t^2 * Var(B)
    to the variance. At T=0 this is zero; at T=1 it adds 0.1225.
    So Var(Y|do(T=1)) should be noticeably larger than Var(Y|do(T=0)).
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.world = ALL_WORLDS["w1_comparative_effectiveness"]

    def test_variance_increases_with_T(self):
        """Var(Y|do(T=1)) > Var(Y|do(T=0)) due to interaction term."""
        data_t1 = sample_interventional(self.world, {"T": 1.0}, N_SAMPLES, SEED)
        data_t0 = sample_interventional(self.world, {"T": 0.0}, N_SAMPLES, SEED + 1)
        var_t1 = np.var(data_t1["Y"])
        var_t0 = np.var(data_t0["Y"])
        # The interaction adds ~0.1225 to variance at T=1
        assert var_t1 > var_t0 + 0.08, (
            f"Var(Y|do(T=1))={var_t1:.4f}, Var(Y|do(T=0))={var_t0:.4f}; "
            f"interaction term should increase variance at T=1"
        )

    def test_variance_asymmetric_due_to_cross_term(self):
        """Var(Y|do(T=-1)) < Var(Y|do(T=0)) < Var(Y|do(T=1)).

        The B-related variance contribution has a cross-term:
          Var_B = 0.04 + 0.1225*t^2 + 0.14*t
        At t=-1: 0.0225 (B and B*T partially cancel)
        At t=0:  0.04
        At t=1:  0.3025 (B and B*T reinforce)
        So variance is NOT symmetric in |T| — it's monotone increasing in T.
        """
        data_tm1 = sample_interventional(self.world, {"T": -1.0}, N_SAMPLES, SEED)
        data_t0 = sample_interventional(self.world, {"T": 0.0}, N_SAMPLES, SEED + 1)
        data_t1 = sample_interventional(self.world, {"T": 1.0}, N_SAMPLES, SEED + 2)
        var_tm1 = np.var(data_tm1["Y"])
        var_t0 = np.var(data_t0["Y"])
        var_t1 = np.var(data_t1["Y"])
        assert var_tm1 < var_t0 < var_t1, (
            f"Expected Var(T=-1)={var_tm1:.4f} < Var(T=0)={var_t0:.4f} "
            f"< Var(T=1)={var_t1:.4f} (cross-term makes variance monotone in T)"
        )


class TestW2PartialCorrelation:
    """W2: Partial correlation of E,D given C should be negative,
    while crude correlation is positive (Simpson's at correlation level)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.world = ALL_WORLDS["w2_observational_epidemiology"]

    def test_partial_corr_E_D_given_C(self):
        """corr(E,D|C) < 0 while corr(E,D) > 0."""
        data = sample_observational(self.world, N_SAMPLES, SEED)
        E, D, C = data["E"], data["D"], data["C"]

        # Crude correlation
        crude_corr = np.corrcoef(E, D)[0, 1]
        assert crude_corr > 0, f"Crude corr(E,D) = {crude_corr:.4f}, expected > 0"

        # Partial correlation via residualization
        # Regress E on C, D on C, then correlate residuals
        beta_ec = np.cov(E, C)[0, 1] / np.var(C)
        beta_dc = np.cov(D, C)[0, 1] / np.var(C)
        e_resid = E - beta_ec * C
        d_resid = D - beta_dc * C
        partial_corr = np.corrcoef(e_resid, d_resid)[0, 1]

        assert partial_corr < 0, (
            f"Partial corr(E,D|C) = {partial_corr:.4f}, expected < 0 "
            f"(crude={crude_corr:.4f} is positive — Simpson's at corr level)"
        )

    def test_collider_bias_conditioning_on_L(self):
        """Conditioning on L (collider) should bias the E->D estimate."""
        data = sample_observational(self.world, N_SAMPLES, SEED)
        E, D, C, L = data["E"], data["D"], data["C"], data["L"]

        # Correct partial corr: adjust for C only
        beta_ec = np.cov(E, C)[0, 1] / np.var(C)
        beta_dc = np.cov(D, C)[0, 1] / np.var(C)
        e_resid_c = E - beta_ec * C
        d_resid_c = D - beta_dc * C
        partial_corr_c = np.corrcoef(e_resid_c, d_resid_c)[0, 1]

        # Biased: adjust for C AND L (opens collider path)
        X = np.column_stack([C, L])
        XtX_inv = np.linalg.inv(X.T @ X)
        beta_e = XtX_inv @ (X.T @ E)
        beta_d = XtX_inv @ (X.T @ D)
        e_resid_cl = E - X @ beta_e
        d_resid_cl = D - X @ beta_d
        partial_corr_cl = np.corrcoef(e_resid_cl, d_resid_cl)[0, 1]

        # Conditioning on L should push the estimate AWAY from the true effect
        # The correct partial corr (given C) should be closer to the true
        # negative effect than the biased one (given C+L)
        assert abs(partial_corr_cl - partial_corr_c) > 0.03, (
            f"Partial corr given C = {partial_corr_c:.4f}, "
            f"given C+L = {partial_corr_cl:.4f}; "
            f"conditioning on collider L should distort the estimate"
        )


class TestW2W3Identifiability:
    """Structural identifiability checks across worlds."""

    def test_w2_ate_identifiable_via_C(self):
        """W2: ATE(E->D) IS identifiable by adjusting for C.

        Adjusting for C (valid backdoor) should recover the true ATE=-0.20.
        NOT adjusting gives the confounded (positive) association.
        """
        world = ALL_WORLDS["w2_observational_epidemiology"]
        data = sample_observational(world, N_SAMPLES, SEED)
        E, D, C = data["E"], data["D"], data["C"]

        # Multiple regression: D ~ E + C => coef of E ~ true ATE
        X = np.column_stack([E, C])
        XtX_inv = np.linalg.inv(X.T @ X)
        betas = XtX_inv @ (X.T @ D)
        adjusted_beta_E = betas[0]

        assert abs(adjusted_beta_E - (-0.20)) < 0.02, (
            f"Adjusted beta(E->D | C) = {adjusted_beta_E:.4f}, expected ~-0.20"
        )

    def test_w3_ate_P_H_not_identifiable(self):
        """W3: ATE(P->H) is NOT identifiable from observables.

        No set of observable variables can block the U->P, U->H backdoor
        because U is latent. Adjusting for any observable subset should
        give a biased estimate (different from true -0.32).
        """
        world = ALL_WORLDS["w3_environmental_health"]
        data = sample_observational(world, N_SAMPLES, SEED)

        # All observable variables except P and H
        observables = ["R", "Temp", "W", "WindSpeed"]
        P, H = data["P"], data["H"]

        # Try adjusting for ALL observables — still biased
        X_all = np.column_stack([P] + [data[v] for v in observables])
        XtX_inv = np.linalg.inv(X_all.T @ X_all)
        betas = XtX_inv @ (X_all.T @ H)
        adjusted_beta_P = betas[0]

        # True ATE is -0.32. The adjusted estimate should be different
        # because U is latent and no observable set blocks U->P, U->H.
        bias = abs(adjusted_beta_P - (-0.32))
        assert bias > 0.03, (
            f"Adjusted beta(P | all observables) = {adjusted_beta_P:.4f}; "
            f"should differ from true ATE=-0.32 by >{0.03} "
            f"(got bias={bias:.4f}) — U confounding is not blockable"
        )
