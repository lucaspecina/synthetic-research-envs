# SREG — Current State

> Detailed technical description of what the system does TODAY.
> Updated: 2026-03-07

---

## Summary

SREG generates fictional research problems backed by Bayesian networks. The full
pipeline works end-to-end: generate a BN world → validate → add semantic layer →
present as a research problem → LLM agent solves it → score against ground truth.

**208 tests passing. 3 template families. 2 task types. Agent, teacher, and batch evaluation working.**

---

## Architecture (implemented)

```
User goal (text or params)
    |
    v
[LLM Orchestrator] -- calls tools in a loop -->
    |-- WorldGenTool ------> World (DAG + CPDs + metadata)
    |-- WorldCheckTool ----> Validation (acyclicity, entropy, d-separation)
    |-- apply_semantics ---> Semantic names + narrative (LLM generates)
    |-- build_problem -----> ResearchProblem (data, actions, question)
    |
    v
ResearchProblem (what the agent sees)
    |-- Title + narrative context
    |-- Tabular data (sampled from BN)
    |-- Available actions with costs
    |-- Research question + target states
    |
    v
[LLM Agent Solver] -- observe/submit loop -->
    |-- Reads context, data, question (free)
    |-- Requests observations (costs budget)
    |-- Submits probability distribution
    |
    v
[VerifierTool] -- scores against BN truth -->
    |-- KL divergence (agent posterior vs true posterior)
    |-- Information efficiency (agent vs teacher)
    |-- Per-step tracking
    |
    v
Score + comparison vs teacher + comparison vs random
```

---

## Two-layer system

### Formal layer (hidden from agent)

A Bayesian network defines the mathematical truth:
- **Nodes**: latent (hidden), observable, target
- **DAG**: directed acyclic graph of causal relationships
- **CPDs**: conditional probability tables (Dirichlet-based, controlled by `edge_strength`)
- All evaluation is exact computation against this network

### Semantic layer (visible to agent)

Built on top by the LLM orchestrator:
- Node renaming: `target_outcome` → `coral_bleaching_severity`
- Narrative context: research scenario with background
- Data: tabular observations sampled from the BN joint distribution
- Actions: "Request sediment analysis" instead of "observe node X"

---

## Template families (3 implemented)

Each template defines a DAG topology + CPD generator. The CPD formula is generic
(Dirichlet with `edge_strength`), so all templates produce worlds with tunable
signal strength.

| Template | Structure | Reasoning tested | Nodes | Teacher accuracy |
|---|---|---|---|---|
| `latent_preference` | Star: latent → N observables + target | Diagnostic inference (infer cause from symptoms) | 3-20 | ~100% |
| `causal_chain` | Linear: root → stage_1 → ... → target | Propagation (closer nodes more informative) | 3-20 | ~95% |
| `fork_collider` | Fork + collider: latent → branches → collider → target | Explaining away / Berkson's paradox | 5-20 | ~85% |

### fork_collider structure (most complex)

```
    hidden_factor (LATENT)
      ↙          ↘
  branch_1(O)  branch_2(O)  [branch_3(O)]
      ↘          ↙
      collider(O)           ← explaining away
          ↓
     [mediator(O)]          ← if extra nodes
          ↓
     target_outcome(T)
```

With more nodes: up to 3 branches, remaining become mediators between collider and target.

---

## Modules

| Module | Location | What it does |
|--------|----------|-------------|
| **Models** | `src/sreg/models/` | Pydantic data contracts: World, Node, Edge, CPD, Episode, Task, Score, TeacherOutput, ResearchProblem |
| **Templates** | `src/sreg/world/templates/` | 3 templates: latent_preference, causal_chain, fork_collider |
| **World check** | `src/sreg/tools/world_check.py` | Validates: DAG acyclicity, entropy, d-separation, paths to target |
| **Teacher solver** | `src/sreg/solver/exact_bayes.py` | Exact Bayesian inference via pgmpy VariableElimination; posteriors, info gain, optimal actions |
| **Episode gen** | `src/sreg/tools/episode_gen.py` | Creates episodes: budget, available nodes, observation costs |
| **Task gen** | `src/sreg/tools/task_gen.py` | Creates tasks: `infer_target` (posterior) and `next_best_observation` (IG ranking) |
| **Verifier** | `src/sreg/tools/verifier.py` | KL divergence scoring, IG ratio scoring (NBO), information efficiency, per-step tracking. |
| **Episode runner** | `src/sreg/env/` | Step-by-step environment interface (observe → submit) |
| **Semantic tools** | `src/sreg/tools/problem_builder.py` | `apply_semantics` (LLM renames nodes), `build_problem` (packages ResearchProblem) |
| **Data sampler** | `src/sreg/tools/data_sampler.py` | Samples from BN joint distribution, presents as tabular observations |
| **Orchestrator** | `src/sreg/orchestrator/` | LLM agentic loop: calls tools via function calling (Azure AI Foundry) |
| **Agent solver** | `src/sreg/agent/` | LLM agent that receives ResearchProblem, observes, submits answer |
| **Batch eval** | `src/sreg/harness/eval.py` | Generates N problems programmatically, runs agent + teacher, collects metrics |
| **Trajectory export** | `src/sreg/harness/trajectory.py` | Teacher trajectory as JSONL (step, action, observation, IG, posterior) |
| **Display** | `src/sreg/display.py` | Dual-mode pretty printing (terminal ANSI + notebook HTML) |

