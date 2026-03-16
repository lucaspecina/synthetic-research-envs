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

**What SREG v1 does RIGHT that we keep:**
- BN as exact ground truth (exact reward signals = differentiator)
- 9 eval types that map to real research questions
- Dataset generation from the BN
- Agent solver with python_exec for real analysis
- Orchestrator that designs cases from seeds/papers

---

## 10 Patterns That Make Real Research Real

> From analysis of 7 real papers (epi, ecology, clinical, education,
> materials, economics) + 7 rounds of debate with Codex.
> Full paper analysis in `research/real_investigations_analysis.md`.

### From real papers (7 studies)

**1. Data assembly is half the work.**
Each real study combines 3-8 heterogeneous data sources. Registries +
surveys + satellite data. Different granularity, coverage, problems.
A single clean CSV of 80 rows is unrealistic.
*Example: Danish asthma study combines 7 national registries, 3-scale
exposure models, and 2 cohorts with their own questionnaires.*

**2. Identification strategy > statistical method.**
The hard part is not "which regression" but "which comparison isolates
the causal effect." Double negative controls, age-at-move variation,
instrumental variables — each is a creative causal argument, not a formula.
*An agent that only runs regressions is not doing research.*

**3. Sensitivity analysis is multidimensional.**
No study reports ONE answer. They vary model specification, confounder
sets, sample definitions, aggregation levels. The PATTERN across
specifications is what builds confidence.
*SREG should evaluate whether the agent CHECKS its answer, not just
whether the answer is correct.*

**4. Constraints shape everything.**
You can't randomize humans to pollution, heat a coral reef, or assign
families to neighborhoods. Each investigation is DEFINED by what it
CANNOT do. Constraints determine investigation type.
*An SRC should start from constraints, not from variables.*

**5. The answer depends on framing.**
Same data, different valid conclusions: school funding appears harmful
(no controls), neutral (with SES), or beneficial for low achievers
(quantile regression). Dexamethasone helps ventilated patients but may
harm mild cases.
*There isn't ONE correct answer — there are defensible answers under
different assumptions.*

**6. Sequential decision-making.**
Research unfolds as a series of decisions: initial results suggest
something → measure in more detail → experiment fails → redesign →
subgroup shows opposite effect → investigate why.
*Not "receive data, analyze, answer." An iterative loop.*

### From debate with Codex (7 rounds)

**7. Researchers PRODUCE evidence, not reveal it.**
In a benchmark, evidence exists and is "discovered." In real research,
the researcher CREATES evidence: designs a study, recruits participants,
fabricates samples, deploys instruments.
*Actions should be "launch a data collection program with real
constraints," not "reveal a hidden node."*

**8. Data comes with systematic problems.**
Not "clean + some noise." Real data has: MNAR missingness (sicker
patients drop out more), differential measurement error (self-report
underestimates smoking), selection bias (only survivors are observed).
*These are threats to validity, not random noise.*

**9. Claims have type and weight.**
A researcher doesn't say "the answer is 0.34." They say: "We found a
moderate association (OR 1.45, 95%CI 1.12-1.88). The evidence suggests
a causal effect but we cannot rule out residual confounding."
*A claim has type, strength, confidence, caveats, limitations.*

**10. The problem is not pre-formulated.**
A benchmark says "answer these 5 questions." A researcher starts with:
"Reefs are dying — why?" and discovers which questions matter through
exploration. Choosing WHAT to ask is part of the scientific work.

### SREG v1 vs v2 on each pattern

| Pattern | SREG v1 | SREG v2 (proposed) |
|---------|---------|-------------------|
| 1. Multi-source data | 1 CSV, 80 rows | 2-3 artifacts, 500-5000 rows |
| 2. Identification | Not evaluated | Evaluate analytic choices |
| 3. Sensitivity | Not required | Reward robustness checking |
| 4. Constraints | Generic budget | Domain-specific constraints |
| 5. Framing | 1 correct answer | Multiple defensible answers |
| 6. Sequential | Atomic actions | Each result informs next step |
| 7. Produce evidence | Reveal variables | Commission studies/experiments |
| 8. Data problems | Clean sampling | Noise, MNAR, selection bias |
| 9. Typed claims | Exact distribution | Direction + strength + confidence |
| 10. Open problem | 5 fixed questions | General brief + free claims |

### Papers analyzed

