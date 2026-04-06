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

### A3b. De data analysis flat a investigacion secuencial (FUNDAMENTAL)

SREG hoy es flat: el solver recibe todo, analiza, submittea. Aunque tenga
turnos y budget, si se resuelve con "cargo CSV, corro 3 analisis, listo",
sigue siendo flat. La investigacion real es long-horizon porque **la
informacion esta en capas y cada capa revela que hacer en la siguiente**.

El salto: convertir el caso de un paquete estatico a un entorno con
informacion gated. El solver empieza con poco (brief + dataset parcial +
catalogo de acciones), y cada accion (query al SCM) cuesta budget y
devuelve datos nuevos. Dead ends y honey traps son parte del diseno.

Esto crea presion evolutiva directa para las propiedades mas dificiles de
forzar: workflow iterativo, plan dinamico, descomposicion de preguntas,
saber cuando parar.

**Referencia:** `PROJECT.md` Horizonte 2 (seccion completa).
**Dependencias:** requiere research actions como interfaz, estructura de
revelacion en el orchestrator, budget como recurso del caso.
**Status:** [ ] Vision documentada, no implementada.

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

### A21. Evaluation harness no reconoce findings correctos — RESUELTO

**Status: RESUELTO y validado E2E (2026-03-29).**

**Root cause:** A21 era un bug de ontologia, no de prompting. El campo
`pattern` cargaba forma estructural + estatus epistemologico + routing
de scoring. Solucion: compatibility algebra que da credito parcial
(obs_association vs causal_effect = 0.65 en vez de 0.00).

**E2E validacion:**
- Coral: obs claims puntuan 0.65 (antes 0.00). SQ Total: 0.552.
- Soil: expuso A22 (ver abajo).

**Implementacion:** `oi_subquestions.py` (algebra), `oi_compiler.py` (v1 migrado).
**Research:** `research/notes/a21_compiler_ontology_investigation.md`
**Codex threads:** 019d3aec, 019d3b67

### A22. Compiler abstention rate + patterns fijos — DONE (multi-unit)

**Descubierto durante E2E de A21 (2026-03-29). Resuelto con multi-unit compiler.**

El compiler rechazaba claims complejos porque `ClaimIntent` tenia UN solo
treatment y UN solo outcome. Solucion: `compile_claim()` extrae N intents
por claim, crea un `CompiledUnit` por intent. `CompilerOutput` tiene lista
de units con status `compiled`/`partial`/`abstention`.

**E2E validacion:** soil 0.200->0.980, coral 0.807, logistics +0.08.

**Paso 1 (DONE):** Multi-intent — un claim -> N ClaimIntents + CompiledUnits.
**Paso 2 (futuro):** Fallback a gramatica composable para tipos nuevos.
**Paso 3 (futuro):** Patterns organicos desde fallback.

**Siguiente bottleneck (S03):** calidad de extraccion LLM. Ver items abajo.

**Research:** `research/notes/a22_compiler_direct_to_atomicspec.md`
**Conecta con:** A21, scm_task_primitives, open_investigation_vision
**Codex thread:** 019d3b67-eb81-7201-9151-9aa26e54ac24

### S03. Compiler LLM extraction quality — BOTTLENECK (parcial)

**Descubierto durante S02 forensics de A22 (2026-03-29).**
**Actualizado con forensics v2 E2E (2026-04-02).**

Multi-unit resolvio abstention, pero la extraccion LLM sigue perdiendo
informacion de claims complejos.

**Forensics v2 (2026-04-02, 3 seeds, 12 claims):**
De 4 claims FALSE en 3 seeds v2, solo 1-2 son fallas del compiler:
- Confounding C4 ("no condicionar en mediadores"): claim metodologico que
  el compiler no puede mapear a ninguno de los 8 PatternClass → truth=0.
  El SQ que preguntaba esto (sq3) quedo con sat=0.36 porque la segunda
  mejor claim era tangencial.
- Social claim_3 (creation_ratio→wellbeing): posible falla compiler con
  relaciones no lineales (SCM usa thresholds `max(0, x-3.5)`).
