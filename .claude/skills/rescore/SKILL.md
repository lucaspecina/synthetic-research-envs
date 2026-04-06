---
name: rescore
description: Re-evaluate frozen E2E cases without regenerating worlds or re-running the solver. Isolates effect of code changes from LLM variance.
---

Controlled rescore: re-run parts of the scoring pipeline on existing results.

## What it does

Takes a frozen case (src.json + oi_result.json from a previous `/run --oi`)
and re-evaluates it, isolating the effect of code changes from worldgen/solver
variance. Three modes let you re-run different parts of the pipeline.

## Requirements

Cases must have been generated AFTER P0 persistence was implemented (2026-04-06).
Specifically:
- `src.json` must contain `sub_questions_v2` (grounded SQs with verdicts)
- `oi_result.json` must contain `score_inputs_v2` (claims, compiled specs,
  truths, relevance, trace, runner_config)

Legacy cases without these fields will fail with an error message.

## Azure LLM

**Azure esta SIEMPRE disponible.** `--rejudge` y `--recompile` requieren LLM.
`--reaggregate` es 100% local (no LLM). Credenciales en `.env`, cargadas
automaticamente.

## How to run

Parse $ARGUMENTS for optional parameters:
- One or more experiment directories
- `--reaggregate` — only re-compute score arithmetic (fastest, no LLM)
- `--rejudge` — re-run LLM relevance judge with frozen specs/truths
- `--recompile` — re-compile + re-verify + re-judge (default, full pipeline)

```bash
# Re-aggregate a single case (no LLM, instant)
python scripts/rescore.py results/case_dir/ --reaggregate

# Re-judge relevance on multiple cases
python scripts/rescore.py results/batch_dir/*/ --rejudge

# Full recompile (default mode)
python scripts/rescore.py results/case_dir/
```

## Modes explained

| Mode | What's frozen | What's re-run | LLM? | Use when... |
|------|--------------|---------------|------|-------------|
| `--reaggregate` | specs, truths, relevance | only score formula | No | Changed scoring arithmetic |
| `--rejudge` | specs, truths | relevance judge + score | Yes | Changed relevance judge |
| `--recompile` | claims, SQs, world | compiler + verifier + judge + score | Yes | Changed compiler or verifier |

## Output

Shows side-by-side comparison:
```
  Original: 0.5634 (corr=0.833 cov=0.676)
  Rescore:  0.5634 (corr=0.833 cov=0.676)
  Delta:    0.0000
```
Plus per-SQ breakdown and summary table for multiple cases.

## Expected behavior

- `--reaggregate` should reproduce the original score EXACTLY (delta 0.0000)
- `--rejudge` will have small drift from LLM non-determinism (~0.02-0.05)
- `--recompile` will have moderate drift from compiler + judge (~0.03-0.08)
- Correctness stays stable across modes (same world + claims)

## After running

1. If `--reaggregate` doesn't reproduce exactly, something is broken in persistence
2. Compare deltas across cases to find systematic effects vs noise
3. Report findings to the user in Spanish
