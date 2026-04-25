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
   boundary clearly. Two categories (do NOT conflate):
   - **Non-expressible abstention**: the grammar lacks the primitives
     (temporal, methodological, distributional shape, optimization).
     Compiler should refuse with a reason code.
   - **Non-identifiability**: the grammar CAN express the question, but
     the answer is "not identifiable." This is NOT abstention — the
     compiler should produce an `identifiability_check` spec.

7. **Relevance judge rubric**: ordinal bands (high/medium/low/none)
   with anchor examples. Pairwise ordering is the primary metric,
   not exact score match.

8. **Gold lives per surface form**: different surface forms of the same
   fact may require different gold specs (see Gold Target Design section).

9. **Mediation terminology**: use "controlled direct/indirect effect",
   never "natural direct/indirect effect." Our specs fix the mediator
   at a reference value, which gives controlled effects.

---

## Gold target design (decisions from Codex review sessions, 2026-04-13)

### Gold lives per SURFACE FORM, not per fact

A single analytical fact can have multiple surface forms at different
difficulty levels. Those surface forms can require DIFFERENT gold specs.

Example — W1_F03 (treatment causes side effects):
- Easy: "Treatment causes side effects" → 1 spec (T→SE)
- Medium: "Treatment improves outcome but causes side effects" → 2 specs (T→Y + T→SE)

Therefore: gold targets attach to each surface form, not to the fact.

### Three-stage evaluation (not just verificational equivalence)

Verificational equivalence alone is too weak. A compiler might produce
wrong specs that happen to give the right verdict (e.g., observational
correlation positive when causal effect is also positive — right answer
for wrong reason).

The evaluation pipeline has 3 stages, in order:

