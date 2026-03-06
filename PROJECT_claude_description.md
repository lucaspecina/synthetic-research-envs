# WorldForge — Synthetic Research Environment
### Project Specification v1
> Document prepared for collaborative review and implementation planning.
> Reflects design decisions from iterative discussion between two AI systems and Lucas Pecina.

---

## What is WorldForge

WorldForge is a **synthetic research environment generator** — a system that creates fictional but causally coherent worlds, produces evidence from those worlds, formulates verifiable research tasks, and evaluates agents that interact with them.

The goal is not to simulate real science. The goal is to generate training environments where LLM agents can develop genuine reasoning skills: updating beliefs as evidence accumulates, knowing what information to request next, reasoning causally under uncertainty, and committing to conclusions with appropriate confidence.

The worlds are fictional by design. A world about "resonance fields driving crystal growth in a fictional planet" is better than a world about real chemistry — because it prevents the agent from solving tasks through memorized facts rather than actual reasoning. If a model trained on fictional WorldForge environments transfers to real scientific tasks, that's proof it learned the reasoning skill, not the content.

**WorldForge is not the agent. It's the gym.**

---

## Why this architecture exists

Standard LLM training either targets tasks with unambiguous correct answers (math, code) or relies on LLM judges for quality assessment. Scientific reasoning fits neither category — it's sequential, probabilistic, and correctness is rarely obvious.

WorldForge solves this by generating tasks where:
- Ground truth is mathematically defined (a DAG + probability distributions)
- Scoring is automatic and doesn't require human or LLM judgment
- The same world can produce many different tasks
- Agents are evaluated on reasoning quality, not fact recall

The key design philosophy: **the LLM orchestrates creation, but programmatic tools own the truth.**

---

## The agents that will use WorldForge

Important context that shapes every design decision: the agents interacting with WorldForge environments are always LLMs. This means:

- They communicate in natural language and structured JSON
- They understand semantic context — `"enzyme_inhibitor"` means something to them even if the world is fictional
- They can read descriptions, interpret partial evidence, and reason about uncertainty
- In future stages they may use tools: web search, code execution, calculators
- They express beliefs as probability distributions or natural language confidence

This justifies giving worlds semantic names even in v0. An LLM agent reasons better about `"thermal_flux causes biofilm_activation"` than about `"node_3 causes node_7"`. The underlying math is identical; the reasoning quality is not.

---

## Core architecture: five layers

Every component maps to one of five layers. The most important rule: **LLMs only appear in Layers 1 (as orchestrator) and 4 (as agent). Layers 2, 3, and 5 are always programmatic.**

```
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 1 — World Model                                           │
│  Hidden ground truth: DAG, variables, parameters, mechanisms.    │
│  CREATED by: LLM Orchestrator calling programmatic tools.        │
│  OWNED by: programmatic backend. LLM never modifies truth.       │
├──────────────────────────────────────────────────────────────────┤
│  LAYER 2 — Artifact Generator                                    │
│  Produces observable evidence: datasets, partial observations,   │
│  (later) synthetic documents derived from the world.             │
│  Always programmatic.                                            │
├──────────────────────────────────────────────────────────────────┤
│  LAYER 3 — Task Generator                                        │
│  Formulates verifiable questions grounded in the world.          │
│  Always programmatic. LLM can enrich phrasing, not content.      │
├──────────────────────────────────────────────────────────────────┤
│  LAYER 4 — Environment Interface                                 │
│  How the LLM agent interacts: actions, observations, budget.     │
│  Agent is always an LLM.                                         │
├──────────────────────────────────────────────────────────────────┤
│  LAYER 5 — Verifier / Scorer                                     │
│  Computes reward from ground truth. Always programmatic.         │
│  Never uses an LLM judge.                                        │
└──────────────────────────────────────────────────────────────────┘
```

---

## The central design decision: LLM as orchestrator of programmatic tools

This is the most important architectural choice and it was explicitly decided.

WorldForge does **not** use a purely hardcoded programmatic generator. It also does **not** let an LLM freely write world definitions. Instead:

> **The LLM designs. The tools build and verify.**

From v0, the system uses an **LLM Orchestrator** that calls a set of programmatic tools in a loop. The LLM proposes, inspects, and refines. The tools construct, validate, and simulate. Ground truth is always owned by the tools.

