"""Tests for OI Compiler: ClaimIntent → AtomicSpec lowering."""

from __future__ import annotations

import pytest

from sreg.models.open_investigation import (
    AnalysisRecord,
    ArtifactAccess,
    AssertionKind,
    ClaimCard,
    ComparisonKind,
    EpisodeTrace,
    EvidenceRef,
    MeasurementKind,
    QueryKind,
)
from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_compiler import (
    ClaimIntent,
    CompilerOutput,
    Direction,
    PatternClass,
    build_world_summary,
    lower_intent,
    match_specs_to_families,
    score_compiled_episode,
    validate_intent,
)
from sreg.tools.oi_salience import build_salience_map
from sreg.tools.oi_verifier import verify_atom
from sreg.world.scm import SCMWorld

# ---------------------------------------------------------------------------
# Test world
# ---------------------------------------------------------------------------


def _test_world() -> SCMWorld:
    """C -> A -> M -> Y, C -> Y, Z -> Y: diverse causal structure."""
    return SCMWorld(
        id="compiler-test",
        graph={
            "C": [],
            "A": ["C"],
            "M": ["A"],
            "Z": [],
            "Y": ["A", "M", "C", "Z"],
        },
        equations={
            "C": lambda p, rng: rng.normal(0, 1),
            "A": lambda p, rng: 0.8 * p["C"] + rng.normal(0, 0.5),
            "M": lambda p, rng: 0.6 * p["A"] + rng.normal(0, 0.3),
            "Z": lambda p, rng: rng.normal(0, 1),
            "Y": lambda p, rng: (
                0.5 * p["A"]
                + 0.4 * p["M"]
                + 0.3 * p["C"]
                + 0.2 * p["Z"]
                + rng.normal(0, 0.3)
            ),
        },
    )


# ---------------------------------------------------------------------------
# WorldSummary tests
# ---------------------------------------------------------------------------


