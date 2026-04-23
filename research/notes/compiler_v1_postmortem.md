# Compiler v1 — Post-mortem (ex "90% push diagnosis")

> **ARCHIVAL DOC.** Registro histórico del trabajo sobre el compiler v1
> (epic #36, worktree compiler-fix). El compiler se elimina en v1.5 —
> ver `research/notes/rethink_sreg_2026-04-23.md` seccion **"Lessons
> rescatadas del compiler v1 para v1.5"** para las ideas trasladables
> organizadas por aplicación.
>
> **Cerrado:** 2026-04-23. Último estado: ~82-84% pass rate (v13-v14)
> desde baseline 50.9% (v5). No alcanzó el 90% target; fue superseded
> por el rediseño v1.5.
>
> **Código completo:** `origin/worktree-compiler-fix` (branch de backup).
> **Uso de este doc:** referencia histórica, detalles de baselines,
> crítica Codex en profundidad. Para diseño v1.5, empezar por el
> rethink doc.

---

# Compiler 90% push — exhaustive root-cause diagnosis (original title)

**Context:** User rejected epic closure at 50.9%. Demands >=90% without overfitting to eval. Each fix must pass triple filtro (universal rule, no LLM in truth, works for all research types, not hackable).

**Baseline:** v5 = 28/55 full_pass = 50.9%. Need 50/55 (90.9%) = +22 targets.

**Source data:** `research/synthesis/compiler_baseline_failures_v5.json` (27 failing targets).

## Root-cause taxonomy

### GROUP P — Compiler PROMPT bug (real defect, prompt fix)

#### P1. Compiler decomposes "approximately X" into lower+upper bound sandwich
**Pattern:** Claim says "effect ≈ 0.7" → compiler emits 2 specs:
  - spec[0]: `greater_than(threshold=0.6)` (lower bound with tol)
  - spec[1]: `less_than(threshold=0.8)` (upper bound with tol)

**Why broken:**
- Fragile: if true value is slightly outside, 1 of 2 specs fails, all_hold=false
- Gold uses 1 spec with sign-only (`positive`), passing regardless of magnitude
- Not a semantic-equivalence issue — compiler is STRICTER than gold, so "if compiler passes, gold would too", but reverse fails

**Cases:** W1_F01_s2 (2→1), W1_F03_s2 (4→2), W1_F06_s2 (4→2), W2_F01_s2 (2→1)

**Fix:** Teach compiler to use single spec with `comparison.min_gap` or `assertion.tolerance` for magnitude claims. Or accept gold's sign-only representation.

#### P2. Recipe G over-applied for single-direction claims
**Pattern:** Claim "direct effect of T on Y beyond M" → compiler applies 4-arm `contrast_diff` pattern (total vs direct). But claim only asks about DIRECT, not about decomposition. Simple 2-arm with M=0 fixed is gold's approach.

**Cases:** W1_F04_s0 (only real_struct_err for contrast_diff mismatch), W1_F05_s2 (applies 4-arm to indirect claim too)

**Fix:** Clarify Recipe G scope — only for claims that explicitly compare total vs direct/indirect. For "direct effect of T holding M constant", use simple 2-arm + difference.

#### P3. Confounder/backdoor uses wrong arm kind
**Pattern:** Claim "adjusting for Z changes observed association" → compiler uses arms `['condition', 'intervene']`. Gold uses `['intervene', 'observe']`.

**Cases:** W1_F07_s0, W1_F07_s1, W1_F07_s2, W3_F04_s0, W3_F08_s2

**Fix:** Teach Recipe H "confounder / backdoor pattern":
  - Observational baseline arm: `kind="observe"` (not `condition`)
  - Interventional arm: `kind="intervene"` with adjust_set={Z} OR raw intervene
  - Gap between them = confounding bias

#### P4. Partial correlation vs correlation for "conditional on Z" claims
**Pattern:** "Controlling for Z, X and Y are [associated/not associated]" → gold uses `partial_correlation(X,Y|Z)`. Compiler uses `correlation` + conditioning arm.

**Cases:** W2_F06_s1

**Fix:** Teach Recipe I "conditional association": when claim says "controlling for Z / given Z / partial", use `measurement.kind=partial_correlation` with `cond_set=[Z]`.

#### P5. Missing Recipe for piecewise / changepoint claims
**Pattern:** "Effect changes sharply at threshold zero" → compiler stage1_fail (abstains/errors). Grammar supports `piecewise_fit` measurement + `changepoint_exists` assertion.

**Cases:** W3_F03_s0, W3_F03_s1, W3_F03_s2

**Fix:** Add Recipe J for changepoint pattern: single arm (baseline), measurement `piecewise_fit`, assertion `changepoint_exists`.

#### P6. Tail/quantile claim direction inversion
**Pattern:** "P(health < threshold) much HIGHER at extreme heat than low" → compiler picked `positive` but world/gold say `negative` at this world's temperatures.

**W3_F04_s1 specific:** World measurement shows P(H<thresh|high_temp)=0.40 < P(H<thresh|low_temp)=0.94 — at low temp, prob of poor health is higher. Either world is bugged or claim is misstated.

**Cases:** W3_F04_s0, W3_F04_s1

**Fix:** First audit W3_F04 world/claim consistency. If world intentionally has U-shape (extreme hot AND cold bad), need different claim framing.

### GROUP F — Flow A structural LIMITS (abstention is correct)

Flow A intentionally has no SCM access. These claims REQUIRE SCM knowledge to verify:

#### F1. Identifiability claims
"Can we estimate the causal effect of X on Y?" — answer depends on observability of confounders, structural relations. Flow A cannot determine this from claim text alone.

**Cases:** W3_F05_s0 (truth=not_identifiable, compiler defaulted identifiable)

**Fix:** Teach compiler: identifiability claims → ABSTAIN. These belong to Flow B (which has SCM).

#### F2. Collider / backdoor structural claims
"Adjusting for collider C introduces bias" — requires knowing C is a collider (structural property). Flow A cannot verify without SCM topology.

**Cases:** W2_F07_s0, W2_F07_s1

**Fix:** Teach compiler: structural-property claims (collider, M-bias, d-separation) → ABSTAIN from Flow A.

### GROUP G — Gold hygiene (objective correction)

Similar to W2_F02 fix: gold over-specifies relative to what claim literally requires.

#### G1. Existence-only claims forced to sign
"Does X affect Y?" (existence only) — gold says `positive`. Claim doesn't specify sign; `distinguishable` is the honest answer.

**Cases:** SQ_F01_s0, SQ_F01_s1, SQ_F01_s2

**Fix:** Update golds to use `distinguishable` when claim asks existence without committing to sign. (Stage 3 will still verify correctly.)

**Justification:** Compiler defaulting to `distinguishable` is MORE faithful to the literal claim. Gold encoding world-truth sign is adding info not present in text.

#### G2. Unclear cases needing individual audit
- W1_F06_s0: `distinguishable != gap_material` — "effect depends on biomarker"; heterogeneity check. Gold wants material gap between levels.
- W1_F07_s2: `near_zero != gap_material` — "severity confounder not mediator" compound claim.

### GROUP E — Evaluator too strict (needs care)

I found NO cases of pure `greater_than(0) ≡ positive` — all stricter-threshold cases are compiler over-specifying magnitude from claim. Adding semantic equivalence in stage 2 would mask real compiler differences.

**Decision:** No stage 2 relaxation. If compiler's spec is STRICTER than gold, fix compiler (it shouldn't be stricter) or fix gold (if compiler is correctly stricter).

