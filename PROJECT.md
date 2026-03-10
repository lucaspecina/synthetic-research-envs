# SREG — Qué vamos a construir y cómo
## Synthetic Research Environment Generator

> **Este documento es la estrella polar del proyecto.** Define el destino final
> — qué queremos que SREG sea cuando esté completo. No describe el estado actual
> ni qué está implementado (eso está en `CURRENT_STATE.md` y `TODO.md`). Cada
> decisión técnica debe medirse contra lo que este documento describe. Si algo
> no está alineado con esta visión, hay que corregir el rumbo o actualizar la visión.

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

## Dirección final del proyecto

Es fundamental entender que los templates iniciales, los mundos pequeños y las tasks acotadas son solo el punto de partida.

La dirección final de SREG no es quedarse en problemas pequeños y estáticos, sino avanzar hacia mundos subyacentes mucho más complejos y que se parezcan, en estructura y dificultad, a problemas reales de investigación científica y técnica.

A largo plazo, los mundos formales deberían poder representar:

- muchas más variables,
- múltiples causas latentes,
- relaciones indirectas y mecanismos acoplados,
- historial temporal,
- varias fuentes de evidencia,
- ruido, datos faltantes y proxies imperfectos,
- múltiples targets,
- y acciones/intervenciones más realistas.

De igual manera, las tasks tampoco deberían quedarse en preguntas fijas y repetitivas. La visión final es que un mismo research case incluya **múltiples preguntas conectadas que nazcan del caso de investigación**, no de un template fijo. Por ejemplo:

- inferir la causa más probable (pregunta principal),
- decidir qué evidencia conviene pedir después (sub-pregunta),
- comparar hipótesis rivales (sub-pregunta),
- estimar el efecto de una intervención (sub-pregunta causal),
- y evaluar si el agente investigó de manera eficiente (evaluación de proceso).

**Las preguntas nacen del caso, no del mundo formal.** Un caso sobre
arenamiento de pozos tiene preguntas sobre mecanismos e intervenciones.
Un caso sobre un material anticorrosivo tiene preguntas sobre diagnóstico
y diseño experimental. Las preguntas son diferentes porque los casos son
diferentes. El LLM orchestrator diseña las preguntas como parte del caso,
inspirándose en la investigación real que sirvió como seed.

**El orchestrator diseña el caso completo**, no solo el mundo. El flujo
no es `world → tasks`, sino:

```
real case seed → orchestrator diseña el research case
              → tools construyen el mundo formal que lo soporta
```

El orchestrator puede partir de un paper o investigación real y extraer:
fenómeno, variables, hipótesis, evidencia, preguntas, subtasks, y tipo
de validación. Con eso diseña un caso sintético nuevo. Y recién ahí los
tools construyen el BN formal que hace ese caso verificable.

**Las tasks, subtasks y evaluaciones están ligadas al research case,
no solo al DAG subyacente.** El DAG sigue siendo clave como estructura
de verdad y validación, pero no es la única fuente de qué preguntas hacer.

En otras palabras: todo el diseño de SREG debe apuntar hacia ese destino final.
Los templates fijos, la semántica inicial y las evaluaciones actuales son una base controlada para comenzar, pero la arquitectura debe construirse desde el principio pensando en research cases cada vez más ricos, multi-step, multi-task y más cercanos a problemas de investigación del mundo real.

**Importante**: las versiones tempranas simplifican el problema para poder construir un núcleo sólido y verificable. Pero el objetivo final del roadmap es llegar a research cases mucho más complejos, con mundos subyacentes más ricos, múltiples preguntas por caso y tareas más parecidas a investigaciones reales.

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

| Template | Estructura | Tipo de razonamiento |
|---|---|---|
| `latent_preference` | Estrella: 1 latente → N observables → 1 target | Diagnóstico (inferir causa desde síntomas) |
| `causal_chain` | Cadena: A → B → C → ... → target | Propagación (seguir la cadena causal) |
| `fork_collider` | Forks y colliders mezclados | Causal puro (confounders, explaining away) |
| `custom` | **Cualquier DAG arbitrario** | Depende de la estructura |

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

