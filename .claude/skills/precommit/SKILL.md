---
name: precommit
description: "THE commit workflow. Run this before EVERY commit: tests, validation, present to user, get approval, update docs, commit. This is the ONLY way to commit."
disable-model-invocation: true
---

# The SREG commit workflow

**This is the ONLY way to commit changes.** No exceptions.
Every change — code or docs — follows this workflow.

## Tracking source of truth

**GitHub Project v2 = source of truth.** Ver skill `/tracking` para comandos exactos.

Antes de commitear, verificar:
- Si trabajaste un issue → Status en `In Progress` (debiste moverlo al empezar).
- Si cerras en este commit → Status auto a `Done` (verificar).
- Si creaste issue en este trabajo → esta en el board con `Worktree` seteado.

Para cualquier operacion de tracking (crear, mover, cerrar, linkear), `/tracking` tiene commands.md con las recipes.

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
  - GitHub Issues: close completed issues (`gh issue close`), create new ones (`gh issue create`)
    with the 3-section body template (Contexto / Detalle tecnico / Criterio de cierre).
    If the new issue belongs to an epic, link it via native sub-issues API:
    `gh api -X POST /repos/O/R/issues/<EPIC>/sub_issues -F sub_issue_id=<CHILD_databaseId>`.
  - Add the new issue to the Project and set `Worktree`:
    `gh project item-add 4 --owner lucaspecina --url <issue-url>`.
  - `CHANGELOG.md`: add entry for new functionality
  - `CURRENT_STATE.md`: update test count, modules, capabilities
  - `CLAUDE.md`: update project structure, conventions, "Epics activos" table if applicable
  - No stale references to deleted/renamed files
- Commit with descriptive message. Use `Refs #NNN ...` (commits do not close; `Closes` goes in the PR body).
- Push (ask user first if unsure)

### Step 5: What's next?
**MANDATORY. Right after commit+push.**

- Check the Project board Todo column (top = next priority):
  https://github.com/users/lucaspecina/projects/4
  Or via API: list open issues and identify which epic is most active.
- Present 1-3 concrete next steps to the user, in friendly Spanish.
  Not a dump of all issues — a curated suggestion of what makes sense NOW.
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

## Escenarios diversos check — OBLIGATORIO para cambios de diseno

**ANTES de disenar o implementar** cualquier cambio en scoring, compiler,
prompts, contratos, o IR: repasar mentalmente los escenarios diversos
(`research/synthesis/investigation_scenarios_rubric.md`).

No solo "X causa Y" — verificar que funciona para: system mapping,
structure discovery, descriptivo, predictivo, epistemologico, optimizacion,
multi-outcome, etc. Si solo funciona para causal simple, es un juguete.
Si mejora 3 tipos pero rompe 5, no vale. Flaggear ANTES de presentar.

## Report format

```
Tests:      PASS (N tests) / SKIP (doc-only)
Lint:       PASS / SKIP
E2E:        PASS / SKIP (reason)
Diagnostic: NOTE: should re-run /eval / N/A
Approval:   PENDING
```
