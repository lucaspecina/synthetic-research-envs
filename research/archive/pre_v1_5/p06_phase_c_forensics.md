# P06 Phase C — Forensics on the 3 broken paired cases

**Date:** 2026-04-07
**Inputs:** `results/p05_canonical_batch/{chemical,confounding,immunotherapy,competing_mech}/oi_result.json` (baseline) + `results/p06_paired/...` (paired)
**Tooling:** `scripts/p06_forensics.py` (Diagnostics A+B+C) + manual inspection of `score_inputs_v2.claims` and `conversation` arrays

**Status:** read-only forensics. No code changes. No reruns.

## TL;DR

The 12-case paired batch failed the pre-registered rule (`d_corr=-0.093`,
P1 fails, RF2 + RF4 fire). The regression is **not** caused by the atomicity
intervention damaging analytical quality. It is caused by a single underlying
bug — **the solver cannot reliably attach a valid `artifact_id` to its
claims** — that the intervention amplified into 3 distinct failure modes.

The claim *content* in the broken cases is real, substantive analysis (real
OLS coefficients, real p-values, real causal-style language). The bug lives
in the metadata-binding step between "I ran an analysis" and "here is the
artifact_id that backs this claim". Each broken claim then takes a 90%
penalty in `correctness` via `evidence_basis` validation in
`_score_with_judge`.

## Diagnostic A (fabrication forensics)

| case | n_claims b/p | save_artifact b/p | fab_refs b/p | accessed paired |
|---|---|---|---|---|
| chemical | 5 / 8 | 0 / 0 | 0 / 8 | 3 base datasets only |
| confounding | 4 / 5 | 3 / 3 | 0 / 5* | 3 base + 3 derived |
| immunotherapy | 4 / 5 | 3 / 0 | 0 / 5 | 3 base datasets only |
| competing_mech (clean) | 4 / 7 | 3 / 16 | 0 / 0 | 3 base + 16 derived |

`*` confounding does not cite literal `python_exec`, but cites human-readable
slugs (e.g. `regression_dosage_models`) that do not exist as
`derived_X_hash` ids in the trace. My initial keyword classifier counted
this as `fab_refs=0`; the `in_trace=False` flag catches it. Effectively,
all 5 confounding paired claims are evidence-fabrications too.

**Three distinct failure modes, all variants of the same bug:**

### Mode 1 — "never saved anything" (chemical)
- Solver does NOT call `save_artifact` in baseline OR paired (zero in both).
- In baseline (5 claims) the solver cited the source datasets directly:
  `dataset_bg`, `dataset_survey`, `dataset_detail`. Score formula was
  satisfied because those ARE in the trace.
- In paired (8 claims) the solver switched to citing `python_exec` for
  every claim. Datasets accessed are identical to baseline, only the
  evidence pointer changed.
- The solver did NOT learn a new behavior; it abandoned the old one.

### Mode 2 — "skipped save_artifact this run" (immunotherapy)
- Baseline: 3 `save_artifact` calls, 4 claims cite the resulting
  `derived_X_hash` ids (`derived_treatment_effect_summary_447342`,
  `derived_biomarker_subgroup_effects_2325d4`,
  `derived_confounder_correlations_3d888d`).
- Paired: 0 `save_artifact` calls. 5 claims cite `python_exec`.
- Same datasets, same depth of analysis (real OLS, real coefficients, real
  p-values). The solver simply skipped the save step entirely.

### Mode 3 — "saved correctly but cited the slug, not the returned id" (confounding)
- Baseline: 3 `save_artifact` calls, 4 claims cite the returned ids
  (`derived_assignment_model_d23954`, `derived_corr_table_7521df`,
  `derived_effects_table_a3adb3`).
- Paired: 3 `save_artifact` calls (good!), 5 claims cite the SLUG
  (`regression_dosage_models`, `dosage_correlations`,
  `stratified_severity_dosage_effect`) — these are the second-arg labels
  passed to `save_artifact`, NOT the `derived_X_hash` ids that the function
  returns.
- The solver DID save artifacts and the artifacts ARE in the trace under
  their full ids. The solver just doesn't know about the returned id.

### Why mode 3 happens (root cause for confounding)

Looking at the actual python_exec calls in the confounding submit window:

