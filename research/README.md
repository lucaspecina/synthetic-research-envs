# research/ — Analisis, hallazgos y sintesis del proyecto

> Este directorio contiene el trabajo de investigacion que alimenta las
> decisiones del proyecto. No es canonico — las decisiones viven en
> `PROJECT.md` y `ARCHITECTURE.md`. Research las informa.

## Estructura

### notes/
Material crudo o semi-crudo: debates, exploraciones, analisis largos,
hallazgos empiricos, working docs. No es canonico.

Pregunta que responde: **"Que estamos explorando o analizando?"**

### synthesis/
Conclusiones consolidadas con evidencia. Resumenes de lo que aprendimos
sobre un tema, listos para informar decisiones.

Pregunta que responde: **"Que concluimos hasta ahora?"**

Documentos de sintesis activos:

- `synthesis/research_case_design.md`
- `synthesis/real_papers_patterns.md`
- `synthesis/sreg_scientific_coverage.md`
- `synthesis/open_investigation_vision.md`
- `synthesis/investigation_scenarios_rubric.md`
- `synthesis/Doc1_Taxonomia_El_Mapa.md`
- `synthesis/oi_scoring_fundamentals.md`
- `synthesis/oi_scoring_next_design.md`
- `synthesis/scm_migration_rationale.md`
- `synthesis/scientific_research_taxonomy.md`

### archive/
Documentos viejos, superseded o referencias heredadas. Read-only.
Se guardan por si hacen falta, no como referencia activa.

## Regla de promocion

1. Idea nueva, debate, exploracion → `notes/`
2. Se investiga y consolida → `synthesis/`
3. Si se vuelve decision del proyecto → se promueve a `PROJECT.md` o
   `ARCHITECTURE.md`
4. Si implica trabajo pendiente → `TODO.md`
5. Si se implementa → `CURRENT_STATE.md` + `CHANGELOG.md`

El archivo de research queda como registro historico — no se borra,
pero deja de ser la fuente de verdad para esa decision.

## Nota sobre docs heredados

Algunos archivos en `notes/` siguen siendo megadocs heredados o notas de
sesion. Se conservan como insumo, pero la referencia activa deberia ir
desplazandose hacia `synthesis/`.

## Lineas de investigacion activas

### Research case design
- **Pregunta:** como diseniar SRCs que se sientan como investigacion real sin
  perder evaluabilidad fuerte.
- **Empezar por:** `synthesis/research_case_design.md`
- **Notas de apoyo:** `archive/world_design_legacy.md` (legacy),
  `archive/sreg_v2_design_findings.md` (legacy)

### Patrones de papers reales
- **Pregunta:** que rasgos aparecen de forma consistente en investigaciones
  reales y que implican para SREG.
- **Empezar por:** `synthesis/real_papers_patterns.md`
- **Notas de apoyo:** `notes/real_investigations_analysis.md`

### Taxonomia cientifica
- **Pregunta:** que tipos de ciencia puede representar SREG y cuales no.
- **Empezar por:** `synthesis/scientific_research_taxonomy.md`

### Cobertura cientifica de SREG
- **Pregunta:** que tipos de ciencia puede representar SREG y cuales no.
- **Empezar por:** `synthesis/sreg_scientific_coverage.md`
- **Framework de referencia:** `synthesis/scientific_research_taxonomy.md`
- **Conecta con:** A2, A4, A5, A8 en `TODO.md`

### Mediciones indirectas — senales proxy en el SCM
- **Pregunta:** como hacer que el solver no vea variables causales directamente
  sino senales instrumentales proxy, como en investigacion real.
- **Empezar por:** `notes/indirect_measurement_design.md`
- **Conclusion:** no requiere capa nueva — son nodos adicionales en el grafo
  cuyas ecuaciones simulan la respuesta del instrumento. El orchestrator decide
  que nodos son latentes y cuales observables al diseñar el SCM.
