# SciAgentGym — analisis y comparacion con SREG

> **Status:** Related work consolidado. Referencia obligada para paper / tesis.
> **Fecha:** 2026-04-07
> **Paper:** Shen, Yang, Xi et al. 2026, "SciAgentGym: Benchmarking
> Multi-Step Scientific Tool-use in LLM Agents", arXiv:2602.12984v1
> (Fudan NLP Group, 20 autores).
> **Conecta con:** `external_benchmarks_transfer_analysis.md`,
> `sreg_training_transfer_protocol.md`, `thesis_evaluation_framework.md`,
> `related_work_sandmle.md`, `related_work_scigym.md`, `PROJECT.md`.

## Por que este paper importa para SREG

SciAgentGym es la pieza que faltaba en el triangulo de related work
contemporaneo de SREG. Junto con SandMLE (Zhou et al. 2026) y SciGym
(Duan et al. 2025), forma el set de tres papers que **convergen en el
mismo diagnostico** desde tres angulos distintos:

- **SandMLE** dice: en ML engineering, RL trajectory-wise sobre
  entornos sinteticos funciona, y SFT-only colapsa fuera del scaffold.
- **SciGym** dice: en biologia de sistemas, frontier models se quedan
  lejos del techo en loop iterativo (RMS F1 < 0.20) — hay headroom enorme.
- **SciAgentGym** dice: en scientific tool-use multi-step, los frontier
  models **pierden 30-50% del exito al pasar de pasos cortos a largos**,
  y nadie ha resuelto el long-horizon collapse.

**Los tres convergen en el problema, divergen en la solucion, y dejan un
gap explicito que SREG intenta llenar:** RL trajectory-wise + reward
verificable + investigacion abierta. Ningun otro proyecto publico esta
intentando esa interseccion.

Para SREG, este paper importa por tres razones:

1. **Validacion externa de la pregunta central.** El long-horizon
   collapse esta documentado con numeros concretos en frontier models.
   Es el problema que SREG dice que entrena.
2. **Metricas de proceso reutilizables.** SciAgentGym caracteriza failure
   modes de long-horizon de una forma que SREG todavia no tiene
   (Adaptation, Tuning, Switching, Loop Escape, dinamica Rise-Fall-Rise).
   Estas metricas son **directamente adoptables** como complemento del
   `score.total` de SREG.
3. **SciAgentBench como benchmark externo candidato (Tier 2).** Es el
   unico benchmark publico que estratifica explicitamente por horizonte
   (L1 ≤3 / L2 4-7 / L3 ≥8 steps), lo que permite medir la mejora **en
   funcion del horizonte**, no solo agregada.

## Resumen ejecutivo del paper

**Autores:** Yujiong Shen, Yajie Yang, Zhiheng Xi, et al. (Fudan NLP
Group). 20 autores.

**Problema:** Como medir la capacidad de un LLM agent de hacer
**multi-step scientific tool-use con horizonte largo**. Los benchmarks
previos miden tool-use en single-step o tareas cortas; nadie estaba
midiendo explicitamente la degradacion en horizontes largos.

**Insight central:** "Existing benchmarks underestimate the difficulty
of multi-step scientific reasoning because they primarily evaluate short
horizons. Long-horizon performance is qualitatively different and
collapses much faster than short-horizon performance."

### Componentes del proyecto

**1. SciAgentGym (el environment)**

Environment ejecutivo con **1.780 tools cientificas tipadas** en 4
disciplinas:

- Physics (109 tareas, 42%)
- Chemistry (81 tareas, 31%)
- Materials Science (37 tareas, 14%)
- Life Sciences (32 tareas, 12%)

Las tools son wrappers JSON-serializables sobre librerias reales
(RDKit, ASE, SciPy, BioPython, PyMatGen). Cada una tiene firma tipada:

```
v: (alpha_1^v, ..., alpha_k_v^v) -> (beta_1^v, ..., beta_m_v^v)
```

con tipos primitivos (`Float`, `Int`), estructurados (`Vector3D`,
`Matrix`) y de dominio (`SMILES`, `ProteinStructure`).

