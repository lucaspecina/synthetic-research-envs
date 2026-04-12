"""Tests for OI Compiler: ClaimIntent → AtomicSpec lowering."""

from __future__ import annotations

import pytest

from sreg.models.open_investigation import (
    ArtifactAccess,
    AssertionKind,
    ClaimCard,
    ComparisonKind,
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
    validate_intent,
)
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

    def test_heterogeneity_ate_spec_is_direction_agnostic(self):
        """Regression #24: spec 1 must use GAP_MATERIAL, not a directional
        assertion. intent.direction is ambiguous for heterogeneity (could
        mean interaction direction or pooled ATE direction), so spec 1 only
        checks that a material ATE exists, regardless of sign.

        Before the fix, a solver correctly detecting heterogeneity would get
        truth=0.4 because the directional ATE spec failed when the LLM
        encoded the interaction direction rather than the pooled ATE sign.
        """
        world = _test_world()
        summary = build_world_summary(world, "Y", seed=42)

        # Try all three directions — spec 1 must always be GAP_MATERIAL.
        for direction in (Direction.POSITIVE, Direction.NEGATIVE, Direction.NEAR_ZERO):
            intent = ClaimIntent(
                claim_id="c1",
                pattern=PatternClass.HETEROGENEITY,
                treatment="A",
                outcome="Y",
                modifier="Z",
                direction=direction,
            )
            output = lower_intent(intent, summary)
            ate_spec = output.specs[0]
            assert ate_spec.assertion.kind == AssertionKind.GAP_MATERIAL, (
                f"direction={direction}: expected GAP_MATERIAL, "
                f"got {ate_spec.assertion.kind}"
            )

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


