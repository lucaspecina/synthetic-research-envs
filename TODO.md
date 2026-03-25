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

No tenemos claro los TIPOS de investigacion que existen, que dimensiones
tienen, y que tasks/preguntas se derivan de cada uno. Sin eso, no podemos
disenar bien las research tasks ni ampliar lo que el sistema puede hacer.

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

### A8. Representacion del mundo — BN vs ecuaciones vs simulacion

**La pregunta de fondo:** es la BN el formalismo correcto para el mundo
subyacente de SREG, o se podria usar algo mas expresivo?

Hoy SREG usa CPD tables discretas (3 estados por variable). Esto causa:

**Problema 1: Realismo.** Variables como `recovery_quality: [poor, adequate,
excellent]` cuando un investigador mediria VO2max=52.3 mL/kg/min. El solver
hace crosstabs en vez de regresion/correlacion.

**Problema 2: Escalabilidad.** CPD tables crecen 3^N con N padres.
MAX_PARENTS=5 es un bottleneck para dominios complejos. Football necesitaba
6 padres y fallo 8/10 iteraciones.

**Problema 3: Expresividad.** Las relaciones reales no son tablas de
probabilidades — son ecuaciones con umbrales, saturaciones, interacciones,
efectos no lineales.

#### Que nos da la BN (lo que NO se puede perder)

1. **Grafo causal** → d-separation, identifiability, do-calculus. Es lo que
   hace posible should_condition, adjustment_set, y reward verificable.
2. **Reward sin LLM judge** → el diferenciador de SREG. La verdad formal
   permite scoring exacto/preciso.

Lo que la BN aporta es el GRAFO + la capacidad de computar reward. Las CPDs
son solo UNA forma de parametrizar las relaciones. No son sagradas.

#### Opciones evaluadas

| Representacion | Continuas | Relaciones | Reward | Escala | Complejidad |
|---|---|---|---|---|---|
| **CPD tables** (actual) | No | Tablas | Exacto (analitico) | No (3^N) | Ya hecho |
| **Linear Gaussian BN** | Si | Lineales | Exacto (analitico) | Si | Media |
| **CLG mixto** | Mix | Lineales condicionadas | Exacto | Si | Alta |
| **SEM no lineal** | Si | Ecuaciones arbitrarias | Monte Carlo (~exacto) | Si | Media-alta |
| **Simulacion libre** | Si | Cualquier regla | Monte Carlo (~exacto) | Si | Variable |

#### La pregunta clave: exacto vs estadisticamente preciso

Un Linear Gaussian BN da P(Y|do(X)) como formula cerrada (reward=0.000 de
error). Un SEM no lineal requiere Monte Carlo: simular 100K muestras de
do(X=x), estimar la distribucion, calcular KL. El error es ~0.001 con
suficientes muestras.

**Para RL, la diferencia probablemente no importa.** El ruido de Monte Carlo
con N grande es menor que el ruido del propio proceso de entrenamiento.

Si Monte Carlo es aceptable, el espacio de diseno se abre enormemente:
ecuaciones con sigmoid, umbrales, interacciones, saturacion. Los datos
serian mucho mas realistas y el solver tendria que hacer analisis estadistico
real (regresion, correlacion, scatterplots) en vez de crosstabs.

#### Sub-preguntas por investigar

- [x] Prototipar Linear Gaussian BN en pgmpy → funciona. Ver
  `research/notes/gaussian_bn_prototype_findings.md`
- [ ] Prototipar SEM no lineal: ecuaciones arbitrarias + Monte Carlo para
  do-calculus. Verificar precision del reward con N=10K, 50K, 100K.
- [ ] CLG mixto: nodos discretos (posicion, tipo) + continuos (temperatura,
  VO2max). Inferencia mixta.
- [ ] Que tan preciso necesita ser el reward para RL? Hay literatura sobre
  tolerancia a ruido en reward signals?
- [ ] Scoring para distribuciones continuas: KL Gaussianas (analitico),
  KL por histograma, Wasserstein, CRPS?
- [ ] Si vamos a SEM no lineal, como genera el orchestrator las ecuaciones?
  Las pide al LLM? Las parametriza?
- [ ] Que eval types nuevos habilita (regresion, correlacion, intervalos,
  prediccion fuera de muestra)?

#### Decision pendiente

