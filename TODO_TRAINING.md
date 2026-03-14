# TODO — Session C: RL Training Integration

> Tasks specific to this worktree. For the general project TODO, see `TODO.md`.

## Phase 1: Environment adapter (TRAIN.3)

> Build `SregEnv(vf.StatefulToolEnv)` that wraps SREG for verifiers.

- [x] **T1.1**: Package skeleton — `src/sreg/training/` with `__init__.py`, types, adapters
- [x] **T1.2**: `adapters.py` — translate between verifiers tool args and SREG Action/StepResult models
- [x] **T1.3**: `validators.py` — submit payload validation by eval_type
- [x] **T1.4**: `tools.py` — `research_action()` and `submit()` as async tool functions
- [x] **T1.5**: `rubric.py` — reward dispatch table (9 eval types) + metrics
- [x] **T1.6**: `env.py` — `SregEnv` class with setup_state, update_tool_args, stop conditions
- [x] **T1.7**: `prompts.py` — render ResearchProblem as agent prompt
- [x] **T1.8**: Unit tests for all of the above (168 tests, no GPU)
- [x] **T1.9**: Integration test — full rollout simulation (dataset → setup → observe → submit → score)
- [x] **T1.10**: `python_exec` tool — persistent Python interpreter (exec + namespace, sandbox, 32 tests)

## Phase 2: Dataset generation (TRAIN.1)

> Generate training data as HuggingFace Dataset.

- [x] **T2.1**: `dataset.py` — SRC to HF Dataset row conversion (programmatic, no LLM needed)
- [x] **T2.2**: `dry_run.py` script generates N SRCs and runs rollouts with real model
- [ ] **T2.3**: Include teacher trajectories as optional field (for SFT)
- [ ] **T2.4**: Dataset validation — schema checks, no BN leakage, reproducibility from seed

## Phase 3: Dry run (TRAIN.2 prep)

> Validate the environment works end-to-end with a real model.

- [x] **T3.1**: Dry run with Qwen2.5-0.5B-Instruct on local GPU (RTX 4000 Ada, 12GB)
- [ ] **T3.2**: Verify rewards compute correctly for all 9 eval types with real model
- [ ] **T3.3**: Check failure modes: no-submit, double submit, parallel tool calls, invalid action_id, budget boundary, malformed submit, state leakage
- [ ] **T3.4**: Dry run with vLLM on Linux (H100) — validate vllm backend

## Phase 4: First RL training (TRAIN.4)

> Actual training run on GPU.

- [ ] **T4.1**: Training config (TOML for prime-rl or RLTrainer config)
- [ ] **T4.2**: SFT warm-start with teacher trajectories (base success rate >= 20%)
- [ ] **T4.3**: First GRPO run on H100 (Qwen3-8B, LoRA rank=32)
- [ ] **T4.4**: Analyze training curves, reward distribution, failure modes

## Phase 5: Curriculum (TRAIN.5) — FUTURE

- [ ] **T5.1**: Difficulty-based curriculum (fewer nodes/budget first, then harder)
- [ ] **T5.2**: Eval-type curriculum (single-type first, then mixed)

## Known risks / blockers

| Risk | Status | Mitigation |
|------|--------|------------|
| verifiers API unstable (v0.1.x) | Active | Pin version, integration tests |
| python_exec sandbox is soft (not Docker) | Accepted | Soft sandbox sufficient for non-adversarial training. Docker = future hardening |
| EpisodeRunner API mismatch with tool functions | Resolved | Adapter layer handles translation |
| Parallel tool calls in verifiers | To handle | Reject or serialize in env |
| Model doesn't learn SREG tool format | Phase 4 | SFT warm-start with teacher trajectories |
| vLLM on WSL2 (WDDM GPU) | Known issue | Use native Linux for vLLM. Transformers fallback on Windows. |
| Qwen 0.5B submit rate low | Expected | Too small for reliable tool calling. SFT + larger model (8B) needed. |

## Dependencies on other sessions

| What we need | From whom | Status |
|-------------|-----------|--------|
| Stable EpisodeRunner API | Session A (main) | Available (Slice B complete) |
| Phase -1 contracts | Session A (main) | Done (commit 43da50c) |
| python_exec sandbox (TOOL.2) | Session C | Done — soft sandbox (exec + namespace) |
| SRC generation via orchestrator | Session A (main) | Available |
| Linux GPU (H100) for vLLM/training | Infrastructure | Needed for Phase 3.4 + Phase 4 |
