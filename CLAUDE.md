# SREG — Claude Code Project Configuration

## Project overview

SREG (Synthetic Research Environment Generator) generates fictional but causally coherent worlds
for evaluating LLM scientific reasoning. See `PROJECT.md` for the full description.

## Key documents — what each one is and when to update it

| Document | Purpose | Update when... |
|---|---|---|
| `CLAUDE.md` | Claude Code config, conventions, commands | Conventions or workflow change |
| `PROJECT.md` | Human-friendly project description | Scope or vision changes |
| `TODO.md` | Current tasks and their status | Starting, completing, or adding tasks |
| `CHANGELOG.md` | History of what changed per version | Any meaningful change is committed |
| `docs/IMPLEMENTATION_PLAN.md` | Detailed phase-by-phase build plan | A phase is completed or plan is revised |
| `docs/references/` | Original design docs (Claude + GPT) | Read-only archive, don't modify |

## Environment setup

```bash
# Activate the conda environment (always do this first)
conda activate sreg
```

The project uses a **conda** environment named `sreg`. All dependencies are installed inside it.
If recreating from scratch: `conda create -n sreg python=3.11 -y && conda activate sreg && pip install -e ".[dev]"`

## Tech stack

- **Python 3.11+** (via conda env `sreg`)
- **pgmpy** — Bayesian network construction and exact inference
- **networkx** — DAG validation and manipulation
- **numpy / scipy** — sampling, distribution operations
- **pydantic** — data contracts and validation
- **openai SDK** — LLM calls via Azure AI Foundry (see below)
- **pytest** — testing framework
- **ruff** — linting and formatting

## LLM consumption — Azure AI Foundry

We consume LLMs through Azure AI Foundry using the standard `openai` SDK with v1 API.
**Do NOT use `AzureOpenAI`** — use `OpenAI`/`AsyncOpenAI` with `base_url`.

```python
from openai import OpenAI
import os

client = OpenAI(
    base_url="https://<resource>.openai.azure.com/openai/v1/",
    api_key=os.environ["AZURE_INFERENCE_CREDENTIAL"],
)
```

Environment variables required:
- `AZURE_INFERENCE_CREDENTIAL` — API key for the Foundry resource
- `AZURE_FOUNDRY_BASE_URL` — base URL (e.g. `https://<resource>.openai.azure.com/openai/v1/`)

## Project structure

```
sreg/
├── CLAUDE.md                         # This file
├── PROJECT.md                        # Project description
├── TODO.md                           # Task tracking
├── CHANGELOG.md                      # Version history
├── pyproject.toml                    # Package config
├── .claude/commands/                 # Custom slash commands
│   ├── plan.md                       # /plan — review implementation plan
│   ├── status.md                     # /status — project status
│   ├── test.md                       # /test — run tests
│   ├── review.md                     # /review — code review
│   └── phase.md                      # /phase — start a specific phase
├── docs/
│   ├── IMPLEMENTATION_PLAN.md        # Detailed build phases
│   └── references/                   # Original design documents (read-only)
├── src/sreg/                         # Main package
│   ├── models/                       # Pydantic data contracts
│   ├── tools/                        # WorldGen, WorldCheck, EpisodeGen, TaskGen, Verifier
│   ├── world/                        # World model + templates
│   ├── solver/                       # Teacher (exact Bayesian)
│   ├── env/                          # Environment interface
│   ├── scoring/                      # Functional + structural scoring
│   ├── orchestrator/                 # LLM orchestrator loop
│   └── harness/                      # Dataset generation + agent evaluation
├── tests/                            # pytest tests
├── configs/                          # YAML configs
└── notebooks/                        # Exploration notebooks
```

## Code conventions

- Use **pydantic v2** for all data models (BaseModel, not dataclass)
- Type hints on all public functions
- Module-level `__all__` exports in every `__init__.py`
- Tests mirror `src/` structure: `src/sreg/tools/world_gen.py` → `tests/tools/test_world_gen.py`
- Use `ruff` for formatting (line length 100)
- Imports: stdlib → third-party → local, separated by blank lines

## Common commands

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/tools/test_world_gen.py -v

# Lint and format
ruff check src/ tests/
ruff format src/ tests/

# Type check (if added)
mypy src/sreg/
```

## Git conventions

- Branch naming: `feature/<name>`, `fix/<name>`, `refactor/<name>`
- Commit messages: imperative mood, concise ("add world generation templates", not "added...")
- Always run tests before committing
- Update `CHANGELOG.md` with every meaningful commit
- Update `TODO.md` when task status changes

## Maintenance rules — IMPORTANT

These rules define how to keep project docs in sync. Follow them always:

1. **When you complete a task**: mark it done in `TODO.md`, add entry to `CHANGELOG.md`
2. **When you start a new phase**: update `docs/IMPLEMENTATION_PLAN.md` status
3. **When you add a new module**: update the project structure section above
4. **When you add a dependency**: add it to `pyproject.toml` and mention it in tech stack above
5. **When conventions change**: update this file immediately
6. **When scope changes**: update `PROJECT.md` first, then propagate to plan and TODO
