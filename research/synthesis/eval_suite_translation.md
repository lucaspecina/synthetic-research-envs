# Suite 2: Translation / Compilation — Design Document

> **Status:** design complete, implementation pending.
> **Date:** 2026-04-13
> **Origin:** `eval_suite_framework.md` Layer 2, issue I-007.

## Objective

Verify that SREG's compilation pipeline correctly translates natural
language claims and sub-questions into verifiable AtomicSpecs.

The compiler is the bridge between human language and formal verification.
If it mistranslates, correct investigation gets wrong scores and the
training signal is corrupted.

## What we evaluate

Three components, all LLM-dependent:

| Component | Input | Output | Question |
|---|---|---|---|
| Claim compiler | ClaimCard (free text) | AtomicSpecs | Did it translate the finding correctly? |
| SQ compiler | text_gloss (question) | AtomicSpecs | Did it translate the question correctly? |
| Relevance judge | (claim, SQ) pair | Score 0-1 | Does it judge relevance correctly? |

## Evaluation method: Verificational equivalence

We do NOT check if the compiler produces the exact same specs as the gold.
We check if the specs it produces, **when run against the SCM, give the
same verdict** as the gold specs.

This is more robust: if the compiler takes a different but valid path to
the same answer, it passes. What matters is the final result.

## Gold set construction: Bottom-up from SCM

Claims are derived FROM the world equations, not invented independently:

1. Define the SCM world (equations, DAG, coefficients)
2. Derive ALL interesting facts analytically (effects, associations,
   mediations, reversals, nulls, non-identifiables)
3. Formulate those facts as natural language claims/SQs at varying
   complexity levels
4. The gold verdict is guaranteed by the mathematics

This ensures the gold is correct — it comes from the equations, not
from AI judgment.

### Formal fact table structure

Each derived fact is recorded as:

| Field | Description |
|---|---|
| `fact_id` | Unique identifier |
| `world` | Which SCM world |
| `regime` | do / observational / adjusted / identifiability |
| `estimand` | What is being measured (ATE, correlation, etc.) |
| `conditioning` | What is being conditioned on (if any) |
| `truth` | The analytical answer (value + holds/not-holds) |
| `surface_forms` | 2-3 natural language formulations of varying complexity |

---

## Semantic family matrix (v3)

Organized by component x challenge type. Designed iteratively with
Codex across 3 review rounds.

### CLAIM COMPILER (25 families)

**CC-A. Pattern recognition** (8 families)
One per historically-recognized pattern type. Tests whether the compiler
produces specs that verify the correct estimand.
- CC-A1: Causal effect (ATE via intervention)
- CC-A2: Observational association (correlation / partial correlation)
- CC-A3: Mediation (direct + indirect effects)
- CC-A4: Heterogeneity (effect modification by subgroup)
- CC-A5: Confounding (crude vs adjusted comparison)
- CC-A6: Effect ranking (which variable has strongest effect)
- CC-A7: Tail risk (probability of extreme outcome)
- CC-A8: Variance effect (effect on spread, not mean)

**CC-B. Role binding / variable grounding** (5 families)
- CC-B1: Edge orientation (treatment->outcome vs outcome->treatment)
- CC-B2: Role disambiguation (mediator vs confounder vs modifier —
  same 3 variables, different roles)
- CC-B3: Variable alias (synonym or partial name -> correct world variable)
- CC-B4: Sign/direction extraction (positive, negative, near_zero
  including numeric cues)
- CC-B5: Quantitative commitments ("doubles", "large effect", "top decile")

**CC-C. Linguistic complexity** (5 families)
- CC-C1: Paraphrases (3 formulations -> same spec family)
- CC-C2: Negation ("no effect", "does not increase")
- CC-C3: Multi-unit / compound (1 claim -> >1 spec)
- CC-C4: Scope / subgroup ("among older patients", "in the high-dose group")
- CC-C5: Conditioning semantics ("holding Z constant", "controlling for Z")

**CC-D. Decision boundaries** (4 families)
Pairs of claims that sound similar but should compile differently.
- CC-D1: Causal vs observational (same variables, different regime)
- CC-D2: Mediation vs confounding (same 3 variables, different structure)
- CC-D3: Ranking vs multiple causal effects
- CC-D4: Adjusting-for-Z causal vs observational partial correlation

**CC-E. Abstention** (3 families)
Claims the compiler should refuse to compile.
- CC-E1: Temporal ("X precedes Y in time")
- CC-E2: Latent / unmeasured variables
- CC-E3: Non-expressible (methodological, distributional)

### SQ COMPILER (9 families)

