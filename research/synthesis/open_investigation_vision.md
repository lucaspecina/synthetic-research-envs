# Open Investigation: investigacion libre con reward exacto

> **Status:** VISION EN DESARROLLO. No implementar todavia — disenar y madurar.
> **Fecha:** 2026-03-25
> **Participantes:** Usuario, Claude, Codex (gpt-5.4)

## El problema

Hoy SREG le dice al solver QUE preguntar y COMO responder:

> "Cual es el efecto causal promedio de X en Y? Submitea un numero."

Esto es verificable pero artificial. Un investigador real no recibe preguntas
pre-armadas — recibe un problema abierto y tiene que descubrir que investigar.

El resultado: SREG mide si el solver RESPONDE bien, pero no si INVESTIGA bien.
La estrategia investigativa (que preguntar, por que, en que orden) no se evalua.

## La vision

El solver recibe un encargo de investigacion abierto y reporta hallazgos
libremente. Un pipeline de verificacion traduce esos hallazgos a queries
formales y los chequea contra el SCM. El reward es exacto.

### El patron universal

Toda investigacion real tiene esta estructura:

1. **Pregunta primaria** (vaga, motivada por el dominio): "Que causa el
   arenamiento en pozos de shale?"
2. **Sub-preguntas instrumentales** (que el investigador genera mientras
   explora): cuales son los factores, por que mecanismo operan, hay
   interacciones, hay confounders, cuanto impacta cada uno.
3. **La calidad de la investigacion** = calidad de sub-preguntas generadas
   + calidad de respuestas.

Este patron aplica a investigacion empirica explicativa en general: clinica,
social, experimental, field science, ingenieria causal, operations.

### Arquitectura de 3 capas

```
Solver                     LLM Translator              SCM Verifier
  |                            |                           |
  |  Investiga libre.          |                           |
  |  Reporta hallazgos    --> |  Traduce hallazgos a  --> |  Computa verdad
  |  en lenguaje natural.      |  queries formales.        |  exacta contra SCM.
  |                            |  (NO juzga, traduce)      |  Score determinista.
  |                            |                           |
```

**Solver**: investiga libre, reporta como investigador. No necesita saber que
es un ATE o una mediacion. Solo describe lo que encontro.

**LLM Translator**: traduce los hallazgos del solver a queries formales contra
el SCM. Rol analogo al orchestrator (que traduce papers a SCM specs). No es
juez — es compilador. Si un hallazgo es ambiguo, lo marca como "unscorable"
en vez de adivinar.

**SCM Verifier**: ejecuta cada query formal contra el SCM y computa la verdad
exacta. Determinista, sin LLM, sin heuristica. Este es el nucleo del reward.

### La analogia clave

El orchestrator ya hace exactamente este patron en la direccion opuesta:

```
Paper (libre) --> LLM traduce --> SCM specs (formal) --> tools construyen (exacto)
```

La verificacion es el mismo patron invertido:

```
Hallazgos (libre) --> LLM traduce --> queries formales --> SCM verifica (exacto)
```

## Dimensiones de scoring

### 1. Correctness (precision)
Cada hallazgo traducido se verifica contra el SCM. Es correcto o no.

### 2. Relevance (conducencia)
El hallazgo es conducente a la pregunta primaria? Verificable via el grafo
causal: si las variables del claim estan en la vecindad causal del target
de la pregunta primaria, es relevante. Si no, es irrelevante. Exacto.

### 3. Coverage (salient coverage)
Encontro los hallazgos importantes? Se compara contra claims verdaderos
significativos del SCM. No contra un answer key escrito a mano — contra
TODOS los claims verdaderos auto-generados del SCM (enumerar primitivas
sobre variables visibles).

Esto resuelve el "problema del camino diferente": si el solver descubre
A->D->C en vez de A->B->C (ambos reales en el SCM), recibe credito.

### 4. Calibration
La confianza que reporto matchea la realidad? Claims mas especificos
(cuantitativos) ganan mas reward si aciertan, mas penalidad si erran.

### 5. Efficiency
No gasto budget en exploracion irrelevante? No hizo "shotgun" de claims
esperando que algunos peguen?

