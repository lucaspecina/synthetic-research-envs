# SciGym — analisis y comparacion con SREG

> **Status:** Related work consolidado. Referencia obligada para paper / tesis.
> **Fecha:** 2026-04-07
> **Paper:** Duan, Lu, Harrigan et al. 2025, "Measuring Scientific
> Capabilities of Language Models with a Systems Biology Dry Lab",
> arXiv:2507.02083 (NeurIPS 2025).
> **Conecta con:** `external_benchmarks_transfer_analysis.md`,
> `sreg_training_transfer_protocol.md`, `thesis_evaluation_framework.md`,
> `related_work_sandmle.md`, `PROJECT.md`.

## Por que este paper importa para SREG

SciGym es el unico benchmark publico que mide **el ciclo iterativo
completo de investigacion** (proponer experimento -> observar -> actualizar
creencia -> refinar) con scoring determinista. En la dimension del loop
iterativo, **es lo mas cercano a lo que SREG aspira a entrenar**.

Esto importa por tres razones:

1. **Transfer benchmark canonico para nuestro paper.** Es el unico que
   puede medir si SREG efectivamente entrena el comportamiento
   Sherlock-type que `PROJECT.md` Horizonte 2 lista como objetivo
   central. Sin SciGym, la suite externa solo mide razonamiento causal
   estatico y generacion single-shot — y la claim de "SREG entrena
   juicio cientifico iterativo" se vuelve indefendible.
2. **Validacion externa parcial del approach.** SciGym demuestra que
   "synthetic env + iterative loop + programmatic ground truth" funciona
   como **benchmark** de investigacion. SREG aplica el mismo principio
   pero como **generador para training**. Su existencia valida el
   patron a nivel de diseno aunque no a nivel de proyecto.
3. **Riesgo conocido para la novelty del paper.** SciGym debilita la
   parte "loop iterativo + programmatic GT en ciencia" como contribucion
   conceptual de SREG. El paper de SREG tiene que articular con
   precision donde SREG va mas lejos.

## Resumen ejecutivo del paper

**Autores:** Haonan Duan, Stephen Zhewen Lu, Caitlin F. Harrigan, et al.
(University of Toronto, SickKids).

**Problema:** Como medimos las capacidades de descubrimiento cientifico
de los LLMs en sistemas complejos sin pagar el costo prohibitivo de
laboratorios humedos.

**Insight central:** Los modelos en SBML (Systems Biology Markup
Language) son **dry labs eficientes**. Permiten correr "experimentos"
biologicos en simulacion, dando ground truth perfecta y costo de
verificacion despreciable.

**Pipeline del benchmark:**

1. **Fuente de tareas:** 350 modelos SBML curados de BioModels
   (repositorio publico de modelos cientificos peer-reviewed). Filtran
   para excluir modelos con `rules` y `events` complejos.
2. **Splits:** small (137 modelos con < 10 reacciones cada uno) y
   large (213 modelos hasta 400 reacciones).
3. **Setup del agente:** recibe un SBML parcial con todas las especies
   y parametros pero **sin ninguna reaccion**. Tiene que recuperar las
   reacciones inferiendolas a partir de experimentos.
4. **Loop:** maximo de 20 iteraciones, mas 3 de debugging si el final
   submission es invalido.
5. **Acciones disponibles:**
   - Escribir y ejecutar codigo Python para analisis.
   - Hacer experimentos: cambiar la concentracion inicial de una
     especie a un valor designado.
   - Submitar el modelo final.
6. **Output:** un bloque de codigo que define el modelo final en una
   variable `final_sbml` usando `libSBML`.

**Scoring (3 metricas complementarias):**

- **Network Topology Score (NTS)** — F1 sobre interacciones entre
  especies (es una variante de graph edit distance).
- **Reaction Matching Score (RMS)** — dos reacciones se consideran
  "matched" si tienen los mismos sets de reactivos y productos.
  Variante mas estricta requiere matching de modificadores.
- **Simulation Trajectory Error (STE)** — SMAPE entre series temporales
  predichas y ground truth.

Todo determinista. No hay LLM-judge en el loop de scoring.

**Resultados principales (frontier models en SciGym-small):**

