# E2E Qualitative Analysis — 2026-03-28

> LA PREGUNTA: "Why isn't this real research yet? What's missing?"

## Context

Two E2E runs after removing `target_node` from OI pipeline.
All non-latent variables now report as `observable` (legacy `target` accepted for backward compat).
Sub-questions define the evaluation agenda, not a single target.

## Case 1: Lianxi Highlands (Development Economics)

**Seed:** poverty_reduction_china.md
**World:** 12 variables, 1 latent (social_norm_orientation), panel data (500 rows, 12 sites, 2 waves)
**Brief:** Evaluate rural resilience grant — income effects + behavioral spillovers
**SQs:** 4 (causal_effect, mediation, heterogeneity, observational_association)

### What looked like real research

1. **World design is realistic.** Multiple causal pathways (program -> income -> preferences), latent confounder (social norms), eligibility formula creating quasi-experiment, panel structure with site/wave identifiers, 15-21% missing data. A development economist would recognize this as plausible.

2. **Brief is high quality.** Multiple research objectives (economic + behavioral), asks about mechanism (mediation), asks about heterogeneity (saturation modifies effects), realistic policy evaluation framing.

3. **Sub-questions are well-targeted.** Each SQ maps to a brief deliverable. Causal_effect on the main treatment, mediation through income, heterogeneity by village saturation, observational association for secondary outcome.

4. **Solver's instincts were correct.** It recognized eligibility_gap as a potential instrument for program_participation (exactly what a development economist would do). It attempted 2SLS. It explored data quality systematically.

### What went wrong (environment failures)

| Iteration | What happened | Category |
|-----------|---------------|----------|
| 1-4 | Data exploration, missingness, panel structure | Real research |
| 5-6 | Eligibility gap as instrument, participation relationship | Real research |
| 7 | `import statsmodels` -> blocked | Environment friction |
| 8 | `from oi import regress` wrong syntax | Solver error (discoverability) |
| 9 | `oi.regress(fe=['site_id'])` unsupported | Environment friction |
| 10 | `d` undefined (prior block failed at import) | Cascade from env friction |
| 11 | `oi.regress` with bool dummies -> error | Environment friction |
| 12 | `inspect` blocked | Environment friction |
| 13 | OLS without dummies works | Real research |
| 14 | OLS with manually converted dummies works | Real research |
| 15 | DEADLINE nudge (5 remaining) | Too late |
| 16-17 | Manual 2SLS with numpy, dtype errors | Real research (forced workaround) |
| 18-19 | 2SLS finally works, first-stage stats | Real research |
| 20 | First-stage R2 computed | Real research (no time to submit) |

**Result: 0 claims submitted, 0 score.** The solver did real analysis but never submitted.

### Root cause diagnosis

