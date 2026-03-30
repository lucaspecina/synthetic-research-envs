# S02 — Diverse E2E Diagnostics

**Date:** 2026-03-30
**Branch:** autoresearch-open-investigation
**Objective:** Run 3 maximally diverse seed types, diagnose every SQ miss as
COMPILER_MISS or SOLVER_MISS.

## Results summary

| E2E | Seed | Type | Score | Hits/SQs | Correctness | Submitted |
|-----|------|------|-------|----------|-------------|-----------|
| 01 | vaca_muerta | Causal | 0.580 | 2/5 | 1.0 | True (force-submit) |
| 02 | vaca_muerta_predictive | Predictive | 0.548 | 2/5 | 1.0 | True |
| 03 | identifiability_pollution | Epistemological | 0.364 | 1/4 | 1.0 | True |

**Key pattern: correctness = 1.0 everywhere. Coverage is the bottleneck.**

## Fix applied: force-submit

Before this session, 2/3 solvers exhausted all iterations without calling
`submit_claims`. Added force-submit mechanism to `oi_driver.py`: after main
loop, if not submitted, one extra LLM turn with ONLY `submit_claims` available.
Fixed E2E 01 (was score 0, now 0.580).

---

## E2E 01 — Vaca Muerta Causal (0.580)

**World:** "Frac-hit sanding risk in the Kalliste shale corridor" — 13 nodes

### Solver claims (4, via force-submit)
- **C1**: Correlations with sanding risk: pressure_transfer_index (r=0.68),
  historical_interference_burden (r=0.57), peak_frac_pressure (r=0.52),
  pad_spacing (r=-0.68)
- **C2**: OLS multivariate — pad spacing, pressure transfer, historical burden
  significant; geology terms not significant
- **C3**: Mediation — pressure_transfer_index mediates peak_frac_pressure →
  sanding risk (coef drops from 0.00173 to 0.00097 when PTI included)
- **C4**: Unmeasured geomechanical susceptibility — site-level residuals vary
  systematically (±0.23)

### SQ-by-SQ forensics

| SQ | Pattern | Tier | Result | Matched by | Miss type | Diagnosis |
|----|---------|------|--------|------------|-----------|-----------|
| sq1 | causal_effect (pad_spacing→risk, sign) | HIGH | **HIT** 0.65 | C1::3 | — | OK |
| sq2 | mediation (fluid_intensity→risk via pressure_transfer) | HIGH | **MISS** | — | **SOLVER** | Solver investigated mediation for peak_frac_pressure, not child_fluid_intensity. Never explored fluid intensity pathway. |
| sq3 | confounding (pressure→risk, confounder=pad_spacing) | MED | **HIT** 0.32 | C1::2 | — | OK (low sat) |
| sq4 | heterogeneity (pressure effect × stratigraphic_alignment) | MED | **MISS** | — | **SOLVER** | Solver never investigated stratigraphic_alignment as moderator |
| sq5 | effect_ranking (pad_spacing, fluid, pressure) | HIGH | **MISS** | — | **SOLVER** | C1 ranks by correlation but with different variables than SQ asks |

**Verdict: 3 SOLVER MISS, 0 COMPILER MISS.** The solver did good work but
missed the child_fluid_intensity pathway entirely and never looked at
stratigraphic_alignment.

---

## E2E 02 — Vaca Muerta Predictive (0.548)

**World:** "Forecasting frac-interference sanding risk in the Kallista shale" — 12 nodes

### Solver claims (4)
- **C1_spacing**: Pad spacing strongest inverse predictor (r=-0.57), OLS
  significant, +100 units → ~0.03 risk reduction
- **C2_sector_proxy**: basin_sector_risk positive and significant after
  controls, captures underlying susceptibility
- **C3_pressure_not_dominant**: pressure_ratio moderate (r=0.34), not
  significant in multivariate; weaker than spacing/sector
- **C4_context_moderation**: Spacing signal stronger in high-risk sectors
  (-0.64 vs -0.51) and shallow intervals

### SQ-by-SQ forensics

| SQ | Pattern | Tier | Result | Matched by | Miss type | Diagnosis |
|----|---------|------|--------|------------|-----------|-----------|
| sq1 | causal_effect (pressure_ratio→risk, sign) | HIGH | **HIT** 0.65 | C3::0 | — | OK |
| sq2 | effect_ranking (pressure_ratio, spacing, sector_risk) | HIGH | **MISS** | — | **COMPILER** | C3 literally says "pressure_ratio...not significant...weaker than spacing/sector signals". This IS a ranking (spacing > sector > pressure). Compiler didn't extract effect_ranking pattern. |
| sq3 | heterogeneity (sector_risk effect × depth) | HIGH | **MISS** | — | **SOLVER** | C4 investigates spacing×sector and spacing×depth, but NOT sector_risk×depth |
| sq4 | mediation (fluid_intensity→risk via pressure_ratio) | MED | **MISS** | — | **SOLVER** | Solver didn't investigate child_fluid_intensity at all |
| sq5 | obs_association (sector_risk→risk, sign) | MED | **HIT** 1.0 | C2::0 | — | OK |

