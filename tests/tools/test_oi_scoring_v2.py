"""Tests for OI Scoring v2: decoupled correctness + structural relevance.

Covers:
- compute_structural_relevance() with various DAG positions
- score_episode_v2() with pre-built claim verdicts
- score_compiled_episode_v2() E2E with curated worlds
"""

from __future__ import annotations

import networkx as nx
import pytest

from sreg.models.open_investigation import (
    ClaimVerdict,
    EpisodeScore,
    FAMILY_HIT_THRESHOLD,
    MAX_CLAIMS,
    NON_TARGET_CAP,
    DESCRIPTIVE_PENALTY,
    RELEVANCE_ANCESTOR,
    RELEVANCE_DESCENDANT,
    SalienceFamily,
    FamilyKey,
    FamilyAtom,
    AtomicSpec,
    QueryArm,
    QueryKind,
    Measurement,
    MeasurementKind,
    Comparison,
    ComparisonKind,
    Assertion,
    AssertionKind,
)
from sreg.tools.oi_compiler import (
    ClaimIntent,
    CompilerOutput,
    Direction,
    PatternClass,
    WorldSummary,
    build_world_summary,
    compute_structural_relevance,
    lower_intent,
    score_compiled_episode_v2,
)
from sreg.tools.oi_salience import build_salience_map
from sreg.tools.oi_verifier import score_episode_v2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dag() -> nx.DiGraph:
    """Treatment world DAG: Age->Severity->Treatment->Biomarker->Recovery."""
    g = nx.DiGraph()
    g.add_edges_from([
        ("Age", "Severity"),
        ("Age", "Recovery"),
        ("Severity", "Treatment"),
        ("Severity", "Recovery"),
        ("Treatment", "Biomarker"),
        ("Treatment", "Recovery"),
        ("Biomarker", "Recovery"),
    ])
    return g


def _make_dummy_family(family_id: str, pattern: str = "causal_effect") -> SalienceFamily:
    """Create a minimal salience family for testing."""
    spec = AtomicSpec(
        spec_id=f"{family_id}_spec",
        arms=(QueryArm(label="a", kind=QueryKind.BASELINE),),
        measurement=Measurement(kind=MeasurementKind.MEAN, target="Recovery"),
        comparison=Comparison(kind=ComparisonKind.IDENTITY),
        assertion=Assertion(kind=AssertionKind.POSITIVE),
    )
    return SalienceFamily(
        family_id=family_id,
        key=FamilyKey(
            brief_target="Recovery",
            focus_signature=("Treatment", "Recovery"),
            pattern_class=pattern,
        ),
        atoms=(FamilyAtom(atom_id=f"{family_id}_a0", spec=spec, weight=1.0),),
        salience=0.8,
    )


# ---------------------------------------------------------------------------
# compute_structural_relevance
# ---------------------------------------------------------------------------