1. **Incoherent contract** (Codex's framing): World requires IV/FE/mediation, but tools only provide OLS.
2. **8/20 iterations wasted** on tooling friction (env: 5, solver discoverability: 2, cascade: 1)
3. **Deadline nudge too late** — by iteration 15, solver was deep in manual 2SLS
4. **No submission urgency** — solver prioritized "get the right answer" over "submit anything"

### Counterfactual: what would have happened with fixes

With statsmodels/linearmodels available:
- Iteration 7: `import statsmodels.api as sm` -> works
- Iteration 8: IV regression with sm.OLS first stage + 2SLS
- By iteration 10: Full IV results with site FE
- Iterations 11-15: Mediation analysis, heterogeneity tests
- Iteration 16-18: Formulate and submit claims
- **Likely outcome: 3-4 claims submitted, reasonable score**

## Case 2: Brackenshire Water (Environmental Engineering)

**Seed:** Orchestrator-generated (from previous session)
**World:** 10 variables, 1 latent (biofilm_instability)
**Brief:** Investigate discoloration drivers in municipal water network
**SQs:** 5 (causal_effect, mediation, heterogeneity, effect_ranking, observational_association)

**Result:** SRC generated successfully. OI solver phase did not complete.
Root cause likely: background process killed during context compaction, or unhandled error.

## Synthesis: gaps ranked by severity

### 1. E2E reliability (CRITICAL)
50% completion rate (1/2 cases didn't finish). A benchmark that doesn't reliably run is not a benchmark.
**Status: Being addressed by current rerun with new seeds.**

### 2. Environment-method mismatch (HIGH)
Worlds require causal inference methods, sandbox only allows OLS.
**Status: FIXED — statsmodels, linearmodels, sklearn now allowed.**

### 3. Claim submission mechanics (HIGH)
Solver did real analysis but scored 0 because it never submitted.
**Status: PARTIALLY FIXED — progressive nudges at 50%/75%/final.**
**Remaining: Consider auto-submit fallback, continuous claim drafting.**

### 4. Tool discoverability (MEDIUM)
Solver couldn't discover oi.regress signature (inspect blocked, help() not tried).
**Status: Partially addressed by allowing statsmodels (solver uses familiar APIs).**
**Remaining: Add oi.help() or docstring access.**

### 5. Attention anchor (MONITOR)
Removing target_node may cause "explore everything, conclude nothing" pattern.
**Status: Monitoring in new runs. Sub-questions should provide some focus.**
**Codex's suggestion: If pattern persists, require solver to choose primary sub-question in first 2-3 iterations.**

## Metrics to track in new runs

Per Codex's recommendation:
1. Iteration to first draft claim
2. Whether draft claim exists by 50% mark
3. Iterations on broad EDA after first answerable result
4. Number of distinct variables touched before first claim
5. Whether claims submitted before final turn
6. Total tooling friction iterations (env vs solver errors)

## Case 3: Darband Delta Soil (Environmental Health) — NEW

**Seed:** soil_heavy_metals.md
**World:** 15 variables, no latent, complex environmental health pathway
**Brief:** Investigate metal exposure pathways in canal-irrigated farms
**SQs:** 4 (causal_effect, mediation, heterogeneity, effect_ranking)

### Key observations

1. **statsmodels worked perfectly** — solver imported and used it throughout
2. **All 3 progressive nudges fired** (50%, 75%, FINAL)
3. **Research quality was excellent**: multiple model specifications, pathway analysis, R2=0.70+
4. **BUT: 0 claims submitted despite FINAL nudge saying "You MUST call submit_claims now"**
5. The solver ran another regression on its last turn instead of submitting

**Root cause: Behavioral — solver treats submit_claims as psychologically terminal.**

## Case 4: Pelagos Arc Coral (Marine Ecology) — NEW, FIRST SUBMISSION

**Seed:** coral_reef_bleaching.md
**World:** 12 variables, no latent, marine ecology
**Brief:** Investigate heat shock and recovery dynamics
**SQs:** 4 (2x causal_effect, mediation, heterogeneity)

### Key observations — BREAKTHROUGH

1. **Solver submitted 5 claims!** (17 steps, 147s)
2. **Claims are substantively correct:**
   - c1: thermal_stress drives bleaching (coeff 3.84, p<1e-9) — matches SQ1
   - c3: prior bleaching reduces recovery (-2.47, p=0.0005) — matches SQ2
   - c5: unmeasured site heterogeneity exists (site residual analysis)
3. **BUT: ALL 4 SQs scored 0.00 MISS!**
4. Total SQ score: 0.200 (entirely from novel_bonus)

### Root cause analysis: claim-to-SQ matching failure

The scoring pipeline:
1. Claim compiler (LLM) extracts formal ClaimIntent from claim text
2. ClaimIntent is matched against SubQuestions by pattern + roles

The failure: solver claims use "association" language (correctly — it's observational data).
But SQs expect "causal_effect" pattern. The compiler likely extracted pattern=observational_association
instead of causal_effect, causing an exact-pattern-match failure.

**This is a fundamental tension**: we tell the solver to be cautious about causation (good science),
but the SQs expect causal claims (because the ground truth IS causal). The compilation layer
needs to bridge this gap without incentivizing overclaiming.

## 4-Case Synthesis

| Case | Domain | Submitted? | Claims | SQ Score | Root cause |
|------|--------|-----------|--------|----------|-----------|
| Poverty | Dev econ | No | 0 | N/A | Tooling friction (pre-fix) |
| Pollution | Water eng | Crash | - | N/A | E2E reliability |
| Soil | Env health | No | 0 | N/A | Submission aversion (post-fix) |
| Coral | Marine eco | **YES** | **5** | 0.200 (0/4 SQs) | Claim compilation failure |

### Answer to LA PREGUNTA (updated)

The **worlds and briefs** already look like real research. The **solver** can do real investigation
(2SLS attempts, multi-model analysis, causal pathway exploration). The **sub-questions** capture
real research objectives.

**What's NOT real yet: the evaluation harness.**

1. The harness can't reliably convert solver findings into scored outcomes
2. The claim compilation (LLM step) fails to bridge hedged language → formal patterns
3. The exact-match scoring rejects correct-but-cautious findings
4. The submit_claims tool creates a terminal-action problem

**Codex's summary**: "the worlds may already be good enough, and the solver may already be
capable of useful research behavior, but the evaluation harness is still not trustworthy
enough to tell you that."

### Priority stack for next work

1. **Redesign submit_claims to be structured** — add fields: relation_type, treatment, outcome,
   direction, estimate, causal_confidence. Don't require LLM to infer ontology from hedged prose.
2. **Split scoring into separate axes** — topical match, inferential type, sign, evidence strength
3. **Hard submit guard on final iteration** — already implemented, needs validation
4. **Audit failed claims** — classify as compiler miss vs SQ ontology mismatch vs wrong answer

## What we changed (code)

1. `python_exec.py`: Added statsmodels, linearmodels, sklearn to ALLOWED_IMPORTS
2. `oi_prompts.py`: Removed "NOT available: statsmodels" -> "You can also import: statsmodels, linearmodels, sklearn"
3. `oi_driver.py`: Progressive nudges (50% operational, 75% deadline, final mandatory)
4. `oi_driver.py`: Hard guard on final iteration (reject non-submit tool calls)
5. `oi_driver.py`: Temperature retry fix (disable after first failure)
6. `pyproject.toml`: Added statsmodels, linearmodels, scikit-learn as dependencies
7. (from previous session): 7 files changed for target_node removal from OI pipeline
