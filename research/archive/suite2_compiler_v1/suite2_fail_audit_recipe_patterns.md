# Suite 2 — Fail audit of zero-bound families (#11a)

**Scope.** Manual audit of the 10 verdict-fails that belong to the 4
"0% effective pass" candidate families identified by the partial
pattern breakdown (Task #10). These are the families where every gold
target in Suite 2 produced a verdict-fail — the strongest recipe-gap
signal in the baseline.

**This is NOT a substitute for the original Task #11** ("audit of the 6
full passes"). That audit is blocked by artifact availability (neither
`full_pass` nor `real_struct_err` is persisted — see I-027) and
executes as #11b once the full per-target dump exists. This document is
the complementary #11a split.

**Source data.** `research/synthesis/compiler_baseline_failures.json`
(21 verdict-fail entries, cross-joined with `ALL_FACTS` for family
metadata). 10 entries fall into the 4 zero-candidate families.

**Taxonomy** (from Codex review, thread
`019d8d5e-6d29-77c1-94a0-63604f4df009`). Two orthogonal axes:

| Axis | Values | Meaning |
|---|---|---|
| **Locus** | `selection.wrong_default` | Compiler picks a wrong primitive and sticks with it |
| | `selection.catalog_visibility_gap` | Compiler cannot reach the correct primitive at all (unclear if catalog lacks it or routing fails) |
| | `assembly.slot_filling` | Correct primitive, wrong slot values (variable binding, arm kind, assertion direction, atom count, missing causal role) |
| **Stability** | `invariant` | Identical output across all paraphrases (strong signal of a fixed default) |
| | `partial` | Identical across some paraphrases, different in others |
| | `fragile` | Different output per paraphrase (unstable routing / lexical fragility) |

**Selection bias caveat (important).** This audit selects the 4
families where `N_verdict_fail == N_total` — i.e. the zero-candidate
set. It is therefore a **severity-biased triage** optimized for
finding universal recipe gaps. It will over-represent stable wrong
defaults and coarse recipe failures, and under-represent mixed-signal
families, boundary failures, adjust-swaps, and verdict-by-accident
pathologies. Do NOT read this audit as a representative sample of
overall compiler error composition — for that, the full per-target
dump (I-027 item 4) is required.

---

## CC-A5 — Confounding (crude vs adjusted)

All three surface forms of fact **W1_F07**: "Severity confounds treatment
-> outcome." Truth value: TRUE (severity is a confounder in W1).
Families: `[CC-A5, CC-B2, CC-D1]` (confounding + role disambiguation +
causal-vs-observational boundary). Regime: `comparative`.

### Gold recipe
```
1 spec | arms=[observe, intervene] | measurement=mean
      | comparison=difference | assertion=gap_material
```
The canonical verifier for confounding: one arm observes the natural
distribution, the other intervenes; if the two differ materially, there
is confounding bias in the observational estimate.

### Compiler outputs

| Surface form | difficulty | Compiler specs |
|---|---|---|
| s0 — "Severity confounds the relationship between treatment and outcome." | easy | 2 specs, `baseline` arms, `correlation` + `partial_correlation`, assertions `distinguishable` + `near_zero` |
| s1 — "Without adjusting for severity, the observed association is biased." | medium | 2 specs, `baseline` arms, `correlation` + `partial_correlation`, assertions `distinguishable` + `not_distinguishable` |
| s2 — "Severity is a confounder, not a mediator..." | hard | 3 specs, all `intervene` arms, `mean` measurements, assertions `distinguishable`+`distinguishable`+`near_zero` |

### Canonical wrong recipe
**`correlation` + `partial_correlation` pair with `baseline` arms.** s0
and s1 are structurally identical — the compiler interprets "confounding"
as "check if the correlation changes after conditioning on Z". That is a
textbook statistical definition of bias detection, but it does not use
the SCM's observe-vs-intervene contrast, which is what the verifier
requires. The compiler never reaches for an `intervene` arm in the easy
and medium forms.

s2 is **different** — the hard paraphrase explicitly says "causes both
the treatment decision and the outcome", which triggers `intervene` arms
and `mean` measurements. But the compiler still emits 3 specs and the
assertions are still wrong (it's now trying a shotgun of intervene-based
contrasts rather than the single observe-vs-intervene comparison).

### Error invariance across paraphrases
- **Partial.** s0 = s1 (identical wrong recipe). s2 diverges under the
  explicit causal phrasing. The recipe gap is stable under weak surface
  cues; strong causal cues shift the compiler to a different (still
  wrong) recipe.

