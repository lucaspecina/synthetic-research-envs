---
id: 20
title: Skills stale update — fix BN/legacy refs
status: open
type: hygiene
lane: hygiene
priority: now
created: 2026-04-10
origin: audit 2026-04-10
---

# I-020: Skills stale update — fix BN/legacy refs

## Status
- **Estado:** diagnosticado durante release audit
- **Ultimo resultado:** 3 skills con refs legacy, 1-2 posiblemente obsoletas
- **Proximo paso:** actualizar o eliminar skills criticas

## Pregunta
Varias skills del proyecto referencian conceptos eliminados (BN, semantic
layer, tools viejas, fases obsoletas). Hay que limpiar para que no confundan
a sesiones futuras.

**Criticas (rompen o confunden hoy):**
- `codex-collab` — referencia "BN" y "semantic layer"
- `prompts` — referencia tools viejas (dag_construct, world_check, etc.)
- `phase` — referencia fases del TODO que ya no existen

**Evaluar:**
- `run` — verificar que refs a tools y pipeline son correctas
- `eval` — verificar que el proceso descrito matchea v1
- `rescore` — verificar que refs a data structures son correctas

**Inútiles / legacy muerto:**
- Evaluar si `phase` tiene sentido post-v1 o debe eliminarse
