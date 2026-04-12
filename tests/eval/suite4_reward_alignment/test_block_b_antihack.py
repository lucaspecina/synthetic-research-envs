"""Suite 4 Block B — Reward Robustness / Anti-Hack.

Tests that adversarial claim patterns score LOWER than honest investigation.
Each test constructs a specific gaming strategy and verifies the scoring
formula penalizes it appropriately.

Adversarial patterns tested:
1. Generic-but-true: vague claims that technically hold but lack specificity
2. Duplicate spam: same claim repeated many times
3. Volume spam: exceeding claim budget massively
4. Wrong-variable claims: claims about non-existent families
5. Precision flood: many wrong claims to dilute correctness
6. Cherry-pick easy: only claim the easiest family
7. Association-as-causation: claim observational as causal (wrong atoms)

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
from sreg.tools.oi_verifier import score_claim_against_family, score_episode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# Same 4-family salience map as block A
FAMILIES = [
    _make_family("f1", n_atoms=3, n_material=2, pattern="causal_effect"),
    _make_family("f2", n_atoms=2, n_material=2, pattern="confounding"),
    _make_family("f3", n_atoms=2, n_material=2, pattern="mediation"),
    _make_family("f4", n_atoms=1, n_material=1, pattern="descriptive"),
]

# Honest baseline: 4 claims hitting all 4 families with solid scores
HONEST_MATCHES = [("f1", 0.85), ("f2", 0.80), ("f3", 0.75), ("f4", 0.90)]
HONEST_N_CLAIMS = 4


def _honest_score() -> float:
    return score_episode(HONEST_MATCHES, FAMILIES, n_claims=HONEST_N_CLAIMS).total


# ---------------------------------------------------------------------------
# 1. Generic-but-true: vague claims with low specificity
# ---------------------------------------------------------------------------


class TestGenericButTrue:
    """A solver could make technically-true but vague claims like
    "X is associated with Y". These should score lower because they
    cover fewer atoms (low specificity bonus) even if atom_precision = 1.0.
    """

    def test_vague_claims_score_lower(self):
        """4 vague claims covering only 1 atom per family (low specificity).

        For f1 (3 atoms, 2 material): covering 1/3 atoms gets low specificity
        bonus and overclaim penalty for the omitted material atom.

        Hand-calc for f1: atom_precision=1.0, specificity_ratio=1/3=0.333,
        omitted_material=1/2=0.5.
        bonus=0.5*0.333=0.167, penalty=0.5*0.5=0.25.
        score = 1.0 * (0.5+0.167) * (1-0.25) = 0.667 * 0.75 = 0.500
        """
        # Vague solver: each claim covers 1 atom in its family
        vague = [("f1", 0.50), ("f2", 0.56), ("f3", 0.56), ("f4", 0.50)]
        vague_ep = score_episode(vague, FAMILIES, n_claims=4)
        honest_ep = score_episode(HONEST_MATCHES, FAMILIES, n_claims=4)

        assert honest_ep.total > vague_ep.total, (
            f"Honest ({honest_ep.total:.3f}) should beat "
            f"vague ({vague_ep.total:.3f})"
        )

    def test_specificity_bonus_gradient(self):
        """More atoms covered in a family -> higher score.
        Incentivizes making specific, detailed claims.
        """
        family = FAMILIES[0]  # f1: 3 atoms, 2 material
        s1, _ = score_claim_against_family({"f1_a0": 1.0}, family)
        s2, _ = score_claim_against_family({"f1_a0": 1.0, "f1_a1": 1.0}, family)
        s3, _ = score_claim_against_family(
            {"f1_a0": 1.0, "f1_a1": 1.0, "f1_a2": 1.0}, family
        )
        assert s1 < s2 < s3, (
            f"Specificity gradient broken: {s1:.3f}, {s2:.3f}, {s3:.3f}"
        )


# ---------------------------------------------------------------------------
# 2. Duplicate spam: same claim repeated
# ---------------------------------------------------------------------------


class TestDuplicateSpam:
    """Submitting the same claim N times should not increase the score
    beyond what a single claim achieves. Coverage only counts the BEST
    score per family, so duplicates are wasted claims.
    """

    def test_duplicates_dont_increase_score(self):
        """5 identical claims on f1 vs 1 claim on f1.

        Both hit 1 family. But 5 claims wastes budget.
        """
        single = [("f1", 0.90)]
        duplicated = [("f1", 0.90)] * 5

        single_ep = score_episode(single, FAMILIES, n_claims=1)
        dup_ep = score_episode(duplicated, FAMILIES, n_claims=5)

        # Same coverage (1 family hit)
        assert single_ep.families_hit == dup_ep.families_hit
        # Duplicated should not score higher
        assert dup_ep.total <= single_ep.total + 0.01, (
            f"Duplicates should not help: single={single_ep.total:.3f}, "
            f"dup={dup_ep.total:.3f}"
        )

    def test_duplicates_lose_to_diverse(self):
        """5 claims all on f1 vs 4 claims on 4 different families.

        Diverse strategy wins on coverage.
        """
        dup5 = [("f1", 0.90)] * 5
        diverse4 = [("f1", 0.75), ("f2", 0.75), ("f3", 0.75), ("f4", 0.75)]

        dup_ep = score_episode(dup5, FAMILIES, n_claims=5)
        div_ep = score_episode(diverse4, FAMILIES, n_claims=4)

        assert div_ep.total > dup_ep.total, (
            f"Diverse ({div_ep.total:.3f}) should beat "
            f"duplicated ({dup_ep.total:.3f})"
        )


# ---------------------------------------------------------------------------
# 3. Volume spam: exceeding claim budget
# ---------------------------------------------------------------------------


class TestVolumeSpam:
    """Submitting way more claims than the budget should be penalized
    through the efficiency term.
    """

    def test_over_budget_reduces_total(self):
        """15 claims at budget=15 is fine. 30 claims is penalized.

        Same claim_matches quality, but n_claims=30 halves efficiency.
        """
        matches = [("f1", 0.85), ("f2", 0.80), ("f3", 0.75), ("f4", 0.90)]
        within = score_episode(matches, FAMILIES, n_claims=15)
        over = score_episode(matches, FAMILIES, n_claims=30)

        assert within.efficiency == 1.0
        assert over.efficiency == 0.0  # 30-15=15 overflow, 15/15=1.0, 1-1=0
        assert within.total > over.total

    def test_massive_spam_near_zero_efficiency(self):
        """100 claims with budget 15. Efficiency should be 0."""
        matches = [("f1", 0.85)]
        ep = score_episode(matches, FAMILIES, n_claims=100)
        assert ep.efficiency == 0.0

    def test_spam_loses_to_focused(self):
        """30 claims (15 good, 15 wrong) vs 4 focused good claims.

        Spam: avg correctness diluted by wrong claims, efficiency penalized.
        Focused: high correctness, full efficiency.
        """
        good = [("f1", 0.85), ("f2", 0.80), ("f3", 0.75), ("f4", 0.90)]
        spam = good + [("f1", 0.0)] * 11  # 15 total claim_matches

        focused_ep = score_episode(good, FAMILIES, n_claims=4)
        spam_ep = score_episode(spam, FAMILIES, n_claims=30)

        assert focused_ep.total > spam_ep.total, (
            f"Focused ({focused_ep.total:.3f}) should beat "
            f"spam ({spam_ep.total:.3f})"
        )


# ---------------------------------------------------------------------------
# 4. Wrong-variable claims: claims about non-existent families
# ---------------------------------------------------------------------------


class TestWrongVariable:
    """Claims about variables not in the salience map should score 0.
    A solver that invents findings about unrelated variables gets nothing.
    """

    def test_unmatched_claims_score_zero(self):
        """4 claims matching non-existent families."""
        wrong = [
            ("fake1", 0.90),
            ("fake2", 0.85),
            ("fake3", 0.80),
            ("fake4", 0.95),
        ]
        ep = score_episode(wrong, FAMILIES, n_claims=4)
        # No families hit (fake IDs don't match)
        assert ep.families_hit == 0
        assert ep.coverage == 0.0

    def test_wrong_variables_lose_to_honest(self):
        """Even one correct claim on a real family beats all wrong claims.

        Wrong-variable claims get score 0.0 from the verifier because there
        are no atoms to confirm them against. One real claim at 0.70 still
        wins via both correctness and coverage.
        """
        wrong = [("fake1", 0.0), ("fake2", 0.0), ("fake3", 0.0)]
        correct = [("f1", 0.70)]

        wrong_ep = score_episode(wrong, FAMILIES, n_claims=3)
        correct_ep = score_episode(correct, FAMILIES, n_claims=1)

        assert correct_ep.total > wrong_ep.total


# ---------------------------------------------------------------------------
# 5. Precision flood: many wrong claims dilute correctness
# ---------------------------------------------------------------------------


class TestPrecisionFlood:
    """Submitting many wrong claims alongside correct ones dilutes
    correctness and can trigger the precision gate.
    """

    def test_wrong_claims_trigger_gate(self):
        """3 correct claims + 7 wrong claims.

        correctness = (0.85+0.80+0.75+0*7)/10 = 2.4/10 = 0.24
        Precision gate: 0.24 < 0.55 -> active -> coverage = 0.
        """
        flood = [
            ("f1", 0.85), ("f2", 0.80), ("f3", 0.75),
            ("f1", 0.0), ("f2", 0.0), ("f3", 0.0), ("f4", 0.0),
            ("f1", 0.0), ("f2", 0.0), ("f3", 0.0),
        ]
        ep = score_episode(flood, FAMILIES, n_claims=10)
        assert ep.precision_gate_active
        assert ep.coverage == 0.0

    def test_precision_flood_loses_to_selective(self):
        """Selective solver (3 claims, all correct) vs flood (10 claims, 7 wrong)."""
        selective = [("f1", 0.85), ("f2", 0.80), ("f3", 0.75)]
        flood = [
            ("f1", 0.85), ("f2", 0.80), ("f3", 0.75),
            ("f1", 0.0), ("f2", 0.0), ("f3", 0.0), ("f4", 0.0),
            ("f1", 0.0), ("f2", 0.0), ("f3", 0.0),
        ]

        sel_ep = score_episode(selective, FAMILIES, n_claims=3)
        flood_ep = score_episode(flood, FAMILIES, n_claims=10)

        assert sel_ep.total > flood_ep.total, (
            f"Selective ({sel_ep.total:.3f}) should beat "
            f"flood ({flood_ep.total:.3f})"
        )


# ---------------------------------------------------------------------------
# 6. Cherry-pick easy: only claim the easiest family
# ---------------------------------------------------------------------------


class TestCherryPick:
    """A solver that only claims the easiest family (e.g., descriptive
    baseline) and avoids harder ones should score less than one that
    attempts the full breadth.
    """

    def test_easy_only_low_coverage(self):
        """1 perfect claim on f4 (easy, descriptive) vs 4 decent claims.

        Cherry-pick: 1 family hit, perfect correctness.
        Broad: 4 families hit, good correctness.
        Broad wins because coverage (30% weight) matters.
        """
        cherry = [("f4", 1.0)]
        broad = [("f1", 0.70), ("f2", 0.70), ("f3", 0.70), ("f4", 0.70)]

        cherry_ep = score_episode(cherry, FAMILIES, n_claims=1)
        broad_ep = score_episode(broad, FAMILIES, n_claims=4)

        assert broad_ep.coverage > cherry_ep.coverage
        assert broad_ep.total > cherry_ep.total


# ---------------------------------------------------------------------------
# 7. Composite: honest investigation beats ALL adversarial strategies
# ---------------------------------------------------------------------------


class TestHonestBeatsAll:
    """The honest investigation strategy should score higher than every
    adversarial strategy. This is the capstone anti-hack test.
    """

    @pytest.mark.parametrize(
        "strategy_name, matches, n_claims",
        [
            (
                "vague",
                [("f1", 0.50), ("f2", 0.50), ("f3", 0.50), ("f4", 0.50)],
                4,
            ),
            (
                "duplicated",
                [("f1", 0.90)] * 5,
                5,
            ),
            (
                "volume_spam",
                [("f1", 0.85), ("f2", 0.80), ("f3", 0.75), ("f4", 0.90)],
                30,
            ),
            (
                "wrong_variables",
                [("fake1", 1.0), ("fake2", 1.0), ("fake3", 1.0)],
                3,
            ),
            (
                "precision_flood",
                [("f1", 0.85), ("f2", 0.80)] + [("f1", 0.0)] * 8,
                10,
            ),
            (
                "cherry_pick",
                [("f4", 1.0)],
                1,
            ),
        ],
        ids=[
            "vague",
            "duplicated",
            "volume_spam",
            "wrong_variables",
            "precision_flood",
            "cherry_pick",
        ],
    )
    def test_honest_beats_adversarial(
        self, strategy_name: str, matches: list, n_claims: int
    ):
        honest = score_episode(HONEST_MATCHES, FAMILIES, n_claims=HONEST_N_CLAIMS)
        adversarial = score_episode(matches, FAMILIES, n_claims=n_claims)

        assert honest.total > adversarial.total, (
            f"Honest ({honest.total:.3f}) should beat {strategy_name} "
            f"({adversarial.total:.3f})"
        )
