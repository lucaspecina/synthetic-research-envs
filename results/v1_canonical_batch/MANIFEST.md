# v1_canonical_batch — SREG v1 Canonical Baseline

## Que es

Baseline canonico de SREG v1: 12 casos diversos de investigacion
corridos con la config v1 congelada. Es el gate minimo de estabilidad
y reproducibilidad del sistema.

## Provenance

- **Source:** `results/p06_cap_decision/cap15/` (arm cap=15 del
  experimento P06 cap decision, 2026-04-09).
- **Casos frozen:** src.json provienen de `results/p05_canonical_batch/`
  (mismos mundos, problemas, sub-questions).
- **Solo el solver investigation es nuevo** — corrido con la config v1
  final.

## Config v1 congelada

| Parametro | Valor |
|-----------|-------|
| Scoring path | SQ v2 + LLM judge (canonico) |
| Claim cap | 15 |
| Solver model | gpt-5.2-codex |
| Compiler/judge model | gpt-5.4 |
| Max iterations | 20 |
| Temperature | 0.0 |
| Seed | 42 |
| n_mc | 20,000 |

## Gate de reproducibilidad

`rescore --reaggregate` sobre los 12 casos: **delta 0.0000** en todos.

```
  Case                 Original  Rescore    Delta
  --------------------------------------------------
  chemical               0.4462   0.4462  0.0000
  competing_mech         0.5797   0.5797  0.0000
  confounding            0.4080   0.4080  0.0000
  coral_bleach           0.3930   0.3930  0.0000
  heterogeneity          0.4171   0.4171  0.0000
  identifiability        0.2178   0.2178  0.0000
  immunotherapy          0.5000   0.5000  0.0000
  microbiome             0.4617   0.4617  0.0000
  missing_data           0.7358   0.7358  0.0000
  policy_equity          0.6454   0.6454  0.0000
  poverty                0.5422   0.5422  0.0000
  selection_bias         0.7618   0.7618  0.0000
  --------------------------------------------------
  AVERAGE                0.5091   0.5091  0.0000
```

Verificado: 2026-04-09.

## Casos (12)

| Caso | Tipo | Total | Correctness | Wt.Coverage |
|------|------|-------|-------------|-------------|
| selection_bias | selection_bias | 0.762 | 0.857 | 0.889 |
| missing_data | epistemological | 0.736 | 0.861 | 0.854 |
| policy_equity | policy_tradeoff | 0.645 | 0.944 | 0.683 |
| competing_mech | causal_mechanism | 0.580 | 0.783 | 0.740 |
| poverty | causal_simple | 0.542 | 0.694 | 0.781 |
| immunotherapy | heterogeneity | 0.500 | 0.571 | 0.875 |
| microbiome | system_mapping | 0.462 | 0.750 | 0.616 |
| chemical | optimization | 0.446 | 0.621 | 0.718 |
| heterogeneity | heterogeneity | 0.417 | 0.812 | 0.513 |
| confounding | confounding | 0.408 | 0.653 | 0.625 |
| coral_bleach | descriptive | 0.393 | 0.625 | 0.629 |
| identifiability | epistemological | 0.218 | 0.400 | 0.545 |

**Average: 0.509** (N=12, 0 errores).
