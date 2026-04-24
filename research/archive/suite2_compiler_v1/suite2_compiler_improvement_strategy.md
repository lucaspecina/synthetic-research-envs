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
| Recipe knowledge — **arm_kinds** | **50%** (bottleneck agregado). Split (§7.7): `single_causal` 79%, `multi_atom` 75%, `single_observational` **0/12**, `single_contrast_causal` **0/3**, `single_sweep` **0/3**. |
| adjust_swap formalization | Upper bound 13→**24%** (no 31%). |
| **Taxonomy consistency (arm.kind)** | **Contract bug** (§7.6): `baseline`/`observe` aliased inconsistentemente en 3 fuentes; `condition.values` documentado pero ignorado por verifier. **Prereq de Rama C** (I-030). |
| **Cardinality (n_atoms)** | Hipótesis Codex refutada (§7.7 F7): 0/4 multi-atom collapse; opposite (10/45 single→multi raise). **No es blocker.** |

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

### 7.7 D2 split analysis — arm_kinds bottleneck atribución (0 LLM calls)

**Motivación.** D2 overall arm_kinds = 50%. Pero 50% uniforme vs 50% por
dos modos muy distintos tiene implicancias opuestas para Rama C. Codex
hipotetizó cardinality (multi-atom collapse) como driver secundario.
Split el JSON de D2 por gold.n_atoms y por tipo de claim para refutar/
confirmar la hipótesis y targetizar exemplares.

Script: `scripts/suite2_diag_d2_split_analysis.py`. Output:
`suite2_diag_d2_split_results.json`.

**F7 — Cardinality collapse REFUTADA.**

| Split | multi_atom_total | collapsed → 1 | kept multi | single_raised → multi |
|---|---|---|---|---|
| Valor | 4 | **0** | 4 | 10 |

El compiler mantiene el n_atoms correcto en 100% de los 4 multi-atom
golds. El error **opuesto** es más frecuente: 10/45 single-atom golds
se predicen como multi-atom (split artificial). La hipótesis "exemplares
Rama C deben enseñar bundle cardinality" es **rechazada** por los datos.
Cardinality no es blocker secundario.

**F8 — Arm_kinds bottleneck atribuido 100% a 3 buckets de claim:**

| Bucket (gold) | n | arm_kinds acc | misses |
|---|---|---|---|
| `single_causal` (sola `[intervene]`) | 28 | **79%** | 6 |
| `multi_atom` | 4 | **75%** | 1 |
| `single_observational` (kinds ⊆ {baseline, observe, condition}) | 12 | **0%** | 12 |
| `single_contrast_causal` (≥2 kinds con `intervene`, e.g. `[intervene, observe]`) | 3 | **0%** | 3 |
| `single_sweep` | 3 | **0%** | 3 |

→ **El 50% agregado esconde dos regímenes.** El compiler es
razonablemente bueno (75-79%) en los modos que domina (intervene puro y
multi-atom) y **completamente ciego** (0/18) en los otros tres.

**F9 — F8 valida F1 empíricamente.**

- `single_observational=0/12` es exactamente lo que predice F1: 3 voces
  contradictorias sobre cuándo usar `baseline` vs `observe` vs
  `condition`. Sin spec unificada, el LLM no converge en ninguno.
- `single_contrast_causal=0/3` también depende de la misma decisión —
  el segundo arm del par `[intervene, observe]` es el "observe" del
  confounding contrast.
- `single_sweep=0/3` es caso aparte: no hay exemplares ni definición
  clara de cuándo "vary X" en la claim dispara sweep vs intervene
  múltiples.

**Implicancia para Rama C (scope reducido).** Los exemplares NO deben
cubrir arm_kinds en general. Deben targetizar:
- **12 `single_observational`** (post I-030, spec unificada): recipe
  discriminatorio baseline vs observe vs condition según measurement y
  tipo de filter.
- **3 `single_contrast_causal`**: recipe del par intervene+observe para
  confounding detection (CC-A5 y similar).
- **3 `single_sweep`**: recipe sweep explícito + cuándo no usarlo.

