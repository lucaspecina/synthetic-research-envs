# SREG — TODO

> Task tracking for the project. Update status as work progresses.
> Statuses: `[ ]` pending | `[~]` in progress | `[x]` done | `[-]` cancelled

## Phase 1 — Contracts and data structures
- [x] Define `World`, `Node`, `Edge` models
- [x] Define `CPD` (conditional probability distribution) model
- [x] Define `Episode`, `Action`, `StepResult` models
- [x] Define `Task`, `TaskSpec` models
- [x] Define `TeacherOutput` model (posterior, recommended action, info gain)
- [x] Define `Score` model (functional, structural, per-step)
- [x] Define JSON schemas for all tool inputs/outputs
- [x] Set up `pyproject.toml` with dependencies
- [x] Set up `pytest` skeleton

## Phase 2 — World generation + validation
- [ ] Implement latent preference template
- [ ] Implement `WorldGenTool` for one template
- [ ] Implement `WorldCheckTool` (difficulty validation)
- [ ] Validate: 100 worlds, all valid DAGs, difficulty varies with params

## Phase 3 — Teacher solver
- [ ] Implement exact Bayesian inference (pgmpy VariableElimination)
- [ ] Implement information gain calculation
- [ ] Implement optimal action sequence generation
- [ ] Validate: teacher reaches >90% on infer_target after full episode

## Phase 4 — Episodes, tasks, verifier
- [ ] Implement `EpisodeGenTool`
- [ ] Implement `TaskGenTool` (infer_target)
- [ ] Implement `VerifierTool` (functional scoring)
- [ ] End-to-end test: teacher as agent through full episode

## Phase 5 — LLM Orchestrator
- [ ] Define orchestrator system prompt
- [ ] Wire 5 tools to LLM via Azure Foundry (openai SDK)
- [ ] Implement orchestrator loop (propose → check → refine → accept)
- [ ] Validate: converges in <=3 iterations per world

## Phase 6 — More templates + more tasks
- [ ] Implement causal chain template
- [ ] Implement fork/collider template
- [ ] Implement `next_best_observation` task type
- [ ] Validate: same world produces both task types

## Phase 7 — Dataset generation + baseline eval
- [ ] Generate teacher trajectories and export as dataset
- [ ] Implement baseline LLM agent evaluation harness
- [ ] Run baseline LLM through episodes and collect metrics
- [ ] Document results

## Backlog (not v0)
- [ ] Hypothesis selection task type
- [ ] Synthetic document artifacts
- [ ] Intervention tasks (do-calculus)
- [ ] Structure recovery tasks
- [ ] Approximate inference teacher (larger worlds)
- [ ] Curriculum over world complexity