---

## Scripts & notebooks

| Script | What it does |
|--------|-------------|
| `scripts/demo.py` | Terminal demo: world gen → teacher solving (with display) |
| `scripts/test_orchestrator.py` | Step-by-step orchestrator run with real LLM |
| `scripts/test_agent.py` | Agent vs teacher vs random baseline comparison |
| `scripts/test_e2e.py` | End-to-end: orchestrator → semantic → agent → score |
| `scripts/batch_eval.py` | Batch eval + teacher trajectory JSONL export (`--template`, `--problems`, `--nodes`) |
| `notebooks/01_explore_system.ipynb` | Interactive exploration notebook |

---

## Key APIs

### WorldGenTool
```python
config = WorldGenConfig(template_family="fork_collider", seed=42, num_nodes=7, edge_strength=0.7)
world = WorldGenTool().generate(config)  # → World
```

### ExactBayesSolver
```python
solver = ExactBayesSolver(world)
state = solver.sample_state(seed=42)                      # → dict[str, str]
post = solver.posterior("target_outcome", evidence)        # → dict[str, float]
ig = solver.information_gain("target", evidence, node)     # → float
out = solver.optimal_action("target", evidence, nodes)     # → TeacherOutput
# out.recommended_action.node → str, out.information_gain → float
```

### ProblemBuilder
```python
problem = ProblemBuilder().build(world, budget=4)  # → ResearchProblem
# problem.target_node, problem.target_states, problem.budget
# problem.available_actions → list[AvailableAction] (each has .node, .description, .cost)
# problem.data_assets → list[DataAsset]
```

### EpisodeGenTool
```python
episode = EpisodeGenTool().generate(world, EpisodeGenConfig(budget=4))  # → Episode
# episode.budget, episode.available_nodes, episode.node_costs
```

### TaskGenTool (next_best_observation)
```python
spec = TaskSpec(type=TaskType.NEXT_BEST_OBSERVATION, target_node="target_outcome", max_budget=5)
task = TaskGenTool().generate(world, spec, seed=42)  # → Task
# task.given_evidence → {"branch_1": "low", "collider": "high"}  (what agent already knows)
# task.correct_answer → {"branch_2": 0.42, "mediator_1": 0.15}   (IG ranking)
# task.available_evidence → ["branch_2", "mediator_1"]            (remaining choices)
```

### VerifierTool
```python
score = VerifierTool().score(agent_posterior, true_posterior)  # → Score
# score.functional_score (KL divergence), score.information_efficiency

ratio = VerifierTool().score_nbo("branch_2", ig_ranking)  # → float (0.0 to 1.0)
# 1.0 = chose the optimal node, 0.0 = chose a useless node
```

---

## Test coverage

- **208 tests** across all modules
- Tests mirror src structure: `src/sreg/tools/X.py` → `tests/tools/test_X.py`
- Key validations:
  - 100 worlds validated per template (all pass)
  - Teacher >90% accuracy on latent_preference, >70% on chain, >60% on fork_collider
  - Closer nodes more informative than distant ones (causal_chain)
  - Fork/collider structure verified: fork topology, collider parents, mediator chain

---

## Known issues (from E2E testing)

- Agent submit format: LLM sends flat keys instead of `{"distribution": {...}}`, wastes 1 turn
- Agent worse than random on 8-node worlds (bad inference with more variables)
- Orchestrator ignores difficulty goal (always generates "easy")
- `apply_semantics` always fails first call (empty `node_renames`, then retries)
- Agent variable selection suboptimal (different order than teacher)

---

## Dependencies

- Python 3.11, pgmpy (DiscreteBayesianNetwork), networkx, numpy/scipy, pydantic v2
- openai SDK (Azure AI Foundry, not AzureOpenAI), python-dotenv
- Dev: pytest, ruff
- LLM: configurable via AZURE_MODEL env var