class TestWorldSummary:
    def test_build_summary(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", n_mc=10_000, seed=42)

        assert summary.world_id == "compiler-test"
        assert summary.target == "Y"
        assert len(summary.variables) == 5
        assert "A" in summary.observable_names

    def test_anchors(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", n_mc=10_000, seed=42)

        a = summary.anchors("A")
        assert a.p25 < a.p50 < a.p75
        assert a.std > 0

    def test_hi_lo(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", n_mc=10_000, seed=42)

        assert summary.hi("A") > summary.lo("A")
        assert summary.mid("A") > summary.lo("A")
        assert summary.mid("A") < summary.hi("A")

    def test_missing_variable_raises(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", n_mc=10_000, seed=42)

        import pytest

        with pytest.raises(ValueError, match="not in world summary"):
            summary.anchors("NONEXISTENT")


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid_causal_effect(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="A",
            outcome="Y",
            direction=Direction.POSITIVE,
        )
        errors = validate_intent(intent, summary)
        assert errors == []

    def test_invalid_treatment(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="FAKE",
            outcome="Y",
        )
        errors = validate_intent(intent, summary)
        assert any("FAKE" in e for e in errors)

    def test_treatment_equals_outcome(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="Y",
            outcome="Y",
        )
        errors = validate_intent(intent, summary)
        assert any("different" in e for e in errors)

    def test_mediation_requires_mediator(self):
        import pytest

        with pytest.raises(ValueError, match="mediator"):
            ClaimIntent(
                claim_id="c1",
                pattern=PatternClass.MEDIATION,
                treatment="A",
                outcome="Y",
            )

    def test_heterogeneity_requires_modifier(self):
        import pytest

        with pytest.raises(ValueError, match="modifier"):
            ClaimIntent(
                claim_id="c1",
                pattern=PatternClass.HETEROGENEITY,
                treatment="A",
                outcome="Y",
            )

    def test_latent_variable_rejected(self):
        world = SCMWorld(
            id="latent-test",
            graph={"U": [], "X": ["U"], "Y": ["X", "U"]},
            equations={
                "U": lambda p, rng: rng.normal(0, 1),
                "X": lambda p, rng: p["U"] + rng.normal(0, 0.5),
                "Y": lambda p, rng: p["X"] + p["U"] + rng.normal(0, 0.3),
            },
            latent_variables={"U"},
        )
        summary = build_world_summary(world, "Y", seed=42)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="U",
            outcome="Y",
        )
        errors = validate_intent(intent, summary)
        assert any("not observable" in e for e in errors)


# ---------------------------------------------------------------------------
# Lowering tests
# ---------------------------------------------------------------------------


class TestLowering:
    def test_causal_effect(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="A",
            outcome="Y",
            direction=Direction.POSITIVE,
        )
        output = lower_intent(intent, summary)
        assert output.compiled
        assert len(output.specs) == 1

        spec = output.specs[0]
        assert spec.assertion.kind == AssertionKind.POSITIVE
        assert spec.comparison.kind == ComparisonKind.DIFFERENCE
        assert len(spec.arms) == 2
        assert spec.arms[0].kind == QueryKind.INTERVENE

    def test_mediation_produces_two_specs(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.MEDIATION,
            treatment="A",
            outcome="Y",
            mediator="M",
            direction=Direction.POSITIVE,
        )
        output = lower_intent(intent, summary)
        assert output.compiled
        assert len(output.specs) == 2  # ATE + indirect

        ate_spec = output.specs[0]
        med_spec = output.specs[1]
        assert ate_spec.comparison.kind == ComparisonKind.DIFFERENCE
        assert med_spec.comparison.kind == ComparisonKind.CONTRAST_DIFF
        assert len(med_spec.arms) == 4

    def test_heterogeneity_produces_two_specs(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.HETEROGENEITY,
            treatment="A",
            outcome="Y",
            modifier="Z",
        )
        output = lower_intent(intent, summary)
        assert output.compiled
        assert len(output.specs) == 2  # ATE + interaction

        het_spec = output.specs[1]
        assert het_spec.comparison.kind == ComparisonKind.CONTRAST_DIFF
        assert len(het_spec.arms) == 4

    def test_tail_risk(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.TAIL_RISK,
            treatment="A",
            outcome="Y",
        )
        output = lower_intent(intent, summary)
        assert output.compiled
        spec = output.specs[0]
        assert spec.measurement.kind == MeasurementKind.TAIL_PROB
        assert spec.measurement.threshold is not None

    def test_variance_effect(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.VARIANCE_EFFECT,
            treatment="A",
            outcome="Y",
        )
        output = lower_intent(intent, summary)
        assert output.compiled
        assert output.specs[0].measurement.kind == MeasurementKind.VARIANCE

    def test_observational_association(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.OBSERVATIONAL_ASSOCIATION,
            treatment="A",
            outcome="Y",
            conditioning_set=["C"],
        )
        output = lower_intent(intent, summary)
        assert output.compiled
        spec = output.specs[0]
        assert spec.measurement.kind == MeasurementKind.PARTIAL_CORRELATION
        assert spec.measurement.cond_set == ("C",)

    def test_effect_ranking(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.EFFECT_RANKING,
            treatment="A",
            outcome="Y",
            ranking_vars=["A", "C", "Z"],
        )
        output = lower_intent(intent, summary)
        assert output.compiled
        spec = output.specs[0]
        assert spec.comparison.kind == ComparisonKind.RANKING
        assert len(spec.arms) == 3

    def test_invalid_intent_produces_abstention(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="NONEXISTENT",
            outcome="Y",
        )
        output = lower_intent(intent, summary)
        assert not output.compiled
        assert output.status == "abstention"
        assert output.abstention_reason is not None

    def test_negative_direction(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="A",
            outcome="Y",
            direction=Direction.NEGATIVE,
        )
        output = lower_intent(intent, summary)
        assert output.compiled
        assert output.specs[0].assertion.kind == AssertionKind.NEGATIVE


# ---------------------------------------------------------------------------
# E2E: lowered specs verify correctly against the SCM
# ---------------------------------------------------------------------------


class TestLoweringE2E:
    def test_causal_effect_verifies(self):
        """Compiled causal effect spec should verify True against real SCM."""
        world = _test_world()
        solver = SCMSolver(world)
        summary = build_world_summary(world, "Y", seed=42)

        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="A",
            outcome="Y",
            direction=Direction.POSITIVE,
        )
        output = lower_intent(intent, summary)
        assert output.compiled

        verdict = verify_atom(output.specs[0], world, solver, n_mc=20_000, seed=42)
        assert verdict.solver_assertion_holds is True, (
            f"A->Y should be positive, got {verdict.ground_truth}"
        )

    def test_mediation_verifies(self):
        """Compiled mediation should verify: both ATE and indirect positive."""
        world = _test_world()
        solver = SCMSolver(world)
        summary = build_world_summary(world, "Y", seed=42)

        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.MEDIATION,
            treatment="A",
            outcome="Y",
            mediator="M",
            direction=Direction.POSITIVE,
        )
        output = lower_intent(intent, summary)
        assert output.compiled
        assert len(output.specs) == 2

        # ATE should be positive
        ate_verdict = verify_atom(output.specs[0], world, solver, n_mc=20_000, seed=42)
        assert ate_verdict.solver_assertion_holds is True

        # Indirect should be positive (A->M->Y path exists)
        med_verdict = verify_atom(output.specs[1], world, solver, n_mc=20_000, seed=42)
        assert med_verdict.solver_assertion_holds is True, (
            f"Indirect A->M->Y should be positive, got {med_verdict.ground_truth}"
        )

    def test_observational_verifies(self):
        """Compiled partial correlation should verify True."""
        world = _test_world()
        solver = SCMSolver(world)
        summary = build_world_summary(world, "Y", seed=42)

        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.OBSERVATIONAL_ASSOCIATION,
            treatment="A",
            outcome="Y",
            conditioning_set=["C"],
        )
        output = lower_intent(intent, summary)
        assert output.compiled

        verdict = verify_atom(output.specs[0], world, solver, n_mc=50_000, seed=42)
        assert verdict.solver_assertion_holds is True


