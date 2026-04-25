# A21 Investigation — Compiler Ontology Bug

**Date:** 2026-03-29
**Type:** Autoresearch — deep investigation + experiments
**Branch:** autoresearch-open-investigation
**Status:** RESOLVED (architecture). Pending: E2E validation + weight tuning.
**Codex thread:** 019d3aec-a7db-75e0-bafd-a2bb889aa901

> **LA PREGUNTA filter**: The compiler mistranslates correct findings → 0 score.
> This means RL training would NOT learn from correct research behavior.
> Fixing this is prerequisite for everything else.

## Problem Statement

The OI compiler LLM extracts the WRONG `pattern` from claims. Correct findings
score 0.00 because pattern matching is exact.

**Evidence (Coral Case E2E):**
- Solver submitted 5 substantively correct claims
- ALL 4 SQs scored 0.00 MISS
- Root cause: compiler extracted `pattern=observational_association` instead of `causal_effect`

**Root cause chain:**
1. Solver prompt says "use associational language when unsure"
2. Solver uses hedged language ("drives", "associated with", "coefficient")
3. Compiler extraction prompt has override rule (line 79-80 oi_extraction.py) but it's insufficient
4. Exemplars show "correlated"→observational, "causes"→causal. No hedged-but-causal exemplars.
5. LLM maps hedged language → observational_association
6. lower_intent() produces PARTIAL_CORRELATION spec (observational) instead of CONTRAST_DIFF (causal)
7. match_specs_to_families() does EXACT pattern match → 0.0

## Failed Attempt: Structured Claims (REVERTED)

Commit 4a24686 (reverted fb99d85): Added `relation_type` enum to ClaimCard.
Violated "no construir juego estructurado" — biases solver toward categories.

## Debate Round 1: Codex Diagnosis

**Key insight: A21 is NOT a prompting bug — it's an ontology bug.**

The `pattern` field carries three incompatible responsibilities:
1. **Structural form** of the claim (mediation, heterogeneity, etc.)
2. **Epistemological status** (causal vs associational)
3. **Scoring routing** (which lowering path, which matching)

Codex's analysis:
- "causal_effect vs observational_association" is epistemological, not structural
- A good researcher with observational data CAN correctly report an association
- Punishing that with 0.0 doesn't reward better research; it rewards overclaiming
- The compiler shouldn't infer "underlying causal truth" — it should extract what the claim commits to
- The subsumption table in oi_subquestions.py (lines 64, 926) is evidence the ontology was already broken

**Codex conclusion:** "The bottleneck #1 is not LLM extraction quality. It's that the system
uses a mixed taxonomy as an exact key for reward."

## Debate Round 2: ClaimSkeleton Design

### Proposed separation of concerns

```python
class ClaimSkeleton(BaseModel):
    # STRUCTURAL (what relationship)
    relation_family: RelationFamily  # pairwise, mediation, heterogeneity, confounding, ranking, tail_risk, variance
    relation_operator: RelationOperator  # do-contrast, marginal-assoc, conditional-assoc, interaction-contrast, indirect-pathway
    roles: dict[str, str]  # {"treatment": "X", "outcome": "Y", ...}
    direction: Direction  # POSITIVE, NEGATIVE, NEAR_ZERO

    # EPISTEMOLOGICAL (how strong is the claim)
    claim_force: ClaimForce  # CAUSAL, ASSOCIATIONAL, AMBIGUOUS
    evidence_regime: EvidenceRegime  # INTERVENTIONAL, OBSERVATIONAL, ADJUSTED_OBS, UNKNOWN
```

### Critical Codex pushback on my original proposal

1. **Don't always lower to interventional specs.** If solver said "X and Y are associated",
   verifying with ATE rewrites the claim. Verify literally, then assess relevance separately.

2. **Need `relation_operator`, not just `relation_family`.** "X predicts Y", "X causes Y",
   "X predicts Y controlling for C" are all pairwise_directional but structurally different.

3. **Scoring should be `truth_literal * task_relevance * warrant`**, not `verified * pattern_match`.
   - `truth_literal`: the claim, taken literally, is true against SCM
   - `task_relevance`: how much does this claim help answer this SQ
   - `warrant`: is the epistemic force justified by evidence

4. **Where the design breaks if implemented naively:** A claim "X and Y are strongly associated
   after adjusting for C" gets lowered to interventional ATE, ATE is positive, scores high
   against causal SQ. But the solver never claimed causation! System rewards inference not stated.

5. **The fix:** Verify claims literally (association → verify association), then compute
   task_relevance as structural compatibility (same variables, same direction = partial credit).

