# Suite 2 Claim Compiler Audits (Flow A) — pre-merge package

**Fecha**: 2026-04-18
**Scope**: Flow A (claim compiler) sobre los 55 gold targets del baseline v2.
**Input**: `research/synthesis/compiler_baseline_full_dump_v2.json`
**Outputs**:
- `claim_compiler_coherence_audit.json` (audit semantico LLM-as-judge)
- `spec_kind_coverage_audit.json` (histogramas estructurales)

Tres audits complementarios al audit estructural de Flow B
(`suite2_sq_dag_coherence_audit.md`). Juntos forman el paquete pre-merge
que cierra la evaluacion de Suite 2.

## TL;DR

- **Audit 1 — Coherencia semantica Flow A**: 24/55 coherent (**44%**), 20
  wrong_claim (36%). Flow A es sustancialmente mas sano que Flow B
  (44% vs 24% coherent), pero sigue siendo mala traduccion en 1 de cada 3
  claims.
- **Atribucion critica**: 9/20 wrong_claim son puros bugs del compiler; 9/20
  heredan ruido del gold target (gold tambien es wrong_claim/narrow/incomplete).
  **Solo 45% del wrong_claim del compiler es puramente culpa del compiler.**
- **Audit 2 — Cobertura de spec-kinds**: el compiler nunca produce
  `piecewise_fit`, `changepoint_exists`, `gap_material` (gold los usa).
  Usa `correlation`+`partial_correlation` 23 veces donde gold usa
  `intervene+mean`. **Mode collapse hacia mediciones observacionales.**
- **Audit 3 — Patrones de exito**: los 7 `full_pass` tienen firma comun:
  67% son `identifiability_check`, 71% usan `baseline` arm, **ninguno usa
  `adjust` arm, ninguno usa `mean`**. El compiler solo funciona en claims
  de identificabilidad o distribucional.

**Decision pre-merge**: los tres audits estan documentados y listos.
Los hallazgos de Audit 2 y 3 dan input directo al epic #36 (compiler-fix).

---

## Audit 1 — Coherencia semantica Flow A

**Script**: `scripts/audit_claim_compiler_coherence.py`
**Metodo**: LLM judge (gpt-5.4) con rubric 7 categorias (coherent, narrow,
incomplete, wrong_claim, orphan_vars, contradictory, abstain). 2-pass auto
reaudit para low-confidence o severe verdicts. Mismo rubric que el audit
semantico de Flow B.
**Control**: `--include-gold` audita los `gold_specs` como sanity check —
si gold sale 100% coherent, el rubric no tiene drift.
**Duracion**: 66.6s (workers=6).

### Resultados agregados

| Verdict         | Compiler specs | Gold specs (control) |
|-----------------|---------------:|---------------------:|
| coherent        |  24 (44%)     | 33 (66%)             |
| wrong_claim     |  20 (36%)     |  9 (18%)             |
| orphan_vars     |   4 ( 7%)     |  0                   |
| abstain         |   4 ( 7%)     |  1                   |
| narrow          |   1 ( 2%)     |  5                   |
| incomplete      |   1 ( 2%)     |  2                   |
| contradictory   |   1 ( 2%)     |  0                   |
| **Total**       | **55**         | **50**               |

**Insight critico: gold tambien tiene 18% wrong_claim.** No es drift del
rubric — los gold wrong_claim son claims con magnitudes cuantitativas
("approximately 0.7", "approximately 0.5") donde el gold spec solo tests
direccion, no magnitud. El rubric correctamente identifica esa
sub-especificacion.

### Atribucion (cross-tab compiler x gold)

| compiler        | gold            |  n |
|-----------------|-----------------|---:|
| coherent        | coherent        | 19 |
| wrong_claim     | coherent        | **9** |
| wrong_claim     | wrong_claim     |  7 |
| orphan_vars     | coherent        |  3 |
| abstain         | coherent        |  2 |
| coherent        | narrow          |  2 |
| coherent        | incomplete      |  1 |
| coherent        | wrong_claim     |  1 |
| (otros)         | ...             | 11 |

- **Puros bugs del compiler** (gold=coherent, compiler=wrong_claim): **9/20 = 45%**
- **Compiler hereda ruido del gold** (gold ya es wrong/narrow/incomplete): 9/20 = 45%
- **Compiler mejor que gold** (compiler=coherent, gold=defectuoso): **4 casos** (notable)