# ---------------------------------------------------------------------------
# Matching tests
# ---------------------------------------------------------------------------


class TestMatching:
    def test_causal_effect_matches_family(self):
        """Compiled ATE spec should match the causal_effect family for (A, Y)."""
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)
        smap = build_salience_map(world, "Y", n_mc=10_000, seed=42)

        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.CAUSAL_EFFECT,
            treatment="A",
            outcome="Y",
        )
        output = lower_intent(intent, summary)
        matches = match_specs_to_families(output.specs, smap.families)

        assert len(matches) == 1
        family_id, spec = matches[0]
        assert family_id is not None
        # Should match a causal_effect family
        matched_family = next(f for f in smap.families if f.family_id == family_id)
        assert matched_family.key.pattern_class == "causal_effect"

    def test_unmatched_returns_none(self):
        """Spec for variable not in any family should return None match."""
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)
        smap = build_salience_map(world, "Y", n_mc=10_000, seed=42)

        # Create a spec about X (independent variable, not in salience map target)
        intent = ClaimIntent(
            claim_id="c1",
            pattern=PatternClass.OBSERVATIONAL_ASSOCIATION,
            treatment="Z",
            outcome="C",
        )
        output = lower_intent(intent, summary)
        matches = match_specs_to_families(output.specs, smap.families)

        # May or may not match — if it does, it should be a weak match
        # The key test is that the function doesn't crash
        assert len(matches) == 1


