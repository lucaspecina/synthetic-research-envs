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
6. **`EVAL_DESIGN.md`** — Evaluation strategy: what to measure, metrics, experimental designs, infrastructure.

## Project overview

SREG (Synthetic Research Environment Generator) **generates synthetic research
environments with exact reward signals**, designed for training policy models
that do science via RL. Like OpenAI Gym for games or PRIME Intellect for math,
SREG produces the environments — others bring their policies and train.

**SREG generates environments + computes rewards. It does NOT train policies.**
There is no training loop here. SREG produces SRCs, the BN computes exact
rewards, and the teacher generates optimal trajectories. A separate RL
framework connects a policy and trains against these environments.

### Key terminology

- **SRC** (Synthetic Research Case): a complete training environment — world + problem + tasks + data. This is the product unit of SREG.
- **Policy**: any agent (LLM, RL, hybrid) that interacts with an SRC.
- **Teacher**: the optimal policy — exact Bayesian inference, upper bound on reward.
- **Reward signal**: computed mathematically from the BN. No heuristics, no judges.

### Two-layer architecture (the core concept)

Every training environment has two layers:

- **Formal layer (hidden)**: A Bayesian network (DAG + CPDs) that defines the
  mathematical truth. The policy never sees this. All reward computation is against this.

- **Semantic layer (visible)**: A realistic presentation of the problem — narrative
  context, datasets, named variables, available experiments, research questions.
  This is what the policy sees, like what a real researcher would receive.

### Key design principles

- **Every task must feel like a real research question, not a DAG exercise.**
  The litmus test for any new eval type, task, or feature: "Would a scientist
  recognize this as a question from their work?" If it feels like a graph theory
  quiz, it's wrong. `adjustment_set` framed as "What variables should you control
  for in your analysis?" = good. Framed as "Find a valid backdoor set in this
  DAG" = bad. The eval type is the same; the framing makes it science or not.
  See WORLD_DESIGN.md "Fundamentos de razonamiento causal" for the full principle.
- **The BN is always the truth.** Every question has a mathematically verifiable
  answer — this is what makes exact reward signals possible for RL.
- **Semi-real naming**: real scientific vocabulary (`water_temperature`) in fictional
  domains ("planet Kepler-442"). Not `indicator_1`, not `zorbax_flux`.
- **Policy freedom**: the policy can reason however it wants (analyze, hypothesize, code).
  Only "real-world actions" (experiments, measurements) cost budget.
- **Data is configurable**: tabular datasets, isolated observations, experimental results,
  multiple datasets, partial/incomplete data — all sampled from the BN.
- **Multiple evaluation types**: target inference (KL), causal effects, hypothesis
  selection, structure discovery, next-best-action, optimization — see PROJECT.md.
- **LLM orchestrates, tools own truth**: the LLM proposes structure and semantics,
  programmatic tools build and verify the math.

### Current state

v0+v1 complete (Etapa 1): 3 template families + 3 task types + multi-task bundles + formal engine + semantic layer + agent solver + eval harness.
v2 in progress: DAGSpec + cpd_gen + CustomTemplate + WorldCheck + 4 DAG generators + LLM orchestrator tools (dag_generate + dag_construct + design_case) + CasePlan (plan-driven task generation with node hints) + 9 eval types (infer_target, NBO, hypothesis_selection, causal_effect, best_intervention, adjustment_set, compare_interventions, should_condition, infer_latent_cause) + QualitySuite v2 (A+B multi-rollout+C) + dataset-rich evidence (multi-dataset, missing data, narratives) + Rich Actions Slice A (ResearchActionType, multi-node, varied costs, IG/cost teacher) + Agent trajectory inspection (extract, compare, export) + Multi-type agent harness (submit + prompt + scoring for 9 eval types) + DiagnosticRunner with per-type baseline scoring + 15-SRC diagnostic (57 tasks, 9/9 types). 718 tests. Ola 1 COMPLETE. Rich Actions Slice A COMPLETE. Agent Solver S.1-S.3 COMPLETE. DIAG.1 COMPLETE. P0 question/answer mismatch FIXED (hints end-to-end).
**Next: Rich Actions Slice B (S.4 rich observe), scale diagnostic to 20-30 SRCs, transfer benchmark infrastructure (BENCH.1-5).** See TODO.md and WORLD_DESIGN.md.

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
├── harness/         # DiagnosticRunner, teacher/agent trajectory, comparison, batch eval
└── display.py       # Dual-mode pretty printing (terminal ANSI + notebook HTML)