## Strategy to reach 90%

Sorted by clarity/correctness (not hackability):

1. **Compiler prompt fixes** (P1-P5) — teach universal rules, no test-specific hardcoding
2. **Abstention prompts** (F1-F2) — principled Flow A limits
3. **Gold hygiene** (G1) — objective claim-literal correction
4. **World audit** (P6) — verify W3_F04 truth_value consistency

## Estimated ceiling per fix category

| Fix | Targets potentially moving to full_pass |
|---|---|
| P1 (approximately-sandwich → single spec) | W1_F01_s2, W1_F03_s2, W1_F06_s2 (if gold fits), W2_F01_s2 → 3-4 |
| P2 (Recipe G scope) | W1_F04_s0, W1_F05_s2 (partial) → 1-2 |
| P3 (confounder/backdoor Recipe H) | W1_F07_s0, W1_F07_s1, W1_F07_s2, W3_F04_s0, W3_F08_s2 → 3-5 |
| P4 (Recipe I partial correlation) | W2_F06_s1 → 1 |
| P5 (Recipe J changepoint) | W3_F03_s0/s1/s2 → 3 |
| P6 (W3_F04 world) | W3_F04_s0, W3_F04_s1 → 1-2 |
| F1 (identifiability abstain) | W3_F05_s0 → 1 (becomes deliberate abstain) |
| F2 (structural abstain) | W2_F07_s0, W2_F07_s1 → 2 (deliberate abstain) |
| G1 (SQ_F01 gold) | SQ_F01_s0/s1/s2 → 3 |
| Mediation Recipe G (better) | W2_F04_s1 → 1 |
| Variance Recipe | W1_F09_s1 → 1 |
| Obs-only discriminator | W2_F02_s2, W3_F08_s2 → 1-2 |
| Complex claims | W1_F04_s2, rest → 0-3 |

