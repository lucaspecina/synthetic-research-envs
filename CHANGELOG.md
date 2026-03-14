# SREG — Changelog

> All notable changes to this project are documented here.
> Format: date, description, phase reference.

## [Unreleased]

### 2026-03-14 — Integrate benchmarks + training from worktrees (BENCH.1, TRAIN.1-4)
- **Benchmarks integrated**: CLadder, QRData, DiscoveryBench adapters from worktree
  benchmark-suite. OpenAIClient (ModelClient protocol). run_benchmark.py script.
  BEFORE scores documented (GPT-5.2: CLadder 78%, QRData 38%, DiscoveryBench 0.299).
- **Training module integrated**: SregEnv (verifiers adapter over EpisodeRunner),
  adapters, types, validators, rubric, dataset generation, prompts. From worktree
  rl-env-verifiers.
- **python_exec unified**: training/tools.py now imports from agent/python_exec.py
  (single kernel). _build_python_namespace delegates to make_python_namespace.
  Identical semantics between diagnostic and training paths.
- 783 -> 1086 tests.

### 2026-03-14 — Unified inference infrastructure (INF.1, INF.3, PYEX.1)
- **Configurable solver backend**: `generate_src.py` now accepts `--solver-model`,
  `--solver-base-url`, `--solver-api-key` flags. Supports Azure, vLLM, or any
  OpenAI-compatible API for the solver (orchestrator stays on Azure).
- **serve_model.sh**: script to setup vLLM and serve Qwen (or other models) on
  OpenAI-compatible API with Hermes tool calling. From worktree rl-env-verifiers.
- **python_exec ExecResult**: `execute_code()` returns structured `ExecResult(output,
  ok, truncated)` instead of plain string. 17 new tests for python_exec.
- **Codex review**: removed fake ThreadPoolExecutor timeout (can't truly kill threads
  in CPython, risks namespace corruption). Honest about limitation in docstring.
- TODO.md rewritten: MERGE.1-2 replaced with proper INF/PYEX/BENCH/TRAIN plan.
  Three solver backends, tools separation (solver tools vs SREG tools), verifiers
  as thin adapter. 783 tests.

### 2026-03-14 — think() tool + full_case.md report
- **`think(reasoning)` tool**: forces model to externalize reasoning as a tool call.
  Free, no environment effect. Renders as [SOLVER REASONS] in reports. Helps debug
  agent decision-making when models skip content tokens before tool calls.
- **`full_case.md`** (NEW output from `--solve`): complete case report in one file.
  Part 1: exact system prompt + dataset info (what the solver received).
  Part 2: full conversation with code, outputs, measurements, reasoning, submits.
  Part 3: evaluation table + per-question detail with correct vs solver answers.
- Prompt improvements: clarified `df` has ALL rows (not just preview), listed tools
  as capabilities not instructions, removed prescriptive phase ordering.

### 2026-03-14 — S.5: Agent Solver v3 — python_exec + unified case solving
- **`src/sreg/agent/python_exec.py`** (NEW): persistent Python interpreter for the agent.
  Sandboxed exec() with namespace persistence (like Jupyter). Pre-loads numpy, pandas,
  scipy. Dataset available as `df`. Observations synced as `observations` dict.
  Import whitelist, restricted builtins, code/output limits. FREE (no budget cost).
- **`AgentSolver.solve_case()`** (NEW): solves all tasks in a single episode.
  Shared budget, shared observations. Agent receives all questions at once.
  `submit(question=N, ...)` per question. Nudge mechanism if agent writes text
  instead of tool calls.
- **`CaseResult`** (NEW): holds per-question AgentResults from unified solving.
- **`build_case_system_prompt()`** + **`build_case_tools()`**: multi-task prompt
  with 3-phase investigation structure (analyze data → gather evidence → submit).
  Multi-format submit tool (distribution, choice, variables, node+state).
- **`generate_src.py --solve`**: now uses unified `solve_case()`. Single episode
  for all tasks. Trajectory shows full conversation with python code blocks.
