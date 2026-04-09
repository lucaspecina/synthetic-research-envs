"""Tests for Open Investigation Verifier: execute AtomicSpecs against SCMWorld."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sreg.models.open_investigation import (
    ApproxEq,
    Assertion,
    AssertionKind,
    AtomicSpec,
    Comparison,
    ComparisonKind,
    ConditionRange,
    FamilyAtom,
    FamilyKey,
    InSet,
    Measurement,
    MeasurementKind,
    QuantileRange,
    QueryArm,
    QueryKind,
    SalienceFamily,
)
from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_verifier import (
    _filter_condition,
    _find_backdoor_set,
    _measure_from_samples,
    score_claim_against_family,
    score_episode,
    verify_atom,
)
from sreg.world.scm import SCMWorld

# ---------------------------------------------------------------------------
# Test worlds
# ---------------------------------------------------------------------------


def _simple_world() -> SCMWorld:
    """A -> Y with positive effect. Simple and predictable."""
    return SCMWorld(
        id="test-simple",
        graph={"A": [], "Y": ["A"]},
        equations={
            "A": lambda p, rng: rng.normal(0, 1),
            "Y": lambda p, rng: 0.8 * p["A"] + rng.normal(0, 0.5),
        },
    )


def _confounder_world() -> SCMWorld:
    """C -> A -> Y, C -> Y. C confounds A->Y."""
    return SCMWorld(
        id="test-conf",
        graph={"C": [], "A": ["C"], "Y": ["A", "C"]},
        equations={
            "C": lambda p, rng: rng.normal(0, 1),
            "A": lambda p, rng: p["C"] + rng.normal(0, 1),
            "Y": lambda p, rng: 0.5 * p["A"] + 0.3 * p["C"] + rng.normal(0, 0.5),
        },
    )


def _threshold_world() -> SCMWorld:
    """A -> Y with threshold: Y = 0 if A < 0.5 else 2*A + noise."""
    return SCMWorld(
        id="test-threshold",
        graph={"A": [], "Y": ["A"]},
        equations={
            "A": lambda p, rng: rng.uniform(0, 1),
            "Y": lambda p, rng: (
                2.0 * p["A"] + rng.normal(0, 0.1) if p["A"] > 0.5 else rng.normal(0, 0.1)
            ),
        },
    )


# ---------------------------------------------------------------------------
# verify_atom tests
# ---------------------------------------------------------------------------


class TestVerifyAtom:
    def test_positive_effect_detected(self):
        """A -> Y with positive effect should verify as positive."""
        world = _simple_world()
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="ate_pos",
            arms=(
                QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"A": 1.0}),
                QueryArm(label="lo", kind=QueryKind.INTERVENE, values={"A": -1.0}),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )
        verdict = verify_atom(spec, world, solver, n_mc=20_000, seed=42)
        assert verdict.solver_assertion_holds is True
        assert verdict.score == 1.0
        assert isinstance(verdict.ground_truth, float)
        assert verdict.ground_truth > 0  # positive effect

    def test_near_zero_when_no_effect(self):
        """Two independent variables: effect should be near zero."""
        world = SCMWorld(
            id="test-indep",
            graph={"A": [], "Y": []},
            equations={
                "A": lambda p, rng: rng.normal(0, 1),
                "Y": lambda p, rng: rng.normal(0, 1),
            },
        )
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="no_effect",
            arms=(
                QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"A": 1.0}),
                QueryArm(label="lo", kind=QueryKind.INTERVENE, values={"A": -1.0}),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
            assertion=Assertion(kind=AssertionKind.NEAR_ZERO, tolerance=0.15),
        )
        verdict = verify_atom(spec, world, solver, n_mc=20_000, seed=42)
        assert verdict.solver_assertion_holds is True

    def test_observational_conditioning(self):
        """Observational conditioning: P(Y | A=high) vs P(Y | A=low)."""
        world = _simple_world()
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="obs_cond",
            arms=(
                QueryArm(label="hi", kind=QueryKind.OBSERVE, values={"A": 1.0}),
                QueryArm(label="lo", kind=QueryKind.OBSERVE, values={"A": -1.0}),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )
        verdict = verify_atom(spec, world, solver, n_mc=50_000, seed=42)
        assert verdict.solver_assertion_holds is True

    def test_variance_measurement(self):
        """Verify variance measurement works."""
        world = _simple_world()
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="var1",
            arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
            measurement=Measurement(kind=MeasurementKind.VARIANCE, target="Y"),
            comparison=Comparison(kind=ComparisonKind.IDENTITY),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )
        verdict = verify_atom(spec, world, solver, n_mc=20_000, seed=42)
        assert verdict.solver_assertion_holds is True
        assert verdict.ground_truth > 0

    def test_tail_probability(self):
        """Verify tail probability measurement."""
        world = _simple_world()
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="tail1",
            arms=(
                QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"A": 2.0}),
                QueryArm(label="lo", kind=QueryKind.INTERVENE, values={"A": -2.0}),
            ),
            measurement=Measurement(
                kind=MeasurementKind.TAIL_PROB, target="Y", threshold=1.0
            ),
            comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )
        verdict = verify_atom(spec, world, solver, n_mc=20_000, seed=42)
        assert verdict.solver_assertion_holds is True

    def test_partial_correlation(self):
        """Verify partial correlation measurement."""
        world = _confounder_world()
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="pcor1",
            arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
            measurement=Measurement(
                kind=MeasurementKind.PARTIAL_CORRELATION,
                lhs="A",
                rhs="Y",
                cond_set=("C",),
            ),
            comparison=Comparison(kind=ComparisonKind.IDENTITY),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )
        verdict = verify_atom(spec, world, solver, n_mc=50_000, seed=42)
        assert verdict.solver_assertion_holds is True

    def test_adjust_with_partial_correlation_does_not_silently_return_mean(self):
        """REGRESSION (P06 forensics, policy_equity): adjust+partial_correlation
        was silently falling through _measure_from_samples() to np.mean(samples),
        i.e. returning E[Y | do(treatment=0)] as if it were a partial correlation.
        The assertion was then applied against that meaningless number, producing
        wrong truth values for claims whose compiler picked arm.kind=ADJUST.

        Defense layers after P06:
          1. AtomicSpec.validate_arm_measurement_compatibility — first line of
             defense, rejects this combination at construction time. Tested in
             tests/models/test_open_investigation.py.
          2. _measure_from_samples — second line of defense in the verifier.
             If a spec ever bypasses validation (e.g. via model_construct or a
             legacy frozen artifact loaded by a future code path that skips
             validation), the verifier itself must NOT silently produce a
             meaningful-looking number. It must return NaN.

        This test targets the second layer directly, by feeding the function
        a 1-D outcome sample array (the only thing the adjust executor ever
        produces) plus a partial_correlation Measurement, and asserting NaN.
        It does not need to construct an AtomicSpec or call verify_atom: the
        bug being prevented lives entirely inside _measure_from_samples.
        """
        # Simulate the output of _run_adjustment: 1-D outcome samples
        outcome_samples = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        bad_measurement = Measurement(
            kind=MeasurementKind.PARTIAL_CORRELATION,
            lhs="A",
            rhs="Y",
            cond_set=("C",),
        )

        value = _measure_from_samples(bad_measurement, outcome_samples)

        assert isinstance(value, float) and np.isnan(value), (
            "Verifier silently returned a non-NaN value for adjust + "
            "partial_correlation. This is the policy_equity P06 bug. "
            f"Got value={value!r}."
        )

        # Sanity: the SAME function returns a real number for a compatible
        # measurement (mean), so the NaN above is specifically due to the
        # incompatibility, not a generic always-NaN bug.
        ok_measurement = Measurement(kind=MeasurementKind.MEAN, target="Y")
        ok_value = _measure_from_samples(ok_measurement, outcome_samples)
        assert isinstance(ok_value, float) and not np.isnan(ok_value), (
            f"Compatible mean measurement should return a real number, "
            f"got {ok_value!r}"
        )
        assert ok_value == pytest.approx(3.0)

    def test_sweep_changepoint(self):
        """Verify sweep + changepoint detection."""
        world = _threshold_world()
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="cp1",
            arms=(
                QueryArm(
                    label="sweep",
                    kind=QueryKind.SWEEP,
                    sweep_var="A",
                    sweep_values=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9),
                    sweep_base=QueryKind.INTERVENE,
                ),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.PIECEWISE_FIT),
            assertion=Assertion(kind=AssertionKind.CHANGEPOINT_EXISTS),
        )
        verdict = verify_atom(spec, world, solver, n_mc=10_000, seed=42)
        assert verdict.solver_assertion_holds is True


# ---------------------------------------------------------------------------
# Scoring tests
# ---------------------------------------------------------------------------


    def test_mediation_indirect_effect(self):
        """Mediation spec: 4-arm contrast-diff detects indirect effect via M."""
        # X -> M -> Y, X -> Y: partial mediation
        world = SCMWorld(
            id="test-mediation",
            graph={"X": [], "M": ["X"], "Y": ["X", "M"]},
            equations={
                "X": lambda p, rng: rng.normal(0, 1),
                "M": lambda p, rng: 0.7 * p["X"] + rng.normal(0, 0.3),
                "Y": lambda p, rng: 0.3 * p["X"] + 0.6 * p["M"] + rng.normal(0, 0.3),
            },
        )
        solver = SCMSolver(world)
        # m_ref: E[M | do(X=-1)] ≈ -0.7
        m_samples = solver.interventional_samples("M", do={"X": -1.0}, n=10_000, seed=42)
        m_ref = float(m_samples.mean())

        spec = AtomicSpec(
            spec_id="med_X_M_Y",
            arms=(
                QueryArm(label="total_hi", kind=QueryKind.INTERVENE, values={"X": 1.0}),
                QueryArm(label="total_lo", kind=QueryKind.INTERVENE, values={"X": -1.0}),
                QueryArm(
                    label="direct_hi",
                    kind=QueryKind.INTERVENE,
                    values={"X": 1.0, "M": m_ref},
                ),
                QueryArm(
                    label="direct_lo",
                    kind=QueryKind.INTERVENE,
                    values={"X": -1.0, "M": m_ref},
                ),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.CONTRAST_DIFF),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )
        verdict = verify_atom(spec, world, solver, n_mc=20_000, seed=42)
        assert verdict.solver_assertion_holds is True, (
            f"Indirect effect should be positive, got {verdict.ground_truth}"
        )
        assert verdict.score == 1.0

    def test_no_mediation_when_no_path(self):
        """No mediation: X -> Y directly, M independent. Indirect should be ~0."""
        world = SCMWorld(
            id="test-no-med",
            graph={"X": [], "M": [], "Y": ["X"]},
            equations={
                "X": lambda p, rng: rng.normal(0, 1),
                "M": lambda p, rng: rng.normal(0, 1),
                "Y": lambda p, rng: 0.8 * p["X"] + rng.normal(0, 0.3),
            },
        )
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="no_med",
            arms=(
                QueryArm(label="total_hi", kind=QueryKind.INTERVENE, values={"X": 1.0}),
                QueryArm(label="total_lo", kind=QueryKind.INTERVENE, values={"X": -1.0}),
                QueryArm(
                    label="direct_hi",
                    kind=QueryKind.INTERVENE,
                    values={"X": 1.0, "M": 0.0},
                ),
                QueryArm(
                    label="direct_lo",
                    kind=QueryKind.INTERVENE,
                    values={"X": -1.0, "M": 0.0},
                ),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.CONTRAST_DIFF),
            assertion=Assertion(kind=AssertionKind.NEAR_ZERO, tolerance=0.15),
        )
        verdict = verify_atom(spec, world, solver, n_mc=20_000, seed=42)
        assert verdict.solver_assertion_holds is True, (
            f"No mediation path, indirect should be ~0, got {verdict.ground_truth}"
        )

    def test_identifiability_with_confounders(self):
        """Identifiability: C -> A -> Y, C -> Y. C is valid backdoor set."""
        world = _confounder_world()
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="ident_valid",
            arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
            measurement=Measurement(
                kind=MeasurementKind.IDENTIFIABILITY_CHECK,
                treatment="A",
                outcome="Y",
                candidate_adjust_set=("C",),
            ),
            comparison=Comparison(kind=ComparisonKind.IDENTITY),
            assertion=Assertion(kind=AssertionKind.IDENTIFIABLE),
        )
        verdict = verify_atom(spec, world, solver, n_mc=1000, seed=42)
        assert verdict.solver_assertion_holds is True

    def test_identifiability_no_parents_always_true(self):
        """Root treatment with no confounders is always identifiable."""
        world = _simple_world()  # A (root) -> Y
        solver = SCMSolver(world)
        spec = AtomicSpec(
            spec_id="ident_root",
            arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
            measurement=Measurement(
                kind=MeasurementKind.IDENTIFIABILITY_CHECK,
                treatment="A",
                outcome="Y",
            ),
            comparison=Comparison(kind=ComparisonKind.IDENTITY),
            assertion=Assertion(kind=AssertionKind.IDENTIFIABLE),
        )
        verdict = verify_atom(spec, world, solver, n_mc=1000, seed=42)
        assert verdict.solver_assertion_holds is True

    def test_identifiability_latent_confounder_rejects(self):
        """Latent confounder in candidate set must be rejected."""
        # U -> A -> Y, U -> Y. U is latent.
        world = SCMWorld(
            id="test-latent",
            graph={"U": [], "A": ["U"], "Y": ["A", "U"]},
            equations={
                "U": lambda p, rng: rng.normal(0, 1),
                "A": lambda p, rng: p["U"] + rng.normal(0, 0.5),
                "Y": lambda p, rng: 0.5 * p["A"] + 0.3 * p["U"] + rng.normal(0, 0.3),
            },
            latent_variables={"U"},
        )
        solver = SCMSolver(world)
        # Candidate set includes U which is NOT observable -> must reject
        spec = AtomicSpec(
            spec_id="ident_latent",
            arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
            measurement=Measurement(
                kind=MeasurementKind.IDENTIFIABILITY_CHECK,
                treatment="A",
                outcome="Y",
                candidate_adjust_set=("U",),
            ),
            comparison=Comparison(kind=ComparisonKind.IDENTITY),
            assertion=Assertion(kind=AssertionKind.IDENTIFIABLE),
        )
        verdict = verify_atom(spec, world, solver, n_mc=1000, seed=42)
        # Should NOT hold — U is unobserved, can't be used as adjustment set
        assert verdict.solver_assertion_holds is False

    def test_assertion_with_proportion(self):
        """GREATER_THAN assertion should work with PROPORTION comparison."""
        world = _simple_world()
        solver = SCMSolver(world)
        # PROPORTION computes vals[1]/vals[0] = mean(lo)/mean(hi)
        # With A=2.0 -> Y~1.6, A=0.5 -> Y~0.4. Proportion ~0.25.
        # Check that _extract_scalar reads "proportion" key correctly.
        spec = AtomicSpec(
            spec_id="prop_gt",
            arms=(
                QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"A": 2.0}),
                QueryArm(label="lo", kind=QueryKind.INTERVENE, values={"A": 0.5}),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.PROPORTION),
            assertion=Assertion(kind=AssertionKind.GREATER_THAN, threshold=0.1),
        )
        verdict = verify_atom(spec, world, solver, n_mc=20_000, seed=42)
        assert verdict.solver_assertion_holds is True

    def test_assertion_with_ratio(self):
        """GREATER_THAN assertion should work with RATIO comparison."""
        world = _simple_world()
        solver = SCMSolver(world)
        # Ratio of mean(Y|do(A=2)) / mean(Y|do(A=-2)) should be > 1
        spec = AtomicSpec(
            spec_id="ratio_gt",
            arms=(
                QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"A": 2.0}),
                QueryArm(label="lo", kind=QueryKind.INTERVENE, values={"A": -2.0}),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.RATIO),
            assertion=Assertion(kind=AssertionKind.LESS_THAN, threshold=0.0),
        )
        verdict = verify_atom(spec, world, solver, n_mc=20_000, seed=42)
        # hi is positive mean, lo is negative mean -> ratio is negative -> < 0
        assert verdict.solver_assertion_holds is True


# ---------------------------------------------------------------------------
# _find_backdoor_set — empty-set edge case (task #46, follow-up to #45)
# ---------------------------------------------------------------------------


class TestFindBackdoorSet:
    def test_root_treatment_returns_empty_set(self):
        """A (root) -> Y: treatment has no parents, empty set is trivially valid."""
        world = _simple_world()  # A -> Y
        result = _find_backdoor_set(world, "A", "Y")
        assert result == ()

    def test_latent_parent_no_backdoor_path_returns_empty_set(self):
        """U -> T -> Y, U is latent, no path from U to Y except through T.
        Empty set is valid because no backdoor path exists. Before the fix,
        _find_backdoor_set returned None here because T has parents.
        """
        world = SCMWorld(
            id="test-latent-no-backdoor",
            graph={"U": [], "T": ["U"], "Y": ["T"]},
            equations={
                "U": lambda p, rng: rng.normal(0, 1),
                "T": lambda p, rng: p["U"] + rng.normal(0, 0.5),
                "Y": lambda p, rng: 0.8 * p["T"] + rng.normal(0, 0.3),
            },
            latent_variables={"U"},
        )
        result = _find_backdoor_set(world, "T", "Y")
        assert result is not None, (
            "_find_backdoor_set returned None but empty set is valid "
            "(no backdoor path from U to Y bypassing T)"
        )
        assert result == ()

    def test_latent_confounder_with_backdoor_path_returns_none(self):
        """U -> T, U -> Y, U is latent. Backdoor path exists via U but
        U is not observable. No valid backdoor set -> must return None.
        """
        world = SCMWorld(
            id="test-latent-confounder",
            graph={"U": [], "T": ["U"], "Y": ["T", "U"]},
            equations={
                "U": lambda p, rng: rng.normal(0, 1),
                "T": lambda p, rng: p["U"] + rng.normal(0, 0.5),
                "Y": lambda p, rng: 0.5 * p["T"] + 0.3 * p["U"] + rng.normal(0, 0.3),
            },
            latent_variables={"U"},
        )
        result = _find_backdoor_set(world, "T", "Y")
        assert result is None, (
            "Latent confounder U opens backdoor path T<-U->Y, "
            "no observable variable can block it"
        )

    def test_observable_parent_no_backdoor_returns_parents(self):
        """C -> A -> Y, C -> Y. C is observable confounder.
        Parents of A = {C}, which is a valid backdoor set.
        """
        world = _confounder_world()  # C -> A -> Y, C -> Y
        result = _find_backdoor_set(world, "A", "Y")
        assert result is not None
        assert "C" in result


class TestScoring:
    def _make_family(self, n_atoms: int = 2, n_material: int = 2) -> SalienceFamily:
        specs = []
        for i in range(n_atoms):
            specs.append(
                FamilyAtom(
                    atom_id=f"a{i}",
                    spec=AtomicSpec(
                        spec_id=f"s{i}",
                        arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
                        measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                        comparison=Comparison(kind=ComparisonKind.IDENTITY),
                        assertion=Assertion(kind=AssertionKind.POSITIVE),
                    ),
                    weight=1.0,
                    material=i < n_material,
                )
            )
        return SalienceFamily(
            family_id="f1",
            key=FamilyKey(
                brief_target="Y",
                focus_signature=("X", "Y"),
                pattern_class="causal_effect",
            ),
            atoms=tuple(specs),
            salience=0.8,
        )

    def test_fully_true(self):
        """All atoms correct, all material covered."""
        family = self._make_family(n_atoms=2, n_material=2)
        scores = {"a0": 1.0, "a1": 1.0}
        score, verdict = score_claim_against_family(scores, family)
        assert verdict == "fully_true"
        assert score == 1.0

    def test_partially_true_with_omission(self):
        """One atom correct, one material atom omitted."""
        family = self._make_family(n_atoms=2, n_material=2)
        scores = {"a0": 1.0}  # a1 omitted but material
        score, verdict = score_claim_against_family(scores, family)
        assert verdict == "partially_true_with_omission"
        assert 0.0 < score < 1.0

    def test_false_claim(self):
        """All atoms wrong."""
        family = self._make_family(n_atoms=2, n_material=2)
        scores = {"a0": 0.0, "a1": 0.0}
        score, verdict = score_claim_against_family(scores, family)
        assert verdict == "false"
        assert score == 0.0

    def test_unmatched(self):
        """No atoms match."""
        family = self._make_family(n_atoms=2, n_material=2)
        scores = {"a99": 1.0}  # doesn't exist in family
        score, verdict = score_claim_against_family(scores, family)
        assert verdict == "unmatched"
        assert score == 0.0

    def test_specificity_bonus(self):
        """More atoms covered → higher score."""
        family = self._make_family(n_atoms=3, n_material=1)
        score_1, _ = score_claim_against_family({"a0": 1.0}, family)
        score_2, _ = score_claim_against_family({"a0": 1.0, "a1": 1.0}, family)
        score_3, _ = score_claim_against_family({"a0": 1.0, "a1": 1.0, "a2": 1.0}, family)
        assert score_1 < score_2 < score_3

    def test_episode_scoring(self):
        """Episode-level scoring with precision gate."""
        families = [self._make_family()]
        # Good solver: 1 claim matching family with high score
        ep = score_episode([("f1", 0.9)], families, n_claims=1)
        assert ep.correctness == 0.9
        assert ep.coverage > 0  # family hit
        assert ep.total > 0

    def test_precision_gate(self):
        """Low precision should zero out coverage."""
        families = [self._make_family()]
        ep = score_episode([("f1", 0.3)], families, n_claims=1)
        assert ep.correctness == 0.3
        assert ep.precision_gate_active is True
        assert ep.coverage == 0.0

    def test_efficiency_penalty(self):
        """Submitting over budget reduces efficiency."""
        families = [self._make_family()]
        ep = score_episode([("f1", 0.9)], families, n_claims=7, claim_budget=5)
        assert ep.efficiency < 1.0


# ---------------------------------------------------------------------------
# _filter_condition tests (P1 condition predicates)
# ---------------------------------------------------------------------------


class TestFilterCondition:
    """Tests for _filter_condition predicate dispatch (P1).

    Coverage:
    - 4 predicates: ApproxEq, ConditionRange, QuantileRange, InSet
    - Edge cases: NaN, ties, degenerate ranges, inclusive bounds
    - Conjunction (AND across columns)
    - Backward compat: legacy raw scalar / string predicates
    - Known-debt: missing column silent skip, non-numeric ApproxEq crash
      (see TODO P1.5: missing-column robustness + non-numeric guards)
    """

    # --- ApproxEq -----------------------------------------------------------

    def test_approx_eq_basic(self):
        """ApproxEq filters rows within tol_std * std of value."""
        df = pd.DataFrame({"x": [10.0, 10.5, 11.0, 20.0, 30.0]})
        result = _filter_condition(df, {"x": ApproxEq(value=10.5, tol_std=0.15)})
        # std ~= 8.65, tol ~= 1.30, so {10.0, 10.5, 11.0} match
        assert set(result["x"].tolist()) == {10.0, 10.5, 11.0}

    def test_approx_eq_non_numeric_known_debt(self):
        """ApproxEq on a non-numeric column raises (KNOWN DEBT, P1.5).

        _filter_condition does not guard against non-numeric columns
        for ApproxEq. Today this crashes with a TypeError. P1.5 should
        replace this with an explicit, informative error.
        """
        df = pd.DataFrame({"region": ["urban", "rural", "suburban"]})
        with pytest.raises(Exception):
            _filter_condition(df, {"region": ApproxEq(value=1.0)})

    # --- ConditionRange -----------------------------------------------------

    def test_range_basic_inclusive_bounds(self):
        """Range filters with inclusive lo and hi (lo <= x <= hi)."""
        df = pd.DataFrame({"x": [0, 5, 10, 15, 20]})
        result = _filter_condition(df, {"x": ConditionRange(lo=5, hi=15)})
        assert set(result["x"].tolist()) == {5, 10, 15}

    def test_range_degenerate_lo_eq_hi(self):
        """Range with lo == hi matches only that exact value."""
        df = pd.DataFrame({"x": [4.99, 5.0, 5.0, 5.01, 6.0]})
        result = _filter_condition(df, {"x": ConditionRange(lo=5.0, hi=5.0)})
        assert len(result) == 2
        assert (result["x"] == 5.0).all()

    # --- QuantileRange ------------------------------------------------------

    def test_quantile_range_basic(self):
        """QuantileRange selects rows in the given quantile range."""
        df = pd.DataFrame({"x": list(range(100))})  # 0..99
        result = _filter_condition(
            df, {"x": QuantileRange(q_lo=0.0, q_hi=0.25)}
        )
        # Bottom quartile: q[0]=0, q[0.25]~=24.75 -> rows with x in [0, 24]
        assert result["x"].min() == 0
        assert result["x"].max() <= 25

    def test_quantile_range_with_nan(self):
        """NaN values are excluded by the quantile filter mask."""
        df = pd.DataFrame({"x": [1.0, 2.0, np.nan, 4.0, 5.0, np.nan, 7.0]})
        result = _filter_condition(
            df, {"x": QuantileRange(q_lo=0.0, q_hi=0.5)}
        )
        # quantile() ignores NaN; df[var] >= lo on NaN row returns False,
        # so NaN rows are excluded from the result.
        assert not result["x"].isna().any()

    def test_quantile_range_ties(self):
        """Repeated values are not lost when within quantile bounds."""
        df = pd.DataFrame({"x": [1, 1, 1, 1, 1, 5, 5, 5, 5, 5]})
        result = _filter_condition(
            df, {"x": QuantileRange(q_lo=0.0, q_hi=0.5)}
        )
        # q[0]=1, q[0.5]=3 -> all five 1s should match
        assert (result["x"] == 1).sum() == 5

    # --- InSet --------------------------------------------------------------

    def test_in_set_string_categorical(self):
        """InSet filters rows where column value is in the listed set."""
        df = pd.DataFrame(
            {"region": ["urban", "rural", "suburban", "urban", "rural"]}
        )
        result = _filter_condition(
            df, {"region": InSet(values=["urban", "suburban"])}
        )
        assert set(result["region"].tolist()) == {"urban", "suburban"}
        assert len(result) == 3

    def test_in_set_numeric(self):
        """InSet works with numeric values."""
        df = pd.DataFrame({"treatment": [0, 1, 2, 0, 1, 2, 0]})
        result = _filter_condition(df, {"treatment": InSet(values=[1, 2])})
        assert set(result["treatment"].tolist()) == {1, 2}
        assert len(result) == 4

    def test_in_set_bool(self):
        """InSet works with boolean values."""
        df = pd.DataFrame({"active": [True, False, True, True, False]})
        result = _filter_condition(df, {"active": InSet(values=[True])})
        assert result["active"].all()
        assert len(result) == 3

    # --- Conjunction --------------------------------------------------------

    def test_conjunction_and(self):
        """Multiple predicates conjoin with AND across different columns."""
        df = pd.DataFrame({
            "x": [1, 2, 3, 4, 5],
            "region": ["a", "b", "a", "b", "a"],
        })
        result = _filter_condition(df, {
            "x": ConditionRange(lo=2, hi=4),
            "region": InSet(values=["a"]),
        })
        # x in [2, 4] AND region == "a" -> only x=3
        assert len(result) == 1
        assert result.iloc[0]["x"] == 3

    # --- Missing column (KNOWN DEBT) ----------------------------------------

    def test_missing_column_silent_skip_known_debt(self):
        """Missing column is silently skipped (KNOWN DEBT, P1.5).

        If the LLM hallucinates a column, _filter_condition currently
        ignores the predicate and returns rows that match the OTHER
        predicates (or all rows if it was the only predicate).

        This is dangerous because it silently changes the question. P1.5
        will replace this with a loud failure (raise / empty DataFrame).
        Locking the contract here only until that fix lands.
        """
        df = pd.DataFrame({
            "x": [1, 2, 3, 4, 5],
            "region": ["a", "b", "a", "b", "a"],
        })
        # Predicate on missing column "fake" is silently dropped;
        # only the region predicate is applied.
        result = _filter_condition(df, {
            "fake": InSet(values=["impossible"]),
            "region": InSet(values=["a"]),
        })
        assert len(result) == 3
        assert (result["region"] == "a").all()

    # --- Backward compat (legacy shorthand) ---------------------------------

    def test_legacy_raw_scalar_backward_compat(self):
        """A raw int/float predicate (legacy shorthand) is treated as approx-equal."""
        df = pd.DataFrame({"x": [10.0, 10.5, 11.0, 20.0, 30.0]})
        result = _filter_condition(df, {"x": 10.5})
        assert 10.5 in result["x"].tolist()
        assert 30.0 not in result["x"].tolist()

    def test_legacy_raw_string_backward_compat(self):
        """A raw string predicate (legacy shorthand) is treated as exact-match."""
        df = pd.DataFrame(
            {"region": ["urban", "rural", "urban", "suburban"]}
        )
        result = _filter_condition(df, {"region": "urban"})
        assert (result["region"] == "urban").all()
        assert len(result) == 2
