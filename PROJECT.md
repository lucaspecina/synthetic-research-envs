# SREG — Qué vamos a construir y cómo
## Synthetic Research Environment Generator

## La idea en una oración

Vamos a construir una **fábrica de mundos ficticios** donde un agente LLM puede investigar, recolectar evidencia, y tomar decisiones — y nosotros sabemos exactamente cuál era la respuesta correcta, así que podemos medir qué tan bien razona.

---

## Pensalo así

Imaginá que sos profesor de medicina y querés evaluar si tus alumnos saben diagnosticar. Tenés dos opciones:

**Opción A**: Les das casos reales. Problema: un alumno que se memorizó el libro de patología puede acertar sin entender realmente el razonamiento clínico.

**Opción B**: Inventás una enfermedad ficticia con síntomas ficticios, pero con una lógica interna perfectamente consistente. Le das al alumno síntomas parciales y lo dejás pedir estudios adicionales. Como la enfermedad no existe, no puede haberla memorizado — si llega al diagnóstico correcto, es porque **razonó bien**.

SREG es la Opción B, pero para LLMs y razonamiento científico.

---

## Qué construye SREG exactamente

SREG genera **mundos** — pequeños universos ficticios con reglas causales internas. Cada mundo tiene:

- **Variables** (algunas visibles, otras ocultas)
- **Relaciones causales** entre ellas (un grafo dirigido — un DAG)
- **Probabilidades** que definen cómo una variable influye en otra
- **Un target**: algo que el agente tiene que descubrir

Un ejemplo concreto de un mundo:

```
Mundo: "Cristalografía energética en el planeta Zephyr"

Variables:
  - resonance_field (oculta) → alta / baja
  - thermal_flux (observable) → baja / media / alta
  - crystal_growth (target) → lento / medio / rápido
  - growth_inhibitor (observable) → presente / ausente

Relaciones:
  resonance_field → thermal_flux
  resonance_field → crystal_growth
  growth_inhibitor → crystal_growth

La pregunta para el agente:
  "Dado lo que podés observar, ¿cuál es la probabilidad
   de que crystal_growth sea rápido?"
```

Nada de esto es real. Pero la matemática detrás (las probabilidades, las relaciones) es precisa y permite calcular la respuesta correcta exacta. No hace falta un humano ni otro LLM para evaluar — es pura matemática.

---

## Por qué los mundos son ficticios a propósito

Si el mundo fuera sobre química real, un LLM podría responder correctamente porque tiene química memorizada de su entrenamiento. No estaría razonando — estaría haciendo recall.

Con mundos ficticios, la única forma de acertar es **razonar con la evidencia que te dan**. Si un modelo entrenado en mundos ficticios después funciona bien en problemas reales, eso prueba que aprendió a razonar, no a memorizar.

---

## Qué NO es SREG

- **No es el agente que resuelve.** Es el gimnasio donde se entrena. Nosotros construimos las pesas, no al atleta.
- **No es un benchmark estático.** No son 500 preguntas fijas. Es un generador que puede producir infinitos mundos distintos.
- **No es un entrenamiento de LLMs.** Eso puede venir después. Nosotros generamos los mundos, las tareas, y los datos. Si alguien quiere usar eso para entrenar, tiene todo listo.

---

## Cómo funciona paso a paso

### Paso 1: Se genera un mundo oculto

Un LLM orquestador (pensalo como un "director creativo") le pide a herramientas programáticas que construyan un mundo. El LLM decide cosas como "quiero 7 variables, dificultad media, dominio: biología marina ficticia". Las herramientas construyen el DAG, asignan las probabilidades, y validan que todo sea consistente.

El LLM **nunca toca los números**. Solo propone la estructura y los nombres. La matemática la hace el código.

### Paso 2: Se valida que el mundo sea interesante

Una herramienta de validación verifica que el mundo no sea trivial (respuesta obvia) ni imposible (sin suficiente información para resolver). Si no pasa, el orquestador ajusta parámetros y regenera.