### Algebra of compatibility (to design)

- `conditional_association(X,Y|Z)` partially supports `causal_effect(X,Y)`
- `mediation(X,M,Y)` partially supports `pairwise(X,Y)`
- `pairwise causal` fully supports causal SQ
- `pairwise associational` partially supports causal SQ
- Compatibility is NOT subsumption — it's a relevance score

## Debate Round 3: Compatibility Tables Design

Codex reviewed the proposed tables and recommended:
- `confounding → pairwise` lowered from 0.50 to 0.40
- `pairwise → confounding` lowered from 0.25 to 0.20
- `mediation → confounding` set to 0.0 (too distant)
- `do_contrast → cond_assoc` lowered from 0.85 to 0.75
- `marginal_assoc → cond_assoc` lowered from 0.70 to 0.55
- Operator compat only applies WITHIN same family (cross-family = 1.0)
- Contribution should NOT be applied inside score_claim_vs_subquestion

## Debate Round 4: Experiment Results Review

Codex validated the algebra is correct conceptually. Key feedback:
- `marginal_assoc → do_contrast = 0.50` is the most suspect value (might need 0.35-0.45)
- Next step: E2E with real LLM to validate systemic effect
- Migrate v1 scorer (match_specs_to_families) to same algebra
- Prompt work can wait — bottleneck may no longer be the compiler

## Experiments Log

### Experiment 1: Subsumption Entry (Proof of Concept)
- **Description:** Add `("observational_association", "causal_effect"): 0.50` to SUBSUMPTION_WEIGHTS
- **Files changed:** `src/sreg/tools/oi_subquestions.py` (1 line), `tests/tools/test_oi_subquestions.py` (4 tests)
- **Result:** 4/4 tests pass. obs_assoc gets partial credit, wrong dir/vars = 0, obs < mediation
- **Conclusion:** Confirms bottleneck was exact match, not compiler
- **Revert?** Superseded by Experiment 2

### Experiment 2: Compatibility Algebra (MAIN FIX)
- **Description:** Replace exact-match + subsumption with principled structural compatibility
- **Files changed:**
  - `src/sreg/tools/oi_subquestions.py`: +~200 lines (new types, tables, functions), modified `score_claim_vs_subquestion`
  - `tests/tools/test_oi_subquestions.py`: +~130 lines (7 new tests: 4 edge cases + 3 Coral simulation)
- **New code:**
  - `RelationFamily` enum (7 values)
  - `RelationOperator` enum (9 values)
  - `ClaimRepr` named tuple
  - `derive_family()`, `derive_operator()`, `claim_repr_from_intent()`, `claim_repr_from_sq()`
  - `FAMILY_COMPAT` table (14 entries)
  - `OPERATOR_COMPAT` table (15 entries)
  - `structural_compatibility()` — core function
- **Result:** 41/41 tests pass (38 existing + 3 Coral simulation)
- **Coral Case Simulation Results:**

  | Scenario | OLD score | NEW score | Change |
  |----------|-----------|-----------|--------|
  | Observational claims (A21 bug) | 0.200 | **0.755** | +277% |
  | Causal claims (correct compile) | 1.000 | **1.000** | unchanged |
  | Gap (incentive to improve) | — | **0.245** | healthy |

- **Key design decisions:**
  1. Operator compat only within same family (cross-family = 1.0)
  2. Contribution NOT applied inside scorer (avoids double-counting)
  3. Multiplicative formula: fam * op * role
  4. Treatment/outcome are hard gates, extra roles are bonuses
- **Revert?** NO — this is the solution. To be refined based on E2E validation.

## Web Research Findings

### Techniques evaluated (from web search)

| Approach | Impact | Effort | Verdict |
|----------|--------|--------|---------|
| Reasoning field before pattern | Medium | Low | Helps prompting but doesn't fix ontology |
| Classify-first-then-extract | Medium | Medium | Same — local optimization on fragile interface |
| Native structured outputs (API) | Low | Low | Format compliance only, not semantic |
| Self-consistency / multi-pass | Low | Low | Doesn't help if model is systematically wrong |
| Tool/function calling | Low | Medium | Same format benefit |
| DSPy typed predictors | Medium | High | Framework adoption, overkill |
| Instructor + retry | Medium | Low | Good for format, not for ontology |
| Fine-tuning | High | Very High | Best accuracy but not generalizable |

**Codex's verdict on all of these:** "They can lower the error rate. None fix that a mixed
label decides relevance and coverage. They're local optimizations on a fragile interface."

