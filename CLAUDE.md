# SREG — Claude Code Project Configuration

## START HERE — Read these docs first

Before doing anything, understand the project by reading these docs in order:

1. **`PROJECT.md`** — **THE vision document.** This is the soul of the project.
   Read it to understand WHY we build what we build, not just WHAT.
   Every technical decision, every implementation choice, every TODO must align
   with the spirit described here. When in doubt about any decision, go back
   to PROJECT.md — it's the ultimate source of truth for the project's direction.
2. **`WORLD_DESIGN.md`** — **Research document** for realistic world generation.
   Conclusions, strategies, open questions, and references for evolving from
   toy worlds to realistic research cases. Dynamic — updated as we learn.
   Key sections: "Fundamentos de razonamiento causal" (Pearl/McElreath theory),
   "Catálogo de evaluaciones científicas" (31 eval types in 6 families),
   "Diseño de Research Cases" (TaskBundle→ResearchCase). Has navigation index.
3. **`CURRENT_STATE.md`** — Detailed description of what the system does TODAY. APIs, modules, templates, test coverage. **Must stay current.**
4. **`TODO.md`** — Task tracking + known issues. Single source of truth for what's done/pending.
5. **`CHANGELOG.md`** — History of what's been done.

## Project overview

SREG (Synthetic Research Environment Generator) generates **fictional but realistic
research problems** for evaluating LLM scientific reasoning.

### Two-layer architecture (the core concept)

Every research problem has two layers:

- **Formal layer (hidden)**: A Bayesian network (DAG + CPDs) that defines the
  mathematical truth. The agent never sees this. All evaluation is against this.

- **Semantic layer (visible)**: A realistic presentation of the problem — narrative
  context, datasets, named variables, available experiments, research questions.
  This is what the agent sees, like what a real researcher would receive.

### Key design principles

- **Every task must feel like a real research question, not a DAG exercise.**
  The litmus test for any new eval type, task, or feature: "Would a scientist
  recognize this as a question from their work?" If it feels like a graph theory
  quiz, it's wrong. `adjustment_set` framed as "What variables should you control
  for in your analysis?" = good. Framed as "Find a valid backdoor set in this
  DAG" = bad. The eval type is the same; the framing makes it science or not.
  See WORLD_DESIGN.md "Fundamentos de razonamiento causal" for the full principle.
- **The BN is always the truth.** Every question has a mathematically verifiable answer.
- **Semi-real naming**: real scientific vocabulary (`water_temperature`) in fictional
  domains ("planet Kepler-442"). Not `indicator_1`, not `zorbax_flux`.
- **Agent freedom**: the agent can reason however it wants (analyze, hypothesize, code).
  Only "real-world actions" (experiments, measurements) cost budget.
- **Data is configurable**: tabular datasets, isolated observations, experimental results,
  multiple datasets, partial/incomplete data — all sampled from the BN.
- **Multiple evaluation types**: target inference (KL), causal effects, hypothesis
  selection, structure discovery, next-best-action, optimization — see PROJECT.md.
- **LLM orchestrates, tools own truth**: the LLM proposes structure and semantics,
  programmatic tools build and verify the math.

### Current state

v0+v1 complete (Etapa 1): 3 template families + 3 task types + multi-task bundles + formal engine + semantic layer + agent solver + eval harness.
v2 in progress: DAGSpec + cpd_gen + CustomTemplate + WorldCheck + 4 DAG generators + LLM orchestrator tools (dag_generate + dag_construct + design_case) + CasePlan (plan-driven task generation) + 9 eval types (infer_target, NBO, hypothesis_selection, causal_effect, best_intervention, adjustment_set, compare_interventions, should_condition, infer_latent_cause) + QualitySuite v2 (A+B multi-rollout+C) + dataset-rich evidence (multi-dataset, missing data, narratives) + Rich Actions Slice A (ResearchActionType, multi-node, varied costs, IG/cost teacher) + Agent trajectory inspection (extract, compare, export). 601 tests. Ola 1 COMPLETE. Rich Actions Slice A COMPLETE. Agent Solver S.1 (trajectories) COMPLETE.
**Next: Agent Solver v2 (S.2 diagnostic pipeline, S.3 harness multi-type), Rich Actions Slice B, narrative.** See TODO.md and WORLD_DESIGN.md.