**Mecanismos del environment:**

- **Tool registry queryable:** el agente puede listar tools por
  subdominio o registrar selectivamente.
- **Fine-grained error feedback:** al fallar una ejecucion, el environment
  devuelve status, outputs tipados y diagnosticos.
- **State accumulation:** filesystem read-only que acumula contexto del
  problema, artefactos intermedios y historia de queries.

**2. SciAgentBench (el benchmark)**

259 tareas con **1.134 sub-questions**. Estratificadas por reasoning
complexity:

- **L1**: ≤3 steps
- **L2**: 4-7 steps
- **L3**: ≥8 steps

**Long-horizon (L2+L3) = 79% del benchmark.** Esto es central: el
benchmark esta intencionalmente sesgado hacia el regime donde los
modelos colapsan.

Cada tarea incluye:

- Expert tool-use trajectories (la secuencia esperada de invocaciones).
- Canonical inputs y outputs reproducibles.
- Reference solution + structured intermediate decomposition (sub-questions).
- Tolerancia numerica 0.05 + LLM-judge para campos textuales.

### Setup experimental

- **Loop:** ReAct-style Thought-Action-Observation con cap de 50 rounds
  por tarea. 30s por tool call, 300s total per request.
- **Modelos evaluados:** GPT-5, Claude-Sonnet-4, Gemini-2.5 series,
  Qwen3-VL series (4B-235B), GLM-4.6V.
- **Tool access:** with-tools vs without-tools como ablacion.

### Metricas

- **SR (Success Rate)** — binario: `SR = (1/N) sum_i S_i`, donde `S_i in
  {0,1}` indica si la tarea i fue completamente resuelta.
- **SPL (Success weighted by Path Length)** — penaliza ineficiencia:

```
SPL = (1/N) sum_i S_i * L_i / max(P_i, L_i)
```

donde `L_i` es el shortest path verificado por el experto y `P_i` es
el path real del agente. Si `P_i > L_i`, el score se descuenta
proporcionalmente.

### Resultados principales

**El collapse de long-horizon es brutal y consistente:**

| Modelo | L1 (≤3 steps) | L3 (≥8 steps) | Drop |
|---|---|---|---|
| GPT-5 | 60.6% | 30.9% | -49% relative |
| Claude-Sonnet-4 | 55.6% | 16.9% | -70% relative |
| GPT-5 overall | 41.3% | — | — |
| Claude-Sonnet-4 overall | 35.9% | — | — |
| SciAgent-8B (SFT) | — | — | 30.1% overall |
| Qwen3-VL-235B | — | — | 23.9% overall |

Average across all models: 28.1% with tools vs 23.2% without tools
(+4.9% gain por usar tools — sorprendentemente bajo).

### Failure modes que documentan (la parte mas valiosa)

Analizan **6.617 instancias de error** y clasifican el comportamiento
del agente en cuatro ejes:

| Eje | Mediana frontier | Que mide |
|---|---|---|
| **Adaptation** | 32.9% | Reacciona a errores, no los ignora |
| **Tuning** | **6.6%** | Refina parametros frente al error |
| **Switching** | 15.3% | Pivota estrategicamente cuando algo no funciona |
| **Loop Escape** | 35.7% | Sale de loops repetitivos |

Los numeros bajisimos en **Tuning** (6.6%) son indicadores criticos: los
modelos casi nunca refinan parametros en respuesta a errores. Solo
abandonan o reintentan.

**Trajectory-Level Recovery Dynamics:**

- Modelos fuertes: patron **"Rise-Fall-Rise"** — caen, se recuperan,
  vuelven a fallar, vuelven a recuperarse. Es un signo de adaptive
  reasoning.
- Modelos debiles: **declive monotonico** — caen y se quedan atrapados
  en error traps.

**Excessive Tool Invocation Loops:** los modelos debiles promedian 16.55
tool calls con 23.4% accuracy; GPT-5 promedia 3.41 tool calls con 41.3%.
**Mas tool calls correlaciona negativamente con accuracy**, una senal
clara de loops repetitivos sin reduccion de incertidumbre.