- **Trajectory rendering**: python code as ```python blocks, research_action results
  concise, submit as formatted JSON, environment outputs as plain text.
- **`agent_trajectory.py`**: handles research_action and python_exec tool calls.

### 2026-03-13 — generate_src.py: official SRC generation script
- **`scripts/generate_src.py`**: single entry point to generate, inspect, and evaluate SRCs.
  - `--goal` or `--seed-file` for research context
  - `--inspect`: exports briefing.md, dataset.csv, answer_key.md (quick guide + BN + CPDs + correct answers), dag.png
  - `--solve`: runs agent on each task, exports evaluation.md (scores) + trajectory.md (reasoning)
  - `--solve` implies `--inspect`
- **Answer key** includes: Mermaid DAG diagram, qualitative quick guide (variable importance via IG,
  causal relationship strengths, baseline), formal BN specification (nodes, edges, CPDs), correct answers.
- **DAG visualization**: matplotlib PNG with layered layout, color-coded nodes (latent=red, observable=green, target=yellow).
- 7 legacy scripts removed (test_orchestrator, test_e2e, test_agent, mini_benchmark, diagnostic_batch, batch_eval, qualitative_analysis). 13 scripts -> 6.

### 2026-03-13 — Docs cleanup: SREG core vs agent harness separation
- Separated SREG environment tools (research_action, submit) from agent harness (python_exec, etc.)
- Agent harness, training pipeline, benchmarks marked as separate workstreams in TODO.md
- Fase -1 contracts clarified as preparatory interfaces, not SREG core

### 2026-03-13 — Rich Actions Slice B: intervene actions (do-operations)
- **ActionType.INTERVENE** + **ActionDef.effects** (`dict[str, str]`): structured
  intervention payload. AvailableAction.intervention_values in semantic layer.
- **EpisodeRunner refactor**: `_handle_rich_action()` dispatches observe/intervene.
  `_execute_intervene()` fixes nodes to specified states, tracks in `_interventions`
  (separate from `_evidence`). `_get_node_value()` samples descendants from
  interventional distribution P(Y | do(X=x), evidence) via pgmpy CausalInference.
- **Post-intervention consistency**: `_invalidate_descendants()` removes stale
  evidence. `true_posterior()` and `_handle_query()` use `causal_query` when
  interventions are active. Monotonic RNG counter for correct sampling.
- **Conflict guards**: cannot observe+intervene same node, cannot intervene twice,
  action type mismatch validation (Action.type vs ActionDef.action_type).
- **ProblemBuilder**: `_build_intervene_actions()` for observable target parents.
  One action per (node, state) pair. Cost 3, capped at 4 actions.
- **Agent solver**: maps ActionDef.action_type to ActionType for clean traces.
- **Prompts**: explains Measurements vs Experiments (do-operations).
- **Codex review**: 3 findings fixed (type mismatch validation, RNG reseeding,
  _invalidate_descendants limitation documented).
- 11 new tests. 766 tests total.

### 2026-03-13 — Fase -1: Shared contracts for parallel development
- **Inference protocol** (`src/sreg/inference/`): Provider-agnostic LLM interface.
  `ModelClient` Protocol, `Message`, `ChatResponse`, `ToolSpec`, `ToolCall`, `Usage`.
  StrEnum roles/finish reasons. Supports OpenAI API and vLLM local.
- **Benchmark format** (`src/sreg/models/benchmark.py`): `BenchmarkResult` with
  reproducibility metadata (seed, prompt/code/dataset versions, toolset version).
  `BenchmarkComparison` for BEFORE/AFTER transfer evaluation.
- **Code execution contract** (`src/sreg/models/code_exec.py`): `CodeExecConfig`
  (timeout, memory, allowed imports) and `CodeExecResult` (status, stdout/stderr,
  truncation flags). Implementation TBD.
- **Environment protocol** (`src/sreg/models/env_protocol.py`): `SREGEnvironment`
  Protocol (reset/step), `EnvAction`, `EnvObservation`, `EnvStepResult`.
  Gymnasium-inspired interface for verifiers MultiTurnEnv integration.
- **Agent toolset** (`src/sreg/models/agent_tools.py`): `AgentTool`, `AgentToolset`,
  canonical tool definitions (RESEARCH_ACTION, PYTHON_EXEC, SUBMIT).
  Same tools for training, diagnostic, and benchmarks.
- 25 new contract tests. 757 tests total.
- **Codex review**: 4 findings (1 P0 fixed: `model_config` -> `inference_config`
  to avoid Pydantic v2 reserved name conflict).

### 2026-03-12 — S.4 MVP-1: observe(variable) -> research_action(action_id)
- **Agent interface redesign**: Agent now selects from an action catalog by ID instead of
  requesting individual variables. Tool renamed `observe` -> `research_action(action_id)`.
  Aligns with PROJECT.md vision of typed research actions.
- **AvailableAction.id**: New field with auto-generation from nodes. ProblemBuilder generates
  explicit IDs (`measure_X`, `survey_X_Y`). EpisodeGenTool uses AvailableAction.id for ActionDefs.
- **Action catalog in prompt**: Actions displayed with ID, type label (Measurement/Experiment/
  Data request/Consultation), cost, and description.
- **Budget tracking fix**: Corrected from `+= 1` to `budget_total - remaining` (accounts for
  variable costs in rich actions).
- **EpisodeRunner guard**: Rejects non-observe action types until Slice B implementation.
- **Prompt cleanup**: Removed hypothesis_selection coaching ("Compare the NUMBERS...").
  SREG presents information, does not coach the agent on how to reason.
- **Generic prompt language**: "actions return findings" instead of "measurements reveal values".
- **Legacy backward compat**: `observe(variable)` still works via `_handle_observe`.
- **Codex review**: No P0 bugs. Deuda: ID uniqueness validation, legacy observe divergence.
- 732 tests (7 new + 1 guard).

### 2026-03-12 — Qualitative analysis fixes: compare_interventions + hypothesis_selection
- **compare_interventions semantic inversion fix**: Auto-generated question (which contains
  the exact intervention states from correct_answer) is no longer overridden by the
  orchestrator's narrative question. Prevents "increasing X" in question but "X:weak" in
  answer. New `_NEVER_OVERRIDE_QUESTION_TYPES` set. 2 tests (1 new + 1 updated).
- **hypothesis_selection framing fix**: Agent prompt now always shows candidate hypotheses
  as numbered probability distributions with explicit instruction to compare NUMBERS not
  narratives. Submit instruction updated: "pick the distribution that best matches evidence".
- **Qualitative analysis script**: New `scripts/qualitative_analysis.py` for step-by-step
  agent reasoning inspection. 3-case run with gpt-5.3 in `experiments/qualitative_20260312_124512/`.
- **Root cause from qualitative analysis**: agent fails hypothesis_selection because it
  reasons narratively ("which story sounds right") not formally ("which distribution matches").
  compare_interventions had real SREG bug (semantic inversion). Both fixed.
- 725 tests (1 new).

### 2026-03-12 — DIAG.4: ZERO_OBS reclassification + Dirichlet distractor fix
- **ZERO_OBS reclassification**: NBO and should_condition with 0 observations and correct
  answer no longer flagged as failures (return `None` instead of "ZERO_OBS_CORRECT").
  These types have valid immediate-answer behavior.
- **Hypothesis D distractor**: Replaced reversed posterior (identical when symmetric) with
  Dirichlet-sampled random distribution. Added KL < 0.05 distinguishability warning.
- **Codex review**: identified deuda — explicit label instead of None, resample on low KL,
  test distractor generation quality. Logged for future iteration.
- 724 tests (3 new/replaced).

### 2026-03-12 — P0 cleanup: submit format, budget wording, apply_semantics, consistency check
- **Agent submit format**: Tool description now shows correct vs wrong format explicitly.
  Auto-correction in code: flat keys are silently normalized instead of rejected.
- **Budget wording**: "N observations" -> "research budget of N units" across agent prompts,
  task_gen, and problem_builder. Costs now described as variable.
- **apply_semantics first-call fix**: Prompt clarifies identity mappings are required.
  Code auto-completes identity mappings when node_renames is empty or partial.
- **Consistency check**: New `_check_question_answer_consistency()` validates that question
  text mentions nodes from the formal answer. Logs WARNING on mismatch. 4 new tests.
- Codex review incorporated: auto-correction in code (not just prompts), test coverage.
- 722 tests (4 new).

### 2026-03-12 — Complete P0 fix: node hints connected to orchestrator + manual audit
- **P0 fix completion**: Node hints now flow end-to-end from orchestrator LLM to task
  generators. Three changes:
  1. `design_case` tool schema exposes hint fields (`intervention_node`, `desired_state`,
     `compare_nodes`, `condition_variable`) so the orchestrator LLM can specify them.
  2. `_handle_design_case()` extracts hints and validates them: required for the 5
     node-sensitive eval types (error if missing → LLM retries), node names must be
     OBSERVABLE (not latent/target), `desired_state` must be a valid state of target node.
  3. System prompt updated with "Node hints — REQUIRED" section guiding the LLM.
- **Manual audit of 3 SRCs**: Generated 3 targeted cases (latent/confounding, interventions,
  evidence/diagnosis) to verify all 9 eval types. Found that without hints, 5/9 types
  had question/answer mismatches. After fix: 4/4 MATCH on the worst case (agriculture).
  Key finding: `best_intervention` was generating "maximize LOW crop yield" (absurd) —
  now correctly generates "maximize high crop yield".
- **Codex collaboration workflow**: Codex (OpenAI) as critical second opinion via MCP.
  Mandatory for code review, recommended for strategy/architecture. Claude leads,
  Codex advises. Flexible guidelines, not rigid checklist.
- 718 tests (22 new: 9 node hints on task_gen, 13 hint validation on orchestrator).

### 2026-03-11 — Rename benchmark to diagnostic + transfer benchmark concept + external benchmarks doc
- **Terminology change**: "benchmark" -> "diagnostic" for the internal environment quality
  control pipeline. Reserved "benchmark" for the real test: transfer experiment on external
  benchmarks (BEFORE -> TRAIN on SREG -> AFTER).
- **`docs/EXTERNAL_BENCHMARKS.md`** created: consolidated analysis of 20+ external benchmarks
  from two independent sources (Claude + GPT). Recommended suite: CLadder (causal reasoning,
  10K questions, deterministic), QRData (causal + data, 411 questions), DiscoveryBench
  (hypothesis from data, 264 tasks), SciGym (experimental cycle, 350 systems).
  Includes BEFORE/AFTER protocol, controls, success criteria, overfitting risks.
- **Three-level QA** documented across PROJECT.md, CLAUDE.md, CURRENT_STATE.md:
  1. Tests + Validation (pre-commit): "did I break something?"
  2. Environment Diagnostic (periodic): "are the environments good?"
  3. Transfer Benchmark (FUTURE): "does training on SREG improve policies?"
- **TODO.md**: BM.* renamed to DIAG.*, new BENCH.1-BENCH.5 section for transfer benchmark.
- **Skills updated**: `/eval` and `/precommit` reflect diagnostic terminology.
- **Code rename complete**: `benchmark.py` -> `diagnostic.py`, `run_benchmark.py` ->
  `run_diagnostic.py`, `test_benchmark.py` -> `test_diagnostic.py`. All classes renamed:
  BenchmarkRunner -> DiagnosticRunner, BenchmarkReport -> DiagnosticReport,
  format_benchmark_report -> format_diagnostic_report, save_benchmark -> save_diagnostic.

### 2026-03-11 — Documentation rewrite: SREG purpose ultra-clear
- **PROJECT.md, CLAUDE.md, CURRENT_STATE.md rewritten** to make SREG's purpose crystal clear:
  SREG generates synthetic research environments with exact reward signals, designed for
  training policy models that do science via RL. SREG generates + computes rewards; it does
  NOT train policies (no training loop, no optimizer, no train.py).
- Reframed as verifier environment (like PRIME Intellect for math, but for scientific reasoning).
- New terminology: SRC = training environment, Teacher = optimal policy, Policy = any agent.
- Backlog: replaced "RL training loop" with "Export formal de entornos para integracion con RL".

### 2026-03-11 — Per-type baseline scoring + 15-SRC benchmark
- **`src/sreg/harness/benchmark.py`**: `compute_baseline_score()` and `beats_baseline()` functions.
  Computes random baseline per eval type: KL(uniform||correct) for distributions, 0.5 for binary
  choice, 1/N for hypothesis_selection, mean/max ratios for NBO and best_intervention.
  Direction-aware comparison (lower KL = beats, higher accuracy = beats).
- **`TaskResult`**: new fields `baseline_score`, `agent_beats_baseline`.
- **`TypeMetrics`**: new fields `baseline_scores`, `n_baseline_computed`, `n_beats_baseline`.
- **`format_benchmark_report()`**: new "BASELINE COMPARISON (random guess)" section.
- **24 new tests** (54 total in test_benchmark.py): TestComputeBaseline (14), TestBeatsBaseline (8),
  TestBaselineAggregation (2). 696 tests total.
- **`scripts/run_benchmark.py`**: expanded to 15 goals (from 5) across diverse domains.
  Default --cases=15. Output shows baseline comparison per task.
- **`experiments/bench_20260311_15srcs/`**: 14/15 SRCs completed, 57 tasks, 9/9 eval types.
  Key findings: causal_effect and compare_interventions beat baseline 71%. hypothesis_selection
  WORSE than random (17% beats). NBO suspicious (100% correct, 100% ZERO_OBS). should_condition
  and infer_latent_cause struggle (25%, 0% beats respectively).

### 2026-03-11 — First full benchmark: 5 SRCs, 19 tasks, 9/9 eval types
- **`experiments/bench_20260311_5srcs/`**: first benchmark covering all 9 eval types.
  5/5 SRCs completed, 100% submit, 0 format errors. infer_target consistently GOOD+.
  causal_effect acceptable (KL ~0.49). ZERO_OBS_CORRECT in 4/19 binary choice tasks
  (preliminary — could be guessing at 50%). N per type still low (1-5).
- Updated `experiments/index.md` with diag and bench entries.

### 2026-03-11 — BenchmarkRunner: type-aware verdicts and failure classification
- **`src/sreg/harness/benchmark.py`**: BenchmarkRunner class — importable library for
  running real E2E benchmarks. Type-aware verdict (KL thresholds for distribution types,
  accuracy for choice types). Type-aware failure modes (ZERO_OBS_LOW_KL, ZERO_OBS_CORRECT,
  INCORRECT, HIGH_KL, FORMAT_RETRY — no global TRIVIAL). Marked PARTIAL always.
- **`scripts/run_benchmark.py`**: thin script wrapper for BenchmarkRunner.
- **30 new tests** (`tests/harness/test_benchmark.py`): verdict classification (11),
  failure mode classification (12), aggregation (5), report formatting (2).
- Absorbs patterns from diagnostic_batch.py and mini_benchmark.py into reusable library.
- 672 tests total.

### 2026-03-11 — S.2 Diagnostic pipeline: real multi-type E2E validation
- **`scripts/diagnostic_batch.py`** (rewritten): generates N SRCs via real orchestrator,
  runs agent on EACH task (not just infer_target), collects per-eval-type metrics,
  classifies failure modes (TRIVIAL, NO_SUBMIT, WRONG_ANSWER, HIGH_KL, FORMAT_ERROR),
  generates diagnostic report. Saves summary + report + per-task trajectories.
- **`src/sreg/harness/agent_trajectory.py`**: `AgentTrajectory.submitted_answer` now `Any`
  (was `dict[str, float]`). Added `task_type` field.
- **First real multi-type diagnostic** (`experiments/diag_20260311_first/`):
  3 SRCs, 11 tasks, 7/9 eval types exercised, 91% submission rate, 0 format errors.
  Key finding: choice types (hypothesis, compare, best_intervention) tend to be trivial
  (agent answers without observing) or wrong. Distribution types (infer_target, causal_effect)
  work well when agent submits.

### 2026-03-11 — Multi-type agent harness: submit + prompt + scoring for all 9 eval types
- **`src/sreg/agent/prompts.py`**: dynamic submit tool per task type (distribution, choice,
  intervention, variable set). System prompt adapts question, target node, format instructions.
  Only overrides states_str for distribution types (not choice/NBO/hypothesis).
- **`src/sreg/agent/agent.py`**: `_handle_submit()` routes to 4 specialized handlers.
  `_submit_distribution()` validates against task-specific states (not just problem.target_states).
  `_score_result()` routes to correct verifier method per type.
  NBO -> choice + score_nbo(). causal_effect/infer_latent_cause -> task.correct_answer.
- **54 agent tests** (was ~15). Full coverage: tool generation, dispatch, scoring, full loops
  for all 9 types. Tests for bug fixes (prompt states, distribution validation, NBO error msg).
- **NOT "the agent solves all 9 types well"** — that requires the real benchmark. This is
  correct plumbing: the harness accepts, formats, and scores all 9 types correctly.
- **Known limitation**: observe remains single-node/cost-1 (Rich Actions S.4 pending).

### 2026-03-11 — First mini benchmark: 3 real SRCs end-to-end
- **`scripts/mini_benchmark.py`**: runs N real SRCs via orchestrator + agent + teacher.
  5 varied goals (marine ecology, epidemiology, materials science, agriculture, geology).
  Per-case: orchestrator generates -> worldcheck -> teacher trajectory -> random baseline ->
  agent solver -> trajectory extraction -> comparison. Summary table + failure mode analysis.
- **First real experiment** (`experiments/mini_20260311_100704/`):
  - Orchestrator: 100% completion, all WorldCheck PASS, 4 eval types per case
  - Agent: 100% submit rate, 1/3 beats random. KL range 0.005-0.54
  - Verdicts: 1 EXCELLENT, 1 GOOD, 1 FAIR
  - Key finding: agent chooses variables by "common sense", not information gain
  - Submit format error in 2/3 cases (agent forgets `distribution` key)
- **Limitation mayor documentada**: solo se evalua infer_target. Los otros 8 eval types
  no tienen solver. No bloquea el mini benchmark pero limita las conclusiones sobre el
  producto completo segun PROJECT.md.
- **SRC** (Synthetic Research Case) defined as project terminology: the complete case
  generated by the system (world + problem + tasks + data).
- `experiments/index.md` created with first experiment entry.
- `EVAL_DESIGN.md` added to CLAUDE.md docs list.

### 2026-03-10 — Quality assurance strategy: tests vs benchmark
- **Documented the two-level QA strategy** across PROJECT.md, CLAUDE.md, TODO.md,
  CURRENT_STATE.md, and skills (`/eval`, `/precommit`):
  - Level 1: Tests + Validation (pre-commit) — unit tests + E2E smoke. "Did I break something?"
  - Level 2: Benchmark & Diagnostic (periodic) — real system E2E with LLM. "Is the product good?"
- **Key principle**: the benchmark ALWAYS uses the real system (LLM, orchestrator,
  CasePlan, semantics). No toy worlds, no fabricated inputs.
- **Identified QualitySuite v2 gap**: only covers 3/9 eval types with programmatic worlds.
  Needs evolution to full benchmark with real pipeline.
- **Planned benchmark tasks** (BM.1-BM.5 in TODO.md): implement real E2E benchmark script,
  create experiments/ directory, update quality.py for all eval types, consolidate scripts.
- **Updated `/eval` skill**: now reflects benchmark philosophy (real system, two outputs:
  aggregate metrics + failure mode analysis).
- **Updated `/precommit` skill**: clearer separation between validation (Level 1) and
  benchmark impact check.

### 2026-03-10 — Agent trajectory inspection (S.1)
- **New module `src/sreg/harness/agent_trajectory.py`**: `AgentTrajectoryStep` and
  `AgentTrajectory` Pydantic models. `extract_agent_trajectory()` post-processes
  the raw chat messages from `AgentResult` into structured, inspectable steps
  (thinking, tool call, observation, error, submit). `export_agent_trajectories()`
  writes JSONL.
- **New module `src/sreg/harness/comparison.py`**: `TrajectoryComparison` model +
  `compare_trajectories()` builds side-by-side agent vs teacher comparison with
  verdict (EXCELLENT/GOOD/FAIR/POOR/NO_SUBMIT).
- **New script `scripts/view_trajectory.py`**: CLI viewer for agent trajectories
  and comparisons. Auto-detects file type.
- **`scripts/test_agent.py`**: new `--save-trajectory DIR` flag. Saves agent
  trajectory JSON + comparison JSON after running.
- 18 new tests (601 total): extraction, serialization, export, comparison.
- Zero changes to `AgentSolver.solve()` — trajectories extracted post-hoc.

### 2026-03-10 — Fix question/answer mismatch bug + budget wording
- **BUG FIX (P0)**: `generate_from_plan` was overriding question text for ALL eval
  types, causing mismatches where the question mentioned different nodes/interventions
  than the correct_answer. Now only safe types (infer_target, NBO, hypothesis_selection,
  infer_latent_cause) get the plan's custom text. Intervention-dependent types
  (causal_effect, best_intervention, compare_interventions, adjustment_set,
  should_condition) keep their auto-generated question that matches the answer.
- **Budget wording**: changed from "N observaciones" to "N unidades de investigacion"
  in display.py (terminal + HTML). Reflects that actions have varied costs now.
- 2 new tests (583 total): safe vs unsafe question override in generate_from_plan.
- Documented 6 design issues from E2E case analysis in TODO.md.

### 2026-03-10 — Activate rich actions and CasePlan question in build_problem
- **Orchestrator `build_problem`** now passes `rich_actions=True` and the CasePlan
  (if available) to `ProblemBuilder.build()`. This means the agent sees varied-cost
  actions and the LLM-designed research question instead of the generic template.
- **`ProblemBuilder.build()`** accepts `case_plan: CasePlan | None`. When provided,
  `_build_question()` uses the primary question's `question_text` from the plan.
- 3 new tests (581 total): case_plan question used, fallback to generic, combo with rich_actions.

### 2026-03-10 — Case inspection tooling: --seed, --export, /run skill
- **`test_orchestrator.py` enhanced**: `--seed N` (reproducibility hint), `--export path.json`
  (full case export), `--verbose` (raw HTTP logs). Step-by-step process display with compact
  tool args, design_case/dag_construct result summaries, case plan questions with rationale,
  generated tasks with correct answers, research problem view.
- **JSON export**: metadata (timestamp, goal, model), process (all tool calls with args/results),
  world (nodes, edges, scenario), case_plan (questions, rationale), tasks (type, question,
  correct answer), research_problem (narrative, data_assets, available_actions).
- **`/run` skill**: new skill for running the orchestrator. Parses topic, builds goal,
  auto-exports with timestamp, reports findings in Spanish.
- **`README.md` rewritten**: quick start, generate and inspect research cases, script examples,
  eval types table (9 types), JSON export structure, LLM integration docs.
- **`TODO.md`**: added Rich Actions Slice A design debt section (sibling grouping and
  target-proximity costs are provisional heuristics).

### 2026-03-10 — Rich Actions Slice A: typed, multi-node, varied-cost actions
- **`ResearchActionType` enum** in `research_problem.py`: `observe`, `intervene`,
  `request_dataset`, `consult` (reserved). Named `ResearchActionType` to avoid
  collision with existing `ActionType` in episode.py (agent interaction types).
- **`AvailableAction` expanded**: `action_type`, `nodes: list[str]`, backward-compat
  `node: str` (auto-synced via model_validator). Supports multi-node actions.
- **`ActionDef` model** in episode.py: formal action definition (id, action_type,
  nodes, cost). `Episode.action_defs` for rich mode, empty = legacy mode.
- **`StepResult.extra_observations`**: additional observations from compound actions.
- **`EpisodeRunner` multi-node**: compound observe via `action_id` reveals N nodes
  in one step. Validates no double-use, budget checks, node overlap.
- **`ProblemBuilder.rich_actions`**: `rich_actions=True` flag generates varied costs
  (target-adjacent cost 2) and compound actions from sibling groups (nodes sharing
  a parent in the DAG). Max 1 compound action per problem.
- **`EpisodeGenTool` rich mode**: accepts `available_actions` parameter, generates
  matching `ActionDef`s and backward-compat `node_costs`.
- **Teacher IG/cost optimization**: `optimal_action()` and `generate_trajectory()`
  accept `costs: dict[str, int]` parameter. Optimizes IG/cost ratio instead of
  pure IG. Budget-aware: skips nodes that don't fit remaining budget.
- 26 new tests (578 total). E2E: 3 templates x 3 seeds, all pass. Compound action
  reveals 3 nodes at once. Teacher handles varied costs correctly.

### 2026-03-10 — Ola 1: infer_latent_cause eval type (Ola 1 COMPLETE)
- **`TaskType.INFER_LATENT_CAUSE`**: "Based on observed symptoms, what is the probability
  distribution over the hidden cause?"
- **`TaskGenTool._infer_latent_cause_task()`**: picks a latent node, samples evidence
  from observables, computes posterior P(latent | evidence) via exact inference
- Uses existing `kl_divergence` scoring (same as infer_target)
- Fixed `generate_all()` to only generate the 3 original bundle types (not all 9)
- 12 new tests. 552 total. E2E validated: entropy reduction 0.13-1.38 bits across
  all templates. More evidence = more certainty about hidden cause.
- **Ola 1 complete**: 5 eval types (causal_effect, best_intervention, adjustment_set,
  compare_interventions, should_condition, infer_latent_cause) + 3 original = 9 total.

### 2026-03-10 — Ola 1: should_condition eval type
- **`TaskType.SHOULD_CONDITION`**: "A colleague suggests controlling for Z when
  analyzing X's effect on Y. Is this correct?"
- **`TaskGenTool._should_condition_task()`**: uses backdoor adjustment sets + DAG
  descendants to classify variables as confounders (should condition) vs
  mediators/collider-descendants (should not condition). Randomizes question type.
- **`VerifierTool.score_should_condition()`**: binary yes/no match
- 14 new tests. 540 total. E2E validated: causal_chain always "no" (mediators),
  fork_collider mixes "yes" (confounders) and "no" (descendants).

### 2026-03-10 — Ola 1: compare_interventions eval type
- **`TaskType.COMPARE_INTERVENTIONS`**: "Your team debates between two interventions.
  Which one has a larger causal effect on the outcome?"
- **`TaskGenTool._compare_interventions_task()`**: picks two interventions from different
  nodes with distinct effects, randomizes presentation order (A/B), computes P(Y|do())
  for each via `causal_query()`
- **`VerifierTool.score_compare_interventions()`**: binary — did the agent pick the better one?
  Equal effects = either answer is correct
- 15 new tests. 526 total. E2E validated across all 3 templates (gaps 0.21-0.51).

### 2026-03-10 — Research: diseño de acciones de investigación
- **New section in WORLD_DESIGN.md**: "Diseño de acciones de investigación"
  - Principle: thinking is free, acting in the world costs budget
  - Four research paradigms: dataset-first, experimental, field, hybrid
  - Distinction: acquisition actions (cost budget) vs analysis (free)
  - Catalog of action types: observe, intervene, request_dataset, consult
  - Parallel with eval types: fixed formal types + orchestrator-designed instances
  - Three worked examples: agriculture, epidemiology, geology
  - Validation chain: orchestrator proposes, tools validate
  - Teacher impact: IG per unit of cost (greedy optimization)
  - Open questions: consult formalization, adaptive actions, noisy measurements
- **TODO.md updated**: Rich actions section rewritten with new design
- Navigation index updated

### 2026-03-10 — Ola 1: adjustment_set eval type
- **`TaskType.ADJUSTMENT_SET`**: "What variables should you control for to estimate
  the causal effect of X on Y?"
- **`TaskGenTool._adjustment_set_task()`**: uses pgmpy `get_all_backdoor_adjustment_sets()`
  to find valid minimal sets, filters to observable-only variables
- **Three task scenarios**: confounded+identifiable (find the set), no confounding (empty set),
  not identifiable (hidden confounder — agent must recognize unidentifiability)
- **`VerifierTool.score_adjustment_set()`**: binary match against valid minimal sets
- 20 new tests. 511 total. E2E validated across all 3 templates + custom DAGSpec.
- Handles pgmpy ValueError when no valid adjustment set exists

### 2026-03-09 — Eval catalog research: 31 task types in 6 scientific families
- **New section in WORLD_DESIGN.md**: "Fundamentos de razonamiento causal y cientifico"
  - Pearl's ladder of causation (3 rungs: association, intervention, counterfactual)
  - McElreath's 4 elemental confounds (fork, pipe, collider, descendant)
  - Design principle: tasks as scientific questions, not DAG exercises
  - Three-level distinction: eval type → question template → research subtask
- **Comprehensive eval catalog** in WORLD_DESIGN.md: 31 eval types in 6 families:
  - A. Diagnosis/explanation (5 types): infer_target, infer_latent_cause, hypothesis_selection, mechanism_selection, explain_anomaly
  - B. Evidence gathering (6 types): NBO, best under cost, measurement bundle, disambiguate experiment, sequential design, efficiency
  - C. Causal intervention (6 types): causal_effect, compare, best, ATE, constrained, mediation
  - D. Structure/model discovery (6 types): adjustment_set, should_condition, simpson_paradox, confounder_detection, structure/skeleton
  - E. Prediction (4 types): prediction, temporal forecast, context shift, counterfactual
  - F. Process quality (5 types): evidence usage, alternative hypotheses, causal coherence, plan quality, calibration
- **Implementation roadmap**: 4 waves (0: done, 1: next 5, 2: 3 more, 3: infrastructure-heavy)
- **pgmpy support mapping**: which functions enable which eval types
- **TODO.md updated**: Eje B rewritten with full wave structure
- Sources: Pearl, McElreath (Statistical Rethinking), CauSciBench, CausalBench, CausalProbe-2024, ResearchGym

### 2026-03-09 — Ola 1: best_intervention eval type
- **`TaskType.BEST_INTERVENTION`**: "What intervention maximizes P(target=desired_state)?"
- **`TaskGenTool._best_intervention_task()`**: iterates all (node, state) interventions,
  computes P(target=desired | do(node=state)) for each, finds optimal
- **`VerifierTool.score_best_intervention()`**: ratio of agent's effect to optimal (like NBO)
- **`Task.intervention`** reused to store optimal {node: state}
- **`correct_answer`** maps "node:state" -> P(target=desired | do(node=state)) (full ranking)
- **13 new tests** (was 478, now 491): generation, ranking, scoring, cross-template, determinism
- **E2E validated**: 6 configs, spreads 0.36-0.99, causally correct (closer nodes = stronger effect)

### 2026-03-09 — B.1: causal_effect eval type (do-calculus)
- **`TaskType.CAUSAL_EFFECT`** added to eval catalog — first new eval type beyond the original 3
- **`ExactBayesSolver.causal_query()`**: computes P(target | do(node=state)) using pgmpy's `CausalInference`
  - Correctly distinguishes interventional from observational: do() != observe() when confounders exist
  - Works across all template families (latent_preference, causal_chain, fork_collider)
- **`TaskGenTool._causal_effect_task()`**: generates causal effect tasks
  - Finds observable nodes with actual causal effect on target (max_diff > 0.02)
  - Weighted selection toward nodes with stronger effects
  - Picks random intervention state, computes P(target | do(node=state)) as correct answer
  - Question text explains the do-operation distinction to the agent
- **`Task.intervention`** field: stores {node: state} for the do() operation
- **`design_case` tool** updated: `causal_effect` added to enum in orchestrator prompts
- **`generate_all()` / `TaskBundle`** updated: now generates all 4 task types
- **14 new tests** (was 465, now 478+existing fixes):
  - 10 causal_effect task generation tests (structure, determinism, cross-template, weighted selection)
  - 4 causal_query solver tests (valid distribution, do!=observe, non-causal node, causal chain)
- **E2E validated**: 7 configs (3 templates × 6-10 nodes), confirmed:
  - do() differs from observe() in latent_preference and fork_collider (confounders)
  - do() equals observe() in causal_chain (no confounders on chain path)
  - Intervention nodes selected with weighted preference for stronger effects

### 2026-03-09 — CasePlan: orchestrator designs research cases (Slice 1)
- **`CasePlan` model** (`src/sreg/models/case_plan.py`):
  - `EvalQuestionPlan`: question_text, eval_type (validated against TaskType), target_node, rationale
  - `CasePlan`: title, research_context, questions list, shared_budget, rationale
  - Validation: no duplicate questions (same eval_type + target_node), min lengths, valid types
  - Properties: primary_question (first), sub_questions (rest), eval_types (unique set)
- **`design_case` orchestrator tool** (`orchestrator/prompts.py` + `orchestrator.py`):
  - LLM proposes a case plan as tool call parameters (like apply_semantics)
  - Tool validates: target nodes exist in world, no duplicates, plan is computable
  - Generates tasks from plan to verify computability before returning
  - Stores validated CasePlan in `_case_plans` dict
- **`generate_from_plan`** (`tools/task_gen.py`):
  - Takes CasePlan + World, returns list[Task] (not TaskBundle)
  - Only generates the tasks the plan requests (not always all 3)
  - Overrides generic question text with plan's custom question_text
- **System prompt updated** to 6-step workflow (added step 4: design_case)
- **35 new tests** (was 430, now 465):
  - 21 CasePlan model tests (validation, serialization, edge cases)
  - 7 generate_from_plan tests (single/multi questions, custom text, determinism)
  - 7 design_case orchestrator dispatch tests (basic, multi-question, invalid target, etc.)
- **E2E validated**: 6 configs across 3 templates (6-10 nodes), full orchestrator dispatch pipeline

### 2026-03-09 — Dataset-rich evidence: multi-dataset, missing data, narratives
- **`DataSampler` rewritten** with multi-dataset mode:
  - `multi_dataset=True`: generates primary + secondary datasets with DAG proximity-based column splits
  - `missing_rate`: injects `"not_measured"` values (configurable 0-50%), ensures >=2 real columns per row
  - `narrative_observations`: generates N natural-language observations from sampled states
  - Original single-dataset mode preserved (backwards compatible)
- **`DataAsset` model extended** with optional metadata: `source`, `columns`, `num_rows`
- **`ProblemBuilder.build(rich_data=True)`**: convenience flag for multi-dataset + missing data + narratives
- **`prompts.py` updated**: renders narrative format, shows source metadata for all assets
- **Column splitting algorithm**: sorts visible nodes by shortest undirected distance to target in DAG,
  closer half → primary, farther half → secondary, 1 overlap column as join key
- **17 new tests** (was 413, now 430): multi-dataset, column splitting, missing data, narratives, determinism
- **E2E validated**: 8 configs across 3 templates (6-12 nodes), all produce coherent rich output
- Bug fix: `_inject_missing` now restores original values instead of placeholder when preserving min columns

### 2026-03-09 — Batch sweep: systematic generator/template comparison
- **`scripts/batch_sweep.py`**: 336 worlds across 7 generators/templates x 4 node counts x 4 edge strengths
- **Key finding: 10-12 nodes is the sweet spot** for research cases with real strategy.
  6-node worlds are budget-saturated (TbRR=0.00), 8 nodes is a "death valley" (21% bundle).
  12 nodes: budget_ratio=0.50, TbRR=0.60, bundle=86%.
- **edge_strength 0.5-0.7 is optimal**. At 0.9, hypothesis distinguishability drops to 43%
  (prior distractor becomes nearly identical to posterior).
- **preferential_attachment eliminated**: 0% WorldCheck pass across all 48 configs.
- **Best generators**: spanning_tree and layered for DAGs, all templates work well at 10+ nodes.
- **Strategic decision**: this closes the formal core validation. Next focus shifts to
  enriching the case presentation (dataset-rich evidence, rich actions, CaseBundle).
- Findings documented in WORLD_DESIGN.md "Batch sweep: regimenes de generacion".

### 2026-03-09 — QualitySuite metric redesign: multi-rollout + entropy reduction
- **Critical finding**: `teacher_beats_prior` metric (KL vs one-hot) penalizes correct
  inference when sampled true state is atypical. Documented with concrete example in WORLD_DESIGN.md.
- **Redesigned Layer B metrics** in WORLD_DESIGN.md:
  - Multi-rollout evaluation (K=5-10 seeds per world, averaged)
  - `mean_entropy_reduction` as primary belief quality metric (sample-independent)
  - `budget_ratio` for episode design quality (uses observables with path to target)
  - Old metrics renamed to `sampled_nll_*` and demoted to diagnostic status
  - `useful_bundle` tightened: requires entropy_reduction AND 2 of 3 quality dimensions
- **E2E with real LLM (GPT-5.2)**: 5 tests across all 3 generation paths (dag_generate,
  dag_construct, classic template). All WorldCheck pass, semantic layer works well.
  Confirmed metric issues in practice (teacher "loses" to prior on atypical samples).
- **CLAUDE.md updated**: E2E must include real LLM when credentials available
- Implementation plan added to TODO.md

### 2026-03-09 — QualitySuite: programmatic evaluation (layers A+B+C)
- **`src/sreg/harness/quality.py`**: suite for measuring world, task, and generator quality
  - Layer A (`compute_world_quality`): structural metrics (density, treewidth, depth, fan-in/out, target reachability, entropy)
  - Layer B (`compute_task_quality`): epistemic metrics (teacher vs prior/random, IG gap, NBO trivial, hyp distinguishable, useful bundle)
  - Layer C (`compute_generator_diversity`): batch statistics (std devs, distributions, acceptance rate, useful bundle rate)
  - `run_quality_suite()`: runs A+B+C on a list of worlds, produces `QualitySuiteReport`
  - `print_quality_report()`: ASCII table with per-world details, summary rates vs targets, diversity stats
  - All models are Pydantic (serializable to JSON)
- **44 new tests** (was 365, now 409): per-layer, runner, reporter, cross-template, cross-generator
- **E2E validation findings**:
  - Templates (6 nodes): teacher_random_gap=0.0 (budget >= observables, both see everything)
  - Preferential attachment: 100% WorldCheck failures (dense graphs lack d-separation)
  - Hypothesis distinguishability low in templates (44%) — known reversed-distractor issue
  - DAG generators (8 nodes): all targets met except worldcheck (75%, due to pref_attach)
- Exported from `sreg.harness` package

### 2026-03-09 — LLM orchestrator integration: dag_generate + dag_construct
- **Two new orchestrator tools** for creating worlds via DAGSpec:
  - `dag_generate`: LLM chooses a generator algorithm (erdos_renyi, spanning_tree, preferential_attachment, layered) + parameters
  - `dag_construct`: LLM specifies exact nodes/edges/types manually for precise causal structures
- Updated SYSTEM_PROMPT with generation method guidance and generator descriptions
- Both tools produce Worlds compatible with existing pipeline (world_check, apply_semantics, build_problem)
- Full pipeline E2E test: dag_generate -> world_check -> apply_semantics -> build_problem
- **15 new tests** (was 350, now 365): dispatch tests, validation errors, downstream pipeline

### 2026-03-09 — DAG generators (4 methods)
- **`dag_generators.py`** (`src/sreg/world/dag_generators.py`): 4 automatic DAG generation methods
  - `generate_erdos_renyi()`: random edges with probability p, good for testing
  - `generate_spanning_tree()`: connected tree + optional extra edges, guaranteed connectivity
  - `generate_preferential_attachment()`: hub-like structures, scale-free-ish DAGs
  - `generate_layered()`: pipeline/stage structures with skip connections
  - All guarantee acyclicity via topological ordering (edges only go lower → higher index)
  - Shared helpers: `_assign_node_types()` (latents early, targets late), `_assign_states()`, `_cap_parents()`
- **E2E validation**: 50 configs (10 generators × 5 seeds), teacher>prior 94%, teacher>random 82%, NBO non-trivial 76%, hypotheses distinguishable 80%
- **40 new tests** (was 310, now 350): per-generator + cross-generator parametrized tests
- Exported generators from `sreg.world` package

### 2026-03-09 — DAGSpec prototype (v2 slice minimo)
- **`DAGSpec` + `DAGNodeSpec`** (`src/sreg/models/dag_spec.py`): universal contract for arbitrary DAGs
  - Validations: acyclic, max parents <= 4, required types, no duplicates
  - Supports heterogeneous state cardinalities (2, 3, 4 states mixed)
  - Convenience methods: parents_of, children_of, to_networkx, nodes_by_type
- **`cpd_gen.py`** (`src/sreg/world/cpd_gen.py`): extracted generic CPD generation
  - Bit-for-bit identical to existing templates (verified by test)
  - Supports heterogeneous parent/child cardinalities
- **`CustomTemplate`** (`src/sreg/world/templates/custom.py`): DAGSpec -> World
  - All 3 task types (infer_target, NBO, hypothesis_selection) work E2E
- **`generate_custom()`** in WorldGenTool: transitional API for custom worlds
- **WorldCheck extended**: max parents (hard fail) + treewidth (warning)
- **E2E results**: teacher always beats prior+random, NBO non-trivial 80-90%, hypotheses distinguishable 75-90%
- **310 tests** (was 229)

### 2026-03-08 — Version alignment + WORLD_DESIGN.md refinements
- **Version scheme simplified**: v0+v1 (done) → v2 (Etapa 2) → v3 (Etapa 3) → Backlog
  - Versions now align 1:1 with WORLD_DESIGN.md stages
  - Dropped v4 (too speculative), moved do-calculus + structure recovery to v3
  - Updated PROJECT.md, TODO.md, CLAUDE.md with new scheme
- **WORLD_DESIGN.md refined** with 4 feedback-driven adjustments:
  - Replaced "teacher >60% accuracy" with improvement-over-prior + gap-over-random
  - Marked `generate_custom()` as transitional API (unify later)
  - Added non-degenerate task rate as success criterion (>70% NBO, >80% hypothesis)
  - Treewidth kept as warning (not hard fail) for learning phase

### 2026-03-08 — WORLD_DESIGN.md research document
- **`WORLD_DESIGN.md` created**: 1100+ line research document for realistic world generation
  - Three-stage progression: motifs → composition → mechanism-first
  - MechanismSpec and DAGSpec as central contracts
  - CaseBundle concept, quality gates, generator health metrics
  - PCG principles adopted: MAP-Elites, generate-evaluate-refine, expressive range analysis
  - Detailed analysis of BoxingGym, DiscoveryWorld, Reasoning Core with concrete takeaways
  - Positioning table: what SREG does that others don't
  - Hallazgos experimentales section for documenting test results
  - Implementation plan for DAGSpec prototype (slice mínimo)
- All docs updated: CLAUDE.md, PROJECT.md, TODO.md reference WORLD_DESIGN.md

### 2026-03-07 — Multiple evaluations per problem (v1 complete)
- **`TaskBundle` model + `generate_all()` method**: one world → all 3 task types
  - `TaskGenTool.generate_all(world, target, budget, seed)` → `TaskBundle`
  - `TaskBundle`: groups infer_target, NBO, and hypothesis_selection tasks
  - Property accessors: `.infer_target`, `.next_best_observation`, `.hypothesis_selection`
  - Full JSON serialization roundtrip support
  - Validated across 18 configs (6 template/node/ES combos × 3 seeds), 0 failures
  - 9 new tests, 229 total, all passing
- **v1 milestone complete**: 3 templates + 3 task types + multi-task generation

### 2026-03-07 — hypothesis_selection task type
- **`hypothesis_selection` task type**: "which of these explanations is most plausible?"
  - Generates 4 hypotheses: true posterior, prior, uniform, reversed posterior
  - Labels shuffled randomly so correct answer isn't always "A"
  - `correct_answer` maps labels to KL from true posterior (lower = better)
  - `VerifierTool.score_hypothesis()`: binary accuracy (chose the best or didn't)
  - `Task.hypotheses` field: stores the labeled distributions
  - Distinguishable in 90%+ of cases across all 3 templates
  - 12 new tests, 220 total, all passing

### 2026-03-07 — next_best_observation task type
- **`next_best_observation` task type**: "which variable should you measure next?"
  - `TaskGenTool` generates NBO tasks: samples state, gives partial evidence, asks what to observe
  - `Task.given_evidence`: new field for evidence already provided to the agent
  - `Task.correct_answer` holds IG ranking: `{node: info_gain}` for each remaining node
  - `VerifierTool.score_nbo()`: scores agent's choice as ratio of chosen IG to optimal IG
  - Works across all 3 templates (latent_preference, causal_chain, fork_collider)
  - 13 new tests (NBO generation + verifier scoring), 208 total, all passing

### 2026-03-07 — Fork-collider template
- **`fork_collider` template**: common cause (fork) + collider with explaining away
  - Structure: hidden_factor → branch_1, branch_2 → collider → [mediators] → target
  - Tests Berkson's paradox: conditioning on collider activates dependency between branches
  - Scales with extra branches (3+) and mediators between collider and target
  - 16 new tests: structure, fork/collider topology, validation, 100 worlds, teacher accuracy
  - Validated: teacher achieves ≥60% accuracy, all 100 worlds pass validation
- Registered in WorldGenTool, exported from templates, added to batch_eval.py
- 196 tests total, all passing

### 2026-03-07 — Causal chain template + KL fix
- **`causal_chain` template**: linear chain root → stage_1 → ... → target
  - Tests evidence propagation: closer nodes are more informative than distant ones
  - 13 new tests: structure, validation, 100 worlds, teacher accuracy, proximity IG
  - Validated: 5/5 agent beats random, mean KL 0.37 vs random 1.67
- **WorldCheckTool d-separation fix**: now also conditions on individual observables
  (chains have d-separations like stage_1 ⊥ stage_3 | stage_2, not just given latents)
- **KL divergence NaN fix**: verifier now clips zero probabilities to epsilon
  (agent sometimes submits 0 for a state, causing 0*log(0)=NaN)
- Batch eval supports `--template` parameter for cross-template comparison
- 180 tests total, all passing

### 2026-03-07 — Phase 8: Dataset export + batch evaluation
- **Teacher trajectory export**: generates optimal teacher trajectory, exports as JSONL
  - `TeacherTrajectory` / `TrajectoryStep`: structured dataclasses with full step info
  - `generate_teacher_trajectory()`: runs teacher, records action, observation, IG, posterior per step
  - `export_trajectories()`: writes list of trajectories to JSONL file
- **Batch evaluation harness**: generate N problems, run agent + teacher, collect metrics
  - `BatchEvaluator`: generates problems programmatically, evaluates agent vs teacher vs random
  - `ProblemResult` / `BatchResult`: structured results with aggregation (mean KL, beats-random count)
  - `scripts/batch_eval.py`: CLI for batch eval and trajectory export
  - Validated: 5/5 agent beats random, mean KL agent=0.30 vs random=2.04
- 167 tests total, all passing (14 new harness tests)

### 2026-03-07 — Phase 7: LLM Agent solver + E2E pipeline
- **Agent solver implemented**: LLM agent that receives ResearchProblem and solves it
  - `AgentSolver`: agentic loop with observe/submit tools routed through EpisodeRunner
  - `build_agent_system_prompt()`: presents problem narrative, data, actions, question
  - `AgentResult`: captures submitted answer, observations, score, messages
  - Observe tool: validates variable, checks budget, returns observed state
  - Submit tool: validates distribution states, normalizes, scores via VerifierTool
  - Comparison script (`scripts/test_agent.py`): runs agent vs teacher vs random baseline
  - 13 tests: prompt generation, tool dispatch, mocked full loops
- **End-to-end pipeline**: orchestrator → agent in a single script
  - `scripts/test_e2e.py`: orchestrator generates semantic world, agent solves it
  - Full flow: world_gen → world_check → apply_semantics → build_problem → agent → score
  - Agent receives semantic node names (e.g., `coral_bleaching_severity` not `target_outcome`)
  - Step-by-step output for both orchestrator and agent phases
  - Validated: agent KL=0.16 vs teacher KL=0.00 vs random KL=0.89 on marine ecology problem
- 153 tests total, all passing

### 2026-03-07 — Phase 6: Semantic layer
- **Semantic layer implemented**: transforms abstract BN worlds into realistic research problems
  - `ResearchProblem` model: packages title, narrative, data, actions, question, budget
  - `DataSampler`: samples from BN joint distribution, presents as tabular/observations
  - `ProblemBuilder`: builds agent-facing ResearchProblem from enriched World
  - `apply_semantics` tool: LLM renames nodes, adds scenario narrative and domain
  - `build_problem` tool: samples data and packages everything the agent sees
  - `show_research_problem()` display function (terminal + notebook)
  - Node renaming propagates through nodes, edges, CPDs, and state_names
  - Orchestrator workflow: world_gen -> world_check -> apply_semantics -> build_problem
  - Updated test script with pretty output for semantic tools
- 139 tests total, all passing (14 new tests for data_sampler, problem_builder, orchestrator)

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
