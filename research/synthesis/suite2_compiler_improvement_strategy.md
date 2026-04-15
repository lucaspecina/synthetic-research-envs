# Suite 2 — Compiler Improvement Strategy

> **🧭 NORTE DE ESTA FASE (I-007 diagnósticos):**
> **Evaluar y testear el compiler para entender POR QUÉ falla, DÓNDE
> falla, y que los diagnósticos INDIQUEN CÓMO MEJORARLO.**
> Toda propuesta de análisis pasa por 3 ejes: ¿por qué? ¿dónde? ¿cómo
> mejorar? Si no sirve a ninguno → YAGNI. NO conectar hints con
> presiones evolutivas / RL transfer mientras escribimos diagnósticos
> (ese framing es correcto pero es otro norte, posterior al merge).
>
> **Scope:** norte aplica a I-007 solamente; el worktree eval-suite
> cubre I-006/I-008/I-009 además y tiene scope más amplio.
>
> **Status:** CANON plan de ataque al recipe gap del claim compiler.
> **Date:** 2026-04-15 (diagnostics D1/D2/D4 + stage1_split corridos).
> **Context:** baseline v2 estable (`suite2_compiler_baseline.md` §9),
> effective_pass_rate = 31%, strict_full_pass_rate = 13%, 5 familias en
> 0% strict pass. Qué hacer ahora y cómo medir el progreso.
> **Related:** I-026 (recipe exemplars), I-027 (baseline hygiene), I-028
> (sweep_values bug), I-029 (abstain decision broken — ver §8.2).

## TL;DR

El bottleneck del compiler es **recipe gap duro**: el LLM reconoce el
patrón por vocabulario (D1 = 69%) pero no sabe componer el spec — en
particular falla al elegir **arm_kinds** (50% slot acc, D2). No es
capability ceiling — es falta de recipes operacionales en el prompt.

**Post-diagnostics (§8):** los findings revisan el plan:
- D4 pasa **6/10** (no 10/10): upper-bound de formalización es 13% →
  **24%** strict_pass, no 31%.
- Los 4 pass-by-accident de D4 deben reclasificarse de `adjust_swap` a
  `real_struct_err` (compiler elige values de percentiles extremos, el
  signo se preserva por casualidad).
- **Hint nuevo #1 (abstain broken):** compiler acierta 0/4 abstain
  decisions. Siempre compila cuando debería abstenerse.
- **Hint nuevo #4 (arm_kinds es el cuello):** 50% slot accuracy en D2;
  los otros 6 slots están en 68-96%. Attacar `intervene vs observe vs
  adjust` es la intervención de máximo apalancamiento.
- **Recognition gap puro solo en CC-B5** (0% D1). El resto de las 5
  familias 0%-pass es composition gap.

## 1. Definición operacional: "recipe gap duro"

> El LLM reconoce el concepto causal por su nombre pero no sabe
> traducirlo en la secuencia de operaciones verificable que lo captura.

**Ejemplo canónico — W1_F07:**
- **Claim:** "Severidad confunde la relación tratamiento→outcome."
- **Recipe correcto:** comparar dos arms — `(observe T, Y)` vs
  `(intervene T, Y)`. La diferencia **es** el confounding.
- **Lo que emite el LLM:** `partial_correlation(T, Y | Severity)`. Método
  clásico correcto para estimar un efecto — pero **no mide** si hay
  confounding. Mide otra cosa.

El LLM vio "confounding" como palabra. Eligió una herramienta que suena
relacionada. No tiene el recipe operacional.

### Por qué es "duro"

- **Determinismo:** audit #11a mostró que SQ-A1 produce output
  **byte-identical** en 3/3 runs a T=0. No hay varianza que explotar
  con sampling + voting.
- **Estructural:** afecta 5 familias enteras (CC-A3, CC-A4, CC-A5,
  CC-B5, SQ-A1) = 20/55 targets.
- **Invariante a hints:** el test A/B/C del baseline mostró que un hint
  tipo "this is a MEDIATION claim" **no alcanza**. Hace falta el recipe
  completo, no solo el label.

## 2. Opciones de mejora (ordenadas por impacto / costo)

