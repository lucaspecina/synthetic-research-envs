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

- **Formal layer (hidden)**: SCM (Structural Causal Model) = equations + graph.
  The policy never sees this. Reward computation is exact (Monte Carlo) against this.
- **Semantic layer (visible)**: Narrative context, datasets, named variables,
  research brief. What the policy sees — like what a real researcher receives.

### Open Investigation (the active pipeline)

The solver receives an open brief and investigates freely. It submits claim
cards with findings. A compiler translates claims to executable specs via a
composable grammar (~24 atomic pieces). The SCM verifier executes them —
deterministic, no LLM. Current bottleneck: compiler (LLM extraction).

### LA PREGUNTA (double filter for every decision)

1. Why isn't this real research yet? What's missing?
2. Why wouldn't RL training on SREG teach good scientific judgment?
   (research taste, problem decomposition, fine-grained questions,
   knowing what to look at, knowing when a conclusion is premature)

### Key components

- **SRC** = Synthetic Research Case = complete training environment
- **SCMSolver** = teacher (Monte Carlo ground truth, upper bound on reward)
- **OI solver** = diagnostic policy (LLM zero-shot, validates environments)
- **Orchestrator** = LLM that designs SCM-based research cases
- **Compiler** = translates solver claims to verifiable specs

### Document hierarchy for THIS project

1. `CLAUDE.md` — START HERE. Conventions, workflow, doc map.
2. `PROJECT.md` — Vision, principles, invariants, LA PREGUNTA.
3. `ARCHITECTURE.md` — System design, contracts, flows.
4. `CURRENT_STATE.md` — What exists TODAY. SCM + OI only.
5. GitHub Issues + Project v2 — Pending work organized as epics (closable goals) -> sub-issues (1 PR each). Labels minimal: `bug`, `blocked`, `parked`, `research`, `design`. Priority = order in the Project Todo column. Worktree = custom Project field.
6. `CHANGELOG.md` — History.
7. `research/` — Analysis, findings, synthesis.

### When reviewing SREG code, check:

- Does it align with PROJECT.md vision and LA PREGUNTA?
- Does the task feel like science, not graph theory?
- Are reward signals exact (from SCM), not heuristic?
- Is the semantic layer realistic but fictional?
- Would this help train scientific judgment via RL?

---
