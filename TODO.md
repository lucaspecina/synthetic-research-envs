# SREG — TODO

> Brecha activa entre `ARCHITECTURE.md` y `CURRENT_STATE.md`.
> Statuses: `[ ]` pending | `[~]` in progress | `[x]` done | `[-]` cancelled
>
> **Estructura:** este documento separa analisis (cosas que hay que pensar
> o investigar) de implementacion (cosas que sabemos que queremos hacer o
> probar). Cada item de implementacion referencia el problema que lo motiva.
> Las ideas crudas nacen en `NOTES.md`, se investigan en `research/`, y
> cuando se vuelven trabajo concreto llegan aca.

---

## Analisis y problemas abiertos

Cosas que hay que pensar, entender o decidir antes de implementar.

### A1. Los SRCs no fuerzan investigacion real

Las preguntas causales se responden desde priors del dominio sin mirar los
datos. Las descriptivas (infer_target, causal_effect) si fuerzan analisis.

**Sub-preguntas:**
- [ ] Que hace que una pregunta sea "data-indexed"? Definir criterio claro.
- [ ] La ambiguedad mecanistica es la solucion? (ver NOTES.md)
- [ ] Cuanto de esto se resuelve con mejores preguntas vs cuanto necesita
  cambios estructurales (datos mas complejos, teoria inventada, etc)?

**Evidencia:** 7-SRC eval (2026-03-16), inspiration reports v2.

### A2. Faltan tipos de preguntas cientificas

Los papers reales preguntan cosas que nuestros eval types no pueden
representar. El orchestrator las fuerza en los tipos existentes y pierde
lo mas interesante.

**Tipos implementados (SCM engine):**
- [x] **ATE** — "cuanto cambia Y si movemos X?" (Fase 6)
- [x] **Mediacion** — "que fraccion del efecto pasa por M?" (Fase 6)
- [x] **Interaccion** — "el efecto de X depende de Z?" (Fase 6)

**Tipos que faltan:**
- [ ] **Sesgo de seleccion** — "es real o es un espejismo?"
- [ ] **Atribucion de fuente** — "de donde viene?"
- [ ] **Efectos heterogeneos** — "funciona igual para todos?"
- [ ] **Inverse design** — "que combinacion produce este resultado?"

**Pregunta abierta:** para cada tipo, se puede evaluar con rigor contra el
SCM? Si no, no pertenece al nucleo de SREG.

**Evidencia:** inspiration reports v2, NOTES.md seccion "Tipos de preguntas".

### A3. Semantica realista vs generica

Si usamos cosas basadas en la realidad, el modelo entrenado puede confundir
mecanismos inventados con conocimiento real. Quizas conviene des-realizar
la semantica para que aprenda el core de investigacion.

**Modos propuestos:** realistic (actual), fictional (nombres inventados),
abstract (X1/X2/Y), theory_rich (fictional + literatura inventada, futuro).

**Evidencia experimental (2026-03-17): 3 modos de Vaca Muerta.** Misma BN,
mismos datos, mismas preguntas. Solo cambian los nombres de variables.

| Modo | Avg score | Budget usado | Hallazgo clave |
|---|---|---|---|
| Realistic | 0.425 | 12/12 | Priors de dominio INVIERTEN la respuesta (Q2) |
| Fictional | **0.142** | 11/12 | Unico modo con backdoor adjustment genuino |
| Abstract | 6.69 | **0/12** | Solver no entiende las preguntas (Q1: variable equivocada) |

**Evidencia Vaca Muerta (con research_actions — datos contaminados):**
- Realistic contamina: solver elige intervencion con direccion invertida por prior.
- Fictional fuerza investigacion: unico modo con backdoor adjustment genuino.
- Abstract rompe comprension: respondio variable equivocada. Scores "GOOD"
  eran artefacto de bugs (ya fixeados).

**Evidencia Football (SIN research_actions — corrida limpia, 2026-03-17):**

| Modo | Avg | causal_eff | latent | should_cond | infer_target |
|---|---|---|---|---|---|
| Realistic | **0.094** | 0.264 OK | 0.105 OK | 0.0 POOR | **0.009 GOOD** |
| Abstract | 0.149 | **0.008 GOOD** | 0.296 OK | 0.0 POOR | 0.292 OK |
| Fictional | 0.166 | 0.023 GOOD | **0.085 GOOD** | 0.0 POOR | 0.556 POOR |

**Hallazgos clave post-football:**
- Sin research_actions, diferencia entre modos es MUCHO menor (1.8x vs 47x).
- Fictional sigue produciendo mejor RAZONAMIENTO (conditional independence
  estratificada) pero realistic puede ganar en SCORE por coincidencia estadistica.
- should_condition falla en los 3 modos (ninguno responde yes/no).
- Abstract es viable post-fix (0.149), ya no catastrofico.
- Priors de dominio: depende del dominio. Oil&gas danino, football neutro.

**Conclusiones (N=2):**
- [x] Des-realizar mejora razonamiento pero no siempre mejora score.
- [x] Priors contaminan en oil&gas, no en football. Depende del dominio.
- [x] Replicado con football — patron parcialmente confirmado.
- [ ] Que implicaciones tiene para el entrenamiento RL futuro?
- [ ] Metricas de proceso (no solo score funcional) para capturar calidad
  de razonamiento vs coincidencia estadistica.

**Referencia:** `research/notes/semantic_modes_experiment_2026_03_17.md`
**Implementar:** I2. Experimentos en `experiments/`.

### A4. Solo data-driven u otros tipos de investigacion?

SREG hoy es puro "descubrimiento desde datasets". La investigacion real
incluye teoria previa, papers, hipotesis existentes, resultados
contradictorios.

**Sub-preguntas:**
- [ ] Se puede agregar "literatura inventada" como capa visible?
- [ ] Teoria derivada parcialmente del mundo verdadero — viable?
- [ ] Esto cambia la direccion del proyecto (PROJECT.md)?

**Referencia:** NOTES.md seccion "Teoria inventada", "Solo data-driven".
**Implementar:** I7 (teoria inventada), y modo `theory_rich` en I2.

### A5. Taxonomia de investigaciones y research tasks

~~No tenemos claro los TIPOS de investigacion que existen.~~

**UPDATE 2026-03-28:** Taxonomia completa documentada:
- `research/synthesis/Doc1_Taxonomia_El_Mapa.md` — 11 tipos de objetivo, 4 preguntas, workflows
- `research/synthesis/investigation_scenarios_rubric.md` — 23 escenarios concretos con rubricas
- `research/synthesis/sreg_scientific_coverage.md` — assessment de cobertura SREG

Hay un primer borrador en `research/notes/scientific_taxonomy.md` con 10
tipos + proceso en fases (framing, propose, plan, execute, analyze). Pero
falta profundizar con ejemplos reales de distintos dominios.