| # | Propuesta | Impacto esperado | Costo | Cambia core? |
|---|---|---|---|---|
| 1 | **Recipe exemplars por familia** (I-026) | Alto | Bajo (prompt + eval) | No |
| 2 | **Compiler en dos pasos** (pattern recognition → recipe retrieval → composition) | Alto | Medio (refactor) | Sí |
| 3 | **Formalizar adjust-swap como equivalencia** | Alto (strict_pass 13→31%) | Mínimo | No (encoding de `alternative_atoms`) |
| 4 | **Verify-and-revise loop** (compiler → schema validator → revise) | Medio | Alto (2× LLM calls por target, + orchestration) | Sí |
| 5 | **Defensive post-processing** (patch quirúrgico para I-028) | Bajo | Mínimo | No |
| 6 | **Dar DAG al compiler** (I-025, controversial) | Desconocido | Medio | Sí (rompe invariante de blind compiler) |

### Recomendación primera acción (post-diagnostics): **Abstain fix + #3 parcial + #1 targetizado**

**Orden concreto (ver §8 para justificación empírica):**

1. **Fix abstain decision** (nuevo, ver I-029). D1 muestra que SQ-C1 y
   CC-E3 se reconocen al 100% en el clasificador, pero en D2 el compiler
   trata de compilar (status=compile) en 4/6 cases. Es un bug de
   **decision-policy**, no de recognition ni de composition. Arreglarlo
   sube 6 stage1_fail → (estimado) 4-5 clean passes.
2. **#3 parcial**: formalizar equivalencia solo para los **6 pares
   probados equivalentes** en D4 (no los 10). Los otros 4 se reclasifican
   a real_struct_err. Strict_pass: 13% → 24%.
3. **#1 (exemplars)** targetizados por slot:
   - CC-B5: scaffolding de **recognition** (doubles, large effect →
     CC-B5, no CC-A4).
   - CC-A3, CC-A4, CC-A5, SQ-A1: scaffolding de **arm_kinds** (la recipe
     canónica para mediation/heterogeneity/confounding).
   - CC-D1, CC-D2: decision boundary — cómo distinguir intervene
     (causal) vs observe (associational) vs adjust (backdoor).

#2, #4, #6 se consideran después del baseline post-#3+#1. No son de
arranque.

## 3. Diagnostic battery — lo que nos falta medir

Antes de atacar con exemplars o cambios arquitecturales, necesitamos
**separar sub-hipótesis** sobre dónde vive el gap. Cada diagnostic
aisla un eje distinto.

### D1 — Pattern recognition isolation

**Pregunta:** ¿el LLM clasifica bien el pattern cuando le pedimos SOLO
eso, sin compilar?

- **Input:** los 55 claims de Suite 2.
- **Output esperado:** family tag (CC-A3, CC-A5, SQ-A1, etc.).
- **Métrica:** accuracy de clasificación por familia.
- **Hipótesis que decide:** si accuracy ≥ 80%, el problema es
  composition (el LLM reconoce, no sabe componer). Si accuracy < 50%,
  el problema es recognition primero, composition después.
- **Costo:** 55 LLM calls, ~3 min.

### D2 — Recipe elicitation (abstract)

**Pregunta:** dado un claim, ¿el LLM puede describir la receta correcta
EN PALABRAS?

- **Input:** 20 claims seleccionados (2 por familia 0% + 2 controles que
  pasan en baseline).
