---
name: status
description: Concise project status overview via GitHub Project v2. Use when the user asks about progress, how things are going, or current focus.
---

Give a concise status overview using the **Project v2 board** as source of truth.

**Para comandos de tracking (query del board, IDs, etc.), usar la skill `/tracking`.**

## Steps

1. **Qué hay en `Status=In Progress` AHORA** — query del board (ver `/tracking reference.md`), filtrar por Status=In Progress.
2. **Top del `Todo` column** = próxima prioridad (prioridad es orden manual, no label).
3. **Progreso de epics abiertos**: para cada uno, `gh api /repos/.../issues/<EPIC>/sub_issues` y contar cerradas vs totales.
4. Últimas 3-5 entradas de `CHANGELOG.md` para contexto de momentum reciente.

## Reporte (español, una pantalla)

- Epics activos con progreso (ej: "Suites correctness: 1/3 sub-issues cerradas").
- Qué está `In Progress` ahora mismo.
- Qué está arriba del Todo (próxima prioridad).
- Últimos cambios del CHANGELOG.
- Blockers si hay (`blocked` label).

Concisa. No listar todo.
