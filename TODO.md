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

### BUG CRITICO: generate_from_plan sobreescribe question pero no answer (2026-03-10)
> Descubierto en E2E caso arenamiento. Afecta potencialmente TODOS los eval types
> donde la pregunta menciona nodos especificos.
>
> **Root cause**: `generate_from_plan()` (task_gen.py:740) reemplaza `task.question`
> con el `question_text` del CasePlan, pero la `correct_answer` se calculo con
> nodos elegidos por el algoritmo — que pueden ser DISTINTOS a los que menciona
> el CasePlan. Resultado: pregunta y respuesta no hablan de lo mismo.
>
> **Ejemplo concreto**: compare_interventions pregunta por `child_fluid_intensity`
> vs `max_fracture_pressure`, pero la respuesta es sobre `historical_interference_risk`
> vs `child_fluid_intensity`.
>
> **Eval types afectados**: compare_interventions, causal_effect, best_intervention,
> should_condition — cualquiera donde la pregunta nombra nodos/intervenciones especificos.
>
> **Fix necesario**: `generate_from_plan` no puede simplemente sobreescribir el texto.
> Debe GUIAR la generacion para que pregunta y respuesta nazcan juntas. Opciones:
> - EvalQuestionPlan incluye campos opcionales (intervention_node, compare_nodes, etc.)
> - El task generator extrae los nodos del question_text (fragil)
> - Se genera la pregunta Y la respuesta a partir del plan, no por separado

- [ ] **P0**: Fix generate_from_plan mismatch (pregunta vs respuesta desalineadas)

### Problemas de diseno del case (hallazgos E2E 2026-03-10)
> Analisis detallado de caso_arenamiento con segunda opinion de AI externa.
> Estos NO son bugs — son limitaciones de diseno que necesitan evolucion.

- [ ] **Budget wording**: dice "N observaciones" pero el sistema ya tiene costos variados. Deberia decir "presupuesto de investigacion: N unidades" o similar. No "observaciones".
- [ ] **Acciones siguen siendo "Measure X"**: la narrativa mejoro pero las acciones siguen siendo 1 nodo = 1 accion. Necesitan ser acciones de investigacion reales (Slice B de Rich Actions).
- [ ] **Primary question vs caso narrativo**: el caso habla de causalidad pero la primary question es infer_target (prediccion). Falta que el orchestrator alinee la primary question con el objetivo real de la investigacion.
- [ ] **Titulo duplicado**: scenario_title vs case_plan.title son distintos y compiten. Unificar.
- [ ] **Estructura investigativa del case**: hoy el case es (titulo, historia, tareas). Deberia ser (objetivo, hipotesis rivales, incertidumbres criticas, evidencia disponible/faltante, decisiones operativas). Esto es el gran salto cualitativo pendiente.
- [ ] **Validacion de consistencia**: falta check automatico de que la pregunta visible menciona los mismos nodos/intervenciones que la task formal. Deberia ser parte de QualitySuite o de generate_from_plan.

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

### QualitySuite v2 — metricas rediseñadas (COMPLETO - pero desactualizado)
> Hallazgo critico: la metrica original teacher_beats_prior (KL vs one-hot del true state)
> castiga inferencia correcta cuando el sample es atipico. Ver WORLD_DESIGN.md "Hallazgo critico".
>
> **IMPORTANTE (2026-03-10):** QualitySuite v2 quedo desactualizado. Solo evalua los
> 3 tipos originales (infer_target, NBO, hypothesis_selection) con mundos programaticos
> (templates, sin LLM). No cubre los 6 eval types nuevos, no usa orchestrator, no evalua
> CasePlan, semantica ni agente. Es un integration test del motor formal, NO control de
> calidad del producto. Ver seccion "Benchmark y diagnostico" abajo para la evolucion.

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

### Benchmark y diagnostico — control de calidad del producto (NUEVO)
> **Definicion clave**: el benchmark NO es lo mismo que los unit tests.
> - Unit tests = "¿el codigo funciona?" (piezas aisladas, inputs fabricados, sin LLM)
> - Benchmark = "¿el producto es bueno?" (sistema real, con LLM, pipeline completo)
>
> El benchmark SIEMPRE usa el sistema real en su mejor version implementada.
> No mundos de juguete, no atajos. Si el sistema usa orchestrator + CasePlan +
> semantica + rich data, el benchmark los usa.
>
> Produce dos salidas del mismo run:
> 1. **Metricas agregadas**: completion rate, submit rate, KL, per-eval-type breakdown
> 2. **Analisis de failure modes**: que patrones de fallo aparecen y por que
>
> Ver PROJECT.md "Aseguramiento de calidad" y CLAUDE.md "Quality assurance" para
> la vision completa. Ver skill `/eval` para como correrlo.
>
> Los scripts sueltos (test_e2e.py, test_agent.py, batch_eval.py, diagnostic_batch.py)
> se consolidan en el benchmark. Solo se mantienen como utilidades: demo.py, view_trajectory.py.

