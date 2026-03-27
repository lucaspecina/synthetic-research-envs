# OI Evidence Warrant System — Design Note

**Date:** 2026-03-27
**Context:** Alpha-0 works. Issue #5: evidence_basis not used in scoring.
A solver can win from domain priors without investigating. This is the
purest form of LA PREGUNTA.
**Codex thread:** 019d2de7-b436-7182-afc5-503aa2de0705

## The Problem

The ClaimCard has `evidence_basis: list[EvidenceRef]` (required, min 1).
Each EvidenceRef has `artifact_id` + `rationale`. But `score_episode()`
ignores evidence_basis entirely. A solver that never touches data can
submit correct claims from priors and get full credit.

**This defeats the purpose of Open Investigation.** If you don't need
data to win, it's not research — it's a knowledge quiz.

## Design Principles

1. **Warrant is about PROCESS, not truth.** The SCM verification stays
   exact (Principle #2). Warrant checks whether the solver EARNED the
   right to make the claim through investigation.

2. **Deterministic only.** No LLM judges in the warrant check. We can
   verify: artifact exists, was accessed, was analyzed, and analysis
   touched relevant variables. We CANNOT verify: analysis was "good"
   or "relevant" — that needs semantic understanding.

3. **Claim-level, not episode-level.** Each claim gets its own warrant
   score. No averaging across claims for a gate — that punishes mixed
   episodes unfairly (Codex).

4. **Affects both correctness AND coverage.** A claim with low warrant
   shouldn't count toward family coverage either — it didn't discover
   the family through investigation (Codex recommendation).

5. **Explicit disabled mode.** When no trace is available (testing,
   backward compat), warrant is explicitly off — no silent penalty.

## Codex Debate Summary

**Thread:** 019d2de7-b436-7182-afc5-503aa2de0705

### Agreements
- Multiplier approach (not separate axis, not hard gate)
- prior_floor = 0.15 (correct from priors = 15% credit, not 0%)
- Warrant affects both correctness and coverage eligibility
- Per-claim max() for multiple EvidenceRefs, not mean
- Keep confidence/calibration separate from warrant
- Doesn't violate "exact SCM verification" principle
- Structured trace with timestamps + metadata, not set[str]

### Codex additions to my design
- Level 1 (artifact exists) should pay almost nothing — it's citation
  hygiene, not evidence
- Missing Level 2.5: temporal ordering (access before claim), variable
  binding (focus_vars in columns_used), op_type compatibility
- Don't score rationale string — add structured fields instead
- df.describe() gaming is acceptable Alpha floor, not final
- Need support for derived artifacts (solver creates filtered subsets)
- Report raw_correctness + avg_warrant as diagnostic metrics

### Disagreement / tension
- None significant. Codex pushed for stricter design which I accept.

## Warrant Levels

| Level | Check | Warrant | What it means |
|-------|-------|---------|---------------|
| 0 | No evidence_basis | 0.0 | Blocked by Pydantic (min_length=1) |
| 1 | artifact_id exists in problem | 0.1 | Citation hygiene only |
| 2 | Solver accessed artifact during episode | 0.4 | Looked at the data |
| 2.5 | Analysis touched claim's focus_variables | 0.7 | Analyzed relevant columns |
| 3 | Analysis with compatible op_type for claim pattern | 1.0 | Full evidence |

**Aggregation per claim:** `max(ref_warrants)` across all EvidenceRefs.
Rationale: one strong piece of evidence is enough; mean penalizes
breadth of citation.

## Scoring Integration

```
effective_i = truth_i * (prior_floor + (1 - prior_floor) * warrant_i)

correctness = mean(effective_i)
coverage = families where max(effective_i) >= FAMILY_HIT_THRESHOLD
```

With `prior_floor = 0.15`:
- Right from priors, no data: 15% credit
- Right, looked at data: 15% + 85%*0.4 = 49% credit
- Right, analyzed relevant vars: 15% + 85%*0.7 = 74.5% credit
- Right, full evidence: 100% credit

**Diagnostic fields added to EpisodeScore:**
- `raw_correctness`: before warrant multiplier
- `avg_warrant`: mean warrant across claims
- `warrant_active`: bool

## Episode Trace Model

The solver's interaction creates a trace. This is NOT an LLM log —
it's structured data from the episode runner.

```python
class ArtifactAccess(BaseModel):
    artifact_id: str
    step: int            # episode step number
    access_type: str     # "load", "inspect", "analyze"

class AnalysisRecord(BaseModel):
    analysis_id: str
    input_artifact_ids: list[str]   # which artifacts were used
    columns_used: list[str]         # which columns were touched
    op_type: str                    # "describe", "regression", "correlation", etc.
    step: int
    output_artifact_id: str | None  # derived artifact, if any

class EpisodeTrace(BaseModel):
    accesses: list[ArtifactAccess]
    analyses: list[AnalysisRecord]
    claim_steps: dict[str, int]     # claim_id → step when submitted
```

## Implementation Plan

1. **Models** (`open_investigation.py`): ArtifactAccess, AnalysisRecord,
   EpisodeTrace, WarrantResult. Add diagnostic fields to EpisodeScore.

2. **Warrant checker** (`oi_warrant.py`): `compute_claim_warrant()` and
   `compute_episode_warrants()`. Pure functions, no side effects.

3. **Scoring integration** (`oi_verifier.py`): Modify `score_episode()`
   to accept optional `warrant_scores` + `prior_floor`. When present,
   apply multiplier to both correctness and coverage.

4. **Pipeline integration** (`oi_compiler.py`): Modify
   `score_compiled_episode()` to accept optional trace + claim cards
   for warrant computation.

5. **Tests**: warrant computation, scoring integration, edge cases
   (no trace, empty trace, all abstentions, gaming scenarios).

## Codex Review Issues (post-implementation)

**Fixed:**
- Cross-analysis combining: now checks per-analysis (describe(A,Y) +
  regression(Z,W) on same artifact does NOT combine to full warrant)
- _SUBSTANTIVE_OPS tightened: removed plot, filter, merge, pivot, compare.
  Level 3 requires inferential ops only (regression, correlation, etc.)
- assert → ValueError for production robustness
- Temporal check documented (fails-closed when possible)

**Known / deferred:**
- Warrant not wired into `score_compiled_episode()` yet — needs solver
  runner to provide ClaimCards + EpisodeTrace. The interface is ready.
- Multi-spec claims (mediation → 2 specs) need warrant replication: same
  warrant_score for all specs from one claim. `score_compiled_episode()`
  will handle this when wired.
- `claim_steps` should be required when trace is present (fail-closed
  for temporal ordering). Currently None → no temporal filter.
- EvidenceRef could point to analysis_id or output_artifact_id, not just
  dataset artifact_id. This is a model enhancement for later.

## What This Does NOT Cover

- **Confidence calibration:** Separate dimension per vision doc + Codex.
  Log `unsupported_confidence` as diagnostic but don't score it yet.
- **Solver runner instrumentation:** The trace comes from the episode
  runner, which doesn't exist yet for OI. This designs the interface.
- **Anti-gaming beyond Alpha:** df.describe() counts as Level 2.5 but
  NOT Level 3. Tightened per Codex review.
- **Derived artifact lineage:** Tracked in model but not deeply
  validated in Alpha.
