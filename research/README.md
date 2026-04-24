# research/ — Indice canonico

> Este directorio contiene el trabajo de investigacion que alimenta las
> decisiones del proyecto. Algunos docs son **canonicos** (fuente de verdad
> activa). Otros son **notas** (working docs). Otros son **archive**
> (historico, no tocar).
>
> **Regla de oro:** si un doc no esta marcado CANON, no es fuente de
> verdad. Para saber el estado actual del proyecto, mira los CANON.

---

## Corte 1 — Por status (que es cada doc)

### Canonicos activos (synthesis/)

| Doc | Rol |
|---|---|
| `synthesis/thesis_evaluation_framework.md` | **CANON tesis.** Que hay que demostrar, metricas, suite, protocolo paper |
| `synthesis/sreg_training_transfer_protocol.md` | **CANON operativo.** Modelo, harness, suite final, BEFORE/TRAIN/AFTER |
| `synthesis/related_work_sandmle.md` | **CANON related work.** Comparacion con SandMLE (Zhou et al. 2026) |
| `synthesis/related_work_scigym.md` | **CANON related work.** Comparacion con SciGym (Duan et al. 2025) |
| `synthesis/related_work_sciagentgym.md` | **CANON related work.** Comparacion con SciAgentGym (Shen et al. 2026) — long-horizon tool-use |
| `synthesis/related_work_corral.md` | **CANON related work.** Corral (Rios-Garcia/Jablonka et al. 2026) — 25k runs, behavioral analysis via epistemic graphs, 95.7% human-LLM agreement. Justification empirica para training reasoning, no scaffolding. Fulltext del paper en `notes/corral_paper_fulltext.txt` |
| `synthesis/external_benchmarks_transfer_analysis.md` | **CANON suite.** Que mide cada benchmark, ejemplos, transferencia esperada de SREG |
| `synthesis/open_investigation_vision.md` | **CANON producto.** Vision de Open Investigation |
| `synthesis/oi_scoring_fundamentals.md` | **CANON scoring.** Salience map = piso, no techo. Verdad vs relevancia vs cobertura |
| `synthesis/sreg_scientific_coverage.md` | **CANON cobertura.** Que ciencia puede representar SREG hoy |
| `synthesis/investigation_scenarios_rubric.md` | **CANON escenarios.** Rubrica de validacion para diversidad de tipos |
| `synthesis/scientific_research_taxonomy.md` | **CANON taxonomia.** Framework general de tipos de investigacion |
| `synthesis/Doc1_Taxonomia_El_Mapa.md` | **CANON mapa.** Mapa operativo para clasificar investigaciones |
| `synthesis/oi_scoring_next_design.md` | **CANON diseno.** Sub-question scoring architecture |
| `synthesis/sq_v2_matching_spec.md` | **CANON matching.** Spec de SQ matching v2 (compile + match + agg) |
| `synthesis/eval_suite_framework.md` | **CANON evaluation.** 4 suites de evaluacion sistematica de SREG v1. (v1.5 re-encuadrará — ver `ARCHITECTURE.md`.) |
| `synthesis/eval_suite_translation.md` | **CANON evaluation.** Suite 2: Translation/Compilation — design doc. (Suite 2 queda obsoleta con v1.5 porque no hay compiler; el doc sirve como referencia histórica del approach.) |
| `synthesis/eval_suite_science_coverage.md` | **CANON evaluation.** Suite 3: Science Coverage — corpus, mundos, harness |
| `synthesis/v1_canonical_batch_manifest.md` | **CANON batch.** Manifest del v1 canonical batch (12 casos, avg 0.509). Movido de `results/v1_canonical_batch/MANIFEST.md` durante cleanup de repo 2026-04-23. |
| `synthesis/scoring_relevance_design.md` | **CANON relevance.** Verdad vs relevancia, opciones de matching |
| `synthesis/a27_answer_key_contract.md` | **CANON answer key.** Contrato del answer key rico |
| `synthesis/scm_migration_rationale.md` | **CANON migracion.** Por que SCM y no BN |
| `synthesis/research_case_design.md` | **CANON disenio.** Como diseniar SRCs que se sientan como investigacion real |
| `synthesis/interactivity_phase1_design.md` | **CANON v1.5 INTERACTIVIDAD (Fase 1).** Loop interactivo agente-Environment, 4 acciones primitivas (observe/intervene/stratify/simulate), budget visible, Case Writer restringe access_policy por caso. Comparativa con SciGym/Corral/Asta/etc. Ejemplo canónico Birth Weight Paradox paso a paso. |
| `synthesis/real_papers_patterns.md` | **CANON patrones.** Patrones consistentes en papers reales |