scripts/
├── demo.py                # Terminal demo: world gen + teacher solving
├── test_orchestrator.py   # Step-by-step orchestrator run with real LLM (--seed, --export, --seed-file)
├── view_case.py           # Inspect exported JSON cases section by section
├── test_agent.py          # Agent vs teacher vs random baseline comparison (--save-trajectory)
├── view_trajectory.py     # Inspect agent trajectories and agent-vs-teacher comparisons
├── test_e2e.py            # End-to-end: orchestrator -> agent -> score
├── mini_benchmark.py      # Mini diagnostic: N real SRCs via orchestrator + agent + teacher
├── batch_eval.py          # Batch eval + teacher trajectory JSONL export
├── diagnostic_batch.py    # S.2 diagnostic: N SRCs via orchestrator, agent on all tasks, per-type metrics
└── run_diagnostic.py      # DiagnosticRunner wrapper: type-aware verdicts + failure modes

experiments/                 # Diagnostic results (timestamped directories)
└── index.md                 # Experiment registry

notebooks/
└── 01_explore_system.ipynb  # Interactive exploration

tests/               # Mirrors src/ structure

research_seed.md             # Optional: research context for orchestrator (read automatically)
WORLD_DESIGN.md              # Research doc: toy worlds → realistic worlds (strategy, references, open questions)
EVAL_DESIGN.md               # Evaluation strategy: metrics, experimental designs, infrastructure

docs/
├── EXTERNAL_BENCHMARKS.md   # External benchmarks for transfer validation (CLadder, QRData, etc.)
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

## Quality assurance — three levels (CRITICAL)

SREG has three distinct levels of quality assurance.
See PROJECT.md "Aseguramiento de calidad" for the full rationale.

### Level 1: Tests + Validation (pre-commit)

- **Unit tests** (`pytest tests/`): isolated functions, fabricated inputs, no LLM.
  Run on every commit.
- **E2E validation** (smoke test): 1-2 cases with real LLM to verify the full
  pipeline still works. Run when code changes touch orchestrator, agent, env, or tools.
- **Purpose: "Did I break something?"** — pass/fail, not quality measurement.

### Level 2: Environment Diagnostic (periodic)

- **Generator quality control.** Runs the REAL system end-to-end (always with LLM)
  and measures the quality of the environments it produces.
- **ALWAYS uses LLM** — the product uses LLM, so the diagnostic must too.
  No toy worlds, no template shortcuts, no fabricated inputs.
- **Two outputs from the same run:**
  1. Aggregate metrics (completion rate, submit rate, KL, per-eval-type breakdown)
  2. Failure mode analysis (what patterns appear and why)
- **Results saved** in `experiments/` for comparison across runs.
- **Purpose: "Are the environments well-formed, solvable, and non-trivial?"**
- **NOTE: This is NOT the real benchmark.** It validates that the generator produces
  quality environments, but does NOT prove that training on them improves policies.
  See Level 3.

### Level 3: Transfer Benchmark (the real test — FUTURE)

- **The true measure of SREG**: take a policy, evaluate it on external benchmarks,
  train it on SREG environments, evaluate again. The delta is the evidence.
- **External benchmarks**: CLadder (causal reasoning), QRData (causal + data),
  DiscoveryBench (hypothesis from data), SciGym (experimental cycle).
  See `docs/EXTERNAL_BENCHMARKS.md` for the full analysis.
