# Session C — RL Training Integration with verifiers

## Who you are

You are **Session C** — your job is to integrate SREG as an RL training environment
using the `verifiers` library by Prime Intellect. You work in the worktree
`rl-env-verifiers`, isolated from the main branch.

Other sessions working in parallel:
- **Session A** (main branch): core generator improvements (interventions, E2E)
- **Session B** (worktree `benchmark-suite`): external benchmark adapters (CLadder, DiscoveryBench, SciGym)

**Your code is isolated. You don't need to coordinate with other sessions.**

## What you do

Build an adapter that wraps SREG as a `verifiers`-compatible environment so that
an RL framework (verifiers RLTrainer or prime-rl) can train a policy model
(Qwen3-8B) to do science by interacting with SREG's synthetic research cases.

### Your scope (files you own)
- `src/sreg/training/` — new module (env, tools, rubric, dataset, adapters)
- `tests/training/` — tests for the new module
- `scripts/` — training scripts, dry-runs, dataset generation

### What you do NOT touch
- **Phase -1 contracts** (stable interfaces, DO NOT modify):
  - `src/sreg/inference/protocol.py`
  - `src/sreg/models/benchmark.py`
  - `src/sreg/models/code_exec.py`
  - `src/sreg/models/env_protocol.py`
  - `src/sreg/models/agent_tools.py`
- **Session A territory**: `src/sreg/world/`, `src/sreg/tools/`, `src/sreg/orchestrator/`
- **Session B territory**: `src/sreg/benchmarks/`

You CAN read anything in the codebase. You only write in your scope.

## Key technical decisions (approved)

These were researched and agreed with the user + Codex:

### Framework choice
- **verifiers** (`pip install verifiers`) — environment library with `MultiTurnEnv`, `ToolEnv`, `Rubric`
- **verifiers-rl** (`pip install verifiers-rl`) — includes `RLTrainer` for 1-2 GPU training
- **prime-rl** — only needed later for scaling to 8+ GPUs
- Repo: `PrimeIntellect-ai/verifiers` (NOT letta-ai)

### Architecture
- Subclass `vf.StatefulToolEnv` (not plain ToolEnv — our tools are stateful)
- `update_tool_args()` injects EpisodeRunner invisibly into tool calls
- Pre-generate SRCs as HuggingFace Dataset (not on-the-fly)
- `submit` is a tool with 3 optional fields (choice, distribution, adjustment_set)
- No-submit termination = failed episode (reward -0.1)
- Reward dispatch table by eval_type to existing VerifierTool scorers
- Adapter layer translates between verifiers format and SREG pydantic models

### Submit tool design
- `choice: str | None` — for hypothesis_selection, NBO, best_intervention, compare_interventions, should_condition
- `distribution: dict[str, float] | None` — for infer_target, causal_effect, infer_latent_cause
- `adjustment_set: list[str] | None` — for adjustment_set
- Exactly one field must be populated per eval_type

### Reward design
- Terminal reward only (sparse) — acceptable for GRPO with short episodes (3-10 turns)
- Main reward: exact score from BN (KL divergence or binary accuracy)
- Penalties: no-submit (-0.1), invalid actions (tracked as metric)
- Zero-weight metrics: turn count, invalid actions, submitted flag

### Hardware target
- Dev: 1x H100, Qwen3-0.5B/1.7B, LoRA rank=32
- Production: 1-2x H100, Qwen3-8B, LoRA rank=32
- Cost estimate: $30-200 USD on Azure spot

## Current state

### Research (COMPLETE)
- verifiers API researched in depth (MultiTurnEnv, ToolEnv, StatefulToolEnv, Rubric)
- prime-rl architecture understood (separate project, training backend)
- Mapping SREG concepts to verifiers concepts documented
- Codex consulted on architecture — produced concrete integration spec
- 10 failure modes identified for testing

### Implementation (NOT STARTED)
- See `TODO_TRAINING.md` for task breakdown

## Key files to understand (read-only references)

| File | What it is |
|------|-----------|
| `src/sreg/env/episode.py` | EpisodeRunner — the core interaction loop we wrap |
| `src/sreg/models/episode.py` | Action, ActionType, StepResult, Episode models |
| `src/sreg/models/world.py` | World, Node, Edge, CPD models |
| `src/sreg/models/task.py` | Task, TaskType (9 eval types), TaskBundle |
| `src/sreg/models/research_problem.py` | ResearchProblem — what the agent sees |
| `src/sreg/models/score.py` | Score, StepScore models |
| `src/sreg/tools/verifier.py` | VerifierTool — scoring methods (KL, accuracy, etc.) |
| `src/sreg/models/env_protocol.py` | SREGEnvironment Protocol (the contract we implement) |
| `src/sreg/models/agent_tools.py` | AgentTool definitions (research_action, python_exec, submit) |

## Workflow reminder

1. Code + tests + validation
2. Codex review (use Codex frequently — research, planning, reviews)
3. Present to user in Spanish, ask for approval
4. Update docs + commit (only after user says yes)
5. Suggest next steps