This architecture is superior to pure code generation for two reasons:
1. **Diversity**: hardcoded templates produce structurally repetitive worlds. The LLM generates causally novel structures and semantically rich names that make training data more varied and more transferable to real scientific tasks.
2. **Quality control via semantic judgment**: a world can pass programmatic validation (valid DAG, correct node counts) but still be trivially easy to solve. Only the LLM can detect that and request regeneration.

---

## The LLM Orchestrator loop

The orchestrator runs an agentic loop using function calling (Anthropic API tool use). It has access to five tools:

### The five tools

**`WorldGenTool`**
Receives a structured world spec and generates a valid world.
- Input: template family, node count, latent/observable ratio, sparsity, difficulty level, semantic domain
- Output: world object with DAG, CPTs, node metadata, seed
- Internally uses `pgmpy` for BN construction and exact parametrization

**`WorldCheckTool`**
Evaluates whether a generated world meets quality criteria.
- Input: world object, desired difficulty profile
- Output: quality report — is it too easy? too sparse? does it have the expected causal structure? is inference non-trivial?
- Programmatic checks: min path length, min number of latent nodes, posterior entropy above threshold, at least one non-trivial d-separation
- Returns pass/fail + specific failure reasons

**`EpisodeGenTool`**
Generates episodes and evidence from a world.
- Input: world object, episode count, observation budget, noise level
- Output: list of episodes, each with initial evidence, available nodes, costs, and step-by-step observation sequences

**`TaskGenTool`**
Generates verifiable tasks from a world and its episodes.
- Input: world object, task type(s), difficulty
- Output: task objects with question, available evidence, correct answer (hidden), scoring function

**`VerifierTool`**
Computes correct answers and scores for completed episodes.
- Input: world object, agent trajectory, task spec
- Output: functional score, structural score (if applicable), per-step belief accuracy

---

### The orchestrator loop in practice

```
Orchestrator receives: "Generate a world of medium difficulty,
with real uncertainty, domain: energy crystallography"

  Step 1 → calls WorldGenTool({
      template: "fork_with_mediation",
      nodes: 7,
      latent_ratio: 0.4,
      domain: "energy crystallography",
      difficulty: "medium"
  })
  → receives world_v1

  Step 2 → calls WorldCheckTool(world_v1)
  → receives: {"pass": false, "reason": "posterior entropy too low, target trivially inferable"}

  Step 3 → calls WorldGenTool({
      ...same params...,
      latent_ratio: 0.5,        ← adjusted based on failure reason
      edge_strength: "weaker"
  })
  → receives world_v2

  Step 4 → calls WorldCheckTool(world_v2)
  → receives: {"pass": true, "entropy": 1.8, "difficulty": "medium"}

  Step 5 → calls EpisodeGenTool(world_v2, count=50)
  → receives 50 episodes

  Step 6 → calls TaskGenTool(world_v2, tasks=["infer_target", "next_best_observation"])
  → receives task batch

  Step 7 → Orchestrator evaluates semantic quality:
  "These tasks look reasonable. World description is coherent.
   Crystal growth target is non-trivially caused by resonance_field
   and growth_inhibitor. Proceeding."

  → World registered. Episodes and tasks stored.
```

The loop converges in 1–3 iterations in practice. The LLM's semantic judgment in Step 7 is the check that no programmatic validator can replace.

---

## Layer 1 — World Model in detail

A world is a **causal probabilistic structure** fully defined by:

```python
World:
  id: str                          # unique, deterministic from seed
  seed: int
  template_family: str
  nodes: List[Node]
  edges: List[Edge]                # defines DAG structure
  cpds: Dict[str, CPD]             # conditional probability distributions
  world_description: str           # LLM-generated, metadata only
  difficulty_profile: DifficultyProfile
```

```python
Node:
  name: str                        # semantic, e.g. "thermal_flux"
  type: Literal["observable", "latent", "target"]
  description: str                 # LLM-generated description
  states: List[str]                # e.g. ["low", "medium", "high"]
```

```python
Edge:
  from_node: str
  to_node: str
  mechanism: str                   # LLM-generated description of causal link
```

