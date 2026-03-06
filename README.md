# SREG — Synthetic Research Environment Generator

A system that generates fictional but causally coherent worlds, produces evidence from those worlds, formulates verifiable research tasks, and evaluates LLM agents that interact with them.

## What is this?

SREG is an **environment factory**, not a solver. It creates synthetic probabilistic worlds where:
- Ground truth is mathematically defined (DAG + probability distributions)
- Scoring is automatic — no human or LLM judge needed
- The same world can produce many different tasks
- Agents are evaluated on reasoning quality, not fact recall

The worlds are fictional by design. If a model trained on SREG environments transfers to real scientific tasks, that proves it learned reasoning, not content.

## Quick start

```bash
# Create and activate conda environment
conda create -n sreg python=3.11 -y
conda activate sreg

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check src/ tests/
```

## Project structure

See `CLAUDE.md` for the full project structure and conventions.

## Documentation

- `PROJECT.md` — What the project is, how it works, version roadmap
- `docs/IMPLEMENTATION_PLAN.md` — Detailed phase-by-phase build plan
- `TODO.md` — Current task tracking
- `CHANGELOG.md` — Version history

## LLM Integration

SREG consumes LLMs via Azure AI Foundry using the standard `openai` SDK. See `CLAUDE.md` for configuration details.
