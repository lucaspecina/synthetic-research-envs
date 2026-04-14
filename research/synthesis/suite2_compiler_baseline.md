# Suite 2 — Claim Compiler Baseline Report

> **Status:** CANON evaluation result.
> **Date:** 2026-04-14.
> **Origin:** Suite 2 (Translation/Compilation), first baseline run.
> **Issue:** I-007.
> **Raw data:** `research/synthesis/compiler_baseline_failures.json` (21 verdict failures, full specs).

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

All scripts are in this branch:
- `scripts/analyze_compiler_results.py` — category breakdown.
- `scripts/dump_compiler_output.py` — per-failure spec dump.
- `scripts/prompt_diagnostic.py` — A/B/C test.

Gold set:
- `tests/eval/suite2_translation/fact_tables.py`
- `tests/eval/suite2_translation/gold_targets.py`
- `tests/eval/suite2_translation/worlds.py`

Raw output:
- `research/synthesis/compiler_baseline_failures.json`

To reproduce: `conda activate sreg && python scripts/analyze_compiler_results.py`.
Requires Azure credentials in `.env`.
