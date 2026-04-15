# Suite 2 — Claim Compiler Baseline Report

> **Status:** CANON evaluation result. **Canonical dump is v2** (post-verifier-fix).
> **Dates:** 2026-04-14 (v1 baseline) · 2026-04-15 (v2 re-baseline after verifier fix).
> **Origin:** Suite 2 (Translation/Compilation).
> **Issue:** I-007.
> **Canonical raw data:** `research/synthesis/compiler_baseline_full_dump_v2.json`
> (all 55 targets, 5 buckets, round-trip-safe AtomicSpec dumps).
> **Historical v1 data:** `research/synthesis/compiler_baseline_failures.json`
> (21 verdict failures only — kept for traceability to the 2026-04-14 analysis).
>
> 📎 **Addendum 2026-04-15** appended at §9 documents the v1→v2 delta, the
> verifier-fix impact, and the SQ-A1 hypothesis confirmation. **Read §9
> before citing any headline number** — §§1–8 are the 2026-04-14 narrative
> preserved verbatim.

## TL;DR

Suite 2 ran the current LLM claim compiler against 55 hand-crafted gold
targets across 3 research-grade worlds. The compiler **effectively passes
31% of them** (17/55) and fails 69% (38/55) with errors that would corrupt
the training signal in a real investigation episode.

A follow-up diagnostic (A/B/C test over 3 canonical patterns) confirms
that the dominant failure mode is **recipe gap**: the LLM recognizes the
claim pattern by vocabulary ("mediation", "confounding", "heterogeneity")
but does not know how to compose the AtomicSpec that verifies it. Adding
pattern-specific worked examples to the compiler prompt demonstrably
fixes at least one of the three canonical failure cases in isolation.

This report documents what the suite caught. It does **not** propose
fixes — that is out of scope for the evaluation lane. Follow-up design
work is tracked in related issues (see §7).

## 1. Setup

**What was evaluated**
- Target: `compile_claim_direct` in `src/sreg/tools/oi_extraction.py` — the
  grammar-direct claim compiler, single LLM call producing AtomicSpecs.
- Model: Azure `gpt-5.4` (project default for compiler).
- Temperature: 0.

**Gold set**
- 55 gold targets across 3 worlds (W1/W2/W3 of Suite 2).
- Each target is a (claim_text, expected_verdict, structural_contract) triple
  derived bottom-up from SCM equations — the facts are analytical truths about
  the world, phrased as natural language claims at 3 difficulty levels.
- Source: `tests/eval/suite2_translation/`.

**Evaluation method: verificational equivalence**
- A compiler output "passes" if the specs it produces, when run against the
  SCM, yield the same verdict (TRUE / FALSE / NOT_IDENTIFIABLE) as the gold.
- Different structural paths to the same answer are accepted (see §2, "adjust-swap").

## 2. Headline results

Over 55 gold targets:

| Category | N | % | Meaning |
|---|---|---|---|
| Full pass (3/3 stages correct) | 6 | 11% | Compile decision, structure, and verdict all match |
| Adjust-swap only (benign S2 mismatch) | 11 | 20% | Verdict correct; used `adjust` arms where gold used `intervene` — same math, different representation |
| Real structural error (S2 broken, verdict by luck) | 11 | 20% | Structure is wrong but verdict lands right for accidental reasons |
| Verdict wrong | 22 | 40% | Compiler produced a spec whose SCM verdict differs from gold |
| Stage 1 fail (wrong compile/abstain decision) | 5 | 9% | Abstained when should have compiled, or vice versa |

**Derived metrics:**
- **Effective pass rate: 31%** = 17/55 (full pass + adjust-swap). These
  are the cases where the compiler would not corrupt a real episode's score.
- **Real error rate: 69%** = 38/55. Errors that would actively mislead
  scoring if they occurred during a live run.

The 20% "real structural error" bucket is notable: verdict is correct, but
for the wrong reason. This is worse than failing cleanly — in a real run,
these would inflate compiler reliability estimates while producing
randomly-correlated training signal.