| Modelo | STE | RMS F1 |
|---|---|---|
| Gemini-2.5-Pro | 0.32 | 0.18 |
| Claude-3.7-Sonnet | 0.36 | 0.17 |
| GPT-4.1 | 0.46 | 0.17 |
| Gemini-2.5-Flash | 0.42 | 0.12 |
| GPT-4.1-mini | 0.60 | 0.13 |
| Claude-3.5-Haiku | 0.63 | 0.05 |

Observaciones:

- "Pro variants consistently outperform their mini counterparts."
- "Performance declined significantly as system complexity increased."
- **Frontier models obtienen RMS F1 < 0.20.** Hay headroom enorme.

**Limitaciones reportadas honestamente por los autores:**

1. **Simulation-to-reality gap:** los SBML no capturan toda la fisiologia
   real, son ODEs simplificadas.
2. **Ausencia de ruido:** las simulaciones no tienen ruido experimental;
   las series son densamente muestreadas.
3. **Cobertura incompleta de SBML:** filtran modelos con `rules` y
   `events` complejos.
4. **Overfitting:** los modelos propuestos por el agente tienden a
   ajustarse a las trayectorias observadas mas que a capturar la
   estructura biologica subyacente.

## Coincidencias estructurales con SREG

### El principio operativo es el mismo

| SciGym | SREG | Que comparten |
|---|---|---|
| **Modelo SBML oculto** (parametros + reacciones) | **SCM** (DAG + ecuaciones + ruido) | Verdad matematica oculta |
| **Simulacion deterministica** del SBML | **Sampler** del SCM | Datos derivados de la verdad |
| **Scoring vs ground truth** (NTS, RMS, STE) | **Scoring vs SCM** (truth + relevance + coverage) | Programmatic GT, no LLM-judge |
| **Loop iterativo** (proponer-observar-refinar) | **OI episode** con turnos | Investigacion como proceso, no Q&A |
| **Curado de fuente publica** (BioModels) | **Compiler con seeds de papers reales** | Anclaje en ciencia real |

Esto es exactamente el principio operativo que comparten SREG y
SandMLE: **la verdad matematica vive separada del envoltorio narrativo,
y se mantiene escondida del agente, que solo accede via experimentos
o queries**.

### Otras coincidencias relevantes

1. **Programmatic ground truth (NO LLM-judge en scoring core).** Mismo
   principio no-negociable que SREG. La verificacion es matematica.
2. **Diseno para investigacion, no para Q&A.** Los autores explicitan
   que "open-ended scientific discovery" es el objetivo, no respuestas
   cerradas.
3. **Curado de fuentes peer-reviewed.** SciGym usa BioModels, SREG usa
   seeds de papers. Mismo principio: anclar la verdad en ciencia real.
4. **Honestidad sobre limitaciones.** El paper de SciGym reconoce
   simulation-to-reality gap, ausencia de ruido, overfitting. SREG
   tiene limitaciones equivalentes que vale reconocer en el paper.

## Divergencias fundamentales (triple filtro de CLAUDE.md)

Aplicando los tres filtros que SREG usa para evaluar cualquier diseno:

### Filtro 1: ¿Se parece a investigacion real?

**SciGym: parcialmente.** El loop de "proponer experimento -> observar ->
inferir" se parece mucho a una sesion de laboratorio. Pero el agente
nunca **decide cual es la pregunta**. La pregunta esta dada: "recupera
las reacciones del modelo oculto". No hay descomposicion del problema,
no hay generacion de hipotesis rivales sobre que vale la pena estudiar,
no hay decision sobre cuando parar (esto ultimo lo controla el cap
externo de 20 iteraciones).

**SREG: si (por diseno).** El brief es libre. El solver decide que
investigar, descompone preguntas vagas, genera hipotesis, decide
cuando una conclusion esta bien fundada. La pregunta no esta dada.

### Filtro 2: ¿Crea presion evolutiva para juicio cientifico?

**SciGym: parcialmente.** Crea presion para descubrir estructura
eficientemente bajo budget. Esa es UNA propiedad de las "Presiones
evolutivas" de PROJECT.md. Pero NO crea presion para:

