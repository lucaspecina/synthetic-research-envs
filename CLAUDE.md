# SREG — Claude Code Project Configuration

## Documentacion del proyecto — donde buscar cada cosa


| Documento            | Responde                                               | Leer                                  |
| -------------------- | ------------------------------------------------------ | ------------------------------------- |
| `PROJECT.md`         | Por que existe SREG, que principios no pueden violarse | Siempre antes de decisiones de diseno |
| `ARCHITECTURE.md`    | Como esta organizado el sistema objetivo               | Antes de implementar algo nuevo       |
| `CURRENT_STATE.md`   | Que parte de la arquitectura existe hoy                | Para saber que hay y que falta        |
| `TODO.md`            | Que trabajo esta pendiente, que problemas hay, inbox de ideas | Para saber que hacer                  |
| `CHANGELOG.md`       | Historia de cambios                                    | Cuando necesites contexto historico   |
| `research/`          | Analisis, hallazgos, sintesis                          | Cuando investigues o explores         |
| `research/README.md` | Reglas + indice de que investiga cada archivo           | Para saber que research existe        |


## Mantener la documentacion actualizada — CRITICO

**Esta es la regla mas importante de todo el archivo.** Si la documentacion
se desactualiza, todo lo demas deja de funcionar. Los otros docs se vuelven
mentira y las decisiones se toman sin informacion.

### Regla de promocion (TODO inbox → research → docs canonicos)

0. Idea cruda, problema, pregunta abierta → seccion "Inbox" de `TODO.md`
1. Se procesa en sesion → `research/notes/` (si necesita investigacion)
   o directamente a la seccion de analisis/implementacion de `TODO.md`
2. Se consolida con evidencia → `research/synthesis/`
3. Se vuelve decision → se promueve a `PROJECT.md` o `ARCHITECTURE.md`
4. Se implementa → `CURRENT_STATE.md` + `CHANGELOG.md`

### Como leer y mantener `research/`

1. Empezar siempre por `research/README.md`
2. Leer `research/synthesis/` antes que `research/notes/`
3. Usar `research/notes/` para detalle, debate, legado o evidencia de apoyo
4. Si creas o mueves un doc de research, actualizar el indice en
   `research/README.md` en el mismo cambio
5. Si un note deja de ser referencia activa, agregar una nota corta arriba
   apuntando a la sintesis o al doc canonico que corresponda

### Que actualizar despues de cada cambio


| Que cambio                         | Actualizar                                                            |
| ---------------------------------- | --------------------------------------------------------------------- |
| Completaste una tarea              | `TODO.md` + `CHANGELOG.md` + `CURRENT_STATE.md` si cambia capacidades |
| Agregaste/moviste archivo o modulo | `CLAUDE.md` si cambia el mapa del repo + `CURRENT_STATE.md` si cambia capacidades |
| Agregaste/moviste research doc     | `research/README.md` + referencias cruzadas o nota de status si hace falta |
| Cambiaste vision o principios      | `PROJECT.md` primero, propagar a `ARCHITECTURE.md` y `TODO.md`        |
| Nuevo hallazgo de research         | `research/notes/` o `research/synthesis/` + actualizar indice en `research/README.md` |
| Nuevo eval type o task type        | `CURRENT_STATE.md` + `ARCHITECTURE.md` si cambia la superficie        |
| Cambiaste orchestrator/agent/env   | Re-correr diagnostico para verificar que no degradaron los entornos   |
| Cambiaste dependencia              | `pyproject.toml` + tech stack de este archivo                         |
| Cambiaste convencion               | Este archivo, inmediatamente                                          |


### Commit workflow — MANDATORIO

```
1. Tests + Validation     (skip si doc-only)
   pytest + ruff + E2E

2. Codex review           (MANDATORIO si MCP disponible, skip si trivial)

3. Presentar al usuario   (SIEMPRE)
   Explicar en espanol. Pedir aprobacion.
   ESPERAR aprobacion. NO commitear sin ella.

4. Actualizar docs + Commit (solo DESPUES de aprobacion)

5. Sugerir proximos pasos
```

Ver `/precommit` skill para el protocolo completo.

## Project overview

