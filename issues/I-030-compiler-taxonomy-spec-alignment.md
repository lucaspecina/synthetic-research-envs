---
id: 30
title: Claim compiler taxonomy spec alignment — baseline/observe aliased; condition.values ignored
status: open
type: bug
lane: compiler
priority: soon
created: 2026-04-15
related: [I-007, I-026, I-029]
origin: Suite 2 taxonomy audit 2026-04-15 (research/synthesis/suite2_compiler_improvement_strategy.md §7.6)
---

# I-030: Compiler taxonomy spec alignment

## Status

Detectado durante el taxonomy audit de cierre de Suite 2 diagnósticos
(2026-04-15). Ver `research/synthesis/suite2_compiler_improvement_strategy.md` §7.6.

## Síntomas

D2 elicitation mostró arm_kinds al 50% (bottleneck duro del compiler).
El audit confirma que **parte de ese 50% no es capability del LLM, es
ruido inducido por un contrato taxonómico inconsistente** entre las
fuentes que el compiler consume.

**F1 — `baseline` vs `observe`: 3 voces contradictorias:**
- `GRAMMAR_REF` (oi_sq_compiler.py:43-76) los define como kinds separados.
- `compile_claim_direct()` (oi_extraction.py:502) los trata como
  intercambiables: *"Use a single `baseline` (or `observe`) arm"*.
- Strategy doc §8.3 pre-audit decía *"usar [baseline], NO usar [observe]"*.
- D2 diag prompt (suite2_diag_d2_recipe_slots.py:112) enseña lo opuesto:
  *"T correlates with Y → arm_kinds=[observe]"*.

El evaluator (test_compiler_llm.py:181) hard-gatea por `allowed_arm_kinds`,
así que cualquiera de las dos elecciones falla strict arbitrariamente
según qué eligió el gold.

**F2 — `condition` con `arm.values`: contract bug invisible:**
- `GRAMMAR_REF:54` dice *"values: dict of variable=value for intervene/condition"*.
- `oi_verifier.py:142-145` implementa `QueryKind.CONDITION` ignorando
  `arm.values` silenciosamente. Solo usa `arm.condition_on`.

→ Un compiler que siga el contract emitiendo `condition` con `values`
no crashea, pero el filter no se aplica. Drop silencioso de info.

## Evidencia

Ver §7.6 completo en
`research/synthesis/suite2_compiler_improvement_strategy.md` para:
- Mapeo fuente × kind × definición (tabla)
- Filtro de severidad 3-capas
- F1-F6 findings y veredictos

Scripts referenciados en evidencia (ya committeados):
- `scripts/suite2_diag_d2_recipe_slots.py:112` — taxonomy block
- `research/synthesis/suite2_diag_d2_results.json` — arm_kinds 50% acc

## Scope del fix

**Spec unificada propuesta** (ver §7.6 "Recomendación"):

- `baseline` = joint sampling **sin** filtros. Uso: claims asociacionales
  donde el filter/adjustment vive dentro del measurement (e.g.
  `partial_correlation` con `cond_set`).
- `observe` = joint sampling + `_filter_condition(arm.values)` point-value.
  Uso: condicionamiento observacional simple sobre valor exacto.
- `condition` = joint sampling + `_filter_condition(arm.condition_on)`.
  Uso cuando el filter NO es point-value (range, quantile, in_set).
- **Eliminar `values` del contrato de `condition`** en GRAMMAR_REF.
- Reemplazar en `compile_claim_direct` el wording *"baseline (or observe)"*
  por regla discriminatoria por measurement:
  - `correlation`/`partial_correlation` → baseline
  - filter point-value retrospectivo → observe
  - filter rich-predicate → condition

**Files a tocar:**
- `src/sreg/tools/oi_sq_compiler.py` — editar `GRAMMAR_REF` (sección QueryArm).
- `src/sreg/tools/oi_extraction.py` — ajustar `compile_claim_direct()`
  system prompt (línea ~477-490).
- `scripts/suite2_diag_d2_recipe_slots.py:112` — sync taxonomy block.
- `research/synthesis/suite2_compiler_improvement_strategy.md:429-431` —
  recipes ya sincronizados en este commit, verificar consistencia.

**Tests a validar:**
- `tests/eval/suite2_translation/test_compiler_llm.py` — que el allowed_arm_kinds
  gate no cambie su comportamiento para golds existentes.
- Re-run `suite2_full_dump_v2.py` post-fix para medir delta sobre el 50%
  arm_kinds.

## Impacto esperado

Parte del 50% arm_kinds en D2 es atribuible a inconsistencia del contrato
(no a capability). Post-fix esperable:

- D2 arm_kinds accuracy: 50% → ≥65% (estimado, requiere rerun para confirmar)
- Effective_pass_rate: sin estimación directa hasta que Rama A también
  esté aplicada.

## Prereq de

**I-026 Rama C (targeted exemplars).** Escribir exemplares sobre un
contrato inconsistente enseña la inconsistencia. Orden obligatorio:
I-030 (spec fix) → I-026 (exemplars).

## Reproducción

Audit es papel-based (sin re-run). Para verificar F2 empíricamente:

```bash
conda activate sreg
python -c "
from sreg.models.open_investigation import QueryArm, QueryKind
from sreg.tools.oi_verifier import _run_single_arm
from tests.eval.suite2_translation.worlds import W1
# Arm condition con values (según GRAMMAR_REF deberia filtrar)
arm = QueryArm(
    kind=QueryKind.CONDITION,
    label='test',
    values={'T': 1.0},  # GRAMMAR_REF dice que esto filtra
    condition_on={},
)
# Verifier deberia usar values como filter, pero lo ignora
# (Expected: N samples sin filtro == N samples totales)
"
```

## Links

- `research/synthesis/suite2_compiler_improvement_strategy.md` §7.6 — audit completo
- Suite 2 baseline issue: I-007
- Recipe exemplars: I-026 (blocked hasta I-030 done)
- Abstain fix: I-029 (independiente, se puede hacer en paralelo)
