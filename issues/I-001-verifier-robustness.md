---
id: 1
title: Verifier robustness — deuda tecnica de P1
status: open
type: task
lane: scoring
priority: next
created: 2026-04-10
related: [I-002]
origin: TODO:P1.5
---

# I-001: Verifier robustness — deuda tecnica de P1

## Status
- **Estado:** diagnosticado, no implementado
- **Ultimo resultado:** tests con sufijo `known_debt` documentan los 4 footguns
- **Proximo paso:** decidir entre warn+skip vs raise para columnas faltantes

## Pregunta
El verifier (`oi_verifier.py`) tiene 4 footguns documentados que producen
scores silenciosamente incorrectos. Si el LLM alucina una columna, el
filtro retorna el dataframe completo y el score parece OK.

**Items concretos:**
1. **Silent skip de columnas faltantes** (`oi_verifier.py:164-165`) — decidir
   entre warn+skip, NaN forzado, o raise
2. **Non-numeric crash en approx_eq** — guard + dispatch a InSet para no-numericos
3. **Panel data column hallucination** — misma raiz que (1)
4. **Sample starvation** — <30 rows produce solo warning, evaluar NaN

**Evidencia:** `tests/tools/test_oi_verifier.py` tests con `known_debt`.