- [~] **BM.1**: Implementar script de benchmark (sistema real E2E con LLM)
  - [x] Mini benchmark: 3 SRCs reales (scripts/mini_benchmark.py)
  - [x] Orchestrator genera N casos con goals variados
  - [x] Agent solver intenta resolver cada caso
  - [x] Trayectorias extraidas y comparadas con teacher
  - [x] Metricas agregadas + failure modes
  - [x] Resultados guardados en `experiments/` con timestamp
  - [ ] Metrica `prior_delta` (agent vs prior, teacher vs prior) — para interpretar "peor que random"
  - [ ] Evolucionar a BenchmarkRunner con infraestructura completa
- [x] **BM.2**: Crear `experiments/` directory con index.md
- [ ] **BM.3**: Actualizar `quality.py` Layer B para cubrir 9 eval types (no solo 3)
- [ ] **BM.4**: Primer benchmark run real (20-30 casos, varied goals)
- [ ] **BM.5**: Consolidar scripts sueltos (deprecar diagnostic_batch.py, absorber test_e2e.py)

### Enriquecimiento del case (SIGUIENTE FOCO — actualizado 2026-03-09)
> **Diagnostico de alineacion con PROJECT.md**: el nucleo formal (BN, generacion,
> teacher, QualitySuite) esta solido y alineado. El gap principal ya no esta en el
> world model sino en la **riqueza del case que ve el agente**.
>
> **Principio rector (regla de oro):**
> > Cada nueva task, eval type, o feature tiene que sentirse como una pregunta
> > natural de un caso de investigacion, no como una operacion bonita sobre un DAG.
> > Si no se puede formular naturalmente dentro de un case, no es prioridad.
>
> **Orden de prioridades (revisado 2026-03-10):**
> 1. ~~Ola 1 de eval types~~ DONE (9 tipos)
> 2. **Agent Solver v2** (diagnostico del entorno — sin el solver diseñamos a ciegas)
> 3. Rich actions Slice B (que las acciones se sientan como ciencia)
> 4. E2E con LLM real usando design_case (el orchestrator diseña el caso)
> 5. Paper-seeded cases (el salto cualitativo: paper real → caso sintetico)
>
> El motor formal ya es suficientemente fuerte. El valor diferencial ahora sale
> de que los cases se parezcan a mini-investigaciones cientificas reales.

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

#### 2. Rich actions (rediseñado 2026-03-10)
> **Principio rector**: pensar es gratis, actuar en el mundo cuesta.
> El agente analiza datos libremente; lo que cuesta budget es adquirir
> evidencia nueva (medir, experimentar, pedir datos adicionales).
>
> **Diseño completo documentado en WORLD_DESIGN.md** "Diseno de acciones
> de investigacion" — incluye catalogo de tipos de accion, ejemplos por
> dominio (agricultura, epidemiologia, geologia), cadena de validacion,
> impacto en teacher solver, y preguntas abiertas.
>
> **Patron**: igual que eval types para preguntas. Tipos formales fijos
> (observe, intervene, request_dataset) + instancias concretas diseñadas
> por el orchestrator para cada research case.
>
> **Cuidados de diseño (feedback 2026-03-10):**
> - No generar acciones multi-nodo arbitrarias. Pocas acciones con
>   semántica clara (ej: "análisis de laboratorio" revela 3 nodos
>   específicos, no "observar N nodos random").
> - Agregar `action_type` desde el inicio (observe, intervene,
>   request_dataset), no solo nodos. Esto prepara el modelo para que
>   el orchestrator diseñe acciones tipadas.
> - El costo NO depende solo de cuántos nodos revela — depende del tipo
>   de acción y la narrativa (un análisis espectrométrico cuesta 3
>   aunque solo revele 1 nodo; un muestreo básico cuesta 1 aunque
>   revele 2 nodos).
> - Diseñar pensando en que después el orchestrator va a PROPONER
>   acciones según el research case. El modelo debe ser lo
>   suficientemente expresivo para recibir esas propuestas.
>
> **Plan en 2 slices:**

