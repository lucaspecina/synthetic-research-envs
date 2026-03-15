# SREG v2 Design — From Causal Benchmark to Research Environment

> Result of deep analysis session (2026-03-15): 6 rounds of debate with Codex,
> analysis of real scientific papers, examination of 5 generated SRCs, and
> critical assessment of what makes real research different from benchmarks.

## The Problem

SREG v1 generates "causal benchmarks with realistic wrappers" — not research
environments. Evidence:
- Agent uses 0 research_actions in 4/5 cases (just analyzes the CSV)
- 80-row clean datasets don't look like real data
- "Spend 1 budget point to reveal variable X" is a game mechanic, not research
- "Set algal_competition to low" is not a real experiment
- Fixed pre-formulated questions say "benchmark", not "investigation"

## The Diagnosis (from debate with Codex)

**What real research has that SREG v1 doesn't:**
1. Multiple data sources with different quality, resolution, provenance
2. Messy, noisy, incomplete data with realistic problems
3. Actions that commission studies, run experiments, request data — not reveal nodes
4. Evidence that's produced, not merely accessed
5. Underspecified problems where the researcher chooses what to investigate
6. Claims with uncertainty, not exact answer submission

**What SREG v1 does RIGHT that we keep:**
- BN as exact ground truth (exact reward signals = differentiator)
- 9 eval types that map to real research questions
- Dataset generation from the BN
- Agent solver with python_exec for real analysis
- Orchestrator that designs cases from seeds/papers

## The 5 Changes (incremental, not redesign)

### Change 1: Multi-Artifact Datasets

Instead of one CSV with all columns, the DataSampler produces 2-3 datasets
with different characteristics, mimicking how real data comes from different
sources.

**For a coral reef study:**
- `satellite_monitoring.csv` — 1000 rows, few columns (SST, lat, reef_id)
- `field_survey.csv` — 150 rows, more columns (species, bleaching, fish biomass)
- `pilot_genetics.csv` — 20 rows, detailed (symbiont type, thermal tolerance marker)

**For an epidemiology study:**
- `national_registry.csv` — 5000 rows (birth date, diagnosis codes, municipality)
- `cohort_survey.csv` — 800 rows (exposures, home environment, questionnaire data)
- `biomarker_subsample.csv` — 50 rows (blood markers, genetic markers)

Each dataset has metadata: source, time period, known limitations.

**Implementation:** Change DataSampler to produce multiple DataAssets with
different subsets of columns and different row counts. The BN still generates
all values; the observation layer selects and degrades them.

### Change 2: Richer, Messier Data

