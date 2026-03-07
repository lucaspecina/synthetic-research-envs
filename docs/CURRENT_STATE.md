# SREG — Current State

> Technical description of what the system does today and what's next.
> Updated: 2026-03-07

---

## Where we are

**Phases 1-5 complete.** The formal engine works end-to-end: generate Bayesian network
worlds, validate them, create episodes, solve with exact teacher, score results.
The LLM orchestrator generates worlds via tool calling.

**Phases 6-9 pending.** The semantic layer (making worlds look like real research
problems), the LLM agent solver, more templates, and dataset export.

**The gap:** The system currently generates abstract worlds (`indicator_1`,
`target_outcome`) with bare mathematical tasks. The goal is to generate realistic
research problems with narrative, data, and context — backed by the same formal
Bayesian networks underneath.

---

## Architecture (implemented)

```
User goal (text)
    |
    v
[LLM Orchestrator] -- calls tools in a loop -->
    |
    |-- WorldGenTool ----> World (DAG + CPDs + metadata)
    |-- WorldCheckTool --> Validation report (pass/fail + metrics)
    |-- EpisodeGenTool --> Episode (budget, available nodes, costs)
    |-- TaskGenTool -----> Task (question + correct answer)
    |
    v
World ready for agents
    |
    v
[EpisodeRunner] -- step loop -->
    |-- Agent observes nodes (observe action)
    |-- Agent queries distributions (query action)
    |-- Agent submits answer (submit action)
    |
    v
[VerifierTool] -- scores against ground truth -->
    |
    v
Score (KL divergence, info efficiency, per-step)
```

### Architecture (planned — Phase 6+)

```
User seed (topic / scenario / paper / params)
    |
    v
[LLM Orchestrator] -- calls tools + generates semantic content -->
    |
    |-- WorldGenTool ----> Bayesian network (formal truth)
    |-- WorldCheckTool --> Validation
    |-- LLM generates --> Narrative, names, descriptions, data format
    |-- EpisodeGenTool --> Episode with semantic actions
    |-- TaskGenTool -----> Research question in context
    |
    v
ResearchProblem (what the agent sees)
    |-- Problem title + description
    |-- Available data (tabular / observations / experiments)
    |-- Available actions with costs and descriptions
    |-- Research question(s)
    |
    v
[LLM Agent Solver] -- reasons freely, pays for observations -->
    |-- Reads context (free)
    |-- Analyzes data (free)
    |-- Formulates hypotheses (free)
    |-- Requests observations (costs budget)
    |-- Submits answer
    |
    v
[VerifierTool] -- scores against Bayesian network truth -->
    |
    v
Score + comparison vs teacher
```

---

## Modules (current)

| Module | Location | What it does |
|--------|----------|-------------|
| **Models** | `src/sreg/models/` | Pydantic data contracts: World, Node, Edge, CPD, Episode, Task, Score, TeacherOutput |
| **World gen** | `src/sreg/world/templates/` | Latent preference template — generates DAG + CPDs from parameters |
| **World check** | `src/sreg/tools/world_check.py` | Validates: DAG acyclicity, entropy, d-separation, paths to target |
| **Teacher solver** | `src/sreg/solver/exact_bayes.py` | Exact Bayesian inference via pgmpy VariableElimination; posteriors + info gain |
| **Episode gen** | `src/sreg/tools/episode_gen.py` | Creates episodes: budget, available nodes, observation costs |
| **Task gen** | `src/sreg/tools/task_gen.py` | Creates `infer_target` tasks with exact correct answer |
| **Verifier** | `src/sreg/tools/verifier.py` | Scores via KL divergence, information efficiency, per-step tracking |
| **Episode runner** | `src/sreg/env/` | Step-by-step environment interface (observe → query → submit) |
| **Orchestrator** | `src/sreg/orchestrator/` | LLM agentic loop: calls tools via function calling |
| **Display** | `src/sreg/display.py` | Dual-mode pretty printing (terminal ANSI + notebook HTML) |

---

## What a world looks like today vs the goal

### Today (abstract)

```
World: world-000042
Nodes: hidden_cause, indicator_1, indicator_2, target_outcome
Task: "Estimate P(target_outcome | evidence)"
Data: single observations via observe action
```

### Goal (realistic research problem)

```
Problem: "Declive de producción de algas en Nelvara"
Context: 3 paragraphs of narrative + background theory
Data: 150-row dataset with named columns (temperature, pH, nitrogen, light)
Actions: "Solicitar análisis de sedimentos (costo: 2)", "Medir compuesto X (costo: 1)"
Question: "¿Cuál es la causa principal del declive en producción?"
Behind: same Bayesian network, same exact inference, same scoring
```

---

## Test coverage

- 125 tests across all modules
- Tests mirror src structure
- Key validations: 100 worlds validated, teacher >90% across 50 worlds

## Dependencies

- Python 3.11, pgmpy, networkx, numpy/scipy, pydantic v2, openai SDK, python-dotenv
- LLM: Azure AI Foundry (gpt-5.2-chat)
- Dev: pytest, ruff, mypy

## Scripts & notebooks

| Script | What it does |
|--------|-------------|
| `scripts/demo.py` | Terminal demo: world gen → teacher solving (with display) |
| `scripts/test_orchestrator.py` | Step-by-step orchestrator run with real LLM |
| `notebooks/01_explore_system.ipynb` | Interactive exploration notebook |
