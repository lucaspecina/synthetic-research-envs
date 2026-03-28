# OI Pilot Batch Analysis — 6 runs across 3 curated worlds

> **Date:** 2026-03-27
> **Models:** Solver: gpt-5.2-codex, Compiler: gpt-5.4
> **Config:** Warrant disabled, N_MC=20000, max_iterations=20

## Score Summary

| World     | Run | Total | Correct | Coverage | Fam Hit | Steps | Time |
|-----------|-----|-------|---------|----------|---------|-------|------|
| ecosystem | A   | 0.603 | 0.750   | 0.176    | 3/17    | 11    | 122s |
| ecosystem | B   | 0.688 | 0.833   | 0.294    | 5/17    | 12    | 134s |
| treatment | A   | 0.619 | 0.750   | 0.231    | 3/13    | 9     | 79s  |
| treatment | B   | 0.649 | 0.800   | 0.231    | 3/13    | 7     | 107s |
| education | A   | 0.400 | 0.500   | 0.000    | 2/16    | 6     | 80s  |
| education | B   | 0.775 | 1.000   | 0.250    | 4/16    | 6     | 89s  |

**Averages:** total=0.622, correctness=0.772, coverage=0.197

## Qualitative Analysis — What the solver investigated

### Ecosystem (target: Fish)

**Investigation strategy (both runs):**
1. Load data, descriptive stats
2. Bivariate correlations with Fish
3. Full multivariate regression (Fish ~ all predictors)
4. Regression without Algae (to test mediation)
5. Regression of Algae on its predictors
6. Interaction terms (Depth x Algae)
7. Stratified analysis (run B)

**Key findings the solver reported:**
- Depth and Algae are the two strongest predictors (correct)
- Temp/Nutrients/Sun lose significance after controlling for Algae (mediation-like)
- Algae itself is driven by Sun, Temp, Nutrients (correct)
- Depth x Algae interaction is weak (p~0.076) — correctly cautious
- Run B: stratified analysis showing Depth effect is robust across Algae levels

**Quality of investigation:** HIGH. The solver correctly identified the causal
structure without claiming causation. Used multiple regression approaches,
checked for mediation patterns, tested interactions, used stratification.
This is genuinely good observational research methodology.

### Treatment (target: Recovery)

**Investigation strategy (both runs):**
1. Load data, correlations
2. Bivariate relationships
3. Adjusted regression (Recovery ~ Treatment + Severity + Age)
4. Biomarker pathway analysis (Treatment -> Biomarker -> Recovery)
5. Quartile analysis of treatment by severity (run B)

**Key findings the solver reported:**
- Severity confounds Treatment-Recovery (sicker patients get more treatment)
- After adjusting for Severity+Age, Treatment has positive effect (coef~0.59)
- Biomarker mediates part of the treatment effect
- Run B: additional confounding evidence via quartile analysis

**Quality of investigation:** HIGH. The solver correctly identified confounding
(Severity) and mediation (via Biomarker) — the two most important structural
features of this world. Anti-overclaiming worked: says "associated" not "causes."

### Education (target: Income)

**Investigation strategy (both runs):**
1. Correlations with Income
2. Bivariate and multivariate regressions
3. Education coefficient with and without controls
4. Education -> Skill -> Income mediation check

**Key findings the solver reported:**
- Wealth is dominant correlate of Income (r~0.71 vs Education r~0.39)
- Education's effect weakens after controlling for Wealth and Motivation
- Education -> Skill -> Income mediation: Education coef drops to ~0 with Skill
- Run B: much cleaner mediation finding (score 1.0 correctness)

**Quality of investigation:** GOOD. Run A was weaker (too broad, imprecise claims).
Run B was excellent — focused, clean mediation analysis.

## Claim-Level Problem Table

### Claims that scored WELL (correctness >= 0.75)

| World     | Claim | What it said | Why it worked |
|-----------|-------|-------------|---------------|
| ecosystem | c1    | Depth+Algae are main predictors | Matched causal_effect families |
| ecosystem | c3    | Algae driven by Sun/Temp/Nutrients | Matched observational_association |
| treatment | c1    | Treatment -> Recovery (adjusted) | Matched causal_effect family |
| treatment | c3    | Treatment -> Biomarker -> Recovery | Matched mediation family |
| education | C3(B) | Education -> Skill -> Income mediation | Matched mediation family |

### Claims that scored POORLY (correctness < 0.5 or unmatched)

| World     | Claim | What it said | Problem | Root cause |
|-----------|-------|-------------|---------|------------|
| ecosystem | c2    | Temp/Nutrients lose significance via Algae | Mediation-suggestive | **Compiler can't compile "association disappears after controlling"** — this is a confounding/mediation signal but not phrased as a formal mediation claim |
| ecosystem | c4    | Depth x Algae interaction is weak | Null finding | **No support for "no effect" claims** — the solver correctly found no interaction but the system can't verify negative claims |
| treatment | c2    | Severity confounds Treatment-Recovery | Confounding | **Confounding is not a compilable pattern** — the salience map has no "confounding" family, so this correct and important finding gets 0 |
| education | C1(A) | Wealth is dominant correlate | Association | **Too broad** — mentions 4 variables, unclear what the compilable claim is |
| education | C2(A) | Education effect weakens with controls | Confounding check | **Same as treatment c2** — confounding analysis can't be compiled |

