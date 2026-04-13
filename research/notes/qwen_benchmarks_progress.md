# Qwen Benchmarks — Progress Log

> **Worktree:** `qwen-benchmarks`
> **Issues en scope:** I-010, I-011, I-012, I-013
> **Inicio:** 2026-04-12

## Fase 0 — Orientacion (completada 2026-04-12)

### Archivos leidos

| Archivo | Status |
|---|---|
| `research/synthesis/sreg_training_transfer_protocol.md` | Leido — canon |
| `research/archive/benchmark_results.md` | Leido — historico NO VALIDO |
| `issues/I-010-qwen-before-benchmarks.md` | Leido |
| `issues/I-011-causal-reasoning-benchmark.md` | Leido |
| `issues/I-012-scigym-integration.md` | Leido |
| `issues/I-013-qrdata-discoverybench-harness.md` | Leido |
| `scripts/run_benchmark.py` | Leido linea por linea |
| `src/sreg/benchmarks/cladder/adapter.py` | Leido |
| `src/sreg/benchmarks/qrdata/adapter.py` | Leido |
| `src/sreg/benchmarks/discoverybench/adapter.py` | Leido |
| `src/sreg/benchmarks/discoverybench/hms.py` | Leido |
| `src/sreg/models/benchmark.py` | Leido |
| `src/sreg/inference/openai_client.py` | Leido |
| `src/sreg/inference/tool_client.py` | Leido |
| `src/sreg/inference/protocol.py` | Leido |
| `src/sreg/agent/engine.py` | Leido |
| `src/sreg/agent/python_exec.py` | Leido |
| `scripts/serve_model.sh` | Leido |
| `.env` | Leido (copiado al worktree) |
| `research/archive/RL_frameworks_research_claude.md` | Leido |
| `research/synthesis/thesis_evaluation_framework.md` | Leido |

### AZURE_MODEL actual

`gpt-5.4` — este es el modelo reference "fuerte".
`gpt-5.2-codex` — solver model (no relevante para benchmarks).

### Decisiones alineadas con usuario (2026-04-12)

1. **Harness:** `--with-tools` obligatorio en TODOS los runs oficiales.
   Mismo SOLVER_TOOLS (python_exec + think) y mismo sandbox que el solver SREG.
   Razon: BEFORE, TRAIN y AFTER deben usar el mismo scaffold.
   **max_iterations=20** (igual que el solver en `oi_driver.py:329`).

2. **verifiers/prime-rl:** NO se instala para este worktree. El harness ya
   es compatible (mismos tools, misma interfaz OpenAI). verifiers es para
   training, no para eval.

3. **Qwen3-8B:** corre en H100 NVL 94GB via Azure ML + vLLM. Se configura
   despues de tener todo documentado y armado.

4. **Modelo reference:** `gpt-5.4` (AZURE_MODEL actual).

5. **.env:** copiado manualmente al worktree (no viaja por .gitignore).

6. **SciGym:** NO deferred. Corre en la H100 (Linux + Docker disponible).
   Se implementa como Pieza 5.

### Hallazgos importantes del codigo

1. **DiscoveryBench HMS judge usa el mismo client que el generador.**
   `adapter.score()` recibe el mismo `client` que `adapter.run()`.
   Viola oracle separation. Hay que fijar un judge model distinto.

2. **`ToolEnrichedClient` vs `engine.solve_question()`:** dos code paths
   para lo mismo (multi-turn con tools). Ambos usan los mismos SOLVER_TOOLS
   y python_exec. `engine.py` es mas sofisticado (usa `previous_response_id`
   para chaining server-side). Para consistencia, considerar migrar los
   adapters a usar `engine.solve_question()` directamente. No bloqueante
   para v1.

3. **`serve_model.sh` defaults:** `Qwen/Qwen2.5-0.5B-Instruct` — hay que
   cambiar a `Qwen/Qwen3-8B` (o `Qwen/Qwen3-8B-Instruct`) para runs reales.

4. **CLadder `_deterministic_subsample` tiene un bug sutil:** crea un `rng`
   con el seed pero despues crea `rng_copy` con el mismo seed para cada
   query_type group, ignorando el rng principal. El resultado es determinista
   pero no usa el seed de la forma esperada. No afecta reproducibilidad
   (es determinista dado un seed), pero es raro.

## Fase 1 — Harness Decisions (I-013)

Status: **COMPLETADA** (2026-04-12)

Ver `research/synthesis/harness_decisions_v1.md` para decisiones finales.

## Fase 2 — Infra Qwen

Status: **PENDIENTE** (gated en Azure ML H100)

## Fase 3 — Runs gpt-5.4 (reference model)

Status: **COMPLETADA** (2026-04-12)

### Fixes aplicados durante los runs

1. **ToolEnrichedClient bug critico:** multi-turn tool calling roto porque
   rebuildeaba el historial sin function_call items. Reescrito para usar
   `previous_response_id` chaining (mismo patron que engine.py).
   Archivos: `openai_client.py` (added previous_response_id + raw_input params),
   `tool_client.py` (rewritten loop).

2. **CRB dataset format:** causal_queries.json es dict-of-dicts, no list.
   Fix: `items = raw.values() if isinstance(raw, dict) else raw`.

3. **.gitignore:** cambiado `data/benchmarks/` a `data/` para cubrir todos
   los datasets descargados.

### Resultados gpt-5.4

| Benchmark | Score | Metric | N | Errors | vs Published |
|---|---|---|---|---|---|
| CLadder | 65.0% | accuracy | 100 | 8 | GPT-4: 62-70% -- in range |
| QRData | 52.0% | accuracy | 50 | 2 | GPT-4+CI: 57.9% -- slightly below |
| DiscoveryBench | 0.360 | HMS median | 25 | 0 | GPT-4o: 24.5% -- higher (model gen) |
| CRB | 43.5% | full_id_acc | 173 | 19 | SOTA: 30.1% -- +13pp |

Summaries committed: `research/benchmarks/before_v1/*_gpt-5.4.json`
Raw results (gitignored): `experiments/benchmarks/before_v1/`

### Observacion: tools sin acceso a datos

Los adapters truncan los CSVs a 50 filas en el prompt. python_exec esta
disponible pero no tiene acceso a los archivos originales. El modelo ve
datos truncados como texto. Esto es correcto para BEFORE — harness identico
para todas las condiciones.

## Fase 3b — Runs Qwen3-8B (target model)

Status: **PENDIENTE** (requiere H100 con vLLM)

## Fase 4 — CRB adapter (I-011)

Status: **COMPLETADA** (2026-04-12)

Adapter creado en `src/sreg/benchmarks/causalreasoning/adapter.py`.
Integrado en `scripts/run_benchmark.py` como `--benchmark crb`.

## Fase 5 — SciGym adapter (I-012)

Status: **PENDIENTE** (corre en H100 Azure ML — Linux + Docker)

## Fase 6 — Reporte consolidado

Status: **PENDIENTE** (gated en Fase 3b + 5)
