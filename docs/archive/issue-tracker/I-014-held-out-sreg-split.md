---
id: 14
title: Held-out SREG split (T6)
status: open
type: task
lane: training
priority: later
created: 2026-04-10
related: [I-010]
origin: TODO:T6
---

# I-014: Held-out SREG split

## Status
- **Estado:** no definido
- **Ultimo resultado:** 12 seeds existen pero no hay split formal train/test
- **Proximo paso:** definir split exacto, seeds, temperatura, max iterations

## Pregunta
Para medir transfer de RL sobre SREG, necesitamos un split held-out que el
modelo nunca vea durante entrenamiento. Definir: que seeds van a train, cuales
a test, que parametros se congelan.

**Referencia:** `research/synthesis/sreg_training_transfer_protocol.md`
seccion "Lo que todavia falta fijar"