The LLM provides `name`, `description`, `mechanism`, and `states` in natural language. The programmatic backend assigns all CPDs — the actual probability values. The LLM never touches the numbers.

### Template families (v0)

**Latent preference** — one hidden variable drives multiple observables. The agent must infer the latent from observable effects. Analogous to the Nature paper's flight task but generalized.

**Causal chain** — A → B → C → target with noise at each step. Tests whether the agent tracks evidence propagation across multiple hops.

**Fork with collider** — a latent common cause produces two observables; a collider downstream creates a dependency trap. Tests understanding of d-separation and Berkson's bias.

---

## Layer 2 — Artifact Generator in detail (v0)

v0 produces two artifact types only. Documents come in v1.

**Tabular dataset**: N rows sampled from the world's joint distribution with latent nodes hidden. Gives the agent population-level statistical signal.

**Sequential partial observations**: individual node values revealed one at a time, each with a cost. This is the primary interaction mode — the agent decides what to observe next within a budget.

Both are generated by sampling from the `pgmpy` Bayesian network. Fully deterministic from seed.

---

## Layer 3 — Task Generator in detail (v0)

Two task types in v0:

**`infer_target`**
Given accumulated evidence, estimate the probability distribution over the target variable.
- Correct answer: exact posterior P(target | evidence) computed by Bayesian inference
- Score: KL divergence between agent's answer and true posterior (lower = better)

**`next_best_observation`**
Given current evidence and remaining budget, which node should be observed next?
- Correct answer: node that maximizes expected information gain (entropy reduction on target)
- Score: information gain achieved vs maximum possible information gain

Both tasks have computable correct answers. No LLM judge involved.

---

## Layer 4 — Environment Interface in detail

The agent (always an LLM) interacts via JSON actions over a step loop.

**Actions available in v0:**

```json
{"action": "observe", "node": "thermal_flux"}

{"action": "query_distribution", "node": "crystal_growth"}

{"action": "submit", "answer": {"low": 0.1, "medium": 0.3, "high": 0.6}, "confidence": 0.7}
```

**What the agent sees at each step:**
- World description (LLM-generated narrative)
- Task description in natural language
- Evidence accumulated so far (natural language + structured)
- Remaining budget
- Available nodes with costs

**Key principle**: observations are returned in natural language, not raw numbers.
`"thermal_flux was observed to be HIGH (value: 0.84)"` — not `0.84`.
This respects that agents are LLMs and reason better with semantic context.

---

## Layer 5 — Verifier / Scorer in detail

Two score types, different weights:

**Functional score (primary, higher weight)**
Does the agent's reasoning produce correct predictions?
- KL divergence between agent posterior and true posterior
- Accuracy on held-out observations given agent's proposed beliefs
- Information efficiency: how much budget did the agent need to reach a given accuracy?

**Structural score (secondary, lower weight)**
How close is the agent's proposed causal structure to the true graph?
- F1 over edges
- Structural Hamming Distance
- **Markov-equivalent graphs score as correct** — two different DAGs that produce the same conditional independencies are both valid answers

The functional score is primary because we are training reasoning skill, not graph memorization. An agent that builds a slightly different but functionally equivalent world model is doing exactly what we want.

---

## What the Teacher Solver produces

The teacher is an exact Bayesian engine — not an LLM — that runs through each episode optimally:

- Maintains the exact posterior distribution over all world states
- At each step, selects the observation that maximizes expected information gain
- Produces the optimal action sequence for the full episode

Teacher trajectories become **SFT training data**: `(history, optimal_action, posterior_state)` triples. The LLM agent learns to imitate not just the actions but the full uncertainty trajectory — exactly the key finding of the Nature paper (Qiu et al. 2026).