- **Conecta con:** Fase 3 (orchestrator diseña SCMs), LA PREGUNTA
- **Status:** DOCUMENTADO. Implementar cuando orchestrator diseñe SCMs.

### Brief vs eval separation — preguntas reales vs scoring oculto
- **Pregunta:** como hacer que el investigador reciba un encargo de
  investigacion real en vez de preguntas tipo benchmark.
- **Empezar por:** `notes/brief_vs_eval_separation.md`
- **Hallazgo clave:** el sistema confunde tres capas: brief (visible),
  eval agenda (scoring plan), query formal (ground truth). Hoy las tres
  estan colapsadas en CasePlan.questions.
- **Solucion implementada:** `CasePlan.research_brief` + `deliverables`.
  `SCMProblemBuilder` prioriza brief. Orchestrator requiere brief para SCM.
  Prompt del solver muestra "Research Brief" como seccion visible.
- **Conecta con:** task primitives, LA PREGUNTA
- **Status:** IMPLEMENTADO (Fase 5). Pendiente: task questions individuales
  siguen semi-mecanicas (futuro: task primitives).

### Task primitives composicionales — expandir evaluacion SCM
- **Pregunta:** como expandir los 9 task types fijos a una arquitectura mas
  expresiva que cubra ciencia real, sin perder reward exacto.
- **Empezar por:** `notes/scm_task_primitives.md`
- **Decision clave:** "free-form wording, closed-form semantics" — el LLM
  escribe preguntas en NL pero compila a primitivas formales con ground truth
  computable. Preguntas realmente libres descartadas (caen en LLM-judge).
- **Primitivas propuestas:** marginal, interventional, ate, mediation,
  interaction, d_separation, adjustment_set, nonlinearity, threshold,
  dose_response, compare_interventions, etc.
- **Conecta con:** Fase 4 (orchestrator wiring), LA PREGUNTA
- **Status:** PROPUESTA EN DISCUSION. No implementar antes de Fase 4.

### Investigation gap y mundos data-indexed
- **Pregunta:** como garantizar que un mundo OI fuerza investigacion real
  (no se responde desde priors del dominio).
- **Empezar por:** `notes/oi_investigation_gap.md`
- **Concepto:** `investigation_gap = score_with_data - score_no_data`.
  Si gap ~ 0, el mundo no sirve para RL.
- **Patrones data-indexed:** suppressor effect, confounding reversal, Simpson's
  paradox. Validados con 6 mundos curados.
- **Conecta con:** A17, A20 en `TODO.md`, LA PREGUNTA
- **Status:** Concepto validado. Falta formalizar como gate en el pipeline.

### Open Investigation — investigacion libre con verificacion SCM exacta
- **Pregunta:** como dejar que el solver investigue libremente sin perder
  verificacion exacta contra el SCM.
- **Empezar por:** `synthesis/open_investigation_vision.md`
- **Insight clave:** gramatica composable de verificacion (Simulacion +
  Medicion + Comparacion + Asercion). No primitivas fijas. El solver
  entrega claim cards semi-estructuradas, un LLM compiler las traduce a
  specs ejecutables, el SCM verifica.
- **Analisis de casos:** `notes/open_investigation_case_analysis.md` — 10
  dominios, 30 respuestas analizadas, patrones de ruptura, gramatica
  composable, debate Claude-Codex-ChatGPT. Working doc activo.
- **Diseno del compiler:** `notes/oi_compiler_design.md` — arquitectura
  LLM->ClaimIntent->lowering->AtomicSpec. Debate con Codex.
- **Diseno del warrant:** `notes/oi_warrant_design.md` — evidence warrant
  system. Verifica que el solver investigo para respaldar sus claims.
  4 niveles, multiplicador claim-level, debate con Codex.
- **Conecta con:** brief_vs_eval_separation, scm_task_primitives, LA PREGUNTA
- **Status:** Alpha-0 piloteado con LLMs reales (6 runs, 3 mundos).
  Warrant disabled para Alpha. ~240 OI-specific tests.
