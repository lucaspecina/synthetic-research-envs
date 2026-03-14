---
name: run
description: Run the LLM orchestrator to generate a research case. Use to create and inspect cases, analyze quality, and export results.
---

Run SREG to generate a full Synthetic Research Case (SRC).

## What it does

Executes `scripts/generate_src.py` which:
1. Sends a goal to the LLM orchestrator
2. LLM designs causal structure (DAG), applies semantics, designs research questions, builds problem
3. Exports the SRC as JSON
4. With `--inspect`: exports briefing, CSV, answer key (quick guide + BN + CPDs + correct answers), DAG visualization
5. With `--solve`: runs the agent on each task, exports evaluation + trajectory

## How to run

Parse $ARGUMENTS for optional parameters:
- A topic/domain/goal description (free text)
- `--seed N` for reproducibility
- `--inspect` for full analysis package
- `--solve` to run agent (implies --inspect)

Build and execute the command:

```bash
# From research_seed.md (reads automatically if file exists)
python scripts/generate_src.py -o experiments/case_NAME/

# With a specific goal
python scripts/generate_src.py --goal "research problem about [topic], 8 nodes, budget 5" -o experiments/case_NAME/

# Full package with inspection
python scripts/generate_src.py --goal "..." -o experiments/case_NAME/ --inspect

# Full package + agent evaluation
python scripts/generate_src.py --goal "..." -o experiments/case_NAME/ --solve --seed 42
```

**Goal priority**: `--goal` > `research_seed.md` (if exists) > default (marine ecology)

If $ARGUMENTS is just a topic (e.g., `/run epidemiology`), build a goal like:
```
"Generate a research problem about [topic] in a fictional setting.
Use dag_construct with 8 nodes. Design a research case with at least
3 different evaluation types. Medium difficulty, budget 5."
```

Always use `-o experiments/case_TOPIC/` with a descriptive name.
Add `--inspect` by default. Add `--solve` if user wants agent evaluation.

## Output files

| File | When | Content |
|------|------|---------|
| `src.json` | Always | Full SRC (world, problem, tasks, metadata) |
| `briefing.md` | --inspect | What the agent sees (narrative + questions) |
| `dataset.csv` | --inspect | Full dataset |
| `answer_key.md` | --inspect | Quick guide + BN + CPDs + correct answers |
| `dag.png` | --inspect | Causal DAG visualization |
| `evaluation.md` | --solve | Agent vs correct answers, scores, verdicts |
| `trajectory.md` | --solve | Agent reasoning step by step |

## After running

1. **Read the output** — especially the answer_key quick guide
2. **Check the DAG** — does the causal structure make sense?
3. **Analyze tasks** — do correct answers align with the questions?
4. **Report findings** to the user in Spanish
5. If `--solve`: analyze where the agent succeeded/failed and why
