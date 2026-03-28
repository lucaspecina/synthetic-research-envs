# AUTORESEARCH: Open Investigation Design
# Fecha inicio: 2026-03-26
# Branch: autoresearch-open-investigation
# Modelo: Claude Opus 4.6 (1M context) + Codex gpt-5.4 (MCP)
# Codex thread: 019d2d62-d371-7072-8b4c-319eab3fe156 (anterior expirado: 019d2ae2)

> **ESTE ARCHIVO ES EL "SAVE FILE" DEL AUTORESEARCH.**
> Despues de cada compact, leer este archivo para recuperar contexto.
> Actualizarlo despues de cada milestone significativo.

---

## Principios inmutables — LEER SIEMPRE

### 0. LA PREGUNTA — el filtro de todo
> **Por que esto todavia no es una investigacion real? Que le falta?**

Cada decision de diseno, cada linea de codigo, cada debate con Codex pasa
por este filtro. Si algo no acerca OI a investigacion real, no vale la pena.

### 1. El solver INVESTIGA, no responde preguntas
OI existe porque "responder preguntas pre-hechas" no es investigar. Si el
diseno final se siente como un examen disfrazado de investigacion libre,
fallamos. El solver debe decidir QUE investigar, COMO, y QUE concluir.

### 2. Verificacion exacta contra el SCM — sin excepciones
El SCM es la verdad. No hay LLM judges en el nucleo de scoring. El compiler
TRADUCE, no JUZGA. Si algo no puede verificarse contra el SCM, no entra al
reward core. Esto NO es negociable.

### 3. La subjetividad esta encapsulada, no eliminada
La compilacion tiene subjetividad — lo admitimos honestamente. Pero esta
ACOTADA: claim cards la reducen, preview loop la audita, abstention la
controla. "Exact SCM-grounded verification" != "100% mecanico end-to-end".

### 4. No construir juguetes
Si el resultado final solo puede verificar 10 tipos de cosas, siempre sera
un juguete. La gramatica composable existe para que las verificaciones sean
ABIERTAS — combinar piezas, no enumerar casos. Cada decision debe preguntarse:
"Esto limita artificialmente lo que se puede descubrir?"

### 5. Un cientifico real haria esto?
Litmus test de PROJECT.md. Aplica a claim cards, scoring, gramatica, todo.
Si la respuesta es no, redisenar.

### 6. Debate ANTES de codigo
Investigar -> pensar -> debatir con Codex -> disenar -> implementar ->
cuestionar -> redisenar. NO saltar a implementar. El codigo viene despues
de que el diseno sobreviva al escrutinio.

### 7. Verificabilidad > realismo > elegancia
La jerarquia de PROJECT.md. Si algo mejora el realismo pero rompe la
verificacion, no sirve. Si algo es elegante pero artificial, tampoco.

### 8. Documentar es parte del trabajo, no overhead
Cada conclusion, cada debate, cada decision queda documentada donde
corresponde. Sin docs actualizados, el autoresearch pierde continuidad.

---

## Workflow del autoresearch

```
INVESTIGAR (que problema resolver?)
  -> PENSAR (cuales son las opciones?)
    -> DEBATIR CON CODEX (que se nos escapa?)
      -> DISENAR (decision con evidencia)
        -> IMPLEMENTAR (codigo + tests)
          -> CUESTIONAR (esto pasa LA PREGUNTA?)
            -> REDISENAR si no pasa
              -> DOCUMENTAR siempre
```

### Principio critico: conectar al producto real, no tests aislados

**SIEMPRE preferir integrar con el pipeline E2E real en vez de quedarse
en tests unitarios aislados.** La unica forma de saber si algo funciona
de verdad es verlo correr end-to-end con los pilotos reales. Los tests
unitarios verifican correctitud del codigo, pero no verifican alineacion
con LA PREGUNTA ni con el resto del sistema.

Orden: implementar → tests basicos → **conectar al pipeline real** →
validar con pilotos → iterar. NO: implementar → 50 tests → 50 tests mas →
nunca correr E2E.

### Adaptacion para modo autonomo (usuario ausente)

- Paso 3 del commit workflow (presentar al usuario): **Codex actua como
  reviewer critico.** Si Codex aprueba, commitear. Si Codex tiene objeciones
  serias, documentar la discrepancia y NO commitear hasta resolverla.
- **NUNCA FRENAR.** Siempre hay algo que investigar, debatir, disenar o
  implementar. Si un camino se bloquea, ir al siguiente.
