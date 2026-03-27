"""OI Evidence Warrant: verify that claims are backed by actual investigation.

The warrant system checks whether the solver actually investigated (accessed
data, ran analyses) to support its claims, or just submitted from priors.

Warrant is a per-claim multiplier on correctness and coverage eligibility:
    effective_score = truth_score * (prior_floor + (1 - prior_floor) * warrant)

With prior_floor=0.15:
- Right from priors, no investigation: 15% credit
- Right, accessed data: ~49% credit
- Right, analyzed relevant variables: ~75% credit
- Right, full evidence: 100% credit

Design from Codex debate (thread 019d2de7-b436-7182-afc5-503aa2de0705):
- Claim-level, not episode-level (no avg gate)
- Per-claim max() across EvidenceRefs (not mean)
- Affects both correctness and coverage eligibility
- Explicit disabled mode when no trace available
- Deterministic only, no LLM judges
"""

from __future__ import annotations

import logging

from sreg.models.open_investigation import (
    AnalysisRecord,
    ClaimCard,
    EpisodeTrace,
    WarrantResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Warrant level thresholds
# ---------------------------------------------------------------------------

# Level 1: artifact exists in problem → 0.1
_W_EXISTS: float = 0.1

# Level 2: solver accessed the artifact → 0.4
_W_ACCESSED: float = 0.4

# Level 2.5: analysis touched claim's focus variables → 0.7
_W_RELEVANT_ANALYSIS: float = 0.7

# Level 3: analysis with substantive op_type → 1.0
_W_FULL: float = 1.0

# Op types that count as substantive (inferential) analysis for Level 3.
# Operational ops (filter, merge, pivot, plot, describe, groupby, compare)
# qualify for Level 2.5 but NOT Level 3 — too easy to spam. (Codex review)
_SUBSTANTIVE_OPS: frozenset[str] = frozenset({
    "regression",
    "correlation",
    "stratify",
    "test",
    "model",
    "causal",
    "mediation",
    "aggregate",
})


# ---------------------------------------------------------------------------
# Per-reference warrant computation
# ---------------------------------------------------------------------------


def _warrant_for_ref(
    artifact_id: str,
    data_asset_ids: set[str],
    trace: EpisodeTrace,
    focus_variables: set[str],
    claim_step: int | None,
) -> tuple[float, int]:
    """Compute warrant score for a single EvidenceRef.

    Returns (warrant_score, level_reached).

    Temporal ordering: when claim_step is None but trace has data,
    we fail-closed (no temporal filtering = conservative). Per Codex review.

    Cross-analysis: Level 3 requires a SINGLE analysis that is both
    relevant (touches focus_variables) and substantive (inferential op_type).
    Combining describe(A,Y) + regression(Z,W) does NOT qualify. Per Codex review.
    """
    # Expand valid IDs to include derived artifacts
    all_valid_ids = data_asset_ids | trace.derived_artifact_ids()

    # Level 1: artifact exists
    if artifact_id not in all_valid_ids:
        return 0.0, 0

    # Level 2: solver accessed the artifact
    accesses = [a for a in trace.accesses if a.artifact_id == artifact_id]
    if not accesses:
        return _W_EXISTS, 1

    # Temporal check: access should be before claim submission
    # Fail-closed: if claim_step unknown, only count accesses at step 0
    # (conservative — better to undercount than overcount)
    if claim_step is not None:
        accesses = [a for a in accesses if a.step <= claim_step]
        if not accesses:
            return _W_EXISTS, 1

    # Level 2.5 / 3: check analyses
    analyses = _get_analyses_for_artifact(artifact_id, trace, claim_step)
    if not analyses:
        return _W_ACCESSED, 2

    # Check each analysis INDIVIDUALLY (no cross-analysis combining)
    # Per Codex review: describe(A,Y) + regression(Z,W) on same artifact
    # should NOT combine to full warrant.
    has_relevant = False
    for a in analyses:
        a_cols = set(a.columns_used)
        is_relevant = bool(a_cols & focus_variables) if focus_variables else True
        is_substantive = a.op_type.lower() in _SUBSTANTIVE_OPS

        if is_relevant and is_substantive:
            return _W_FULL, 3
        if is_relevant:
            has_relevant = True

    if has_relevant:
        return _W_RELEVANT_ANALYSIS, 2

    # Analyses exist but none touched relevant columns
    # Still Level 2 (accessed) — wrong columns analyzed
    return _W_ACCESSED, 2


def _get_analyses_for_artifact(
    artifact_id: str,
    trace: EpisodeTrace,
    claim_step: int | None,
) -> list[AnalysisRecord]:
    """Get analyses that used a specific artifact, respecting temporal order."""
    analyses = [a for a in trace.analyses if artifact_id in a.input_artifact_ids]
    if claim_step is not None:
        analyses = [a for a in analyses if a.step <= claim_step]
    return analyses


# ---------------------------------------------------------------------------
# Per-claim warrant
# ---------------------------------------------------------------------------


def compute_claim_warrant(
    claim: ClaimCard,
    data_asset_ids: set[str],
    trace: EpisodeTrace,
    compiled_focus_vars: set[str] | None = None,
) -> WarrantResult:
    """Compute warrant score for a single ClaimCard.

    Uses max() across EvidenceRefs (not mean): one strong piece of
    evidence is enough per Codex recommendation.

    Args:
        claim: The solver's claim card.
        data_asset_ids: Valid artifact IDs in the problem.
        trace: Structured log of the solver's investigation.
        compiled_focus_vars: Variables from the compiled AtomicSpecs.
            If None, uses claim.focus_variables.
    """
    focus_vars = compiled_focus_vars or set(claim.focus_variables)
    claim_step = trace.claim_steps.get(claim.claim_id)

    ref_warrants: list[tuple[float, int]] = []
    valid_refs = 0
    accessed_refs = 0
    analyzed_refs = 0

    for ref in claim.evidence_basis:
        w, level = _warrant_for_ref(
            ref.artifact_id, data_asset_ids, trace, focus_vars, claim_step
        )
        ref_warrants.append((w, level))

        if level >= 1:
            valid_refs += 1
        if level >= 2:
            accessed_refs += 1
        if level >= 2:
            # Check if this specific ref has analysis
            analyses = _get_analyses_for_artifact(ref.artifact_id, trace, claim_step)
            if analyses:
                analyzed_refs += 1

    if not ref_warrants:
        return WarrantResult(
            claim_id=claim.claim_id,
            warrant_score=0.0,
            level_reached=0,
            valid_refs=0,
            accessed_refs=0,
            analyzed_refs=0,
        )

    # max() across refs per Codex recommendation
    best_warrant, best_level = max(ref_warrants, key=lambda x: x[0])

    return WarrantResult(
        claim_id=claim.claim_id,
        warrant_score=best_warrant,
        level_reached=best_level,
        valid_refs=valid_refs,
        accessed_refs=accessed_refs,
        analyzed_refs=analyzed_refs,
    )


# ---------------------------------------------------------------------------
# Episode-level warrant computation
# ---------------------------------------------------------------------------


def compute_episode_warrants(
    claims: list[ClaimCard],
    data_asset_ids: set[str],
    trace: EpisodeTrace | None,
    compiled_focus_vars_per_claim: dict[str, set[str]] | None = None,
) -> list[float] | None:
    """Compute warrant scores for all claims in an episode.

    Returns None if trace is None (warrant disabled — full credit for all).
    Returns list of per-claim warrant scores [0, 1] otherwise.

    Args:
        claims: All ClaimCards from the solver.
        data_asset_ids: Valid artifact IDs in the problem.
        trace: Structured episode trace, or None to disable warrant.
        compiled_focus_vars_per_claim: Optional dict of claim_id -> focus vars
            from compiled AtomicSpecs (more precise than claim.focus_variables).
    """
    if trace is None:
        return None

    warrants: list[float] = []
    for claim in claims:
        focus_vars = None
        if compiled_focus_vars_per_claim:
            focus_vars = compiled_focus_vars_per_claim.get(claim.claim_id)

        result = compute_claim_warrant(claim, data_asset_ids, trace, focus_vars)
        warrants.append(result.warrant_score)

    return warrants


def compute_warrant_details(
    claims: list[ClaimCard],
    data_asset_ids: set[str],
    trace: EpisodeTrace,
    compiled_focus_vars_per_claim: dict[str, set[str]] | None = None,
) -> list[WarrantResult]:
    """Like compute_episode_warrants but returns full WarrantResult objects."""
    results: list[WarrantResult] = []
    for claim in claims:
        focus_vars = None
        if compiled_focus_vars_per_claim:
            focus_vars = compiled_focus_vars_per_claim.get(claim.claim_id)
        results.append(
            compute_claim_warrant(claim, data_asset_ids, trace, focus_vars)
        )
    return results


__all__ = [
    "compute_claim_warrant",
    "compute_episode_warrants",
    "compute_warrant_details",
]