**Ejemplo real (surfactantes/petroleo):** seleccion basada en teoria y
tablas → prueba rapida de efectividad → 200-500 ensayos iterativos de
fine-tuning de estabilidad con ajustes finos. Esto es un patron de
investigacion industrial que combina knowledge retrieval, validacion
rapida, y optimizacion iterativa. Nuestros eval types no cubren nada
de esto.

**Sub-preguntas:**
- [ ] Que tipos de investigacion existen? (observacional, experimental,
  de campo, clinica, ingenieria, optimizacion iterativa, etc)
- [ ] Que dimensiones tienen? (fases, tipos de preguntas, tipos de datos,
  tipos de acciones, restricciones)
- [ ] Que hacen Research Gym, SciGym, DiscoveryBench, SciDesignBench como
  tasks? Que podemos aprender?
- [ ] Como se traduce cada tipo a tasks verificables en SREG?

**Referencia:** `research/notes/scientific_taxonomy.md`, inbox de TODO.

### A6. Estudiar como otros sistemas evaluan y entrenan

Estudiar Research Gym, SciGym, Kimi, SciDesignBench y otros proyectos
de RL agentico y long-horizon para entender como EVALUAN y ENTRENAN.
Esto no es para copiar sus tasks, sino para aprender:

- [ ] Que metricas usan para evaluar si un agente "investiga bien"?
- [ ] Como estructuran el RL loop (reward, episodes, curriculum)?
- [ ] Como miden agentic behavior (no solo respuestas correctas)?
- [ ] Que benchmarks usan para medir transferencia?
- [ ] Como hacen el training — que framework, que escala, que datos?
- [ ] Que podemos aprender para disenar nuestro propio eval y training?

Referencia: https://x.com/askalphaxiv/status/2030765298723283424
SciDesignBench: arxiv 2603.12724

**Esto es diferente de A5:** A5 es sobre taxonomia de investigaciones
reales (para disenar SRCs mas diversos). A6 es sobre como otros sistemas
miden y entrenan razonamiento cientifico (para evaluar SREG mejor).

### A7. Evaluaciones y validaciones existentes sin uso

Se construyeron QualitySuite, DiagnosticRunner, baselines, pero parte
quedo desactualizada o sin uso real. Hay que repasar que sirve y que no.

- [ ] QualitySuite: solo 3/9 eval types. Actualizar o reemplazar?
- [ ] DiagnosticRunner: funciona pero los resultados no se usaron para
  iterar. Como cerrar el loop?
- [ ] Baselines: son los correctos para los eval types actuales?

### A8. Representacion del mundo — RESUELTO

**[x] RESUELTO.** SREG migro completamente a SCM (Structural Causal Model)
con ecuaciones arbitrarias y variables continuas. Todo el codigo BN discreto
(pgmpy, CPD tables, ExactBayesSolver) fue eliminado.

El SCM resuelve los 3 problemas originales:
- **Realismo**: variables continuas con unidades reales (celsius, mg/L, etc.)
- **Escalabilidad**: sin limite de padres (ecuaciones, no tablas exponenciales)
- **Expresividad**: sigmoid, umbrales, interacciones, saturacion

Reward via Monte Carlo (~exacto con N=20K+). El grafo causal se mantiene
intacto (d-separation, do-calculus, identifiability).

### A9. Inspiration report: racionalizacion post-hoc

El report narrativo se genera DESPUES del SRC, por un LLM diferente al
orchestrator. Eso significa que "explica" las decisiones reconstruyendo
razones, no capturando las reales. Solo el manifest tiene la intencion
real del orchestrator (y el manifest solo se usa como input del report).

**Solucion propuesta:** reemplazar emit_inspiration_manifest por un paso
donde el orchestrator escriba el report directamente durante la creacion.
El orchestrator tiene todo fresco: que leyo del seed, por que eligio cada
variable, como mapeo las preguntas, que no pudo representar.

Partes que el orchestrator puede escribir: decisiones de variables,
estructura causal, mapeo de preguntas, que se perdio. Partes que necesitan
post-hoc: verificacion contra el SRC final, evaluacion de datos generados,
limitaciones desde perspectiva de SREG developer.

- [ ] Reemplazar manifest por report escrito durante la creacion.
- [ ] Paso post-hoc liviano solo para verificacion y limitaciones.

### A10. Errores de formato del solver queman iteraciones

En los 3 modos semanticos, el solver lucha con los formatos de submission
(distribution vs choice vs node+state). Gasta 2-4 iteraciones del budget
en errores de formato antes de lograr submitir correctamente. Esto NO es
un problema semantico — es un problema del prompt/tooling.

**Evidencia (2026-03-17):** En realistic, el solver primero envio `choice`
para Q1 (necesitaba `distribution`), `choice` para Q2 (necesitaba
`node+state`). En fictional, envio `variables` para Q3-Q5 (necesitaba
`choice`/`distribution`). Solo despues de recibir errores corrigio.

**Sub-preguntas:**
- [ ] Mejorar prompt del solver para que sepa el formato antes de submitir?
- [ ] Agregar ejemplos de formato en el system prompt por pregunta?
- [ ] El deadline nudge compensa esto parcialmente pero no es solucion.

### A11. Solver confunde variables target con observables similares

El solver computa la distribucion de una variable EQUIVOCADA cuando el
nombre en la pregunta se parece a una columna del dataset. Ejemplo:
pregunta sobre `neuromuscular_fatigue` (latente), solver computa
`first_half_high_intensity_output` (observable con distribucion similar).

El prompt ya incluye `Target: **variable_name** (states: ...)` pero el
lenguaje natural de la pregunta domina la atencion del solver. Esto es un
failure mode legitimo del solver, no un bug del sistema — un investigador
real tambien deberia inferir la variable latente, no reportar la observable.

**Evidencia (2026-03-17):** Football realistic Q1 (computo tactical_drop
en vez de physical_drop) y Q2 (computo first_half_output en vez del latente
neuromuscular_fatigue). Score "bueno" por coincidencia estadistica.

**Decision:** No agregar pistas extra al prompt. Si el solver confunde
variables, es un error legitimo que el scoring deberia penalizar. La solucion
a futuro es mejorar el scoring para detectar cuando la distribucion submitida
proviene de la variable equivocada.

### A12. Scores enganiosos por coincidencia estadistica

En algunos SRCs, la distribucion marginal de una variable observable es
casi identica a la posterior causal de otra variable. El solver computa la
marginal (facil, sin causal inference) y obtiene un score GOOD por
coincidencia. Esto infla artificialmente los scores del modo realistic.

**Evidencia (2026-03-17):** Football realistic Q1: marginal de
tactical_drop {moderate: 0.674} vs posterior causal de physical_drop
{moderate: 0.656}. KL = 0.002 GOOD, pero el razonamiento fue incorrecto.