class TestStructuralRelevance:

    def test_target_in_focus(self):
        """Claim involving target directly should get relevance 1.0."""
        dag = _make_dag()
        rel = compute_structural_relevance({"Treatment", "Recovery"}, "Recovery", dag)
        assert rel == 1.0

    def test_ancestor_only(self):
        """Claim involving only ancestors gets capped at NON_TARGET_CAP."""
        dag = _make_dag()
        rel = compute_structural_relevance({"Age", "Severity"}, "Recovery", dag)
        # base=0.7, coverage=2/2=1.0, but capped at 0.5 (no target)
        assert rel == pytest.approx(NON_TARGET_CAP)

    def test_ancestor_with_target(self):
        """Claim with ancestor + target gets full ancestor base."""
        dag = _make_dag()
        rel = compute_structural_relevance({"Age", "Recovery"}, "Recovery", dag)
        # target in focus -> base=1.0, coverage=2/2=1.0
        assert rel == 1.0

    def test_descendant_only(self):
        """Target has no descendants in this DAG (Recovery is leaf)."""
        dag = _make_dag()
        # Recovery has no descendants
        rel = compute_structural_relevance({"SomeChild"}, "Recovery", dag)
        assert rel == 0.0

    def test_irrelevant_variables(self):
        """Variables not in DAG at all get 0."""
        dag = _make_dag()
        rel = compute_structural_relevance({"X", "Y"}, "Recovery", dag)
        assert rel == 0.0

    def test_mixed_relevant_irrelevant(self):
        """Coverage penalty for mixing relevant and irrelevant vars."""
        dag = _make_dag()
        rel = compute_structural_relevance(
            {"Treatment", "Recovery", "RandomVar"}, "Recovery", dag
        )
        # target in focus -> base=1.0, coverage=2/3
        assert rel == pytest.approx(2.0 / 3.0, abs=0.01)

    def test_empty_focus(self):
        """Empty focus returns 0."""
        dag = _make_dag()
        assert compute_structural_relevance(set(), "Recovery", dag) == 0.0

    def test_single_ancestor_claim(self):
        """Age-Severity claim: both ancestors but no target."""
        dag = _make_dag()
        rel = compute_structural_relevance({"Age", "Severity"}, "Recovery", dag)
        # Both are ancestors, coverage=1.0, but cap at NON_TARGET_CAP
        assert rel == pytest.approx(NON_TARGET_CAP)


# ---------------------------------------------------------------------------
# score_episode_v2
# ---------------------------------------------------------------------------

class TestScoreEpisodeV2:

    def _make_families(self, n: int = 5) -> list[SalienceFamily]:
        return [_make_dummy_family(f"fam_{i}") for i in range(n)]

    def test_all_true_relevant(self):
        """All claims true and relevant -> high correctness."""
        families = self._make_families(5)
        verdicts = [
            ClaimVerdict(
                claim_id=f"c{i}",
                matched_family_id=f"fam_{i}",
                truth_score=1.0,
                relevance=1.0,
                effective_score=1.0,
                score=1.0,
                verdict="fully_true",
            )
            for i in range(3)
        ]
        score = score_episode_v2(verdicts, families, n_claims=3)
        assert score.correctness == 1.0
        assert score.families_hit == 3
        assert score.total > 0.7

    def test_true_but_irrelevant(self):
        """True claims with 0 relevance -> correctness 0."""
        families = self._make_families(5)
        verdicts = [
            ClaimVerdict(
                claim_id="c0",
                matched_family_id=None,
                truth_score=1.0,
                relevance=0.0,
                effective_score=0.0,
                score=0.0,
                verdict="true_but_irrelevant",
            )
        ]
        score = score_episode_v2(verdicts, families, n_claims=1)
        assert score.correctness == 0.0

    def test_true_unmatched_gets_credit(self):
        """TRUE claim that doesn't match any family still gets correctness.

        This is THE key difference from v1: unmatched != zero.
        """
        families = self._make_families(5)
        verdicts = [
            ClaimVerdict(
                claim_id="c0",
                matched_family_id=None,  # no family match
                truth_score=1.0,
                relevance=0.7,
                effective_score=0.7,
                score=0.7,
                verdict="fully_true",
            )
        ]
        score = score_episode_v2(verdicts, families, n_claims=1)
        assert score.correctness == 0.7
        assert score.families_hit == 0  # no coverage
        assert score.total > 0.0  # but still has correctness + efficiency

    def test_false_claim_zero(self):
        """False claim gets 0 effective even with high relevance."""
        families = self._make_families(3)
        verdicts = [
            ClaimVerdict(
                claim_id="c0",
                matched_family_id="fam_0",
                truth_score=0.0,
                relevance=1.0,
                effective_score=0.0,
                score=0.0,
                verdict="false",
            )
        ]
        score = score_episode_v2(verdicts, families, n_claims=1)
        assert score.correctness == 0.0

    def test_precision_gate(self):
        """Low correctness triggers precision gate, zeroing coverage."""
        families = self._make_families(3)
        verdicts = [
            ClaimVerdict(
                claim_id="c0",
                matched_family_id="fam_0",
                truth_score=0.3,
                relevance=1.0,
                effective_score=0.3,
                score=0.3,
                verdict="mixed",
            )
        ]
        score = score_episode_v2(verdicts, families, n_claims=1)
        assert score.precision_gate_active is True
        assert score.coverage == 0.0

    def test_empty_claims(self):
        """No claims at all -> minimal score."""
        families = self._make_families(3)
        score = score_episode_v2([], families, n_claims=0)
        assert score.correctness == 0.0
        assert score.total == pytest.approx(0.10)  # only efficiency

    def test_mixed_true_and_false(self):
        """Mix of true and false claims averages correctly."""
        families = self._make_families(5)
        verdicts = [
            ClaimVerdict(
                claim_id="c0",
                matched_family_id="fam_0",
                truth_score=1.0,
                relevance=1.0,
                effective_score=1.0,
                score=1.0,
                verdict="fully_true",
            ),
            ClaimVerdict(
                claim_id="c1",
                matched_family_id=None,
                truth_score=0.0,
                relevance=1.0,
                effective_score=0.0,
                score=0.0,
                verdict="false",
            ),
        ]
        score = score_episode_v2(verdicts, families, n_claims=2)
        assert score.correctness == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# E2E: Confounding in treatment world
