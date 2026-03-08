# SREG — Qué vamos a construir y cómo
## Synthetic Research Environment Generator

## La idea en una oración

SREG genera **problemas de investigación ficticios pero realistas** — con contexto, datos,
preguntas abiertas y restricciones — donde la verdad subyacente es una red bayesiana formal,
lo que permite evaluar con exactitud matemática qué tan bien razona un agente LLM.

---

## Pensalo así

Imaginá que sos director de un laboratorio y querés evaluar si un investigador junior
sabe investigar de verdad. Tenés dos opciones:

**Opción A**: Le das un problema real publicado. Problema: si leyó el paper, ya sabe la
respuesta. No estás midiendo razonamiento — estás midiendo memoria.

**Opción B**: Inventás un problema ficticio pero realista. Le das datos parciales, contexto
teórico, y algunas pistas. El dominio no existe, así que no puede haberlo memorizado.
Si llega a conclusiones correctas, es porque **razonó bien con la evidencia**.

SREG es la Opción B, pero para LLMs y razonamiento científico.

---

## Qué genera SREG — el producto final

Cada "ambiente de investigación" que SREG genera tiene dos capas:

### Capa formal (oculta) — la verdad matemática

Una red bayesiana que define con precisión exacta las relaciones causales del mundo:
- **Variables** (algunas observables, otras latentes)
- **Relaciones causales** (un DAG — grafo dirigido acíclico)
- **Distribuciones de probabilidad** condicionales (CPDs)
- **Un target**: lo que el agente tiene que descubrir

Esta capa nunca la ve el agente. Es la referencia contra la que se evalúa.

### Capa semántica (visible) — el problema de investigación

Encima de la red bayesiana se construye una presentación que simula lo que un
investigador o ingeniero recibiría en la realidad. Esto incluye:

- **Narrativa del problema**: qué está pasando, por qué importa, cuál es el contexto.
  No un paper completo — una descripción clara de la situación y por qué hay que
  investigarla.

- **Datos disponibles**: lo que el investigador ya tiene en la mano. Puede incluir
  cualquier combinación de:
  - Un dataset tabular (CSV/DataFrame con columnas nombradas, N filas)
  - Múltiples datasets de distintas fuentes
  - Observaciones puntuales ("en la estación 3 se midió temperatura de 24.3°C")
  - Resultados de experimentos previos
  - Datos parciales o incompletos (valores faltantes, mediciones con ruido)
  - Metadata (cuándo se tomó, quién lo midió, con qué instrumento)

  Todos los datos se derivan sampleando de la red bayesiana, pero se presentan
  en el formato que tendría sentido para el dominio.

