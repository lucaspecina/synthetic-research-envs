# SQ <-> DAG Coherence Audit — Flow B fase 1 (#44)

**Fecha**: 2026-04-17
**Scope**: Flow B (SQ compiler sobre SRCs canonicos), batch `p05_canonical_batch` (pre-fix, 2026-04-06).
**Script**: `scripts/audit_sq_dag_coherence.py`
**Output**: `sq_dag_audit.json`

## TL;DR

El audit sobre 198 specs generadas por el SQ compiler antes del fix de
`2f69f71` (2026-04-09) confirma la hipotesis de I-025/#44: cuando el LLM
elige `adjust_set`, el 11.6% de las veces el set NO es un backdoor valido.
**El fix (strip + auto-compute desde SCM) es la respuesta correcta**, y el
audit entrega la evidencia cuantitativa que exigia #44 fase 1 para cerrar.

## Metodologia

Tres niveles de coherencia spec <-> DAG por arm/measurement:

- **L1 (existence)**: toda variable referenciada por la spec aparece en `world.variables`.
- **L2 (causal path)**: para `kind=adjust`, existe camino dirigido `T -> Y`.
- **L3 (backdoor validity)**: para `kind=adjust`, el `adjust_set` propuesto (i) no contiene descendientes de T, y (ii) d-separa T de Y en el grafo mutilado (`out_edges(T)` removidas).

L3 replica la misma validacion que hace `_is_valid_backdoor_set` en
`src/sreg/tools/oi_verifier.py:226`.

## Resultados agregados

| Metrica        | Valor       |
|----------------|-------------|
| Cases          | 12          |
| SQs            | 55          |
| Specs          | 198         |
| L1 fail        | **0 (0.0%)** |
| L2 fail        | 1 (0.5%)    |
| L3 fail        | **23 (11.6%)** |
| Total L3 violation-instances (una spec puede tener varios arms malos) | 28 |

## Split de violations L3

| Patron                  | Count | % de L3 | Diagnostico                                                            |
|-------------------------|-------|---------|------------------------------------------------------------------------|
| `backdoor-unblocked`    | 23    | 82%     | LLM elige subset parcial de confounders; no cierra todos los backdoors |
| `descendants-of-T`      | 5     | 18%     | LLM incluye mediators/colliders downstream de T                         |

### Casos con >0 L3

| Case             | Specs | L3 fail |
|------------------|-------|---------|
| confounding      | 18    | 6       |
| microbiome       | 21    | 4       |
| selection_bias   | 15    | 3       |
| coral_bleach     | 12    | 2       |
| identifiability  | 7     | 2       |
| immunotherapy    | 24    | 2       |
| missing_data     | 17    | 2       |
| competing_mech   | 14    | 1       |
| poverty          | 19    | 1       |

Casos **limpios** (0 L3 fail): `chemical`, `heterogeneity`, `policy_equity`.

### Ejemplos representativos

**Pattern A — backdoor unblocked** (`confounding/sq2`):
```
T=drug_y_exposure, Y=recovery_index_14d
Z chosen={baseline_severity}
=> does not d-separate T from Y (backdoor paths open)
```
Aqui hay mas de un confounder en el DAG; el LLM eligio solo uno.

**Pattern B — descendants-of-T** (`microbiome/sq2`):
```
T=recent_antibiotic_exposure, Y=systemic_inflammation_crp
Z chosen={immune_function_score, microbial_diversity_index}
=> adjust_set contains descendants of T
```
Ambas variables son downstream de T (mediators), no confounders.

## Correlacion con Suite 2 baseline (claim compiler)

El dump `compiler_baseline_full_dump_v2.json` (55 gold targets, claim
compiler sobre w1/w2/w3) muestra **0 arms con `adjust_set` no vacio**
sobre 145 arms totales. El claim compiler ya opera bajo politica
"LLM blind, verifier auto-fills" — el bug es **exclusivo de Flow B pre-fix**.

La tasa de 31% fail de Suite 2 NO esta explicada por este modo de fallo;
vive en otras fuentes (taxonomia `adjust` vs `intervene`, kinds como
`distinguishable` vs `positive`, etc. — ver
`research/synthesis/suite2_pattern_breakdown.md`).

## Estado del fix

