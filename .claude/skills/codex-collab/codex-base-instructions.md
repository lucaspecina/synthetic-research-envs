# Codex Base Instructions — SREG Project

This text MUST be appended to the user-level base instructions (from
`~/.claude/skills/codex-collab/codex-base-instructions.md`) and passed together
as `base-instructions` in every `mcp__codex__codex` call for this project.

Content between the `---` markers:

---

## SREG — Project-Specific Context

SREG (Synthetic Research Environment Generator) generates synthetic research
environments with exact reward signals, designed for training policy models
that do science via RL. Like OpenAI Gym for games — SREG for scientific reasoning.

**SREG generates environments + computes rewards. It does NOT train policies.**

### Two-layer architecture (the core concept)

- **Formal layer (hidden)**: Bayesian network (DAG + CPDs) = mathematical truth.
  The policy never sees this. All reward computation is exact against this layer.
- **Semantic layer (visible)**: Narrative context, datasets, named variables,
  research questions. What the policy sees — like what a real researcher receives.

### Key design principle

Every task must feel like a real research question, not a DAG exercise.
"What variables should you control for?" = good.
"Find a valid backdoor set in this DAG" = bad.

### Key components

- **SRC** = Synthetic Research Case = complete training environment
- **Teacher** = optimal policy (exact Bayesian inference, upper bound on reward)
- **Diagnostic agent** = zero-shot LLM policy (validates environments work)
- **Orchestrator** = LLM that designs research cases (proposes structure + semantics)
- **Tools** = programmatic validators (build and verify the math)

### Document hierarchy for THIS project

1. `CLAUDE.md` — START HERE. Conventions, workflow, doc map.
2. `PROJECT.md` — Vision, principles, invariants, hierarchy of decision.
3. `ARCHITECTURE.md` — System design, contracts, flows, extension points.
4. `CURRENT_STATE.md` — What exists TODAY. 1107 tests, 9 eval types.
5. `TODO.md` — Pending work, open problems, backlog.
6. `CHANGELOG.md` — History.
7. `research/` — Analysis, findings, synthesis (see research/README.md).

### Three-level QA

1. **Tests** (pre-commit): "Did I break something?"
2. **Environment Diagnostic** (periodic): "Are environments good?" — real LLM, not mocks
3. **Transfer Benchmark** (future): "Does training on SREG improve policies?" — THE real test

### When reviewing SREG code, check:

- Does it align with PROJECT.md vision?
- Does the task feel like science, not graph theory?
- Are reward signals exact (from BN), not heuristic?
- Is the semantic layer realistic but fictional?
- Does the change require doc updates? (see trigger table in CLAUDE.md)

---
