"""Suite 4 Block A — Investigation Pressure (no-data gap).

Tests that the scoring system rewards data-informed investigation over
prior-only guessing. For each scenario, we hand-craft two claim sets:
- "data": claims derived from looking at the actual data (correct effects)
- "nodata": claims derived from domain priors (some right, some wrong)

The score of the data-informed set must exceed the prior-only set by a
meaningful gap (epsilon). This verifies that the scoring formula creates
INCENTIVE to actually investigate the data.

No LLM involved — all inputs are hand-crafted.
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
from sreg.tools.oi_verifier import score_episode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MIN_GAP = 0.05  # Minimum acceptable investigation gap


def _dummy_spec(spec_id: str = "s") -> AtomicSpec:
    return AtomicSpec(
        spec_id=spec_id,
        arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
        measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
        comparison=Comparison(kind=ComparisonKind.IDENTITY),
        assertion=Assertion(kind=AssertionKind.POSITIVE),
    )


def _make_family(
    family_id: str,
    n_atoms: int = 2,
    n_material: int = 2,
    pattern: str = "causal_effect",
) -> SalienceFamily:
    atoms = []
    for i in range(n_atoms):
        atoms.append(
            FamilyAtom(
                atom_id=f"{family_id}_a{i}",
                spec=_dummy_spec(f"{family_id}_s{i}"),
                weight=1.0,
                material=i < n_material,
            )
        )
    return SalienceFamily(
        family_id=family_id,
        key=FamilyKey(
            brief_target="Y",
            focus_signature=("X", "Y"),
            pattern_class=pattern,
        ),
        atoms=tuple(atoms),
        salience=0.8,
    )


# ---------------------------------------------------------------------------
# Salience map: 4 families representing a typical research case
# ---------------------------------------------------------------------------
#
# F1: main causal effect (2 material atoms) — e.g., Treatment -> Outcome
# F2: confounding structure (2 material atoms) — e.g., Confounder bias
# F3: mediation pathway (2 material atoms) — e.g., indirect effect
# F4: descriptive baseline (1 material atom) — e.g., variance of outcome

FAMILIES = [
    _make_family("f1", n_atoms=2, n_material=2, pattern="causal_effect"),
    _make_family("f2", n_atoms=2, n_material=2, pattern="confounding"),
    _make_family("f3", n_atoms=2, n_material=2, pattern="mediation"),
    _make_family("f4", n_atoms=1, n_material=1, pattern="descriptive"),
]


# ---------------------------------------------------------------------------
# Scenario 1: Thorough data-informed vs generic priors
# ---------------------------------------------------------------------------


class TestInvestigationGapBasic:
    """Data-informed solver vs no-data solver on a typical 4-family case."""

    def test_data_beats_nodata(self):
        """Solver with data hits more families with higher scores.

        Data-informed: 4 claims, each hitting a different family with 0.85+
        No-data: 4 claims, 2 match families weakly (0.4), 2 miss entirely

        Expected: data_total >> nodata_total
        """
        data_matches = [
            ("f1", 0.90),  # correct main effect
            ("f2", 0.85),  # identified confounding correctly
            ("f3", 0.80),  # found mediation pathway
            ("f4", 0.95),  # described baseline accurately
        ]
        nodata_matches = [
            ("f1", 0.40),  # guessed direction, wrong magnitude
            ("f2", 0.00),  # didn't identify confounding at all
            ("f3", 0.30),  # vague claim about mediation
            ("f4", 0.50),  # guessed baseline roughly right
        ]

        data_ep = score_episode(data_matches, FAMILIES, n_claims=4)
        nodata_ep = score_episode(nodata_matches, FAMILIES, n_claims=4)

        gap = data_ep.total - nodata_ep.total
        assert gap > MIN_GAP, (
            f"Investigation gap too small: {gap:.3f} "
            f"(data={data_ep.total:.3f}, nodata={nodata_ep.total:.3f})"
        )
        # Also verify specifics
        assert data_ep.families_hit > nodata_ep.families_hit
        assert data_ep.correctness > nodata_ep.correctness

    def test_precision_gate_punishes_wild_guessing(self):
        """No-data solver guesses wildly: 5 claims, all wrong.

        correctness < 0.55 -> precision gate activates -> coverage = 0.
        Even if one claim accidentally matches a family, no coverage credit.
        """
        wild_guesses = [
            ("f1", 0.10),  # wrong direction
            ("f2", 0.00),  # no match
            ("f3", 0.20),  # vague, mostly wrong
            ("f1", 0.15),  # second try, still wrong
            ("f4", 0.10),  # wrong
        ]
        ep = score_episode(wild_guesses, FAMILIES, n_claims=5)
        assert ep.precision_gate_active, (
            f"Precision gate should activate: correctness={ep.correctness:.3f}"
        )
        assert ep.coverage == 0.0
        assert ep.total < 0.20  # very low total

    def test_half_right_still_below_data(self):
        """No-data solver gets 2/4 families right (domain priors work partially).

        Still scores below a thorough data-informed solver because coverage
        and correctness are both lower.
        """
        partial_priors = [
            ("f1", 0.70),  # got the main effect roughly right (common knowledge)
            ("f4", 0.80),  # descriptive claim from priors
        ]
        thorough_data = [
            ("f1", 0.95),
            ("f2", 0.85),
            ("f3", 0.80),
            ("f4", 0.90),
        ]

        prior_ep = score_episode(partial_priors, FAMILIES, n_claims=2)
        data_ep = score_episode(thorough_data, FAMILIES, n_claims=4)

        gap = data_ep.total - prior_ep.total
        assert gap > MIN_GAP, (
            f"Gap between partial priors and thorough data too small: {gap:.3f}"
        )


# ---------------------------------------------------------------------------
# Scenario 2: Coverage reward forces breadth
# ---------------------------------------------------------------------------


class TestBreadthIncentive:
    """Scoring rewards covering MORE families, not just one deeply."""

    def test_broad_beats_deep_single(self):
        """4 claims across 4 families beats 4 claims on 1 family.

        Broad: 4 claims hitting f1, f2, f3, f4 with 0.70 each
        Deep:  4 claims all hitting f1 with 0.95 (but only 1 family)

        Broad should win on coverage (4/4 vs 1/4), even with lower per-claim.
        """
        broad = [("f1", 0.70), ("f2", 0.70), ("f3", 0.70), ("f4", 0.70)]
        deep = [("f1", 0.95), ("f1", 0.95), ("f1", 0.95), ("f1", 0.95)]

        broad_ep = score_episode(broad, FAMILIES, n_claims=4)
        deep_ep = score_episode(deep, FAMILIES, n_claims=4)

        assert broad_ep.coverage > deep_ep.coverage
        assert broad_ep.total > deep_ep.total, (
            f"Broad ({broad_ep.total:.3f}) should beat deep-single ({deep_ep.total:.3f})"
        )

    def test_incremental_family_discovery(self):
        """Each additional family hit increases coverage -> increases total.

        Monotonic: score(1 fam) < score(2 fam) < score(3 fam) < score(4 fam)
        """
        scores = []
        for n_fam in range(1, 5):
            matches = [(f"f{i+1}", 0.80) for i in range(n_fam)]
            ep = score_episode(matches, FAMILIES, n_claims=n_fam)
            scores.append(ep.total)

        for i in range(len(scores) - 1):
            assert scores[i] < scores[i + 1], (
                f"Score should increase with more families: "
                f"{scores[i]:.3f} -> {scores[i+1]:.3f}"
            )


# ---------------------------------------------------------------------------
# Scenario 3: Overclaim penalty forces evidence thoroughness
# ---------------------------------------------------------------------------


class TestOverclaimPenalty:
    """A claim that covers only part of a family is penalized vs one
    that covers all material atoms. This forces the solver to investigate
    thoroughly, not just make surface-level claims.
    """

    def test_full_coverage_beats_partial(self):
        """Claim covering 2/2 material atoms scores higher than 1/2.

        Full: score_claim_against_family({"f1_a0": 1.0, "f1_a1": 1.0}, f1)
        Partial: score_claim_against_family({"f1_a0": 1.0}, f1)

        (Already tested in scoring_math but repeated here as incentive test)
        """
        from sreg.tools.oi_verifier import score_claim_against_family

        family = FAMILIES[0]  # f1: 2 material atoms
        full_score, _ = score_claim_against_family(
            {"f1_a0": 1.0, "f1_a1": 1.0}, family
        )
        partial_score, _ = score_claim_against_family(
            {"f1_a0": 1.0}, family
        )
        assert full_score > partial_score, (
            f"Full coverage ({full_score:.3f}) should beat "
            f"partial ({partial_score:.3f})"
        )

    def test_episode_penalizes_shallow_investigation(self):
        """Solver that superficially touches all families scores less than
        one that covers them in depth (all material atoms per family).

        Shallow: 4 claims, each hitting 1 family but only 1 atom
        Deep: 4 claims, each hitting 1 family covering all atoms

        For score_episode: shallow has lower per-claim scores due to
        overclaim penalty on omitted material atoms.
        """
        # Shallow: partial truth on each family (around 0.5625 per claim)
        shallow = [("f1", 0.56), ("f2", 0.56), ("f3", 0.56), ("f4", 0.56)]
        # Deep: full truth on each family (1.0 per claim)
        deep = [("f1", 1.0), ("f2", 1.0), ("f3", 1.0), ("f4", 1.0)]

        shallow_ep = score_episode(shallow, FAMILIES, n_claims=4)
        deep_ep = score_episode(deep, FAMILIES, n_claims=4)

        assert deep_ep.total > shallow_ep.total
