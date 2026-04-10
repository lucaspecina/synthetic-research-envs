---
id: 5
title: Investigation gap como gate de aceptacion de mundos (A20)
status: open
type: task
lane: scoring
priority: later
created: 2026-04-10
origin: TODO:A20
---

# I-005: Investigation gap como gate de aceptacion de mundos

## Status
- **Estado:** medido manualmente en 6 mundos, no automatizado
- **Ultimo resultado:** 4/6 mundos curados fuerzan investigacion (gap > 0.10),
  2/6 no (treatment, education)
- **Proximo paso:** definir threshold y automatizar como parte del pipeline

## Pregunta
Cada mundo OI debe pasar un test: `score_with_data - score_no_data > threshold`.
Si el gap es bajo, el mundo no fuerza investigacion y no sirve para RL.

**Sub-preguntas:**
- Cual es el threshold correcto? (0.10? 0.15? 0.20?)
- Automatizar como parte de `generate_src.py`?
- Que hacer con mundos que fallan? Redisenar o descartar?

**Mundos curados (gap medido):**
| Mundo | Gap | Fuerza? |
|-------|-----|---------|
| ecosystem | +0.570 | SI |
| productivity | +0.488 | SI |
| screen_time | +0.350 | SI |
| treatment_simpson | +0.132 | SI (mod) |
| treatment | -0.093 | NO |
| education | 0.000 | NO |

**Evidencia:** `research/notes/oi_investigation_gap.md`