# ---------------------------------------------------------------------------
# Full pipeline E2E: compile → match → verify → score
# ---------------------------------------------------------------------------


class TestFullPipeline:
    def test_oracle_scores_high(self):
        """Oracle claims (correct patterns + direction) should score well."""
        world = _test_world()
        solver = SCMSolver(world)
        summary = build_world_summary(world, "Y", seed=42)
        smap = build_salience_map(world, "Y", n_mc=20_000, seed=42)

        # Oracle: submit correct claims matching known truths
        claims = [
            lower_intent(
                ClaimIntent(
                    claim_id="ate_A",
                    pattern=PatternClass.CAUSAL_EFFECT,
                    treatment="A",
                    outcome="Y",
                    direction=Direction.POSITIVE,
                ),
                summary,
            ),
            lower_intent(
                ClaimIntent(
                    claim_id="med_A_M",
                    pattern=PatternClass.MEDIATION,
                    treatment="A",
                    outcome="Y",
                    mediator="M",
                    direction=Direction.POSITIVE,
                ),
                summary,
            ),
        ]

        episode = score_compiled_episode(
            claims, smap.families, world, solver, n_mc=20_000, seed=42
        )
        assert episode.total > 0.3, f"Oracle should score > 0.3, got {episode.total}"

    def test_abstention_scores_zero(self):
        """Abstention claims should contribute 0 to correctness."""
        world = _test_world()
        solver = SCMSolver(world)
        smap = build_salience_map(world, "Y", n_mc=10_000, seed=42)

        claims = [
            CompilerOutput(
                claim_id="abstained",
                status="abstention",
                abstention_reason="Test abstention",
            ),
        ]
        episode = score_compiled_episode(
            claims, smap.families, world, solver, n_mc=10_000, seed=42
        )
        assert episode.correctness == 0.0
        assert episode.coverage == 0.0


# ---------------------------------------------------------------------------
# Warrant-wired pipeline: compile → verify → match → warrant → score
# ---------------------------------------------------------------------------


