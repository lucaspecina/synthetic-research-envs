---
id: 6
title: Eval suite — core correctness
status: open
type: task
lane: eval
priority: next
created: 2026-04-10
related: [I-007, I-008, I-009]
origin: eval_suite_framework.md
---

# I-006: Eval suite — core correctness

## Status
- **Estado:** disenado en eval_suite_framework.md, no implementado
- **Ultimo resultado:** diseno de 4 suites aprobado
- **Proximo paso:** implementar tests sobre mundos fijos con preguntas formales

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
