---
id: 3
title: Claim compiler — migrar a grammar-direct (A23)
status: closed
type: task
lane: scoring
priority: done
created: 2026-04-10
closed: 2026-04-10
related: [I-002]
origin: TODO:A23
---

# I-003: Claim compiler — migrar a grammar-direct

## Cierre retroactivo (2026-04-10)

**Este issue se creó por error durante la migración de TODO.md a issue
tracking (2026-04-10). El trabajo ya estaba hecho desde el 2026-04-03.**

**Commit de prueba:** `9ebf29d` — "feat: grammar-direct claim compiler
(A23) — LLM produces AtomicSpecs without PatternClass IR"

**Estado real en main hoy:**

El pipeline E2E del claim compiler usa grammar-direct como path principal
desde 2026-04-03. El flujo real es:

```
oi_runner.py:418
  └─> compile_episode_claims() en oi_extraction.py:708-715
      └─> compile_claim() en oi_extraction.py:604-705
          ├─ compile_claim_direct() en oi_extraction.py:443-596  [DEFAULT]
          │    └─ usa el mismo GRAMMAR_REF que oi_sq_compiler.py
          │    └─ el LLM produce AtomicSpecs directamente, sin PatternClass IR
          └─ lower_intent() + PatternClass en oi_compiler.py   [FALLBACK]
               └─ solo se dispara si compile_claim_direct() falla o devuelve
                 specs inválidos
```

El camino por defecto NO usa los 8 `PatternClass` (CAUSAL_EFFECT, MEDIATION,
HETEROGENEITY, TAIL_RISK, VARIANCE_EFFECT, OBSERVATIONAL_ASSOCIATION,
EFFECT_RANKING, CONFOUNDING). El LLM recibe `GRAMMAR_REF` y produce
`AtomicSpec`s directamente, igual que el SQ compiler.

**Verificación:**
- `src/sreg/tools/oi_extraction.py:625-638` — lógica "grammar-direct first,
  v1 fallback".
- `src/sreg/tools/oi_extraction.py:443-596` — implementación
  `compile_claim_direct()`.
- `src/sreg/tools/oi_extraction.py:458-464` — importa `GRAMMAR_REF`,
  `_build_variables_info`, `_parse_specs_json`, `_validate_variables` desde
  `oi_sq_compiler`. La misma gramática universal.

## Deuda derivada (no es este issue)

Los 8 `PatternClass` y todo el código del fallback v1 siguen vivos en el
repo (`oi_compiler.py` `lower_intent`, `_lower_*` helpers, `PatternClass`
enum; `oi_extraction.py` `_deterministic_extract`, `_PATTERN_KEYWORDS`,
`build_extraction_prompt`, `parse_extraction_response`). No son código
muerto literal — se disparan cuando `compile_claim_direct()` falla — pero
pueden ser dead-ish: si en E2E reales el fallback nunca se activa, son
candidatos a borrar.

**Esto se resuelve en el worktree `audit-cleanup`**, no acá. El audit
tiene que medir la frecuencia real del fallback sobre batches recientes
y decidir: (a) borrar el fallback si es dead-ish, (b) mantenerlo si se
dispara lo suficiente como para justificar el safety net, (c) mejorar
`compile_claim_direct()` si el fallback se dispara en casos que deberían
ser compilables directo.

## Sección original (preservada como historia)

> El SQ compiler (`oi_sq_compiler.py`) ya usa grammar-direct exitosamente.
> El claim compiler (`oi_compiler.py`) sigue en v1 con catalogo fijo de 8
> PatternClass, lo que produce abstention en claims que el SCM SI puede
> verificar.
>
> **Items:**
> - [x] `compile_claim_to_specs(claim_text, summary, llm_call)` con GRAMMAR_REF
>   → implementado como `compile_claim_direct()` en `oi_extraction.py:443`
> - [x] Integrar en runner: reemplazar `compile_claim()` v1 en `_score_with_judge()`
>   → hecho vía `compile_claim()` que llama grammar-direct primero
> - [x] Fallback: si grammar-direct falla, intentar v1 PatternClass como backup
>   → implementado en `compile_claim()` líneas 625-638
> - [ ] Validar E2E: re-correr 3 seeds con nuevo compiler, comparar truths
>   → NO verificado formalmente en este audit retroactivo. Si no se hizo,
>   queda como sub-ticket del audit-cleanup.
>
> **Spec de diseno:** `research/synthesis/sq_v2_matching_spec.md`
> **Research:** `research/notes/a23_grammar_first_sq_and_compiler.md`