## Conclusions (evolving)

1. A21 is an ontology problem, not a prompting problem
2. `pattern` must be factored into `relation_family`, `relation_operator`, `claim_force`, `evidence_regime`
3. Matching must become compatibility-based, not exact
4. Verification must be literal (verify what was claimed, not what we wish was claimed)
5. Task relevance is a separate axis from truth
6. Prompting improvements are worthwhile BUT only as secondary optimizations
7. **VALIDATED**: The compatibility algebra fixes A21 (+277% on Coral case) while preserving correct incentives (causal > obs gap = 0.245)

## E2E Validation with Real LLM (2026-03-29)

### Setup
- Coral seed (`seeds/coral_reef_bleaching.md`) + soil goal (8 nodes)
- Orchestrator: gpt-5.4, Solver: gpt-5.2-codex, Compiler: gpt-5.4
- Algebra active in oi_subquestions.py and oi_compiler.py

### Coral Results (5 claims submitted)
| Claim | Compiler output | Matched SQ | Score |
|-------|----------------|------------|-------|
| C1: thermal stress → bleaching (multivariable) | `obs_association(acute_thermal_stress → bleaching_severity)` | sq1 (causal_effect) | **0.65 HIT** |
| C2: 1 SD reduction → 10.35 pts | `obs_association(acute_thermal_stress → bleaching_severity)` | — (duplicate C1) | — |
| C3: prior bleaching → recovery | `obs_association(prior_bleaching_burden → recovery_index)` | sq2 (causal_effect) | **0.65 HIT** |
| C4: water quality > management | `effect_ranking(water_quality_index → recovery_index)` | — | — |
| C5: hidden site property | ABSTENTION (residual site differences) | — | — |

**SQ Total: 0.552** (correctness 1.0, coverage 0.396). sq3 mediation MISS (no claims),
sq4 heterogeneity 0.12 HIT (cross-family partial from C1).

**Key finding:** Algebra works — obs claims get 0.65 partial credit against causal SQs.
Old system would score 0.00 on sq1 and sq2 (exact-match failure = A21).

### Soil Results (4 claims submitted)
| Claim | Compiler output | Matched SQ | Score |
|-------|----------------|------------|-------|
| C1: mining → metals → stress → vigor (chain) | **ABSTENTION** ("multiple associations") | — | — |
| C2: stress symptoms = strongest correlates | `effect_ranking(root_stress_index → crop_vigor)` | — (wrong vars) | — |
| C3: soil acidity buffers contamination | **ABSTENTION** ("multiple claims") | — | — |
| C4: residual site differences | **ABSTENTION** ("not testable") | — | — |

**SQ Total: 0.200** (all 5 SQs MISS, only novel bonus 0.200).

### E2E Conclusions

1. **A21 algebra VALIDATED**: In coral, obs_association claims correctly get 0.65
   partial credit against causal_effect SQs. Old code = 0.00.
2. **NEW BOTTLENECK DISCOVERED (A22): Compiler abstention rate.**
   In soil, 3/4 claims are ABSTENTION because the solver writes compound/chain
   claims that the compiler can't decompose into a single treatment→outcome pair.
   The ClaimIntent IR forces one treatment + one outcome. Claims like "X→Y→Z→W"
   or "X is associated with both Y and Z" are rejected.
3. **Solver non-submission** is also a recurring issue (3/5 runs didn't submit).
   Separate from A21/A22 but affects evaluation reliability.

## Legacy code to clean up

These are now dead code after Experiment 2:
- `SUBSUMPTION_WEIGHTS` dict (oi_subquestions.py:66-91) — ALREADY REMOVED
- `_exact_pattern_roles_match()` function — ALREADY REMOVED
- `_roles_compatible_subsumption()` function — ALREADY REMOVED

## Next Steps

- [x] Design the compatibility algebra
- [x] Prototype compatibility matching
- [x] Run against Coral case claims — recall improved from 0.200 to 0.755
- [x] Validate no false positive explosion — direction/variable gates still work
- [x] E2E with real LLM — coral validated, soil exposed A22
- [x] Migrate v1 scorer (match_specs_to_families) to same algebra
- [x] Clean up legacy code (SUBSUMPTION_WEIGHTS, etc.)
- [ ] Tune marginal_assoc→do_contrast (currently 0.50, might need 0.35-0.45)
- [ ] ClaimSkeleton proper as new IR (Phase 3, deprioritized vs A22)
- [ ] **A22: Fix compiler abstention rate** — decompose compound claims or extract
  dominant pair instead of abstaining. This is now the #1 bottleneck.