SREG genera entornos sinteticos de investigacion con reward signals exactos,
para entrenar razonamiento cientifico via RL. Ver `PROJECT.md` para la
vision completa, `ARCHITECTURE.md` para el diseno del sistema.

**Terminologia clave:**

- **SRC** (Synthetic Research Case): la unidad de producto — world + problem + tasks + data
- **Teacher**: policy optima (inferencia bayesiana exacta, upper bound)
- **BN**: red bayesiana — la verdad formal oculta de cada SRC

## Environment setup

```bash
conda activate sreg
```

Python 3.11. Recrear: `conda create -n sreg python=3.11 -y && conda activate sreg && pip install -e ".[dev]"`

## Tech stack

- **pgmpy** — BN construction + inference (`DiscreteBayesianNetwork`, NOT `BayesianNetwork`)
- **networkx** — DAG validation (`nx.is_d_separator()`, NOT `nx.d_separated`)
- **numpy / scipy** — sampling, distributions
- **pydantic v2** — data contracts (`BaseModel`, not dataclass)
- **openai SDK** — LLM via Azure AI Foundry, Responses API (`client.responses.create`, NOT `chat.completions`)
- **pytest** + **ruff** (line length 100)

Env vars: `AZURE_INFERENCE_CREDENTIAL`, `AZURE_FOUNDRY_BASE_URL`, `AZURE_MODEL` (orchestrator),
`AZURE_SOLVER_MODEL` (solver, defaults to AZURE_MODEL)

## Project structure

```
src/sreg/
├── models/          # Pydantic contracts (World, Episode, Task, Score, DAGSpec, CasePlan...)
├── inference/       # LLM protocol (ModelClient, OpenAIClient, ToolEnrichedClient, responses_utils)
├── world/           # Templates, cpd_gen, DAG generators, pgmpy utils
├── solver/          # Teacher (exact Bayesian inference)
├── tools/           # WorldGen, WorldCheck, EpisodeGen, TaskGen, Verifier, ProblemBuilder
├── env/             # EpisodeRunner
├── orchestrator/    # LLM orchestrator (function calling, case design)
├── agent/           # Solver diagnostico (python_exec, engine, solve_case)
├── benchmarks/      # CLadder, QRData, DiscoveryBench adapters
├── training/        # SregEnv/verifiers adapter (experimental)
├── harness/         # DiagnosticRunner, trajectories, comparison
└── display.py

scripts/
├── generate_src.py        # Generar SRCs (--inspect, --solve, --report, PDF seeds)
├── run_benchmark.py       # Benchmarks externos (--with-tools, --base-url)
├── run_diagnostic.py      # N SRCs + metricas + failure modes
├── serve_model.sh         # vLLM setup
├── demo.py                # Demo sin LLM
├── view_case.py           # Inspeccionar casos exportados
├── view_trajectory.py     # Inspeccionar trayectorias
├── batch_sweep.py         # Parameter sweep
├── semantic_transform.py  # Transformar SRC a modo abstract/fictional
└── run_inspiration_reports.py  # Batch inspiration reports

seeds/               # Paper seeds (PDF, markdown)
experiments/         # Resultados de diagnostico
research/            # Analisis, hallazgos, sintesis (ver research/README.md)
tests/               # Mirrors src/ structure
.claude/skills/      # /plan, /status, /test, /review, /phase, /codex-collab
```

## Code conventions

- Type hints on public functions
- `__all__` exports in every `__init__.py`
- Tests mirror src: `src/sreg/tools/X.py` → `tests/tools/test_X.py`
- Imports: stdlib → third-party → local, separated by blank lines
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

- **Mandatory**: code review after implementation
- **Recommended**: strategy, design, problem-solving (use judgment)
- **Skip**: doc-only, trivial fixes

Claude leads, Codex advises. Present BOTH perspectives when disagreeing.
See `/codex-collab` skill for full protocol.

## Worktrees

Multiple Claude Code sessions MUST use worktrees (`claude --worktree <name>`).
Each worktree gets its own branch and working directory. Check at session start:

```bash
git rev-parse --git-dir   # "worktrees/" = you're in one
git branch --show-current
```

Rules: each session owns specific files, shared docs are danger zones,
merge via main session review (not blind merge). No active worktrees currently.
