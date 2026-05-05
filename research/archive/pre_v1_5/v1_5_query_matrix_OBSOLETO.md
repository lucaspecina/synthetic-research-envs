# Query Matrix canónica — Verifier v1.5 (16 query_kinds)

> Spec congelada de los 16 query_kinds soportados por el Verifier en v1.5.
> Cada query_kind define: env requerido, args, shape canónico de
> `AnswerKey.numeric`. Esta matrix es la fuente de verdad — el código
> del Verifier la respeta y los tests la validan.
>
> NO se incluyen query_kinds SDE (eso entra en v1.6 con `noise_response`
> y distribuciones para `time_to_event`).

---

## Convenciones

- **`env`**: tipo de Environment requerido (`scm` o `ode`).
- **`args`**: argumentos del `VerifierQuery.args`. Tipos Python.
- **`numeric`**: shape canónico del `AnswerKey.numeric` que el verifier produce.
- **`summary`**: el `AnswerKey.summary` se redacta a partir de `numeric`. No tipado, lo escribe el `Question Designer` o un helper.

Todos los query_kinds toman además un `seed: int | None = None` opcional implícito (no se lista) para reproducibilidad.

**Sample size para SCM**: NO va en `args` — es presupuesto numérico, no semántica del query. Vive en `VerifierConfig` (default interno del verifier, ej. `n=10000`). En `numeric` queda como provenance: `n_samples`.

**`t_horizon` vs `t_eval` para ODE**: usar `t_horizon` cuando lo semántico es "hasta cuándo simular" y el verifier puede elegir la grilla interna (`equilibrium`, `parameter_sensitivity`, `time_to_event`). Usar `t_eval` solo cuando importan los puntos exactos reportados (`trajectory_summary`).

**Enum `regime`** (compartido entre `phase_portrait_topology` y `bifurcation_threshold`):
`Literal["stable_node", "unstable_node", "saddle", "limit_cycle", "mixed"]`.

---

## SCM (10 query_kinds)

### 1. `ate` — Average Treatment Effect

- **env**: `scm`
- **args**:
  ```python
  treatment: str
  outcome: str
  treatment_value: float = 1.0
  control_value: float = 0.0
  ```
- **numeric**:
  ```python
  {
      "ate": float,                                 # E[Y|do(T=tv)] - E[Y|do(T=cv)]
      "effect_direction": Literal["positive", "negative", "null"],
      "std_error": float,
      "ci_low": float,                              # 95% CI
      "ci_high": float,
      "n_samples": int,                             # provenance del sample size usado
  }
  ```

### 2. `association` — asociación cruda observacional

- **env**: `scm`
- **args**:
  ```python
  var1: str
  var2: str
  kind: Literal["correlation", "covariance"] = "correlation"
  ```
- **numeric**:
  ```python
  {
      "value": float,                       # correlación o covarianza
      "kind": str,                          # "correlation" | "covariance"
      "direction": Literal["positive", "negative", "null"],
      "ci_low": float,
      "ci_high": float,
      "n_samples": int,
  }
  ```
- **Scope**: asume variables continuas o binarias. Para categóricas con >2 niveles, escalar después.

### 3. `conditional_association` — asociación condicional

- **env**: `scm`
- **args**:
  ```python
  var1: str
  var2: str
  condition_on: list[str]               # variables a condicionar (como controls de regresión)
  ```
- **numeric**:
  ```python
  {
      "partial_correlation": float,
      "direction": Literal["positive", "negative", "null"],
      "condition_set": list[str],
      "ci_low": float,
      "ci_high": float,
      "n_samples": int,
  }
  ```
- **Scope**: asume variables continuas o binarias.

### 4. `heterogeneity` — efecto modificado por subgrupo

- **env**: `scm`
- **args**:
  ```python
  treatment: str
  outcome: str
  modifier: str                                # variable que potencialmente modifica el efecto
  modifier_strata: list[Any] | None = None     # si None, usa los valores únicos del modifier
  ```
- **numeric**:
  ```python
  {
      "ate_overall": float,
      "ate_by_stratum": dict[str, float],   # str(stratum_value) -> ate
      "heterogeneity_present": bool,        # max - min > umbral
      "heterogeneity_magnitude": float,     # max - min de los ATE
      "n_samples": int,
  }
  ```

### 5. `mediation_decomposition` — descomposición direct/indirect (interventional)

- **env**: `scm`
- **args**:
  ```python
  treatment: str
  outcome: str
  mediator: str
  mediator_value: float      # valor fijo del mediador para el controlled direct effect
  ```