### Training (importante para nuestra decision SFT vs RL)

**No usan RL.** Solo SFT.

- **SciForge:** pipeline de sintesis de datos via "backward program
  construction". Modela las dependencias entre tools como un grafo
  dirigido, samplea paths validos, ejecuta en el environment, y genera
  dos clases de trayectorias:
  - **Golden Traces:** ejecuciones exitosas.
  - **Error-Recovery Trajectories:** intentos fallidos seguidos de
    correcciones.
- **SciAgent-8B:** Qwen3-VL-8B fine-tuneado por 3 epochs full-parameter,
  lr `1e-6` en bfloat16, sobre 11.074 trayectorias. Mejora: **+6.7%
  sobre el base** (de 23.4% a 30.1%).

**Lo que NO probaron:** RL trajectory-wise sobre el reward verificable
del environment. Es exactamente la pieza que SREG quiere validar.

## Coincidencias estructurales con SREG

### El loop iterativo con state accumulation

| SciAgentGym | SREG | Que comparten |
|---|---|---|
| **Filesystem read-only state** con contexto, artefactos, historia | **EpisodeTrace** + artifacts del solver | Estado evolutivo accesible al agente |
| **Fine-grained error feedback** tipado | **python_exec** stderr + traceback | Diagnostico estructurado para recovery |
| **ReAct loop** (Thought-Action-Observation) | **OI episode runner** (turn-based) | Multi-turn con observacion |
| **Sub-question decomposition** | **Sub-questions ocultas del orchestrator** | Estructura interna de la agenda |
| **SciForge data synthesis** (backward program construction) | **Compiler genera SRCs desde seeds** | Sintesis programatica para training data |

### Otras coincidencias relevantes

1. **Curado de fuentes peer-reviewed.** Las 259 tareas vienen de 5
   benchmarks academicos (ScienceQA, GPQA, R-Bench-V, BMMR, SFE).
   Mismo principio que SREG con seeds de papers.
2. **Diseno explicito para long-horizon.** 79% del benchmark es L2+L3.
   No es un benchmark accidentalmente largo — es intencional.
3. **Metricas duales: outcome + eficiencia.** SR mide outcome, SPL mide
   eficiencia. Mismo patron que SREG con `correctness` + `coverage` +
   `no-spam`.
4. **Honestidad sobre el collapse.** El paper no esconde que los frontier
   models fracasan en L3. Es la parte central de su narrativa.

## Divergencias fundamentales (triple filtro de CLAUDE.md)

### Filtro 1: ¿Se parece a investigacion real?

**SciAgentGym: parcialmente.** Las tareas son resolver problemas
cientificos multi-step que requieren composicion correcta de
herramientas. Eso parece investigacion. Pero **el agente no decide que
investigar** — la pregunta esta dada y tiene respuesta unica. Es mas
"ejercicio cientifico avanzado con herramientas reales" que
"investigacion abierta con brief libre".

Ademas: las **sub-questions estan dadas al agente como descomposicion
estructurada del problema**. En investigacion real, descomponer el
problema ES parte del trabajo. Si te dan la descomposicion, te
sacan la mitad de la skill.

**SREG: si (por diseno).** El brief es libre, el solver decide que
investigar, descompone el problema, genera hipotesis. Las sub-questions
son **agenda oculta del orchestrator**, no descomposicion visible al
agente.

### Filtro 2: ¿Crea presion evolutiva para juicio cientifico?

**SciAgentGym: parcialmente.** El SR penaliza errores, el SPL penaliza
ineficiencia. Eso presiona hacia "saber que tool usar" y "no perder el
tiempo". Los failure modes que ellos documentan (Adaptation, Tuning,
Switching, Loop Escape) son **propiedades reales de juicio cientifico**
y el scoring las presiona indirectamente.

Pero NO presiona hacia: hipotesis rivales, anti-overexcitement, decision
sobre que medir, **cuando parar** (el cap externo de 50 rounds resuelve
eso por afuera), distinguir mecanismos de simples correlaciones.

