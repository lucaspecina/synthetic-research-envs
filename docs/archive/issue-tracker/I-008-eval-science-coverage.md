---
id: 8
title: Eval suite — science coverage
status: open
type: task
lane: eval
priority: next
created: 2026-04-10
related: [I-006, I-007, I-009]
origin: eval_suite_science_coverage.md
---

# I-008: Eval suite — science coverage

## Status
- **Estado:** diseno detallado en eval_suite_science_coverage.md, no implementado
- **Ultimo resultado:** 23 escenarios de investigacion definidos en
  investigation_scenarios_rubric.md
- **Proximo paso:** definir gold_answer offline por caso, implementar harness

## Pregunta
Mapa de alcance cientifico del sistema: que tipos de preguntas SREG puede
representar/resolver hoy, y cuales no.

**Scope:**
- Que tipos de investigacion se pueden representar como SCM + SQs
- Que tipos de claims el compiler puede compilar
- Que tipos de verificacion el verifier puede ejecutar
- Fronteras: que queda fuera (prediction, optimization, temporal, etc.)

**gold_answer debe venir del mundo/oracle/manual offline, no del pipeline.**
Foco: recall / cobertura / fronteras del sistema.

**Referencia:**
- `research/synthesis/eval_suite_science_coverage.md`
- `research/synthesis/investigation_scenarios_rubric.md` (23 escenarios)
