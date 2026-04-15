---
id: 28
title: Claim compiler emits `sweep_values` as list inside `arm.values` (schema violation)
status: open
type: bug
lane: compiler
priority: later
created: 2026-04-15
related: [I-007, I-026, I-027]
origin: Suite 2 v2 re-baseline (2026-04-15) — W3_F03_s0 and W3_F03_s2 stage1_fail
---

# I-028: Claim compiler emits `sweep_values` as list inside `arm.values` (schema violation)

## Status
- **Estado:** detectado durante el v2 re-baseline de Suite 2
  (2026-04-15). Aparece como `stage1_fail` en el dump
  `compiler_baseline_full_dump_v2.json` para `W3_F03_s0` y
  `W3_F03_s2`.
- **Proximo paso:** reproducir el error en aislado (1 target, sin el
  harness completo) y decidir si se arregla con un post-procesado
  del output LLM o con una revisión de prompt/schema hints.

## Síntomas

Para los targets `W3_F03_s0` y `W3_F03_s2` (claim: "changepoint /
threshold effect of Temp on Health"), el compiler devuelve:

```
compiled: False
abstain_reason: None
n_specs: 0
stage1_ok: False
```

No hay `abstain_reason` porque **no fue una decisión del compiler**,
fue una excepción en la validación del output LLM contra el schema
`AtomicSpec`.

Inspección del output raw muestra que el LLM produjo un arm con:
```python
arm.values = {"Temp": [-0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75]}
```

Esto viola el contrato: `QueryArm.values` es `dict[str, float]`
(escalares), no `dict[str, list[float]]`. La intención del LLM era
claramente un `sweep` arm donde los valores iban en `sweep_values`,
no en `values`.

## Hipótesis de causa

1. **Prompt ambiguity:** el sweep recipe del compiler no es explícito
   suficiente sobre dónde van los valores del sweep. El LLM confunde
   `values` (scalar per arm) con `sweep_values` (array para el sweep
   arm).
2. **Falta de few-shot exemplar con sweep:** si los exemplars existentes
   no muestran un sweep arm, el LLM lo inventa en paralelo a `values`.
3. **Target structural:** W3_F03 es un `piecewise_fit` / `changepoint`
   contract — recipes muy poco visitados. Puede ser un blind spot general,
   no solo de sweep.

## Por qué no se había visto antes

- El v1 dump (`compiler_baseline_failures.json`) sólo persistía
  `verdict_fail`, así que los crashes de compilación caían fuera. W3_F03_s1
  (el único que no crashea) estaba en verdict_wrong, pero el bucketing
  del viejo script agrupaba todo lo que no era verdict_fail como "OK de
  alguna forma".
- El v2 dumper explícitamente clasifica `stage1_fail = compiled != gold`,
  y entonces un compile-target que devuelve 0 specs aparece.

## Reproducción

```bash
conda activate sreg
python -c "
from tests.eval.suite2_translation.fact_tables import ALL_FACTS
from tests.eval.suite2_translation.gold_targets import ALL_TARGETS
# Find W3_F03_s0 target and run compile_claim_direct on it in isolation
"
```

Target definitions en `tests/eval/suite2_translation/fact_tables.py`
(buscar `W3_F03`).

## Scope del fix

- **Opción A (defensiva):** post-procesar el output LLM en
  `compile_claim_direct` — detectar `arm.values[k]` que sea lista, moverlo
  a `sweep_values` / promover el arm a `kind=sweep`. Fix quirúrgico.
- **Opción B (prompt):** agregar un exemplar de sweep con los slots
  (`kind=sweep`, `sweep_var`, `sweep_values`) claramente separados.
- **Opción C (schema hint):** inyectar en el prompt la restricción
  `arm.values: dict[str, float]` explícita + contraejemplo.

Preferencia tentativa: A + B. A cierra el síntoma inmediato, B cierra
la causa raíz.

## Links
- `research/synthesis/compiler_baseline_full_dump_v2.json` (entries
  `W3_F03_s0`, `W3_F03_s1`, `W3_F03_s2`)
- `research/synthesis/suite2_compiler_baseline.md` §9.5, §9.7
- Cross-linked desde I-027 item 7 (split `stage1_fail` bucket)
- Suite 2 baseline issue: I-007
- Recipe exemplar work: I-026
