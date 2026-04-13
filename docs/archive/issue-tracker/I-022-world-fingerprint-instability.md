---
id: 22
title: World fingerprint instability (P06 debt)
status: open
type: hygiene
lane: hygiene
priority: parked
created: 2026-04-10
origin: TODO:#28
---

# I-022: World fingerprint instability

## Status
- **Estado:** documentado como deuda P06, no investigado
- **Ultimo resultado:** detectado durante P06 experiments
- **Proximo paso:** investigar root cause

## Pregunta
El world_fingerprint no es estable entre regeneraciones del mismo mundo.
Esto dificulta la comparacion de resultados y la validacion de reproducibilidad
mas alla del rescore.

Baja prioridad — el rescore pipeline ya funciona con src.json congelados.
Este issue solo importaria si necesitamos comparar mundos regenerados.