1. **Compile/abstain decision**: Did the compiler correctly decide to
   compile (when the claim IS expressible) or abstain (when it isn't)?
   This is binary and catches gross failures.

2. **Structural contract**: Did the compiler produce specs with the
   right structure? Check (coarsest to finest):
   - `allowed_arm_kinds` (INTERVENE for causal, BASELINE for observational)
   - `required_role_vars` (treatment, outcome)
   - `required_measurement_kind` (MEAN, VARIANCE, TAIL_PROB, etc.)
   - `required_comparison_kind` (DIFFERENCE, IDENTITY, CONTRAST_DIFF)
   - `required_assertion_polarity` (assertion kind or polarity class)
   - `n_atoms` + `acceptance_rule` (ALL_OF or ANY_OF)
   - Causal structure roles: `required_mediator`, `required_modifier`,
     `required_condition_vars`, `required_cond_set`
   This catches "right answer, wrong reason" failures.

3. **Verdict equivalence**: Do the compiler's specs produce the same
   verdict as the gold specs when run against the SCM? This is the
   final check for correctness.

A compiler that passes stage 3 but fails stage 2 is SUSPICIOUS — it
may be exploiting a coincidence. A compiler that passes all 3 stages
is trustworthy.

### GoldTarget object structure (implemented)

Each surface form has a GoldTarget with a separate StructuralContract:

```python
@dataclass
class StructuralContract:
    allowed_arm_kinds: set[str]
    required_role_vars: dict[str, str]
    required_measurement_kind: str
    required_comparison_kind: str
    required_assertion_polarity: str
    n_atoms: int | tuple[int, int] = 1
    # Causal structure roles (Phase 1 enrichment):
    required_mediator: str | None = None
    required_modifier: str | None = None
    required_condition_vars: set[str] = field(default_factory=set)
    required_cond_set: tuple[str, ...] | None = None

@dataclass
class GoldTarget:
    fact_id: str
    surface_form_index: int
    status: str                          # "compile" | "abstain"
    atoms: list[AtomicSpec]              # Gold AtomicSpec(s)
    acceptance_rule: str = "all_of"
    structural_contract: StructuralContract | None = None
    alternative_atoms: list[list[AtomicSpec]] = field(default_factory=list)
    abstain_reason_code: str | None = None
```

### Alternatives: avoiding false negatives (structure only, runner pending)

A compiler may produce specs that differ from the gold but are equally
valid. The `alternative_atoms` field holds additional valid spec sets.
The compiler output matches if it equals ANY of: `atoms` or any entry
in `alternative_atoms`. This is critical for mediation and heterogeneity,
where multiple valid formalizations exist.

**Status:** the field exists in `GoldTarget` but nothing consumes it
yet. The test runner must implement alternative-matching before this
provides actual false-negative protection. Noted as tech debt.

### Abstention vs non-identifiability (NOT the same)

Two distinct failure modes that must not be conflated:

- **Non-identifiability**: the claim IS expressible in the grammar.
  The compiler should produce specs with
  `measurement=identifiability_check` and `assertion=not_identifiable`.
  The verdict is a **real answer**: "this cannot be estimated from
  observational data." Example: "Can we estimate P→H?" in W3.

- **Abstention**: the claim CANNOT be expressed in the grammar at all.
  The compiler should refuse to compile. No spec is produced.
  Example: "Temperature changes precede health effects" (temporal),
  "What is the optimal dose?" (optimization).

### Intervention values: anchors, not hardcoded (target state)

**Target state:** For vague claims ("treatment improves outcome"), the
gold spec should use canonical anchors from the WorldSummary (hi/lo/mid),
not hardcoded values like 1.0/0.0. The compiler uses the WorldSummary to
pick intervention points, so the gold should match this contract.

Only when the surface form specifies exact values ("a one-unit increase")
should the gold use explicit numeric values.

**Current state:** The WorldSummary anchor system does not exist yet.
Current gold targets use hardcoded values (0.0, 1.0, -1.0, 1.5) that
are correct for these specific worlds. When anchors are implemented,
gold targets should migrate to use them. Noted as tech debt.

### Compound claims → multiple specs + acceptance rule

When a single claim contains multiple sub-findings, the gold has
multiple AtomicSpecs with an acceptance rule:

- **ALL_OF**: all sub-specs must hold. "T improves Y AND causes SE."
- **ANY_OF**: at least one sub-spec must hold. (Rare in practice.)

### False claims: same formalization, false verdict

A false claim (e.g., "exposure increases disease" when ATE is negative)
should compile to specs that are structurally correct but produce a
FALSE verdict. The gold has:
- `status="compile"` (it IS expressible)
- `assertion=POSITIVE` (what the claim asserts)
- Expected verdict = FALSE (because the SCM disagrees)

This tests whether the compiler formalizes correctly even when the
claim is wrong. The compiler is a TRANSLATOR, not a fact-checker.

### Mediation specs use CONTRAST_DIFF

For direct/indirect effect decomposition, the grammar has CONTRAST_DIFF:
- 4 arms: total_hi, total_lo, direct_hi, direct_lo
- Measurement: MEAN on outcome
- Comparison: CONTRAST_DIFF = (total_hi - total_lo) - (direct_hi - direct_lo)
- Assertion: POSITIVE if indirect is positive, etc.

Direct effect uses 2 arms with mediator fixed at reference value.

### Heterogeneity specs use conditioned arms

"Effect varies by modifier" → 4 arms conditioned on modifier high/low:
- hi_mod_hi, lo_mod_hi, hi_mod_lo, lo_mod_lo
- Comparison: CONTRAST_DIFF (effect in high stratum minus effect in low)
- Assertion: GAP_MATERIAL (generic heterogeneity) or POSITIVE (directional)

### Confounding detection: OBSERVE vs INTERVENE CONTRAST_DIFF

Confounding = observational effect differs from causal effect.
Formalization: 4-arm CONTRAST_DIFF with OBSERVE and INTERVENE arms:
- obs_hi, obs_lo (observational conditioning)
- causal_hi, causal_lo (interventional do-calculus)
- CONTRAST_DIFF = (obs effect) - (causal effect)
- GAP_MATERIAL assertion (non-zero = confounding exists)

Use symmetric values (e.g., T=+1/-1) to maximize the gap.

### Collider bias: IDENTIFIABILITY_CHECK with candidate_adjust_set

Collider bias facts ("adjusting for L biases the estimate") map to
identifiability checks with a specific candidate adjustment set:
- IDENTIFIABILITY_CHECK with `candidate_adjust_set=("L",)`
- NOT_IDENTIFIABLE assertion (this candidate set is invalid)

**Important distinction:** this is NOT "globally non-identifiable"
(like P->H in W3 where no adjustment set works). This is "this
specific candidate adjustment set is invalid." The causal effect E->D
IS identifiable via {C} — just not via {L}. The `candidate_adjust_set`
parameter makes this distinction explicit.

This is cleaner than trying to measure partial_corr(E,D|L) and
determine its sign, because the claim is about the validity of the
adjustment set, not about a specific numerical value.

### Stage 3 detail: beyond boolean verdicts (tech debt)

Codex review identified that stage 3 ("same boolean verdict") is too
weak for some fact types:
- **Scalars**: should compare sign + approximate magnitude, not just
  pass/fail. Use `AtomVerdict.detail` for this.
- **Changepoints**: should verify existence AND location (e.g.,
  changepoint_x near 0), not just existence.
- **Identifiability**: boolean is sufficient.

This is noted as tech debt for the test harness implementation. The
gold targets are correct; the harness needs to extract and compare
`detail` fields. NOT blocking for current batch.

### Abstention reason codes: soft labels

Codex recommended treating abstention reason codes as soft diagnostic
labels, not hard-fail criteria. Exact code match is useful for
categorization but should not be a pass/fail gate. The critical test
is: did the compiler abstain when it should have?

### Decisions documented but NOT yet implemented

- RJ (relevance judge) gold pairs: separate table structure with
  claim-SQ pairs and expected ordinal bands. Deferred to after claim/SQ
  gold is complete.
- `equivalence_group_id` for paraphrase families: will be added when
  CC-C1 / SQ-B3 families are implemented.

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

World implementation (W1-W3) reviewed by Codex (1 round, 2026-04-13).
Key contributions: variance-effect fact via B*T interaction in W1,
partial correlation Simpson's test in W2, keep sharp threshold in W3,
4 additional MC verification tests recommended and implemented.

Gold target design reviewed by Codex (4 rounds, 2026-04-13). Key
contributions: gold per surface form (not per fact), 3-stage evaluation
(compile/abstain → structural contract → verdict equivalence),
abstention vs non-identifiability distinction, CONTRAST_DIFF for
mediation and heterogeneity, anchor-based intervention values,
GoldTarget object structure, W3_F10 variance bug caught, label
overload bug (NOT_IDENTIFIABLE) caught, true/false balance critique.

Phase 1+2 review (rounds 3-4): alternative_atoms for false-negative
prevention, StructuralContract enrichment (mediator/modifier/condition
roles), W2_F02 covariance-vs-correlation fix, stage 3 detail comparison
(tech debt noted), confounding formalization (OBSERVE vs INTERVENE
CONTRAST_DIFF), collider bias as IDENTIFIABILITY_CHECK with
candidate_adjust_set, batch 2 coverage gaps (VARIANCE, TAIL_PROB,
opposite-sign mediation, positive identifiability, compileable SQ).
