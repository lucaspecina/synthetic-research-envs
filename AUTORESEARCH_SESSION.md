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

