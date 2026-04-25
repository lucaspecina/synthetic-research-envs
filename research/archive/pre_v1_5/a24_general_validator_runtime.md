# A24 — Un solo metodo general: de AtomicSpec a validator programs restringidos

**Date:** 2026-03-30
**Type:** Arquitectura / principio de scoring
**Branch:** autoresearch-open-investigation
**Status:** DISCUSION ABIERTA. No implementado. No reemplaza A23 como siguiente paso inmediato.
**Prerequisitos:** PROJECT invariants, A23, S04, taxonomia de investigacion

> **Pregunta central:** si SREG debe usar **un solo metodo general de scoring**
> para todos los tipos de investigacion, alcanza con compilar todo a
> `AtomicSpec`, o el target final deberia ser algo mas general: validadores
> ocultos ejecutables sobre un runtime comun?

## Lo que SI esta fijado por proyecto

Esto no esta abierto a interpretacion. Los docs principales ya lo fijan:

- **CLAUDE.md**: "UN solo metodo para todo — sin scoring profiles por tipo de
  investigacion."
- **PROJECT.md**: "UN solo metodo de scoring para todo" y "El sistema se adapta
  a los casos, no al reves."
- **PROJECT.md**: el brief puede ser libre, vago, concreto, multi-objetivo,
  predictivo, descriptivo, causal, epistemologico, de optimizacion, etc.

### Consecuencia

**NO** es aceptable resolver diversidad diciendo:

- "para casos causales usamos un scorer"
- "para casos predictivos otro"
- "para capacidades otro"

Eso violaria una de las premisas mas centrales del proyecto.

La taxonomia puede distinguir casos para:

- coverage audit,
- seed design,
- generacion de benchmarks diversos,
- analisis de failure modes,

pero **no** para bifurcar el metodo de scoring.

## A23 sigue siendo correcto como siguiente paso

A23 ya mostro el bottleneck inmediato:

- SQ y claims pasan por catalogos demasiado estrechos;
- el sesgo a causal simple entra antes del verifier;
- la gramatica atomica ya es mas expresiva que la IR actual;
- ir mas directo a `AtomicSpec` recupera semantica perdida.

Por eso, **en el corto plazo**, la direccion correcta sigue siendo:

1. SQ grammar-first
2. claims con compilacion mas directa a atoms
3. menos dependencia del catalogo fijo

Este documento NO invalida A23. Lo extiende.

## El problema mas profundo

Aunque A23 corrige el sesgo del catalogo, queda una pregunta mas general:

> Hay tipos de investigacion donde el solver no solo "descubre una relacion",
> sino que **entrega un artefacto** o construye un sistema:
> predicciones, rankings, policies, disenos, propuestas operativas, etc.

Ejemplos:

- un caso predictivo puro donde el objetivo es maximizar AUC en un hidden set
- un caso de optimizacion donde hay que elegir una policy bajo constraints
- un caso de diseno experimental donde hay que proponer el experimento mas
  informativo

En esos casos, el solver no esta solo diciendo:

- "X afecta Y"

Tambien puede estar haciendo algo como:

- "aca estan mis risk scores"
- "aca esta mi ranking de prioridad"
- "aca esta la policy que maximiza reward"

## Donde `AtomicSpec` alcanza y donde no

### Donde SI alcanza bien

`AtomicSpec` actual es muy bueno para validar afirmaciones sobre el mundo:

- asociaciones
- efectos causales
- heterogeneidad
- mediacion
- identificabilidad
- rankings de influencia
- comparaciones sobre quantities del SCM

En ese sentido, `AtomicSpec` ya es una especie de mini-programa declarativo:

- corre brazos/queries
- mide algo
- compara
- afirma una condicion

### Donde puede quedar corto

Cuando el objeto a evaluar no es solo una "teoria" o "claim sobre el mundo",
`AtomicSpec` actual puede quedarse corto.

Casos problematicos:

- scoring de predicciones en private/test set
- calibration de probabilidades
- metricas tipo ROC-AUC, PR-AUC, Brier, top-k recall
- evaluacion de una policy o decision rule
- optimizacion bajo restricciones
- quality-of-design de un experimento propuesto

No porque sean "otro tipo de investigacion" en el sentido de scoring profile,
sino porque el objeto evaluado es distinto:

- a veces es una claim;
- a veces es un artefacto ejecutable o una submission.

## La distincion importante NO es "tipo de investigacion"

La distincion util NO deberia ser:

- conocimiento vs capacidad
- causal vs predictivo
- ciencia vs ingenieria

porque eso nos empuja de vuelta a clasificar y bifurcar.

La distincion mas generalizable parece ser otra:

- **que entrega el solver**
- **y que programa oculto valida si esa entrega cumple el objetivo del caso**

Eso unifica mejor todo.

## Propuesta conceptual: runtime comun de validacion

En vez de pensar que el target final del compiler es siempre un `AtomicSpec`,
pensar en algo mas general:

- **hidden validator programs** ejecutados sobre un runtime comun.

Ese runtime comun seria el unico mecanismo de scoring.

### Idea central

Cada caso define:

- que entrega puede hacer el solver (`claim`, `prediction`, `ranking`,
  `policy`, `design`, etc.)
