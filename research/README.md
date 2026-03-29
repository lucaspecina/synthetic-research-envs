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