```python
# msg[29] solver code
save_artifact(reg_table, 'regression_dosage_models')
# stratified table
strat = pd.DataFrame(res, columns=['severity_quartile', ...])
save_artifact(strat, 'stratified_severity_dosage_effect')
strat   # <-- last expression
```

`python_exec` only echoes the LAST expression. The solver's code discards
the return value of `save_artifact` (which is the actual `derived_X_hash`
id) and ends with `strat`, so the tool result shows `strat` (the dataframe)
and the real id is invisible.

Compare with `competing_mech` (clean) at msg[34]:
```python
main_coef_id = save_artifact(main_coef, 'main_ols_coefficients')
std_coef_id  = save_artifact(std_coef,  'standardized_ols_coefficients')
...
# last expression returns the tuple of all _id variables
```

The clean case explicitly captures every return value, so msg[35] shows the
full tuple `('derived_main_ols_coefficients_b5462c', ...)` and the solver
copies these into `evidence_basis` correctly.

This is a **prompt + tool-design** problem, not a model-capability problem.
The solver doesn't know that the returned id is the canonical artifact_id;
the tool description doesn't tell it; and the instruction "do NOT cite
python_exec steps" (already in `oi_prompts.py:95-98`) doesn't cover the
slug-vs-id mismatch.

## Diagnostic B (force-submit forensics)

| case | n_python b/p | force b/p | micro-tail b/p |
|---|---|---|---|
| chemical | 20/20 | Y/Y | 4/3 |
| confounding | 12/15 | ./. | 1/5 |
| immunotherapy | 18/20 | ./Y | 3/6 |
| competing_mech | 15/16 | ./. | 4/3 |

Aggregate force-submit: baseline 4/12 → paired 7/12 (Δ=+3, RF2 fires).

**Cross-tabbing force-submit and fabrication:**
- chemical: forced in BOTH runs. Forced ≠ cause of new fabrication
  (baseline was forced and not fabricating). The combination forced+no-save
  is the issue: in baseline, chemical avoided the trap by citing datasets
  directly; in paired, the new prompt bias toward "cite the analysis step"
  removed that escape hatch.
- immunotherapy: NEW force-submit AND new fabrication. Here the time
  pressure does seem to play a causal role: the solver was still doing
  exploratory python_exec at msg 43 when "ERROR: No iterations remaining"
  fired, then dumped 5 atomic claims with python_exec citations.
- confounding: NOT force-submitted. Submit happened with 5 iterations
  remaining after a normal DEADLINE nudge. Force-submit cannot explain
  confounding's fabrication. This is purely the slug-vs-id bug.

So **force-submit is a partial cause for immunotherapy only**. The other
two broken cases would still have fabricated even with infinite iterations.

**Micro-python at end** (last 1/3 of tool calls with args_len < 500):
mostly stable across paired (4/12 cases increased significantly:
confounding 1→5, heterogeneity 2→5, missing_data 3→5, poverty 3→5).
Suggests the new atomic prompt slightly fragments analysis at the end,
but no smoking gun.

## Diagnostic C (submit-path inspection)

The submit windows for the 3 broken cases show:

- **chemical** (msg 38-46): solver running OLS regressions until msg 41,
  receives FINAL nudge at msg 42, runs ONE more small python_exec at msg
  43, hits ERROR at msg 44, gets force-submit nudge at msg 45, dumps 8
  claims at msg 46. Pattern: out-of-time, never had a save_artifact habit.
- **immunotherapy** (msg 38-46): same pattern as chemical. Last
  python_exec at msg 43 is an interaction model. Force-submitted at msg
  46 with 5 claims, none of which had been saved.
- **confounding** (msg 26-34): NO force-submit. Solver ran
  `save_artifact(...)` at msg 29 and 31, but the python_exec output never
  echoed the returned ids. At msg 33 a normal DEADLINE nudge fires; at
  msg 34 the solver submits 5 claims using the slugs it remembered, not
  the ids it never saw.

Manual reading of the actual `claim_text` confirms these are real,
substantive analytical claims with correct causal language and real
coefficient values — not nonsense filler:

> C1 (chemical): "In the 101-record regression
> (days_to_phase_separation on crude chemistry, test severity, and
> formulation variables), phase_balance_margin shows a strong positive
> association with long-run stability (coef≈0.44, p<0.001)..."