**SREG: ese es el objetivo central.** PROJECT.md "Presiones evolutivas"
lista 16 propiedades. SciAgentGym mide algunas (eficiencia, recovery,
loop escape) pero deja afuera la mitad epistemologica.

### Filtro 3: ¿Funciona para tipos diversos de investigacion?

**SciAgentGym: NO.** Es exclusivamente *problem-solving asistido por
tools* sobre dominios STEM duros (Physics, Chemistry, Materials, Life
Sciences). No cubre causal, descriptivo, epistemologico, system mapping,
heterogeneidad, etc. Su "diversidad" es de **dominio cientifico**, no de
**tipo de investigacion**.

**SREG: ese es un requisito de diseno.** El scoring debe funcionar
uniformemente para los 23+ escenarios de
`investigation_scenarios_rubric.md`.

### Sintesis del triple filtro

SciAgentGym **pasa parcialmente F1**, **pasa parcialmente F2**, y
**falla F3**. Es un benchmark serio y bien diseñado para lo que se
propone (medir scientific tool-use multi-step), pero NO es un competidor
estructural de SREG. Es un **slice del problema** que SREG aspira a
generalizar.

### El expert trajectory como ground truth

SciAgentGym usa **expert trajectories pre-grabadas** como referencia.
Esto es estructuralmente distinto al SCM de SREG:

| Aspecto | SciAgentGym | SREG |
|---|---|---|
| Forma de la verdad | secuencia esperada de tool calls + outputs | SCM con DAG y ecuaciones |
| Granularidad | path-level (¿el agente siguio el path correcto?) | claim-level (¿la afirmacion es verdadera?) |
| Multiplicidad | un path canonico (puede haber alternativas, pero no infinitas) | infinitas trayectorias validas si llegan a la verdad |
| Premia eficiencia? | si, via SPL (penaliza paths mas largos que el experto) | si, pero via no-spam, no via shortest-path |
| Permite caminos no anticipados? | parcialmente (LLM-judge puede aceptar respuestas correctas via paths no expert) | si, completamente — el SCM no sabe nada del path |

**Ventaja del expert trajectory:** scoring mas barato y reproducible,
captura "eficiencia" naturalmente.

**Desventaja:** induce un sesgo hacia "imitar al experto", no hacia
"resolver el problema". Si un agente encuentra un camino mejor que el
del experto, SPL lo castiga (porque `P_i > L_i`).

**Por que SREG no copia esto:** queremos que el reward presione hacia
**verdad**, no hacia **proceso canonico**. Un agente que descubre un
camino no anticipado pero correcto debe recibir credito completo. El SCM
permite eso. Las expert trajectories no.

## Lo que rescatamos para SREG

En orden de utilidad concreta:

### 1. Adoptar las metricas de proceso (Adaptation/Tuning/Switching/Loop Escape)

Esto es **la pieza mas valiosa** del paper para SREG. Hoy SREG mide
`score.total` (truth + relevance + coverage + no-spam) pero **no tiene
metricas de proceso** que distingan "el agente esta investigando bien"
de "el agente esta disparando tools al voleo". Las cuatro metricas de
SciAgentGym son directamente adoptables.

**Definiciones operativas que vale formalizar para SREG:**

- **Adaptation:** porcentaje de errores del solver donde el siguiente
  turn cambia explicitamente de approach (no es un retry identico).
- **Tuning:** porcentaje de turnos donde el solver ajusta parametros de
  un analisis previo en respuesta a una observacion (mas continuous que
  binary).
- **Switching:** porcentaje de turnos donde el solver abandona una rama
  de investigacion y abre otra distinta.
- **Loop Escape:** porcentaje de turnos donde el solver evita repetir
  exactamente la misma accion que ya hizo.

**Accion concreta:** instrumentar el `OIEpisodeRunner` para emitir
estas cuatro metricas en cada episodio. Reportarlas en el sub-question
score como complemento del total. Especialmente utiles para los audits
cualitativos que ya hacemos.