Los otros 2 FALSE son errores del SOLVER (multicolinealidad, confundir
asociacion con mecanismo directo) — un compiler perfecto no los salva.

**Conclusion:** el compiler no es "el unico" bottleneck, pero SI es el que
NOSOTROS controlamos. Solver errors son presion evolutiva valida. Compiler
errors son bugs nuestros.

**Resolucion:** S03 se resuelve migrando claims al approach grammar-direct
de A23 (que ya funciona para SQs). Los items sueltos de abajo quedan
obsoletos con la migracion.

Items legacy (pre-A23):
- [ ] **Chain claim extraction**: "A causes B causes C" debe extraer TODAS
  las relaciones pairwise (A->B, B->C, A->C), no solo la cadena narrativa
- [ ] **Indirect/distal conclusion extraction**: conclusiones implicitas
  o distales se pierden en la extraccion
- [x] **effect_ranking matching** (S02): ranking_vars en ClaimRepr + role_compat
  special case. Ranking ya no muere por hard gate en treatment.
- [x] **Sign vs significance** (S02): prompt + exemplar. Slope -3.83 ya no se
  clasifica como near_zero por p > 0.05.
- [ ] **effect_ranking from prose**: extraer rankings de magnitud de efecto
  desde texto libre del solver (extraccion, no matching)

### A23. Compilacion directa a AtomicSpec — NEXT STEP

**Descubierto S02/S03, validado empiricamente S04 (2026-03-30).**
**Actualizado: forensics v2 E2E confirma necesidad (2026-04-02).**

**Hipotesis validada:** cuanto menos dependamos del catalogo fijo (PatternClass),
mejor preservamos la semantica de claims y SQs en casos diversos.

**Evidencia S04 (5 casos diversos, 18 claims):**
- Catalogo: 17/18 compilados, 28 units.
- Directo (LLM → AtomicSpec): 18/18 compilados, 65 specs validos, 50 TRUE.
- 2.3x mas verificaciones, 0 abstentions, mediciones mas ricas.
- Caveats: 77% TRUE (vs ~100% catalogo); prueba capacidad, no arquitectura final.

**Evidencia forensics v2 (2026-04-02):**
- Claims metodologicos (ej: "no condicionar en mediadores") no compilables
  con los 8 PatternClass fijos → truth=0 injustamente.
- SQ compiler (`oi_sq_compiler.py`) ya usa grammar-direct exitosamente.
- El claim compiler (`oi_compiler.py`) sigue en v1 con PatternClass.

**Direccion:** migrar claim compiler al mismo approach grammar-direct que el
SQ compiler. El catalogo PatternClass queda como fallback opcional.

**Spec de diseno:** `research/synthesis/sq_v2_matching_spec.md` (CANONICO).

**SQ compiler (DONE):**
- [x] **Modelo v2:** SubQuestionIntentV2 + VerificationSpec (required/support)
- [x] **Compile step:** `compile_sq_to_specs()` — LLM + grammar, sin pattern routing
- [x] **Matching:** `spec_match()` exacto en estimand + bipartite 1-a-1, pooled
- [x] **Primer test acotado:** 5 SQs diversas, 18 specs, 72% TRUE, 4 meas kinds
- [x] **Orchestrador v2:** genera SQs como texto libre, compila a specs (spike)
- [x] **Validacion semantica:** `validate_compilation_alignment()` — chequea
  causal→intervene, direccion, variables, confounding, mediation, identifiability
- [x] **Answer key:** verify_atom en compile step funciona. El answer key es el resultado rico del SCM, no una Assertion simplificada.
- [x] **E2E real:** generar caso completo, correr solver, scoring v2
- [x] **Integracion:** si funciona, reemplazar v1 en el pipeline del orchestrador

**Claim compiler (NEXT — migrar a grammar-direct):**
- [ ] **Compile function:** `compile_claim_to_specs(claim_text, summary, llm_call)`
  usando misma GRAMMAR_REF que `oi_sq_compiler.py`