Total: 18/46 single-atom claims. Si C levanta esos 18 al 70%+ (y
single_causal se queda al 79%), arm_kinds overall sube a
`(28·0.79 + 4·0.75 + 18·0.70) / 50 ≈ 76%`. Objetivo realista post-I-030
+ Rama C focused.

**Hint secundario de F7 (single → multi raising).** 10/45 single-atom
golds se predicen multi. No es el blocker primario pero sugiere que el
prompt actual over-segmenta. Documentar; no priorizar.

### 7.8 D2 × verdict zipper — slot-fail → verdict-fail attribution (0 LLM calls)

**Motivación.** D2 elicitation da arm_kinds 50% agregado pero no dice si
los slot-fails **son los que causan** los verdict-fails del baseline v2.
Join por `id` de `suite2_diag_d2_results.json` × `compiler_baseline_full_dump_v2.json`
para cruzar bucket de baseline (full_pass / adjust_swap / verdict_wrong /
real_struct_err / stage1_fail) × per-slot match de D2.

Script: `scripts/suite2_diag_d2_verdict_zipper.py`. Output:
`suite2_diag_d2_verdict_zipper.json`.

**Per-bucket slot accuracy (cross-tab):**

| bucket | n | status | n_atoms | arm_kinds | role_vars | measurement | comparison | assertion |
|---|---|---|---|---|---|---|---|---|
| full_pass | 7 | 71% | 83% | **17%** | 83% | 67% | 83% | 83% |
| adjust_swap | 10 | 100% | 100% | **100%** | 100% | 90% | 100% | 100% |
| verdict_wrong | 19 | 100% | 68% | **42%** | 95% | 79% | 42% | 47% |
| real_struct_err | 13 | 100% | 69% | 46% | 100% | 54% | 69% | 62% |
| stage1_fail | 6 | 67% | 100% (n=2) | 0% (n=2) | 100% | 100% | 100% | 100% |

**F10 — `adjust_swap` es composition bug puro, NO recognition bug.**

Los 10 casos de `adjust_swap` tienen:
- **D2 arm_kinds = 100%** (el LLM elicita `[intervene]` correcto)
- **9/10 con 0 slots D2 mal** (solo un CC-A1 tiene measurement_kind 1-miss)

Cuando el compiler escribe la spec completa (Flow A `compile_claim_direct`),
pone `adjust`. Cuando se le pregunta por slot por separado, pone `intervene`.
**Recognition OK, synthesis broken.** Este es el patrón textbook de
composition-gap predicho por D1-vs-D2 (§7.3 + §7.4) manifestado en datos
del baseline.

