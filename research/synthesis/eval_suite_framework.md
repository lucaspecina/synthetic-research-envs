# SREG Evaluation Suite Framework

> **Status:** CANON evaluation.
> **Date:** 2026-04-09, updated 2026-04-12
> **Purpose:** Define what SREG must evaluate to demonstrate it fulfills
> its objective, and how each evaluation layer maps to concrete suites.

## The objective

SREG's goal is to be a **training environment** where RL produces agents
with good scientific judgment. For that to work, a chain of properties
must ALL hold. If any link breaks, the system doesn't fulfill its purpose.

## The 6 evaluation layers

Each layer answers one question. They are ordered by dependency — each
layer assumes the previous ones hold.

```
Layer 1: Mathematical correctness        Suite 1         DONE
Layer 2: Translation fidelity            Suite 2         TODO
Layer 3: Science coverage                Suite 3         TODO (separate lane)
Layer 4: Reward formula properties       Suite 4 A+B     DONE
Layer 5: Training signal quality         Suite 5 (NEW)   TODO — identified gap
Layer 6: Behavioral outcomes             Future          needs trained model
```

### Layer 1 — Is the math correct?
> If the verifier gives wrong answers, nothing else is interpretable.

Evaluates: SCM engine, verifier, scoring arithmetic.
**Suite 1: Core Correctness** — 52 tests, 100% pass.

### Layer 2 — Does translation preserve meaning?
> If "X causes Y" compiles to the wrong spec, correct investigation
> gets wrong scores.

Evaluates: SQ compiler, claim compiler, relevance judge accuracy.
**Suite 2: Translation/Compilation** — TODO.

### Layer 3 — Can the system represent diverse science?
> If SREG only works for "X causes Y", the agent learns one trick.

Evaluates: grammar + compiler + verifier expressiveness across the
full spectrum of scientific question types.
**Suite 3: Science Coverage** — TODO (separate worktree/lane).

### Layer 4 — Does the scoring formula have the right incentives?
> If the formula can be hacked or doesn't reward investigation,
> RL trains for the wrong thing.

Evaluates: formula properties with hand-crafted inputs — investigation
pressure, anti-hack robustness, trajectory ordering.
**Suite 4 A+B** — 25 tests, 100% pass. **Block C** gated on P2.

### Layer 5 — Does the reward signal have enough quality for training?
> If all trajectories score between 0.45 and 0.55, there's no gradient.
> RL learns nothing regardless of how correct the formula is.

This is a **newly identified gap** (2026-04-12). Layers 1-4 verify
that the system is *correct* — but correctness is not sufficient for
training. The reward must also have sufficient **diversity, sensitivity,
and discrimination** to provide a useful training signal.

**Key questions:**
- **Score spread**: Do real runs produce scores distributed across a
  wide range, or do they cluster in a narrow band?
- **Score sensitivity**: Does a small improvement in investigation
  quality produce a measurable increase in score?
- **Score stability**: Does the same quality of investigation produce
  similar scores across different runs? (low noise)
- **Score discrimination**: Can the system reliably separate good
  investigation from mediocre? Or is there too much overlap?

**How to evaluate:**
- Run the solver over multiple diverse cases (canonical batch or new)
- Analyze score distributions: histogram, variance, inter-quartile range
- Compare score distributions across quality tiers (if trajectory bank
  exists from Block C)
- Measure score-quality correlation (requires human quality labels or
  proxy)
- Check per-component contribution: is the signal coming from
  correctness? coverage? efficiency? or is one term dominating?

**Dependency:** Requires Layers 1-4 to be characterized. Also benefits
from Layer 3 (diverse cases produce more meaningful distributions).

**Suite 5: Training Signal Quality** — TODO. Design not started.

### Layer 6 — Does training produce the right capabilities?
> The ultimate test: does an agent trained on SREG actually develop
> good scientific judgment?

This is qualitatively different from Layers 1-5. Those evaluate the
*system*. This evaluates the *outcome of training on the system*.

Evaluates: whether SREG's evolutionary pressures produce the 16
desired behavioral properties (see PROJECT.md). Requires controlled
scenarios that isolate specific capabilities.

