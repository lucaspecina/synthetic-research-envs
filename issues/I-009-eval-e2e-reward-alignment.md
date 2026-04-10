---
id: 9
title: Eval suite — E2E reward alignment
status: open
type: task
lane: eval
priority: next
created: 2026-04-10
related: [I-006, I-007, I-008, I-002]
origin: eval_suite_framework.md
---

# I-009: Eval suite — E2E reward alignment

## Status
- **Estado:** disenado, no implementado
- **Ultimo resultado:** A28 audit identifico 4 failure modes del scoring
- **Proximo paso:** disenar casos adversariales y no-data baselines

## Pregunta
Evalua si el sistema completo fuerza investigacion real y si el reward
ordena mejor vs peor investigacion como deberia.

**Scope:**
- No-data baselines: score sin datos < score con datos
- Trayectorias buenas vs malas: el reward las ordena correctamente
- Reward robustness / anti-hack: claims genericas, duplicadas, spam,
  variable equivocada, asociacion reportada como causalidad, fabricated
  evidence
- Relevance judge: impacto sobre el reward (accuracy esta en I-007)

**Casos adversariales minimos:**
- Claims genericas que matchean todo
- Claims duplicadas / spam
- Variable correcta pero direccion invertida
- Asociacion reportada como causalidad
- Fabricated evidence_basis

**Referencia:** `research/synthesis/eval_suite_framework.md`, A28 taxonomia
