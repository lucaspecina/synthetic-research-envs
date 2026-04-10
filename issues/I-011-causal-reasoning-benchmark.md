---
id: 11
title: CausalReasoningBenchmark integration (T2)
status: open
type: task
lane: training
priority: later
created: 2026-04-10
related: [I-010]
origin: TODO:T2
---

# I-011: CausalReasoningBenchmark integration

## Status
- **Estado:** no iniciado
- **Ultimo resultado:** benchmark identificado (HuggingFace, arXiv:2602.20571)
- **Proximo paso:** escribir adapter

## Pregunta
Integrar CausalReasoningBenchmark (173 queries, 138 datasets reales) como
benchmark externo de la tesis.

**Items:**
- [ ] Adapter para CRB
- [ ] Reportar identification accuracy (strategy, treatment, outcome, controls)
  + full identification accuracy
- [ ] Estimacion (point + SE) como metrica secundaria
- [ ] Correr BEFORE con Qwen3-8B