### Paso 3: Se genera evidencia

Del mundo se samplea evidencia: datos tabulares, observaciones parciales. Esto es lo que el agente va a poder ver.

### Paso 4: Se generan tareas

Del mundo se derivan preguntas verificables. Por ejemplo:
- "¿Cuál es la distribución de probabilidad del target dado lo que observaste?" (respuesta correcta: cálculo bayesiano exacto)
- "¿Qué variable conviene observar ahora para maximizar lo que aprendés?" (respuesta correcta: la que maximiza information gain)

### Paso 5: Un agente interactúa con el entorno

El agente (un LLM) ve la descripción del mundo, la tarea, y la evidencia inicial. Puede pedir observar variables (cada una tiene un costo) dentro de un presupuesto limitado. Al final, da su respuesta.

### Paso 6: Se evalúa automáticamente

El verificador compara la respuesta del agente contra la verdad matemática del mundo oculto. Puntaje objetivo, sin jueces humanos ni LLMs.

---

## El Teacher Solver — el "jugador perfecto"

El teacher es un motor bayesiano exacto (no es un LLM, es puro código) que juega cada episodio de forma óptima:

- Siempre elige observar la variable que más información le da
- Siempre mantiene la distribución de probabilidad exacta dado lo que vio
- Siempre da la respuesta correcta al final

¿Para qué sirve?

1. **Para validar mundos**: si el teacher no puede resolver un mundo con buena accuracy, el mundo está mal diseñado.
2. **Para tener una línea base perfecta**: podemos comparar cualquier agente contra "lo mejor posible".
3. **Para generar trayectorias óptimas**: el teacher produce secuencias de (estado → acción → resultado) que muestran cómo se ve el razonamiento perfecto paso a paso. Esas trayectorias son un producto valioso del sistema — alguien podría usarlas después para fine-tuning, pero eso ya no es nuestro problema.

---

## Versiones del proyecto

### v0 — El motor que funciona

El objetivo de v0 es tener un sistema end-to-end funcional: generar mundos, generar tareas, correr un agente, puntuar.

**Lo que incluye v0:**

- Generación de mundos con DAGs probabilísticos (usando pgmpy)
- 3 familias de templates: latent preference, causal chain, fork/collider
- 2 tipos de tareas: inferir el target + elegir la mejor próxima observación
- Generación de evidencia: datos tabulares + observaciones secuenciales
- Teacher solver (bayesiano exacto) que resuelve cada mundo óptimamente
- Interfaz de interacción por JSON para agentes LLM
- Verificador/scorer automático (KL divergence, information gain)
- LLM orquestador que llama a las herramientas para generar mundos
- Evaluación baseline: correr un LLM sin fine-tuning para ver cómo le va
- Exportación de trayectorias del teacher como dataset

**Lo que NO incluye v0:**

- Documentos sintéticos (papers ficticios, reportes)
- Intervenciones (do-calculus)
- Descubrimiento de estructura (proponer el grafo)
- Entrenamiento de modelos (SFT, RL)
- Dominios científicos reales
- Búsqueda web u otras herramientas para agentes

### v1 — Mundos más ricos

- Documentos sintéticos simples (generados con templates, no free-form)
- Tareas de intervención: "si forzás X a este valor, ¿qué pasa con Y?"
- Tareas de descubrimiento de estructura: el agente propone las relaciones
- Mundos más grandes (10-20 nodos, con inferencia aproximada)
- Más familias de templates

### v2 — Hacia investigación real

- Documentos generados por LLM con ruido controlado
- Tareas multi-paso: leer docs + consultar datos + proponer hipótesis + testearla
- Evaluación de transferencia: entrenar en template A, testear en template B
- Currículo de complejidad creciente

### v3 — Escala

- RL loop con el verificador como señal de reward
- Herramientas externas disponibles para agentes (búsqueda web)
- Currículo completo
- Evaluación contra benchmarks científicos reales

---

## Cómo se implementa v0 — el plan paso a paso

### Fase 1: Contratos y estructuras de datos