### 2. SPL como formalizacion de "no spam acciones"

Hoy SREG tiene un `no_spam_gate` binario que penaliza cuando el solver
emite muchas claims no relevantes. SPL es la version continua y mas
fina:

```
SPL = success * shortest_useful_path / max(actual_path, shortest_useful_path)
```

**Adaptacion para SREG:** podemos definir `shortest_useful_path` como
"numero minimo de turnos que un solver con la informacion correcta
necesita para llegar a la respuesta". Esto requiere medir tracks:
ground-truth-with-cheating-knowledge runs como referencia.

No es trivial implementarlo, pero la formalizacion existe y es
defensible. **Vale considerarlo como metrica derivada.**

### 3. La estratificacion L1/L2/L3 en held-out SREG

SciAgentGym muestra que **agregar accuracy oculta el collapse de
long-horizon**. Frontier models tienen 60% en L1 y 17% en L3 — el
average 35% no cuenta esa historia.

**Accion concreta:** estratificar nuestro `held-out SREG` por longitud
esperada de investigacion. Casos L1 (3 turnos), L2 (4-7), L3 (≥8). Esto
permite:

- Reportar "SREG-trained baja el collapse de L3 del X% al Y%", que es
  una claim mucho mas fuerte que "mejora el accuracy promedio".
- Diagnosticar exactamente donde el training tiene efecto.
- Comparar directamente con la dinamica de SciAgentBench.

Este es probablemente el cambio mas accionable para
`held-out SREG` en `TODO.md` T6.

### 4. SciForge data synthesis como referencia para nuestro pipeline de SFT

Si decidimos correr la variante `base + SFT` (reabierta en T7), SciForge
es un buen modelo de como sintetizar trayectorias de calidad: backward
construction sobre el grafo de dependencias + inclusion de error-recovery
trajectories (no solo golden traces). Las error-recovery son criticas
porque ensenan al modelo a recuperarse de fallos.

**Accion concreta:** cuando disenemos los datos de SFT (T7), incluir
explicitamente trayectorias de error-recovery, no solo trayectorias
optimas. SREG ya tiene los pilotos historicos como fuente — vale
filtrarlos en dos buckets (golden + recovery) en vez de mezclarlos.

### 5. SciAgentBench como benchmark externo Tier 2

SciAgentBench tiene tres ventajas frente a otros candidatos:

- **Stratification por horizonte explicita.** Unico benchmark publico
  que separa L1/L2/L3.
- **Tools reales que la gente usa** (RDKit, ASE, SciPy, etc.). Dominio
  proximo al "scientific Python" que SREG entrena.
- **Failure modes ya caracterizados.** Hay un baseline cualitativo de
  "como deberia comportarse un agente bueno en long-horizon".

Y tres desventajas:

- **Multimodal** (imagenes de moleculas, espectros). Qwen3-8B no es VL.
- **Expert-trajectory ground truth** rompe el principio "verdad
  matematica". Pero SR sobre sub-questions sigue siendo evaluable.
- **Scoring parcialmente LLM-judge** para campos textuales (no
  totalmente determinista).

**Recomendacion:** agregarlo a Tier 2 de la suite, NO a Tier 1.
Razones:
- SciGym ya cubre el slot "loop iterativo deterministico" en Tier 1.
- SciAgentBench complementa con dominio mas amplio y stratification por
  horizonte.
- Es scoring mixto, asi que no compite con la pureza determinista de
  Tier 1.

Ver `external_benchmarks_transfer_analysis.md` para el lugar exacto.

### 6. La observacion "more tool calls correlates with worse accuracy"

Es contraria a lo que uno esperaria intuitivamente. Validar si esto se
replica en SREG es importante. Si en SREG el solver hace mas
`python_exec` calls cuando el caso es mas dificil **pero** falla mas,
entonces estamos midiendo lo mismo y SPL aplica.