> C3 (chemical): "When phase_balance_margin is added to a model with
> salinity, thermal stress, and visual clarity, the salinity and
> thermal-stress coefficients shrink and become statistically weak,
> suggesting stability loss from harsh conditions is partly captured by
> phase_balance_margin."

> c3_adj_survival_treat (immunotherapy): "After adjusting for patient_age,
> disease_burden, functional_status, immune_marker_level, mutation_load,
> prior_therapy_lines, site_id, and wave..."

These are not bad claims. They are good claims wearing wrong nametags.

## Cross-case pattern

The clean case (`competing_mech`) is the control:
- Did 16 `save_artifact` calls in paired (vs 3 in baseline)
- Accessed 19 artifacts (3 base + 16 derived)
- ALL 7 paired claims correctly cite `derived_X_hash` ids
- Paired total score 0.430 vs baseline ~0.38 — moved in the predicted
  direction

The difference between clean and broken cases is **whether the solver
captured `xx_id = save_artifact(...)` and exposed the returned ids in the
tool output**. competing_mech does this consistently. The 3 broken cases
each fail at a different step of this pipeline:
- chemical: never tried (no save_artifact at all)
- immunotherapy: tried in baseline but skipped under the new prompt
- confounding: tried, but didn't capture the return value, so never saw
  the canonical id

The atomic prompt + cap=15 didn't break these cases by demanding too
much. It broke them by offering an extra rope (more claims) without
explicitly requiring the artifact_id capture discipline that the cap=5
baseline implicitly enforced.

## Concrete prediction (the user's stop-rule criterion)

> Si al final de A+B+C podés escribir una predicción concreta del tipo
> 'si cambio X, desaparece fabrication en estos casos y no sube force-submit',
> entonces ya está: pasamos a diseño del fix. Si no, stop diagnóstico y
> pasamos a hardening + mini re-test.

I can write **two** predictions, ranked by surgical-ness and confidence.

### Prediction A — single surgical fix (HIGHEST confidence)

**Change:** make `save_artifact` always print/return its full id as the
visible value in `python_exec` output, and update the tool description in
`oi_runner.py` so the LLM knows the canonical id is what comes back from
the call (not the slug it passed in).

Two micro-steps:
1. Wrap `save_artifact` so it both returns the id AND prints
   `f"saved as {new_id}"` to stdout, so the python_exec captured-output
   stream always contains the id even if the solver discards the return
   value with a trailing raw expression.
2. Update the tool description for `python_exec` (where save_artifact is
   exposed in the namespace) to read: "save_artifact(df, label) returns
   and prints the canonical id (e.g. 'derived_X_a1b2c3'). USE THIS ID in
   `evidence_basis.artifact_id`. Do NOT cite the label slug, the
   python_exec step, or python_exec literal."

**Predicted effect on the 4 forensic cases:**
- confounding: fabrication DISAPPEARS. The solver had the analysis saved
  correctly; the only barrier was visibility of the returned id. With the
  printout, the next iteration's tool result shows the id.
- immunotherapy: fabrication PARTIALLY RESOLVED. The solver still has to
  call save_artifact in the first place; if it doesn't, no id to cite.
  But the explicit prompt change ("USE THIS ID") may push the solver to
  call save_artifact at all (because the contract explicitly says
  evidence_basis must point to it).
- chemical: fabrication PARTIALLY RESOLVED via the same mechanism. May
  still fall back to citing `dataset_X` directly if it never calls
  save_artifact.
- competing_mech: NO REGRESSION (already does it right; the printout is
  redundant for it).

**Predicted effect on force-submit:** UNCHANGED. The fix doesn't add
prompt length, doesn't add sub-instructions, doesn't change iteration
budget. RF2 should not move (force-submit count stable at ~7).

**Predicted effect on aggregate `d_corr`:** assuming the 3 broken cases
recover their lost ~0.45 correctness on average (90% penalty removed),
the aggregate d_corr should move from -0.093 toward roughly +0.025 to
+0.04 — close to the P1 threshold but not guaranteed to pass it. This
is a STRONG-WEAK win at best, not a STRONG WIN.

### Prediction B — two changes (broader, lower confidence)