- **numeric**:
  ```python
  {
      "total_effect": float,
      "controlled_direct_effect": float,     # E[Y|do(T=1, M=mediator_value)] - E[Y|do(T=0, M=mediator_value)]
      "indirect_effect": float,              # total - direct
      "proportion_mediated": float,          # indirect / total (puede ser inestable si total ~ 0)
      "mediator_value": float,               # provenance: el m0 usado
      "n_samples": int,
  }
  ```
- **Scope (importante)**: en MVP esta descomposición es **interventional** (controlled direct effect), NO natural direct/indirect effect (que requiere muestreo cross-world counterfactual). Si en el futuro se agrega soporte para natural effects, será un query_kind aparte.

### 6. `confounding_gap` — gap entre asociación cruda y efecto causal

- **env**: `scm`
- **args**:
  ```python
  treatment: str
  outcome: str
  ```
- **numeric**:
  ```python
  {
      "crude_association": float,                        # asociación observacional
      "causal_ate": float,                               # ATE post-do
      "gap": float,                                      # crude - causal
      "gap_direction": Literal["positive", "negative", "null"],
      "confounding_present": bool,                       # |gap| > umbral interno
      "n_samples": int,
  }
  ```

### 7. `rank_order` — ranking de drivers sobre un outcome

- **env**: `scm`
- **args**:
  ```python
  outcome: str
  candidates: list[str]              # variables candidatas a "driver"
  ```
- **numeric**:
  ```python
  {
      "ranking": list[dict],         # [{variable: str, ate: float, abs_ate: float}, ...] ordenado por |ate| desc
      "top_driver": str,             # primero del ranking
      "n_samples": int,
  }
  ```

### 8. `threshold_scan` — efecto en función del nivel del tratamiento

- **env**: `scm`
- **args**:
  ```python
  treatment: str
  outcome: str
  threshold_grid: list[float]        # valores del tratamiento a probar
  baseline: float = 0.0              # valor de referencia para el contraste
  ```
- **numeric**:
  ```python
  {
      "effects_at_thresholds": list[dict],   # [{threshold: float, effect: float}, ...]
      "monotonic": bool,
      "sign_change_at": float | None,        # primer threshold donde cambia el signo
      "n_samples": int,
  }
  ```

### 9. `identifiability_status` — ¿es identificable este efecto?

- **env**: `scm`
- **args**:
  ```python
  treatment: str
  outcome: str
  observable_set: list[str] | None = None  # si None, usa todas las variables observables
  ```
- **numeric**:
  ```python
  {
      "identifiable": bool,
      "valid_adjustment_sets": list[list[str]],    # sets backdoor válidos ([] si no identificable)
      "minimal_adjustment_set": list[str] | None,  # el más chico de la lista anterior
      "reason_code": Literal[
          "identifiable_with_backdoor",
          "identifiable_no_adjustment_needed",
          "not_identifiable_unblocked_backdoor",
          "not_identifiable_collider_only",
          "not_identifiable_latent_confounder",
      ],
  }
  ```
- **Nota**: la prosa explicativa va en `AnswerKey.summary`, NO en `numeric`. `reason_code` permite anchors estructurados.

### 10. `subgroup_ate` — ATE condicional a un subgrupo

- **env**: `scm`
- **args**:
  ```python
  treatment: str
  outcome: str
  treatment_value: float = 1.0
  control_value: float = 0.0
  subgroup: dict[str, float]                # filtro de condicionamiento (ej: {modifier: 1.0})
  ```
- **numeric**:
  ```python
  {
      "subgroup_ate": float,                                  # E[Y|do(T=tv), subgroup] - E[Y|do(T=cv), subgroup]
      "effect_direction": Literal["positive", "negative", "null"],
      "subgroup": dict[str, float],
      "ci_low": float,
      "ci_high": float,
      "n_samples": int,
  }
  ```
- **Nota**: este NO es un counterfactual a la Pearl/Rubin (potential outcomes a nivel individual con datos counterfactual). Es un ATE interventional condicionado a subgrupo. Counterfactual real requeriría backend SCM dedicado (no en MVP).

---

## ODE (6 query_kinds)

### 11. `equilibrium` — punto fijo / steady state

- **env**: `ode`
- **args**:
  ```python
  initial: dict[str, float]
  t_horizon: float                    # cuánto tiempo simular
  tolerance: float = 1e-3             # umbral de "ya alcanzó equilibrio"
  parameters: dict[str, float] | None = None  # override de params del WorldModel
  ```