- **Scoring fundamentals:** `synthesis/oi_scoring_fundamentals.md` — framework
  mental para el scoring de OI. Salience map = piso, no techo. Verdad
  se verifica contra SCM directamente, no contra lista precomputada.
- **Pilot analysis:** `notes/oi_pilot_analysis_batch1.md` — 6 OI pilots
  (3 worlds x 2 runs), avg total=0.622, correctness=0.772. 6 problemas
  sistematicos identificados (P1: confounding=0 credito, P2: null findings,
  P3: coverage baja, P4: precision gate, P5: tags, P6: import errors).
  Codex review: "solver is better than scorer, family match gates correctness".
- **Sub-question scoring:** `synthesis/oi_scoring_next_design.md` — next
  scoring architecture with orchestrator sub-questions. Design validated,
  implementation complete: `oi_subquestions.py` (resolution + scoring),
  23 tests, 7 Codex bugs fixed.
  Treatment world: 0.983 total (vs 0.400 with v2). Dual scoring wired to runner.

### A21 Compiler Ontology Investigation (2026-03-29)
- **Pregunta:** por que el compiler traduce mal los claims? Es un problema
  de prompting o de ontologia?
- **Empezar por:** `notes/a21_compiler_ontology_investigation.md`
- **Hallazgo clave:** A21 es un bug de ontologia, no de prompting. El campo
  `pattern` cargaba tres responsabilidades: forma estructural, estatus
  epistemologico y routing de scoring. Solucion: compatibility algebra que
  separa `relation_family`, `relation_operator`, roles y `claim_force`.
- **Resultado E2E:** Coral: obs claims pasan de 0.00 a 0.65 (algebra funciona).
  Soil: expuso A22 (compiler abstention rate).
- **Codex thread:** 019d3aec-a7db-75e0-bafd-a2bb889aa901
- **Conecta con:** A21 en `TODO.md`, A22, E2E qualitative analysis
- **Status:** RESUELTO y VALIDADO E2E.

### Autoresearch S02: Diverse E2E Diagnostics (2026-03-30)
- **Pregunta:** como se comporta el sistema con tipos de investigacion distintos
  al causal simple? Donde falla exactamente?
- **Empezar por:** `autoresearch/s02_diverse_e2e_diagnostics.md`
- **3 E2E corridos:** causal (vaca_muerta), predictivo (vaca_muerta_predictive),
  epistemologico (identifiability_pollution). Scores: 0.580, 0.548, 0.364.
- **Hallazgo clave:** correctness=1.0 en todos. Coverage es el cuello de
  botella. 3 compiler misses (efecto_ranking, sign extraction, SQ matching)
  + 6 solver misses (variables no exploradas, interacciones equivocadas).
- **Fix aplicado:** force-submit en oi_driver.py (solver no submitia 2/3 veces).
- **Conecta con:** S01, A22, compiler improvement roadmap

### A22 Compiler: de patterns fijos a compilacion directa (2026-03-29)
- **Pregunta:** por que el compiler rechaza claims correctos? Por que solo
  hay 8 patterns cuando la gramatica composable puede expresar mucho mas?
- **Empezar por:** `notes/a22_compiler_direct_to_atomicspec.md`
- **Hallazgo clave:** El ClaimIntent con 8 patterns fijos y 1 treatment/1
  outcome es un cuello de botella innecesario. La gramatica composable
  (5 QueryKind x 10 Measurement x 8 Comparison x 12 Assertion) ya existe
  en `open_investigation.py` y el verifier ya la ejecuta.
- **Evidencia:** Soil case: 3/4 claims ABSTENTION por ser compuestos.
- **Propuesta:** Camino A (multi-intent, inmediato) + Camino B (compilacion
  directa a AtomicSpec, arquitectura correcta a largo plazo).
