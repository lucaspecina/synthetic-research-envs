# Synthetic Research Environment Generator (SREG)
## Project Spec for Claude Code / Coding Agent Bootstrap

## 1. Project identity

**Working name:** Synthetic Research Environment Generator  
**Short name:** SREG

This project is about building a system that generates **synthetic, verifiable research environments** in which **LLM agents** can later investigate, gather evidence, make decisions, and receive an automatic score.

The main product is **not** the final solving agent.

The main product is the **environment-generation platform**:
- it creates hidden worlds,
- derives evidence from them,
- generates tasks,
- defines interaction interfaces,
- and scores agents against the hidden truth.

The long-term purpose is to improve **LLM scientific decision-making**, especially:
- uncertainty-aware reasoning,
- evidence prioritization,
- active information gathering,
- hypothesis comparison,
- sequential research decisions,
- and eventually **research taste**.

---

## 2. Core principle

The project should be built around one central separation:

- **LLM = orchestrator / designer / semantic planner**
- **Programmatic tools = source of truth / simulator / verifier**

This is critical.

We do want an LLM to play an important role from **v0**.
But we do **not** want the LLM to be the hidden source of truth of the environment.

So the design should be:

1. the **LLM proposes or refines world/task specifications**,
2. the **tooling constructs the actual world**,
3. the **tooling validates and simulates it**,
4. the **tooling computes the ground-truth answers and scores**,
5. later, the **LLM can also enrich the semantic presentation** of the environment.

This gives us both:
- flexibility and semantic richness,
- and verifiability and control.

---

## 3. What we are building

The ambitious vision is:

> A platform where an LLM orchestrates tools to generate hidden synthetic research worlds, derive structured evidence and later richer artifacts from those worlds, generate verifiable research tasks, and produce environments in which LLM agents can interact and be scored automatically against the underlying truth.

The system is meant for **future LLM research agents** that may:
- read structured evidence,
- later read documents and reports,
- compare hypotheses,
- select what to inspect next,
- eventually use search or external tools,
- and make research decisions under uncertainty.

So the system should be designed from day one with the assumption that the eventual solvers are **LLM agents**, not narrow symbolic policies.

---

## 4. What the project is and is not

### This project is
- an environment factory,
- a hidden-world generator,
- a task generator,
- a verifier/scorer platform,
- a substrate for later LLM training and evaluation.

### This project is not
- primarily a solver project,
- primarily a fixed benchmark of hand-written tasks,
- primarily a document-generation project,
- primarily a “DAG discovery from text” project.

Baseline agents may exist early for testing.
Real solvers may come later.
But the main focus is the **generation system**.

---

## 5. Why LLMs should be involved from v0

A key design decision:

We **do want an LLM in the loop from v0**.

Not as the hidden world itself.
Not as the truth source.
But as the **orchestrator that interacts with the world-generation tools**.

That means the LLM can:
- choose or sample templates,
- decide world complexity,
- pick difficulty knobs,
- request regeneration if a world is too trivial,
- choose what task families to instantiate,
- later generate semantic framings of the tasks.

This is better than a purely hardcoded generator because:
- it aligns with the long-term agentic direction,
- it gives flexible generation control,
- it allows richer scenario diversity,
- and it already exercises the “LLM using tools” pattern.

So v0 should already support:

> **LLM orchestration over programmatic world-generation tools**

---

## 6. The 5-layer architecture

The system should be organized into five main layers.

### 6.1 World Model
This is the hidden ground-truth world.

Examples:
- Bayesian network,
- causal DAG,
- discrete probabilistic system,
- latent mechanism graph,
- later maybe dynamic systems or richer mechanistic simulators.

The world model defines:
- variables,
- observable vs latent nodes,
- dependencies,
- parameters,
- valid episode state,
- task-relevant hidden truth.

This layer must remain **programmatic and explicit**.

### 6.2 Artifact Generator
This derives evidence from the world.

Early artifacts:
- sampled observations,
- tabular data,
- partial evidence,
- metadata about available variables.

