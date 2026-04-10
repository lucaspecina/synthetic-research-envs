---
id: 3
title: Claim compiler — migrar a grammar-direct (A23)
status: open
type: task
lane: scoring
priority: next
created: 2026-04-10
related: [I-002]
origin: TODO:A23
---

# I-003: Claim compiler — migrar a grammar-direct

## Status
- **Estado:** SQ compiler ya migrado exitosamente; claim compiler sigue en
  v1 con PatternClass fijo
- **Ultimo resultado:** forensics v2 confirma que claims metodologicos
  (ej: "no condicionar en mediadores") no compilables con 8 PatternClass
- **Proximo paso:** implementar `compile_claim_to_specs()` usando misma
  GRAMMAR_REF que `oi_sq_compiler.py`

## Pregunta
El SQ compiler (`oi_sq_compiler.py`) ya usa grammar-direct exitosamente.
El claim compiler (`oi_compiler.py`) sigue en v1 con catalogo fijo de 8
PatternClass, lo que produce abstention en claims que el SCM SI puede
verificar.

**Items:**
- [ ] `compile_claim_to_specs(claim_text, summary, llm_call)` con GRAMMAR_REF
- [ ] Integrar en runner: reemplazar `compile_claim()` v1 en `_score_with_judge()`
- [ ] Fallback: si grammar-direct falla, intentar v1 PatternClass como backup
- [ ] Validar E2E: re-correr 3 seeds con nuevo compiler, comparar truths

**Spec de diseno:** `research/synthesis/sq_v2_matching_spec.md`
**Research:** `research/notes/a23_grammar_first_sq_and_compiler.md`