- [ ] **Integrar en runner:** reemplazar `compile_claim()` v1 en `_score_with_judge()`
- [ ] **Fallback:** si grammar-direct falla, intentar v1 PatternClass como backup
- [ ] **Validar E2E:** re-correr 3 seeds v2 con nuevo compiler, comparar truths

**Pendientes generales:**
- [ ] **Comparacion v1 vs v2:** mismos episodios, comparar scores y cobertura
- [ ] **Calibracion del directo:** reducir specs FALSE (prompting, ejemplos)

**Research:** `research/notes/s04_epistemic_ir_gap_analysis.md`,
`research/notes/a23_grammar_first_sq_and_compiler.md`,
`research/synthesis/sq_v2_matching_spec.md`
**Conecta con:** A22, S02, S03, S04, S05, open_investigation_vision

### A24. Runtime comun de validacion — DISCUSION ABIERTA

**No reemplaza A23 como siguiente paso inmediato.**

Pregunta de fondo: si el proyecto exige **un solo metodo general de scoring**
para todo tipo de investigacion, `AtomicSpec` es el target final o solo la
primera familia fuerte de validadores?

Direccion exploratoria:
- [ ] Clarificar que la taxonomia sirve para coverage audit y seed design, NO
  para scoring profiles ni bifurcacion del reward
- [ ] Disenar un concepto de `validator program` restringido/auditable sobre un
  runtime comun, sin caer en codigo arbitrario
- [ ] Mapear como `AtomicSpec` encaja como subconjunto de ese runtime comun
- [ ] Evaluar si casos de prediccion/optimizacion se pueden expresar como
  validators generales sin introducir scorers separados por tipo
- [ ] Mantener A23 como prioridad corta: no saltar a esto sin antes explotar
  bien la compilacion directa a atoms

**Research:** `research/notes/a24_general_validator_runtime.md`
**Conecta con:** PROJECT invariants, CLAUDE scoring principles, A23, S04

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
- [x] Validate hard submit guard in E2E rerun (S02: 2/3 cases fixed)
- [x] Force-submit fallback (S02): turno extra con SOLO submit_claims disponible
- [ ] Consider continuous claim drafting (draft_claim tool, finalize at end)

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

## Limpieza — eliminar legacy que no aporta

### A26. Scoring de relevancia — claim vs SQ

**Status: RESUELTO y validado E2E (2026-04-01).**

El scoring de claims tiene dos componentes:
- **Verdad:** claim → AtomicSpec → verify contra SCM (determinístico, funciona)
- **Relevancia:** esta claim responde a alguna SQ del brief?

**Implementación (Híbrida):**
- LLM juez de relevancia (`oi_relevance_judge.py`) que toma el claim_text + specs_summary y lo compara contra el SQ text + answer_key rico.
- Pre-filtro determinístico por solapamiento de variables para ahorrar llamadas al LLM.
- Score final: verdad × relevancia × tier.

**Pendiente futuro:**
- [ ] Evaluar si features determinísticas alcanzan para reemplazar LLM en RL.

### A27. Answer key rico — el SCM result como verdad, no Assertion

**Status: RESUELTO y validado E2E (2026-04-01).**

El answer key no es una Assertion simplificada sino el resultado completo del SCM (`AtomVerdict.detail`). La Assertion del compiler sigue siendo útil como "hipótesis del LLM", pero no como verdad.

**Implementación:**
- `ground_sq_answer_key` guarda el resultado rico sin intentar reparar Assertions.
- `render_answer_key()` normaliza `verdict.detail` a una vista consumible para el LLM juez de relevancia.
- `oi_sq_matching.py` ya no usa `sq_verdict.solver_assertion_holds` como gate de validez del teacher.

**Pendiente:**
- [ ] **Desacoplar matching de la Assertion del teacher:** `assertion_compat()` todavía compara la Assertion de la SQ con la del claim. El matching completo debe migrar a comparar claim result vs answer key rico.
- [ ] **Separar resolve/assert en verify_atom:** separar a `resolve(spec)` + `assert_(resolution, assertion)`.
- [ ] **Rankings por composicion:** SQs de ranking deben compilar a N specs atomicos (uno por variable/entidad).

