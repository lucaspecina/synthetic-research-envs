# P06 Phase C — Pre-registered interpretation rule

**Timestamp:** 2026-04-07 (written BEFORE looking at the 12-case paired results)
**Commit snapshot:** `results/p06_paired/_snapshot/head.txt`
**Diff snapshot:** `results/p06_paired/_snapshot/diff_experiment.patch`

This document is a pre-registration. It pins the decision logic before we see
the 12-case data. The purpose is to prevent post-hoc rationalization of
whatever pattern emerges. The analysis script
`scripts/p06_analyze.py` implements these rules mechanically.

## Hypothesis under test

> In P05_canonical_batch, solver claim bundling was a *dominant* bottleneck.
> The scorer's formula `truth = mean(holds over specs)` severely penalized
> bundled claims whose extracted spec set contained any failing spec. Relaxing
> bundling pressure (atomic-claims prompt + cap raised 5→15) should lift
> `correctness` per claim, and through that, `total` score.

## What we actually changed (not a pure A/B on bundling)

- `MAX_CLAIMS: 5 → 15` (Pydantic + JSON schema + runtime guard)
- Solver prompt rewritten in `oi_prompts.py` to instruct atomic claims
- Tool description in `oi_driver.py` updated to reference atomic claims

**Important:** this is a test of the *atomicity intervention*, not a pure
test of "bundling and nothing else". Two levers moved together (prompt + cap).
If results support the hypothesis, the honest wording is: *"in these 12 cases,
the atomicity intervention lifted scores in the direction predicted by the
bundling hypothesis"*, not *"bundling is proven to be the dominant
bottleneck in general"*.

Additional residual confounds noted in advance:
- Baseline is historical; model deployment drift on `gpt-5.2-codex` cannot
  be ruled out.
- Chemical paired case shows `evidence_basis` fabrication (citing
  `python_exec` as artifact_id) that is NOT present in baseline. This is
  a *separate* bug (ticket #25) that will confound the chemical delta.

## Decision variables

### Primary (must decide on these)

- **Aggregate `delta_correctness`** — mean of per-case deltas
- **Per-case `delta_correctness` sign** — how many of 12 improved vs regressed
- **Aggregate `delta_weighted_coverage`** — mean of per-case deltas
- **Aggregate `delta_total`** — mean of per-case deltas

### Secondary (corroborating)

- **Atomization mechanism metrics:** `delta_mean_n_specs`, `delta_frac_atomic`,
  `delta_n_claims`
- **Bundling-severity correlation:** Pearson correlation between
  baseline `mean_n_specs` and per-case `delta_total`
- **Cap-saturation correlation:** were deltas concentrated in cases where
  baseline had `n_claims == 5` (saturated)?

### Confounds (exclude before interpreting)

- **Force-submit:** solver ran out of iterations without submitting; driver
  forced a final submit-only round. Detected via conversation messages
  containing `_NUDGE_FORCE_SUBMIT` text.
- **Evidence fabrication penalty:** claim cites an artifact_id not in the
  trace → 90% penalty applied. Detected via comparing
  `score_inputs_v2.claims[].evidence_basis[].artifact_id` against
  `trace.accessed_artifact_ids()`.
- **Compilation failures:** non-zero `n_partial + n_abstention + n_error`
  in `score_inputs_v2.compiled_claims`.
- **Cap pegging:** `n_claims == 15` in paired (new cap biting).

## Pre-registered verdict rules

### PRIMARY criterion — must hold for any positive conclusion

**P1.** `aggregate_delta_correctness >= +0.03` AND `>= 8/12` cases show
`delta_correctness > 0`.

- *Pass:* the `truth = mean(holds)` story has support.
- *Fail:* hypothesis of "bundling was dominant" is NOT supported. Further
  diagnosis needed before any other conclusion.

### CORROBORATING criteria — needed for a STRONG win

**C1 (mechanism fired).** `aggregate_delta_mean_n_specs <= -0.5` AND
`aggregate_delta_frac_atomic >= +0.15`.
- If C1 fails and P1 passes → suspicious: we measured something other than
  atomization (e.g., judge drift, compilation luck, model deployment change).

**C2 (coverage aligned).** `aggregate_delta_weighted_coverage >= +0.05` AND
same-sign majority with `delta_correctness` across cases.
- If C2 fails (coverage flat or negative) while P1 passes → partial win:
  truth penalty was real but SQ matching stayed weak.
- If C2 passes but P1 fails → DIFFERENT story: the intervention helped the
  judge, not the truth formula. Bundling hypothesis does NOT win.

**C3 (bundling-severity correlation).** Pearson `corr(baseline_mean_n_specs,
delta_total) >= +0.30` across the 12 cases.
- If correlation is flat or negative → the delta is not coming from the
  cases we expected. Red flag for the bundling story.

### DISQUALIFYING red flags (override even a passing P1)

**RF1.** `>= 3 cases` have paired `n_claims == 15` (cap still biting).
- Means the new cap is itself limiting; the experiment ran into a new
  ceiling.

**RF2.** Paired force-submit count > baseline force-submit count + 2.
- The new prompt is overwhelming the solver.

**RF3.** Aggregate `delta_abstention_rate + delta_error_rate >= +0.05`.
- Compilation regression nullifies the atomization benefit.

**RF4.** `>= 3 cases` with new evidence-fabrication penalty in paired
that was absent in baseline.
- Solver is citing wrong artifacts more often under the new prompt.
- `chemical` is already known to have this; if ≥2 others appear, RF4 fires.

**RF5.** P1 passes only if we include cases with force-submit or
fabrication. If excluding confounded cases drops aggregate_delta_correctness
below +0.03 → not robust.

### VERDICT MATRIX

| P1 | C1 | C2 | C3 | RF* | Verdict |
|----|----|----|----|-----|---------|
| Pass | Pass | Pass | Pass | none | **STRONG WIN** — atomicity intervention moves scores in the direction predicted by bundling hypothesis |
| Pass | Pass | Pass/Fail | Pass/Fail | none | **WEAK WIN** — mechanism fired, scores improved, story incomplete |
| Pass | Pass | Pass | Any | 1+ | **INCONCLUSIVE** — delta is real but confounded |
| Pass | Fail | Any | Any | Any | **SUSPICIOUS** — score improved without mechanism firing; investigate |
| Fail | Any | Pass | Any | Any | **DIFFERENT STORY** — judge/coverage improvement, not bundling |
| Fail | Any | Fail | Any | Any | **HYPOTHESIS FAILS** — scores did not improve |

## Post-hoc analyses ALLOWED only after primary verdict is locked

Once the primary verdict is recorded, these are OK to explore without
invalidating the pre-registration:

- Per-case story (why did case X behave differently?)
- Distribution of claim lengths, focus_variables count, confidence
- Which SQs got better-covered and why
- Qualitative inspection of a sample of new atomic claims

## What a positive result DOES NOT prove

- That bundling is the dominant bottleneck for Open Investigation **in general**
- That the current scoring formula is right
- That atomic claims are always better than composite claims
- That the cap of 15 is correct; we only know 5 was too low for these cases
- That this reproduces with a different solver model or a different compiler

## What a negative result DOES prove

- That the current working-tree changes, taken together, did not shift
  scores in the direction predicted by the bundling hypothesis, on the 12
  cases of `p05_canonical_batch`, under the same seeds and SCMs.
- Further diagnosis of the scoring stack is warranted.