Commit `2f69f71` (2026-04-09, "feat(P06): #45 Flow B — adjust_set
derivado del SCM, no del LLM") aplica dos defensas simultaneas:

1. **Prompt** (`oi_sq_compiler.py:70-71, 100-101`): GRAMMAR_REF dice
   "DO NOT specify `adjust_set`".
2. **Code** (`oi_sq_compiler.py:691-700`): si el LLM emite
   `adjust_set` en un arm `kind=adjust`, se hace `pop` antes del
   `AtomicSpec(**spec_dict)`. La lista vacia dispara
   `_find_backdoor_set` en el verificador.

Tests de regresion en `tests/tools/test_oi_sq_compiler.py`:
- `test_strips_adjust_set_from_both_adjust_arms`
- `test_strip_is_noop_when_no_adjust_set_provided`
- `test_strip_does_not_touch_baseline_arm`
- `test_strip_works_for_direct_atomic_format`
- `test_strip_removes_invalid_variable_names_without_error`

## Decision para fase 2 (#44): pasar el DAG al prompt del LLM?

**Recomendacion: NO.** Evidencia:

- 82% de las violations son `backdoor-unblocked` — requieren d-separation
  reasoning, que LLMs hacen mal sistematicamente (ver CLadder
  benchmarks). Pasar el DAG no arregla esto sin un solver adicional.
- 18% son `descendants-of-T` — podrian mitigarse con la DAG en el
  prompt, pero al costo de (a) prompt mas largo, (b) violar la
  simetria con Flow A (solver no ve SCM), (c) tentacion a que la
  presion evolutiva sobre el scoring se erosione.
- El approach "blind LLM + code auto-compute" ya cubre 100% de los
  casos **y** preserva la invariante 8 de `PROJECT.md` (Flow A vs Flow B).
- El strip es deterministico y testable; la correcion por LLM es
  probabilistica.

**Mantener** politica actual. Registrar decision en `CHANGELOG.md` y
cerrar GH issue #44.

## Deliverables

- [x] Script reutilizable: `scripts/audit_sq_dag_coherence.py`
- [x] JSON detallado: `sq_dag_audit.json`
- [x] Sintesis (este doc)
- [x] Evidencia >50 SQs (criterio cierre fase 1): **55 SQs auditadas**
- [x] Root cause por caso: tabla arriba
- [ ] Regenerar batch post-fix y confirmar 0 L3 (pendiente, opcional)

## Audit complementario — Coherencia semantica SQ texto <-> specs

**Motivacion**: el audit L1/L2/L3 valida estructura (variables existen, hay
camino causal, adjust_set es backdoor valido). No valida si las specs miden
**semanticamente** lo que el texto de la SQ pide. Con Azure disponible se
corrio un LLM-judge (gpt-5.4) sobre los mismos 12 cases / 55 SQs.

**Script**: `scripts/audit_sq_text_spec_coherence.py`
**Output**: `sq_text_spec_coherence_audit.json`
**Two-pass**: re-audit automatico para SQs con `confidence<0.6` o verdict
severo (`wrong_claim`, `contradictory`, `orphan_vars`). 38/55 reauditadas.

### Rubric

- `coherent`: specs miden lo que el texto pide
- `narrow`: texto amplio, specs cubren subset
- `incomplete`: texto con 2+ subclaims, specs cubren solo algunos
- `wrong_claim`: spec mide algo distinto a lo que el texto pide
- `orphan_vars`: vars nombradas en texto ausentes en spec, o viceversa
- `contradictory`: specs dentro del SQ se contradicen
- `abstain`: info insuficiente

### Resultados agregados

| Verdict         | Count | %     |
|-----------------|-------|-------|
| coherent        | 13    | 23.6% |
| wrong_claim     | 26    | 47.3% |
| orphan_vars     | 7     | 12.7% |
| narrow          | 4     | 7.3%  |
| contradictory   | 3     | 5.5%  |
| incomplete      | 1     | 1.8%  |
| abstain         | 1     | 1.8%  |

**Solo 23.6% de las SQs son semanticamente coherentes.** Cada SQ puede tener
multiples violations (total instances: 76 violations sobre 55 SQs).

### Per-case (coherent / total)

| Case               | Coherent | Observaciones                                             |
|--------------------|----------|-----------------------------------------------------------|
| microbiome         | 0/5      | **Todos wrong_claim**                                     |
| confounding        | 0/4      | 3 wrong_claim, 1 narrow                                   |
| coral_bleach       | 0/4      | 2 wrong_claim, 1 contradictory, 1 narrow                  |
| identifiability    | 0/3      | 1 wrong_claim, 1 contradictory, 1 incomplete              |
| competing_mech     | 3/5      | Mejor caso (60% coherente)                                |
| heterogeneity      | 2/5      |                                                           |
| selection_bias     | 2/5      |                                                           |
| policy_equity      | 2/5      |                                                           |
| chemical           | 1/5      |                                                           |
| immunotherapy      | 1/5      |                                                           |
| missing_data       | 1/4      |                                                           |
| poverty            | 1/5      |                                                           |

### Patrones de `wrong_claim` (40 instancias)

Clasificacion heuristica sobre las razones devueltas por el judge:

| Patron                            | Instancias | Descripcion |
|-----------------------------------|------------|-------------|
| explanation_to_identifiability    | 16         | Texto pide "se explica por X?" -> spec hace `identifiability_check` (booleano, no estima porcion) |
| causal_to_correlation             | 9          | Texto pide efecto causal -> spec mide `correlation`/`partial_correlation` |
| mediation_collapse                | 6          | Texto pide cadena mediada ("reduce Y y thereby aumenta Z") -> specs atan endpoints sin medir la cadena |
| moderation_missing_interaction    | 2          | Texto pide "depende del contexto" -> specs miden efecto en cada contexto sin compararlos ni medir interaction |
| directional_to_distinguish        | 1          | Texto pide direccion -> `assertion=distinguishable` |
| other                             | 6          | Miscelaneo                                                 |

### Ejemplos representativos

**Explanation -> identifiability** (`confounding/sq1`):
- Texto: "Is the negative crude association between Immunex-R use and
  14-day recovery **explained by confounding from baseline severity and
  comorbidity burden** rather than a genuine causal effect?"
- Spec: `adjusted_assoc_drugy_recovery_not_negative_after_severity_comorbidity`
  con `measurement.kind=identifiability_check` y
  `assertion.kind=identifiable`.
- Bug: el texto pide una prueba de que el confounding **explica** la
  asociacion cruda (requiere comparar crude vs adjusted). El spec solo
  checkea si la causa es identificable asumiendo el adjust_set. No mide
  la explicacion.

**Mediation collapse** (`chemical/sq1`):
- Texto: "Do harsher salinity and temperature conditions causally reduce
  phase-balance margin **and thereby** increase reformulation iterations?"
- Specs: (1) harsh -> margin (assertion=negative), (2) harsh -> iterations
  (assertion=positive), (3) correlation(margin, iterations).
- Bug: el "thereby" pide la cadena mediada (harsh -> margin -> iterations).
  Los specs miden los dos efectos totales por separado y una asociacion
  no-causal entre margin e iterations — nunca mide la mediacion.

**Causal -> correlation** (`competing_mech/sq5`):
- Texto: pide evidencia de un mecanismo causal compartido.
- Specs: miden `correlation` / `partial_correlation`.
- Bug: correlacion (aun parcial) no prueba mecanismo causal.

### Diagnostico

El SQ compiler **traduce mal el claim semantico del texto** en un numero
elevado de casos (47% wrong_claim). Los patrones sugieren que el prompt
del compiler/orchestrator no tiene recipes explicitos para:
- **explanation_of_association**: "X explica Y" -> medir delta entre
  adjusted y crude, no `identifiability_check`.
- **mediation**: "A -> B -> C" -> spec con measurement de efecto directo
  vs indirecto, no 3 specs separados.
- **moderation**: "X depende de Z" -> comparar efecto en contextos
  distintos (`contrast_diff` o `ranking` sobre efectos condicionales).
- **ranking / informativeness**: "¿cual es mas X?" -> spec con `ranking`
  assertion, no pairwise correlations.

### Decision

Abrir **issue nuevo** (fuera de #42/#43): **SQ compiler semantic coverage
recipes**. Prioritario porque:
- Afecta ground truth de Flow B (Sherlock) mas que el bug estructural L3.
- Ya explica otros modos de fallo documentados (ej: agentes que responden
  bien la pregunta pero el verifier rechaza porque la spec medía otra cosa).
- Los fixes son **prompt-level** — agregar recipes / few-shot en el
  orchestrator prompt para los 6 patrones identificados.

### Deliverables de este audit

- [x] Script: `scripts/audit_sq_text_spec_coherence.py`
- [x] JSON: `sq_text_spec_coherence_audit.json`
- [x] Sintesis (esta seccion)
- [x] Evidencia: 55 SQs auditadas con LLM-judge + 2do pase automatico
- [ ] Issue nuevo (proximo paso)

## Proximos pasos

1. Abrir issue nuevo: "SQ compiler semantic coverage — add recipes for
   explanation/mediation/moderation/ranking". Prioridad alta.
2. **Validacion empirica L3**: regenerar p05 con compiler post-fix; re-run
   audit estructural; esperado 0 L3.
3. **Integrar ambos audits en CI**: correr sobre cualquier SRC batch nuevo.
4. **Cerrar GH #44** con este doc + decision "NO pass DAG to LLM".

## Referencias

- GH issue #44: "Sub · Suite 2 · Flow B LLM DAG visibility"
- Local issue origen: `issues/I-025-flow-b-llm-dag-visibility.md`
- Fix: commit `2f69f71` (2026-04-09)
- Verificador: `src/sreg/tools/oi_verifier.py:226-305`
- Compiler: `src/sreg/tools/oi_sq_compiler.py:684-700`
- Invariante: `PROJECT.md` invariante 8 (Flow A vs Flow B boundary)
- Memoria: `project_flow_a_vs_flow_b.md`
