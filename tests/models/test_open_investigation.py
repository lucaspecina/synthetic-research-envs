"""Tests for Open Investigation models: DSL grammar, claim cards, salience map."""

from __future__ import annotations

import pytest

from sreg.models.open_investigation import (
    EPISODE_PRECISION_GATE,
    FAMILY_HIT_THRESHOLD,
    MAX_CLAIMS,
    MAX_FAMILIES,
    OVERCLAIM_MAX,
    SPEC_BASE,
    SPEC_BONUS_MAX,
    ApproxEq,
    Assertion,
    AssertionKind,
    AtomicSpec,
    AtomVerdict,
    ClaimCard,
    ClaimSubmission,
    ClaimVerdict,
    Comparison,
    ComparisonKind,
    ConditionRange,
    EpisodeScore,
    EvidenceRef,
    FamilyAtom,
    FamilyKey,
    InSet,
    Measurement,
    MeasurementKind,
    QuantileRange,
    QueryArm,
    QueryKind,
    SalienceFamily,
    SalienceMap,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mean_contrast_spec(treatment: str, outcome: str, spec_id: str = "s1") -> AtomicSpec:
    """Minimal ATE-like spec: intervene high vs low, compare means."""
    return AtomicSpec(
        spec_id=spec_id,
        arms=(
            QueryArm(label="hi", kind=QueryKind.INTERVENE, values={treatment: 1.0}),
            QueryArm(label="lo", kind=QueryKind.INTERVENE, values={treatment: 0.0}),
        ),
        measurement=Measurement(kind=MeasurementKind.MEAN, target=outcome),
        comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
        assertion=Assertion(kind=AssertionKind.POSITIVE),
    )


def _evidence() -> list[EvidenceRef]:
    return [EvidenceRef(artifact_id="dataset_1", rationale="Regression shows significant effect")]


def _claim_card(claim_id: str = "c1", text: str = "X causes Y positively") -> ClaimCard:
    return ClaimCard(
        claim_id=claim_id,
        claim_text=text,
        focus_variables=["X", "Y"],
        confidence=0.8,
        evidence_basis=_evidence(),
    )


# ---------------------------------------------------------------------------
# QueryArm tests
# ---------------------------------------------------------------------------


class TestQueryArm:
    def test_baseline(self):
        arm = QueryArm(label="base", kind=QueryKind.BASELINE)
        assert arm.kind == QueryKind.BASELINE
        assert arm.values == {}

    def test_intervene(self):
        arm = QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"pressure": 1.0})
        assert arm.values["pressure"] == 1.0

    def test_observe(self):
        arm = QueryArm(label="obs", kind=QueryKind.OBSERVE, values={"temp": 0.5})
        assert arm.kind == QueryKind.OBSERVE

    def test_condition(self):
        arm = QueryArm(label="strat", kind=QueryKind.CONDITION, condition_on={"region": "north"})
        # String auto-promoted to InSet
        pred = arm.condition_on["region"]
        assert isinstance(pred, InSet)
        assert pred.values == ["north"]

    def test_adjust(self):
        arm = QueryArm(label="adj", kind=QueryKind.ADJUST, adjust_set=("Z1", "Z2"))
        assert arm.adjust_set == ("Z1", "Z2")

    def test_sweep(self):
        arm = QueryArm(
            label="sw",
            kind=QueryKind.SWEEP,
            sweep_var="X",
            sweep_values=(0.1, 0.3, 0.5, 0.7, 0.9),
        )
        assert len(arm.sweep_values) == 5