**Sub-preguntas:**
- [ ] Se puede verificar que la variable computada sea la correcta?
- [ ] Agregar una metrica de "proceso" ademas del score funcional?
- [ ] Datos con distribuciones mas diferenciadas reducirian este problema?

### A13. El brief visible muestra preguntas internas, no el research_brief

**El problema central**: el sistema genera un `research_brief` natural y
`deliverables` naturales (Fase 5), pero el briefing que ve el solver los
IGNORA y muestra las preguntas internas de scoring directamente.

En `generate_src.py:219-228`, cuando hay tasks, el codigo:
1. Muestra `### Question N (eval_type)` — revelando el tipo de evaluacion
2. Muestra `Task.question` — que viene de templates tipo examen
3. Muestra `Target variable: X` — metadata interna de scoring

Mientras tanto, el `research_brief` y los `deliverables` del `CasePlan`
se guardan en `ResearchProblem.research_question` pero nunca se muestran.

**Evidencia (2026-03-24):** 3 SRCs generados (football, Vaca Muerta, coral
reef). Los backgrounds son creibles, pero las preguntas suenan a parcial:
- "maximize X being above 45.73" (compare_interventions)
- "Answer yes or no" (interaction)
- "Which variables should be controlled for?" (adjustment_set)

**Causa raiz (3 capas):**
1. `export_briefing()` ignora el brief y muestra task questions (arreglo facil)
2. Las preguntas nacen del catalogo de eval types, no del paper (arreglo medio)
3. Los templates de preguntas son rigidos y tipo examen (arreglo medio)

**Diagnosticado con Codex.** Codex confirmo que `compare_interventions` esta
en `NEVER_OVERRIDE` (el orchestrator ni siquiera puede mejorar el wording),
y que el prompt pide "different eval types" forzando cobertura del menu en
vez de coherencia cientifica.

**Referencia:** sesion 2026-03-24. Implementar: I10.

### A14. Falta evaluacion cualitativa formal

Los problemas mas graves de SREG (preguntas tipo examen, mecanicas de juego,
framing artificial, narrativa como skin) se encontraron siempre via inspeccion
cualitativa ad-hoc. El framework cuantitativo (KL, submit rate, verdicts)
NO captura estos problemas — un SRC puede tener scores "GOOD" y seguir
sintiendo como un benchmark disfrazado.

**Diagnosis (con Codex, 2026-03-24):**
- eval_strategy.md ya dice "inspeccion cualitativa sigue siendo necesaria"
  (principio 4), pero nunca se volvio operativa.
- eval_design_notes.md tiene P.1-P.6 (presentacion) y E.5 (litmus test
  subjetivo), pero sin protocolo concreto ni rubrica.
- Cada mejora se evalua con 1-3 SRCs leidos informalmente. No hay
  comparacion sistematica ni tracking temporal.

**Propuesta:** rubrica con 7 dimensiones (0/1/2) + 6 critical failures
(binarios) + probe hibrido "no-data baseline". Revision manual de 3-20
SRCs por cambio, formato estructurado, tracking temporal.

**Referencia:** `research/synthesis/qualitative_eval_rubric.md`
**Implementar:** I11.

### A15. Open Investigation — investigacion libre con verificacion SCM exacta

Hoy SREG mide si el solver RESPONDE bien, no si INVESTIGA bien. La
estrategia investigativa (que preguntar, por que, en que orden) no se evalua.

**Arquitectura (3 capas):** Solver (investiga libre, entrega claim cards) →
LLM Compiler (compila a specs ejecutables, no juzga) → SCM Verifier (exacto).

**Gramatica composable (reemplaza 4 primitivas fijas):** cada verificacion =
Simulacion + Medicion + Comparacion + Asercion. ~24 piezas atomicas que se
combinan en cientos de verificaciones posibles. No es catalogo fijo. Agregar
tipo nuevo = combinar piezas o agregar pieza atomica.

**Claim cards semi-estructuradas:** el solver reporta hallazgos con: texto,
variables foco, contexto, patron, confianza, evidencia. Es un formato de
reporte cientifico, no un formulario tecnico.

**Compile-preview loop:** el compiler muestra parafrasis canonica, el solver
corrige en NL (max 2 rondas). Para eval formal: loop completo. Para RL: claim
cards explicitas + compilador local, sin preview.

**Truth map algoritmico:** enumerar verdades canonicas del SCM sin LLM
(ATEs, mediaciones, interacciones, thresholds, quantiles, d-separations).
Clusterar en familias. Coverage = familias descubiertas.

**Scoring Alpha:** correctness 60%, coverage 30% (con precision gate),
efficiency 10%. Sin calibration ni warrant formal en Alpha.

**Stress test (30 casos, 10 dominios):** 12 FUNCIONA (40%), 13 PARCIAL (43%),
5 NO FUNCIONA (17%). Cuello: compilacion, no claim cards. Lo que rompe:
claims epistemicos (taxonomia, subidentificacion), no causales complejos.

**Referencia:** `research/synthesis/open_investigation_vision.md`
**Working doc:** `research/notes/open_investigation_case_analysis.md`
**Status:** ALPHA-0 PILOTEADO CON LLMs REALES (6 runs, 3 mundos).

- [x] Formalizar gramatica composable como DSL ejecutable
- [x] Prototype truth map (salience map: 7 pattern types, multi-atom families)
- [x] Claim card contract (Pydantic models con slots minimos)
- [x] Verifier scoring sin compiler (claims formales perfectos)
- [x] Compiler deterministic pipeline (ClaimIntent IR + lowering + matching)
- [x] Evidence warrant system (4 levels, prior_floor=0.15)
- [x] Instrumented helpers (corr, regress, stratify, test_independence)
- [x] Episode runner (artifact catalog, namespace, trace, scoring pipeline)
- [x] Compiler LLM extraction infra (prompt builder, parser, fallback)
- [x] Solver prompt template (system + tools + briefing + strategy)
- [x] OI Driver (LLM solver <-> runner loop, submit-is-terminal, 38 tests)
- [x] Curated worlds (3 SCMWorlds for testing: ecosystem, treatment, education)
- [x] Piloto real (6 runs, solver gpt-5.2-codex + compiler gpt-5.4)
- [x] Warrant disabled para Alpha (era demasiado agresivo)
- [x] Scoring fundamentals documentados (salience map = piso no techo)
- [x] Fix P1: confounding como patron compilable (scoring v2, Sesion 7)
- [x] Fix P2: NEAR_ZERO assertions (exemplars + prompt, Sesion 7)
- [x] Desacoplar correctness de family match (scoring v2, Sesion 7)
- [x] Conectar OI al orchestrator (generar OI problems, no solo task-based) — Sesion 7
- [x] Fix: compiler LLM perdia todos los few-shot exemplars — Sesion 8
- [x] Fix: extraction prompt no listaba confounding — Sesion 8
- [x] Re-pilotar 3 mundos con scoring v2 + SQ dual scoring (batch validated)
- [ ] Compiler benchmark offline (200+ claims, >90% precision)
- [ ] Alinear verificacion de confounding con deteccion (gap raw-partial)
- [x] **Migrar a scoring por sub-preguntas (A19)** — implementado, piloteado, E2E

