"""Suite 1 Core Correctness — Scoring formula arithmetic tests.

Every expected value here is computed BY HAND from the formulas in
oi_verifier.py, not by running the code. This catches regressions in
the scoring arithmetic independently of the verifier.

Constants (from models/open_investigation.py):
    SPEC_BASE              = 0.50
    SPEC_BONUS_MAX         = 0.50
    OVERCLAIM_MAX          = 0.50
    FAMILY_HIT_THRESHOLD   = 0.60
    EPISODE_PRECISION_GATE = 0.55
    MAX_CLAIMS             = 15
"""

from __future__ import annotations

import pytest

from sreg.models.open_investigation import (
    Assertion,
    AssertionKind,
    AtomicSpec,
    Comparison,
    ComparisonKind,
    FamilyAtom,
    FamilyKey,
    Measurement,
    MeasurementKind,
    QueryArm,
    QueryKind,
    SalienceFamily,
)
from sreg.tools.oi_verifier import score_claim_against_family, score_episode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dummy_spec(spec_id: str = "s") -> AtomicSpec:
    """Minimal valid AtomicSpec for scoring tests (never executed)."""
    return AtomicSpec(
        spec_id=spec_id,
        arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
        measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
        comparison=Comparison(kind=ComparisonKind.IDENTITY),
        assertion=Assertion(kind=AssertionKind.POSITIVE),
    )


def _make_family(
    n_atoms: int,
    n_material: int,
    weights: list[float] | None = None,
    family_id: str = "f1",
) -> SalienceFamily:
    """Build a SalienceFamily with configurable atoms."""
    if weights is None:
        weights = [1.0] * n_atoms
    atoms = []
    for i in range(n_atoms):
        atoms.append(
            FamilyAtom(
                atom_id=f"a{i}",
                spec=_dummy_spec(f"s{i}"),
                weight=weights[i],
                material=i < n_material,
            )
        )
    return SalienceFamily(
        family_id=family_id,
        key=FamilyKey(
            brief_target="Y",
            focus_signature=("X", "Y"),
            pattern_class="causal_effect",
        ),
        atoms=tuple(atoms),
        salience=0.8,
    )


# ---------------------------------------------------------------------------
# score_claim_against_family — hand-calculated values
# ---------------------------------------------------------------------------