La narrativa "31% pass rate por culpa del compiler" es incorrecta — parte
del gap es estructural en los gold targets. **Mejora del gold** es un eje
independiente de trabajo.

### Por mundo

| World                             | coherent | total | %   |
|-----------------------------------|---------:|------:|----:|
| w3_environmental_health           |       8 |   14 | 57% |
| w2_observational_epidemiology     |       7 |   16 | 44% |
| w1_comparative_effectiveness      |       9 |   25 | 36% |

W1 (clinical, mediation-heavy) tiene la peor coherencia — consistente con
que los claims de mediacion y heterogeneidad son los mas duros de compilar.

### Por dificultad

| Difficulty | coherent | total | %   |
|------------|---------:|------:|----:|
| easy       |       7 |   14 | 50% |
| medium     |      11 |   21 | 52% |
| hard       |       6 |   20 | **30%** |

Drop brusco en `hard`: la coherencia semantica colapsa en claims complejos
(mediacion, identificabilidad negativa, trade-offs multi-outcome).

### Por baseline-category

| Category          | coherent | wrong_claim | total |
|-------------------|---------:|------------:|------:|
| verdict_wrong     |        3 |    **13**   |    19 |
| real_struct_err   |       10 |       2     |    13 |
| adjust_swap       |        5 |       3     |    10 |
| full_pass         |        5 |       0     |     7 |
| stage1_fail       |        1 |       2     |     6 |

**Insight**: el `verdict_wrong` (19 cases) tiene 13/19 = **68% wrong_claim
semantico**. La causa raiz de los verdict errors no es numerica, es
traduccion semantica. Esto refuerza que fix del compiler es lane prioritario
para el epic #36.

### Comparacion Flow A vs Flow B

| Metrica         | Flow A (claim) | Flow B (SQ) |
|-----------------|---------------:|------------:|
| coherent        |  24/55 (44%)  | 13/55 (24%) |
| wrong_claim     |  20 (36%)     | 26 (47%)    |
| orphan_vars     |   4           |  7          |

Flow A es ~1.8x mas sano que Flow B. Dos posibles razones:
1. **Text complexity**: los claims son sentencias cortas (1 oracion); los
   SQ text son multi-parte con mas ambigüedad.
2. **Scope**: Flow A apunta a una verdad puntual ("X causes Y"); Flow B
   cubre una pregunta amplia ("como se relaciona X con Y considerando Z").

Las tres categorias de violaciones mas comunes en ambos flows:
- **explanation_to_identifiability** (Flow B) / direction-to-identifiability (Flow A)
- **causal_to_correlation**
- **mediation_collapse**

Son los mismos recipes faltantes — ambos flows comparten el mismo prompt
base, y los mismos gaps semanticos se manifiestan a los dos niveles.

---

## Audit 2 — Cobertura de spec-kinds

**Script**: `scripts/audit_spec_kind_coverage.py`
**Metodo**: sin LLM. Histogramas de `arm_kind`, `measurement_kind`,
`comparison_kind`, `assertion_kind`, `n_arms_per_spec`, `specs_per_entry`
sobre los 84 compiler_specs y 54 gold_specs. Joint distributions
(measurement x assertion, arm_kind x measurement). Deteccion de mode
collapse via set-diff.

### Distribuciones principales

**Arm kind (compiler vs gold)**:

| arm_kind    | compiler | %   | gold | %   |
|-------------|---------:|----:|-----:|----:|
| adjust      |       86 | 59% |    0 |  0% |
| intervene   |       23 | 16% |   94 | 82% |
| baseline    |       27 | 19% |   12 | 10% |
| condition   |        9 |  6% |    0 |  0% |
| observe     |        0 |  0% |    6 |  5% |
| sweep       |        0 |  0% |    3 |  3% |

- **Gold nunca usa `adjust`**: usa `intervene` y deja que el verificador
  auto-calcule el backdoor via d-separacion.
