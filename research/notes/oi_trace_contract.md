# OI Trace Contract — Solver Runner Interface Design

**Date:** 2026-03-27
**Context:** Warrant system implemented. Need to define how the solver
runner produces EpisodeTrace data for warrant verification.
**Codex thread:** 019d2de7-b436-7182-afc5-503aa2de0705

## Design Principle (Codex)

> "Force artifact discipline, not analysis bureaucracy."

The solver must use explicit artifact loading (provenance tracking), but
analysis should be free-form Python. Instrumented helpers AVAILABLE but
not REQUIRED — they grant higher warrant, not exclusive access.

## Architecture: Hybrid Instrumentation

```
Solver prompt + research brief + artifact catalog
    → python_exec (free-form, tracked namespace)
        → load_artifact("dataset_bg") → tracked DataFrame + ArtifactAccess
        → oi.regress(df, y="Y", x=["A"]) → result + AnalysisRecord
        → raw pandas on tracked objects → best-effort logging
        → save_artifact(filtered_df) → derived artifact + lineage
    → submit_claims([ClaimCard, ...]) → claim_steps recorded
    → EpisodeTrace assembled
```

## Artifact Lifecycle

1. **Base artifacts:** created by problem builder with stable `artifact_id`
   (e.g., "dataset_bg", "dataset_survey", "dataset_detail")
2. **Loaded artifacts:** solver calls `load_artifact(id)` → DataFrame
   enters namespace as tracked object + ArtifactAccess logged
3. **Derived artifacts:** solver calls `save_artifact(obj, label)` →
   new artifact_id minted with lineage (input_artifact_ids from source)
4. **Claim references:** ClaimCard.evidence_basis.artifact_id → must
   match a base or derived artifact_id

## DataAsset.artifact_id (NEW)

Added `artifact_id: str | None` to `DataAsset` model. Set in
`SCMProblemBuilder._build_data()`:

| Dataset name | artifact_id |
|-------------|-------------|
| background_records | dataset_bg |
| field_survey | dataset_survey |
| detailed_analysis | dataset_detail |
| research_data (single) | dataset_main |

## Helper Library (proposed, not yet implemented)

```python
# Pre-loaded in solver's python_exec namespace
class OIHelpers:
    def corr(self, df, cols=None) -> pd.DataFrame:
        # Logs AnalysisRecord(op_type="correlation", columns_used=cols)
        ...

    def regress(self, df, y, x, controls=None) -> dict:
        # Logs AnalysisRecord(op_type="regression", columns_used=[y]+x+controls)
        ...

    def groupby_mean(self, df, group_col, value_col) -> pd.DataFrame:
        # Logs AnalysisRecord(op_type="aggregate", columns_used=[group_col, value_col])
        ...

    def stratify(self, df, strat_col, value_col) -> dict:
        # Logs AnalysisRecord(op_type="stratify", columns_used=[strat_col, value_col])
        ...

    def test_independence(self, df, x, y, z=None) -> dict:
        # Logs AnalysisRecord(op_type="test", columns_used=[x, y] + (z or []))
        ...

oi = OIHelpers(trace_collector)  # injected in namespace
```

Helpers log automatically → Level 3 warrant. Raw pandas → Level 2 at best.

## Runner Contract (proposed)

```python
class OIEpisodeRunner:
    def __init__(self, problem: ResearchProblem, ...):
        self.trace = EpisodeTrace()
        self.artifact_catalog = {
            asset.artifact_id: asset for asset in problem.data_assets
            if asset.artifact_id
        }
        self.step = 0

    def load_artifact(self, artifact_id: str) -> pd.DataFrame:
        # Log ArtifactAccess, return DataFrame
        ...

    def run_code(self, code: str) -> str:
        # Execute in python_exec, increment step, best-effort trace
        ...

    def submit_claims(self, claims: list[ClaimCard]) -> None:
        # Record claim_steps, validate artifact_ids
        ...

    def get_trace(self) -> EpisodeTrace:
        return self.trace
```

## What Codex Said About Design Choices

1. **load_artifact mandatory** — provenance must be explicit. No
   pre-loading `df` variables without trace.

2. **python_exec stays free** — don't force `analyze(artifact_id, cols,
   op_type, code)` as a tool. That's self-reported metadata.

3. **op_type from helper, not declaration** — `oi.regress(...)` implies
   "regression". Don't let solver declare op_type in free text.

4. **Transparent interface, opaque scoring** — solver knows
   load_artifact exists and claims need evidence_basis. Solver does
   NOT know warrant thresholds or substantive op whitelist.

5. **Track exec_id/cell_id** — step alone is not granular enough.
   Each python_exec call should have a unique ID.

6. **Don't count failed analyses** — if code errors, no AnalysisRecord.

## Implementation Status

- [x] DataAsset.artifact_id field added
- [x] artifact_id set in SCMProblemBuilder._build_data()
- [x] EpisodeTrace + WarrantResult models
- [x] Warrant computation + scoring integration
- [ ] OI episode runner (needs LLM for solver)
- [ ] Helper library (oi.corr, oi.regress, etc.)
- [ ] Runtime DataFrame tracking (best-effort)
- [ ] Solver prompt for OI mode

## Dependencies

The OI episode runner depends on:
1. Azure API access (for LLM solver)
2. python_exec infrastructure (already exists)
3. Trace models (DONE)
4. Warrant system (DONE)
5. Compiler pipeline (deterministic part DONE, LLM extraction pending)