Later artifacts:
- reports,
- notes,
- summaries,
- hints,
- document collections,
- simulated literature/search results.

Important:
**v0 should start without free-form document generation.**

### 6.3 Task Generator
This turns a world plus artifacts into a task.

Examples:
- infer target variable,
- choose next variable to observe,
- select most plausible hypothesis,
- later compare explanations,
- later propose interventions,
- later answer research-style questions.

### 6.4 Environment Interface
This defines how an agent interacts with the task.

Examples:
- what the agent sees,
- action schema,
- step budget,
- observation return format,
- terminal conditions.

This should be compatible with **LLM agents** and tool-based interaction.

### 6.5 Verifier / Scorer
This scores the final episode against the hidden world.

Examples:
- exact correctness,
- probabilistic scoring,
- penalties for wasted observations,
- calibration-aware metrics,
- later structural metrics,
- later inferential fidelity metrics.

This layer must remain **world-grounded**, not dependent on subjective LLM judging.

---

## 7. The most important design rule

**The LLM should design the world through tools, not directly author the truth.**

That means the rough pattern is:

- LLM proposes structured world spec
- Tool builds world
- Tool validates constraints
- Tool simulates candidate episodes
- Tool returns world summary / diagnostics
- LLM may accept, reject, or refine
- Tool finalizes environment package
- Verifier computes ground-truth labels and scores

This is the core pattern to preserve.

---

## 8. How the world generation should work

The intended design is a hybrid pipeline.

### Step A: Seed / intent
A user or upstream system provides a seed, high-level goal, or randomness source.

Example:
- “Generate a medium-difficulty world with real uncertainty and an informative-but-not-trivial target.”
- “Generate a world where active observation matters.”
- “Generate 50 worlds suitable for hypothesis selection tasks.”

### Step B: LLM orchestration
An LLM receives that goal and decides how to instantiate the world generation tools.

The LLM should not emit raw prose only.
It should emit a **structured request** for tools.

Example structured fields:
- template family,
- number of nodes,
- expected number of latent variables,
- sparsity,
- noise level,
- task families,
- difficulty target,
- desired ambiguity level.

### Step C: Programmatic world generation
A world-generation tool creates the hidden world from that spec.

It should:
- build valid structures,
- reject invalid configurations,
- assign parameters,
- tag observable/latent nodes,
- choose targets,
- compute world metadata.

### Step D: Programmatic validation
A validation tool checks whether the world actually matches the requested properties.

Examples:
- Is the target too easy?
- Is active information gain meaningful?
- Is there enough uncertainty?
- Is the world degenerate or trivial?

If the world is poor, the LLM can regenerate or refine the spec.

### Step E: Artifact generation
The programmatic system generates observable evidence:
- sampled rows,
- partial observations,
- target-related context,
- structured metadata.

### Step F: Task generation
A task-generation tool instantiates one or more tasks from the world.

### Step G: Ground-truth generation
A verifier/teacher tool computes:
- correct answers,
- probabilistic targets,
- evaluation metadata,
- scoring rules.

### Step H: Optional semantic packaging
Later, an LLM can transform that structured environment into a more natural semantic presentation.

But **this is not required in v0**.

---

## 9. Why v0 should still start without documents

Even though we want LLMs involved from v0, **we should not start with free-form textual artifacts**.

Reason:
documents are the most fragile part of the stack.

If introduced too early, they make it harder to debug:
- is the world bad,
- is the task bad,
- is the text misleading,
- or is the agent bad?

So the correct compromise is:

- **yes** to LLM orchestration in v0,
- **yes** to programmatic world generation in v0,
- **no** to heavy document/story generation in v0,
- **later** add semantic layers once the core is stable.

This keeps the system solid while still giving LLMs an important role from the beginning.

---

## 10. v0 / initial POC

The v0 should be a strong environment core with LLM orchestration.

### v0 should include
- an LLM orchestrator that calls world-generation tools,
- one programmatic hidden-world family,
- structured evidence generation,
- automatic task generation,
- multi-step environment interface,
- automatic scoring,
- simple baseline agents for testing.

