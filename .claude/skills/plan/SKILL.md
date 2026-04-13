---
name: plan
description: Review the implementation plan and project status. Use when the user asks about the project roadmap or what needs to be done next.
---

Review the current implementation plan and project status.

1. List open GitHub Issues: `gh issue list --state open --limit 30`
2. Read `CURRENT_STATE.md` for system context
3. Identify what's in progress (`status:in-progress`), what's next (`prio:now`, `prio:next`), blockers (`status:blocked`)
4. If the user provides arguments, focus on that specific area: $ARGUMENTS