**Total potential:** ~22-28 targets can move. 90%+ achievable.

## Open questions to consult with Codex

1. Is it principled to teach compiler to produce SINGLE spec for "approximately X" with tolerance, even though it loses fidelity vs 2-bound sandwich?
2. For Flow A abstention on identifiability/collider — should compiler emit explicit abstain signal, or should we move these facts out of Flow A benchmark?
3. W3_F04 world — if world's U-shape doesn't match claim "higher at elevated temp", is this world bug, claim bug, or legitimate hard case?
4. W1_F06_s2 claim "ATE ≈ 1.0 at high biomarker" but world measures 0.45 — is world underpowered or claim over-ambitious?

---

## CODEX CRITIQUE (2026-04-19) — revised plan

Codex corrected 3 critical mistakes in my v1 taxonomy:

### CORRECTION 1 — P3 is NOT a compiler bug, it's a gold canonicalization issue
- Grammar table in `oi_compiler_prompts.py:52` explicitly deprecates `observe`, tells compiler to use `condition`.
- `oi_verifier.py:124-136` shows `observe` and `condition` execute the SAME underlying operation (sample without intervention, filter).
- So when gold says `['intervene', 'observe']` and compiler says `['condition', 'intervene']`, **the compiler is canonical. The gold uses legacy spelling.**
- **Fix:** canonicalize `observe` → `condition` in gold contracts (or evaluator treats them as aliases). Do NOT re-teach `observe` to compiler.
- Also: my proposed `adjust_set={Z}` language is INVALID — `oi_sq_compiler.py:350` strips it, grammar forbids it.

### CORRECTION 2 — P5 (changepoint) grammar is different than I wrote
- `MeasurementKind` does NOT have `piecewise_fit`. Only `ComparisonKind.PIECEWISE_FIT` exists.
- Correct Recipe J grammar: `arm.kind=sweep` + `measurement.kind=mean` (or target-appropriate) + `comparison.kind=piecewise_fit` + `assertion.kind=changepoint_exists`.

### CORRECTION 3 — P1 sign-only would be metric-chasing
- Teaching compiler to use single sign-only spec for "≈ X" claims throws away numeric content.
- Principled options: (a) add real approximate-equality semantics to IR/evaluator, OR (b) audit world/claim consistency when world numerically fails the claim.
- W1_F06_s2 ("ATE ≈ 1.0" but world gives 0.45) → compiler is not the defect. World/claim mismatch is the real issue.
- **Defer P1 last.** Don't make compiler dumber to pass stage 2.

### REVISED categories

- **GROUP P (real compiler defects):** P2 (Recipe G scope), P4 (partial_correlation), P5 (Recipe J for changepoint, corrected grammar).
- **GROUP F (Flow A abstention, benchmark-contract fix):** F1 (identifiability), F2 (collider/structural topology). Frame as "these facts are Flow-B only or gold_status=abstain" — NOT a compiler win.
- **GROUP C (canonicalization):** `observe` ≡ `condition` in stage 2. Gold audit pass.
- **GROUP G (gold hygiene, strict rule):** only when gold encodes info absent from claim. SQ_F01_s0/s1/s2 clear. Never "gold follows compiler" heuristically.
- **GROUP W (world/claim audit):** W3_F04 (tail dir inversion), W1_F06_s2 (magnitude mismatch).
- **GROUP P1 (approx-eq semantics):** last. Needs real IR extension, not compiler simplification.

### Revised priority order

1. Real compiler bugs: P4 → P2 → P5(corrected)
2. Benchmark-contract: F1/F2 abstain + C canonicalization + G1 gold hygiene
3. World/claim audit: P6 (W3_F04, W1_F06_s2)
4. Approximate-eq semantics: P1 last with real grammar/evaluator extension

### New categories Codex flagged

- **Compound-claim under-spec:** W3_F08_s2 gold missing observational half (gold bug, not compiler). Need audit.

---

## Final implementation log (2026-04-19 evening)

### Progression table