**Change A** (above) PLUS **Change B**: add an explicit instruction in
`oi_prompts.py` after the existing `evidence_basis` rules saying "before
your final 3 iterations, consolidate any analysis you intend to claim
into a `save_artifact` call." This addresses the immunotherapy
"skipped-save-this-run" mode and the chemical "never-saved" mode.

**Predicted effect:** all 3 broken cases recover. Aggregate `d_corr`
moves into the +0.04 to +0.06 range. **Risk:** the new instruction adds
prompt length and may push more cases into force-submit (RF2 risk).
This is a 2-knob fix, harder to attribute the result.

## Recommendation — what to actually do next

I recommend **Prediction A** as the next intervention, scoped as a
hardening fix to the artifact contract, NOT as a re-test of the
bundling hypothesis.

Reasons:
1. Surgical and uncontested. It addresses a real bug independent of any
   experimental hypothesis. confounding will demonstrably recover; the
   other cases will at worst stay broken.
2. It does not introduce force-submit risk. RF2 stable.
3. It cleanly separates "scoring contract" from "atomicity
   intervention". After the fix, a clean re-test of the atomicity
   intervention has a fair shot.
4. Even if the aggregate d_corr does not reach P1, the residual signal
   becomes interpretable: we will know whether atomicity helps once the
   contract bug is removed.

Out of scope deliberately:
- Prediction B (force-submit prompt change). Re-evaluate AFTER seeing the
  effect of A. If A removes >=2 of the 3 fabrications and force-submit
  stays flat, B is not needed. If A removes only confounding, then we
  layer B on top.
- Re-running the 12-case paired batch. Run a 3-case mini re-test first
  on chemical + confounding + immunotherapy, then decide.

## Stop-rule outcome

The user's stop-rule was: write a concrete prediction or stop. I have
**Prediction A as concrete**. Therefore: **PASS**, proceed to fix design.

## Open items not addressed in this forensics

- The `world_fingerprint` non-determinism bug (cosmetic, deferred).
- The `_score_with_judge` 90% penalty magnitude — is 90% the right
  penalty for evidence_basis mismatch? (Outside this scope.)
- Post-hoc per-case investigation of the 9 non-broken cases — why didn't
  atomicity move the needle for them either? (Allowed under
  pre-registration but defer until after the fix.)

---

# Phase D — `adjust + partial_correlation` semantic crack

**Date:** 2026-04-08
**Trigger:** rerun-12 of `p06_paired_run.py` with the new `AtomicSpec` validator (rejects `arm.kind=ADJUST` paired with `measurement.kind in {CORRELATION, PARTIAL_CORRELATION}`).
**Status:** read-only forensics + plan. No code changes yet.
**Verified by:** Lucas (intuition), Codex (technical), Cursor (project-rule alignment).

## TL;DR

5 of 12 cases in the rerun-12 batch hard-failed during `SubQuestionIntentV2`
reconstruction with the same validation error: at least one verification
spec used `arm.kind=ADJUST` with `measurement.kind=PARTIAL_CORRELATION`.
The pattern is **not random**. All 5 failing claims express the same
applied-statistics intent — *"controlled regression / multivariate model
with controls / association after adjustment"* — and the compiler
systematically translates that intent into the same invalid hybrid.

The bug root is **not** in the compiler alone, **not** in the verifier
alone, and **not** in the validator we just added. It is a 4-layer
**semantic misalignment** in the contract between layers, with ambiguity
seeded all the way upstream in the deterministic extraction. Fixing it
requires disambiguation in the compiler prompt, abstention exemplars for
model-dependent quantities, and a robust loader for historical artifacts.
It does **not** require a new measurement primitive — the project
explicitly forbids `regression_coefficient` for principled reasons
documented at `src/sreg/models/open_investigation.py:11`.

## How the crack was found

The user's intuition: *"if this happens 5 of 12 times, it cannot be
accidental. The compiler must be misunderstanding something the solver
is trying to say in a systematic way."* This was correct.

The 5 baseline claims that the compiler translated to `adjust + pcor`:

| case | claim text fragment |
|---|---|
| competing_mech | "substantially reduced when ... included with controls" |
| coral_bleach | "In multivariate models with site+wave controls" |
| immunotherapy | "even after adjustment" |
| microbiome | "even after adjusting for" |
| selection_bias | "given selection proxies" (= controlling for proxies) |