- **Codex thread:** 019d3b67-eb81-7201-9151-9aa26e54ac24
- **Conecta con:** A21, scm_task_primitives, open_investigation_vision
- **Status:** PROPUESTA. Pendiente debate + diseno.

### S03 Extraction Diagnosis — A/B test y taxonomia de fallos (2026-03-30)
- **Pregunta:** por que el compiler LLM pierde informacion de claims complejos?
- **Empezar por:** `notes/s03_extraction_diagnosis.md`
- **Hallazgo clave:** el compiler operaba en vacio de contexto (solo nombres
  de variables). A/B test: brief+SQs+descripciones elimina variables invalidas
  y recupera claims de abstention. Pero e2e_03 (epistemologico) no mejora.
- **Taxonomia:** F1 vars invalidas, F2 abstention recuperable, F3 direcciones
  contradictorias, F4 sign/significance, F5 campos faltantes, F6 submission aversion.
- **Conecta con:** A22, A23, S02
- **Status:** IMPLEMENTADO (S03a). Validacion parcial: ayuda modestamente,
  pero no resuelve casos epistemologicos (limitacion de la IR, no del contexto).

### A23 Grammar-first para SQ y compiler (2026-03-30)
- **Pregunta:** el bottleneck actual es solo extraccion LLM, o estamos
  forzando tanto SQ como claims a pasar por un catalogo demasiado estrecho
  de patterns conocidos?
- **Empezar por:** `notes/a23_grammar_first_sq_and_compiler.md`
- **Hallazgo clave:** la gramatica atomica ya es suficientemente rica; el
  sesgo a causal simple entra antes, porque SQ y claims se comprimen a
  `pattern + roles` antes de llegar al verifier.
- **Evidencia:** `e2e_02` pierde atoms pairwise al colapsar a ranking;
  `e2e_03` comprime un brief epistemologico a SQs causales estrechas;
  `e2e_05` muestra que cuando todo entra en causal-simple el sistema
  funciona mejor, pero el matching sigue sobrepremiando claims broad.
- **Direccion propuesta:** SQ grammar-first (bundles mas cercanos a
  `AtomicSpec`), patterns como fast-path solamente, compiler hibrido con
  fallback directo a gramatica atomica para claims fuera de catalogo.
- **Conecta con:** A22, S02, S03, scm_task_primitives, open_investigation_vision
- **Status:** PROPUESTA. Prioridad alta para la proxima ronda.

### S04 Epistemic IR Gap + Direct-to-AtomicSpec vs Catalog (2026-03-30)
- **Pregunta:** cuanto menos dependamos del catalogo fijo, mejor preservamos
  la semantica de claims y SQs en casos diversos?
- **Empezar por:** `notes/s04_epistemic_ir_gap_analysis.md`
- **Metodo:** (1) Trace de e2e_03 epistemologico. (2) Hand-craft de AtomicSpecs.
  (3) Prototipo directo LLM → AtomicSpec. (4) Comparacion sistematica en
  5 casos nuevos diversos (selection bias, competing mechanisms, policy equity,
  value of info, methodology comparison).
- **Hallazgos clave:**
  - e2e_03: 2/4 claims ABSTENTION en catalogo. Directo recupera todos.
  - 5 casos nuevos (18 claims): catalogo 17/18 compilados (28 units).
    Directo 18/18 compilados (65 specs validos, 50 TRUE). 2.3x mas
    verificaciones, 0 abstentions.
  - **El camino directo preserva mas semantica que el catalogo fijo.**
  - Caveats: identifiability_check != IV validity; prueba capacidad no
    arquitectura final; 77% TRUE vs ~100% del catalogo (calibracion).
- **Seeds creadas:** selection_bias_police, methodology_missing_data,
  competing_mechanisms, policy_equity_tradeoff, value_of_information.
