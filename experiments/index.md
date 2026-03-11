# SREG Experiments Index

> Registro de experimentos de benchmark y diagnostico.
> Cada entrada referencia un directorio con resultados completos.

## Experimentos

| ID | Fecha | Descripcion | Casos | Estado |
|----|-------|------------|-------|--------|
| mini_20260311_100704 | 2026-03-11 | Primer mini benchmark: 3 SRCs reales via orchestrator + agent + teacher. Baseline inicial. | 3 | Completo |

### mini_20260311_100704

- **Objetivo**: obtener un baseline real antes de diseñar la infraestructura del benchmark.
- **Resultado**: orchestrator 100%, agent 100% submit, 1/3 beats random.
- **Hallazgos**: agente elige variables por sentido comun (no info gain), error de formato en submit (2/3), limitation mayor: solo evalua infer_target.
- **Archivos**: `mini_20260311_100704/summary.json`, `report.txt`, `config.json`, `cases/`