### A19. Scoring Next: sub-preguntas ocultas del orchestrator

**EL cambio mas importante del sistema.** El scoring actual ancla todo a
UNA variable target — solo funciona para ~3/23 escenarios de investigacion.
La investigacion real tiene multiples outcomes, system mapping, confounding
como objetivo, prediccion, y mas.

**Idea central**: el orchestrator genera sub-preguntas ocultas (inspiradas
en el seed/paper) que son el criterio real de evaluacion. El mundo se
diseña PARA que esas sub-preguntas sean respondibles. Claims del solver y
sub-preguntas pasan por el MISMO pipeline de compilacion formal.

**Diseno detallado**: `research/synthesis/oi_scoring_next_design.md`
**Escenarios de validacion**: `research/synthesis/investigation_scenarios_rubric.md` (23 escenarios)
**Taxonomia de investigacion**: `research/synthesis/Doc1_Taxonomia_El_Mapa.md`

**Principios de diseno (en CLAUDE.md):**
- UN solo metodo de scoring para todo (no tipos hardcodeados)
- El sistema se adapta a los casos, no al reves
- El brief es libre (1 o N objetivos, vagos o precisos)
- Verificacion exacta (SCM), relevancia puede evolucionar (formal → LLM si necesario)
- Sub-preguntas = piso de coverage, no techo (bonus para novel discoveries)

**Implementacion (en orden):**
- [x] Modelo de datos: SubQuestionIntent, ResolvedSubQuestion, SQRoles, etc.
- [x] Orchestrator emite sub-preguntas al diseñar el caso (design_case + validate)
- [x] Sub-preguntas compiladas a specs formales (resolve_subquestion pipeline)
- [x] Matching programatico (firma canonica) claim vs sub-pregunta
- [x] Scoring: truth(SCM) * match * coverage_subpreguntas * no-redundancia
- [x] Pilotar con 3 mundos curados: comparar vs scoring v2
- [x] E2E con orchestrator real: 5 SQs generados por LLM, repair loop funciona
- [ ] Comparativo: manual SQs vs orchestrator SQs (mismo mundo)
- [ ] Decidir si reemplazar v2 o mantener dual

**Conecta con**: A15 (OI), A2 (tipos de preguntas), A5 (taxonomia), A1 (forzar investigacion)

---

### A16. Quality gates por task primitive — eval cualitativa 2026-03-25

Evaluacion de 3 SRCs (I11 Fase 2) revelo que varios eval types producen
respuestas que no discriminan:

- **Interaction siempre "no" (2/2 SRCs)**: `_find_modifier()` elige pares
  al azar sin verificar si la ecuacion tiene interaccion real. Las ecuaciones
  del orchestrator tienden a ser aditivas.
- **Mediacion = 1.0 exacto (1/3 SRCs)**: cadenas lineales puras dan mediacion
  total trivial.
- **best_intervention incluye downstream (1/3 SRCs)**: el sistema no
  distingue "observable" de "intervenible".

**Sub-preguntas:**
- [x] Interaction: mezcla yes/no garantizada. Busca strongest "yes" entre
  todos los ancestros; si no hay, devuelve "no" con mejor par. (Paso 2)
- [x] Mediacion: quality gate 0.05-0.95. Multi-treatment search. (Paso 2)
- [x] best_intervention: inferido desde DAG (ancestros causales). (Paso 2)

**Evidencia:** `research/synthesis/qualitative_eval_2026_03_25.md` (P1, P3, P4)

### A17. Direccion causal obvia desde priors — PARCIALMENTE RESUELTO

Los 3 Q1 de causal_effect piden efectos cuya direccion es sentido comun.
Un LLM podria acertar sin datos. Es EL problema central para LA PREGUNTA.

**Sub-preguntas:**
- [x] Cuanto afecta? Correr no-data baseline probe formal.
  HECHO: `scripts/oi_nodata_baseline.py`. Resultado: treatment gap=-0.093,
  education gap=0.000. Solo ecosystem fuerza datos (gap=+0.570).
- [x] Soluciones: mundos ficcionales, Simpson's paradox, efectos no
  monotonicos, preguntas con direccion genuinamente incierta?
  HECHO: 3 patrones data-indexed validados (Simpson gap=+0.13,
  suppressor gap=+0.49, confounding reversal gap=+0.35).
- [ ] Es un problema del SCM (relaciones intuitivas) o de la pregunta
  (pedir direccion en vez de magnitud)?
- [ ] Formalizar investigation_gap como gate de aceptacion de mundos.
  Propuesta: gap < 0.15 -> rechazar o redisenar el mundo.
- [ ] Mundos que no fuerzan (treatment, education): redisenar o mantener
  solo como test fixtures?

**Evidencia:** `research/notes/oi_investigation_gap.md` (analisis completo,
resultados 6 mundos, debate con Codex, patrones identificados).
**Conecta con:** A1, A3 (modos semanticos), I2 (fictional mode)

### A21. Evaluation harness no reconoce findings correctos — E2E 2026-03-28

**EL problema actual mas critico.** En el E2E de 4 casos, el coral reef
caso demostro que el solver PUEDE investigar y PUEDE submitir (5 claims),
pero las 4 sub-preguntas scored 0.00 MISS. Los claims eran correctos.

**Root cause: claim compilation (LLM step) extrae patron equivocado.**
El solver usa lenguaje hedgeado ("associated with") porque el prompt dice
ser cauteloso. Pero los SQs esperan pattern=causal_effect. El compiler
extrae pattern=observational_association -> exact-match falla.

**Codex summary:** "the worlds may already be good enough, and the solver
may already be capable of useful research behavior, but the evaluation
harness is still not trustworthy enough to tell you that."

**Sub-preguntas:**
- [ ] Mejorar el compiler (LLM extraction): el bottleneck real es que el
  compiler traduce mal los claims. Mejorar prompts, exemplars, fallbacks.
  **NOTA: se intento resolver con structured claims (A21-fix) pero fue
  REVERTIDO porque sesga al solver mostrando categorias de scoring.
  La solucion es mejorar el compiler, no constreñir al solver.**
- [ ] Split scoring into separate axes: topical match, inferential type,
  sign, evidence strength. A claim can be topically correct but pattern-wrong.
- [ ] Audit failed coral claims: classify as compiler miss vs SQ ontology
  mismatch vs wrong answer.

**Evidencia:** `research/notes/e2e_qualitative_analysis_20260328.md` (Case 4)
**Conecta con:** A15 (OI), A19 (SQ scoring), LA PREGUNTA

### A22. Submission aversion — solver resists calling submit_claims