All 5 are the same conceptual move expressed in everyday applied-stats
English: "give me the association/effect after adjusting for these
covariates." This phrasing maps naturally to `arm.kind=adjust` from the
field names alone (`treatment`, `outcome`, `adjust_set`), and to
`measurement.kind=partial_correlation` from the words "association" /
"coefficient" / "effect after controlling". The Frankenstein is
predictable, not pathological.

## The 4-layer misalignment (verified in code)

### Layer 1 — `oi_extraction.py:728-730` (deterministic pattern keywords)
```python
(PatternClass.OBSERVATIONAL_ASSOCIATION, [
    "associat", "correlat", "controlling for", "adjusting for",
]),
```
At extraction time, the literal phrases "controlling for" and "adjusting
for" are classified as `OBSERVATIONAL_ASSOCIATION`. So the deterministic
upstream layer says: "this language means observational."

### Layer 2 — `oi_exemplars.py:152` and `:202` (LLM exemplars)
```python
# line 152 — OBSERVATIONAL_ASSOCIATION example
"In the data, education and income show a strong positive association "
"after adjusting for region and age"
# evidence_type = "observational"

# line 202 — CAUSAL_EFFECT example
"The effect of Education on Income is negligible after controlling for Skill"
# pattern = CAUSAL_EFFECT
```
**The same surface phrase** ("after adjusting/controlling for X") appears
once as observational and once as causal. The exemplars correctly model
the real-world ambiguity — but they also propagate it without giving the
downstream layer a disambiguation rule.

### Layer 3 — `oi_sq_compiler.py:50` (compiler prompt grammar reference)
```
- kind: "baseline" (sample from joint), "intervene" (do-calculus, set values),
  "observe" (observe natural distribution), "condition" (condition on values),
  "adjust" (observe but adjust for confounders), "sweep" (vary a variable)
```
The prompt presents `adjust` to the LLM as **"observe but adjust for
confounders"**. To any reader trained on applied statistics, this reads
as observational regression with controls — exactly what the failing
claims are asking for. The field names that follow reinforce the trap:
`treatment`, `outcome`, `adjust_set` are the canonical OLS-with-controls
vocabulary.

### Layer 4 — `oi_verifier.py:339` (executor)
```python
samples = solver.interventional_samples(
    arm.outcome, do={arm.treatment: x_val}, n=n_mc, seed=seed
)
```
The executor implements `adjust` as **interventional do-calculus**: it
queries the SCM oracle for `E[Y | do(T=t)]` and returns a 1-D array of
outcome samples. This is **not** observational regression. It is the
oracle's exact causal effect via the SCM's `interventional_samples()`.
The two semantics are fundamentally incompatible: do-calculus collapses
the joint distribution to a marginal-under-intervention, destroying the
multivariate information that `partial_correlation` would need.

### Why the layers diverge

Layer 4 (verifier) is internally coherent: it implements the only thing
the verifier can guarantee from the SCM oracle as ground truth — the
exact interventional distribution. There is no bug in the verifier.

Layer 3 (compiler prompt) is internally coherent for an LLM trained on
applied statistics: every word and field name reads as
"observation-with-controls", which is the most common applied-stats
move. There is no bug in the LLM compiler — it follows the prompt
faithfully.

Layers 1 and 2 already encode the ambiguity: the same surface phrase
maps to two different patterns depending on context the deterministic
extractor cannot see. This ambiguity is real (it exists in the
literature) but the system never resolves it.

**The crack is in the contract between layers 3 and 4**, amplified by
the ambiguity seeded in layers 1 and 2. The validator we added catches
the symptom at construction time, but the symptom is downstream of a
real design alignment problem.

## Why a `regression_coefficient` primitive is *not* the answer

The natural-looking deep fix is to add `measurement.kind=regression_coefficient`
with `target / outcome / controls` as a first-class primitive. This was
**explicitly considered and rejected** for v1.

Reason, from `src/sreg/models/open_investigation.py:11`:
```
- regression_coefficient is explicitly forbidden (model-dependent, not world truth)
```

