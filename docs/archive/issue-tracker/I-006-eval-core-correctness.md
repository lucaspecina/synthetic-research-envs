---
id: 6
title: Eval suite — core correctness
status: done
type: task
lane: eval
priority: next
created: 2026-04-10
closed: 2026-04-12
related: [I-007, I-008, I-009]
origin: eval_suite_framework.md
---

# I-006: Eval suite — core correctness

## Status
- **Estado:** implementado y pasando 52/52
- **Ultimo resultado:** 52 passed in 6.18s (2026-04-12)
- **Proximo paso:** ninguno (cerrado)

## Resultado

Suite 1 Core Correctness implementada en `tests/eval/suite1_core_correctness/`.

**52 tests, 100% pass:**
- 26 verifier specs sobre 6 mundos hand-crafted con ground truth analitico
- 5 validation rejection tests (contratos pydantic)
- 1 rescore determinism test
- 4 enum coverage self-checks (34/34 enums activos cubiertos)
- 16 scoring arithmetic tests con valores calculados a mano

**Enums cubiertos (100% de activos):**
- QueryKind: BASELINE, INTERVENE, OBSERVE, CONDITION, ADJUST, SWEEP
- MeasurementKind: MEAN, VARIANCE, QUANTILE, TAIL_PROB, CORRELATION,
  PARTIAL_CORRELATION, IDENTIFIABILITY_CHECK (skip: PROB, DISTRIBUTION)
- ComparisonKind: IDENTITY, DIFFERENCE, RATIO, RANKING, GAP, PROPORTION,
  PIECEWISE_FIT, CONTRAST_DIFF
- AssertionKind: todos los 13 valores

**Mundos:** linear_chain, confounder, latent_confounder, threshold,
independence, mediation. Cada uno con derivaciones analiticas documentadas.

## Pregunta
Valida la base matematica del sistema: SCM engine, verifier, partes mecanicas
del scoring. Pregunta central: "si le doy una pregunta formal bien definida
sobre un mundo fijo, devuelve la respuesta correcta?"

**Scope:**
- SCM sampling + do-calculus correctness
- Verifier: AtomicSpec execution contra SCM
- Scoring: formulas aritmeticas (truth, coverage, total)
- Rescore determinism (reaggregate delta = 0.0000)

**NO incluye:** LLM behavior, compilation quality, solver judgment.

**Referencia:** `research/synthesis/eval_suite_framework.md`