| Version | Pass% | Note |
|---|---|---|
| v5 (original epic cierre) | 50.9% | H6 W2_F02 gold hygiene |
| v7 | 54.5% | SQ_F01 gold hygiene + W1_F07 canonicalization |
| v8 (LLM) | 52.7% | Recipe J + Recipe G-simple — mix wins/losses |
| v9 | 58.2% | sweep_var evaluator bug fix |
| **v10** | **69.1%** | **Coverage matcher stage 2 (Codex-recommended)** |
| v11 (LLM) | 61.8% | tail_prob sign + ATE disambiguation |
| v12 | 76.4% | coverage matcher on v11 |
| **v13** | **81.8%** | **Assertion entailment (greater_than ≥ tol → positive)** |
| v14 | 83.6% | alternative_atoms W2_F04 + W1_F07_s2 |
| v15 (LLM) | 58.2% | Abstention section 6 + per-unit scaling + modifier focus (TOO aggressive abstain) |
| v16 | 81.8% | coverage matcher on v15 |
| v17 (LLM) | TBD | Refined narrow abstention |
| v18 | TBD | coverage matcher on v17 |

### Design artifacts introduced

1. **Coverage matcher stage 2** (`tests/eval/suite2_translation/test_compiler_llm.py:check_stage2` + parallel in `scripts/suite2_rescore_*.py`): replaces single-contract-per-atom with per-gold-atom structural-signature matching. Extras accepted as auxiliaries. Adjust ≡ intervene normalization.

2. **Assertion entailment** (`_assertion_entails` in same): tolerance-aware logical entailment. `greater_than(threshold=t)` covers gold `positive` iff `t >= gold_tol`. Same for `less_than` ↔ `negative`. Mathematically airtight.

3. **Recipe J** (`oi_compiler_prompts.py` after Recipe G): sweep arm + mean + piecewise_fit comparison + changepoint_exists assertion.

4. **Recipe G-simple** (inline in Recipe G section): 2-arm CDE pattern for "direct effect holding M constant" claims, separate from 4-arm contrast_diff.

5. **ABSTENTION section 6 (refined narrow)**: pure structural-role label claims ("the collider variable") with no named variable → abstain. Text cues ("unmeasured factor", "hidden") → compile.

6. **Per-unit scaling (prompt)**: per-unit effect claims need T=1.0 vs T=0.0, not T=0.5 vs T=0.0.

7. **Modifier focus (`test_compiler_llm.py:_make_claim_card`)**: contract.required_modifier/mediator added to claim.focus_variables so compiler knows biomarker/mediator variable.

### Gold changes (per-case hygiene)

1. **SQ_F01 s0/s1/s2**: `POSITIVE → DISTINGUISHABLE` (claim asks existence without sign).
2. **W1_F07**: `OBSERVE → CONDITION` (legacy kind → canonical).
3. **W2_F04 s0/s1**: added `alternative_atoms` for chain decomposition (E→M pos + M→D pos ≡ indirect pos in linear SCM).
4. **W1_F07_s2**: added `alternative_atoms` for structural decomposition (S→T|Y, S→Y|T, S-not-downstream-of-T ≡ confounder-not-mediator structure).
5. **W2_F07 s0/s1**: `compile → abstain` (pure collider-role label, no named variable).

### Flow B implications

All prompt changes apply to both Flow A (`oi_extraction.py`) and Flow B (`oi_sq_compiler.py`) via shared `TARGETED_RECIPE_EXEMPLARS` + `ABSTENTION_EXEMPLARS`. Grammar validator changes (QueryArm) also apply to both. Only stage 2 / gold changes are Suite-2-Flow-A specific (since only Flow A is tested in Suite 2).

### Remaining Flow A structural limits

Residual targets that won't pass without grammar extension or deep compiler refactor:

- **W1_F05_s2** ("indirect < direct"): requires cross-spec comparison. Grammar has no rank_order between separate specs. Compiler would need to know numerical direct value ex-ante.
- **W1_F06_s0** (heterogeneity `distinguishable` vs `gap_material`): Codex vetoed distinguishable→gap_material entailment.
- **W1_F07_s0/s1** (2-arm difference vs 4-arm contrast_diff for confounding): Codex vetoed (compiler's `not_distinguishable` is semantically opposite).
- **W3_F05_s0** ("Can we estimate?" plain): Flow A cannot determine identifiability without SCM. Accepted as verdict_wrong.
- **W1_F06_s2** (over-decomposition with correct variable B, 8 specs vs 2): compiler now uses right variable via modifier focus, but over-sandwiches.
