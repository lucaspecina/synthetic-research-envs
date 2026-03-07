# SREG — Implementation Plan

> Detailed phase-by-phase plan for building v0.
> Update the status of each phase as work progresses.

## Overview

v0 delivers: realistic-looking research problems backed by formal Bayesian networks,
a teacher solver, and an LLM agent solver that attempts to solve them.

Each phase produces something independently testable before moving to the next.

| Phase | Name | Status | Depends on |
|---|---|---|---|
| 1 | Contracts and data structures | **Done** | — |
| 2 | World generation + validation | **Done** | Phase 1 |
| 3 | Teacher solver | **Done** | Phase 1, 2 |
| 4 | Episodes, tasks, verifier | **Done** | Phase 1, 2, 3 |
| 5 | LLM Orchestrator | **Done** | Phase 2, 4 |
| 6 | Semantic layer | Pending | Phase 5 |
| 7 | LLM Agent solver | Pending | Phase 6 |
| 8 | More templates + more tasks | Pending | Phase 6, 7 |
| 9 | Dataset generation + eval harness | Pending | Phase 7, 8 |

---

## Phase 1 — Contracts and data structures — DONE

**Goal**: Define every data type before writing any logic.

All Pydantic models defined and tested: World, Node, Edge, CPD, Episode, Action,
StepResult, Task, TaskSpec, TeacherOutput, Score. JSON serialization roundtrips working.

---

## Phase 2 — World generation + validation — DONE

**Goal**: Generate valid Bayesian network worlds from one template family.

Latent preference template implemented. WorldGenTool and WorldCheckTool working.
100 worlds generated and validated, difficulty varies with parameters.

---

## Phase 3 — Teacher solver — DONE

**Goal**: Exact Bayesian engine that plays each episode optimally.

ExactBayesSolver implemented with pgmpy VariableElimination. Teacher reaches >90%
accuracy across 50 worlds (250 episodes).

---

## Phase 4 — Episodes, tasks, verifier — DONE

**Goal**: Connect everything end-to-end.

EpisodeGenTool, TaskGenTool (infer_target), VerifierTool, and EpisodeRunner all working.
Full episodes run end-to-end with teacher as agent.

---

## Phase 5 — LLM Orchestrator — DONE

**Goal**: LLM drives world generation via tool calling.

Orchestrator loop working with gpt-5.2-chat via Azure Foundry. Proposes worlds,
validates, adjusts on failure, generates episodes and tasks. Converges in 1-5 iterations.

---

## Phase 6 — Semantic layer

**Goal**: Transform abstract worlds into realistic research problems.

This is where the system goes from "estimate P(target_outcome)" to
"determine the main cause of algae production decline in Nelvara."

### What to build

**6.1 — Semantic world model extensions**

Extend the World model to include semantic metadata:
- `scenario_title`: name of the research problem
- `scenario_description`: narrative context (2-3 paragraphs)
- `domain`: scientific domain (ecology, epidemiology, materials, etc.)
- Node names become semantic: `water_temperature` not `indicator_1`
- Node descriptions explain what each variable represents in the scenario
- Edge mechanisms describe causal relationships in plain language
- Action descriptions: what each observation means in context
  ("solicitar análisis de sedimentos" not "observe node_3")

**6.2 — Data presentation**

Generate evidence from the Bayesian network in realistic formats:
- **Tabular dataset**: N rows sampled from the joint distribution, with named
  columns, presented as a DataFrame/CSV the agent can analyze
