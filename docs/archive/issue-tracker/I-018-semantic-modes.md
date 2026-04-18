---
id: 18
title: Semantic modes — fictional / abstract (I2)
status: open
type: task
lane: research
priority: later
created: 2026-04-10
related: [I-016]
origin: TODO:I2, TODO:A3
---

# I-018: Semantic modes — fictional / abstract

## Status
- **Estado:** prototipado manualmente (experimento 2026-03-17), no
  implementado como feature
- **Ultimo resultado:** fictional produce mejor razonamiento, abstract es
  viable post-fix, realistic contamina en algunos dominios
- **Proximo paso:** disenar transformacion post-generacion (renombrar
  variables, reescribir narrativa)

## Pregunta
Des-realizar la semantica para que el modelo entrenado aprenda research
skill en vez de domain priors. Tres modos sobre el mismo SCM:

- **realistic** (actual): nombres cientificos reales
- **fictional**: nombres inventados con estructura semantica
- **abstract**: X1/X2/Y sin contexto

**Evidencia experimental (N=2, 2026-03-17):**
- Fictional fuerza investigacion (unico con backdoor adjustment genuino)
- Realistic contamina en oil&gas pero no en football
- Abstract viable pero fragil

**Referencia:** `research/archive/semantic_modes_experiment_2026_03_17.md`