class TestClaimScoring:
    """Test claim-level scoring formula with hand-calculated values.

    Formula:
        atom_precision = verified_w / covered_w
        specificity_ratio = verified_w / family_w
        omitted_material_ratio = omitted_material_w / material_w
        specificity_bonus = 0.50 * specificity_ratio
        overclaim_penalty = 0.50 * omitted_material_ratio
        score = clamp(0, 1, atom_precision * (0.50 + bonus) * (1 - penalty))
    """

    def test_all_true_all_material(self):
        """2 atoms, both material, both correct (weight=1.0 each).

        verified_w = 1.0 + 1.0 = 2.0
        covered_w = 2.0
        family_w = 2.0
        material_w = 2.0
        omitted_material_w = 0.0

        atom_precision = 2.0 / 2.0 = 1.0
        specificity_ratio = 2.0 / 2.0 = 1.0
        omitted_material_ratio = 0.0 / 2.0 = 0.0

        bonus = 0.50 * 1.0 = 0.50
        penalty = 0.50 * 0.0 = 0.0
        score = 1.0 * (0.50 + 0.50) * (1.0 - 0.0) = 1.0
        verdict = "fully_true"
        """
        family = _make_family(n_atoms=2, n_material=2)
        score, verdict = score_claim_against_family({"a0": 1.0, "a1": 1.0}, family)
        assert score == pytest.approx(1.0)
        assert verdict == "fully_true"

    def test_all_false(self):
        """2 atoms, both wrong.

        verified_w = 0 + 0 = 0.0
        atom_precision = 0.0
        score = 0.0
        verdict = "false"
        """
        family = _make_family(n_atoms=2, n_material=2)
        score, verdict = score_claim_against_family({"a0": 0.0, "a1": 0.0}, family)
        assert score == pytest.approx(0.0)
        assert verdict == "false"

    def test_one_correct_one_omitted_material(self):
        """2 atoms (both material), only a0 covered and correct.

        verified_w = 1.0 * 1.0 = 1.0
        covered_w = 1.0
        family_w = 2.0
        material_w = 2.0
        omitted_material_w = 1.0 (a1 is material and omitted)

        atom_precision = 1.0 / 1.0 = 1.0
        specificity_ratio = 1.0 / 2.0 = 0.5
        omitted_material_ratio = 1.0 / 2.0 = 0.5

        bonus = 0.50 * 0.5 = 0.25
        penalty = 0.50 * 0.5 = 0.25
        score = 1.0 * (0.50 + 0.25) * (1.0 - 0.25) = 0.75 * 0.75 = 0.5625
        verdict = "partially_true_with_omission"
        """
        family = _make_family(n_atoms=2, n_material=2)
        score, verdict = score_claim_against_family({"a0": 1.0}, family)
        assert score == pytest.approx(0.5625)
        assert verdict == "partially_true_with_omission"

    def test_mixed_verdicts(self):
        """2 atoms (both material), a0 correct, a1 wrong.

        verified_w = 1.0 * 1.0 + 1.0 * 0.0 = 1.0
        covered_w = 2.0
        family_w = 2.0
        material_w = 2.0
        omitted_material_w = 0.0

        atom_precision = 1.0 / 2.0 = 0.5
        specificity_ratio = 1.0 / 2.0 = 0.5
        omitted_material_ratio = 0.0

        bonus = 0.50 * 0.5 = 0.25
        penalty = 0.0
        score = 0.5 * (0.50 + 0.25) * 1.0 = 0.375
        verdict = "mixed"
        """
        family = _make_family(n_atoms=2, n_material=2)
        score, verdict = score_claim_against_family({"a0": 1.0, "a1": 0.0}, family)
        assert score == pytest.approx(0.375)
        assert verdict == "mixed"

    def test_unmatched(self):
        """No atoms match the family.

        score = 0.0
        verdict = "unmatched"
        """
        family = _make_family(n_atoms=2, n_material=2)
        score, verdict = score_claim_against_family({"a99": 1.0}, family)
        assert score == pytest.approx(0.0)
        assert verdict == "unmatched"

    def test_non_material_omission_no_penalty(self):
        """3 atoms, 1 material (a0). Cover a0 + a1, omit a2 (non-material).

        verified_w = 1.0 + 1.0 = 2.0
        covered_w = 2.0
        family_w = 3.0
        material_w = 1.0 (only a0)
        omitted_material_w = 0.0 (a0 is covered, a2 is non-material)

        atom_precision = 2.0 / 2.0 = 1.0
        specificity_ratio = 2.0 / 3.0 = 0.6667
        omitted_material_ratio = 0.0

        bonus = 0.50 * 0.6667 = 0.3333
        penalty = 0.0
        score = 1.0 * (0.50 + 0.3333) * 1.0 = 0.8333
        verdict = "fully_true" (precision=1.0 and omitted_material=0)
        """
        family = _make_family(n_atoms=3, n_material=1)
        score, verdict = score_claim_against_family({"a0": 1.0, "a1": 1.0}, family)
        assert score == pytest.approx(0.8333, abs=0.001)
        assert verdict == "fully_true"

    def test_weighted_atoms(self):
        """2 atoms, weights [2.0, 1.0], both material, both correct.

        verified_w = 2.0 * 1.0 + 1.0 * 1.0 = 3.0
        covered_w = 3.0
        family_w = 3.0
        material_w = 3.0
        omitted_material_w = 0.0

        atom_precision = 1.0
        specificity_ratio = 1.0
        score = 1.0 * (0.50 + 0.50) * 1.0 = 1.0
        """
        family = _make_family(n_atoms=2, n_material=2, weights=[2.0, 1.0])
        score, verdict = score_claim_against_family({"a0": 1.0, "a1": 1.0}, family)
        assert score == pytest.approx(1.0)
        assert verdict == "fully_true"

    def test_weighted_partial(self):
        """2 atoms, weights [2.0, 1.0], both material. Only a1 correct.

        verified_w = 2.0 * 0.0 + 1.0 * 1.0 = 1.0
        covered_w = 3.0
        family_w = 3.0
        material_w = 3.0

        atom_precision = 1.0 / 3.0 = 0.3333
        specificity_ratio = 1.0 / 3.0 = 0.3333

        bonus = 0.50 * 0.3333 = 0.1667
        penalty = 0.0
        score = 0.3333 * (0.50 + 0.1667) = 0.3333 * 0.6667 = 0.2222
        """
        family = _make_family(n_atoms=2, n_material=2, weights=[2.0, 1.0])
        score, verdict = score_claim_against_family({"a0": 0.0, "a1": 1.0}, family)
        assert score == pytest.approx(0.2222, abs=0.001)
        assert verdict == "mixed"


# ---------------------------------------------------------------------------
# score_episode — hand-calculated values
# ---------------------------------------------------------------------------