| Domain | Paper | Investigation Type |
|--------|-------|--------------------|
| Epidemiology | Pedersen et al. (asthma + pollution, 1M subjects) | Observational cohort |
| Ecology | Hughes et al. (coral bleaching, GBR) | Field survey + satellite |
| Clinical | RECOVERY trial (dexamethasone, COVID) | Multi-center RCT |
| Education | Jackson et al. (school funding) | Quasi-experimental |
| Materials | High-entropy alloys (BO-guided) | Lab experimental |
| Economics | Card & Krueger (minimum wage) | Natural experiment |
| Ecology | Biodiversity-productivity | Causal inference observational |

---

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

---

## Open Design Questions (for further analysis)

### HALLAZGO CRITICO: el solver shortcuttea con conocimiento preentrenado

> Descubierto analizando la trayectoria real del caso coral reef (2026-03-15).
> El solver hizo UNA llamada a python_exec (df.head() + value_counts), pensó
> UNA vez, y respondió las 5 preguntas desde su conocimiento de ecología de
> arrecifes. NO analizó los datos. NO usó los 3 datasets. NO investigó.
>
> Esto es más fundamental que las acciones o el formato de datos. Si el modelo
> puede responder bien desde su pretraining, SREG no está enseñando investigación.
> Está testeando recall de dominio.
>
> **Consecuencia directa:** los nombres genéricos para training ya no son
> opcionales — son NECESARIOS para evitar que el modelo haga shortcut con
> conocimiento previo. "herbivore_fish_biomass" le dice al modelo qué esperar.
> "biotic_factor_B" lo fuerza a analizar los datos.

**El problema real no es la interfaz del ambiente. Es que el ambiente es
shortcutteable por priors semánticos del modelo preentrenado.**

**Analisis profundo (debate Claude + Codex, round 10):**

El shortcutting NO es solo un problema de nombres. Es un **mismatch de
objetivos**: si la pregunta se puede responder desde priors, entonces
NO investigar es la estrategia OPTIMA. El solver no esta "fallando"
— esta siendo racional bajo los incentivos actuales.

