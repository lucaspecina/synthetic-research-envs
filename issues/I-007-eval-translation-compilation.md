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

## Progreso — Claim compiler baseline (2026-04-14)

- [x] W1/W2/W3 mundos implementados (I-007)
- [x] Gold targets (55) implementados
- [x] Harness `test_compiler_llm.py` con flag `--run-llm`
- [x] **Primer baseline:** 31% effective pass sobre 55 gold targets
  ver `research/synthesis/suite2_compiler_baseline.md`
- [x] Diagnostic A/B/C sobre 3 patterns (confirma recipe gap)

## Pendiente para cerrar Suite 2

**Profundizar sobre claim compiler (datos que ya tenemos):**
- [x] **Desglose parcial por patrón** (2026-04-15). Triage basado
  solo en `compiler_baseline_failures.json` (21 verdict-fails) +
  gold set metadata. Ver `research/synthesis/suite2_pattern_breakdown.md`.
  Findings: 4 families concentran 10/21 fails y son candidatas a
  **0% effective pass**: CC-A5 (confounding), SQ-A1 (direct causal
  question), CC-A7 (tail risk), CC-D2 (mediation vs confounding).
  Fail rate plano por dificultad → recipe gap ortogonal a hardness.
- [ ] **Audit manual — #11a: zero-bound verdict-fail families**
  (ejecutable ahora). Leer los 10 verdict-fails de las 4 families
  zero-candidate uno por uno. Taxonomía: recipe selection vs slot
  filling, variable binding, atom count, missing causal role.
  Cierre por family: canonical wrong recipe, error invariance across
  paraphrases. Output: `suite2_fail_audit_recipe_patterns.md`.
- [ ] **Audit manual — #11b: full_pass + real_struct_err**
  (bloqueado por full per-target dump, ver I-027 item 4). Clasificar
  pass-por-razón-correcta vs pass-por-casualidad sobre los 6 full
  passes y los 11 real struct errors. Requiere artefactos que hoy
  NO existen.
- [ ] **Ablation con exemplars sobre los 55**. Correr el prompt mejorado
  (A/B/C condicion B) contra el gold set completo. Si sube a ~50%+,
  recipe gap explica todo. Si se queda en ~35%, hay algo más grande.
  Script nuevo + 55 LLM calls.

**Componentes del compiler pipeline que no testeamos:**
- [ ] **SQ compiler baseline** (Flow B). Compila `text_gloss`→AtomicSpec
  y ES el que fabrica la ground truth. Mismo método que claim compiler:
  gold targets SQ-side → harness → baseline → diagnostic si falla.
  Sin esto, el 31% del claim compiler está medido contra algo que
  tambien puede estar roto.
- [ ] **Relevance judge baseline**. LLM judge que decide si una claim
  es relevante a una SQ. Gold: pares (claim, SQ) con label binario.
  Si el judge está al 60% en vez de 90%, el solver pierde puntos
  aunque acierte.

**Pre-condición fundacional (fuera de Suite 2 pero relacionada):**
- [ ] **Script SQ↔DAG coherence** (issue I-024). Chequear sobre ~20
  casos históricos cuántas SQs son estructuralmente incoherentes con
  el DAG que el orchestrator construyó. Si la tasa es material, todo
  lo de arriba está medido contra gold contaminado. Primero script
  standalone, no suite completa.

**5to actor del pipeline (identificado por Codex):**
- [ ] **Answer-key grounding/rendering baseline**. Vive entre SQ compiler
  y relevance judge (`oi_sq_compiler.py:990` y `oi_runner.py:573`). El
  judge no consume specs crudos — consume answer keys ya renderizadas.
  Si esta capa está rota, el scoring final también.

## Orden final (revisado con Codex 2026-04-14)

Cambios vs mi draft inicial: (a) pattern breakdown va antes de audit
(cheapest → más barato, te dice dónde auditar primero); (b) ablation
con exemplars va al FINAL — es explicativo no bloqueante, y hacerlo
temprano sobre los 55 mete overfit a Suite 2 gold; (c) agregado
answer-key grounding como paso propio.

1. ~~**Pattern breakdown** del 31% (gratis).~~ → hecho 2026-04-15
   (partial, ver `suite2_pattern_breakdown.md`).
2. **Audit #11a: zero-bound verdict-fail families** (gratis, ejecutable
   ahora — 10 fichas sobre CC-A5/SQ-A1/CC-A7/CC-D2).
3. **Audit #11b: full_pass + real_struct_err** (bloqueado por I-027,
   requiere full per-target dump).
4. **Script SQ↔DAG coherence** (detecta gold contamination).
5. **SQ compiler baseline** (Flow B).
6. **Relevance judge baseline**.
7. **Answer-key grounding baseline** (5to actor).
8. **Ablation con exemplars** sobre los 55, held-out por fact
   family / pattern, **labelado como diagnóstico no confirmatorio**.
9. **Reporte final Suite 2 + cierre de I-007**.