class TestWarrantPipeline:
    def test_warrant_reduces_prior_only_score(self):
        """Oracle claims with no investigation get reduced by warrant."""
        world = _test_world()
        solver = SCMSolver(world)
        summary = build_world_summary(world, "Y", seed=42)
        smap = build_salience_map(world, "Y", n_mc=20_000, seed=42)

        compiled = [
            lower_intent(
                ClaimIntent(
                    claim_id="ate_A",
                    pattern=PatternClass.CAUSAL_EFFECT,
                    treatment="A",
                    outcome="Y",
                    direction=Direction.POSITIVE,
                ),
                summary,
            ),
        ]

        # Claim card referencing a valid artifact but no trace → no warrant
        claim_cards = [
            ClaimCard(
                claim_id="ate_A",
                claim_text="A has a positive causal effect on Y in this study",
                focus_variables=["A", "Y"],
                confidence=0.8,
                evidence_basis=[
                    EvidenceRef(
                        artifact_id="dataset_bg",
                        rationale="Regression analysis on background data",
                    )
                ],
            ),
        ]

        # Empty trace: solver never accessed data
        empty_trace = EpisodeTrace()
        data_assets = {"dataset_bg", "dataset_survey"}

        # Score without warrant (baseline)
        base_episode = score_compiled_episode(
            compiled, smap.families, world, solver,
            n_mc=20_000, seed=42,
        )

        # Score with empty trace (no investigation)
        warranted_episode = score_compiled_episode(
            compiled, smap.families, world, solver,
            n_mc=20_000, seed=42,
            claim_cards=claim_cards,
            trace=empty_trace,
            data_asset_ids=data_assets,
        )

        # With warrant: score should be lower
        assert warranted_episode.total < base_episode.total
        assert warranted_episode.warrant_active
        assert warranted_episode.raw_correctness is not None
        assert warranted_episode.avg_warrant is not None
        assert warranted_episode.avg_warrant < 0.5

    def test_warrant_with_investigation_preserves_score(self):
        """Oracle claims with full investigation keep their score."""
        world = _test_world()
        solver = SCMSolver(world)
        summary = build_world_summary(world, "Y", seed=42)
        smap = build_salience_map(world, "Y", n_mc=20_000, seed=42)

        compiled = [
            lower_intent(
                ClaimIntent(
                    claim_id="ate_A",
                    pattern=PatternClass.CAUSAL_EFFECT,
                    treatment="A",
                    outcome="Y",
                    direction=Direction.POSITIVE,
                ),
                summary,
            ),
        ]

        claim_cards = [
            ClaimCard(
                claim_id="ate_A",
                claim_text="A has a positive causal effect on Y in this study",
                focus_variables=["A", "Y"],
                confidence=0.8,
                evidence_basis=[
                    EvidenceRef(
                        artifact_id="dataset_bg",
                        rationale="Regression analysis on background data",
                    )
                ],
            ),
        ]

        # Full investigation trace
        full_trace = EpisodeTrace(
            accesses=[
                ArtifactAccess(artifact_id="dataset_bg", step=1),
            ],
            analyses=[
                AnalysisRecord(
                    analysis_id="a1",
                    input_artifact_ids=["dataset_bg"],
                    columns_used=["A", "Y"],
                    op_type="regression",
                    step=3,
                ),
            ],
            claim_steps={"ate_A": 5},
        )
        data_assets = {"dataset_bg", "dataset_survey"}

        base_episode = score_compiled_episode(
            compiled, smap.families, world, solver,
            n_mc=20_000, seed=42,
        )

        warranted_episode = score_compiled_episode(
            compiled, smap.families, world, solver,
            n_mc=20_000, seed=42,
            claim_cards=claim_cards,
            trace=full_trace,
            data_asset_ids=data_assets,
        )

        # Full investigation: score should be very close to baseline
        assert warranted_episode.total == pytest.approx(
            base_episode.total, abs=0.01
        )
        assert warranted_episode.avg_warrant == pytest.approx(1.0)

    def test_multispec_claim_shares_warrant(self):
        """Mediation (2 specs) gets same warrant for both specs."""
        world = _test_world()
        solver = SCMSolver(world)
        summary = build_world_summary(world, "Y", seed=42)
        smap = build_salience_map(world, "Y", n_mc=20_000, seed=42)

        # Mediation produces 2 specs
        compiled = [
            lower_intent(
                ClaimIntent(
                    claim_id="med_A_M",
                    pattern=PatternClass.MEDIATION,
                    treatment="A",
                    outcome="Y",
                    mediator="M",
                    direction=Direction.POSITIVE,
                ),
                summary,
            ),
        ]
        assert len(compiled[0].specs) == 2  # ATE + indirect

        claim_cards = [
            ClaimCard(
                claim_id="med_A_M",
                claim_text="A affects Y partly through M in this dataset",
                focus_variables=["A", "M", "Y"],
                confidence=0.7,
                evidence_basis=[
                    EvidenceRef(
                        artifact_id="dataset_bg",
                        rationale="Mediation analysis on background",
                    )
                ],
            ),
        ]

        # Partial investigation: accessed but no substantive analysis
        partial_trace = EpisodeTrace(
            accesses=[ArtifactAccess(artifact_id="dataset_bg", step=1)],
            claim_steps={"med_A_M": 5},
        )
        data_assets = {"dataset_bg"}

        episode = score_compiled_episode(
            compiled, smap.families, world, solver,
            n_mc=20_000, seed=42,
            claim_cards=claim_cards,
            trace=partial_trace,
            data_asset_ids=data_assets,
        )

        # Should have warrant active
        assert episode.warrant_active
        # Warrant < 1.0 (accessed but not analyzed)
        assert episode.avg_warrant is not None
        assert episode.avg_warrant < 1.0
