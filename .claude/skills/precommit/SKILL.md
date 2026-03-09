---
name: precommit
description: Run the full pre-commit checklist before committing. Use BEFORE every git commit to verify tests, lint, docs, and get user approval.
disable-model-invocation: true
---

Run the mandatory pre-commit checklist. Do NOT commit until all steps pass and the user approves.

## Steps (in order)

1. **Tests**: Run `pytest tests/ -q`. ALL must pass. If any fail, stop and fix.

2. **Lint**: Run `ruff check` on modified files only (check with `git diff --name-only`).
   Fix any new errors introduced by this commit. Pre-existing errors (like E402 in orchestrator) are OK.

3. **E2E validation** (if the commit adds features or changes behavior):
   - Write an inline script (`python -c`) that exercises the new feature as a user would.
   - Run with at least 5 different configurations (vary seeds, params, etc.).
   - Read the output carefully. Do the values make sense?
   - Report any anomalies.
   - Skip this step for doc-only or trivial changes.

4. **Docs check** — verify each is up to date:
   - `TODO.md`: completed tasks marked `[x]`? New tasks added?
   - `CHANGELOG.md`: entry added for new functionality?
   - `CURRENT_STATE.md`: test count, modules table, capabilities still accurate?
   - `CLAUDE.md`: project structure, test count, current state still accurate?
   - No stale references to deleted/renamed files.

5. **Explain to user** (MANDATORY): Before committing, use `/explain` to present the
   changes to the user. Wait for their approval.

6. **Report**: Show a summary table:
   ```
   Tests:     PASS (N tests)
   Lint:      PASS (no new errors)
   E2E:       PASS / SKIP (reason)
   Docs:      PASS (list which were updated)
   Approval:  PENDING
   ```

Do NOT run `git commit` until the user explicitly approves.
