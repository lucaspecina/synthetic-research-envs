---
id: 16
title: Sequential investigation — Sherlock / gated info layers (A3b)
status: open
type: research
lane: research
priority: later
created: 2026-04-10
updated: 2026-04-13
origin: TODO:A3b
---

# I-016: Sequential investigation — Sherlock / gated info layers

## Status
- **Estado:** design doc completo, no implementado
- **Ultimo resultado:** design document canon con 3 modelos de information
  gating, comparacion con SciGym, diseño concreto del Modelo 1 (budget-gated
  interventions)
- **Proximo paso:** prototype con 1 mundo toy, 3 variables, budget=5

## Pregunta
SREG hoy es flat: el solver recibe todo, analiza, submittea. La investigacion
real es long-horizon porque la informacion esta en capas y cada capa revela
que hacer en la siguiente.

El salto: convertir el caso de un paquete estatico a un entorno interactivo
con revelacion secuencial de informacion.

## Scope

**Modelo 1 (v2 minimo viable):**
- 3 tools nuevas: `request_observation`, `request_intervention`,
  `request_counterfactual`
- Budget model: cada tool call cuesta, budget limitado
- Dataset inicial reducido (N=100 observacionales gratis)
- Mundos "intervention-requiring" (confounding, mediacion, collider)
- Backward compat: v1 = budget infinito, solo observacional

**Criterio de cierre (Modelo 1):**
- [ ] Tools integradas en agent framework
- [ ] Budget model en OIEpisodeRunner
- [ ] 3+ mundos intervention-requiring
- [ ] Piloto E2E: agente usa intervenciones y mejora score vs observational-only
- [ ] Backward compat: casos v1 producen mismo score

## Dependencias
- v1 scoring estable (eval suites, P1/P2 cerrados)
- SCM engine do-operator verificado (Suite 1 core correctness)

## Design doc
**`research/synthesis/sherlock_interactive_design.md`** — doc canonico con:
- Comparacion SciGym, 3 modelos de information gating
- Diseño concreto Modelo 1 (tools, budget, scoring)
- Open questions (D1-D6)
- Problema dificil: reward y diseño experimental
- Mundos intervention-requiring
- Path de implementacion

## Referencia
- `research/synthesis/sherlock_interactive_design.md` (CANON)
- `research/synthesis/related_work_scigym.md`
- `PROJECT.md` Horizonte 2