class TestEpisodeScoring:
    """Test episode-level scoring formula with hand-calculated values.

    Formula:
        correctness = mean(match_scores)
        families_hit = count(fam where best_score >= 0.60)
        coverage = families_hit / n_families  (zeroed if precision gate)
        precision_gate = correctness < 0.55
        efficiency = max(0, 1 - overflow / budget)
        total = 0.60 * correctness + 0.30 * coverage + 0.10 * efficiency
    """

    def test_perfect_single_claim(self):
        """1 family, 1 claim with score=0.9.

        correctness = 0.9
        families_hit = 1 (0.9 >= 0.60)
        coverage = 1/1 = 1.0  (precision gate: 0.9 >= 0.55, inactive)
        efficiency = max(0, 1 - 0/15) = 1.0
        total = 0.60*0.9 + 0.30*1.0 + 0.10*1.0 = 0.54 + 0.30 + 0.10 = 0.94
        """
        families = [_make_family(n_atoms=2, n_material=2)]
        ep = score_episode([("f1", 0.9)], families, n_claims=1)
        assert ep.correctness == pytest.approx(0.9)
        assert ep.coverage == pytest.approx(1.0)
        assert ep.efficiency == pytest.approx(1.0)
        assert ep.total == pytest.approx(0.94)
        assert ep.precision_gate_active is False

    def test_precision_gate_active(self):
        """1 family, 1 claim with score=0.3. Gate should activate.

        correctness = 0.3
        precision_gate = 0.3 < 0.55 → active
        coverage = 0.0 (gated)
        efficiency = 1.0
        total = 0.60*0.3 + 0.30*0.0 + 0.10*1.0 = 0.18 + 0 + 0.10 = 0.28
        """
        families = [_make_family(n_atoms=2, n_material=2)]
        ep = score_episode([("f1", 0.3)], families, n_claims=1)
        assert ep.correctness == pytest.approx(0.3)
        assert ep.coverage == pytest.approx(0.0)
        assert ep.precision_gate_active is True
        assert ep.total == pytest.approx(0.28)

    def test_efficiency_penalty(self):
        """1 family, 1 claim with score=0.9, but 20 claims (budget=15).

        correctness = 0.9
        coverage = 1.0
        overflow = 20 - 15 = 5
        efficiency = max(0, 1 - 5/15) = 1 - 0.3333 = 0.6667
        total = 0.60*0.9 + 0.30*1.0 + 0.10*0.6667
              = 0.54 + 0.30 + 0.06667 = 0.9067
        """
        families = [_make_family(n_atoms=2, n_material=2)]
        ep = score_episode([("f1", 0.9)], families, n_claims=20)
        assert ep.correctness == pytest.approx(0.9)
        assert ep.efficiency == pytest.approx(0.6667, abs=0.001)
        assert ep.total == pytest.approx(0.9067, abs=0.001)

    def test_two_families_partial_coverage(self):
        """2 families. Claim 1 hits f1 with 0.8, claim 2 hits f2 with 0.4.

        correctness = (0.8 + 0.4) / 2 = 0.6
        family f1: best=0.8 >= 0.60 → hit
        family f2: best=0.4 < 0.60 → miss
        families_hit = 1
        coverage = 1/2 = 0.5  (precision: 0.6 >= 0.55, gate off)
        efficiency = 1.0 (2 claims, budget 15)
        total = 0.60*0.6 + 0.30*0.5 + 0.10*1.0 = 0.36 + 0.15 + 0.10 = 0.61
        """
        f1 = _make_family(n_atoms=2, n_material=2, family_id="f1")
        f2 = _make_family(n_atoms=2, n_material=2, family_id="f2")
        ep = score_episode([("f1", 0.8), ("f2", 0.4)], [f1, f2], n_claims=2)
        assert ep.correctness == pytest.approx(0.6)
        assert ep.families_hit == 1
        assert ep.coverage == pytest.approx(0.5)
        assert ep.total == pytest.approx(0.61)

    def test_custom_budget(self):
        """Custom budget=5, 7 claims. Overflow = 2.

        efficiency = max(0, 1 - 2/5) = 0.6
        """
        families = [_make_family(n_atoms=2, n_material=2)]
        ep = score_episode([("f1", 0.9)], families, n_claims=7, claim_budget=5)
        assert ep.efficiency == pytest.approx(0.6)

    def test_massive_overflow_floors_efficiency(self):
        """Budget=5, 100 claims. Overflow = 95.

        efficiency = max(0, 1 - 95/5) = max(0, -18) = 0.0
        """
        families = [_make_family(n_atoms=2, n_material=2)]
        ep = score_episode([("f1", 0.9)], families, n_claims=100, claim_budget=5)
        assert ep.efficiency == pytest.approx(0.0)

    def test_boundary_precision_gate(self):
        """Correctness exactly at boundary: 0.55 should NOT trigger gate.

        (Gate triggers when correctness < 0.55, not <=)
        Use score=0.65 so the family IS hit (0.65 >= 0.60 threshold).
        correctness = 0.65 >= 0.55 → gate OFF → coverage should be 1.0.
        total = 0.60*0.65 + 0.30*1.0 + 0.10*1.0 = 0.39 + 0.30 + 0.10 = 0.79
        """
        families = [_make_family(n_atoms=2, n_material=2)]
        ep = score_episode([("f1", 0.65)], families, n_claims=1)
        assert ep.precision_gate_active is False
        assert ep.coverage == pytest.approx(1.0)
        assert ep.total == pytest.approx(0.79)

    def test_just_below_gate(self):
        """Correctness = 0.549 → gate active."""
        families = [_make_family(n_atoms=2, n_material=2)]
        ep = score_episode([("f1", 0.549)], families, n_claims=1)
        assert ep.precision_gate_active is True
        assert ep.coverage == pytest.approx(0.0)
