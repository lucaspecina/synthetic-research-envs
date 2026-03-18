# SREG — Vision del Proyecto
## Synthetic Research Environment Generator

> **Este documento es la estrella polar del proyecto.** Define que es SREG,
> para que existe, que deberia lograr y que principios no pueden romperse.
> No describe implementacion, estado actual ni backlog. Para eso existen
> `ARCHITECTURE.md`, `CURRENT_STATE.md` y `TODO.md`.

---

## Mision

SREG genera **entornos sinteticos de investigacion** con **verdad formal
verificable**, diseniados para que un solver solo pueda rendir bien si
**investiga bien**.

En una frase:

**SREG genera investigaciones sinteticas con reward signals exactos.**

```text
SREG genera:    entorno (SRC) + reward signal
Otros proveen:  policy + framework de RL + loop de entrenamiento
```

No es un benchmark estatico. Es un generador de casos nuevos, donde cada seed
puede producir un entorno distinto y evaluable con rigor.

**Criterio de exito**: una policy entrenada con entornos SREG demuestra mejor
razonamiento cientifico en benchmarks externos que la misma policy sin entrenar.

---

## Que quiere lograr

El objetivo de SREG no es solo producir casos interesantes ni preguntas bien
formadas.

El objetivo es construir entornos donde la estrategia ganadora sea investigar de
una manera parecida a como investiga un cientifico real.

Eso implica que, para resolver bien un caso, el solver deberia tener que:

- interpretar evidencia parcial,
- integrar datos con contexto y material teorico,
- formular y comparar hipotesis rivales,
- decidir que medir, que analizar o que experimento conviene hacer,
- razonar bajo restricciones,
- y responder con fundamento en la evidencia del caso, no en memoria o priors.

### El caso define las reglas del juego

Cada SRC es un mundo con sus propias reglas. Es el **caso** el que define que
puede hacer el solver y bajo que condiciones: que instrumentos hay disponibles,
que tipo de experimentos se pueden proponer, que restricciones de presupuesto o
etica aplican, que fuentes de informacion existen, con que colaboradores puede
interactuar. SREG no impone una mecanica fija — el caso la diseña.

### El potencial es muy amplio

La vision de SREG no se limita a "datos tabulares + preguntas". En su maxima
expresion, un SRC podria simular muchos aspectos de una investigacion real:

- **Material teorico sintetico**: papers ficticios, hallazgos previos, teorias
  rivales — el solver tiene que hacer deep research en literatura inventada
  para descubrir pistas o descartar hipotesis.
- **Laboratorios y equipamiento simulado**: el caso define que maquinas o
  instrumentos hay disponibles, sus capacidades y limitaciones. "Tenes acceso
  a un espectrofotometro pero no a un microscopio electronico."
- **Diseno experimental**: el solver no solo elige que medir — propone
  experimentos completos dentro de reglas del caso (formulaciones, replicas,
  controles, condiciones).
- **Colaboradores simulados**: un "colega cientifico" (simulado) con quien el
  solver puede discutir hipotesis, pedir opiniones, o consultar expertise
  especifico del dominio.
- **Restricciones operativas realistas**: presupuesto limitado, tiempo,
  disponibilidad de muestras, limitaciones eticas, acceso parcial a datos.
- **Multiples fuentes contradictorias**: datos de distintas campanas que no
  coinciden, reportes con conclusiones opuestas, evidencia ambigua.
- **Ciclo iterativo**: los resultados de un experimento informan el siguiente.
  El solver gestiona una investigacion completa, no responde preguntas sueltas.

Todo esto es potencial — no todo esta implementado ni tiene que implementarse
a la vez. Pero la arquitectura debe permitirlo sin techo artificial.

La vara conceptual es esta:

> **Si el solver no tuvo que investigar como un cientifico real para llegar a
> su respuesta, el entorno fallo aunque el score final sea alto.**

---

## Que NO es SREG

- **No entrena policies.** Genera entornos y computa rewards; otros sistemas
  traen la policy y el framework de RL.
- **No es un benchmark fijo.** Cada caso debe poder ser nuevo.
- **No prescribe como razonar.** Da el entorno, las restricciones y las
  herramientas; la policy decide como proceder.
- **No depende de jueces humanos como nucleo de evaluacion.** La referencia
  central debe ser formal y verificable.
- **No busca replicar papers reales.** Los papers pueden inspirar casos, pero
  SREG debe construir mundos nuevos que controla completamente.

---

## Invariantes

### 1. Verdad formal y reward exacto

Detras de cada SRC debe existir una capa formal que permita verificar con rigor
la calidad de respuestas, decisiones y trayectorias. Hoy esa verdad es una red
bayesiana (DAG + CPDs) que permite computar reward signals exactos sin jueces
ni heuristicas. Si algo no puede evaluarse contra esa verdad subyacente, no
pertenece al nucleo de SREG.

### 2. El caso debe sentirse como investigacion real

Todo lo que diseniemos tiene que acercar el entorno a una investigacion
cientifica real, no a una mecanica de juego ni a un ejercicio abstracto
disfrazado.

> **LA PREGUNTA que guia todo el proyecto:**
> **¿Por que esto todavia no es una investigacion real? ¿Que le falta?**
>
> Esta pregunta debe estar presente en cada decision, cada evaluacion, cada
> linea de codigo. La respuesta evoluciona a medida que SREG mejora.
> Las brechas conocidas estan en `research/synthesis/sreg_scientific_coverage.md`.

Litmus test operativo: "Un investigador real en este dominio haria esto?"

### 3. Las preguntas deben forzar investigacion