- Despues de cada commit: revisar TODO, elegir siguiente paso, seguir.
- Seguir el workflow normal de CLAUDE.md para todo lo demas (tests, docs,
  promotion rules, etc.)

---

## Build order de Open Investigation Alpha (A15)

1. [x] Formalizar gramatica composable como DSL ejecutable
2. [x] Prototype salience map (7 pattern types, multi-atom families)
3. [x] Claim card contract (Pydantic models con slots minimos)
4. [x] Compiler: deterministic pipeline + LLM extraction infrastructure.
   ClaimIntent IR + lowering + matching + scoring + extraction prompt builder +
   response parser + deterministic fallback. LLM call is pluggable.
5. [x] Verifier scoring sin compiler (claims formales perfectos)
6. [~] Episode runner + extraction pipeline implemented. Solo falta LLM real.
   OIEpisodeRunner: artifact catalog, namespace, trace, scoring pipeline.
   oi_extraction: prompt builder, parser, compile_claim, deterministic fallback.

**STATUS:** Full OI pipeline implemented end-to-end with mock solver. ~200 tests.
Issue #5 (evidence_basis) RESUELTO. Issue #7 (DISTRIBUTION) pendiente (low priority).
Para Alpha-1: solo falta conectar LLM real (solver + compiler extraction).

---

## Referencia rapida — donde esta todo

| Que buscar | Donde |
|------------|-------|
| Vision OI | `research/synthesis/open_investigation_vision.md` |
| Working doc (30 casos, debate) | `research/notes/open_investigation_case_analysis.md` |
| Compiler design | `research/notes/oi_compiler_design.md` |
| Warrant design | `research/notes/oi_warrant_design.md` |
| DSL models | `src/sreg/models/open_investigation.py` |
| Salience map | `src/sreg/tools/oi_salience.py` |
| Verifier | `src/sreg/tools/oi_verifier.py` |
| Compiler (IR + lowering + matching) | `src/sreg/tools/oi_compiler.py` |
| Warrant checker | `src/sreg/tools/oi_warrant.py` |
| Instrumented helpers | `src/sreg/tools/oi_helpers.py` |
| Exemplar bank | `src/sreg/tools/oi_exemplars.py` |
| Episode runner | `src/sreg/tools/oi_runner.py` |
| LLM extraction | `src/sreg/tools/oi_extraction.py` |
| Solver prompt template | `src/sreg/tools/oi_prompts.py` |
| Todo list OI | `TODO.md` seccion A15 |
| Principios del proyecto | `PROJECT.md` |

---

## Log de progreso (actualizar despues de cada milestone)

### Sesion 1 — 2026-03-26 noche
- **Inicio:** branch creada, principios documentados, crons configurados
- **Se corto:** la sesion se interrumpio antes de avanzar

### Sesion 2 — 2026-03-27
- **Continuacion:** retomado por usuario, crons reconfigurados
- **Fase 1 COMPLETA:** 5 preocupaciones criticas investigadas (sesgo
  interventional, Goodhart simplicidad, truth map explota, taxonomia
  es fundamental, compiler sin evidencia)
- **Fase 2 COMPLETA:** debate con Codex. 3 cirugias aceptadas. Spec
  corregida entregada con QueryContext, 15 macros, salience map, scoring.
  Thread Codex activo: 019d2d62-d371-7072-8b4c-319eab3fe156
- **Fase 3 COMPLETA:** DSL implementado como Pydantic models (42 tests)
- **Fase 4 EN CURSO:** verifier engine implementado (15 tests, 57 total)
  - verify_atom: arms -> measure -> compare -> assert, all 6 QueryKinds
  - score_claim_against_family: specificity bonus + overclaim penalty
  - score_episode: correctness(60%) + coverage(30%) + efficiency(10%)
  - Pendiente: salience map generator, macros, docs update
- **Issue #4 FIXED:** familias multi-atomo (1-3 atomos con qualifiers)
- **Issue #1 FIXED:** ADJUST ahora usa stratificacion observacional
- **Issue #6 FIXED:** 7 pattern types (was 5): added observational + ranking
- **Issue #3 FIXED:** mediation specs ahora usan 4-arm contrast-diff (indirect
  effect = total - controlled_direct), antes usaban PROPORTION que solo
  calculaba ratio de medias (no verificaba mediacion en absoluto)
