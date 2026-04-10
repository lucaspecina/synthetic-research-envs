---
id: 10
title: Qwen3-8B BEFORE benchmarks (T1)
status: open
type: task
lane: training
priority: next
created: 2026-04-10
related: [I-011, I-012, I-013]
origin: TODO:T1
---

# I-010: Qwen3-8B BEFORE benchmarks

## Status
- **Estado:** bloqueante para tesis. No iniciado.
- **Ultimo resultado:** BEFOREs actuales son con gpt-5.2-chat, no sirven
- **Proximo paso:** confirmar acceso a Qwen3-8B (modelo, endpoint, harness)

## Pregunta
Los BEFORE de la tesis deben ser con Qwen3-8B (el modelo que se va a
entrenar con RL). Los benchmarks existentes (CLadder, QRData, DiscoveryBench)
se corrieron con GPT, que no es comparable.

**Items:**
- [ ] Confirmar acceso a Qwen3-8B (HuggingFace, Azure, o local)
- [ ] Re-correr CLadder con Qwen3-8B
- [ ] Re-correr QRData con Qwen3-8B
- [ ] Re-correr DiscoveryBench con Qwen3-8B
- [ ] Documentar resultados como BEFORE oficial

**Referencia:** `research/synthesis/sreg_training_transfer_protocol.md`
