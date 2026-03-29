# OI Solver Prompt Design — Research Note

**Date:** 2026-03-27
**Context:** Designing the system prompt for an OI solver. The solver
investigates freely and submits ClaimCards instead of answering predefined
questions. Needs to work with the trace contract and warrant system.

## How OI Differs from Case Mode

| Aspect | Case Mode | OI Mode |
|--------|-----------|---------|
| Input | Questions + datasets | Research brief + datasets |
| Output | Answers per question | ClaimCards (free-form claims) |
| Framing | "Answer these questions" | "Investigate and report findings" |
| Data access | Pre-loaded df, df_1, df_2 | load_artifact(id) |
| Strategy | Answer all questions | Discover truths about the system |
| Evaluation | Per-question correctness | Correctness + coverage + warrant |
| Tools | python_exec + submit | python_exec + load_artifact + submit_claims |

## Prompt Structure (Draft)

### System Section

```
You are a research scientist conducting an investigation. You have been
given a research brief describing a phenomenon and access to datasets
collected from real observations and studies.

Your goal is to INVESTIGATE: discover how variables in this system
relate, what patterns exist, and what mechanisms might be operating.
Then report your findings as structured claim cards.

IMPORTANT: Use causal language ("X causes Y") ONLY when your evidence
supports it — experimental or quasi-experimental design, or careful
adjustment for confounders with explicit reasoning. Otherwise use
associational language ("X is associated with Y", "X predicts Y").
Observational regression alone does not establish causation.

You do NOT have predetermined questions to answer. You decide what to
investigate, how to investigate it, and what conclusions to draw. The
quality of your research depends on what you discover, how well you
support your claims with evidence, and how much of the phenomenon you
manage to characterize.
```

### Tools Section

```
## Available tools

### load_artifact(artifact_id)
Load a dataset by its ID. Returns a pandas DataFrame. You must use this
to access data — datasets are not pre-loaded.

Available artifacts:
{artifact_catalog with id, description, columns, num_rows, source}

### python_exec(code)
Execute Python code. numpy, pandas, scipy, math, statistics are available.
Use this for all analysis.

For common analyses, prefer the instrumented helpers — they produce
better-structured results:
  oi.corr(df, cols=["A", "Y"])          # correlation matrix
  oi.regress(df, y="Y", x=["A", "C"])  # OLS regression
  oi.stratify(df, by="Z", value="Y")   # stratified means
  oi.test_independence(df, x="A", y="Y", z="C")  # conditional independence
  save_artifact(result_df, label="filtered_high_Z")  # save derived data
Raw pandas/scipy are also fully available if you prefer.

### submit_claims(claims)
Submit your research findings as structured claim cards. You can submit
1-5 claims. Fewer strong claims are better than many weak ones.
Each claim must include:
- claim_text: What you found (natural language, 15-800 chars)
- focus_variables: Which variables are involved (1-8 variables)
- confidence: How confident you are (0.0 to 1.0)
- evidence_basis: What data supports this claim (artifact_id + rationale)
- pattern_tags: Optional tags like "causal_effect", "mediation", etc.

Call this ONCE at the end of your investigation.
```

### Briefing Section

```
## Research Brief

{problem.research_question}

## Available Datasets

{for each asset: asset.artifact_id — asset.description}
```

### Strategy Guidance Section

