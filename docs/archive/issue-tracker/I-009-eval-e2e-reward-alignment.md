---
id: 9
title: Eval suite — E2E reward alignment
status: partial
type: task
lane: eval
priority: next
created: 2026-04-10
related: [I-006, I-007, I-008, I-002]
origin: eval_suite_framework.md
---

# I-009: Eval suite — E2E reward alignment

## Status
- **Estado:** blocks A+B implementados y pasando (25/25)
- **Ultimo resultado:** 25 passed in 0.69s (2026-04-12)
- **Proximo paso:** block C (trajectory ordering) — gated on P2 credit-assignment

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

## Resultado (blocks A+B)

Suite 4 Blocks A+B implementadas en `tests/eval/suite4_reward_alignment/`.

**25 tests, 100% pass:**

**Block A — Investigation Pressure (7 tests):**
- `TestInvestigationGapBasic`: data beats no-data (gap>0.05), precision gate
  castiga guessing, priors parciales pierden vs datos completos
- `TestBreadthIncentive`: cobertura amplia beats profundidad en 1 familia,
  descubrimiento incremental es monotónico
- `TestOverclaimPenalty`: cobertura completa de atoms beats parcial,
  investigación profunda beats superficial

**Block B — Anti-Hack / Reward Robustness (18 tests):**
- `TestGenericButTrue`: claims vagos pierden + gradiente de especificidad
- `TestDuplicateSpam`: duplicados no suman + pierden vs diversidad
- `TestVolumeSpam`: over-budget penalizado, massive spam = 0% efficiency
- `TestWrongVariable`: fake IDs = 0 coverage, pierden vs 1 claim real
- `TestPrecisionFlood`: flood activa precision gate, pierde vs selectivo
- `TestCherryPick`: 1 familia fácil pierde vs cobertura amplia
- `TestHonestBeatsAll`: capstone — honesto beats 6 estrategias adversariales

**Block C — Trajectory Ordering:** pendiente, gated on P2 credit-assignment.

Archivos: `tests/eval/suite4_reward_alignment/`
  (test_block_a_investigation_pressure.py, test_block_b_antihack.py)
