"""Tests for OI Evidence Warrant system."""

from __future__ import annotations

import pytest

from sreg.models.open_investigation import (
    WARRANT_PRIOR_FLOOR,
    AnalysisRecord,
    ArtifactAccess,
    ClaimCard,
    EpisodeTrace,
    EvidenceRef,
    SalienceFamily,
    WarrantResult,
)
from sreg.tools.oi_verifier import score_episode
from sreg.tools.oi_warrant import (
    compute_claim_warrant,
    compute_episode_warrants,
    compute_warrant_details,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _claim(
    claim_id: str = "c1",
    artifact_ids: list[str] | None = None,
    focus_vars: list[str] | None = None,
) -> ClaimCard:
    """Create a minimal ClaimCard for testing."""
    if artifact_ids is None:
        artifact_ids = ["dataset_bg"]
    if focus_vars is None:
        focus_vars = ["A", "Y"]
    return ClaimCard(
        claim_id=claim_id,
        claim_text="A has a positive causal effect on Y in this dataset",
        focus_variables=focus_vars,
        confidence=0.8,
        evidence_basis=[
            EvidenceRef(artifact_id=aid, rationale=f"Analysis of {aid} showed the pattern")
            for aid in artifact_ids
        ],
    )


def _trace(
    accesses: list[ArtifactAccess] | None = None,
    analyses: list[AnalysisRecord] | None = None,
    claim_steps: dict[str, int] | None = None,
) -> EpisodeTrace:
    """Create an EpisodeTrace for testing."""
    return EpisodeTrace(
        accesses=accesses or [],
        analyses=analyses or [],
        claim_steps=claim_steps or {},
    )


DATA_ASSETS = {"dataset_bg", "dataset_survey", "dataset_detail"}


# ---------------------------------------------------------------------------
# Trace model tests
# ---------------------------------------------------------------------------


class TestTraceModels:
    def test_empty_trace(self):
        trace = EpisodeTrace()
        assert trace.accessed_artifact_ids() == set()
        assert trace.analyzed_artifact_ids() == set()
        assert trace.derived_artifact_ids() == set()

    def test_access_tracking(self):
        trace = _trace(
            accesses=[
                ArtifactAccess(artifact_id="dataset_bg", step=1),
                ArtifactAccess(artifact_id="dataset_survey", step=3),
            ]
        )
        assert trace.accessed_artifact_ids() == {"dataset_bg", "dataset_survey"}

    def test_analysis_tracking(self):
        trace = _trace(
            analyses=[
                AnalysisRecord(
                    analysis_id="a1",
                    input_artifact_ids=["dataset_bg"],
                    columns_used=["A", "Y", "C"],
                    op_type="regression",
                    step=5,
                    output_artifact_id="result_1",
                ),
            ]
        )
        assert trace.analyzed_artifact_ids() == {"dataset_bg"}
        assert trace.derived_artifact_ids() == {"result_1"}
        assert trace.columns_analyzed_for_artifact("dataset_bg") == {"A", "Y", "C"}
        assert trace.columns_analyzed_for_artifact("other") == set()

    def test_warrant_result_model(self):
        wr = WarrantResult(
            claim_id="c1",
            warrant_score=0.7,
            level_reached=2,
            valid_refs=1,
            accessed_refs=1,
            analyzed_refs=1,
        )
        assert wr.warrant_score == 0.7
        assert wr.level_reached == 2


# ---------------------------------------------------------------------------
# Per-claim warrant computation
# ---------------------------------------------------------------------------


class TestClaimWarrant:
    def test_nonexistent_artifact_gets_zero(self):
        """Referencing a non-existent artifact: warrant = 0."""
        claim = _claim(artifact_ids=["fake_dataset"])
        trace = _trace()
        result = compute_claim_warrant(claim, DATA_ASSETS, trace)
        assert result.warrant_score == 0.0
        assert result.level_reached == 0
        assert result.valid_refs == 0

    def test_exists_but_not_accessed(self):
        """Artifact exists but solver never accessed it: Level 1 = 0.1."""
        claim = _claim(artifact_ids=["dataset_bg"])
        trace = _trace()  # no accesses
        result = compute_claim_warrant(claim, DATA_ASSETS, trace)
        assert result.warrant_score == pytest.approx(0.1)
        assert result.level_reached == 1
        assert result.valid_refs == 1
        assert result.accessed_refs == 0

    def test_accessed_but_no_analysis(self):
        """Solver loaded artifact but didn't analyze it: Level 2 = 0.4."""
        claim = _claim(artifact_ids=["dataset_bg"])
        trace = _trace(
            accesses=[ArtifactAccess(artifact_id="dataset_bg", step=1)]
        )
        result = compute_claim_warrant(claim, DATA_ASSETS, trace)
        assert result.warrant_score == pytest.approx(0.4)
        assert result.level_reached == 2
        assert result.accessed_refs == 1

    def test_analyzed_relevant_columns(self):
        """Analysis touched claim's focus variables: Level 2.5 = 0.7."""
        claim = _claim(focus_vars=["A", "Y"])
        trace = _trace(
            accesses=[ArtifactAccess(artifact_id="dataset_bg", step=1)],
            analyses=[
                AnalysisRecord(
                    analysis_id="a1",
                    input_artifact_ids=["dataset_bg"],
                    columns_used=["A", "Y"],
                    op_type="describe",  # not substantive
                    step=3,
                )
            ],
        )
        result = compute_claim_warrant(claim, DATA_ASSETS, trace)
        assert result.warrant_score == pytest.approx(0.7)
        assert result.analyzed_refs == 1

    def test_substantive_analysis_full_warrant(self):
        """Substantive analysis (regression) on relevant columns: Level 3 = 1.0."""
        claim = _claim(focus_vars=["A", "Y"])
        trace = _trace(
            accesses=[ArtifactAccess(artifact_id="dataset_bg", step=1)],
            analyses=[
                AnalysisRecord(
                    analysis_id="a1",
                    input_artifact_ids=["dataset_bg"],
                    columns_used=["A", "Y", "C"],
                    op_type="regression",
                    step=3,
                )
            ],
        )
        result = compute_claim_warrant(claim, DATA_ASSETS, trace)
        assert result.warrant_score == pytest.approx(1.0)
        assert result.level_reached == 3

    def test_analysis_wrong_columns(self):
        """Analysis exists but on unrelated columns: Level 2 = 0.4."""
        claim = _claim(focus_vars=["A", "Y"])
        trace = _trace(
            accesses=[ArtifactAccess(artifact_id="dataset_bg", step=1)],
            analyses=[
                AnalysisRecord(
                    analysis_id="a1",
                    input_artifact_ids=["dataset_bg"],
                    columns_used=["Z", "W"],  # wrong columns
                    op_type="regression",
                    step=3,
                )
            ],
        )
        result = compute_claim_warrant(claim, DATA_ASSETS, trace)
        assert result.warrant_score == pytest.approx(0.4)
        assert result.level_reached == 2

    def test_max_across_refs(self):
        """With multiple EvidenceRefs, warrant = max (not mean)."""
        claim = _claim(artifact_ids=["dataset_bg", "fake_dataset"])
        trace = _trace(
            accesses=[ArtifactAccess(artifact_id="dataset_bg", step=1)]
        )
        result = compute_claim_warrant(claim, DATA_ASSETS, trace)
        # fake_dataset: 0.0, dataset_bg: 0.4 -> max = 0.4
        assert result.warrant_score == pytest.approx(0.4)
        assert result.valid_refs == 1  # only dataset_bg is valid

    def test_temporal_ordering_enforced(self):
        """Access after claim submission doesn't count."""
        claim = _claim(artifact_ids=["dataset_bg"])
        trace = _trace(
            accesses=[ArtifactAccess(artifact_id="dataset_bg", step=10)],
            claim_steps={"c1": 5},  # claim at step 5, access at step 10
        )
        result = compute_claim_warrant(claim, DATA_ASSETS, trace)
        # Access was after claim → doesn't count → Level 1 only
        assert result.warrant_score == pytest.approx(0.1)
        assert result.level_reached == 1

    def test_derived_artifacts_valid(self):
        """Derived artifacts (from solver analyses) count as valid."""
        claim = _claim(artifact_ids=["derived_1"])
        trace = _trace(
            accesses=[
                ArtifactAccess(artifact_id="dataset_bg", step=1),
                ArtifactAccess(artifact_id="derived_1", step=3),
            ],
            analyses=[
                AnalysisRecord(
                    analysis_id="a1",
                    input_artifact_ids=["dataset_bg"],
                    columns_used=["A"],
                    op_type="filter",
                    step=2,
                    output_artifact_id="derived_1",
                ),
                AnalysisRecord(
                    analysis_id="a2",
                    input_artifact_ids=["derived_1"],
                    columns_used=["A", "Y"],
                    op_type="regression",
                    step=4,
                ),
            ],
        )
        # "derived_1" is not in DATA_ASSETS but is in trace.derived_artifact_ids()
        result = compute_claim_warrant(claim, DATA_ASSETS, trace)
        assert result.warrant_score >= 0.4  # at least accessed

    def test_operational_ops_not_substantive(self):
        """plot, filter, merge, pivot are NOT substantive (Codex review)."""
        for op in ["plot", "filter", "merge", "pivot", "describe"]:
            claim = _claim(focus_vars=["A", "Y"])
            trace = _trace(
                accesses=[ArtifactAccess(artifact_id="dataset_bg", step=1)],
                analyses=[
                    AnalysisRecord(
                        analysis_id="a1",
                        input_artifact_ids=["dataset_bg"],
                        columns_used=["A", "Y"],
                        op_type=op,
                        step=3,
                    )
                ],
            )
            result = compute_claim_warrant(claim, DATA_ASSETS, trace)
            assert result.warrant_score == pytest.approx(0.7), (
                f"op_type '{op}' should NOT reach Level 3"
            )

    def test_cross_analysis_not_combined(self):
        """describe(A,Y) + regression(Z,W) should NOT combine to full warrant.

        Per Codex review: Level 3 requires a SINGLE analysis that is both
        relevant and substantive. Cross-analysis combining is forbidden.
        """
        claim = _claim(focus_vars=["A", "Y"])
        trace = _trace(
            accesses=[ArtifactAccess(artifact_id="dataset_bg", step=1)],
            analyses=[
                AnalysisRecord(
                    analysis_id="a1",
                    input_artifact_ids=["dataset_bg"],
                    columns_used=["A", "Y"],  # relevant columns
                    op_type="describe",  # NOT substantive
                    step=2,
                ),
                AnalysisRecord(
                    analysis_id="a2",
                    input_artifact_ids=["dataset_bg"],
                    columns_used=["Z", "W"],  # WRONG columns
                    op_type="regression",  # substantive but wrong columns
                    step=3,
                ),
            ],
        )
        result = compute_claim_warrant(claim, DATA_ASSETS, trace)
        # Neither analysis is both relevant AND substantive → Level 2.5 max
        assert result.warrant_score == pytest.approx(0.7)
        assert result.level_reached < 3

    def test_compiled_focus_vars_override(self):
        """compiled_focus_vars takes precedence over claim.focus_variables."""
        claim = _claim(focus_vars=["X", "Z"])  # claim says X,Z
        trace = _trace(
            accesses=[ArtifactAccess(artifact_id="dataset_bg", step=1)],
            analyses=[
                AnalysisRecord(
                    analysis_id="a1",
                    input_artifact_ids=["dataset_bg"],
                    columns_used=["A", "Y"],  # matches compiled, not claim
                    op_type="correlation",
                    step=3,
                )
            ],
        )
        # Without override: columns [A,Y] don't match focus [X,Z] → Level 2
        result_no_override = compute_claim_warrant(claim, DATA_ASSETS, trace)
        assert result_no_override.warrant_score == pytest.approx(0.4)

        # With override: columns [A,Y] match compiled focus {A,Y} → Level 3
        result_override = compute_claim_warrant(
            claim, DATA_ASSETS, trace, compiled_focus_vars={"A", "Y"}
        )
        assert result_override.warrant_score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Episode-level warrant computation
# ---------------------------------------------------------------------------


class TestEpisodeWarrants:
    def test_none_trace_returns_none(self):
        """No trace → warrant disabled → returns None."""
        claims = [_claim()]
        result = compute_episode_warrants(claims, DATA_ASSETS, trace=None)
        assert result is None

    def test_multiple_claims(self):
        """Each claim gets its own warrant score."""
        claims = [
            _claim("c1", artifact_ids=["dataset_bg"]),
            _claim("c2", artifact_ids=["dataset_survey"]),
        ]
        trace = _trace(
            accesses=[
                ArtifactAccess(artifact_id="dataset_bg", step=1),
                # dataset_survey NOT accessed
            ]
        )
        warrants = compute_episode_warrants(claims, DATA_ASSETS, trace)
        assert warrants is not None
        assert len(warrants) == 2
        assert warrants[0] > warrants[1]  # c1 accessed, c2 not

    def test_details_returns_full_results(self):
        """compute_warrant_details returns WarrantResult objects."""
        claims = [_claim("c1")]
        trace = _trace(
            accesses=[ArtifactAccess(artifact_id="dataset_bg", step=1)]
        )
        details = compute_warrant_details(claims, DATA_ASSETS, trace)
        assert len(details) == 1
        assert isinstance(details[0], WarrantResult)
        assert details[0].claim_id == "c1"


# ---------------------------------------------------------------------------
# Scoring integration — warrant affects correctness + coverage
# ---------------------------------------------------------------------------


class TestScoringIntegration:
    def _dummy_families(self, n: int = 3) -> list[SalienceFamily]:
        """Create dummy families for scoring tests."""
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
        )

        families = []
        for i in range(n):
            fid = f"fam_{i}"
            families.append(
                SalienceFamily(
                    family_id=fid,
                    key=FamilyKey(
                        brief_target="Y",
                        focus_signature=(f"V{i}",),
                        pattern_class="causal_effect",
                    ),
                    atoms=(
                        FamilyAtom(
                            atom_id=f"a_{i}",
                            spec=AtomicSpec(
                                spec_id=f"s_{i}",
                                arms=(
                                    QueryArm(
                                        label="hi", kind=QueryKind.INTERVENE,
                                        values={f"V{i}": 1.0},
                                    ),
                                    QueryArm(
                                        label="lo", kind=QueryKind.INTERVENE,
                                        values={f"V{i}": 0.0},
                                    ),
                                ),
                                measurement=Measurement(kind=MeasurementKind.MEAN, target="Y"),
                                comparison=Comparison(kind=ComparisonKind.DIFFERENCE),
                                assertion=Assertion(kind=AssertionKind.POSITIVE),
                            ),
                        ),
                    ),
                    salience=0.8,
                )
            )
        return families

    def test_no_warrant_backward_compatible(self):
        """Without warrant_scores, scoring works as before."""
        families = self._dummy_families(3)
        claim_matches = [("fam_0", 0.8), ("fam_1", 0.9)]
        episode = score_episode(claim_matches, families, n_claims=2)

        assert not episode.warrant_active
        assert episode.raw_correctness is None
        assert episode.avg_warrant is None
        assert episode.correctness == pytest.approx(0.85)

    def test_full_warrant_no_change(self):
        """With warrant_scores all 1.0, scores identical to no-warrant."""
        families = self._dummy_families(3)
        claim_matches = [("fam_0", 0.8), ("fam_1", 0.9)]

        base = score_episode(claim_matches, families, n_claims=2)
        warranted = score_episode(
            claim_matches, families, n_claims=2,
            warrant_scores=[1.0, 1.0],
        )

        assert warranted.warrant_active
        assert warranted.correctness == pytest.approx(base.correctness)
        assert warranted.coverage == base.coverage
        assert warranted.avg_warrant == pytest.approx(1.0)
        assert warranted.raw_correctness == pytest.approx(0.85)

    def test_zero_warrant_reduces_correctness(self):
        """With warrant_scores all 0.0, correctness is scaled to prior_floor."""
        families = self._dummy_families(3)
        claim_matches = [("fam_0", 1.0), ("fam_1", 1.0)]

        episode = score_episode(
            claim_matches, families, n_claims=2,
            warrant_scores=[0.0, 0.0],
        )

        assert episode.warrant_active
        # effective = 1.0 * (0.15 + 0.85 * 0.0) = 0.15
        assert episode.correctness == pytest.approx(WARRANT_PRIOR_FLOOR)
        assert episode.raw_correctness == pytest.approx(1.0)
        assert episode.avg_warrant == pytest.approx(0.0)

    def test_mixed_warrants(self):
        """Mixed warrants: one backed, one not."""
        families = self._dummy_families(3)
        claim_matches = [("fam_0", 1.0), ("fam_1", 1.0)]

        episode = score_episode(
            claim_matches, families, n_claims=2,
            warrant_scores=[1.0, 0.0],
        )

        # c1: 1.0 * (0.15 + 0.85 * 1.0) = 1.0
        # c2: 1.0 * (0.15 + 0.85 * 0.0) = 0.15
        expected_correctness = (1.0 + WARRANT_PRIOR_FLOOR) / 2
        assert episode.correctness == pytest.approx(expected_correctness)

    def test_warrant_affects_coverage(self):
        """Low warrant can push effective score below family hit threshold."""
        families = self._dummy_families(3)
        # truth_score = 0.7, which is above FAMILY_HIT_THRESHOLD (0.6)
        claim_matches = [("fam_0", 0.7)]

        # Without warrant: fam_0 hit (0.7 >= 0.6)
        base = score_episode(claim_matches, families, n_claims=1)
        assert base.families_hit == 1

        # With zero warrant: effective = 0.7 * 0.15 = 0.105 < 0.6
        warranted = score_episode(
            claim_matches, families, n_claims=1,
            warrant_scores=[0.0],
        )
        assert warranted.families_hit == 0
        assert warranted.coverage == 0.0

    def test_custom_prior_floor(self):
        """Custom prior_floor is respected."""
        families = self._dummy_families(1)
        claim_matches = [("fam_0", 1.0)]

        episode = score_episode(
            claim_matches, families, n_claims=1,
            warrant_scores=[0.0],
            prior_floor=0.5,
        )
        # effective = 1.0 * (0.5 + 0.5 * 0.0) = 0.5
        assert episode.correctness == pytest.approx(0.5)

    def test_warrant_length_mismatch_raises(self):
        """Mismatched warrant_scores length raises ValueError."""
        families = self._dummy_families(1)
        claim_matches = [("fam_0", 1.0)]

        with pytest.raises(ValueError, match="warrant_scores length"):
            score_episode(
                claim_matches, families, n_claims=1,
                warrant_scores=[0.5, 0.5],  # 2 warrants for 1 claim
            )