# ---------------------------------------------------------------------------


class TestConfoundingE2E:
    """Test confounding pattern with the treatment world (Severity confounds Treatment→Recovery)."""

    def test_confounding_intent_compiles(self):
        """A confounding ClaimIntent should compile to 2 specs."""
        from tests.tools.test_oi_curated_worlds import world_treatment

        world = world_treatment()
        summary = build_world_summary(world, "Recovery", n_mc=20_000, seed=42)

        intent = ClaimIntent(
            claim_id="conf_test",
            pattern=PatternClass.CONFOUNDING,
            treatment="Treatment",
            outcome="Recovery",
            confounder="Severity",
            direction=Direction.POSITIVE,
        )

        output = lower_intent(intent, summary)
        assert output.compiled
        assert len(output.specs) == 2
        assert "confound" in output.specs[0].spec_id

    def test_confounding_family_in_salience_map(self):
        """Treatment world should produce confounding families in salience map."""
        from tests.tools.test_oi_curated_worlds import world_treatment

        world = world_treatment()
        smap = build_salience_map(world, "Recovery", n_mc=20_000, seed=42)
        patterns = {f.key.pattern_class for f in smap.families}
        assert "confounding" in patterns, (
            f"Expected confounding family but only found: {patterns}"
        )

    def test_confounding_claim_scores_nonzero(self):
        """A correct confounding claim should get nonzero score in v2."""
        from sreg.solver.scm_solver import SCMSolver
        from tests.tools.test_oi_curated_worlds import world_treatment

        world = world_treatment()
        solver = SCMSolver(world, n_mc=20_000)
        summary = build_world_summary(world, "Recovery", n_mc=20_000, seed=42)
        smap = build_salience_map(world, "Recovery", n_mc=20_000, seed=42)

        # Compile a confounding claim
        intent = ClaimIntent(
            claim_id="conf_real",
            pattern=PatternClass.CONFOUNDING,
            treatment="Treatment",
            outcome="Recovery",
            confounder="Severity",
            direction=Direction.POSITIVE,
        )
        compiled = lower_intent(intent, summary)
        assert compiled.compiled

        # Score with v2
        score = score_compiled_episode_v2(
            compiled_claims=[compiled],
            families=smap.families,
            world=world,
            solver=solver,
            target="Recovery",
            n_mc=20_000,
            seed=42,
        )

        # The key assertion: confounding claim gets nonzero score
        assert score.correctness > 0, (
            f"Confounding claim should score >0 but got {score.correctness}"
        )
        assert score.total > 0