## Environment setup

```bash
conda activate sreg
```

Conda env `sreg` with Python 3.11. Recreate: `conda create -n sreg python=3.11 -y && conda activate sreg && pip install -e ".[dev]"`

## Tech stack

- **pgmpy** — Bayesian network construction and exact inference (`DiscreteBayesianNetwork`, not `BayesianNetwork`)
- **networkx** — DAG validation (`nx.is_d_separator()`, not `nx.d_separated`)
- **numpy / scipy** — sampling, distribution operations
- **pydantic v2** — data contracts (BaseModel, not dataclass)
- **openai SDK** — LLM calls via Azure AI Foundry (see below)
- **python-dotenv** — auto-load `.env` for credentials
- **pytest** — testing
- **ruff** — linting and formatting (line length 100)

## LLM consumption — Azure AI Foundry

Use `OpenAI`/`AsyncOpenAI` with `base_url`. **Do NOT use `AzureOpenAI`.**
See `src/sreg/orchestrator/orchestrator.py` for the pattern.
Env vars: `AZURE_INFERENCE_CREDENTIAL`, `AZURE_FOUNDRY_BASE_URL`, `AZURE_MODEL`

## Project structure

```
src/sreg/
├── models/          # Pydantic data contracts (world, episode, task, teacher, score, dag_spec)
├── world/           # World model, templates (incl. custom), cpd_gen, pgmpy utils
├── solver/          # Teacher solver (exact Bayesian inference)
├── tools/           # WorldGen, WorldCheck, EpisodeGen, TaskGen, Verifier
├── env/             # EpisodeRunner (step-by-step environment interface)
├── orchestrator/    # LLM orchestrator loop (system prompt, tool definitions)
├── agent/           # LLM agent solver (Phase 7)
├── harness/         # Teacher trajectory, agent trajectory, comparison, batch eval (Phase 8)
└── display.py       # Dual-mode pretty printing (terminal ANSI + notebook HTML)

scripts/
├── demo.py                # Terminal demo: world gen + teacher solving
├── test_orchestrator.py   # Step-by-step orchestrator run with real LLM (--seed, --export, --seed-file)
├── view_case.py           # Inspect exported JSON cases section by section
├── test_agent.py          # Agent vs teacher vs random baseline comparison (--save-trajectory)
├── view_trajectory.py     # Inspect agent trajectories and agent-vs-teacher comparisons
├── test_e2e.py            # End-to-end: orchestrator -> agent -> score
└── batch_eval.py          # Batch eval + teacher trajectory JSONL export

notebooks/
└── 01_explore_system.ipynb  # Interactive exploration

tests/               # Mirrors src/ structure

research_seed.md             # Optional: research context for orchestrator (read automatically)
WORLD_DESIGN.md              # Research doc: toy worlds → realistic worlds (strategy, references, open questions)

docs/
└── references/              # Original design docs (read-only)

.claude/skills/      # Project skills: /plan, /status, /test, /review, /phase
```

## Code conventions

- Type hints on all public functions
- Module-level `__all__` exports in every `__init__.py`
- Tests mirror src: `src/sreg/tools/world_gen.py` → `tests/tools/test_world_gen.py`
- Imports: stdlib → third-party → local, separated by blank lines
- Terminal output must use ASCII-safe characters (Windows cp1252 compatibility)
- Communicate with the user in **Spanish**

## Commands

```bash
pytest tests/ -v                          # All tests
pytest tests/tools/test_world_gen.py -v   # Specific file
ruff check src/ tests/                    # Lint
ruff format src/ tests/                   # Format
```

## Quality assurance — two levels (CRITICAL)