- **Compiler casi nunca usa `intervene`**: prefiere `adjust` (problematico
  pre-#45) o `condition`.
- **Compiler nunca usa `observe` ni `sweep`**: son kinds que gold usa para
  patrones especificos (threshold detection, distributional analysis) que
  el compiler no reconoce.

**Measurement kind (compiler vs gold)**:

| measurement_kind       | compiler | %   | gold | %   |
|------------------------|---------:|----:|-----:|----:|
| mean                   |       50 | 60% |   38 | 70% |
| correlation            |       13 | 15% |    0 |  0% |
| partial_correlation    |       10 | 12% |    5 |  9% |
| identifiability_check  |        7 |  8% |    7 | 13% |
| variance               |        2 |  2% |    2 |  4% |
| tail_prob              |        2 |  2% |    2 |  4% |

- **Gold nunca usa `correlation`**: correlacion cruda no es suficiente para
  verificar claims causales. Compiler la usa 13 veces = **defecto puro**.
- `partial_correlation`: compiler 2x mas que gold — fallback observacional.

**Assertion kind (compiler vs gold)**:

| assertion_kind          | compiler | %   | gold | %   |
|-------------------------|---------:|----:|-----:|----:|
| positive                |       26 | 31% |   29 | 54% |
| distinguishable         |       15 | 18% |    0 |  0% |
| near_zero               |       10 | 12% |    3 |  6% |
| greater_than            |        8 | 10% |    0 |  0% |
| not_distinguishable     |        6 |  7% |    0 |  0% |
| less_than               |        5 |  6% |    1 |  2% |
| negative                |        5 |  6% |    7 | 13% |
| identifiable            |        4 |  5% |    2 |  4% |
| not_identifiable        |        3 |  4% |    5 |  9% |
| rank_order              |        1 |  1% |    0 |  0% |
| sign_flip               |        1 |  1% |    0 |  0% |
| **changepoint_exists**  |        0 |  0% |    3 |  6% |
| **gap_material**        |        0 |  0% |    4 |  7% |

- **Compiler nunca produce `changepoint_exists` ni `gap_material`**. Gold
  las usa para W3 threshold effects y W1 multi-outcome trade-offs. Sin
  estos kinds, el compiler no puede compilar claims como "hay un
  changepoint en Temp=0" o "la magnitud del trade-off es material".
- **Compiler produce `distinguishable` 15 veces donde gold nunca la usa**:
  es su fallback cuando no sabe si el claim pide direccion o distinguibilidad.
  Genera wrong_claim porque claims como "X causes Y" piden `positive`, no
  `distinguishable`.
- `greater_than`/`less_than`/`not_distinguishable` son otros fallbacks
  que gold raramente usa — sintoma de que el compiler evita committear
  a una aserccion fuerte cuando no esta seguro.

### Comparison kind

| comparison_kind  | compiler | gold |
|------------------|---------:|-----:|
| difference       |       54 |   28 |
| identity         |       27 |   12 |
| contrast_diff    |        2 |   11 |
| **piecewise_fit**|        0 |    3 |
| ranking          |        1 |    0 |

- **Compiler nunca produce `piecewise_fit`**: necesario para threshold
  effects (W3). Se compila como `difference` con assertion=positive —
  falso positivo cuando el efecto es piecewise.

### Mode collapse sintesis

Kinds que **gold usa y compiler nunca produce** (gaps del compiler):
- `arm_kind`: `observe`, `sweep`
- `comparison_kind`: `piecewise_fit`
- `assertion_kind`: `changepoint_exists`, `gap_material`

Kinds que **compiler produce y gold nunca usa** (fallbacks espurios):
- `arm_kind`: `adjust` (86x!), `condition`
- `measurement_kind`: `correlation`
- `assertion_kind`: `distinguishable`, `greater_than`, `not_distinguishable`, `rank_order`, `sign_flip`

**Interpretacion**: el compiler tiene un vocabulario estrecho de patrones
causales y un vocabulario ancho de fallbacks observacionales / debiles.
Cuando no puede traducir un claim a `intervene+mean+positive` (su "happy
path"), se degrada a `adjust+partial_correlation+distinguishable` en vez
de abstener.

---

## Audit 3 — Patrones de exito (7 full_pass)

**Metodo**: inline Python sobre baseline + coherence audit. Features
extraidas: world, difficulty, n_specs, n_arms, arm_kinds, measurement_kind,
assertion_kind, claim length.

### Los 7 full_pass casos

| fact_id       | world | diff    | coh verdict | measurement | arm_kinds | claim |
|---------------|-------|---------|-------------|-------------|-----------|-------|
| SQ_F07_s0     | W1    | easy    | abstain     | - (n_cs=0)  | -         | What is the optimal treatment dose? |
| W1_F09_s0     | W1    | medium  | coherent    | variance    | intervene×2 | Treated patients show more variable outcomes |
| W2_F06_s0     | W2    | medium  | coherent    | partial_correlation | baseline | After adjusting for confounder, exposure negatively assoc with disease |
| W2_F09_s0     | W2    | easy    | coherent    | identifiability_check | baseline | Can we estimate the causal effect of exposure on disease? |
| W2_F09_s1     | W2    | hard    | orphan_vars | identifiability_check | baseline | Is the causal effect identifiable from observational data? |
| W3_F05_s1     | W3    | medium  | coherent    | identifiability_check | baseline | Causal effect of P on H cannot be determined — unmeasured confounder |
| W3_F05_s2     | W3    | hard    | coherent    | identifiability_check | baseline | No set of measured variables is sufficient to block backdoor |

### Firma del exito

| Feature                       | full_pass (n=7) | non-full_pass (n=48) |
|-------------------------------|----------------:|---------------------:|
| `identifiability_check` meas. | **67%** (4/6)   | 4% (3/78)            |
| `baseline` arm kind           | **71%** (5/7)   | 16% (22/138)         |
| `adjust` arm kind             | **0%**          | 62% (86/138)         |
| `mean` measurement            | **0%**          | 64% (50/78)          |
| n_specs = 1                   | 100% (7/7)      | 47% (23/48)          |
| median claim length           | 83 chars        | 78 chars             |

**El compiler solo tiene "happy path" para tres tipos de claim**:
1. **Identificabilidad** (4/7): "¿es identificable?", "¿existe backdoor set
   suficiente?". Produce un solo spec con `identifiability_check` +
   `baseline` arm. No requiere aritmetica causal.
2. **Distribucional** (1/7, W1_F09 variance): "¿es mas variable?". Produce
   `variance` sobre dos arms de intervene.
3. **Adjust-by-design** (1/7, W2_F06): "despues de ajustar por C, X es
   negativa con D". Aqui la especificacion es directamente `partial_correlation(X,D|C)`.

**TODOS los claims de direccion/magnitud de efecto causal fallan.** El
compiler no puede construir `intervene+mean+positive/negative` bien para
esos casos — usa `adjust+partial_correlation+distinguishable`.

### Implicaciones para #36 compiler-fix

Los 7 full_pass son **proof-of-concept** de que el compiler puede producir
specs correctos bajo condiciones estrechas. El trabajo de fix debe:
1. **Extender el happy path** a `intervene+mean+positive/negative` — hoy
   el compiler prefiere `adjust` (con bug de adjust_set=[]).
2. **Agregar recipes faltantes**:
   - Threshold/changepoint -> `piecewise_fit` comparison + `changepoint_exists`
   - Multi-outcome trade-off -> `gap_material` assertion
   - Mediation decomposition -> specs para direct vs indirect, no 3
     specs separados
3. **Restringir el uso de `correlation`**: debe requerir justificacion
   explicita (el claim mismo pide asociacion, no causalidad).
4. **Restringir `distinguishable`**: solo valido cuando el claim es
   explicitamente "are they different?" — no fallback.

---

## Deliverables del paquete pre-merge

- [x] **Audit 1 — Semantico Flow A**: `scripts/audit_claim_compiler_coherence.py` + `claim_compiler_coherence_audit.json`
- [x] **Audit 2 — Spec-kind coverage**: `scripts/audit_spec_kind_coverage.py` + `spec_kind_coverage_audit.json`
- [x] **Audit 3 — Success patterns**: inline analisis + firma documentada en este doc
- [x] Sintesis (este doc)
- [x] Cross-referencia con audit Flow B (`suite2_sq_dag_coherence_audit.md`)
- [ ] Issue de tracking — evaluar si abrir uno separado o sumar a #46/#36

## Referencias

- Audit estructural + semantico Flow B: `suite2_sq_dag_coherence_audit.md`
- Baseline v2 dump: `compiler_baseline_full_dump_v2.json`
- Strategy doc: `suite2_compiler_improvement_strategy.md`
- Pattern breakdown: `suite2_pattern_breakdown.md`
- Diagnostic battery D1/D2/D4: `suite2_diag_*.{json,md}`
- GH issues: #7 (Suite 2 epic sub), #26 (eval-suite epic), #36 (compiler-fix epic), #46 (SQ semantic coverage)