Si en SREG el solver hace mas calls cuando es mas dificil **y** acierta
mas, entonces SREG esta entrenando una skill diferente: persistencia
util, no thrashing. Eso seria evidencia POSITIVA de que el reward de
SREG es bueno.

**Accion concreta:** medir la correlacion `n_calls vs success` en los
pilotos historicos de SREG. Es una linea de codigo que diagnostica algo
profundo.

## Lo que NO copiamos

1. **Tool registry tipado pre-registrado.** Viola el principio de action
   space abierto. SREG mantiene `python_exec` libre porque queremos
   ensenar "decidir que herramienta usar", no "registrar tools del
   menu". Si pre-registramos las herramientas, sacamos una skill clave.
2. **Expert trajectories como ground truth.** Sesga el reward hacia
   imitar al experto, no hacia resolver el problema. Un agente con
   camino mejor que el experto es CASTIGADO por SPL. SREG verifica vs
   SCM, que es path-agnostic.
3. **Sub-questions visibles al agente.** En SciAgentGym la
   descomposicion del problema esta dada. En SREG es agenda oculta.
   Descomponer el problema ES parte de la skill que queremos entrenar.
4. **Solo SFT.** Es exactamente el camino que SandMLE mostro que
   colapsa fuera del scaffold. SREG quiere validar RL trajectory-wise.
5. **Multimodalidad VL.** Out of scope para Qwen3-8B y para el primer
   paper.
6. **Cap externo de 50 rounds para resolver "cuando parar".** Queremos
   que el agente aprenda a parar via reward, no via cap externo. Esa
   es una de las "Presiones evolutivas" no negociables.

## Como evalua SciAgentGym (para alinear nuestro setup)

Aunque SciAgentBench va a Tier 2 (no Tier 1), las decisiones de
evaluacion ahi nos ayudan a calibrar nuestra suite.

### Setup que vamos a replicar (si lo agregamos a la suite)

- **Splits:** evaluar inicialmente sobre L1+L2+L3 estratificado.
  Reportar accuracy por nivel **sin agregar**, para no esconder el
  collapse.
- **Modo de tool access:** with-tools (no probar without-tools — nos
  interesa evaluar al agente con su scaffold de SREG completo, no
  ablacionarlo).
- **Modelos:** Qwen3-8B (base + RL desde base + opcionalmente SFT+RL).
- **Metricas a reportar:** SR overall, SR por nivel, SPL, y las cuatro
  metricas de proceso si las podemos extraer del trace.

### Lo que vamos a tener que adaptar

1. **Multimodalidad.** Qwen3-8B no es VL. Tenemos dos opciones:
   - **Filtrar tareas no-multimodales** (las que solo usan texto).
     Reduce el N pero mantiene la metrica limpia.
   - **Convertir multimodal a textual** via captioning previo de las
     imagenes. Mas trabajo, mas N, pero introduce ruido.
   - Recomendacion: empezar filtrando, ver si queda N suficiente.
2. **Tool access.** SciAgentGym da el registry de 1.780 tools tipadas.
   El solver de SREG usa `python_exec`. Hay que decidir: ¿exponemos las
   tools como modulos importables desde python_exec? ¿O escribimos un
   adapter tool por tool?
3. **Path measurement.** SPL requiere medir el path real. Nuestro
   `OIEpisodeRunner` tracquea turnos pero no necesariamente
   "tool calls" en el sentido de SciAgentGym. Hay que normalizar.

Estas son decisiones de scaffold a cerrar antes del BEFORE de
SciAgentBench. Vale agregar como T8 en `TODO.md` si confirmamos el
plan.

## Implicaciones para el paper de SREG

### Posicionamiento en related work

SciAgentGym es la **tercera cita central** en related work, junto con
SandMLE (training) y SciGym (loop iterativo deterministico). Las tres
son citas independientes que cubren distintas dimensiones del problema.

Borrador de framing combinado:

