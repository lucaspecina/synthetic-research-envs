# Open Investigation: investigacion libre con reward exacto

> **Status:** VISION EN DESARROLLO. No implementar todavia — disenar y madurar.
> **Fecha:** 2026-03-25 (actualizado 2026-03-26 con diseno Alpha + Codex)
> **Participantes:** Usuario, Claude, Codex (gpt-5.4)

## Explicacion simple (empieza por aca)

### Hoy: examen con preguntas

Hoy SREG es como un profesor que le da un examen al alumno con preguntas
especificas:

> "Pregunta 1: cual es el efecto de la presion sobre el arenamiento?"
> "Pregunta 2: que importa mas, la presion o la viscosidad?"

El alumno responde cada pregunta, y nosotros tenemos la respuesta exacta
(el SCM). Facil de corregir, pero **no es investigacion** — es un examen.

### Lo que queremos: investigacion libre

Queremos darle al solver lo que le darian a un investigador real:

> "Tenes datos de pozos en Vaca Muerta. Algunos se arenan, otros no.
> Averigua por que y que se puede hacer."

El solver investiga, analiza los datos, y al final entrega un reporte:

> "La presion es el factor principal. Opera a traves del colapso de
> fracturas. La viscosidad modera el efecto."

**El problema: como le ponemos nota a eso?**

### El truco: traducir y verificar

Nosotros tenemos la verdad completa (el SCM). El solver no lo sabe, pero
nosotros si. Entonces:

1. **El solver** investiga libre y escribe su reporte
2. **Un traductor** (otro LLM) lee el reporte y lo convierte a preguntas
   formales:
   - "La presion es el factor principal" -> verificar efecto causal de presion
   - "Opera a traves de fracturas" -> verificar mediacion
   - "La viscosidad modera" -> verificar interaccion
3. **El SCM** responde cada pregunta con la verdad exacta

Es como tener un profesor que lee la tesis del alumno, la descompone en
afirmaciones verificables, y las checkea contra la realidad.

### Preguntas clave resueltas (sesion 2026-03-26 con Codex)

**"Una nota final o varias?"** — Varias. El solver entrega 1 hallazgo
principal + hasta 4 de soporte. Cada uno se verifica por separado.

**"Y si hace mil afirmaciones a ver si alguna pega?"** — Cap de 5 claims
maximo. Y si tira muchas cosas incorrectas, la nota baja aunque acierte
algunas (precision gate sobre coverage).

**"Y si llega al resultado correcto pero sin investigar?"** — Para eso
esta "warrant" (fundamentacion). No alcanza con acertar — tenes que
mostrar que usaste los datos para llegar ahi. Un solver que responde
desde la intuicion sin mirar los datos saca mala nota en warrant.

**"Y el traductor? Si traduce mal?"** — Si no esta seguro de como
traducir algo, lo marca como "no puntuable" en vez de adivinar. Y el
solver puede ver como se tradujo y corregir antes de la entrega final.

### Orden de construccion (consenso Claude + Codex)

No construir todo junto. Ir de a pasos:

1. **Definir que es un "hallazgo"** formalmente (Claim, CompiledQuery,
   ClaimFamily)
2. **Construir el corrector sin traductor** — probar que el scoring
   funciona cuando los hallazgos ya vienen en formato perfecto
3. **Probar el traductor por separado** — darle textos y ver si traduce
   bien (benchmark offline)
4. **Recien ahi** juntar todo con un solver real (modo scaffolded, no
   fully open)

### Criterios de exito del Alpha

- El no-data baseline puntua claramente peor que un solver que investiga
- El shotgun (tirar muchos claims a ver si pegan) no puede explotar el
  coverage
- El score es estable ante variaciones del traductor
- Un solver mejor realmente supera a uno peor por margen interpretable

---

## El problema (version tecnica)

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

## Diseno del Alpha (sesion 2026-03-26 con Codex)

### Modo: Scaffolded Open (no fully open)