- **Nombres semánticos**: vocabulario científico real (`water_temperature`,
  `enzyme_activity`) en un dominio ficticio ("Síndrome de Harmon", "ecosistema
  del planeta Kepler-442")

- **Preguntas de investigación**: una o varias preguntas que el agente tiene que
  resolver. Pueden ser preguntas principales y sub-preguntas. Cada pregunta
  tiene un tipo de evaluación asociado (inferencia, causal, selección de
  hipótesis, etc.) — ver la sección de evaluación para el espacio completo.

- **Acciones disponibles**: qué "experimentos" o "mediciones" puede solicitar el
  agente, cada uno con un costo. Son las únicas interacciones que cuestan budget.

- **Restricciones**: presupuesto total, qué se puede medir y qué no, limitaciones
  del contexto.

- **Contexto teórico (opcional)**: teorías existentes, hallazgos previos, hints,
  información parcial que orienta (o despista) al agente.

Un mismo mundo formal puede generar múltiples escenarios con distintas
combinaciones de datos, preguntas, y restricciones.

### Por qué nombres semi-reales

Los nodos usan vocabulario científico real en contextos ficticios. No `indicator_1`
(demasiado abstracto) ni nombres completamente inventados como `zorbax_flux`
(el LLM no puede usar intuición científica). Queremos `water_temperature` en el
"archipiélago de Thalassia" — así el LLM puede usar su conocimiento real para
guiar su investigación, pero las relaciones causales pueden diferir de la realidad.
Esto testea si el agente se adapta a la evidencia o se queda con priors memorizados.

### Ejemplo concreto del objetivo final

```
PROBLEMA DE INVESTIGACIÓN
Declive de producción en cultivos de algas del archipiélago ficticio de Nelvara

CONTEXTO:
Investigadores del Instituto Oceánico de Nelvara han reportado una caída del 40%
en la producción de algas Spirulina en las granjas del sector norte durante los
últimos 6 meses. Se sospechan múltiples factores: cambios en la temperatura del
agua, niveles de nutrientes, y un posible compuesto no identificado en sedimentos.

Estudios previos en la región de Korvath (publicados en el ficticio Journal of
Nelvaran Marine Biology) sugieren que la temperatura y los nutrientes son los
drivers principales del crecimiento de Spirulina, pero los investigadores de
campo sospechan que hay un factor no considerado en esos estudios.

DATOS DISPONIBLES:
- Dataset 1: 150 mediciones de 4 estaciones de monitoreo
  (columnas: station_id, date, water_temp, pH, nitrogen, luminosity)
- Dataset 2: 12 muestras de sedimento del sector norte
  (columnas: sample_id, location,ite_concentration,ite_depth)
- Observación aislada: "el sector sur, que no muestra declive, tiene
  temperaturas similares pero sedimentos distintos"

ACCIONES POSIBLES (cada una tiene un costo):
- Solicitar análisis completo de sedimentos (sector norte + sur) → costo: 2
- Medir concentración de compuesto X en agua de las estaciones → costo: 1
- Obtener datos históricos de temperatura (3 años) → costo: 1
- Realizar cultivo experimental controlado → costo: 3
- Comparar composición de sedimentos norte vs sur → costo: 2

PRESUPUESTO: 5 unidades

PREGUNTAS:
1. ¿Cuál es la causa principal del declive en producción? (principal)
2. ¿Qué medición adicional sería la más informativa? (sub-pregunta)
3. Si el compuesto X se elimina del sedimento, ¿se recuperaría la producción? (causal)

[Detrás de todo esto: una red bayesiana de 8 nodos con CPDs exactas.
Cada pregunta tiene una respuesta verificable matemáticamente.
El agente puede hacer lo que quiera — pensar, analizar datos, escribir
código, formular hipótesis — pero los "experimentos" cuestan budget.]
```

---

## Las dos capas en detalle

### La red bayesiana (siempre presente, siempre formal)

Esto NO cambia. Es el motor del sistema:

```
Variables:
  sediment_compound (latente) → presente / ausente
  water_temperature (observable) → baja / media / alta
  nitrogen_level (observable) → bajo / medio / alto
  algae_production (target) → baja / media / alta
  light_exposure (observable) → baja / media / alta

Relaciones causales (DAG):
  sediment_compound → water_temperature
  sediment_compound → algae_production
  nitrogen_level → algae_production
  light_exposure → algae_production

CPDs: tablas de probabilidad condicional exactas para cada nodo
```

La respuesta correcta a cualquier pregunta sobre este mundo se calcula
matemáticamente. No hace falta un humano ni otro LLM para evaluar.

### La capa semántica (se construye encima)

La misma red bayesiana se presenta como un problema de investigación:
- El LLM orchestrator genera la narrativa y los nombres
- Los datos se sampean de la red bayesiana y se presentan en formato realista
- Las acciones disponibles corresponden a observar nodos (con costos)
- Las preguntas corresponden a inferir el target o elegir la mejor acción

Esta capa es modular — se puede mejorar independientemente sin tocar la formalización.

---

## Templates — qué son y por qué hacen falta

### El problema de crear un mundo "de la nada"

Una red bayesiana no es solo un grafo. Es un grafo + **tablas de probabilidad**
(CPDs) para cada nodo. Para un nodo con 3 estados y 2 padres de 3 estados cada
uno, la tabla tiene 3 × 9 = 27 valores que deben sumar 1 por columna, producir
relaciones interesantes (no todo uniforme), y ser coherentes entre sí.

Si dejamos al LLM inventar un DAG arbitrario, ¿quién llena esas tablas? Generar
CPDs al azar produce mundos basura donde todo es ruido. Hay que generarlas con
lógica que entienda la estructura.

### Un template es un generador completo

Un template NO es solo "la forma del grafo". Es un **generador** que sabe hacer
tres cosas:

1. **Crear la estructura**: qué nodos, qué tipos (latente/observable/target),
   qué flechas conectan qué
2. **Generar CPDs válidas**: tablas de probabilidad que producen mundos con
   señal real (no ruido puro), usando `edge_strength` para controlar cuánto
   "manda" un padre sobre un hijo
3. **Garantizar propiedades**: que haya camino del latente al target, que existan
   d-separaciones no triviales, que la entropía esté en un rango interesante

### Templates actuales y futuros

| Template | Estructura | Tipo de razonamiento | Estado |
|---|---|---|---|
| `latent_preference` | Estrella: 1 latente → N observables → 1 target | Diagnóstico (inferir causa desde síntomas) | Implementado |
| `causal_chain` | Cadena: A → B → C → ... → target | Predicción (seguir la cadena causal) | Futuro |
| `fork_collider` | Forks y colliders mezclados | Causal puro (confounders, explaining away) | Futuro |
| `custom` | **Cualquier DAG arbitrario** | Depende de la estructura | Futuro |

### La evolución: de templates fijos a DAGs arbitrarios

Los templates con formas predefinidas son el punto de partida, no el destino.
Lo que un template realmente hace son dos cosas separables:

1. **Definir la estructura del DAG** (qué nodos, qué flechas)
2. **Generar CPDs válidas para esa estructura** (las tablas de probabilidad)

La segunda parte — la generación de CPDs — es **genérica**. La fórmula basada
en `edge_strength` que hoy usa `latent_preference` funciona para cualquier
DAG, no depende de la forma. Esto abre la puerta a:

**Template `custom`**: acepta una especificación arbitraria de DAG (nodos,
tipos, flechas) y genera CPDs para ella. Con esto se pueden crear redes
bayesianas de **decenas de variables** con relaciones complejas — múltiples
latentes, múltiples targets, cadenas largas, confounders, colliders,
mediadores, lo que sea.

**Seeds desde papers**: el LLM lee un paper científico, extrae la estructura
causal ("hay 15 variables, estas son las relaciones"), y pasa eso como
especificación al template `custom`. El sistema genera CPDs que producen un
mundo formalmente correcto pero ficticio — las relaciones pueden diferir del
paper real, que es exactamente el punto.

### Variables discretas y continuas

Hoy todas las variables son categóricas (`low`, `medium`, `high`). Pero el
sistema debería soportar ambos tipos:

- **Variables discretas** (lo actual): estados categóricos, CPDs como tablas
  de probabilidad, evaluación con KL divergence discreta
- **Variables continuas** (futuro): valores numéricos reales, CPDs como
  distribuciones Gaussianas condicionales (`LinearGaussianCPD` en pgmpy),
  evaluación con Wasserstein distance o KL continuo

Un mundo podría mezclar ambos tipos: algunas variables categóricas
(diagnóstico: presente/ausente) y otras continuas (temperatura: 24.3°C).
Esto haría los problemas de investigación mucho más realistas.

### La visión completa

Cuando todo esto esté implementado, SREG podría generar un problema como:

> "Una red bayesiana de 25 variables (3 latentes, 20 observables, 2 targets)
> extraída de un paper sobre dinámica de ecosistemas. Variables mixtas:
> 8 categóricas (tipo de suelo, presencia de especie) y 17 continuas
> (temperatura, pH, concentración). Relaciones complejas con confounders,
> mediadores, y efectos indirectos."

Empezamos simple con `latent_preference` de 6 nodos discretos. Pero la
arquitectura no tiene ningún límite fundamental para escalar.

Lo importante: **el template es lo que permite que exista una verdad matemática
verificable**. Sin generador de CPDs → sin ground truth → sin evaluación.

---

## El agente solver — filosofía

El agente que resuelve los problemas es un LLM. Principios clave:

### El agente tiene libertad total para razonar

El agente puede hacer lo que quiera para resolver el problema:
- Leer y analizar el contexto (gratis)
- Analizar los datos disponibles (gratis)
- Formular hipótesis (gratis)
- Escribir código para analizar datos (gratis)
- Razonar, comparar explicaciones, pensar (gratis)

**Nosotros no prescribimos cómo debe pensar.** No le decimos "primero hacé X,
después hacé Y". Le damos el problema y que haga lo que quiera.

### Lo único que cuesta son las "acciones del mundo real"

Lo que sí controlamos son las acciones que equivalen a hacer cosas en el mundo
real — experimentos, mediciones, recolección de datos nuevos:

- Pedir una medición nueva → cuesta budget
- Solicitar un análisis de laboratorio → cuesta budget
- Obtener datos adicionales → cuesta budget

Estas acciones están definidas como parte del mundo. Cada una tiene un costo
y corresponde a observar un nodo (o conjunto de nodos) de la red bayesiana.

### Las acciones se definen por mundo

Qué puede hacer el agente, cuánto cuesta cada cosa, y qué restricciones tiene
se define como parte de la configuración del mundo/episodio. Esto permite:
- Mundos donde todo es barato pero hay muchas variables
- Mundos donde hay pocas acciones pero son caras
- Mundos con acciones que revelan mucho vs poco
- Mundos con restricciones específicas

En las primeras versiones, las acciones son simples (observar variable X con
costo Y). Después se puede escalar a acciones más complejas.

---

## Cómo se genera un mundo — el pipeline

### Seed (input)

El sistema recibe una semilla para crear el mundo. Puede ser:
- Un tema: "epidemiología", "ecología marina", "materiales"
- Un escenario narrativo: "hay un problema con la producción de X..."
- Un paper o documento de referencia (el LLM extrae la estructura)
- Parámetros técnicos: "6 nodos, dificultad media"
- Nada (generación libre)

### Generación (LLM + tools)

1. **El LLM orchestrator** recibe el seed y decide la estructura del mundo
2. **WorldGenTool** construye la red bayesiana (DAG + CPDs) — programático
3. **WorldCheckTool** valida que el mundo sea interesante y no trivial
4. Si falla, el LLM ajusta parámetros y reintenta
5. **El LLM genera la capa semántica**: nombres, narrativa, descripción
6. **EpisodeGenTool** crea episodios con datos y acciones disponibles
7. **TaskGenTool** formula las preguntas de investigación

El LLM **nunca toca los números**. Propone estructura y semántica.
Las tools construyen y verifican la matemática.

### Validación

- DAG válido (acíclico)
- Entropía adecuada (ni trivial ni imposible)
- D-separaciones no triviales
- El teacher solver puede resolverlo con >90% accuracy

---

## El Teacher Solver — el investigador perfecto

El teacher es un motor bayesiano exacto (no es un LLM) que resuelve cada
problema de forma óptima:

- Siempre elige la acción que más información le da
- Siempre mantiene la distribución de probabilidad exacta
- Siempre da la respuesta correcta al final

Sirve para:
1. **Validar mundos**: si el teacher no puede resolver bien, el mundo está mal
2. **Línea base perfecta**: comparar cualquier agente contra lo mejor posible
3. **Generar trayectorias óptimas**: secuencias de decisiones perfectas que
   pueden usarse como datos de entrenamiento

---

## Evaluación — qué se mide y cómo

La gran ventaja de tener una red bayesiana formal como verdad oculta es que
**muchas cosas distintas se pueden evaluar**. Hay dos familias de evaluación,
fundamentalmente distintas en cómo funcionan.

### Familia 1: Evaluaciones formales (automáticas, exactas)

Estas evaluaciones se calculan **directamente de la matemática del BN**. No
necesitan LLM judge ni humano. La respuesta correcta se computa con certeza
y la comparación es objetiva.

Funcionan con **cualquier template** — la ground truth viene del BN formal,
no de la forma del grafo. Lo que cambia entre templates es el *tipo de
razonamiento* que requiere, no el mecanismo de evaluación.

| Evaluación | Pregunta | Cómo se evalúa | Estado |
|---|---|---|---|
| **Inferir target** | ¿Cuál es P(target \| evidencia)? | KL divergence entre la predicción del agente y la posterior exacta. Variante simple: accuracy del estado más probable. | Implementado |
| **Mejor próxima acción** | ¿Qué variable conviene medir? | Information gain de la acción elegida vs la óptima (calculada por el teacher). | Implementado (teacher lo calcula) |
| **Efecto causal** | Si intervenimos en X, ¿qué pasa con Y? | Diferencia entre la estimación y P(Y \| do(X=x)), calculada exactamente desde el DAG (do-calculus). | Futuro |
| **Descubrimiento de estructura** | ¿Cuál es el DAG real? | Structural Hamming Distance, edge F1. Grafos Markov-equivalentes se aceptan como correctos. | Futuro |
| **Selección de hipótesis** | De estas explicaciones, ¿cuál es la más plausible? | ¿Eligió la hipótesis con mayor probabilidad posterior? | Futuro |
| **Predicción** | Dado lo observado, ¿qué valor tendrá Z? | Accuracy, calibración, Brier score contra la distribución real. | Futuro |
| **Optimización** | ¿Qué acción maximiza/minimiza un outcome? | Regret respecto al óptimo calculado desde el BN. | Futuro |

**Lo clave**: todas estas evaluaciones son posibles porque tenemos el BN
completo con CPDs exactas. No importa cuántos templates agreguemos — la
evaluación funciona igual en todos.

### Familia 2: Evaluaciones semánticas (soft, requieren juez)

Estas evalúan la **calidad del razonamiento**, no solo la respuesta final.
Son más difíciles de automatizar y menos precisas, pero capturan aspectos
que las formales no pueden.

| Evaluación | Pregunta | Cómo se evalúa |
|---|---|---|
| **Coherencia del razonamiento** | ¿El argumento tiene sentido? | Rúbrica + LLM-as-judge |
| **Uso de evidencia** | ¿Actualizó creencias al recibir datos nuevos? | Comparar trayectoria vs teacher |
| **Consideración de alternativas** | ¿Exploró hipótesis distintas? | Análisis de la cadena de razonamiento |
| **Eficiencia de budget** | ¿Pidió las observaciones más útiles? | Info acumulada vs budget gastado (esto es computable) |

Algunas de estas se pueden **aproximar formalmente** comparando la trayectoria
del agente con la del teacher óptimo. Otras requieren LLM-judge o rúbricas
humanas.

### Múltiples evaluaciones por tarea

Un mismo problema de investigación puede tener varias preguntas, cada una
con su evaluación formal:

```
Problema: Declive de producción de algas

Evaluación 1 (principal): ¿Cuál es la causa más probable?
  → inferir target, scored por KL divergence

Evaluación 2: ¿Qué medición adicional sería más informativa?
  → mejor próxima acción, scored por info gain

Evaluación 3: Si eliminamos el compuesto del sedimento, ¿se recupera la producción?
  → efecto causal, scored por diferencia con P(Y | do(X))

Sub-evaluación: Calidad del proceso
  → ¿Usó el budget eficientemente? ¿Pidió observaciones relevantes?
  → scored por info acumulada vs budget gastado
```

### Métricas transversales

Además de la evaluación específica por pregunta, hay métricas que aplican
a todo problema:

- **Eficiencia**: ¿cuánto budget usó para llegar a su respuesta?
- **Calibración**: cuando dice "70% seguro", ¿acierta el 70% de las veces?
- **Mejora incremental**: ¿mejora su respuesta con más evidencia, o se queda
  con su primer guess? (El teacher siempre mejora — un buen agente también)
- **Comparación vs teacher**: ¿qué tan lejos está del óptimo?
- **Comparación vs random**: ¿es mejor que elegir al azar?

### Por qué esto es una ventaja

SREG tiene una ventaja sobre la mayoría de benchmarks de agentes: **la verdad
es matemática**. En SWE-bench necesitás tests que pueden no cubrir todos los
casos. En WebArena necesitás heurísticas para verificar resultados. En SREG,
la red bayesiana te da la respuesta exacta a cualquier pregunta que tenga
sentido hacer sobre el mundo oculto — sin jueces, sin ambigüedad.

---

## Qué NO es SREG

- **No es el agente que resuelve.** Es el gimnasio donde se entrena.
- **No es un benchmark estático.** Es un generador que produce infinitos problemas.
- **No entrena LLMs.** Genera los mundos, tareas, y datos. Si alguien quiere
  usar eso para entrenar, tiene todo listo.
- **No prescribe cómo debe razonar el agente.** Solo le da el problema y las
  acciones disponibles. El agente decide cómo proceder.

---

## Versiones del proyecto

### v0 — Motor formal + semántica mínima + agent solver POC

El objetivo de v0 es tener un sistema que genera problemas de investigación
ficticios pero creíbles, y un agente LLM que intenta resolverlos.

**Incluye:**
- Red bayesiana como verdad oculta (pgmpy)
- 1 familia de templates (latent preference) con capa semántica
- Capa semántica mínima: nombres semi-reales, narrativa breve del problema,
  datos presentados de forma realista (configurable: tabular o datapoints)
- Acciones del agente: observar variables (con costo) + submit respuesta
- Teacher solver exacto como referencia
- Agente LLM solver básico que recibe el problema e interactúa
- Evaluación: inferencia de target (KL divergence), eficiencia de budget
- LLM orchestrator que genera mundos con semántica
- Exportación de trayectorias del teacher como dataset

**No incluye:**
- Documentos sintéticos elaborados (papers ficticios, reportes largos)
- Seeds desde papers reales (input manual sí, búsqueda automática no)
- Evaluación de efectos causales o intervenciones
- Acciones complejas del agente (solo observar variables)
- Múltiples preguntas por tarea (solo la pregunta principal)
- Rúbricas de proceso
- Entrenamiento de modelos

### v1 — Más templates + más evaluación + datos más ricos

- 3 familias de templates predefinidos: latent preference, causal chain, fork/collider
- Datos más ricos: múltiples datasets por problema, múltiples formatos
- Más tipos de evaluación formal: next_best_observation, hypothesis_selection
- Múltiples preguntas/sub-evaluaciones por tarea
- Acciones más variadas (siguen mapeando a nodos bayesianos)
- Seeds desde papers o documentos (el LLM extrae estructura)
- Narrativas más elaboradas con contexto teórico y hints

### v2 — DAGs arbitrarios + variables continuas

- Template `custom`: acepta cualquier especificación de DAG, genera CPDs
- Redes bayesianas grandes (decenas de variables, relaciones complejas)
- Variables continuas (Gaussianas) además de discretas, mundos mixtos
- Seeds desde papers: LLM extrae estructura causal → template `custom`
- Evaluación causal: efecto de intervenciones (do-calculus)
- Evaluación de estructura: redescubrir el DAG
- Documentos generados por LLM con ruido controlado (papers ficticios, notas)
- Rúbricas de proceso: evaluar calidad del razonamiento, no solo la respuesta

### v3 — Escala

- Tareas multi-paso con sub-evaluaciones encadenadas
- RL loop con el verificador como señal de reward
- Herramientas externas para agentes (ejecución de código, búsqueda)
- Métricas de calibración y mejora incremental
- Currículo de complejidad creciente
- Evaluación contra benchmarks científicos reales
- Framework de rúbricas customizable

---

## Stack técnico

- **Python 3.11+**
- **pgmpy** — construcción de redes bayesianas, inferencia exacta
- **networkx** — validación y manipulación de DAGs
- **numpy / scipy** — sampling y operaciones con distribuciones
- **pydantic v2** — schemas y validación de datos
- **openai SDK** — LLM via Azure AI Foundry
- **pytest** — tests
- **ruff** — linting y formatting

---

## Cómo se ve v0 cuando esté completo

```
> "Generame un problema de investigación sobre ecología marina, dificultad media"

El sistema:
1. El orchestrator LLM elige la estructura y genera nombres/narrativa
2. Las tools construyen la red bayesiana formal
3. Se valida que el mundo sea interesante
4. Se generan datos (muestreados de la red bayesiana, presentados como
   un dataset realista o como observaciones puntuales)
5. Se definen las acciones disponibles con sus costos
6. Se formula la pregunta de investigación
7. El teacher resuelve el problema óptimamente (referencia)

Resultado: un problema de investigación completo, listo para que un
agente LLM lo intente resolver.
```

Y por separado:

```
> "Evaluá GPT-5 resolviendo estos 50 problemas"

El sistema:
1. Le presenta cada problema al LLM agent (contexto, datos, acciones)
2. El LLM agent razona libremente — analiza, hipotetiza, pide datos
3. Las acciones que pide (observaciones) cuestan budget
4. El agente da su respuesta final
5. El verificador puntúa contra la verdad matemática
6. Métricas: accuracy, eficiencia, calibración vs teacher perfecto
```