- **numeric**:
  ```python
  {
      "reached": bool,                # si la trayectoria se estabilizó dentro del horizon
      "equilibrium": dict[str, float] | None,  # valor de cada variable en equilibrio
      "time_to_equilibrium": float | None,
  }
  ```

### 12. `trajectory_summary` — resumen estadístico de una trayectoria

- **env**: `ode`
- **args**:
  ```python
  initial: dict[str, float]
  t_eval: list[float]                 # puntos temporales a evaluar
  target: str                         # variable de interés
  parameters: dict[str, float] | None = None
  ```
- **numeric**:
  ```python
  {
      "peak_value": float,
      "peak_time": float,
      "settling_time": float | None,  # tiempo a 95% del valor final
      "oscillates": bool,
      "oscillation_period": float | None,
      "amplitude": float | None,
      "final_value": float,
  }
  ```

### 13. `parameter_sensitivity` — sensibilidad a un parámetro

- **env**: `ode`
- **args**:
  ```python
  parameter: str
  parameter_grid: list[float]         # valores del parámetro a barrer
  target: str                         # qué medir (ej: peak_value, equilibrium[target])
  metric: Literal["peak_value", "equilibrium", "final_value"] = "equilibrium"
  initial: dict[str, float]
  t_horizon: float
  ```
- **numeric**:
  ```python
  {
      "sensitivity_curve": list[dict], # [{parameter_value: float, target_metric: float}, ...]
      "elasticity_at_default": float | None,  # sensibilidad relativa cerca del valor default
      "monotonic": bool,
  }
  ```

### 14. `phase_portrait_topology` — clasificación de equilibrios

- **env**: `ode`
- **args**:
  ```python
  parameters: dict[str, float] | None = None    # override de params
  search_grid: dict[str, list[float]] | None = None  # grid para buscar puntos fijos
  ```
- **numeric**:
  ```python
  {
      "equilibria": list[dict],  # [{state: dict, stability: Literal["stable", "unstable", "saddle"]}]
      "limit_cycles": list[dict],  # [{period: float, amplitude: float}] (puede ser [])
      "regime": Literal["stable_node", "unstable_node", "saddle", "limit_cycle", "mixed"],
  }
  ```
- **Nota**: `regime` usa el enum compartido (ver "Convenciones").

### 15. `bifurcation_threshold` — parámetro de bifurcación

- **env**: `ode`
- **args**:
  ```python
  parameter: str
  parameter_range: tuple[float, float]
  n_samples: int = 50
  parameters: dict[str, float] | None = None
  ```
- **numeric**:
  ```python
  Regime = Literal["stable_node", "unstable_node", "saddle", "limit_cycle", "mixed"]
  {
      "bifurcation_value": float | None,         # primer parámetro donde cambia la topología (None si no hay)
      "regime_before": Regime,
      "regime_after": Regime,
      "regime_changes": list[dict],              # [{parameter_value: float, from_regime: Regime, to_regime: Regime}]
  }
  ```
- **Nota**: usa el mismo enum `regime` que `phase_portrait_topology`.

### 16. `time_to_event` — primer cruce de un umbral

- **env**: `ode`
- **args**:
  ```python
  initial: dict[str, float]
  target: str                         # variable a monitorear
  threshold: float                    # valor a cruzar
  direction: Literal["above", "below"] = "above"
  t_horizon: float
  parameters: dict[str, float] | None = None
  ```
- **numeric**:
  ```python
  {
      "reached": bool,
      "time_to_event": float | None,  # None si no se alcanzó dentro del horizon
      "value_at_horizon": float,
  }
  ```

---

## Reglas operativas

1. **Determinismo**: dado el mismo WorldModel + args + seed, todos los query_kinds devuelven exactamente el mismo `numeric`. Tests de roundtrip y reproducibilidad lo verifican.

2. **Independencia de v2 (multi-turno)**: ningún query_kind asume capacidad interactiva. Los args declaran todo lo que el query necesita; el verifier no "pregunta más" al environment.

3. **`subgroup` y `condition_on` viven en los args**, NO en el Environment. (Crítica explícita de Codex en diseño.)

4. **`AnswerKey.summary`** es texto NL libre que el `Question Designer` redacta usando `numeric`. NO es producido automáticamente por el Verifier en MVP.

5. **Errores recuperables**: si un cómputo falla por motivo legítimo (ej: bifurcación no encontrada, equilibrium no alcanzado), el `numeric` registra `reached: False` o equivalente. NO se lanza excepción.

6. **Errores no recuperables**: args inconsistentes, variables que no existen en el WorldModel, environment incompatible con `query_kind` → ValueError explícito.
