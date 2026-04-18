---
id: 2
title: Credit-assignment — unit-level truth scoring (P2)
status: open
type: task
lane: scoring
priority: next
created: 2026-04-10
related: [I-001, I-003]
origin: TODO:I0d/P2
---

# I-002: Credit-assignment — unit-level truth scoring

## Status
- **Estado:** disenado, no implementado
- **Ultimo resultado:** A28 audit confirma que microbiome (0.196) es el caso
  emblematico — claims correctas pierden contra claim generica
- **Proximo paso:** implementar paso 1 (threshold para matched)

## Pregunta
El scoring calcula truth a nivel claim (promedio de todos los specs). Esto
penaliza claims ambiciosas con muchos specs y favorece claims genericas.

**Secuencia de cambios (uno a la vez):**
1. **Threshold para matched** — hoy `best_score > 0` infla coverage.
   Definir threshold minimo (ej: 0.15)
2. **Unit-level truth x relevance** — cambiar unidad de scoring de claim
   a CompiledUnit. Requiere resumen semantico por unit.
3. **Penalizacion por reuso** (solo si paso 1+2 no bastan) — marginal
   gain decreciente

**Path target:** `oi_runner._score_with_judge` + `rescore.py::_aggregate_score`

**Evidencia:** `research/notes/open_investigation_case_analysis.md` (A28
audit, caso microbiome)