##### Slice A: modelo de acciones ricas (COMPLETO)
> Cambiar el modelo y la infraestructura para soportar acciones con
> tipo, costo variable y multi-nodo. NO requiere orchestrator — se
> puede usar programáticamente o con CasePlan.

- [x] `ResearchActionType` enum: `observe`, `intervene`, `request_dataset` (y `consult` reservado). Nombrado `ResearchActionType` para evitar colision con `ActionType` de episode.py
- [x] `AvailableAction` ampliado: `action_type: ResearchActionType`, `nodes: list[str]`, `cost: int` (> 1 posible). Campo `node: str` se mantiene como alias retrocompatible (= nodes[0] si len==1)
- [x] `ActionDef` model en episode.py: definicion formal de acciones (id, action_type, nodes, cost). `Episode.action_defs` para modo rico, backward-compat con `available_nodes`/`node_costs`
- [x] `EpisodeRunner` procesa acciones multi-nodo via `action_id`: una accion revela N valores, cuesta cost. `StepResult.extra_observations` para las observaciones adicionales
- [x] `ProblemBuilder` genera acciones ricas (`rich_actions=True`): costos variados (target-adjacent cost 2), compound actions por sibling groups (nodos con mismo padre)
- [x] `EpisodeGenTool` actualizado: acepta `available_actions` para generar `ActionDef`s correspondientes
- [x] Teacher solver: `optimal_action()` y `generate_trajectory()` aceptan `costs` para optimizar IG/costo (greedy)
- [x] 26 tests nuevos (578 total): acciones con cost > 1, multi-nodo, compound observe, IG/cost, cross-template

##### Deuda de diseno de Slice A (NO resolver ahora, tener en cuenta en Slice B)
> Feedback post-Slice A: la infraestructura esta lista, pero las heuristicas
> actuales del ProblemBuilder son provisorias y NO deben cristalizarse:
> - **Sibling grouping**: agrupar nodos con mismo padre es una heuristica razonable
>   para el primer slice, pero NO deberia ser la logica general. Las acciones
>   compuestas futuras deben nacer del research case (ej: "analisis de laboratorio"
>   agrupa variables por logica del dominio, no por estructura del DAG).
> - **Costo por cercania al target**: sirve como primer paso, pero el costo real
>   deberia depender del tipo de accion y la narrativa del case (un analisis
>   espectrometrico cuesta 3 porque es caro, no porque esta cerca del target).
> - **Direccion general**: las acciones deben sentirse cada vez mas naturales
>   dentro del case, no solo mas flexibles tecnicamente. Slice B debe apuntar a que
>   el orchestrator diseñe acciones con sentido narrativo, no solo formal.

##### Slice B: intervenciones como acciones + orchestrator (DESPUES)
> El agente puede INTERVENIR (do-operation) como accion del episodio.
> El orchestrator diseña acciones como parte del ResearchCase.
> Las acciones deben sentirse naturales dentro del case, no solo
> tecnicamente flexibles.

- [ ] Acciones de intervencion: do-operations como acciones del agente (costo alto, info alta)
- [ ] `ActionPlan` model: el orchestrator propone acciones tipadas como parte del CasePlan
- [ ] Costos y agrupaciones diseñados por el orchestrator segun el research case (reemplaza heuristicas de Slice A)
- [ ] Validacion de coherencia: cada accion ayuda a al menos 1 pregunta, no regala respuestas
- [ ] Despues: acciones de consulta (revelar info parcial sobre estructura/CPDs)

#### 3. ResearchCase — el orchestrator diseña el caso completo
> **Reformulacion fundamental (2026-03-09)**: el producto de SREG no es
> "un mundo + siempre las mismas 3 tasks". Es un **caso de investigacion
> completo** con preguntas que nacen del caso, no de un template fijo.
> El orchestrator debe diseñar el caso (preguntas + datos + acciones),
> no solo el mundo. ResearchCase generaliza TaskBundle incrementalmente.
> Ver analisis completo en WORLD_DESIGN.md "Diseno de Research Cases".
>
> **Hay dos ejes de avance independientes:**
>
> **Eje A — Que el orchestrator elija mejor** (qué preguntas, cuántas, por qué):
>   Hoy CasePlan puede tener 1, 2 o 3 preguntas, pero el orchestrator
>   todavía no "decide" inteligentemente. Falta: case plan quality validation,
>   E2E con LLM real usando design_case, combinaciones variadas en tests.
>
> **Eje B — Ampliar el catálogo de eval types** (qué preguntas PUEDE hacer):
>   Hoy solo hay 3 tipos de evaluación. Para que el sistema se parezca
>   a la visión de PROJECT.md, necesita poder preguntar: ¿cuál es el
>   mecanismo?, ¿qué pasa si intervengo?, ¿cuál es la estructura causal?,
>   ¿qué configuración optimiza Y?, etc. Cada eval type nuevo requiere
>   su propia lógica de generación, scoring, y teacher solver.
>   Ver catálogo completo en WORLD_DESIGN.md "Catalogo de evaluaciones".
>
> Sin el Eje B, el Eje A es "elegir entre las mismas 3 opciones de siempre".
> Sin el Eje A, el Eje B es "tener muchos tipos pero siempre usarlos todos".
> Ambos ejes se necesitan.