- **Issue #2 FIXED:** identifiability usa DAG dirigido + backdoor criterion
  (mutilated graph), antes usaba dag.to_undirected() que era incorrecto
- **_extract_scalar helper:** assertions (POSITIVE, NEGATIVE, etc.) ahora
  funcionan con cualquier tipo de comparacion (DIFFERENCE, CONTRAST_DIFF,
  PROPORTION, RATIO, GAP) — antes solo leian "difference" key
- **Pilot E2E VALIDADO:** Oracle(0.775) > No-data(0.550) > Shotgun(0.340)
- **103 tests passing** (42 models + 22 verifier + 9 salience + 4 pilot + 26 compiler)
- **16 commits**, todo pushed
- **Compiler COMPLETO (sin LLM):** ClaimIntent IR + WorldSummary + lowering
  (7 patterns) + preview validator + matching a salience families +
  score_compiled_episode full pipeline. 26 tests inc. E2E pipeline.
  Falta: LLM extraction (ClaimCard -> ClaimIntent) solamente.
- **Docs actualizados:** case_analysis.md, vision.md, session file
- **STATUS: Alpha-0 funcional.** Pipeline separa oracle/nodata/shotgun.
  Issues pendientes: #5 (evidence_basis no se usa), #7 (DISTRIBUTION placeholder).
  Para Alpha-1 necesita compiler LLM + solver adaptado.

### Sesion 3 — 2026-03-27 (continuacion post-compact)
- **Issue #5 FIXED:** Evidence warrant system designed + implemented.
  Codex debate thread: 019d2de7-b436-7182-afc5-503aa2de0705
  - EpisodeTrace model: ArtifactAccess + AnalysisRecord (structured, timestamped)
  - WarrantResult model: per-claim assessment (score, level, ref counts)
  - oi_warrant.py: compute_claim_warrant (4 levels: exists/accessed/relevant/substantive)
  - score_episode modified: warrant_scores multiplier on correctness + coverage
  - prior_floor=0.15: right from priors=15%, full evidence=100%
  - Temporal ordering enforced: access before claim
  - Derived artifacts supported: solver-created data counts
  - Explicit disabled mode: None trace = full credit (backward compat)
  - 28 tests (4 trace + 12 warrant + 3 episode + 7 scoring + 2 pipeline)
  - Codex review: 4 fixes applied (cross-analysis, ops tightened, ValueError, temporal)
  - Design note: research/notes/oi_warrant_design.md
- **Warrant wired into score_compiled_episode():** multi-spec claims
  (mediation → 2 specs) share same warrant. Pipeline: compile → verify →
  match → warrant → score. 3 new E2E pipeline tests added.
- **134 tests passing** (42 models + 22 verifier + 9 salience + 4 pilot +
  29 compiler + 28 warrant)
- **Trace contract designed:** research/notes/oi_trace_contract.md
  Hybrid instrumentation: load_artifact() mandatory, helpers preferred,
  raw pandas allowed. DataAsset.artifact_id added to model + builder.
- **Solver prompt designed:** research/notes/oi_solver_prompt_design.md
  Association vs causation guidance, instrumented helpers exposed,
  epistemological closure criteria. Codex-reviewed (anti-overclaiming,
  anti-shotgun, metadata in catalog).
- **WorldSummary consistency audit:** No structural problem. Salience map
  and compiler both use p25/p75 from same world. Matching doesn't
  compare arm values. Shared WorldSummary would be cleaner but not
  blocking.
- **Instrumented helpers implemented:** oi_helpers.py with corr, regress,
  stratify, test_independence, groupby_mean. Auto-log AnalysisRecords.
  tag_dataframe() for artifact provenance. 17 tests.
- **151 tests passing** (42 models + 22 verifier + 9 salience + 4 pilot +
  29 compiler + 28 warrant + 17 helpers)
- **STATUS: All non-LLM infrastructure complete.** Warrant, helpers,
  trace contract, solver prompt, artifact_id all done. 27 commits.
  For Alpha-1: LLM extraction, OI episode runner, solver prompt impl.

### Sesion 4 — 2026-03-27 (post-compact #2)
- **OI Episode Runner implemented:** `oi_runner.py` — ArtifactCatalog,
  OIEpisodeRunner (namespace, trace, scoring pipeline). 25 tests.
- **Compiler LLM extraction implemented:** `oi_extraction.py` — prompt
  builder, response parser, compile_claim, deterministic fallback. 28 tests.