SREG has two distinct levels of quality assurance. **Both must stay current.**
See PROJECT.md "Aseguramiento de calidad" for the full rationale.

### Level 1: Tests + Validation (pre-commit)

- **Unit tests** (`pytest tests/`): isolated functions, fabricated inputs, no LLM.
  Run on every commit.
- **E2E validation** (smoke test): 1-2 cases with real LLM to verify the full
  pipeline still works. Run when code changes touch orchestrator, agent, env, or tools.
- **Purpose: "Did I break something?"** — pass/fail, not quality measurement.

### Level 2: Benchmark & Diagnostic (periodic)

- **Product quality control.** Runs the REAL system end-to-end (always with LLM)
  and measures the quality of what it produces.
- **ALWAYS uses LLM** — the product uses LLM, so the benchmark must too.
  No toy worlds, no template shortcuts, no fabricated inputs.
- **ALWAYS uses the best current implementation** — if the system now uses
  orchestrator + CasePlan + rich data, the benchmark uses all of that.
- **Two outputs from the same run:**
  1. Aggregate metrics (completion rate, submit rate, KL, per-eval-type breakdown)
  2. Failure mode analysis (what patterns appear and why)
- **Results saved** in `experiments/` for comparison across runs.
- **Purpose: "How good is the product? Where does it fail?"**

### Keeping it current (NON-NEGOTIABLE)

When you add a new feature (eval type, action type, data format, orchestrator tool):
1. The **unit tests** validate the piece works in isolation
2. The **benchmark** must be able to exercise it with the real system
3. If the benchmark can't exercise it, that's a gap — log it and fix it

The benchmark is NOT a one-time thing. It's a living tool that evolves
with the system. If it falls behind, we're designing the product blind.

## Git conventions

- Branch naming: `feature/<name>`, `fix/<name>`, `refactor/<name>`
- Commit messages: imperative mood, concise
- Push works from the assistant. Always ask user before pushing.

## Commit workflow — MANDATORY

**The ONLY way to commit changes. No exceptions. See `/precommit` skill for full details.**

```
1. Tests + Validation     (skip if doc-only or trivial)
   pytest + ruff + E2E with real execution

2. Present to user        (ALWAYS, even for doc-only)
   Explain in Spanish, friendly + detailed
   Ask: "¿Actualizo docs y hago commit + push?"
   WAIT for approval. Do NOT proceed without it.

3. Update docs + Commit   (only AFTER user says yes)
   TODO.md, CHANGELOG.md, CURRENT_STATE.md, CLAUDE.md
   Then commit + push
```

**Why this order:** tests first (catch bugs), present before docs (if user
requests changes you'd re-update everything), docs last (written once correctly).

### Trigger-specific updates

These are common changes that REQUIRE updating specific docs:

| What changed | Update |
|---|---|
| Completed a task | `TODO.md`: mark `[x]`. `CHANGELOG.md`: add entry. `CURRENT_STATE.md`: update if it changes capabilities. |
| Added/removed a file or module | `CLAUDE.md`: project structure. `CURRENT_STATE.md`: modules table. |
| Added/changed a template | `CURRENT_STATE.md`: template table + structure diagram |
| Changed an API signature | `CURRENT_STATE.md`: Key APIs section |
| Changed test count | `CURRENT_STATE.md`: test coverage section |
| Added a dependency | `pyproject.toml` AND `CLAUDE.md`: tech stack |
| Changed a convention | `CLAUDE.md`: update immediately |
| Changed scope or vision | `PROJECT.md` first, then propagate to `CLAUDE.md` and `TODO.md` |
| New research findings on world generation | `WORLD_DESIGN.md`: update relevant section |
| Added/changed a NodeType | `display.py`: `_node_styles()` and `_HTML_NODE_COLORS` |
| New display function | `display.py`, update `scripts/demo.py` and notebook |
| New eval type or task type | `quality.py`: add non-trivial check. Benchmark: verify it's exercised by the real system. |
| Changed orchestrator/agent/env | Benchmark: re-run to verify product quality hasn't degraded. |