Instead of exact BN samples, add realistic data problems:
- **Measurement noise** — values jittered from true BN state
- **Realistic missingness** — not random; correlated with variables
  (sicker patients drop out more, poorer families don't respond to surveys)
- **More rows** — 500-5000 instead of 80
- **Column metadata** — "self-reported", "instrument: pH meter model X",
  "satellite resolution: 1km"

**Implementation:** Add noise/missingness models to DataSampler. The true
BN value is sampled, then degraded through an observation model before
being included in the dataset.

### Change 3: Realistic Action Semantics

Instead of "Measure variable X (cost: 1)", actions describe what a researcher
actually does:

**Bad (current):**
- "Measure thermal_stress_duration (cost: 1)"
- "Experiment: set algal_competition to low"

**Good (proposed):**
- "Commission underwater survey at N additional sites (cost: 3)"
  → Returns a new dataset with bleaching, species, depth at surveyed sites
- "Request genetic analysis of K coral samples (cost: 5)"
  → Returns a small dataset with genetic thermal tolerance markers
- "Deploy algae removal experiment at M sites for 6 months (cost: 8)"
  → Returns before/after comparison with noise, partial success, site effects

Actions are parameterized and return ARTIFACTS (datasets/reports), not values.

**Implementation:** Redesign ProblemBuilder action generation and EpisodeRunner
action handling. Actions return DataAssets instead of single observations.

### Change 4: Structured-Claim Evaluation

Instead of "submit the exact posterior distribution", the agent submits
structured claims that are scored against BN truth:

**Current submission:**
```json
{"distribution": {"survived": 0.85, "deceased": 0.15}}
```

**Proposed submission:**
```json
{
  "question_addressed": "Does prenatal smoking increase asthma risk?",
  "claim_type": "associational",
  "effect_direction": "increase",
  "effect_strength": "moderate",
  "confidence": 0.75,
  "key_caveat": "Cannot rule out residual confounding by SES",
  "evidence_basis": "observational cohort, adjusted for 5 covariates"
}
```

**Scoring:**
- truth_score: direction correct? strength roughly right?
- calibration_score: confidence matches actual correctness?
- overclaim_penalty: claimed "causal" from observational data?
- design_penalty: high confidence without adequate evidence?

**Implementation:** New claim submission format in agent tools, new scoring
in VerifierTool. Keep existing eval types as internal scoring targets.

### Change 5: Underspecified Brief (not fixed questions)

Instead of "Answer these 5 causal questions", give the agent a broad brief:

**Current:**
```
Question 1 (infer_target): What is P(recovery | evidence)?
Question 2 (causal_effect): If we reduce thermal stress, what happens?
...
```

**Proposed:**
```
Coral reef health is declining across monitored sites in the Aurelian
chain. Management needs evidence-based recommendations for prioritizing
conservation resources. Investigate the most plausible drivers of
bleaching and recovery, and provide actionable conclusions.
```

The agent explores, analyzes, and submits up to K structured claims.
Each claim is scored against BN truth. The agent decides what questions
to pursue.

**Implementation:** Change briefing format in ProblemBuilder. Keep internal
eval type targets for scoring, but don't expose them to the agent.

## Investigation Type Taxonomy (backend only, not agent-facing)

The orchestrator uses this internally to design appropriate environments:

| Type | Actions Available | Cannot Do | Example |
|------|------------------|-----------|---------|
| Observational cohort | Request data, survey, measure | Experiment on humans | Asthma risk factors |
| Case-control | Select cases/controls, measure | Establish temporality | Rare disease causes |
| Field survey | Choose sites, sample, measure | Control conditions | Coral reef assessment |
| Lab experiment | Design factors, fabricate, test | Guarantee field validity | Coating development |
| Natural experiment | Identify quasi-random variation | Randomize | Policy evaluation |
| Clinical trial | Randomize, dose, monitor | Unethical interventions | Drug efficacy |

The agent never sees this classification. It experiences the constraints.

## Scientific Task Types (for scoring)

| Task | What Agent Should Do | How to Score |
|------|---------------------|-------------|
| Identify risk factors | Find which variables drive outcome | Direction + importance ranking |
| Estimate treatment effect | Quantify do(X) on Y | Effect size + design validity |
| Predict outcome | Build predictive model | Discrimination + calibration |
| Discover mechanism | Identify causal pathway | Pathway correctness |
| Optimize | Find best intervention | Optimality + robustness |
| Validate hypothesis | Test a specific claim | Correct accept/reject + power |

## Rollout Order

1. **DataSampler** — multi-artifact + richer noise/missingness (foundation)
2. **ProblemBuilder** — pre-existing artifacts + realistic actions + underspecified brief
3. **VerifierTool** — structured claims + calibration + overclaim penalty

## What We're NOT Doing (yet)

- Big formal taxonomy exposed at runtime
- Mandatory planning actions
- Complex institutional simulation (ethics boards, funding)
- Freeform natural-language-only scoring
- Full workflow/state-machine redesign
- Open-ended question discovery beyond choosing from implicit options

## Key Design Rules

1. **No universal table** — every SRC has 2-4 artifacts, not one CSV
2. **No non-physical interventions** — actions must be things a researcher could do
3. **Some data pre-exists** — satellite, registries, historical data start available
4. **Actions produce artifacts, not truth** — datasets, reports, failed attempts
5. **Start with underspecified brief** — not fixed questions
6. **BN stays as ground truth** — exact reward, no LLM judge