- **Isolated observations**: individual datapoints ("in station 3, temperature
  was measured at 24.3°C on March 5")
- **Experimental results**: structured outputs ("the controlled experiment
  showed growth rate of 0.7 under condition X")
- Configurable per world: which format(s) to use

The underlying data always comes from sampling the Bayesian network.
The presentation format is the semantic layer.

**6.3 — Orchestrator semantic generation**

Expand the orchestrator prompt so the LLM also generates:
- Scenario title and description
- Semantic names for all nodes
- Descriptions for all edges (causal mechanisms in context)
- Action descriptions with costs
- The research question in natural language

The orchestrator still calls the same programmatic tools for the formal layer.
The semantic content is LLM-generated metadata that doesn't affect the math.

**6.4 — Research problem packaging**

A `ResearchProblem` model that bundles everything the agent sees:
- Problem title and description
- Available data (in chosen format)
- Available actions with costs and descriptions
- Budget constraint
- Research question(s)
- Any initial evidence or context

### What NOT to build yet

- Synthetic documents (papers, reports) — that's v1/v2
- Automatic paper search for seeds — that's v1
- Complex action types — just observe with semantic names

### Done when

- Same Bayesian network produces a research problem with narrative, names, and data
- Orchestrator generates semantic layer via LLM
- Agent-facing output looks like a realistic (if simple) research brief
- All existing tests still pass

---

## Phase 7 — LLM Agent solver

**Goal**: An LLM agent that receives research problems and tries to solve them.

### What to build

**7.1 — Agent interface**

The agent receives a `ResearchProblem` and interacts via the existing EpisodeRunner,
but with semantic presentation:
- Sees the problem description, context, available data
- Can request observations (semantically described, with costs)
- Can submit its answer
- Everything else (reasoning, analysis, hypothesis generation) is free and
  up to the agent — we don't prescribe how it thinks

**7.2 — Agent orchestrator**

An LLM agentic loop (similar to the world orchestrator) that:
- Receives the research problem as context
- Decides what to observe based on the problem
- Reasons about the evidence
- Submits its final answer

The agent uses the same OpenAI function calling pattern:
- `observe(node)` → returns observation in semantic format
- `submit(answer)` → submits final probability distribution

**7.3 — Agent evaluation**

Compare the agent's performance against:
- The teacher solver (perfect baseline)
- A random agent (worst-case baseline)
- Metrics: KL divergence, accuracy, information efficiency, budget usage

### Done when

- An LLM agent can receive a research problem and attempt to solve it
- The agent's performance is scored against the teacher
- We can identify where the agent fails vs the teacher

---

## Phase 8 — More templates + more tasks

**Goal**: Add diversity in world structure and task types.

### Templates to add

**Causal chain**: A → B → C → target. Tests evidence propagation across hops.
Each template gets semantic layer support from the start.

**Fork with collider**: Latent common cause + collider downstream.
Tests d-separation understanding and Berkson's bias.

### Tasks to add

**`next_best_observation`**: Given current evidence, which action should be taken next?
Correct answer: the action maximizing expected information gain.

**`hypothesis_selection`**: Given a set of possible explanations, which is most plausible?
Correct answer: the hypothesis with highest posterior probability.

### Done when

- 3 templates generating valid worlds with semantic layers
- Same world can produce multiple task types
- Agent solver works across all templates

---

## Phase 9 — Dataset generation + evaluation harness

**Goal**: Produce exportable datasets and systematic evaluation.

### What to build

**Teacher trajectory dataset**: For each episode, export the full optimal
trajectory as (problem, action, result, posterior) sequences. JSONL format.

**Batch evaluation harness**: Run the LLM agent across many problems,
collect metrics, produce summary reports.

**Comparative analysis**: Teacher vs agent performance across:
- Different templates
- Different difficulty levels
- Different budget constraints

### Done when

- Dataset exported correctly as JSONL
- Batch eval runs across 100+ problems
- Results show where the agent fails relative to the teacher

---

## v0 success criteria

| Criterion | What it proves |
|---|---|
| Generate research problems with narrative + data + actions | Semantic layer works |
| Same Bayesian network → realistic research problem | Two-layer architecture is correct |
| Teacher reaches >90% on infer_target | World quality is sufficient |
| LLM agent can interact with research problems | Agent interface works |
| Agent performance scored vs teacher | Evaluation pipeline works |
| Generate 100+ reproducible problems across templates | Generator is stable |
| Teacher trajectories exported as dataset | Output pipeline works |

---

## What comes after v0

See `PROJECT.md` sections on v1, v2, v3 for the full roadmap.
Key additions: richer data formats, paper-based seeds, synthetic documents,
more action types, intervention tasks, RL training loop.