**SQ-A. Pattern recognition** (4 families)
- SQ-A1: Direct causal question ("Does X affect Y?")
- SQ-A2: Observational / associative question ("Is X associated with Y?")
- SQ-A3: Identifiability question ("Can we estimate the causal effect?")
- SQ-A4: Compound question ("Does X affect Y, and if so, through what pathway?")

**SQ-B. Decision boundaries** (3 families)
- SQ-B1: Causal-adjust vs observational-partial-correlation
  ("after adjusting for Z")
- SQ-B2: Effect question vs mechanism question
- SQ-B3: Paraphrases (3 formulations -> equivalent specs)

**SQ-C. Abstention** (2 families)
- SQ-C1: Non-expressible ("What's the optimal X?")
- SQ-C2: Unobservable variable

### RELEVANCE JUDGE (7 families)

**RJ-A. Calibration** (4 families, ordinal bands)
- RJ-A1: Direct match (high relevance)
- RJ-A2: Partial overlap (medium)
- RJ-A3: Near-miss — same variables, different question (low)
- RJ-A4: Irrelevant — different variables entirely (none)

**RJ-B. Hard negatives** (3 families)
- RJ-B1: Rhetorically similar but semantically different
- RJ-B2: True-but-off-target (correct claim, wrong question)
- RJ-B3: Broad claim vs specific SQ (and vice versa)

### Totals

- 41 families across 3 components
- ~2-3 items per family -> ~90-120 gold items
- Relevance judge additionally needs ~150-250 claim-SQ pairs

---

## Three research-grade SCM worlds

Each world has ~7-8 variables with linear-Gaussian equations (except W3
which uses piecewise-linear for threshold). All have analytically
derivable ground truth.

Each world has a distinct role in the evaluation:

### W1 — Comparative Effectiveness Study (structure)

**Domain:** Clinical medicine. Observational study of treatment
effectiveness with confounding, mediation, and effect modification.

**Variables (7 observable + interaction):**
- A (age) ~ N(0, 1)
- S (severity) = 0.4*A + eps(0.5)
- T (treatment) = -0.5*S + eps(0.6)
- M (compliance) = 0.6*T + eps(0.4)
- B (biomarker) ~ N(0, 1) independent
- Y (outcome) = 0.5*T + 0.3*M + 0.2*B + 0.35*B*T - 0.3*S + 0.15*A + eps(0.3)
- SE (side_effect) = 0.7*T + 0.2*A + eps(0.4)

**DAG:** A->S->T, A->Y, A->SE, S->Y, T->M->Y, T->Y, T->SE, B->Y, B*T->Y

**Key analytical facts:**
- ATE(T->Y) = 0.50 (direct) + 0.18 (via M) = 0.68
- Effect of T on Y given B=b: 0.68 + 0.35*b (heterogeneity)
- S confounds T->Y (S->T negative, S->Y negative)
- Total effect of A on Y: ~-0.11 (direct positive 0.15, but
  indirect through S->T->Y is negative and dominates)
- T->SE = 0.70 (multi-outcome: treatment helps Y but hurts SE)

**Families covered:** CC-A1 through A6, CC-B1/B2/B4, CC-C1 through C5,
CC-D2/D3, SQ-A1/A4, SQ-B2/B3, RJ-A1 through A4.

### W2 — Observational Epidemiology (disambiguation)

**Domain:** Epidemiological study with Simpson's paradox. Crude
association has opposite sign from causal effect.

**Variables (6 observable + collider):**
- C (confounder) ~ N(0, 1)
- I (upstream factor) ~ N(0, 1)
- E (exposure) = 0.5*C + 0.3*I + eps(0.5)
- M (mediator) = 0.4*E + eps(0.5)
- D (disease) = -0.4*E + 0.5*M + 0.6*C + eps(0.4)
- L (collider) = 0.4*E + 0.5*D + eps(0.5)

**DAG:** C->E, C->D, I->E, E->M->D, E->D, E->L<-D