2/4 E2E cases: solver did real analysis but scored 0 because it never
submitted. Even with progressive nudges (50%, 75%, FINAL) and explicit
"You MUST call submit_claims now", the soil case solver ran another
regression on its last turn.

**Root cause:** behavioral — solver treats submit_claims as psychologically
terminal. It always wants "one more analysis" before committing.

**Mitigaciones implementadas:**
- [x] Progressive deadline nudges (3-phase: halfway, deadline, final)
- [x] Hard submit guard on final iteration (reject non-submit tool calls)
- [ ] Validate hard submit guard in E2E rerun
- [ ] Consider continuous claim drafting (draft_claim tool, finalize at end)
- [ ] Consider auto-submit fallback (extract claims from analysis log)

**Evidencia:** `research/notes/e2e_qualitative_analysis_20260328.md` (Cases 1, 3)

### A20. Investigation gap como criterio de aceptacion de mundos

Cada mundo OI debe pasar un test: `score_with_data - score_no_data > threshold`.
Si el gap es bajo, el mundo no fuerza investigacion y no sirve para RL.

**Sub-preguntas:**
- [ ] Cual es el threshold correcto? (0.10? 0.15? 0.20?)
- [ ] Automatizar el probe como parte del pipeline de generacion
- [ ] Que hacer con mundos que fallan? Redisenar automaticamente?
- [ ] El probe debe correr con SQ scoring, v2, o ambos?

**Mundos curados actuales (6):**
| Mundo | Gap v2 | Fuerza? | Patron |
|-------|--------|---------|--------|
| ecosystem | +0.570 | SI | Priors errados en ecologia |
| productivity | +0.488 | SI | Efecto supresor |
| screen_time | +0.350 | SI | Confounding reversal |
| treatment_simpson | +0.132 | SI (mod) | Simpson's paradox |
| treatment | -0.093 | NO | Priors correctos |
| education | 0.000 | NO | Priors correctos |

**Evidencia:** `research/notes/oi_investigation_gap.md`
**Conecta con:** A17, A1, A19

### A18. Capa de datos mecanica y clonico — eval cualitativa 2026-03-25

Todos los SRCs tienen metadata identica ("500 obs, 4 sites, 3 waves") y
descripcion de dataset tipo dump tecnico. Rompe realismo.

**Sub-preguntas:**
- [x] Variar panel config por SRC (3-15 sites, 2-5 waves, 200-2000 obs)?
  HECHO: orchestrator genera PanelConfig con seed-based randomization.
- [x] Reescribir `_describe()` para generar descripcion narrativa?
  HECHO: panel/cross-sectional/generic phrasing, variable counts.
- [ ] Que el orchestrator escriba la descripcion del dataset?

**Evidencia:** `research/synthesis/qualitative_eval_2026_03_25.md` (P2, P6)

---

## Implementacion y experimentos

Cosas que sabemos que queremos hacer o probar. Cada una referencia el
analisis que la motiva.

### I0. Fixes criticos encontrados en sesion 2026-03-17

**Bug verifier: keys de distribucion no validadas en case mode.**
En `_handle_case_submit` (agent.py), el solver podia submitir una
distribucion con keys completamente diferentes a las esperadas (ej:
`{medium, high, low}` cuando se esperaba `{no, yes}`). La distribucion se
aceptaba, se grababa, y el scoring daba KL = 31.7 bits (catastrofico).
**Fix aplicado:** validacion de keys identica a la de single mode (linea 921).
Tests: `test_case_submit_rejects_wrong_distribution_keys`,
`test_case_submit_accepts_correct_distribution_keys`. **1104 tests pasan.**

**Bottleneck: MAX_PARENTS=4 insuficiente para dominios complejos.**
El seed de football genero nodos con 5-6 padres naturales. El orchestrator
gasto 8/10 iteraciones en dag_construct rechazado, nunca llego a design_case.
- [x] Subir `max_iterations` del orchestrator de 10 a 15.
- [x] Migrado a SCM — ya no hay limite de padres (ver A8).

**Bug verdict: logica invertida para choice types.**
El verdict (GOOD/OK/POOR) usaba `< 0.1 = GOOD` para TODOS los tipos, pero
choice types (should_condition, hypothesis, compare, best_intervention, NBO,
adjustment_set) retornan 1.0 = correcto, 0.0 = incorrecto. Resultado:
toda respuesta INCORRECTA se reportaba como "GOOD".
**Fix aplicado:** generate_src.py ahora detecta el tipo y usa `> 0.9 = GOOD`
para choice types vs `< 0.1 = GOOD` para KL types.

### I10. Brief real en vez de preguntas internas — motivado por A13

El solver debe ver el `research_brief` + `deliverables`, NO las preguntas
internas de scoring. Las preguntas internas (`Task.question`) solo sirven
para scoring y debugging.

**Fase 1 (urgente): mostrar el brief real**
- [~] `export_briefing()` en `generate_src.py`: mostrar `research_brief` +
  `deliverables` en vez de task questions individuales
- [~] Quitar `(eval_type)` y `Target variable:` del output visible
- [~] Las preguntas internas van al `answer_key.md`, no al briefing

**Fase 2: mejorar templates de preguntas internas** (Fase 9)
- [x] Reescribir template de `compare_interventions` — quitar threshold
  numerico, quitar "maximize algo negativo", quitar "Answer A or B"
- [x] Reescribir template de `interaction` — quitar "Answer yes or no"
- [x] Sacar `compare_interventions` de `NEVER_OVERRIDE` → movido a
  `SAFE_OVERRIDE` con estimand + entity check
- [x] Quitar restriccion "different eval types" del prompt de design_case

**Hallazgos de Codex (code review Fase 2, 2026-03-24):**
- [x] Entity check para `compare_interventions`: ahora verifica `outcome`.
- [x] `desired_state` residuo BN: eliminado de hints requeridos, marcado
  legacy en schema. Bug oculto: best_intervention override nunca se aceptaba.
- [x] `should_condition` en SCM: ya estaba naturalizado (verificado 2026-03-25).
- [ ] Faltan tests: `test_question_is_natural` para `compare_interventions`
  e `interaction`, test de rechazo de override con entities equivocados.
- [x] Fallback templates usan `snake_case` crudo → RESUELTO por P2
  (`_semantic_name()` + templates naturalizados).

**Fase 2c: naturalizacion de preguntas (P2)** HECHO
Variables como codigo + framing "setting X to Y" → nombres semanticos +
contrafactuales naturales. 3 piezas: helper semantico + templates + entity
matching + prompt. Ver `research/notes/p2_semantic_question_naturalization.md`.
- [x] Helper `_semantic_name()` / `_semantic_aliases()` en `scm_task_gen.py`
- [x] Naturalizar templates en los 12 metodos `_*_task()`
- [x] Actualizar `_entities_match_question` y `_check_question_answer_consistency`
- [x] Prompt de orchestrator: `question_text` ES visible, prohibir snake_case
- [ ] E2E con 3 SRCs nuevos (pendiente: I11 Fase 2)