- **Auto-compilation wired:** submit_claims() auto-compiles via extraction
  pipeline when no pre-compiled claims provided. Deterministic fallback
  uses focus_variables (strict, no text scanning).
- **Codex review (thread 019d2e52):** 5 issues found, all addressed:
  - FIXED: Namespace leak (__self__ → closures, no backrefs)
  - FIXED: OIHelpers proxy (blocks _log/_trace access)
  - FIXED: Derived artifact provenance (AnalysisRecord + lineage)
  - FIXED: compiled_claims validation (type, count, claim_id alignment)
  - FIXED: LLM extraction fails closed (exceptions → abstention)
  - FIXED: Stricter deterministic fallback (focus_variables only)
  - KNOWN: Fabricated data bypass (solver creates DataFrame from scratch,
    saves as derived, cites in claim → warrant 1.0). Deferred to RL
    hardening phase — Alpha-1 solver is cooperative.
- **67 new tests** (25 runner + 28 extraction + 14 Codex-fix tests)
- **1709 total tests passing** (was 1656 + 53 new)
- **STATUS: Full OI pipeline end-to-end.** Solo falta conectar LLM real.

### Sesion 5 — 2026-03-27 (con usuario presente)
- **Primer piloto real OI** con LLM (gpt-5.2-codex solver + gpt-5.4 compiler)
  contra treatment world curado
- **Hallazgo 1:** Warrant demasiado agresivo mataba claims correctos
  (0.167 con warrant → 0.619 sin warrant). Warrant deshabilitado para Alpha.
  No estaba en el plan Alpha original ("sin warrant formal").
- **Hallazgo 2:** LLM compiler funciona — traduce mediacion a 2 specs,
  detecta confounding como abstention. Score mejoro de 0.078 a 0.750
  correctness con compiler LLM.
- **Hallazgo 3:** Solver investiga de verdad (correlaciones, regresion,
  estratificacion, Baron & Kenny para mediacion). Anti-overclaiming del
  prompt funciona — dice "association" no "causal effect".
- **Debate fundamental sobre scoring:** salience map como techo vs piso.
  4 AIs + usuario coinciden: salience map no puede ser el arbitro.
  Documentado en `research/synthesis/oi_scoring_fundamentals.md`.
- **Framework mental clave:** pregunta vaga = multiples outputs valiosos
  (no multiples verdades arbitrarias). Sub-preguntas con pesos como
  mecanismo de relevancia: el brief implica que es mas/menos importante.
- **Decision:** no redisenar scoring sin datos. Correr 3 mundos primero,
  identificar problemas reales, iterar despues.
- **Cambios en codigo:** warrant disabled en oi_runner.py, oi_pilot.py
  (script de piloto, removido post-uso).
- **Codex threads:** 019d2f29 (test), 019d2f6d (analisis piloto, expirado),
  019d305a (critica scoring)
- **STATUS:** Principios de scoring documentados. Proximo: correr pilotos
  en 3 mundos con pipeline actual.

### Sesion 6 — 2026-03-27 (con usuario presente, continuacion)
- **6 pilotos OI reales** (3 mundos x 2 runs): ecosystem, treatment, education.
  Solver: gpt-5.2-codex, Compiler: gpt-5.4, warrant disabled.
- **Resultados:** avg total=0.622, correctness=0.772, coverage=0.197.
  Treatment mejor caso: 0.769 total, 1.0 correctness.
- **6 problemas sistematicos (P1-P6):**
  - P1 CRITICO: confounding no es compilable → claims correctos score 0
  - P2: null findings (no effect) no soportados
  - P3: coverage saturada por diseno (MAX_CLAIMS=5, 17 familias)
  - P4: precision gate mata runs con claims vagos pero correctos
  - P5: tags del solver no matchean compiler
  - P6: import errors gastan steps (prompt puede mejorar)
- **Codex review (thread 019d30b7):** "El solver es mejor que el scorer.
  Family match esta gateando correctness — un claim verdadero unmatched
  recibe 0. Esto contradice el principio documentado en scoring_fundamentals.
  Correctness promedia por specs no por claims (bug conceptual). Coverage
  esta en el techo por diseno."
- **Fix generate_src.py:** --solve ahora funciona con SCMWorlds.
- **Scripts creados:** oi_pilot_batch.py, oi_demo_case.py (full_case_oi.md).
- **4 demos generados:** oi_treatment (OI, 0.769), oi_ecosystem (OI, 0.571),
  air_pollution (task-based E2E), coral_reef (task-based E2E).
