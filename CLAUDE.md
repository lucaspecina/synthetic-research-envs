# SREG — Claude Code Project Configuration

## START HERE — Read these docs first

Before doing anything, understand the project by reading these docs in order:

1. **`PROJECT.md`** — **THE vision document.** This is the soul of the project.
   Read it to understand WHY we build what we build, not just WHAT.
   Every technical decision, every implementation choice, every TODO must align
   with the spirit described here. When in doubt about any decision, go back
   to PROJECT.md — it's the ultimate source of truth for the project's direction.
2. **`docs/CURRENT_STATE.md`** — What exists today, what's implemented, what's missing.
3. **`docs/IMPLEMENTATION_PLAN.md`** — Detailed phase-by-phase plan (9 phases).
4. **`TODO.md`** — Concrete task tracking per phase.
5. **`CHANGELOG.md`** — History of what's been done.

## Project overview

SREG (Synthetic Research Environment Generator) generates **fictional but realistic
research problems** for evaluating LLM scientific reasoning.

### Two-layer architecture (the core concept)

Every research problem has two layers:

- **Formal layer (hidden)**: A Bayesian network (DAG + CPDs) that defines the
  mathematical truth. The agent never sees this. All evaluation is against this.

- **Semantic layer (visible)**: A realistic presentation of the problem — narrative
  context, datasets, named variables, available experiments, research questions.
  This is what the agent sees, like what a real researcher would receive.

### Key design principles

- **The BN is always the truth.** Every question has a mathematically verifiable answer.
- **Semi-real naming**: real scientific vocabulary (`water_temperature`) in fictional
  domains ("planet Kepler-442"). Not `indicator_1`, not `zorbax_flux`.
- **Agent freedom**: the agent can reason however it wants (analyze, hypothesize, code).
  Only "real-world actions" (experiments, measurements) cost budget.
- **Data is configurable**: tabular datasets, isolated observations, experimental results,
  multiple datasets, partial/incomplete data — all sampled from the BN.
- **Multiple evaluation types**: target inference (KL), causal effects, hypothesis
  selection, structure discovery, next-best-action, optimization — see PROJECT.md.
- **LLM orchestrates, tools own truth**: the LLM proposes structure and semantics,
  programmatic tools build and verify the math.

### Current state

Phases 1-7 complete (formal engine + semantic layer + agent solver). 153 tests passing.
**Next: Phase 8 (more templates + tasks)** — causal chain, fork/collider,
new task types. Then Phase 9 (dataset gen + eval harness).

See `docs/CURRENT_STATE.md` for full details.

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
- **python-dotenv** — auto-load `.env` for credentials
- **pytest** — testing
- **ruff** — linting and formatting (line length 100)

## LLM consumption — Azure AI Foundry

Use `OpenAI`/`AsyncOpenAI` with `base_url`. **Do NOT use `AzureOpenAI`.**
See `src/sreg/orchestrator/orchestrator.py` for the pattern.
Env vars: `AZURE_INFERENCE_CREDENTIAL`, `AZURE_FOUNDRY_BASE_URL`, `AZURE_MODEL`

## Project structure

```
src/sreg/
├── models/          # Pydantic data contracts (world, episode, task, teacher, score)
├── world/           # World model, templates, pgmpy utils
├── solver/          # Teacher solver (exact Bayesian inference)
├── tools/           # WorldGen, WorldCheck, EpisodeGen, TaskGen, Verifier
├── env/             # EpisodeRunner (step-by-step environment interface)
├── orchestrator/    # LLM orchestrator loop (system prompt, tool definitions)
├── agent/           # LLM agent solver (Phase 7)
├── display.py       # Dual-mode pretty printing (terminal ANSI + notebook HTML)
└── harness/         # Dataset generation + agent evaluation (Phase 9)

scripts/
├── demo.py                # Terminal demo: world gen + teacher solving
├── test_orchestrator.py   # Step-by-step orchestrator run with real LLM
└── test_agent.py          # Agent vs teacher vs random baseline comparison

notebooks/
└── 01_explore_system.ipynb  # Interactive exploration

tests/               # Mirrors src/ structure

docs/
├── IMPLEMENTATION_PLAN.md   # Phase-by-phase build plan (9 phases)
├── CURRENT_STATE.md         # Detailed current state description
└── references/              # Original design docs (read-only)

.claude/skills/      # Project skills: /plan, /status, /test, /review, /phase
```

## Code conventions

- Type hints on all public functions
- Module-level `__all__` exports in every `__init__.py`
- Tests mirror src: `src/sreg/tools/world_gen.py` → `tests/tools/test_world_gen.py`
- Imports: stdlib → third-party → local, separated by blank lines
- Terminal output must use ASCII-safe characters (Windows cp1252 compatibility)
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
- Run tests before committing
- Update `CHANGELOG.md` and `TODO.md` with every meaningful change
- User must push manually (wincredman credential store issue)

## Maintenance rules

1. **Complete a task** → mark done in `TODO.md`, add entry to `CHANGELOG.md`
2. **Start a new phase** → update `docs/IMPLEMENTATION_PLAN.md` status
3. **Add a module** → update project structure above
4. **Add a dependency** → add to `pyproject.toml` and tech stack above
5. **Change conventions** → update this file immediately
6. **Change scope** → update `PROJECT.md` first, then propagate
7. **Add/change a NodeType** → update `_node_styles()` and `_HTML_NODE_COLORS` in `src/sreg/display.py`
8. **Add a new display need** → add function to `display.py`, update `scripts/demo.py` and notebook
9. **Change the vision or architecture** → update `PROJECT.md`, `docs/CURRENT_STATE.md`, this file, and `MEMORY.md`