### Classification
- **Locus:** `selection.wrong_default` (`correlation` + `partial_correlation` pair).
- **Stability:** `partial` (2/3 identical, 1 diverges under strong causal cue).

### Interpretation
The LLM recognizes "confounding" as a concept but does not know the
AtomicSpec primitive (`observe` + `intervene` arms, `gap_material`
assertion). This matches exactly what the A/B/C diagnostic found:
confounding is fixed by a worked example that demonstrates the
observe-vs-intervene pattern. No other recipe gap layered on top.

---

## SQ-A1 — Direct causal question

All three surface forms of SQ **SQ_F01**: "Does treatment affect
outcome?" Families: `[SQ-A1]` (single-family). Regime: `do`. Truth
value: TRUE (ATE(T→Y) ≈ 0.68 in W1).

### Gold recipe
```
1 spec | arms=[intervene] | measurement=mean
      | comparison=difference | assertion=positive
```

### Compiler outputs

| Surface form | difficulty | Compiler output |
|---|---|---|
| s0 — "Does treatment affect outcome?" | easy | `adjust` + `mean` + `distinguishable` |
| s1 — "What is the causal effect of treatment on patient outcomes?" | medium | `adjust` + `mean` + `distinguishable` |
| s2 — "If we were to intervene and change the treatment level..." | hard | `adjust` + `mean` + `distinguishable` |

### Canonical wrong recipe
**`adjust` arms + `distinguishable` assertion — identical across all 3.**
The compiler defaults to an adjust-based spec with a directionless
assertion (`distinguishable` asks only "are the arms different?", not
"in which direction?"). Gold requires `intervene` + `positive` (signed).

### Error invariance across paraphrases
- **Total (3/3 identical output).** Even s2, which explicitly says "if
  we were to intervene", produces the same `adjust` spec as the bare "Does
  X affect Y?" question. The strongest possible causal cue in natural
  language fails to route the compiler to an `intervene` arm.

### Classification
- **Locus:** `selection.wrong_default` (fixed `adjust + distinguishable`).
- **Stability:** `invariant` (3/3 byte-identical output).

### Key observation — causal cue does not override the default
The system prompt of the claim compiler (`src/sreg/tools/oi_extraction.py`
line 477) explicitly instructs the model that causal claims require
interventional arms. Despite that, all three paraphrases — including
s2 which literally says "if we were to intervene" — produce `adjust`
arms. The strongest possible causal cue in both the user text AND the
system instruction is insufficient to move the default. This suggests
the routing is fixed at a level the prompt cannot reach with cues
alone; either an exemplar or a structural change (e.g. required-role
enforcement) is likely necessary.

### Interpretation
**Single stable wrong default.** The cleanest signal in the audit:
one recipe, three paraphrases, one output. No lexical fragility —
any fix has to change the default response to direct causal SQs;
no paraphrase engineering will help.

### Caveat — verdict-fail bucket inflated by verifier contract mismatch
**Finding from Codex code review (2026-04-15):** in
`src/sreg/tools/oi_verifier.py` the `comparison=difference` branch
(line ~622) produces a result dict with `{difference, ref, other}`,
but the `DISTINGUISHABLE` assertion (line ~800) only reads
`comparison_result["value"]`. That key is absent from the dict
produced by `difference` comparisons, so `distinguishable` returns
`holds=false` even when the actual difference is clearly non-zero.
This is why SQ_F01 specs with a large positive ATE (0.68) appear as
verdict-fails — the verifier contract is under-specified, not the
compiler's computation.

**Implication for this audit.** The compiler is still structurally
wrong against gold (uses `adjust` instead of `intervene`, uses a
directionless assertion where gold requires a signed one). But the
specific failure flag for SQ-A1 targets in `compiler_baseline_failures.json`
is **partially explained by the verifier bug**, not only by the
recipe-selection gap. Tracked as a new item in I-027. Classification
above is unchanged — the `adjust + distinguishable` recipe is still
the wrong recipe for a TRUE direct causal claim — but the failure
magnitude is inflated by this upstream issue.

---

## CC-A7 — Tail risk (probability of extreme outcome)

Two surface forms of fact **W3_F04**: "Extreme heat creates tail risk for
health." Families: `[CC-A7]` (single-family). Regime: `do`. Truth value:
TRUE. World: W3 (environmental health).