### Notas activas (notes/)

Material crudo o semi-crudo: debates, exploraciones, working docs, hallazgos
empiricos. **NO es canonico** — son insumos para futuras decisiones.

Lista no exhaustiva: ver `notes/` directamente. Items mas relevantes hoy:

- `notes/oi_pilot_analysis_batch1.md` — analisis de pilots OI
- `notes/p06_cap_decision_result.md` — **P06 resultado: cap=15 congelado para v1**
- `notes/p06_addendum_cap_decision.md` — P06 protocolo del experimento cap decision
- `notes/oi_compiler_design.md` — debate de arquitectura del compiler
- `notes/oi_investigation_gap.md` — investigation gap concept
- `notes/scm_task_primitives.md` — primitivas composicionales propuestas
- `notes/a21_compiler_ontology_investigation.md` — bug ontologia compiler
- `notes/a22_compiler_direct_to_atomicspec.md` — propuesta de compilacion directa
- `notes/a23_grammar_first_sq_and_compiler.md` — grammar-first para SQ
- `notes/s04_epistemic_ir_gap_analysis.md` — gap epistemologico evidencia empirica
- `notes/s03_extraction_diagnosis.md` — A/B test extraccion compiler
- `notes/brief_vs_eval_separation.md` — separacion brief vs eval
- `notes/indirect_measurement_design.md` — instrumentos como nodos del SCM
- `notes/open_investigation_case_analysis.md` — 10 dominios analizados
- `notes/sq_flow_and_dag_visibility_open_questions.md` — briefing 2026-04-14: quien ve el DAG en cada actor (orchestrator / SQ compiler / claim compiler), dudas D1-D8 destapadas por Suite 2 baseline
- `notes/rethink_sreg_2026-04-23.md` — **WORKING DOC activo.** Rediseño del flujo de SREG desde primeros principios: matar compiler runtime, rubricas graduadas + LLM judge con acceso al mundo ejecutable, abrir a ODEs/SDEs. Incorpora findings de Corral. Conversacion Claude+usuario+Codex 2026-04-19 → 2026-04-23. Aun no promovido a synthesis.
- `notes/corral_paper_fulltext.txt` — fulltext de Rios-Garcia/Jablonka et al. 2026 (arXiv:2604.18805), 4822 lineas. Referencia para citas. Synthesis canonico en `synthesis/related_work_corral.md`.
- `notes/compiler_v1_postmortem.md` — **ARCHIVAL.** Post-mortem del compiler v1 (epic #36, cerrado 2026-04-23). Root-cause taxonomy, progresion empirica v5-v18 (50.9%→83.6%), critica Codex, limites estructurales irresolubles. **Ideas trasladables a v1.5 extraidas en `notes/rethink_sreg_2026-04-23.md` seccion 11 "Lessons rescatadas".** Codigo original en branch `origin/worktree-compiler-fix`.

### Archive (historico, read-only)

> **Archives en el repo:**
> - `research/archive/` — research obsoleto/superseded (este dir).
> - `docs/archive/` — docs del proyecto (TODOs legacy, architecture v1, issue-tracker local pre-GitHub).

| Doc | Por que esta en archive |
|---|---|
| `archive/suite2_compiler_v1/` | **20 archivos** (13 JSON + 7 MD) del diagnóstico del compiler v1 (Suite 2). Incluye baselines, audits Flow A/B, strategies, diagnostics D1-D4, per-family breakdown. Obsoletos con v1.5 (compiler eliminado). Código con iteraciones v3-v18 en branch `origin/worktree-compiler-fix`. |
| `archive/benchmark_analysis.md` | Research landscape denso de benchmarks (Claude+GPT consolidado). Background util para paper, NO canon operativo. Las decisiones canonicas viven en `synthesis/sreg_training_transfer_protocol.md` |
| `archive/benchmark_results.md` | BEFORE scores corridos con `gpt-5.2-chat`, NO con Qwen3-8B. **No valido para tesis** — re-correr antes de usar como baseline. Ver banner del archivo |
| `archive/scientific_benchmarks_policy_claude.md` | Research exploratorio original consolidado en `benchmark_analysis.md` |
| `archive/scientific_benchmarks_policy_gpt.md` | Research exploratorio original consolidado en `benchmark_analysis.md` |
| `archive/eval_strategy.md` | Estrategia de eval anterior, superseded por `synthesis/thesis_evaluation_framework.md` |
| `archive/eval_design_notes.md` | Notas de diseno de eval anteriores, superseded |
| `archive/world_design_legacy.md` | Disenio de mundos legacy (BN era), superseded por SCM |
| `archive/sreg_v2_design_findings.md` | Findings de la era v2, superseded |
| `archive/s06_*` | Investigacion S06 archivada |

---

## Corte 2 — Por pregunta (si necesitas X, anda a Y)

### v1.5 Rediseno (ACTIVO, rama dev)

| Necesito... | Doc canonico |
|---|---|
| Arquitectura completa de v1.5 (spec vivo) | `ARCHITECTURE.md` (root) |
| Historia del rediseno (debates, Codex, decisiones) | `notes/rethink_sreg_2026-04-23.md` |
| Post-mortem compiler v1 (por que lo matamos) | `notes/compiler_v1_postmortem.md` |

### Tesis y paper

| Necesito... | Doc canonico |
|---|---|
| Que hay que demostrar para defender la tesis | `synthesis/thesis_evaluation_framework.md` |
| Modelo, harness, suite, training config | `synthesis/sreg_training_transfer_protocol.md` |
| Related work / SandMLE / RL-only vs SFT+RL | `synthesis/related_work_sandmle.md` |
| Related work / SciGym / loop iterativo en biologia | `synthesis/related_work_scigym.md` |
| Related work / SciAgentGym / long-horizon tool-use | `synthesis/related_work_sciagentgym.md` |
| Related work / Corral / behavioral analysis + epistemic graphs | `synthesis/related_work_corral.md` |
| Rediseno del flujo de SREG (working doc) | `notes/rethink_sreg_2026-04-23.md` |
| Que mide cada benchmark + ejemplos + transfer esperado | `synthesis/external_benchmarks_transfer_analysis.md` |
| Por que SciGym esta en Tier 1 ahora | `synthesis/thesis_evaluation_framework.md` (seccion "Por que SciGym esta en Tier 1") |
| Background denso de benchmarks (para writing) | `archive/benchmark_analysis.md` (background, no canon) |
| BEFORE scores viejos (no validos hoy) | `archive/benchmark_results.md` (con banner) |

### Producto y scoring

| Necesito... | Doc canonico |
|---|---|
| Vision de Open Investigation | `synthesis/open_investigation_vision.md` |
| Principios de scoring (verdad/relevancia/cobertura) | `synthesis/oi_scoring_fundamentals.md` |
| Cobertura cientifica (que cubre SREG y que no) | `synthesis/sreg_scientific_coverage.md` |
| Taxonomia de investigacion | `synthesis/scientific_research_taxonomy.md` + `synthesis/Doc1_Taxonomia_El_Mapa.md` |
| Escenarios diversos para validacion E2E | `synthesis/investigation_scenarios_rubric.md` |
| **4 suites de evaluacion sistematica** | `synthesis/eval_suite_framework.md` |
| **Science Coverage suite (diseño)** | `synthesis/eval_suite_science_coverage.md` |
| Spec de SQ matching (compile + match + agg) | `synthesis/sq_v2_matching_spec.md` |
| Diseno del answer key | `synthesis/a27_answer_key_contract.md` |
| Por que SCM y no BN | `synthesis/scm_migration_rationale.md` |

### Casos y diseno

| Necesito... | Doc canonico |
|---|---|
| Como diseniar SRCs que parezcan investigacion real | `synthesis/research_case_design.md` |
| Patrones que aparecen en papers reales | `synthesis/real_papers_patterns.md` |

### Investigaciones empiricas activas (notes/)

Para findings empiricos en curso (compiler bugs, modos semanticos, A21/A22/A23,
S03/S04, etc.) ver `notes/`. Estos no son canon — son insumo.

---

## Regla de promocion

1. Idea nueva, debate, exploracion -> `notes/`
2. Se investiga y consolida -> `synthesis/`
3. Si se vuelve decision del proyecto -> se promueve a `PROJECT.md` o
   `ARCHITECTURE.md`
4. Si implica trabajo pendiente -> GitHub Issue (`gh issue create`)
5. Si se implementa -> `CURRENT_STATE.md` + `CHANGELOG.md`

El archivo de research queda como registro historico — no se borra, pero
deja de ser la fuente de verdad para esa decision.

---

## Que NO hacer

- **No citar `archive/` como fuente de verdad activa.** Es background.
- **No promover docs viejos a `synthesis/` sin actualizarlos.** Si hace
  falta material de archive en el paper, **extraer** lo vigente al canon
  en lugar de mover el archivo entero.
- **No agregar docs nuevos a `synthesis/` sin actualizar este indice.**
  Si rompes esto, este README deja de ser util.
