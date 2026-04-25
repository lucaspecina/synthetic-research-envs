# P06 Addendum: Claim Cap Decision (2026-04-09)

## Relacion con el protocolo original

Este addendum **redefine** la pregunta del experimento P06
(`p06_interpretation_rule.md`, 2026-04-07). No lo reemplaza — el
protocolo original queda como registro historico. Este addendum corre
sobre el code state post-fixes (commits `2d96bca`, `4488a89`, `bb3a8cf`,
`23b1d69`, `fb7e206`) y responde una pregunta distinta y mas angosta.

## Pregunta exacta

> Bajo el prompt atomico actual y el codigo post-fixes (2026-04-09),
> conviene cap=5 o cap=15 para SREG v1?

**Lo que esta pregunta SI responde:**
- Cual es la configuracion optima de claim cap para congelar en v1.
- Si el solver produce mejores scores con mas espacio para claims atomicas.

**Lo que esta pregunta NO responde:**
- Si la intervencion original (prompt atomico + cap 15 vs prompt viejo +
  cap 5) mejoro el sistema. Eso seria otro experimento.
- Si el prompt atomico en si es mejor que el prompt viejo. El prompt
  atomico esta en ambas condiciones — no es variable.

## Diseno experimental

### Condiciones

| Aspecto | Control (cap=5) | Treatment (cap=15) |
|---------|-----------------|-------------------|
| src.json | Frozen de p05_canonical_batch | Idem |
| Codigo | Post-fixes (2026-04-09) | Idem |
| Solver prompt | Atomico actual | Idem |
| Solver model | gpt-5.2-codex | Idem |
| Compiler model | gpt-5.4 | Idem |
| Temperature | 0.0 | 0.0 |
| max_iterations | 20 | 20 |
| Seed / n_mc | Frozen de baseline | Idem |
| **MAX_CLAIMS** | **5** | **15** |

**Unica variable:** MAX_CLAIMS. Todo lo demas es identico.

### Casos

Los 12 casos de `p05_canonical_batch`. Lista:
chemical, competing_mech, confounding, coral_bleach, heterogeneity,
identifiability, immunotherapy, microbiome, missing_data, policy_equity,
poverty, selection_bias.

### Ejecucion

Cada caso se corre 2 veces (1 con cap=5, 1 con cap=15). Total: 24 runs.
Orden intercalado por caso para reducir drift temporal del modelo:
caso_1 cap=5, caso_1 cap=15, caso_2 cap=5, caso_2 cap=15, ...

### Outputs

- `results/p06_cap_decision/cap5/<case>/oi_result.json`
- `results/p06_cap_decision/cap15/<case>/oi_result.json`
- `results/p06_cap_decision/analysis.json` (verdicts automaticos)

## Criterios de lectura

### P1: Primary — correctness lift

El cap=15 produce mejor `correctness` que cap=5.

**Pasa si:**
- `mean(correctness_15) - mean(correctness_5) >= +0.03`
- Y `>= 8/12` casos tienen `delta_correctness > 0`

**Interpretacion:** si P1 pasa, cap=15 es estrictamente mejor para la
metrica principal. Si P1 falla, cap=5 es igual o mejor — congelar en 5.

### C1: Mecanismo — el solver usa el espacio extra

**Pasa si:**
- `mean(n_claims_15) > mean(n_claims_5) + 1.0` (el solver emite mas claims)

**Interpretacion:** si C1 no pasa, el solver ignora el espacio extra y
el cap es irrelevante. Congelar en el mas conservador (5).

### C2: Coverage alineada

**Pasa si:**
- `mean(weighted_coverage_15) - mean(weighted_coverage_5) >= +0.02`

**Interpretacion:** correctness sin coverage es tramposo (el solver
podria concentrarse en claims faciles). C2 verifica que el espacio extra
se usa para cubrir mas del brief, no para inflar score.

### C3: Total score

**Pasa si:**
- `mean(total_15) - mean(total_5) >= +0.02`

**Interpretacion:** check de coherencia. Total = correctness x
weighted_coverage. Si P1 y C2 pasan pero C3 falla, hay algo raro.

## Monitoreo (no son criterios de decision, pero se reportan)

### M1: Force-submit

Reportar `n_force_submit_5` vs `n_force_submit_15`. Si cap=15 causa
significativamente mas force-submits, el solver esta bajo presion de
tiempo (no de espacio) y el cap es irrelevante.

### M2: Evidence rejection (#25)

Reportar cuantos casos tuvieron `submit_claims` rechazado por
evidence_basis invalida y cuantos se recuperaron (resubmit exitoso).
Con #25, la fabricacion ya no es un confound silencioso — es un evento
observable.

### M3: Abstention rate

Reportar `mean(abstention_rate_5)` vs `mean(abstention_rate_15)`. Si
cap=15 genera mas abstenciones, el solver esta emitiendo claims que el
compiler no puede verificar.

### M4: Cap saturation

Reportar cuantos casos pegan contra el cap (n_claims == MAX_CLAIMS).
Si muchos casos pegan contra cap=15, considerar cap mas alto.

## Regla de decision

| P1 | C1 | Lectura | Accion |
|----|-----|---------|--------|
| PASS | PASS | Cap=15 es mejor y el solver lo usa | Congelar cap=15 |
| PASS | FAIL | Cap=15 es mejor pero el solver no usa el espacio | Raro. Investigar caso por caso |
| FAIL | PASS | El solver usa el espacio pero no mejora | Congelar cap=5 (mas claims != mejor) |
| FAIL | FAIL | Ni mejora ni usa el espacio | Congelar cap=5 |

C2 y C3 son corroboracion. Si P1+C1 pasan pero C2 falla, el lift es
real pero concentrado en claims faciles — aun asi congelar cap=15 pero
documentar la limitacion.

## Fuera de inferencia

- Calidad del prompt atomico (identica en ambas condiciones)
- Efecto de los bugfixes (#10, #24, #25) — identicos en ambas condiciones
- Calidad del compiler o del juez de relevancia
- Efecto del modelo LLM (mismo en ambas condiciones, temp 0.0)
- Comparacion con resultados historicos de P06 original

## Notas de implementacion

El harness (`scripts/p06_cap_decision.py`) parametriza MAX_CLAIMS via
CLI flag `--max-claims`. Internamente:
1. Monkey-patch de `open_investigation.MAX_CLAIMS` antes de crear runner
2. Tool definitions y prompt text deben referenciar MAX_CLAIMS (no
   hardcodear "15")
3. El scoring usa `claim_budget=MAX_CLAIMS` — debe reflejar la condicion
