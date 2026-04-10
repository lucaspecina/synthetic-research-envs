# S06 -- SubQuestionIntent architecture: research for the agenda

**Date:** 2026-03-30
**Type:** Research / architectural proposal
**Branch:** autoresearch-open-investigation
**Status:** PROPUESTA PARA DISCUSION
**Prerequisitos:** S04, S05, A23, A24, CURRENT_STATE.md

> Este documento aborda la agenda completa sobre la nueva arquitectura de
> SubQuestionIntent -> AtomicSpec. No es solo un analisis -- propone contratos,
> decisiones y un primer experimento.

---

## 1. Target architecture

### Estado actual (lo que S05 ya fijo)

El paso pattern + roles + ask es el cuello de botella documentado.
El pipeline actual: seed -> SQ intents (pattern+roles+ask) -> ClaimIntent
candidatos -> lower_intent() -> AtomicSpec(s) -> verify.

### Arquitectura propuesta

seed + brief + orchestrator context -> SubQuestionIntent v2
(text_gloss + verification_specs) -> AtomicSpec(s) directos -> verify
contra SCM -> ResolvedSubQuestion.

Los cambios clave:

1. El orchestrator genera SQs con dos caras: una legible (text_gloss) y
   una verificable (verification_specs -- lista de AtomicSpec).
2. No hay paso intermedio de ClaimIntent para las SQs. El orchestrator (o
   un compile step inmediato) baja directamente a atoms.
3. El matching claim-vs-SQ opera sobre specs, no sobre patterns.

### Que pasa con pattern

pattern desaparece de SubQuestionIntent como campo obligatorio. Se mantiene
opcionalmente como pattern_hint: str | None para fast-path del compiler,
logging/diagnostico, y compatibilidad con SQs ya generadas. Pero NO
participa en scoring ni en matching.

Razon: S05 ya demostro que 10/10 experimentos convergen a los mismos
patterns cuando pattern es obligatorio.

---

## 2. Nuevo contrato de SubQuestionIntent

### Pregunta previa: que describe una SQ

> SubQuestionIntent describe una pregunta, una incertidumbre o una
> necesidad de evidencia?

**Respuesta propuesta: una necesidad de evidencia verificable.**

No es una pregunta en NL (eso es text_gloss). No es una incertidumbre
abstracta (no sabemos verificar incertidumbre). Es: para considerar
cubierta esta dimension de la investigacion, necesitamos que al menos
una claim del solver sea consistente con estas verificaciones.

Implicacion: la SQ no dice investiga X. Dice si investigaste X
correctamente, deberia haber evidencia verificable de estas cosas.

### Campos minimos

    sq_id: str
    text_gloss: str                      # legible, libre, para humanos
    verification_specs: list[AtomicSpec]  # 1..N atoms verificables
    tier: SQTier = SQTier.HIGH           # weight: high/medium/low
    acceptance_rule: AcceptanceRule = AcceptanceRule.ANY_OF
    pattern_hint: str | None = None      # legacy compat / diagnostico
    focus_variables: tuple[str, ...] = () # para matching rapido
    rationale: str | None = None         # por que esta SQ importa

### Que expresa semanticamente

1. text_gloss -- descripcion humana. Sin restriccion de formato.
2. verification_specs -- definicion formal de cubierto. Cada atom dice
   que simular, que medir, que comparar y que afirmar.
3. tier -- importancia relativa (high/medium/low).
4. focus_variables -- variables centrales. Para pre-filtrar, NO para scoring.

### Que cosas ya no debe forzarse a clasificar

1. No mas pattern obligatorio. SQs descriptivas/epistemologicas no encajan.
2. No mas roles como estructura fija (SQRoles con treatment/outcome etc
   asume estructura causal que muchas SQs no tienen).
3. No mas ask como enum fijo (existence/sign/magnitude/rank_order no cubre
   identificabilidad, heterogeneidad entre subgrupos, sensibilidad al ajuste).
   Lo que se pregunta queda en los verification_specs.

### Ejemplo: SQ epistemologica

Brief: Assess whether the causal interpretation is defensible

Hoy (v1): Se reduce a causal_effect + existence_and_sign. Pierde todo lo
epistemologico.

