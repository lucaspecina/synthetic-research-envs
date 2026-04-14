---
id: 24
title: SQ↔DAG coherence audit (D1-D3)
status: open
type: research
lane: research
priority: later
created: 2026-04-14
related: [I-007]
origin: research/notes/sq_flow_and_dag_visibility_open_questions.md
---

# I-024: SQ↔DAG coherence audit

## Status
- **Estado:** open question surfaced by Suite 2 baseline (2026-04-14).
- **Ultimo resultado:** identificado que el orchestrator LLM ve el DAG en
  su contexto (porque él lo construyó) pero el prompt NO le fuerza a
  chequear que las SQs emitidas sean estructuralmente coherentes con
  ese DAG.
- **Proximo paso:** decidir si hace falta audit empírico antes de
  diseñar fix.

## Pregunta (D1-D3)

Cuando el orchestrator LLM emite `sub_questions` dentro de `design_case`,
tiene el DAG en su contexto (lo acaba de construir con `scm_construct`).
Pero no hay chequeo explícito de coherencia.

**D1.** ¿El orchestrator emite en la práctica SQs inconsistentes con el
DAG que él mismo construyó? Ejemplo: SQ pregunta "¿X media T→Y?" donde
X no está en ningún camino T→Y del DAG.

**D2.** Si D1 pasa, ¿debería haber un paso de **validación estructural
explícita** post-generación de SQs? Por ejemplo: chequear
deterministicamente que cada SQ sea satisfacible en el DAG antes de
pasarla al SQ compiler.

**D3.** Si D2 aplica, ¿dónde va la validación? Opciones:
- En el orchestrator loop (forzar re-emisión).
- En el SQ compiler (Flow B), que ya tiene el DAG downstream.
- En una etapa nueva de grounding pre-compilación.

## Evidencia hasta hoy

Ninguna — no se verificó sistemáticamente. Hace falta audit sobre SQs
históricas (batch de casos generados) para saber si la incoherencia es
teórica o real.

**Referencia:** `research/notes/sq_flow_and_dag_visibility_open_questions.md` §5.

## Alcance

- Fuera de scope: arreglar el orchestrator. Primero medir.
- Scope propuesto (fase 1): audit sobre ~20 casos generados; contar
  cuántas SQs son estructuralmente incoherentes con su DAG.
- Fase 2 (gated en fase 1): diseñar validación si la tasa de incoherencia
  es material.

## Links
- Suite 2 baseline: `research/synthesis/suite2_compiler_baseline.md`
- Briefing interno: `research/notes/sq_flow_and_dag_visibility_open_questions.md`
- Invariante Flow A vs B: `PROJECT.md` invariante 8