La raiz es triple:
1. Las preguntas son genérico-dominiales, no episodio-específicas
   ("does thermal stress affect recovery?" vs "which variable is the
   strongest driver IN THIS PARTICULAR DATASET?")
2. La narrativa activa priors semánticos que hacen la investigación
   innecesaria (pero NO es suficiente solo sacar los nombres reales
   — también hay que hacer que los priors sean no-confiables)
3. El scoring recompensa la respuesta correcta, no el USO de evidencia

**Root cause (debate Claude + Codex, round 11-12):**

La diferencia entre preguntas reales y las nuestras:
- Nuestras eval types son GENERICAS CAUSALES: "does X affect Y?"
  → respondibles desde conocimiento de dominio
- Las preguntas de papers reales son EMPIRICAS ANALITICAS:
  "what does THIS analysis of THIS dataset show?"
  → requieren analizar los datos porque la respuesta depende del dataset

Un paper real pregunta:
- "Is the HR > 1.0 after adjusting for 15 covariates IN THIS cohort?"
- "Does the effect survive 5 alternative specifications?"
- "Which predictor dominates in a two-pollutant model?"

Nuestros eval types preguntan:
- "Does thermal stress affect recovery?" (causal_effect)
- "What variables should you control for?" (adjustment_set)

Las preguntas de papers son ANALISIS-CONDICIONADAS y DATASET-INDEXADAS.
Las nuestras son DOMINIO-GENERICAS y GRAFO-INDEXADAS.

Por eso las reales requieren investigacion y las nuestras no.

**INSIGHT FINAL (usuario + Claude + Codex, rounds 11-13):**

No es genericidad vs especificidad. No es nombres reales vs genéricos.
Es GRANULARIDAD: nuestras preguntas piden invariantes del TIPO de mundo
(que los priors ya saben), en vez de cantidades del INSTANCE del mundo
(que solo los datos de este episodio pueden revelar).

El BN ya CONTIENE respuestas episodio-específicas (las CPDs definen
magnitudes exactas). Solo que no PREGUNTAMOS por ellas.

Tres niveles de evaluación:
1. STRUCTURAL (grafo): "qué es confounder?" → no fuerza investigación
2. ESTIMAND (cantidad): "cuál es el efecto ajustado?" → fuerza análisis
3. SPECIFICATION-SENSITIVITY: "cambia el efecto si ajusto diferente?"
   → más cercano a lo que papers reales hacen

Nuestros 9 eval types están en nivel 1 (structural).
Papers reales viven en niveles 2 y 3.

El cambio necesario: pasar de evaluar CONOCIMIENTO CAUSAL ESTRUCTURAL
a evaluar RESULTADOS DE ANALISIS SOBRE DATOS ESPECIFICOS.

Ejemplos de mejores preguntas:
- "In this dataset, which variable has the strongest adjusted association?"
- "Run two models (with/without variable_Z). Does the main effect change?"
- "Is the relationship linear or is there a threshold effect?"
- "The background data shows pattern X. Does the field survey confirm it?"
- "Which of these two causal graphs better explains the observed correlations?"

**Fix combinado (no solo uno de estos):**
1. Preguntas episodio-específicas: "en ESTE dataset, cuál variable tiene
   el efecto más fuerte?" no "does X affect Y in general?"
2. Priors no confiables: a veces el mundo coincide con la expectativa
   del dominio, a veces NO. El agente no puede saber cuál sin analizar.
   NO invertir siempre (eso crea un nuevo shortcut: "lo obvio esta mal").
   Hacer que la alineacion sea VARIABLE e impredecible.
3. Reward por evidencia: no solo correctness, también calidad del proceso.
   Calibración, uso de datos, robustez.
4. Preguntas discriminativas: "cuál de estos dos DAGs explica mejor los
   datos?" "qué edge esperado esta AUSENTE en este mundo?" "estima el
   signo Y la magnitud relativa de X->Y en ESTE episodio"

**Nombres genéricos vs realistas (decision refinada):**
- Nombres genéricos solos NO resuelven el problema
  (el modelo puede shortcuttear con heurísticas estructurales)
- Nombres realistas solos son PEORES (activan pretraining directo)
- La solución real es EPISODIO-DEPENDENCIA + PRIORS VARIABLES
- Nombres genéricos son útiles como control experimental, no como fix

### Generic vs Realistic Variable Names — CRITICAL for training

**The problem:** if we train a model on SRCs with realistic names
(`maternal_smoking`, `water_temperature`) but INVENTED causal relationships,
the model may learn FALSE factual associations about the real world.

Example: an SRC where `smoking -> birth_weight` is POSITIVE (more smoking =
higher weight) for training purposes. A model trained on this might incorrectly
"learn" that smoking helps birth weight.

**Proposed solution: TWO modes**

| Mode | Names | Use for |
|------|-------|---------|
| **Training mode** | Typed-generic: `exposure_1`, `outcome_primary`, `site_covariate` | RL training, curriculum, methodology learning |
| **Evaluation mode** | Realistic: `maternal_smoking`, `birth_weight` | Benchmarking, paper-seeded cases, human review |

Training mode teaches METHODOLOGY (how to investigate, design studies,
handle confounders). Evaluation mode tests whether the skill transfers
to realistic scientific language.

**Not fully anonymous** (`var_17` is too sterile). Use role-typed labels:
`prenatal_exposure_A`, `environmental_stressor_1`, `lab_marker_2`.

**Codex assessment (round 8):** "Do NOT use realistic names with arbitrary
synthetic truths as your main RL training corpus. That is the wrong tradeoff.
You may accidentally train a model that is good at SREG and worse at science."

### Continuous Variables + Other Model Types

Current SREG only has discrete variables (`low/medium/high`) in Bayesian
networks. Real science has continuous measurements, time series, ODEs, etc.

**Assessment:** important for realism but lower priority than fixing the
research interface (data, actions, evaluation). A continuous-variable system
with the same toy action loop would still feel like a toy.

**Plan:** v2.5 or v3 concern. Short-term: allow limited continuous extension
(linear-Gaussian nodes) if cheap. Don't make "support arbitrary model families"
the next milestone.

### Task Structure: Primary + Secondary with Rubrics

Real investigations have:
- A primary research question (the main finding)
- Secondary questions (validation, robustness, mechanism)
- Process quality (did the researcher follow good practices?)

**Idea:** score not just the final answer but the PROCESS:
- Did the agent explore the data before claiming?
- Did it check for confounders?
- Did it run sensitivity analyses?
- Did it qualify its claims appropriately?

This could use rubrics (structured checklists) scored against the
agent's trajectory, not just the final submission.

**Status:** needs further design. Related to Change 4 (structured claims)
but goes beyond it into process evaluation.