- **Output esperado:** descripción textual del recipe ("compará arms
  observe vs intervene, medí la diferencia, chequeá si supera tol").
- **Métrica:** LLM-judge contra gold recipe, dicotómica.
- **Hipótesis que decide:** si el LLM conoce el recipe en palabras pero
  no lo emite como spec, es problema de **traducción** (formato /
  catálogo de primitivas), no de conocimiento. Eso cambia cómo se
  escriben los exemplars.
- **Costo:** 20 LLM calls + 20 judge calls.

### D3 — Spec completion (structural)

**Pregunta:** dado el esqueleto del spec (arms con kinds correctos,
values y condition_on vacíos), ¿puede completarlo?

- **Input:** 55 claims + esqueleto parcial derivado del gold.
- **Output esperado:** spec completo.
- **Métrica:** strict/effective pass usando el mismo harness Suite 2.
- **Hipótesis que decide:** si completion alcanza >80% pero from-scratch
  está en 31%, el bottleneck está en el **arm design** (elegir kinds), no
  en el filling. Eso sugiere una primera llamada "arm designer" antes
  que full compilation.
- **Costo:** 55 LLM calls.

### D4 — Adjust-swap formal equivalence **[ARRANCAR POR ACÁ]**

**Pregunta:** para los 10 `adjust_swap` observados en v2, ¿la
equivalencia `intervene(T=v) ≡ adjust(T=v | back-door set)` se sostiene
matemáticamente sobre el SCM?

- **Input:** los 10 pares (gold_spec, compiler_spec) desde
  `compiler_baseline_full_dump_v2.json`.
- **Output:** `verify_atom` de ambos contra el SCM del mundo, comparar
  `ground_truth` numérico.
- **Métrica:** count de pares donde
  `|ground_truth_gold − ground_truth_compiler| < tol_verifier`.
- **Hipótesis que decide:** si pasa 10/10, encoding la equivalencia en
  `alternative_atoms` es legítimo — reclasifica 10 de `adjust_swap` a
  `strict_pass`, subiendo strict_pass 13% → 31%. Si pasa menos,
  hay que entender los edge cases.
- **Costo:** **0 LLM calls.** Verificación analítica sobre el dump.

### D5 — Exemplar transfer

**Pregunta:** ¿un exemplar de confounding mejora la performance en
mediation? O son ortogonales?

- **Conditions:** 4 — baseline / +confounding_exemplar /
  +mediation_exemplar / +both.
- **Targets:** 10 mediation targets (CC-A3).
- **Hipótesis que decide:** si no transfiere, necesitamos un exemplar
  por familia (≥5 exemplars). Si transfiere bien, un exemplar genérico
  "compositional recipe pattern" puede alcanzar.
- **Costo:** 4 × 10 = 40 LLM calls.

### D6 — Determinism check (full families)

**Pregunta:** ¿todas las familias 0% son byte-identical como SQ-A1? O
algunas tienen varianza explotable?

- **Input:** las 20 entries de 0%-pass families × 3 seeds distintos del
  LLM (cambiar temperatura 0.0 → 0.3 controlado).
- **Output:** compiler_specs por seed.
- **Métrica:** fraction of families donde al menos 1 seed produce un
  spec distinto al de T=0.
- **Hipótesis que decide:** si todas son byte-identical, ni sampling +
  voting ayuda — solo prompt revision. Si algunas tienen varianza,
  hay señal adicional para self-consistency voting.
- **Costo:** 60 LLM calls.

### D7 — Catalog awareness (opcional)

**Pregunta:** ¿el LLM sabe que todas las primitives existen? O hay gaps
de "nunca alcanza" (ej: `identifiability_check` nunca usado en
compiler output)?

- **Input:** pedirle al LLM "para cada item del catalog (measurements,
  comparisons, assertions), dame un ejemplo de claim que lo requiera".
- **Métrica:** coverage del catálogo en sus ejemplos.
- **Hipótesis que decide:** confirma/descarta el "catalog visibility
  gap" que audit #11a sospechó para CC-D2.
- **Costo:** 1 LLM call.

## 4. Priorización

