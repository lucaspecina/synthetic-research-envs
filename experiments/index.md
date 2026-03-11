# SREG Experiments Index

> Registro de experimentos de benchmark y diagnostico.
> Cada entrada referencia un directorio con resultados completos.

## Experimentos

| ID | Fecha | Descripcion | Casos | Estado |
|----|-------|------------|-------|--------|
| mini_20260311_100704 | 2026-03-11 | Primer mini benchmark: 3 SRCs reales via orchestrator + agent + teacher. Baseline inicial. | 3 | Completo |
| diag_20260311_first | 2026-03-11 | S.2 diagnostic: primer run multi-tipo. Agent en cada task. | 3 (11 tasks) | Completo |
| bench_20260311_5srcs | 2026-03-11 | BenchmarkRunner: 5 SRCs, 19 tasks, 9/9 eval types. Primer benchmark completo. | 5 (19 tasks) | Completo |

### mini_20260311_100704

- **Objetivo**: obtener un baseline real antes de diseñar la infraestructura del benchmark.
- **Resultado**: orchestrator 100%, agent 100% submit, 1/3 beats random.
- **Hallazgos**: agente elige variables por sentido comun (no info gain), error de formato en submit (2/3), limitation mayor: solo evalua infer_target.
- **Archivos**: `mini_20260311_100704/summary.json`, `report.txt`, `config.json`, `cases/`

### diag_20260311_first

- **Objetivo**: validar que el harness multi-tipo funciona E2E con orchestrator real.
- **Resultado**: 3/3 SRCs, 11 tasks, 7/9 tipos ejercitados, 91% submit, 0 format errors.
- **Hallazgos**: distribution types funcionan bien, choice types preliminarmente mixtos.
- **Archivos**: `diag_20260311_first/summary.json`, `report.txt`, `config.json`, `cases/`

### bench_20260311_5srcs

- **Objetivo**: primer benchmark con BenchmarkRunner, cubrir los 9 eval types.
- **Resultado**: 5/5 SRCs, 19 tasks, 9/9 tipos ejercitados, 100% submit, 0 format errors.
- **Hallazgos**:
  - infer_target consistente (5/5 GOOD+, KL 0.07-0.32)
  - causal_effect aceptable (KL medio 0.49)
  - ZERO_OBS_CORRECT en 4/19 tasks (choice types binarios — podria ser azar)
  - INCORRECT en 3/19 tasks (adjustment_set, compare, hypothesis)
  - N por tipo todavia bajo (1-5) para separar ruido de patron
- **Archivos**: `bench_20260311_5srcs/summary.json`, `report.txt`, `config.json`