A regression coefficient is the output of a particular statistical
model. It depends on:
- Choice of functional form (linear, quadratic, log-transformed, kernel)
- Choice of control variables (different sets give different coefficients)
- Choice of estimator (OLS, robust, GLS, ridge)
- Sample restrictions, outlier handling, weighting

The same world (the same SCM) can produce infinitely many "coefficients"
depending on the analyst's modeling choices. None of them are properties
of the SCM. They are properties of the model the analyst imposed on the
SCM. If we made the verifier compute "the regression coefficient", it
would have to first decide which regression to run — and that decision
is exactly the analyst's judgment, the thing being graded. Circular.

The project's design principle is that **ground truth must be a property
of the world (the SCM)**, not a property of any particular model
applied to the world. Quantities that survive this test:
- `E[Y | do(T=t)]` — interventional mean, defined by the SCM mechanism.
- `corr(T, Y)` — observational correlation, defined by the joint
  distribution.
- `pcor(T, Y | W)` — partial correlation, defined by the joint
  distribution.
- `Pr[Y > k | do(T=t)]` — interventional tail probability.

Quantities that fail this test:
- "OLS coefficient of T in `lm(Y ~ T + W)`"
- "standardized beta of T"
- "partial R-squared of W in the multivariate model"

These are model outputs, not world truths. v1 must abstain on them, not
approximate them with a hybrid spec.

## What "the system improves" does and does not mean (clarification)

A confusion that contaminated earlier reporting in this session needs to
be made explicit, because it affects how this work is evaluated:

**`delta_total` between two runs measures something different depending
on what changed between the runs.**

- If the **solver** changed (different model, different prompt, different
  strategy) and the system was held fixed → `delta_total` is evidence of
  a change in solver quality. A higher score means the solver did
  research the system values more.
- If the **system** changed (verifier, validator, compiler) and the
  solver was held fixed → `delta_total` is evidence that the system
  changed its mind about the same investigation. It is **not** evidence
  of solver improvement, and it is **not** evidence of system
  improvement either. It is only evidence that the system is now scoring
  differently. Whether the new score is more accurate than the old one
  is a separate question that requires qualitative inspection.

In rerun-12, the solver was held fixed (same model, seed, frozen src,
prompt). The validator changed. So the deltas in rerun-12 are evidence
of the system changing its mind, not evidence of system quality
improving. Quality improvement of the system would require showing,
case by case, that the new judgments are more aligned with what a
human expert would say about that investigation.

**This forensics doc, and any follow-up work, will not use aggregate
delta as evidence of "system improved". The system improving is a
qualitative claim that needs case-by-case validation against expert
judgment.**

## Critical correction: frozen src does *not* exercise the compiler

A second confusion that needs documenting because it affects the
experimental design.

`scripts/p06_paired_run.py:157-160`:
```python
sqs_v2_raw = src.get("sub_questions_v2", [])
sqs_v2 = [SubQuestionIntentV2(**sq) for sq in sqs_v2_raw]
runner.set_subquestions_v2(sqs_v2)
```

The "rerun" reconstructs `SubQuestionIntentV2` instances **directly from
the frozen JSON**, bypassing the compiler entirely. This means:

- A change to `oi_sq_compiler.py` (prompt, exemplars, anything in
  `GRAMMAR_REF`) **does not get exercised** by a frozen-src rerun.
- The only things exercised by a frozen rerun are: (a) the JSON
  loader, (b) any `pydantic` validators on the model, (c) the verifier
  when the runner executes specs, (d) the validator we just added.

Therefore, validating that the prompt fix actually works requires a
**different** experiment: re-generating the SQs by calling the compiler
on the same SCM worlds (same seed, same problem) with the new prompt.
Frozen replay alone cannot validate the root fix.

This implies splitting future work into two distinct experiments
documented in the plan below.

## Required-fallback policy (decision)

When the robust loader (or the validator) drops every spec marked as
`required` for a given sub-question but some `support` specs survive,
the policy is:

> **Abstain the entire SQ.** Do not promote `support` specs to
> `required` post hoc.

Reason: a `support` spec is by design additional evidence that
strengthens an answer, not the core that answers the question. If the
core is dropped, the SQ is not actually addressed; promoting a support
spec would be cosmetic credit for an unaddressed question. Honesty is
preferable to cosmetic coverage.

