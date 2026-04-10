# SREG -- Synthetic Research Environment Generator

Generates synthetic research environments with **exact reward signals** for training
policy models that do science via RL. Like OpenAI Gym for games -- SREG for scientific
reasoning.

## What is this?

SREG is an **environment factory**. It creates synthetic research cases where:
- Ground truth is mathematically defined (SCM with structural equations)
- Scoring is automatic -- no human or LLM judge needed
- Every case feels like a real scientific investigation
- Agents are evaluated on reasoning quality, not fact recall

SREG **generates environments + computes rewards**. It does NOT train policies.
Others bring their policy + RL framework and train against SREG's environments.

## Quick start

```bash
conda create -n sreg python=3.11 -y && conda activate sreg
pip install -e ".[dev]"
```

Configure LLM credentials in `.env`:
```
AZURE_FOUNDRY_BASE_URL=https://your-resource.openai.azure.com/openai/v1
AZURE_INFERENCE_CREDENTIAL=your-api-key
AZURE_MODEL=gpt-5.4                    # Orchestrator (case design)
AZURE_SOLVER_MODEL=gpt-5.2-codex       # Solver (optional, defaults to AZURE_MODEL)
```

## Generate a synthetic research case

```bash
# From a research topic
python scripts/generate_src.py --goal "ecology of coral reefs, 10 nodes" \
  --inspect -o output/reef/

# From a research seed (markdown)
python scripts/generate_src.py --seed-file research_seed.md \
  --inspect -o output/case/

# From a scientific paper (PDF)
python scripts/generate_src.py --seed-file seeds/paper.pdf \
  --inspect -o output/from_paper/

# Full pipeline with Open Investigation solver
python scripts/generate_src.py --goal "marine ecology" \
  --oi --inspect -o output/case_oi/
```

### What `--inspect` produces

```
output/
  src.json                  # Full SRC (world, problem, tasks, metadata)
  briefing.md               # What the agent sees (narrative + questions)
  dataset.csv               # Sampled data from the SCM
  answer_key.md             # Ground truth: DAG + equations + correct answers
  dag.png                   # Causal DAG visualization
```

### What `--oi` adds (Open Investigation)

```
  oi_result.json            # Solver claims, compilation, verification, scores
  full_case_oi.md           # Complete OI report with investigation trace
```

The solver investigates freely and submits claim cards. A compiler translates
claims to executable specs. The SCM verifier scores them -- deterministic, no LLM.

## Use different solver backends

The orchestrator always uses Azure (needs a strong model to design cases).
The solver can use any OpenAI-compatible backend:

```bash
# Azure (default)
python scripts/generate_src.py --oi -o output/

# vLLM (local GPU)
bash scripts/serve_model.sh  # starts Qwen on localhost:8000
python scripts/generate_src.py --oi -o output/ \
  --solver-base-url http://localhost:8000/v1 \
  --solver-api-key none \
  --solver-model Qwen/Qwen2.5-7B-Instruct
```

## Run external benchmarks

```bash
# Text-only (baseline)
python scripts/run_benchmark.py -b cladder --subset dev

# With solver tools (python_exec for data analysis)
python scripts/run_benchmark.py -b qrdata --subset dev --with-tools
```

## Paper-seeded SRCs

Drop a PDF (or any research description) and SREG creates a synthetic case
**inspired** by it. Not a replica -- a new world that feels like the same type
of investigation. The system extracts inspiration dimensions (domain, scale,
causal structure, questions, signal/noise) and builds a matching SCM.

## Scripts

| Script | Purpose |
|--------|---------|
| `generate_src.py` | Generate SRCs (--inspect, --oi) |
| `oi_demo_case.py` | OI demo with curated worlds |
| `oi_pilot_batch.py` | Batch OI evaluation |
| `oi_nodata_baseline.py` | No-data baseline probe |
| `run_benchmark.py` | External benchmarks (CLadder, QRData, DiscoveryBench) |
| `serve_model.sh` | Start vLLM server for local models |

## Documentation

| Document | What it contains |
|----------|-----------------|
| `PROJECT.md` | Vision, principles, what SREG should achieve |
| `ARCHITECTURE.md` | System design, contracts, flows |
| `CURRENT_STATE.md` | What exists today, limitations |
| `TODO.md` | Pending work, open problems |
| `CHANGELOG.md` | Version history |
| `research/` | Analysis, findings, synthesis (see research/README.md) |

## Architecture

```
src/sreg/
  models/          # Pydantic data contracts (SCM, OI, tasks, episodes)
  inference/       # LLM protocol (ModelClient, Responses API)
  world/           # SCM engine (scm.py, expression compiler, scm_data)
  solver/          # SCMSolver (teacher / ground truth via Monte Carlo)
  tools/           # SCM pipeline + OI pipeline (compiler, verifier, salience)
  orchestrator/    # LLM orchestrator (function calling, SCM-only)
  agent/           # python_exec + tool-calling engine (for OI solver)
  benchmarks/      # External benchmark adapters (CLadder, QRData, DiscoveryBench)

scripts/           # Entry points (generate_src, run_benchmark, OI scripts)
experiments/       # Generated SRCs and results
```

## Tests

```bash
pytest tests/tools/test_scm_task_gen.py -v   # Specific module
ruff check src/ tests/                        # Lint
```