**Fase 3: preguntas desde la investigacion, no desde el menu** HECHO
Reestructuracion del prompt de orchestrator para romper la monocultura de
eval types. Tres cambios: (1) proceso de dos etapas (preguntas primero,
tipos despues), (2) catalogo plano y alfabetico sin jerarquia, (3) reglas
operativas de type-fit check en vez de auto-reflexion pasiva. Tool definition
tambien neutralizada.

**Evidencia ANTES (2026-03-24):** 3 SRCs post-P2 todos con el mismo patron:
causal_effect + best_intervention + interaction + mediation + infer_latent_cause.
**Evidencia DESPUES (2026-03-24):** 3 SRCs con mismos temas:
- Coral: infer_target, causal_effect, compare_interventions, infer_latent_cause
- Smoking: causal_effect, adjustment_set, mediation, best_intervention, infer_latent_cause
- Football: ate, interaction, mediation, best_intervention, infer_latent_cause
4 tipos nuevos aparecen (ate, adjustment_set, compare_interventions, infer_target).
Revisado con Codex (2 rondas). 1479 tests.

Sub-tareas:
- [x] Proceso de dos etapas en el prompt (preguntas primero, tipos despues)
- [x] Catalogo plano y alfabetico con "Use when" / "Not when" por tipo
- [x] Quitar jerarquia "primary" vs "complementary" del prompt y tool definition
- [x] Reglas operativas de type-fit en vez de "Quality over coverage" pasivo
- [x] Guia de overlap entre tipos que se solapan (ambos sentidos, no solo causales)
- [x] "500 obs / 4 sites / 3 waves" repetido en todos — variar estructura
  (A18: panel config varied per SRC, descriptions improved)
- [x] "hidden factor best explains..." clonado — el template de infer_latent
  siempre produce la misma forma de pregunta (3 variantes rotantes added)

**Fase 4: calidad de realizacion de preguntas** HECHO (parcial)
- [x] Descripciones verbose: threshold tightened (_semantic_name <45 chars, <=6 words)
- [x] Snake_case leak: world-aware sanitization + generic fallback
- [x] Templates mecanicos: 3 variantes rotantes para ate/mediation/interaction
- [ ] Permitir que un deliverable mapee a multiples scoring atoms

### I11. Harness de evaluacion cualitativa — motivado por A14

Formalizar la evaluacion cualitativa de SRCs como parte del workflow de
desarrollo, no como inspeccion ad-hoc. La rubrica es un PISO que evoluciona
— siempre se buscan problemas nuevos mas alla del checklist.

**Fase 1: definir rubrica (HECHO)**
- [x] 7 dimensiones con escala 0/1/2 (framing real, necesidad de datos,
  coherencia entre capas, validez de comparacion, realismo de datos,
  riqueza epistemica, workflow investigativo)
- [x] 6 critical failures binarios (answerable_without_data, exam_like_wording,
  brief_eval_mismatch, variable_name_leak, toy_comparison, narrative_as_skin)
- [x] Documentar en `research/synthesis/qualitative_eval_rubric.md`

**Fase 1b: formalizar harness (HECHO)**
- [x] Seccion "Harness de evaluacion" en `CLAUDE.md` — 3 niveles, cuali+cuanti,
  evolucion de rubrica
- [x] Reescribir skill `/eval` — 8 pasos: cuanti + rubrica + no-data probe +
  descubrimiento abierto + registro + reporte + actualizacion de rubrica
- [x] Protocolo de evolucion en rubrica: descubrimiento → registro → promocion
  cuando recurrente
- [x] Seccion "Registro de hallazgos" y versionado en rubrica

**Fase 2: primera evaluacion formal** HECHO (2026-03-25)
- [x] Generar 3 SRCs post-I10 (football, coral, asthma)
- [x] Aplicar rubrica completa: 7D + 6CF + descubrimiento abierto
- [x] Registrar resultados: `research/synthesis/qualitative_eval_2026_03_25.md`
- [x] Analizar con Codex: 6 problemas nuevos (P1-P6), 3 hallazgos confirmados
- [ ] Correr no-data baseline probe (manual: brief sin dataset a LLM)

**Fase 3: protocolo operativo**
- [ ] Definir set canonico de 5 seeds para comparacion temporal
- [ ] Formato de registro persistente (YAML en experiments/qualitative/)
- [ ] Integrar en workflow post-cambio: generar N SRCs + revisar + registrar

**Fase 4: no-data baseline probe automatizado**
- [ ] Script que toma briefing.md, alimenta un LLM SIN dataset, compara
  con answer_key.md. Si supera random, el SRC no fuerza investigacion.
- [ ] Integrar como paso opcional del diagnostico.

**Fase 5 (futuro): automatizacion parcial**
- [ ] Checks automaticos para CF2 (regex: "Answer A or B", "Submit...") y
  CF4 (pattern match: snake_case en briefing visible)
- [ ] LLM-judge calibrado SOLO despues de 50+ reviews humanas como ground truth

**Referencia:** `research/synthesis/qualitative_eval_rubric.md`, `CLAUDE.md`

### I1. Nuevos eval types — motivado por A2

- [x] `ate`: estimacion de ATE continuo (Fase 6, SCM engine)
- [x] `mediation`: fraccion mediada (Fase 6, SCM engine)
- [x] `interaction`: modificacion de efecto (Fase 6, SCM engine)
- [ ] Disenar `subgroup_effect` o `selection_bias_assessment`.
- [ ] Disenar `inverse_design`: "que combinacion de intervenciones produce
  este resultado?" Verificable con do-calculus multi-intervencion.
  Referencia: SciDesignBench (arxiv 2603.12724).
- [ ] Para cada tipo nuevo: definir scoring, correcta ground truth, y
  agregar al teacher.

### I2. Modos semanticos — motivado por A3

Cuatro modos, opcionales, sobre el mismo SRC (misma BN, mismas preguntas):

- **`realistic`** (actual): nombres cientificos reales, dominio reconocible.
  "maternal_algae_smoke_exposure", "hatchling_mass", "Miralune tern colonies"
- **`fictional`**: nombres inventados con estructura semantica. El solver no
  puede usar priors pero la narrativa suena a ciencia.
  "trelline_exposure", "maturation_index", "Region Veldara"
- **`abstract`**: nombres genericos sin contexto. Puro ejercicio formal.
  "X1", "X3", "Y"
- **`theory_rich`** (FUTURO): fictional + literatura inventada. Papers
  ficticios con hallazgos parciales, contradictorios o sesgados. El solver
  tiene que integrar teoria previa con datos. → Ver A4.

Implementacion:
- [ ] Disenar como transformar la capa semantica post-generacion (renombrar
  variables, reescribir narrativa, ajustar preguntas).