**Verdict: 2 SOLVER MISS, 1 COMPILER MISS.** The compiler missed an
effect_ranking that's clearly stated in prose. The solver again missed
child_fluid_intensity and the specific sector×depth interaction.

---

## E2E 03 — Identifiability / Epistemological (0.364)

**World:** "Identifiability of refinery-linked particle exposure effects on
childhood wheeze in Port Aurelia" — 13 nodes

### Solver claims (3)
- **C1**: Positive bivariate association proxy→wheeze (slope 0.231, p~2e-27)
- **C2**: After multivariate adjustment, proxy coefficient small and NS
  (0.027, p=0.62) — high sensitivity to covariates
- **C3**: Wind dispersion weakly related to proxy (slope -3.83, p=0.32) but
  strongly related to wheeze (slope -3.99, p=1e-6) — undermines IV validity

### SQ-by-SQ forensics

| SQ | Pattern | Tier | Result | Matched by | Miss type | Diagnosis |
|----|---------|------|--------|------------|-----------|-----------|
| sq1 | causal_effect (proxy→wheeze, sign) | HIGH | **MISS** | — | **COMPILER** | C1 literally states "positively associated...slope ≈0.231". The answer is POSITIVE. But compiler matched C1 to sq2 instead (confounding), leaving sq1 unmatched. |
| sq2 | confounding (emissions confound proxy→wheeze) | HIGH | **HIT** 0.06 | C1::0 | — | Very low satisfaction (0.06). C1 is about bivariate association, not really about confounding. Weak match. |
| sq4 | obs_association (wind→proxy, sign=negative) | MED | **MISS** | — | **COMPILER** | C3 states "slope ≈-3.83" — the sign is literally NEGATIVE. This is the exact answer. Compiler didn't extract it. |
| sq5 | tail_risk (high proxy → elevated wheeze tail) | LOW | **MISS** | — | **SOLVER** | Solver never investigated extreme values or tail risk |

**Verdict: 1 SOLVER MISS, 2 COMPILER MISS.** The compiler failures are
egregious — the claims contain the literal numerical answers but the compiler
couldn't extract them. C1→sq1 (positive sign) and C3→sq4 (negative sign)
are both trivial extractions that failed.

---

## Aggregate diagnosis

### Miss classification across all 14 SQs

| Type | Count | % | Description |
|------|-------|---|-------------|
| HIT | 5 | 36% | Correctly matched and verified |
| SOLVER MISS | 6 | 43% | Solver didn't investigate the topic |
| COMPILER MISS | 3 | 21% | Claim contains the answer but compiler didn't extract |

### Compiler miss patterns (S01 + S02 combined)

| # | Pattern | Example | Frequency |
|---|---------|---------|-----------|
| 1 | **effect_ranking from prose** | "weaker than spacing/sector" → should extract rank order | 2 (S01 + S02) |
| 2 | **sign extraction when claim has literal slope** | "slope ≈-3.83" → should extract negative sign for wind→proxy | 2 (S02) |
| 3 | **claim matched to wrong SQ** | C1 (association) matched to sq2 (confounding) instead of sq1 (sign) | 1 (S02) |

### Solver miss patterns

| # | Pattern | Example | Frequency |
|---|---------|---------|-----------|
| 1 | **Unexplored variable** | child_fluid_intensity not investigated in both vaca cases | 3 |
| 2 | **Wrong interaction tested** | Spacing×depth instead of sector×depth | 2 |
| 3 | **Unexplored analysis type** | Tail risk never attempted | 1 |

---

## Implications

1. **Compiler is the higher-leverage fix.** 3 compiler misses are trivially
   fixable (the answers are literally in the text). Solver misses require
   the solver to be smarter about exploration strategy — harder to fix.

2. **effect_ranking is still broken** (recurring from S01). The compiler
   doesn't know how to extract rankings from prose like "X is weaker than Y".

3. **Sign extraction should be trivial** but fails. When a claim says
   "slope ≈-3.83", extracting a negative sign for an obs_association SQ
   should be mechanical.

4. **Solver ignores some variables entirely.** child_fluid_intensity was
   available in both vaca cases but the solver never explored it. This might
   be a prompt issue (brief doesn't emphasize it) or a solver exploration
   strategy issue.

5. **Force-submit works** — prevents score=0 from non-submission.

## Next steps (S03)

1. **Compiler: sign extraction** — when claim has a numerical slope/coefficient,
   extract the sign automatically without LLM interpretation
2. **Compiler: effect_ranking** — detect comparative language ("stronger than",
   "weaker than", "not significant while X is significant")
3. **Compiler: claim→SQ matching** — improve assignment so claims match the
   most relevant SQ, not just first compatible one
4. **Solver: broader exploration** — investigate whether brief phrasing or
   variable naming affects which variables the solver explores