El Alpha NO es prosa totalmente libre. Es un modo intermedio:
- Brief abierto con pregunta primaria y target claro
- Solver investiga libre con las tools actuales (python_exec, etc.)
- Entrega final estructurada: 1 main finding + hasta 4 supporting findings
- Cada finding con: confianza y base de evidencia
- Translator compila cada finding a 0 o 1 query formal
- Verifier scorea contra el SCM

### Primitivas del Alpha (minimas)

Solo 4 para empezar (consenso Codex):
- `rank_effect(X1 vs X2, Y)` — cual importa mas
- `ate(X, Y)` o `effect_direction(X, Y)` — efecto causal
- `mediation(X, M, Y)` — fraccion mediada
- `interaction(X, Z, Y)` — el efecto depende del contexto

**NO en Alpha:** confounding (es mas de metodologia que de hallazgo).
**SI agregar:** `null/no-material-effect` como resultado posible.

### Scoring Alpha (propuesta Codex, discutida)

| Dimension | Peso | Que mide |
|-----------|------|----------|
| Correctness | 40% | Cada claim traducido se verifica contra el SCM |
| Warrant | 25% | Fundamentacion: uso la evidencia o adivino? |
| Weighted coverage | 20% | Encontro los hallazgos importantes descubribles? |
| Efficiency | 10% | No gasto budget en exploracion irrelevante? |
| Calibration | 5% | La confianza reportada matchea la realidad? |

**Gate critico:** coverage se multiplica por precision. Si tira muchos
claims falsos, no gana coverage por los correctos.

### Anti-shotgun

- Cap duro: maximo K=5 claims finales
- Deduplicacion por "familias de claims" (variantes del mismo hallazgo)
- Coverage solo paga si precision supera umbral
- Penalidad por claims no compilables o falsos
- Requerir evidence basis por claim

### Agenda oculta auto-generada

En vez de answer key manual, auto-generar claims verdaderos significativos
del SCM:

1. Enumerar primitivas sobre pares/tripletas de variables observables
2. Computar ground truth para cada una
3. Filtrar por: significancia (effect size > threshold) + descubribilidad
   (dado el budget y evidencia visible)
4. Clusterar en familias de claims equivalentes
5. Coverage = fraccion de familias descubiertas por el solver

### Translator: sound but incomplete

- Compilacion por bullet (no por reporte entero)
- Salida tipada: status, primitive, args, span, confidence
- Si duda: "unscorable" (nunca adivina)
- Compile-preview loop: solver ve la compilacion y corrige antes de submit
- Reliability medida OFFLINE antes de meter en el loop

### Orden de construccion

1. **Claim contract**: definir Claim, CompiledQuery, ClaimFamily como
   modelos formales
2. **Agenda generator + verifier**: probar scoring con claims formales
   perfectos (sin LLM, sin translator)
3. **Translator benchmark offline**: medir compile rate, precision,
   abstention rate, estabilidad entre reruns
4. **Piloto scaffolded**: solver real + translator + scoring, modo
   scaffolded (no fully open)

## Proximos pasos de investigacion (actualizado 2026-03-26)

1. **Definir claim contract** (Claim, CompiledQuery, ClaimFamily) como
   modelos Pydantic. Esto es el paso 1 del orden de construccion.

2. **Implementar agenda generator**: dado un SCM, enumerar todos los
   claims verdaderos significativos agrupados en familias.

3. **Implementar verifier scoring**: dado un set de claims formales
   (sin translator), computar correctness + coverage + los demas scores.

4. **Prototype translator offline**: dado un hallazgo en NL, compilarlo
   a query formal. Benchmark de reliability.

5. **Piloto E2E**: solver investiga, entrega reporte, translator compila,
   verifier scorea.

## Origen de esta idea

Sesion 2026-03-25. El usuario observo que las preguntas seguian sonando a
ejercicio de libro de texto y pregunto: "no deberiamos tener una pregunta
principal y secundarias que aporten a la principal? y que lo que testeemos
sea que el solver genere tambien esas mismas sub-preguntas?"

Eso llevo a la discusion sobre libertad investigativa, el rol del LLM
translator (analogo al orchestrator pero en la direccion inversa), y como
mantener reward exacto sin sesgar al solver.
