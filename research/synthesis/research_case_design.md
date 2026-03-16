# Principios de diseno de research cases

> Sintesis consolidada a partir de `notes/world_design_legacy.md` y
> `notes/sreg_v2_design_findings.md`.
>
> Este documento resume decisiones y aprendizajes sobre como deberia
> diseniarse un SRC para parecerse mas a una investigacion real sin perder
> evaluabilidad fuerte.

## Idea central

La unidad correcta de producto no es "un mundo formal con tasks encima".
Es un **research case**: un caso de investigacion donde mundo, evidencia,
preguntas, restricciones y acciones se disenan como conjunto.

## Principios consolidados

### 1. Mechanism-first, no graph-first

El generador no deberia empezar por "que DAG hago", sino por:

- que fenomeno quiero explicar,
- que mecanismos plausibles pueden producirlo,
- y que evidencia distinguiria entre esos mecanismos.

El DAG es la formalizacion del caso, no el punto de partida conceptual.

### 2. El caso define las reglas del juego

Cada SRC debe definir:

- que evidencia existe al inicio,
- que acciones de investigacion tienen sentido,
- que restricciones aplican,
- y que preguntas vale la pena formular.

No deberia existir una mecanica universal independiente del caso.

### 3. Las preguntas nacen del caso, no de una lista fija

La investigacion real no empieza con "responde estas 5 tasks". Empieza con un
problema, evidencia disponible e incertidumbres importantes. Las preguntas deben
desprenderse de ese research case.

### 4. Las acciones deben producir evidencia, no verdad

Una accion de investigacion bien disenada devuelve:

- datasets,
- reportes,
- observaciones nuevas,
- o resultados experimentales parciales,

no "la respuesta correcta" ni revelaciones directas del grafo.

### 5. Las restricciones son estructurales

Costo, etica, disponibilidad de muestras, acceso a instrumentos y tiempo no son
detalles cosmeticos. Son parte de lo que hace que un caso se sienta como
investigacion real.

### 6. Los casos fuertes necesitan mecanismos rivales

Un caso solo obliga a investigar si hay explicaciones plausibles que compiten y
si los datos del episodio pueden discriminar entre ellas.

## Alcance implicado para SREG

Dentro del horizonte actual de arquitectura, esto implica:

- mantener una verdad formal discreta y verificable,
- disenar `CasePlan` como capa intermedia real,
- enriquecer `ResearchProblem` con evidencia y acciones mas expresivas,
- y evitar que el caso sea solo un wrapper narrativo sobre un grafo.

## Que ya fue promovido

Las partes ya aceptadas como canon del proyecto viven ahora en:

- `PROJECT.md`
- `ARCHITECTURE.md`

Este documento existe para conservar la sintesis de research que todavia
informa decisiones futuras.