## Systematic Problems Identified

### P1: Confounding claims get zero credit (CRITICAL)
The solver correctly identified confounding in 4 out of 6 runs — this is one
of the most valuable things a researcher can discover. But the compiler has
no "confounding" pattern. These claims get compiled as observational_association
or abstention, losing the key insight.

**Impact:** 4/6 runs have at least one confounding claim that scores 0.
**Fix needed:** Add confounding as a compilable pattern, or map it to existing
patterns (e.g., "X confounds Y-Z" -> observational_association(X,Y) with note
that controlling for X changes Y-Z relationship).

### P2: Null/negative findings get zero credit (MODERATE)
The solver sometimes correctly concludes "this effect is weak or absent" (e.g.,
Depth x Algae interaction). These are valuable scientific conclusions but the
system only rewards positive findings.

**Impact:** 1-2 claims per batch.
**Fix needed:** Support NEAR_ZERO assertions in the compiler for "no effect" claims.

### P3: Coverage is very low (MODERATE)
Best coverage: 0.294 (5/17 families). The salience map has 13-17 families but
the solver typically matches 3-5. Many families are about patterns the solver
didn't investigate (tail_risk, effect_ranking, heterogeneity).

**Interpretation:** This is EXPECTED — the salience map intentionally covers
more than any single investigation would. But it means coverage contributes
very little to the total score (30% weight, but 0.2 coverage = 0.06 contribution).

**Question:** Is 17 families too many for a 5-claim investigation? Should coverage
weight be lower, or should the salience map be pruned?

### P4: Precision gate kills education run A (MODERATE)
Education run A got precision_gate=True, dropping total to 0.400 despite having
correct claims. The precision gate activates when too many claims are false/unmatched.

**Impact:** 1/6 runs.
**Analysis:** The solver's claims were correct but too broad/vague for the compiler.

### P5: "Association" tags don't help the compiler (LOW)
The solver uses tags like "association", "adjusted", "confounding_check" but the
compiler only knows: causal_effect, mediation, heterogeneity, tail_risk,
variance_effect, observational_association, effect_ranking.

**Impact:** Low — the LLM compiler ignores tags and reads claim text.
**Note:** The deterministic fallback would be more affected.

### P6: Import errors waste steps (LOW)
In every run, the solver tries `from functions import load_artifact` or
`import statsmodels` first, gets blocked, then uses the correct approach.
Wastes 1-2 steps per run.

**Fix:** Improve prompt to emphasize available functions more clearly.

## What SHOULD have received credit but didn't?

1. **Confounding identification** — the single most valuable finding in the
   treatment world (Severity confounds Treatment-Recovery). Score: 0.

2. **"Association disappears after controlling"** — a sophisticated mediation/
   confounding signal. The solver notices that Nutrients' effect on Fish disappears
   after adding Algae. This IS mediation evidence but isn't phrased as a formal
   mediation claim.

3. **Quartile/stratification analysis** — the solver stratifies data to show
   that treatment effect varies by severity level. This is heterogeneity
   evidence but framed as "confounding check."

4. **Null findings** — "no significant interaction" is a real finding that
   narrows the hypothesis space.

## What the solver gets RIGHT that the system doesn't reward

- **Epistemological humility**: says "associated" not "causes" throughout
- **Confounding awareness**: identifies and discusses confounders in every run
- **Multi-step reasoning**: starts broad, narrows, tests alternative explanations
- **Mediation detection**: correctly identifies mediating pathways
- **Appropriate caution**: notes limitations (observational data, can't claim causation)

## Recommendations (priority order)

1. **P1 Fix: Add confounding as compilable pattern** — this is the highest-value
   fix. Map "X confounds Y->Z" to a verifiable spec (e.g., observational
   association X-Y + X-Z + sign change in Y-Z after conditioning on X).

2. **P2 Fix: Support NEAR_ZERO assertions** — allow the compiler to handle
   "no significant effect" as a valid finding.

3. **P6 Fix: Improve solver prompt** — add explicit "load_artifact is already
   in your namespace" and "statsmodels is not available, use oi.regress".

4. **P3 Consider: Reduce coverage weight** — coverage is systematically low
   because the salience map is comprehensive. Consider 0.15 instead of 0.30.

5. **P4 Consider: Relax precision gate** — or make it more granular (currently
   seems binary — either kills score or doesn't).

## Conclusion

The OI pipeline works. The solver genuinely investigates, finds real patterns,
uses appropriate methodology, and maintains epistemological humility. The main
gap is between what the solver discovers (confounding, null effects, mediation
signals) and what the scoring system can verify. The compiler + salience map
cover ~60-70% of what a good investigation finds. The remaining 30-40% are
valuable findings that fall through the cracks — primarily confounding analysis
and null results.

**Next step:** Fix P1 (confounding) and P2 (null findings), then re-run pilots
to see if scores improve.