> "Recent benchmarks and frameworks have begun to characterize the
> challenges of long-horizon scientific reasoning in LLM agents.
> SciGym (Duan et al. 2025) measures iterative experiment design over
> systems biology models with deterministic graph-recovery scoring.
> SciAgentGym (Shen et al. 2026) demonstrates that frontier models
> collapse from 60% to 30% success rate as task horizon extends from
> 3 to 8+ steps in scientific tool-use, and characterizes the failure
> modes (loop entrapment, lack of parameter tuning, monotonic decline
> in recovery rate). SandMLE (Zhou et al. 2026) shows that synthetic
> environments enable RL trajectory-wise training in ML engineering,
> but that SFT-only collapses outside the generation scaffold. **All
> three converge on the same diagnosis: long-horizon agentic reasoning
> in science is the bottleneck, and no public approach has yet combined
> RL trajectory-wise training with verifiable rewards on open
> investigation tasks. SREG fills exactly that gap.**"

### Diferenciador clave a defender en el paper

Frente a SciAgentGym:

1. **Open investigation vs guided tool composition.** El brief de SREG
   es libre; en SciAgentBench la pregunta y la descomposicion estan
   dadas.
2. **SCM-based truth vs expert trajectory.** SREG verifica contra
   verdad matematica, no contra path canonico. Permite caminos no
   anticipados.
3. **Action space abierto vs tool registry tipado.** SREG ensena
   "decidir que tool", SciAgentGym ensena "usar bien tools del menu".
4. **Generador para training vs benchmark estatico.** SREG produce
   environments arbitrarios; SciAgentBench tiene 259 tareas fijas.
5. **RL trajectory-wise (planeado) vs SFT only.** Es exactamente el
   gap que SciAgentGym deja abierto.

### Validacion empirica que tomamos prestada

- **El long-horizon collapse esta cuantificado.** No tenemos que
  defenderlo en abstracto — los numeros estan en SciAgentGym.
- **Las metricas de proceso son una referencia validada.** Si SREG
  reporta Adaptation/Tuning/Switching/Loop Escape, hereda la
  legitimidad de SciAgentGym.
- **Los failure modes son los mismos en toda la literatura.** Loops
  repetitivos, no tuning, falta de switching. SREG puede citar esto
  como problema universal y posicionarse como solucion.

### Lo que SREG tiene que probar (que ellos no probaron)

- Que **RL trajectory-wise sobre reward verificable** mejora long-horizon
  mas que SFT solo (SciAgentGym solo probo SFT).
- Que el beneficio **transfiere** a sus benchmarks (SciAgentBench L3,
  SciGym, CRB).
- Que SREG entrena las cuatro metricas de proceso de SciAgentGym (no
  solo accuracy agregado).

## Open questions para el equipo

1. **SciAgentBench como Tier 2.** ¿Lo confirmamos? Si si, abrir T8 en
   `TODO.md` con las decisiones de scaffold pendientes.
2. **Adoptar las cuatro metricas de proceso en `held-out SREG`.** ¿Las
   formalizamos ahora o esperamos a tener mas data de pilotos?
3. **SPL en SREG.** ¿Vale el costo de implementar
   `shortest_useful_path` como referencia? Es un compromiso de
   ingenieria no trivial.
4. **Stratification L1/L2/L3 en held-out.** ¿Cambiamos T6 en `TODO.md`
   para que el split de tesis incluya esto desde el inicio?
5. **SciForge como referencia para SFT data.** ¿Cuando armemos los
   datos de SFT (T7), seguimos el patron golden + error-recovery?
6. **Multimodalidad.** ¿Filtramos las tareas multimodales de
   SciAgentBench, o evitamos el benchmark hasta que tengamos un VL?

## Referencia

Shen, Y., Yang, Y., Xi, Z., et al. (2026). *SciAgentGym: Benchmarking
Multi-Step Scientific Tool-use in LLM Agents*. arXiv:2602.12984v1.
Fudan NLP Group (20 authors).

Resources:
- Paper: https://arxiv.org/abs/2602.12984
- HTML: https://arxiv.org/html/2602.12984v1
- HuggingFace: https://huggingface.co/papers/2602.12984
- Code: https://github.com/CMarsRover/SciAgentGYM
