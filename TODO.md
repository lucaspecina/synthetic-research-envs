# SREG — TODO

> Single source of truth for task tracking.
> Statuses: `[ ]` pending | `[~]` in progress | `[x]` done | `[-]` cancelled
> Vision and scope: see PROJECT.md

## Done — v0+v1 (Etapa 1: motifs curados)
- [x] Pydantic data contracts (World, Episode, Task, Score, etc.)
- [x] World generation + validation (latent_preference template, WorldCheckTool)
- [x] Teacher solver (exact Bayesian inference, optimal actions, >90% accuracy)
- [x] Episodes, tasks, verifier, EpisodeRunner
- [x] LLM Orchestrator (world generation via tool calling)
- [x] Semantic layer (names, narrative, data presentation, ResearchProblem)
- [x] LLM Agent solver (observe/submit loop, comparison with teacher/random)
- [x] End-to-end pipeline: orchestrator -> agent -> score (scripts/test_e2e.py)
- [x] Teacher trajectory export as JSONL (problem, actions, observations, posteriors)
- [x] Batch evaluation: generate N problems programmatically, run agent + teacher, collect metrics
- [x] Summary report: agent vs teacher vs random across difficulty levels
- [x] Causal chain template (with semantic layer from start)
- [x] Fork/collider template (with semantic layer from start)
- [x] `next_best_observation` task type
- [x] `hypothesis_selection` task type
- [x] Multiple evaluations per problem: same world generates all 3 task types together

## Loose ends (v0+v1)
- [ ] Update demo script and notebook
- [x] Run batch eval across varying parameters (nodes, edge_strength, budget)
  > Done via `scripts/batch_sweep.py` (336 worlds). See WORLD_DESIGN.md "Batch sweep".

## Known issues (from E2E testing + batch sweep)
- [ ] Agent submit format: LLM sends flat keys instead of `{"distribution": {...}}`, wastes 1 turn on retry every time
- [ ] Agent worse than random on 8-node worlds: bad inference when more variables are involved (soil case KL 4.21 vs random 0.30)
- [ ] Orchestrator ignores difficulty in goal: always generates "easy" regardless of "hard difficulty" in prompt
- [ ] `apply_semantics` always fails first call: LLM sends empty `node_renames`, then retries correctly (wastes 1 API call)
- [ ] Agent variable selection suboptimal: doesn't pick most informative variables (different order than teacher)
- [ ] NBO trivial tasks: at 6-8 nodes, NBO is non-trivial 88-48% of the time. At 10-12 nodes improves to 52-53%. Fix in `_next_best_observation_task`: check `max(ig_ranking.values()) > 0`, resample with less evidence if not. Cap retries.
- [ ] Hypothesis near-indistinguishable: batch sweep confirmed this is worst at es=0.9 (43% distinguishable) and best at es=0.7 (87%). The "prior" distractor becomes identical to posterior when evidence confirms prior strongly. Fix: filter by min KL > 0.05 or replace reversed distractor with Dirichlet sample.
- [-] preferential_attachment: 0% WorldCheck pass across all configs. Eliminated as active generator. (See batch sweep findings in WORLD_DESIGN.md.)

## v2 — Composicion controlada + research cases (Etapa 2)

> Estrategia de investigacion y diseno detallado en **`WORLD_DESIGN.md`**.

### Prototipo DAGSpec (slice minimo — completo)
- [x] `DAGSpec` + `DAGNodeSpec` models: Pydantic contract with validations (acyclic, max parents <=4, required types)
- [x] `cpd_gen.py`: extract shared CPD generation from 3 templates (eliminate copy-paste)
- [x] `CustomTemplate`: accepts DAGSpec, generates valid CPDs using generic edge_strength logic → World
- [x] WorldCheck extended: max parents check + treewidth metric (warning, not failure)
- [x] `generate_custom()` method in WorldGenTool (separate from `generate()` — API to be unified, but both input paths are permanent)
- [x] All 3 task types work with custom worlds (TaskGenTool + TaskBundle)
- [x] Tests: custom worlds with 5-15 nodes, heterogeneous states, multiple latents (81 new tests)
- [x] E2E validation: 12-15 node worlds, teacher improves over prior + beats random, documented findings in WORLD_DESIGN.md

### QualitySuite v2 — metricas rediseñadas (PRIORIDAD)
> Hallazgo critico: la metrica original teacher_beats_prior (KL vs one-hot del true state)
> castiga inferencia correcta cuando el sample es atipico. Ver WORLD_DESIGN.md "Hallazgo critico".

