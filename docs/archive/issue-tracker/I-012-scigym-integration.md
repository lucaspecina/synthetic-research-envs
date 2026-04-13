---
id: 12
title: SciGym integration (T3)
status: open
type: task
lane: training
priority: later
created: 2026-04-10
related: [I-010]
origin: TODO:T3
---

# I-012: SciGym integration

## Status
- **Estado:** no iniciado
- **Ultimo resultado:** unico benchmark publico que mide loop iterativo
- **Proximo paso:** standup de SciGym (Linux/Docker, SBML)

## Pregunta
SciGym es el unico benchmark publico que mide loop investigativo iterativo,
que es exactamente lo que SREG quiere entrenar. Costo operativo aceptado.

**Items:**
- [ ] Standup de SciGym (Linux/Docker, SBML, repo h4duan/SciGym)
- [ ] Adapter compatible con el harness del solver (mismo scaffold OI)
- [ ] Reportar graph edit distance final, curva ged-vs-iterations, recovery rate
- [ ] Correr BEFORE con Qwen3-8B

**Referencia:** `research/synthesis/related_work_scigym.md`
