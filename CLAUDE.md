# SREG — Claude Code Project Configuration

## LA PREGUNTA — el filtro de todo

> **Por que esto todavia no es una investigacion real? Que le falta?**

Cada decision, cada cambio, cada linea de codigo pasa por este filtro.
Si algo no se parece a investigacion real, es un bug. Si algo se parece
a un juego artificial, hay que eliminarlo o rediseniarlo.

## Principios de scoring — NO NEGOCIABLE

1. **UN solo metodo para todo** — sin scoring profiles por tipo de investigacion.
2. **El sistema se adapta a los casos** — el scoring no fuerza una forma.
3. **El brief es libre** — una pregunta, varias, vagos, mixtos: todo valido.
4. **No construir un juego** — si necesita "roles", "slots", "pattern_weights"
   para funcionar, es un juego, no evaluacion de investigacion.
5. **Verificacion es el core** — el SCM verifica. El scoring solo pregunta:
   es verdad? es relevante? cubrio lo pedido? no spameo?

Validar cambios de scoring contra los 23 escenarios:
`research/synthesis/investigation_scenarios_rubric.md`.

## Documentos del proyecto — que es cada uno y como mantenerlos

| Documento | Que es | Frecuencia de lectura |
|-----------|--------|----------------------|
| `PROJECT.md` | Estrella polar: vision, principios, invariantes. No cambia seguido. | Antes de decisiones de diseno |
| `ARCHITECTURE.md` | Referencia tecnica: componentes, contratos, flows. | Antes de implementar algo nuevo |
| `CURRENT_STATE.md` | Explicacion end-to-end amigable de como funciona el sistema HOY. Sin jerga interna. | Verificar que sigue siendo verdad despues de cada cambio |
| `TODO.md` | Trabajo pendiente + inbox de ideas. | Para saber que hacer |
| `CHANGELOG.md` | Historia de cambios de producto (no diario de sesion). | Despues de cada commit |
| `research/README.md` | Indice de investigacion. Apunta a synthesis/ y notes/. | Cuando agregues/muevas research docs |

### research/ — mantener limpio

- `synthesis/` = conclusiones consolidadas, pulidas. Referencia activa.
- `notes/` = working docs, debates, exploraciones. Pueden volverse legacy.
- `archive/` = legacy. Solo referencia historica.
- **REGLA: si un doc de notes/ ya no es relevante, moverlo a archive/ o borrarlo.**
  No dejar docs legacy donde alguien pueda encontrarlos y usarlos como si fueran actuales.
- Siempre actualizar `research/README.md` cuando muevas o crees un doc.

## Antes de cada commit — QUE ACTUALIZAR

Esto no es opcional. **Antes de commitear, revisar:**

1. **CURRENT_STATE.md** — el cambio afecta como funciona el sistema? Actualizar.
2. **CHANGELOG.md** — agregar entrada describiendo el cambio (producto, no internals).
3. **TODO.md** — completaste algo? Marcarlo. Surgio algo nuevo? Agregarlo.
4. **research/README.md** — cambiaste o creaste docs de research? Actualizar indice.
5. **ARCHITECTURE.md** — cambiaste componentes, contratos o flows? Actualizar.
6. **Tests y scripts** — el cambio deja tests o scripts obsoletos? Eliminarlos.

**Los docs no se actualizan "despues". Se actualizan COMO PARTE del cambio.**

## Commit workflow — MANDATORIO

```
1. Desarrollo + Tests (pytest modulo afectado + ruff)
2. Codex review + Fix (MANDATORIO si MCP disponible, skip si trivial)
3. Presentar al usuario — explicar en espanol, pedir aprobacion
   ESPERAR aprobacion. NO commitear sin ella.
4. Actualizar docs (ver lista arriba) + Commit
5. Sugerir proximos pasos
```

## Test execution — NO CORRER TESTS A LO LOCO

- Correr SOLO tests del modulo afectado, NO la suite completa.
- NO correr la misma suite en paralelo.
- Suite completa solo UNA VEZ antes del commit final.
- La validacion REAL es el E2E con LLM. Unit tests verifican que no se rompio nada.

## Evaluacion — 3 niveles

| Nivel | Que mide | Cuando |
|-------|----------|--------|
| L1 Tests (`pytest`) | Codigo funciona | Cada commit |
| L2 Diagnostico (`/eval`) | Entornos buenos (cuali + cuanti + no-data baseline) | Post-cambio generacion |
| L3 Transfer (futuro) | Entrenar en SREG mejora policies | Cuando haya policies |

## Environment setup

```bash
conda activate sreg  # Python 3.11
pip install -e ".[dev]"
```

## Tech stack

- **pgmpy** — BN (legacy): `DiscreteBayesianNetwork` (NOT `BayesianNetwork`)
- **networkx** — DAG: `nx.is_d_separator()` (NOT `nx.d_separated`)
- **numpy / scipy / pydantic v2** — sampling, distributions, contracts
- **openai SDK** — Responses API: `client.responses.create` (NOT `chat.completions`)
- **pytest** + **ruff** (line length 100)

Env vars: `AZURE_INFERENCE_CREDENTIAL`, `AZURE_FOUNDRY_BASE_URL`, `AZURE_MODEL`

## Project structure

```
src/sreg/
  models/        # Pydantic contracts
  inference/     # LLM protocol (ModelClient, Responses API)
  world/         # Templates, cpd_gen, DAG generators, SCM
  solver/        # Teacher (ExactBayes + SCMSolver)
  tools/         # WorldGen, TaskGen, Verifier, ProblemBuilder, OI pipeline
  env/           # EpisodeRunner
  orchestrator/  # LLM orchestrator (function calling)
  agent/         # Solver diagnostico (python_exec, solve_case)
  benchmarks/    # CLadder, QRData, DiscoveryBench
  training/      # SregEnv/verifiers adapter (experimental)
  harness/       # DiagnosticRunner, trajectories
scripts/         # generate_src.py, run_benchmark.py, etc.
tests/           # Mirrors src/ structure
research/        # Analisis y sintesis (ver research/README.md)
```

## Code conventions

- Type hints on public functions
- `__all__` exports in every `__init__.py`
- Tests mirror src: `src/sreg/tools/X.py` -> `tests/tools/test_X.py`
- Imports: stdlib -> third-party -> local, separated by blank lines
- Terminal output: ASCII-safe (Windows cp1252)
- Communicate with the user in **Spanish**

## Commands

```bash
pytest tests/ -v                          # All tests
pytest tests/tools/test_world_gen.py -v   # Specific file
ruff check src/ tests/                    # Lint
ruff format src/ tests/                   # Format
```

## Git conventions

- Branch naming: `feature/<name>`, `fix/<name>`, `refactor/<name>`
- Commit messages: imperative mood, concise
- Always ask user before pushing

## Codex collaboration

**Only when Codex MCP is available.** Codex = critical collaborator, not yes-man.
Mandatory for code review. Recommended for strategy/design. Skip for trivial fixes.
SIEMPRE reusar `threadId` existente con `codex-reply`. Sesion nueva solo si el tema
cambio completamente.

## Worktrees

Multiple sessions MUST use `claude --worktree <name>`. No active worktrees currently.
