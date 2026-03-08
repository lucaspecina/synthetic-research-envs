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
- [x] Implement latent preference template
- [x] Implement `WorldGenTool` for one template
- [x] Implement `WorldCheckTool` (difficulty validation)
- [x] Validate: 100 worlds, all valid DAGs, difficulty varies with params

## Phase 3 — Teacher solver
- [x] Implement exact Bayesian inference (pgmpy VariableElimination)
- [x] Implement information gain calculation
- [x] Implement optimal action sequence generation
- [x] Validate: teacher reaches >90% on infer_target after full episode

## Phase 4 — Episodes, tasks, verifier
- [x] Implement `EpisodeGenTool`
- [x] Implement `TaskGenTool` (infer_target)
- [x] Implement `VerifierTool` (functional scoring)
- [x] Implement `EpisodeRunner` (environment interface)
- [x] End-to-end test: teacher as agent through full episode

## Phase 5 — LLM Orchestrator
- [x] Define orchestrator system prompt
- [x] Define tool definitions for function calling (4 tools)
- [x] Wire tools to LLM via Azure Foundry (openai SDK)
- [x] Implement orchestrator loop (propose → check → refine → accept)
- [x] Mocked tests (full loop, retry, max iterations)

## Phase 6 — Semantic layer
- [x] Extend World model with semantic metadata (scenario_title, scenario_description, domain)
- [x] Semantic node names and descriptions (water_temperature not indicator_1)
- [x] Semantic edge mechanisms (causal descriptions in context)
- [x] Semantic action descriptions with costs ("solicitar análisis" not "observe node_3")
- [x] Simple theoretical context per world (prior theories, hints, partial findings)
- [x] Data presentation: tabular dataset format (sample from BN, present as DataFrame)
- [x] Data presentation: isolated observations format
- [x] Configurable data presentation per world
- [x] Orchestrator accepts narrative seeds ("contaminación de suelos", scenarios, etc.)
- [x] Update orchestrator prompt to generate semantic content from seed
- [x] `ResearchProblem` model that packages everything the agent sees
- [x] Update display.py for semantic worlds
- [x] Update test_orchestrator.py script for semantic output
- [ ] Update demo script and notebook

## Phase 7 — LLM Agent solver
- [x] Agent interface: receive ResearchProblem, interact via EpisodeRunner
- [x] Agent orchestrator: LLM agentic loop with observe/submit tools
- [x] Agent system prompt and tool definitions
- [x] Agent evaluation: score vs teacher and random baseline
- [x] Comparison script: agent vs teacher vs random baseline
- [x] Run agent with real LLM and validate end-to-end
- [x] End-to-end script: orchestrator -> agent (scripts/test_e2e.py)

## Phase 8 — More templates + more tasks
- [ ] Implement causal chain template (with semantic layer from start)
- [ ] Implement fork/collider template (with semantic layer from start)
- [ ] Implement `next_best_observation` task type
- [ ] Implement `hypothesis_selection` task type
- [ ] Validate: same world produces multiple task types

## Phase 9 — Dataset generation + eval harness
- [ ] Generate teacher trajectories and export as JSONL dataset
- [ ] Implement batch evaluation harness
- [ ] Run agent across 100+ problems, collect metrics
- [ ] Comparative analysis: teacher vs agent across templates/difficulties
- [ ] Document results

## Known issues (from E2E testing, 2026-03-07)
- [ ] Agent submit format: LLM sends flat keys instead of `{"distribution": {...}}`, wastes 1 turn on retry every time
- [ ] Agent worse than random on 8-node worlds: bad inference when more variables are involved (soil case KL 4.21 vs random 0.30)
- [ ] Orchestrator ignores difficulty in goal: always generates "easy" regardless of "hard difficulty" in prompt
- [ ] `apply_semantics` always fails first call: LLM sends empty `node_renames`, then retries correctly (wastes 1 API call)
- [ ] Agent variable selection suboptimal: doesn't pick most informative variables (different order than teacher)

## Backlog (not v0)
- [ ] Synthetic document artifacts (papers, reports, notes)
- [ ] Seeds from real papers (LLM extracts structure)
- [ ] Automatic paper search for seeds
- [ ] Intervention tasks (do-calculus)
- [ ] Structure recovery tasks
- [ ] Complex agent actions (multi-node, conditional)
- [ ] Agent actions defined freely per world (beyond observe)
- [ ] Approximate inference teacher (larger worlds)
- [ ] Curriculum over world complexity
- [ ] RL training loop with verifier as reward
