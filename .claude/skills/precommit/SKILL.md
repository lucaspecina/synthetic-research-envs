---
name: precommit
description: "THE commit workflow. Run this before EVERY commit: tests, validation, present to user, get approval, update docs, commit. This is the ONLY way to commit."
disable-model-invocation: true
---

# The SREG commit workflow

**This is the ONLY way to commit changes.** No exceptions.
Every change — code or docs — follows this workflow.

## The workflow (in order)

### Step 1: Targeted validation
**Skip if doc-only or trivial changes (typos, comments).**

- Run `pytest` ONLY on the specific test file(s) affected by the change. NOT the full suite.
- Run `ruff check` on modified files.
- If the change touches orchestrator/tools/OI pipeline AND LLM credentials available:
  run 1 real case as smoke test (`/run --oi`).

### Step 2: Codex review (if Codex MCP available)
**MANDATORY for code changes. SKIP for doc-only or trivial changes.**
**SKIP ENTIRELY if Codex MCP is not connected.**

- Pass the diff to Codex via `mcp__codex__codex` (or `codex-reply` if thread exists).
- Include context briefing: what we're doing, why, what the user decided.
- Ask Codex to be critical: bugs, over-engineering, missed edge cases.
- If Codex finds real issues → fix them before presenting to user.
- If Codex disagrees on approach → note it for the presentation.
- See `/codex-collab` skill for full protocol.

### Step 3: Present to user
**MANDATORY. ALWAYS. Even for doc-only changes.**

- Explain the changes in Spanish, friendly and detailed.
- Cover: what was done, how it fits, what's now possible.
- If there was E2E validation, show the key results.
- If Codex reviewed: include key feedback and how it was addressed.
- Be honest about limitations and next steps.
- **Ask explicitly**: "¿Actualizo docs y hago commit + push?" (or similar).
- **WAIT for the user's approval.** Do NOT proceed without it.
- If the user requests changes → make them → re-run tests → re-present.

### Step 4: Update docs + Commit + Push
**Only AFTER user says yes.**

- Update docs:
  - `TODO.md`: mark completed tasks `[x]`, add new tasks
  - `CHANGELOG.md`: add entry for new functionality
  - `CURRENT_STATE.md`: update test count, modules, capabilities
  - `CLAUDE.md`: update project structure, conventions
  - No stale references to deleted/renamed files
- Commit with descriptive message
- Push (ask user first if unsure)

### Step 5: What's next?
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

If the commit changes orchestrator/tools/OI pipeline: note that `/eval` should
be re-run to verify environment quality. This is a NOTE, not a blocker.

## 23 escenarios check

If the commit changes scoring, compiler, prompts, or contracts: verify mentally
that the change works for ALMOST ALL 23 diverse investigation scenarios
(`research/synthesis/investigation_scenarios_rubric.md`). If it only works for
a few types, flag it before presenting to the user.

## Report format

```
Tests:      PASS (N tests) / SKIP (doc-only)
Lint:       PASS / SKIP
E2E:        PASS / SKIP (reason)
Diagnostic: NOTE: should re-run /eval / N/A
Approval:   PENDING
```