- **STATUS:** OI piloteado con datos reales. Problemas concretos identificados.
  Proximo: fix P1 (confounding), desacoplar correctness de family match,
  conectar OI al orchestrator.

### Sesion 7 — 2026-03-27 (autoresearch, scoring v2)
- **Scoring v2 implementado** (3 fases, Codex thread 019d31e7):
  - Fase 1: correctness desacoplada de family match + relevancia estructural
  - Fase 2: confounding como patron compilable (PatternClass.CONFOUNDING)
  - Fase 3: prompt mejorado (imports, null findings) + exemplars actualizados
- **Diseño con Codex (3 rounds):**
  - R1: esquema v2 minimalista, relevancia, formula por claim
  - R2: stress test de relevancia, guardrails (NON_TARGET_CAP, descriptive penalty)
  - R3: review implementacion, 5 hallazgos, fixes aplicados
- **Cambios principales en codigo:**
  - `compute_structural_relevance()`: DAG-based, sin LLM. Tiers 1.0/0.7/0.4/0.0
  - `score_compiled_episode_v2()`: truth separado de family match, per-claim min()
  - `score_episode_v2()`: correctness=mean(effective), coverage=truth-based
  - `_lower_confounding()`: causal ATE + partial correlation (2 specs)
  - `_enumerate_confounding()`: raw corr vs partial corr gap detection
  - Solver prompt: explicit namespace, no imports, null findings validos
  - Exemplar bank: +2 NEAR_ZERO, +2 CONFOUNDING
- **Runner wired:** OIEpisodeRunner.submit_claims() usa v2
- **Tests:** 18 nuevos (8 relevance + 7 episode + 3 confounding E2E),
  todos los existentes siguen pasando (130+)
- **Codex fixes aplicados:** family match usa match_score no truth,
  coverage usa truth_score no effective, confounder validado en validate_intent,
  sign-flip gap en salience
- **Orchestrator OI wiring:** oi_mode flag, generate_src.py --oi,
  full pipeline seed → orchestrator → SCMWorld → OI → score
- **E2E test running:** generate_src.py --oi con LLM real
- **STATUS:** Scoring v2 + confounding + OI-orchestrator wiring implementados.
  201 tests passing. Pendiente: validar E2E con LLM, re-pilotar comparativo.

### Sesion 8 — 2026-03-28 (con usuario, luego autoresearch)
- **Debate fundamental de scoring** con usuario: scoring actual es single-target,
  no funciona para investigaciones reales multi-objetivo.
- **Decisiones de diseño criticas (usuario):**
  - UN solo metodo de scoring para todo (sin tipos hardcodeados)
  - Sistema se adapta a casos, no al reves
  - Brief libre (1 o N objetivos, vago o preciso)
  - No construir juego estructurado
  - Validar contra 23 escenarios siempre
- **23 escenarios de investigacion creados** como checklist permanente.
  Documentado: `research/synthesis/investigation_scenarios_rubric.md`
- **Sub-preguntas del orchestrator** — diseño completo:
  Documentado: `research/synthesis/oi_scoring_next_design.md`
- **Fixes del compiler aplicados:** exemplars + confounding pattern
- **Merge a feature/open-investigation-design:** todo consolidado
- **Codex thread:** 019d3279-c1c2 (5+ exchanges)

### Sesion 9 — 2026-03-28 (autoresearch continuacion)
- **E2E post-fix:** 3 worlds x 1 run. Confounding fix FUNCIONA
  (treatment C2 matched, education C2 matched). Precision gate sigue
  agresiva (treatment 0.4, education 0.75, ecosystem 0.53).
- **Sub-preguntas prototipadas a mano** para 3 mundos (5 SQs cada uno).
  Documentado: `research/notes/oi_subquestion_prototype.md`
- **Debate con Codex (5 exchanges, thread 019d32e4):**
  - SQ != claim (investigation agenda vs assertion)
  - SubQuestionIntent: pattern + roles + ask_operator + tier
  - ResolvedSubQuestion: resolved_answer + components + acceptance_rule
  - ALL_OF for mediation/confounding (multi-component)
  - Subsumption table for cross-pattern credit
  - Scalar-first classification (not assertion-based)
- **Resolucion validada:** SQ1-SQ3 del treatment world se resuelven
  correctamente contra SCM via pipeline existente (lower+verify).
