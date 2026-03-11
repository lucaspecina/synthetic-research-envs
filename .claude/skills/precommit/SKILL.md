---
name: precommit
description: "THE commit workflow. Run this before EVERY commit: tests, validation, present to user, get approval, update docs, commit. This is the ONLY way to commit."
disable-model-invocation: true
---

# The SREG commit workflow

**This is the ONLY way to commit changes.** No exceptions.
Every change — code or docs — follows this workflow.

## The workflow (in order)

### Step 1: Tests + Validation
**Skip if doc-only or trivial changes (typos, comments).**

- Run `pytest tests/ -q`. ALL must pass.
- Run `ruff check` on modified files.
- If the change adds features or modifies behavior:
  - Write an inline script (`python -c`) that exercises the change with real execution.
  - Run with at least 5 different configurations.
  - If LLM credentials are available AND the change touches orchestrator/agent/env/tools:
    run 1-2 real LLM pipeline cases as smoke test.
  - Read the output carefully. Do the values make sense?

### Step 2: Present to user
**MANDATORY. ALWAYS. Even for doc-only changes.**

- Explain the changes in Spanish, friendly and detailed.
- Cover: what was done, how it fits, what's now possible.
- If there was E2E validation, show the key results.
- Be honest about limitations and next steps.
- **Ask explicitly**: "¿Actualizo docs y hago commit + push?" (or similar).
- **WAIT for the user's approval.** Do NOT proceed without it.
- If the user requests changes → make them → re-run tests → re-present.

### Step 3: Update docs + Commit + Push
**Only AFTER user says yes.**

- Update docs:
  - `TODO.md`: mark completed tasks `[x]`, add new tasks
  - `CHANGELOG.md`: add entry for new functionality
  - `CURRENT_STATE.md`: update test count, modules, capabilities
  - `CLAUDE.md`: update project structure, conventions
  - No stale references to deleted/renamed files
- Commit with descriptive message
- Push (ask user first if unsure)

### Step 4: What's next?
**MANDATORY. Right after commit+push.**

- Review `TODO.md` and identify what's next in the roadmap.
- Present 1-3 concrete next steps to the user, in friendly Spanish.
  Not a dump of the whole TODO — a curated suggestion of what makes sense NOW.
- Explain briefly WHY each option matters (how it fits in the big picture).
- Ask: "¿Qué te parece? ¿Seguimos con algo?" (or similar).
- Let the user choose, or suggest a different direction.

## Why this order matters

- **Tests first**: catch bugs before presenting broken code
- **Present before docs**: if the user requests changes, you'd have to re-update all docs
- **Docs after approval**: they get written once, correctly, right before commit

## Diagnostic impact check

If the commit adds a new eval type, action type, or changes orchestrator/agent/env:
note that the environment diagnostic (`/eval`) should be re-run to verify
environment quality. This is a NOTE, not a blocker — log it and move on.

(Note: `/eval` runs the environment diagnostic, NOT the transfer benchmark.
The transfer benchmark is a separate, future process — see docs/EXTERNAL_BENCHMARKS.md.)

## Report format

```
Tests:      PASS (N tests) / SKIP (doc-only)
Lint:       PASS / SKIP
E2E:        PASS / SKIP (reason)
Diagnostic: NOTE: should re-run /eval / N/A
Approval:   PENDING
```
