# TEMP: Scientific Taxonomy Debate (2026-03-15/16)

> Working note. Este debate alimenta `research/synthesis/eval_types_analysis.md`.
> Se conserva como material de exploracion, no como conclusion final.

## User's taxonomy (7 types + 2 axes)

1. **Descriptive/measurement**: What's there? How much? How distributed?
2. **Explanatory/causal**: What causes what? What's the mechanism?
3. **Predictive**: Can I predict Y from X?
4. **Design/engineering**: Can I build something that works?
5. **Methodological**: Can I invent a better way to do science?
6. **Theoretical**: What general principles explain a family of phenomena?
7. **Synthesis**: What does ALL the evidence say?

Axes: observational vs experimental, exploratory vs confirmatory

## Codex's additions (3 missing types)

1. **Decision/optimization**: What should we do? Which intervention? Resource allocation?
2. **Validation/robustness**: Is this real? Does it survive scrutiny?
3. **Heterogeneity/boundary conditions**: When/where/for whom does this hold?

## BN compatibility assessment (Codex)


| Type                      | BN support               | Currently doing?            |
| ------------------------- | ------------------------ | --------------------------- |
| 1. Descriptive            | STRONG                   | Barely                      |
| 2. Explanatory/causal     | STRONG                   | YES (but too generic)       |
| 3. Predictive             | MODERATE-STRONG          | Partial                     |
| 4. Decision/optimization  | MODERATE                 | Partial (best_intervention) |
| 5. Validation/robustness  | PARTIAL                  | NO                          |
| 6. Heterogeneity/boundary | MODERATE                 | Barely                      |
| 7. Design/engineering     | WEAK                     | NO                          |
| 8. Methodological         | WEAK                     | NO                          |
| 9. Theoretical            | VERY WEAK                | NO                          |
| 10. Synthesis             | WEAK (needs multi-study) | NO                          |


## Which types naturally FORCE investigation?

**Most investigation-forcing** (hard to shortcut):

- Descriptive: must look at data to know patterns
- Validation/robustness: analysis-dependent, not prior-knowable
- Heterogeneity: "why here but not there" is case-specific
- Decision/optimization: context-specific tradeoffs

**Investigation-forcing IF done right**:

- Explanatory/causal: only with competing mechanisms (our key finding)
- Predictive: only if quantitative, not directional

**Least investigation-forcing in BN context**:

- Theoretical, methodological, synthesis, design/engineering

## Key insight from debate

Our current eval types are almost entirely TYPE 2 (explanatory/causal) at a
GENERIC level. That's exactly the type most vulnerable to semantic shortcutting.

The types we're MISSING are the ones that naturally force investigation:

- Descriptive (what patterns do you see?)
- Robustness (does this survive alternative analysis?)
- Heterogeneity (why different outcomes in similar cases?)

## User's process elements taxonomy

### FRAMING

- Question/objective
- Background/context
- Inspiration
- Assumptions + scope

### PROPOSE

- Hypotheses
- Model/mechanism
- Observable predictions

### PLAN/DESIGN

- Research plan
- Experimental design
- Metrics and success criteria
- Data plan

### EXECUTE

- Data collection / experiments
- System building
- Mathematical derivations

### ANALYZE AND VALIDATE

- EDA + cleaning
- Statistical analysis / inference
- Modeling
- Visualization and diagnostics
- Robustness checks
- Reproducibility

### TASK TYPES (what researchers DO)

A) Search info / situate yourself
B) Define the problem operationally
C) Propose explanations/solutions
D) Design how to decide
E) Execute
F) Analyze and close the loop

## Hallazgo empirico: 7-SRC evaluation sin budget (2026-03-16)

Corrimos 7 SRCs de papers reales SIN budget ni research_actions.
El solver solo tiene python_exec + think + submit.

**Patron claro:**

- Descriptive questions (infer_target): FUERZAN analisis de datos.
El solver TIENE que hacer value_counts/crosstabs. Scores GOOD.
- Causal questions (should_condition, adjustment_set): NO fuerzan analisis.
El solver responde desde priors del dominio. A menudo WRONG.
- causal_effect: intermedio — a veces compara grupos (empirico shallow),
a veces adivina desde priors.

**Conclusion confirmada por Codex:**
Si queremos forzar investigacion, las preguntas deben ser DATA-INDEXED
(su respuesta depende de los datos de este episodio). Las preguntas
STRUCTURAL-CAUSAL no fuerzan investigacion porque se responden desde
conocimiento de dominio.

**Implicacion para SREG:**
Separar dos objetivos de benchmark:

1. Data-grounded empirical analysis (descriptivo, estimacion)
2. Causal structure reasoning (condicionar, confounders, mecanismo)

Solo el primero fuerza investigacion naturalmente.

## Open questions for next session

1. For SREG v2, which 3-4 objective types should we prioritize?
2. How do we make ALL eval types data-indexed (not just infer_target)?
3. How do we make robustness tasks?
4. How do we implement heterogeneity tasks?
5. Should we restructure around the PROCESS (framing, proposing, planning,
  executing, analyzing) rather than just final answers?
6. What to do about realistic experiments/actions (future feature)?

