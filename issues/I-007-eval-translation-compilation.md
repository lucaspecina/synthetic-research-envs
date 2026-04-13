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
- **Estado:** diseño completo, implementación pendiente
- **Ultimo resultado:** design doc completo con matriz 41 familias + 3 mundos
  (revisado con Codex, 3 rondas)
- **Proximo paso:** implementar mundos W1-W3, derivar fact tables, escribir gold claims

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

## Diseño (2026-04-13)

Design doc completo en `research/synthesis/eval_suite_translation.md`.

**Approach:** bottom-up desde ecuaciones del SCM. Derivar hechos
analíticos, formularlos como claims/SQs en lenguaje natural. Gold
verificado por equivalencia verificacional (no string match).

**Matriz:** 41 familias semánticas (25 claim compiler, 9 SQ compiler,
7 relevance judge). Organizada por componente x tipo de desafío.

**3 mundos research-grade (~7-8 vars, ground truth analítico):**
- W1: Comparative Effectiveness (estructura: causal, mediation, heterogeneity)
- W2: Observational Epidemiology (disambiguation: Simpson reversal, collider)
- W3: Environmental Health (distribucional: threshold, latent, tail risk)

**Gold set estimado:** ~90-120 claims/SQs + ~150-250 pares relevance.

Diseño revisado con Codex (GPT-5.4) en 3 rondas de crítica.
