# TODO — Session C: RL Training Integration

> Tasks specific to this worktree. For the general project TODO, see `TODO.md`.

## Phase 1: Environment adapter (TRAIN.3)

> Build `SregEnv(vf.StatefulToolEnv)` that wraps SREG for verifiers.

- [ ] **T1.1**: Package skeleton — `src/sreg/training/` with `__init__.py`, types, adapters
- [ ] **T1.2**: `adapters.py` — translate between verifiers tool args and SREG Action/StepResult models
- [ ] **T1.3**: `validators.py` — submit payload validation by eval_type
- [ ] **T1.4**: `tools.py` — `research_action()` and `submit()` as async tool functions
- [ ] **T1.5**: `rubric.py` — reward dispatch table (9 eval types) + metrics
- [ ] **T1.6**: `env.py` — `SregEnv` class with setup_state, update_tool_args, stop conditions
- [ ] **T1.7**: `prompts.py` — render ResearchProblem as agent prompt
- [ ] **T1.8**: Unit tests for all of the above (no GPU, mock model)
- [ ] **T1.9**: Integration test — create SregEnv with a real SRC, verify rollout mechanics

## Phase 2: Dataset generation (TRAIN.1)

> Generate training data as HuggingFace Dataset.

- [ ] **T2.1**: `dataset.py` — SRC to HF Dataset row conversion
- [ ] **T2.2**: Script to generate N SRCs via orchestrator and export as Dataset
- [ ] **T2.3**: Include teacher trajectories as optional field (for SFT)
- [ ] **T2.4**: Dataset validation — schema checks, no BN leakage, reproducibility from seed

## Phase 3: Dry run (TRAIN.2 prep)

> Validate the environment works end-to-end without training.

- [ ] **T3.1**: `vf-eval` dry run with small model (Qwen3-0.5B), verify rollouts complete
- [ ] **T3.2**: Verify rewards compute correctly for all 9 eval types
- [ ] **T3.3**: Check failure modes: no-submit, double submit, parallel tool calls, invalid action_id, budget boundary, malformed submit, state leakage

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
| python_exec not implemented (TOOL.2) | Blocked | Phase 1 uses research_action + submit only |
| EpisodeRunner API mismatch with tool functions | To verify | Adapter layer handles translation |
| Parallel tool calls in verifiers | To handle | Reject or serialize in env |
| Model doesn't learn SREG tool format | Phase 4 | SFT warm-start with teacher trajectories |

## Dependencies on other sessions

| What we need | From whom | Status |
|-------------|-----------|--------|
| Stable EpisodeRunner API | Session A (main) | Available (Slice B complete) |
| Phase -1 contracts | Session A (main) | Done (commit 43da50c) |
| python_exec sandbox (TOOL.2) | Session A (main) | Not started — we skip for Phase 1 |
| SRC generation via orchestrator | Session A (main) | Available |
