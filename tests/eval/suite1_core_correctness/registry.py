"""Suite 1 Core Correctness — Registry of eval cases.

Each EvalCase is a tuple of (spec, world, expected_holds) with metadata
for coverage tracking. Every active QueryKind, MeasurementKind,
ComparisonKind, and AssertionKind value appears at least once.

Ground truth values are derived analytically from the world equations
documented in worlds.py — NOT from running the verifier.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sreg.models.open_investigation import (
    Assertion,
    AssertionKind,
    AtomicSpec,
    Comparison,
    ComparisonKind,
    ConditionRange,
    Measurement,
    MeasurementKind,
    QueryArm,
    QueryKind,
)


@dataclass(frozen=True)
class EvalCase:
    """A single eval case: spec + world + expected outcome."""

    case_id: str
    world_name: str
    spec: AtomicSpec
    expected_holds: bool
    description: str
    tags: frozenset[str] = field(default_factory=frozenset)
    expected_value: float | None = None
    mc_tolerance: float = 0.05


# ---------------------------------------------------------------------------
# Helper constants
# ---------------------------------------------------------------------------

N_MC = 50_000
SEED = 42


# ---------------------------------------------------------------------------
# Cases on LINEAR CHAIN world  (A -> B -> C)
# ---------------------------------------------------------------------------


def _linear_chain_cases() -> list[EvalCase]:
    return [
        # 1. Basic ATE: do(A=1) vs do(A=-1) on C. Expected diff = 0.8
        EvalCase(
            case_id="lc_ate_positive",
            world_name="linear_chain",
            spec=AtomicSpec(
                spec_id="lc_ate_positive",
                arms=(
                    QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"A": 1.0}),
                    QueryArm(label="lo", kind=QueryKind.INTERVENE, values={"A": -1.0}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="C"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
            expected_holds=True,
            description="ATE of A on C through chain is positive (0.8)",
            tags=frozenset({"INTERVENE", "MEAN", "DIFFERENCE", "POSITIVE"}),
            expected_value=0.8,
        ),
        # 2. Reverse: assert NEGATIVE on same ATE (should fail — it's positive)
        EvalCase(
            case_id="lc_ate_not_negative",
            world_name="linear_chain",
            spec=AtomicSpec(
                spec_id="lc_ate_not_negative",
                arms=(
                    QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"A": 1.0}),
                    QueryArm(label="lo", kind=QueryKind.INTERVENE, values={"A": -1.0}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="C"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
                assertion=Assertion(kind=AssertionKind.NEGATIVE),
            ),
            expected_holds=False,
            description="ATE is +0.8, asserting NEGATIVE should fail",
            tags=frozenset({"NEGATIVE"}),
            expected_value=0.8,
        ),
        # 3. No direct A->C: fix B, ATE should be ~0
        #    do(A=1, B=0) vs do(A=-1, B=0) → E[C] = 0.8*0 = 0 for both
        EvalCase(
            case_id="lc_no_direct_near_zero",
            world_name="linear_chain",
            spec=AtomicSpec(
                spec_id="lc_no_direct_near_zero",
                arms=(
                    QueryArm(
                        label="hi",
                        kind=QueryKind.INTERVENE,
                        values={"A": 1.0, "B": 0.0},
                    ),
                    QueryArm(
                        label="lo",
                        kind=QueryKind.INTERVENE,
                        values={"A": -1.0, "B": 0.0},
                    ),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="C"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
                assertion=Assertion(kind=AssertionKind.NEAR_ZERO, tolerance=0.1),
            ),
            expected_holds=True,
            description="With B fixed, A has no direct effect on C (near zero)",
            tags=frozenset({"NEAR_ZERO"}),
            expected_value=0.0,
        ),
        # 4. Variance of C under baseline > 0.2
        #    Var[C|baseline] = 0.8^2 * (0.25 + 0.09) + 0.04 ≈ 0.258
        EvalCase(
            case_id="lc_variance_baseline",
            world_name="linear_chain",
            spec=AtomicSpec(
                spec_id="lc_variance_baseline",
                arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
                measurement=Measurement(kind=MeasurementKind.VARIANCE, target="C"),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.GREATER_THAN, threshold=0.2),
            ),
            expected_holds=True,
            description="Variance of C under baseline > 0.2 (analytical ≈ 0.258)",
            tags=frozenset({"BASELINE", "VARIANCE", "IDENTITY", "GREATER_THAN"}),
            expected_value=0.258,
            mc_tolerance=0.02,
        ),
        # 5. Quantile: median of C under do(A=1) ≈ 0.4
        EvalCase(
            case_id="lc_quantile_median",
            world_name="linear_chain",
            spec=AtomicSpec(
                spec_id="lc_quantile_median",
                arms=(
                    QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"A": 1.0}),
                ),
                measurement=Measurement(
                    kind=MeasurementKind.QUANTILE, target="C", q=0.5
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.GREATER_THAN, threshold=0.3),
            ),
            expected_holds=True,
            description="Median of C under do(A=1) > 0.3 (analytical ≈ 0.4)",
            tags=frozenset({"QUANTILE"}),
            expected_value=0.4,
        ),
        # 6. Tail prob: P(C > 0.5 | do(A=1)) > P(C > 0.5 | do(A=-1))
        EvalCase(
            case_id="lc_tail_prob",
            world_name="linear_chain",
            spec=AtomicSpec(
                spec_id="lc_tail_prob",
                arms=(
                    QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"A": 1.0}),
                    QueryArm(
                        label="lo", kind=QueryKind.INTERVENE, values={"A": -1.0}
                    ),
                ),
                measurement=Measurement(
                    kind=MeasurementKind.TAIL_PROB, target="C", threshold=0.5
                ),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
            expected_holds=True,
            description="Tail P(C>0.5) higher under do(A=1) than do(A=-1)",
            tags=frozenset({"TAIL_PROB"}),
        ),
        # 7. Ratio: E[B|do(A=2)] / E[B|do(A=1)] = 1.0 / 0.5 = 2.0
        EvalCase(
            case_id="lc_ratio",
            world_name="linear_chain",
            spec=AtomicSpec(
                spec_id="lc_ratio",
                arms=(
                    QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"A": 2.0}),
                    QueryArm(label="lo", kind=QueryKind.INTERVENE, values={"A": 1.0}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="B"),
                comparison=Comparison(kind=ComparisonKind.RATIO, ref_arm="lo"),
                assertion=Assertion(kind=AssertionKind.GREATER_THAN, threshold=1.5),
            ),
            expected_holds=True,
            description="Ratio of E[B] under do(A=2)/do(A=1) ≈ 2.0 > 1.5",
            tags=frozenset({"RATIO"}),
            expected_value=2.0,
        ),
        # 8. Observational conditioning (A is root, so obs ≈ causal)
        EvalCase(
            case_id="lc_observe",
            world_name="linear_chain",
            spec=AtomicSpec(
                spec_id="lc_observe",
                arms=(
                    QueryArm(label="hi", kind=QueryKind.OBSERVE, values={"A": 1.0}),
                    QueryArm(label="lo", kind=QueryKind.OBSERVE, values={"A": -1.0}),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="C"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
            expected_holds=True,
            description="Observational: E[C|A≈1] - E[C|A≈-1] > 0 (A is root)",
            tags=frozenset({"OBSERVE"}),
        ),
    ]


# ---------------------------------------------------------------------------
# Cases on CONFOUNDER world  (Z -> A, Z -> Y, A -> Y)
# ---------------------------------------------------------------------------


def _confounder_cases() -> list[EvalCase]:
    return [
        # 9. Backdoor adjustment: true ATE(A->Y) = 0.6
        EvalCase(
            case_id="conf_adjust_ate",
            world_name="confounder",
            spec=AtomicSpec(
                spec_id="conf_adjust_ate",
                arms=(
                    QueryArm(
                        label="hi",
                        kind=QueryKind.ADJUST,
                        treatment="A",
                        outcome="Y",
                        values={"A": 1.0},
                    ),
                    QueryArm(
                        label="lo",
                        kind=QueryKind.ADJUST,
                        treatment="A",
                        outcome="Y",
                        values={"A": -1.0},
                    ),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
            expected_holds=True,
            description="Adjusted ATE(A->Y) = 0.6 (positive, deconfounded)",
            tags=frozenset({"ADJUST"}),
            expected_value=0.6,
        ),
        # 10. Condition on Z range: E[Y|Z>0.5] > E[Y|Z<-0.5]
        EvalCase(
            case_id="conf_condition_z",
            world_name="confounder",
            spec=AtomicSpec(
                spec_id="conf_condition_z",
                arms=(
                    QueryArm(
                        label="z_hi",
                        kind=QueryKind.CONDITION,
                        condition_on={"Z": ConditionRange(lo=0.5, hi=3.0)},
                    ),
                    QueryArm(
                        label="z_lo",
                        kind=QueryKind.CONDITION,
                        condition_on={"Z": ConditionRange(lo=-3.0, hi=-0.5)},
                    ),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="z_lo"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
            expected_holds=True,
            description="E[Y|Z high] > E[Y|Z low] (Z has 0.7 direct effect on Y)",
            tags=frozenset({"CONDITION"}),
        ),
        # 11. Correlation(A, Y | baseline) > 0
        EvalCase(
            case_id="conf_correlation",
            world_name="confounder",
            spec=AtomicSpec(
                spec_id="conf_correlation",
                arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
                measurement=Measurement(
                    kind=MeasurementKind.CORRELATION, lhs="A", rhs="Y"
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
            expected_holds=True,
            description="Corr(A,Y) > 0 (direct + confounded, both positive)",
            tags=frozenset({"CORRELATION"}),
        ),
        # 12. Partial corr(A, Y | Z) > 0 (direct effect remains)
        EvalCase(
            case_id="conf_partial_correlation",
            world_name="confounder",
            spec=AtomicSpec(
                spec_id="conf_partial_correlation",
                arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
                measurement=Measurement(
                    kind=MeasurementKind.PARTIAL_CORRELATION,
                    lhs="A",
                    rhs="Y",
                    cond_set=("Z",),
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
            expected_holds=True,
            description="Partial corr(A,Y|Z) > 0 (direct effect A->Y = 0.3)",
            tags=frozenset({"PARTIAL_CORRELATION"}),
        ),
        # 13. Identifiability: A->Y identifiable with Z as backdoor
        EvalCase(
            case_id="conf_identifiable",
            world_name="confounder",
            spec=AtomicSpec(
                spec_id="conf_identifiable",
                arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
                measurement=Measurement(
                    kind=MeasurementKind.IDENTIFIABILITY_CHECK,
                    treatment="A",
                    outcome="Y",
                    candidate_adjust_set=("Z",),
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.IDENTIFIABLE),
            ),
            expected_holds=True,
            description="A->Y identifiable: Z is valid backdoor set",
            tags=frozenset({"IDENTIFIABILITY_CHECK", "IDENTIFIABLE"}),
        ),
        # 14. Distinguishable: A->Y identifiable (auto-detect) → True
        EvalCase(
            case_id="conf_distinguishable",
            world_name="confounder",
            spec=AtomicSpec(
                spec_id="conf_distinguishable",
                arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
                measurement=Measurement(
                    kind=MeasurementKind.IDENTIFIABILITY_CHECK,
                    treatment="A",
                    outcome="Y",
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.DISTINGUISHABLE),
            ),
            expected_holds=True,
            description="A->Y effect is distinguishable (identifiable via Z)",
            tags=frozenset({"DISTINGUISHABLE"}),
        ),
    ]


# ---------------------------------------------------------------------------
# Cases on LATENT CONFOUNDER world  (U -> A, U -> Y; U latent)
# ---------------------------------------------------------------------------


def _latent_cases() -> list[EvalCase]:
    return [
        # 15. NOT identifiable: U is latent, no valid backdoor set
        EvalCase(
            case_id="lat_not_identifiable",
            world_name="latent_confounder",
            spec=AtomicSpec(
                spec_id="lat_not_identifiable",
                arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
                measurement=Measurement(
                    kind=MeasurementKind.IDENTIFIABILITY_CHECK,
                    treatment="A",
                    outcome="Y",
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.NOT_IDENTIFIABLE),
            ),
            expected_holds=True,
            description="A->Y NOT identifiable (U is latent confounder)",
            tags=frozenset({"NOT_IDENTIFIABLE"}),
        ),
        # 16. NOT distinguishable (same identifiability check, same outcome)
        EvalCase(
            case_id="lat_not_distinguishable",
            world_name="latent_confounder",
            spec=AtomicSpec(
                spec_id="lat_not_distinguishable",
                arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
                measurement=Measurement(
                    kind=MeasurementKind.IDENTIFIABILITY_CHECK,
                    treatment="A",
                    outcome="Y",
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.NOT_DISTINGUISHABLE),
            ),
            expected_holds=True,
            description="A->Y not distinguishable (latent confounder blocks identification)",
            tags=frozenset({"NOT_DISTINGUISHABLE"}),
        ),
    ]


# ---------------------------------------------------------------------------
# Cases on THRESHOLD world  (A -> Y with changepoint at A=0.5)
# ---------------------------------------------------------------------------


def _threshold_cases() -> list[EvalCase]:
    return [
        # 17. Sweep + changepoint detection
        EvalCase(
            case_id="th_sweep_changepoint",
            world_name="threshold",
            spec=AtomicSpec(
                spec_id="th_sweep_changepoint",
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
            ),
            expected_holds=True,
            description="Changepoint detected at A≈0.5 in threshold world",
            tags=frozenset({"SWEEP", "PIECEWISE_FIT", "CHANGEPOINT_EXISTS"}),
        ),
    ]


# ---------------------------------------------------------------------------
# Cases on INDEPENDENCE world  (A ⊥ Y)
# ---------------------------------------------------------------------------


def _independence_cases() -> list[EvalCase]:
    return [
        # 18. ATE is near zero
        EvalCase(
            case_id="ind_near_zero_ate",
            world_name="independence",
            spec=AtomicSpec(
                spec_id="ind_near_zero_ate",
                arms=(
                    QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"A": 1.0}),
                    QueryArm(
                        label="lo", kind=QueryKind.INTERVENE, values={"A": -1.0}
                    ),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
                assertion=Assertion(kind=AssertionKind.NEAR_ZERO, tolerance=0.1),
            ),
            expected_holds=True,
            description="ATE(A->Y) = 0 (independent variables)",
            tags=frozenset(),
            expected_value=0.0,
        ),
        # 19. Correlation ≈ 0
        EvalCase(
            case_id="ind_correlation_zero",
            world_name="independence",
            spec=AtomicSpec(
                spec_id="ind_correlation_zero",
                arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
                measurement=Measurement(
                    kind=MeasurementKind.CORRELATION, lhs="A", rhs="Y"
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.NEAR_ZERO, tolerance=0.05),
            ),
            expected_holds=True,
            description="Corr(A,Y) ≈ 0 (independent)",
            tags=frozenset(),
        ),
        # 20. Assert POSITIVE on zero ATE should FAIL
        EvalCase(
            case_id="ind_false_positive",
            world_name="independence",
            spec=AtomicSpec(
                spec_id="ind_false_positive",
                arms=(
                    QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"A": 1.0}),
                    QueryArm(
                        label="lo", kind=QueryKind.INTERVENE, values={"A": -1.0}
                    ),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            ),
            expected_holds=False,
            description="Assert POSITIVE on zero ATE should fail (no effect)",
            tags=frozenset(),
        ),
        # 21. Baseline mean of Y ≈ 3.0 → LESS_THAN(4.0) holds
        EvalCase(
            case_id="ind_baseline_lt",
            world_name="independence",
            spec=AtomicSpec(
                spec_id="ind_baseline_lt",
                arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.LESS_THAN, threshold=4.0),
            ),
            expected_holds=True,
            description="E[Y|baseline] ≈ 3.0 < 4.0",
            tags=frozenset({"LESS_THAN"}),
            expected_value=3.0,
        ),
    ]


# ---------------------------------------------------------------------------
# Cases on MEDIATION world  (X -> M -> Y, X -> Y)
# ---------------------------------------------------------------------------


def _mediation_cases() -> list[EvalCase]:
    # m_ref = E[M | do(X=-1)] = 0.7 * (-1) = -0.7
    m_ref = -0.7

    return [
        # 22. Ranking: 3 dose levels of X, ranked by E[Y]
        #     E[Y|do(X=1)]=0.72, E[Y|do(X=0)]=0, E[Y|do(X=-1)]=-0.72
        EvalCase(
            case_id="med_ranking",
            world_name="mediation",
            spec=AtomicSpec(
                spec_id="med_ranking",
                arms=(
                    QueryArm(
                        label="hi", kind=QueryKind.INTERVENE, values={"X": 1.0}
                    ),
                    QueryArm(
                        label="mid", kind=QueryKind.INTERVENE, values={"X": 0.0}
                    ),
                    QueryArm(
                        label="lo", kind=QueryKind.INTERVENE, values={"X": -1.0}
                    ),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.RANKING),
                assertion=Assertion(
                    kind=AssertionKind.RANK_ORDER, order=("hi", "mid", "lo")
                ),
            ),
            expected_holds=True,
            description="Rank order hi > mid > lo by E[Y] under 3 dose levels",
            tags=frozenset({"RANKING", "RANK_ORDER"}),
        ),
        # 23. GAP between X=1 and X=-1: abs(0.72 - (-0.72)) = 1.44
        EvalCase(
            case_id="med_gap",
            world_name="mediation",
            spec=AtomicSpec(
                spec_id="med_gap",
                arms=(
                    QueryArm(
                        label="hi", kind=QueryKind.INTERVENE, values={"X": 1.0}
                    ),
                    QueryArm(
                        label="lo", kind=QueryKind.INTERVENE, values={"X": -1.0}
                    ),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.GAP),
                assertion=Assertion(kind=AssertionKind.GAP_MATERIAL),
            ),
            expected_holds=True,
            description="Gap |E[Y|do(X=1)] - E[Y|do(X=-1)]| ≈ 1.44 > 0.1",
            tags=frozenset({"GAP", "GAP_MATERIAL"}),
            expected_value=1.44,
        ),
        # 24. Proportion: E[Y|do(X=-1)] / E[Y|do(X=1)] ≈ -1.0
        EvalCase(
            case_id="med_proportion",
            world_name="mediation",
            spec=AtomicSpec(
                spec_id="med_proportion",
                arms=(
                    QueryArm(
                        label="hi", kind=QueryKind.INTERVENE, values={"X": 1.0}
                    ),
                    QueryArm(
                        label="lo", kind=QueryKind.INTERVENE, values={"X": -1.0}
                    ),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.PROPORTION),
                assertion=Assertion(kind=AssertionKind.LESS_THAN, threshold=0.0),
            ),
            expected_holds=True,
            description="Proportion E[Y|do(-1)]/E[Y|do(1)] ≈ -1.0 < 0",
            tags=frozenset({"PROPORTION"}),
            expected_value=-1.0,
        ),
        # 25. Contrast-diff: indirect effect = total - direct ≈ 0.84
        #     4 arms: total_hi, total_lo, direct_hi (M fixed), direct_lo (M fixed)
        #     m_ref = E[M|do(X=-1)] = -0.7
        EvalCase(
            case_id="med_contrast_diff",
            world_name="mediation",
            spec=AtomicSpec(
                spec_id="med_contrast_diff",
                arms=(
                    QueryArm(
                        label="total_hi",
                        kind=QueryKind.INTERVENE,
                        values={"X": 1.0},
                    ),
                    QueryArm(
                        label="total_lo",
                        kind=QueryKind.INTERVENE,
                        values={"X": -1.0},
                    ),
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
            ),
            expected_holds=True,
            description="Indirect effect via contrast-diff ≈ 0.84 (positive)",
            tags=frozenset({"CONTRAST_DIFF"}),
            expected_value=0.84,
        ),
        # 26. Sign flip: same contrast-diff, checked as SIGN_FLIP (|cd| > tol)
        EvalCase(
            case_id="med_sign_flip",
            world_name="mediation",
            spec=AtomicSpec(
                spec_id="med_sign_flip",
                arms=(
                    QueryArm(
                        label="total_hi",
                        kind=QueryKind.INTERVENE,
                        values={"X": 1.0},
                    ),
                    QueryArm(
                        label="total_lo",
                        kind=QueryKind.INTERVENE,
                        values={"X": -1.0},
                    ),
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
                assertion=Assertion(kind=AssertionKind.SIGN_FLIP, tolerance=0.05),
            ),
            expected_holds=True,
            description="Indirect effect is material (|contrast_diff| > 0.05)",
            tags=frozenset({"SIGN_FLIP"}),
        ),
    ]


# ---------------------------------------------------------------------------
# Full registry
# ---------------------------------------------------------------------------


def build_registry() -> list[EvalCase]:
    """Build the complete eval case registry."""
    cases: list[EvalCase] = []
    cases.extend(_linear_chain_cases())
    cases.extend(_confounder_cases())
    cases.extend(_latent_cases())
    cases.extend(_threshold_cases())
    cases.extend(_independence_cases())
    cases.extend(_mediation_cases())
    return cases


# Pre-built for import convenience
REGISTRY: list[EvalCase] = build_registry()


# ---------------------------------------------------------------------------
# Enum coverage summary
# ---------------------------------------------------------------------------

# Expected coverage (active enums only — PROB and DISTRIBUTION are skipped):
#
# QueryKind:       BASELINE(4,11,12,13,14,15,16,19)  INTERVENE(1..8,18,20..26)
#                  OBSERVE(8)  CONDITION(10)  ADJUST(9)  SWEEP(17)
#
# MeasurementKind: MEAN(most)  VARIANCE(4)  QUANTILE(5)  TAIL_PROB(6)
#                  CORRELATION(11,19)  PARTIAL_CORRELATION(12)
#                  IDENTIFIABILITY_CHECK(13,14,15,16)
#
# ComparisonKind:  IDENTITY(4,5,11,12,13,14,15,16,19,21)  DIFFERENCE(1,2,3,6,8,9,10,18,20)
#                  RATIO(7)  RANKING(22)  GAP(23)  PROPORTION(24)
#                  PIECEWISE_FIT(17)  CONTRAST_DIFF(25,26)
#
# AssertionKind:   POSITIVE(1,6,8,9,10,11,12,25)  NEGATIVE(2)  NEAR_ZERO(3,18,19)
#                  GREATER_THAN(4,5,7)  LESS_THAN(21,24)  RANK_ORDER(22)
#                  CHANGEPOINT_EXISTS(17)  SIGN_FLIP(26)  GAP_MATERIAL(23)
#                  IDENTIFIABLE(13)  NOT_IDENTIFIABLE(15)
#                  DISTINGUISHABLE(14)  NOT_DISTINGUISHABLE(16)
