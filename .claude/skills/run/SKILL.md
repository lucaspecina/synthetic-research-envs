---
name: run
description: Run the LLM orchestrator to generate a research case. Use to create and inspect cases, analyze quality, and export results.
---

Run SREG to generate a full Synthetic Research Case (SRC).

## What it does

Executes `scripts/generate_src.py` which:
1. Sends a goal to the LLM orchestrator
2. LLM designs SCM (causal structure + equations), applies semantics, designs sub-questions, builds problem
3. Exports the SRC as JSON
4. With `--inspect`: exports briefing, CSV, answer key, DAG visualization
5. With `--oi`: runs the OI solver (free investigation + claim cards + compilation + verification)

## Azure LLM

**Azure esta SIEMPRE disponible.** Credenciales en `.env` (raiz del repo),
cargadas automaticamente por `python-dotenv`. No verificar env vars manualmente.
Solo ejecutar el script.

## How to run

Parse $ARGUMENTS for optional parameters:
- A topic/domain/goal description (free text)
- `--seed N` for reproducibility
- `--inspect` for full analysis package
- `--oi` to run Open Investigation solver

Build and execute the command:

```bash
# With a specific goal + inspection
python scripts/generate_src.py --goal "research problem about [topic], 8 nodes" -o experiments/case_NAME/ --inspect

# Full package with OI solver
python scripts/generate_src.py --goal "..." -o experiments/case_NAME/ --oi --seed 42

# From a paper seed
python scripts/generate_src.py --seed-file seeds/paper.pdf -o experiments/case_NAME/ --inspect
```

**Goal priority**: `--goal` > `--seed-file` > default

If $ARGUMENTS is just a topic (e.g., `/run epidemiology`), build a goal like:
```
"Generate a research problem about [topic] in a fictional setting.
Use dag_construct with 8 nodes. Design a research case."
```

Always use `-o experiments/case_TOPIC/` with a descriptive name.
Add `--inspect` by default. Add `--oi` if user wants solver evaluation.

## Output files

| File | When | Content |
|------|------|---------|
| `src.json` | Always | Full SRC (world, problem, metadata) |
| `briefing.md` | --inspect | What the solver sees (brief + data description) |
| `dataset.csv` | --inspect | Full dataset |
| `answer_key.md` | --inspect | SCM structure + equations + correct answers |
| `dag.png` | --inspect | Causal DAG visualization |
| OI results | --oi | Solver claims, compilation, verification, scores |

## After running

1. **Read the output** — especially briefing and answer_key
2. **Check the DAG** — does the causal structure make sense?
3. **If OI**: read solver claims, check compilation quality (the bottleneck)
4. **Report findings** to the user in Spanish
5. Apply LA PREGUNTA: does it feel like real research? Would RL training on this teach scientific judgment?