- **Codex thread:** 019d3f92-6b3b-7851-a5d2-d53830a07b56
- **Conecta con:** A23, S03, A22, open_investigation_vision
- **Status:** EVIDENCIA EMPIRICA COMPLETA. Siguiente: decidir integracion,
  disenar matching entre conjuntos de specs, calibrar prompting.

### A24 Un solo runtime general de validacion (2026-03-30)
- **Pregunta:** si SREG debe tener un solo metodo de scoring para todo, el
  target final es `AtomicSpec` o un runtime mas general de validadores
  ocultos ejecutables?
- **Empezar por:** `notes/a24_general_validator_runtime.md`
- **Hallazgo clave:** la taxonomia puede distinguir casos para coverage audit,
  pero NO puede bifurcar el scoring. `AtomicSpec` parece ser una muy buena
  familia de validators, pero quizas no el techo final para prediccion,
  optimizacion o artefactos evaluables.
- **Direccion propuesta:** mantener A23 como siguiente paso inmediato
  (menos catalogo, mas atoms), pero pensar `AtomicSpec` como subconjunto de un
  runtime comun de validator programs restringidos y auditables.
- **Conecta con:** PROJECT invariants, CLAUDE scoring principles, A23, S04
- **Status:** DISCUSION ABIERTA. Arquitectura de mediano/largo plazo.

### SQ v2 Matching Spec — spec de diseno consolidado (2026-03-30)
- **Pregunta:** como liberar SQs del catalogo de 8 patterns, como matchear
  claim-specs vs SQ-specs, como agregar el score.
- **Empezar por:** `synthesis/sq_v2_matching_spec.md` (CANONICO)
- **Decisiones clave:** SQ = text_gloss + verification_specs (required/support)
  + tier. Sin pattern. Match exacto en estimand (measurement kind + variables
  + conditioning). Fuzzy solo en assertion. Bipartite 1-a-1. Anti-spam via
  precision gate. Compile step separado (orc genera texto, compilador baja
  a specs).
- **Evidencia:** S05 (10/10 causualizados), S04 (direct compilation 2.3x),
  debate Claude-Codex-Gemini sobre matching.
- **Conecta con:** S04, S05, A23, A24, PROJECT scope boundaries
- **Status:** PROTOTIPO IMPLEMENTADO. Primer test exitoso (5/5 SQs, 72% TRUE).
- **Implementacion:** `SubQuestionIntentV2` + `VerificationSpec` en
  `open_investigation.py`. Compile step en `oi_sq_compiler.py`. Matching en
  `oi_sq_matching.py`. Test script: `scripts/test_sq_v2_compile.py`.
- **Docs superseded:** `notes/s05_*` (diagnostico, marcado superseded),
  `archive/s06_*` (research, archivado).

### E2E Qualitative Analysis — 4-case evaluation (2026-03-28)
- **Pregunta:** por que SREG todavia no es investigacion real (post-OI pipeline)?
- **Empezar por:** `notes/e2e_qualitative_analysis_20260328.md`
- **4 cases:** poverty, pollution, soil, coral reef. 2 domains per batch.
- **Key finding:** worlds + solver are research-capable. Evaluation harness
  is the bottleneck (claim compilation fails, scoring rejects correct findings).
- **Fixes applied:** statsmodels/linearmodels allowed, progressive nudges,
  hard submit guard on final iteration.
- **Next:** mejorar compiler (LLM extraction es el bottleneck), split scoring axes.
- **Codex thread:** 019d3654-fa2b-7b92-a457-627687961699

### Migracion a SCM — de BN a grafo + ecuaciones + simulacion
- **Decision:** migrar de BN discreta (CPD tables) a SCM (Structural Causal
  Model) con ecuaciones arbitrarias y reward via Monte Carlo.
- **Empezar por:** `synthesis/scm_migration_rationale.md` (fundamentos completos)
- **Status:** IMPLEMENTADO. Mergeado a main. BN legacy eliminado del repo.