### Pesos tentativos (de Codex)
- Precision/accuracy: 50% (con gate: coverage solo paga si false-positive rate es bajo)
- Salient coverage: 25%
- Efficiency: 15%
- Calibration: 10%

## Desafio central de diseno

> **Cual es el minimo de estructura que necesitamos pedirle al solver para
> poder verificar sus hallazgos, sin sesgarlo hacia los hallazgos que
> nosotros esperamos?**

### La respuesta: convenciones de reporte, no formato de respuesta

Como un paper cientifico: el journal no dice QUE descubrir, pero si dice
COMO reportar resultados. Convenciones minimas que habilitan verificacion
sin sesgar la investigacion.

### El LLM translator como puente

La decision de diseno clave: NO pedirle al solver que use primitivas
formales (eso lo sesga). En vez, dejar que reporte libre y usar un LLM
translator para compilar hallazgos a queries. Esto elimina el sesgo:
el solver no necesita saber que tipos de evaluacion existen.

El riesgo (mistranslation) se mitiga con:
- Claims ambiguos marcados como "unscorable"
- El solver puede ver la compilacion y corregir
- Medicion empirica de la reliability del translator

## Auto-generacion de la agenda oculta

En vez de escribir un answer key a mano, auto-generar TODOS los claims
verdaderos significativos del SCM:

1. Enumerar primitivas (effect, mediation, interaction, confounding, etc.)
   sobre pares/tripletas de variables observables
2. Computar ground truth para cada una
3. Filtrar por significancia (effect size > threshold)
4. Clusterar en "familias de hallazgos" equivalentes
5. Dar credito a cualquier claim del solver que matchee una familia

Esto es generativo, no manual. Escala con el tamano del SCM.

**Correccion importante (Codex):** coverage debe ser contra claims
DESCUBRIBLES dado el budget y la evidencia visible del episodio, no contra
todos los verdaderos del SCM. No premiar descubrimientos imposibles.

## Dimensiones de scoring — version refinada (con feedback Codex)

### 1. Correctness (precision) — ~40%
Cada hallazgo traducido se verifica contra el SCM.

### 2. Warrant (justificacion evidencial) — ~20%
**Dimension critica agregada por Codex.** Un claim puede ser verdadero en
el SCM pero mal fundamentado. Mide:
- Era identificable desde la evidencia visible?
- El solver junto la evidencia necesaria antes de afirmarlo?
- La fuerza del claim es proporcional al soporte?

Esto separa "investigar bien" de "acertar por priors" — es exactamente
lo que LA PREGUNTA del proyecto pide. Sin esta dimension, un solver que
responde desde pretraining sin mirar datos podria sacar buen score.

### 3. Relevance (conducencia) — ~15%
Tres sub-tipos (no solo causal):
- **Causal**: el claim involucra ancestros, mediadores, confounders o
  descendientes del target de la pregunta primaria
- **Epistemica**: el claim ayuda a distinguir mecanismos rivales
- **Operacional**: el claim afecta que medir o en que confiar

Para data quality y metodologia: si el hidden truth incluye un modelo de
observacion (missingness, measurement error, etc.), se puede verificar.
Si no, esos claims quedan sin puntuar.

### 4. Coverage (salient coverage) — ~15%
Encontro los hallazgos descubribles y significativos? Contra claims
auto-generados del SCM, filtrados por descubribilidad.

### 5. Calibration — ~5%
La confianza reportada matchea la realidad?

### 6. Efficiency — ~5%
No gasto budget en exploracion irrelevante?

**Nota:** los pesos son tentativos. Precision + warrant dominan (~60%)
porque sin ellos se premia al solver que hace shotgun o aciertan por suerte.

## Convenciones minimas de reporte

En vez de pedir primitivas formales (que sesgan), pedir convenciones de
escritura que hagan la compilacion tractable sin limitar la investigacion:

- Un hallazgo principal por parrafo o bullet
- Nombres explicitos de variables/entidades (no pronombres vagos)
- Separar hallazgos de caveats/limitaciones
- Separar descripciones de los datos de conclusiones causales

Estas son convenciones de estilo cientifico, no formatos de respuesta.
Cualquier paper real las cumple.