**Key analytical facts:**
- ATE(E->D) = -0.40 + 0.50*0.40 = -0.20 (negative)
- Crude corr(E,D) > 0 (Simpson's reversal: C drives both up)
- Conditioning on L (collider) biases the estimate
- Mediation: E->M->D indirect = +0.20, E->D direct = -0.40
- I is upstream of E but NOT connected to D except through E

**Families covered:** CC-A1/A2/A3/A5, CC-B1/B4, CC-D1/D2/D4,
SQ-A1/A2, SQ-B1, RJ-B1/B2.

### W3 — Environmental Health (distributional + abstention)

**Domain:** Climate and pollution effects on health. Includes latent
confounding, threshold effects, and null relationships.

**Variables (6 observable + 1 latent):**
- R (region) ~ N(0, 1)
- U (hidden factor) ~ N(0, 1) — LATENT, not observable
- Temp (temperature) = 0.5*R + eps(0.3)
- P (pollution) = 0.3*R + 0.4*U + eps(0.3)
- W (water quality) = -0.5*Temp - 0.3*P + eps(0.3)
- H (health) = 0.4*W - 0.2*P + 0.3*U + f(Temp) + eps(0.3)
  where f(Temp) = 0 if Temp < 0, else -0.8*Temp (piecewise threshold)
- WindSpeed ~ N(0, 1) — observable but NO effect on anything

**DAG:** R->Temp, R->P, U->P, U->H, Temp->W->H, P->W, P->H,
Temp->H (piecewise)

**Key analytical facts:**
- Temp->H: threshold/changepoint (total slope ~-0.2 below 0, ~-1.0 above 0;
  the indirect path Temp->W->H always contributes, the piecewise term
  adds -0.8 above the threshold)
- U confounds P->H: causal effect of P on H is NOT identifiable
  without measuring U -> abstention case
- WindSpeed has ZERO effect on H (null relationship)
- R affects H only indirectly (through Temp and P)
- Var(H) varies by region (through Temp/P heterogeneity)

**Families covered:** CC-A2/A7/A8, CC-B4/B5, CC-C2, CC-D1,
CC-E2/E3, SQ-A2/A3, SQ-C2, RJ-A3/A4, RJ-B2/B3.

---

## Annotation policy (pre-requisite for gold labeling)

Before annotating gold items, define:

1. **Verificational equivalence**: two spec sets are equivalent if they
   produce the same verdict when run against the SCM. Multiple valid
   compilations are allowed.

2. **Multiple valid lowerings**: when a claim has >1 valid compilation,
   the gold includes ALL valid spec sets. The compiler passes if it
   produces any of them.

3. **Compound claims — ALL_OF vs ANY_OF**: when a claim contains
   multiple sub-findings, define whether ALL must compile correctly
   or ANY suffices.

4. **False/trap claims vs abstention**: a claim that is compilable but
   factually wrong (e.g., "X increases Y" when ATE is negative) gets
   `truth=False` in the gold — it is NOT an abstention. Abstention is
   reserved for claims that CANNOT be compiled (temporal, latent, etc.).

5. **Paraphrase vs variant**: paraphrases (same meaning, different words)
   must compile to equivalent specs. Variants that change the regime or
   family (e.g., "causes" vs "is associated with") are DIFFERENT gold
   items, not paraphrases.

6. **Abstention rules**: when should the compiler abstain? Define the
   boundary clearly (temporal, latent, methodological, non-expressible).

7. **Relevance judge rubric**: ordinal bands (high/medium/low/none)
   with anchor examples. Pairwise ordering is the primary metric,
   not exact score match.

---

## Implementation plan

1. **Write annotation policy** (1 page). Must be finalized before
   any gold labeling begins.

2. **Build the 3 worlds** as Python fixtures (like Suite 1 worlds.py).
   Derive analytical ground truth. Verify against Monte Carlo.

3. **Derive fact tables** from each world's equations. Bottom-up:
   enumerate all interesting facts, record as formal table.

4. **Write gold claims/SQs** from fact tables. 2-3 surface forms per
   fact, varying complexity. Include negations, traps, abstentions.

5. **Implement deterministic tests first** — anything that doesn't
   need LLM (e.g., verificational equivalence of gold specs against SCM).

6. **Implement LLM tests** — run compiler on gold claims, compare
   verdicts. Track which backend was used (grammar-direct vs fallback).

7. **Implement relevance judge tests** — gold pairs with expected
   ordinal bands.

## Diagnostic output (not pass/fail)

Beyond pass/fail, Suite 2 should report:
- **Compile rate** by family (what % compiles at all)
- **Correctness rate** by family (of those that compile, what % correct)
- **Backend usage** (grammar-direct vs v1 fallback — diagnostic only)
- **Abstention precision/recall**
- **Failure patterns** (where does the compiler systematically fail?)
- **Relevance judge calibration** (score distribution by ordinal band)

---

## Relationship to other suites

- **Depends on Suite 1** — if the verifier is broken, we can't check
  verificational equivalence.
- **Informs Suite 3** — compiler failures found here help distinguish
  "coverage gap" (grammar can't express) from "compiler gap" (grammar
  CAN express but compiler doesn't know how).
- **Informs Suite 4** — if the compiler systematically fails on certain
  claim types, the reward signal is corrupted for those types.

---

## Design credits

Matrix v3 and world design reviewed in 3 rounds with Codex (GPT-5.4).
Key contributions from Codex: role binding as separate family, separating
scope/conditioning/adjusting, Simpson reversal margin check, near_zero
correction in W3, annotation policy recommendation.