The critical training signal is that the teacher is *not always right* early in the episode (because it genuinely doesn't have enough information yet) but *consistently improves* as evidence accumulates. An LLM fine-tuned on this signal learns to keep updating beliefs rather than plateauing after the first observation.

---

## v0 — Concrete scope

### In scope

- LLM Orchestrator with five tools (WorldGenTool, WorldCheckTool, EpisodeGenTool, TaskGenTool, VerifierTool)
- Three template families: latent preference, causal chain, fork/collider
- Two task types: `infer_target`, `next_best_observation`
- Artifact types: tabular datasets + sequential partial observations
- Exact Bayesian teacher solver
- Functional score (KL divergence) as primary metric
- Semantic node names and world descriptions from LLM
- All episodes seeded and reproducible
- SFT dataset export from teacher trajectories
- Basic LLM agent eval (baseline, no fine-tuning)

### Explicitly excluded from v0

- Synthetic document artifacts (v1)
- Intervention / do-calculus tasks (v1)
- Structure recovery tasks — edge proposal (v1)
- RL training loop (v1 — SFT only in v0)
- Real scientific domains (v2)
- Web search or external tools for agents (v2)
- Approximate inference teacher for large worlds (v1)

---

## Build order — implementation phases

Build in this order. Each phase produces something independently testable before moving to the next.

**Phase 1 — Contracts and data structures**
Define all dataclasses and schemas before any logic. Nothing else starts until these are stable.
- `World`, `Node`, `Edge`, `CPD`
- `Episode`, `Action`, `StepResult`
- `Task`, `TaskSpec`
- `TeacherOutput` (posterior, recommended action, info gain)
- `Score` (functional, structural, per-step)
- JSON schemas for all tool inputs/outputs

**Phase 2 — WorldGenTool + WorldCheckTool**
Implement world generation for one template (latent preference).
Validate: 100 generated worlds, all valid DAGs, distributions look correct, difficulty varies with parameters.

**Phase 3 — Teacher Solver**
Exact Bayesian inference using pgmpy `VariableElimination`.
Validate: teacher reaches >90% accuracy on `infer_target` after full episode.

**Phase 4 — EpisodeGenTool + TaskGenTool + VerifierTool**
`infer_target` task end-to-end. Run teacher as agent. Validate scoring.

**Phase 5 — LLM Orchestrator loop**
Wire the five tools to an LLM via Anthropic function calling.
Validate: orchestrator generates a world, rejects trivial ones, converges in ≤3 iterations.

**Phase 6 — Second and third templates + second task**
Add causal chain and fork/collider templates.
Add `next_best_observation` task.
Validate: same world produces both task types.

**Phase 7 — SFT dataset generation + baseline LLM eval**
Generate teacher trajectories, format as SFT examples.
Run baseline LLM (no fine-tuning) through episodes.
Measure: does the baseline plateau after observation 1? (It should.)

---

## v0 success criteria

v0 is complete when all of these pass:

| Criterion | What it proves |
|---|---|
| Generate 10,000+ reproducible episodes across 3 template families | World generator is stable and diverse |
| Teacher reaches >90% on `infer_target` after full episode | World quality is sufficient for meaningful inference |
| LLM Orchestrator converges in ≤3 iterations per world | Orchestrator loop works |
| Same world produces both task types without regeneration | Layer 3 architecture is correct |
| Baseline LLM shows plateau effect (no improvement after obs 1) | Environment captures the target failure mode |
| SFT dataset exported and formatted correctly | Training pipeline is ready |
| All components pass unit tests independently | Architecture is modular and correct |

The most important implicit criterion: after fine-tuning on teacher SFT data, an LLM should show **improvement over steps** rather than plateau. That's the proof that WorldForge trains something real.

---

## Roadmap beyond v0

**v1 — Richer worlds and interactions**
- Synthetic document artifacts (short texts generated from world parameters via templates, not free LLM generation)
- Intervention tasks: `do(X=v)` and predict effect on target
- Structure recovery tasks: agent proposes edges
- Approximate inference teacher for larger worlds (10–20 nodes)
- More template families: mediation, mini-science/rule discovery

**v2 — Semantic richness and domain transfer**
- LLM-generated documents with controllable noise and incompleteness
- Multi-step research tasks: read docs + query data + propose hypothesis + test it
- Evaluation of transfer: train on template family A, test on family B
- Curriculum over world complexity

**v3 — Agent training at scale**
- RL loop with verifier as reward signal (RLVR)
- Web search tool available to agents for semantic grounding
- Full curriculum from simple to complex worlds
- Evaluation on held-out world families and eventually real scientific benchmarks

---

## Resolved design decisions

These were explicitly discussed and decided. Don't reopen without strong reason.

| Decision | Resolution | Reason |
|---|---|---|
| LLM as source of world truth | Never | Breaks verifiability |
| LLM role in generation | Orchestrator calling tools | Diversity + semantic quality without losing control |
| LLM semantic check | Yes, part of orchestrator loop | Programmatic validators can't detect "trivially easy" |
| Score type | Functional primary, structural secondary | Equivalent graphs should both score well |
| Documents in v0 | Excluded | Adds complexity before foundation is solid |
| Node naming | Always semantic (even if fictional) | LLMs reason better with semantic context |
| Agent output format | JSON | Parseable, testable, RL-compatible |
| Teacher type in v0 | Exact Bayesian inference | Small worlds allow it; cleanest training signal |
| DAG generation | LLM proposes structure, code validates | Balance of diversity and correctness |
| Markov equivalent graphs | Score as correct | Testing reasoning, not graph memorization |
| Interventions in v0 | Excluded | V1 feature |
| RL in v0 | Excluded | SFT first, RL after interface is stable |

---

## Tech stack

- **Python 3.11+**
- **pgmpy** — Bayesian network construction, CPD specification, exact inference (`VariableElimination`)
- **networkx** — DAG validation and manipulation
- **numpy / scipy** — parameter sampling, distribution operations
- **pydantic** — data contracts for all dataclasses and tool schemas
- **anthropic Python SDK** — LLM Orchestrator via tool use / function calling
- **pytest** — unit tests from day one

Note: avoid `bnlearn` in v0 (R dependency makes CI painful). `pgmpy` covers everything needed for discrete worlds.

---

## Repository structure

```
worldforge/
├── src/
│   ├── orchestrator/
│   │   ├── orchestrator.py         # LLM Orchestrator — main agentic loop
│   │   └── prompts.py              # System prompts for orchestrator
│   ├── tools/
│   │   ├── world_gen.py            # WorldGenTool
│   │   ├── world_check.py          # WorldCheckTool
│   │   ├── episode_gen.py          # EpisodeGenTool
│   │   ├── task_gen.py             # TaskGenTool
│   │   └── verifier.py             # VerifierTool
│   ├── world/
│   │   ├── world.py                # World, Node, Edge dataclasses
│   │   ├── templates/
│   │   │   ├── latent_preference.py
│   │   │   ├── causal_chain.py
│   │   │   └── fork_collider.py
│   │   └── parameterizer.py        # Assigns CPDs to LLM-proposed structure
│   ├── solver/
│   │   └── exact_bayes.py          # Teacher: exact inference + info gain
│   ├── env/
│   │   ├── interface.py            # Episode step loop
│   │   ├── actions.py              # Action schemas
│   │   └── episode.py              # Episode dataclass + history
│   ├── scoring/
│   │   ├── functional.py           # KL divergence, prediction accuracy
│   │   └── structural.py           # SHD, edge F1
│   └── harness/
│       ├── generate_dataset.py     # SFT dataset from teacher trajectories
│       └── evaluate_agent.py       # Run LLM agent, collect metrics
├── configs/
│   ├── orchestrator.yaml
│   └── difficulty_profiles.yaml
├── tests/
│   ├── test_world_gen.py
│   ├── test_teacher.py
│   ├── test_verifier.py
│   └── test_orchestrator.py
├── notebooks/
│   └── explore_worlds.ipynb
└── docs/
    ├── project_spec.md             # This document
    ├── tool_contracts.md           # Exact schemas for all 5 tools
    └── api_reference.md
```

---

## What WorldForge is not

To prevent scope creep:

- **Not a benchmark of real scientific knowledge.** Worlds are synthetic. Prior knowledge of real science should be neither necessary nor sufficient.
- **Not a free-form research agent.** Tasks are closed and verifiable in v0–v1.
- **Not a causal discovery research contribution.** It evaluates agents; it doesn't claim to solve causal discovery.
- **Not dependent on LLM correctness for ground truth.** LLM failure in orchestration means regeneration, not corrupted ground truth.
- **Not a simulator of physical reality.** Worlds are probabilistic causal structures, not physics engines.

---

*WorldForge — Project Specification v1*
*Prepared for collaborative review. Based on iterative design discussion.*
*Key reference: Qiu et al., "Bayesian teaching enables probabilistic reasoning in large language models", Nature Communications 2026.*