## El translator: sound but incomplete

Principio de diseno clave (Codex): el translator debe ser **correcto pero
incompleto** — abstener seguido, adivinar nunca. Mejor dejar un claim sin
puntuar que traducirlo mal.

Modos de fallo a trackear por separado:
- Wording ambiguo (culpa del solver)
- Tipo de claim no soportado (limitacion del sistema)
- Error del translator (bug a corregir)

El solver puede ver la compilacion y corregir antes del submit final.
Esto crea un "compile-preview loop" que mejora reliability sin limitar
libertad.

**Precision sobre exactitud:** el verifier es exacto (SCM). El pipeline
end-to-end es "exacto despues de compilacion". La compilacion introduce
un margen de error controlable pero real. No overstatar la exactitud del
sistema completo.

## Modos de evaluacion

### Guided (evolucion del modo actual)
- El solver recibe: brief + preguntas instrumentales explicitas
- Scoring: per-question exact (como hoy)
- Util para: training inicial, warm-up, evaluacion dirigida
- Ensenia: inferencia local, uso de herramientas, formato

### Scaffolded (intermedio)
- El solver recibe: brief + deliverables vagos ("identifica los drivers
  principales", "evalua mecanismos") sin preguntas formales
- Scoring: como Open pero con hints de direccion
- Util para: donde empieza el skill real de investigacion
- Ensenia: decidir que investigar, cuando la evidencia es suficiente

### Open (completo)
- El solver recibe: solo el brief con la pregunta primaria
- Scoring: correctness + warrant + relevance + coverage + calibration +
  efficiency
- Util para: medir calidad de estrategia investigativa completa

### Curriculum: mixto, no secuencial
**Codex advierte:** Guided-only no transfiere bien a Open. El skill real
(decidir que investigar, cuando parar, que reportar) se entrena en
Scaffolded, no en Guided. Usar curriculum mixto con weight shifting,
no fases limpias secuenciales.

## Que NO es esta vision

- **No es "free-form NL scoring".** El LLM traduce, no juzga. El scoring
  siempre es contra el SCM (despues de compilacion).
- **No es "eliminar preguntas tipadas".** Las preguntas siguen existiendo
  como agenda oculta y como modo Guided.
- **No es implementable manana.** Requiere: translator pipeline, auto-claim
  generation, scoring framework nuevo, y mucho testing.

## Conexion con el proyecto

- Responde a la tension "Apertura del problema vs verificabilidad exacta"
  de PROJECT.md — esta es la solucion.
- Extiende el trabajo de brief_vs_eval_separation (las 3 capas que ahi se
  identificaron: brief visible, eval agenda, query formal).
- Complementa scm_task_primitives (las primitivas son el vocabulario
  del translator y del claim generator).
- Es la siguiente evolucion natural despues de completar el pipeline
  orchestrator -> SCM.

## Proximos pasos de investigacion

1. **Experiment minimo** (propuesta de Codex): tomar 3-5 SRCs existentes,
   esconder las preguntas, darle solo el brief al solver, soportar 4
   primitivas (rank_effect, ate, mediation, interaction). Comparar:
   prosa parseada por LLM vs prosa + claim cards. Medir compile rate,
   precision, coverage, y reward stability.

2. **Disenar claim language**: que primitivas soporta el translator, como
   se compila cada una a query SCM, que nivel de especificidad (direccional,
   ordinal, cuantitativo).

3. **Auto-claim generation**: implementar enumeracion de claims verdaderos
   significativos desde un SCM.

4. **Prototype translator**: dado un hallazgo en NL, compilarlo a query
   formal. Medir reliability.

## Origen de esta idea

Sesion 2026-03-25. El usuario observo que las preguntas seguian sonando a
ejercicio de libro de texto y pregunto: "no deberiamos tener una pregunta
principal y secundarias que aporten a la principal? y que lo que testeemos
sea que el solver genere tambien esas mismas sub-preguntas?"

Eso llevo a la discusion sobre libertad investigativa, el rol del LLM
translator (analogo al orchestrator pero en la direccion inversa), y como
mantener reward exacto sin sesgar al solver.
