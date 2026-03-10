# SREG — Changelog

> All notable changes to this project are documented here.
> Format: date, description, phase reference.

## [Unreleased]

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