### v0 should not include
- realistic papers or reports,
- simulated web search,
- open-ended scientific corpora,
- large intervention spaces,
- full training loops for large LLMs.

### v0 should prove
That we can build a **reliable environment-generation system** where:
- an LLM uses tools to generate worlds,
- the worlds are valid and controllable,
- tasks are automatically derived,
- agents can interact with those tasks,
- and scoring is objective.

That is enough for a meaningful first version.

---

## 11. Concrete v0 world type

Start with one hidden-world family:

### Discrete probabilistic world
A small causal/probabilistic world with:
- a small DAG-like structure,
- observable variables,
- latent variables,
- one or more target variables,
- controllable noise and ambiguity,
- explicit episode budget.

This is enough to support:
- uncertainty,
- sequential observation,
- hidden hypotheses,
- nontrivial scoring.

This is a good first substrate.

---

## 12. Concrete v0 task families

Start with a small number of task families.

### 12.1 Target inference
The agent must estimate or select the state of a target variable.

### 12.2 Active observation
The agent chooses which observable variable to inspect next under a limited budget.

### 12.3 Hypothesis selection
The system presents a small set of possible explanations derived from the world, and the agent must select the most plausible one.

### 12.4 Optional terminal structure guess
As an optional later-v0 extension, the agent may provide a partial structural guess at the end of the episode.

But structure prediction should not dominate v0.

---

## 13. Agent interaction model in v0

The eventual solvers are LLMs, but v0 can keep the interface simple.

Recommended initial actions:
- `observe(node)`
- `submit_answer(...)`

The environment returns:
- structured observation results,
- updated remaining budget,
- task metadata,
- terminal score after submission.

The format should be JSON-friendly and easy to wrap in text later.

---

## 14. How the LLM should interact with generation tools

This is one of the central design requirements.

The LLM should have access to a world-generation tool API, for example:

- `generate_world(spec)`
- `analyze_world(world_id)`
- `regenerate_world(world_id, edits)`
- `generate_tasks(world_id, task_spec)`
- `package_episode(world_id, task_id)`
- `score_episode(world_id, episode_result)`

The LLM workflow might look like this:

1. receive high-level generation intent
2. call `generate_world(...)`
3. inspect diagnostics
4. refine / regenerate if needed
5. call `generate_tasks(...)`
6. call `package_episode(...)`
7. emit an environment package for downstream agents

This gives the LLM a meaningful role without letting it break verifiability.

---

## 15. What “LLM role” means in this project

There are really two LLM roles in the full vision.

### Role 1: Generator-Orchestrator (starts in v0)
The LLM uses tools to create and refine worlds and tasks.

This role is included from the beginning.

### Role 2: Story / Semantic Layer (starts later)
The LLM transforms structured environments into semantically rich scenarios:
- named variables,
- research framing,
- notes,
- reports,
- hints,
- later document collections.

This role should come later, after the environment core is stable.

---

## 16. Long-term ambitious vision

The most ambitious version of the project is:

- an LLM orchestrates tool-based generation of hidden research worlds,
- programmatic systems define truth and verification,
- artifacts become increasingly rich and semantic,
- tasks become increasingly research-like,
- LLM agents investigate those environments,
- and the resulting environments are used for:
  - evaluation,
  - synthetic dataset generation,
  - teacher trajectory generation,
  - and eventually SFT / RL / RLVR for improving scientific research behavior.

In later stages, an environment may include:
- structured data,
- experiment logs,
- notes,
- papers,
- partial literature,
- search interfaces,
- and multiple research subquestions.

But the early stages should remain narrower and solid.

---

## 17. Why this matters for scientific reasoning and research taste

The point is not just to train LLMs to “get answers right.”

The point is to create environments where better behavior means:
- asking better questions,
- gathering more useful evidence,
- allocating limited attention wisely,
- knowing when uncertainty is still too high,
- preferring more plausible explanations,
- and making better research decisions.

