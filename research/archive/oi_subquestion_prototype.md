# OI Sub-Question Prototype — 3 Curated Worlds

> **Date:** 2026-03-28
> **Purpose:** Hand-craft sub-questions for all 3 curated worlds to validate
> the sub-question architecture BEFORE implementing anything.
> **Codex thread:** 019d32e4-0fbb-7972-aa23-efd3277e235d (5 exchanges)
> **Status:** IMPLEMENTED — models + resolution + scoring + tests (23 passing)
> **Code:** `src/sreg/models/open_investigation.py` (models),
>   `src/sreg/tools/oi_subquestions.py` (resolution + scoring),
>   `tests/tools/test_oi_subquestions.py` (23 tests)
> **Codex review:** 4 bugs found and fixed (ranking matching, ALL_OF
>   correctness, heterogeneity spec selection, subsumption strictness)

## Design Schema (from Codex debate)

### Key insight: a sub-question is NOT a claim

A sub-question represents an **investigation agenda** (what to look into),
not an **assertion** (what's true). It needs its own type, not a reuse of
ClaimIntent.

### SubQuestionIntent (what the orchestrator generates)

```python
class SubQuestionIntent(BaseModel):
    sq_id: str
    pattern: PatternClass
    roles: SQRoles          # treatment/outcome/mediator/modifier/confounder
    ask: AskOperator         # existence | sign | existence_and_sign | magnitude | rank_order
    weight: float            # 0..1, from tiers: high=1.0, medium=0.6, low=0.4
    materiality_threshold: float | None  # what counts as "exists"
    text_gloss: str | None   # human-readable, not used in scoring
```

### ResolvedSubQuestion (after deterministic resolution against SCM)

```python
class ResolvedSubQuestion(BaseModel):
    intent: SubQuestionIntent
    resolved_answer: ResolvedAnswer     # exists/direction/magnitude
    components: list[SQComponent]       # for multi-component SQs (mediation, confounding)
    acceptance_rule: AcceptanceRule      # any_of | all_of
    resolution_evidence: dict           # raw scalars (ATE, indirect_effect, gap, etc.)
```

### Resolution flow

```
SubQuestionIntent
  -> build candidate answers (positive/negative/near_zero)
  -> lower each to AtomicSpecs (reuse existing lowering)
  -> verify against SCM
  -> pick winner -> ResolvedSubQuestion
```

### Matching: claim vs sub-question

```
score_claim_vs_sq(claim, resolved_sq) -> float:
    1. Check truth (claim verified against SCM upstream)
    2. Direct match: pattern + roles -> full credit
    3. Component match: claim matches a component -> partial credit
    4. Subsumption match: e.g., mediation claim -> partial credit on causal_effect SQ
    5. Multiply: truth * match_quality * answer_compatibility * component.contribution
```

### Subsumption table (from Codex)

| SQ pattern | Full match | Partial/component match | No credit |
|---|---|---|---|
| causal_effect(X,Y) | causal_effect(X,Y) | mediation(X,M,Y): 0.6, heterogeneity(X,Z,Y): 0.4 | confounding, obs_assoc, tail_risk |
| mediation(X,M,Y) | mediation(X,M,Y) | causal_effect(X,Y): 0.35 (total effect component) | heterogeneity, confounding |
| confounding(X,C,Y) | confounding(X,C,Y) | causal_effect(X,Y): 0.35, obs_assoc(X,Y): 0.35 | mediation, heterogeneity |
| heterogeneity(X,Z,Y) | heterogeneity(X,Z,Y) | causal_effect(X,Y): 0.35 (base effect) | mediation, confounding |
| obs_association | exact only | none in Alpha | all others |
| tail_risk | exact only | none in Alpha | all others |
| effect_ranking | exact set | multiple causal_effect claims -> set-level | all others |

---

## World 1: Treatment (5 variables)

### Brief
"Investigate why treatment outcomes varied across patients. Does the treatment
help recovery? Through what mechanism? Are there confounding factors?"

### Causal structure
```
Age -> Severity -> Treatment -> Biomarker -> Recovery
                   Treatment -> Recovery (direct: 0.3)
                   Severity -> Recovery (direct: -0.5)
                   Age -> Recovery (direct: -0.01)
```

### Sub-questions

**SQ1: Does Treatment causally affect Recovery?** [HIGH]
- pattern: causal_effect, roles: {treatment: Treatment, outcome: Recovery}
- ask: existence_and_sign, weight: 1.0
- Resolution: ATE positive (total ~0.54 = 0.3 direct + 0.24 indirect)
- Maps to salience family #5

**SQ2: Is Treatment effect mediated through Biomarker?** [HIGH]
- pattern: mediation, roles: {treatment: Treatment, mediator: Biomarker, outcome: Recovery}
- ask: existence, weight: 0.8
- Resolution: Yes, indirect effect +0.24 (-0.6 * -0.4)
- acceptance_rule: ALL_OF (indirect component + total effect component)
- Maps to salience family #2

**SQ3: Does Severity confound Treatment-Recovery?** [HIGH]
- pattern: confounding, roles: {treatment: Treatment, outcome: Recovery, confounder: Severity}
- ask: existence, weight: 0.9
- Resolution: Yes, material gap between naive and adjusted association
- acceptance_rule: ALL_OF (gap component + causal component + obs component)
- Maps to salience family #12

**SQ4: Does Severity causally affect Recovery?** [MEDIUM]
- pattern: causal_effect, roles: {treatment: Severity, outcome: Recovery}
- ask: sign, weight: 0.6
- Resolution: Negative (-0.5 total)
- Maps to salience family #11
- NOTE: Codex correction — this measures TOTAL effect, not direct

**SQ5: Does Age affect Recovery?** [LOW]
- pattern: causal_effect, roles: {treatment: Age, outcome: Recovery}
- ask: existence_and_sign, weight: 0.4
- Resolution: Small negative (total via Age->Severity->Recovery + direct -0.01)
- Materiality concern: effect may be below threshold
- No direct salience family

### Validation against batch 1 + E2E post-fix

| Pilot claim | Compiled as | Matches SQ | Score |
|---|---|---|---|
| "Treatment -> Recovery adjusted" | causal_effect(T,R) | SQ1 | 1.0 |
| "Severity confounds T-R" | confounding(T,R,Severity) | SQ3 | 1.0 (NEW: was 0) |
| "Treatment -> Biomarker -> Recovery" | mediation(T,B,R) | SQ2 | 1.0 |
| "Treatment association modest" | abstention | none | 0.0 (compiler issue) |
| "Sicker patients recover worse" | folded into confounding | SQ4 | partial via subsumption |

---

## World 2: Ecosystem (6 variables)

### Brief
"Investigate the factors that drive fish population variation across sites.
What are the main determinants? Are there interaction effects or confounding
relationships?"

### Causal structure
```
Sun -> Nutrients (0.6)
Sun -> Algae (0.3)
Temp (exogenous)
Depth (exogenous)
Nutrients -> Algae (0.5)
Nutrients x Temp -> Algae (interaction: 0.25*(Temp-20)/4)
Algae -> Fish (0.4)
Depth -> Fish (0.5)
```

### Sub-questions

**SQ1: What are the main determinants of Fish population?** [HIGH]
- pattern: effect_ranking, roles: {ranking_vars: [Algae, Depth, Sun, Nutrients, Temp], outcome: Fish}
- ask: rank_order, weight: 1.0
- Resolution: Algae > Depth >> others (direct parents dominate)
- Maps to salience families for causal_effect

**SQ2: Does Algae causally affect Fish?** [HIGH]
- pattern: causal_effect, roles: {treatment: Algae, outcome: Fish}
- ask: existence_and_sign, weight: 0.8
- Resolution: Positive (0.4)
- Maps to salience family: causal_effect(Algae, Fish)

**SQ3: Does Depth causally affect Fish?** [MEDIUM]
- pattern: causal_effect, roles: {treatment: Depth, outcome: Fish}
- ask: existence_and_sign, weight: 0.7
- Resolution: Positive (0.5)
- Maps to salience family: causal_effect(Depth, Fish)

**SQ4: Is there a Nutrients x Temperature interaction on Algae?** [HIGH]
- pattern: heterogeneity, roles: {treatment: Nutrients, modifier: Temp, outcome: Algae}
- ask: existence, weight: 0.8
- Resolution: Yes (coefficient 0.25, material)
- Maps to salience family: heterogeneity(Nutrients, Temp, Algae)
- NOTE: target is Algae not Fish — sub-question about intermediate variable

**SQ5: Does Sun confound Nutrients-Algae relationship?** [MEDIUM]
- pattern: confounding, roles: {treatment: Nutrients, outcome: Algae, confounder: Sun}
- ask: existence, weight: 0.6
- Resolution: Yes (Sun->Nutrients and Sun->Algae both exist)
- May not have salience family (confounding enum for Algae, not Fish)

### Validation against batch 1

| Pilot claim | Matches SQ |
|---|---|
| "Depth and Algae are main predictors" | SQ1 (ranking), SQ2 + SQ3 (individual) |
| "Temp/Nutrients lose significance via Algae" | SQ4/SQ5 partial (mediation signal) |
| "Algae driven by Sun/Temp/Nutrients" | SQ4 partial |
| "Depth x Algae interaction weak" | none — novel null finding |

---

## World 3: Education (5 variables)

### Brief
"Investigate the determinants of income inequality. What role does education
play? Is the education-income relationship confounded? Are there mediating
pathways?"

### Causal structure
```
Wealth (exogenous)
Motivation (exogenous)
Wealth -> Education (0.03)
Motivation -> Education (0.8)
Education -> Skill (0.5)
Wealth -> Income (0.15)
Skill -> Income (0.6)
Motivation -> Income (0.3)
Income noise scales with Skill (variance effect)
```

### Sub-questions

**SQ1: Does Education causally affect Income?** [HIGH]
- pattern: causal_effect, roles: {treatment: Education, outcome: Income}
- ask: existence_and_sign, weight: 1.0
- Resolution: Positive (via Skill)
- Maps to salience family: causal_effect(Education, Income)

**SQ2: Is Education-Income mediated through Skill?** [HIGH]
- pattern: mediation, roles: {treatment: Education, mediator: Skill, outcome: Income}
- ask: existence, weight: 0.9
- Resolution: Yes (Education->Skill: 0.5, Skill->Income: 0.6)
- acceptance_rule: ALL_OF
- Maps to salience family: mediation(Education, Skill, Income)

**SQ3: Is Education-Income confounded by Wealth?** [HIGH]
- pattern: confounding, roles: {treatment: Education, outcome: Income, confounder: Wealth}
- ask: existence, weight: 0.8
- Resolution: Yes (Wealth->Education: 0.03 + Wealth->Income: 0.15)
- Note: Wealth->Education effect is SMALL (0.03), so confounding may be below
  materiality threshold. This is an interesting edge case.
- Maps to salience family: confounding(Education, Income, Wealth) IF it exists

**SQ4: Does Wealth directly affect Income?** [MEDIUM]
- pattern: causal_effect, roles: {treatment: Wealth, outcome: Income}
- ask: sign, weight: 0.6
- Resolution: Positive (0.15)
- Maps to salience family: causal_effect(Wealth, Income)

**SQ5: Does Motivation affect Income?** [LOW]
- pattern: causal_effect, roles: {treatment: Motivation, outcome: Income}
- ask: existence_and_sign, weight: 0.4
- Resolution: Positive (0.3 direct + indirect via Education->Skill)
- Maps to salience family: causal_effect(Motivation, Income)

### Validation against E2E post-fix (1.0 correctness!)

| Pilot claim | Compiled as | Matches SQ |
|---|---|---|
| C1: "Income associated with Wealth" | obs_association(Wealth, Income) | SQ4 partial (subsumption) |
| C2: "Education confounded by Wealth+Motivation" | confounding(Education, Income, ...) | SQ3 |
| C3: "Education -> Skill -> Income mediation" | mediation(Edu, Skill, Income) | SQ2 |

All 3 claims scored 1.0 correctness! SQ1 (causal_effect Education->Income)
would get partial credit via subsumption from the mediation claim (SQ2).

---

## E2E Post-Fix Results (2026-03-28)

| World | Total | Correct | Coverage | Key finding |
|---|---|---|---|---|
| ecosystem | 0.533 | 0.667 | 0.111 | Compiler still loses some claims |
| treatment | 0.400 | 0.500 | 0.000 | Confounding NOW compiles! Precision gate kills score |
| education | 0.750 | 1.000 | 0.167 | All 3 claims correct, confounding works |

**Key validation:** Confounding fix works. Treatment C2 matched confounding
family (score=1.0). Education C2 matched confounding (score=1.0).

---

## Cross-World Analysis

### Patterns in sub-questions

All 3 worlds share:
- A core causal_effect SQ (highest weight)
- At least one confounding or mediation SQ
- Secondary causal_effect SQs for other variables
- Brief directly implies the top 2-3 SQs

### Coverage vs sub-questions

| World | Salience families | Sub-questions | Batch 1 avg claims | Coverage |
|---|---|---|---|---|
| treatment | 14 | 5 | 3-4 | 5 SQs * max 5 claims = good match |
| ecosystem | 17 | 5 | 3-4 | similar |
| education | 18 | 5 | 3 | similar |

Sub-questions (5) are much closer to what a solver actually produces (3-5 claims)
than salience families (14-18). This means coverage will be meaningful instead
of always being ~0.2.

### Novel findings (outside sub-questions)

These should get **bonus credit** (10-20%):
- Biomarker -> Recovery (treatment world)
- Depth x Algae interaction null finding (ecosystem)
- Motivation -> Education pathway (education)

---

## Open Questions (resolved and pending)

### RESOLVED (via Codex debate)

1. **Format**: SubQuestionIntent (separate type, not ClaimIntent) [RESOLVED]
2. **Multi-claim**: Take best (any_of) or require all components (all_of) [RESOLVED]
3. **Null findings**: Support "near_zero" in resolution + ask_operator [RESOLVED]
4. **Weights**: Tiers high/medium/low, not continuous [RESOLVED]
5. **Subsumption**: Explicit table, conservative [RESOLVED]

### PENDING

1. **Materiality threshold**: What value? Per-pattern default? Need empirical calibration.
2. **SQ generation by orchestrator**: How does the LLM generate these? Template? Free-form?
3. **SQ validation**: How to ensure orchestrator's SQs are answerable by the SCM?
4. **Bonus for novel findings**: Exact formula? Cap at 20%?
5. **Compound claims**: "Treatment and Severity both affect Recovery" — split before matching?
6. **SQ independence**: SQ1 and SQ2 overlap (mediation implies causal effect).
   Codex says: need subsumption + depends_on rules. Not fully designed yet.
7. **Number of SQs**: 5 per world seems right for these, but what about larger worlds?

## Key Finding: Epistemological Alignment (2026-03-28)

**SQs must match what the solver can epistemologically justify, not what the
orchestrator knows from the SCM.**

In the ecosystem world (observational only), the solver correctly reports
"Fish is associated with Depth" (observational_association). But the SQ
asked "Does Depth causally affect Fish?" (causal_effect). Zero SQs matched
because there's no subsumption obs_assoc → causal_effect.

**Codex ruling:** Don't add global subsumption. The solver can't claim
causation from observational data — rewarding association as causal credit
would be epistemological leakage.

**Fix:** SQ pattern depends on:
1. What the brief asks (causal? descriptive?)
2. What evidence the solver has (observational? experimental?)
3. What's epistemologically defensible

For observational-only worlds without causal hints in the brief:
- Use observational_association, effect_ranking, confounding
- NOT causal_effect (unless brief explicitly asks causal questions)

For worlds with causal brief language + adequate evidence:
- causal_effect, mediation, confounding are appropriate
- Treatment world: "does treatment help?" → causal SQs OK
- Education world: "confounded?" → confounding SQ OK

**This principle must guide orchestrator SQ generation.**

## Next Steps (updated 2026-03-28)

1. [x] Prototype resolution + matching + scoring (DONE)
2. [ ] Fix ecosystem SQs: change causal_effect to observational_association
3. [ ] Re-run pilots with corrected SQs
4. [ ] Analyze: does treatment/education improve? Does ecosystem match now?
5. [ ] Design orchestrator SQ generation with epistemological alignment
6. [ ] Implement orchestrator SQ emission (draft + validate + repair)
