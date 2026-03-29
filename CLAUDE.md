# SREG — Claude Code Project Configuration

## LA PREGUNTA — el filtro de todo

> **Por que esto todavia no es una investigacion real? Que le falta?**
>
> **Por que un modelo entrenado con RL sobre SREG todavia no aprenderia
> buen juicio cientifico?** Que le falta al sistema para ensenar:
> research taste, descomposicion de problemas, generacion de preguntas
> fine-grained, buen plan de investigacion, saber que es relevante para
> el objetivo y que no, saber cuando una conclusion es prematura vs
> bien fundada.

Cada decision pasa por este doble filtro:
1. Se parece a investigacion real? Si no, es un bug.
2. Entrenaria buen juicio cientifico (incluida relevancia)? Si no, redisenar.

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
7. **Skills, memorias, otros** — el cambio deja skills (`.claude/skills/`),
   memorias, o scripts con referencias obsoletas? Actualizarlos o eliminarlos.

**"Actualizar" no es solo docs del repo. Es TODO lo que referencia al sistema:
skills, memorias, scripts, configs. Si algo quedo desactualizado, arreglarlo.**

## Commit workflow — MANDATORIO

```
1. Desarrollo + Tests (pytest modulo afectado + ruff)
2. Codex review + Fix (MANDATORIO si MCP disponible, skip si trivial)
3. Presentar al usuario — explicar en espanol, pedir aprobacion
   ESPERAR aprobacion. NO commitear sin ella.
4. Actualizar docs (ver lista arriba) + Commit
5. Sugerir proximos pasos
```

## Test execution — MINIMO INDISPENSABLE

- **NUNCA correr la suite completa** salvo que el usuario lo pida explicitamente.
- Si cambias un archivo, correr SOLO el test de ese archivo. UNA VEZ.
- Si falla un import, arreglar el import — no re-correr toda la suite.
- **NUNCA** correr tests en paralelo ni repetir la misma suite.
- La validacion REAL es el E2E con LLM (`--oi`). Unit tests son secundarios.
- En caso de duda: NO correr tests. Preguntar al usuario.

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

- **networkx** — DAG: `nx.is_d_separator()` (NOT `nx.d_separated`)
- **numpy / scipy / pydantic v2** — sampling, distributions, contracts
- **openai SDK** — Responses API: `client.responses.create` (NOT `chat.completions`)
- **pytest** + **ruff** (line length 100)

Env vars: `AZURE_INFERENCE_CREDENTIAL`, `AZURE_FOUNDRY_BASE_URL`, `AZURE_MODEL`

## Project structure

```
src/sreg/
  models/        # Pydantic contracts (SCM, OI, tasks, episodes)
  inference/     # LLM protocol (ModelClient, Responses API)
  world/         # SCM engine (scm.py, expression compiler, scm_data)
  solver/        # SCMSolver (teacher / ground truth)
  tools/         # SCM pipeline + OI pipeline (compiler, verifier, salience, runner)
  orchestrator/  # LLM orchestrator (function calling, SCM-only)
  agent/         # python_exec + tool-calling engine (for OI solver)
  benchmarks/    # CLadder, QRData, DiscoveryBench
scripts/         # generate_src.py, run_benchmark.py
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
pytest tests/tools/test_scm_world_gen.py -v   # Specific file
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
