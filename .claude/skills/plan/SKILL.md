---
name: plan
description: Review the implementation plan and project status via GitHub Project v2. Use when the user asks about the roadmap, what's next, or epic progress.
---

Review the current plan using the **Project v2 board** as source of truth.

**Para todos los comandos de tracking (query del board, listar epics, sub-issues, etc.), usar la skill `/tracking`** — reference.md tiene los IDs y queries, commands.md tiene las recipes.

## Steps

1. **Query del board** (ver `/tracking reference.md` -> "Query del board") — da Status + Worktree por item.
2. **Listar epics abiertos**: `gh issue list --state open --search "Epic in:title" --json number,title`.
3. **Para cada epic de interes, listar sub-issues** (ver `/tracking reference.md` -> "Sub-issue API").
4. **Leer `CURRENT_STATE.md`** para contexto del sistema.
5. Si `$ARGUMENTS`, focus en ese epic/worktree.

## Qué reportar (español, breve)

- **Epics activos** con progreso (sub-issues cerradas / totales).
- **Standalones abiertos** relevantes.
- **Top del Todo column** (eso es la prioridad actual).
- Si el usuario dio un `$ARGUMENTS`, zoom sobre ese epic/worktree.

Curar, no dumpear. El usuario quiere un read del proyecto, no un listado exhaustivo.
