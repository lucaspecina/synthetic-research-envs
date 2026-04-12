"""Tests for Open Investigation models: DSL grammar, claim cards, salience map."""

from __future__ import annotations

import pytest

from sreg.models.open_investigation import (
    MAX_CLAIMS,
    ApproxEq,
    Assertion,
    AssertionKind,
    AtomicSpec,
    AtomVerdict,
    ClaimCard,
    ClaimSubmission,
    Comparison,
    ComparisonKind,
    ConditionRange,
    EvidenceRef,
    InSet,
    Measurement,
    MeasurementKind,
    QuantileRange,
    QueryArm,
    QueryKind,
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

    def test_adjust_with_partial_correlation_rejected(self):
        """REGRESSION (P06 forensics, policy_equity): the compiler emitted
        spec(arm.kind=ADJUST + measurement.kind=PARTIAL_CORRELATION) which
        is structurally incoherent — ADJUST returns 1-D outcome samples and
        cannot support multivariate measurements. The grammar must reject
        this combination at construction time.
        """
        with pytest.raises(ValueError, match="kind=ADJUST"):
            AtomicSpec(
                spec_id="bad_adjust_pcor",
                arms=(
                    QueryArm(
                        label="adjusted",
                        kind=QueryKind.ADJUST,
                        treatment="X",
                        outcome="Y",
                        adjust_set=("Z",),
                    ),
                ),
                measurement=Measurement(
                    kind=MeasurementKind.PARTIAL_CORRELATION,
                    lhs="X",
                    rhs="Y",
                    cond_set=("Z",),
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.NEGATIVE),
            )

    def test_adjust_with_correlation_rejected(self):
        """ADJUST + CORRELATION is also incoherent: correlation needs
        lhs and rhs columns, but ADJUST samples are 1-D outcome only.
        """
        with pytest.raises(ValueError, match="kind=ADJUST"):
            AtomicSpec(
                spec_id="bad_adjust_cor",
                arms=(
                    QueryArm(
                        label="adjusted",
                        kind=QueryKind.ADJUST,
                        treatment="X",
                        outcome="Y",
                        adjust_set=("Z",),
                    ),
                ),
                measurement=Measurement(
                    kind=MeasurementKind.CORRELATION,
                    lhs="X",
                    rhs="Y",
                ),
                comparison=Comparison(kind=ComparisonKind.IDENTITY),
                assertion=Assertion(kind=AssertionKind.POSITIVE),
            )

    def test_adjust_with_mean_still_valid(self):
        """ADJUST + MEAN is the canonical valid combination: compute
        E[Y | do(X=x)] from interventional samples. Must NOT regress.
        """
        spec = AtomicSpec(
            spec_id="ok_adjust_mean",
            arms=(
                QueryArm(
                    label="adjusted",
                    kind=QueryKind.ADJUST,
                    treatment="X",
                    outcome="Y",
                    adjust_set=("Z",),
                    values={"X": 1.0},
                ),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
            comparison=Comparison(kind=ComparisonKind.IDENTITY),
            assertion=Assertion(kind=AssertionKind.POSITIVE),
        )
        assert spec.arms[0].kind == QueryKind.ADJUST
        assert spec.measurement.kind == MeasurementKind.MEAN

    def test_baseline_with_partial_correlation_still_valid(self):
        """BASELINE + PARTIAL_CORRELATION is the canonical valid form for
        an observational partial correlation. Must NOT regress.
        """
        spec = AtomicSpec(
            spec_id="ok_baseline_pcor",
            arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
            measurement=Measurement(
                kind=MeasurementKind.PARTIAL_CORRELATION,
                lhs="X",
                rhs="Y",
                cond_set=("Z",),
            ),
            comparison=Comparison(kind=ComparisonKind.IDENTITY),
            assertion=Assertion(kind=AssertionKind.NEGATIVE),
        )
        assert spec.arms[0].kind == QueryKind.BASELINE
        assert spec.measurement.kind == MeasurementKind.PARTIAL_CORRELATION


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
        assert MAX_CLAIMS == 15

    def test_over_max_rejected(self):
        cards = [_claim_card(f"c{i}", f"Valid claim number {i} text here") for i in range(16)]
        with pytest.raises(ValueError):
            ClaimSubmission(claims=cards)



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


# ---------------------------------------------------------------------------
# Robust loader tests (P06 Experiment R)
# ---------------------------------------------------------------------------


class TestRobustLoader:
    """Tests for load_sub_questions_v2_robust — frozen artifact loader.

    The loader has three contractually-locked behaviors:
      1. Happy path: a valid raw SQ list round-trips into SubQuestionIntentV2.
      2. Spec-level fallback: an invalid spec is dropped with a reason; the
         SQ continues with the surviving specs.
      3. SQ-level fallback: if EVERY required spec falls, the whole SQ is
         abstained — surviving `support` specs are NOT promoted.
    """

    def _good_required_raw(self, spec_id: str = "good") -> dict:
        """Raw verification_spec dict for a valid baseline+mean+positive spec."""
        return {
            "spec": _mean_contrast_spec("X", "Y", spec_id=spec_id).model_dump(mode="json"),
            "role": "required",
        }

    def _bad_adjust_pcor_required_raw(self, spec_id: str = "bad") -> dict:
        """Raw verification_spec dict for the policy_equity bug shape:
        adjust + partial_correlation. The validator added in P06 must reject
        this at AtomicSpec construction time, so the loader must drop it.
        """
        return {
            "spec": {
                "spec_id": spec_id,
                "arms": [{
                    "label": "adjusted",
                    "kind": "adjust",
                    "treatment": "X",
                    "outcome": "Y",
                    "adjust_set": ["Z"],
                }],
                "measurement": {
                    "kind": "partial_correlation",
                    "lhs": "X",
                    "rhs": "Y",
                    "cond_set": ["Z"],
                },
                "comparison": {"kind": "identity"},
                "assertion": {"kind": "positive"},
            },
            "role": "required",
        }

    def _good_support_raw(self, spec_id: str = "supp") -> dict:
        """Raw verification_spec dict marked as support (not required)."""
        return {
            "spec": _mean_contrast_spec("X", "Y", spec_id=spec_id).model_dump(mode="json"),
            "role": "support",
        }

    def _wrap_sq(self, sq_id: str, specs: list[dict]) -> dict:
        return {
            "sq_id": sq_id,
            "text_gloss": "Investigate the relationship between X and Y",
            "tier": "high",
            "verification_specs": specs,
        }

    def test_happy_path_no_drops(self):
        """Valid raw SQ list loads cleanly with zero drops or abstentions."""
        from sreg.models.open_investigation import (
            SubQuestionIntentV2,
            load_sub_questions_v2_robust,
        )

        raw = [self._wrap_sq("sq1", [self._good_required_raw()])]
        result = load_sub_questions_v2_robust(raw)

        assert len(result.loaded) == 1
        assert isinstance(result.loaded[0], SubQuestionIntentV2)
        assert result.loaded[0].sq_id == "sq1"
        assert result.abstained_sq_ids == []
        assert result.dropped_specs == []

    def test_invalid_spec_dropped_sq_continues(self):
        """An invalid spec is dropped, the SQ continues with the survivors.

        SQ has [required-good, required-bad, support-good]. Loader drops the
        bad one, retains 1 required + 1 support.
        """
        from sreg.models.open_investigation import load_sub_questions_v2_robust

        raw = [self._wrap_sq("sq1", [
            self._good_required_raw("ok_req"),
            self._bad_adjust_pcor_required_raw("dropped_req"),
            self._good_support_raw("ok_sup"),
        ])]
        result = load_sub_questions_v2_robust(raw)

        assert len(result.loaded) == 1
        sq = result.loaded[0]
        assert sq.sq_id == "sq1"
        # Bad spec is gone; the two valid specs remain (1 required + 1 support).
        assert len(sq.verification_specs) == 2
        assert {vs.spec.spec_id for vs in sq.verification_specs} == {"ok_req", "ok_sup"}
        assert {vs.role for vs in sq.verification_specs} == {"required", "support"}
        # Drop record is captured with the offending spec_id.
        assert len(result.dropped_specs) == 1
        dropped = result.dropped_specs[0]
        assert dropped.sq_id == "sq1"
        assert dropped.spec_id == "dropped_req"
        assert dropped.role == "required"
        assert "adjust" in dropped.reason.lower() or "partial" in dropped.reason.lower()
        assert result.abstained_sq_ids == []

    def test_all_required_drop_abstains_sq_supports_not_promoted(self):
        """If every required spec falls, the SQ is abstained as a whole.

        The surviving `support` spec is NOT promoted to required and the SQ
        does NOT appear in `loaded`. This is the required-fallback policy
        from research/notes/p06_phase_c_forensics.md.
        """
        from sreg.models.open_investigation import load_sub_questions_v2_robust

        raw = [self._wrap_sq("sq_dead", [
            self._bad_adjust_pcor_required_raw("dropped_req_only"),
            self._good_support_raw("orphan_support"),
        ])]
        result = load_sub_questions_v2_robust(raw)

        # SQ is NOT in loaded; it is in abstained_sq_ids.
        assert result.loaded == []
        assert result.abstained_sq_ids == ["sq_dead"]
        # The bad required spec is recorded as dropped (the orphan support
        # is not synthesized into the loaded list — it is silently discarded
        # along with the abstained SQ).
        assert any(
            d.spec_id == "dropped_req_only" and d.role == "required"
            for d in result.dropped_specs
        )
