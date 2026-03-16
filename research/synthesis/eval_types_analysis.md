# Analisis de eval types y taxonomia cientifica

> Sintesis consolidada a partir de `notes/scientific_taxonomy.md`,
> `notes/solver_trajectory_findings.md` y `notes/sreg_v2_design_findings.md`.

## Pregunta central

Que tipos de preguntas obligan realmente a investigar y cuales se pueden
resolver por shortcut, prior o conocimiento de dominio?

## Hallazgo principal

No todos los tipos de pregunta fuerzan investigacion por igual.

En particular:

- las preguntas descriptivas y de estimacion suelen obligar a mirar datos,
- las preguntas causales estructurales genericas suelen poder responderse desde
  priors o conocimiento del dominio,
- y las preguntas mas interesantes son las que exigen distinguir entre
  mecanismos rivales usando evidencia del episodio.

## Tipos que naturalmente fuerzan investigacion

- **Descriptive / measurement**
- **Validation / robustness**
- **Heterogeneity / boundary conditions**
- **Decision / optimization**, cuando el contexto especifico importa

Estos tipos suelen depender del dataset, del caso o del analisis concreto.

## Tipos que requieren diseno cuidadoso

- **Explanatory / causal**
- **Predictive**

No alcanzan por si solos. Para forzar investigacion necesitan:

- preguntas episodio-especificas,
- ambiguedad mecanistica real,
- y respuestas que dependan de evidencia del caso, no de invariantes del tipo
  de mundo.

## Tipos debiles para el horizonte actual

- **Theoretical**
- **Methodological**
- **Synthesis**
- **Design / engineering** en su forma mas abierta

No son imposibles, pero hoy quedan fuera del foco principal del sistema.

## Implicaciones para SREG

### 1. Pasar de graph-indexed a data-indexed

La pregunta no deberia ser solo "que dice el grafo?" sino "que muestra este
dataset o esta evidencia sobre este caso?".

### 2. Favorecer preguntas discriminativas

Las mejores preguntas no piden una afirmacion causal generica. Piden distinguir
entre explicaciones plausibles, comparar especificaciones o justificar por que
una lectura de los datos es mejor que otra.

### 3. Mantener la taxonomia como backend, no como interfaz

La taxonomia cientifica sirve para disenar casos, no para exponersela al agente
como si fueran botones de benchmark.

## Resumen operativo

La superficie de evaluacion de SREG deberia seguir creciendo, pero con esta
regla:

> un eval type nuevo vale la pena solo si obliga mas a investigar y menos a
> responder por priors o por estructura generica.
