# SREG -- Synthetic Research Environment Generator

A system that generates fictional but causally coherent worlds, produces evidence from those worlds, formulates verifiable research tasks, and evaluates LLM agents that interact with them.

## What is this?

SREG is an **environment factory**, not a solver. It creates synthetic probabilistic worlds where:
- Ground truth is mathematically defined (DAG + probability distributions)
- Scoring is automatic -- no human or LLM judge needed
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

## Generate and inspect research cases

The main workflow is: the LLM orchestrator generates a complete research case (causal structure + narrative + questions + data) that you can inspect and analyze.

```bash
# Edit research_seed.md with your research context, then run:
python scripts/test_orchestrator.py --export output/case.json

# Or provide a goal directly (ignores seed file):
python scripts/test_orchestrator.py \
    --goal "research problem about tropical disease outbreak, 8 nodes" \
    --seed 42 \
    --export output/case_disease.json

# Use a different seed file:
python scripts/test_orchestrator.py --seed-file my_case.md

# Default case (marine ecology, when no seed file exists):
python scripts/test_orchestrator.py

# With verbose LLM logs
python scripts/test_orchestrator.py --goal "..." --verbose
```

**Goal priority**: `--goal` flag > `research_seed.md` (if file exists) > built-in default

### What the output shows

1. **Process**: each LLM iteration, which tools it calls, with what arguments
2. **World**: the causal structure (nodes, edges, types, states)
3. **Case plan**: research questions with eval types and rationale
4. **Tasks**: generated tasks with mathematically correct answers
5. **Research problem**: what an agent would see (narrative, data, actions)

### Exported JSON structure

```
{
  "metadata":         { timestamp, goal, model }
  "process":          { tools_called: [{ tool, args, result }] }
  "world":            { nodes, edges, scenario, domain, ... }
  "case_plan":        { title, questions: [{ eval_type, target, rationale }] }
  "tasks":            [{ type, question, correct_answer, scoring_method }]
  "research_problem": { narrative, data_assets, actions, budget, ... }
}
```

## Other scripts

```bash
# Terminal demo: world generation + teacher solving (no LLM needed)
python scripts/demo.py --seed 42 --nodes 8 --strength 0.7 --budget 5

# Agent vs teacher comparison (requires LLM)
python scripts/test_agent.py --seed 42 --nodes 8 --budget 5

# End-to-end: orchestrator -> agent -> score (requires LLM)
python scripts/test_e2e.py

# Batch evaluation across configurations
python scripts/batch_eval.py --problems 10 --nodes 8

# Batch sweep across parameter space
python scripts/batch_sweep.py
```

## Evaluation types (9 total)

| Type | What it asks | Scoring |
|------|-------------|---------|
| `infer_target` | Estimate P(target \| evidence) | KL divergence |
| `next_best_observation` | Which variable to measure next? | IG ratio |
| `hypothesis_selection` | Which hypothesis fits the data? | Binary match |
| `causal_effect` | What is P(Y \| do(X=x))? | KL divergence |
| `best_intervention` | Which intervention maximizes effect? | Binary match |
| `adjustment_set` | What variables to control for? | Set F1 |
| `compare_interventions` | Which of two interventions is better? | Binary match |
| `should_condition` | Should you control for variable Z? | Binary yes/no |
| `infer_latent_cause` | What is P(hidden_cause \| symptoms)? | KL divergence |

## Project structure

See `CLAUDE.md` for the full project structure and conventions.

## Documentation

- `PROJECT.md` -- Vision, architecture, design principles
- `CURRENT_STATE.md` -- What the system does today, in detail
- `TODO.md` -- Current task tracking
- `CHANGELOG.md` -- Version history
- `WORLD_DESIGN.md` -- Research document for realistic world generation

## LLM Integration

SREG consumes LLMs via Azure AI Foundry using the standard `openai` SDK. Configure credentials in `.env`:

```
AZURE_FOUNDRY_BASE_URL=https://your-resource.openai.azure.com/openai/v1
AZURE_INFERENCE_CREDENTIAL=your-api-key
AZURE_MODEL=gpt-4o
```

See `CLAUDE.md` for details.