→ Rama B (adjust-swap formalization) tiene **evidencia directa**: no hace
falta enseñarle que `adjust` ≠ `intervene` en el prompt a nivel lexical;
hace falta arreglar la composición (exemplar showing "when gold=intervene,
write intervene, don't collapse to adjust").

**F11 — Inversión `full_pass` vs `adjust_swap` en arm_kinds.**

| Bucket | D2 arm_kinds | Interpretación |
|---|---|---|
| `full_pass` (7 compiled OK) | **17%** (5/6 misses) | Compile_direct acertó, D2 falla |
| `adjust_swap` (10 compiled mal) | **100%** | Compile_direct falló, D2 acierta |

Las dos vías divergen en direcciones opuestas. Hipótesis:
- Los full_pass del baseline son mayormente causales (CC-A1 single_causal
  con `[intervene]` gold) donde D2 sufre la inconsistencia F1 y elicita
  `[observe]` o `[baseline]`.
- Los adjust_swap son justamente los casos donde compile_direct tiene su
  bias propio a `adjust`, independiente del slot elicitation.

**Implicancia: D2 y Flow A tienen biases ORTOGONALES.** No se puede
tratar D2 como "ground truth sobre capability del LLM". Es una elicitación
con su propio bias (el prompt de D2 enseña `[observe]` para claims
asociacionales, lo cual es consistente con verifier pero inconsistente
con Flow A actual). Post I-030 + sync del D2 taxonomy block, esta
divergencia debería cerrarse.

**F12 — `verdict_wrong` es multi-fault.**

Distribución de n_slots_wrong en D2 para los 19 verdict_wrong:

| n_slots_wrong | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| count | 2 | 4 | 4 | 5 | 4 |

Promedio ≈ 2.4 slots mal por caso. Los tres slots que más concentran los
misses en este bucket:
- `arm_kinds` (11/19)
- `comparison_kind` (11/19)
- `assertion_polarity` (10/19)

→ Rama C (exemplars) **no debería targetizar solo arm_kinds**. Los
exemplares deben mostrar la **spec completa bien formada** (con
comparison y assertion coherentes), no slots aislados. Este es input
directo para el diseño de exemplares en I-026.

**F13 — D2 como oracle: ruidoso, no limpio.**

6 de 7 `full_pass` (casos que compilaron PERFECTO según el verifier)
tienen ≥1 slot D2 mal. Esto descalifica D2 como "proxy de capability
máxima del LLM". D2 es una elicitación con un prompt específico que
tiene su propio bias. Interpretación correcta:
- D2 captura **la probabilidad de que el LLM, en modo recognition
  guiado, elija el slot correcto**, dado el prompt actual.
- No captura **la capability máxima del LLM bajo compile_direct**.
- El verdadero oracle es el baseline v2 full_pass set (aún con ruido
  del seed).

**Implicancia para el plan.** Cuando post-fix midamos el delta:
- Target primario: arm_kinds accuracy en **`suite2_full_dump_v2.py` re-run**
  (no en D2).
- Target secundario: D2 sync (cuando I-030 aplique a `suite2_diag_d2_recipe_slots.py:112`,
  el D2 arm_kinds debería subir por la simple sincronización del bloque
  taxonómico del prompt, sin tocar el compiler).

**Síntesis del zipper.**

1. Adjust_swap = composition (F10) → Rama B validada.
2. Observacional single-arm = F1/F9 (taxonomy) → Rama A (I-030) valida fix.
3. verdict_wrong multi-fault (F12) → exemplares deben enseñar spec
   completa, no slot aislado.
4. D2 es proxy ruidoso (F13) → medir delta post-fix con full_dump_v2,
   no con D2.

### 7.9 D1 × D2 joint-failure matrix (0 LLM calls)

**Motivación.** D1 mide recognition (family), D2 mide composition (slots),
pero ¿son la misma habilidad? Join los 3 datasets (D1 × D2 × baseline)
para construir 2×2 y cuantificar ortogonalidad.

Script: `scripts/suite2_diag_d1_d2_joint_matrix.py`. Output:
`suite2_diag_d1_d2_joint_results.json`.

**Marginals.** D1 pass=38/55 (69%), D2-critical pass=27/55 (49%),
D2-strict pass=14/55 (25%). Las tres métricas divergen mucho; no es
una única escala de "capability".

**Matriz A — D1 × D2-critical (arm_kinds match):**

|  | D2-crit pass | D2-crit fail | total |
|---|---|---|---|
| D1 pass | 22 | 16 | 38 |
| D1 fail | 5 | 12 | 17 |
| total | 27 | 28 | 55 |

φ = 0.26 (correlación positiva leve).

**Matriz B — D1 × D2-strict (todos los 7 slots match):**

|  | D2-strict pass | D2-strict fail | total |
|---|---|---|---|
| D1 pass | 9 | 29 | 38 |
| D1 fail | 5 | 12 | 17 |
| total | 14 | 41 | 55 |

φ = −0.06 (esencialmente **ortogonal**).

**F14 — D1 ⟂ D2-strict (φ=−0.06); acople leve con D2-critical (φ=0.26).**

Recognition (family) y composition-completa (los 7 slots) son
habilidades **independientes** sobre esta suite. Con D2-critical
(arm_kinds match) hay acople POSITIVO leve — reconocer family ayuda
un poco a acertar arm_kinds, pero no es predictivo. NO se puede decir
"si mejoramos recognition, mejora composition-completa"; sí hay
transferencia chica a arm_kinds específicamente.

**F15 — `adjust_swap` confirma F10 a nivel matricial.**

Los 10 adjust_swap se reparten: 6 en `D1-pass+D2-crit-pass`, 4 en
`D1-fail+D2-crit-pass`. **100% en la columna D2-crit pass** (el LLM
SIEMPRE elicita arm_kinds correcto en D2). Cuando compile_direct
compone la spec entera, pone `adjust`. Confirma F10 y agrega:
4 adjust_swap tienen D1 fail (no reconocen family) pero D2 arm_kinds
OK (el prompt guiado compensa el fallo de recognition a nivel slot).

**F16 — F13 confirmado con fuerza matricial.**

Los 7 `full_pass` (casos que compilaron perfecto) se reparten:
1 en `D1-pass+D2-crit-pass`, **5 en `D1-pass+D2-crit-fail`**, 1 en
`D1-fail+D2-crit-fail`. **5 de 7 pasaron el verifier pero en D2 el
arm_kinds falla.** D2 no es ground truth: el prompt de D2 tiene su
propio bias, y los "capability-max" targets vienen de full_dump_v2
full_pass, no de D2.

**F17 — `verdict_wrong` sorprendentemente disperso.**

Los 19 verdict_wrong se reparten **casi uniformemente** entre
cuadrantes: 7 en `D1-pass+D2-pass`, 7 en `D1-pass+D2-fail`, 1 en
`D1-fail+D2-pass`, 4 en `D1-fail+D2-fail`. **7 están en `D1-pass+D2-pass`**
— el LLM reconoce family Y elige slots correctamente (arm_kinds), pero
ASÍ Y TODO la spec final está mal.

→ Hay un **tercer nivel de fallo** más fino: valores numéricos,
`cond_set`, `adjust_set`, `condition_on`, que ni D1 ni D2 capturan.
Los exemplares de Rama C deben enseñar no solo qué slot elegir sino
los detalles completos de la spec.

**F18 — Composition-gap cell: top slots que rompen.**

Celda `D1-pass + D2-crit-fail` (n=16, el bloque principal de
composition-gap): top slot misses =
- arm_kinds: 14
- comparison_kind: 8
- assertion_polarity: 6
- measurement_kind: 6

Coincide con F12. **Los 4 slots principales de composition-gap son
los mismos que dominan verdict_wrong.** Los exemplares deben
targetizar los 4 conjuntamente, no solo arm_kinds.

**F19 — `D1-fail + D2-pass` es bloque REAL, no anecdótico (n=5).**

4 adjust_swap + 1 verdict_wrong. El prompt guiado de D2 logra que el
LLM elicite arm_kinds correcto pese a no reconocer la family. Sugiere
que el prompt de Flow A podría beneficiarse de una mini-scaffolding
equivalente al bloque taxonómico de D2 (una vez unificado post I-030).

**F20 — `D1-pass + D2-pass + baseline-FAIL` (n=13/22).**

De los 22 casos con D1 pass Y D2-critical pass, **13 (59%) fallan el
baseline**: 6 real_struct_err, 6 adjust_swap, 7 verdict_wrong, 2
stage1_fail, 1 full_pass. **D1 y D2 son proxies insuficientes para
predecir compile success.** Incluso con recognition + critical
elicitation OK, compile_direct falla 59% de las veces. El error
vive en composition completa de la spec (detail binding, valores,
cond_set, adjust_set) — zona que ni D1 ni D2 prueban.

**Follow-up sugerido (no blocker, post-merge).** Diagnóstico acotado
D8 solo sobre los 13 targets de este cuadrante: reconstrucción de
spec completa contra `full_dump_v2` para aislar si el fallo es
detail-binding, serialization, o prompt-flow del compile_direct.
Scope chico (~13 LLM calls), alto valor. Tracked como follow-up
explícito, no como blocker del merge.

**Síntesis del joint matrix.**

1. Recognition ≠ composition (F14 ortogonales) — fix de uno no implica
   fix del otro. Ramas A/B/C atacan targets distintos, no apilados.
2. adjust_swap es composition-pure (F15) — Rama B es necesaria y
   suficiente para ese bucket.
3. D2 no es oracle (F16) — target primario post-fix es full_dump_v2,
   D2 como secundario.
4. verdict_wrong tiene fallos "ocultos" en D1+D2 pass (F17, F20) — los
   exemplares deben enseñar spec completa incluso en casos que
   "parecen OK" a nivel recognition + slot.
5. Los 4 slots que dominan composition-gap (F18) son el set que los
   exemplares I-026 deben cubrir conjuntamente.
6. D2 prompt taxonomy bloque es efectivo (F19) — una vez unificado
   post I-030, es candidato para inyectar scaffolding similar en
   Flow A.

### 7.10 D2 per-family × per-slot (input directo para I-026)

**Motivación.** La vista agregada per-family del §7.4 suma match/total
sobre slots, lo que oculta qué slot específico rompe en qué family. Para
diseñar exemplares I-026 targeting-exact, hace falta cruzar family × slot
+ bucket mix + failure rate.

Script: `scripts/suite2_diag_d2_per_family_slots.py`. Output:
`suite2_diag_d2_per_family_slots.{json,md}`. Orden: peor weakest-slot
primero, tie-break por n_targets desc.

| family | n | status | n_atoms | arm_kinds | role_vars | meas_kind | comp_kind | assert | top-2 weak | fail rate | bucket mix |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CC-A2 | 5 | 100% | 60% | **0%** | 100% | 0% | 100% | 80% | `arm_kinds` 0%, `measurement_kind` 0% | 80% | real_struct_err=4, full_pass=1 |
| CC-A4 | 3 | 100% | 33% | **0%** | 100% | 100% | 0% | 33% | `arm_kinds` 0%, `comparison_kind` 0% | 100% | verdict_wrong=3 |
| CC-A5 | 3 | 100% | 100% | **0%** | 100% | 0% | 0% | 33% | `arm_kinds` 0%, `measurement_kind` 0% | 100% | verdict_wrong=3 |
| CC-B5 | 3 | 100% | 100% | **0%** | 100% | 100% | 100% | 100% | `arm_kinds` 0%, `n_atoms` 100% | 100% | stage1_fail=2, verdict_wrong=1 |
| CC-E2 | 3 | 66% | 66% | **0%** | 66% | 66% | 66% | 33% | `arm_kinds` 0%, `assertion_polarity` 33% | 33% | full_pass=2, verdict_wrong=1 |
| SQ-A1 | 3 | 100% | 100% | **100%** | 100% | 100% | 100% | 0% | `assertion_polarity` 0%, `n_atoms` 100% | 100% | real_struct_err=3 |
| CC-D2 | 2 | 100% | 100% | **0%** | 100% | 0% | 0% | 0% | `arm_kinds` 0%, `measurement_kind` 0% | 100% | real_struct_err=1, verdict_wrong=1 |
| SQ-A3 | 2 | 100% | 100% | **0%** | 100% | 100% | 100% | 100% | `arm_kinds` 0%, `n_atoms` 100% | 0% | full_pass=2 |
| CC-A7 | 2 | 100% | 100% | **50%** | 100% | 100% | 50% | 0% | `assertion_polarity` 0%, `arm_kinds` 50% | 100% | verdict_wrong=2 |
| CC-A3 | 8 | 100% | 37% | **75%** | 87% | 100% | 37% | 87% | `n_atoms` 37%, `comparison_kind` 37% | 100% | verdict_wrong=5, real_struct_err=3 |
| CC-A8 | 2 | 100% | 50% | **100%** | 100% | 100% | 100% | 100% | `n_atoms` 50%, `arm_kinds` 100% | 50% | full_pass=1, real_struct_err=1 |
| CC-C2 | 3 | 100% | 100% | **66%** | 100% | 66% | 66% | 100% | `arm_kinds` 66%, `measurement_kind` 66% | 100% | adjust_swap=2, real_struct_err=1 |
| CC-A1 | 9 | 100% | 100% | **100%** | 100% | 88% | 100% | 88% | `measurement_kind` 88%, `assertion_polarity` 88% | 100% | adjust_swap=6, verdict_wrong=3 |
| CC-D1 | 2 | 100% | 100% | **100%** | 100% | 100% | 100% | 100% | `n_atoms` 100%, `arm_kinds` 100% | 100% | adjust_swap=2 |
| CC-E3 | 2 | 50% | — | — | — | — | — | — | — | 100% | stage1_fail=2 |
| SQ-C1 | 2 | 0% | — | — | — | — | — | — | — | 50% | full_pass=1, stage1_fail=1 |
| CC-E1 | 1 | 100% | — | — | — | — | — | — | — | 100% | stage1_fail=1 |

**F21 — Bloque arm_kinds=0% (7 families, ~21 targets).**

CC-A2, CC-A4, CC-A5, CC-B5, CC-E2, CC-D2, SQ-A3 tienen D2 arm_kinds=0%.
Bucket mix dominado por verdict_wrong + real_struct_err. **Son el
target primario de I-030 + I-026 Rama C.** Si post-fix estos 21 suben
a ≥70%, arm_kinds overall se mueve de 50% a ~75%.

**F22 — CC-A1 y CC-D1: composition-gap puro confirmado a nivel family.**

- **CC-A1** (9 targets): todos los slots D2 ≥88%, fail rate 100%
  (6 adjust_swap + 3 verdict_wrong). El LLM sabe los 7 slots pero
  compile_direct colapsa a `adjust` o rompe detalles.
- **CC-D1** (2 targets): 7/7 slots al 100%, fail rate 100% (2
  adjust_swap). Caso canónico — **Rama B (adjust-swap) tiene que
  fixear específicamente este patrón**.

**F23 — SQ-A1 es el outlier inverso.**

arm_kinds=100%, measurement_kind=100%, comparison_kind=100% — todo bien
excepto `assertion_polarity=0%` (0/3) y todos son real_struct_err.
**El fail es la polaridad, no los arms.** Sugiere que una clase del
bucket real_struct_err se debe a assertion_polarity flipping, no a
estructura. Investigar post-fix (rama independiente, chica).

**F24 — Priorización de exemplars I-026 (derivada directa).**

Orden de impacto por target-count × weakest-slot-severity:

1. **arm_kinds=0% targets (21)**: CC-A2, CC-A4, CC-A5, CC-B5, CC-E2,
   CC-D2, SQ-A3. Exemplars con discriminación baseline/observe/
   condition según measurement + filter predicate (post I-030).
2. **CC-A1 + CC-D1 (11 targets)**: Exemplars anti-`adjust-swap` —
   "cuando gold=intervene, escribir `kind: intervene`, no `adjust`".
3. **CC-A7 + SQ-A1 (5 targets)**: Exemplars con assertion_polarity
   explícita para claims ambigua/contra-intuitivas.

Total targeting: 37/55 (67%) del suite con ~3 exemplars bien elegidos.

### 7.11 TL;DR del diagnostic battery (F1-F24)

Los 24 findings se agrupan en 3 causas raíz atribuidas a fixes
específicos + 1 follow-up:

- **Contract inconsistency (F1-F9, F11, F21)** → atribuido a **I-030**.
  Fix del contrato baseline/observe/condition + sync del D2 taxonomy
  block. Target: 21 targets con D2 arm_kinds=0% (CC-A2, CC-A4, CC-A5,
  CC-B5, CC-E2, CC-D2, SQ-A3).
- **Composition gap puro (F10, F15, F22)** → atribuido a **I-026 Rama B**.
  El LLM reconoce slots (D2 ≥88%) pero compile_direct colapsa a `adjust`
  o rompe detalles. Target: CC-A1 + CC-D1 (11 targets) anti-adjust-swap.
- **Multi-slot composition (F12, F17, F18, F23, F24)** → atribuido a
  **I-026 Rama C**. Exemplars targeting 3 buckets: arm_kinds=0% (21) +
  anti-adjust-swap (11) + assertion-polarity (5 — CC-A7 + SQ-A1) =
  **37/55 (67%) del suite** con ~3 exemplars bien elegidos.
- **Detail-binding black-box (F20)** → follow-up **I-031** (D8 post-fix).
  13 targets donde D1 y D2 pass pero compile_direct falla — fuera del
  alcance de los 3 exemplars. Diagnóstico quirúrgico post-fix.

Además:
- **D2 es proxy ruidoso (F13, F16)** — post-fix medir delta con
  `full_dump_v2`, no con D2. D2 captura recognition guiada, no
  capability del compile_direct.
- **D1 ⟂ D2-strict (F14)** — recognition y composition completa son
  habilidades independientes; el fix tiene targets separados, no
  apilados.

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