- **IMPLEMENTACION COMPLETA:**
  - Models: AskOperator, AcceptanceRule, SQTier, SQRoles, SubQuestionIntent,
    ResolvedAnswer, SQComponent, ResolvedSubQuestion, SubQuestionScore,
    EpisodeSubQuestionScore (en open_investigation.py)
  - Resolution: resolve_subquestion, resolve_all (en oi_subquestions.py)
  - Scoring: score_claim_vs_subquestion, score_episode_with_subquestions
  - 23 tests passing
- **Codex review (4 bugs fixed):**
  - ranking_vars/conditioning_set not checked in matching
  - correctness excluded ALL_OF SQs
  - heterogeneity used ATE instead of interaction spec
  - subsumption too lax for confounding
- **Resultado clave:** Treatment world con 4 claims correctas:
  total=0.983 con sub-preguntas (vs 0.400 con scoring actual).
  Confounding recibe credito completo.
- **Dual scoring wired to runner** (oi_pilot_batch.py + oi_runner.py):
  set_subquestions() + _score_with_subquestions() + get_sq_score()
- **Batch run (3 worlds x 1 run, dual scoring):**
  - ecosystem: v2=0.400, SQ=0.200 (SQs all MISS: causal SQs vs obs claims)
  - treatment: v2=0.543, SQ=0.581 (SQ1-SQ3 HIT via c3 mediation)
  - education: v2=0.767, SQ=0.766 (SQ1-SQ2 HIT, comparable to v2)
- **Epistemological fix:** ecosystem SQs changed from causal_effect to
  observational_association. Principle documented: SQs must match what
  solver can epistemologically justify, not orchestrator's knowledge.
- **Codex round 2 (3 more bugs fixed):**
  - ALL_OF component intent built from parent SQ (match-stealing) → from component
  - truth as average of atoms → conjunctive (1.0 if all hold, else 0.0)
  - rank_order no order checking → pairwise concordance
- **5 commits pushed** (d04453d, ab2b674, d1f471a, d69f33c, 7c1e19f)
- **STATUS:** Sub-question pipeline COMPLETE + validated E2E. SQ scoring
  systematically better or comparable to v2. Proximo: orchestrator genera SQs.

### Sesion 10 — 2026-03-28 (autoresearch continuacion)
- **Objetivo:** Disenar e implementar orchestrator SQ generation
- **Codex debate (thread 019d3338):** 2 exchanges. Design questions Q1-Q6.
  Key agreements: Option B (extend design_case), 4-6 SQs, strict validation
  with partial repair, epistemic_regime field, single CasePlan.
- **Implementacion COMPLETA:**
  - CasePlan: optional oi_sub_questions + epistemic_regime, is_oi_mode prop
  - validate_sub_questions(): grounding, roles, epistemology, portfolio, dups
  - Orchestrator: _build_oi_case_plan() handler, OI_MODE_PROMPT (SQ guidance)
  - Tool schema: sub_questions + epistemic_regime in design_case
  - OrchestratorResult.sub_questions propagated to runner
  - generate_src.py: SQ export + runner wiring
- **Codex review (5 findings):**
  - HIGH: SQs not wired E2E → FIXED (generate_src.py wiring)
  - HIGH: experimental/mixed regimes not supported → documented limitation
  - MEDIUM: effect_ranking uses ATEs in obs_only → documented
  - MEDIUM: duplicate detection too coarse → FIXED (directional roles)
  - MEDIUM: latent vars accepted → FIXED (observable check)
- **11 new tests** (8 validation + 3 CasePlan OI mode), 134 passing
- **E2E VALIDATED with real LLM:**
  - 13-variable SCM world (oil&gas frac-hit sanding, from seed)
  - 5 SQs generated by gpt-5.4: 2 causal_effect(HIGH), 1 mediation(HIGH),
    1 confounding(MEDIUM), 1 effect_ranking(MEDIUM)
  - Repair loop worked: 2 rejections (causal in obs_only) → LLM switched
    to mixed regime → accepted on 3rd attempt
  - SQ quality high: 4/5 correctly match SCM causal structure
  - sq4 (confounding) questionable: zone_risk may not confound fluid→sanding
  - JSON export includes sub_questions, wired to runner
- **STATUS:** Orchestrator SQ generation COMPLETE + E2E validated. Next:
  compare orchestrator SQs vs manual SQs on curated worlds, or move to
  other high-priority work.