- [ ] Implementar modos `fictional` y `abstract` como post-proceso del SRC.
- [ ] Experimento: tomar 3 SRCs, generar las 3 versiones, correr solver en
  cada una, comparar scores.
- [ ] Medir si el solver usa priors del dominio o investiga los datos.

### I3. Mejorar fidelidad de preguntas al paper — motivado por A1, A2

- [x] Prompt reescrito: preguntas causales como primarias, infer_target
  complementario, seed-first question design.
- [x] Default task_type: causal_effect en vez de infer_target.
- [ ] Re-evaluar los 7 SRCs con prompt nuevo (v2 generados, pendiente
  revisar reports en detalle).
- [ ] Comparar preguntas v1 vs v2 para cada seed.

### I4. Fortalecer el diseno del case — motivado por A1, A5

- [ ] Unificar `scenario_title` y `case_plan.title`.
- [ ] Evolucionar el case hacia estructura investigativa: objetivo,
  hipotesis rivales, evidencia, incertidumbres.
- [ ] Agregar validacion de calidad para CasePlan.

### I5. Validar calidad multi-dominio — motivado por A6

- [ ] Actualizar QualitySuite para 9 eval types.
- [ ] Validar paper-seeded SRCs con 3-5 papers de dominios distintos.
- [ ] Construir taxonomia de failure modes.
- [ ] Avanzar en reproducibilidad.

### I6. Consolidar documentacion

- [ ] Alinear README, PROJECT, ARCHITECTURE, CURRENT_STATE, TODO sin
  solapamientos.
- [ ] Reorganizar research/ (notas, sintesis, archivo).
- [ ] Eliminar referencias stale.

### I7. Teoria inventada y literatura sintetica — motivado por A4

- [ ] Disenar como generar "papers ficticios" derivados parcialmente del
  mundo verdadero (incompletos, sesgados, contradictorios).
- [ ] Implementar como DataAsset o nuevo tipo de artefacto visible.
- [ ] Probar si el solver usa la teoria inventada para investigar.

### I8. Datasets mas realistas — motivado por A1

**Implementado (Fase 7, SCM engine):**
- [x] Estructura de panel: sites + waves con random effects y trend temporal.
- [x] Missing informativo: dropout acumulativo por wave (~18-39% total).
- [x] Proxy columns: variables correlacionadas con noise que el solver debe
  distinguir del signal real.
- [x] Shared study frame: un master sample, artefactos como vistas.

**Pendiente:**
- [ ] Multiples fuentes con discrepancias reales (mas alla de shared frame).
- [ ] Metadata de calidad por columna (instrumento, precision, fecha).
- [ ] Dropout total de sites (no solo parcial).

### I9. Mejorar prompt del orchestrator para eval types — motivado por A2

**Resuelto parcialmente por I10 Fase 3** (catalogo plano, two-stage process,
type-fit rules). Lo que queda:

- [x] Descripciones y "Use when" / "Not when" por tipo (I10 Fase 3).
- [x] Instruir que si no hay tipo adecuado, no forzar (I10 Fase 3).
- [ ] Agregar ejemplos concretos de papers para cada eval type.
- [ ] Cuando se agreguen nuevos eval types, actualizar el prompt.

---

## Backlog

### Infraestructura

- [ ] Timeout real para python_exec via process boundary.
- [ ] Agregar verifiers como dependencia opcional.
- [ ] Coleccion mantenible de paper seeds.
- [ ] Unificar generate() y generate_custom() en WorldGenTool.

### Mundo formal

- [ ] Validar CPDs con checks mas fuertes.
- [ ] Motif composer y expressive range para DAGs.
- [ ] Variables continuas y mundos mixtos. → **Promovido a A8** con analisis
  completo de opciones (Linear Gaussian, CLG, SEM).

### Producto

- [ ] Actualizar demo script y notebook.
- [ ] Budget compartido entre preguntas del mismo caso.

---

## Futuro

### Horizonte siguiente del core

- [ ] MechanismSpec, mechanism library, composicion mechanism-first.
- [ ] Rival mechanisms como hipotesis competidoras.
- [ ] Approximate inference teacher para mundos grandes.
- [ ] Curriculum sobre complejidad.
- [ ] Semantic mode configurable (full/abstract/fictional).
- [ ] **Research actions rediseniadas desde cero.** Las viejas (observe X
  cuesta 2, intervene Y cuesta 3) estan muertas — eran un juego artificial.
  Las nuevas deben ser interacciones ricas con el entorno: disenar
  experimentos, pedir campanas de datos, proponer intervenciones y ver
  resultados, consultar expertos simulados. Son la interfaz del entorno
  (como step() en Gym), NO herramientas internas del solver.
  IMPORTANTE: el solver ya investiga con python_exec (analisis, subgrupos,
  sensibilidad, etc). Eso es asunto del solver, no del entorno.

### Integraciones no-core

- [ ] Agent harness mas rico para policies externas.
- [ ] Reward design extendido para training real.
- [ ] Training pipeline completo sobre SregEnv.
- [ ] Transfer experiment falsificable.

---

## Hitos completados

- [x] v0+v1: contratos base, world generation, teacher solver, orchestrator,
  semantic layer y pipeline E2E.
- [x] Superficie v2 base: DAGSpec, mundos custom, 9 eval types y rich action
  infrastructure.
- [x] Solver diagnostico con python_exec, think, submit y reportes completos.
- [x] Paper-seeded SRCs + Inspiration Report v1.
- [x] Benchmarks externos integrados y backend de inferencia unificado.
- [x] Prompt reescrito: preguntas causales primarias, infer_target
  complementario, seed-first design. Inspiration Report v2.
- [x] Migracion BN → SCM completa: engine, solver, tasks, pipeline wiring,
  world gen, orchestrator wiring. 1494 tests. Branch `feature/scm-engine`
  mergeada a `main` (2026-03-25).
- [x] I10 preguntas reales: brief visible, naturalizar templates, override
  por hints, sanitizar snake_case, catalogo plano, two-stage process.
- [x] I11 Fase 2: primera evaluacion cualitativa formal. 3 SRCs, rubrica
  completa, 6 problemas nuevos documentados. Score promedio 1.3/2.0.

Detalle historico en `CHANGELOG.md`.

---

## Roadmap — como seguimos

### Paso 1: No-data baseline probe (diagnostico)

Darle briefings sin datos a un LLM y medir si acierta. Cuantifica P5
(direccion causal obvia desde priors). Directo en main, no necesita branch.

- [ ] Correr probe en los 3 SRCs de eval (football, coral, asthma)
- [ ] Documentar resultados

### Paso 2: Substrate minimum viable gate (solo blockers)

Solo lo que contamina el experimento de Open Investigation. Si los mundos
no tienen hallazgos interesantes, no podemos saber si el translator falla
o si el mundo es pobre. Consenso Claude + Codex: no hacer fase larga de
fixes ni ir directo a ciegas — solo limpiar lo que arruina la senal.