**Future: Behavioral Ablation Evals** — idea stage. See dedicated
section below.

---

## Why this exists

SREG v1 is evaluated today with qualitative E2E runs over 12 diverse
worlds. That gives intuition but not defensible evidence for a thesis.

The 6 layers above define WHAT must be true. The suites below define
HOW to measure each layer systematically.

The thesis evaluation framework (`thesis_evaluation_framework.md`) defines
WHAT to demonstrate. This document defines HOW to measure it.

---

## The 4 suites

### Suite 1: CORE CORRECTNESS

**Question:** If we give the system a well-defined formal question about
a known world, does it return the correct answer?

**What it evaluates:** The mathematical substrate — SCM engine, verifier,
and mechanical scoring aggregation. No LLM involved.

**Unit of evaluation:** `(AtomicSpec, SCMWorld) -> AtomVerdict`

**Design:** Small hand-crafted SCMs with closed-form solutions (linear
equations). For each world, a table of AtomicSpecs where we know the
expected verdict a priori. Every QueryKind, MeasurementKind,
ComparisonKind, and AssertionKind should be covered by at least one test
case.

**Key metric:** Accuracy (% verdicts matching golden). Target: 100%.
Any failure is a bug, not noise. Only Monte Carlo tolerance (±0.01 at
N=50K) is acceptable.

**Dependency:** None. This is the foundation. If it fails, nothing else
is interpretable.

**Detail doc:** Implemented in `tests/eval/suite1_core_correctness/`
(52 tests, 100% pass, 2026-04-12)

---

### Suite 2: TRANSLATION / COMPILATION

**Question:** Given an SQ or claim in natural language, does the system
translate it correctly into something verifiable?

**What it evaluates:** SQ compiler, claim compiler, and relevance judge
accuracy. These are the LLM-dependent components that sit between human
language and formal specs.

**Unit of evaluation:** `(text_gloss or claim_text, WorldSummary) ->
compiled specs` and `(claim, SQ) -> relevance score`