- [x] QualitySuite v1: Capas A+B+C implementadas con metricas originales (44 tests)
- [x] Documentar hallazgo critico y metricas rediseñadas en WORLD_DESIGN.md
- [x] Rediseñar Capa B con multi-rollout:
  - [x] Cambiar `compute_task_quality()` para aceptar lista de seeds (K=5-10 rollouts)
  - [x] Agregar metricas de diseno: `budget_ratio` (budget / observables con path al target)
  - [x] Agregar `mean_entropy_reduction` como metrica principal de belief quality
  - [x] Agregar `mean_nll_improvement`, `mean_teacher_nll`, `mean_prior_nll`, `mean_random_nll`
  - [x] Agregar `teacher_beats_random_rate` (fraccion de rollouts)
  - [x] Agregar `nbo_nontrivial_rate` y `hyp_distinguishable_rate` (multi-rollout)
  - [x] Renombrar metricas viejas: `teacher_kl` → `sampled_nll_teacher`, etc. (diagnostico)
  - [x] Redefinir `useful_bundle`: entropy_reduction > 0.1 AND 2 de 3 (nbo, hyp, budget_ratio)
- [x] Ajustar Capa C: reemplazar `ig_gap_std` por `entropy_reduction_std`
- [x] Actualizar tests para nuevas metricas (48 tests)
- [x] E2E con LLM: verificar que las metricas nuevas dan resultados coherentes
- [x] Recorrer batches grandes y comparar generators/templates con metricas v2
  > Hallazgos clave: 10-12 nodos + es=0.5-0.7 es el regimen optimo. 6-8 nodos no
  > sirven para estrategia (budget satura). preferential_attachment eliminable (0% WC).
  > Documentado en WORLD_DESIGN.md "Batch sweep: regimenes de generacion".

### Enriquecimiento del case (SIGUIENTE FOCO — decision 2026-03-09)
> **Diagnostico de alineacion con PROJECT.md**: el nucleo formal (BN, generacion,
> teacher, QualitySuite) esta solido y alineado. El gap principal ya no esta en el
> world model sino en la **riqueza del case que ve el agente**. Las 3 tasks actuales
> son evaluaciones ancla validas, no el espacio final. El budget actual es un proxy
> simple de costo de adquisicion de evidencia, no la version final.
>
> Prioridades en orden:

#### 1. Dataset-rich evidence (PROXIMO PASO)
> Hoy: `DataSampler` genera UNA tabla plana (N filas, todas las columnas visibles)
> o observaciones aisladas ("variable: value"). `DataAsset` model ya soporta
> nombre, descripcion, formato y datos — pero solo se usa con un dataset.
> `ResearchProblem.data_assets` es una lista, asi que el modelo ya soporta
> multiples datasets. El gap esta en el DataSampler, no en el modelo.
>
> Referencia: ver PROJECT.md ejemplo de Nelvara (3 data assets distintos)
> y los dos ejemplos finales (pozos de petroleo, material anticorrosivo).
>
> Plan concreto (slice minimo):

- [x] Extender `DataSampler` para generar multiples `DataAsset` por mundo:
  - Dataset principal: tabla con N filas (observable columns, como hoy)
  - Dataset secundario: subconjunto de columnas, menos filas, distinta seed
  - Observaciones puntuales: 3-5 hechos narrativos extraidos de samples
- [x] Agregar campos a `DataAsset`: `source` (quien lo genero), `num_rows`, `columns`
- [x] Datos con valores faltantes: al generar la tabla, omitir aleatoriamente X% de celdas ("not_measured")
- [x] `ProblemBuilder` usa los nuevos assets: `rich_data=True` flag, agente recibe 2+ datasets + narrativas
- [x] `prompts.py` soporta formato "narrative" y muestra metadata (source, num_rows)
- [ ] E2E con LLM agent: verificar que el agente razona sobre datos ricos correctamente
- [ ] Despues (no en slice minimo): metadata (fecha, instrumento), temporal column, datos contradictorios entre datasets

#### 2. Rich actions
> Hoy: `AvailableAction` tiene node, description y cost. Pero cost=1 siempre
> y cada accion revela exactamente 1 nodo. La descripcion viene del LLM
> via apply_semantics pero es generica ("Observe X").
>
> Plan concreto (slice minimo):