**Conecta con:** A23, A24, A26, scoring_relevance_design.md

### A25. Metricas custom para prediccion y optimizacion

Hoy SREG evalua con AtomicSpecs (DSL composable contra el SCM). Pero para
prediccion y optimizacion, no deberiamos necesitar inventar nada nuevo — solo
una metrica custom ejecutable:

**La idea:** el caso define UNA metrica puntual (ej: MSE, AUC, rendimiento
quimico) + un dataset latente (holdout no visible al solver). El solver
entrega un modelo/prediccion/configuracion. El sistema ejecuta la metrica
contra el holdout y eso es el score.

**Variantes:**
- **Prediccion:** solver recibe dataset sin target, sistema tiene target oculto,
  se mide MSE/AUC/etc contra holdout
- **Optimizacion:** solver propone configuracion de variables, sistema evalua
  contra funcion objetivo oculta (el SCM mismo)
- **Hibrido:** el caso tiene SQs de entendimiento + metrica de performance

**Preguntas abiertas:**
- [ ] Cuanta infra nueva necesita? (dataset holdout, metrica runner, etc.)
- [ ] Se puede expresar como un tipo especial de AtomicSpec o es algo aparte?
- [ ] Como convive con SQs? (un caso puede tener SQs + metrica custom?)
- [ ] Es compatible con el principio "un solo metodo de scoring"?

**Esto NO requiere la infra de H1/H2 del PROJECT.md.** Es mas simple: una
funcion que toma output del solver y devuelve un numero. El SCM ya puede
generar holdouts y evaluar.

**Pensar despues de cerrar SQ v2 + limpieza.**

### A28. Audit E2E 2026-04-06 — Taxonomia de failure modes del scoring

**Status: DIAGNOSTICADO.** Batch de 12 seeds diversas (BUG 8+9 fix).
Average 0.443, 11/12 exitosos. Audit profundo de todos los casos revelo
4 failure modes + 1 transversal.

**Taxonomia de failure modes:**

1. **Grammar/representation gap** — el sistema no puede expresar la claim
   en la IR actual. El solver hace buena ciencia y es penalizado.
   - Caso: `poverty` (0.003). Solver hizo RDD con bandwidths, 4/5 claims
     en abstention porque QueryArm no soporta rangos/ventanas.
   - Viola presion evolutiva: claims sofisticadas → abstention, simples → ok.

2. **Scorer credit-assignment** — el scoring asigna credito mal aunque
   las piezas (claim, spec, verificacion) funcionen correctamente.
   - Caso: `microbiome` (0.196). Claims correctas segun SCM, pero C3
     (generica) gano 4/5 SQs sobre C1 (especifica y correcta para SQ1).
   - Causa: truth se calcula a nivel claim (promedio de todos sus specs).
     Una claim ambiciosa con specs mixtos pierde contra una generica.
   - Agravante: `matched = best_score > 0` infla coverage artificialmente.

3. **SQ decomposition/overlap** — SQs comparten demasiada semantica,
   dificultando la asignacion correcta. Factor secundario en microbiome.

4. **Solver miss / wrong science** — el solver concluye mal o no
   investiga la variable clave. Scoring justo.
   - `policy_equity` (0.142): solver testo interaccion equivocada
     (tax × poverty_rate en vez de tax × price_sensitivity).
   - `coral_bleach` (0.380): solver no detecto confounding latente
     (thermal_tolerance). Correlaciones espurias reportadas como causales.
   - `competing_mech` (0.363): un claim confunde correlacion con
     confounding causal (sq5 = 0.056).

5. *(transversal)* **Experimental-control drift** — comparar batches
   regenerados no aisla efecto de cambios de codigo vs varianza del
   worldgen/solver. Necesitamos rescore controlado sobre casos congelados.

**Resultados del batch completo:**