Antes de escribir una línea de lógica, definimos todos los tipos de datos:
- World, Node, Edge, CPD (el mundo y sus componentes)
- Episode, Action, StepResult (la interacción)
- Task, TaskSpec (las tareas)
- Score (los resultados)
- Schemas JSON para inputs/outputs de todas las herramientas

Esto es lo primero porque todo lo demás depende de que estas interfaces estén estables.

### Fase 2: Generación y validación de mundos

Implementar la generación de mundos para un template (latent preference).
- Construir DAGs válidos con pgmpy
- Asignar probabilidades condicionales
- Validar que la dificultad sea la deseada

Prueba: generar 100 mundos, verificar que todos tienen DAGs válidos y dificultad variable.

### Fase 3: Teacher solver

El motor bayesiano exacto que resuelve mundos.
- Inferencia exacta con pgmpy (VariableElimination)
- Cálculo de information gain para cada observación posible
- Generación de la trayectoria óptima completa

Prueba: el teacher llega a >90% accuracy después de un episodio completo.

### Fase 4: Episodios, tareas y verificador

Conectar todo: generar episodios, formular tareas, correr el teacher como agente, verificar los scores.

Prueba: un episodio end-to-end funciona y el scoring da resultados coherentes.

### Fase 5: LLM Orquestador

Conectar un LLM (vía Anthropic API) como orquestador que llama a las herramientas.
- El LLM propone mundos
- Inspecciona la validación
- Ajusta parámetros si el mundo no pasa
- Converge en 1-3 iteraciones

Prueba: el orquestador genera un mundo, rechaza uno trivial, y converge.

### Fase 6: Más templates y más tareas

Agregar causal chain y fork/collider como templates.
Agregar next_best_observation como tipo de tarea.

Prueba: el mismo mundo puede generar ambos tipos de tarea.

### Fase 7: Dataset y evaluación baseline

- Generar trayectorias del teacher y exportarlas como dataset
- Correr un LLM sin fine-tuning por los episodios
- Medir su performance como baseline

---

## El stack técnico

- **Python 3.11+**
- **pgmpy** — construcción de redes bayesianas, inferencia exacta
- **networkx** — validación y manipulación de DAGs
- **numpy / scipy** — sampling y operaciones con distribuciones
- **pydantic** — schemas y validación de datos
- **anthropic SDK** — para el LLM orquestador
- **pytest** — tests desde el día uno

---

## Cómo se ve el resultado final de v0

Cuando v0 esté completo, vas a poder hacer esto:

```
> "Generame 50 mundos de dificultad media sobre distintos dominios ficticios"

El sistema:
1. El orquestador LLM genera 50 especificaciones de mundos
2. Las herramientas construyen cada mundo (DAG + probabilidades)
3. Se valida cada mundo (descarta los triviales o imposibles)
4. Se generan episodios con evidencia parcial
5. Se generan tareas verificables para cada mundo
6. El teacher resuelve cada episodio óptimamente
7. Se exporta todo: mundos, episodios, tareas, trayectorias del teacher, scores

Resultado: un dataset listo con miles de episodios donde sabés
exactamente cuál era la respuesta correcta en cada paso.
```

Y por separado, podés correr cualquier LLM como agente:

```
> "Evaluá GPT-4 en estos 50 mundos"

El sistema:
1. Le presenta cada episodio al LLM
2. El LLM decide qué observar y da sus respuestas
3. El verificador puntúa automáticamente
4. Obtenés métricas: accuracy, eficiencia, calibración
```

---

## Preguntas que deberías hacerme

- ¿Tiene sentido la división en fases?
- ¿Falta algo que te parezca importante en v0?
- ¿Hay algo que te parezca que sobra en v0?
- ¿Los 3 templates son los correctos o preferís otros?
- ¿Te interesa que hypothesis_selection sea un tercer tipo de tarea en v0?
- ¿Querés que el orquestador use Claude (Anthropic) o preferís que sea agnóstico al proveedor?
