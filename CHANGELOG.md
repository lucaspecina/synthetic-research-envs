# SREG — Changelog

> All notable changes to this project are documented here.
> Format: date, description, phase reference.

## [Unreleased]

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