Propuesta (v2): Tres atoms -- identifiability_check (es identificable el
efecto?), correlacion cruda (hay asociacion?), partial_correlation ajustada
(cambia al controlar confounders?). Una claim de sensibilidad al ajuste
ahora puede matchear esta SQ.

### Ejemplo: SQ descriptiva

Brief: What usage profiles exist in the population?

Hoy: no representable. Se forzaria a causal_effect o effect_ranking.
Propuesta: atoms de varianza y correlacion. No es causal, no tiene
treatment/outcome, pero es verificable contra el SCM.


---

## 3. Compilacion: como un intent produce specs

### La unidad de compilacion

La unidad es 1 intent -> N AtomicSpecs? Si, pero con matices.

Para SQs: los specs ya vienen en el intent. No hay compilacion en
runtime -- hay validacion y resolucion contra el SCM.
Para claims del solver: la compilacion sigue siendo 1 ClaimCard ->
N AtomicSpecs, pero ahora puede ir directo a atoms (sin PatternClass).

### Dos caminos de generacion de specs para SQs

Camino A: el orchestrator los genera directamente.
S04 demostro que gpt-5.4 genera specs validos (65/65). Riesgo: carga
cognitiva del orchestrator (ya hace mucho).

Camino B: el orchestrator genera SQs libres, un compile step las baja.
Separacion de concerns. El orchestrator se enfoca en que investigar,
el compilador en como verificar.

Recomendacion: empezar con Camino B. Menos riesgoso, permite iterar
sin tocar el orchestrator.

### Esquema del compile step

SQ raw (text_gloss + focus_vars + pattern_hint + tier)
-> compile_sq_to_specs(sq, world, summary)
-> SQ full (con verification_specs)
-> verify contra SCM
-> ResolvedSubQuestion

### Invariantes del compile step

1. Toda SQ debe producir al menos 1 spec valido.
2. Los specs deben usar solo variables del mundo.
3. Los specs deben ser ejecutables por el verifier.
4. Los specs deben ser relevantes al text_gloss.

### Relevancia al seed: donde se valida

1. En el orchestrator prompt (SQs nacen del seed).
2. En validate_sub_questions() (variables existen en el mundo).
3. En el compile step (specs usan variables del focus).

NO se hace chequeo semantico profundo (LLM-as-judge).

---

## 4. Matching claim-vs-SQ sobre specs

### El cambio fundamental

Hoy: structural_compatibility(claim_repr, sq_repr) compara family,
operator y roles via tablas. Todo pasa por PatternClass.

Nuevo: claim y SQ bajan a AtomicSpecs. Matching compara specs vs specs.

### Propuesta de matching

spec_match(claim_spec, sq_spec) =
    variables_overlap * measurement_compat * assertion_compat

claim_satisfies_sq(claim_specs, sq_specs) =
    max over sq_spec:
        max over claim_spec:
            truth(claim_spec) * spec_match(claim_spec, sq_spec)

Mas granular que pattern matching. No clasifica -- compara verificaciones.

Ventaja clave: un claim de sensibilidad al ajuste (partial_correlation +
contrast_diff) puede matchear una SQ epistemologica que tiene un spec de
partial_correlation. Hoy no puede, porque sensibilidad al ajuste no es
un PatternClass.


---

## 5. Relevancia sin taxonomia rigida

Tres mecanismos:

### 5.1 Relevancia por construccion
El orchestrator genera SQs a partir del seed. La diversidad viene del seed,
no de un catalogo. Esto ya es la posicion de S05.

### 5.2 Relevancia por variable overlap
Una claim es relevante a una SQ si toca las mismas variables. Filtro
mecanico rapido. No clasifica -- filtra.

### 5.3 Relevancia por spec compatibility
Medicion y asercion compatibles. No necesita saber si el caso es causal o
descriptivo. Solo compara specs.

---

## 6. Metricas para el primer experimento

### Diversidad de specs
Metric: unique_measurement_kinds per episode. Fraccion del espacio de
MeasurementKind usada. Si el pipeline viejo genera SQs que solo implican
mean y correlation, y el nuevo genera mean, correlation,
partial_correlation, identifiability_check, variance -- eso es diversidad.

