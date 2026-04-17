---
name: tracking
description: USE WHENEVER creating, editing, closing, labeling, linking, or organizing GitHub issues, epics, sub-issues, or Project v2 board fields (Status, Worktree). ALSO when asked about epics, roadmap, priorities, or "what's next". Covers issue templates, sub-issue linking via native API, Project v2 Status/Worktree field updates (GraphQL), epic promotion, close reasons, and concurrent session coordination. This project's tracking source of truth is GitHub Project v2 — not raw Issues.
---

# SREG tracking workflow

**SOURCE OF TRUTH = GitHub Project v2 "SREG Roadmap"**
https://github.com/users/lucaspecina/projects/4

Every open issue MUST appear on the board with `Status` and `Worktree` fields set. If you touch an issue and don't sync the board, the board breaks and other sessions lose visibility.

For exact commands: see `commands.md`. For IDs and GraphQL templates: see `reference.md`.

## Modelo mental (los 3 conceptos)

| Concepto | Que es | Vida util |
|---|---|---|
| **Epic** | Meta concreta con criterio de cierre. No es label ni tema paraguas. | Semanas/meses |
| **Worktree** | Directorio fisico donde corre una sesion. Mecanismo de paralelizacion. Campo custom del Project. | Finito |
| **Issue** | Sub-issue de un epic (puede tener hijos) o issue concreta (1 PR). | Dias |

Reglas clave:
- **1 epic = 1 worktree es la buena practica recomendada** (no forzada). Si todo sale limpio, hay match 1:1. Casos raros (un worktree tocando varios epics en paralelo) son aceptables.
- **Anidacion permitida dentro del epic.** Estructura tipica:
  ```
  Epic: Suites de correctness (#26, worktree eval-suite)
    -> Suite 1 (#6)          <-- sub-issue con hijos
         -> tarea concreta (1 PR)
         -> tarea concreta (1 PR)
    -> Suite 2 (#7)          <-- sub-issue con hijos
         -> tarea concreta (1 PR)
    -> Suite 4 (#9)          <-- sub-issue con hijos
         -> tarea concreta (1 PR)
  ```
  GitHub soporta anidacion de sub-issues sin limite.
- **La hoja (la que cierra un PR) sigue siendo "1 issue = 1 PR"**. Lo que tiene hijos es un agrupador conceptual (equivale al viejo "hito").
- **Sub-issues via API nativa** de GitHub (NO "Part of #N" en body). Aplica a cualquier nivel.
- **Un issue puede ser standalone** (sin epic padre) para one-offs: bugs, docs, research parkeado.
- **Cuando splittear trabajo de un epic a otro epic separado**: cuando el trabajo es **orthogonal** al epic actual (toca otro componente arquitectonico) y tiene su propio criterio de cierre. Ejemplo real: los fixes del compiler descubiertos por Suite 2 se movieron a epic #36 `compiler-fix` (worktree separado) porque tocan el compiler, no el eval-suite.

## Arranque de sesion (primer check cuando la tarea toca tracking)

```bash
# 1. Donde estoy
pwd && git worktree list && git branch --show

# 2. Que hay activo en el board (Status + Worktree por item)
# Ver commands.md -> "query del board"

# 3. Que epic/issue corresponde a mi worktree actual
# Ver tabla "Epics activos" en CLAUDE.md + gh api /repos/O/R/issues/<EPIC>/sub_issues
```

## Los 2 campos obligatorios del board

| Campo | Valores | Cuando cambia |
|---|---|---|
| **Status** | `Todo` / `In Progress` / `Done` | Crear issue -> `Todo`. Empezar trabajo -> `In Progress` (mover AL EMPEZAR, no al final). Mergear PR / cerrar issue -> `Done` (auto). |
| **Worktree** | `eval-suite` / `qwen-benchmarks` / `rl-training-infra` / `main` / `compiler-fix` / `none` | Al crear (obligatorio). Rara vez cambia. |

**Prioridad** = orden manual en la columna `Todo` (drag&drop o reorder via API). **NO es label.**

## Template de body (obligatorio para epic o issue)

```markdown
## Contexto (para humanos)

<1-3 frases en español: que es, por que importa, cuando lo harias>

## Detalle tecnico (para Claude / sesiones)

<jerga, refs a codigo, decisiones, edge cases, links a research/>

## Criterio de cierre

<que tiene que pasar para estar hecho>
```

## Convenciones de titulo

- **Epic**: `Epic · <worktree> · <meta>` (ej: `Epic · compiler-fix · Mejorar el compiler post-diagnostico Suite 2`).
- **Sub-issue / standalone**: descriptivo, sin prefijo, < 70 chars.

## Labels (5 — no crear nuevos sin consultar)

| Label | Cuando |
|---|---|
| `bug` | Bug real |
| `blocked` | Esperando dependencia (comentar que bloquea) |
| `parked` | Idea abierta pero no activa |
| `research` | Analisis o sintesis, no produce codigo |
| `design` | Requiere diseno/decision antes de codear |

Sin `area:*` (el worktree ya cubre scope) ni `prio:*` (el orden en Todo cubre prioridad).

## Crear un epic (reactivo, no predictivo)

Crear epic SOLO si hay 3+ sub-issues concretos + semanas de trabajo + criterio de cierre claro + idealmente un worktree propio (buena practica).

**Reactivo, no predictivo**: empezar con issues sueltos; promover a epic cuando emerge el patron (ver commands.md -> "Promover sub-issue a epic").