- **Purpose: "Does training on SREG environments actually improve scientific reasoning?"**
- If a policy improves in SREG but not in external benchmarks = overfitting to the generator.
  If it improves in both = real transfer of scientific reasoning ability.
- **Status: NOT YET IMPLEMENTED.** Requires training infrastructure, model access,
  and benchmark adapters. See TODO.md "Benchmark de transferencia".

### Keeping it current (NON-NEGOTIABLE)

When you add a new feature (eval type, action type, data format, orchestrator tool):
1. The **unit tests** validate the piece works in isolation
2. The **diagnostic** must be able to exercise it with the real system
3. If the diagnostic can't exercise it, that's a gap — log it and fix it

The diagnostic is NOT a one-time thing. It's a living tool that evolves
with the system. If it falls behind, we're designing the product blind.

## Git conventions

- Branch naming: `feature/<name>`, `fix/<name>`, `refactor/<name>`
- Commit messages: imperative mood, concise
- Push works from the assistant. Always ask user before pushing.

## Codex collaboration — critical second opinion

**ONLY when Codex MCP (`mcp__codex__codex`) is available.** If not connected, skip entirely.

Codex (OpenAI) acts as a **critical collaborator** — it should challenge, find flaws,
and propose alternatives. If it just agrees with everything, it's not doing its job.

- **MANDATORY: Code review** — After implementation, before presenting to user.
  Codex reviews the diff for bugs, over-engineering, inconsistencies.
- **RECOMMENDED (use judgment, don't overuse):**
  - **Strategy/next steps** — When deciding what to work on next or how to prioritize.
  - **Pre-implementation strategy** — When a task involves significant design decisions,
    consider consulting Codex before coding. Use judgment.
  - **Design/architecture** — When there are multiple valid approaches.
  - **Problem-solving** — When stuck or unsure about an approach.
- **SKIP:** Doc-only changes, trivial fixes, when user says to skip.

Thread management: start with `mcp__codex__codex`, continue with `codex-reply` + `threadId`.
Always ask Codex to be critical: "Don't just agree — tell me what's wrong."

When Codex and Claude disagree: present BOTH perspectives to the user. The user decides.

**Claude leads, Codex advises.** Codex will always find something — that's its job.
Fix what's IMPORTANT (bugs, correctness), log minor findings as deuda, move on.
Use good judgment on how many review rounds are needed — don't enter infinite loops
chasing diminishing returns. Time matters.

See `/codex-collab` skill for full protocol.

## Commit workflow — MANDATORY

**The ONLY way to commit changes. No exceptions. See `/precommit` skill for full details.**

```
1. Tests + Validation     (skip if doc-only or trivial)
   pytest + ruff + E2E with real execution

2. Codex review           (MANDATORY if Codex MCP available, skip if doc-only/trivial)
   Pass diff to Codex, ask for critical review
   Fix issues found before presenting to user

3. Present to user        (ALWAYS, even for doc-only)
   Explain in Spanish, friendly + detailed
   Include Codex feedback and how disagreements were resolved
   Ask: "¿Actualizo docs y hago commit + push?"
   WAIT for approval. Do NOT proceed without it.

4. Update docs + Commit   (only AFTER user says yes)
   TODO.md, CHANGELOG.md, CURRENT_STATE.md, CLAUDE.md
   Then commit + push

5. What's next?           (right after commit+push)
   Review TODO, suggest 1-3 concrete next steps
   Ask: "¿Qué te parece? ¿Seguimos con algo?"
```

**Why this order:** tests first (catch bugs), Codex review (catch what tests don't),
present before docs (if user requests changes you'd re-update everything),
docs last (written once correctly).

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
| New eval type or task type | `quality.py`: add non-trivial check. Diagnostic: verify it's exercised by the real system. |
| Changed orchestrator/agent/env | Diagnostic: re-run to verify environment quality hasn't degraded. |