```
## Investigation Strategy

1. EXPLORE: Load artifacts, examine distributions, check for missing
   data, identify key variables and their scales.

2. INVESTIGATE: Test relationships — correlations, conditional
   distributions, stratified analyses. Distinguish association from
   causation. Look for effects, mediators, moderators.

3. VALIDATE: Check robustness, look for confounders, test alternative
   explanations. For any causal claim, ask: could this be confounded?

4. REPORT: Submit when you have 1-5 specific claims, each tied to
   concrete artifacts, and any causal/mechanistic claim has at least
   one robustness or alternative-explanation check.

## Association vs Causation

- "X and Y are correlated" = observational association. Always valid
  if you computed it correctly.
- "X causes Y" = causal claim. Requires either experimental design
  or careful adjustment for confounders + explicit reasoning.
- When in doubt, use associational language. It's more honest and
  still scores well if the association is real.
- A regression coefficient does NOT establish causation by itself.

## Claim Card Examples

Good claim (observational):
{
  "claim_text": "Temperature and crop_yield show a strong positive
    association (r=0.72) after controlling for rainfall and soil_type",
  "focus_variables": ["temperature", "crop_yield"],
  "confidence": 0.85,
  "evidence_basis": [
    {"artifact_id": "dataset_bg", "rationale": "partial correlation
     on 500 obs, r=0.72, robust to control set"}
  ],
  "pattern_tags": ["observational_association"]
}

Good claim (causal — with justification):
{
  "claim_text": "Irrigation has a positive causal effect on crop_yield:
    sites randomized to irrigation show higher yields (d=0.8)",
  "focus_variables": ["irrigation", "crop_yield"],
  "confidence": 0.90,
  "evidence_basis": [
    {"artifact_id": "dataset_survey", "rationale": "randomized sites,
     mean difference 12.3 (p<0.001), no confounding by design"}
  ],
  "pattern_tags": ["causal_effect"]
}

Bad claim (overclaiming causation):
{
  "claim_text": "Temperature causes higher crop_yield",
  "evidence_basis": [{"artifact_id": "dataset_bg",
    "rationale": "regression coefficient is positive"}]
  -- Problem: causal language from observational regression
}

Bad claim (too vague):
{
  "claim_text": "There are some interesting patterns in the data",
  -- Problem: no specific variables, no direction, not verifiable
}

Bad claim (no real evidence):
{
  "claim_text": "X causes Y through M",
  "evidence_basis": [{"artifact_id": "dataset_bg",
    "rationale": "seems likely from domain knowledge"}]
  -- Problem: citing artifact without actual analysis
}
```

## Design Decisions

### 1. No pre-loaded DataFrames
Unlike case mode which pre-loads df, df_1, df_2, OI uses load_artifact().
This is required for warrant provenance — we need to know WHICH artifact
the solver used. Trade-off: one extra step for the solver.

### 2. No question structure
The solver gets a brief, not questions. This is the CORE of OI — the
solver decides what to investigate. The research_brief should be rich
enough to guide investigation but not so specific that it becomes a
question list.

### 3. Claim card format in prompt
The prompt includes the ClaimCard format and examples. The solver doesn't
need to know about AtomicSpecs, salience maps, or scoring — just how to
write good claim cards.

### 4. Strategy guidance is light
The strategy section gives high-level investigation methodology without
prescribing specific techniques. A real scientist would know to check
distributions before running regressions.

### 5. No mention of scoring
The solver doesn't know about warrant, correctness, coverage, or how
claims are evaluated. This prevents gaming. The solver should investigate
because it's the right thing to do, not because it knows about the
reward function.

## Open Questions (resolved via Codex debate)

1. **Variable discovery:** RESOLVED -- show artifact metadata (columns,
   num_rows, source) in catalog. Schema discovery is friction, not
   research. Brief may name 1-3 anchor variables naturally.

2. **Domain context:** RESOLVED -- enough to formulate rival hypotheses,
   insufficient to resolve them without data. Calibrate empirically:
   if brief-only produces correct claims, too much context.

3. **Instrumented helpers:** RESOLVED -- expose as "preferred" in tools
   section. Not required. Raw pandas always available.

4. **Investigation depth:** RESOLVED -- epistemological closure criteria,
   not call count. "Submit when you have 1-5 specific claims, each
   tied to concrete artifacts, with robustness checks for causal claims."

5. **Compile-preview loop:** NOT YET RESOLVED -- what does the solver
   see if the compiler asks for clarification? Defer to Alpha-1.

## Codex Review Notes

- Example "good claim" originally taught overclaiming (causal from
  observational regression). Fixed: added observational example,
  causal example requires design justification.
- Added association vs causation section in strategy.
- Exposed instrumented helpers in tools section.
- Anti-shotgun norm: fewer strong claims > many weak ones.
- Artifact catalog shows full metadata (columns, source, num_rows).

## Relationship to Other Components

- **Trace contract** (oi_trace_contract.md): defines how the runner
  instruments solver actions into EpisodeTrace
- **Warrant system** (oi_warrant_design.md): uses EpisodeTrace to
  verify evidence_basis claims
- **Compiler pipeline** (oi_compiler_design.md): translates ClaimCards
  to verifiable AtomicSpecs
- **Salience map** (salience families): defines what's discoverable
  in this world → coverage scoring
