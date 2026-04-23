# Session brief — worktree `compiler-fix`

> Este archivo es el punto de entrada para cualquier sesion nueva de Claude Code
> en este worktree. Leer antes de tocar codigo o issues.

## Tu rol

Ejecutar el **epic #36** — "Mejorar el compiler post-diagnostico Suite 2".

Tres sub-issues abiertas:

| Issue | Titulo | Rama |
|---|---|---|
| #32 | Compiler: arreglar abstain bug | **A** (primera) |
| #34 | Compiler: agregar recipe exemplars (arm_kinds, anti-adjust-swap, assertion-polarity) | **C** (segunda, con N-ablation staircase N=0/4/8/12) |
| #33 | Compiler: alinear contratos y taxonomia (baseline/observe, condition.values) | **B** (tercera) |

**Orden sugerido: A -> C -> B** (decision del closure package de Suite 2, 2026-04-18).

**Criterio de cierre del epic (#36):**
- Suite 2 effective pass rate >= 50%
- `arm_kinds` accuracy >= 70%
- Compiler abstiene correctamente (sin false positives ni false negatives)

## Antes de codear

1. **Leer el contexto en GitHub:**
   ```bash
   gh issue view 36   # epic
   gh issue view 32   # primer issue (abstain)
   gh issue view 34   # segundo (exemplars)
   gh issue view 33   # tercero (taxonomy)
   ```

2. **Leer la estrategia detallada y los audits:**
   - `research/synthesis/suite2_compiler_improvement_strategy.md` — plan completo
   - `research/synthesis/suite2_claim_compiler_audits.md` — Flow A audits (44% coherent, 36% wrong_claim)
   - `research/synthesis/suite2_sq_dag_coherence_audit.md` — Flow B audits (47% wrong_claim)
   - `research/synthesis/suite2_compiler_baseline.md` — baseline v2 (31% effective pass)
   - `research/synthesis/suite2_diag_d2_per_family_slots.md` — per-family bottlenecks

3. **Consultar la skill `/tracking`** (auto-invocable) para cualquier operacion de issues, Project v2, sub-issues, Worktree field, etc. Tiene `reference.md` con IDs y `commands.md` con recipes.

4. **Chequear el estado del board:**
   ```bash
   # Todos los items del Project con Status + Worktree
   # Ver commands.md del skill /tracking ("Query del board")
   ```

## Convenciones

- **1 issue concreta = 1 PR**. Branch `issue/NNN-slug`.
- PR body empieza con `Closes #NNN` (cierre automatico al mergear).
- Commits referencian con `Refs #NNN descripcion` (no cierran).
- Al empezar cada sub-issue: **mover Status -> In Progress** en el Project ANTES de codear.
- Labels disponibles: `bug`, `blocked`, `parked`, `research`, `design`. Nada mas.
- Template de body obligatorio (3 secciones): Contexto (humanos) / Detalle tecnico (Claude) / Criterio de cierre.

## Modo de trabajo

**Colaborativo** (default): contar que haces paso a paso en español, consultar antes de avanzar, NO commitear sin OK explicito del usuario, mostrar los cambios antes.

**Codex review mandatorio** para cambios de codigo grandes. Thread activo en `.codex-thread.md` (threadId `019da2e8-1696-7d92-bb72-72104be24da9`).
- Reusar con `codex-reply` (MCP).
- CLAUDE LIDERA, CODEX ASESORA — formar opinion propia antes de consultar.

## Contexto historico clave

- **Main acaba de recibir el merge grande de eval-suite** (commit `110c4e1`, 2026-04-18). Toda la infraestructura de Suite 1/2/4 + audits esta disponible.
- **Smoke E2E post-merge** (2026-04-18) con 3 casos diversos (system mapping, heterogeneity, predictive): correctness 0.33-0.78, coverage 0.50-0.76. Confirma que el compiler es el bottleneck del ceiling.
- **Tracking esta en GitHub Project v2** (https://github.com/users/lucaspecina/projects/4), no en archivos locales. `Status` + `Worktree` campos custom.
- **Skill `/tracking` es source of truth** del workflow de issues/epics. Auto-invocable.

## Lo que NO tenes que hacer

- No tocar otros epics (#26 eval-suite, #29 science-coverage, #30 qwen-benchmarks, #31 rl-training-infra) — cada uno tiene su propio worktree.
- No crear labels nuevos.
- No cambiar el modelo de tracking sin consultar.
- No pushear sin aprobacion explicita del usuario.
- No correr `pytest tests/` entero — solo el test del archivo modificado, una vez.

## Empezar

Primer paso concreto:

```bash
gh issue view 36 && gh issue view 32
# Leer la estrategia
cat research/synthesis/suite2_compiler_improvement_strategy.md
# Presentar un plan al usuario para arrancar #32 (Rama A, abstain bug)
```

Good luck.