## 3. Diagnostic: A/B/C prompt test

To separate *recipe gap* ("LLM doesn't know how to compose the spec")
from *recognition gap* ("LLM doesn't realize which pattern applies")
from *capability gap* ("LLM can't do this at all"), we ran a controlled
3-condition test on 3 representative failing cases.

**Conditions:**
- **A) Baseline** — current prompt.
- **B) + Exemplar** — same prompt plus an abstract worked example of the
  relevant pattern (mediation / confounding / heterogeneity recipe, no
  case-specific details).
- **C) + Hint only** — prompt plus a one-line label ("this is a MEDIATION
  claim") without any recipe.

**Results:**

| Case (world, claim) | A) Baseline | B) + Exemplar | C) + Hint |
|---|---|---|---|
| W1_F05 — "Compliance mediates treatment→outcome" | OK by accident (3 association specs; correct verdict for wrong reason) | WRONG (recipe right, assertion wrong) | WRONG |
| W1_F07 — "Severity confounds treatment→outcome" | WRONG (used partial_correlation) | **✅ OK** (observe vs intervene + contrast_diff) | WRONG (malformed arms) |
| W1_F06 — "Effect of treatment on outcome depends on biomarker" | timeout | WRONG (copied 4-arm skeleton but omitted `condition_on`) | WRONG |

**Script:** `scripts/prompt_diagnostic.py`.

## 4. Interpretation

### 4.1 Confounding: recipe gap, confirmed

Baseline produces `partial_correlation` specs — a textbook beginner mistake
for confounding. Exemplar fixes it cleanly by demonstrating the correct
observe-vs-intervene pattern. Hint alone does not fix it.

**Conclusion:** the LLM recognizes "confounding" as a concept but does not
know the AtomicSpec recipe that verifies it. This is recipe gap, not
recognition gap.

### 4.2 Mediation: accidental-success pathology

Baseline "passes" by producing three independent association specs
(T↔M, M↔Y, T↔Y). In W1 all three are positive, so the combined verdict
matches gold. But the compiler is not measuring the indirect effect — it
is measuring three unrelated correlations. In a world where T→M and M→Y
had opposite signs (valid mediation, different pattern), the same compiler
output would silently disagree with ground truth.

**Conclusion:** the headline 11% full pass may overstate real compiler
quality. Some of those "passes" are this failure mode in disguise.

### 4.3 Heterogeneity: recipe gap with deeper structure

Even with an exemplar, the compiler copied the 4-arm skeleton but omitted
the `condition_on` subgroup selectors — the single feature that
distinguishes heterogeneity from a simple ATE. This suggests the exemplar
we tried is insufficient, not that the capability is missing. A better
exemplar (more explicit about why `condition_on` is required) or a
two-step compiler (pattern recognition → targeted composition) might close
this. We did not test that here.

### 4.4 Overall

The dominant failure mode is **compositional recipe knowledge**, not
semantic understanding. The LLM knows the vocabulary; it does not know
how to build the verifier query for each pattern. This is a
prompt-engineering problem, not a capability ceiling.

Equally important: the compiler **does not have access to the SCM DAG**
in its prompt, and we did not test whether giving it DAG access would
help. Separate architectural debate, tracked in follow-up issues.

## 5. What Suite 2 caught that we did not previously know

1. **The headline pass rate is low** (31%). This was not previously
   quantified — prior pilots worked with small ad-hoc sets and no
   controlled gold.
2. **Verdict-by-accident is a measurable bucket** (20% of targets).
   Existing validation methods that check only the final verdict would
   mis-classify these as compiler wins.
3. **Adjust-swap is a real phenomenon, and benign** (20%): the compiler
   frequently uses `adjust` arms where gold uses `intervene`. For the
   subset of claims where these are mathematically equivalent (linear
   effects on continuous outcomes), verdicts match. This suggests a
   family of equivalences the suite can encode as `alternative_atoms`.