# ---------------------------------------------------------------------------
# Integration scenario: full warrant pipeline
# ---------------------------------------------------------------------------


class TestWarrantPipeline:
    def test_prior_solver_vs_investigator(self):
        """Prior-only solver scores much lower than investigating solver."""
        families_list = TestScoringIntegration._dummy_families(
            TestScoringIntegration(), n=3
        )
        # Both solvers get same truth scores (both correct!)
        claim_matches = [("fam_0", 0.9), ("fam_1", 0.85), ("fam_2", 0.8)]

        # Prior-only solver: no evidence
        prior_score = score_episode(
            claim_matches, families_list, n_claims=3,
            warrant_scores=[0.0, 0.0, 0.0],
        )

        # Investigating solver: full evidence
        invest_score = score_episode(
            claim_matches, families_list, n_claims=3,
            warrant_scores=[1.0, 1.0, 1.0],
        )

        # Investigating solver should score MUCH higher
        assert invest_score.total > prior_score.total
        assert invest_score.total > 2 * prior_score.total  # at least 2x
        assert invest_score.correctness > prior_score.correctness

        # Prior solver gets only floor credit
        floor = WARRANT_PRIOR_FLOOR
        expected_prior_correctness = sum(
            s * floor for _, s in claim_matches
        ) / 3
        assert prior_score.correctness == pytest.approx(expected_prior_correctness)

    def test_partial_investigation_intermediate_score(self):
        """Partial evidence gives intermediate score."""
        families_list = TestScoringIntegration._dummy_families(
            TestScoringIntegration(), n=3
        )
        claim_matches = [("fam_0", 0.9), ("fam_1", 0.9), ("fam_2", 0.9)]

        prior = score_episode(
            claim_matches, families_list, n_claims=3,
            warrant_scores=[0.0, 0.0, 0.0],
        )
        partial = score_episode(
            claim_matches, families_list, n_claims=3,
            warrant_scores=[1.0, 0.4, 0.0],
        )
        full = score_episode(
            claim_matches, families_list, n_claims=3,
            warrant_scores=[1.0, 1.0, 1.0],
        )

        assert prior.total < partial.total < full.total