class TestConditionPredicates:
    """Tests for P1 condition predicates (approx_eq, range, quantile_range, in_set)."""

    # --- Auto-promotion from raw scalars ---

    def test_float_promotes_to_approx_eq(self):
        arm = QueryArm(label="a", kind=QueryKind.CONDITION, condition_on={"X": 5.0})
        pred = arm.condition_on["X"]
        assert isinstance(pred, ApproxEq)
        assert pred.value == 5.0
        assert pred.tol_std == 0.15

    def test_int_promotes_to_approx_eq(self):
        arm = QueryArm(label="a", kind=QueryKind.CONDITION, condition_on={"X": 3})
        pred = arm.condition_on["X"]
        assert isinstance(pred, ApproxEq)
        assert pred.value == 3

    def test_string_promotes_to_in_set(self):
        arm = QueryArm(label="a", kind=QueryKind.CONDITION, condition_on={"R": "urban"})
        pred = arm.condition_on["R"]
        assert isinstance(pred, InSet)
        assert pred.values == ["urban"]

    def test_bool_promotes_to_in_set(self):
        arm = QueryArm(label="a", kind=QueryKind.CONDITION, condition_on={"F": True})
        pred = arm.condition_on["F"]
        assert isinstance(pred, InSet)
        assert pred.values == [True]

    # --- Explicit predicate dicts ---

    def test_explicit_range(self):
        arm = QueryArm(
            label="a", kind=QueryKind.CONDITION,
            condition_on={"X": {"kind": "range", "lo": -1000, "hi": 1000}},
        )
        pred = arm.condition_on["X"]
        assert isinstance(pred, ConditionRange)
        assert pred.lo == -1000
        assert pred.hi == 1000

    def test_explicit_quantile_range(self):
        arm = QueryArm(
            label="a", kind=QueryKind.CONDITION,
            condition_on={"income": {"kind": "quantile_range", "q_lo": 0.0, "q_hi": 0.25}},
        )
        pred = arm.condition_on["income"]
        assert isinstance(pred, QuantileRange)
        assert pred.q_lo == 0.0
        assert pred.q_hi == 0.25

    def test_explicit_in_set(self):
        arm = QueryArm(
            label="a", kind=QueryKind.CONDITION,
            condition_on={"region": {"kind": "in_set", "values": ["urban", "suburban"]}},
        )
        pred = arm.condition_on["region"]
        assert isinstance(pred, InSet)
        assert pred.values == ["urban", "suburban"]

    def test_explicit_approx_eq_custom_tol(self):
        arm = QueryArm(
            label="a", kind=QueryKind.CONDITION,
            condition_on={"X": {"kind": "approx_eq", "value": 10.0, "tol_std": 0.3}},
        )
        pred = arm.condition_on["X"]
        assert isinstance(pred, ApproxEq)
        assert pred.tol_std == 0.3

    # --- Validators ---

    def test_range_invalid_order_raises(self):
        with pytest.raises(ValueError, match="lo=.*must be <= hi"):
            ConditionRange(lo=10, hi=0)

    def test_quantile_range_invalid_order_raises(self):
        with pytest.raises(ValueError, match="q_lo=.*must be <= q_hi"):
            QuantileRange(q_lo=0.8, q_hi=0.2)

    def test_quantile_range_out_of_bounds(self):
        with pytest.raises(ValueError):
            QuantileRange(q_lo=-0.1, q_hi=0.5)

    def test_in_set_empty_raises(self):
        with pytest.raises(ValueError):
            InSet(values=[])

    # --- JSON round-trip ---

    def test_json_roundtrip(self):
        arm = QueryArm(
            label="a", kind=QueryKind.CONDITION,
            condition_on={
                "X": {"kind": "range", "lo": 0, "hi": 100},
                "Y": 5.0,
                "Z": {"kind": "in_set", "values": ["A", "B"]},
            },
        )
        dumped = arm.model_dump(mode="json")
        restored = QueryArm(**dumped)
        assert isinstance(restored.condition_on["X"], ConditionRange)
        assert isinstance(restored.condition_on["Y"], ApproxEq)
        assert isinstance(restored.condition_on["Z"], InSet)
        assert restored.condition_on["X"].hi == 100

    def test_multiple_predicates_conjunction(self):
        arm = QueryArm(
            label="a", kind=QueryKind.CONDITION,
            condition_on={
                "income": {"kind": "quantile_range", "q_lo": 0.0, "q_hi": 0.5},
                "region": {"kind": "in_set", "values": ["urban"]},
            },
        )
        assert len(arm.condition_on) == 2


# ---------------------------------------------------------------------------
# Measurement tests
# ---------------------------------------------------------------------------