4. **Recipe gap is isolable from recognition gap** via a short A/B/C test.
   That diagnostic protocol is reusable for future compiler revisions.

## 6. What this does NOT say

- Suite 2 does **not** measure end-to-end training quality. A bad
  compiler may or may not degrade trained-agent behavior; that is
  Suite 5's question.
- Suite 2 does **not** cover the **SQ compiler** (Flow B) with the same
  depth. Only the claim compiler (Flow A) has been baselined here.
- The diagnostic A/B/C is **3 cases**, not a statistically powered
  comparison. It is sufficient to falsify the "capability gap" hypothesis
  for the tested patterns; it is not sufficient to estimate effect sizes
  of a full prompt revision.
- No fix was applied. The report is observational.

## 7. Follow-ups (tracked outside this report)

Design/architectural questions destapadas by this baseline are documented
in `research/notes/sq_flow_and_dag_visibility_open_questions.md` as an
internal briefing. That note enumerates 8 open questions (D1–D8) across
three actors: orchestrator (SQ generation), SQ compiler, and claim
compiler. Those questions should become issues before any fix work starts.

Relevant existing issues:
- **I-003** — claim compiler grammar-direct (pre-existing).
- **I-007** — Suite 2 itself (this report is the first deliverable of the
  baseline track).

Proposed new issues (see §8 of the notes doc for justification):
- **I-024 (research)** — SQ↔DAG coherence audit (D1–D3).
- **I-025 (design)** — Flow B LLM: should prompt include DAG? (D4–D5).
- **I-026 (design)** — Claim compiler recipe exemplars: scope + eval
  protocol (D6–D8).

## 8. Reproducibility

**v2 (canon, 2026-04-15):**
- `scripts/suite2_full_dump_v2.py` — full 55-target dump, 5-bucket
  categorization, round-trip-safe. **Run this to reproduce the headline.**
- Output: `research/synthesis/compiler_baseline_full_dump_v2.json`
  (+ `.jsonl` stream log, + derived `compiler_baseline_failures_v2.json`).

**v1 (historical, 2026-04-14):**
- `scripts/analyze_compiler_results.py` — v1 category breakdown (the
  original baseline runner).
- `scripts/dump_compiler_output.py` — v1 per-failure dump (lossy for
  adjust arms — see §9.2 for why this was replaced).
- Output: `research/synthesis/compiler_baseline_failures.json` (21
  verdict_fails, pinned for traceability to §§1–8 of this doc).

**Shared:**
- `scripts/prompt_diagnostic.py` — A/B/C test (§3). Still valid.

**Gold set:**
- `tests/eval/suite2_translation/fact_tables.py`
- `tests/eval/suite2_translation/gold_targets.py`
- `tests/eval/suite2_translation/worlds.py`

To reproduce the canonical (v2) baseline:
```bash
conda activate sreg
python scripts/suite2_full_dump_v2.py  # ~6 min, 55 LLM calls
```
Requires Azure credentials in `.env`.

---

## 9. Addendum 2026-04-15 — v2 re-baseline after verifier fix

### 9.1 Why v2 exists

During the v1 close-out (2026-04-14) Codex spotted a verifier contract
mismatch (I-027 item 5): `ComparisonKind.DIFFERENCE` produces a dict
`{difference, ref, other}`, but `AssertionKind.DISTINGUISHABLE` was
reading `"value"` — a key that doesn't exist in that dict. Result:
`DIFFERENCE + DISTINGUISHABLE` always returned `holds=False`, regardless
of the actual magnitude.

This is **verifier (ground-truth machinery), not compiler**. The fix
was in scope because the verifier defines what "correct" means; leaving
a broken verifier in place would contaminate every future eval.

**Fix applied** (`src/sreg/tools/oi_verifier.py:800-815`): magnitude-based,
`abs(scalar) > tol`, with a bool fast-path so `IDENTITY +
IDENTIFIABILITY_CHECK` semantics are preserved. Guarded by 4 new unit
tests in `TestAssertDistinguishable`. Suite 1 core correctness still
52/52.