- Saber cuando una conclusion es prematura (la submission final es
  obligatoria al fin del budget).
- Generar hipotesis rivales (la unica hipotesis es "que reacciones
  hay").
- Anti-overexcitement (no hay claims para puntuar como over-claimed).
- Distinguir mecanismos de simples correlaciones (es structure
  recovery).
- Separar evidencia de priors (no hay priors de dominio, todo es
  abstracto).

**SREG: ese es el objetivo central.** El scoring debe presionar para
las 16 propiedades de PROJECT.md. SciGym mide solo una rebanada de
eso (eficiencia de descubrimiento estructural).

### Filtro 3: ¿Funciona para tipos diversos de investigacion?

**SciGym: NO. Cubre un tipo unico.** Structure discovery / network
recovery, en biologia de sistemas, sobre datos de series temporales
sin ruido, con action space cerrado (`set_initial_concentration` +
`submit_sbml`). Es un slice muy especifico del espacio de
investigacion cientifica.

**SREG: ese es un requisito de diseno.** Tiene que cubrir 23+
escenarios de `investigation_scenarios_rubric.md`: causal effect,
mediacion, heterogeneidad, descriptivo, epistemologico, multi-outcome,
identifiability, mecanismo discrimination, etc. Y el scoring debe
funcionar uniformemente para todos sin scoring profiles por tipo.

### Sintesis

SciGym **pasa parcialmente el filtro 1**, **falla parcialmente el filtro
2**, y **falla el filtro 3**. Esto NO es critica del paper — es
delineacion de scope. SciGym esta bien diseñado para lo que se propone
(medir capacidades cientificas en una rebanada controlable). SREG es
una **generalizacion estructural**, no un competidor.

### El SBML es un primo del SCM, mas restringido

SciGym usa SBML, que es un formalismo concreto: especies + reacciones +
parametros + leyes cineticas. SREG usa SCM, que es mas general: DAG
arbitrario + ecuaciones arbitrarias + ruido + capacidad de intervencion
explicita.

| Aspecto | SBML (SciGym) | SCM (SREG) |
|---|---|---|
| Estructura | grafo de reacciones bioquimicas | DAG causal arbitrario |
| Dinamica | ODEs continuas en el tiempo | sampler con ecuaciones libres |
| Causalidad explicita | implicita en las reacciones | explicita via do-operator |
| Intervenciones | cambiar concentracion inicial | `do(X = x)` sobre cualquier nodo |
| Contrafactuales | no representables directamente | representables via SCM twinning |
| Mediacion | implicita en las cadenas | explicita y medible |
| Confounding | implicito | explicito y estructural |

El SCM cubre todo lo que el SBML cubre como caso particular. La
diferencia no es estilistica — es **expresividad**. El SCM permite
ensenar cosas que el SBML no puede expresar: identifiability,
contrafactuales, frontdoor adjustment, mediacion estructural.

## Lo que rescatamos para SREG

### 1. SciGym como benchmark externo en la suite de tesis

**Decision tomada.** SciGym es Tier 1 en `thesis_evaluation_framework.md`
y suite final v1 en `sreg_training_transfer_protocol.md`. Es el unico
benchmark que mide la rebanada de loop iterativo del problema, y por
eso es la prueba mas afilada de si SREG entrena meta-skills reales.

### 2. Las tres metricas complementarias como modelo

NTS, RMS, STE son tres formas distintas de mirar la misma submission.
Cada una captura algo diferente:

- NTS: estructura local correcta?
- RMS: reacciones coherentes?
- STE: el modelo predicho hace las cosas correctas?

**Accion concreta para SREG:** vale la pena pensar si nuestro scoring
de OI deberia tener un analogo: **multiples vistas complementarias del
mismo episode**, en lugar de un score escalar unico. El sub-question
score ya empuja en esa direccion (coverage + correctness por
sub-question), pero SciGym sugiere que se puede ir mas lejos.

### 3. El cap de iteraciones como diseno honesto

SciGym fija 20 iteraciones max + 3 de debugging. Es un cap externo,
no un budget interno que el agente gasta. Es honesto pero deja
afuera la decision de "cuando parar" como skill.

**Implicacion para SREG:** si queremos medir "saber cuando parar"
(presion evolutiva clave), necesitamos un budget interno cerrado, no
un cap externo. Esa es exactamente la diferencia entre SREG-flat
(turnos cap) y SREG-Sherlock (presupuesto cerrado).

### 4. El reporte de resultados con headroom explicito

Frontier models en SciGym-small: RMS F1 < 0.20. **Reportan headroom
enorme y lo cuentan como hallazgo.** Es una buena practica: no se
pide que el modelo "gane" el benchmark, se muestra que esta lejos del
techo y por eso vale la pena entrenar.

**Accion concreta:** adoptar la convencion en el paper de SREG.
Reportar headroom contra el ceiling teorico (no contra otros modelos),
para enfatizar que el problema es lejos de estar resuelto.

### 5. Honestidad sobre limitaciones del environment sintetico

SciGym reconoce explicitamente que sus modelos no tienen ruido, son
ODEs simplificadas, y los agentes pueden overfittear a las
trayectorias mas que entender la biologia. **Esa honestidad es lo
que hace al paper defendible.**

**Implicacion para SREG:** vale tener una seccion analoga en el paper.
Limitaciones reconocidas:

- Ruido en los datos sinteticos vs ruido en datos reales.
- SCM limitado a DAGs y mecanismos representables.
- No covariate shift en held-out vs training.
- Sub-question agenda como proxy de "que vale la pena descubrir".

## Lo que NO copiamos

1. **Action space cerrado.** SciGym solo permite `set_initial_concentration`
   + `submit_sbml`. SREG deja `python_exec` libre, porque el space de
   acciones de la investigacion real es abierto. Cerrar action space
   es eficiente para benchmarking pero destruye la capacidad de
   ensenar "que herramienta usar".
2. **Domain narrow.** SciGym solo cubre biologia de sistemas. SREG
   debe cubrir todos los dominios. Generalidad es no-negociable.
3. **Output como artefact (SBML file).** SciGym evalua un archivo
   final. SREG evalua claims durante el episode. Esto cambia el
   shape del scoring fundamental: SREG puede dar credito parcial a
   piezas correctas, SciGym evalua un binario "¿el grafo coincide?".
4. **Cap externo en lugar de budget interno.** Como discutido arriba,
   esto destruye la skill "saber cuando parar".

## Como evalua SciGym (para alinear nuestro setup)

Esta seccion es la mas relevante para `external_benchmarks_transfer_analysis.md`
y para el setup BEFORE/AFTER.

### Setup que vamos a replicar

- **Splits:** evaluar inicialmente sobre **SciGym-small (137 modelos)**.
  Large (213 modelos) en una segunda pasada si el primer set es
  manejable computacionalmente.
- **Iteraciones max:** 20 por tarea + 3 debugging.
- **Modelos:** Qwen3-8B (base + RL desde base + opcionalmente SFT+RL,
  segun la decision pendiente que abrimos en `related_work_sandmle.md`).
- **Metricas a reportar:** NTS, RMS F1, STE. Convencion: reportar las
  tres como en el paper original.

### Lo que vamos a tener que adaptar

1. **Scaffolding del agente.** SREG usa OI episode runner; SciGym usa
   un loop con action space cerrado. Hay que escribir un adaptor que
   exponga las acciones de SciGym al agente OI con la misma interfaz
   que las de SREG (o lo mas parecida posible).
2. **Manejo de SBML.** El agente probablemente no sabe `libSBML`. Hay
   que decidir si proveer documentacion en el system prompt (zero-shot
   con context ayuda) o pre-entrenar exposicion via SFT.
3. **Time-series interpretation.** El agente SREG no fue expuesto a
   series temporales en el training. Hay que decidir si darles
   pre-procesamiento (resumenes estadisticos) o pasarlos crudos.

Estas son decisiones de scaffold que hay que cerrar antes del BEFORE
de SciGym. Ver GitHub Issue #12.

## Implicaciones para el paper de SREG

### Posicionamiento en related work

SciGym y SandMLE son las dos citas centrales a las que SREG tiene que
diferenciarse. Borrador de framing combinado:

> "Recent work has demonstrated that synthetic environments with
> programmatic ground truth can enable rigorous evaluation and training
> of agentic capabilities in scientific domains. SciGym (Duan et al.
> 2025) provides a benchmark for iterative experiment design over
> systems biology models in SBML, with deterministic scoring against
> ground-truth networks. SandMLE (Zhou et al. 2026) extends this idea
> from benchmarking to training, generating synthetic ML engineering
> tasks at scale and enabling RL trajectory-wise. SREG generalizes both
> directions: it is a *generator* (like SandMLE) that produces *open
> investigation environments* (broader than SciGym's structure
> recovery), with *causal verification against an SCM* (richer than
> SciGym's network matching), supporting *arbitrary research types*
> (broader than SandMLE's predictive ML tasks)."

### Diferenciador clave a defender en el paper

Frente a SciGym, los cinco puntos a defender son:

1. **Generalidad de tipos de investigacion** (23+ vs 1).
2. **Action space abierto** via `python_exec` (vs menu cerrado).
3. **Brief libre y scoring de relevancia/coverage** (vs "recupera el
   grafo").
4. **Disenado como generador para training**, no como benchmark
   estatico.
5. **SCM con causalidad explicita** (do-operator, contrafactuales,
   mediacion estructural) vs SBML (estructura implicita en reacciones).

Esos cinco puntos son la diferenciacion defendible. Sin ellos, el
paper podria ser leido como "SciGym pero en otros dominios".

### Validacion empirica que tomamos prestada

SciGym valida que:

- **Synthetic env + iterative loop + programmatic GT** es un setup
  viable para evaluar capacidades cientificas.
- **Frontier models tienen headroom enorme** en este tipo de tareas
  (RMS F1 < 0.20 en small, peor en large). Hay espacio para mejorar.
- **Scoring determinista funciona** sin necesidad de LLM-judge.

Esto baja el riesgo de que un revisor diga "¿porque el approach del
paper deberia funcionar?". Hay precedente publico de que el setup es
sano.

### Lo que SREG tiene que probar (que SciGym no necesita probar)

- Que **el approach escala** del benchmark estatico al training
  generator.
- Que **la transferencia es real** (held-out vs externos).
- Que **el reward de SREG crea presion** para juicio cientifico mas
  alla de structure recovery.
- Que **un agente entrenado con SREG mejora SciGym**, no solo
  benchmarks de razonamiento estatico — esto cierra el loop.

## Open questions para el equipo

1. **Adaptor del scaffold.** ¿Como exponemos las acciones de SciGym al
   agente OI? ¿Wrapeamos la API de SciGym dentro de `python_exec`, o
   replicamos el action space original?
2. **Pre-exposicion a SBML.** ¿Vale la pena darle al agente una
   exposicion minima a `libSBML` durante el SFT (si decidimos correr
   SFT)? ¿O dejarlo zero-shot?
3. **Series temporales.** ¿Damos el output de los experimentos crudo
   (concentraciones x tiempo) o pre-procesado (resumen estadistico)?
   La decision afecta la transferencia esperada.
4. **Splits.** Empezamos con SciGym-small (137 modelos) o vamos
   directo a large (213, hasta 400 reacciones)? El small es mas
   manejable pero menos diferenciador.
5. **Metrica primaria.** Reportamos las tres (NTS, RMS, STE) como
   ellos, o elegimos una como "metrica primaria de SREG"?
6. **Lectura del headroom.** Si SREG-trained mejora SciGym de RMS
   0.17 a 0.25, ¿es exito? Necesitamos un threshold de exito antes
   de correr.

## Referencia

Duan, H., Lu, S. Z., Harrigan, C. F., et al. (2025). *Measuring
Scientific Capabilities of Language Models with a Systems Biology Dry
Lab*. arXiv:2507.02083. NeurIPS 2025.

Resources:
- Paper: https://arxiv.org/abs/2507.02083
- Code: https://github.com/h4duan/SciGym
- Dataset: https://huggingface.co/datasets/h4duan/scigym-sbml
- OpenReview: https://openreview.net/forum?id=Cmx6b7w2nk