### Gold recipe
```
1 spec | arms=[intervene] | measurement=tail_prob
      | comparison=difference | assertion=negative
```
(Negative because the contrast measures health delta under high-heat
intervention; higher heat reduces the tail mass of healthy outcomes.)

### Compiler outputs

| Surface form | difficulty | Compiler output |
|---|---|---|
| s0 — "Extreme heat creates a significant risk of very poor health." | medium | `adjust` + `tail_prob` + `positive` |
| s1 — "The probability of health falling below a critical threshold is much higher at elevated temperatures than at low." | hard | `condition` + `tail_prob` + `greater_than` |

### Canonical wrong recipe
No single canonical recipe — **the two surface forms produce structurally
different outputs.** Both share `tail_prob` measurement (right primitive),
but diverge on arm kind (`adjust` vs `condition`) and assertion kind
(`positive` vs `greater_than`). Both disagree with gold on arm kind (not
`intervene`) and assertion direction (not `negative`).

### Error invariance across paraphrases
- **None.** The 2 paraphrases produce structurally different wrong specs.
  The compiler knows "this is about tail risk" (measurement stays
  correct) but every slot around it is filled differently per paraphrase.

### Classification
- **Locus:** `assembly.slot_filling` (measurement right, arms + assertion wrong).
- **Stability:** `fragile` (2/2 different outputs).

### Interpretation
The compiler has the right measurement primitive (`tail_prob`) but
cannot commit to a stable filling of the surrounding slots. Different
wordings trigger different (still wrong) arm kinds and assertions.
This is a different failure profile from CC-A5 and SQ-A1: the recipe
SELECTION is approximately correct; the compiler just cannot fill it
in consistently. Likely fix: an exemplar that shows the canonical
arm+assertion pairing for tail risk, not a recipe-selection hint.

---

## CC-D2 — Mediation vs confounding (same 3 vars, different structure)

Two surface forms of fact **W2_F07**: "Adjusting for the collider
introduces bias." Families: `[CC-D2, CC-B2]` (decision boundary +
role disambiguation). Regime: `adjusted`. Truth value: TRUE (W2 has a
collider structure; adjusting for it opens a spurious path).

### Gold recipe
```
1 spec | arms=[baseline] | measurement=identifiability_check
      | assertion=not_identifiable
```
The gold verifier uses an **identifiability_check primitive** — this
answer is not a distributional contrast but a structural claim about
the SCM: "this estimand is not identifiable under the given adjustment
set".

### Compiler outputs

| Surface form | difficulty | Compiler specs |
|---|---|---|
| s0 — "Adjusting for the collider introduces bias." | medium | 2 specs, `baseline` arms, `partial_correlation` + `correlation`, assertions `not_distinguishable` + `near_zero` |
| s1 — "Conditioning on the collider opens a spurious path..." | hard | 4 specs, mix of `intervene`/`baseline`/`condition` arms, `mean` + `partial_correlation` + `correlation`, all assertions `distinguishable` |

### Canonical wrong recipe
No stable recipe. **Both specs reach for statistical-distribution
primitives (`correlation`, `partial_correlation`, `mean`) and never
touch `identifiability_check`.** s1 scales up to 4 specs as the
wording becomes more technical.

### Error invariance across paraphrases
- **None.** s0 and s1 are structurally different; complexity scales
  with wording complexity (1 wording → 2 specs; harder wording → 4
  specs). That pattern suggests the compiler uses the wording as a
  cue for *how much structure to emit*, not *which primitive to pick*.

