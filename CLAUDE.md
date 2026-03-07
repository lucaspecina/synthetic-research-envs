# SREG — Claude Code Project Configuration

## Project overview

SREG (Synthetic Research Environment Generator) generates fictional but causally coherent
Bayesian network worlds for evaluating LLM scientific reasoning.

## Environment setup

```bash
conda activate sreg
```

Conda env `sreg` with Python 3.11. Recreate: `conda create -n sreg python=3.11 -y && conda activate sreg && pip install -e ".[dev]"`

## Tech stack

- **pgmpy** — Bayesian network construction and exact inference (`DiscreteBayesianNetwork`, not `BayesianNetwork`)
- **networkx** — DAG validation (`nx.is_d_separator()`, not `nx.d_separated`)
- **numpy / scipy** — sampling, distribution operations
- **pydantic v2** — data contracts (BaseModel, not dataclass)
- **openai SDK** — LLM calls via Azure AI Foundry (see below)
- **pytest** — testing
- **ruff** — linting and formatting (line length 100)

## LLM consumption — Azure AI Foundry

Use `OpenAI`/`AsyncOpenAI` with `base_url`. **Do NOT use `AzureOpenAI`.**
See `src/sreg/orchestrator/orchestrator.py` for the pattern.
Env vars: `AZURE_INFERENCE_CREDENTIAL`, `AZURE_FOUNDRY_BASE_URL`

## Project structure

```
src/sreg/
├── models/          # Pydantic data contracts (world, episode, task, teacher, score)
├── world/           # World model, templates, pgmpy utils
├── solver/          # Teacher solver (exact Bayesian inference)
├── tools/           # WorldGen, WorldCheck, EpisodeGen, TaskGen, Verifier
├── env/             # EpisodeRunner (step-by-step environment interface)
├── orchestrator/    # LLM orchestrator loop (system prompt, tool definitions)
└── harness/         # Dataset generation + agent evaluation (Phase 7)

tests/               # Mirrors src/ structure
docs/
├── IMPLEMENTATION_PLAN.md   # Phase-by-phase build plan
└── references/              # Original design docs (read-only)

.claude/skills/      # Project skills: /plan, /status, /test, /review, /phase
```

## Code conventions

- Type hints on all public functions
- Module-level `__all__` exports in every `__init__.py`
- Tests mirror src: `src/sreg/tools/world_gen.py` → `tests/tools/test_world_gen.py`
- Imports: stdlib → third-party → local, separated by blank lines

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
- Run tests before committing
- Update `CHANGELOG.md` and `TODO.md` with every meaningful change

## Maintenance rules

1. **Complete a task** → mark done in `TODO.md`, add entry to `CHANGELOG.md`
2. **Start a new phase** → update `docs/IMPLEMENTATION_PLAN.md` status
3. **Add a module** → update project structure above
4. **Add a dependency** → add to `pyproject.toml` and tech stack above
5. **Change conventions** → update this file immediately
6. **Change scope** → update `PROJECT.md` first, then propagate
7. **Add/change a NodeType** → update `_node_styles()` and `_HTML_NODE_COLORS` in `src/sreg/display.py`
8. **Add a new display need** → add function to `display.py`, update `scripts/demo.py` and notebook