Las preguntas deben depender de la evidencia de **este caso**, no solo del
conocimiento general del dominio. Si un solver puede responder sin mirar los
datos, sin integrar contexto o sin investigar, la pregunta no sirve.

Lo que mas fuerza investigacion real no es una pregunta generica, sino la
**ambiguedad mecanica**: multiples explicaciones plausibles que solo pueden
distinguirse con evidencia del episodio.

### 4. La policy tiene libertad total para razonar

SREG no debe prescribir el razonamiento interno del solver. La policy puede
analizar, programar, comparar hipotesis o usar el procedimiento que quiera. Lo
que si importa es que las acciones del caso tengan sentido investigativo y que
sus consecuencias puedan evaluarse con rigor.

### 5. El paper inspira, no se replica

Cuando un paper real o un caso real inspira un SRC, SREG extrae problematica,
estructura, tipo de investigacion y tensiones relevantes, pero construye un
mundo nuevo. El agente no debe poder resolverlo por memoria.

### 6. La capa semantica es parte del entrenamiento

La semantica no es decoracion. Afecta que tipo de shortcuts aparecen, que
razonamiento exige el caso y que tan transferible puede ser lo aprendido.

### 7. Las restricciones son parte del problema

Costo, acceso a datos, imposibilidad de ciertas intervenciones, etica, ruido,
sesgo y ambiguedad no son detalles accesorios. Son parte constitutiva de la
investigacion.

---

## Jerarquia de decision

Cuando hay conflicto entre objetivos, aplicar estas reglas en orden:

1. **Verificabilidad > realismo.** Si algo mejora el realismo pero rompe la
   capacidad de evaluar con rigor, no sirve para el nucleo de SREG.
2. **Experiencia investigativa > formalismo elegante.** Si algo mejora la
   formalizacion pero hace que el caso se sienta artificial, tampoco sirve.
3. **Forzar investigacion > facilitar respuesta.** Si un solver puede acertar
   sin investigar, el entorno esta mal disenado.
4. **El caso manda.** Las preguntas, acciones y datos deben nacer del research
   case como conjunto, no como piezas desconectadas derivadas mecanicamente.
5. **Simplicidad > complejidad vacia.** No agregar capacidad si no mejora la
   experiencia investigativa ni la calidad de evaluacion.

---

## Hacia donde va SREG

El punto de partida puede ser un entorno pequeno y controlado. El destino es un
generador de investigaciones sinteticas cada vez mas ricas, donde el solver
tenga que:

- situarse en un problema,
- trabajar con evidencia imperfecta,
- usar teoria ademas de datos,
- discriminar entre mecanismos rivales,
- decidir que acciones de investigacion valen la pena,
- y sostener conclusiones bajo restricciones y ambiguedad.

La direccion del proyecto no es "un CSV y una pregunta".

La direccion es **investigacion completa**: leer, situar, proponer, diseniar
experimentos, medir, intervenir, analizar, validar, consultar, y decidir.

A futuro, SREG deberia poder cubrir formas diversas de investigacion:
observacional, experimental, de campo, clinica, ingenieril u otras, cada una
con sus propias reglas, instrumentos, restricciones y acciones posibles.

El caso es el que define el universo del solver. Cuanto mas rico sea ese
universo — con literatura sintetica, colaboradores simulados, laboratorios
con capacidades especificas, restricciones operativas reales — mas se acerca
a lo que enfrenta un investigador real.

El resultado buscado no es solo "mas tasks". Es un entorno donde investigar
bien sea necesario, medible y transferible.

---

## Tensiones estrategicas abiertas

Estas tensiones si pertenecen a la vision del proyecto, porque afectan que tipo
de sistema estamos construyendo.

### Semantica realista vs semantica abstracta

Una semantica mas realista puede hacer que el agente razone como un cientifico
real, pero tambien puede empujarlo a usar priors del mundo real en vez de
investigar el caso. Una semantica mas abstracta reduce esa contaminacion, pero
puede volver el caso menos natural y menos transferible.

Esto no debe resolverse por gusto. Es una pregunta experimental del proyecto.

### Apertura del problema vs verificabilidad exacta

Cuanto mas abierto y ambiguo sea el caso, mas se parece a la ciencia real. Pero
cuanto mas abierto sea, mas dificil puede ser verificar con exactitud lo que
hizo el agente. SREG debe encontrar un equilibrio util entre apertura y rigor.

### Realismo investigativo vs control generativo

Los casos simples son mas faciles de generar, controlar y validar. Los casos
realistas son mas valiosos, pero tambien mas dificiles de diseniar y evaluar.
La arquitectura del proyecto debe permitir empezar simple sin fijar un techo
bajo para siempre.

---

## Ejemplo: como se ve un SRC

Un caso sobre declive en produccion de algas en un archipielago ficticio. El
solver recibe datasets de estaciones de monitoreo con datos faltantes, "estudios
previos" que sugieren hipotesis rivales, y la posibilidad de solicitar analisis
o proponer experimentos dentro de restricciones de presupuesto. Debe responder:
cual es la causa mas probable, que conviene medir, y que pasaria si se elimina
un compuesto del sedimento. Detras hay una red bayesiana — cada respuesta se
evalua matematicamente. El solver no sabe que existe la BN; solo ve un problema
de investigacion con datos y herramientas.

---

## Que no deberia contener este documento

Este documento no deberia describir:

- detalles finos de implementacion,
- estado actual del codigo,
- backlog o prioridades,
- bugs y deuda tecnica,
- resultados experimentales puntuales,
- decisiones locales todavia no estabilizadas.

Todo eso debe vivir en otros documentos.