### 9.2 Sequence of fixes and artifacts (2026-04-15)

1. **Verifier fix** + 4 unit tests → `oi_verifier.py`, `test_oi_verifier.py`.
2. **Offline re-verify of v1's 21 verdict_fails** → blocked for 11/21
   entries because `scripts/dump_compiler_output.py` was lossy for adjust
   arms (missing `treatment`, `outcome`, `adjust_set`, `sweep_*`).
   Documented in `compiler_baseline_reverify_summary.json`. This forced
   the move to a full re-baseline.
3. **Round-trip test for AtomicSpec serialization** (6 tests in
   `TestAtomicSpecRoundTrip`) → guarantees `model_dump(mode="json")` +
   `model_validate()` preserves every spec field across all arm kinds,
   measurements, comparisons, and assertions.
4. **Expanded dumper** `scripts/suite2_full_dump_v2.py` — all 55 targets,
   5-bucket categorization, round-trip-safe persistence.
5. **Full re-baseline** — 55 fresh LLM calls, ~5:42 min. Output:
   `compiler_baseline_full_dump_v2.json` + `compiler_baseline_failures_v2.json`.

### 9.3 v2 headline results

| Bucket | v1 (2026-04-14) | v2 (2026-04-15) | Δ |
|---|---|---|---|
| `full_pass` (stage 1+2+3 all OK) | 6 | **7** | +1 |
| `adjust_swap` (arm_kinds-only S2 mismatch, S3 OK) | 11 | **10** | -1 |
| `real_struct_err` (other S2 error, S3 OK — pass-by-accident) | 11 | **13** | +2 |
| `verdict_wrong` (S2 OK, S3 wrong) | 22 | **19** | -3 |
| `stage1_fail` (compile decision wrong or compiler crash) | 5 | **6** | +1 |

**Headline metrics** (nomenclature per I-027 item 6):

- `strict_full_pass_rate` = **7/55 = 13%** (was 6/55 = 11% in v1).
- `effective_pass_rate` = **17/55 = 31%** (identical to v1 — the bucket
  shuffle is internal).
- `real_error_rate` = **38/55 = 69%** (identical to v1).

**Qualitative conclusion unchanged:** severe recipe gap; most failures
are compositional (the LLM names the pattern but can't compose the
spec). The fix didn't rescue the baseline — it sharpened it.

### 9.4 SQ-A1 hypothesis — CONFIRMED

Codex predicted that adjust-arm + distinguishable targets would be
disproportionately affected by the bug. Verified:

- All three `SQ_F01_s{0,1,2}` moved from v1 `verdict_fail` → v2
  `real_struct_err`.
- Stage 3 (verdict) now **passes** for SQ-A1 — the verifier fix reaches
  them.
- Stage 2 (structure) still **fails** — the compiler emits `adjust` arms
  + `distinguishable` assertion where gold expects `intervene` +
  `positive`. Both are real recipe gaps, independent of the verifier bug.

This is exactly the expected outcome of separating machinery bugs from
compositional gaps. The verifier artifact was load-bearing for verdict
bucketing but not for stage 2.

### 9.5 Internal bucket shuffle — which IDs moved

Using the v1 `compiler_baseline_failures.json` (21 verdict_fails) as the
reference set:

- **3 → `real_struct_err`** (verdict now correct, structure still wrong):
  `SQ_F01_s0, SQ_F01_s1, SQ_F01_s2` — the SQ-A1 case above.
- **1 → `full_pass`** (verdict now correct, structure OK, stage 1 OK):
  `W2_F09_s0` — clean flip thanks to the fix.
- **2 stage1_fail additions** that weren't in v1's bucketing:
  - `W3_F03_s0, W3_F03_s2` — compiler crashed on `sweep_values` emitted
    as a list inside `arm.values` (schema violation). This is a
    **separate compiler bug** surfaced by the new dump, not an effect of
    the verifier fix. Tracked as a new issue (see §9.7).