##### Eje A: Orchestrator elige mejor
- [x] **Slice 1**: CasePlan model + design_case tool + generate_from_plan (35 tests)
- [ ] **A.1**: Case plan quality validation (NBO no trivial, hipotesis distinguibles, preguntas no redundantes)
- [ ] **A.2**: E2E con LLM real: el orchestrator mira un mundo y decide qué preguntas valen la pena
- [ ] **A.3**: Tests con combinaciones variadas (1 sola pregunta, 2 sin infer_target, hyp_sel como primary, etc.)
- [ ] **A.4**: Budget compartido entre preguntas del mismo caso
- [ ] **A.5**: Paper-seeded cases — el orchestrator lee un paper y diseña un caso sintetico inspirado

##### Eje B: Nuevos eval types (catálogo de 31 tipos en 6 familias)
> **Research completo en WORLD_DESIGN.md** (3 secciones clave):
> - "Fundamentos de razonamiento causal" — Pearl (3 escalones), McElreath (4 confounders)
> - "Catálogo de evaluaciones científicas" — 31 eval types en 6 familias, tablas detalladas
> - "Mapa de implementación por olas" — qué hacer primero y por qué
>
> Cada eval type necesita: TaskType enum, generación en TaskGenTool,
> scoring en VerifierTool, teacher solver support, tests.
> Regla de priorización: "¿se siente como pregunta científica de un case real?"

- [x] **B.1**: `causal_effect` — Si do(X=x), qué pasa con Y?
  > Implementado: `causal_query()`, `_causal_effect_task()`, `Task.intervention`.
  > 14 tests. E2E validado: do() != observe() con confounders.
- [x] **Ola 1** (builds on lo que hay, pgmpy directo):
  - [x] `best_intervention` — Qué intervención maximiza Y? (argmax sobre do-queries)
  - [x] `compare_interventions` — do(X) vs do(Z), cuál cambia más Y?
  - [x] `adjustment_set` — Qué variables debo controlar? (backdoor criterion)
  - [x] `should_condition` — Alguien sugiere controlar por Z. Es correcto? (elemental confounds)
  - [x] `infer_latent_cause` — Qué causa oculta explica los síntomas? (posterior sobre LATENT)
- [ ] **Ola 2** (requieren más diseño):
  - [ ] `simpson_paradox` — Datos que engañan, solo la estructura causal resuelve
  - [ ] `mediation` — Efecto directo vs indirecto (NDE/NIE via múltiples do-queries)
  - [ ] `confounder_detection` — Este análisis está confundido? Por qué?
- [ ] **Ola 3** (infraestructura nueva):
  - [ ] `mechanism_selection` — Cuál mecanismo generó los datos? (requiere MechanismSpec v3)
  - [ ] `best_experiment_to_disambiguate` — Qué experimento separa 2 hipótesis rivales?
  - [ ] `structure_discovery` — Recuperar la estructura causal (SHD, edge F1)
  - [ ] `prediction` — Posterior de un nodo no-target
  - [ ] Familia F: evaluaciones de proceso (rubrics, calibración, LLM-as-judge)

