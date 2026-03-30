# S01 — Compiler Multi-Unit + Claim Diversity

**Fecha:** 2026-03-29
**Branch:** autoresearch-open-investigation
**Status:** EN CURSO
**Codex thread:** 019d3b67-eb81-7201-9151-9aa26e54ac24

## Pregunta de investigacion

Como hacer que el compiler traduzca claims compuestos Y claims no-pair
(system mapping, predictivo, epistemologico, etc.) a verificaciones
ejecutables contra el SCM?

## Hallazgos del debate (pre-empirico)

### H1: Multi-unit es fix tactico, no solucion general
- Multi-unit (1 claim → N unidades verificables) resuelve ~10/20 escenarios
  (los que tienen claims causales compuestos).
- Los otros ~10 escenarios producen claims que NO son pares treatment→outcome:
  "nodo 4 es critico", "hay 3 clusters", "RMSE=4.2", "efecto no identificable".
- Decision: implementar multi-unit como Fase 1, pero no tratarlo como arquitectura final.

### H2: ClaimIntent no puede ser IR universal
- ClaimIntent (8 patterns, 1 treatment, 1 outcome) solo cubre claims causales/asociativos.
- La arquitectura correcta: ClaimIntent como uno de varios "backends de lowering".
- Futuro: backends para structure, identifiability, predictive, etc.

### H3: Solver hints opcionales > solver structured obligatorio
- Obligar al solver a formalizar = form-filling = "juego" (viola principio scoring #4).
- Hints opcionales semanticos (claim_family, assertion_type) = bueno para routing.
- El hint NO debe parecerse a AtomicSpec (no ejecutable, solo semantico).

### H4: CompiledUnit preserva intent→specs
- Bug encontrado por Codex: flattenear specs de N intents pierde mapping.
- Solucion: CompiledUnit(unit_id, intent, specs) dentro de CompilerOutput.
- CompilerOutput sigue 1:1 con ClaimCard (warranty/trace/efficiency keyed por claim_id).

### H5: 3 clases de claims no-pair
1. **Exactificables con nuevos operadores**: identifiability, VOI, structure/paths,
   optimization — el SCM ya tiene la info, solo faltan operadores formales.
2. **Requieren extender formal layer**: predictive protocol, clustering, method comparison
   — necesitan definir train/test, metricas, protocolos.
3. **No core todavia**: demasiado abiertos para reward exacto hoy.

## Experimentos pendientes

### E1: Multi-unit con soil case
- Implementar multi-unit minimo.
- Correr soil case (3/4 ABSTENTION hoy).
- Target: C1 y C3 dejan de ser ABSTENTION, score > 0.

### E2: Coral no-regresion
- Correr coral case con multi-unit.
- Target: score no baja (oversplitting check).

### E3: Probar claim diversity con LLM
- Dar al solver un caso tipo system mapping (#6) o structure discovery (#9).
- Ver que claims produce realmente.
- Evaluar cuantos compila el compiler actual vs cuantos deberia compilar.

## Conclusiones (se actualizan durante la sesion)

(pendiente — se llena con resultados empiricos)
