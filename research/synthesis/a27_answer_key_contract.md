# A27: Contrato del Answer Key Rico

> Fecha: 2026-03-31
> Status: DECIDIDO (contrato actual), FUTURO (AtomResolution como modelo)
> Consenso: Claude, Codex, Cursor

## El problema

`verify_atom()` produce un resultado rico del SCM en `verdict.detail`, pero
hasta ahora no habia contrato formal. Consumidores leian keys ad-hoc
(`detail["comparison"]["difference"]`, etc.) sin garantias de estabilidad.

Ademas, `AtomVerdict` mezcla dos conceptos:
- **Resolucion:** que devolvio el SCM (measurements, comparison)
- **Chequeo de assertion:** la claim/hipotesis matchea el resultado?

Para el teacher, solo importa la resolucion. Para el solver, importan ambas.

## Decision: contrato explicito + adaptador, no modelo nuevo (todavia)

### Opciones evaluadas

| Opcion | Pro | Contra |
|---|---|---|
| AtomResolution nuevo (Cursor) | Separacion limpia, tipado fuerte | Refactor de pipeline antes de tener E2E |
| Formalizar detail como contrato (Codex/Claude) | Pragmatico, no rompe nada | detail sigue siendo dict[str, Any] |
| No hacer nada | Cero esfuerzo | Judge construido sobre arena |

### Elegimos: contrato + adaptador

1. **Documentar el schema de `detail`** por ComparisonKind (en docstring de AtomVerdict)
2. **Crear `render_answer_key(verdict)`** — vista normalizada que consume el judge
3. **Prohibir** que consumidores lean `detail` directamente — usar el adaptador
4. **Futuro:** cuando haya 2-3 consumidores reales, promover a `AtomResolution`

## Contrato de `verdict.detail`

### Estructura general

```python
detail = {
    "measurements": dict[str, float | bool | dict],  # por arm label
    "comparison": dict[str, Any],                      # por ComparisonKind
}
```

### measurements

- Key: arm label (string del QueryArm.label)
- Value: depende de MeasurementKind
  - MEAN, VARIANCE, QUANTILE, TAIL_PROB, CORRELATION, PARTIAL_CORRELATION,
    DISTRIBUTION: `float`
  - IDENTIFIABILITY_CHECK: `bool`
  - SWEEP arms: `dict[float, float]` (sweep values)
- Multi-target MEAN: keys son `"{arm}_{target}"` (e.g., `"baseline_X"`)

### comparison (por ComparisonKind)

| ComparisonKind | Keys estables | Tipos |
|---|---|---|
| IDENTITY | `value` | `float \| bool` |
| DIFFERENCE | `difference`, `ref`, `other` | `float` |
| RATIO | `ratio` | `float` |
| RANKING | `ranking`, `values` | `tuple[str,...]`, `dict[str,float]` |
| GAP | `gap`, `values` | `float`, `dict[str,float]` |
| PROPORTION | `proportion` | `float` |
| PIECEWISE_FIT | `sweep_data`, `changepoint` | `dict`, `{detected: bool, changepoint_x?: float, reduction_fraction?: float}` |
| CONTRAST_DIFF | `contrast_diff` | `float` |

### Caso de error

Si `verify_atom()` crashea: `detail = {"error": str}` (sin measurements ni comparison).

## Asimetria teacher / solver

| | Teacher (SQ answer key) | Solver (claim verification) |
|---|---|---|
| Lo que importa | `detail` (measurements + comparison) | `solver_assertion_holds` |
| `solver_assertion_holds` | Diagnostico (compiler adivino?) | Core truth (claim es cierta?) |
| Assertion | Hipotesis del compiler, auxiliar | La claim misma, central |
| Usa `render_answer_key()`? | Si — para judge y matching futuro | No necesita |

## `render_answer_key()` — el adaptador

Vista normalizada de `verdict.detail` para consumo externo. Objetivo:
desacoplar consumidores (judge, matching futuro) de las keys internas.

### Que debe incluir

- **Tipo de resultado** (scalar, ratio, ranking, bool, changepoint, contrast)
- **Valor principal** normalizado (el "headline" del resultado)
- **Contexto** (measurements por arm, para comparaciones ricas)
- **NO incluye** la Assertion del compiler

### Ejemplo de output

```python
# Para DIFFERENCE:
{
    "result_type": "difference",
    "headline": "treatment effect = +15.3 (treated: 42.3, control: 27.0)",
    "value": 15.3,
    "arms": {"treated": 42.3, "control": 27.0},
}

# Para RANKING:
{
    "result_type": "ranking",
    "headline": "ranking by mean: stress > fluid > pressure > spacing",
    "ranking": ["stress", "fluid", "pressure", "spacing"],
    "values": {"stress": 0.82, "fluid": 0.65, "pressure": 0.41, "spacing": 0.12},
}

# Para IDENTITY (identifiability):
{
    "result_type": "bool",
    "headline": "identifiable = True (via backdoor criterion)",
    "value": true,
}
```

### Quien lo consume

1. **LLM relevance judge** (proximo paso) — recibe headline + contexto
2. **Matching deterministico futuro** — recibe value + result_type
3. **Diagnosticos/inspeccion** — puede leer detail directo (excepcional)

## Rankings: composicion, no specs monoliticos

SQs como "cuales variables tienen mayor efecto sobre Y?" se resuelven con
N specs atomicos (uno por variable) + agregacion en el answer key del SQ.

```
spec_1: ATE de spacing sobre sanding_risk    → answer_key.value = -8.2
spec_2: ATE de fluid sobre sanding_risk      → answer_key.value = +12.1
spec_3: ATE de pressure sobre sanding_risk   → answer_key.value = +5.4
...
SQ answer key agrega: ranking = [fluid, pressure, spacing] por |ATE|
```

El verifier sigue produciendo resultados atomicos. La composicion es
responsabilidad del SQ-level answer key, no del spec individual.

**Implicacion para el compiler:** cuando genera specs para una SQ de ranking,
debe emitir N specs (uno por variable/entidad), no un mega-spec con N arms.

## Destino futuro: AtomResolution

Cuando haya 2+ consumidores reales de `render_answer_key()`, promover a:

```python
class AtomResolution(BaseModel):
    """Canonical SCM result — the rich answer key."""
    spec_id: str
    result_type: str  # "difference", "ranking", "bool", ...
    measurements: dict[str, float | bool | dict]
    comparison: dict[str, Any]
    ground_truth: float | bool | str | dict[str, Any]
    seed: int
```

Y separar el chequeo:

```python
class AssertionCheck(BaseModel):
    """Evaluation of an Assertion against a resolution."""
    assertion: Assertion
    holds: bool
    score: float
```

**No hacerlo ahora.** El adaptador es suficiente. Promover cuando la
evidencia lo justifique.

## Proximos pasos

1. [x] Documentar contrato en docstring de AtomVerdict
2. [ ] Implementar `render_answer_key()` en oi_sq_compiler.py
3. [ ] Construir LLM relevance judge sobre la vista normalizada
4. [ ] E2E con seeds diversas
5. [ ] Evaluar si promover a AtomResolution