This decision is recorded here so it is not re-relitigated during
implementation. It applies in both the loader (Experiment R) and the
compiler (Experiment G).

## Plan

The fix splits into two distinct experiments. Order matters: Experiment
R must complete before Experiment G is interpretable.

### Experiment R — Replay (validates loader + validator + verifier integrity)

| # | task | layer touched |
|---|---|---|
| 33 | **MINIMAL** shared load/normalize function for `SubQuestionIntentV2` | one helper, not new architecture |
| 35 | required-fallback policy → abstain SQ | loader + docs |
| 34 | rewrite verifier test using `model_construct()` | tests only |
| - | rerun-12 frozen → confirm loader degrades cleanly | end-to-end check |

This experiment does **not** validate the prompt fix. It only validates
that the system no longer hard-fails on historical artifacts that
contain `adjust + pcor` specs.

**Constraint on #33 (per Cursor):** the loader is one shared
load-and-normalize function — *not* a mini-architecture, *not* a new
package, *not* a class hierarchy. It centralizes the JSON-to-pydantic
step that today is script-local in `p06_paired_run.py:157-160` and
`rescore.py`, plus applies the required-fallback policy. Nothing more.

**Success criteria for Experiment R (predefined, per Cursor):**
1. Zero hard-fails on the rerun-12 batch. Every case produces an
   `oi_result.json`.
2. Specs that would have hard-failed (`adjust + pcor` or any other
   validator violation) are dropped *cleanly*: dropped specs are listed
   in a structured field (`dropped_specs` or similar), the SQ continues
   with the surviving specs.
3. If all `required` specs of an SQ fall, the SQ as a whole is marked
   abstained — never silently re-promoted from `support`. The
   abstention is visible in the result and in the score.
4. The rerun-12 deltas are reported but **not** used as evidence of
   improvement. They are interpreted only as "the system no longer
   hard-fails; here is what it now scores instead."

### Experiment G — Generate (validates compiler prompt fix + exemplars)

Per Cursor's adjustment (2026-04-08): do **not** jump to
`generate_src.py --oi` first. That re-introduces the solver, the
orchestrator, and additional Azure stochasticity, all of which obscure
whether a compiler-prompt change actually fixed the compiler. Start
with an **isolated compiler recompilation test**, then escalate to
end-to-end only if the isolated test passes and an end-to-end check is
needed.

#### G.1 — Isolated compiler recompilation (mandatory first step)

| # | task | layer touched |
|---|---|---|
| 30 | rewrite `adjust` description in compiler prompt | `oi_sq_compiler.py` prompt only |
| 31 | positive exemplars for "controlled regression" → both valid routes | `oi_sq_compiler.py` prompt only |
| 32 | abstention exemplars for model-dependent quantities | `oi_sq_compiler.py` prompt only |
| 36a | new script `scripts/p06_recompile_only.py` | isolated harness |
| 37 | calibration sets for false-abstention / false-non-abstention rates | new fixture |

The new harness loads the **same 12 frozen worlds** plus the **same
frozen claim texts / SQ glosses** that produced the rerun-12 input,
then re-invokes only the compiler (`oi_sq_compiler` LLM call) on
those texts to produce a new `sub_questions_v2`. No solver, no
orchestrator, no `generate_src.py`. The harness diffs the new
`sub_questions_v2` against the frozen one and reports per-spec
classification: kept identical / changed kind / changed measurement /
newly abstained / newly emitted.

This isolates the compiler from every other moving part. The only
stochasticity is the compiler LLM itself (acceptable; it is the
component being tested).

**Success criteria for Experiment G.1 (predefined, per Cursor):**
1. **Pattern reduction:** the `adjust + pcor` combination drops
   substantially in the recompiled SQs vs. the frozen baseline. Target:
   the 5 previously-failing claims no longer compile to that hybrid;
   they compile to either `baseline + pcor + cond_set` (observational
   reading), `adjust + mean` (causal reading), or are abstained as
   model-dependent — all three are acceptable, the choice is the
   compiler's job.
2. **No false-abstention spike:** on the regenerated 12-case set, the
   total fraction of abstained specs does not increase by more than
   10 percentage points absolute over the frozen baseline. The
   intervention must not collapse into "abstain on everything."
