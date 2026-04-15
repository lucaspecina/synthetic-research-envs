# Suite 2 — Compiler Improvement Strategy

> **Status:** CANON plan de ataque al recipe gap del claim compiler.
> **Date:** 2026-04-15.
> **Context:** baseline v2 estable (`suite2_compiler_baseline.md` §9),
> effective_pass_rate = 31%, strict_full_pass_rate = 13%, 5 familias en
> 0% strict pass. Qué hacer ahora y cómo medir el progreso.
> **Related:** I-026 (recipe exemplars), I-027 (baseline hygiene), I-028
> (sweep_values bug).

## TL;DR

El bottleneck del compiler es **recipe gap duro**: el LLM reconoce el
patrón por vocabulario pero no sabe componer el spec. No es capability
ceiling — es falta de recipes operacionales en el prompt.

Antes de atacar con exemplars (I-026), nos faltan **6 diagnostics
específicos** que aíslan mejor el problema. D4 (equivalence formal de
adjust-swap) es **gratis** y solo subiría `strict_full_pass_rate` de
13% → 31% si se sostiene. Es la primera acción obligatoria.

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

### Recomendación primera acción: **#3 primero, después #1**

- **#3 es gratis** (ver §3 diagnostic D4) y solo formalizar — si la
  equivalencia se sostiene empíricamente sobre los 10 `adjust_swap`
  observados, ya subimos strict_pass de 13% → 31% sin tocar el LLM.
- **#1 (exemplars)** ataca las 5 familias 0%-pass con evidencia concreta
  del A/B/C test. Pero antes necesita el diagnostic battery (§3) para
  no overfitear.

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

## 7. Próximos pasos concretos

1. **Correr D4** (0 LLM calls) — `scripts/suite2_diag_d4_adjust_swap_equivalence.py`.
2. Según resultado D4 → implementar `alternative_atoms` o investigar edge cases.
3. **Correr D1 + D2** (aislación recognition vs composition) —
   definen la forma de los exemplars.
4. Iterar I-026 con exemplars diseñados a partir de D1+D2.
5. Re-run baseline v2 script para medir strict_pass y effective_pass
   después del cambio.
6. Documentar hallazgos en un `suite2_compiler_improvement_findings.md`
   (sucesor de este doc, o §8 acá).

## Links

- `research/synthesis/suite2_compiler_baseline.md` §9 — baseline v2
- `research/synthesis/suite2_pattern_breakdown.md` — per-family bucket counts
- `research/synthesis/suite2_fail_audit_recipe_patterns.md` — audit #11a
- `research/synthesis/compiler_baseline_full_dump_v2.json` — fuente para D4
- I-026 — recipe exemplars (este doc informa su diseño)
- I-027 — baseline hygiene (closed except item 7)
- I-028 — sweep_values schema violation
