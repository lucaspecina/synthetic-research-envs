---
id: 13
title: QRData + DiscoveryBench harness decisions (T4/T5)
status: open
type: decision
lane: training
priority: later
created: 2026-04-10
origin: TODO:T4, TODO:T5
---

# I-013: QRData + DiscoveryBench harness decisions

## Status
- **Estado:** decisiones pendientes que bloquean comparabilidad
- **Ultimo resultado:** QRData corrido text-only (38%) vs paper con code
  interpreter (57.9%). DiscoveryBench tiene LLM judge no-determinista.
- **Proximo paso:** decidir si QRData incluye code execution o sale de Tier 1

## Pregunta
Dos benchmarks con problemas de comparabilidad:

**QRData (T4):** el setup canonico del paper usa code interpreter (57.9%).
Nosotros lo corrimos text-only (38%). Decidir: incluir code execution en
BEFORE/AFTER, o QRData sale del Tier 1.

**DiscoveryBench (T5):** el HMS (holistic match score) depende del LLM judge.
Sin fijar judge model + prompt + version + multiple seeds + voting, no es
comparable BEFORE/AFTER.
