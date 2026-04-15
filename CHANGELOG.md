# SREG — Changelog

> All notable changes to this project are documented here.
> Format: date, description, phase reference.

## [Unreleased]

### 2026-04-15 — harden recovery path + fix step_count diagnostics

**Review critico de Codex post-#25**: el recovery path del env bridge
reutilizaba cualquier score del runner cuando veia `"already submitted"`,
sin verificar que los claims del retry coincidieran con los que
realmente commitearon en background. Bajo un retry con claims
modificados, eso atribuia silenciosamente el score viejo al tool call
nuevo — un bug de correctness disfrazado de recuperacion.

- Nueva exception tipada `AlreadySubmittedError(RuntimeError)` en
  `oi_runner.py` con atributo `last_claims`. Subclass de `RuntimeError`
  por backward-compat.
- `submit_claims` tira la exception tipada en vez de `RuntimeError`
  plano; expone los claims commiteados para fingerprint.
- `training/tools.py` atrapa `AlreadySubmittedError` especificamente y
  compara el payload del retry (helper `_claims_match`, pydantic
  equality con orden preservado) antes de recuperar. En mismatch:
  retorna error explicito `already_submitted_payload_mismatch` en vez
  de silenciosamente usar el score viejo.
- `submit_claims` ahora incrementa `state["step_count"]` como hacen
  `python_exec` y `think`. Sin esto, las diagnostics de tool-count y
  cualquier per-step penalty futuro estaban sesgadas.
- Tests: 3 nuevos (total 51 passed). Runner: exception carga
  `last_claims` y mantiene `isinstance(RuntimeError)`. Env:
  (a) retry con claims modificados NO recupera, reporta mismatch;
  (b) submit_claims incrementa step_count.

### 2026-04-14 — env bridge async race fix (cierre #25)

**Complemento del fix transaccional anterior**: `asyncio.wait_for` cancela
el `await` pero NO el thread worker. Sin proteccion, el thread podia
commitear el runner DESPUES de que el env ya le retorno "timeout" al
agente, y el retry subsecuente veia `_submitted=True` → "already submitted".

- `OIEpisodeRunner.submit_claims` acepta `cancel_event: threading.Event`
  y lo chequea en `_commit_scoring_result` antes de mutar estado. Si esta
  seteado, tira `SubmissionCancelled` y el runner queda pristine.
- Nueva exception `SubmissionCancelled` (exportada) para distinguir abort
  pre-commit de errores normales de validacion/runtime.
- `sreg.training.tools.submit_claims` instancia `threading.Event()` por
  llamada, lo setea en el `TimeoutError`, y agrega recovery path en
  `RuntimeError`: si el thread gano la carrera y commiteo antes del
  signal, se recupera el score del runner en vez de perder el episodio.
- `tests/training/test_tools.py` (nuevo): 4 tests async E2E via
  `asyncio.run()` que cubren (a) timeout sin commit, (b) retry tras
  timeout, (c) recovery cuando el thread commiteo primero, (d) path
  rapido normal.
- `TestRunnerTransactionality`: 3 tests adicionales de `cancel_event`
  (set antes de commit, no set, retry tras cancel).

### 2026-04-14 — submit_claims transaccional (fix bloqueante #24)

**Bug de contrato encontrado en eval real (pre-training)**: un timeout del
LLM judge durante scoring dejaba el runner con `_submitted=True`, bloqueando
cualquier retry del agente con `"Claims already submitted"`. El episodio se
perdia (reward=-0.05, truncated).

- `OIEpisodeRunner._score_with_judge` es ahora puro: retorna
  `(score, claim_truths, relevance_results, judge_claims)` sin mutar `self`.
- `submit_claims` stagea compile + scoring en locales y commitea todas las
  mutaciones atomicamente solo si ambos pasos tuvieron exito, via el nuevo
  helper privado `_commit_scoring_result` (single source of truth del
  invariante de commit).
- `scripts/rescore.py` consume el mismo helper (`record_claim_steps=False`)
  en vez de duplicar el bloque.
- `TestRunnerTransactionality` agrega 4 tests de regresion: TimeoutError en
  scoring, RuntimeError, retry tras failure transitorio, y fallo de compile.
  Todos verifican runner pristine tras error.
- **Nota**: este commit cierra el bug INTERNO del runner. Un race separado
  en el bridge async del env (`asyncio.wait_for` cancela el await pero no
  el thread) queda para el proximo commit.

### 2026-04-12 — Deep audit cleanup

**Eliminacion de codigo muerto y docs drift tras la consolidacion SQ v2.**

- **~4500 LoC eliminados**: `oi_salience.py` (1170), `oi_subquestions.py` (1234),
  tests asociados (`test_oi_salience.py`, `test_oi_subquestions.py`,
  `test_oi_scoring_v2.py`, `test_oi_pilot.py`), secciones muertas en
  `test_oi_compiler.py`, `test_oi_verifier.py`, `test_open_investigation.py`.
- **Modelos eliminados**: EpisodeScore, FamilyKey, FamilyAtom, SalienceFamily,
  SalienceMap, ClaimVerdict + 11 constantes de scoring legacy.
- **API simplificada**: `get_score()` y `get_sq_score()` fusionados en un solo
  `get_score() -> EpisodeSubQuestionScore | None`.
- **14 scripts archivados** en `scripts/archive/` (p06_*, compiler_benchmark,
  trace_e2e, oi_pilot_batch, etc.).
- **Docs reescritos**: CURRENT_STATE.md (grammar-direct como default, SQ v2
  como canonico, eliminada seccion salience), ARCHITECTURE.md (Task types,
  ClaimIntent parenthetical), PROJECT.md (Flow A pointer),
  open_investigation_vision.md (pipeline diagram actualizado).
- **E2E validado** con 2 seeds diversos post-cleanup. Bugs encontrados y
  corregidos: refs stale a `get_sq_score()`, imports muertos en cadena
  de imports (oi_demo_case → test_oi_curated_worlds → oi_salience).

### 2026-04-10 — Issue tracking + cierre formal v1

**Merge a main + tags + issue tracking local.**
- Tag `sreg-v0` en `770ad28` (sistema viejo BN + guided tasks)
- Tag `sreg-v1` en `0a28783` (merge commit, OI + SCM cerrado)
- `main` ahora es SREG v1 estable
- Issue tracking local: `issues/I-NNN.md` (23 issues creados)
- `TODO.md` reescrito como board operativo (54 lineas, refs a issues)
- TODO v1 historico archivado en `docs/archive/todo_v1_history.md`
- Skills actualizadas: codex-collab (BN→SCM)
- CLAUDE.md actualizado con nuevas rutas (issues/, docs/archive/)

### 2026-04-09 — Criterio 6: build->use handoff

**`scripts/run_oi.py` — entry point publico para correr el solver
sobre un caso existente.** Completa el loop build->use->eval:
`generate_src.py` (build) -> `run_oi.py` (use) -> `rescore.py` (eval).
Smoke E2E verificado. Documentado en `CURRENT_STATE.md` seccion
"Como usar SREG v1". Criterio 6 cerrado.

### 2026-04-09 — Criterio 5: config v1 congelada

**Config v1 documentada en `CURRENT_STATE.md` seccion "Config v1
congelada".** Tabla con los 11 parametros que definen SREG v1 (scoring
path, claim cap, modelos, iterations, temperature, seed, n_mc, formulas
de score). Cualquier cambio a estos valores es cambio de version, no
bugfix. Criterio 5 cerrado.

### 2026-04-09 — Criterio 4: v1 canonical batch estable

**Suite canonica de 12 casos promovida a `results/v1_canonical_batch/`.**
Proviene de `results/p06_cap_decision/cap15/` (run E2E con config v1
final). `rescore --reaggregate` da delta 0.0000 en los 12 casos.
Average total: 0.509. MANIFEST.md documenta provenance, config, y
gate de reproducibilidad. Criterio 4 cerrado.

### 2026-04-09 — Criterio 1: cap=15 congelado para SREG v1

**Experimento P06 cap decision completo.** 24 runs (12 casos x 2
condiciones cap=5 vs cap=15), 0 errores. Resultado: cap=15 congelado
como configuracion de SREG v1.

Evidencia clave:
- Delta mean(total): +0.071 (cap15 > cap5).
- 8/12 casos saturan cap=5 (solver no puede expresar mas de 5 claims).
- Cap=15 permite decomposicion atomica: claims bundled de 6-10 specs
  se separan en claims focalizadas que compilan y verifican mejor.
- Cap=15 tambien penaliza especulacion: solver que rellena slots con
  claims falsas obtiene peor score. Buena presion evolutiva.
- P1 delta medias PASS (+0.056), P1 amplitud FAIL (6/12). Decision
  basada en argumento de instrumento, no de solver performance.

Cambios:
- `scripts/p06_cap_decision.py`: harness de experiment paired A/B.
- `src/sreg/tools/oi_runner.py`: `claim_cap` como parametro explicito.
- `src/sreg/tools/oi_driver.py`: `build_oi_solver_tools(claim_cap)`.
- `src/sreg/tools/oi_prompts.py`: `claim_cap` en prompt dinamico.
- `research/notes/p06_addendum_cap_decision.md`: protocolo.
- `research/notes/p06_cap_decision_result.md`: resultado y decision.
- Tests actualizados para claim_cap wiring.

### 2026-04-09 — Criterio 2: SQ v2 declarado path canonico de SREG v1

**SQ v2 (specs-based) + LLM judge es el unico path canonico de SREG v1.**
SQ v1 (pattern-based) y salience map quedan en codigo como legacy fallback
documentado, pero sus scores no son validos como resultados oficiales de v1.

Cambios:
- `oi_runner.py`: header comment declara path canonico. `logger.warning()`
  emitido cuando se usa SQ v1 o salience map (visible en logs de produccion).
- `CURRENT_STATE.md`: tabla de scoring paths actualizada. Seccion
  terminologica clarifica que solo SQ v2 es canonico.
- `ARCHITECTURE.md`: nota de scoring path canonico agregada.
- `TODO.md`: criterio 2 marcado como decidido.

### 2026-04-09 — P1.5 #10: missing-column raises + non-numeric guards

**`_filter_condition` ahora lanza `ValueError` en vez de fallar
silenciosamente.** Cierra la deuda P1.5 documentada desde P1.

1. **Columna faltante → raise.** Si un spec referencia una columna que no
   existe en el DataFrame (e.g., columna alucinada por el LLM), la funcion
   ahora lanza `ValueError` en vez de ignorar el predicado silenciosamente.
   `verify_atom` atrapa la excepcion y la convierte en `score=0.0`.

2. **Predicado numerico sobre columna no-numerica → raise.** `ApproxEq`,
   `ConditionRange`, `QuantileRange` y el legacy raw scalar ahora validan
   `is_numeric_dtype` antes de operar. Si la columna es string/categorical,
   se lanza `ValueError` con mensaje informativo.

3. **Sample starvation (<30 rows):** mantiene solo el warning actual (no
   cambia comportamiento). Evaluacion de si deberia ser `NaN` queda como
   deuda separada.

### 2026-04-09 — P06 #24: hotfix heterogeneity ATE spec direction-agnostic

**Spec 1 del compiler para claims de heterogeneidad ahora usa
`GAP_MATERIAL` en vez de una assertion direccional.** Antes, el compiler
mapeaba `intent.direction` (ambiguo: puede ser la direccion del ATE
pooled o la del termino de interaccion) a `POSITIVE`/`NEGATIVE`/`NEAR_ZERO`
en spec 1, causando que specs estructuralmente correctas fallaran en
verificacion y deprimieran el truth score (e.g., 0.4 en vez de 1.0).

Ahora spec 1 solo verifica que un ATE material existe (`|diff| > threshold`),
sin imponer signo. Spec 2 (`SIGN_FLIP`) sigue siendo el guardrail principal
para heterogeneidad.

**Follow-up posible:** el teacher (salience) ya modela heterogeneity como
un solo atomo `CONTRAST_DIFF → SIGN_FLIP`. A futuro podria eliminarse
spec 1 completamente, pero eso es cambio de cardinalidad, no hotfix.

### 2026-04-09 — P06 #25: rechazo atomico de evidence_basis fabricadas

**`submit_claims` ahora rechaza la submission completa si cualquier claim
cita un `artifact_id` que el solver nunca accedio via `load_artifact()` o
`save_artifact()`.** Rechazo atomico: si un solo claim tiene refs invalidas,
ninguno se registra. Cero mutacion de estado — el solver puede corregir y
reenviar.

**Cambios:**

1. **`oi_runner.py` — `validate_evidence_refs()` + bloque de validacion.**
   Helper module-level que clasifica refs invalidas en dos categorias:
   `unknown_artifact_id` (el artifact no existe en el catalogo) y
   `artifact_exists_but_not_accessed` (existe pero el solver nunca lo cargo).
   El bloque de validacion va en `submit_claims()` ANTES de cualquier
   mutacion de estado (`claim_steps`, `_submitted`), garantizando atomicidad.

2. **Tests: `TestEvidenceBasisValidation`** (5 tests). Cubre: rechazo total
   con zero side effects, rechazo atomico de batch mixto, submission valida
   aceptada, resubmit corregido post-rechazo, distincion de las dos
   categorias de error.

3. **Tests existentes actualizados.** 8 tests que llamaban `submit_claims`
   sin haber cargado artifacts ahora registran acceso via
   `load_artifact()`. Adicionalmente, `test_submit_validates_claim_count`
   corregido para usar `range(16)` (consistente con `MAX_CLAIMS=15`).

### 2026-04-09 — P06 #45: Flow B strip — adjust_set derivado del SCM

**El LLM del SQ compiler ya no elige `adjust_set` en adjust arms.** El
verifier auto-computa un backdoor set valido desde el DAG del SCM via
`_find_backdoor_set`. Elimina la clase de bug donde el LLM adivinaba
confounders por semantica de dominio y producía `measurement_finite=0`
en specs estructuralmente validas.

**Cambios:**

1. **`PROJECT.md` — invariante 8 (Flow A vs Flow B).** Explicita el
   contrato de las dos fronteras del compiler: Flow A (`oi_compiler.py`)
   debe seguir ciega al SCM (preserva presion evolutiva sobre el solver);
   Flow B (`oi_sq_compiler.py`) debe derivar estructura del SCM
   deterministicamente (protege integridad del ground truth).

2. **`oi_sq_compiler.py` — GRAMMAR_REF + strip programatico.**
   - GRAMMAR_REF: `adjust_set` cambia de "tuple of back-door covariates"
     a "DO NOT specify". Semantics, common-phrasings y Example A
     actualizados para no mencionar `adjust_set` como campo a llenar.
   - Strip: en el loop de `compile_sq_to_specs`, antes de
     `_validate_variables` y `AtomicSpec(**spec_dict)`, se hace
     `arm.pop("adjust_set")` en cada arm con `kind=="adjust"`.
     Log a nivel info. No-op silencioso si el LLM ya omitio el campo.
   - Flow A (`oi_compiler.py::lower_intent`) intacto: zero cambios.

3. **Tests: `TestFlowBAdjustSetStrip`** (4 tests via stub LLM). Verifica
   strip de ambos arms, no-op, baseline untouched, formato directo.

### 2026-04-08 — P06 G.1: contrato de abstencion explicito + harness aislado

**Cierra la grieta semantica `adjust + partial_correlation` a nivel prompt**
y agrega un harness aislado de recompile para medir, sin volver a correr el
runner completo, cuanto del compiler emite rutas validas vs invalidas.

**Cambios (dos commits):**

1. **`feat(P06): explicit abstention contract for SQ compiler` (df5abf1).**
   El SQ compiler ahora puede senalar abstencion deliberada devolviendo un
   array vacio explicito. `SQCompileResult` gana `abstained` y
   `abstain_reason`; `compile_sq_to_specs` corta corto a esa rama cuando el
   LLM devuelve `[]` (despues de quitar fences markdown). El orchestrator's
   compile loop ahora distingue tres estados terminales —
   `success` / `abstained` / `error` — y descarta SQs abstenidas
   silenciosamente en lugar de contarlas como compile error. Scoring,
   matching y la politica de required-fallback quedan intencionalmente
   sin cambios: solo cambia el contrato de superficie.
   - Tests: helper, los 3 estados terminales, end-to-end via stub LLMs,
     y un test downstream del consumer en `_compile_oi_subquestions` para
     que las ramas abstain/error queden distinguibles bajo refactors
     futuros.

2. **`feat(P06): G.1 — compiler prompt fix + isolated recompile harness` (15d75ae).**
   Bloque "Adjust arm semantics" en el prompt del compiler que ensena que
   las adjust arms emiten samples 1-D de `outcome` y son incompatibles con
   `partial_correlation`. Dos exemplars trabajados:
   - Ruta causal: 2 adjust arms + `mean` + `difference` + `ref_arm`.
   - Ruta observacional: 1 baseline arm + `partial_correlation` + `identity`.

   Regla de desambiguacion explicitamente sesgada hacia la ruta observacional
   cuando el lenguaje es ambiguo (evita sobre-causalizacion). Bloque
   adicional de exemplars de abstencion para cantidades model-dependent que
   la gramatica no puede verificar (coeficientes de regresion, betas
   estandarizados, AIC, R-cuadrado, componentes de varianza de
   mixed-effects) — el compiler debe senalarlas via el contrato de
   abstencion.

   Harness aislado `scripts/p06_recompile_only.py` que reinvoca
   `compile_sq_to_specs` sobre los textos de sub-questions congelados de
   un baseline y diffea los `verification_specs` resultantes contra el
   baseline congelado. Outcomes por-SQ alimentan tres metricas:
   - **C1a** `resolved_rate` — fraccion de SQs cuyas required specs
     compilan a una ruta valida.
   - **C1b** `bad_replacement_rate` — fraccion de SQs donde la nueva
     compilacion empeora la baseline (rompe specs que antes compilaban).
   - **C1c** flags por-componente de reroute quality.

   El classifier usa un gate estricto `role=required`: las route shapes
   que solo aparecen como `support` NO pueden inflar C1a. Flag opcional
   `--ground-sanity` corre `verify_atom` sobre las required specs reruteadas
   como diagnostico — los criterios de exito son `no_exception` /
   `detail_nonempty` / `measurement_finite`, NO `solver_assertion_holds`.

   Defaults a 5 hard-fail cases (`competing_mech`, `coral_bleach`,
   `immunotherapy`, `microbiome`, `selection_bias`); `--all-cases`
   recompila la baseline completa.
   - Tests: predicados estrictos de route shape, el trap de inflacion de
     C1a (una route shape solo en `support` NO clasifica como `route_*`),
     deteccion de role-flip, y extraccion de variables de spec.

