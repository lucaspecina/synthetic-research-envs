# Suite 3: Science Coverage

> **Status:** CANON evaluation — design phase.
> **Date:** 2026-04-09
> **Parent:** `eval_suite_framework.md`
> **Purpose:** Define the design, construction, and execution of the
> Science Coverage evaluation suite.

## What this suite answers

> **What types of scientific questions can SREG represent and evaluate
> today, and where are the boundaries?**

This is not a pass/fail test. It is an **empirical coverage map**. The
output is a matrix that says: SREG covers X well, Y partially, Z not at
all. When someone asks "what can SREG do?", this suite provides the
evidence-backed answer.

---

## Design overview

The suite has 4 pieces:

1. **Fixed worlds** — 5-8 hand-crafted SCMs with known ground truth
2. **Corpus** — ~200-500 SQs and claims, diverse and NOT biased toward
   what we know works
3. **Golden answers** — for each (question, world) pair, the correct
   answer from the SCM oracle
4. **Harness** — runs the compiler + verifier on each item and
   classifies the outcome

```
PRIOR (built offline, before harness runs):

  corpus item (SQ or claim)
      + fixed world
      + world_truth (from SCM, NOT from AtomicSpec)
      + sreg_expectation (human label: supported / partial / should_abstain / out_of_scope)


HARNESS (what runs at evaluation time):

  corpus item
      |
      v
  compile_sq_to_specs / claim compiler
      |
      +--[success]----> verify_atom(specs, world)
      |                     |
      |                     v
      |                 check_answer(verdicts, world_truth)
      |                 check_formalization(specs, science_type)
      |                     |
      |                     v
      |                 final_outcome: correct / answer_only / incorrect
      |
      +--[abstained]--> final_outcome: abstained
      |
      +--[error]------> final_outcome: compile_error


ANALYSIS (post-hoc):

  Cross sreg_expectation x final_outcome -> coverage matrix
  (expectation is a PRIOR label, outcome is OBSERVED — never mixed)
```

---

## Piece 1: Fixed worlds

We need 5-8 SCMs that are:
- **Diverse in domain** (health, ecology, social, engineering, economics)
- **Rich enough** to support many question types (7-12 nodes each, with
  confounders, mediators, heterogeneity, latent variables)
- **Simple enough** to have known ground truth (linear or piecewise-linear
  equations where possible, so we can verify analytically)
- **Pre-validated** via Suite 1 (Core Correctness)

### Proposed world roster

| World ID | Domain | Nodes | Key features |
|---|---|---|---|
| `health_8` | Medicine | 8 | Treatment, outcome, mediator, confounder, subgroup modifier, latent severity |
| `ecology_7` | Ecology | 7 | Climate driver, species interactions, threshold effects, indirect paths |
| `social_9` | Social science | 9 | Policy, income, health, education, feedback-like structure (DAG), equity modifier |
| `engineering_6` | Engineering | 6 | Process params, quality metrics, nonlinear threshold, tail risk |
| `economics_8` | Economics | 8 | Market vars, intervention (tax/subsidy), heterogeneous effects by group |
| `neuro_7` | Neuroscience | 7 | Brain regions, connectivity, latent state, partial observability |
| `epi_6` | Epidemiology | 6 | Exposure, disease, selection bias structure, missing data pattern |
| `generic_5` | Abstract | 5 | Minimal world for boundary testing, all linear, full analytic solutions |