**Design:** A gold set of ~90-120 items derived bottom-up from SCM
equations, organized in 41 semantic families across 3 research-grade
worlds. Measured by **verificational equivalence** — not string match.
Also includes:
- Paraphrase robustness (same meaning, 3 formulations -> same spec family)
- Abstention correctness (abstains when it should, doesn't when it shouldn't)
- Relevance judge vs human gold (Cohen's kappa, calibration)

**Key metrics:**
- Compile rate by science type
- Abstention precision and recall
- Verificational equivalence rate
- Judge-human agreement (kappa, Spearman rho)

**Dependency:** Requires Suite 1 to pass. If the verifier is broken, we
can't measure verificational equivalence.

**Detail doc:** `eval_suite_translation.md` (design complete, 2026-04-13)

---

### Suite 3: SCIENCE COVERAGE

**Question:** What types of scientific questions can SREG represent and
evaluate today, and where are the boundaries?

**What it evaluates:** The expressive reach of the system — grammar,
compiler, verifier — across the diversity of real scientific inquiry.

**Unit of evaluation:** `(SQ or claim, fixed world) -> coverage outcome`

**Design:** A large, diverse corpus of research questions (~200-500)
formulated as SQs and claims, over 5-8 fixed worlds. Each item has a
golden answer (from the SCM oracle or manual validation) and an expected
coverage status. Sources: real papers, external benchmarks, LLM
generation with curation, internal taxonomy.

The corpus is NOT biased toward what we know works. It covers the full
spectrum of scientific question types, including many we expect to fail.

**Key output:** A **coverage matrix** — science_type x outcome — that
answers "SREG covers X well, Y partially, Z not at all." This is the
figure for the thesis coverage chapter.

**Coverage outcomes per item:**
- `compiles_correct` — compiles and produces correct verdict
- `compiles_incorrect` — compiles but verdict doesn't match golden (bug)
- `abstains_correct` — not expressible and compiler knows it
- `abstains_incorrect` — should be expressible but compiler doesn't know how
- `compile_error` — compiler crashes or produces invalid specs
- `not_expressible` — grammar lacks the primitives entirely

**Key metrics:**
- Coverage rate by science type
- Correct rate (of those that compile)
- Abstention precision/recall
- Boundary map (where expressibility ends)

**Dependency:** Requires Suite 1 to pass (math must be correct) and
Suite 2 to be understood (compiler behavior must be characterized) to
interpret results properly.

**Detail doc:** `eval_suite_science_coverage.md`

---

### Suite 4: END-TO-END / REWARD ALIGNMENT

**Question:** Does the system as a whole force real investigation, and
does the reward correctly rank better investigation higher?

**What it evaluates:** The complete SREG loop as a training environment.
Not individual components but the emergent properties of the system.

**Unit of evaluation:** `(case, trajectory) -> score` and orderings
across trajectories.

**Design:** Three sub-blocks:

**A. Investigation pressure (no-data gap)**
Same case, two solver variants: one with data access, one answering from
priors only. Gap `score(data) - score(no_data)` must exceed epsilon.
Base exists in `oi_nodata_baseline.py`.

**B. Reward robustness (anti-hack)**
Hand-crafted adversarial scenarios testing whether the scoring formula
and relevance judge can be gamed. Derived from two axes:
- Evolutionary pressures (PROJECT.md): anti-overexcitement, relevance,
  honest verification, etc.
- Attack surfaces: scoring formula (max exploit, duplication), compiler
  (abstention dodge), judge (rhetorical fool), evidence trace (citation
  fabrication).

Examples: generic-but-true claims, duplicated claims, wrong-variable
claims, association-as-causation, fabricated evidence, spam vs focused.

**C. Trajectory ordering (M3)**
Trajectory bank per case: T0 (no data), T1 (superficial), T2
(reasonable), T3 (strong). System must rank T3 > T2 > T1 > T0.
**Gated on P2 (credit-assignment) landing** — running this before the
scorer is stable would measure a mix of ordering + known bugs.

**Key metrics:**
- no_data_gap per case
- Anti-hack pass rate (adversarial scenarios correctly handled)
- Reward-order accuracy (% of pairwise orderings correct)

**Dependency:** All other suites should be characterized first. This is
the capstone evaluation.

**Detail doc:** Blocks A+B implemented in `tests/eval/suite4_reward_alignment/`
(25 tests, 100% pass, 2026-04-12). Block C gated on P2.

---

## Cross-cutting concerns

### Relevance judge spans two suites
- Its **accuracy** (does it agree with human labels?) is measured in
  Suite 2 (Translation).
- Its **robustness to gaming** (does it get fooled by adversarial
  claims?) is measured in Suite 4 (Reward Alignment).

### Reproducibility (C0) is implicit
`rescore --reaggregate` producing delta=0 is a prerequisite, not a
separate suite. It's checked as part of Suite 1 and Suite 4 setup.

### Worlds are shared across suites
The hand-crafted toy SCMs built for Suite 1 can be reused in Suites 2
and 3 (where the worlds need to be fixed and known). Suite 4 may use
the frozen `p05_canonical_batch` for E2E runs.

---

## Dependency ordering

```
Suite 1 (Core Correctness)            Layer 1
    |
    v
Suite 2 (Translation)     Suite 3 (Science Coverage)    Layers 2-3
    |                          |
    +-----------+--------------+
                |
                v
        Suite 4 (E2E / Reward)        Layer 4
                |
                v
        Suite 5 (Signal Quality)      Layer 5
                |
                v
        Behavioral Ablations          Layer 6 (future)
```

Suite 1 is the foundation. Suites 2 and 3 can proceed in parallel once
Suite 1 passes. Suite 4 requires understanding from all three.
Suite 5 requires Suite 4 + real solver runs to produce score distributions.
Layer 6 requires a trained model.

---

## Relationship to thesis claims

| Thesis claim | Primary suite | Supporting suite |
|---|---|---|
| Reward is exact where promised | Suite 1 | — |
| Semantic translation preserves meaning | Suite 2 | Suite 3 |
| System covers diverse science types | Suite 3 | Suite 2 |
| Cases force real investigation | Suite 4 (block A) | — |
| Reward ranks better investigation higher | Suite 4 (block C) | Suite 4 (block B) |
| LLM judge is calibrated | Suite 2 | Suite 4 (block B) |
| Reward provides viable RL training signal | Suite 5 | Suite 4 |
| Training produces scientific judgment | Layer 6 (future) | Suite 5 |

---

## Implementation priority

| # | Suite | Cost | Gating | Status |
|---|---|---|---|---|
| 1 | Suite 1: Core Correctness | Low (no LLM) | — | DONE (52/52) |
| 2 | Suite 4 A+B: Reward Formula | Low (no LLM) | Suite 1 | DONE (25/25) |
| 3 | Suite 3: Science Coverage | Medium-high (corpus) | Suite 1 | TODO |
| 4 | Suite 2: Translation | Medium (gold set) | Suite 1 | TODO |
| 5 | Suite 4 C: Trajectory Ordering | High (trajectories) | P2 | TODO |
| 6 | Suite 5: Signal Quality | Medium (real runs) | Suite 4 | TODO |
| 7 | Layer 6: Behavioral Ablations | Very high (trained model) | Suite 5 | Future |

Suite 3's **corpus construction** is prioritized over Suite 2 because
it can start immediately and produces the broadest evidence for the
thesis (coverage chapter).

However, **strong coverage claims for the thesis** should wait until
Suite 2 has provided a first characterization of compiler accuracy.
Without that, it's hard to distinguish "coverage gap" (the grammar
can't express this) from "compiler gap" (the grammar CAN express it
but the compiler doesn't know how). Suite 2's gold set can be derived
as a controlled subset of Suite 3's corpus.

In practice: build the corpus and worlds now (Phase 1-3 of Suite 3),
run Suite 1 in parallel, then run Suite 2 on a subset, and only then
interpret Suite 3 results as thesis evidence.

---

## Future direction: Behavioral ablation evals

> **Status:** idea stage, needs design work. Documented 2026-04-12.

Suites 1-4 evaluate the **system** (math, translation, scoring formula,
reward ordering). But there's a complementary question:

> Do the evolutionary pressures in SREG actually produce the desired
> behavioral properties in a trained agent?

This would be a different kind of evaluation: **controlled scenarios
that isolate a specific capability and measure whether the agent has it.**

### The pattern

Take a capability from the evolutionary pressures list (PROJECT.md) and
design a scenario that forces the agent into a situation where HAVING
that capability produces a better outcome than NOT having it. Then
measure whether the agent (or its score) reflects the difference.

### Concrete examples (brainstorm, not designed)

- **Data access ablation** (partially in Block A): same case, solver
  with vs without data access. Already tested at formula level; could
  extend to real solver runs.
- **Code execution ablation**: same case, solver with python_exec vs
  solver restricted to text-only reasoning. Tests whether the system
  rewards computational investigation over verbal reasoning.
- **Dead-end recovery**: start the solver from a hypothesis history that
  is heading toward a dead end. Does the agent pivot or persist? Tests
  research taste and knowing when a line of inquiry is unproductive.
- **Premature conclusion resistance**: give the solver partial evidence
  that suggests a wrong conclusion. Does it investigate further or
  commit early? Tests knowing when a conclusion is premature vs well
  founded.
- **Breadth vs depth judgment**: cases where the right strategy is to
  go broad (many families) vs cases where depth matters (complex
  mediation). Does the agent adapt its strategy?

### Key differences from current suites

- Current suites use **hand-crafted inputs** or **fixed trajectories**.
  These would use **live solver runs under controlled conditions**.
- Current suites verify the **scoring system**. These would verify that
  the scoring system **produces the right training signal** — i.e., that
  agents trained on SREG actually develop the properties we want.
- Closer to behavioral evals / capability evals than to unit tests.
- Likely requires a trained (or at least fine-tuned) model to be
  meaningful — testing base models may just measure pre-training priors.

### Open questions

- How to measure subtle properties (research taste, question quality)
  without human judges or another LLM in the loop?
- Which properties are measurable via score differential vs which need
  qualitative evaluation?
- Can we design these as automated evals, or are some inherently
  qualitative?
- What's the minimum viable version — one property, one case, one
  ablation?
