---
id: 25
title: Flow B LLM prompt — ¿debería incluir el DAG? (D4-D5)
status: open
type: design
lane: research
priority: later
created: 2026-04-14
related: [I-007, I-024]
origin: research/notes/sq_flow_and_dag_visibility_open_questions.md
---

# I-025: Flow B LLM prompt — ¿debería incluir el DAG?

## Status
- **Estado:** open design question surfaced by Suite 2 baseline (2026-04-14).
- **Ultimo resultado:** la política actual ("LLM sin DAG + código con DAG")
  ya produjo al menos un bug documentado (Task #45, P06 G.1: 3/5 reroutes
  con `measurement_finite=0` por adjust_sets inválidos). No queda claro si
  hay más casos escondidos.
- **Proximo paso:** medir antes de debatir. No implementar cambios.

## Pregunta (D4-D5)

El SQ compiler (Flow B) compila texto SQ → AtomicSpecs. Hoy:
- **El LLM en su prompt** recibe variables + stats, pero **NO el DAG**.
- **El código downstream** (verifier) sí usa el DAG: auto-computa backdoor
  sets, marca adjust_invalid, etc.

**D4.** ¿Deberíamos pasar el DAG al prompt del LLM en Flow B? Argumentos:

**Pro:**
- Traducir "X media T→Y" a 4 arms es más fácil si el compiler sabe
  cuál es el mediator en el DAG.
- Flow B **fabrica ground truth**, no evalúa al solver. La presión
  evolutiva (argumento por el que Flow A está ciego) **no aplica** a
  Flow B.

**Contra:**
- Abre la puerta a que el LLM "arregle" silenciosamente una SQ mal
  escrita en vez de abstenerse. Aún sin presión evolutiva, queremos
  separación limpia entre "LLM propone" y "código valida".
- El código downstream ya hace la corrección estructural
  (`_find_backdoor_set`). ¿Cuál es la ganancia marginal?

**D5.** ¿Hay evidencia medible de que la política actual está fallando?

Evidencia puntual: Task #45 (P06 G.1 ground-sanity). Falta:
- Batch systematic de SQs compiladas, contando cuántas tuvieron
  `adjust_invalid` o fallos en el verifier por decisiones estructurales
  del LLM.
- ¿Cuántos fallos de Flow B se verificarían mejor con DAG access vs
  con prompt exemplars (como en Flow A)?

## Alcance

- Fuera de scope: cambiar Flow B. Primero medir.
- Scope propuesto (fase 1): instrumentar Flow B para loggear casos de
  `adjust_invalid` sobre batch de SQs; caracterizar causa raíz de cada
  uno.
- Fase 2 (gated en fase 1): debate de diseño con evidencia.

## Links
- Suite 2 baseline: `research/synthesis/suite2_compiler_baseline.md`
- Briefing interno: `research/notes/sq_flow_and_dag_visibility_open_questions.md` §5
- Task #45 histórico: P06 G.1 ground-sanity
- Invariante Flow A vs B: `PROJECT.md` invariante 8, memoria
  `project_flow_a_vs_flow_b.md`