class TestMeasurement:
    def test_mean(self):
        m = Measurement(kind=MeasurementKind.MEAN, target="Y")
        assert m.target == "Y"

    def test_quantile_requires_q(self):
        with pytest.raises(ValueError, match="quantile measurement requires q"):
            Measurement(kind=MeasurementKind.QUANTILE, target="Y")

    def test_quantile_valid(self):
        m = Measurement(kind=MeasurementKind.QUANTILE, target="Y", q=0.9)
        assert m.q == 0.9

    def test_tail_prob_requires_threshold(self):
        with pytest.raises(ValueError, match="tail_prob measurement requires threshold"):
            Measurement(kind=MeasurementKind.TAIL_PROB, target="Y")

    def test_tail_prob_valid(self):
        m = Measurement(kind=MeasurementKind.TAIL_PROB, target="Y", threshold=0.8)
        assert m.threshold == 0.8

    def test_partial_correlation_requires_lhs_rhs(self):
        with pytest.raises(ValueError, match="partial_correlation requires lhs and rhs"):
            Measurement(kind=MeasurementKind.PARTIAL_CORRELATION, lhs="X")

    def test_partial_correlation_valid(self):
        m = Measurement(
            kind=MeasurementKind.PARTIAL_CORRELATION,
            lhs="X",
            rhs="Y",
            cond_set=("Z",),
        )
        assert m.cond_set == ("Z",)

    def test_identifiability_requires_treatment_outcome(self):
        with pytest.raises(ValueError, match="identifiability_check requires"):
            Measurement(kind=MeasurementKind.IDENTIFIABILITY_CHECK, treatment="X")

    def test_identifiability_valid(self):
        m = Measurement(
            kind=MeasurementKind.IDENTIFIABILITY_CHECK,
            treatment="X",
            outcome="Y",
            candidate_adjust_set=("Z",),
        )
        assert m.candidate_adjust_set == ("Z",)


# ---------------------------------------------------------------------------
# AtomicSpec tests
# ---------------------------------------------------------------------------