### Classification
- **Locus:** `selection.catalog_visibility_gap` (`identifiability_check`
  never reached; unclear if catalog lacks it or routing can't select it).
- **Stability:** `fragile` (2/2 different outputs; complexity scales
  with wording).

### Interpretation
The compiler appears unable to reach `identifiability_check` as a
measurement kind. It maps "adjustment / conditioning / collider /
spurious path" vocabulary to statistical comparisons. Even the word
"spurious path" in s1 does not route to identifiability. This is
qualitatively different from CC-A5: in CC-A5 the compiler has SOME
canonical wrong recipe; here it has no recipe at all and synthesizes
a collection of statistical comparisons per paraphrase. Whether this
is a **catalog gap** (the primitive is not listed in the system prompt)
or a **routing gap** (it is listed but the LLM does not reach it) is
not determined by this audit and requires inspecting the compiler
prompt content. Likely fix regardless: inject an exemplar that uses
`identifiability_check` explicitly, and confirm the catalog exposure.

---

## Summary — failure mode per family

| Family | Locus | Stability | Proposed fix class |
|---|---|---|---|
| **CC-A5** Confounding | `selection.wrong_default` (`partial_correlation`) | `partial` (2/3 identical) | Exemplar of observe-vs-intervene contrast (confirmed works in A/B/C test) |
| **SQ-A1** Direct causal Q | `selection.wrong_default` (`adjust + distinguishable`) | `invariant` (3/3 identical) | Change the default response to direct causal SQs; no paraphrase engineering will help. Also fix verifier `difference + distinguishable` contract (I-027) |
| **CC-A7** Tail risk | `assembly.slot_filling` | `fragile` (2/2 different) | Exemplar of canonical arm + assertion pairing for `tail_prob`; recipe selection is ~OK |
| **CC-D2** Mediation-vs-confounding | `selection.catalog_visibility_gap` | `fragile` (2/2 different) | Verify `identifiability_check` is in the primitive catalog; add a collider exemplar |

### Cross-family observations

1. **Recipe selection dominates slot filling** as a failure mode. 3 of
   the 4 families fail at selection; only CC-A7 fails at filling.
2. **"Default recipes" are strongly stable** when they exist. SQ-A1 is
   3/3 byte-identical across paraphrases; CC-A5 is 2/3 identical. That
   stability is useful — it means a targeted exemplar has a high
   chance of flipping ALL surface forms at once.
3. **Missing primitives** (CC-D2) look different from wrong recipes
   (CC-A5): more specs, more variability, larger fail surface. These
   cases may need catalog-level fixes, not prompt-level fixes.
4. **Lexical fragility is the minority pattern**, confined to CC-A7.
5. **`comparative` regime is fully broken** (3/3 in W1_F07). That's not
   one of the 4 target families — it's a cross-cutting observation
   from the pattern breakdown (§ suite2_pattern_breakdown.md). All 3
   comparative-regime fails in W1_F07 are within CC-A5 (confounding),
   which already dominates this audit. No independent comparative-regime
   failure mode is visible beyond CC-A5.

### Relationship to the A/B/C diagnostic

The baseline's diagnostic run (`scripts/prompt_diagnostic.py`) tested
only 3 cases: W1_F05 (mediation — not in this audit), W1_F07
(confounding = CC-A5 above), and W1_F06 (heterogeneity — CC-A4, not a
zero-candidate family). That diagnostic found:
- **CC-A5 fixed by exemplar.** ✅ Consistent with our analysis: stable
  recipe selection failure, single dominant wrong recipe.
- **Mediation (CC-A3) and heterogeneity (CC-A4)** failed the diagnostic
  in different ways. Those are NOT zero-candidate families (they have
  some passes), so they don't appear here.

The zero-candidate families not yet tested with exemplars are **SQ-A1,
CC-A7, CC-D2**. This audit identifies the failure class for each, so
the next ablation can test a targeted exemplar per failure class
rather than a generic worked example.

---

## What this audit does NOT answer

- **The 6 `full_pass` targets** — blocked, requires full per-target
  dump (I-027 item 4). The question "are those 6 passes by correct
  reasoning or by accident?" stays open.
- **The 11 `real_struct_err` targets** (verdict correct by accident) —
  also blocked on the full dump. These are the highest-risk category
  in the baseline because they silently pass verdict but emit wrong
  specs; in a world with different SCM parameters they would silently
  fail.
- **The 11 verdict-fails NOT in zero-candidate families** — these come
  from mixed-signal families (CC-A1, CC-A3, CC-A4, CC-B5, CC-E2,
  SQ-A3) where the compiler sometimes gets it right and sometimes
  doesn't. Auditing them is useful but lower signal-to-noise than
  the 10 audited here.
- **The missing 22nd verdict-fail.** The baseline doc reports 22
  verdict-wrong; the dump has 21. The missing row is tracked in I-027
  item 1 and may belong to one of our 4 audited families.

## Next implied steps

1. **Targeted exemplar ablation** for each of the 4 families, using
   the failure-class classification above to choose the exemplar type
   (pattern recipe vs slot filling pair vs primitive catalog
   expansion). That is a Suite 2 close-out step (Task #16 / I-007),
   not this audit.
2. **#11b** (audit of `full_pass` + `real_struct_err`) waits on
   I-027 item 4.
3. **Formal name for the metric used throughout this audit**:
   `verdict_fail` in the Suite 2 baseline equals
   `N - effective_pass - stage1_fail - real_struct_err`. This audit is
   a slice of `verdict_fail`, not of the full error surface.
