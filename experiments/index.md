# SREG Experiments Index

> Registro de diagnosticos de entornos (Level 2 QA).
> Cada entrada referencia un directorio con resultados completos.
>
> NOTA: estos son diagnosticos del generador, NO el benchmark real de SREG.
> El benchmark real es el experimento de transferencia (BEFORE/AFTER en
> benchmarks externos). Ver docs/EXTERNAL_BENCHMARKS.md.

## Experimentos

| ID | Fecha | Descripcion | Casos | Estado |
|----|-------|------------|-------|--------|
| mini_20260311_100704 | 2026-03-11 | Primer mini diagnostic: 3 SRCs reales via orchestrator + agent + teacher. Baseline inicial. | 3 | Completo |
| diag_20260311_first | 2026-03-11 | S.2 diagnostic: primer run multi-tipo. Agent en cada task. | 3 (11 tasks) | Completo |
| bench_20260311_5srcs | 2026-03-11 | DiagnosticRunner: 5 SRCs, 19 tasks, 9/9 eval types. Primer diagnostic completo. | 5 (19 tasks) | Completo |
| bench_20260311_15srcs | 2026-03-11 | DiagnosticRunner + baselines: 15 SRCs, 57 tasks, 9/9 eval types. Per-type baseline comparison. | 14/15 (57 tasks) | Completo |

### mini_20260311_100704

- **Objetivo**: obtener un baseline real antes de disenar la infraestructura del diagnostico.
- **Resultado**: orchestrator 100%, agent 100% submit, 1/3 beats random.
- **Hallazgos**: agente elige variables por sentido comun (no info gain), error de formato en submit (2/3), limitacion mayor: solo evalua infer_target.
- **Archivos**: `mini_20260311_100704/summary.json`, `report.txt`, `config.json`, `cases/`

### diag_20260311_first

- **Objetivo**: validar que el harness multi-tipo funciona E2E con orchestrator real.
- **Resultado**: 3/3 SRCs, 11 tasks, 7/9 tipos ejercitados, 91% submit, 0 format errors.
- **Hallazgos**: distribution types funcionan bien, choice types preliminarmente mixtos.
- **Archivos**: `diag_20260311_first/summary.json`, `report.txt`, `config.json`, `cases/`

### bench_20260311_5srcs

- **Objetivo**: primer diagnostic con DiagnosticRunner, cubrir los 9 eval types.
- **Resultado**: 5/5 SRCs, 19 tasks, 9/9 tipos ejercitados, 100% submit, 0 format errors.
- **Hallazgos**:
  - infer_target consistente (5/5 GOOD+, KL 0.07-0.32)
  - causal_effect aceptable (KL medio 0.49)
  - ZERO_OBS_CORRECT en 4/19 tasks (choice types binarios — podria ser azar)
  - INCORRECT en 3/19 tasks (adjustment_set, compare, hypothesis)
  - N por tipo todavia bajo (1-5) para separar ruido de patron
- **Archivos**: `bench_20260311_5srcs/summary.json`, `report.txt`, `config.json`

### bench_20260311_15srcs

- **Objetivo**: mas evidencia por eval type + baseline comparison.
- **Resultado**: 14/15 SRCs, 57 tasks, 9/9 tipos, 95% submit.
- **Hallazgos**:
  - causal_effect y compare_interventions beat baseline 71%
  - hypothesis_selection PEOR que azar (17% beats baseline)
  - NBO sospechoso (100% correct, 100% ZERO_OBS)
  - should_condition 25%, infer_latent_cause 0% beats baseline
- **Archivos**: `bench_20260311_15srcs/summary.json`, `report.txt`, `config.json`