3. **`fix(P06): G.1 harness list-vs-tuple bug + --ground-sanity-only flag`
   (commit 3).** Bug en el classifier del harness aislado:
   `spec_signature` construye `arm_kinds` como tupla, pero JSON no tiene
   tipo tupla y las firmas reloadeadas desde `recompile.json` (el path que
   toma `--ground-sanity-only`) volvian como listas, haciendo que
   `is_causal_route` comparara contra un tuple literal y fallara en
   silencio — la primer corrida de `--ground-sanity` solo ejecutaba
   `verify_atom` en 2 de los 5 reroutes (los route_obs).
   `is_observational_route` ya era tolerante (`"adjust" in arm_kinds` +
   `set(arm_kinds) & {...}`), por eso los observacionales ejecutaban bien.
   Fix: normalizar a tupla con `tuple(sig.get("arm_kinds") or ())` dentro
   de `is_causal_route`.
   - Test de regresion JSON round-trip agregado en
     `tests/scripts/test_p06_recompile_classifier.py`.
   - Flag nuevo `--ground-sanity-only` permite iterar el diagnostico sin
     re-invocar al compiler LLM: reloadea `case_summaries` desde el
     `_recompile_summary.json` ya persistido y corre solo
     `_run_ground_sanity`.

**Por que importa.** El runner E2E es caro y mezcla muchas variables
(LLM noise, costo, latencia). El harness aislado permite medir
exclusivamente cuanto del compiler emite rutas semanticamente validas
sobre los mismos textos de SQs, asi cualquier delta es atribuible al
prompt y no a otras fuentes. La separacion `success` / `abstained` /
`error` impide que abstenciones legitimas (cantidades no-verificables)
queden mezcladas con errores reales del compiler en C1a/C1b.

**Estado.** Codigo y tests landed (df5abf1 + 15d75ae + commit 3). La
corrida G.1 sobre los 5 hard-fail se completo: **C1a 100% (6/6)**, **C1b
0% (0/6)**, **C1c 100% (5/5 reroutes)**. La grieta
`adjust + partial_correlation` no aparece en ninguna emision nueva del
compiler. La alarma C2 `+12pp` en abstention delta fue adjudicada
manualmente — las 3 abstenciones del slice hard-fail son
latent-variable legitimas; la calibracion general sigue dependiendo de
#37. Esto es evidencia sobre las rutas de emision del compiler, NO
sobre el sistema E2E.

**Hallazgo secundario (no invalida G.1).** La re-corrida del
ground-sanity post-harness-fix ejecuta 5/5 reroutes sin excepcion, pero
3/5 (todos route_causal) devuelven `measurement_finite=0` porque el
compiler LLM elige `adjust_set` que NO son backdoor sets validos para el
DAG del mundo. `verify_atom` loguea explicitamente el caso. Es una
clase de problema distinta: G.1 cerro la grieta sobre formas
estructuralmente imposibles; esto es sobre formas estructuralmente
validas pero con un `adjust_set` que no identifica causalmente. Root
cause: `oi_sq_compiler.py::_build_variables_info` solo pasa
`{nombre: mean/std/range}` al LLM, cero aristas ni DAG — el LLM adivina
confounders por semantica de dominio. Registrado como **task #45**
(contrato SCM -> compiler, ver `TODO.md`). Se resuelve aparte, no bajo
G.1. Los artifacts del run (`results/p06_recompile/`) quedan fuera del
commit: la carpeta esta gitignored y el framing vive en este entry y en
el scope del task #45.

### 2026-04-07 — Docs: SREG v1 definition — roadmap + criterios de done

**Vocabulario canonico para versiones del producto.** Antes de hoy "v1" era
ambiguo: convivian "SREG v1" (producto), "SQ v1" (sub-pipeline interno del
compiler/matcher) y "Suite v1" (suite externa de tesis). Esta entrada fija
el roadmap del producto y separa versiones de producto de evoluciones
internas.

**Roadmap del producto (v0 → v1 → v2 → v3):**
- **SREG v0**: Bayes Net + preguntas especificas fijas. Eliminado 2026-03-29.
- **SREG v1**: Open Investigation sobre SCM — brief libre, sub-questions
  ocultas, claims en lenguaje natural, traduccion/compilacion a AtomicSpec,
  verificacion exacta contra el SCM, LLM juez de relevancia. **En cierre
  activo.**
- **SREG v2**: Sherlock-type — research actions con budget, capas de
  revelacion, teoria sintetica, nuevos task types (time-series, anomalias,
  optimizacion). Futuro.
- **SREG v3**: Sistemas complejos dinamicos (cellular automata, biologia
  real). Futuro lejano.

**Cambios:**
- `PROJECT.md` — nueva subseccion "Roadmap del producto: v0 → v1 → v2 → v3"
  al inicio de "Scope actual y horizontes futuros". Define el vocabulario
  canonico y la nota terminologica que separa SREG v1 (producto) de
  SQ v1/v2 / Suite v1 (sub-pipelines y suite externa, no versiones del
  producto).
- `CURRENT_STATE.md` — top quote-block declara explicitamente "este
  documento describe SREG v1". Nueva seccion "Sutileza terminologica"
  antes de "SQ v2 — Pipeline principal" aclara que SQ v1/v2 son
  sub-pipelines internos del compiler/matcher dentro de SREG v1.
