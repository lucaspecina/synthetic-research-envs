# SREG -- Synthetic Research Environment Generator

Generates synthetic research environments with **exact reward signals** for training
policy models that do science via RL. Like OpenAI Gym for games or PRIME Intellect
for math -- SREG for scientific reasoning.

## What is this?

SREG is an **environment factory**. It creates synthetic research cases where:
- Ground truth is mathematically defined (Bayesian network + exact inference)
- Scoring is automatic -- no human or LLM judge needed
- Every case feels like a real scientific investigation
- Agents are evaluated on reasoning quality, not fact recall

SREG **generates environments + computes rewards**. It does NOT train policies.
Others bring their policy + RL framework and train against SREG's environments.

## Quick start

```bash
conda create -n sreg python=3.11 -y && conda activate sreg
pip install -e ".[dev]"
pytest tests/ -v  # 1101 tests
```

Configure LLM credentials in `.env`:
```
AZURE_FOUNDRY_BASE_URL=https://your-resource.openai.azure.com/openai/v1
AZURE_INFERENCE_CREDENTIAL=your-api-key
AZURE_MODEL=gpt-4o
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

# With Inspiration Report (seed vs SRC comparison)
python scripts/generate_src.py --seed-file research_seed.md \
  --inspect --report -o output/case/

# Solve with the diagnostic agent
python scripts/generate_src.py --seed-file research_seed.md \
  --solve -o output/case/
```

### What `--inspect` produces

```
output/
  src.json                  # Full SRC (world, problem, tasks, metadata)
  briefing.md               # What the agent sees (narrative + questions)
  dataset.csv               # Sampled data from the Bayesian network
  answer_key.md             # Ground truth: DAG + CPDs + correct answers
  dag.png                   # Causal DAG visualization
```

### What `--report` adds

```
  inspiration_report.md     # How the seed inspired the SRC (narrative + scores)
  inspiration_manifest.json # What the orchestrator intended to preserve/simplify
```

The Inspiration Report tells the story of how the seed was translated into a
synthetic case: which variables were preserved, what was simplified, whether the
research questions are of the same type. It's for reviewing the quality of
inspiration, not a reward signal.

### What `--solve` adds

```
  evaluation.md             # Agent scores per question
  trajectory.md             # Full agent conversation (code, reasoning, actions)
  full_case.md              # Complete report (system prompt + conversation + eval)
```

## Use different solver backends

The orchestrator always uses Azure (needs a strong model to design cases).
The solver (diagnostic agent) can use any backend:

```bash
# Azure (default)
python scripts/generate_src.py --solve -o output/

# vLLM (local GPU)
bash scripts/serve_model.sh  # starts Qwen on localhost:8000
python scripts/generate_src.py --solve -o output/ \
  --solver-base-url http://localhost:8000/v1 \
  --solver-api-key none \
  --solver-model Qwen/Qwen2.5-7B-Instruct

# Any OpenAI-compatible API
python scripts/generate_src.py --solve -o output/ \
  --solver-base-url https://api.example.com/v1 \
  --solver-api-key sk-... \
  --solver-model model-name
```

## Run external benchmarks

Evaluate models on CLadder, QRData, or DiscoveryBench -- with or without
solver tools (python_exec + think):

```bash
# Text-only (baseline)
python scripts/run_benchmark.py -b cladder --subset dev

# With solver tools (python_exec for data analysis)
python scripts/run_benchmark.py -b qrdata --subset dev --with-tools

# With vLLM backend
python scripts/run_benchmark.py -b cladder \
  --base-url http://localhost:8000/v1 --api-key none
```

BEFORE scores (GPT-5.2, text-only): CLadder 78%, QRData 38%, DiscoveryBench 0.299 HMS.

## Generate training datasets

```python
from sreg.training.dataset import generate_dataset

# 50 SRCs, ~450 rows (9 eval types each), no LLM needed
ds = generate_dataset(n=50, seed=0)
```

## Train with verifiers (RL)

```python
from sreg.training.env import SregEnv

env = SregEnv(dataset=ds, max_turns=10)
# Use with verifiers/prime-rl for RL training
```

## Paper-seeded SRCs

The most powerful mode: drop a PDF (or any research description) and SREG
creates a synthetic case **inspired** by it. Not a replica -- a new world
that feels like the same type of investigation.

The system extracts 8 **inspiration dimensions** from the seed:
1. Domain and problem
2. Scale and complexity (match the seed's variable count)
3. Causal structure (confounders, mediators, colliders, latent variables)
4. Data types and their problems
5. Type of work (what researchers DO)
6. Type of research questions (maps to eval types)
7. Signal vs noise
8. Available research actions

See `WORLD_DESIGN.md` for the full research on inspiration dimensions.

## Evaluation types (9)

| Type | Question | Scoring |
|------|----------|---------|
| `infer_target` | What is P(target \| evidence)? | KL divergence |
| `next_best_observation` | What to measure next? | IG ratio |
| `hypothesis_selection` | Which hypothesis fits? | Binary match |
| `causal_effect` | What is P(Y \| do(X=x))? | KL divergence |
| `best_intervention` | Which intervention maximizes Y? | Binary match |
| `adjustment_set` | What variables to control for? | Set F1 |
| `compare_interventions` | Is do(X) better than do(Z)? | Binary match |
| `should_condition` | Should you control for Z? | Binary yes/no |
| `infer_latent_cause` | What hidden cause explains this? | KL divergence |

## Scripts

| Script | Purpose |
|--------|---------|
| `generate_src.py` | Generate SRCs (--inspect, --solve, --report) |
| `run_benchmark.py` | External benchmarks (CLadder, QRData, DiscoveryBench) |
| `run_diagnostic.py` | Diagnostic: N SRCs + per-type metrics |
| `serve_model.sh` | Start vLLM server for local models |
| `demo.py` | Terminal demo: world gen + teacher (no LLM) |
| `batch_sweep.py` | Parameter sweep with QualitySuite v2 |

## Documentation

| Document | What it contains |
|----------|-----------------|
| `PROJECT.md` | Vision, architecture, design principles |
| `WORLD_DESIGN.md` | Research: inspiration dimensions, causal theory, eval catalog |
| `CURRENT_STATE.md` | What the system does today, APIs, test coverage |
| `TODO.md` | Task tracking, priorities |
| `CHANGELOG.md` | Version history |
| `CLAUDE.md` | Project config, conventions, commit workflow |

## Architecture

```
src/sreg/
  models/          # Pydantic data contracts
  inference/       # LLM protocol (ModelClient, OpenAIClient, ToolEnrichedClient)
  world/           # World model, templates, cpd_gen
  solver/          # Teacher solver (exact Bayesian inference)
  tools/           # WorldGen, WorldCheck, EpisodeGen, TaskGen, Verifier
  env/             # EpisodeRunner (step-by-step environment)
  orchestrator/    # LLM orchestrator (system prompt, tool definitions)
  agent/           # Solver (python_exec, engine, transformers_backend)
  benchmarks/      # External benchmark adapters
  training/        # RL training adapter (SregEnv/verifiers)
  harness/         # DiagnosticRunner, trajectories, Inspiration Report

seeds/             # Paper seeds (PDF, markdown)
experiments/       # Generated SRCs and results
```

## Tests

```bash
pytest tests/ -v                          # All 1101 tests
pytest tests/tools/test_task_gen.py -v    # Specific module
ruff check src/ tests/                    # Lint
```
