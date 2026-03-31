"""SQ v2 matching: claim-specs vs SQ-specs.

Implements the matching algorithm from sq_v2_matching_spec.md:
- spec_match(): exact on estimand, fuzzy on assertion
- claim_covers_sq(): bipartite 1-to-1 matching with required/support
- score_episode_v2(): episode-level SQ scoring

Design principles:
- Exact match on estimand (measurement kind + primary vars + conditioning set)
- Fuzzy ONLY on assertion (positive/negative/near_zero compatibility)
- Bipartite 1-to-1: one claim-spec covers at most one SQ-spec
- Required specs must be covered for SQ satisfaction; support gives bonus
"""

from __future__ import annotations

import logging

from sreg.models.open_investigation import (
    AssertionKind,
    AtomicSpec,
    AtomVerdict,
    SubQuestionIntentV2,
    VerificationSpec,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Variable extraction helpers
# ---------------------------------------------------------------------------


def primary_vars(spec: AtomicSpec) -> frozenset[str]:
    """Extract primary variables from a spec's measurement."""
    m = spec.measurement
    vs: set[str] = set()
    if m.target:
        if isinstance(m.target, tuple):
            vs.update(m.target)
        else:
            vs.add(m.target)
    if m.lhs:
        vs.add(m.lhs)
    if m.rhs:
        vs.add(m.rhs)
    if m.treatment:
        vs.add(m.treatment)
    if m.outcome:
        vs.add(m.outcome)
    return frozenset(vs)


def conditioning_set(spec: AtomicSpec) -> frozenset[str]:
    """Extract conditioning set from a spec's measurement."""
    return frozenset(spec.measurement.cond_set) if spec.measurement.cond_set else frozenset()


# ---------------------------------------------------------------------------
# Assertion compatibility
# ---------------------------------------------------------------------------

# Directional assertions (positive, negative, greater_than, less_than)
_POSITIVE_DIR = {AssertionKind.POSITIVE, AssertionKind.GREATER_THAN}
_NEGATIVE_DIR = {AssertionKind.NEGATIVE, AssertionKind.LESS_THAN}
_DIRECTIONAL = _POSITIVE_DIR | _NEGATIVE_DIR
_ZERO = {AssertionKind.NEAR_ZERO}


def assertion_compat(claim_kind: AssertionKind, sq_kind: AssertionKind) -> float:
    """Soft compatibility between assertion kinds.

    Returns:
        1.0 — same kind
        0.8 — compatible direction (positive ~ greater_than)
        0.0 — contradictory or incompatible
    """
    if claim_kind == sq_kind:
        return 1.0

    # Same directional family
    if claim_kind in _POSITIVE_DIR and sq_kind in _POSITIVE_DIR:
        return 0.8
    if claim_kind in _NEGATIVE_DIR and sq_kind in _NEGATIVE_DIR:
        return 0.8

    # Contradictory: positive vs negative
    if (claim_kind in _POSITIVE_DIR and sq_kind in _NEGATIVE_DIR) or \
       (claim_kind in _NEGATIVE_DIR and sq_kind in _POSITIVE_DIR):
        return 0.0

    # near_zero vs directional = incompatible
    if (claim_kind in _ZERO and sq_kind in _DIRECTIONAL) or \
       (claim_kind in _DIRECTIONAL and sq_kind in _ZERO):
        return 0.0

    # Non-directional assertions (rank_order, changepoint, sign_flip, etc.)
    # Only match exact
    return 0.0


# ---------------------------------------------------------------------------
# Spec-level matching
# ---------------------------------------------------------------------------


def spec_match(claim_spec: AtomicSpec, sq_spec: AtomicSpec,
               claim_verdict: AtomVerdict | None = None,
               sq_verdict: AtomVerdict | None = None) -> float:
    """Match a single claim-spec against a single SQ-spec.

    Hard gates on estimand (measurement kind, primary vars, conditioning set).
    Soft score on assertion compatibility.

    Args:
        claim_spec: spec compiled from a solver claim
        sq_spec: spec from the SQ's verification bundle
        claim_verdict: verdict of claim_spec against SCM (if available)
        sq_verdict: verdict of sq_spec against SCM (if available)

    Returns:
        0.0-1.0 match score
    """
    # Hard gate: measurement kind
    if claim_spec.measurement.kind != sq_spec.measurement.kind:
        return 0.0

    # Hard gate: primary variables
    if primary_vars(claim_spec) != primary_vars(sq_spec):
        return 0.0

    # Hard gate: conditioning set
    if conditioning_set(claim_spec) != conditioning_set(sq_spec):
        return 0.0

    # Hard gate: claim must be verified TRUE (if verdict available)
    if claim_verdict is not None and not claim_verdict.solver_assertion_holds:
        return 0.0

    # SQ spec FALSE in ground truth — skip, don't penalize
    if sq_verdict is not None and not sq_verdict.solver_assertion_holds:
        return 0.0

    # Soft score: assertion compatibility
    return assertion_compat(claim_spec.assertion.kind, sq_spec.assertion.kind)


# ---------------------------------------------------------------------------
# Bipartite 1-to-1 matching (Hungarian-style, small N)
# ---------------------------------------------------------------------------


def _bipartite_max_weight(
    claim_specs: list[tuple[AtomicSpec, AtomVerdict | None, ...]],
    sq_vspecs: list[VerificationSpec],
) -> dict[int, tuple[int, float]]:
    """Optimal 1-to-1 matching between claim-specs and SQ-specs.

    Returns dict: sq_idx -> (claim_pool_idx, score).
    Uses brute-force for small N (SQ bundles are typically 2-5 specs).
    claim_specs tuples may have extra elements (e.g. claim index) that are ignored.
    """
    n_claims = len(claim_specs)
    n_sq = len(sq_vspecs)

    if n_claims == 0 or n_sq == 0:
        return {}

    # Build cost matrix (only first 2 elements of tuple matter for matching)
    scores: list[list[float]] = []
    for si, vs in enumerate(sq_vspecs):
        row = []
        for ci, cs in enumerate(claim_specs):
            cspec, cverdict = cs[0], cs[1]
            row.append(spec_match(cspec, vs.spec, cverdict, vs.verdict))
        scores.append(row)

    # For small N, brute-force all permutations
    # Typical: 1-5 SQ specs, 1-15 claim specs => manageable
    if n_sq <= 8 and n_claims <= 15:
        return _brute_force_match(scores, n_sq, n_claims)

    # Fallback: greedy (good enough for larger cases)
    return _greedy_match(scores, n_sq, n_claims)


def _brute_force_match(
    scores: list[list[float]], n_sq: int, n_claims: int
) -> dict[int, tuple[int, float]]:
    """Brute-force optimal matching for small N."""
    best_total = -1.0
    best_assignment: dict[int, tuple[int, float]] = {}

    # Generate all possible assignments of claim indices to SQ indices
    # Each SQ can be matched to at most one claim, and vice versa
    claim_indices = list(range(n_claims))

    def _search(sq_idx: int, used: set[int],
                current: dict[int, tuple[int, float]], total: float) -> None:
        nonlocal best_total, best_assignment

        if sq_idx == n_sq:
            if total > best_total:
                best_total = total
                best_assignment = dict(current)
            return

        # Option: don't match this SQ
        _search(sq_idx + 1, used, current, total)

        # Option: match to each unused claim
        for ci in claim_indices:
            if ci in used:
                continue
            s = scores[sq_idx][ci]
            if s > 0:
                used.add(ci)
                current[sq_idx] = (ci, s)
                _search(sq_idx + 1, used, current, total + s)
                del current[sq_idx]
                used.discard(ci)

    _search(0, set(), {}, 0.0)
    return best_assignment


def _greedy_match(
    scores: list[list[float]], n_sq: int, n_claims: int
) -> dict[int, tuple[int, float]]:
    """Greedy matching fallback for larger inputs."""
    # Collect all (score, sq_idx, claim_idx) triples
    triples = []
    for si in range(n_sq):
        for ci in range(n_claims):
            s = scores[si][ci]
            if s > 0:
                triples.append((s, si, ci))

    triples.sort(reverse=True)

    used_sq: set[int] = set()
    used_claim: set[int] = set()
    result: dict[int, tuple[int, float]] = {}

    for s, si, ci in triples:
        if si in used_sq or ci in used_claim:
            continue
        result[si] = (ci, s)
        used_sq.add(si)
        used_claim.add(ci)

    return result


# ---------------------------------------------------------------------------
# SQ satisfaction
# ---------------------------------------------------------------------------


def claim_covers_sq(
    claim_specs: list[tuple[AtomicSpec, AtomVerdict | None, int]],
    sq: SubQuestionIntentV2,
) -> tuple[float, set[int]]:
    """How well a pool of claim-specs covers a single SQ.

    Args:
        claim_specs: list of (spec, verdict, claim_index) from ALL claims pooled
        sq: the sub-question to match against

    Returns:
        (satisfaction 0.0-1.0, set of claim indices that contributed)
    """
    matches = _bipartite_max_weight(claim_specs, sq.verification_specs)

    # Required coverage
    required_indices = [i for i, vs in enumerate(sq.verification_specs)
                        if vs.role == "required"]
    if not required_indices:
        return 0.0, set()

    required_covered = sum(1 for ri in required_indices if ri in matches and matches[ri][1] > 0)
    required_coverage = required_covered / len(required_indices)

    # Support bonus
    support_indices = [i for i, vs in enumerate(sq.verification_specs)
                       if vs.role == "support"]
    support_bonus = 0.0
    if support_indices:
        support_covered = sum(1 for si in support_indices
                              if si in matches and matches[si][1] > 0)
        support_bonus = (support_covered / len(support_indices)) * 0.2

    # Track which claims contributed
    contributing_claims = set()
    for sq_idx, (claim_idx, score) in matches.items():
        if score > 0:
            # claim_idx indexes into claim_specs, which carries the original claim index
            contributing_claims.add(claim_specs[claim_idx][2])

    return min(1.0, required_coverage + support_bonus), contributing_claims


# ---------------------------------------------------------------------------
# Episode-level scoring
# ---------------------------------------------------------------------------


def score_episode_sqs_v2(
    sqs: list[SubQuestionIntentV2],
    all_claim_specs: list[list[tuple[AtomicSpec, AtomVerdict | None]]],
) -> dict:
    """Score an episode using v2 SQ matching.

    Pools ALL claim-specs together before matching against each SQ.
    This avoids penalizing solvers who spread findings across claims.

    Args:
        sqs: the episode's sub-questions (v2)
        all_claim_specs: for each claim, its compiled (spec, verdict) pairs

    Returns:
        dict with: sq_scores, coverage, weighted_coverage, correctness,
        novel_bonus, total
    """
    if not sqs:
        return {
            "sq_scores": [],
            "coverage": 0.0,
            "weighted_coverage": 0.0,
            "correctness": 0.0,
            "novel_bonus": 0.0,
            "total": 0.0,
        }

    # Pool all specs with claim index for traceability
    pooled: list[tuple[AtomicSpec, AtomVerdict | None, int]] = []
    for ci, claim in enumerate(all_claim_specs):
        for spec, verdict in claim:
            pooled.append((spec, verdict, ci))

    # Per-SQ satisfaction against the full pool
    sq_scores = []
    all_contributing: set[int] = set()
    for sq in sqs:
        sat, contributing = claim_covers_sq(pooled, sq)
        all_contributing.update(contributing)
        sq_scores.append({
            "sq_id": sq.sq_id,
            "satisfaction": sat,
            "contributing_claims": sorted(contributing),
        })

    # Aggregation
    n_sqs = len(sqs)
    coverage = sum(1 for s in sq_scores if s["satisfaction"] > 0) / n_sqs
    total_weight = sum(sq.weight for sq in sqs)
    weighted_coverage = (
        sum(s["satisfaction"] * sq.weight for s, sq in zip(sq_scores, sqs))
        / total_weight
        if total_weight > 0
        else 0.0
    )

    # Correctness: truth rate of claims that contributed to matching
    if all_contributing:
        truth_rates = []
        for ci in all_contributing:
            claim = all_claim_specs[ci]
            if claim:
                true_count = sum(1 for _, v in claim if v and v.solver_assertion_holds)
                truth_rates.append(true_count / len(claim))
        correctness = sum(truth_rates) / len(truth_rates) if truth_rates else 0.0
    else:
        correctness = 0.0

    # Novel bonus placeholder — full implementation when integrated with pipeline
    novel_bonus = 0.0

    total = (
        weighted_coverage * 0.70
        + correctness * 0.20
        + novel_bonus
        + coverage * 0.10
    )

    return {
        "sq_scores": sq_scores,
        "coverage": coverage,
        "weighted_coverage": weighted_coverage,
        "correctness": correctness,
        "novel_bonus": novel_bonus,
        "total": min(1.0, total),
    }
