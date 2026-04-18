---
id: 26
title: Claim compiler recipe exemplars (D6-D8)
status: open
type: design
lane: scoring
priority: next
created: 2026-04-14
related: [I-003, I-007]
origin: research/synthesis/suite2_compiler_baseline.md
---

# I-026: Claim compiler recipe exemplars

## Status
- **Estado:** design question with empirical evidence from Suite 2
  baseline (2026-04-14).
- **Ultimo resultado:** diagnostic A/B/C sobre 3 casos confirma que el
  bottleneck del claim compiler es **recipe gap** (composición), no
  recognition gap ni capability gap. Un worked example abstracto arregló
  el caso de confounding; mediación y heterogeneidad requieren exemplars
  más refinados.
- **Proximo paso:** diseñar protocolo de eval para validar mejoras de
  prompt SIN overfitear a los 3 casos testeados.

## Pregunta (D6-D8)

Suite 2 baseline mostró 31% effective pass rate del claim compiler sobre
55 gold targets. El diagnóstico A/B/C (`scripts/prompt_diagnostic.py`)
separó:

- **Recipe gap (A vs B):** exemplar abstracto en system prompt mejora.
- **Recognition gap (A vs C):** hint solo no mejora.
- **Capability gap:** no observado para confounding; posible para
  heterogeneidad (condition_on omitido incluso con exemplar).

**D6.** ¿Cuál es el protocolo correcto para revisar el prompt de Flow A
**sin overfitear** a los 3 casos diagnosticados? Opciones:
- Held-out split sobre los 55 gold targets de Suite 2.
- Nueva batería de claims generativa (LLM-generated), con verificational
  equivalence contra gold analítico.
- Suite 2 como test set fijo + nuevo dev set para iteración.

**D7.** ¿Alcanza con pattern exemplars, o hace falta pipeline de dos
pasos (extracción + composición)? Codex opinó: para separar "usar DAG
para componer" de "usar DAG para corregir" hace falta pipeline de dos
pasos. Pero nuestro diagnostic no testeó esa arquitectura.

**D8.** ¿Dónde viven los exemplars? Opciones:
- Inline en `oi_extraction.py::compile_claim_direct` system prompt.
- Archivo separado `src/sreg/prompts/claim_compiler_exemplars.py`.
- Data-driven: catálogo de patterns con template + exemplar + contract.

## Alcance

- Fuera de scope de esta issue: implementar el fix. Primero diseño
  + protocolo de eval.
- Scope propuesto:
  - (a) Diseñar eval protocol (D6).
  - (b) Armar held-out vs dev split sobre Suite 2.
  - (c) Iterar prompt con exemplars sobre dev set, medir sobre held-out.
  - (d) Decidir arquitectura (D7) si el A/B con exemplars llega a ~60%+
    pass rate pero no más.

## Links
- Suite 2 baseline: `research/synthesis/suite2_compiler_baseline.md` §3-4
- Briefing interno: `research/notes/sq_flow_and_dag_visibility_open_questions.md` §3
- Scripts: `scripts/prompt_diagnostic.py`, `scripts/analyze_compiler_results.py`
- Dump de fallos: `research/synthesis/compiler_baseline_failures.json`
- Issue pre-existente: I-003 (claim compiler grammar-direct — ya
  completada a nivel migración; esta issue es sobre mejorar el prompt
  del grammar-direct actual).
