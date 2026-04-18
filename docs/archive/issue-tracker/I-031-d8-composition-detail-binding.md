---
id: 31
title: D8 diagnostic — compile_direct detail-binding on D1+D2 pass + baseline-fail
status: open
type: research
lane: eval
priority: follow-up
created: 2026-04-16
related: [I-007, I-026, I-029, I-030]
origin: Suite 2 closure §7.9 F20 (research/synthesis/suite2_compiler_improvement_strategy.md)
---

# I-031: D8 diagnostic — black-box composition fails

## Status

Follow-up derivado del closure de Suite 2 compiler (§7.9 F20 + §7.11
TL;DR). **NO blocker del merge.** Prioridad: **después** de que
compiler-fix aplique I-029/I-030/I-026 y se re-mida el baseline.

## Motivación

F20 del joint matrix (§7.9): de los 22 targets con `D1-pass +
D2-critical-pass`, **13 (59%) fallan el baseline** (6 real_struct_err,
6 adjust_swap, 7 verdict_wrong, 2 stage1_fail, 1 full_pass).

D1 y D2 son proxies insuficientes de compile success. Hay un tercer
nivel de fallo que ni recognition (D1) ni slot elicitation (D2)
capturan — vive en la composición detallada de la spec completa:
valores numéricos, `cond_set`, `adjust_set`, `condition_on`,
serialización, o quirks del prompt-flow de `compile_claim_direct`.

## Scope del diagnostic

Sobre los 13 targets del cuadrante `D1-pass + D2-critical-pass +
baseline-fail` (IDs exactos en `suite2_diag_d1_d2_joint_results.json`,
campo `matrix_critical.d1_pass_d2_pass` filtrando por `bucket != full_pass`).

Pasos:

1. Re-run `compile_claim_direct` sobre los 13, capturar la spec completa
   + raw_response.
2. Clasificar failure mode (etiquetado manual o LLM judge):
   - **detail-binding**: arm values / cond_set / adjust_set incorrectos
   - **serialization**: sintaxis del JSON/schema (extensión de I-028)
   - **prompt-flow**: decisiones del compilador que se ven macro-correctas
     pero producen specs incoherentes
3. Agregar por categoría + interpretar.

## Pre-requisitos

- I-029 (abstain policy) aplicado
- I-030 (taxonomy spec alignment) aplicado
- I-026 (exemplars) aplicado
- Baseline re-medido post-fix (`suite2_full_dump_v2.py` re-run)

Solo entonces D8 aísla fallas que **persisten** post-fix, no las que
el fix ya resolvió.

## Alcance esperado

~13 LLM calls. Diagnostic quirúrgico, scope chico.

## Deliverables

- `scripts/suite2_diag_d8_composition_detail.py`
- `research/synthesis/suite2_diag_d8_results.{json,md}`
- Nueva sección §7.12 en strategy doc (o en paper de seguimiento)

## Impacto esperado

Si detail-binding domina → input para ajustes al prompt de
compile_direct post I-030.
Si serialization → posible bug del contrato (extensión de I-028/I-030).
Si prompt-flow → rediseñar estructura de compile_direct.

## Links

- `research/synthesis/suite2_compiler_improvement_strategy.md` §7.9 F20 + §7.11
- `research/synthesis/suite2_diag_d1_d2_joint_results.json`
- Suite 2 closure merge: I-007