| Caso | Score | Failure mode |
|------|-------|-------------|
| missing_data | 0.786 | (ninguno — BUG 8 fix confirmado) |
| selection_bias | 0.719 | (ninguno) |
| identifiability | 0.679 | (ninguno) |
| heterogeneity | 0.632 | (ninguno) |
| chemical | 0.551 | (ninguno) |
| confounding | 0.422 | solver miss parcial (delay mediator) |
| coral_bleach | 0.380 | solver miss (latente no detectada) |
| competing_mech | 0.363 | solver miss (causal framing error) |
| microbiome | 0.196 | credit-assignment (truth dilution) |
| policy_equity | 0.142 | solver miss (interaccion equivocada) |
| poverty | 0.003 | grammar gap (RDD inexpresable) |
| vaca_predict | FAIL | tipo predictivo no implementado (A25) |

**Datos:** `results/e2e_batch_bug8_9_fix/`
**Conecta con:** A23 (compiler), A26 (relevancia), A25 (prediccion)

### L0. Reescribir CURRENT_STATE.md — post cambios

Cuando terminemos los cambios actuales (SQ v2 integrado, limpieza legacy),
reescribir CURRENT_STATE para que:
- Sea un walkthrough narrado del E2E, no secciones tecnicas sueltas
- Explique cada paso con ejemplos concretos (no solo nombres de clases)
- Critique abstracciones innecesarias (ClaimCard, WorldSummary, etc.)
- Menos nombres tecnicos, mas "que pasa y por que"
- La tabla de 15 tipos de investigacion se mantiene
- Las explicaciones de SQ, claims, scoring van dentro del flow, no aparte

**Hacer DESPUES de terminar L1 + integracion SQ v2. No antes.**

### L1. Eliminar warrant system y OI helpers instrumentadas — DONE (2026-04-01)

**Completado.** Se eliminaron:
- [x] `src/sreg/tools/oi_helpers.py` — helpers instrumentadas completas
- [x] `src/sreg/tools/oi_warrant.py` — sistema de warrant completo
- [x] `WarrantResult` y campos de warrant en `EpisodeScore`
- [x] `AnalysisRecord` y metodos relacionados en `EpisodeTrace`
- [x] Referencias a `oi_helpers` en `oi_runner.py` (namespace, proxy)
- [x] Tests de warrant en `test_oi_compiler.py`, `test_oi_runner.py`, `test_oi_driver.py`
- [x] Warrant logic en `oi_compiler.py` y `oi_verifier.py`

El solver usa pandas/numpy directamente. 93 tests pasan.

---

## Implementacion y experimentos

Cosas que sabemos que queremos hacer o probar. Cada una referencia el
analisis que la motiva.

### I0b. Fixes criticos encontrados en sesion 2026-04-01

**E2E v1+v2 validado (2026-04-02):** 5 curated worlds (v1) + 3 seeds
(microbiome, confounding, social_media — v2 con juez LLM). 0 crashes.
Coverage v2 (0.65-0.79) >> v1 (0.11-0.25). Correctness discrimina:
social_media 0.500, education 0.625, microbiome/confounding 0.750.
Vaca_muerta falla por JSON truncado en orchestrator (bug pre-existente).

**BUG 1 — auto-adjust multi-confounder (FIXED):**
`_run_adjustment()` estratificaba confounders uno por uno (marginal) en vez
de ajustar conjuntamente. Ademas, el verifier estimaba desde datos
observacionales cuando tiene acceso al SCM. Fix: validar backdoor set +
usar `do()` para verdad exacta. `_is_valid_backdoor_set()` agregado.

**BUG 2 — coverage threshold demasiado bajo:** `required_fraction=0.5`
aprueba investigaciones que ignoran la mitad de las SQs. Deberia ser 0.7+.

**BUG 3 — required vs support SQs:** todas las SQs pesan igual. Un claim
que responde una SQ de soporte pero ignora la principal deberia penalizarse.

**BUG 4 — spam penalty debil:** `max_claims=5` pero el penalty por exceso
es suave. Un solver puede submitir 5 claims vagos y cubrir todo.

**BUG 5 — evidence_basis no se valida (FIXED):** el campo `evidence_basis`
del claim card ahora se valida contra `trace.accessed_artifact_ids()`.
Citar artifacts no accedidos = truth 0. `save_artifact` registra en trace.

