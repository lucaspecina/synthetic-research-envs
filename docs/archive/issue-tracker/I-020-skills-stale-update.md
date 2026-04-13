---
id: 20
title: Skills stale update — fix BN/legacy refs
status: done
type: hygiene
lane: hygiene
priority: now
created: 2026-04-10
origin: audit 2026-04-10
---

# I-020: Skills stale update — fix BN/legacy refs

## Status
- **Estado:** DONE
- **Cerrado:** 2026-04-10

## Diagnostico original (incorrecto en partes)
El diagnostico inicial decia que `codex-collab` referenciaba BN — falso.
La semantic layer que menciona es correcta (capa visible del sistema).

## Lo que realmente se arreglo

**Skills eliminados:**
- `phase/` — concepto obsoleto, duplicaba /plan + /precommit

**Skills actualizados:**
- `prompts` — quitado ejemplo `dag_construct vs dag_generate` (ahora solo `scm_construct`)
- `run` — `dag_construct` → `scm_construct`; `experiments/` → `results/`
- `eval` — quitada ref a archivo inexistente; `experiments/` → `results/`
- `status` — "per phase" → "per lane"
- `plan` — quitado "current phase" de descripcion
- `validate` — quitado `--solve` inexistente; fix "sin solver" (era `--oi --inspect`, ahora `--inspect`)

**Docs actualizados (parte del mismo audit):**
- `ARCHITECTURE.md` — quitado "modo Guided = exacto"
- `PROJECT.md`, `CURRENT_STATE.md` — actualizadas refs a criterios v1 cerrados
- `README.md` — `experiments/` → `results/`
- `research/README.md` — fix typo nombre archivo
- `generate_src.py` — `dag_construct` → `scm_construct`
- `TODO.md` — I-020 movido a RECENTLY CLOSED

## Fuera de scope (para I-021 o issue nuevo)
- 3 scripts hardcodeados (direct_to_atoms, test_c2_bundle, trace_e2e_03)
- Indexar 8 notes + 18 archive en research/README
- Codigo legacy en src/ (Score, StepScore, v1 SQ classes)