class TestAtomicSpec:
    def test_mean_contrast(self):
        spec = _mean_contrast_spec("pressure", "sanding")
        assert len(spec.arms) == 2
        assert spec.measurement.kind == MeasurementKind.MEAN
        assert spec.comparison.kind == ComparisonKind.DIFFERENCE
        assert spec.assertion.kind == AssertionKind.POSITIVE

    def test_duplicate_arm_labels_rejected(self):
        with pytest.raises(ValueError, match="arm labels must be unique"):
            AtomicSpec(
                spec_id="bad",
                arms=(
                    QueryArm(label="a", kind=QueryKind.BASELINE),
                    QueryArm(label="a", kind=QueryKind.BASELINE),
                ),
                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            )

    def test_observational_spec(self):
        """Verify an observational contrast can be expressed."""
        spec = AtomicSpec(
            spec_id="obs1",
            arms=(
                QueryArm(label="hi", kind=QueryKind.OBSERVE, values={"X": 1.0}),
                QueryArm(label="lo", kind=QueryKind.OBSERVE, values={"X": 0.0}),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )
        assert spec.arms[0].kind == QueryKind.OBSERVE

    def test_identifiability_spec(self):
        """Verify identifiability check can be expressed."""
        spec = AtomicSpec(
            spec_id="id1",
            arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
            measurement=Measurement(
                kind=MeasurementKind.IDENTIFIABILITY_CHECK,
                treatment="X",
                outcome="Y",
                candidate_adjust_set=("Z",),
            ),
            comparison=Comparison(kind=ComparisonKind.IDENTITY),
            assertion=Assertion(kind=AssertionKind.IDENTIFIABLE),
        )
        assert spec.assertion.kind == AssertionKind.IDENTIFIABLE

    def test_sweep_spec(self):
        """Verify a dose-response / threshold scan can be expressed."""
        spec = AtomicSpec(
            spec_id="sweep1",
            arms=(
                QueryArm(
                    label="dose",
                    kind=QueryKind.SWEEP,
                    sweep_var="X",
                    sweep_values=(0.1, 0.3, 0.5, 0.7, 0.9),
                ),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.PIECEWISE_FIT),
            assertion=Assertion(kind=AssertionKind.CHANGEPOINT_EXISTS),
        )
        assert len(spec.arms[0].sweep_values) == 5


# ---------------------------------------------------------------------------
# ClaimCard / Submission tests
# ---------------------------------------------------------------------------


class TestClaimCard:
    def test_valid_card(self):
        card = _claim_card()
        assert card.confidence == 0.8

    def test_minimal_card(self):
        card = ClaimCard(
            claim_id="c1",
            claim_text="This is a valid claim text",
            focus_variables=["X"],
            confidence=0.5,
            evidence_basis=_evidence(),
        )
        assert card.outcome_aspect is None

    def test_text_too_short(self):
        with pytest.raises(ValueError):
            ClaimCard(
                claim_id="c1",
                claim_text="Too short",
                focus_variables=["X"],
                confidence=0.5,
                evidence_basis=_evidence(),
            )

    def test_no_evidence_rejected(self):
        with pytest.raises(ValueError):
            ClaimCard(
                claim_id="c1",
                claim_text="This is a valid claim text",
                focus_variables=["X"],
                confidence=0.5,
                evidence_basis=[],
            )


class TestClaimSubmission:
    def test_valid_submission(self):
        sub = ClaimSubmission(
            claims=[_claim_card("c1"), _claim_card("c2", "Another valid claim text")]
        )
        assert len(sub.claims) == 2

    def test_duplicate_ids_rejected(self):
        with pytest.raises(ValueError, match="claim_id must be unique"):
            ClaimSubmission(claims=[_claim_card("c1"), _claim_card("c1")])

    def test_max_claims(self):
        assert MAX_CLAIMS == 5

    def test_over_max_rejected(self):
        cards = [_claim_card(f"c{i}", f"Valid claim number {i} text here") for i in range(6)]
        with pytest.raises(ValueError):
            ClaimSubmission(claims=cards)


# ---------------------------------------------------------------------------
# Salience Map tests
# ---------------------------------------------------------------------------


class TestSalienceMap:
    def _family(self, fid: str, target: str = "Y") -> SalienceFamily:
        return SalienceFamily(
            family_id=fid,
            key=FamilyKey(
                brief_target=target,
                focus_signature=("X", "Y"),
                pattern_class="causal_effect",
            ),
            atoms=(
                FamilyAtom(
                    atom_id=f"{fid}_a1",
                    spec=_mean_contrast_spec("X", "Y", spec_id=f"{fid}_s1"),
                ),
            ),
            salience=0.8,
        )

    def test_valid_map(self):
        sm = SalienceMap(
            world_id="w1",
            brief_target="Y",
            families=[self._family("f1"), self._family("f2")],
        )
        assert len(sm.families) == 2
        assert sm.family_ids == {"f1", "f2"}

    def test_family_key_sorts_signature(self):
        key = FamilyKey(
            brief_target="Y",
            focus_signature=("Z", "A", "M"),
            pattern_class="mediation",
        )
        assert key.focus_signature == ("A", "M", "Z")

    def test_max_families(self):
        assert MAX_FAMILIES == 30


# ---------------------------------------------------------------------------
# Scoring model tests
# ---------------------------------------------------------------------------


class TestScoring:
    def test_episode_score_weights(self):
        es = EpisodeScore(
            correctness=0.8,
            coverage=0.6,
            efficiency=0.9,
            total=0.0,
            families_hit=3,
            families_total=5,
        )
        assert es.W_CORRECTNESS == 0.60
        assert es.W_COVERAGE == 0.30
        assert es.W_EFFICIENCY == 0.10

    def test_constants(self):
        assert SPEC_BASE == 0.50
        assert SPEC_BONUS_MAX == 0.50
        assert OVERCLAIM_MAX == 0.50
        assert FAMILY_HIT_THRESHOLD == 0.60
        assert EPISODE_PRECISION_GATE == 0.55

    def test_claim_verdict_model(self):
        v = ClaimVerdict(
            claim_id="c1",
            matched_family_id="f1",
            score=0.75,
            verdict="partially_true_with_omission",
        )
        assert v.verdict == "partially_true_with_omission"

    def test_atom_verdict_model(self):
        spec = _mean_contrast_spec("X", "Y")
        v = AtomVerdict(
            atom_id="a1",
            spec=spec,
            ground_truth=0.35,
            solver_assertion_holds=True,
            score=1.0,
        )
        assert v.solver_assertion_holds is True


# ---------------------------------------------------------------------------
# Grammar composability tests — verify diverse claim types are expressible
# ---------------------------------------------------------------------------


class TestGrammarExpressiveness:
    """Verify that the 4-piece grammar can express diverse claim types."""

    def test_tail_risk(self):
        """'PM2.5 increases extreme hospitalization risk'"""
        AtomicSpec(
            spec_id="tail1",
            arms=(
                QueryArm(label="hi", kind=QueryKind.INTERVENE, values={"PM2_5": 1.0}),
                QueryArm(label="lo", kind=QueryKind.INTERVENE, values={"PM2_5": 0.0}),
            ),
            measurement=Measurement(
                kind=MeasurementKind.TAIL_PROB, target="hospitalization", threshold=0.9
            ),
            comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )

    def test_variance_reduction(self):
        """'Timely irrigation reduces yield variability'"""
        AtomicSpec(
            spec_id="var1",
            arms=(
                QueryArm(label="timely", kind=QueryKind.INTERVENE, values={"timing": 1.0}),
                QueryArm(label="late", kind=QueryKind.INTERVENE, values={"timing": 0.0}),
            ),
            measurement=Measurement(kind=MeasurementKind.VARIANCE, target="yield"),
            comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="late"),
            assertion=Assertion(kind=AssertionKind.NEGATIVE),
        )

    def test_policy_bundle(self):
        """'Spacing + viscosity combination beats either alone'"""
        AtomicSpec(
            spec_id="pol1",
            arms=(
                QueryArm(
                    label="combo",
                    kind=QueryKind.INTERVENE,
                    values={"spacing": 1.0, "viscosity": 0.5},
                ),
                QueryArm(label="spacing_only", kind=QueryKind.INTERVENE, values={"spacing": 1.0}),
                QueryArm(label="visc_only", kind=QueryKind.INTERVENE, values={"viscosity": 0.5}),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="outcome"),
            comparison=Comparison(kind=ComparisonKind.RANKING),
            assertion=Assertion(
                kind=AssertionKind.RANK_ORDER, order=("combo", "spacing_only", "visc_only")
            ),
        )

    def test_measurement_gap(self):
        """'Observed defect rate rose but real defect rate stayed flat'"""
        AtomicSpec(
            spec_id="gap1",
            arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
            measurement=Measurement(
                kind=MeasurementKind.MEAN, target=("defect_observed", "defect_real")
            ),
            comparison=Comparison(kind=ComparisonKind.GAP, min_gap=0.10),
            assertion=Assertion(kind=AssertionKind.GAP_MATERIAL),
        )

    def test_observational_partial_correlation(self):
        """'X and Y are correlated controlling for Z'"""
        AtomicSpec(
            spec_id="pcor1",
            arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
            measurement=Measurement(
                kind=MeasurementKind.PARTIAL_CORRELATION,
                lhs="X",
                rhs="Y",
                cond_set=("Z",),
            ),
            comparison=Comparison(kind=ComparisonKind.IDENTITY),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )

    def test_adjusted_contrast(self):
        """'After adjusting for confounders, X still affects Y'"""
        AtomicSpec(
            spec_id="adj1",
            arms=(
                QueryArm(
                    label="adj_hi",
                    kind=QueryKind.ADJUST,
                    values={"X": 1.0},
                    adjust_set=("Z1", "Z2"),
                    treatment="X",
                    outcome="Y",
                ),
                QueryArm(
                    label="adj_lo",
                    kind=QueryKind.ADJUST,
                    values={"X": 0.0},
                    adjust_set=("Z1", "Z2"),
                    treatment="X",
                    outcome="Y",
                ),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="adj_lo"),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )

    def test_not_identifiable(self):
        """'Cannot distinguish effect of X1 from X2'"""
        AtomicSpec(
            spec_id="nid1",
            arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
            measurement=Measurement(
                kind=MeasurementKind.IDENTIFIABILITY_CHECK,
                treatment="X1",
                outcome="Y",
                candidate_causes=("X1", "X2"),
            ),
            comparison=Comparison(kind=ComparisonKind.IDENTITY),
            assertion=Assertion(kind=AssertionKind.NOT_DISTINGUISHABLE),
        )
