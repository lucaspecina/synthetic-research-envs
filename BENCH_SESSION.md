# Session B — Benchmark Suite

> **LEE ESTO PRIMERO si estas en el worktree `benchmark-suite`.**
> Este documento define tu rol, scope, y prioridades. No sigas el TODO.md
> general — ahi estan las tareas del generador (Session A). Tu trabajo es otro.

## Tu rol

Sos la **Session B**: investigacion y construccion de la infraestructura de
benchmarks externos para evaluacion de transferencia (BEFORE/AFTER).

Tu objetivo: obtener los **scores BEFORE** de modelos (Qwen3-8B, GPT) en
benchmarks externos, para despues comparar con los scores AFTER de entrenar
en SREG.

## Sesiones paralelas (NO tocar su territorio)

| Session | Worktree | Foco | Territorio |
|---------|----------|------|------------|
| **A** | `main` | Generador de entornos (intervenciones, E2E, orchestrator) | `src/sreg/world/`, `tools/`, `orchestrator/`, `agent/`, `harness/` |
| **B (vos)** | `benchmark-suite` | Benchmarks externos + evaluacion de transferencia | `src/sreg/benchmarks/`, `src/sreg/inference/openai_client.py` |
| **C** | `rl-env-verifiers` | Integracion SREG con verifiers/prime-rl para RL training | `src/sreg/training/` |

## Que HACER

1. **Adapters de benchmarks externos**: CLadder, DiscoveryBench, SciGym
2. **OpenAI adapter** para `ModelClient` protocol (conecta con Azure/OpenAI/vLLM)
3. **Scripts para correr benchmarks**: `scripts/run_benchmark.py`
4. **Guardar resultados** con `BenchmarkResult` (metadata de reproducibilidad)
5. Scope basico: pregunta -> modelo -> respuesta -> score. Sin harness agentivo sofisticado.

## Que NO tocar

### Contratos Fase -1 (interfaz estable, compartida entre sesiones)
- `src/sreg/inference/protocol.py` — ModelClient Protocol
- `src/sreg/models/benchmark.py` — BenchmarkResult, BenchmarkComparison
- `src/sreg/models/code_exec.py` — CodeExecConfig, CodeExecResult
- `src/sreg/models/env_protocol.py` — SREGEnvironment Protocol
- `src/sreg/models/agent_tools.py` — AgentTool, AgentToolset

### Territorio de otras sesiones
- `src/sreg/world/`, `src/sreg/tools/`, `src/sreg/orchestrator/` — Session A
- `src/sreg/training/` — Session C
- `src/sreg/agent/`, `src/sreg/harness/` — Session A

## Archivos de esta session

```
src/sreg/
  inference/
    openai_client.py          # ModelClient -> OpenAI SDK adapter
  benchmarks/
    __init__.py
    cladder/
      __init__.py
      adapter.py              # CLadderAdapter: load, prompt, score
    qrdata/
      __init__.py
      adapter.py              # QRDataAdapter: load, prompt, score (numeric + MC)
    discoverybench/           # (pendiente)
    scigym/                   # (futuro)

tests/
  inference/
    test_openai_client.py     # 12 tests
  benchmarks/
    test_cladder.py           # 41 tests
    test_qrdata.py            # 43 tests

scripts/
  run_benchmark.py            # CLI: --benchmark cladder|qrdata --model X --subset dev|all|causal
```

## Estado actual

### Hecho
- [x] Investigacion: SOTA en frameworks de eval + como ejecutan CLadder/DiscoveryBench/SciGym
- [x] OpenAI adapter para ModelClient (openai_client.py) + reasoning model compat (gpt-5.2-chat)
- [x] CLadder adapter (load, run, score, save_results) + Codex fixes (error tracking, parser robusto, max_tokens)
- [x] QRData adapter (load, run, score con tolerancia 3% + MC prefix match, subsets causal/statistical)
- [x] Tests unitarios (135 de benchmarks, 901 total)
- [x] Script run_benchmark.py (CLadder + QRData + DiscoveryBench)
- [x] Datasets descargados (CLadder 10K + QRData 411 + 195 CSVs + DiscoveryBench 25 train)
- [x] **BEFORE scores con gpt-5.2-chat** (2026-03-13)
  - CLadder dev (100): **78%** (rung1=100%, rung2=70%, rung3=67.5%)
  - QRData dev (50): **38%** (causal=43.8%, stat=27.8%)
  - Resultados en `docs/BENCHMARK_RESULTS.md` y `experiments/benchmarks/`
- [x] **DiscoveryBench adapter** (2026-03-13)
  - HMS scorer via LLM judge (decompose + context match + variable F1 + relationship acc)
  - Train split only (25 examples with gold). Test split held-out.
  - Full train (25 examples): **0.299 HMS** (biology=0.427, econ=0.215, socio=0.213)
  - 39 tests
- [x] **Validacion vs literatura** — los 3 benchmarks son consistentes con scores publicados

### Pendiente
- [ ] Correr Qwen3-8B BEFORE scores (cuando haya acceso)
- [ ] SciGym adapter (futuro, requiere Linux/Docker por stack SBML)

## Benchmarks elegidos

| Benchmark | Tipo | Scoring | Prioridad |
|-----------|------|---------|-----------|
| **CLadder** | 10K preguntas yes/no sobre causalidad (3 rungs de Pearl) | Determinista (accuracy) | **1 — arranca aca** |
| **DiscoveryBench** | Hipotesis desde datos tabulares (CSVs) | LLM-judge (HMS, no determinista) | 2 |
| **SciGym** | Ciclo experimental multi-turn (biologia, SBML) | Determinista (GED, STE) | 3 (futuro) |

## Decisiones de diseno

- **Runner propio minimo**, no inspect_ai ni lm-eval-harness. SREG ya tiene ModelClient + BenchmarkResult.
- **Sin harness agentivo**: scope basico = pregunta -> modelo -> respuesta -> score.
- **Subsampling determinista**: dev subset (100 ejemplos) para iterar rapido, full dataset para eval.
- **Per-example JSONL**: guardar cada resultado individual, no solo agregados.
- **Pinnear versiones de dataset**: reproducibilidad total.

## Reglas de trabajo

1. Lee CLAUDE.md para convenciones de codigo, git, y testing
2. Workflow: codigo+tests -> Codex review -> presentar al usuario -> user aprueba -> docs+commit
3. **NUNCA commitear sin aprobacion del usuario**
4. Comunicar en espanol, amigable y detallado
5. Consultar Codex como second opinion para decisiones importantes