Each world is a Python fixture (like Suite 1's toy worlds but richer).
The `generic_5` world is intentionally simple for fast debugging.

### What each world must provide

- `SCMWorld` instance (graph + equations)
- `SCMSolver` instance
- `WorldSummary` (for compiler context)
- Analytic or MC-validated ground truth for key quantities:
  - All pairwise causal effects (do-calculus)
  - Key partial correlations
  - Identifiability status for each pair
  - Subgroup heterogeneity where present
  - Tail probabilities for relevant variables

---

## Piece 2: The corpus

### Item schema — three explicit blocks

Each item has three blocks that must NOT be conflated:

1. **`world_truth`** — the correct answer to this question, derived from
   the SCM independently of SREG's grammar or compiler. This is a fact
   about the world, not about the system.
2. **`sreg_expectation`** — our a priori prediction of what the system
   should do with this question. This is a claim about the system.
3. **`run_result`** — filled by the harness at runtime. What actually
   happened.

This separation is critical. Without it, the suite becomes circular:
if the golden answer is built by hand-writing AtomicSpecs, we end up
measuring "can the compiler match our spec?" rather than "can SREG
answer this scientific question?".

```json
{
  "item_id": "SQ_causal_042",
  "text": "Does exercise intensity have a positive causal effect on recovery speed?",
  "focus_variables": ["exercise_intensity", "recovery_speed"],
  "item_type": "sq",
  "world_id": "health_8",

  "science_type": "causal_effect",
  "scope_group": "in_scope",
  "domain": "medicine",
  "source": "adapted from JAMA 2019",
  "tags": ["do-calculus", "continuous", "direct_effect"],

  "family_id": "FAM_exercise_recovery",
  "variant_of": null,

  "world_truth": {
    "answer_type": "bool_with_magnitude",
    "direction": "positive",
    "magnitude_approx": 2.3,
    "derivation": "analytic",
    "notes": "From structural equation: recovery = 2.3 * exercise + noise"
  },

  "sreg_expectation": {
    "coverage_expected": "supported",
    "notes": ""
  },

  "run_result": {
    "compile_status": null,
    "specs_emitted": null,
    "answer_correct": null,
    "formalization_match": null,
    "final_outcome": null
  }
}
```

### The three blocks explained

#### Block 1: `world_truth`

The correct answer derived from the SCM **without using SREG's grammar
or compiler**. This is the ground truth.

**`answer_type`**: what kind of answer this question expects:
- `bool` — yes/no (e.g., "does X cause Y?")
- `bool_with_magnitude` — yes/no + approximate effect size
- `scalar` — a number (e.g., correlation value, variance)
- `ranking` — ordered list (e.g., "A > B > C in effect on Y")
- `set` — unordered set (e.g., valid adjustment set)
- `direction` — positive/negative/near_zero
- `not_applicable` — for items that have no well-defined answer in the
  world (e.g., "what is the R-squared?" depends on the model, not the
  world)

**`derivation`**: how the golden was obtained:
- `analytic` — closed-form from the structural equations
- `mc_validated` — high-N Monte Carlo (N >= 500K)
- `dag_structural` — from the DAG structure (e.g., identifiability)
- `manual` — human judgment (only for ambiguous cases, must document)

**Critical rule:** the world truth must NEVER be derived by running the
SREG compiler. It must come from the world directly (equations, DAG
structure, Monte Carlo sampling, or analytical derivation). The compiler
is what we're testing.

#### Block 2: `sreg_expectation`

Our prediction of what the system should do:
- `"supported"` — grammar can express this, compiler should compile
- `"partial"` — grammar can partially express, may lose nuance
- `"should_abstain"` — not expressible in the grammar, compiler should
  know and abstain
- `"out_of_scope"` — grammar fundamentally lacks the primitives (e.g.,
  time series, optimization, experimental design)

This is a LABEL we assign when building the corpus, NOT a result the
harness discovers. It represents our best understanding of the system's
capabilities.

#### Block 3: `run_result`

Filled by the harness. Contains:
- **`compile_status`**: `success` / `abstained` / `error`
- **`specs_emitted`**: the actual specs (for inspection)
- **`answer_correct`**: does the final verdict match `world_truth`?
  (bool/direction/magnitude comparison)
- **`formalization_match`**: are the emitted specs a semantically valid
  formalization of the question? This catches the case where the answer
  happens to be right but the formalization is wrong (e.g., compiler
  checks correlation when the question asks about causation, and the
  answer happens to be the same sign). Evaluated by:
  - Checking measurement kind (causal question → do-calculus, not corr)
  - Checking primary variables match focus_variables
  - Checking comparison type is appropriate
- **`final_outcome`**: the classification for the coverage matrix

### `item_type`

`"sq"` or `"claim"`. SQs are cleaner (orchestrator language), claims
are messier (solver language). Both go through compilation. The corpus
should have both.

### `science_type` — grouped by scope

The taxonomy is organized in three groups to make the coverage matrix
interpretable. This is NOT a value judgment — it's a statement about
what SREG v1's grammar was designed to handle.

**In-scope** (grammar has the primitives, compiler should handle):

| Type | Example |
|---|---|
| `causal_effect` | "Does X cause Y?" |
| `confounding` | "Does Z confound X→Y?" |
| `mediation` | "Is the effect of X on Y mediated by M?" |
| `heterogeneity` | "Does the X→Y effect vary by subgroup S?" |
| `interaction` | "Do X and W interact in their effect on Y?" |
| `tail_risk` | "What is the probability of Y exceeding threshold T?" |
| `dose_response` | "How does Y change as X increases from low to high?" |
| `identifiability` | "Is the X→Y effect identifiable from observational data?" |

**Edge / partial** (grammar can partially express, or requires
non-obvious compilation):

| Type | Example |
|---|---|
| `epistemological` | "Is the X-Y association robust to adjustment for Z?" |
| `descriptive_association` | "Which variables correlate most with Y?" |
| `descriptive_distribution` | "What is the distribution/variance of Y?" |
| `structure_discovery` | "Which variable is the strongest driver of Y?" |
| `ranking` | "Rank these variables by effect size on Y" |
| `selection_bias` | "Is the observed effect an artifact of selection?" |
| `policy_tradeoff` | "Does intervention on X improve Y but worsen Z?" |

**Out-of-scope by design** (grammar fundamentally lacks primitives):

| Type | Example | Why out of scope |
|---|---|---|
| `temporal` | "Does the effect change over time?" | SCM is static, no time dimension |
| `optimization` | "What value of X maximizes Y?" | Requires artefact evaluation, not claim verification |
| `experimental_design` | "What should we measure next?" | Requires VOI / sequential decision |
| `model_fit` | "What is the R-squared / AIC?" | Model-dependent, not a world property |
| `meta_analytic` | "Is the effect consistent across studies?" | No multi-study structure |

The corpus MUST include items from all three groups. The out-of-scope
items are controls: we expect abstention or non-expressibility, and
we verify that the system knows its limits.

### `family_id` and `variant_of`

Questions come in families. A base question + 3-5 variants (paraphrases,
type shifts, perturbations). This lets us measure within-family
consistency and see how small changes in formulation affect compilation.

### Corpus size targets

| Category | Count | Purpose |
|---|---|---|
| Base questions | 50-80 | Core diverse coverage |
| Variants/perturbations | 150-300 | Robustness + fine-grained boundary mapping |
| Adversarial/edge cases | 30-50 | Known hard cases, ambiguous formulations |
| Not-expressible controls | 30-50 | Types we KNOW are outside grammar |
| **Total** | **~250-500** | |

### Family structure (example)

```
FAM_exercise_recovery (world: health_8)
├── SQ_causal_042      "Does exercise have a causal effect on recovery?"     [causal_effect, supported]
├── SQ_causal_042a     "Is the exercise→recovery effect mediated by inflammation?"  [mediation, supported]
├── SQ_causal_042b     "Does the effect vary between young and old patients?"  [heterogeneity, supported]
├── SQ_causal_042c     "What is the R-squared of recovery ~ exercise?"  [model_fit, should_abstain]
├── CL_causal_042d     "Exercise strongly predicts recovery (r=0.7)"  [descriptive_association, supported]
├── CL_causal_042e     "Patients who exercise more recover faster, p<0.001"  [claim, messier language]
└── SQ_causal_042f     "What exercise dose maximizes recovery?"  [optimization, not_expressible]
```

---

## Piece 3: Sources for the corpus

The corpus must NOT be biased toward what SREG already does well.
Multiple sources ensure diversity:

### Source A: Real papers (~50-80 items)

Extract sub-questions from the methods/results sections of published
papers across diverse fields. Each paper typically yields 2-5 items.

Target journals/fields:
- Medicine: JAMA, NEJM, Lancet, BMJ
- Ecology: Nature Ecology, Ecology Letters
- Economics: AER, QJE, Econometrica
- Social science: AJPS, ASR
- Engineering: reliability, chemical process optimization
- Psychology: cognitive, developmental
- Epidemiology: AJE, IJE
- Neuroscience: connectivity studies

What to extract: not the paper's main finding, but the **sub-questions
implicit in the analysis**. "We tested whether the effect was mediated
by M" → SQ about mediation. "We checked robustness to confounding by Z"
→ SQ about epistemological robustness.

### Source B: External benchmarks (~50-80 items)

Adapt questions from existing benchmarks to SQ/claim format:

| Benchmark | What to extract | ~Items |
|---|---|---|
| CausalReasoningBenchmark (CRB) | 173 queries on causal identification/estimation | 20-30 |
| CLadder | Rung 1/2/3 questions (association, intervention, counterfactual) | 10-15 |
| QRData | Statistical + causal questions on tabular data | 10-15 |
| DiscoveryBench | Hypothesis generation tasks | 10-15 |
| CauSciBench | Causal inference in scientific contexts | 5-10 |

These are already classified by type. We adapt the QUESTION (not the
data) to our SQ/claim format and assign it to one of our fixed worlds.

### Source C: LLM generation with curation (~100-200 items)

Use an LLM to generate diverse questions, then curate manually. Prompt
strategy:

1. Give the LLM a world description (variables, domain, rough structure)
2. Ask for N questions of type T ("give me 10 epistemological questions
   about this world", "10 descriptive questions", etc.)
3. Also ask for "questions that would be hard or impossible to answer
   with do-calculus and observational statistics" — to get items outside
   the grammar
4. Manually curate: remove duplicates, fix variables, assign golden
   answers, label coverage_expected

This is the volume source. Quality comes from curation, not from the
LLM itself.

### Source D: Internal taxonomy (~20-30 items)

From `investigation_scenarios_rubric.md`, `Doc1_Taxonomia_El_Mapa.md`,
and `scientific_research_taxonomy.md`. For each cell in our taxonomy
that isn't already covered by sources A-C, generate 1-2 items to fill
gaps.

### Source E: Textbook methods chapters (~20-30 items)

Research methods and applied statistics textbooks naturally organize
questions by type. Each chapter suggests a family of questions:
- Descriptive statistics chapter → "what is the distribution of Y?"
- Regression chapter → "what predicts Y?" (+ "what is the R²?" which
  should abstain)
- Causal inference chapter → "does X cause Y?"
- Mediation chapter → "is the effect mediated?"
- Experimental design chapter → "what should we measure next?"
  (not expressible)
- Time series chapter → "does the effect change over time?"
  (not expressible today)

---

## Piece 4: World truth — how to construct it (without circularity)

This is the expensive part. For each (item, world) we need the correct
answer **derived from the world, not from the SREG grammar**.

**The anti-circularity rule:** the world truth must NEVER be obtained by
hand-writing AtomicSpecs and running verify_atom. That would make the
golden dependent on the same IR the compiler produces, biasing the
coverage measurement toward what the grammar already knows how to
express.

Instead, world truth comes from the world directly:

### Method 1: Analytical derivation (preferred for linear worlds)

For SCMs with linear equations, many quantities have closed-form:
- **Causal effects:** coefficient in the structural equation.
  "Y = 2.3*X + ..." → the causal effect of X on Y is +2.3 per unit.
- **Correlations:** from the implied covariance matrix of the SCM.
- **Partial correlations:** from the precision matrix.
- **Identifiability:** from the DAG structure (backdoor criterion).
- **Direction:** sign of the structural coefficient.

This is the most rigorous path. Document the derivation for each item.

### Method 2: Monte Carlo from the SCM (for nonlinear worlds)

When analytics are hard:
1. `world.sample(n=500_000, do={X: high})` and
   `world.sample(n=500_000, do={X: low})`
2. Compute the quantity directly (mean difference, correlation, etc.)
3. Record as golden with `derivation: "mc_validated"`

Key: this uses `world.sample()` and `world.interventional_distribution()`
directly — NOT `verify_atom()`. The world's sampling engine is the
oracle, not the verification pipeline.

### Method 3: DAG structural properties

For graph-theoretic questions:
- Identifiability: `_find_backdoor_set()` or manual DAG inspection
- d-separation: `nx.is_d_separator()`
- Adjustment sets: enumerate from the DAG

These are deterministic and don't depend on equations.

### Method 4: Manual judgment (sparingly)

For genuinely ambiguous questions where the "correct" answer depends on
interpretation (e.g., "does X affect Y?" could be causal or
associational), record **multiple acceptable answers** and count as
correct if any match. Mark `derivation: "manual"` and document the
reasoning.

### For out-of-scope items

The world truth is `answer_type: "not_applicable"`. These items exist
to test whether the system knows its limits, not to test whether the
answer is correct.

### Formalization match — the second check

Even when the answer is correct, we need to verify the FORMALIZATION
is appropriate. This catches false positives where the compiler
produces a semantically wrong spec that happens to give the right
boolean answer by coincidence.

Example of a false positive:
- Question: "Does X causally affect Y?" (causal_effect)
- Compiler emits: correlation(X, Y), assertion=positive
- World truth: positive effect (X→Y exists)
- `answer_correct`: TRUE (correlation is positive)
- `formalization_match`: FALSE (measured association, not causation)

The `formalization_match` check verifies:
- Measurement kind is appropriate for the question type
  (causal → do-calculus/adjust, not correlation)
- Primary variables match focus_variables
- Comparison type is appropriate
- Arm kinds are correct (intervene/adjust for causal, baseline for
  descriptive)

This is evaluated by a lightweight rule-based checker (not LLM) that
maps science_type to expected spec properties.

---

## The harness

### Execution flow

```python
for item in corpus:
    world = load_world(item.world_id)
    summary = build_world_summary(world)
    solver = SCMSolver(world)

    # --- Compile ---
    if item.item_type == "sq":
        result = compile_sq_to_specs(
            text_gloss=item.text,
            focus_variables=item.focus_variables,
            world_summary=summary,
            llm_call=llm,
        )
    else:  # claim
        result = compile_claim(item, summary, llm)

    # --- Fill run_result ---
    run = {"compile_status": result.status, "specs_emitted": result.specs}

    if result.status == "success":
        verdicts = [verify_atom(spec, world, solver) for spec in result.specs]
        run["answer_correct"] = check_answer(verdicts, item.world_truth)
        run["formalization_match"] = check_formalization(
            result.specs, item.science_type, item.focus_variables
        )
    else:
        run["answer_correct"] = None
        run["formalization_match"] = None

    # --- Classify final_outcome ---
    run["final_outcome"] = classify(
        compile_status=result.status,
        answer_correct=run["answer_correct"],
        formalization_match=run["formalization_match"],
    )
    # Possible outcomes:
    #   "correct"              — compiled, answer right, formalization right
    #   "answer_only"          — compiled, answer right, formalization wrong
    #                            (false positive: right answer, wrong reason)
    #   "incorrect"            — compiled, answer wrong
    #   "abstained"            — compiler abstained
    #   "compile_error"        — compiler failed

    item.run_result = run
    record(item)
```

### Output: coverage matrix (two axes)

The coverage matrix crosses TWO independent axes:
- **Rows:** `sreg_expectation.coverage_expected` (our prior label)
- **Columns:** `run_result.final_outcome` (what actually happened)

This separation is essential. It lets us distinguish:
- **System working as expected:** expected=supported, outcome=correct
- **Compiler gap:** expected=supported, outcome=abstained (grammar can
  express it but compiler doesn't know how)
- **Compiler bug:** expected=supported, outcome=incorrect or error
- **False positive:** expected=out_of_scope, outcome=correct (suspicious)
- **Correct self-knowledge:** expected=should_abstain, outcome=abstained

#### Primary view — expectation x outcome (aggregated):

```
| expectation     | N   | correct | answer_only | incorrect | abstained | error |
|-----------------|-----|---------|-------------|-----------|-----------|-------|
| supported       | 150 |     120 |           8 |        10 |         7 |     5 |
| partial         |  50 |      25 |           5 |         8 |         8 |     4 |
| should_abstain  |  30 |       0 |           2 |         3 |        23 |     2 |
| out_of_scope    |  40 |       0 |           0 |         0 |        35 |     5 |
```

#### Secondary view — by science type (grouped):

```
IN-SCOPE
| science_type         | N  | correct | ans_only | incorrect | abstained | error |
|----------------------|----|---------|----------|-----------|-----------|-------|
| causal_effect        | 45 |      38 |        2 |         2 |         1 |     2 |
| confounding          | 30 |      23 |        1 |         2 |         3 |     1 |
| mediation            | 20 |      14 |        1 |         1 |         3 |     1 |
| heterogeneity        | 25 |      18 |        2 |         2 |         2 |     1 |
| ...                  |    |         |          |           |           |       |

EDGE / PARTIAL
| science_type         | N  | correct | ans_only | incorrect | abstained | error |
|----------------------|----|---------|----------|-----------|-----------|-------|
| epistemological      | 15 |       8 |        1 |         1 |         3 |     2 |
| structure_discovery  | 15 |       4 |        1 |         1 |         5 |     4 |
| ...                  |    |         |          |           |           |       |

OUT-OF-SCOPE BY DESIGN
| science_type         | N  | correct | ans_only | incorrect | abstained | error |
|----------------------|----|---------|----------|-----------|-----------|-------|
| temporal             | 10 |       0 |        0 |         0 |        10 |     0 |
| optimization         | 10 |       0 |        0 |         0 |         8 |     2 |
| model_fit            | 10 |       0 |        0 |         0 |         9 |     1 |
| ...                  |    |         |          |           |           |       |
```

#### Tertiary views:
- By world (does one world produce more errors?)
- By source (do paper-derived questions compile differently than LLM-generated?)
- By family (within-family consistency)
- By item_type (SQ vs claim — is one harder to compile?)

### Derived metrics

**Coverage metrics (from the expectation x outcome matrix):**
- **True coverage rate**: `correct / N` for expected=supported items
- **Precision**: `correct / (correct + answer_only + incorrect)` — of
  things that compiled, how many were actually right AND well formalized
- **Answer-only rate**: `answer_only / compiled` — false positives
  (right answer, wrong formalization). High values mean the suite would
  overestimate coverage without the formalization check.
- **Abstention precision**: of items where compiler abstained, fraction
  that SHOULD have abstained (expected=should_abstain or out_of_scope)
- **Abstention recall**: of items expected to not be expressible, fraction
  where compiler actually abstained
- **Compiler gap**: `abstained / N` for expected=supported items — the
  grammar CAN express it but the compiler doesn't know how
- **Grammar frontier**: the boundary line between in-scope and
  out-of-scope types, empirically validated

---

## Construction plan

### Phase 1: Worlds (prerequisite)

1. Build 5-8 SCMWorld fixtures as Python files
2. Validate each with Suite 1 (Core Correctness) oracle tests
3. Generate WorldSummary for each
4. Document ground truth for key quantities

### Phase 2: Corpus skeleton

1. Define the science_type taxonomy (finalize the list above)
2. For each type, set target item count
3. Extract items from Source A (papers) — manual, high quality, ~50
4. Adapt items from Source B (benchmarks) — semi-manual, ~50
5. Generate items from Source C (LLM) — fast, curate, ~150
6. Fill gaps from Sources D and E — ~30

### Phase 3: World truth construction

**Anti-circularity rule applies here.** World truth is derived from the
SCM directly, NEVER by writing AtomicSpecs. See Piece 4 for the 4
valid methods.

1. For each item: derive the answer from the world using the methods
   in Piece 4 (analytic, Monte Carlo from SCM, DAG structural, manual).
   Record the answer + derivation method in `world_truth`.
2. For items where multiple interpretations exist: record all valid
   answers and document the ambiguity.
3. For out_of_scope / should_abstain items: mark `answer_type:
   "not_applicable"` — the test is about system self-knowledge, not
   about the answer itself.

### Phase 4: Harness implementation

1. Build the execution loop (pseudocode above)
2. Build the classification logic
3. Build the reporting (coverage matrix + derived metrics)

### Phase 5: First run + iteration

1. Run the full corpus
2. Analyze results — where does SREG surprise us (good or bad)?
3. Fix obvious compiler bugs exposed by the suite
4. Re-run and establish the baseline coverage matrix
5. Document for thesis

---

## Open decisions

**D1. Exact world count and complexity.** 5 might be enough if they're
diverse; 8 gives more robustness but more construction cost.

**D2. Corpus generation strategy.** How much manual vs LLM-generated?
The quality/cost tradeoff. More manual = higher quality golden answers
but smaller corpus. More LLM = larger corpus but curation overhead.

**D3. How to handle genuinely ambiguous questions.** Multiple valid
goldens? Or exclude from the main metrics and report separately?

**D4. LLM variance in compilation.** The compiler is stochastic. Run
each item 1x or 3x? 3x gives stability estimates but 3x the LLM cost.

**D5. Versioning.** When the compiler improves, we re-run. Need to
version results so we can show progress over time.

---

## What this suite is NOT

- It is NOT a regression test (that's Suite 1).
- It is NOT a compiler accuracy test (that's Suite 2 — controlled gold,
  focused on precision).
- It is NOT an E2E evaluation of investigation quality (that's Suite 4).

It IS a **map of what SREG can and cannot do**, built from diverse,
externally-grounded scientific questions, with verified answers.