| Diag | Costo | Impacto | Prioridad | Desbloquea |
|---|---|---|---|---|
| **D4** | **0 calls** | **Alto** (strict_pass 13→31%) | **1** | Formalización adjust-swap (#3) |
| D1 | 55 calls | Alto (recognition vs composition) | 2 | Decide si D2 es necesario |
| D2 | 40 calls | Alto (traducción vs conocimiento) | 3 | Forma del exemplar |
| D6 | 60 calls | Medio (sampling útil?) | 4 | Estrategia de decoding |
| D3 | 55 calls | Medio (arm design vs filling) | 5 | Arquitectura en 2 pasos |
| D5 | 40 calls | Medio (transfer?) | 6 | Scope de los exemplars |
| D7 | 1 call | Bajo (confirma hipótesis #11a) | 7 | CC-D2 específico |

**Total si corremos todo:** ~250 LLM calls. Costo bajo (~15 min de wall
time, unos pocos centavos de Azure).

**Arrancar por D4** porque es gratis y no requiere diseño nuevo —
puede correr directamente sobre `compiler_baseline_full_dump_v2.json`.

## 5. Qué decisión toma cada diagnostic

| Escenario | Decisión |
|---|---|
| D4 pasa 10/10 | Implementar `alternative_atoms` encoding para adjust↔intervene. Strict_pass sube a 31% sin tocar el LLM. |
| D4 pasa <10/10 | Estudiar los contra-ejemplos — probablemente back-door set insuficiente. Decidir caso por caso. |
| D1 ≥ 80% + D2 alto | El problema es **traducción/formato**. Exemplars deben ser pequeños + explícitos sobre el catálogo. |
| D1 ≥ 80% + D2 bajo | El problema es **recipe knowledge**. Exemplars deben ser detallados sobre el recipe entero. |
| D1 < 50% | Antes que exemplars, agregar un pattern-recognition preface al prompt. |
| D3 ≥ 80% | Arquitectura en 2 pasos justificada: "arm designer" + "filler". |
| D5 transfer alto | Un exemplar genérico "recipe pattern" alcanza. Scope chico. |
| D5 transfer bajo | Un exemplar por familia. Scope ~5-6 exemplars. |
| D6 byte-identical | Sampling no ayuda. Solo prompt revision es señal. |

## 6. Qué SÍ y qué NO queda fuera

**Queda fuera de esta estrategia:**
- SQ compiler (Flow B) — aún sin baseline, suite 2 no lo ha testeado.
- Relevance judge, answer-key grounding — sin baseline.
- Ablations E2E (Suite 4) — gated en que el compiler suba del 31%.

**Sí queda dentro:**
- Cualquier trabajo sobre `compile_claim_direct` (Flow A).
- Re-run del baseline cuando el compiler cambie (script v2 ya está
  listo y es reproducible).
- Encoding de equivalencias estructurales en `alternative_atoms`.

## 7. Findings (2026-04-15, post-diagnostics)

Esta sección documenta los hints empíricos que nos da la diagnostic
battery. Los scripts viven en `scripts/suite2_diag_*.py` y las tablas
crudas en `research/synthesis/suite2_diag_*_results.json`.

### 7.1 D4 — adjust_swap equivalence (0 LLM calls)

Procesó los 10 pares (gold_spec, compiler_spec) del bucket
`adjust_swap`. Criterio: mismo n_atoms, mismas measurement/comparison/
assertion kinds, mismo `solver_assertion_holds`, y |Δ ground_truth| ≤
0.05 — todo bajo **verifier actual**, no equivalencia causal abstracta.

| Resultado | Count |
|---|---|
| equivalent | 6 |
| numerical_diff (holds se preserva pero gt difiere > 0.05) | 4 |

**Los 4 numerical_diff son pass-by-accident**: el compiler elige
`values` desde los percentiles extremos del sample empírico (~±0.87,
±0.99), no del contraste unitario 0/1 del gold. El signo coincide por
casualidad; `ground_truth` se infla proporcional al rango.

**Upper-bound revisado:** formalizar equivalencia solo para los 6
probados sube strict_pass de **13% → 24%** (7+6/55), **no** 31%. Los
otros 4 deben reclasificarse de `adjust_swap` a `real_struct_err`.

**Hint #2 (value-scale bias):** el compiler tiene una preferencia por
decodar `values` de sample statistics (min/max, percentiles) cuando la
claim pide un contraste binario (0/1). En el current SCM esto compensa
por linealidad; en un SCM no-lineal o con sign flip por región, la
misma receta rompe.

### 7.2 Stage1 split (0 LLM calls)

Re-clasifica los 6 `stage1_fail` en sub-modos:

| Sub-modo | Count | Definición |
|---|---|---|
| decision_fail | 4 | compiled cuando gold=abstain (o versa) |
| crash | 2 | no compiled pero gold=compile (I-028 sweep_values) |

**Hint #1 (ABSTAIN BROKEN):** compiler acierta **0/4** abstain
decisions. Las 4 claims con gold=abstain (non_expressible, latent,
temporal) se compilan igual — con specs estructuralmente razonables
pero semánticamente inválidos. La decision-policy del compiler no
tiene puerta de abstain funcional.

Este bug no es D1-level (recognition) ni D2-level (composition). Es
una policy missing: el compiler asume "si me dieron una claim,
compilarla". Arreglarlo debe ser intervención #0 porque es cheap y
no requiere exemplars — solo un prompt clause y un classifier-head
explícito.

### 7.3 D1 — Pattern recognition (55 LLM calls, 69.1% overall)

Clasificación de los 55 claims en 33 familias, sin compilar. Match
exacto con `fact.families[0]`.

| Familia | D1 acc | n | Comportamiento |
|---|---|---|---|
| CC-A4 (heterogeneity) | 100% | 3 | Reconoce ok |
| CC-C2 (negation) | 100% | 3 | Reconoce ok |
| CC-A7 (tail risk) | 100% | 2 | Reconoce ok |
| CC-A8 (variance) | 100% | 2 | Reconoce ok |
| CC-E1 (temporal) | 100% | 1 | Reconoce ok |
| SQ-A1 (direct causal Q) | 100% | 3 | Reconoce ok |
| SQ-A3 (identifiability Q) | 100% | 2 | Reconoce ok |
| SQ-C1 (non-expressible) | 100% | 2 | Reconoce ok |
| CC-A3 (mediation) | 88% | 8 | Fuerte |
| CC-A1 (causal effect) | 67% | 9 | Mediano |
| CC-A5 (confounding) | 67% | 3 | Mediano |
| CC-E2 (latent) | 67% | 3 | Mediano |
| CC-E3 (non-expressible) | 50% | 2 | Mediano |
| CC-A2 (observational) | 40% | 5 | Débil |
| **CC-B5** (quantitative) | **0%** | 3 | **Recognition gap** |
| **CC-D1** (causal-vs-obs) | **0%** | 2 | Colapsa a CC-A1 |
| **CC-D2** (med-vs-conf) | **0%** | 2 | Colapsa a CC-E3/A5 |

**Hint #3 (recognition vs composition):** de las 5 familias 0%-strict-
pass en el baseline:
- **CC-A3, CC-A4, SQ-A1** reconocen ≥88% pero fallan compose →
  **composition gap puro**.
- **CC-A5** mixed (67%).
- **CC-B5** 0% reconoce → **recognition gap puro**. Exemplars sin un
  pattern-recognition preface no van a funcionar para esta familia.

**Familias de decision boundary (CC-D1, CC-D2) caen al patrón más
simple.** Esto confirma que el compiler no tiene señal para elegir
entre recetas parecidas — es exactamente el bottleneck que D2 destapa
(arm_kinds 50%).

### 7.4 D2 — Recipe slot elicitation (55 LLM calls, 75.5% overall)

Por target, pedir al LLM un JSON cerrado con 7 slots (status, n_atoms,
arm_kinds, role_vars, measurement_kind, comparison_kind,
assertion_polarity). Match determinista contra gold
`StructuralContract`. Prompt incluye las variables del mundo.

| Slot | Accuracy | Nota |
|---|---|---|
| role_vars | 96% (48/50) | **No es el cuello** (con world context) |
| status | 93% (51/55) | Falla en 4 abstain cases (consistente con Hint #1) |
| n_atoms | 78% (39/50) | Mediation/heterogeneity suele emitirse como 1 atom |
| measurement_kind | 74% (37/50) | Razonablemente robusto |
| comparison_kind | 68% (34/50) | Débil en difference vs identity |
| assertion_polarity | 68% (34/50) | SQ-A1 siempre falla (emite "greater_than" cuando gold es "positive") |
| **arm_kinds** | **50% (25/50)** | **CUELLO DE LA COMPOSICIÓN** |

**Confusiones top de arm_kinds** (gold → pred):
- `[intervene]` → `[condition, intervene]` (5×): añade `condition` innecesariamente cuando se menciona "adjusting for Z".
- `[baseline]` → `[observe]` (4×): dos etiquetas semánticamente casi equivalentes para el LLM.
- `[intervene, observe]` → `[adjust, observe]` (3×): la misma forma del adjust-swap, pero ahora al nivel de recipe — el LLM prefiere `adjust` aún cuando el gold pide un contraste observe-vs-intervene.
- `[baseline]` → `[adjust, observe]` / `[intervene]` (4× combinados): el LLM inventa arms cuando la claim solo pide una medición single-arm.

**D2a addendum (antes de arreglar world context):** al no pasar las
variables del mundo, role_vars caía a 10% (el LLM inventaba nombres
como "Treatment" en vez de "T"). Es señal independiente: el compiler
real obtiene el vocab via `build_world_summary`, pero el hallazgo
confirma que **variable-grounding es 100% context-dependent**.
Archivado en `suite2_diag_d2a_no_world_context_results.json`.

**Hint #4 (arm_kinds es el bottleneck real de composición):** con
world context, los demás slots están en 68-96%. Solo arm_kinds está
en 50%. La intervención de máximo apalancamiento es enseñar al
compiler cuándo usar `intervene` vs `observe` vs `adjust` —
específicamente, cuándo **no** usar `condition` y cuándo el par
`[intervene, observe]` es el contraste canónico.

### 7.5 Síntesis

| Dimensión | Estado post-diagnostics |
|---|---|
| Abstain decision | **Completamente rota** (0/4). Fix independiente. |
| Pattern recognition | **69%**. Grueso aceptable, decision boundaries y CC-B5 fallan. |
| Recipe knowledge — n_atoms, role_vars, measurement, comparison, assertion | **68-96%**. Variabilidad por familia. |
| Recipe knowledge — **arm_kinds** | **50%**. El bottleneck duro. |
| adjust_swap formalization | Upper bound 13→**24%** (no 31%). |
| **Taxonomy consistency (arm.kind)** | **Contract bug** (§7.6): `baseline`/`observe` aliased inconsistentemente en 3 fuentes; `condition.values` documentado pero ignorado por verifier. **Prereq de Rama C** (I-030). |

### 7.6 Taxonomy audit — `arm.kind` contract vs executor vs evaluator (0 LLM calls)

**Motivación.** D2 mostró arm_kinds al 50% — bottleneck duro. Antes de
escribir exemplares (Rama C), auditamos si la definición operacional de
cada kind es consistente entre las fuentes que el compiler consume y
los tests/scoring ejecutan. Codex flaggeó preliminarmente 3 fuentes
contradictorias; el audit confirma el bug y agrega más.

**Fuentes auditadas.**

| Fuente | Rol |
|---|---|
| `src/sreg/tools/oi_sq_compiler.py:43-76` — `GRAMMAR_REF` | Contrato del lenguaje, compartido por SQ compiler y claim compiler direct |
| `src/sreg/tools/oi_extraction.py:466-490` — `compile_claim_direct()` | Prompt real de Flow A (el que se corrió en baseline v2) |
| `src/sreg/tools/oi_verifier.py:119-155` — `_run_single_arm()` | Ejecutor (semántica efectiva de cada kind) |
| `tests/eval/suite2_translation/gold_targets.py:50+` — `StructuralContract.allowed_arm_kinds` | Hard gate del test Suite 2 (`test_compiler_llm.py:181`) |
| `src/sreg/tools/oi_sq_matching.py` — `spec_match()` | Matcher para scoring canónico (Suite 4+) |
| `scripts/suite2_diag_d2_recipe_slots.py:110-126` — D2 diag prompt | Lo que enseñamos al LLM en el diagnostic (elicitation) |
| Este doc §8.3 recipes | Recipe prescriptions actuales |

**Filtro de severidad (3 capas).** Si cualquiera dice "distinto", no son aliases.
1. **Contract**: ¿se describen como distintos en schema/prompt?
2. **Executor**: ¿el verifier los ejecuta distinto en algún caso válido?
3. **Evaluator**: ¿gold structural contract / matching dependen de la distinción?

#### F1 — `baseline` vs `observe`: contract bug real

- **Executor (capa 2):** `baseline` = `world.sample(n)` **sin filtros** (joint nativa). `observe` = `world.sample(n)` + `_filter_condition(df, arm.values)` + optional `condition_on`. **Distintos** cuando observe tiene `arm.values`, que es el uso típico. Coinciden solo en el caso degenerado "observe sin values ni condition_on".
- **Evaluator (capa 3):** `allowed_arm_kinds` usa cada kind como token exacto. W3_F07 gold lista `{"observe", "intervene"}` explícitamente; otros golds listan `{"baseline"}`. `test_compiler_llm.py:181` exige `arm_kinds.issubset(allowed_arm_kinds)` — **hard gate**. Un compiler que emita "observe" donde gold dice "baseline" falla strict.
- **Contract (capa 1) — 3 voces contradictorias:**
  - `GRAMMAR_REF` las presenta como kinds separados con descripciones distintas (✓).
  - `compile_claim_direct()` prompt:502 las trata como intercambiables: `"Use a single baseline (or observe) arm"` para claims asociacionales.
  - Strategy doc §8.3 pre-audit decía: `"recipe observational association: [baseline]. No usar [observe]"`.
  - D2 diag prompt `recipe_slots.py:112` enseña lo opuesto: `"T correlates with Y → arm_kinds=[observe]"`.

→ Un compiler siguiendo cualquiera de las fuentes puede emitir cualquiera de los dos kinds razonablemente, y fallar `allowed_arm_kinds` gate arbitrariamente según qué eligió el gold. **Parte del 50% de arm_kinds es atribuible a esta incoherencia, no a capability del LLM.**

#### F2 — `condition` con `arm.values`: contract bug (verifier ignora silenciosamente)

- `GRAMMAR_REF:54`: `"values: dict of variable=value for intervene/condition"`.
- `oi_verifier.py:142-145` — `QueryKind.CONDITION`: solo usa `arm.condition_on`. **Ignora `arm.values` silenciosamente.** No crashea; drop info.

→ Un compiler que siga `GRAMMAR_REF` al pie de la letra puede emitir `condition` con `values={var: val}` esperando filtrar, y el verifier sample sin filtro. Bug real, invisible en logs.

#### F3 — `condition` vs `observe`: semánticamente distintos, docs OK

- `observe` filtra por `arm.values` (point-value, tolerancia 15% std implícita).
- `condition` filtra por `arm.condition_on` (predicates ricos: range, quantile_range, in_set).
- Ambos observacionales, distintos slots. `GRAMMAR_REF` los describe como separados. Sin contradicción entre fuentes — solo la guía "cuándo usar cuál" no es muy explícita.

#### F4 — `intervene` + `condition_on` (híbrido): no documentado en contract

- `oi_verifier.py:125-129`: si `intervene` tiene `condition_on`, se hace `sample(do=values)` + filter después (interventional conditioned). Comportamiento válido y útil (ej. "effect of T on Y in subgroup with X > threshold").
- `GRAMMAR_REF` no menciona esta composición. Un compiler que no sepa que es legal podría abstenerse o producir specs incorrectas cuando el uso canónico es este.

#### F5 — `adjust` semántica bien aislada, sin bugs

`GRAMMAR_REF` tiene sección dedicada "Adjust arm semantics"; `compile_claim_direct` agrega ejemplos concretos; verifier `_run_adjustment()` match. **No es parte del bottleneck.**

#### F6 — Matcher (`oi_sq_matching.py`): `arm.kind` NO es hard gate

- `spec_match()` usa `measurement.kind`, `primary_vars`, `conditioning_set` como hard gates.
- Grep en `oi_sq_matching.py` para `arm\.kind|QueryKind\.` → **0 matches**.
- **Implicancia:** la ambigüedad baseline/observe es **más grave para Suite 2** (que sí gate por `allowed_arm_kinds`) que para scoring canónico Suite 4+ (que usa matching sin `arm.kind`).

#### Veredicto

- **F1 y F2 son contract bugs reales.** Violan capas 2-3 simultáneamente (F1) o capa 2 (F2). Son prereq de Rama C — escribir exemplares sobre un contrato inconsistente enseña la inconsistencia.
- **F3-F5:** documentación incompleta o clarificación, no bugs.
- **F6:** bound del bug. Es bug Suite 2-local, no global a SREG.

**Acción:** abrir **I-030: compiler taxonomy spec alignment** (separado de I-026). Rama C depende de I-030 (spec first, exemplars después).

**Recomendación de spec unificada (propuesta para I-030):**
- `baseline` = joint sampling SIN filtros. Uso: claims asociacionales donde el filter/adjustment está dentro del measurement (e.g. `partial_correlation` con `cond_set`).
- `observe` = joint sampling + `_filter_condition(arm.values)` (point-value). Uso: condicionamiento observacional simple sobre valor exacto.
- `condition` = joint sampling + `_filter_condition(arm.condition_on)`. Uso cuando el filter NO es point-value (range, quantile, in_set).
- **Eliminar `values` del contrato de `condition`** en GRAMMAR_REF; dejarlo solo para `intervene`.
- Reemplazar en `compile_claim_direct` el wording `"baseline (or observe)"` por regla discriminatoria por measurement: `correlation`/`partial_correlation` → baseline; filter point-value retrospectivo → observe; filter rich-predicate → condition.
- Sync D2 diag prompt + strategy doc §8.3 con la spec unificada.

## 8. Próximos pasos concretos (post-diagnostics)

Plan revisado con el aprendizaje empírico. Tres ramas paralelas,
todas chicas, ninguna requiere cambio arquitectural del compiler:

### 8.1 Rama A — Abstain policy (I-029, nueva)

1. Crear I-029: "Compiler abstain decision missing / broken."
2. Agregar al prompt del compiler una cláusula "If the claim mentions
   X/Y/Z (latent variables, temporal-only, non-expressible
   methodological) → status=abstain with code".
3. Test: los 6 stage1_fail deberían caer a 2 (solo los crashes de
   I-028).

### 8.2 Rama B — Adjust-swap formalization parcial

1. Encoding de `alternative_atoms` en gold_targets solo para los **6
   pares equivalentes probados** (lista en
   `suite2_diag_d4_results.equivalent_ids`).
2. Los **4 numerical_diff** NO se codifican — quedan como
   real_struct_err correctamente.
3. Re-run baseline v2: strict_pass sube 13% → 24%.

### 8.3 Rama C — Exemplars targetizados (I-026 refinado)

> **⚠ Prereq: I-030 (taxonomy spec alignment, §7.6).** Los recipes
> abajo asumen spec unificada. Si se escriben exemplares sobre el
> contrato actual (inconsistente), enseñan la inconsistencia. Orden:
> I-030 → I-026.

Contenido del exemplar diseñado por slot, no por familia (recipes
**post I-030**, según spec unificada propuesta en §7.6):

- **Recognition preface** (solo para CC-B5): explicar que "doubles",
  "halves", "large positive", "small negative" son señales de
  **quantitative commitment** (CC-B5), no de heterogeneity (CC-A4).
- **arm_kinds recipes** — 3 exemplars compactos:
  - Recipe "causal effect" (simple): `[intervene]` × treatment
    binarios 0/1, measurement=mean, comparison=difference.
  - Recipe "observational association":
    - Si measurement es `correlation` o `partial_correlation`: usar
      `[baseline]` (joint sampling, filter va en el measurement).
    - Si filter es point-value retrospectivo: `[observe]` con
      `arm.values`.
    - Si filter es range/quantile/in_set: `[condition]` con
      `arm.condition_on`.
  - Recipe "confounding detection" (CC-A5): pair `[intervene,
    observe]`, measurement=mean, comparison=difference. La diferencia
    entre los brazos **es** el sesgo.
- **Decision boundary** (CC-D1, CC-D2): un exemplar en contraste
  explícito, "si la claim dice X usar recipe A; si dice Y usar recipe B".
- **Staircase ablation** (proposed Codex 2026-04-15): antes de
  congelar N, medir accuracy con N=0/4/8/12 exemplares sobre
  arm-kinds confusion set. Guess: 6-8 suficiente. Si 8 no mueve la
  aguja, el issue no es shot count sino prompt semantics (→
  escalar a arch change).

### 8.4 Después: re-run baseline y medir

1. Re-run `suite2_full_dump_v2.py` con el compiler modificado.
2. Meta: strict_full_pass_rate ≥ 40% (desde 13% actual). Si no llega a
   40% con las 3 ramas, escalar a compiler-en-2-pasos (#2 en la tabla
   de §2).
3. Actualizar `suite2_compiler_baseline.md` §10 (v3).

## Links

- `research/synthesis/suite2_compiler_baseline.md` §9 — baseline v2
- `research/synthesis/suite2_pattern_breakdown.md` — per-family bucket counts
- `research/synthesis/suite2_fail_audit_recipe_patterns.md` — audit #11a
- `research/synthesis/compiler_baseline_full_dump_v2.json` — fuente
- `research/synthesis/suite2_diag_d1_results.json` — D1 raw
- `research/synthesis/suite2_diag_d2_results.json` — D2 raw (con world context)
- `research/synthesis/suite2_diag_d2a_no_world_context_results.json` — D2a (variable grounding test)
- `research/synthesis/suite2_diag_d4_results.json` — D4 raw (equivalence)
- `research/synthesis/suite2_stage1_split.json` — stage1 sub-modes
- I-026 — recipe exemplars (este doc informa su diseño)
- I-027 — baseline hygiene (closed except item 7)
- I-028 — sweep_values schema violation
- I-029 — compiler abstain decision broken (nuevo)