- `TODO.md` — nueva seccion "SREG v1 — criterios de done" al top con los
  6 criterios concretos de cierre: (1) decision sobre bundling (P06
  task #26), (2) canonical path estable (SQ v2 vs SQ v1), (3) bugs
  bloqueantes resueltos (#10, #24, #25), (4) smoke validation suite
  estable (`p05_canonical_batch` con `/rescore --reaggregate` delta
  0.0000), (5) config v1 congelada (modelo, budget, pipeline, weights),
  (6) build → use handoff (otros pueden generar y usar casos sin tocar
  el repo).

**Por que importa.** Sin este vocabulario, no se puede decir "SREG v1 esta
cerrado" ni planificar v2 sin renegociar el significado de "v1" en cada
conversacion. El cierre concreto del producto vive ahora como criterios
accionables en `TODO.md`, no como folklore conversacional.

### 2026-04-07 — Docs: tesis canon — suite final v1, related work, indexacion

**Cierre del bloque de research para tesis/paper.** Suite final v1 fijada,
related work cerrado en tres papers contemporaneos, indices de research
reescritos, decisiones operativas reabiertas con evidencia externa.

**Suite final v1 (6 benchmarks):**
- in-domain: `held-out SREG`
- external: `CLadder + QRData + DiscoveryBench + CausalReasoningBenchmark + SciGym`
- SciGym promovido Tier 3 -> Tier 1: unico publico que mide loop iterativo
  Sherlock-type (proponer-observar-refinar). Costo de integracion (Linux/
  Docker/SBML) aceptado porque sin SciGym la suite no mide nada del loop
  iterativo que SREG dice que entrena.

**Decision reabierta — SFT+RL vs RL-from-base:**
- SandMLE reporta empiricamente que SFT-only colapsa a 17.7% Valid Submission
  en MLE-Dojo (vs 83.9% RL-from-base) en 30B. Convierte nuestra eleccion de
  `SFT + RL` en hipotesis empirica, no decision cerrada.
- Tres opciones abiertas: mantener SFT+RL, cambiar a RL-from-base, correr
  ambas. Recomendacion: paralelo si el budget alcanza, sino RL-from-base.
- Comparaciones canonicas ahora incluyen `base + RL` ademas de `base + SFT + RL`.
- Ver `T7` en TODO.md.

**Related work cerrado en tres papers (los tres convergen en el mismo gap):**
- `related_work_sandmle.md` — SandMLE (Zhou et al. 2026): SFT brittle fuera
  del scaffold de generacion. Validacion del approach SREG en dominio adyacente.
- `related_work_scigym.md` — SciGym (Duan et al. 2025): frontier models lejos
  del techo en loop iterativo (RMS F1 < 0.20 en biologia de sistemas).
  Documenta por que SciGym NO compite con SREG (un task type vs 23+).
- `related_work_sciagentgym.md` — SciAgentGym (Shen et al. 2026): frontier
  models pierden 30-50% del exito al pasar de pasos cortos a largos
  (Adaptation 32.9%, Loop Escape 35.7%). Diagnostico del long-horizon collapse.

**Doc canonico nuevo — `external_benchmarks_transfer_analysis.md`:**
- Para cada benchmark: ejemplo concreto, scoring, argumento estructural de
  transferencia, prediccion de magnitud, riesgo principal.
- Correccion central: SREG solver responde en prosa libre, NO en formato
  estructurado. El compiler traduce. Esto es lo que permite argumentar
  transferencia razonable a benchmarks externos.
- Insight central: el delta in-domain vs out-of-domain es la metrica de tesis.

**Indexacion reescrita:**
- `research/README.md` reescrito con dos cortes: por status (CANON activo /
  notes / archive) y por pregunta ("si necesito X, anda a Y"). Regla nueva:
  si un doc no esta marcado CANON, no es fuente de verdad.
- `CLAUDE.md` "Donde buscar que" actualizado con 6 nuevos pointers de tesis.
- `archive/benchmark_results.md` con banner "NO VALIDO PARA TESIS" porque
  los BEFORE scores fueron corridos con `gpt-5.2-chat`, no Qwen3-8B.

**TODO actualizado** con bloque "Suite de tesis — bloques canonicos" T1-T7:
- T1: BEFORE con Qwen3-8B (BLOQUEANTE)
- T2: integrar CRB
- T3: integrar SciGym (Linux/Docker/SBML)
- T4: decidir QRData code execution (BLOQUEA comparabilidad)
- T5: DiscoveryBench judge mitigation
- T6: congelar held-out SREG split
- T7: decidir SFT+RL vs RL-from-base (reabierto)

**No incluye:** cambios en `src/` ni `scripts/`. Quedan para su propio commit.

### 2026-04-06 — Feat: subpopulation predicates in condition_on (P1, smoke-validated)

**P1 implementado.** El compiler-LLM ahora puede expresar subpoblaciones
(rangos, cuartiles, categorias) en `QueryArm.condition_on`, no solo valores
puntuales. Antes esto bloqueaba claims sobre "los pobres", "near the cutoff",
"high vs low biomarker", "urban areas", etc. — el compiler abstainia o
inventaba variables derivadas inexistentes.

**4 predicados universales** (discriminated union via `kind` field):
- `approx_eq` — match aproximado a un punto (legacy, default via shorthand)
- `range` — `lo <= x <= hi`, para ventanas, near-cutoff, RDD bandwidths
- `quantile_range` — `q_lo` a `q_hi` del distribution, para "high vs low"
- `in_set` — match contra una lista de valores, para categoricos

**Backward compat exacto:** raw scalars `{"x": 5.0}` y strings `{"region": "urban"}`
se auto-promueven a `ApproxEq` y `InSet` via `@model_validator(mode="before")`.
`rescore --reaggregate` sobre el batch p05 verifica delta 0.0000 en los 12 casos.

**Smoke-validated en producción** (batch `p05_canonical_batch`, 12 seeds):
- 6/12 casos usan los nuevos predicados (heterogeneity 36 quantile_range,
  chemical 12, immunotherapy 6, policy_equity 4, selection_bias 2,
  missing_data 2 range)
- Adopcion semanticamente correcta (cuartiles para "high/low", range para
  "near cutoff" como `retention_wave3 in [0.2, 0.36]`)
- Recompile poverty: con MISMOS claims/mundo, el compiler emite 8
  `quantile_range` donde antes solo habia point values
- 14 unit tests del verifier (`TestFilterCondition`): 4 predicados + edge cases
  (NaN, ties, degenerate ranges, inclusive bounds, AND conjunction, backward
  compat scalars/strings)

**Caveats explicitos** (NO declarado "validated", ver TODO P1.5):
- NO se atribuye causalidad sobre score: el delta de poverty
  (0.003 → 0.449) NO es atribuible a P1 — variancia LLM en compiler +
  cambios de pipeline lo confunden. P1 da capability de emision, no
  score lift demostrado.
- `in_set` NO probado E2E porque el SCM no soporta nodos categoricos
  (`world.variables` es 100% continuo). Cubierto solo por unit tests sobre
  DataFrames sinteticos. Worldgen extension queda como ticket aparte.
- Ventanas temporales generales (wave/site_id, panel data) NO resueltas:
  P1 cubre predicados sobre variables del world, no sobre columnas
  fuera de `world.variables`.
- El score promedio del batch (0.417) NO mejora con P1 — es techo mas
  profundo (claim quality, teacher gap, scoring metric).

**Bug fix incidental** (`oi_sq_compiler.py:845`): `render_answer_key` crasheaba
con `TypeError: unsupported format string` cuando `comparison["contrast_diff"]`
era `None` (caso edge en arms con NaN/insufficient data). Fix minimo: chequear
`isinstance(cd, (int, float))` antes de format. Pre-existente, expuesto por
el rescore controlado de poverty.

**Archivos nuevos / modificados:**
- `src/sreg/models/open_investigation.py` (+predicate types, +auto-promotion)
- `src/sreg/tools/oi_verifier.py` (`_filter_condition` dispatch por kind)
- `src/sreg/tools/oi_sq_compiler.py` (GRAMMAR_REF + bug fix)
- `tests/models/test_open_investigation.py` (+TestConditionPredicates, 14 tests)
- `tests/tools/test_oi_verifier.py` (+TestFilterCondition, 14 tests)
- `scripts/run_p05_batch.sh` (baseline canonico, 12 seeds diversos)

**Conocido como deuda P1.5** (ver TODO):
- `_filter_condition` hace silent skip cuando la columna no existe (footgun:
  el LLM puede inventar columnas y la pregunta cambia silenciosamente).
- `approx_eq` sobre columna no numerica crashea con `TypeError`.
- Compiler inventa columnas panel (`site_id`, `wave`) que no estan en
  `world.variables` — bloquea casos panel-data.

### 2026-04-06 — Feat: controlled rescore pipeline (P0)

**Rescore controlado implementado.** Permite re-evaluar casos congelados
(`src.json` + `oi_result.json`) sin regenerar mundo ni re-correr el solver.
Aisla el efecto de cambios de codigo de la varianza del worldgen/solver.

**3 modos:**
- `--reaggregate` — solo re-computa aritmetica de scoring (sin LLM, instantaneo)
- `--rejudge` — re-corre juez de relevancia LLM con specs/truths congelados
- `--recompile` — full re-compile + re-verify + re-judge (default)

**Persistencia (P0 prerequisito):**
- `oi_result.json` ahora incluye `score_inputs_v2`: claims, compiled specs,
  claim truths, relevance results, judge claims, runner config, trace
- `src.json` ahora incluye `sub_questions_v2`: SQs grounded con verdicts

**Nuevo:** `scripts/rescore.py`, skill `/rescore` (`.claude/skills/rescore/`).
**Modificados:** `oi_runner.py` (persistence), `generate_src.py` (export),
`CLAUDE.md` (skill table).

### 2026-04-06 — Audit: E2E forensic audit, failure mode taxonomy, scoring roadmap

**Audit E2E completo:** 12 seeds diversas, audit profundo de los 11 casos
exitosos. Identificados 4 failure modes del scoring pipeline (ver TODO A28):

1. **Grammar/representation gap** — claims quasi-experimentales (RDD,
   bandwidths) inexpresables en AtomicSpec (poverty 0.003).
2. **Scorer credit-assignment** — truth a nivel claim penaliza claims
   ambiciosas, coverage inflada por threshold 0 (microbiome 0.196).
3. **SQ decomposition/overlap** — SQs semanticamente solapadas.
4. **Solver miss** — solver concluye mal; scoring justo (policy_equity,
   coral_bleach).

**Roadmap de scoring (TODO I0d):** 3 prioridades — rescore controlado (P0),
predicados de subpoblacion (P1), unit-level truth (P2 en 3 pasos).

**Cleanup:** target_states ya no se computan en OI mode (vestigial).
Presiones evolutivas nuevas en PROJECT.md (4 failure modes de AI scientists).

**Files:** `TODO.md`, `CURRENT_STATE.md`, `ARCHITECTURE.md`, `PROJECT.md`,
`CHANGELOG.md`, `scm_problem_builder.py`, `orchestrator.py`.

### 2026-04-06 — Fix: evidence trap penalty + arm ordering enforcement (BUG 8, 9)

**BUG 8 — Evidence Trap:** Solver citing `python_exec_N` as artifact IDs
caused `truth=0` for all claims (root cause of `missing_data` scoring 0.000
in E2E batch). Evidence validation now applies proportional penalty instead
of zeroing: all fabricated → 0.1, partial → proportional. Solver prompt
updated to explicitly prohibit citing python_exec steps.

**BUG 9 — Arm Ordering Ambiguity:** Verifier difference sign depended on
undocumented QueryArm array order. Correct causal claims could fail
verification if LLM placed arms in natural [control, treatment] order.
Fix: `ref_arm` required for difference/ratio comparisons (auto-filled with
warning for backward compat), exactly 2 arms enforced via `@model_validator`.
GRAMMAR_REF and claim compiler prompt updated: `difference = other - ref_arm`.

**Files:** `oi_runner.py`, `oi_prompts.py`, `open_investigation.py`,
`oi_sq_compiler.py`, `oi_extraction.py` (5 files, +50/-7 lines).

**Discovered via:** 12-seed E2E diverse batch (proportional truth validation).
Forensic audit with Codex + 2 Cursor instances.

### 2026-04-02 — E2E validation: v2 scoring pipeline validated

**Validated:** Full v2 pipeline (juez LLM + answer keys + verifier with
do-calculus + evidence_basis validation) tested with 7 worlds: 5 curated
(v1 path) + 2 seeds: microbiome (14 nodes) and confounding_by_indication
(12 nodes) through the complete v2 path with LLM judge scoring.

**Results:** v2 coverage (0.65-0.79) >> v1 coverage (0.11-0.25). The LLM
judge matches claims against SQs much better than structural salience map.
Correctness discriminates: social_media got 0.500 (half claims false),
microbiome/confounding 0.750, curated worlds mostly 1.0.

### 2026-04-02 — Fix: validate evidence_basis against actual artifact accesses

**Fixed:** Solver could cite artifact_ids in `evidence_basis` that it never
actually loaded or created. No validation existed — fabricated evidence was
silently accepted.

**New:** Step 1b in `_score_with_judge()` checks that all cited artifact_ids
exist in `trace.accessed_artifact_ids()`. If any are fabricated, the claim's
truth drops to 0.

**Fixed:** `save_artifact()` now registers in `trace.accesses` (as
`access_type="analyze"`), so derived artifacts the solver creates are valid
evidence citations.

### 2026-04-01 — Fix: verifier auto-adjust uses do() instead of observational estimation

**Fixed:** `_run_adjustment()` in `oi_verifier.py` was estimating E[Y|do(X)]
from observational data via marginal stratification (one confounder at a time).
This gave wrong results with multiple confounders. The verifier is the oracle —
it should use exact do-calculus, not statistical estimation.

**New:** `_is_valid_backdoor_set()` validates that a proposed adjustment set
blocks all backdoor paths (no descendants of treatment + d-separation check).

**Changed:** `_run_adjustment()` now: (1) validates the backdoor set, (2)
computes exact truth via `solver.interventional_samples()`. Returns
`kind="adjust_invalid"` (NaN) if the set is invalid. Removed ~50 lines of
observational stratification code.

**Why:** The verifier is God-mode — it has access to the true SCM. Estimating
from observational data introduced numerical errors and the marginal
stratification bug. Using do() gives exact causal truth.

### 2026-04-01 — L1: Eliminate warrant system and OI helpers

**Removed:** entire warrant system (`oi_warrant.py`, `oi_helpers.py`) and all
instrumented helpers (`oi.corr`, `oi.regress`, `oi.stratify`, etc). The solver
now uses pandas/numpy directly via `python_exec`.

**Removed from models:** `WarrantResult`, `AnalysisRecord`, warrant fields
from `EpisodeScore` (`raw_correctness`, `avg_warrant`, `warrant_active`),
`WARRANT_PRIOR_FLOOR` constant. `EpisodeTrace` simplified to accesses only.

**Removed from scoring:** warrant multiplier in `oi_compiler.py` (both v1 and
v2 paths) and `oi_verifier.py`. Score is now purely truth-based.

**Why:** warrant never participated in the main SQ scoring path. It added
complexity (~800 lines) without contributing to the reward signal. The solver
can do the same analyses with raw pandas.

**Tests:** 93 pass. All warrant-specific tests removed, remaining tests
updated to use pandas instead of `oi.*` helpers.

### 2026-04-01 — Paso B: LLM relevance judge + E2E scoring pipeline

**New:** `oi_relevance_judge.py` — LLM judge scores claim × SQ relevance
(0..1) with pre-filter by variable overlap. Scoring formula:
`total = correctness × weighted_coverage`.

**Fixes:** auto-compute adjust_set from DAG, force-submit sends pending
tool outputs, focus_variables max 8→12, score wiring in driver.

**E2E results (3 diverse seeds):**
- identifiability_pollution (epistemological): 0.413
- vaca_muerta (causal complex): 0.533
- microbiome (system mapping): 0.889

### 2026-03-30 — SQ v2 prototype: specs-based sub-questions

**New models:** `SubQuestionIntentV2` + `VerificationSpec` in
`open_investigation.py`. SQ = text_gloss + verification_specs (AtomicSpec
bundle with required/support roles) + tier. No pattern, no roles enum.
Coexists with v1.

**New modules:**
- `oi_sq_compiler.py` — LLM compile step: text_gloss → AtomicSpec bundle.
  Uses composable grammar (same as S04 direct-to-atoms).
- `oi_sq_matching.py` — spec_match (exact on estimand, fuzzy on assertion),
  bipartite 1-to-1 matching, episode-level scoring. Pools all claim-specs
  across claims (fix for per-claim penalty identified by Cursor review).

**First test results (5 diverse SQs against 8-node SCM):**
- 5/5 compiled, 18 specs total, 4 measurement kinds (vs ~2 with v1)
- 0 validation errors, 13/18 TRUE (72%)
- Causal + epistemological: 100% TRUE

**Script:** `test_sq_v2_compile.py` — focused test without full E2E.

**Spec:** `research/synthesis/sq_v2_matching_spec.md` (canonical design doc).

### 2026-03-30 — S04 Direct-to-AtomicSpec: catalog vs direct compilation

**Research finding:** the less we depend on the fixed catalog (PatternClass),
the better we preserve claim/SQ semantics across diverse investigation types.

**Evidence (S04):**
- Traced e2e_03 epistemic claims through full pipeline: 2/4 ABSTENTION,
  score 0.239. Hand-crafted AtomicSpecs verified correctly (partial_correlation
  shrinks from 0.517 to 0.189).
- Direct compilation prototype (LLM → AtomicSpec, no catalog):
  - e2e_03: C2 ABSTENTION → 4 specs; C3 0/2 TRUE → 3/3 TRUE
  - SQ brief: 1 compressed SQ → 10 specs (8/10 TRUE)
- Systematic comparison on 5 NEW diverse cases (18 claims):
  catalog 17/18 compiled (28 units), direct 18/18 (65 specs, 50 TRUE).

**5 new seeds for diverse investigation types:**
- selection_bias_police.md (scenario #11)
- methodology_missing_data.md (scenario #17)
- competing_mechanisms.md (scenario #22)
- policy_equity_tradeoff.md (scenario #3)
- value_of_information.md (scenario #23)

**5 new experiments:** e2e_07 through e2e_11, all with submitted claims.

**Scripts:** `direct_to_atoms.py`, `compare_compilers.py`, `test_c2_bundle.py`,
`trace_e2e_03.py` — diagnostic and comparison tools.

### 2026-03-30 — S02 Diverse E2E diagnostics + force-submit fix

**Force-submit mechanism:**
- After main solver loop, if not submitted, one extra LLM turn with ONLY
  `submit_claims` as available tool (python_exec removed)
- Fixed 2/3 cases where solver exhausted iterations without submitting

**Diverse E2E results (3 seeds, 3 types):**
- Vaca Muerta causal: 0.580 (2/5 SQs, correctness 1.0)
- Vaca Muerta predictive: 0.548 (2/5 SQs, correctness 1.0)
- Identifiability epistemic: 0.364 (1/4 SQs, correctness 1.0)

**Diagnostics:** 14 SQs total → 5 HIT, 6 SOLVER_MISS, 3 COMPILER_MISS.
Compiler misses: effect_ranking from prose, sign extraction from literal
slopes, claim-to-SQ matching. See `research/autoresearch/s02_diverse_e2e_diagnostics.md`.

**New seed:** `seeds/vaca_muerta_predictive.md` — predictive classification
variant (AUC-focused, ~18% prevalence imbalanced).

### 2026-03-29 — A22 multi-unit compiler: compound claims decomposed into N units

**Multi-unit compiler pipeline:**
- New `CompiledUnit` model: each unit has its own `ClaimIntent` + `AtomicSpecs`
- `CompilerOutput` restructured with `units` list and status (`compiled` /
  `partial` / `abstention`)
- `compile_claim()` iterates N intents extracted from a single claim, creates
  one `CompiledUnit` per intent
- SQ scoring now per-unit instead of per-claim flat

**E2E validation:**
- Soil: 0.200 -> 0.980 (chain claim now decomposes into pairwise units)
- Coral: 0.807 (compound claims fully compiled)
- Logistics: +0.08 improvement
- S02 forensics: compiler LLM extraction quality is the next bottleneck
  (chain claims miss pairwise relationships, indirect conclusions lost)

### 2026-03-29 — Deep cleanup round 2: remove last BN vestiges from active code

**Code cleanup:**
- Deleted `models/world.py` (legacy BN: Node, CPD, DifficultyProfile, World)
- Deleted `tests/models/test_world.py`
- `orchestrator.py`: removed World/NodeType imports, dead `_task_gen` branch,
  BN polymorphic code paths. All type annotations now SCMWorld-only.
- `generate_src.py`: removed BN code paths in export_json, export_dag_png,
  OI mode check. Fixed "Ground truth BN" -> "Ground truth SCM" in docstring.
- `research_problem.py`: `target_states` now optional (default_factory=list)
- OI scripts: removed discrete `target_states=["low","medium","high"]`

**Dependencies:**
- `pyproject.toml`: removed pgmpy, added pandas
- Deleted stale `src/sreg.egg-info/`

**Documentation:**
- `README.md`: full rewrite for SCM+OI (removed BN, --solve, deleted scripts, training, harness)
- `TODO.md`: A8 (BN vs SCM) marked RESOLVED, removed stale sub-questions
- `ARCHITECTURE.md`: World -> SCMWorld, removed BN comparison table, DAGSpec ref
- `CLAUDE.md`: fixed stale test_world_gen.py reference

### 2026-03-29 — Massive legacy cleanup: BN + guided mode removal (~27K lines)

**Entire BN/guided mode pipeline removed:**
- Deleted `training/` (10 files), `harness/` (8 files) — full packages
- Deleted `agent/agent.py`, `agent/prompts.py`, `agent/transformers_backend.py` — guided solver
- Deleted `env/episode.py` — EpisodeRunner
- Deleted BN tools: `world_gen.py`, `task_gen.py`, `problem_builder.py`,
  `data_sampler.py`, `episode_gen.py`, `verifier.py`, `world_check.py`
- Deleted BN world: `cpd_gen.py`, `dag_generators.py`, `pgmpy_utils.py`, 4 templates
- Deleted `solver/exact_bayes.py` — BN teacher
- Deleted legacy models: `dag_spec.py`, `env_protocol.py`, `agent_tools.py`, `code_exec.py`
- Deleted `display.py`
- Deleted 5 legacy scripts, 30+ legacy test files
- Cleaned `orchestrator.py`: removed all BN handlers, SCM-only now
- Cleaned `generate_src.py`: removed --solve, --report, BN inspect
- All `__init__.py` exports updated to reflect surviving code
- 16 research docs archived
- Updated CURRENT_STATE, ARCHITECTURE, research/README to reflect SCM+OI only

**Result:** ~101 files changed, ~27,347 lines removed. Repo is now SCM+OI only.

### 2026-03-29 — Documentation audit + A21 revert cleanup

**A21 structured claims REVERTED (critical design violation):**
- Structured claims gave solver an enum of relation_type values, directly
  biasing investigation. Violated PROJECT.md principle "no construir juego
  estructurado". Reverted in fb99d85.
- Removed pattern_tags from solver-visible tool schema and prompt.
- The ORIGINAL problem (compiler misinterprets claims) remains — fix the
  compiler, not the solver.

**Full documentation audit + repo cleanup:**
- CLAUDE.md: 489 -> 153 lines. LA PREGUNTA + scoring principles + doc
  maintenance rules + pre-commit checklist. Eliminated duplicated content.
- CURRENT_STATE.md: rewritten as friendly end-to-end explanation with examples.
  Readable by anyone, not a technical inventory.
- ARCHITECTURE.md: OI section from "future" to "implemented (Alpha-0)".
  Fixed horizonte ("SCM continuo", not "discreto"). Fixed AZURE_SOLVER_MODEL.
- PROJECT.md: added scoring design principles. Cleaned OI to vision-level.
- research/README.md: fixed broken refs, removed A21 ref, updated indices.
- Deleted 13 BN-legacy test files (361 tests, ~4000 lines):
  test_world_gen, test_task_gen, test_problem_builder, test_episode_gen,
  test_verifier, test_exact_bayes, test_causal_chain, test_fork_collider,
  test_data_sampler, test_dataset, test_episode_runner, test_env, test_trajectory.
- Deleted 3 legacy scripts: demo.py, run_inspiration_reports.py, batch_sweep.py.
- Deleted loose files: AGENTS.md, tmp-open-investigation-chatgpt.md,
  research_seed.md, research_seed.example.md, scheduled_tasks.lock.
- Moved 4 research docs to archive/: world_design_legacy, sreg_v2_design_findings,
  solver_trajectory_findings, qualitative_eval_2026_03_24.

### 2026-03-28 — Remove target_node + solver tooling + E2E qualitative analysis

**Target node removal from OI pipeline (Session 12):**
- Removed `target` role requirement from SCMSpec (OI uses sub-question roles)
- Updated orchestrator: SCM tool schema, variable summary, OI_MODE_PROMPT
- Updated prompt: "Exactly 1 target" -> role-neutral sub-question guidance
- Legacy `target` role accepted for backward compat, treated as observable
- 7 files changed, all tests pass (46 targeted, 182 model)

**Solver tooling expansion (Session 12):**
- Added statsmodels, linearmodels, sklearn to python_exec ALLOWED_IMPORTS
- Updated solver prompt: "You can also import: statsmodels, linearmodels, sklearn"
- Added linearmodels to pyproject.toml dependencies
- RESULT: soil case used statsmodels successfully — zero tooling friction

**Progressive deadline nudges (Session 12):**
- Replaced one-shot 75% deadline with 3-phase system: 50% (operational), 75% (deadline), final (mandatory)
- Added hard guard: reject non-submit tool calls on final iteration
- Fixed temperature retry: disable unsupported params after first failure

**E2E qualitative analysis (Session 12) — 4 cases:**
- Poverty (dev econ): 0 claims, tooling friction (pre-fix)
- Pollution (water eng): OI solver crashed, reliability issue
- Soil (env health): 0 claims despite working statsmodels + 3 nudges (submission aversion)
- Coral (marine eco): 5 claims submitted! But SQ matching scored 0/4 (claim compilation failure)
- KEY FINDING: worlds + solver are research-capable; evaluation harness is the bottleneck
- Analysis: `research/notes/e2e_qualitative_analysis_20260328.md`
- Codex thread: 019d3654-fa2b-7b92-a457-627687961699

### 2026-03-28 — Data-indexed worlds + investigation gap validation

**Sub-question scoring pipeline (Session 9-10):**
- SubQuestionIntent, ResolvedSubQuestion models + resolution + matching + scoring
- Dual scoring (v2 + SQ) wired to OI runner
- Orchestrator generates SubQuestionIntents via design_case (validate + repair loop)
- E2E validated: 5 SQs generated by gpt-5.4, repair loop works (2 rejections -> fix)
- Treatment world: SQ score 0.983 vs v2 score 0.400

**No-data baseline probe (Session 10):**
- New script `oi_nodata_baseline.py`: gives solver brief + variable names, NO data
- CRITICAL FINDING: treatment (gap=-0.093) and education (gap=0.000) don't force
  investigation. Only ecosystem forces data use (gap=+0.570).
- Confirms A17: LLM priors answer correctly without data.

**Simpson's paradox world (Session 10):**
- `world_treatment_simpson()`: crude r(Treatment, Recovery) = -0.64, ATE = +0.4
- Confounding fix: GAP_MATERIAL assertion (direction-agnostic) for sign-reversal
- Subsumption table extended: confounding -> obs_assoc (0.40), confounding -> causal_effect (0.35)
- Investigation gap: v2 +0.132, correctness 0.75 -> 1.00

**Two new data-indexed worlds (Session 11):**
- `world_productivity()`: suppressor effect. Training-Productivity crude r ~ 0 despite
  ATE = 0.5. Team_size suppresses the relationship. Gap v2 = +0.488.
- `world_screen_time()`: confounding reversal. Screen-Academic crude r ~ +0.56 despite
  negative causal effect. Parental_income confounds. Gap v2 = +0.350.
- Both worlds validated: solver discovers the phenomena from data.
- 9 new tests (1849 total passing).

**Orchestrator SQ generation (Session 10):**
- CasePlan extended: oi_sub_questions, epistemic_regime, is_oi_mode
- validate_sub_questions(): grounding, roles, epistemology, portfolio, duplicates
- OI_MODE_PROMPT: SQ generation guidance for LLM
- 11 new tests for validation

**Research:** `research/notes/oi_investigation_gap.md` (concept + results + Codex debate)

### 2026-03-27 — OI real-LLM pilots + demo case generation

**OI pilot batch (6 runs, 3 curated worlds):**
- Ran ecosystem, treatment, education worlds with gpt-5.2-codex (solver) +
  gpt-5.4 (compiler). Warrant disabled for Alpha-0.
- Avg total=0.622, correctness=0.772, coverage=0.197.
- Solver genuinely investigates: regressions, confounding checks, mediation
  analysis, stratification. Epistemological humility (says "associated" not "causes").
- 6 systematic problems identified: P1 (confounding=0 credit), P2 (null findings),
  P3 (coverage low), P4 (precision gate), P5 (tags mismatch), P6 (import errors).
- Codex review: "solver is better than scorer, family match gates correctness."
- Analysis: `research/notes/oi_pilot_analysis_batch1.md`

**Scripts:**
- `scripts/oi_pilot_batch.py`: batch runner for OI pilots, JSON output
- `scripts/oi_demo_case.py`: generates `full_case_oi.md` report (5 parts)

**Fix:** `generate_src.py --solve` now works with SCMWorlds (was crashing on
ExactBayesSolver which only supports BN worlds). Added `_build_scm_dag_section()`.

**Demo experiments generated:**
- `experiments/oi_treatment/` — OI, score 0.769, correctness 1.0
- `experiments/oi_ecosystem/` — OI, score 0.571
- `experiments/air_pollution/` — task-based, orchestrator E2E
- `experiments/coral_reef/` — task-based, orchestrator E2E

### 2026-03-26 — Paso 2: Substrate minimum viable gate (3 quality gates)

**Code: quality gates en scm_task_gen.py**

- **Manipulability gate** (P4 fix): `_manipulable_nodes()` filtra solo ancestros
  causales del target como levers. `best_intervention` y `compare_interventions`
  ya no ofrecen variables downstream o no relacionadas.
- **Interaction gate** (P1 fix): `_find_interacting_pair()` busca exhaustivamente
  entre todos los ancestros observables. Elige el par con interaccion mas fuerte
  ("yes"). Si no hay interaccion real, devuelve el mejor par con "no" — mezcla
  natural sin bias. Reviewed by Codex: strongest-yes fix (evita falsos positivos
  con ATE ~0).
- **Mediation gate** (P3 fix): `_find_nontrivial_mediation()` prueba multiples
  treatments y mediadores. Solo acepta fraccion parcial (0.05-0.95). Reviewed by
  Codex: multi-treatment fix (no se queda con un solo treatment fijo).
- 11 nuevos tests (1505 total), lint limpio.

### 2026-03-25 — Mini-fixes + I11 Fase 2 eval + roadmap + merge to main

**Code: mini-fixes pre-evaluacion**

- **Entity check para `compare_interventions`**: ahora verifica `outcome`
  (target) ademas de `option_a`/`option_b`. Antes podia aceptar preguntas
  con outcome equivocado.
- **`desired_state` residuo BN eliminado**: removido como hint requerido de
  `best_intervention` y `compare_interventions`. Marcado legacy en tool schema.
  Bug oculto resuelto: best_intervention override nunca se aceptaba porque
  `desired_state` no matcheaba con texto "above median" del generador SCM.
- **`_hints_honored` para `best_intervention`**: ahora retorna True (no
  necesita hints — target_node es suficiente).
- **Thread management de Codex**: documentado como NON-NEGOTIABLE en CLAUDE.md.
  Siempre usar `codex-reply` con threadId existente.
- 1494 tests (3 nuevos), 0 failures.

**I11 Fase 2: primera evaluacion cualitativa formal**

- 3 SRCs post-I10 generados (football, coral reef, public health/asthma).
- Rubrica completa aplicada: 7 dimensiones + 6 critical failures.
- Score promedio: 1.3/2.0. Mejora significativa en capa visible vs pre-I10.
- Revisado con Codex (2 llamadas en thread continuo).
- 6 problemas nuevos documentados (P1-P6):
  - P1: interaction siempre "no" (task gen no busca pares con interaccion real)
  - P2: metadata identica "4 sites, 3 waves, 500 obs" en los 3 SRCs
  - P3: mediacion = 1.0 exacto (cadena lineal trivial)
  - P4: best_intervention incluye variables downstream
  - P5: direccion causal obvia desde priors (EL problema para LA PREGUNTA)
  - P6: dataset description mecanica (dump tecnico, no narrativa)
- 3 problemas confirmados recurrentes de eval anterior (H3, H4, H8).
- 2 problemas resueltos confirmados (H1 snake_case, H2 "setting X to Y").
- Registro completo: `research/synthesis/qualitative_eval_2026_03_25.md`
- Rubrica actualizada a v1.1 con 3 hallazgos nuevos (H9-H11).

**Roadmap: como seguimos**

- Consenso Claude + Codex: fixear lo que sobrevive a Open Investigation
  (sustrato causal, quality gates, anti-shortcuts). NO fixear cosmetica
  de preguntas Guided.
- Nuevo analisis A16 (quality gates), A17 (direccion desde priors), A18
  (datos mecanicos) en TODO.
- Roadmap refinado (consenso Claude + Codex): no hacer fase larga de fixes
  ni ir directo a ciegas. 4 pasos: (1) no-data probe, (2) substrate minimum
  viable gate, (3) Open Investigation Alpha con mundos curados, (4) mejorar
  generador.

**Merge: feature/scm-engine → main**

- Migracion BN→SCM completa. 1494 tests. Orchestrator wiring funciona.
- Fast-forward merge, 22 commits, 56 archivos, ~14.8K lineas nuevas.
- Docs canónicos actualizados: BN marcado legacy, SCM como engine principal.

### 2026-03-25 — I10 Fase 4: Question quality + Open Investigation vision

**Code: question realization quality (3 fixes + 2 architectural changes)**

- **`_semantic_name()` threshold tightened**: from `<80 chars` to `<45 chars
  AND <=6 words`. Prevents verbose descriptions (60-70 chars) from producing
  unreadable inline question text. Docstring updated.
- **`_sanitize_question_text()` added**: world-aware sanitization (replaces
  known node_ids, longest first) + generic fallback for remaining snake_case
  tokens. Applied in generation loop before consistency check.
- **ATE/mediation/interaction templates naturalized**: 3 rotating variants per
  type, phrased as domain researcher (not textbook). "Shifted from low to
  high" and "What fraction of the causal effect" eliminated.
- **Override logic refactored**: structural hints (intervention_node,
  condition_variable) are now the gate for accepting orchestrator questions.
  Entity matching downgraded to informational warning. Non-estimand types
  always safe to override. Result: most questions are now natural language
  from the orchestrator instead of mechanical templates.
- **`_hints_honored()` strengthened**: mediation now verifies treatment AND
  mediator match; interaction verifies treatment AND modifier.
- **`scm_problem_builder.py` thresholds aligned**: lines 235, 274 now use
  same `<45 chars, <=6 words` logic as `_semantic_name()`.
- 1491 tests, 3 E2E SRCs verified (air_pollution, football_v3, coral_v2).
  Reviewed with Codex (3 rounds).

**Vision: Open Investigation — free research with exact reward**

- Documented vision for future SREG evolution where the solver investigates
  freely and reports findings in natural language. A 3-layer architecture:
  Solver (free NL) -> LLM Translator (compiles to queries) -> SCM Verifier
  (exact truth). The LLM translates, never judges.
- 6 scoring dimensions: correctness, warrant (evidential justification),
  relevance (causal + epistemic + operational), coverage (against discoverable
  claims auto-generated from SCM), calibration, efficiency.
- Key insight: "warrant" dimension measures whether the solver had the right
  to make a claim based on evidence gathered, not just whether the claim is
  true. This separates real investigation from lucky prior-based guessing.
- Three modes: Guided (current), Scaffolded, Open. Mixed curriculum.
- Designed with Codex (3 sessions). See `research/synthesis/open_investigation_vision.md`.
- Tracked as A15 in TODO.md. Status: VISION, not scheduled for implementation.

### 2026-03-24 — I10 Fase 3: Break eval type monoculture

- **Prompt restructured**: eval types section rewritten from hierarchical
  categories ("CORE", "complementary, not primary") to flat alphabetical
  catalog with symmetric "Use when" / "Not when" guidance per type.
- **Two-stage workflow**: step 4 now requires drafting research questions in
  plain domain language BEFORE consulting the eval type catalog.
- **Operational type-fit rules**: replaced passive "re-examine if same subset"
  with concrete gating rules (e.g., "do not assign causal type unless
  question explicitly asks about intervention or counterfactual").
- **Tool definition neutralized**: `eval_type` field description no longer says
  "PRIMARY should almost always be causal" — now says "no type family is
  preferred a priori."
- **Overlap guidance**: boundary rules for similar types in both directions
  (causal AND non-causal pairs).
- **Results**: 4 previously-unused types appeared (ate, adjustment_set,
  compare_interventions, infer_target). 3 SRCs no longer share identical
  type patterns. Reviewed with Codex (2 rounds). 1479 tests.

### 2026-03-24 — P2: Semantic question naturalization (I10 Fase 2c)

- **Semantic name helpers**: `_semantic_name()`, `_semantic_aliases()`,
  `_semantic_evidence_desc()`, `_semantic_node_list()` in SCMTaskGenTool.
  Converts node_ids to human-readable names using variable_meta.description
  (if <80 chars) or node_id.replace('_', ' ').
- **12 task templates naturalized**: all `_*_task()` methods now use semantic
  names without single quotes. "setting X to Y" replaced with natural
  counterfactuals ("if X were at Y", "changing X to Y levels").
- **Entity matching updated**: `_entities_match_question()` and
  `_check_question_answer_consistency()` accept `world` param and match
  against semantic aliases (node_id, spaces version, description).
- **Problem builder updated**: `_build_question()` and `_build_description()`
  use semantic names without single quotes.
- **Orchestrator prompt updated**: `question_text` explicitly marked as visible
  in briefing. Prohibits snake_case, single quotes, "setting X to Y".
  Good/bad examples added.
- **Research note**: `research/notes/p2_semantic_question_naturalization.md`
  with full plan, Codex review, priority map, and metrics.
- Reviewed with Codex (2 rounds). 1479 tests.

### 2026-03-24 — First formal qualitative evaluation: 3 SRCs, 8 findings

- Applied qualitative rubric to 3 SRCs (football=current, coral_reef/vaca_muerta=old).
- Football scored 1.14/2.0 (Codex-adjusted), CF4 only. Old SRCs: DEFECTIVE.
- 8 findings registered (H1-H8): variable names as code, "setting X to Y",
  clean answers, metadata leak, causal warrant, measurement provenance,
  indexing realism, eval ontology leak.
- Root cause: questions born from scorer ontology, not from investigation.
- 4-priority action plan: P1 (root), P2 (naming), P3 (epistemic), P4 (metadata).
- Codex review identified 4 additional findings and stricter scoring.
- See `research/synthesis/qualitative_eval_2026_03_24.md`.

### 2026-03-24 — Formalize evaluation harness (I11 Fase 1b)

- **CLAUDE.md**: added "Harness de evaluacion" section with 3 levels,
  qualitative component, rubric evolution protocol, reference table.
- **/eval skill rewritten**: 8-step protocol covering quantitative +
  qualitative + no-data baseline probe + open discovery + registration.
- **Rubric evolution protocol**: discovery -> register -> promote (2+ SRCs).
- See `research/synthesis/qualitative_eval_rubric.md`.

### 2026-03-24 — Template rewrites + qualitative eval rubric (Fase 9 / I10 Fase 2)

- **compare_interventions template rewritten**: removed numeric threshold
  ("above 26.93"), "maximize", and "Answer 'A' or 'B'". Now: "Which of
  these two changes would have a greater impact on Y: setting A to X,
  or setting B to Z?"
- **interaction template simplified**: removed "Answer 'yes' if...or 'no'
  if..." exam-style instructions. Question is self-explanatory.
- **compare_interventions override enabled**: moved from NEVER_OVERRIDE to
  SAFE_OVERRIDE. Added estimand field (option_a, option_b, outcome) and
  entity check so orchestrator can improve wording when it mentions the
  correct variable names.
- **Orchestrator prompt relaxed**: "Use 3-5 questions with different
  eval_types" changed to "Pick eval_types that fit the scenario naturally
  -- repeating a type is fine."
- **Qualitative evaluation rubric**: new research synthesis doc with
  7 dimensions (0-2 scale) + 6 critical failures + no-data baseline probe
  protocol. Addresses A14 (ad-hoc qualitative review → formal framework).
- **Codex review**: 5 remaining findings documented in TODO I10
  (weak entity check, desired_state residue, should_condition wording,
  missing tests, snake_case in fallbacks).
- Reviewed with Codex. 1479 tests.

### 2026-03-24 — Brief/eval visibility separation (Fase 8 / I10 Fase 1)

- **Briefing shows research brief**: `export_briefing()` now displays the
  `Research Assignment` section (CasePlan's research_brief + deliverables)
  instead of only showing individual task questions.
- **Eval types hidden from briefing**: question headings no longer show
  `(eval_type)`. Was `### Question 1 (causal_effect)`, now `### Question 1`.
- **Target variable hidden from briefing**: removed `Target variable: X`
  line from each question in the briefing.
- **Target node hidden from solver prompt**: `_format_question()` no longer
  shows `Target: **{target_node}**`. Distribution types show
  `Submit a probability distribution over: states` instead.
- **Eval type hidden from solver format table**: removed `tt.value` column.
- **Answer key exported for SCM**: `_export_scm_answer_key()` now called
  in `--inspect` mode. Contains full scoring agenda (eval types, target
  nodes, estimands, correct answers, scoring methods).
- **TODO updated**: A2, I1, I8 marked done items. New A13 (problem analysis)
  and I10 (3-phase fix plan) added.
- Reviewed with Codex. 1479 tests.

### 2026-03-23 — Realistic observational data structure (Fase 7)

- **Panel structure**: `PanelConfig` + `apply_panel_structure()`. Datos con
  `site_id` y `wave`, random effects por sitio (variable-specific loadings),
  wave trend, dropout cumulativo. ICC realista (~0.08).
- **Proxy columns**: `_add_proxy_columns()` inyecta columnas correlacionadas
  con variables reales pero no causales. El solver debe distinguir signal de
  ruido.
- **Shared study frame**: `_multi_dataset_panel()` samplea UNA muestra
  maestra. Los 3 artifacts son vistas del mismo estudio (comparten
  sample_id), no muestras independientes.
- **Informative missingness**: 15-25% en background (vs 2% anterior). Mas
  missing en waves tardios. Dropout de sitios completos.
- **Narrative guard**: seccion "Data structure awareness" en orchestrator
  prompts. El brief menciona estudio multi-sitio y datos incompletos.
- 15 tests nuevos (panel, proxies, shared frame, missingness). 1479 totales.

### 2026-03-23 — Estimand separation + quality fixes (Fase 6b)

- **Estimand separation**: nuevo campo `Task.estimand` con parametros
  estructurados (treatment, outcome, v_low, v_high, mediator, modifier).
  Las preguntas de ATE/mediation ahora son naturales — sin boilerplate
  mecanico ("Submit a single numeric value"). El orchestrator's question_text
  tiene prioridad via override.
- **Entity-match gating**: override de pregunta solo se aplica cuando las
  entidades del estimand (treatment, mediator, modifier) aparecen en el
  question_text del orchestrator. Evita preguntas misleading.
- **Contrast sharing**: tasks del mismo treatment comparten v_low/v_high
  identicos via cache en `generate_from_plan()`.
- **Interaction scoring fix**: `_score_result()` ahora scorea INTERACTION
  via `score_should_condition` (antes score=0.0 silencioso).
- **Hint validation**: ATE, MEDIATION, INTERACTION agregados a
  `_HINT_REQUIRED_TYPES` del orchestrator.
- **Agent prompts**: nueva seccion "Analysis specification" renderiza el
  estimand como bloque separado de la pregunta natural.
- 5 tests nuevos (estimand + natural question). 1464 tests totales.

### 2026-03-21 — Task primitives: ATE, mediation, interaction (Fase 6)

- **3 nuevos task types**: `ate` (average treatment effect), `mediation`
  (effect decomposition), `interaction` (effect modification). De 9 a 12
  eval types totales.
- **SCMSolver**: +`ate()`, +`mediation_analysis()`, +`detect_interaction()`.
  Mediation usa binned nested counterfactual (20 bins). Interaction detecta
  heterogeneidad via ATE estratificado (threshold 30% relativo).
- **VerifierTool**: +`score_numeric()` — scoring por error relativo (0-1).
  Unico scoring nuevo; interaction reutiliza `should_condition`.
- **SCMTaskGenTool**: 3 generadores + 3 helpers (`_find_best_causal_parent`,
  `_find_mediator`, `_find_modifier`). Seleccion automatica de nodos con
  fallback a hints del orchestrator.
- **Agent layer**: `NUMERIC_TYPES` format (`{"value": float}`), submit tool,
  parsing, scoring dispatch. Interaction usa CHOICE_TYPES existente.
- **Orchestrator prompts**: 3 tipos en SYSTEM_PROMPT con guidance y ejemplos.
  `design_case` enum ampliado. Hints documentados. Mediation y effect
  modification removidos de "What we CANNOT represent yet".
- **Diagnostic harness**: `_NUMERIC_TYPES` set, baselines (0.0 para numeric,
  0.5 para interaction).
- **Training layer**: `EvalType` Literal ampliado, `NUMERIC_EVAL_TYPES`,
  `SubmitPayload.value`, validator actualizado.
- 23 tests nuevos (solver, task gen, verifier, training). 1459 tests totales.

### 2026-03-21 — Brief/eval separation (Fase 5)

- **Brief/eval separation**: el investigador ahora recibe un encargo de
  investigacion real en vez de preguntas tipo benchmark. `CasePlan` tiene
  `research_brief` (visible) y `deliverables` separados de `questions`
  (eval agenda oculta).
- **CasePlan model**: +`research_brief: str`, +`deliverables: list[str]`.
  Backward compatible (defaults vacios, fallback a questions[0]).
- **SCMProblemBuilder**: `_build_question()` prioriza brief sobre questions[0].
- **Orchestrator prompts**: seccion "Brief vs eval separation" con guidelines
  y ejemplos buenos/malos. `design_case` requiere research_brief y deliverables.
  `build_problem` description actualizada. Validacion runtime: brief vacio
  rechazado para SCM worlds.
- **Agent prompts**: `build_case_system_prompt()` muestra "Research Brief"
  como seccion visible antes de las preguntas individuales.
- **Codex review**: prompt contradictorio arreglado, validacion de brief
  vacio agregada, test de prompt-level agregado.
- 9 tests nuevos (case_plan, scm_problem_builder, scm_wiring). 1436 tests.
- E2E validado: 2 runs con gpt-5.4 (free goal + Vaca Muerta seed).

### 2026-03-21 — Orchestrator SCM wiring + BN removal (Fase 4)

- **Orchestrator SCM wiring**: el orchestrator ahora genera mundos SCM via
  `scm_construct`. Handler `_handle_scm_construct` parsea SCMSpec del LLM,
  compila ecuaciones, valida, y almacena el mundo.
- **Dispatch polimorfico**: world_check (auto-pass para SCM), apply_semantics
  (metadata-only), design_case (validacion adaptada), build_problem
  (usa SCMProblemBuilder) — todos manejan World | SCMWorld.
- **BN tools removidas de TOOL_DEFINITIONS**: world_gen, dag_generate,
  dag_construct ya no expuestos al LLM. El orchestrator es SCM-only.
  Los handlers BN siguen en el codigo para uso programatico.
- **SYSTEM_PROMPT**: reescrito para SCM. Documenta sintaxis de ecuaciones,
  guidelines de diseno de variables y ecuaciones.
- **SCMProblemBuilder**: acepta title/description/domain del orchestrator.
- **generate_src.py**: adaptado para SCMWorld (export JSON, DAG PNG,
  answer key, display).
- **Hallazgo critico**: las preguntas generadas parecen benchmark, no
  investigacion real. Diagnostico: brief, eval agenda y query formal
  estan colapsados en CasePlan.questions. Documentado en
  `research/notes/brief_vs_eval_separation.md`.
- 21 tests nuevos (test_scm_wiring.py). 1427 tests totales.
- E2E validado: 3 runs con gpt-5.4 (free goal + Vaca Muerta seed).

### 2026-03-20 — SCMWorldGenTool: declarative SCM world generation (Fase 3)

- **ExpressionCompiler** (`src/sreg/world/expression_compiler.py`): compila
  expression strings a EquationFn via ast.parse() + whitelist visitor.
  Sin catalogo fijo — cualquier ecuacion matematica. Soporta funciones math,
  distribuciones (normal, uniform, beta, gamma, etc.), y piecewise/ternarios.
- **SCMSpec** (`src/sreg/models/scm_spec.py`): modelo Pydantic declarativo
  para function calling. Validaciones: DAG, no duplicados, nombres reservados.
- **SCMWorldGenTool** (`src/sreg/tools/scm_world_gen.py`): compila spec,
  valida por sampling (NaN/Inf/varianza/extremos), construye SCMWorld.
- **Pipeline E2E**: SCMSpec -> SCMWorldGenTool -> SCMTaskGenTool -> SCMProblemBuilder.
- **Codex fixes**: nombres reservados bloqueados (normal, exp, etc.),
  edges duplicados rechazados, test de sync entre listas.
- 92 tests nuevos. 1406 tests totales, todos pasando.

### 2026-03-20 — SCM pipeline wiring (Fase 2c)

- **SCMProblemBuilder** (`src/sreg/tools/scm_problem_builder.py`): construye ResearchProblem
  desde SCMWorld. Data via `realistic_sample()` / `multi_dataset_sample()`.
  Filtra latentes de data, acciones, y descripciones.
- **SCMTaskGenTool.generate_from_plan()**: genera tasks desde CasePlan con node hints.
  Override de pregunta seguro para safe types, condicional para el resto.
  `_infer_latent_cause_task()` ahora respeta `spec.target_node`.
- **AgentSolver dispatch polimorfico**: `_make_solver(world)` despacha
  SCMWorld→SCMSolver, World→ExactBayesSolver. `solve()` y `solve_case()` aceptan
  `World | SCMWorld`. `solve()` single-task con SCMWorld → NotImplementedError.
- **37 tests nuevos**: SCMProblemBuilder (17), pipeline integration (20 incl. 4 Codex findings).
- **Workflow en CLAUDE.md**: paso 2 ahora dice "Codex review + Fix" explicitamente.
- 1314 tests totales, todos pasando.

### 2026-03-20 — SCMTaskGenTool: task generation for continuous worlds

- **SCMTaskGenTool** (`src/sreg/tools/scm_task_gen.py`): genera los 9 eval types
  desde SCMWorld + SCMSolver. Mirrors TaskGenTool pero para variables continuas.
  - Distribuciones discretizadas como histogramas de bins (equal-width, mean +/- 4*std).
  - Intervenciones: "low" (p25) y "high" (p75) por variable.
  - "Desired outcome": target above median (para best_intervention, compare_interventions).
  - Graph tasks (should_condition, adjustment_set) via SCMWorld.dag.
- **SCMWorld extendido**: campos `id`, `latent_variables`, propiedad `observable_variables`.
- **`get_all_backdoor_adjustment_sets()`**: enumeracion exhaustiva de sets minimales
  via backdoor criterion + networkx d-separation. Fallback heuristico para >15 candidatos.
- **41 tests** nuevos: 9 eval types + scoring compatibility + cross-task consistency.
- **Fixes post-review Codex**: bins equal-width (no quantile), precision alignment en
  intervenciones, warning log en fallback >15 candidatos.
- 1277 tests totales, todos pasando.

### 2026-03-20 — SCMSolver: robustness fixes + rigorous evaluation

- **Stopping criterion**: `optimal_action()` devuelve `None` si mejor IG < 0.02
  bits (por encima del noise floor MC ~0.01, debajo de senal real minima ~0.04).
  Trajectories terminan antes si no hay informacion util.
- **Strict mode**: `posterior_samples(strict=True)` y `interventional_samples(strict=True)`
  lanzan `ValueError` cuando rejection sampling falla, en vez de caer silenciosamente
  al marginal. Default sigue siendo `strict=False` (backward compatible).
- **Evaluacion rigurosa** (`scripts/eval_scm_solver.py`): comparacion contra
  posteriors analiticas cerradas (Linear Gaussian) via KS test.
  - Posterior KS pass: B|A 83%, C|A 90%, C|B 73%
  - Interventional con evidence: 100% KS pass
  - IG ranking 100% estable (5 seeds, 3 grafos)
  - Acceptance rates documentadas
- **60 tests** en SCMSolver (6 nuevos: StoppingCriterion + StrictMode).
- 1236 tests totales, todos pasando.

### 2026-03-20 — SCMSolver: Monte Carlo teacher for continuous worlds

- **SCMSolver** (`src/sreg/solver/scm_solver.py`): teacher de Monte Carlo
  que reemplaza ExactBayesSolver para mundos SCM continuos.
  - `posterior_samples()`: P(Y|evidence) via rejection sampling con tolerancia adaptiva.
  - `interventional_samples()`: P(Y|do(X=x)) via interventional sampling.
  - `information_gain()`: IG estimado via binned mutual information.
  - `optimal_action()` / `generate_trajectory()`: seleccion optima de observaciones.
- **Fixed bin edges for entropy**: sin bins fijos, histogramas adaptativos
  hacian que toda distribucion pareciera "uniforme", matando IG estimation.
- **Entropy en bits** (log2): consistente con ExactBayesSolver.
- **IG weight normalization**: bins sparse asumen entropy prior (conservador),
  evitando inflacion artificial del IG. Fix encontrado via Codex review.
- **Variable validation**: ValueError inmediato para variables inexistentes
  en evidence, do, o target. Evita bugs silenciosos de wiring.
- **54 tests** nuevos: posteriors, interventions, entropy, IG, trajectories,
  validation, multi-evidence, grafos 10 nodos, bits exactos.
- 1230 tests totales, todos pasando.

### 2026-03-20 — SCM realistic datasets + indirect measurements

- **scm_data.py**: capa de datos realistas para SCMWorld.
- **indirect_measurement_design.md**: mediciones proxy como nodos del SCM.
- Ver commit anterior para detalles completos.

### 2026-03-20 — SCM engine core (Fase 1)

- **SCMWorld**: grafo causal + ecuaciones Python + ruido + do-operator.
- **Scoring continuo**: KL histogram, KL Gaussian, Wasserstein distance.
- 33 tests. Ver commit anterior para detalles.

### 2026-03-16 — Deadline nudge + codex solver findings

- **Deadline nudge**: proactive warning when 75% of iterations used and
  questions remain unanswered. Fixes codex spending all iterations analyzing
  without submitting. Submission rate: 0/4 -> 4/4.
- **Max iterations**: 25 -> 40 for solver scripts.
- **Bug fix**: solver now handles distribution submitted as JSON string
  (codex sometimes sends `'{"yes": 0.7}'` instead of `{"yes": 0.7}`).
- **Vaca Muerta 3-mode experiment**: abstract (avg 0.62) > fictional (0.82)
  > realistic (8.30). Evidence that domain priors hurt when world is synthetic.
- **Codex as solver**: investigates data-driven (crosstabs, Cramer's V,
  naive Bayes, backdoor adjustment) unlike gpt-5.4 which answered from priors.

### 2026-03-16 — Migrate to Responses API + dual model support

- **Responses API migration**: entire codebase migrated from Chat Completions
  to OpenAI Responses API. Supports all models including reasoning models
  (gpt-5.2-codex, o-series) that don't support Chat Completions on Azure.
- **Dual model config**: `AZURE_MODEL` for orchestrator (gpt-5.4), new
  `AZURE_SOLVER_MODEL` for solver (gpt-5.2-codex). Configurable via env vars.
- **New module**: `src/sreg/inference/responses_utils.py` — helper to convert
  Chat Completions tool format to Responses API format.
- Multi-turn loops now use `previous_response_id` for token efficiency.
- All 1102 tests pass. No regressions.

### 2026-03-16 — Semantic modes + TODO restructure + Prompt overhaul + Inspiration Report v2

- **Semantic transform prototype**: `scripts/semantic_transform.py` transforms
  SRCs to 3 modes (realistic/fictional/abstract) as post-process. Same BN,
  different semantic layer. Tested on smoking + vaca_muerta cases.
- **TODO restructured**: analysis (A1-A7) separated from implementation (I1-I9).
  Research actions clarified: old observe/intervene/budget mechanics dead,
  future actions need fresh design. Solver investigates with python_exec.
- **Inspiration report**: "Research actions" -> "Investigation workflow",
  "ACTION GAP" -> "CASE DESIGN GAP".
- **7 SRCs regenerated** with new prompt (gpt-5.4, causal-first design).

### 2026-03-16 — Prompt overhaul + Inspiration Report v2 (earlier)

- **Orchestrator prompt rewritten**: eval types now described in research
  language (not statistical). Causal questions promoted as primary; infer_target
  demoted to complementary. Seed-first question design: identify paper's real
  questions, then map to eval types. Missing types documented (mediation,
  effect modification, selection bias, source attribution).
- **Default task_type changed**: causal_effect instead of infer_target.
- **Seed prompt improved**: section 4 now instructs to list actual paper
  questions first, then map to closest eval_type.
- **Inspiration Report v2**: 10 sections with detailed qualitative comparison.
  Variable mapping table, question-by-question with eval_type, data/evidence
  gap analysis, research actions comparison, and new section 10 with
  classified limitations (MISSING EVAL TYPE, ORCHESTRATOR WEAKNESS,
  DATA/EVIDENCE GAP, ACTION GAP, STRUCTURAL LIMITATION) with actionable fixes.
  Removed overall score — report is qualitative, not quantitative.
- **Model upgraded**: gpt-5.2-chat -> gpt-5.4.
- **NOTES.md created**: user inbox for ideas, problems, and open questions.
  Added to CLAUDE.md doc table and promotion rules.
- **Vaca Muerta seed**: copied from research_seed.md to seeds/vaca_muerta.md.
  Previous eval used wrong seed (causal_observational.pdf = epidemiology paper).
- **run_inspiration_reports.py**: batch script to generate reports for existing
  experiments.
- **7-SRC inspiration report findings**: Research Actions 0% in 5/7 cases,
  infer_target always primary (now fixed), missing question types identified.
- **output/ directory removed**: stale, experiments/ is the canonical location.

### 2026-03-15 — 5-SRC multi-domain evaluation + CPD direction fix
- **CPD.1 COMPLETE**: directional CPDs via signed ordinal scoring model.
  dag_construct edges accept direction (positive/negative). Verified E2E:
  smoking=heavy -> 97% preterm. Smooth interpolation, Codex reviewed.
- **5-SRC evaluation** across 5 domains (oil&gas, epidemiology, occupational
  health, marine ecology, education). All generate + solve end-to-end.
- **Critical finding**: solver used 0 research_actions in 4/5 cases.
  The environment doesn't force investigation. Dataset exposes everything.
  Codex: "benchmark causal, not research environment yet."
- **Next priority**: LOOP.1 — hide variables to force active investigation.
- TODO rewritten with LOOP.1-3 as top priority.
- WORLD_DESIGN.md: new section with 5-SRC evaluation findings.

### 2026-03-14 — Inspiration Report (PS.2)
- **`harness/inspiration_report.py`**: compares seed vs SRC on 8 dimensions
  with structured profiles, programmatic scoring, and markdown report.
- **LLM seed extraction**: extracts InspirationProfile (variables, causal
  features, question types, data problems) from seed text via LLM.
- **SRC extraction**: programmatic profile from world nodes, edges, task types,
  causal structure detection (colliders, confounders, mediators).
- **Question type normalization**: maps LLM-extracted types (prediction,
  feature_importance) to SREG eval types (infer_target, next_best_observation).
- **Weighted scoring**: Research Questions (2.5x) and Scale (2x) weigh most.
- **`generate_src.py --report`**: generates inspiration_report.md alongside SRC.
- Vaca Muerta test: 50% overall (scale 75%, questions 77%, domain 75%).

### 2026-03-14 — Paper-seeded SRCs (PS.1) + inspiration dimensions
- **PDF seed support**: `generate_src.py --seed-file paper.pdf` extracts text
  via pymupdf and feeds it to the orchestrator. Any seed format works (paper,
  business case, operational problem, markdown, PDF).
- **8 inspiration dimensions** documented in PROJECT.md and WORLD_DESIGN.md:
  domain, scale, causal structure, data types, type of work, research questions,
  signal/noise, available actions.
- **Scale matching**: prompt emphasizes matching seed's variable count.
  Vaca Muerta improved from 10 to 15 nodes (+50% coverage).
- **E2E tested**: PDF (Nature agriculture paper), markdown (Vaca Muerta, smoking).
- **seeds/ directory** for paper seeds.

### 2026-03-14 — Tool-calling engine + benchmarks with tools (INF.2, BENCH.2-3)
- **Shared tool-calling engine** (`agent/engine.py`): reusable multi-turn tool loop
  with python_exec + think. Used by solver and benchmarks. Codex-reviewed.
- **Transformers backend** (`agent/transformers_backend.py`): HuggingFace local
  inference with Hermes tool-call parsing. Separated from engine per Codex advice.
- **ToolEnrichedClient** (`inference/tool_client.py`): wraps any ModelClient,
  adds python_exec + think transparently. Benchmark adapters don't change.
- **run_benchmark.py**: `--with-tools` (python_exec + think), `--base-url`,
  `--api-key` for vLLM or custom backends. 1101 tests.

### 2026-03-14 — Integrate benchmarks + training from worktrees (BENCH.1, TRAIN.1-4)
- **Benchmarks integrated**: CLadder, QRData, DiscoveryBench adapters from worktree
  benchmark-suite. OpenAIClient (ModelClient protocol). run_benchmark.py script.
  BEFORE scores documented (GPT-5.2: CLadder 78%, QRData 38%, DiscoveryBench 0.299).
- **Training module integrated**: SregEnv (verifiers adapter over EpisodeRunner),
  adapters, types, validators, rubric, dataset generation, prompts. From worktree
  rl-env-verifiers.
- **python_exec unified**: training/tools.py now imports from agent/python_exec.py
  (single kernel). _build_python_namespace delegates to make_python_namespace.
  Identical semantics between diagnostic and training paths.
- 783 -> 1086 tests.

### 2026-03-14 — Unified inference infrastructure (INF.1, INF.3, PYEX.1)
- **Configurable solver backend**: `generate_src.py` now accepts `--solver-model`,
  `--solver-base-url`, `--solver-api-key` flags. Supports Azure, vLLM, or any
  OpenAI-compatible API for the solver (orchestrator stays on Azure).
- **serve_model.sh**: script to setup vLLM and serve Qwen (or other models) on
  OpenAI-compatible API with Hermes tool calling. From worktree rl-env-verifiers.
- **python_exec ExecResult**: `execute_code()` returns structured `ExecResult(output,
  ok, truncated)` instead of plain string. 17 new tests for python_exec.
- **Codex review**: removed fake ThreadPoolExecutor timeout (can't truly kill threads
  in CPython, risks namespace corruption). Honest about limitation in docstring.
- TODO.md rewritten: MERGE.1-2 replaced with proper INF/PYEX/BENCH/TRAIN plan.
  Three solver backends, tools separation (solver tools vs SREG tools), verifiers
  as thin adapter. 783 tests.

### 2026-03-14 — think() tool + full_case.md report
- **`think(reasoning)` tool**: forces model to externalize reasoning as a tool call.
  Free, no environment effect. Renders as [SOLVER REASONS] in reports. Helps debug
  agent decision-making when models skip content tokens before tool calls.
- **`full_case.md`** (NEW output from `--solve`): complete case report in one file.
  Part 1: exact system prompt + dataset info (what the solver received).
  Part 2: full conversation with code, outputs, measurements, reasoning, submits.
  Part 3: evaluation table + per-question detail with correct vs solver answers.
- Prompt improvements: clarified `df` has ALL rows (not just preview), listed tools
  as capabilities not instructions, removed prescriptive phase ordering.

### 2026-03-14 — S.5: Agent Solver v3 — python_exec + unified case solving
- **`src/sreg/agent/python_exec.py`** (NEW): persistent Python interpreter for the agent.
  Sandboxed exec() with namespace persistence (like Jupyter). Pre-loads numpy, pandas,
  scipy. Dataset available as `df`. Observations synced as `observations` dict.
  Import whitelist, restricted builtins, code/output limits. FREE (no budget cost).
- **`AgentSolver.solve_case()`** (NEW): solves all tasks in a single episode.
  Shared budget, shared observations. Agent receives all questions at once.
  `submit(question=N, ...)` per question. Nudge mechanism if agent writes text
  instead of tool calls.
- **`CaseResult`** (NEW): holds per-question AgentResults from unified solving.
- **`build_case_system_prompt()`** + **`build_case_tools()`**: multi-task prompt
  with 3-phase investigation structure (analyze data → gather evidence → submit).
  Multi-format submit tool (distribution, choice, variables, node+state).
- **`generate_src.py --solve`**: now uses unified `solve_case()`. Single episode
  for all tasks. Trajectory shows full conversation with python code blocks.
- **Trajectory rendering**: python code as ```python blocks, research_action results
  concise, submit as formatted JSON, environment outputs as plain text.
- **`agent_trajectory.py`**: handles research_action and python_exec tool calls.

### 2026-03-13 — generate_src.py: official SRC generation script
- **`scripts/generate_src.py`**: single entry point to generate, inspect, and evaluate SRCs.
  - `--goal` or `--seed-file` for research context
  - `--inspect`: exports briefing.md, dataset.csv, answer_key.md (quick guide + BN + CPDs + correct answers), dag.png
  - `--solve`: runs agent on each task, exports evaluation.md (scores) + trajectory.md (reasoning)
  - `--solve` implies `--inspect`
- **Answer key** includes: Mermaid DAG diagram, qualitative quick guide (variable importance via IG,
  causal relationship strengths, baseline), formal BN specification (nodes, edges, CPDs), correct answers.
- **DAG visualization**: matplotlib PNG with layered layout, color-coded nodes (latent=red, observable=green, target=yellow).
- 7 legacy scripts removed (test_orchestrator, test_e2e, test_agent, mini_benchmark, diagnostic_batch, batch_eval, qualitative_analysis). 13 scripts -> 6.

### 2026-03-13 — Docs cleanup: SREG core vs agent harness separation
- Separated SREG environment tools (research_action, submit) from agent harness (python_exec, etc.)
- Agent harness, training pipeline, benchmarks marked as separate workstreams in TODO.md
- Fase -1 contracts clarified as preparatory interfaces, not SREG core

### 2026-03-13 — Rich Actions Slice B: intervene actions (do-operations)
- **ActionType.INTERVENE** + **ActionDef.effects** (`dict[str, str]`): structured
  intervention payload. AvailableAction.intervention_values in semantic layer.
- **EpisodeRunner refactor**: `_handle_rich_action()` dispatches observe/intervene.
  `_execute_intervene()` fixes nodes to specified states, tracks in `_interventions`
  (separate from `_evidence`). `_get_node_value()` samples descendants from
  interventional distribution P(Y | do(X=x), evidence) via pgmpy CausalInference.
- **Post-intervention consistency**: `_invalidate_descendants()` removes stale
  evidence. `true_posterior()` and `_handle_query()` use `causal_query` when
  interventions are active. Monotonic RNG counter for correct sampling.
- **Conflict guards**: cannot observe+intervene same node, cannot intervene twice,
  action type mismatch validation (Action.type vs ActionDef.action_type).
- **ProblemBuilder**: `_build_intervene_actions()` for observable target parents.
  One action per (node, state) pair. Cost 3, capped at 4 actions.
- **Agent solver**: maps ActionDef.action_type to ActionType for clean traces.
- **Prompts**: explains Measurements vs Experiments (do-operations).
- **Codex review**: 3 findings fixed (type mismatch validation, RNG reseeding,
  _invalidate_descendants limitation documented).
- 11 new tests. 766 tests total.

### 2026-03-13 — Fase -1: Shared contracts for parallel development
- **Inference protocol** (`src/sreg/inference/`): Provider-agnostic LLM interface.
  `ModelClient` Protocol, `Message`, `ChatResponse`, `ToolSpec`, `ToolCall`, `Usage`.
  StrEnum roles/finish reasons. Supports OpenAI API and vLLM local.
- **Benchmark format** (`src/sreg/models/benchmark.py`): `BenchmarkResult` with
  reproducibility metadata (seed, prompt/code/dataset versions, toolset version).
  `BenchmarkComparison` for BEFORE/AFTER transfer evaluation.
- **Code execution contract** (`src/sreg/models/code_exec.py`): `CodeExecConfig`
  (timeout, memory, allowed imports) and `CodeExecResult` (status, stdout/stderr,
  truncation flags). Implementation TBD.
- **Environment protocol** (`src/sreg/models/env_protocol.py`): `SREGEnvironment`
  Protocol (reset/step), `EnvAction`, `EnvObservation`, `EnvStepResult`.
  Gymnasium-inspired interface for verifiers MultiTurnEnv integration.
- **Agent toolset** (`src/sreg/models/agent_tools.py`): `AgentTool`, `AgentToolset`,
  canonical tool definitions (RESEARCH_ACTION, PYTHON_EXEC, SUBMIT).
  Same tools for training, diagnostic, and benchmarks.
- 25 new contract tests. 757 tests total.
- **Codex review**: 4 findings (1 P0 fixed: `model_config` -> `inference_config`
  to avoid Pydantic v2 reserved name conflict).

### 2026-03-12 — S.4 MVP-1: observe(variable) -> research_action(action_id)
- **Agent interface redesign**: Agent now selects from an action catalog by ID instead of
  requesting individual variables. Tool renamed `observe` -> `research_action(action_id)`.
  Aligns with PROJECT.md vision of typed research actions.
- **AvailableAction.id**: New field with auto-generation from nodes. ProblemBuilder generates
  explicit IDs (`measure_X`, `survey_X_Y`). EpisodeGenTool uses AvailableAction.id for ActionDefs.
- **Action catalog in prompt**: Actions displayed with ID, type label (Measurement/Experiment/
  Data request/Consultation), cost, and description.
- **Budget tracking fix**: Corrected from `+= 1` to `budget_total - remaining` (accounts for
  variable costs in rich actions).
- **EpisodeRunner guard**: Rejects non-observe action types until Slice B implementation.
- **Prompt cleanup**: Removed hypothesis_selection coaching ("Compare the NUMBERS...").
  SREG presents information, does not coach the agent on how to reason.
- **Generic prompt language**: "actions return findings" instead of "measurements reveal values".
- **Legacy backward compat**: `observe(variable)` still works via `_handle_observe`.
- **Codex review**: No P0 bugs. Deuda: ID uniqueness validation, legacy observe divergence.
- 732 tests (7 new + 1 guard).

### 2026-03-12 — Qualitative analysis fixes: compare_interventions + hypothesis_selection
- **compare_interventions semantic inversion fix**: Auto-generated question (which contains
  the exact intervention states from correct_answer) is no longer overridden by the
  orchestrator's narrative question. Prevents "increasing X" in question but "X:weak" in
  answer. New `_NEVER_OVERRIDE_QUESTION_TYPES` set. 2 tests (1 new + 1 updated).
- **hypothesis_selection framing fix**: Agent prompt now always shows candidate hypotheses
  as numbered probability distributions with explicit instruction to compare NUMBERS not
  narratives. Submit instruction updated: "pick the distribution that best matches evidence".
- **Qualitative analysis script**: New `scripts/qualitative_analysis.py` for step-by-step
  agent reasoning inspection. 3-case run with gpt-5.3 in `experiments/qualitative_20260312_124512/`.
- **Root cause from qualitative analysis**: agent fails hypothesis_selection because it
  reasons narratively ("which story sounds right") not formally ("which distribution matches").
  compare_interventions had real SREG bug (semantic inversion). Both fixed.
- 725 tests (1 new).

### 2026-03-12 — DIAG.4: ZERO_OBS reclassification + Dirichlet distractor fix
- **ZERO_OBS reclassification**: NBO and should_condition with 0 observations and correct
  answer no longer flagged as failures (return `None` instead of "ZERO_OBS_CORRECT").
  These types have valid immediate-answer behavior.
- **Hypothesis D distractor**: Replaced reversed posterior (identical when symmetric) with
  Dirichlet-sampled random distribution. Added KL < 0.05 distinguishability warning.
- **Codex review**: identified deuda — explicit label instead of None, resample on low KL,
  test distractor generation quality. Logged for future iteration.
- 724 tests (3 new/replaced).

### 2026-03-12 — P0 cleanup: submit format, budget wording, apply_semantics, consistency check
- **Agent submit format**: Tool description now shows correct vs wrong format explicitly.
  Auto-correction in code: flat keys are silently normalized instead of rejected.
- **Budget wording**: "N observations" -> "research budget of N units" across agent prompts,
  task_gen, and problem_builder. Costs now described as variable.
- **apply_semantics first-call fix**: Prompt clarifies identity mappings are required.
  Code auto-completes identity mappings when node_renames is empty or partial.
- **Consistency check**: New `_check_question_answer_consistency()` validates that question
  text mentions nodes from the formal answer. Logs WARNING on mismatch. 4 new tests.
- Codex review incorporated: auto-correction in code (not just prompts), test coverage.
- 722 tests (4 new).

### 2026-03-12 — Complete P0 fix: node hints connected to orchestrator + manual audit
- **P0 fix completion**: Node hints now flow end-to-end from orchestrator LLM to task
  generators. Three changes:
  1. `design_case` tool schema exposes hint fields (`intervention_node`, `desired_state`,
     `compare_nodes`, `condition_variable`) so the orchestrator LLM can specify them.
  2. `_handle_design_case()` extracts hints and validates them: required for the 5
     node-sensitive eval types (error if missing → LLM retries), node names must be
     OBSERVABLE (not latent/target), `desired_state` must be a valid state of target node.
  3. System prompt updated with "Node hints — REQUIRED" section guiding the LLM.
- **Manual audit of 3 SRCs**: Generated 3 targeted cases (latent/confounding, interventions,
  evidence/diagnosis) to verify all 9 eval types. Found that without hints, 5/9 types
  had question/answer mismatches. After fix: 4/4 MATCH on the worst case (agriculture).
  Key finding: `best_intervention` was generating "maximize LOW crop yield" (absurd) —
  now correctly generates "maximize high crop yield".
- **Codex collaboration workflow**: Codex (OpenAI) as critical second opinion via MCP.
  Mandatory for code review, recommended for strategy/architecture. Claude leads,
  Codex advises. Flexible guidelines, not rigid checklist.
- 718 tests (22 new: 9 node hints on task_gen, 13 hint validation on orchestrator).

### 2026-03-11 — Rename benchmark to diagnostic + transfer benchmark concept + external benchmarks doc
- **Terminology change**: "benchmark" -> "diagnostic" for the internal environment quality
  control pipeline. Reserved "benchmark" for the real test: transfer experiment on external
  benchmarks (BEFORE -> TRAIN on SREG -> AFTER).
- **`docs/EXTERNAL_BENCHMARKS.md`** created: consolidated analysis of 20+ external benchmarks
  from two independent sources (Claude + GPT). Recommended suite: CLadder (causal reasoning,
  10K questions, deterministic), QRData (causal + data, 411 questions), DiscoveryBench
  (hypothesis from data, 264 tasks), SciGym (experimental cycle, 350 systems).
  Includes BEFORE/AFTER protocol, controls, success criteria, overfitting risks.
- **Three-level QA** documented across PROJECT.md, CLAUDE.md, CURRENT_STATE.md:
  1. Tests + Validation (pre-commit): "did I break something?"
  2. Environment Diagnostic (periodic): "are the environments good?"
  3. Transfer Benchmark (FUTURE): "does training on SREG improve policies?"
- **TODO.md**: BM.* renamed to DIAG.*, new BENCH.1-BENCH.5 section for transfer benchmark.
- **Skills updated**: `/eval` and `/precommit` reflect diagnostic terminology.
- **Code rename complete**: `benchmark.py` -> `diagnostic.py`, `run_benchmark.py` ->
  `run_diagnostic.py`, `test_benchmark.py` -> `test_diagnostic.py`. All classes renamed:
  BenchmarkRunner -> DiagnosticRunner, BenchmarkReport -> DiagnosticReport,
  format_benchmark_report -> format_diagnostic_report, save_benchmark -> save_diagnostic.

### 2026-03-11 — Documentation rewrite: SREG purpose ultra-clear
- **PROJECT.md, CLAUDE.md, CURRENT_STATE.md rewritten** to make SREG's purpose crystal clear:
  SREG generates synthetic research environments with exact reward signals, designed for
  training policy models that do science via RL. SREG generates + computes rewards; it does
  NOT train policies (no training loop, no optimizer, no train.py).
- Reframed as verifier environment (like PRIME Intellect for math, but for scientific reasoning).
- New terminology: SRC = training environment, Teacher = optimal policy, Policy = any agent.
- Backlog: replaced "RL training loop" with "Export formal de entornos para integracion con RL".

### 2026-03-11 — Per-type baseline scoring + 15-SRC benchmark
- **`src/sreg/harness/benchmark.py`**: `compute_baseline_score()` and `beats_baseline()` functions.
  Computes random baseline per eval type: KL(uniform||correct) for distributions, 0.5 for binary
  choice, 1/N for hypothesis_selection, mean/max ratios for NBO and best_intervention.
  Direction-aware comparison (lower KL = beats, higher accuracy = beats).
- **`TaskResult`**: new fields `baseline_score`, `agent_beats_baseline`.
- **`TypeMetrics`**: new fields `baseline_scores`, `n_baseline_computed`, `n_beats_baseline`.
- **`format_benchmark_report()`**: new "BASELINE COMPARISON (random guess)" section.
- **24 new tests** (54 total in test_benchmark.py): TestComputeBaseline (14), TestBeatsBaseline (8),
  TestBaselineAggregation (2). 696 tests total.
- **`scripts/run_benchmark.py`**: expanded to 15 goals (from 5) across diverse domains.
  Default --cases=15. Output shows baseline comparison per task.
- **`experiments/bench_20260311_15srcs/`**: 14/15 SRCs completed, 57 tasks, 9/9 eval types.
  Key findings: causal_effect and compare_interventions beat baseline 71%. hypothesis_selection
  WORSE than random (17% beats). NBO suspicious (100% correct, 100% ZERO_OBS). should_condition
  and infer_latent_cause struggle (25%, 0% beats respectively).

### 2026-03-11 — First full benchmark: 5 SRCs, 19 tasks, 9/9 eval types
- **`experiments/bench_20260311_5srcs/`**: first benchmark covering all 9 eval types.
  5/5 SRCs completed, 100% submit, 0 format errors. infer_target consistently GOOD+.
  causal_effect acceptable (KL ~0.49). ZERO_OBS_CORRECT in 4/19 binary choice tasks
  (preliminary — could be guessing at 50%). N per type still low (1-5).
- Updated `experiments/index.md` with diag and bench entries.

### 2026-03-11 — BenchmarkRunner: type-aware verdicts and failure classification
- **`src/sreg/harness/benchmark.py`**: BenchmarkRunner class — importable library for
  running real E2E benchmarks. Type-aware verdict (KL thresholds for distribution types,
  accuracy for choice types). Type-aware failure modes (ZERO_OBS_LOW_KL, ZERO_OBS_CORRECT,
  INCORRECT, HIGH_KL, FORMAT_RETRY — no global TRIVIAL). Marked PARTIAL always.
- **`scripts/run_benchmark.py`**: thin script wrapper for BenchmarkRunner.
- **30 new tests** (`tests/harness/test_benchmark.py`): verdict classification (11),
  failure mode classification (12), aggregation (5), report formatting (2).
- Absorbs patterns from diagnostic_batch.py and mini_benchmark.py into reusable library.
- 672 tests total.

### 2026-03-11 — S.2 Diagnostic pipeline: real multi-type E2E validation
- **`scripts/diagnostic_batch.py`** (rewritten): generates N SRCs via real orchestrator,
  runs agent on EACH task (not just infer_target), collects per-eval-type metrics,
  classifies failure modes (TRIVIAL, NO_SUBMIT, WRONG_ANSWER, HIGH_KL, FORMAT_ERROR),
  generates diagnostic report. Saves summary + report + per-task trajectories.
- **`src/sreg/harness/agent_trajectory.py`**: `AgentTrajectory.submitted_answer` now `Any`
  (was `dict[str, float]`). Added `task_type` field.
- **First real multi-type diagnostic** (`experiments/diag_20260311_first/`):
  3 SRCs, 11 tasks, 7/9 eval types exercised, 91% submission rate, 0 format errors.
  Key finding: choice types (hypothesis, compare, best_intervention) tend to be trivial
  (agent answers without observing) or wrong. Distribution types (infer_target, causal_effect)
  work well when agent submits.

### 2026-03-11 — Multi-type agent harness: submit + prompt + scoring for all 9 eval types
- **`src/sreg/agent/prompts.py`**: dynamic submit tool per task type (distribution, choice,
  intervention, variable set). System prompt adapts question, target node, format instructions.
  Only overrides states_str for distribution types (not choice/NBO/hypothesis).
- **`src/sreg/agent/agent.py`**: `_handle_submit()` routes to 4 specialized handlers.
  `_submit_distribution()` validates against task-specific states (not just problem.target_states).
  `_score_result()` routes to correct verifier method per type.
  NBO -> choice + score_nbo(). causal_effect/infer_latent_cause -> task.correct_answer.
- **54 agent tests** (was ~15). Full coverage: tool generation, dispatch, scoring, full loops
  for all 9 types. Tests for bug fixes (prompt states, distribution validation, NBO error msg).
- **NOT "the agent solves all 9 types well"** — that requires the real benchmark. This is
  correct plumbing: the harness accepts, formats, and scores all 9 types correctly.
- **Known limitation**: observe remains single-node/cost-1 (Rich Actions S.4 pending).

### 2026-03-11 — First mini benchmark: 3 real SRCs end-to-end
- **`scripts/mini_benchmark.py`**: runs N real SRCs via orchestrator + agent + teacher.
  5 varied goals (marine ecology, epidemiology, materials science, agriculture, geology).
  Per-case: orchestrator generates -> worldcheck -> teacher trajectory -> random baseline ->
  agent solver -> trajectory extraction -> comparison. Summary table + failure mode analysis.
- **First real experiment** (`experiments/mini_20260311_100704/`):
  - Orchestrator: 100% completion, all WorldCheck PASS, 4 eval types per case
  - Agent: 100% submit rate, 1/3 beats random. KL range 0.005-0.54
  - Verdicts: 1 EXCELLENT, 1 GOOD, 1 FAIR
  - Key finding: agent chooses variables by "common sense", not information gain
  - Submit format error in 2/3 cases (agent forgets `distribution` key)
- **Limitation mayor documentada**: solo se evalua infer_target. Los otros 8 eval types
  no tienen solver. No bloquea el mini benchmark pero limita las conclusiones sobre el
  producto completo segun PROJECT.md.
- **SRC** (Synthetic Research Case) defined as project terminology: the complete case
  generated by the system (world + problem + tasks + data).
- `experiments/index.md` created with first experiment entry.
- `EVAL_DESIGN.md` added to CLAUDE.md docs list.

### 2026-03-10 — Quality assurance strategy: tests vs benchmark
- **Documented the two-level QA strategy** across PROJECT.md, CLAUDE.md, TODO.md,
  CURRENT_STATE.md, and skills (`/eval`, `/precommit`):
  - Level 1: Tests + Validation (pre-commit) — unit tests + E2E smoke. "Did I break something?"
  - Level 2: Benchmark & Diagnostic (periodic) — real system E2E with LLM. "Is the product good?"
- **Key principle**: the benchmark ALWAYS uses the real system (LLM, orchestrator,
  CasePlan, semantics). No toy worlds, no fabricated inputs.
- **Identified QualitySuite v2 gap**: only covers 3/9 eval types with programmatic worlds.
  Needs evolution to full benchmark with real pipeline.
- **Planned benchmark tasks** (BM.1-BM.5 in TODO.md): implement real E2E benchmark script,
  create experiments/ directory, update quality.py for all eval types, consolidate scripts.
- **Updated `/eval` skill**: now reflects benchmark philosophy (real system, two outputs:
  aggregate metrics + failure mode analysis).
- **Updated `/precommit` skill**: clearer separation between validation (Level 1) and
  benchmark impact check.

### 2026-03-10 — Agent trajectory inspection (S.1)
- **New module `src/sreg/harness/agent_trajectory.py`**: `AgentTrajectoryStep` and
  `AgentTrajectory` Pydantic models. `extract_agent_trajectory()` post-processes
  the raw chat messages from `AgentResult` into structured, inspectable steps
  (thinking, tool call, observation, error, submit). `export_agent_trajectories()`
  writes JSONL.
- **New module `src/sreg/harness/comparison.py`**: `TrajectoryComparison` model +
  `compare_trajectories()` builds side-by-side agent vs teacher comparison with
  verdict (EXCELLENT/GOOD/FAIR/POOR/NO_SUBMIT).
- **New script `scripts/view_trajectory.py`**: CLI viewer for agent trajectories
  and comparisons. Auto-detects file type.
- **`scripts/test_agent.py`**: new `--save-trajectory DIR` flag. Saves agent
  trajectory JSON + comparison JSON after running.
- 18 new tests (601 total): extraction, serialization, export, comparison.
- Zero changes to `AgentSolver.solve()` — trajectories extracted post-hoc.

### 2026-03-10 — Fix question/answer mismatch bug + budget wording
- **BUG FIX (P0)**: `generate_from_plan` was overriding question text for ALL eval
  types, causing mismatches where the question mentioned different nodes/interventions
  than the correct_answer. Now only safe types (infer_target, NBO, hypothesis_selection,
  infer_latent_cause) get the plan's custom text. Intervention-dependent types
  (causal_effect, best_intervention, compare_interventions, adjustment_set,
  should_condition) keep their auto-generated question that matches the answer.
- **Budget wording**: changed from "N observaciones" to "N unidades de investigacion"
  in display.py (terminal + HTML). Reflects that actions have varied costs now.
- 2 new tests (583 total): safe vs unsafe question override in generate_from_plan.
- Documented 6 design issues from E2E case analysis in TODO.md.

### 2026-03-10 — Activate rich actions and CasePlan question in build_problem
- **Orchestrator `build_problem`** now passes `rich_actions=True` and the CasePlan
  (if available) to `ProblemBuilder.build()`. This means the agent sees varied-cost
  actions and the LLM-designed research question instead of the generic template.
- **`ProblemBuilder.build()`** accepts `case_plan: CasePlan | None`. When provided,
  `_build_question()` uses the primary question's `question_text` from the plan.
- 3 new tests (581 total): case_plan question used, fallback to generic, combo with rich_actions.

### 2026-03-10 — Case inspection tooling: --seed, --export, /run skill
- **`test_orchestrator.py` enhanced**: `--seed N` (reproducibility hint), `--export path.json`
  (full case export), `--verbose` (raw HTTP logs). Step-by-step process display with compact
  tool args, design_case/dag_construct result summaries, case plan questions with rationale,
  generated tasks with correct answers, research problem view.
- **JSON export**: metadata (timestamp, goal, model), process (all tool calls with args/results),
  world (nodes, edges, scenario), case_plan (questions, rationale), tasks (type, question,
  correct answer), research_problem (narrative, data_assets, available_actions).
- **`/run` skill**: new skill for running the orchestrator. Parses topic, builds goal,
  auto-exports with timestamp, reports findings in Spanish.
- **`README.md` rewritten**: quick start, generate and inspect research cases, script examples,
  eval types table (9 types), JSON export structure, LLM integration docs.
- **`TODO.md`**: added Rich Actions Slice A design debt section (sibling grouping and
  target-proximity costs are provisional heuristics).

### 2026-03-10 — Rich Actions Slice A: typed, multi-node, varied-cost actions
- **`ResearchActionType` enum** in `research_problem.py`: `observe`, `intervene`,
  `request_dataset`, `consult` (reserved). Named `ResearchActionType` to avoid
  collision with existing `ActionType` in episode.py (agent interaction types).
- **`AvailableAction` expanded**: `action_type`, `nodes: list[str]`, backward-compat
  `node: str` (auto-synced via model_validator). Supports multi-node actions.
- **`ActionDef` model** in episode.py: formal action definition (id, action_type,
  nodes, cost). `Episode.action_defs` for rich mode, empty = legacy mode.
- **`StepResult.extra_observations`**: additional observations from compound actions.
- **`EpisodeRunner` multi-node**: compound observe via `action_id` reveals N nodes
  in one step. Validates no double-use, budget checks, node overlap.
- **`ProblemBuilder.rich_actions`**: `rich_actions=True` flag generates varied costs
  (target-adjacent cost 2) and compound actions from sibling groups (nodes sharing
  a parent in the DAG). Max 1 compound action per problem.
- **`EpisodeGenTool` rich mode**: accepts `available_actions` parameter, generates
  matching `ActionDef`s and backward-compat `node_costs`.
- **Teacher IG/cost optimization**: `optimal_action()` and `generate_trajectory()`
  accept `costs: dict[str, int]` parameter. Optimizes IG/cost ratio instead of
  pure IG. Budget-aware: skips nodes that don't fit remaining budget.
- 26 new tests (578 total). E2E: 3 templates x 3 seeds, all pass. Compound action
  reveals 3 nodes at once. Teacher handles varied costs correctly.

### 2026-03-10 — Ola 1: infer_latent_cause eval type (Ola 1 COMPLETE)
- **`TaskType.INFER_LATENT_CAUSE`**: "Based on observed symptoms, what is the probability
  distribution over the hidden cause?"
- **`TaskGenTool._infer_latent_cause_task()`**: picks a latent node, samples evidence
  from observables, computes posterior P(latent | evidence) via exact inference
- Uses existing `kl_divergence` scoring (same as infer_target)
- Fixed `generate_all()` to only generate the 3 original bundle types (not all 9)
- 12 new tests. 552 total. E2E validated: entropy reduction 0.13-1.38 bits across
  all templates. More evidence = more certainty about hidden cause.
- **Ola 1 complete**: 5 eval types (causal_effect, best_intervention, adjustment_set,
  compare_interventions, should_condition, infer_latent_cause) + 3 original = 9 total.

### 2026-03-10 — Ola 1: should_condition eval type
- **`TaskType.SHOULD_CONDITION`**: "A colleague suggests controlling for Z when
  analyzing X's effect on Y. Is this correct?"
- **`TaskGenTool._should_condition_task()`**: uses backdoor adjustment sets + DAG
  descendants to classify variables as confounders (should condition) vs
  mediators/collider-descendants (should not condition). Randomizes question type.
- **`VerifierTool.score_should_condition()`**: binary yes/no match
- 14 new tests. 540 total. E2E validated: causal_chain always "no" (mediators),
  fork_collider mixes "yes" (confounders) and "no" (descendants).

### 2026-03-10 — Ola 1: compare_interventions eval type
- **`TaskType.COMPARE_INTERVENTIONS`**: "Your team debates between two interventions.
  Which one has a larger causal effect on the outcome?"
- **`TaskGenTool._compare_interventions_task()`**: picks two interventions from different
  nodes with distinct effects, randomizes presentation order (A/B), computes P(Y|do())
  for each via `causal_query()`
- **`VerifierTool.score_compare_interventions()`**: binary — did the agent pick the better one?
  Equal effects = either answer is correct
- 15 new tests. 526 total. E2E validated across all 3 templates (gaps 0.21-0.51).

### 2026-03-10 — Research: diseño de acciones de investigación
- **New section in WORLD_DESIGN.md**: "Diseño de acciones de investigación"
  - Principle: thinking is free, acting in the world costs budget
  - Four research paradigms: dataset-first, experimental, field, hybrid
  - Distinction: acquisition actions (cost budget) vs analysis (free)
  - Catalog of action types: observe, intervene, request_dataset, consult
  - Parallel with eval types: fixed formal types + orchestrator-designed instances
  - Three worked examples: agriculture, epidemiology, geology
  - Validation chain: orchestrator proposes, tools validate
  - Teacher impact: IG per unit of cost (greedy optimization)
  - Open questions: consult formalization, adaptive actions, noisy measurements
- **TODO.md updated**: Rich actions section rewritten with new design
- Navigation index updated

### 2026-03-10 — Ola 1: adjustment_set eval type
- **`TaskType.ADJUSTMENT_SET`**: "What variables should you control for to estimate
  the causal effect of X on Y?"
- **`TaskGenTool._adjustment_set_task()`**: uses pgmpy `get_all_backdoor_adjustment_sets()`
  to find valid minimal sets, filters to observable-only variables
- **Three task scenarios**: confounded+identifiable (find the set), no confounding (empty set),
  not identifiable (hidden confounder — agent must recognize unidentifiability)
- **`VerifierTool.score_adjustment_set()`**: binary match against valid minimal sets
- 20 new tests. 511 total. E2E validated across all 3 templates + custom DAGSpec.
- Handles pgmpy ValueError when no valid adjustment set exists

### 2026-03-09 — Eval catalog research: 31 task types in 6 scientific families
- **New section in WORLD_DESIGN.md**: "Fundamentos de razonamiento causal y cientifico"
  - Pearl's ladder of causation (3 rungs: association, intervention, counterfactual)
  - McElreath's 4 elemental confounds (fork, pipe, collider, descendant)
  - Design principle: tasks as scientific questions, not DAG exercises
  - Three-level distinction: eval type → question template → research subtask
- **Comprehensive eval catalog** in WORLD_DESIGN.md: 31 eval types in 6 families:
  - A. Diagnosis/explanation (5 types): infer_target, infer_latent_cause, hypothesis_selection, mechanism_selection, explain_anomaly
  - B. Evidence gathering (6 types): NBO, best under cost, measurement bundle, disambiguate experiment, sequential design, efficiency
  - C. Causal intervention (6 types): causal_effect, compare, best, ATE, constrained, mediation
  - D. Structure/model discovery (6 types): adjustment_set, should_condition, simpson_paradox, confounder_detection, structure/skeleton
  - E. Prediction (4 types): prediction, temporal forecast, context shift, counterfactual
  - F. Process quality (5 types): evidence usage, alternative hypotheses, causal coherence, plan quality, calibration
- **Implementation roadmap**: 4 waves (0: done, 1: next 5, 2: 3 more, 3: infrastructure-heavy)
- **pgmpy support mapping**: which functions enable which eval types
- **TODO.md updated**: Eje B rewritten with full wave structure
- Sources: Pearl, McElreath (Statistical Rethinking), CauSciBench, CausalBench, CausalProbe-2024, ResearchGym

### 2026-03-09 — Ola 1: best_intervention eval type
- **`TaskType.BEST_INTERVENTION`**: "What intervention maximizes P(target=desired_state)?"
- **`TaskGenTool._best_intervention_task()`**: iterates all (node, state) interventions,
  computes P(target=desired | do(node=state)) for each, finds optimal
- **`VerifierTool.score_best_intervention()`**: ratio of agent's effect to optimal (like NBO)
- **`Task.intervention`** reused to store optimal {node: state}
- **`correct_answer`** maps "node:state" -> P(target=desired | do(node=state)) (full ranking)
- **13 new tests** (was 478, now 491): generation, ranking, scoring, cross-template, determinism
- **E2E validated**: 6 configs, spreads 0.36-0.99, causally correct (closer nodes = stronger effect)

### 2026-03-09 — B.1: causal_effect eval type (do-calculus)
- **`TaskType.CAUSAL_EFFECT`** added to eval catalog — first new eval type beyond the original 3
- **`ExactBayesSolver.causal_query()`**: computes P(target | do(node=state)) using pgmpy's `CausalInference`
  - Correctly distinguishes interventional from observational: do() != observe() when confounders exist
  - Works across all template families (latent_preference, causal_chain, fork_collider)
- **`TaskGenTool._causal_effect_task()`**: generates causal effect tasks
  - Finds observable nodes with actual causal effect on target (max_diff > 0.02)
  - Weighted selection toward nodes with stronger effects
  - Picks random intervention state, computes P(target | do(node=state)) as correct answer
  - Question text explains the do-operation distinction to the agent
- **`Task.intervention`** field: stores {node: state} for the do() operation
- **`design_case` tool** updated: `causal_effect` added to enum in orchestrator prompts
- **`generate_all()` / `TaskBundle`** updated: now generates all 4 task types
- **14 new tests** (was 465, now 478+existing fixes):
  - 10 causal_effect task generation tests (structure, determinism, cross-template, weighted selection)
  - 4 causal_query solver tests (valid distribution, do!=observe, non-causal node, causal chain)
- **E2E validated**: 7 configs (3 templates × 6-10 nodes), confirmed:
  - do() differs from observe() in latent_preference and fork_collider (confounders)
  - do() equals observe() in causal_chain (no confounders on chain path)
  - Intervention nodes selected with weighted preference for stronger effects

### 2026-03-09 — CasePlan: orchestrator designs research cases (Slice 1)
- **`CasePlan` model** (`src/sreg/models/case_plan.py`):
  - `EvalQuestionPlan`: question_text, eval_type (validated against TaskType), target_node, rationale
  - `CasePlan`: title, research_context, questions list, shared_budget, rationale
  - Validation: no duplicate questions (same eval_type + target_node), min lengths, valid types
  - Properties: primary_question (first), sub_questions (rest), eval_types (unique set)
- **`design_case` orchestrator tool** (`orchestrator/prompts.py` + `orchestrator.py`):
  - LLM proposes a case plan as tool call parameters (like apply_semantics)
  - Tool validates: target nodes exist in world, no duplicates, plan is computable
  - Generates tasks from plan to verify computability before returning
  - Stores validated CasePlan in `_case_plans` dict
- **`generate_from_plan`** (`tools/task_gen.py`):
  - Takes CasePlan + World, returns list[Task] (not TaskBundle)
  - Only generates the tasks the plan requests (not always all 3)
  - Overrides generic question text with plan's custom question_text
- **System prompt updated** to 6-step workflow (added step 4: design_case)
- **35 new tests** (was 430, now 465):
  - 21 CasePlan model tests (validation, serialization, edge cases)
  - 7 generate_from_plan tests (single/multi questions, custom text, determinism)
  - 7 design_case orchestrator dispatch tests (basic, multi-question, invalid target, etc.)
- **E2E validated**: 6 configs across 3 templates (6-10 nodes), full orchestrator dispatch pipeline

### 2026-03-09 — Dataset-rich evidence: multi-dataset, missing data, narratives
- **`DataSampler` rewritten** with multi-dataset mode:
  - `multi_dataset=True`: generates primary + secondary datasets with DAG proximity-based column splits
  - `missing_rate`: injects `"not_measured"` values (configurable 0-50%), ensures >=2 real columns per row
  - `narrative_observations`: generates N natural-language observations from sampled states
  - Original single-dataset mode preserved (backwards compatible)
- **`DataAsset` model extended** with optional metadata: `source`, `columns`, `num_rows`
- **`ProblemBuilder.build(rich_data=True)`**: convenience flag for multi-dataset + missing data + narratives
- **`prompts.py` updated**: renders narrative format, shows source metadata for all assets
- **Column splitting algorithm**: sorts visible nodes by shortest undirected distance to target in DAG,
  closer half → primary, farther half → secondary, 1 overlap column as join key
- **17 new tests** (was 413, now 430): multi-dataset, column splitting, missing data, narratives, determinism
- **E2E validated**: 8 configs across 3 templates (6-12 nodes), all produce coherent rich output
- Bug fix: `_inject_missing` now restores original values instead of placeholder when preserving min columns

### 2026-03-09 — Batch sweep: systematic generator/template comparison
- **`scripts/batch_sweep.py`**: 336 worlds across 7 generators/templates x 4 node counts x 4 edge strengths
- **Key finding: 10-12 nodes is the sweet spot** for research cases with real strategy.
  6-node worlds are budget-saturated (TbRR=0.00), 8 nodes is a "death valley" (21% bundle).
  12 nodes: budget_ratio=0.50, TbRR=0.60, bundle=86%.
- **edge_strength 0.5-0.7 is optimal**. At 0.9, hypothesis distinguishability drops to 43%
  (prior distractor becomes nearly identical to posterior).
- **preferential_attachment eliminated**: 0% WorldCheck pass across all 48 configs.
- **Best generators**: spanning_tree and layered for DAGs, all templates work well at 10+ nodes.
- **Strategic decision**: this closes the formal core validation. Next focus shifts to
  enriching the case presentation (dataset-rich evidence, rich actions, CaseBundle).
- Findings documented in WORLD_DESIGN.md "Batch sweep: regimenes de generacion".

### 2026-03-09 — QualitySuite metric redesign: multi-rollout + entropy reduction
- **Critical finding**: `teacher_beats_prior` metric (KL vs one-hot) penalizes correct
  inference when sampled true state is atypical. Documented with concrete example in WORLD_DESIGN.md.
- **Redesigned Layer B metrics** in WORLD_DESIGN.md:
  - Multi-rollout evaluation (K=5-10 seeds per world, averaged)
  - `mean_entropy_reduction` as primary belief quality metric (sample-independent)
  - `budget_ratio` for episode design quality (uses observables with path to target)
  - Old metrics renamed to `sampled_nll_*` and demoted to diagnostic status
  - `useful_bundle` tightened: requires entropy_reduction AND 2 of 3 quality dimensions
- **E2E with real LLM (GPT-5.2)**: 5 tests across all 3 generation paths (dag_generate,
  dag_construct, classic template). All WorldCheck pass, semantic layer works well.
  Confirmed metric issues in practice (teacher "loses" to prior on atypical samples).
- **CLAUDE.md updated**: E2E must include real LLM when credentials available
- Implementation plan added to TODO.md

### 2026-03-09 — QualitySuite: programmatic evaluation (layers A+B+C)
- **`src/sreg/harness/quality.py`**: suite for measuring world, task, and generator quality
  - Layer A (`compute_world_quality`): structural metrics (density, treewidth, depth, fan-in/out, target reachability, entropy)
  - Layer B (`compute_task_quality`): epistemic metrics (teacher vs prior/random, IG gap, NBO trivial, hyp distinguishable, useful bundle)
  - Layer C (`compute_generator_diversity`): batch statistics (std devs, distributions, acceptance rate, useful bundle rate)
  - `run_quality_suite()`: runs A+B+C on a list of worlds, produces `QualitySuiteReport`
  - `print_quality_report()`: ASCII table with per-world details, summary rates vs targets, diversity stats
  - All models are Pydantic (serializable to JSON)
- **44 new tests** (was 365, now 409): per-layer, runner, reporter, cross-template, cross-generator
- **E2E validation findings**:
  - Templates (6 nodes): teacher_random_gap=0.0 (budget >= observables, both see everything)
  - Preferential attachment: 100% WorldCheck failures (dense graphs lack d-separation)
  - Hypothesis distinguishability low in templates (44%) — known reversed-distractor issue
  - DAG generators (8 nodes): all targets met except worldcheck (75%, due to pref_attach)
- Exported from `sreg.harness` package

### 2026-03-09 — LLM orchestrator integration: dag_generate + dag_construct
- **Two new orchestrator tools** for creating worlds via DAGSpec:
  - `dag_generate`: LLM chooses a generator algorithm (erdos_renyi, spanning_tree, preferential_attachment, layered) + parameters
  - `dag_construct`: LLM specifies exact nodes/edges/types manually for precise causal structures
- Updated SYSTEM_PROMPT with generation method guidance and generator descriptions
- Both tools produce Worlds compatible with existing pipeline (world_check, apply_semantics, build_problem)
- Full pipeline E2E test: dag_generate -> world_check -> apply_semantics -> build_problem
- **15 new tests** (was 350, now 365): dispatch tests, validation errors, downstream pipeline

### 2026-03-09 — DAG generators (4 methods)
- **`dag_generators.py`** (`src/sreg/world/dag_generators.py`): 4 automatic DAG generation methods
  - `generate_erdos_renyi()`: random edges with probability p, good for testing
  - `generate_spanning_tree()`: connected tree + optional extra edges, guaranteed connectivity
  - `generate_preferential_attachment()`: hub-like structures, scale-free-ish DAGs
  - `generate_layered()`: pipeline/stage structures with skip connections
  - All guarantee acyclicity via topological ordering (edges only go lower → higher index)
  - Shared helpers: `_assign_node_types()` (latents early, targets late), `_assign_states()`, `_cap_parents()`
- **E2E validation**: 50 configs (10 generators × 5 seeds), teacher>prior 94%, teacher>random 82%, NBO non-trivial 76%, hypotheses distinguishable 80%
- **40 new tests** (was 310, now 350): per-generator + cross-generator parametrized tests
- Exported generators from `sreg.world` package

### 2026-03-09 — DAGSpec prototype (v2 slice minimo)
- **`DAGSpec` + `DAGNodeSpec`** (`src/sreg/models/dag_spec.py`): universal contract for arbitrary DAGs
  - Validations: acyclic, max parents <= 4, required types, no duplicates
  - Supports heterogeneous state cardinalities (2, 3, 4 states mixed)
  - Convenience methods: parents_of, children_of, to_networkx, nodes_by_type
- **`cpd_gen.py`** (`src/sreg/world/cpd_gen.py`): extracted generic CPD generation
  - Bit-for-bit identical to existing templates (verified by test)
  - Supports heterogeneous parent/child cardinalities
- **`CustomTemplate`** (`src/sreg/world/templates/custom.py`): DAGSpec -> World
  - All 3 task types (infer_target, NBO, hypothesis_selection) work E2E
- **`generate_custom()`** in WorldGenTool: transitional API for custom worlds
- **WorldCheck extended**: max parents (hard fail) + treewidth (warning)
- **E2E results**: teacher always beats prior+random, NBO non-trivial 80-90%, hypotheses distinguishable 75-90%
- **310 tests** (was 229)

### 2026-03-08 — Version alignment + WORLD_DESIGN.md refinements
- **Version scheme simplified**: v0+v1 (done) → v2 (Etapa 2) → v3 (Etapa 3) → Backlog
  - Versions now align 1:1 with WORLD_DESIGN.md stages
  - Dropped v4 (too speculative), moved do-calculus + structure recovery to v3
  - Updated PROJECT.md, TODO.md, CLAUDE.md with new scheme
- **WORLD_DESIGN.md refined** with 4 feedback-driven adjustments:
  - Replaced "teacher >60% accuracy" with improvement-over-prior + gap-over-random
  - Marked `generate_custom()` as transitional API (unify later)
  - Added non-degenerate task rate as success criterion (>70% NBO, >80% hypothesis)
  - Treewidth kept as warning (not hard fail) for learning phase

### 2026-03-08 — WORLD_DESIGN.md research document
- **`WORLD_DESIGN.md` created**: 1100+ line research document for realistic world generation
  - Three-stage progression: motifs → composition → mechanism-first
  - MechanismSpec and DAGSpec as central contracts
  - CaseBundle concept, quality gates, generator health metrics
  - PCG principles adopted: MAP-Elites, generate-evaluate-refine, expressive range analysis
  - Detailed analysis of BoxingGym, DiscoveryWorld, Reasoning Core with concrete takeaways
  - Positioning table: what SREG does that others don't
  - Hallazgos experimentales section for documenting test results
  - Implementation plan for DAGSpec prototype (slice mínimo)
- All docs updated: CLAUDE.md, PROJECT.md, TODO.md reference WORLD_DESIGN.md

### 2026-03-07 — Multiple evaluations per problem (v1 complete)
- **`TaskBundle` model + `generate_all()` method**: one world → all 3 task types
  - `TaskGenTool.generate_all(world, target, budget, seed)` → `TaskBundle`
  - `TaskBundle`: groups infer_target, NBO, and hypothesis_selection tasks
  - Property accessors: `.infer_target`, `.next_best_observation`, `.hypothesis_selection`
  - Full JSON serialization roundtrip support
  - Validated across 18 configs (6 template/node/ES combos × 3 seeds), 0 failures
  - 9 new tests, 229 total, all passing
- **v1 milestone complete**: 3 templates + 3 task types + multi-task generation

### 2026-03-07 — hypothesis_selection task type
- **`hypothesis_selection` task type**: "which of these explanations is most plausible?"
  - Generates 4 hypotheses: true posterior, prior, uniform, reversed posterior
  - Labels shuffled randomly so correct answer isn't always "A"
  - `correct_answer` maps labels to KL from true posterior (lower = better)
  - `VerifierTool.score_hypothesis()`: binary accuracy (chose the best or didn't)
  - `Task.hypotheses` field: stores the labeled distributions
  - Distinguishable in 90%+ of cases across all 3 templates
  - 12 new tests, 220 total, all passing

### 2026-03-07 — next_best_observation task type
- **`next_best_observation` task type**: "which variable should you measure next?"
  - `TaskGenTool` generates NBO tasks: samples state, gives partial evidence, asks what to observe
  - `Task.given_evidence`: new field for evidence already provided to the agent
  - `Task.correct_answer` holds IG ranking: `{node: info_gain}` for each remaining node
  - `VerifierTool.score_nbo()`: scores agent's choice as ratio of chosen IG to optimal IG
  - Works across all 3 templates (latent_preference, causal_chain, fork_collider)
  - 13 new tests (NBO generation + verifier scoring), 208 total, all passing

### 2026-03-07 — Fork-collider template
- **`fork_collider` template**: common cause (fork) + collider with explaining away
  - Structure: hidden_factor → branch_1, branch_2 → collider → [mediators] → target
  - Tests Berkson's paradox: conditioning on collider activates dependency between branches
  - Scales with extra branches (3+) and mediators between collider and target
  - 16 new tests: structure, fork/collider topology, validation, 100 worlds, teacher accuracy
  - Validated: teacher achieves ≥60% accuracy, all 100 worlds pass validation
- Registered in WorldGenTool, exported from templates, added to batch_eval.py
- 196 tests total, all passing

### 2026-03-07 — Causal chain template + KL fix
- **`causal_chain` template**: linear chain root → stage_1 → ... → target
  - Tests evidence propagation: closer nodes are more informative than distant ones
  - 13 new tests: structure, validation, 100 worlds, teacher accuracy, proximity IG
  - Validated: 5/5 agent beats random, mean KL 0.37 vs random 1.67
- **WorldCheckTool d-separation fix**: now also conditions on individual observables
  (chains have d-separations like stage_1 ⊥ stage_3 | stage_2, not just given latents)
- **KL divergence NaN fix**: verifier now clips zero probabilities to epsilon
  (agent sometimes submits 0 for a state, causing 0*log(0)=NaN)
- Batch eval supports `--template` parameter for cross-template comparison
- 180 tests total, all passing

### 2026-03-07 — Phase 8: Dataset export + batch evaluation
- **Teacher trajectory export**: generates optimal teacher trajectory, exports as JSONL
  - `TeacherTrajectory` / `TrajectoryStep`: structured dataclasses with full step info
  - `generate_teacher_trajectory()`: runs teacher, records action, observation, IG, posterior per step
  - `export_trajectories()`: writes list of trajectories to JSONL file
- **Batch evaluation harness**: generate N problems, run agent + teacher, collect metrics
  - `BatchEvaluator`: generates problems programmatically, evaluates agent vs teacher vs random
  - `ProblemResult` / `BatchResult`: structured results with aggregation (mean KL, beats-random count)
  - `scripts/batch_eval.py`: CLI for batch eval and trajectory export
  - Validated: 5/5 agent beats random, mean KL agent=0.30 vs random=2.04
- 167 tests total, all passing (14 new harness tests)

### 2026-03-07 — Phase 7: LLM Agent solver + E2E pipeline
- **Agent solver implemented**: LLM agent that receives ResearchProblem and solves it
  - `AgentSolver`: agentic loop with observe/submit tools routed through EpisodeRunner
  - `build_agent_system_prompt()`: presents problem narrative, data, actions, question
  - `AgentResult`: captures submitted answer, observations, score, messages
  - Observe tool: validates variable, checks budget, returns observed state
  - Submit tool: validates distribution states, normalizes, scores via VerifierTool
  - Comparison script (`scripts/test_agent.py`): runs agent vs teacher vs random baseline
  - 13 tests: prompt generation, tool dispatch, mocked full loops
- **End-to-end pipeline**: orchestrator → agent in a single script
  - `scripts/test_e2e.py`: orchestrator generates semantic world, agent solves it
  - Full flow: world_gen → world_check → apply_semantics → build_problem → agent → score
  - Agent receives semantic node names (e.g., `coral_bleaching_severity` not `target_outcome`)
  - Step-by-step output for both orchestrator and agent phases
  - Validated: agent KL=0.16 vs teacher KL=0.00 vs random KL=0.89 on marine ecology problem
- 153 tests total, all passing

### 2026-03-07 — Phase 6: Semantic layer
- **Semantic layer implemented**: transforms abstract BN worlds into realistic research problems
  - `ResearchProblem` model: packages title, narrative, data, actions, question, budget
  - `DataSampler`: samples from BN joint distribution, presents as tabular/observations
  - `ProblemBuilder`: builds agent-facing ResearchProblem from enriched World
  - `apply_semantics` tool: LLM renames nodes, adds scenario narrative and domain
  - `build_problem` tool: samples data and packages everything the agent sees
  - `show_research_problem()` display function (terminal + notebook)
  - Node renaming propagates through nodes, edges, CPDs, and state_names
  - Orchestrator workflow: world_gen -> world_check -> apply_semantics -> build_problem
  - Updated test script with pretty output for semantic tools
- 139 tests total, all passing (14 new tests for data_sampler, problem_builder, orchestrator)

### 2026-03-07 — Vision realignment
- **Project vision updated**: shifted from abstract Bayesian worlds to realistic
  research problems with semantic layer on top of formal networks
- Revised implementation plan: 9 phases (was 7). Added Phase 6 (semantic layer),
  Phase 7 (LLM agent solver), renumbered Phase 8 (templates) and Phase 9 (eval)
- Created `docs/CURRENT_STATE.md` — detailed description of what exists today
- Updated PROJECT.md with full vision:
  - Two-layer architecture: formal (BN) + semantic (narrative, data, actions)
  - Rich data presentation: tabular, multi-dataset, observations, experiments
  - Agent freedom: free to reason however it wants, only actions cost budget
  - Semi-real naming: real vocabulary in fictional domains
  - Comprehensive evaluation framework: inference, causal, structure, optimization,
    hypothesis selection, multiple evaluations per task, rubrics, SOTA references
  - Clear version roadmap (v0-v3) with evaluation types mapped to versions
- Updated TODO.md, CLAUDE.md, IMPLEMENTATION_PLAN.md to reflect new direction
- Added configurable model via AZURE_MODEL env var and auto-load .env
- Rewrote orchestrator test script with step-by-step pretty output

### 2026-03-07
- **Phase 4 complete**: episodes, tasks, verifier, and environment interface
  - `EpisodeGenTool`: generates episodes from worlds (budget, costs, initial evidence)
  - `TaskGenTool`: formulates `infer_target` tasks with correct answer (prior distribution)
  - `VerifierTool`: KL divergence scoring, information efficiency, per-step scoring
  - `EpisodeRunner`: step-by-step environment interface (observe, query, submit)
  - End-to-end test: teacher as agent achieves >90% MAP accuracy through EpisodeRunner
- **Phase 5 complete**: LLM orchestrator for world generation
  - System prompt with workflow instructions and guidelines
  - 4 tool definitions for function calling (world_gen, world_check, episode_gen, task_gen)
  - `Orchestrator` class: agentic loop with tool dispatch, retry logic, world registry
  - Uses Azure AI Foundry via openai SDK (OpenAI client, not AzureOpenAI)
  - Mocked tests: full loop (4 iterations), retry on validation failure, max iterations
  - Created `.env.example` for credential configuration
- 125 tests total, all passing

### 2026-03-06
- **Phase 2 complete**: world generation and validation
  - `LatentPreferenceTemplate`: generates DAG + CPDs with controllable edge_strength
  - `WorldGenTool`: generates worlds from config (template, num_nodes, edge_strength, seed)
  - `WorldCheckTool`: validates DAG acyclicity, latent nodes, paths, entropy, d-separation
  - `world_to_pgmpy()`: converts World models to pgmpy DiscreteBayesianNetwork
  - 100 worlds generated and validated, difficulty varies with parameters
- **Phase 3 complete**: exact Bayesian teacher solver
  - `ExactBayesSolver`: posterior computation, information gain, optimal action selection
  - Ancestral sampling for world state generation
  - Trajectory generation with optimal observation ordering
  - Teacher reaches >90% MAP accuracy across 50 worlds (250 episodes)
- 81 tests total, all passing

### 2026-03-06
- **Phase 1 complete**: all Pydantic data contracts defined and tested
  - `World`, `Node`, `Edge`, `CPD`, `DifficultyProfile` (world.py)
  - `Episode`, `Action`, `ActionType`, `Observation`, `StepResult` (episode.py)
  - `Task`, `TaskSpec`, `TaskType` (task.py)
  - `TeacherOutput` (teacher.py)
  - `Score`, `StepScore` (score.py)
- Set up `pyproject.toml` with all dependencies (pgmpy, networkx, numpy, scipy, pydantic, openai)
- Set up pytest skeleton with 40 tests covering all models
- All models support JSON serialization roundtrips
- Validation: CPD table shape, probability sums, node references, target existence

### 2026-03-06
- Initial project scaffolding: CLAUDE.md, PROJECT.md, TODO.md, CHANGELOG.md
- Created implementation plan (`docs/IMPLEMENTATION_PLAN.md`)
- Created custom Claude Code slash commands
- Moved original design documents to `docs/references/`
- Defined project conventions and maintenance rules