**Cuando agrupar sub-issues dentro de un epic (nivel intermedio)**: si dentro de un epic se ven varios sub-issues que comparten un objetivo comun pero no lo suficiente para otro epic separado, crearlos como sub-issues-con-hijos (ej: "Suite 1" bajo epic #26 tiene sus propias tareas de implementacion). No hace falta marca especial — GitHub soporta el anidamiento nativo.

## Razones de cierre — Completed vs Not planned

- `gh issue close <N> --reason completed` — Se hizo. Va a la columna `Done`. **Usar esto para la mayoria.**
- `gh issue close <N> --reason "not planned"` — No se va a hacer (scope change, duplicado, replanteo). Queda cerrado pero NO aparece en Done. **Remover del board** con GraphQL `deleteProjectV2Item` para que no lo poluye.

## Comentarios en issues (obligatorios)

- **Al cerrar**: parrafo explicando que se hizo + link al PR mergeado.
- **Al bloquear**: que lo bloquea y que lo destrabaria.
- **Scope change**: si cambia alcance, documentar decision y por que.
- **Hand-off entre sesiones**: estado actual + que falta.

NO comentar para updates triviales ni discusiones largas (esas van a `research/notes/`).

## Flujo de trabajo: GitHub vs filesystem

**Regla**: GitHub Issues = superficie externa (visibilidad, tracking). Filesystem = superficie interna (pensamiento, debates, diseño, investigacion).

| Info | Donde |
|---|---|
| Trabajo concreto con criterio de cierre (1+ dias, 1+ PR) | **GitHub Issue** |
| Exploracion / investigacion / debate en curso | `research/notes/<scratch>.md` (efimero, puede borrarse) |
| Conclusiones estables que guian decisiones | `research/synthesis/<doc>.md` (canon, perdura) |
| Contexto sobre usuario / proyecto / como trabajamos | `memory/` (cross-session) |
| TODOs efimeros de la sesion actual | Task tool (no persiste) |
| Progreso en issue especifico | Comentario del issue |
| Debate sobre cambios de codigo | Comentario del PR |

**Flujo natural (va izquierda-a-derecha, no al reves):**

```
exploracion/debate      diseño/sintesis        trabajo concreto
research/notes/    ->   research/synthesis/ -> GitHub Issue
```

Una idea entra por `notes/`. Si se decanta → pasa a `synthesis/`. Cuando hay unidad PR-sized con criterio de cierre claro → recien ahi se vuelve issue. **No crear issues para ideas vagas ni investigacion abierta** (poluciona el board).

**Cross-linking** es el pegamento:
- Body de issue linkea a `research/synthesis/foo.md` cuando la justificacion vive ahi.
- Comentario de issue linkea a `research/notes/debate_X.md` si hubo debate.
- Docs de synthesis citan issues que motivaron / cerraron.

**Casos concretos:**
- Bug encontrado → issue con `bug`, directo (skip notes).
- "¿Y si probamos X?" → `research/notes/ideas.md`, NO issue todavia.
- Investigacion con 3 hipotesis → `research/notes/` → cuando hay fix concreto → issue `bug` linkeando a la nota.
- "Deberiamos rediseñar scoring" → debate en `notes/` → cuando se decanta → `synthesis/` → si requiere N PRs → epic con sub-issues linkeando al synthesis.

No crear issues para preguntas, discusiones, o trabajo < 1 dia.

## Sesiones concurrentes (multiples Claude en paralelo)

- El board es el punto de sync. Todas leen/escriben al mismo.
- Antes de empezar: verificar `Status`. Si esta `In Progress`, buscar otro issue.
- Mover a `In Progress` **al empezar, no al final**. Otras sesiones necesitan ver que esta tomado.
- Sesiones distintas = branches distintas. Nunca 2 sesiones misma branch.

## Issue workflow (codigo + PRs)

- **1 issue = 1 PR**.
- Branch: `issue/NNN-short-slug`.
- PR body empieza con `Closes #NNN`.
- Commits referencian con `Refs #NNN descripcion` (no cierra).
- Squash merge preferido.

## Flujo end-to-end

1. Project board view "Epics" -> elegir top del `Todo`.
2. Mover Status -> `In Progress` (ver commands.md).
3. Campo Worktree del item -> trabajar ahi (`cd .claude/worktrees/<nombre>`).
4. Codear. Commits con `Refs #NNN ...`.
5. PR con `gh pr create` + body `Closes #NNN`.
6. Merge -> issue cierra -> Project mueve a `Done` (auto).

## Mantener CLAUDE.md "Epics activos" sincronizada

La tabla en CLAUDE.md debe reflejar el estado real. Si creas/cerras epic o cambia worktree/criterio: actualizar la tabla en el mismo PR.

## Checklist antes de commit que toque tracking

- [ ] Issues cerradas -> Status `Done` (auto, verificar).
- [ ] Issues nuevas -> Status `Todo` + Worktree seteado + agregadas al board.
- [ ] Issues en curso -> Status `In Progress`.
- [ ] Sub-issues linkeadas via API nativa.
- [ ] Tabla "Epics activos" en CLAUDE.md refleja el estado actual.

## Referencias

- **`commands.md`** — Recipes exactos por situacion (crear, empezar, cerrar, linkear, promover, agregar worktree option).
- **`reference.md`** — Project ID, field IDs, option IDs, GraphQL templates, query de refresh.