- y que validadores ocultos definen exito.

El scoring general sigue preguntando lo mismo:

- es verdadero / correcto?
- es relevante?
- cubrio lo pedido?
- no spameo?

Pero el chequeo de "verdad/correccion" ya no siempre es solo
`ClaimIntent -> AtomicSpec`.

## Como se veria la unificacion

### Opcion A — Estado actual

```text
ClaimCard -> ClaimIntent -> AtomicSpec -> verifier
SQ -> pattern + roles + ask -> AtomicSpec -> verifier
```

Muy cerrado, sesgo a causal simple.

### Opcion B — A23

```text
Claim/SQ -> 1..N AtomicSpec(s) directos
```

Mucho mejor. Menos catalogo. Mas semantica preservada.

### Opcion C — A24 (target mas general)

```text
Submission (claim / prediction / ranking / policy / design / ...)
    -> validator program oculto
    -> runtime comun
    -> verdict(s)
```

En esta vision:

- `AtomicSpec` pasa a ser un **subconjunto** o caso especial de validator program;
- no el techo final.

## Que NO queremos

No queremos:

- scoring profiles por tipo
- `if predictive: usar scorer_predictivo()`
- `if causal: usar scorer_causal()`
- una taxonomia operativa que el scoring tenga que chequear primero

Eso seria un parche y rompe un principio central del proyecto.

## Que podria tener de malo ir a "programas libres"

La idea de validator programs es atractiva, pero hay un riesgo serio si se
hace como codigo arbitrario generado por LLM.

### Riesgos

1. **Perdida de auditabilidad**
   - cuesta ver que se esta chequeando exactamente
2. **Reward inestable**
   - distintos casos pueden introducir reglas arbitrarias
3. **Bugs silenciosos**
   - leakage, metricas mal calculadas, criterios inconsistentes
4. **Menor comparabilidad entre episodios**
   - dos casos parecidos pueden evaluar con logicas muy distintas
5. **Debugging mucho mas dificil**

## Entonces: no codigo arbitrario, sino programas restringidos

La version sana de esta idea no es:

- "el LLM escribe cualquier Python"

Sino algo como:

- runtime comun
- operaciones permitidas
- tipos permitidos
- acceso controlado al mundo / datasets / splits
- agregadores permitidos
- validadores auditables

O sea:

- **programas tipados/restringidos**
- no codigo arbitrario

## Donde encaja `AtomicSpec`

`AtomicSpec` sigue siendo valioso incluso en A24:

- es un validator declarativo excelente para claims sobre el mundo;
- ya esta implementado;
- ya es auditable;
- ya tiene verifier deterministico.

Por eso, A24 no deberia empezar borrando `AtomicSpec`.

La formulacion correcta es:

- `AtomicSpec` = una familia importante de validator programs
- no necesariamente la unica familia futura

## Como pensarlo sin romper el principio de generalidad

La forma correcta NO es:

- "hay dos scorers"

La forma correcta seria:

- **un solo runtime comun**
- que ejecuta **validadores ocultos del caso**
- y produce verdicts comparables

El runtime comun podria soportar primitivas generales como:

- consultar el SCM
- samplear / intervenir / condicionar
- leer datasets publicos / privados
- evaluar una submission del solver
- calcular metricas
- comparar con thresholds / constraints / baselines

Todo eso bajo un mismo formalismo de "validator".

## Implicacion para SQ

Si vamos en esta direccion, las SQ ya no deberian pensarse como:

- `pattern + roles + ask`

Sino como:

- `text_gloss` humano
- `hidden validator` ejecutable

En algunos casos ese validator sera:

- un bundle de `AtomicSpec`

En otros podria ser:

- una evaluacion de predicciones sobre holdout
- una comparacion contra baseline
- un chequeo de constraint satisfaction

## Decision provisional

1. **Corto plazo:** seguir con A23
   - salir del catalogo fijo
   - ir mas directo a `AtomicSpec`
   - validar que eso mejora diversidad real

2. **Mediano plazo:** no tratar `AtomicSpec` como techo final
   - tratarlo como la primera familia fuerte de validators

3. **Largo plazo:** disenar un runtime comun de validator programs restringidos
   - un solo metodo general
   - sin scoring profiles por tipo
   - sin codigo arbitrario

## Preguntas abiertas

1. Cual es la IR minima correcta para esos validator programs restringidos?
2. Que partes del runtime actual de `AtomicSpec` ya sirven como kernel comun?
3. Como mantener auditabilidad y comparabilidad entre casos?
4. Como definir submissions generales sin convertir el sistema en un juego?
5. Puede `AtomicSpec` extenderse lo suficiente para cubrir estos casos, o hace
   falta una capa por encima?

## Conexiones

- **PROJECT.md** — fija el principio de "un solo metodo de scoring para todo"
- **CLAUDE.md** — refuerza que no puede haber scoring profiles por tipo
- **A23** — corrige el bottleneck inmediato: demasiada dependencia del catalogo
- **S04** — evidencia empirica de que el camino directo a atoms recupera semantica
- **Taxonomia** — sirve para coverage audit, NO para bifurcar el scoring