**BUG 6 — conjunctive truth (FIXED — proportional truth):** la verdad
all-or-nothing mataba claims con muchos specs (ej: 8 specs, si 1 falla = 0.0).
Cambiado a truth proporcional: M/N (fraccion de specs que pasan).
Corregido en 3 lugares: `_score_with_judge` (v2), `_score_with_subquestions` (v1),
y `score_compiled_episode_v2` (salience path). Ej: claim con 6/8 specs = truth 0.75.

**BUG 7 — orchestrator json.loads crash (FIXED):** `orchestrator.py:262`
no tenia try/except en `json.loads(tc.arguments)`. Seeds grandes (19+ vars)
pueden generar payloads truncados que crashean el batch entero.
Fix: try/except retorna error al LLM para que reintente.

**FORENSICS v2 (2026-04-02, 3 seeds):**

Analisis claim-por-claim de microbiome, confounding, social_media:

| Seed | Claims | TRUE | FALSE | Correctness | Causa FALSE |
|------|--------|------|-------|-------------|-------------|
| microbiome | 4 | 3 | 1 | 0.750 | c2: solver confunde multicolinealidad con no-efecto |
| confounding | 4 | 3 | 1 | 0.750 | C4: compiler no puede compilar claim metodologico |
| social_media | 4 | 2 | 2 | 0.500 | claim_3: compiler/nonlinear; claim_4: solver confunde asoc→mecanismo |

**Patrones identificados:**
1. **Solver: multicolinealidad → "no effect"** — OLS con variables colineales
   anula coeficientes reales. Presion evolutiva valida, NO corregir.
2. **Compiler: claims metodologicos/epistemologicos** — "no condicionar en X"
   no cabe en 8 PatternClass. Resolver con A23 grammar-direct.
3. **Solver: asociacion ≠ mecanismo** — reporta "X→Y" observacional como
   si fuera arco directo. Presion evolutiva valida, NO corregir.
4. **Correctness es el bottleneck, no coverage** — coverage=1.0 en los 3 seeds.
5. **Brief→SQ alignment es correcto:** briefs vagos, SQs descubribles desde
   datos, presion evolutiva funciona. NO tocar briefs ni SQs.

**Decision:** migrar claim compiler a grammar-direct (A23). Correr mas E2E
para validar con datos reales. Solver errors son presion, no bugs.

### I0d. Scoring pipeline improvements — motivado por A28

**Audit E2E 2026-04-06 revelo 3 mejoras necesarias en el scoring.**

**Secuencia decidida (2026-04-06, consenso Claude+Codex):**
P0 → P1 → P2 → A3b. Razon: no apilar complejidad sobre incentivos rotos.
P0 es prerequisito epistemologico (sin el, no podemos medir efecto de
cambios). P1 es techo arquitectonico (expande lo que cuenta como
investigacion). P2 calibra el reward. A3b (Sherlock-type) va DESPUES
de que el reward sea confiable.

**>>> NEXT: P1 <<<**

**P0. Rescore controlado sobre casos congelados — DONE (2026-04-06)**

Implementado `scripts/rescore.py` con 3 modos: `--reaggregate` (solo
aritmetica, sin LLM), `--rejudge` (re-corre juez de relevancia),
`--recompile` (full re-compile + verify + judge). Persistencia de scoring
internals en `oi_result.json` via `score_inputs_v2`. SQs v2 grounded
persistidas en `src.json` via `sub_questions_v2`. Skill `/rescore`.

- [x] Script de rescore que toma `src.json` + `oi_result.json` y re-ejecuta
  solo compiler + verifier + scorer. Sin LLM solver, sin worldgen.
- [x] Validar que produce scores identicos al original (determinismo check).
- [x] Poder cambiar scorer params y re-evaluar (para comparar cambios).

**P1. Predicados de subpoblacion en QueryArm — grammar gap**

`QueryArm.condition_on` solo acepta valores puntuales (float/int con ±15%
desvio). Claims quasi-experimentales (RDD, subgrupos, ventanas temporales)
no pueden expresarse. poverty (0.003) es el caso emblematico: 4/5 claims
en abstention por usar bandwidths.

