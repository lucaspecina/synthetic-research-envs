# SREG — Implementation Plan

> Detailed phase-by-phase plan for building v0.
> Update the status of each phase as work progresses.

## Overview

v0 delivers a working end-to-end system: generate worlds, generate tasks, run agents, score results.
Each phase produces something independently testable before moving to the next.

| Phase | Name | Status | Depends on |
|---|---|---|---|
| 1 | Contracts and data structures | **Done** | — |
| 2 | World generation + validation | Pending | Phase 1 |
| 3 | Teacher solver | Pending | Phase 1, 2 |
| 4 | Episodes, tasks, verifier | Pending | Phase 1, 2, 3 |
| 5 | LLM Orchestrator | Pending | Phase 2, 4 |
| 6 | More templates + more tasks | Pending | Phase 2, 4 |
| 7 | Dataset generation + baseline eval | Pending | Phase 3, 4, 5 |

---

## Phase 1 — Contracts and data structures

**Goal**: Define every data type before writing any logic. Nothing else starts until these are stable.

**What to build**:

```
src/sreg/models/
├── __init__.py
├── world.py          # World, Node, Edge, CPD
├── episode.py        # Episode, Action, StepResult
├── task.py           # Task, TaskSpec, TaskType
├── teacher.py        # TeacherOutput (posterior, action, info_gain)
└── score.py          # Score (functional, structural, per_step)
```

**Data models**:

- `Node`: name (semantic), type (observable/latent/target), description, states list
- `Edge`: from_node, to_node, mechanism description
- `CPD`: node name, parents list, probability table (numpy array), state names
- `World`: id, seed, template_family, nodes, edges, cpds, description, difficulty_profile
- `Episode`: world_id, steps list, budget, initial_evidence
- `Action`: type (observe/submit/query), parameters
- `StepResult`: action taken, observation returned, remaining budget
- `Task`: id, type, world_id, question, available_evidence, correct_answer (hidden), scoring_fn
- `TeacherOutput`: posterior distribution, recommended action, information gain
- `Score`: functional_score (KL div), structural_score (SHD/F1), per_step_scores

**Also in this phase**:
- `pyproject.toml` with all dependencies
- `pytest` skeleton with one smoke test
- `ruff` config

**Done when**: All models pass validation tests, can serialize to/from JSON, and cover all interfaces between layers.

---

## Phase 2 — World generation + validation

**Goal**: Generate valid, interesting Bayesian network worlds from one template family.

**What to build**:

```
src/sreg/world/
├── __init__.py
├── templates/
│   └── latent_preference.py    # First template
└── parameterizer.py            # Assigns CPDs to LLM-proposed structures

src/sreg/tools/
├── __init__.py
├── world_gen.py                # WorldGenTool
└── world_check.py              # WorldCheckTool
```

**WorldGenTool** receives:
- template family, node count, latent/observable ratio, sparsity, difficulty, semantic domain
- Returns: World object with DAG, CPDs, node metadata, seed

**WorldCheckTool** validates:
- DAG is valid (acyclic)
- Min path length between observables and target
- Min number of latent nodes
- Posterior entropy above threshold (not trivially solvable)
- At least one non-trivial d-separation
- Returns: pass/fail + specific failure reasons

**Implementation details**:
- Use `pgmpy` for BN construction and CPD specification
- Use `networkx` for DAG validation
- All worlds deterministic from seed

**Template: Latent Preference**:
- One hidden variable drives multiple observables
- Agent must infer the latent from observable effects
- 5-8 nodes, 1-2 latent, 1 target, rest observable

**Done when**: Generate 100 worlds, all valid DAGs, difficulty varies controllably with parameters.

---

## Phase 3 — Teacher solver

**Goal**: An exact Bayesian engine that plays each episode optimally.

**What to build**:

```
src/sreg/solver/
├── __init__.py
└── exact_bayes.py    # Exact inference + info gain calculation
```

**What the teacher does**:
1. Maintains exact posterior P(all variables | evidence so far)
2. At each step, computes expected information gain for every observable node
3. Selects the node that maximizes entropy reduction on the target
4. Produces the full optimal trajectory: (state, action, result) triples

**Implementation**: pgmpy `VariableElimination` for posterior computation.

**Why this matters**:
- Validates that worlds are solvable (teacher should reach >90%)
- Provides the "perfect score" baseline
- Generates optimal trajectories that can be exported as training data

**Done when**: Teacher reaches >90% accuracy on `infer_target` after full episode across 50+ worlds.

---

## Phase 4 — Episodes, tasks, verifier