#### 4. Agent Solver v2 — diagnostico del entorno (PRIORIDAD)
> **El agent solver no es un extra. Es parte del loop de validacion de SREG.**
> Sin el solver, seguimos diseñando el entorno a ciegas. Con el solver, el
> propio entorno empieza a mostrar si tiene sentido para RL y entrenamiento
> de agentes cientificos.
>
> **Estado actual del solver**: observe/submit con soporte multi-tipo en el
> harness (submit + prompt + scoring para los 9 eval types). Trayectorias
> inspeccionables (S.1). Observe todavia simple (nodo unico, costo 1).
> Pendiente: S.2 diagnostico, S.4 rich actions.
>
> **Rol del solver v2**: diagnostico, no competitivo. Correr casos E2E,
> elegir acciones, razonar con budget, responder preguntas, y dejarnos
> inspeccionar trayectorias, errores y failure modes.
>
> **Principio clave: el agente NO recibe pistas sobre el tipo de evaluacion.**
> Recibe una pregunta cientifica y se las arregla. No hay "soporte por eval
> type" en el agente — la gracia es que el entorno le presenta un problema
> y el agente investiga. Lo que si necesita funcionar es la infraestructura
> del harness: que el formato de respuesta sea aceptable (distribucion,
> eleccion, set de variables, si/no) y que el verifier pueda scorear lo
> que devuelve. Eso es plumbing, no inteligencia del agente.
>
> **Prioridad: trayectorias legibles + diagnostico ANTES que breadth.**
> Ver como un agente recorre 20 casos y donde se rompe dice mas que
> soporte superficial para muchos tipos sin buena inspeccion.
>
> **Que queremos detectar con el solver**:
> - Casos triviales (resuelve sin medir) o imposibles (no puede resolver)
> - Narrativa confusa (no entiende que se le pide)
> - Preguntas que no guian investigacion real
> - Acciones que no se sienten naturales
> - Leakage / shortcuts (infiere sin investigar)
> - Reward que no coincide con "investigar bien"

- [x] **S.1**: Trayectorias inspeccionables (PRIMERO)
  - [x] Exportar trayectoria completa como JSON (acciones, razonamiento, observaciones, respuesta)
  - [x] Comparacion lado a lado: agent trajectory vs teacher trajectory
  - [x] Script de inspeccion: ver paso a paso que hizo el agente y por que
  - Deuda conocida (S.1):
    - Parseo post-hoc de messages es fragil — si cambia el formato del chat se rompe silenciosamente. v1 OK, pero la solucion final son eventos estructurados emitidos por el harness (el on_step callback va en esa direccion).
    - El "thinking" textual es ruido para diagnosticar el entorno. El nucleo del diagnostico es: que accion eligio, con que evidencia, que observo, cual fue su respuesta, como se compara con el teacher. El thinking ayuda a entender *por que* se confundio, pero no es el dato primario.
    - La comparacion agent vs teacher es para inspeccion, NO para imponer una unica trayectoria correcta. El teacher es el upper bound formal, un agente puede elegir distinto y estar bien. El verdict se basa en KL del resultado final, no en si siguio los mismos pasos.
- [x] **S.2**: Pipeline de diagnostico de entorno
  - [x] Script que corre N SRCs E2E via orchestrator real, agent en CADA task
  - [x] Detectar patrones: TRIVIAL, NO_SUBMIT, WRONG_ANSWER, HIGH_KL, FORMAT_ERROR
  - [x] Metricas por eval type: count, submission rate, mean score, failures
  - [x] Report diagnostico: por tipo, por SRC, failure modes, tipos no ejercitados
  - [x] Primer diagnostico real: 3 SRCs, 11 tasks, 7/9 tipos, 91% submit, 0 format errors
  - Hallazgos: choice types (hypothesis, compare, best_intervention) tienden a ser
    triviales o wrong — sugiere que no requieren suficiente razonamiento basado en evidencia
- [x] **S.3**: Harness multi-tipo (plumbing, NO pistas al agente)
  - [x] Aceptar formatos de respuesta variados (distribucion, eleccion, set, si/no)
  - [x] Verifier scorea cada formato contra ground truth
  - [x] El agente recibe la pregunta y punto — no sabe que "tipo" es
  - [x] Instrucciones neutrales de formato de salida (submit tool adapta schema por tipo, no sugiere estrategia)
  - [x] Prompt no mezcla correct_answer.keys() con "possible states" para tipos no distribucionales
  - [x] _submit_distribution() valida contra estados de la task (no solo problem.target_states)
  - Limitacion conocida: observe sigue siendo nodo unico / costo 1 (Rich Actions S.4 pendiente)
- [ ] **S.4**: Agent con acciones ricas
  - [ ] Soportar action_id (acciones multi-nodo, costos variados)
  - [ ] Soportar intervenciones como acciones del agente

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
- [ ] Rival mechanisms as competing hypotheses (→ eval type B.4: mechanism_selection)
- [ ] Generator health metrics: acceptance rate, structural diversity, distinguishability

## Backlog
- [ ] Continuous variables (Gaussian CPDs, mixed worlds)
- [ ] Synthetic document artifacts (papers, reports, notes)
- [ ] Approximate inference teacher (larger worlds)
- [ ] Curriculum over world complexity
- [ ] RL training loop with verifier as reward