- **Remaining v1 verdict_fails** (~15) stayed in `verdict_wrong` or
  moved within structural-error buckets due to LLM non-determinism at
  `temperature=0` (small rewrite drift across runs, expected).

### 9.6 Full IDs per v2 bucket

For downstream audit work (Task #11b):

**`full_pass` (7)** — correct at all 3 stages:
- `SQ_F07_s0` (abstain-correct: gold=abstain, compiler abstained)
- `W1_F09_s0, W2_F06_s0, W2_F09_s0, W2_F09_s1, W3_F05_s1, W3_F05_s2`

**`adjust_swap` (10)** — benign S2 arm_kinds mismatch:
- `W1_F01_s0, W1_F01_s1, W1_F03_s0, W1_F03_s1, W2_F01_s0, W2_F01_s1,
  W2_F11_s0, W2_F11_s1, W3_F08_s0, W3_F08_s1`

**`real_struct_err` (13)** — pass-by-accident pathology:
- `SQ_F01_s0, SQ_F01_s1, SQ_F01_s2, W1_F04_s1, W1_F05_s0, W1_F05_s2,
  W1_F09_s1, W2_F02_s0, W2_F02_s1, W2_F02_s2, W2_F06_s1, W2_F07_s0,
  W3_F08_s2`

**`verdict_wrong` (19)** — structure OK per gold contract, verdict wrong:
- `W1_F01_s2, W1_F03_s2, W1_F04_s0, W1_F04_s2, W1_F05_s1, W1_F06_s0,
  W1_F06_s1, W1_F06_s2, W1_F07_s0, W1_F07_s1, W1_F07_s2, W2_F01_s2,
  W2_F04_s0, W2_F04_s1, W2_F07_s1, W3_F03_s1, W3_F04_s0, W3_F04_s1,
  W3_F05_s0`

**`stage1_fail` (6)** — see §9.7 for split.

### 9.7 `stage1_fail` now mixes two distinct failure modes

The bucket label is no longer atomic. v2 reveals it now conflates:

**(a) Abstain/compile decision errors** (4 entries) — the compiler
compiled when gold said abstain, or vice versa. These are legitimate
stage 1 failures, the original intent of the bucket.
- `SQ_F07_s1` (gold=abstain, compiler compiled)
- `W3_F11_s0, W3_F12_s0, W3_F12_s1` (gold=abstain, compiler compiled)

**(b) Compiler runtime/schema crashes** (2 entries) — the compiler
failed to produce specs on a target where gold expected compilation.
Distinct failure mode: not a decision error, a bug.
- `W3_F03_s0, W3_F03_s2` — `sweep_values` as list inside `arm.values`
  violated the AtomicSpec schema. New issue (see below).

Going forward, `stage1_fail` should either be split (`stage1_decision_fail`
vs `stage1_crash`) or annotated. Added as item 7 on I-027.

### 9.8 New issue spawned from v2

- **I-028** — Compiler emits `sweep_values` as list inside
  `arm.values` (schema violation). Cross-linked from I-027 §9.7.

### 9.9 What v2 does NOT change

- End-to-end conclusion: **effective_pass_rate stable at 31%**, gap is
  dominated by compositional recipe failures, not verifier artifacts.
- A/B/C prompt diagnostic results (§3) — those tests did not hit the
  DIFFERENCE+DISTINGUISHABLE path and remain valid.
- The pass-by-accident pathology (§4.2) — now quantified at 13/55 (24%)
  in v2, up from 11/55 (20%) in v1. Still the most worrying bucket.

### 9.10 Canonicality rule

From this date forward:

- **v2** is the canonical Suite 2 compiler baseline. Cite v2 counts.
- **v1** remains pinned here for traceability of the 2026-04-14 analysis
  (the A/B/C diagnostic and narrative in §§1–8 were produced against it).
- **Never conflate.** When citing bucket counts or IDs, state which
  baseline you mean.
