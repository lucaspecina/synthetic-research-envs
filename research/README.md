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
- `synthesis/eval_types_analysis.md`
- `synthesis/eval_strategy.md`
- `synthesis/qualitative_eval_rubric.md`
- `synthesis/benchmark_analysis.md`
- `synthesis/sreg_scientific_coverage.md`
- `synthesis/open_investigation_vision.md`
- `synthesis/investigation_scenarios_rubric.md`
- `synthesis/Doc1_Taxonomia_El_Mapa.md`
- `synthesis/oi_scoring_next_design.md`

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
- **Notas de apoyo:** `notes/world_design_legacy.md`,
  `notes/sreg_v2_design_findings.md`

### Patrones de papers reales
- **Pregunta:** que rasgos aparecen de forma consistente en investigaciones
  reales y que implican para SREG.
- **Empezar por:** `synthesis/real_papers_patterns.md`
- **Notas de apoyo:** `notes/real_investigations_analysis.md`

### Eval types y taxonomia cientifica
- **Pregunta:** que tipos de preguntas fuerzan investigacion real y cuales se
  pueden resolver por shortcut, prior o estructura generica.
- **Empezar por:** `synthesis/eval_types_analysis.md`
- **Notas de apoyo:** `notes/scientific_taxonomy.md`,
  `notes/scientific_taxonomy_deep_research.md` (deep research: como se hace
  ciencia hoy, taxonomy explicita/implicita, curriculum RL propuesto),
  `synthesis/scientific_research_taxonomy.md` (framework completo de
  clasificacion con objectives, axes, workflows, scoring, ejemplos),
  `notes/solver_trajectory_findings.md`,
  `notes/sreg_v2_design_findings.md`

### Estrategia de evaluacion
- **Pregunta:** como evaluar SREG sin reducirlo a un benchmark disfrazado.
- **Empezar por:** `synthesis/eval_strategy.md`
- **Rubrica cualitativa:** `synthesis/qualitative_eval_rubric.md` — 7
  dimensiones + 6 critical failures + no-data baseline probe. Formaliza la
  evaluacion cualitativa que antes era ad-hoc.
- **Segunda evaluacion formal:** `synthesis/qualitative_eval_2026_03_25.md` —
  3 SRCs post-I10 (football, coral, asthma). 6 problemas nuevos encontrados.
  Mejora significativa en capa visible; problemas actuales son mas profundos.
- **Notas de apoyo:** `notes/eval_design_notes.md`

### Benchmarks externos
- **Pregunta:** con que benchmarks conviene medir alineacion y transferencia
  fuera de SREG.
- **Empezar por:** `synthesis/benchmark_analysis.md`
- **Notas de apoyo:** `notes/benchmark_results.md`

### Modos semanticos (realistic vs fictional vs abstract)
- **Pregunta:** que modo semantico fuerza mas investigacion genuina y minimiza
  contaminacion por priors de pretraining.
- **Empezar por:** `notes/semantic_modes_experiment_2026_03_17.md`
- **Conecta con:** A3 y I2 en `TODO.md`
- **Status:** dos experimentos (Vaca Muerta + Football). Ver notas para
  hallazgos consolidados.

### Cobertura cientifica de SREG
- **Pregunta:** que tipos de ciencia puede representar SREG y cuales no.
- **Empezar por:** `synthesis/sreg_scientific_coverage.md`
- **Framework de referencia:** `synthesis/scientific_research_taxonomy.md`
- **Conecta con:** A2, A4, A5, A8 en `TODO.md`

### Por que SREG todavia no es investigacion real (debate)
- **Pregunta:** que brechas fundamentales separan a SREG de la investigacion real,
  mas alla de las conocidas (variables continuas, teoria inventada).
- **Empezar por:** `notes/why_not_real_research_debate.md`
- **Participantes:** Claude, Codex (gpt-5.2), usuario
- **Hallazgos clave:** el solver no sabe que es una BN, pero los templates de
  preguntas filtran el framework (do-operation, backdoor paths). Fix aplicado:
  preguntas naturalizadas.
- **Conecta con:** A1, A3 en `TODO.md`

### Mediciones indirectas — senales proxy en el SCM
- **Pregunta:** como hacer que el solver no vea variables causales directamente
  sino senales instrumentales proxy, como en investigacion real.
- **Empezar por:** `notes/indirect_measurement_design.md`
- **Conclusion:** no requiere capa nueva — son nodos adicionales en el grafo
  cuyas ecuaciones simulan la respuesta del instrumento. El orchestrator decide
  que nodos son latentes y cuales observables al diseñar el SCM.
- **Conecta con:** Fase 3 (orchestrator diseña SCMs), LA PREGUNTA
- **Status:** DOCUMENTADO. Implementar cuando orchestrator diseñe SCMs.

### P2: Naturalizacion de preguntas
- **Pregunta:** como eliminar node_ids como codigo y framing de do-calculus
  de las preguntas visibles al investigador.
- **Empezar por:** `notes/p2_semantic_question_naturalization.md`
- **Conecta con:** I10 Fase 2c en `TODO.md`, hallazgos H1/H2/CF4 de evaluacion
  cualitativa (`synthesis/qualitative_eval_2026_03_24.md`)
- **Status:** IMPLEMENTADO. Pendiente: E2E con 3 SRCs nuevos.

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
  Warrant disabled para Alpha. 129 tests.
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
  23 tests, 7 Codex bugs fixed. Prototype: `notes/oi_subquestion_prototype.md`.
  Treatment world: 0.983 total (vs 0.400 with v2). Dual scoring wired to runner.

### Migracion a SCM — de BN a grafo + ecuaciones + simulacion
- **Decision:** migrar de BN discreta (CPD tables) a SCM (Structural Causal
  Model) con ecuaciones arbitrarias y reward via Monte Carlo.
- **Empezar por:** `synthesis/scm_migration_rationale.md` (fundamentos completos)
- **Evidencia de apoyo:** `notes/gaussian_bn_prototype_findings.md` (prototipo Gaussian)
- **Que se mantiene:** grafo causal, d-separation, do-calculus, reward sin LLM judge
- **Que cambia:** CPD tables -> ecuaciones Python, inferencia analitica -> Monte Carlo
- **Status:** DECIDIDO. Implementacion en branch `feature/scm-engine`
- **Conecta con:** A8 en `TODO.md`