> **Para la estrategia detallada de cómo pasar de mundos de juguete a mundos
> realistas** — incluyendo la progresión de etapas, el diseño mechanism-first,
> los contratos MechanismSpec/DAGSpec, quality gates, y las conclusiones de
> investigación sobre proyectos similares — ver **`WORLD_DESIGN.md`**.

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
y corresponde a observar o intervenir en nodos de la red bayesiana.

**Observar vs intervenir**: hay una diferencia fundamental entre ver lo que ya
existe (observación) y cambiar algo para ver qué pasa (intervención). Observar
`water_temperature` revela su valor sin modificar el mundo. Intervenir en
`water_temperature` (fijarla en "alta") rompe las causas naturales de esa
variable y permite estimar efectos causales. Esta distinción es central en la
teoría causal (Pearl's do-calculus) y se refleja en los tipos de acción.

### Las acciones se definen por caso

Qué puede hacer el agente, cuánto cuesta cada cosa, y qué restricciones tiene
se define como parte del research case — no como una lista genérica. Cada caso
tiene acciones que hacen sentido para su contexto de investigación:
- Un caso de ecología puede ofrecer "tomar muestras de suelo" o "analizar pH"
- Un caso de epidemiología puede ofrecer "consultar registros hospitalarios"
- Un caso de materiales puede ofrecer "ensayo de adherencia" o "análisis de
  microdefectos"

Las acciones tienen **tipos formales fijos** (observar, intervenir, solicitar
dataset, consultar fuente) pero **instancias concretas** diseñadas por el
orchestrator para cada caso. Paralelo con los eval types: los tipos son fijos,
las preguntas son específicas del caso.

Guía: **4-8 acciones por caso** — suficientes para que haya decisiones
interesantes, pocas para que no sea abrumador.

> **Para el diseño detallado de acciones de investigación** — paradigmas de
> investigación, tipos de acción, co-diseño con preguntas y evidencia,
> principios y ejemplos — ver la sección "Diseño de acciones de investigación"
> en **`WORLD_DESIGN.md`**.

---

## Cómo se genera un research case — el pipeline

### Seed (input)

El sistema recibe una semilla para crear el caso. Puede ser:
- **Un paper o investigación real** (lo más potente): el orchestrator lee
  el paper, entiende qué variables había, qué se investigó, qué preguntas
  se hicieron, y diseña un caso sintético inspirado en él
- Un escenario narrativo: "hay un problema con la producción de X..."
- Un tema: "epidemiología", "ecología marina", "materiales"
- Parámetros técnicos: "6 nodos, dificultad media"
- Nada (generación libre)

**Paper-seeded cases**: cuando el seed es un paper real, el orchestrator
extrae la estructura causal, las variables, los datos disponibles, y las
preguntas de investigación. Luego genera un caso sintético inspirado en
él: las variables son similares pero en un contexto ficticio, las relaciones
causales PUEDEN diferir del paper real (el agente no puede memorizar la
respuesta), y los datos son frescos (sampleados del BN, no del paper).
Las preguntas del caso se inspiran en las preguntas reales del paper.

### Generación (LLM orchestrator + tools)

El orchestrator no solo genera el mundo — **diseña el caso completo**:

1. **El LLM orchestrator entiende el seed** y decide qué tipo de caso crear
2. **El LLM propone la estructura causal** (variables, relaciones, tipos)
3. **WorldGenTool** construye la red bayesiana (DAG + CPDs) — programático
4. **WorldCheckTool** valida que el mundo sea interesante y no trivial
5. Si falla, el LLM ajusta parámetros y reintenta
6. **El LLM genera la capa semántica**: nombres, narrativa, descripción
7. **El LLM diseña el research case**: pregunta principal, sub-preguntas,
   qué tipo de evaluación para cada una, qué datos presenta, qué acciones
   ofrece, con qué costos
8. **Los tools validan cada pregunta**: que tenga respuesta computable desde
   el BN, que la evaluación no sea trivial
9. **Se arma el ResearchCase** con todo empaquetado

**Principio clave: el orchestrator propone, los tools validan.** El LLM
tiene libertad creativa para diseñar el caso, pero cada pregunta debe
tener una respuesta verificable matemáticamente desde la red bayesiana.
El LLM nunca toca los números — propone estructura, semántica, y preguntas.

**Co-diseño de preguntas, acciones y evidencia.** Las preguntas, las acciones
disponibles y los datos iniciales no se diseñan por separado — se diseñan
juntos para que el caso sea coherente. Si una pregunta es "¿cuál es el efecto
causal de X sobre Y?", debe existir una acción de intervención sobre X. Si
se presenta un dataset con 5 variables, las acciones deben dar acceso a las
que faltan. La evidencia inicial no debe regalar la respuesta, y las acciones
deben poder cambiar la incertidumbre del agente de manera significativa.

### Validación

- DAG válido (acíclico)
- Entropía adecuada (ni trivial ni imposible)
- D-separaciones no triviales
- El teacher solver puede resolverlo
- Cada pregunta del caso tiene respuesta computable desde el BN
- Las evaluaciones no son triviales (NBO no degenerada, hipótesis distinguibles)

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
**cualquier pregunta que se pueda responder desde el BN puede convertirse en
una evaluación**. Esto abre un espacio enorme de evaluaciones posibles —
las que se listan acá son ejemplos ilustrativos, no una lista cerrada.

A medida que el sistema evolucione, se pueden agregar nuevos tipos de
evaluación, combinar evaluaciones formales con semánticas, crear
evaluaciones específicas para ciertos dominios, o inventar métricas
nuevas. Lo único que se necesita es que la pregunta tenga una respuesta
computable desde la red bayesiana.

### Evaluaciones formales (automáticas, exactas)

Se calculan **directamente de la matemática del BN**. No necesitan LLM
judge ni humano. La respuesta correcta se computa con certeza y la
comparación es objetiva.

Funcionan con **cualquier template** — la ground truth viene del BN formal,
no de la forma del grafo. Algunos ejemplos del tipo de preguntas que se
pueden evaluar formalmente:

| Tipo de evaluación | Pregunta | Cómo se evalúa |
|---|---|---|
| **Inferir target** | ¿Cuál es P(target \| evidencia)? | KL divergence entre la predicción del agente y la posterior exacta |
| **Mejor próxima acción** | ¿Qué variable conviene medir? | Information gain de la acción elegida vs la óptima |
| **Selección de hipótesis** | De estas explicaciones, ¿cuál es más plausible? | ¿Eligió la hipótesis con mayor probabilidad posterior? |
| **Efecto causal** | Si intervenimos en X, ¿qué pasa con Y? | Diferencia con P(Y \| do(X=x)) calculada desde el DAG |
| **Descubrimiento de estructura** | ¿Cuál es el DAG real? | Structural Hamming Distance, edge F1 |
| **Predicción** | Dado lo observado, ¿qué valor tendrá Z? | Accuracy, calibración, Brier score |
| **Optimización** | ¿Qué acción maximiza/minimiza un outcome? | Regret respecto al óptimo calculado desde el BN |

Pero estos son solo ejemplos. Cualquier pregunta que tenga respuesta
computable desde el BN puede ser una evaluación formal — incluyendo
combinaciones de las anteriores, evaluaciones condicionales ("si ya hiciste
X, ¿cuánto mejora tu estimación?"), evaluaciones secuenciales, etc.

### Evaluaciones semánticas (soft, requieren juez)

Evalúan la **calidad del razonamiento**, no solo la respuesta final.
Son más difíciles de automatizar y menos precisas, pero capturan aspectos
que las formales no pueden. Algunos ejemplos:

- **Coherencia del razonamiento**: ¿el argumento tiene sentido? (rúbrica + LLM-as-judge)
- **Uso de evidencia**: ¿actualizó creencias al recibir datos nuevos? (comparar trayectoria vs teacher)
- **Consideración de alternativas**: ¿exploró hipótesis distintas?
- **Eficiencia de budget**: ¿pidió las observaciones más útiles? (info acumulada vs budget gastado)

Algunas de estas se pueden **aproximar formalmente** comparando la trayectoria
del agente con la del teacher óptimo. Otras requieren LLM-judge o rúbricas.
Y al igual que las formales, no son una lista cerrada — se pueden diseñar
evaluaciones semánticas nuevas según el dominio o el tipo de razonamiento
que se quiera medir.

### Múltiples evaluaciones por caso (ResearchCase)

Un research case completo tiene una pregunta principal y sub-preguntas.
**Las preguntas las diseña el orchestrator** según el caso, no un template fijo.
Cada pregunta tiene un tipo de evaluación del catálogo (extensible):

```
ResearchCase: Declive de producción de algas en Nelvara

Pregunta principal: ¿Cuál es la causa más probable del declive?
  → infer_target, scored por KL divergence, weight=0.5

Sub-pregunta 1: ¿Qué medición adicional sería más informativa?
  → next_best_obs, scored por info gain ratio, weight=0.2

Sub-pregunta 2: Si eliminamos el compuesto del sedimento, ¿se recupera?
  → causal_effect, scored por diferencia con P(Y | do(X)), weight=0.2

Sub-evaluación: Calidad del proceso investigativo
  → efficiency, scored por info acumulada vs budget gastado, weight=0.1

Budget compartido: 5 unidades para todo el caso
Score compuesto: weighted sum de los scores individuales
```

No todos los casos tienen las mismas preguntas. Un caso con estructura de
collider puede generar preguntas causales. Un caso con cadena larga puede
enfocarse en predicción y estrategia de medición. **El orchestrator decide
qué preguntas son interesantes para cada caso**, los tools verifican que
cada pregunta sea computable y no trivial.

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

## Dos ejemplos concretos

### Ejemplo 1 - Arenamiento de pozos de petróleo tras frac hits

Imaginemos un research case inspirado en un problema petrolero real.

**Contexto**  
En una cuenca no convencional, ciertos pozos muestran episodios de arenamiento después de frac hits en pozos vecinos. El equipo quiere entender:
- Qué mecanismos explican mejor el arenamiento.
- Qué variables conviene analizar para reducir incertidumbre.
- Qué intervención podría reducir el problema en futuros eventos.

**Mundo oculto formal**  
Debajo del caso visible, SREG define un mundo probabilístico con variables como:
- Intensidad del frac hit en pozos vecinos.
- Presión de fondo.
- Configuración de completación.
- Tipo de arena / formación.
- Integridad del pack.
- Historial de producción.
- Geometría del pozo.
- Cambios de drawdown.
- Entrada de finos.
- Severidad del arenamiento.

Algunas variables son observables directamente.  
Otras son latentes o solo accesibles mediante proxies.  
Puede haber historial temporal: antes del frac hit, durante el evento, después del evento.

La verdad del caso no es “una ecuación inventada a mano” sino una estructura probabilística completa que define cómo se relacionan esas variables.

**Evidencia visible para el agente**  
El agente podría recibir:
- Historial de producción por pozo.
- Presión y caudal en distintas ventanas temporales.
- Eventos operativos.
- Registros de frac hits.
- Características de completación.
- Observaciones de arena producida.
- Datos faltantes en algunos pozos.
- Y contexto técnico narrativo.

**Acciones posibles**  
Con budget limitado, el agente podría pedir cosas como:
- Revisar historial de un pozo vecino.
- Solicitar análisis granulométrico.
- Comparar eventos antes/después del frac hit.
- Pedir un diagnóstico adicional sobre integridad del completamiento.
- Consultar una serie temporal más larga de presión.

Cada acción revela evidencia nueva y consume costo.

**Preguntas dentro del mismo caso**  
Un mismo case podría incluir:
- Pregunta principal: ¿cuál es el mecanismo más probable del arenamiento?
- Task estratégica: ¿qué dato adicional conviene pedir ahora?
- Task causal: si redujéramos el drawdown después del frac hit, ¿bajaría la probabilidad de arenamiento?
- Task de comparación: ¿qué hipótesis explica mejor las diferencias entre pozos afectados y no afectados?

**Qué testea este caso**  
Este tipo de caso ya no testea solo inferencia simple. Testea:
- Razonamiento con muchas variables.
- Evidencia histórica.
- Múltiples hipótesis plausibles.
- Decisiones de adquisición de información.
- Y evaluación de intervenciones.

Es mucho más parecido a una investigación técnica real que a una task aislada.

### Ejemplo 2 - Falla inesperada en un nuevo material anticorrosivo

**Contexto**  
Un laboratorio está desarrollando un recubrimiento anticorrosivo para uso marino. En ensayos acelerados, algunas muestras muestran degradación temprana, pero no está claro cuál es la causa principal. El equipo quiere entender:
- Qué mecanismo explica la falla.
- Qué modificación experimental convendría probar.

**Mundo oculto formal**  
El mundo subyacente puede incluir variables como:
- Composición del recubrimiento.
- Espesor de capa.
- Temperatura de curado.
- Humedad del proceso.
- Adhesión al sustrato.
- Presencia de microdefectos.
- Exposición salina.
- Formación de grietas.
- Severidad de corrosión observada.

Algunas variables son latentes, como microdefectos internos o tensiones residuales, que no se observan directamente.

**Evidencia visible para el agente**  
El agente podría recibir:
- Tablas de ensayos de distintas formulaciones.
- Resultados de cámaras salinas.
- Micrografías resumidas como metadata.
- Historial de lote y curado.
- Resultados parciales de adherencia.
- Observaciones contradictorias entre distintos ensayos.

**Acciones posibles**  
Con budget limitado, el agente podría:
- Pedir un ensayo adicional de adherencia.
- Consultar una medición de espesor no disponible.
- Comparar lotes con distinta temperatura de curado.
- Solicitar un análisis de microdefectos.
- Simular una modificación de formulación.

**Preguntas dentro del caso**  
Un mismo caso podría incluir:
- ¿Cuál es la causa más probable de la degradación temprana?
- ¿Qué ensayo convendría hacer ahora para maximizar información?
- ¿Qué modificación del proceso tendría más probabilidad de mejorar el material?
- ¿Cuál de varias hipótesis mecanísticas explica mejor los resultados observados?

**Qué testea este caso**  
Este caso testea:
- Diagnóstico de tipo mechanistic-style.
- Selección de evidencia útil.
- Comparación de explicaciones rivales.
- Elección de una intervención experimental.

---

## Qué NO es SREG

- **No es el agente que resuelve.** Es el gimnasio donde se entrena.
- **No es un benchmark estático.** Es un generador que produce infinitos problemas.
- **No entrena LLMs.** Genera los mundos, tareas, y datos. Si alguien quiere
  usar eso para entrenar, tiene todo listo.
- **No prescribe cómo debe razonar el agente.** Solo le da el problema y las
  acciones disponibles. El agente decide cómo proceder.

---

## Evolución del proyecto

Las versiones se alinean con las tres etapas de evolución de mundos
descritas en `WORLD_DESIGN.md`. Cada una amplía la complejidad de los
mundos que el sistema puede generar y la riqueza de las evaluaciones.

### v0+v1 — Motor formal + templates curados (completo)

El motor formal produce mundos con verdad matemática verificable. Tres
familias de templates (latent_preference, causal_chain, fork_collider),
tres tipos de evaluación (inferencia, NBO, hipótesis), multi-task
bundles, agente LLM, teacher solver, y harness de evaluación. El
sistema genera, resuelve, y evalúa end-to-end.

Corresponde a la **Etapa 1** de WORLD_DESIGN.md: motifs curados.

### v2 — Composición controlada + research cases (en curso)

DAGs arbitrarios via `DAGSpec`, composición de motifs, datos más ricos
(múltiples datasets, datos parciales, narrativas). El cambio más importante:
**el orchestrator pasa de generar solo el mundo a diseñar el research case
completo** — elige qué preguntas hacer, qué evaluaciones usar, qué datos
presentar. `ResearchCase` como generalización de `TaskBundle`. Acciones
con costos variados. Mundos de 10-25 nodos con múltiples latentes.
Paper-seeded cases como input más potente.

Corresponde a la **Etapa 2** de WORLD_DESIGN.md: composición controlada.
Ver también "Diseño de Research Cases" en WORLD_DESIGN.md.

### v3 — Mechanism-first + evaluación profunda

Diseño mechanism-first: `MechanismSpec` como contrato de entrada,
librería de mecanismos reutilizables, `WorldComposer` que combina
mecanismos en mundos. Hipótesis rivales como mecanismos competidores.
Evaluación de intervenciones (do-calculus). Descubrimiento de estructura.

Corresponde a la **Etapa 3** de WORLD_DESIGN.md: diseño mechanism-first.

### Backlog

Variables continuas y mixtas. Documentos sintéticos (papers ficticios,
reportes). Rúbricas de proceso (evaluar razonamiento, no solo respuesta).
Currículo de complejidad. RL loop con verificador como reward.
Herramientas externas para agentes.

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