- [ ] Permitir cost > 1 en `AvailableAction` (el modelo ya lo soporta, falta usarlo)
- [ ] Permitir acciones que revelan multiples nodos: agregar `nodes: list[str]` a `AvailableAction` (hoy solo `node: str`)
- [ ] `EpisodeRunner` procesa acciones multi-nodo: una accion revela N valores, cuesta cost
- [ ] `EpisodeGenTool` genera acciones con costos variados (1, 2, 3) segun config
- [ ] Despues: acciones semanticas mas ricas (el LLM genera la descripcion por accion)

#### 3. ResearchCase — el orchestrator diseña el caso completo
> **Reformulacion fundamental (2026-03-09)**: el producto de SREG no es
> "un mundo + siempre las mismas 3 tasks". Es un **caso de investigacion
> completo** con preguntas que nacen del caso, no de un template fijo.
> El orchestrator debe diseñar el caso (preguntas + datos + acciones),
> no solo el mundo. ResearchCase generaliza TaskBundle incrementalmente.
> Ver analisis completo en WORLD_DESIGN.md "Diseno de Research Cases".
>
> Plan concreto (incremental):

- [x] **Slice 1**: `world → case plan → tasks seleccionadas` (no tocar agent)
  > Implementado: CasePlan model, design_case tool, generate_from_plan, 35 new tests.
  > E2E validado: 6 configs (3 templates, 6-10 nodos), orchestrator dispatch completo.
  >
- [ ] **Paso 2**: El orchestrator escribe las preguntas en lenguaje natural (no text fijo)
- [ ] **Paso 3**: Budget compartido entre preguntas del mismo caso
- [ ] **Paso 4**: Agregar `causal_effect` eval type (do-calculus, pgmpy lo soporta)
- [ ] **Paso 5**: Paper-seeded cases — el orchestrator lee un paper y diseña un caso sintetico inspirado
- [ ] Despues: prediction eval type, structure_discovery, optimization
- [ ] Despues: evaluaciones semanticas con rubrics (reasoning quality, evidence usage)

### Composicion de motifs
- [ ] Motif composer: combine chain+fork+collider into a single DAGSpec
- [x] DAG generators: Erdos-Renyi, spanning tree, preferential attachment, layered (inspired by Reasoning Core)
- [ ] Expressive range analysis: generate 100+ worlds, measure distributions, detect biases

### Integracion LLM orchestrator + DAGSpec
- [x] `dag_generate` tool: LLM elige generador (erdos_renyi, layered, etc.) + parametros -> DAGSpec automatico
- [x] `dag_construct` tool: LLM especifica nodos y aristas manualmente -> DAGSpec custom
- [ ] Unificar `generate()` y `generate_custom()` en una sola API de WorldGenTool
- [ ] Seeds desde papers: LLM extrae estructura causal de texto -> `dag_construct`

### Narrativa elaborada
- [ ] Theoretical context: prior studies, hints, misleading context
- [ ] Richer semantic layer: apply_semantics generates multi-paragraph narrative

### Semantic mode (pregunta abierta — ver WORLD_DESIGN.md #5)
- [ ] Decidir: semantic_mode configurable (full / abstract / fictional)
- [ ] Implementar modo abstracto (sin apply_semantics, variables genéricas)
- [ ] Experimentar: comparar respuestas del agent en cada modo

## v3 — Mechanism-first + evaluacion profunda (Etapa 3)

### Mechanism-first design
- [ ] `MechanismSpec` model: subgraph + semantics + shared variables
- [ ] Mechanism library: 5-10 reusable base mechanisms
- [ ] `WorldComposer`: combines mechanisms into a world (resolves conflicts, shared vars)
- [ ] Rival mechanisms as competing hypotheses (structure selection tasks)
- [ ] Generator health metrics: acceptance rate, structural diversity, distinguishability

### Evaluacion avanzada
- [ ] Intervention tasks (do-calculus via graph surgery)
- [ ] Structure recovery tasks (SHD evaluation)

## Backlog
- [ ] Continuous variables (Gaussian CPDs, mixed worlds)
- [ ] Synthetic document artifacts (papers, reports, notes)
- [ ] Process rubrics (evaluate reasoning quality, not just answer)
- [ ] Approximate inference teacher (larger worlds)
- [ ] Complex agent actions (multi-node, conditional)
- [ ] Curriculum over world complexity
- [ ] RL training loop with verifier as reward