### Relevancia de specs
Metric: spec_variable_coverage. Interseccion de variables en specs con
variables del brief.

### Coverage delta
Mismo solver, mismos claims. Cuantas SQs cubre el pipeline viejo vs nuevo.
Si coverage baja porque SQs son mas ricas, no es fallo -- es evidencia de
que el solver tambien necesita liberarse.

### Lo que NO medimos
- Calidad del solver (el experimento es sobre SQs).
- Score final del episodio (no hay scoring v3).
- Precision del compiler de claims (no cambia).

---

## 7. Diseno del primer experimento

### Setup

Seeds: las 14 de S05 (diversidad intencional: causal, predictivo,
epistemologico, system mapping, selection bias, competing mechanisms,
policy equity, value of information, methodology, descriptivo, tradeoff,
deep heterogeneity).

Pipeline viejo: SQs actuales (pattern+roles+ask). Datos de S05.
Pipeline nuevo: SQs v2 (text_gloss + verification_specs).

### Que se mide

- unique_patterns: patterns usados (diversidad de tipo)
- unique_measurement_kinds: kinds de medicion (diversidad de verificacion)
- unique_assertion_kinds: kinds de asercion (diversidad de verificacion)
- specs_per_sq: N directo vs 1 via lower_intent (riqueza)
- spec_validity: porcentaje ejecutables (calidad del compilador)
- variable_relevance: vars en specs vs brief (relevancia al seed)
- clustering_entropy: P(measurement_kind) (anti-monocultura)

### Criterio de exito

1. unique_measurement_kinds > 3 por episodio.
2. spec_validity > 90%.
3. variable_relevance > 0.80.
4. clustering_entropy mayor en pipeline nuevo.
5. Diversidad cualitativa confirmada en 3-5 casos.

### Lo que NO es criterio de exito

Coverage del solver, score final, precision del compiler de claims.

---

## 8. Preguntas abiertas

1. Como genera el orchestrator los specs? Empezar con compile step offline
   (opcion a). El orchestrator emite text_gloss + focus_variables y un
   script Python compila a specs.
2. Granularidad del matching spec-vs-spec. Calibrar despues del primer exp.
3. Aggregacion del score con N specs por SQ. Propuesta preliminar: fraccion
   de specs de la SQ cubiertos por specs del claim con truth > 0.
4. Sanity check para specs absurdos del LLM.

---

## 9. Ruta de implementacion minima

Paso 1: Modelo de datos SubQuestionIntentV2 (1-2h).
  No tocar SubQuestionIntent actual -- coexisten.
Paso 2: Compile step compile_sq_to_specs() (2-4h).
  LLM-based, valida specs ejecutables, fast-path para patterns comunes.
Paso 3: Post-procesamiento design_case v1->v2 (1-2h).
  Orchestrator genera v1, se convierte a v2 via compile step.
Paso 4: Script de comparacion (2-3h).
  Similar a compare_compilers.py de S04.

Total estimado: 6-11 horas de implementacion.

---

## Conexiones

- S04 -- evidencia empirica de compilacion directa a AtomicSpec
- S05 -- diagnostico de diversidad de SQs (10/10 causualizados)
- A23 -- propuesta original de grammar-first
- A24 -- horizonte de mediano plazo (runtime de validators)
- CLAUDE.md -- UN solo metodo, el sistema se adapta, brief libre
- PROJECT.md -- invariantes de scoring

---

## Resumen ejecutivo

| Agenda item | Propuesta |
|-------------|-----------|
| Target architecture | seed -> SQ (text_gloss + verification_specs) -> AtomicSpecs -> verify |
| Pattern | Desaparece obligatorio. Queda pattern_hint informativo |
| SubQuestionIntent v2 | text_gloss + verification_specs + tier + focus_variables |
| Que describe una SQ | Una necesidad de evidencia verificable |
| Compilacion | 1 SQ -> N AtomicSpecs via compile step (LLM-based) |
| Relevancia | Construccion + variable overlap + spec compatibility |
| Metrica principal | unique_measurement_kinds + spec_validity + variable_relevance |
| Primer experimento | 14 seeds, SQs v1 vs v2, diversidad/relevancia, no scorer |
