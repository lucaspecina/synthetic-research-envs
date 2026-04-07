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