- [x] **Manipulabilidad**: solo ancestros causales del target como levers
  en best_intervention y compare_interventions. Helper `_manipulable_nodes()`.
- [x] **Interaction gate**: busca el mejor par con interaccion real entre
  todos los ancestros. Si no hay, devuelve "no" con el par mas plausible
  (mezcla yes/no natural, sin bias). Reviewed by Codex: strongest-yes fix.
- [x] **Mediation gate**: prueba multiples treatments y mediadores. Solo
  acepta fraccion parcial (0.05-0.95). Reviewed by Codex: multi-treatment fix.

**NO hacer todavia** (no contamina el experimento Alpha):
- Rework de descripcion narrativa de datos
- Campana de "ecuaciones mas ricas" en el generador
- Cosmetica Guided, multi-atom deliverables, variar panel config

### Paso 3: Open Investigation Alpha — First Compile

Primera prueba E2E del pipeline de verificacion abierta. **No necesita
generador perfecto — necesita mundos donde haya algo real para compilar.**

Usar **2-3 mundos curados a mano** (no el generador automatico):
- Uno con interaccion real
- Uno con mediacion parcial
- Uno con confounding interesante

**Que se prueba:**
1. Solver recibe SOLO el brief, entrega claim cards semi-estructuradas
2. LLM compiler compila cards a specs ejecutables (gramatica composable)
3. SCM verifier ejecuta specs y computa reward

**Sub-pasos (ver A15 para detalle):**
- [ ] Formalizar gramatica composable como DSL ejecutable
- [ ] Prototype truth map (enumerar verdades del SCM, clusterar en familias)
- [ ] Claim card contract (Pydantic models)
- [ ] Compiler benchmark offline (200+ claims, >90% precision)
- [ ] Verifier scoring sin compiler (validar correctness + coverage)
- [x] Piloto scaffolded E2E (solver + compiler + scoring) — 6 runs done

**Criterio de exito:** al menos 1 SRC donde el pipeline completo produce
un score significativo (no necesariamente bueno — que funcione E2E).
Compiler precision >90% en benchmark offline.

### Paso 4: Mejorar generador (despues de Alpha)

Recien despues de validar el pipeline con mundos curados, mejorar el
generador para que produzca mundos ricos automaticamente:
- Ecuaciones con interacciones, umbrales, saturaciones
- Variar panel config por SRC
- Descripcion narrativa de datos

**Referencia:** `research/synthesis/open_investigation_vision.md`

---

## Inbox — ideas sueltas

> Espacio libre para anotar cosas que se me ocurren. Se procesan en sesion
> y se mueven a la seccion que corresponda (analisis, implementacion, etc).

- Repasar evaluaciones y validaciones que se hicieron y quedaron sin uso
  (QualitySuite, diagnostics, baselines). → ver A6
- Teoria inventada como literatura visible (papers ficticios derivados
  parcialmente del mundo verdadero). → ver A4, I7
- Investigar Research Gym, SciGym, Kimi como referencia para tasks. → ver A5
- Preguntas vagas → entrenar plan de investigacion. → ver A5
- Critica: SREG solo data-driven? Necesita data + theory + literature. → ver A4
- SciDesignBench (arxiv 2603.12724): inverse design con simuladores.
  Nuestra BN puede hacer lo mismo. → ver I1 (inverse_design)
- CATALOGO EMERGENTE DE EVAL TYPES: en vez de un menu fijo de tipos, que el
  orchestrator genere preguntas libres desde el caso/paper e intente resolverlas
  contra el SCM en el momento. Si puede computar ground truth → la usa. Si no →
  busca en el catalogo algo cercano o la descarta. Si descubre una forma nueva de
  scoring → la agrega al catalogo. El catalogo crece organicamente con lo que los
  casos necesitan, en vez de ser un menu predefinido. Requiere un "query engine"
  generico sobre el SCM que evalue scorability de preguntas arbitrarias. Problemas:
  verificacion de scorability, mantener reward exacto (sin LLM-judge), bootstrap
  (el catalogo actual seria el seed), complejidad del meta-loop. Direccion correcta
  a largo plazo pero requiere avance arquitectural. → Conecta con A2, I1, I9.
  **UPDATE 2026-03-25:** esta idea evoluciono a la vision de Open Investigation
  (A15) donde el SOLVER (no solo el orchestrator) tambien descubre que preguntar.
  El catalogo emergente aplica a ambos lados.
- DISTINCION CRITICA: research actions (FUTURO) = interacciones con el
  ENTORNO. Analisis del solver (AHORA) = python_exec, asunto del solver.
- Ejemplo real (surfactantes/petroleo): seleccion basada en teoria +
  tablas, prueba rapida de efectividad, despues 200-500 ensayos iterativos
  de estabilidad con ajustes finos. → esto es un patron de investigacion
  industrial que SREG deberia poder representar. Conecta con A5 (taxonomia
  de investigaciones) e inverse_design iterativo.
- Taxonomia de investigaciones: no tenemos claro los TIPOS de investigacion
  que existen y que dimensiones tienen. Necesitamos eso para disenar las
  research tasks. → ver A5, research/
- Ver no solo cualquier paper promedio sino TIPO DE INVESTIGACIONES CLAVES QUE HAN SIDO IMPORTANTES… y tipos (anatomía y forma) de investigaciones que pueden llevar a cosas importantes en el futuro. Penémoslo… por ej hoy en día cuáles que sería clave descubrir? Independientemente del cómo… cuáles son las preguntas de investigación CLAVES para áreas que tendrían impacto realmente? O no es tan así y no es que una investigación hace algo increíble sino que son acumulados chicos?
- CLAVE (incluye lo de tipo de investigaciones, taxonomia, preguntas, etc) ---> QUE SIGNIFICA HACER CIENCIA, QUE ES HACER CIENCIA, COMO SE ESTA HACIENDO CIENCIA ULTIMAMENTE? (moderna). COMO SE HACE CIENCIA ULTIMAMENTE? QUE SIGNIFICA? los descubrimientos cientificos modernos y avances como son? son encontrar cosas causales? son cosas computacionales? es construir herramientas mas que inferir estadisticamente algo? cuales son los approaches? como ha ido cambiando y ahora como funciona? para tener IMPACTO realmente. Como son los ultimos avances en biologia, tipo para el cancer, drogas, quimica, materiales, superconductores o cosas asi. Todo el tipo de ciencia mas avanzada actual... se sigue haciendo descubriendo causas como lo suponemos? o armando sistemas? ha habido un cambio y ya no tenemos mas la ciencia clasica y ahora tenemos ciencia moderna computacional? como dice Wolfram, a new kind of science? sigue siendo util descubrir causas como lo estamos planteando? hay una lucha de approaches computational-based vs human-based? expandir en esto para entender como se hace ciencia hoy en dia.