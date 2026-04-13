---
id: 23
title: Compiler benchmark offline (200+ claims, >90% precision)
status: open
type: task
lane: eval
priority: later
created: 2026-04-10
blocked_by: [I-003]
origin: TODO:A15
---

# I-023: Compiler benchmark offline

## Status
- **Estado:** no iniciado. Bloqueado por I-003 (claim compiler grammar-direct)
- **Ultimo resultado:** SQ compiler tiene benchmark informal (5 SQs, 18 specs)
- **Proximo paso:** esperar migracion del claim compiler, luego construir gold set

## Pregunta
El compiler (SQ + claims) necesita un benchmark offline con gold set de
compilaciones esperadas. Target: 200+ claims/SQs, >90% precision.

Tiene sentido hacerlo DESPUES de I-003 (claim compiler grammar-direct) para
no construir gold set sobre el compilador viejo.

**Items:**
- [ ] Gold set de claims con compilacion esperada (manualmente curado)
- [ ] Gold set de SQs con compilacion esperada
- [ ] Script de benchmark que mida precision/recall del compiler
- [ ] Integrar como parte del eval suite (I-007)