Diseñar predicados genericos, NO hotfixes para RDD:
- [ ] Extender `condition_on` para soportar predicados de rango,
  cuantiles, categorias, y ventanas temporales.
- [ ] Actualizar `_filter_condition` en `oi_verifier.py` para procesarlos.
- [ ] Actualizar GRAMMAR_REF para que el compiler sepa emitirlos.
- [ ] Agregar PatternClass o equivalente en grammar-direct para
  claims de local estimand / subpoblacion.
- [ ] Validar con poverty rescoreado — abstention debe bajar de 80% a <20%.

**P2. Credit-assignment: unit-level truth — scorer design**

El scoring actual calcula truth a nivel claim (promedio de todos los specs
de la claim). Esto penaliza claims ambiciosas con muchos specs donde algunos
fallan, favoreciendo claims genericas con pocos specs. microbiome (0.196) es
el caso emblematico: claims correctas pierden contra una claim generica.

Secuencia de cambios (uno a la vez):

- [ ] **Paso 1: Threshold para matched.** Hoy `best_score > 0` cuenta como
  matched, inflando coverage. Definir threshold minimo (ej: 0.15) para
  contar un SQ como genuinamente respondido.
- [ ] **Paso 2: Unit-level truth × relevance.** Cambiar la unidad de scoring
  de claim completa a CompiledUnit (ya existe en `oi_compiler.py:219`).
  Cada unit tiene sus propios specs y su propio truth score.
  **CUIDADO:** requiere representacion semantica por unit. Si se hereda
  claim_text entero, se mete credito fantasmal. Pensar como generar
  un resumen semantico por unit.
- [ ] **Paso 3 (solo si necesario): Penalizacion suave por reuso.**
  Si despues de paso 1+2 una claim generica sigue ganando N SQs
  injustamente, agregar marginal gain decreciente por reuso.
  NO hacer antes de paso 1+2 — puede castigar injustamente claims
  que genuinamente cubren multiples SQs.

**Conecta con:** A28 (taxonomia), A26 (relevancia), A23 (compiler)

### I0c. Batch E2E diverso — validacion con mas datos — DONE (2026-04-06)

**Completado.** 2 batches de 12 seeds diversas:
- `results/e2e_batch_proportional_truth/` — baseline (pre BUG 8+9 fix)
- `results/e2e_batch_bug8_9_fix/` — post fix

11/12 exitosos. Average 0.443 (mejora sobre baseline 0.401).
Audit profundo documentado en A28. Hallazgos derivaron en I0d.

- [x] Correr 10+ seeds diversas por el pipeline v2 completo
- [x] Seeds cubren: system mapping, descriptivo, epistemologico,
  heterogeneidad, confounding, causal simple, optimization, etc.
- [x] Reportar: per-claim truths, satisfaction distribution
- [x] Identificar patrones de falla → A28 taxonomia de failure modes

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

### Exclusiones de scope actual — horizontes de expansion

Estas NO son tareas pendientes. Son capacidades que el sistema hoy no
tiene por decision explicita de scope (`PROJECT.md` "Scope actual y
horizontes futuros"). Se listan aca para que cuando decidamos expandir,
el punto de partida este claro.

**H1. Ciencia que produce artefactos evaluables.**
El solver hoy entrega claims sobre el mundo. En el futuro podria
entregar predicciones (scored por AUC/RMSE), policies, disenos
experimentales u otros artefactos. Requiere validator programs mas
generales que AtomicSpec (ver A24). Referencia: `PROJECT.md` horizonte 1.

**H2. Interaccion rica con el entorno investigativo.**
Proponer experimentos, pedir campanas de datos, gestionar budget,
interactuar con colaboradores simulados, elegir instrumentos. Requiere
research actions como interfaz del entorno. Referencia: `PROJECT.md`
horizonte 2, item de research actions abajo.

**H3. Material teorico sintetico.**
Papers ficticios, hallazgos previos contradictorios, teorias rivales.
Requiere generacion de literatura sintetica. Referencia: `PROJECT.md`
horizonte 3, A4, I7.

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
