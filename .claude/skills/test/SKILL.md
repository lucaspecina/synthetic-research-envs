---
name: test
description: Run targeted tests for the project. NEVER run the full suite unless explicitly asked. Tests are a SECONDARY mechanical check — the real validation is always E2E with /eval.
disable-model-invocation: true
---

Run TARGETED tests for the project. The full suite takes 40+ minutes — avoid it.

## IMPORTANTE: tests NO validan que algo "funciona"

Unit tests son un check mecanico: confirman que el codigo no rompe. Nada mas.
**La unica forma de validar que un cambio funciona es E2E con LLM real (`/eval`).**
NUNCA presentar resultados de unit tests como evidencia de que algo esta bien.

## Como correr

1. If arguments are provided, run tests matching: $ARGUMENTS
   Example: `/test scm_task_gen` runs `pytest tests/ -v -k scm_task_gen`
2. If no arguments: ask the user what to test. Do NOT run the full suite.
3. After running, summarize results: passed, failed, errors
4. If any tests fail, read the failing test and the relevant source code to diagnose

## Reglas — NO NEGOCIABLE

- **NUNCA correr la suite completa** salvo que el usuario lo pida explicitamente.
- Solo correr el test del archivo que cambio. UNA VEZ.
- **NUNCA** correr tests en paralelo ni repetir la misma suite.
- Si falla un import, arreglar el import — no re-correr toda la suite.
- En caso de duda: NO correr tests. Preguntar al usuario.