Lo que hay que decidir no es "Gaussian vs discreto" sino algo mas
fundamental: **el mundo subyacente se define por CPDs, por ecuaciones,
o por simulacion?** Las tres mantienen el grafo causal y la capacidad de
computar reward. La diferencia es expresividad vs simplicidad.

**Referencia:** `research/notes/gaussian_bn_prototype_findings.md`

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

### A12. Scores enganiosos por coincidencia estadistica (legacy BN)

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
- [x] Subir `MAX_PARENTS` de 4 a 5 en `dag_spec.py` (CPDs: 3^5=243, manejable).
- [x] Subir `max_iterations` del orchestrator de 10 a 15.
- [ ] Evaluar si es suficiente o necesitamos la migracion a Gaussian (ver A8).

**Bug verdict: logica invertida para choice types.**
El verdict (GOOD/OK/POOR) usaba `< 0.1 = GOOD` para TODOS los tipos, pero
choice types (should_condition, hypothesis, compare, best_intervention, NBO,
adjustment_set) retornan 1.0 = correcto, 0.0 = incorrecto. Resultado:
toda respuesta INCORRECTA se reportaba como "GOOD".
**Fix aplicado:** generate_src.py y solve_existing.py ahora detectan el tipo
y usan `> 0.9 = GOOD` para choice types vs `< 0.1 = GOOD` para KL types.

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
- [ ] Entity check para `compare_interventions` solo verifica `option_a` y
  `option_b` (nodos) pero no `label_a`/`label_b`/`outcome`. Podria aceptar
  preguntas con direccion o outcome equivocados.
- [ ] `desired_state` en el schema de `compare_interventions` es residuo BN.
  El generador SCM no lo usa pero el prompt del orchestrator lo sigue
  pidiendo, empujando framing "maximize state high".
- [ ] `should_condition` en SCM todavia tiene formato "Answer yes or no".
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

**Fase 3: preguntas desde la investigacion, no desde el menu** ← SIGUIENTE
Los 3 SRCs de P2 (football, coral, smoking) comparten EXACTAMENTE el mismo
patron: causal_effect + best_intervention + interaction + mediation +
infer_latent_cause. Tenemos 11 eval types usables pero el orchestrator
siempre elige los mismos 5. El prompt los presenta como menu y el LLM
gravita a los "flashy causales". Esto es H8 (eval_ontology_leak): las
preguntas nacen del menu de tipos, no de lo que un investigador preguntaria.

**Evidencia:** 3 SRCs post-P2 (2026-03-24). Los 3 tienen el mismo patron.
Smoking es el mejor (8.5/10 Codex) porque las preguntas del orchestrator
son mas naturales, pero el patron subyacente es identico.

Sub-tareas:
- [ ] El orchestrator deberia pensar primero "que preguntaria un investigador
  sobre ESTE caso" y DESPUES mapear a eval types disponibles
- [ ] Si no hay eval type que represente una pregunta natural, NO forzarla
- [ ] Permitir que un deliverable mapee a multiples scoring atoms
- [ ] Diversificar: should_condition, adjustment_set, ate, hypothesis_selection,
  infer_target, compare_interventions aparecen poco o nunca. El prompt debe
  dejar de jerarquizar tipos como "primary" vs "complementary"
- [ ] "500 obs / 4 sites / 3 waves" repetido en todos — variar estructura
- [ ] "hidden factor best explains..." clonado — el template de infer_latent
  siempre produce la misma forma de pregunta

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

**Fase 2: primera evaluacion formal** ← SIGUIENTE
- [ ] Generar 3-5 SRCs con seeds diversos (football, oil&gas, ecology, health)
- [ ] Aplicar rubrica completa: 7D + 6CF + descubrimiento abierto
- [ ] Correr no-data baseline probe (manual: brief sin dataset a LLM)
- [ ] Registrar resultados en formato estructurado
- [ ] Analizar: donde estamos bien, donde mal, que problemas nuevos aparecen

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

El orchestrator a veces elige mal entre los eval types existentes.
Necesita mejores descripciones y ejemplos de cuando usar cada uno.

- [ ] Agregar ejemplos concretos de papers para cada eval type.
- [ ] Instruir que si no hay tipo adecuado, lo diga en vez de forzar.
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

Detalle historico en `CHANGELOG.md`.

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