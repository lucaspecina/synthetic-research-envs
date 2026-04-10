---
id: 15
title: SFT+RL vs RL-from-base decision (T7)
status: open
type: decision
lane: training
priority: later
created: 2026-04-10
origin: TODO:T7
---

# I-015: SFT+RL vs RL-from-base decision

## Status
- **Estado:** reabierta por evidencia de SandMLE
- **Ultimo resultado:** SandMLE muestra que SFT-only colapsa fuera del
  scaffold (17.7% valid submission en MLE-Dojo) y RL desde base generaliza
  mejor (83.9%)
- **Proximo paso:** decidir entre (a) SFT+RL, (b) RL-from-base, (c) ambas

## Pregunta
Si SFT memoriza nuestro compiler/SQ/claim format, va a fallar en transfer.
SandMLE sugiere que RL-from-base generaliza mejor. Riesgo asimetrico.

**Opciones:**
- (a) Mantener SFT+RL como v1
- (b) RL-from-base como v1 + SFT+RL como ablacion
- (c) Correr ambas en paralelo (si el costo lo permite)

**Recomendacion actual:** (c) si costo permite, sino (b).

**Referencia:** `research/synthesis/related_work_sandmle.md`
