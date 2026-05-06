# research/ — Indice canonico

> Este directorio contiene el trabajo de investigacion que alimenta las
> decisiones del proyecto. Algunos docs son **canonicos** (fuente de verdad
> activa). Otros son **notas** (working docs). Otros son **archive**
> (historico, no tocar).
>
> **Regla de oro:** si un doc no esta marcado CANON, no es fuente de
> verdad. Para saber el estado actual del proyecto, mira los CANON.

---

## Estado actual del proyecto

| Versión | Paradigma | Formalismos | Epic |
|---|---|---|---|
| **v1.5** | estático (single-turn) | SCM + ODE + SDE | [#63](https://github.com/lucaspecina/synthetic-research-envs/issues/63) |
| **v2** | interactivo Sherlock multi-turno | SCM + ODE + SDE | [#64](https://github.com/lucaspecina/synthetic-research-envs/issues/64) |

ODE/SDE entran ya en v1.5: la dinámica del mundo es ortogonal a la
interactividad del agente. Lo que v2 agrega es el loop multi-turno
agente-Environment.

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
| `synthesis/eval_suite_framework.md` | **CANON evaluation.** 4 suites de evaluacion sistematica de SREG v1. (v1.5 re-encuadrará — ver `ARCHITECTURE.md`.) |
| `synthesis/eval_suite_science_coverage.md` | **CANON evaluation.** Suite 3: Science Coverage — corpus, mundos, harness |
| `synthesis/scm_migration_rationale.md` | **CANON migracion.** Por que SCM y no BN |
| `synthesis/research_case_design.md` | **CANON disenio.** Como diseniar SRCs que se sientan como investigacion real |
| `synthesis/sherlock_v2_design.md` | **CANON v2 SHERLOCK.** Loop interactivo agente-Environment multi-turno: 4 acciones primitivas (observe/intervene/stratify/simulate), budget visible, Case Writer restringe access_policy. Comparativa con SciGym/Corral/Asta/etc. Ejemplo Birth Weight Paradox paso a paso. (Renombrado desde `interactivity_phase1_design.md` 2026-04-25 al separar ODE/SDE — que entran en v1.5 — del multi-turno — que queda en v2.) |
| `synthesis/real_papers_patterns.md` | **CANON patrones.** Patrones consistentes en papers reales |
| `synthesis/world_design_techniques_survey.md` | **CANON survey.** Técnicas de diseño de mundos/tareas tomadas de fuera del dominio: PCG en videojuegos, mystery design, UED/RL, LLM-as-environment-designer. 12 técnicas transferibles priorizadas + §5.b adiciones del SOTA review (5 prácticas: shortcut resistance, difficulty band, evidence logging, parametric variations, semantic triplets). Sub-docs detallados en `notes/world_design_*.md` |
| `synthesis/sota_synthetic_envs_for_rl.md` | **CANON SOTA.** Catálogo de ~30 proyectos del estado del arte en generación/validación de entornos sintéticos para RL (Endless Terminals, SWE-Gym, R2E-Gym, CLadder, DiscoveryWorld, AgentClinic, OrgForge-IT, Absolute Zero, CodeScientist, etc.). Análisis profundo de los 8 más relevantes para SREG + síntesis cross-cutting + recomendaciones (qué adoptar / adaptar / NO adoptar / gaps). Posiciona SREG en el cuadrante "investigación interactiva multi-paso + verificación formal causal" (gap real en la literatura). |

### Notas activas (notes/)

Material crudo o semi-crudo: debates, exploraciones, working docs, hallazgos
empiricos. **NO es canonico** — son insumos para futuras decisiones.

- `notes/v1_5_debates.md` — **WORKING DOC v1.5.** 10 rondas de debate Claude/Codex/usuario sobre la arquitectura v1.5 (rubric+juez+answer key) y v2 (Sherlock). Source of truth para historia de decisiones.
- `notes/rethink_sreg_2026-04-23.md` — Rediseño del flujo desde primeros principios: matar compiler runtime, rubricas graduadas + LLM judge, abrir a ODE/SDE. Origen del v1.5.
- `notes/compiler_v1_postmortem.md` — Post-mortem del compiler v1 (epic cerrado). Root-cause taxonomy, progresion empirica v5-v18 (50.9%→83.6%), limites estructurales irresolubles.
- `notes/corral_paper_fulltext.txt` — Fulltext de Rios-Garcia/Jablonka et al. 2026 (4822 lineas). Synthesis canonico en `synthesis/related_work_corral.md`.
- `notes/scm_task_primitives.md` — primitivas composicionales propuestas
- `notes/brief_vs_eval_separation.md` — separacion brief vs eval
- `notes/indirect_measurement_design.md` — instrumentos como nodos del SCM
- `notes/open_investigation_case_analysis.md` — 10 dominios analizados
- `notes/real_investigations_analysis.md` — análisis de investigaciones reales
- `notes/world_design_pcg.md` — Vertical 1 del survey: PCG en videojuegos (WFC, ASP, MAP-Elites, Spelunky, Dwarf Fortress, NMS, Caves of Qud)
- `notes/world_design_mystery.md` — Vertical 2 del survey: mystery & discovery design (Obra Dinn, Outer Wilds, Three-Clue Rule, Gumshoe, Brindlewood Bay)
- `notes/world_design_ued.md` — Vertical 3 del survey: UED & open-endedness en RL (POET, PAIRED, ACCEL, MAP-Elites, XLand, Genie)
- `notes/world_design_llm.md` — Vertical 4 del survey: LLM-as-environment-designer 2023-2026 (GenSim, RoboGen, Eureka, Voyager, AI Scientist, Auto MC-Reward)

### Archive (historico, read-only)

> **Archives en el repo:**
> - `research/archive/` — research obsoleto/superseded (este dir).
> - `research/archive/pre_v1_5/` — docs y notes pre-v1.5 movidos durante el cleanup 2026-04-25.
> - `docs/archive/` — docs del proyecto (TODOs legacy, architecture v1, issue-tracker local pre-GitHub).

| Subdir / Doc | Contiene |
|---|---|
| `archive/pre_v1_5/` | 22 docs pre-v1.5 movidos: contratos antiguos (a27_answer_key_contract, sq_v2_matching_spec), scoring v1 (scoring_relevance_design), batch v1 (v1_canonical_batch_manifest), suite 2 translation, working notes del compiler/IR (a21-a24, oi_compiler_design, s03-s05, p06_*), pilot OI batch1, etc. Superseded por v1.5. |
| `archive/suite2_compiler_v1/` | **20 archivos** del diagnóstico del compiler v1 (Suite 2). Obsoletos con v1.5 (compiler eliminado). Código original en branch `origin/worktree-compiler-fix`. |
| `archive/benchmark_analysis.md` | Research landscape denso de benchmarks (Claude+GPT consolidado). Background util para paper. |
| `archive/benchmark_results.md` | BEFORE scores corridos con `gpt-5.2-chat`, NO con Qwen3-8B. **No valido para tesis** — re-correr antes de usar como baseline. |
| `archive/scientific_benchmarks_policy_*.md` | Research exploratorio original consolidado en `benchmark_analysis.md`. |
| `archive/eval_strategy.md`, `archive/eval_design_notes.md` | Estrategia/notas de eval anteriores, superseded. |
| `archive/world_design_legacy.md` | Disenio de mundos legacy (BN era), superseded por SCM. |
| `archive/sreg_v2_design_findings.md` | Findings de la era v2 (concepto distinto del v2 actual), superseded. |
| `archive/s06_*` | Investigacion S06 archivada. |

---

## Corte 2 — Por pregunta (si necesitas X, anda a Y)

### v1.5 + v2 (ACTIVO, rama dev)

| Necesito... | Doc canonico |
|---|---|
| Arquitectura completa de v1.5 (spec vivo) | `ARCHITECTURE.md` (root) |
| Diseño v2 Sherlock (interactividad multi-turno) | `synthesis/sherlock_v2_design.md` |
| Historia del rediseno (debates, Codex, decisiones) | `notes/v1_5_debates.md` + `notes/rethink_sreg_2026-04-23.md` |
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
| Que mide cada benchmark + ejemplos + transfer esperado | `synthesis/external_benchmarks_transfer_analysis.md` |

### Producto y scoring

| Necesito... | Doc canonico |
|---|---|
| Vision de Open Investigation | `synthesis/open_investigation_vision.md` |
| Principios de scoring (verdad/relevancia/cobertura) | `synthesis/oi_scoring_fundamentals.md` |
| Cobertura cientifica (que cubre SREG y que no) | `synthesis/sreg_scientific_coverage.md` |
| Taxonomia de investigacion | `synthesis/scientific_research_taxonomy.md` + `synthesis/Doc1_Taxonomia_El_Mapa.md` |
| Escenarios diversos para validacion E2E | `synthesis/investigation_scenarios_rubric.md` |
| 4 suites de evaluacion sistematica | `synthesis/eval_suite_framework.md` |
| Science Coverage suite (diseño) | `synthesis/eval_suite_science_coverage.md` |
| Por que SCM y no BN | `synthesis/scm_migration_rationale.md` |

### Casos y diseno

| Necesito... | Doc canonico |
|---|---|
| Como diseniar SRCs que parezcan investigacion real | `synthesis/research_case_design.md` |
| Patrones que aparecen en papers reales | `synthesis/real_papers_patterns.md` |

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
