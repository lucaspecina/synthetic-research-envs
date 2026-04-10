---
id: 7
title: Eval suite — translation / compilation
status: open
type: task
lane: eval
priority: next
created: 2026-04-10
related: [I-006, I-008, I-009, I-003]
origin: eval_suite_framework.md
---

# I-007: Eval suite — translation / compilation

## Status
- **Estado:** disenado, no implementado
- **Ultimo resultado:** SQ compiler funciona bien; claim compiler (v1) tiene
  gaps conocidos en claims metodologicos
- **Proximo paso:** definir gold set de SQs + claims con compilacion esperada

## Pregunta
Evalua si SQs y claims en lenguaje natural se traducen bien a specs
verificables. Foco: precision de la compilacion.

**Scope:**
- SQ compiler: texto → VerificationSpec
- Claim compiler: claim_text → AtomicSpec
- Matching/relevance: accuracy semantica claim-vs-SQ
- Relevance judge: accuracy del LLM judge

**gold_answer debe venir del oracle (manual offline), no del mismo pipeline.**

**Nota sobre relevance judge:** su accuracy semantica vive en esta suite.
Su impacto sobre el reward vive en I-009 (E2E reward alignment).

**Referencia:** `research/synthesis/eval_suite_framework.md`
