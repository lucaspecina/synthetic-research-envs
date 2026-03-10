---
name: phase
description: Start working on a specific implementation phase. Reads TODO, plans the work, asks for confirmation, then implements following the commit workflow.
disable-model-invocation: true
---

Start working on a specific implementation phase.

1. Read `TODO.md` to see pending tasks for the requested area: $ARGUMENTS
2. Read `CURRENT_STATE.md` for what exists today
3. Check that prerequisite work is complete
4. Present the plan: what files to create, what to implement, in what order
5. Ask for confirmation before starting implementation
6. Implement following the **commit workflow** (`/precommit`):
   - Make changes → tests + validation → present to user → get approval → update docs → commit
