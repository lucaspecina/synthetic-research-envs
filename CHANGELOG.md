# SREG — Changelog

> All notable changes to this project are documented here.
> Format: date, description, phase reference.

## [Unreleased]

### 2026-03-07 — Vision realignment
- **Project vision updated**: shifted from abstract Bayesian worlds to realistic
  research problems with semantic layer on top of formal networks
- Revised implementation plan: 9 phases (was 7). Added Phase 6 (semantic layer),
  Phase 7 (LLM agent solver), renumbered Phase 8 (templates) and Phase 9 (eval)
- Created `docs/CURRENT_STATE.md` — detailed description of what exists today
- Updated PROJECT.md with full vision:
  - Two-layer architecture: formal (BN) + semantic (narrative, data, actions)
  - Rich data presentation: tabular, multi-dataset, observations, experiments
  - Agent freedom: free to reason however it wants, only actions cost budget
  - Semi-real naming: real vocabulary in fictional domains
  - Comprehensive evaluation framework: inference, causal, structure, optimization,
    hypothesis selection, multiple evaluations per task, rubrics, SOTA references
  - Clear version roadmap (v0-v3) with evaluation types mapped to versions
- Updated TODO.md, CLAUDE.md, IMPLEMENTATION_PLAN.md to reflect new direction
- Added configurable model via AZURE_MODEL env var and auto-load .env
- Rewrote orchestrator test script with step-by-step pretty output

### 2026-03-07
- **Phase 4 complete**: episodes, tasks, verifier, and environment interface
  - `EpisodeGenTool`: generates episodes from worlds (budget, costs, initial evidence)
  - `TaskGenTool`: formulates `infer_target` tasks with correct answer (prior distribution)
  - `VerifierTool`: KL divergence scoring, information efficiency, per-step scoring
  - `EpisodeRunner`: step-by-step environment interface (observe, query, submit)
  - End-to-end test: teacher as agent achieves >90% MAP accuracy through EpisodeRunner
- **Phase 5 complete**: LLM orchestrator for world generation
  - System prompt with workflow instructions and guidelines
  - 4 tool definitions for function calling (world_gen, world_check, episode_gen, task_gen)
  - `Orchestrator` class: agentic loop with tool dispatch, retry logic, world registry
  - Uses Azure AI Foundry via openai SDK (OpenAI client, not AzureOpenAI)
  - Mocked tests: full loop (4 iterations), retry on validation failure, max iterations
  - Created `.env.example` for credential configuration
- 125 tests total, all passing

### 2026-03-06
- **Phase 2 complete**: world generation and validation
  - `LatentPreferenceTemplate`: generates DAG + CPDs with controllable edge_strength
  - `WorldGenTool`: generates worlds from config (template, num_nodes, edge_strength, seed)
  - `WorldCheckTool`: validates DAG acyclicity, latent nodes, paths, entropy, d-separation
  - `world_to_pgmpy()`: converts World models to pgmpy DiscreteBayesianNetwork
  - 100 worlds generated and validated, difficulty varies with parameters
- **Phase 3 complete**: exact Bayesian teacher solver
  - `ExactBayesSolver`: posterior computation, information gain, optimal action selection
  - Ancestral sampling for world state generation
  - Trajectory generation with optimal observation ordering
  - Teacher reaches >90% MAP accuracy across 50 worlds (250 episodes)
- 81 tests total, all passing

### 2026-03-06
- **Phase 1 complete**: all Pydantic data contracts defined and tested
  - `World`, `Node`, `Edge`, `CPD`, `DifficultyProfile` (world.py)
  - `Episode`, `Action`, `ActionType`, `Observation`, `StepResult` (episode.py)
  - `Task`, `TaskSpec`, `TaskType` (task.py)
  - `TeacherOutput` (teacher.py)
  - `Score`, `StepScore` (score.py)
- Set up `pyproject.toml` with all dependencies (pgmpy, networkx, numpy, scipy, pydantic, openai)
- Set up pytest skeleton with 40 tests covering all models
- All models support JSON serialization roundtrips
- Validation: CPD table shape, probability sums, node references, target existence

### 2026-03-06
- Initial project scaffolding: CLAUDE.md, PROJECT.md, TODO.md, CHANGELOG.md
- Created implementation plan (`docs/IMPLEMENTATION_PLAN.md`)
- Created custom Claude Code slash commands
- Moved original design documents to `docs/references/`
- Defined project conventions and maintenance rules