3. **Calibration set A (verifiable observational/causal claims using
   applied vocabulary):** false-abstention rate < 10%.
4. **Calibration set B (genuinely model-dependent claims):**
   false-non-abstention rate < 10%.
5. **No regression on the unaffected cases:** the 7 cases that did not
   contain `adjust + pcor` claims should produce SQs with the same
   structure as before (allowing for compiler-LLM stochasticity within
   the policy ranges defined above: deltas <0.1 noise, 0.1-0.2
   tentative, >0.2 real).

#### G.2 — End-to-end (only if G.1 passes)

If and only if G.1 passes its success criteria, optionally re-run a
full `generate_src.py --oi` end-to-end on a small subset (3-5 cases,
not all 12) to verify the prompt fix survives the larger pipeline
without unintended interactions with the solver/orchestrator. This
step is **optional** and is only justified if the isolated test alone
leaves doubt about end-to-end behavior.

**Success criteria for G.2 (predefined):**
- No new hard-fails.
- The same `adjust + pcor` reduction observed in G.1 holds in the
  end-to-end output.
- No qualitative regression in the affected cases (case-by-case
  inspection, not aggregate delta).

#### What G does *not* claim

Experiment G does not claim that the system "improved" in any
aggregate sense. It claims that one specific semantic crack —
`adjust + pcor` for controlled-regression-style claims — is closed by
the prompt fix, on a specific set of 12 worlds. Whether that
translates to broader system improvement requires separate
qualitative evaluation, deferred.

### Calibration sets (task 37)

Two small synthetic claim sets, hand-curated:

**Set A — verifiable observational/causal claims using applied vocabulary**
(should NOT abstain):
- "After controlling for `W`, `T` is positively associated with `Y`."
- "Holding `W1` and `W2` constant, `T` increases `Y`."
- "The adjusted association between `T` and `Y` is negative."
- "Even after adjustment for confounders, `T` reduces `Y`."

**Set B — genuinely model-dependent claims** (should abstain):
- "The OLS coefficient of `T` in the multivariate model is 0.42."
- "The standardized beta of `T` is 0.18."
- "The partial R-squared of `W` is 0.06."
- "The model AIC drops by 12 when `T` is included."
- "In a hierarchical mixed-effects model, the random slope variance is..."

Within each set, separate observational from causal phrasings to ensure
the abstention criterion is *"asks for a model-output quantity"*, not
*"contains the substring `model` or `regression`"*.

## What this work does *not* do

- Does not add `regression_coefficient` or any other model-dependent
  primitive to the grammar.
- Does not modify the verifier (`_run_adjustment` or
  `interventional_samples`). The verifier is internally coherent.
- Does not remove or relax the validator added at the start of P06.
  The validator remains the contract enforcer; this work just gives
  it graceful failure modes and ambient prompt support.
- Does not interpret aggregate `delta_total` from rerun-12 as "the
  system improved" or "the solver improved". Whether the new judgments
  are more accurate is a qualitative question, evaluated case by case
  on three buckets after Experiment G:
  1. The 5 previously hard-failing cases.
  2. Any new abstentions introduced.
  3. Any case with "controlled regression" phrasing, to verify route
     selection.

## Open items (not addressed here, deferred)

- Task #28: `world_fingerprint` non-determinism (cosmetic, deferred).
- LLM compiler/solver stochasticity even with frozen seed (Azure does
  not honor `temperature=0.0` reliably). Policy: deltas <0.1 not
  interpretable without replicates; deltas 0.1-0.2 tentative; deltas
  >0.2 real signal. Per Codex 2026-04-08.
- Whether layers 1 (`oi_extraction.py` keyword mapping) and 2
  (`oi_exemplars.py`) should also be touched to remove the upstream
  ambiguity. **Per Cursor: do not mix this into the first pass.** The
  first pass touches only the compiler prompt (#30/#31/#32). If
  Experiment G.1 fails its success criteria, *then* revisit
  `oi_exemplars.py` as a second pass — and document the revisit as a
  separate experiment, not as a silent extension of G.1.
- The same applies to `oi_extraction.py:728-730`: do not modify the
  deterministic keyword mapping in the first pass. Note it as upstream
  debt; address only if G.1 results force it.