**Goal**: Connect everything end-to-end. Generate episodes, formulate tasks, score agent performance.

**What to build**:

```
src/sreg/tools/
├── episode_gen.py    # EpisodeGenTool
├── task_gen.py       # TaskGenTool
└── verifier.py       # VerifierTool

src/sreg/env/
├── __init__.py
├── interface.py      # Episode step loop
├── actions.py        # Action schemas
└── episode.py        # Episode runner
```

**EpisodeGenTool**: generates episodes from a world — initial evidence, available nodes, costs, budget.

**TaskGenTool**: formulates tasks from a world.
- `infer_target`: estimate P(target | evidence). Scored by KL divergence.
- (next_best_observation added in Phase 6)

**VerifierTool**: computes scores.
- Functional score (primary): KL divergence between agent posterior and true posterior
- Information efficiency: budget used vs accuracy achieved

**Environment interface**:
- Agent sends JSON actions: `observe`, `query_distribution`, `submit`
- Environment returns: observation in natural language + structured data, remaining budget
- Observations use semantic names: "thermal_flux was observed to be HIGH (value: 0.84)"

**Done when**: Full episode works end-to-end with teacher as agent. Scores are correct and consistent.

---

## Phase 5 — LLM Orchestrator

**Goal**: An LLM (via Azure Foundry) orchestrates world generation by calling tools in a loop.

**What to build**:

```
src/sreg/orchestrator/
├── __init__.py
├── orchestrator.py   # Main agentic loop
└── prompts.py        # System prompts
```

**How it works**:
1. Orchestrator receives a high-level goal ("generate a medium-difficulty world about X")
2. Calls WorldGenTool with proposed parameters
3. Calls WorldCheckTool to validate
4. If validation fails, adjusts parameters and regenerates
5. Once valid, calls EpisodeGenTool and TaskGenTool
6. LLM does a final semantic quality check (coherent names, non-trivial structure)
7. World registered and stored

**LLM integration**:
- Azure Foundry via `openai` SDK (v1 API, `OpenAI` not `AzureOpenAI`)
- Tool use / function calling for the 5 tools
- Converges in 1-3 iterations typically

**Done when**: Orchestrator generates a world, rejects a trivial one, converges in <=3 iterations.

---

## Phase 6 — More templates + more tasks

**Goal**: Add diversity — two more template families and one more task type.

**Templates to add**:

**Causal chain**: A -> B -> C -> target with noise at each step.
Tests whether the agent tracks evidence propagation across multiple hops.

**Fork with collider**: A latent common cause produces two observables; a collider downstream creates a dependency trap.
Tests understanding of d-separation and Berkson's bias.

**Task to add**:

**`next_best_observation`**: Given current evidence and remaining budget, which node should be observed next?
- Correct answer: node that maximizes expected information gain
- Score: achieved info gain vs maximum possible info gain

**Done when**: Same world can produce both task types. All 3 templates generate valid, diverse worlds.

---

## Phase 7 — Dataset generation + baseline evaluation

**Goal**: Produce output datasets and measure baseline LLM performance.

**What to build**:

```
src/sreg/harness/
├── __init__.py
├── generate_dataset.py   # Teacher trajectories → exportable dataset
└── evaluate_agent.py     # Run LLM agent through episodes, collect metrics
```

**Teacher trajectory dataset**:
- For each episode: sequence of (history, optimal_action, posterior_state) triples
- Export as JSON/JSONL
- This is a valuable product — usable for future SFT by anyone

**Baseline evaluation**:
- Run a baseline LLM (no fine-tuning) through episodes
- Measure: accuracy, information efficiency, calibration
- Expected result: baseline plateaus after first observation (doesn't improve with more evidence)
- This confirms the environment captures the reasoning failure we want to train against

**Done when**: Dataset exported correctly. Baseline LLM shows expected plateau behavior.

---

## v0 success criteria

| Criterion | What it proves |
|---|---|
| Generate 1,000+ reproducible episodes across 3 templates | Generator is stable and diverse |
| Teacher reaches >90% on infer_target after full episode | World quality is sufficient |
| LLM Orchestrator converges in <=3 iterations | Orchestrator loop works |
| Same world produces both task types | Layer 3 architecture is correct |
| Baseline LLM shows plateau effect | Environment captures the target failure mode |
| Teacher trajectories exported as dataset | Output pipeline works |
| All components pass unit tests independently | Architecture is modular and correct |

---

## What comes after v0

See `PROJECT.md` sections on v1, v2, v3 for the full roadmap.