That is much closer to **research taste** than static QA.

So the environment generator should be seen as infrastructure for teaching and measuring:
- scientific decision quality,
- evidence prioritization,
- and uncertainty-aware investigation.

---

## 18. Recommended repository-level architecture

Suggested components:

```text
sreg/
  README.md
  pyproject.toml

  src/
    orchestrator/
      llm_orchestrator.py
      prompts.py
      schemas.py

    tools/
      world_gen.py
      world_validate.py
      task_gen.py
      episode_packager.py
      scorer.py

    worlds/
      base.py
      probabilistic_world.py
      generators.py
      metadata.py

    artifacts/
      tabular.py
      observations.py

    tasks/
      target_inference.py
      active_observation.py
      hypothesis_selection.py

    envs/
      episode_runner.py
      action_schema.py
      observation_schema.py

    baselines/
      random_agent.py
      heuristic_agent.py
      oracle_agent.py

    configs/
      defaults.yaml
      templates.yaml
      difficulty.yaml

    utils/
      serialization.py
      sampling.py
      registry.py

  tests/
    test_world_generation.py
    test_world_validation.py
    test_task_generation.py
    test_episode_runner.py
    test_scoring.py
```

The exact structure can evolve, but the split between:
- orchestrator,
- tools,
- world core,
- tasks,
- environment,
- verifier
should remain explicit.

---

## 19. Milestone plan

### Milestone 1: Programmatic world core
- define hidden-world abstraction
- implement one discrete probabilistic world family
- implement world validation

### Milestone 2: Tool interface
- implement `generate_world`
- implement `analyze_world`
- implement `generate_tasks`
- implement `package_episode`
- implement `score_episode`

### Milestone 3: LLM orchestrator
- create the LLM wrapper that uses those tools
- support iterative regeneration/refinement

### Milestone 4: Environment loop
- define action schema
- implement episode runner
- support observation budget and terminal answer submission

### Milestone 5: Baselines
- random baseline
- simple heuristic baseline
- simple oracle baseline

### Milestone 6: Evaluation harness
- batch-generate tasks
- measure environment difficulty
- measure baseline performance

### Milestone 7: Later semantic layer
- variable naming
- semantic rendering
- eventually controlled text artifact generation

---

## 20. Open design questions that should stay explicit

These questions should be documented and kept open:

- What backend should implement the probabilistic world core?
- How should world quality/interestingness be measured?
- How should inferential fidelity be defined later?
- When should interventions enter the action space?
- How should textual artifacts be grounded when introduced?
- How should environment difficulty be calibrated?
- How should synthetic worlds eventually be inspired by real scientific domains and papers?

These should remain explicit, but they should not block v0.

---

## 21. Final summary

This project should be understood as:

> a hybrid system where an LLM orchestrates programmatic tools to generate synthetic, verifiable research environments for future LLM scientific agents.

The key commitments are:
- **LLM involved from v0**
- **truth remains programmatic**
- **no heavy documents in v0**
- **focus first on a strong environment core**
- **design for future semantic LLM agents**
- **long-term aim = better scientific decision-making and research taste**

The first implementation should therefore prioritize:
- world generation,
- validation,
- task derivation,
- environment interaction,
- scoring,
- and LLM tool orchestration.

It should avoid:
- premature document realism,
- premature open-endedness,
- and premature coupling to one specific solver.

---

## 22. Bootstrapping instruction for Claude Code

Use this document as the initial project spec.

Build the first version around:
1. one hidden-world family,
2. one set of world-generation tools,
3. one LLM orchestrator that uses those tools,
4. structured tasks,
5. structured episodes,
6. objective scoring,
7. minimal baselines.

Prefer:
- modular abstractions,
- explicit schemas,
- testable components,
- tool-oriented design,
- clean separation between LLM orchestration and programmatic truth.

Do not start by implementing:
- large textual artifact systems,
- external search,
- complex open-ended research simulation,
- or solver-heavy infrastructure.

The first goal is a **solid, extensible environment-generation core**.
