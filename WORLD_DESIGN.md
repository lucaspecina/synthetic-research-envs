# De mundos de juguete a mundos realistas

> **Documento de investigacion y referencia.** Estrategia, decisiones de diseno,
> preguntas abiertas y conclusiones parciales para evolucionar los mundos de SREG
> desde patrones aislados hacia research cases que se parezcan a investigaciones
> reales.
>
> Este documento es **dinamico** — se actualiza a medida que investigamos
> alternativas, encontramos problemas, o descubrimos nuevos enfoques. No es un
> plan de implementacion (eso esta en TODO.md). Es el espacio para pensar,
> investigar y decidir antes de escribir codigo.
>
> **Relacion con PROJECT.md**: PROJECT.md es la estrella polar (hacia donde vamos).
> Este documento es la brujula de investigacion para una parte especifica del
> camino: como generar mundos formales mas ricos y realistas.

### Indice de navegacion

Este documento es largo (~2000 lineas). Usa este indice para ir directo
a la seccion que necesites:

| Seccion | Que contiene |
|---|---|
| **El salto que queremos dar** | Donde estamos vs donde queremos llegar |
| **Principio fundamental** | Mechanism-first, no graph-first |
| **La progresion en tres etapas** | v0+v1 → v2 → v3 |
| **Los dos contratos centrales** | MechanismSpec + DAGSpec |
| **Mecanismos rivales** | Nucleo de la investigacion real |
| **Fundamentos de razonamiento causal** | Pearl (escalera de causalidad), McElreath (4 elemental confounds), principio de diseno de tasks |
| **Dimensiones de un caso real** | 17 dimensiones que hacen a una investigacion real, estado en SREG, prioridades |
| **Diseno de Research Cases** | TaskBundle → ResearchCase, rol del orchestrator, CasePlan |
| **Catalogo de evaluaciones cientificas** | 31 eval types en 6 familias (A-F), mapa de implementacion por olas, soporte pgmpy |
| **Paper-seeded cases** | Flujo: paper real → caso sintetico |
| **Diseno de acciones de investigacion** | Tipos de accion (observar, intervenir, consultar), catalogo, validacion, impacto en teacher, ejemplos |
| **Enriquecimiento de datos** | Multi-dataset, missing data, narrativas |
| **Quality gates + QualitySuite** | Que hace que un mundo sea "bueno" + metricas |
| **Principios de PCG** | Generate-evaluate-refine, MAP-Elites, expressive range |
| **Hallazgos experimentales** | Resultados de templates, DAGSpec, batch sweep |
| **Hallazgos 5-SRC eval** | 5 dominios, budget 0 en 4/5, diagnostico Codex |
|---|---|
| **docs/SREG_V2_DESIGN.md** | 10 patrones reales + 5 cambios + taxonomia (TODO unificado) |
| **research/real_investigations_analysis.md** | Analisis detallado de 7 papers reales |
| **Investigacion previa** | BoxingGym, DiscoveryWorld, Reasoning Core, benchmarks |

---

## El salto que queremos dar

### Donde estamos hoy

Mundos con un solo patron causal aislado:

- 1 patron por mundo (cadena O fork O collider)
- 6-9 nodos
- 1 latente
- Estructura simple, casi adivinable
- Evidencia limpia
- Pregunta: "cual es P(target)?"

### Donde queremos llegar

Mundos que se parezcan a investigaciones reales:

- Muchos patrones mezclados
- 10-30+ variables
- Multiples latentes a distintos niveles
- Estructura compleja y ambigua
- Datos faltantes, ruidosos, contradictorios
- Pregunta: "cual es el mecanismo? que conviene hacer? que hipotesis explica mejor?"

### El ejemplo concreto

El caso de arenamiento de pozos de petroleo (ver PROJECT.md) tiene ~10 variables,
multiples mecanismos competidores, evidencia temporal, proxies imperfectos, y
preguntas de inferencia + decision + intervencion. Eso es lo que queremos poder
generar.

---

## Principio fundamental: mechanism-first, no graph-first

**El generador no deberia pensar primero "que grafo hago", sino "que fenomeno
quiero que exista y que mecanismos plausibles lo pueden producir". El grafo
sale como compilacion de eso, no como punto de partida.**

Esto es el verdadero salto entre benchmark formal y synthetic research environment.

Un cientifico no empieza con un DAG. Empieza con:
1. Un **fenomeno** que quiere explicar (el pozo se arena, el material falla)
2. Varios **mecanismos plausibles** que podrian producirlo
3. **Variables** con roles claros (causas, efectos, proxies, confounders)
4. **Evidencia** parcial que favorece algunos mecanismos sobre otros

El DAG es la formalizacion de eso, no el punto de partida.

---

## La progresion en tres etapas

### Etapa 1: Motifs curados — v0+v1 (completo)

Templates fijos: latent_preference, causal_chain, fork_collider. Cada uno
testea un tipo de razonamiento especifico. Sirven para:
- Validar todo el stack
- Aprender que dificultades produce cada patron
- Tener una linea base controlada

**Estado: completo.**

### Etapa 2: Composicion controlada de motifs — v2 (en curso)

No generamos "un template", sino un mundo formado por varios submodulos:
una cadena, un fork con latente, un collider, un mediador extra, algunos
observables/proxies alrededor. "Moleculas" construidas con "atomos" conocidos.

Ventajas:
- Cada pieza es interesante (ya lo sabemos por etapa 1)
- La composicion preserva propiedades interesantes
- Se puede especificar que se quiere ("dame 2 forks + 1 chain + 1 collider")
- Control sobre la complejidad

Riesgos:
- Las conexiones entre piezas necesitan cuidado (pueden anular propiedades)
- La combinatoria es grande
- Puede ser demasiado "mecanico" (no se parece a como se piensa un problema real)

### Etapa 3: Diseno mechanism-first — v3 (futuro)

El generador piensa en terminos de:
1. **Roles de variables** (no solo tipos node)
2. **Mecanismos plausibles** (con semantica y estructura)
3. **Hipotesis rivales** (mecanismos que compiten)
4. **Compilacion a DAG** (los mecanismos se traducen a estructura formal)

Esto es lo mas cercano a como un cientifico piensa un sistema.

**La recomendacion: etapa 2 primero, etapa 3 despues. No saltar a DAGs
totalmente libres sin pasar por composicion controlada.**

---

## Los dos contratos centrales: MechanismSpec y DAGSpec

El sistema tiene dos contratos de datos fundamentales, a distinto nivel
de abstraccion:

### MechanismSpec — el lenguaje del cientifico

Un mecanismo es una explicacion plausible de un fenomeno. En esta etapa,
lo representamos como un subgrafo reutilizable con variables tipadas y
relaciones causales. Mas adelante, un mecanismo puede incluir no solo
estructura, sino tambien constraints sobre parametros, observabilidad,
costos y firmas esperadas en los datos.

```python
class MechanismSpec(BaseModel):
    name: str                        # "pressure_mobilization"
    description: str                 # "Frac hit alters pressure, mobilizes fines"
    variables: list[DAGNodeSpec]     # Variables del mecanismo
    edges: list[tuple[str, str]]     # Relaciones causales internas
    shared_variables: list[str]      # Variables compartidas con otros mecanismos
```

El flujo mental correcto es:

```
MechanismSpec(s) --> WorldComposer --> DAGSpec --> CPDs --> World
```

Los mecanismos son el input conceptual. El DAGSpec es el output tecnico.

**Ejemplo: arenamiento de pozos**

```
Mecanismo A ("pressure_mobilization"):
  variables: [frac_hit, pressure_change, fines_mobilization, sanding]
  edges: frac_hit -> pressure_change -> fines_mobilization -> sanding
  shared: [frac_hit, sanding]

Mecanismo B ("completion_damage"):
  variables: [frac_hit, completion_integrity, sanding]
  edges: frac_hit -> completion_integrity -> sanding
  shared: [frac_hit, sanding]

Mecanismo C ("mechanical_failure"):
  variables: [rock_quality, frac_hit, mechanical_stress, sanding]
  edges: rock_quality -> mechanical_stress, frac_hit -> mechanical_stress,
         mechanical_stress -> sanding
  shared: [frac_hit, sanding]
```

El WorldComposer toma el mecanismo verdadero (A), las variables compartidas,
observables adicionales, y produce un DAGSpec completo.

### DAGSpec — el contrato universal

Independientemente de como se genere la estructura (mecanismos, composicion,
manual, random, LLM), todo se reduce a un DAGSpec que entra al mismo pipeline
de generacion.

```python
class DAGNodeSpec(BaseModel):
    name: str
    type: NodeType           # LATENT, OBSERVABLE, TARGET
    states: list[str]        # ["low", "medium", "high"]
    role: str | None = None  # "driver", "proxy", "confounder", etc. (metadata)

class DAGSpec(BaseModel):
    nodes: list[DAGNodeSpec]
    edges: list[tuple[str, str]]  # (from, to)

    # Validaciones automaticas en el modelo:
    # - Es un DAG (aciclico)
    # - Al menos un target
    # - Al menos un observable
    # - Cada nodo en edges existe en nodes
    # - Max parents por nodo (e.g., 4)
```

### Restriccion clave: max parents

Un nodo con `k` padres de `s` estados cada uno tiene una CPD de
`s^k * s_hijo` valores. Con s=3:
- 1 padre: 9 valores (ok)
- 2 padres: 27 valores (ok)
- 3 padres: 81 valores (manejable)
- 4 padres: 243 valores (limite)
- 5 padres: 729 valores (peligroso, la CPD se llena de ruido)

**Regla: max 3-4 padres por nodo.** Si la estructura real tiene mas,
hay que introducir variables intermedias (mediadores).

---

## Roles de variables (mas alla de LATENT/OBSERVABLE/TARGET)

Hoy tenemos 3 tipos de nodo: LATENT, OBSERVABLE, TARGET. Para mundos
realistas, necesitamos pensar en **roles** mas ricos:

| Rol | Descripcion | Ejemplo (pozo de petroleo) |
|---|---|---|
| **Driver externo** | Causa exogena que inicia cadenas | Intensidad del frac hit |
| **Estado latente** | Variable oculta que el agente no puede ver directamente | Integridad del pack |
| **Observable directo** | Se puede medir con costo | Presion de fondo |
| **Proxy** | Observable que refleja una latente imperfectamente | Produccion de finos (proxy de dano) |
| **Outcome / Target** | Lo que el agente quiere predecir/explicar | Severidad del arenamiento |
| **Confounder** | Causa comun de dos variables, puede enganar | Tipo de formacion |
| **Mediador** | Transmite el efecto de una causa al outcome | Cambio de drawdown |
| **Intervencion** | Variable que el agente podria manipular (do-calculus) | Reducir drawdown post frac hit |

**Decision tentativa**: los roles empiezan como metadata (string libre en
`DAGNodeSpec.role`). Formalmente siguen siendo LATENT/OBSERVABLE/TARGET.
A medida que veamos cuales se repiten y tienen implicaciones en la generacion,
los roles pueden cristalizarse en un enum o afectar costos de observacion,
tasks disponibles, etc. No over-engineerear desde el dia 1.

---

## Mecanismos rivales: el nucleo de la investigacion real

En investigacion real, la pregunta rara vez es "cual es P(target)". La
pregunta es **"cual de estos mecanismos explica los datos"**.

Cada mecanismo es una explicacion plausible. Pueden compartir variables.
La evidencia disponible favorece mas a unos que a otros. El agente tiene
que descubrir cual es el correcto (o cual es el mas probable).

### Como se conecta con lo que tenemos hoy

Ya tenemos `hypothesis_selection` que compara distribuciones sobre el target.
El siguiente nivel es **comparar estructuras causales**: cada hipotesis no
es una distribucion diferente, sino un DAG diferente (o un subconjunto de
aristas diferente).

Esto abre evaluaciones como:
- "Cual de estos 3 mecanismos es el verdadero?" (structure selection)
- "Que evidencia discriminaria entre mecanismo A y B?" (experimental design)
- "Si el mecanismo A es correcto, que intervenciones servirian?" (planning)

### Niveles de complejidad para mecanismos rivales

La progresion natural es:

1. **Excluyentes**: solo un mecanismo es verdadero, los otros son distractores
   puros. La task es elegir cual es el correcto. (Mas simple de implementar y
   evaluar.)

2. **Uno domina**: varios mecanismos contribuyen, pero uno es el principal.
   La task es identificar el dominante y cuantificar su contribucion.
   (Mas realista.)

3. **Mezcla**: la verdad es una combinacion de mecanismos con distintos pesos.
   (Lo mas realista, pero mas dificil de evaluar formalmente.)

**Inclinacion: empezar con nivel 1, evolucionar a 2 cuando el stack lo soporte.**

---

## ResearchCase: el producto final (actualizado 2026-03-09)

> **Nota**: este concepto fue reformulado significativamente. Ver la seccion
> "Diseno de Research Cases" mas abajo para el analisis completo, la
> comparacion con ResearchGym, y las preguntas abiertas.

El producto de SREG no es solo un mundo ni solo una task. Es un **caso de
investigacion completo** donde las preguntas nacen del caso, no de un
template fijo. El LLM orchestrator diseña el caso completo.

### Que incluye un ResearchCase

```
ResearchCase
  |-- world: World                       # Mundo oculto (BN formal)
  |-- narrative: str                     # Contexto de la investigacion
  |-- data_assets: list[DataAsset]       # Datos del caso (multi-dataset)
  |-- available_actions: list[Action]    # Que puede hacer, con que costos
  |-- shared_budget: int                 # Budget para todo el caso
  |-- evaluation_objective: str          # Que se quiere evaluar
  |-- primary_question: EvalQuestion     # La pregunta principal
  |-- sub_questions: list[EvalQuestion]  # 0-N subpreguntas conectadas
  |-- rival_mechanisms: list[...]        # Mecanismos alternativos (futuro)
```

```
EvalQuestion
  |-- question_text: str                 # En lenguaje natural, escrita por orchestrator
  |-- eval_type: EvalType                # Del catalogo (infer_target, NBO, causal, ...)
  |-- ground_truth: dict                 # Respuesta correcta (computada desde el BN)
  |-- weight: float                      # Peso en el score compuesto del caso
```

### Relacion con lo que tenemos hoy

`TaskBundle` agrupa siempre las mismas 3 tasks del mismo mundo.
`ResearchCase` lo generaliza: las preguntas las elige el orchestrator
segun el caso, no un template fijo. La transicion es incremental:
1. Primero: el orchestrator elige CUALES eval types usar (no siempre 3)
2. Despues: el orchestrator escribe las preguntas en lenguaje natural
3. Despues: budget compartido, preguntas conectadas
4. Despues: nuevos eval types (causal, prediccion, etc.)

`TaskBundle` sigue funcionando como caso degenerado (siempre los mismos 3).

---

## Arquitectura tentativa de generacion

```
MechanismSpec(s)          Mecanismos plausibles para un fenomeno
       |                  (estructura + semantica + variables compartidas)
       v
WorldComposer             Combina mecanismos en un DAGSpec
       |                  (elige el verdadero, resuelve conflictos, agrega observables)
       v
DAGSpec                   Contrato universal de estructura
       |
       v
Parameterizer             Asigna edge_strength, estados, seed
       |                  (controla dificultad)
       v
WorldGenerator            Genera CPDs y construye World (pgmpy)
       |                  (usa la formula edge_strength existente)
       v
QualityChecker            Valida que el mundo sea bueno
       |                  (treewidth, entropia, d-seps, teacher solvability)
       v
CaseBundleGenerator       Genera el caso completo
       |                  (tasks multiples + semantica + datos + acciones)
       v
QualityChecker (tasks)    Valida que las tasks sean utiles
                          (NBO no trivial, hipotesis distinguibles, etc.)
```

### Entradas alternativas al DAGSpec

No solo MechanismSpec alimenta al pipeline. Multiples entradas posibles:

```
MechanismSpec(s)    --+
Motif composer      --+
Manual DAGSpec      --+--->  DAGSpec  --->  [Pipeline de arriba]
DAG generators      --+
LLM constructor     --+
pgmpy get_random()  --+
```

**Principio de diseno: el LLM orchestrator tendra DOS caminos permanentes para crear mundos:**

1. **DAG generators con parametros** — el LLM elige un generador (Erdos-Renyi, layered, etc.)
   y le pasa parametros (num_nodes, edge_prob, etc.). Rapido, produce variedad, bueno para
   generar mundos en batch o cuando no importa la forma exacta.

2. **Construccion manual de DAGSpec** — el LLM especifica nodos y aristas uno por uno.
   Permite disenar estructuras especificas (e.g., "quiero un confounding path entre A y B
   con un mediador C"). Necesario para crear mundos a partir de descripciones textuales,
   papers, o requerimientos especificos del usuario.

Ambos caminos son de primera clase y permanentes. No es uno transitorio y otro final —
son complementarios. Un generador produce variedad; un DAGSpec manual produce precision.

### Preguntas abiertas sobre esta arquitectura

1. **MechanismLibrary: curada o generada?**
   - Opcion A: libreria fija de mecanismos (como templates, pero mas granulares)
   - Opcion B: el LLM genera mecanismos ad-hoc (mas flexible, menos controlado)
   - Opcion C: ambos — libreria base + capacidad de crear nuevos
   - Inclinacion: C, empezando por A
   - **Referencia para disenar la libreria curada**: los 10 ambientes de BoxingGym
     (Location Finding, Temporal Discounting, Death Process, IRT, Dugongs, Peregrines,
     Survival Analysis, Predator-Prey, Emotion, Moral Machines) son casos hand-crafted
     por cientificos. No para copiar sus modelos PyMC, sino para estudiar que patrones
     hacen que un problema de descubrimiento sea interesante: que estructura tiene el
     fenomeno, que relacion hay entre variables, que hace que un experimento sea mas
     informativo que otro, que tipo de feedback devuelve el mundo. Son una buena
     "biblioteca de referencia" para inspirar mecanismos curados.

2. **WorldComposer: como resuelve conflictos?**
   - Dos mecanismos pueden tener variables con el mismo nombre pero distintos roles
   - Pueden crear ciclos al conectarse
   - Pueden producir nodos con demasiados padres
   - Necesita reglas claras de composicion

3. **Cuantos mecanismos por mundo?**
   - Minimo: 2 (para que haya hipotesis rivales)
   - Tipico: 2-4
   - Maximo: depende de nodos totales y treewidth
   - Solo 1 es el "verdadero", los otros son distractores? O todos coexisten?
   - (Ver "Niveles de complejidad para mecanismos rivales" arriba)

4. **Quality filtering: cuantos intentos antes de rendirse?**
   - Si el 90% de los mundos generados no pasa quality check, el generador es malo
   - Necesitamos metricas de "tasa de aceptacion" para saber si el generador funciona

5. **Semantica: obligatoria, opcional, o ficticia?**
   - **Problema**: si usamos vocabulario real ("water_temperature") con mecanismos inventados,
     una AI entrenada con estos mundos podria aprender asociaciones causales incorrectas
     sobre el mundo real. Ej: si en nuestro mundo water_temp causa coral_bleaching con
     mecanismo X, pero en la realidad el mecanismo es Y, el modelo aprende algo errado.
   - **Opciones**:
     - A) Semantica completa (hoy): vocabulario real + dominio ficticio. Riesgo de confusion.
     - B) Modo abstracto: variables "A", "B", "C" sin narrativa. Evalua razonamiento puro.
        No contamina con conocimiento falso. Pero no evalua integracion de contexto.
     - C) Semantica ficticia: nombres inventados ("zanthor_level", "flux_7b") con narrativa
        ficticia. Suena cientifico pero no existe. No confunde, pero pierde naturalidad.
     - D) Configurable: flag `semantic_mode` que controla el nivel de vestimenta semantica.
        `abstract` = sin nombres, `fictional` = nombres inventados, `full` = lo de hoy.
   - **Inclinacion**: D — hacer configurable. Cada modo tiene su uso:
     - `abstract`: para evaluar razonamiento puro (ej: training sin contaminar)
     - `fictional`: para evaluacion realista sin riesgo de memorizar ciencia falsa
     - `full`: para evaluar integracion de conocimiento previo (el agente usa lo que sabe)
   - **Pregunta derivada**: en modo `abstract`, que pasa con `apply_semantics`? Se saltea?
     Se usa con nombres genericos? Se necesita narrativa o solo se dan datos crudos?
   - **Para decidir**: requiere experimentacion — generar problemas en cada modo y evaluar
     si las respuestas del agente son cualitativamente diferentes

---

## Quality gates: que hace que un mundo sea "bueno"

No alcanza con que el DAG sea valido. Un buen mundo de investigacion
tiene que ser:

### Formalmente correcto
- [x] DAG aciclico
- [ ] Todas las CPDs suman 1 por columna
- [ ] Target alcanzable desde al menos un observable

### Epistemologicamente interesante
- [ ] Entropia del target en rango util (ni trivial ni maxima)
- [ ] Al menos N pares de variables d-separados (estructura no trivial)
- [ ] Al menos un nodo con information gain > 0 dado evidencia parcial (NBO no trivial)
- [ ] Hipotesis distinguibles (KL entre verdadera y distractor > threshold)
- [ ] No todas las observaciones son igualmente informativas (hay estrategia)

### Computacionalmente viable
- [ ] Treewidth <= 6-8 (Variable Elimination viable)
- [ ] Max parents por nodo <= 4
- [ ] Numero total de nodos <= 30 (para inferencia exacta)

### Solvable
- [ ] Teacher solver mejora claramente sobre el prior (no usamos % accuracy fijo
  porque depende del numero de estados y la task)
- [ ] Teacher supera ampliamente a random baseline (gap significativo)
- [ ] Existe al menos una secuencia de observaciones que mejora significativamente la posterior

### Task-specific
- [ ] NBO: al menos un nodo con IG > 0 (no trivial)
- [ ] Hypothesis selection: KL entre hipotesis > 0.05 (distinguibles)
- [ ] Infer target: la posterior con toda la evidencia difiere del prior
- [ ] Tasa de tasks no degeneradas: el generador debe producir una proporcion
  razonable (>70%) de tasks utiles. Si >50% salen triviales, el generador
  tiene un problema aunque los mundos individuales pasen quality check.

Si un mundo no pasa, se regenera con otra seed o se ajustan parametros.
El quality checker reporta QUE fallo para que el generador pueda corregir.

---

## Metricas de salud del generador

No alcanza con validar mundos individuales. Necesitamos evaluar si el
**generador en su conjunto** esta produciendo buenos resultados. Metricas
a trackear:

| Metrica | Que mide | Por que importa |
|---|---|---|
| **Acceptance rate** | % de mundos que pasan quality check | Si es <50%, el generador es malo |
| **Diversidad estructural** | Cuantas topologias distintas genera | Si siempre genera lo mismo, no sirve |
| **Distribucion de entropias** | Rango de dificultad de los mundos | Queremos variedad, no todo facil o todo imposible |
| **IG gap promedio** | Diferencia de IG entre mejor y peor nodo | Si es ~0, las tasks NBO son triviales |
| **Distinguishability promedio** | KL promedio entre hipotesis | Si es bajo, hypothesis_selection es loteria |
| **Gap teacher vs random** | Cuanto mejor es el teacher que random | Si es chico, el mundo no tiene estructura util |
| **Tasa de CaseBundles utiles** | % de casos con al menos 2 tasks no triviales | El producto final necesita variedad de tasks |

Los thresholds numericos concretos se definiran cuando tengamos datos de
generacion real (etapa 2). Por ahora lo importante es saber QUE medir.

---

## Suite de evaluacion y validacion (QualitySuite)

Suite programatica rigurosa para evaluar la calidad del sistema a multiples niveles.
La premisa central: **separar las capas de evaluacion** para saber DONDE esta un
problema cuando algo falla. No mezclar calidad del mundo con calidad del orchestrator
con calidad del agent.

Un mundo esta bueno si cumple tres cosas al mismo tiempo:
1. Tiene estructura real (no es ruido ni trivialidad)
2. Produce decisiones interesantes (hay valor en decidir que mirar, que creer)
3. Se puede convertir en un caso util para un LLM (no solo un DAG bonito)

Dicho mas directamente: **un buen mundo es uno que genera un buen case, no solo un
buen DAG.**

Senales de que el sistema funciona bien:
- teacher reduce entropia consistentemente
- random y heuristicas quedan claramente por debajo en promedio multi-rollout
- el LLM a veces acierta y a veces falla de formas interpretables
- distintas tasks sobre el mismo caso miden cosas distintas
- el quality checker descarta una porcion razonable pero no enorme
- cuando miras ejemplos concretos sentis que "aca hay una mini investigacion"

### Hallazgo critico: metricas vs one-hot del true state (2026-03-09)

La metrica original `teacher_beats_prior` comparaba `KL(one-hot(true_state) || posterior)`
entre prior y teacher. Esto es equivalente a `-log P(true_state)` (negative log
likelihood del estado sampleado).

**Problema**: esta metrica mezcla dos cosas:
1. Calidad de la inferencia (¿la posterior es correcta dada la evidencia?)
2. Suerte del true state sampleado (¿el estado real es probable dada la evidencia?)

Caso concreto encontrado: mundo de 12 nodos, true_state=medium.
- Prior asigna P(medium)=0.41 → NLL=1.30
- Teacher observa 5 nodos, evidencia apunta fuertemente a "low"
- Teacher posterior P(medium)=0.15 → NLL=2.75 — PEOR que prior
- Pero el teacher REDUJO entropia de 1.49 a 0.79 bits — hizo inferencia correcta

**El teacher no razona peor. La metrica castiga inferencia correcta cuando el
true state sampleado es atipico dado la evidencia.**

Conclusion: no usar NLL single-sample como metrica principal. Usar multi-rollout
para promediar, y entropia como metrica estructural independiente del sample.

### Capa A — World Quality (estructura pura, sin teacher)

Evalua si el mundo es formalmente valido y tiene estructura aprovechable.
100% programatico, rapido de computar. Sin cambios respecto a v1.

| Metrica | Definicion | Tipo | Target |
|---|---|---|---|
| `worldcheck_pass` | WorldCheckTool.check().passed | bool | >85% en batch |
| `num_nodes` | Cantidad de nodos | int | info |
| `num_edges` | Cantidad de aristas | int | info |
| `density` | edges / max_possible_edges | float | info (0.1-0.5 ideal) |
| `treewidth` | Estimado via min-fill heuristic | int | <=8 (warning >6) |
| `graph_depth` | Longest path en el DAG | int | info |
| `max_fan_in` | Max padres de cualquier nodo | int | <=4 (hard) |
| `max_fan_out` | Max hijos de cualquier nodo | int | info |
| `target_reachable_frac` | Fraccion de observables con camino al target en el DAG subyacente | float | >0.3 |
| `target_entropy` | H(target) sin evidencia (bits) | float | info (0.5-2.0 ideal) |

**target_reachable_frac** es mas util que "es conexo si/no" porque mide cuantos
observables son realmente relevantes para el target. Un grafo puede ser conexo pero
tener el target aislado en una esquina donde nadie lo alcanza.

### Capa B — Task Quality (con teacher, sin agent) — REDISEÑADA v2

Evalua si el mundo produce tareas interesantes y resolubles.
Requiere correr el teacher (ExactBayesSolver).

**Cambio clave en v2**: se corre con **K rollouts** (K=5-10 seeds) por mundo.
Las metricas de belief se promedian sobre rollouts para eliminar ruido de
episodios atipicos. Esto separa calidad de inferencia de suerte del sample.

#### Metricas de diseno del episodio (no dependen del sample)

| Metrica | Definicion | Tipo | Target |
|---|---|---|---|
| `budget_ratio` | budget / num_observables_con_path_al_target | float | <0.8 |
| `prior_entropy` | H(target) sin evidencia (bits) | float | info (0.5-2.0 ideal) |
| `best_first_ig` | IG del mejor primer movimiento del teacher | float | >0.05 |
| `ig_gap` | max(IG) - min(IG) entre todos los observables | float | >0.01 (hay estrategia) |

**budget_ratio** usa observables con path al target (no observables totales), porque
observables desconectados no cuentan como "opciones reales". Si budget_ratio >= 1.0,
no hay decision-making — el agent puede ver todo lo relevante.

#### Metricas de belief quality (promediadas sobre K rollouts)

| Metrica | Definicion | Tipo | Target |
|---|---|---|---|
| `mean_entropy_reduction` | promedio de H(prior) - H(teacher_posterior) | float | >0.1 |
| `mean_teacher_nll` | promedio de -log P_teacher(true_state) | float | info |
| `mean_prior_nll` | promedio de -log P_prior(true_state) | float | info |
| `mean_nll_improvement` | promedio de prior_nll - teacher_nll | float | info (>0 en promedio) |
| `mean_random_nll` | promedio de -log P_random(true_state) | float | info |
| `teacher_beats_random_rate` | fraccion de rollouts donde teacher_nll < random_nll | float | >0.6 |

**mean_entropy_reduction** es la metrica principal de belief quality. No depende
de si el true state es tipico o atipico — solo mide si la evidencia redujo
incertidumbre. Siempre positiva para inferencia bayesiana correcta.

**mean_nll_improvement** se reporta pero NO se usa como criterio de useful_bundle
porque es mas fragil que entropy reduction (sigue dependiendo de la tipicidad del
sample, aunque el promedio lo suaviza).

#### Metricas de task no-degeneracion (por rollout, luego se agregan)

| Metrica | Definicion | Tipo | Target |
|---|---|---|---|
| `nbo_nontrivial_rate` | fraccion de rollouts con max(IG restante) > 0 | float | >0.7 |
| `hyp_distinguishable_rate` | fraccion de rollouts con min KL distractor > 0.05 | float | >0.8 |

#### Metricas diagnosticas (se reportan, no son criterio)

| Metrica | Definicion | Tipo | Estatus |
|---|---|---|---|
| `sampled_nll_teacher` | -log P_teacher(true_state) en un solo rollout | float | diagnostico |
| `sampled_nll_prior` | -log P_prior(true_state) en un solo rollout | float | diagnostico |
| `teacher_steps_to_stable` | pasos hasta que IG marginal < 0.01 bits | int | diagnostico |

**Nota sobre las metricas diagnosticas**: `sampled_nll_*` es la vieja metrica
`teacher_beats_prior` con nombre honesto. Es sensible a episodios atipicos y
**no debe interpretarse como medida principal de calidad de inferencia**.
Se mantiene para debugging y para comparar con la version multi-rollout.

#### useful_bundle (redefinido)

Un bundle es "util" si:
- `mean_entropy_reduction > 0.1` **Y**
- al menos 2 de 3: `nbo_nontrivial_rate > 0.5`, `hyp_distinguishable_rate > 0.5`,
  `budget_ratio < 0.8`

Esto es mas estricto que la v1 (que solo pedia 2 de 3 tasks no-degeneradas).
Ahora exige que haya reduccion de entropia real Y que al menos dos dimensiones
de calidad esten presentes.

### Capa C — Generator Diversity (sobre batches de mundos)

Evalua si un generador produce mundos variados o siempre lo mismo.
Se computa sobre un batch de N mundos (N >= 20) con seeds distintas.

| Metrica | Definicion | Tipo | Target |
|---|---|---|---|
| `node_count_std` | Std dev de num_nodes en el batch | float | >0 (si parametrizado, puede ser 0) |
| `edge_count_std` | Std dev de num_edges en el batch | float | >0 |
| `density_range` | max(density) - min(density) | float | >0.05 |
| `depth_range` | max(depth) - min(depth) | int | >0 |
| `fan_in_distribution` | Histograma de fan-in across all nodes in batch | dict | info |
| `fan_out_distribution` | Histograma de fan-out across all nodes in batch | dict | info |
| `target_entropy_std` | Std dev de H(target) en el batch | float | >0.1 |
| `entropy_reduction_std` | Std dev de mean_entropy_reduction en el batch | float | >0 |
| `acceptance_rate` | % de mundos que pasan WorldCheck | float | >70% |
| `useful_bundle_rate` | % de mundos con useful_bundle=True (v2 def) | float | >60% |

Cambio en v2: `ig_gap_std` reemplazado por `entropy_reduction_std` (mas robusto,
alineado con la metrica principal de belief quality).

### Capa D — Semantic/Case Quality (checklist cerrada, evaluacion futura)

Evalua si el problema presentado al agent es coherente y util. Hoy es manual;
en el futuro podria ser evaluado por un LLM juez.

**Checklist minima (5 criterios, pass/fail cada uno):**

1. **Nombres coherentes con dominio**: los nombres de variables encajan con el
   dominio declarado. No "water_temperature" en un problema de astrofisica.
2. **Narrativa no contradice DAG**: si la narrativa dice "A causa B", la arista
   A->B debe existir (o al menos no contradecir la estructura).
3. **Acciones comprensibles**: las acciones disponibles tienen descripciones
   claras y el agent puede entender que hace cada una.
4. **Pregunta principal clara**: el research_question es especifico, respondible,
   y apunta al target.
5. **Datos consistentes con el caso**: los datos tabulares/observaciones son
   coherentes con la narrativa y el dominio.

**No implementar automaticamente todavia.** Pero la checklist queda cerrada para
que cuando evaluemos manualmente o con LLM juez, usemos siempre los mismos
criterios (no "me gusta / no me gusta").

### Capa E — Agent Probe (ultima prioridad, como sonda exploratoria)

Usa agentes de distinto nivel para verificar que el entorno separa bien
capacidades. NO es la metrica principal — es una sonda.

**Agentes a comparar:**

| Agente | Estrategia | Que mide |
|---|---|---|
| `random` | Observa nodos al azar, submite prior | Piso minimo |
| `heuristic_degree` | Observa nodo con mas conexiones primero | Estrategia naive |
| `heuristic_proximity` | Observa nodo mas cercano al target | Estrategia razonable |
| `teacher` | Observa por IG optimo | Techo maximo |
| `llm_agent` | AgentSolver con LLM | Capacidad real del LLM |

**Curva ideal esperada:**

```
random << heuristic_degree < heuristic_proximity < llm_agent < teacher
```

Si todo queda igual → el entorno no mide nada.
Si el LLM queda debajo de random → el entorno es demasiado dificil o la interfaz
esta mal.
Si el LLM iguala al teacher → el problema es demasiado facil.

**Implementacion**: las heuristicas son funciones simples (no requieren LLM).
El `llm_agent` requiere credenciales de Azure. El teacher ya existe.

### Implementacion

**Modulo**: `src/sreg/harness/quality.py`

**Estado actual**: v1 implementada con metricas originales (A+B+C). Funciona, 44
tests pasan, pero Capa B usa metricas single-sample que estan mal alineadas
(ver "Hallazgo critico" arriba).

**v2 pendiente**: rediseñar Capa B con multi-rollout + entropy reduction + nuevas
metricas. Ver TODO.md para las tareas concretas.

**Funciones principales (v2):**
- `compute_world_quality(world) -> WorldQualityMetrics` (Capa A, sin cambios)
- `compute_task_quality(world, seeds) -> TaskQualityMetrics` (Capa B, multi-rollout)
- `compute_generator_diversity(reports) -> GeneratorDiversityMetrics` (Capa C, ajustada)
- `run_quality_suite(worlds) -> QualitySuiteReport` (A+B+C combinadas)
- `print_quality_report(report)` (tabla legible en terminal)

**Integracion con /eval skill**: la skill llama a `run_quality_suite()` y
muestra el reporte.

**Orden de implementacion:**
1. [x] Capa A (world quality) — implementada, sin cambios
2. [~] Capa B (task quality) — v1 implementada, v2 multi-rollout pendiente
3. [~] Capa C (diversity) — v1 implementada, v2 ajuste menor pendiente
4. [ ] Integrar con /eval skill
5. [ ] Capa D — checklist manual o LLM juez (futuro)
6. [ ] Capa E — heuristicas + LLM agent (futuro, requiere credenciales)

---

## Principios adoptados de PCG y proyectos relacionados

Despues de investigar en profundidad BoxingGym, DiscoveryWorld, Reasoning Core,
y la literatura de Procedural Content Generation, identificamos principios
concretos que SREG deberia adoptar. Esta seccion documenta QUE tomamos de cada
fuente, POR QUE, y COMO se mapea a nuestro sistema.

### SREG como Procedural Content Generation

SREG es, en esencia, **procedural content generation aplicado a entornos de
investigacion verificables**. No generamos dungeons ni niveles de juego, pero
la logica es la misma: hay que definir que significa "interesante" antes de
generar, filtrar por calidad, y cubrir el espacio de contenido posible.

La diferencia clave: en PCG de juegos, la "fitness" suele ser jugabilidad,
diversion, o estetica. En SREG, la fitness es **interesabilidad epistemologica**:
que haya hipotesis distinguibles, que las observaciones tengan IG desigual, que
el teacher pueda resolver pero no trivialmente, que la estructura causal sea
no obvia.

### Principio 1: Generate-Evaluate-Refine con simulation-based fitness

**Fuente**: Togelius et al. 2011 (Search-Based PCG), patron general de PCG.

El patron mas inmediatamente implementable:

```
Generate:  crear mundo (estructura + CPDs)
Evaluate:  teacher solver resuelve, metricas miden calidad
           (KL hipotesis, IG de experimentos, pasos requeridos)
Refine:    si no pasa quality check, feedback especifico del error,
           ajustar parametros o regenerar con otra seed
```

Nuestro teacher solver ES la "simulacion" que valida el contenido. Esta es
una ventaja enorme: no necesitamos heuristicas de calidad — tenemos un agente
bayesiano exacto que nos dice si el mundo es resoluble y no trivial.

**Lo que ya tenemos**: WorldCheck valida estructura. Teacher valida solvability.
**Lo que falta**: formalizar el loop como pipeline explicito con feedback
estructurado al generador. El feedback debe ser especifico y accionable:
"hipotesis 2 y 3 tienen KL < 0.05, aumentar edge_strength o cambiar estructura".

Investigacion reciente (Maleki & Zhao 2024) muestra que repair loops con
feedback especifico mejoran hasta 415% sobre generacion sin feedback.

### Principio 2: Quality-Diversity via MAP-Elites

**Fuente**: Gravina, Khalifa & Liapis 2019 (PCG through Quality Diversity).

Este es probablemente el framework MAS relevante para SREG.

MAP-Elites no busca UN buen problema — busca **cubrir el espacio** con buenos
problemas diversos. Particiona el espacio de comportamiento en celdas y mantiene
solo el mejor ejemplar encontrado en cada celda.

Para SREG, las dimensiones del mapa podrian ser:

| Dimension | Valores posibles |
|---|---|
| Dificultad estimada | facil / media / dificil (pasos del teacher) |
| Tipo de estructura | chain-dominated / fork-dominated / collider-dominated / mixed |
| Numero de variables | 5-10 / 10-15 / 15-25 |
| Task types no triviales | 1 / 2 / 3 |

Cada celda contiene el "mejor" problema para esa combinacion, donde "mejor"
se mide por distinguibilidad de hipotesis, no-trivialidad de NBO, y riqueza
del espacio experimental.

**Resultado**: un benchmark diverso y de alta calidad por construccion. No
"generar 1000 problemas y esperar que haya variedad", sino garantizar
cobertura del espacio.

**Cuando implementar**: cuando tengamos el generador custom (etapa 2). Es
una capa encima del generador, no un cambio al generador mismo.

### Principio 3: Expressive Range Analysis

**Fuente**: Smith & Whitehead (PCG theory).

Evaluar el **generador**, no solo los artefactos individuales. Generar N
problemas, medir distribucion de propiedades, detectar sesgos.

Ya lo hacemos informalmente: "el generador produce 25% de NBO triviales"
es un defecto del generador que detectamos en E2E testing. Pero deberiamos
**automatizarlo**: un script que genera 100-500 mundos, mide la distribucion
de metricas, y reporta:
- Histograma de entropias del target
- Histograma de IG gaps (mejor nodo vs peor nodo)
- Histograma de KL entre hipotesis
- Tasa de acceptance del quality checker
- Distribucion por tipo de estructura

Esto va directamente a las "metricas de salud del generador" de la seccion
anterior.

### Principio 4: Mixed-Initiative Repair Loop

**Fuente**: Liapis et al. 2016 (Mixed-Initiative Content Creation), Maleki
& Zhao 2024.

El patron mixed-initiative ya es nuestra arquitectura: LLM propone estructura
y semantica, tools programaticas construyen y validan la matematica. Pero
podemos hacerlo mas explicito:

| PCG Mixed-Initiative | SREG equivalente |
|---|---|
| Humano propone estructura | LLM propone estructura del BN |
| Sistema valida restricciones | WorldCheck + QualityChecker |
| Sistema sugiere mejoras | Feedback estructurado: "edge_strength demasiado bajo" |
| Humano refina | LLM ajusta basado en feedback |

La clave es que el feedback del sistema sea **especifico y accionable**, no
solo "fallo". Ejemplo: "Hipotesis B y D tienen KL=0.009 (threshold: 0.05).
Sugerencia: aumentar edge_strength de 0.3 a 0.5, o cambiar la estructura
para que el target tenga mas dependencias."

### Principio 5: Constraint-Based Design Space

**Fuente**: Smith & Mateas 2011 (ASP for PCG), WaveFunctionCollapse.

Definir el espacio de BNs validos e interesantes **declarativamente**:
- Restricciones duras: DAG aciclico, CPDs validas, max parents, target alcanzable
- Restricciones blandas: entropia en rango, hipotesis distinguibles, IG > 0
- Parametros de control: num_nodes, edge_density, edge_strength

No estamos usando un CSP solver para generar, pero el principio guia nuestra
validacion: cada quality gate es una restriccion. El pattern de WFC (empezar
con todo abierto, ir colapsando propagando restricciones) mapea a nuestro
pipeline: elegir template -> asignar roles -> generar aristas -> parametrizar
CPDs, propagando restricciones en cada paso.

### Principio 6: Difficulty via Constraint Density

**Fuente**: PCG puzzle generation theory, Reasoning Core.

La dificultad de un problema se controla por la densidad de restricciones y
la distancia al punto de transicion de fase. Para SREG:

| Facil | Dificil |
|---|---|
| Pocas variables (5-8) | Muchas variables (15-25) |
| Hipotesis muy distinguibles (KL > 1.0) | Hipotesis sutilmente diferentes (KL ~ 0.1) |
| 1-2 experimentos revelan mucho | Se necesitan 5+ experimentos |
| 1 latente | Multiples latentes |
| Estructura obvia (cadena lineal) | Confounders, colliders, proxies |
| Teacher resuelve en 2 pasos | Teacher necesita 5+ pasos |

Reasoning Core usa un mecanismo elegante: **stochastic rounding** de un float
de dificultad. Cada llamada a `update()` incrementa suavemente todos los
parametros (num_nodes += 0.5, max_states += 0.5, etc.), y el redondeo
estocastico da variedad natural. Podriamos adoptar algo similar como un
"difficulty knob" continuo que escala todos los parametros proporcionalmente.

---

## Que tomar de cada proyecto — detalle concreto

### De BoxingGym: metricas y evaluacion

**1. Standardized Prediction Error (adoptar en v2)**

BoxingGym normaliza el error contra lo que sabrias con cero experimentos:
`standardized_error = (error - prior_error) / prior_std`. Negativo = aprendiste.
Cero = no aprendiste nada.

Nosotros ya tenemos el prior (es lo que calcula `_infer_target_task`). Podemos
reportar "mejora sobre prior" como metrica complementaria a KL crudo. Un agente
que solo repite el prior tiene score 0. Un agente que mejora tiene score negativo.
Un agente que empeora tiene score positivo. Mas interpretable que KL puro.

**2. EIG Regret como metrica post-hoc (adoptar en v2)**

BoxingGym computa EIG DESPUES para evaluar las decisiones del agente, no para
guiarlo. Nosotros ya hacemos algo similar con IG ratio en NBO, pero podriamos
extenderlo a evaluar toda la secuencia de observaciones en `infer_target`:
para cada observacion que hizo el agente, calcular su IG y comparar con la
que habria elegido el teacher.

Esto da una metrica de "eficiencia de investigacion": no solo "acertaste?"
sino "investigaste bien?". Directamente conectado con la evaluacion de proceso
que propone DiscoveryWorld.

**3. Scientist-Novice evaluation (explorar en v3+)**

Despues de resolver, el agente explica lo que descubrio. Un segundo agente
(novice) usa SOLO esa explicacion para responder preguntas. Si el novice
acierta, el scientist realmente entendio. Si no, solo memorizo.

Para SREG: pedirle al agente que explique la estructura causal despues de
resolver. Darle esa explicacion a otro agente y ver si puede responder
preguntas sobre el mismo mundo. Mide comprension profunda vs respuesta correcta
por casualidad.

Pregunta abierta: como formalizar esto? El segundo agente necesitaria recibir
preguntas sobre el mismo mundo pero sin acceso a las observaciones originales.

**4. Box's Apprentice — LLM genera modelo generativo (inspiracion)**

BoxingGym tiene un modo donde el LLM genera codigo PyMC que modela el sistema.
El modelo se ajusta a datos y se usa para predecir. Hallazgo: los LLMs tienden
a oversimplificar (usan modelos lineales para fenomenos no lineales).

Para SREG esto es relevante porque muestra que pedirle al agente que proponga
un modelo (no solo que compute una probabilidad) es una evaluacion mucho mas
profunda. Futuro: "propone la estructura causal que crees que explica los datos"
y evaluar con SHD contra el DAG verdadero.

### De DiscoveryWorld: evaluacion multi-dimensional y distractores

**1. Triple evaluacion: completion + proceso + conocimiento (adoptar en v2-v3)**

DiscoveryWorld evalua 3 dimensiones simultaneamente:
- **Completion**: logro el objetivo? (binario)
- **Proceso**: hizo las acciones correctas? (scorecard normalizado)
- **Conocimiento explicativo**: puede articular por que? (preguntas binarias)

Para SREG, la triple evaluacion mapea a:
- **Completion**: KL del target, accuracy de hipotesis, IG ratio de NBO
- **Proceso**: comparar secuencia de observaciones con teacher trajectory
  (porcentaje de overlap, orden, IG acumulado)
- **Conocimiento**: preguntas sobre la estructura causal despues de resolver
  (requiere LLM-as-judge, mas fragil, pero captura algo distinto)

Hoy solo tenemos completion. Proceso es implementable con lo que ya tenemos
(teacher trajectories existen). Conocimiento requiere mas trabajo.

**2. Distractores deliberados (adoptar en etapa 3)**

En DiscoveryWorld Space Sick, la comida es levemente radioactiva (distractor
fuerte) pero la causa real es moho. El agente tiene que descartar la hipotesis
"radioactividad causa enfermedad" activamente.

Para SREG: cuando generemos mecanismos rivales, incluir variables que estan
**correlacionadas** con el target pero **no son causales**. El agente que solo
mira correlaciones va a ser enganado. El que entiende causalidad va a descartar
el distractor.

Implementacion posible: agregar nodos "distractor" al DAGSpec que son hijos
del mismo confounder que el target, pero no estan en el camino causal. El
agent ve correlacion, pero no hay causalidad directa.

**3. Variaciones parametricas via seeds (ya adoptado)**

DiscoveryWorld confirma que seed-based generation es correcto. Un seed cambia
datos, solucion, layout. Genera diversidad real sin nuevos templates.
Nosotros ya hacemos esto — es bueno saber que esta validado externamente.

**4. Costo como consideracion practica**

DiscoveryWorld cuesta $3-10k por benchmark run (1000+ steps x llamadas LLM).
Leccion: mantener las evaluaciones de SREG eficientes. Los task types que
no requieren loop interactivo (NBO, hypothesis_selection) son mucho mas
baratos que infer_target con el agente. Considerar un "modo batch" que
evalua solo tasks no interactivas cuando se necesita escala.

### De Reasoning Core: generacion de BNs y CPDs

**1. Cuatro metodos de DAG generation (adoptar en etapa 2)**

Reasoning Core implementa 4 metodos, todos garantizando aciclicidad:

| Metodo | Como funciona | Cuando usarlo en SREG |
|---|---|---|
| **Erdos-Renyi** | Matriz upper-triangular, cada edge con prob `p` | DAGs random para testing |
| **Spanning tree** | Arbol primero, luego edges extra probabilisticos | Garantizar conexion + densidad variable |
| **Preferential attachment** | Nodos con mas edges atraen mas | Hubs naturales (como latent_preference) |
| **Layered** | Nodos en capas, edges solo hacia adelante | Estructuras tipo pipeline/cadena |

Podriamos implementar estos como `DAGSpec generators` — funciones que producen
DAGSpecs validos con distintas propiedades topologicas. Son entradas alternativas
al pipeline, no reemplazos de los templates curados.

**2. Noisy-OR/AND/MAX/MIN como CPDs alternativas (explorar en v2)**

Reasoning Core usa "Causal Influence Models" ademas de CPDs tabulares:

- **Noisy-OR**: cada padre tiene `activation_magnitude` independiente.
  `p_active = 1 - product(1 - mag[active_parents])`. Mas interpretable
  que una tabla llena de numeros.
- **Noisy-AND**: `p_active = product(magnitudes)` si todos activos, else leak.
- **Noisy-MAX/MIN**: para variables multi-estado. Usa tablas de influencia
  por padre con stochastic dominance.

Ventaja sobre nuestro edge_strength Dirichlet: las CPDs tipo Noisy-OR son
**mecanisticamente interpretables**. "El padre A activa al hijo con 70% de
probabilidad, independiente del padre B." Esto es mas cercano a como un
cientifico piensa sobre mecanismos.

Pregunta abierta: integrar Noisy-OR como modo alternativo de CPD generation?
Podria ser un parametro del Parameterizer: `cpd_mode = "dirichlet" | "noisy_or"`.
El modo Noisy-OR seria mas interpretable para mecanismos rivales (cada mecanismo
tiene su "activation probability" independiente).

**3. do-intervention via graph surgery (adoptar en v3)**

Para tareas de intervencion (do-calculus), Reasoning Core implementa:
1. Deep-copy del modelo
2. Remover TODAS las aristas entrantes al nodo intervenido
3. Reemplazar su CPD con punto masa en el valor de intervencion
4. Correr Variable Elimination normal en el modelo modificado

Esto es exactamente lo que necesitamos para future task types de intervencion
("si eliminamos el compuesto del sedimento, se recupera la produccion?").
pgmpy ya tiene `do()` pero la implementacion manual via graph surgery es
mas transparente y controlable.

**4. SemanticTraceVE — teacher traces como texto natural (explorar en v3)**

Reasoning Core loguea cada paso de Variable Elimination como texto natural:
"Eliminando variable X_2: marginalizando sobre X_2 en el factor phi(X_1, X_2, X_3)..."

Podriamos hacer lo mismo con nuestro teacher solver. No solo registrar
"observe branch_1=low, IG=0.42" sino generar una explicacion narrativa:
"El teacher observo branch_1 porque era el nodo con mayor information gain
(0.42 vs 0.15 para branch_2). Tras observar branch_1=low, la posterior de
target_outcome cambio de [0.33, 0.33, 0.34] a [0.60, 0.25, 0.15], lo que
sugiere que la causa oculta esta activa."

Esto serviria para: (a) generar datos de entrenamiento para agentes,
(b) debugging del teacher, (c) la evaluacion scientist-novice.

**5. JS divergence como alternativa a KL (considerar)**

Reasoning Core usa Jensen-Shannon divergence: `JS(p,q) = 0.5*KL(p||m) + 0.5*KL(q||m)`
donde `m = (p+q)/2`.

Ventajas sobre KL:
- Simetrica (KL no lo es: KL(p||q) != KL(q||p))
- Bounded [0, ln(2)] (KL puede ser infinito si q tiene ceros)
- Mas estable numericamente

Con exponente alto (power=128) se vuelve casi binaria: near-perfect = 1.0,
cualquier error = 0.0. Util para rewards en RL.

Pregunta abierta: cambiar de KL a JS como metrica principal, o mantener KL
y agregar JS como metrica complementaria? KL es mas estandar en la literatura
bayesiana. JS es mas robusta computacionalmente.

**6. Stochastic rounding para dificultad (considerar en v2)**

Mecanismo elegante: un solo parametro `level`, cada llamada a `update()`
incrementa float values suavemente, y al leer se aplica redondeo estocastico.

```
level 0: 3 nodes, 2 states, 1 decimal
level 1: ~3-4 nodes, ~2-3 states (stochastic)
level 3: ~4-5 nodes, ~3-4 states
level 5: ~5-6 nodes, ~4-5 states
```

Para SREG: un `difficulty_level` que escala proporcionalmente num_nodes,
edge_strength (inverso), num_latents, etc. Un solo knob para controlar
la complejidad general del mundo.

### De PCG en general: teoria aplicable

**1. Design Space como CSP (guia conceptual)**

Smith & Mateas (2011): definir formalmente el espacio de BNs validos e
interesantes. Variables = nodos, aristas, CPD params. Restricciones duras =
DAG aciclico, CPDs validas. Restricciones blandas = entropia en rango,
hipotesis distinguibles. No necesariamente usamos un CSP solver, pero el
pensamiento declarativo guia nuestro QualityChecker.

**2. Generate-and-Test es nuestro patron (ya adoptado)**

El patron basico de PCG: generar candidatos, testear contra fitness function,
aceptar o rechazar. Es exactamente lo que hacemos con WorldGen + WorldCheck.

**3. Simulation-based fitness es nuestra ventaja (ya adoptado)**

Togelius identifica tres tipos de fitness:
- **Theory-driven**: "KL > 0.05" (reglas del disenador)
- **Data-driven**: calibrado contra problemas reales (no tenemos aun)
- **Simulation-based**: correr un agente y evaluar su experiencia

El teacher solver es nuestra fitness function simulation-based. Es la mas
poderosa de las tres y ya la tenemos.

---

## Posicionamiento: que hace SREG que otros no hacen

Despues de investigar BoxingGym, DiscoveryWorld, y Reasoning Core a fondo,
confirmamos que SREG ocupa un nicho que ninguno de ellos cubre completamente:

| Dimension | BoxingGym | DiscoveryWorld | Reasoning Core | SREG |
|---|---|---|---|---|
| **Mundos** | 10 fijos, hand-crafted | 8 temas, parametrizados | Procedural, escala masiva | Procedural, quality-filtered |
| **Verdad formal** | PyMC generativo | Ad-hoc por tema | BN + pgmpy | BN + pgmpy |
| **Semantica** | Descripciones textuales | Mundo virtual 2D | Variables X_0, X_1 | Narrativa + nombres realistas |
| **Interaccion** | 10 experimentos max | Acciones fisicas (grid) | One-shot (no interactivo) | Budget + observaciones |
| **Evaluacion** | Prediction error + EIG | Completion + proceso + conocimiento | JS divergence | KL + IG ratio + accuracy |
| **Tasks por caso** | 1 (predict) | 1 (discover) | 1 (compute posterior) | 3+ (infer + NBO + hypothesis) |
| **Mecanismos rivales** | No | Distractores informales | No | Planeado (etapa 3) |
| **Escalabilidad** | Limitada (10 envs) | 120 instancias | 10M+ problemas | Ilimitada por diseno |

**Lo que SREG combina que nadie mas tiene**:
- World model formal y verificable (como Reasoning Core)
- Generacion procedural de mundos (como Reasoning Core, pero con quality filters)
- Semantica de investigacion realista (como DiscoveryWorld, pero con BN formal)
- Experimental design evaluation (como BoxingGym, pero con multiples tasks)
- Mechanism-first con hipotesis rivales (unico)
- Case bundles con evaluaciones multiples (parcialmente en DiscoveryWorld)

---

## Plan de implementacion

### Slice minimo: prototipo DAGSpec (en curso)

Objetivo: validar que el stack actual sobrevive a mundos arbitrarios de 10-15
nodos. NO es v2 completa — es el contrato tecnico intermedio que despues
`MechanismSpec -> WorldComposer` enchufara arriba sin romper nada.

**Archivos nuevos:**

| Archivo | Que es |
|---|---|
| `src/sreg/models/dag_spec.py` | `DAGSpec` + `DAGNodeSpec` — Pydantic con validaciones (aciclico, max parents <=4, al menos 1 target + 1 observable, nodos referenciados en edges existen, sin duplicados) |
| `src/sreg/world/cpd_gen.py` | CPD generation extraida — hoy esta copy-pasteada identica en los 3 templates. Extraerla permite reusar y soportar estados heterogeneos por nodo |
| `src/sreg/world/templates/custom.py` | `CustomTemplate.generate(dag_spec, edge_strength, seed) -> World` — acepta cualquier DAGSpec valido |
| `tests/tools/test_custom_template.py` | Tests: DAGs de 5 a 15 nodos, E2E con TaskGen, teacher solver |

**Archivos modificados:**

| Archivo | Que cambia |
|---|---|
| `src/sreg/models/__init__.py` | Exportar DAGSpec, DAGNodeSpec |
| `src/sreg/world/templates/__init__.py` | Exportar CustomTemplate |
| `src/sreg/tools/world_gen.py` | Metodo `generate_custom(CustomWorldGenConfig)` separado |
| `src/sreg/tools/world_check.py` | Check de max parents + metrica de treewidth (warning, no fallo) |

**Orden:**
1. DAGSpec model (puro contrato, sin dependencias)
2. CPD generation utility (extraer de templates, verificar resultados identicos)
3. CustomTemplate (el core: DAGSpec + edge_strength -> World)
4. WorldGenTool extension (registrar custom)
5. WorldCheck extensions (max parents + treewidth)
6. E2E validation (TaskGen con 10-15 nodos, teacher, quality metrics)
7. Docs (TODO, CURRENT_STATE, CHANGELOG, CLAUDE)

**Decisiones clave del prototipo:**
- Templates existentes NO se tocan. CustomTemplate es un camino paralelo.
- `generate_custom()` es metodo separado, no se cambia `generate()`.
  **Nota: la API se unificara** — `generate()` y `generate_custom()` como
  metodos separados es temporal (por seguridad en este slice). Se unificaran
  bajo una sola API de generacion. Pero los dos CAMINOS de entrada (DAG
  generators automaticos + DAGSpec manual/LLM) son permanentes y
  complementarios — ver seccion "Entradas alternativas al DAGSpec".
- DAGSpec soporta estados heterogeneos (2 y 3 estados mezclados).
- El `role` en DAGNodeSpec es string libre (metadata), no afecta generacion.
- Target se sigue llamando "target_outcome" por compatibilidad.
- Despues los templates existentes podrian convertirse en funciones que
  generan DAGSpecs (`latent_preference_spec() -> DAGSpec`), pero eso es
  un refactor posterior.

**Riesgos identificados:**

| Riesgo | Mitigacion |
|---|---|
| Variable Elimination lenta en 15 nodos | max_parents=4 acota treewidth. Loguear treewidth. |
| CPDs ruidosas con 4 padres (81 combinaciones) | Testear con edge_strength >= 0.5 en mundos grandes. |
| NBO trivial mas frecuente en mundos grandes | Es aprendizaje valioso — documentar en hallazgos. |
| Estados heterogeneos con wrapping | La formula ya los maneja (`p_state % num_states`). Testear. |

**Criterio de exito:**
- Mundo custom de 12-15 nodos con 2-3 latentes pasa WorldCheck
- Los 3 task types se generan exitosamente
- Teacher solver mejora claramente sobre el prior y supera ampliamente a random
  (no usamos "teacher >60% accuracy" porque depende mucho de la task y del
  numero de estados — la mejora relativa es mas robusta como criterio)
- TaskGen produce una proporcion razonable de tasks no degeneradas:
  NBO con IG > 0 en al menos ~70% de los casos, hipotesis distinguibles
  (KL > 0.05) en al menos ~80%. Si la tasa de tasks degeneradas es alta
  (e.g., >50% triviales), es un hallazgo importante pero el slice no fue
  tan exitoso como parece.
- Datos concretos de que se rompe, documentados en la seccion de hallazgos

### Siguiente: mechanism-first — v3 (etapa 3)

7. MechanismSpec model (estructura + semantica + variables compartidas)
8. Libreria base de mecanismos (5-10 mecanismos reutilizables)
9. WorldComposer que combina mecanismos en un mundo
10. Mecanismos rivales como hipotesis competidoras
11. Nuevas tasks: structure selection, experimental design
12. Quality checker robusto con metricas de generador

### Integracion LLM + DAGSpec (v2-v3, prioritario)

13. **LLM orchestrator tools para DAGSpec** — dos tools nuevos:
    - `dag_generate`: LLM elige generador + parametros -> DAGSpec automatico
    - `dag_construct`: LLM especifica nodos y aristas manualmente -> DAGSpec custom
14. Seeds desde papers (LLM extrae estructura causal -> `dag_construct`)

### Mas adelante

15. CaseBundle como modelo formal
16. Dimension temporal (DBNs o multi-slice)
17. Variables continuas / mixtas

---

## Notas de diseno

### Por que NO empezar con DAGs random libres

1. La mayoria de DAGs random son epistemologicamente inutiles
   - Estructura trivial o imposible
   - Sin hipotesis interesantes
   - Sin estrategia de observacion no trivial

2. No sabemos que razonamiento testean
   - Un template curado testea "diagnostico" o "propagacion"
   - Un DAG random testea... algo. No sabemos que.

3. La calidad no se puede filtrar si no la podes definir
   - Primero necesitamos quality checks robustos (de etapa 2)
   - Despues podemos aplicarlos a DAGs mas libres

### Por que SI necesitamos eventualmente DAGs flexibles

1. Los mundos reales no son combinaciones limpias de motifs
   - Tienen irregularidades, excepciones, patrones inusuales

2. Seeds desde papers o descripciones producen DAGs arbitrarios
   - No podemos forzar que un paper real se ajuste a "2 forks + 1 chain"

3. Para escalar a 20-30 nodos, la composicion manual se vuelve tediosa

### La formula de CPDs ya es generica

El generador de CPDs basado en edge_strength (formula Dirichlet con
`base = max(0.1, (1-es)*2)`, `alpha[dominant] += es*15`) funciona para
cualquier DAG. No depende de la forma. **Esta es la pieza clave que hace
viable el custom template** — no hay que reinventar la generacion de CPDs.

---

## Fundamentos de razonamiento causal y cientifico (research 2026-03-09)

> **Investigacion teorica** para fundamentar el catalogo de evaluaciones.
> Fuentes principales: Judea Pearl (do-calculus, escalera de causalidad),
> Richard McElreath (Statistical Rethinking, confounders elementales),
> benchmarks existentes (CausalBench, CauSciBench, CausalProbe-2024).
> Esta seccion es referencia conceptual — no es un plan de implementacion.

### La escalera de causalidad de Pearl

Pearl define tres niveles cualitativamente distintos de razonamiento causal.
Cada nivel requiere informacion que el nivel inferior NO puede proveer
(demostrado formalmente por el Causal Hierarchy Theorem).

```
Escalon 3: CONTRAFACTUAL (imaginar)
  P(Y_x' | X=x, Y=y)
  "Este paciente tomo el medicamento y se curo.
   Se habria curado SIN tomarlo?"
  Requiere: SCM completo (ecuaciones estructurales + ruido)
  ──────────────────────────────────────────────────
Escalon 2: INTERVENCION (hacer)
  P(Y | do(X=x))
  "Si FORZAMOS a todos los pacientes a tomar el medicamento,
   cual seria la tasa de recuperacion?"
  Requiere: DAG causal (para graph surgery / do-calculus)
  ──────────────────────────────────────────────────
Escalon 1: ASOCIACION (ver)
  P(Y | X=x)
  "Los pacientes que tomaron el medicamento tuvieron mejor
   tasa de recuperacion."
  Requiere: datos observacionales
```

**Donde esta SREG hoy:**
- Escalon 1: `infer_target`, `hypothesis_selection`, `next_best_observation`
- Escalon 2: `causal_effect` (recien implementado)
- Escalon 3: no implementado (requiere SCM, no solo DAG+CPDs)

**Por que importa la distincion:**
- `P(Y | X=x)` != `P(Y | do(X=x))` cuando hay confounders.
  Observar que alguien toma un medicamento (quizas porque esta mas enfermo)
  es distinto de forzar a todos a tomarlo (ensayo clinico).
- `do(X=x)` = mutilar el grafo eliminando todas las flechas que llegan a X,
  luego calcular P(Y) en el grafo mutilado. Esto "corta" la influencia de
  los confounders sobre X.
- Los contrafactuales son retrospectivos y sobre individuos especificos.
  Requieren un modelo estructural completo, no solo un DAG con CPDs.

**Implicancia para el catalogo de evaluaciones:**
El catalogo debe cubrir al menos los escalones 1 y 2. El escalon 3 es futuro
y requiere infraestructura nueva (SCM). Pero dentro de cada escalon hay
muchas preguntas cientificas distintas — no se trata solo de "calcular
una probabilidad" sino de razonar sobre la estructura causal.

### Los 4 confounders elementales de McElreath

Statistical Rethinking (cap. 5-6) identifica 4 patrones fundamentales
que todo investigador debe reconocer. Cada uno produce un tipo diferente
de error si se trata incorrectamente.

```
1. FORK (causa comun)           2. PIPE (mediador/cadena)

     Z                              X -> Z -> Y
    / \
   X   Y                      Z media el efecto de X sobre Y.
                               Condicionar en Z BLOQUEA el camino causal.
X e Y parecen correlacionados  ERROR: "post-treatment bias" si controlas
pero no hay relacion causal.   por el mediador cuando queres el efecto total.
Condicionar en Z elimina
la correlacion espuria.
ERROR: confounding si no
controlas por Z.

3. COLLIDER                     4. DESCENDANT

   X -> Z <- Y                    X -> Z <- Y
                                       |
X e Y son independientes,              D
pero condicionar en Z crea
una correlacion espuria.        Condicionar en D (descendiente de Z)
ERROR: "Berkson's paradox",     produce una version ATENUADA del
"explaining away".              efecto del patron original.
Condicionar abre un camino      ERROR: efecto parcial inesperado.
que deberia estar cerrado.
```

**El "Haunted DAG" de McElreath (cap. 6):**
Cuando hay un confounder NO observado, puede producir collider bias
a traves de variables observadas. El agente ve correlaciones fantasma
causadas por una variable que no puede medir directamente. Esta situacion
aparece naturalmente en nuestros mundos (nodos LATENT = no observables).

**Cada patron mapea a un tipo de pregunta cientifica:**

| Patron | Pregunta cientifica | Eval type potencial |
|---|---|---|
| Fork | "Esta correlacion es espuria?" | `should_condition`, `adjustment_set` |
| Pipe | "Debo controlar por este mediador?" | `should_condition`, `mediation` |
| Collider | "Observar Z cambia la relacion X-Y?" | `should_condition`, `explaining_away` |
| Descendant | "Este proxy me da informacion util?" | `conditional_independence` |

**Inspiracion adicional de McElreath:**
- Cap. 8: Interacciones — el efecto de X sobre Y DEPENDE de Z
- Cap. 13: Modelos con memoria — autocorrelacion y procesos dinamicos
- Cap. 14: Instrumentos y disenos causales — variables instrumentales
- Cap. 15: Missing data y measurement error — datos incompletos y ruidosos
- Cap. 16: Dinamica poblacional — sistemas que cambian en el tiempo

Varios de estos temas (missing data, instrumentos, interacciones) son
directamente modelables con BNs y estan en el horizonte de SREG.

### Principio de diseno: tasks como preguntas cientificas

> **El catalogo de eval types deberia parecerse a un catalogo de preguntas
> cientificas, no a un catalogo de metricas de benchmark.**

Esta es la regla de oro para decidir que eval types agregar. El filtro es:

> **¿Esto se siente como una subtask de un research case real,
> o como un ejercicio abstracto de DAGs?**

Ejemplos:
- "¿Son X e Y d-separados dado Z?" → ejercicio de grafos (malo)
- "Si ya conocemos la composicion del suelo, ¿importa medir la lluvia
  para predecir el rendimiento?" → pregunta cientifica (bueno)

La diferencia no esta en el eval type, sino en el FRAMING. El mismo
`conditional_independence` puede ser abstracto o cientifico segun como
el orchestrator lo formule dentro del research case.

**Distincion de tres niveles (arquitectura conceptual):**

```
eval type          = familia abstracta (ej. "adjustment_set")
                     → define QUE se evalua y COMO se puntua
                     → implementado como TaskType + scoring method

question template  = como se formula la pregunta
                     → puede ser abstracto o cientifico
                     → implementado como question_text en EvalQuestionPlan

research subtask   = pregunta concreta dentro del caso
                     → nace del research case, no del DAG
                     → implementado como CasePlan + generate_from_plan
```

**Ya tenemos la arquitectura para esto.** CasePlan + EvalQuestionPlan +
generate_from_plan ES exactamente este patron de tres niveles. El eval_type
define la mecanica formal, el question_text da el framing cientifico,
y el research_context del CasePlan da el caso de investigacion.

**Consecuencia practica:** no necesitamos infraestructura nueva para que
las tasks se sientan como preguntas cientificas. Necesitamos (a) ampliar
el catalogo de eval types y (b) que el orchestrator genere buenos
question_text dentro de CasePlans convincentes.

---

## Dimensiones de inspiracion desde papers reales (research 2026-03-14)

> **Principio fundamental**: un paper INSPIRA el SRC, no lo replica. SREG
> toma la problematica y el tipo de investigacion del paper, pero construye
> un mundo NUEVO que conoce perfectamente (BN exacta con reward signal).
>
> Estas son las dimensiones que el orchestrator debe EXTRAER de un paper
> real para crear un caso sintetico creible. No son dimensiones teoricas
> de "que es investigacion" — son cosas PRACTICAS que el sistema lee
> de un paper y usa para disenar el SRC.
>
> Fuentes: analisis de paper real (Pedersen et al. 2022, asma infantil
> y contaminacion del aire, 1M+ sujetos) + Codex (2026-03-14)

### Las 8 dimensiones de inspiracion

**1. Dominio y problematica**: de que trata la investigacion, por que importa.
   - Ejemplo paper danes: "contaminacion del aire durante el embarazo aumenta
     el riesgo de asma infantil — pero cuanto? y por que mecanismo?"
   - Que inspira en SREG: el contexto narrativo, los stakes, el dominio ficticio.

**2. Escala y complejidad**: cuantas variables, cuantas relaciones, cuantos
   factores tiene que manejar el investigador a la vez.
   - Ejemplo: 13 contaminantes, 20+ covariables, 4 tipos de outcome, 3 cohortes.
   - Que inspira: cantidad de nodos en el DAG, cantidad de tasks, budget.

**3. Estructura causal que se intuye**: confounders, mediadores, colliders,
   variables latentes. El paper a veces muestra un DAG, a veces se deduce.
   - Ejemplo: SES confunde la relacion contaminacion-asma. Tabaquismo materno
     confunde tambien. Prenatal care es mediador. Hay posibles colliders.
   - Que inspira: la topologia del BN, tipos de nodos, relaciones entre variables.

**4. Tipo de datos y sus problemas**: de donde vienen los datos, como se
   recolectaron, que problemas tienen. Esto es CLAVE — los datos reales
   son sucios, incompletos, y con sesgos.
   - Ejemplo: 3 fuentes (registro nacional, cohorte con encuestas, cohorte
     clinica). 7% excluido por faltantes. Definiciones de asma inconsistentes.
     Attrition diferencial (los mas pobres abandonan mas).
   - Que inspira: tipo de datasets, datos faltantes, multiples fuentes,
     narrativas de recoleccion.

**5. Tipo de trabajo**: que HACEN los investigadores — no solo que modelo
   usan, sino como abordan el problema.
   - Ejemplo: ajustan progresivamente (modelos 1-5 con mas covariables),
     hacen two-pollutant models, estratifican por sexo, usan splines para
     no-linealidad, comparan definiciones de asma.
   - Que inspira: el tipo de eval types, la complejidad de las preguntas,
     las acciones disponibles.

**6. Tipo de preguntas que se hacen**: las preguntas REALES de la investigacion,
   que mapean a nuestros eval types.
   - Ejemplo: "hay efecto causal de PM2.5 sobre asma?" (causal_effect).
     "que variables ajustar?" (adjustment_set). "el efecto es lineal?"
     "varia por sexo?" (futuro: heterogeneidad). "PM2.5 o NO2 importa mas?"
     (compare_interventions).
   - Que inspira: DIRECTAMENTE las tasks del SRC. Esta es quizas la
     dimension mas importante — queremos que las preguntas del SRC sean
     del MISMO TIPO que las de la investigacion real.

**7. Senal vs ruido**: que tan fuerte o sutil es el efecto que buscan.
   - Ejemplo: HR 1.06 por IQR — efecto real pero chico. Solo detectable
     con 1M de sujetos. A nivel individual, casi indistinguible del azar.
   - Que inspira: edge_strength, dificultad del caso, si el agente puede
     o no detectar el efecto con los datos disponibles.

**8. Que puede hacer el investigador**: que acciones de investigacion tiene
   disponibles y cuales no.
   - Ejemplo: pueden medir mas contaminantes, estratificar por subgrupo,
     pedir biomarcadores. NO pueden hacer un RCT (no se puede asignar
     contaminacion aleatoriamente). Pueden hacer analisis de sensibilidad.
   - Que inspira: las research_actions del SRC, observe vs intervene,
     costos, restricciones.

### Ejemplo aplicado: del paper danes al SRC

| Dimension | Paper real | SRC inspirado |
|---|---|---|
| Dominio | Epidemiologia perinatal, Dinamarca | Estacion de investigacion en archipielago ficticio |
| Escala | 13 contaminantes, 20+ covariables | 8-12 nodos, 5 tasks |
| Estructura causal | SES confunde, tabaquismo confunde, prenatal care media | DAG con confounders + mediador + collider |
| Datos | 3 fuentes, 7% missing, definiciones inconsistentes | Multi-dataset, % faltantes, narrativa de fuente |
| Tipo de trabajo | Ajuste progresivo, two-pollutant models, sensibilidad | Preguntas que requieren analisis similar |
| Preguntas | Efecto causal? Que ajustar? Lineal? Subgrupos? | causal_effect, adjustment_set, should_condition |
| Senal | HR 1.06, sutil | edge_strength moderado, caso no trivial |
| Acciones | Medir contaminantes, estratificar, NO experimentar | observe (costo variable), intervene limitado |

### Que puede SREG hacer hoy vs futuro

| Dimension | Hoy | Proximo | Futuro |
|---|---|---|---|
| 1. Dominio | OK narrativa + contexto | — | — |
| 2. Escala | OK DAGSpec configurable | — | — |
| 3. Estructura causal | OK todos los tipos | — | — |
| 4. Datos y problemas | OK basico (multi-dataset, % missing) | Proveniencia, MNAR | Sesgo de seleccion |
| 5. Tipo de trabajo | OK parcial (9 eval types) | Mas eval types | Ambiguedad analitica |
| 6. Preguntas | OK 9 eval types | Ola 2 (simpson, mediacion) | Ola 3 |
| 7. Senal vs ruido | OK parcial (edge_strength) | CPDs con direccion | Control fino |
| 8. Acciones | OK observe + intervene | Costos realistas | request_dataset, consult |

### Hallazgos de la evaluacion 5-SRC (2026-03-15)

> 5 SRCs generados desde papers reales de dominios distintos:
> 1. Vaca Muerta (oil & gas, 16 nodos)
> 2. Smoking/Birthweight (epidemiologia perinatal, 9 nodos)
> 3. Alcohol/COVID HCW (salud ocupacional, 12 nodos)
> 4. Coral Reef Bleaching (ecologia marina, 15 nodos)
> 5. School Performance (educacion/sociologia, 15 nodos)
>
> Todos generados con --inspect --solve --report. Resultados en experiments/eval_*/

**Lo que funciona:**
- End-to-end generation en 5 dominios distintos
- CPDs con direccion correcta post-fix (smoking=heavy -> 97% preterm)
- Escala razonable (9-16 nodos por caso)
- Narrativas relevantes y apropiadas por dominio
- 5 tasks por caso, variedad de eval types

**Problema critico: el agente no investiga**
- Budget usado: 0/9, 0/5, 0/7, **6/9**, 0/8
- Solo en 1 de 5 casos el agente uso research_actions
- El dataset CSV expone TODAS las variables observables de entrada
- El agente analiza el dataset con python_exec y responde sin medir nada
- Codex: "es un benchmark causal con wrappers realistas, no un ambiente
  de investigacion. Si el agente puede saltear el loop de investigar,
  no estamos entrenando investigacion"

**Estructura causal**
- DAGs tienden a ser convergentes (todo apunta al target)
- Faltan confounders y mediadores que el seed implica
- Inspiration Report: causal structure 20-60%

**Calidad de respuestas**
- Mezcla de GOOD y POOR por caso (no uniformemente malos)
- POOR scores ambiguos: puede ser el agente O el ambiente
- Tareas faciles se resuelven sin investigar, tareas dificiles fallan

**Diagnostico general (Codex):**
> "Un ambiente de investigacion real tiene tres propiedades:
> 1. Incertidumbre util: el agente empieza materialmente ignorante
> 2. Acciones consecuentes: medir/intervenir cambia lo que se puede saber
> 3. Presion de identificacion: algunas preguntas solo se responden
>    despues de reunir la evidencia correcta
>
> Los dominios se sienten reales, pero el loop de interaccion no."

**Siguiente paso: LOOP.1 — ocultar variables en el dataset para forzar
investigacion. Ver TODO.md.**

## Diseno de Research Cases — del TaskBundle al ResearchCase (analisis 2026-03-09)

> **Este es el analisis mas importante del proyecto hasta ahora.** Cambia la
> perspectiva de como pensamos las tareas y evaluaciones.

### El problema central: tasks fijas vs cases de investigacion

Hoy, para cada mundo se generan siempre las mismas 3 tasks:
1. `infer_target` — estima P(target | evidence)
2. `next_best_observation` — que variable medirias?
3. `hypothesis_selection` — cual de estas 4 hipotesis es correcta?

Esto no se alinea con PROJECT.md. Los ejemplos de Nelvara, pozos de petroleo,
y material anticorrosivo muestran **preguntas que nacen del caso de investigacion**,
no de un template fijo de evaluaciones. Cada caso tiene preguntas diferentes
porque cada investigacion es diferente.

El producto de SREG no es "un mundo + siempre las mismas 3 evaluaciones". Es
un **caso de investigacion completo** con preguntas que tienen sentido para
ese caso en particular.

### Insight fundamental: las preguntas nacen del caso, no del mundo formal

El modelo mental NO es:

```
world → tasks
```

El modelo mental correcto es:

```
real case seed → orchestrator diseña el research case → tools construyen
                 el mundo formal que lo soporta y lo hace verificable
```

El flujo concreto:

```
Caso de investigacion real (paper, escenario, seed)
  → Orchestrator lee/entiende el seed y extrae:
    - fenomeno investigado
    - variables relevantes
    - hipotesis en juego
    - evidencia disponible
    - preguntas de investigacion
    - subtasks y tipo de validacion
  → Orchestrator diseña un caso sintetico INSPIRADO en el real:
    - Define la estructura causal (→ BN formal)
    - Define la narrativa y los datos (→ capa semantica)
    - Define las preguntas y sub-preguntas (→ evaluaciones)
    - Define las acciones y costos (→ interacciones)
  → Tools construyen el BN, validan, y verifican que cada pregunta
    tenga respuesta computable desde la red bayesiana
  → Se arma el ResearchCase
```

**Consecuencia clave: las tasks, subtasks y evaluaciones estan ligadas al
research case, no solo al DAG subyacente.** El DAG sigue siendo esencial
— es la estructura de verdad y validacion que hace todo verificable — pero
no es la unica fuente de que preguntas hacer. Las preguntas nacen del caso
de investigacion que las inspiro.
Un caso sobre arenamiento de pozos naturalmente tiene preguntas sobre mecanismos,
intervenciones, y datos temporales. Un caso sobre un material anticorrosivo
tiene preguntas sobre diagnostico, seleccion de ensayos, y modificaciones
experimentales. Las preguntas no son las mismas porque los casos no son iguales.

### El rol ampliado del orchestrator

Hoy el orchestrator:
1. Genera la estructura del mundo (DAG)
2. Le pone nombres y narrativa (semantica)

Deberia:
1. **Entender el seed** — sea un paper, un escenario, o un tema
2. **Diseñar el caso de investigacion** — que variables, que relaciones,
   que contexto, que datos
3. **Proponer las preguntas** — principal + sub-preguntas, cada una con
   un tipo de evaluacion del catalogo
4. **Definir acciones y costos** — que puede hacer el agente, cuanto cuesta
5. **Los tools validan todo** — que el BN sea correcto, que las preguntas
   tengan respuesta computable, que las evaluaciones no sean triviales

**Principio clave: el orchestrator propone, los tools validan.** El LLM no
decide libremente — propone un caso y el sistema verifica que es viable,
interesante, y formalmente evaluable.

### Comparacion con ResearchGym

ResearchGym es un benchmark de agentes de investigacion que usa repos reales
(codigo + datos + baselines). Puntos relevantes para nuestro diseno:

| Concepto ResearchGym | Equivalente SREG |
|---|---|
| Task = repo con datos y baselines | ResearchCase = mundo + datos + acciones |
| Subtasks = datasets/settings del paper | Sub-preguntas del caso |
| Primary subtask = la que mas importa | Pregunta principal del caso |
| Grader = corre codigo, compara outputs | Grader = compara con verdad del BN |
| Baseline = mejor metodo del repo | Teacher = upper bound (optimo bayesiano) |
| Completion rate = cuantas subtasks intento | Cuantas preguntas del caso respondio |
| Improvement rate = cuantas mejoro | En cuantas supero al prior/random |
| Inspection agent = detecta cheating | No es prioridad (verdad formal, mundos nuevos), pero no descartado |

**Diferencia clave**: ResearchGym usa repos reales (finitos, contaminables).
SREG genera casos sinteticos infinitos con verdad formal verificable. La
ventaja de SREG es que la evaluacion es exacta y los casos son nuevos. La
desventaja es que todavia no tienen la riqueza de un research case real.

**Lo que tomamos de ResearchGym:**
- Estructura de task principal + subtasks
- Grading multi-dimensional (completion + improvement + efficiency)
- La idea de que el caso es una unidad, no tasks sueltas
- Metricas separadas: completion rate vs improvement rate

**Lo que NO tomamos (por ahora):**
- Ejecucion de codigo como parte del caso (futuro posible)
- Anti-cheating activo (no es prioridad, pero no descartado)
- Duracion de horas (nuestros casos son mas acotados)

### ResearchCase como generalizacion de TaskBundle

`ResearchCase` no reemplaza `TaskBundle` de golpe — lo generaliza:

```
TaskBundle (hoy):
  - infer_target: Task          # siempre
  - next_best_observation: Task # siempre
  - hypothesis_selection: Task  # siempre

ResearchCase (vision):
  - world: World
  - narrative: str                          # contexto del caso
  - primary_question: EvalQuestion          # la pregunta principal
  - sub_questions: list[EvalQuestion]       # 0-N subpreguntas
  - data_assets: list[DataAsset]            # datos del caso
  - available_actions: list[Action]         # acciones con costos
  - shared_budget: int                      # budget para todo el caso
  - evaluation_objective: str               # que se quiere medir

EvalQuestion:
  - question_text: str                      # en lenguaje natural
  - eval_type: EvalType                     # del catalogo
  - ground_truth: dict                      # respuesta correcta (del BN)
  - weight: float                           # peso en el score compuesto
```

**La transicion tiene dos ejes independientes que se necesitan mutuamente:**

**Eje A — Que el orchestrator elija mejor** (que preguntas, cuantas, por que):
- [x] A.0: CasePlan model + design_case tool (el andamiaje)
- A.1: Case plan quality validation
- A.2: E2E con LLM real usando design_case
- A.3: Tests con combinaciones variadas (1, 2, 3 preguntas, sin infer_target, etc.)
- A.4: Budget compartido, preguntas conectadas
- A.5: Paper-seeded cases

**Eje B — Ampliar el catalogo de eval types** (que preguntas PUEDE hacer):
- [x] B.1: `causal_effect` — do-calculus (implementado, 14 tests)
- B.2 (ola 1): `best_intervention` — argmax sobre do()
- B.3 (ola 1): `compare_interventions` — do(X) vs do(Z)
- B.4 (ola 1): `adjustment_set` — backdoor adjustment sets
- B.5 (ola 1): `should_condition` — los 4 elemental confounds
- B.6 (ola 1): `infer_latent_cause` — posterior sobre nodo latente
- B.7 (ola 2): `simpson_paradox`, `mediation`, `confounder_detection`
- B.8 (ola 3): `mechanism_selection`, `structure_discovery`, `prediction`, etc.

Ver catalogo completo de 31 eval types en 6 familias arriba
("Catalogo de evaluaciones cientificas").

Sin el Eje B, el Eje A es "elegir entre las mismas opciones de siempre".
Sin el Eje A, el Eje B es "tener muchos tipos pero siempre usarlos todos".
Ambos ejes se necesitan para que el sistema se parezca a la vision de PROJECT.md.

### Catalogo de evaluaciones cientificas (research 2026-03-09)

> **Catalogo completo de evaluaciones posibles sobre un research case.**
> Organizado en 6 familias de razonamiento cientifico. Cada eval type tiene
> una pregunta cientifica, un ground truth computable, y una metrica de scoring.
> El catalogo crece incrementalmente — no se implementan todas a la vez.
>
> **Fuentes**: Pearl (do-calculus, escalera de causalidad), McElreath
> (Statistical Rethinking, elemental confounds), CauSciBench, CausalBench,
> ResearchGym, PROJECT.md, y analisis conjunto de multiples perspectivas.
>
> **Principio de diseno**: ver seccion "Fundamentos de razonamiento causal"
> arriba. Las tasks deben sentirse como preguntas cientificas de un case,
> no como ejercicios abstractos de DAGs.

#### Las 6 familias de evaluacion

##### A. Diagnosis / explanation — "¿Que esta pasando?"

| # | Eval type | Pregunta cientifica | Ground truth | Scoring | Status |
|---|---|---|---|---|---|
| 1 | `infer_target` | Dada la evidencia, cual es la distribucion del target? | Posterior exacta P(T\|E) | KL divergence | **Implementado** |
| 2 | `infer_latent_cause` | Que causa oculta explica lo que vemos? | Posterior sobre nodo latente P(L\|E) | KL divergence | Proxima ola |
| 3 | `hypothesis_selection` | Cual de estas hipotesis explica mejor los datos? | KL de cada hipotesis vs posterior verdadera | Accuracy (eligio la mejor?) | **Implementado** |
| 4 | `mechanism_selection` | Cual mecanismo genero los datos? | BN verdadero vs rivales (KL o likelihood ratio) | Accuracy o ranking | Requiere MechanismSpec v3 |
| 5 | `explain_anomaly` | Que mecanismo explica este patron raro? | Posterior condicionado en evidencia anomala | KL o accuracy | Futuro |

**Notas:**
- `infer_latent_cause` es la inversion de `infer_target`: en vez de predecir
  el outcome, el agente infiere la variable oculta que lo explica. Es lo que
  hace un medico ("dados los sintomas, cual es la enfermedad?"). pgmpy lo
  soporta directamente (posterior sobre nodo LATENT).
- `mechanism_selection` es la generalizacion mas potente de `hypothesis_selection`.
  En vez de elegir entre distribuciones, el agente elige entre mecanismos causales
  completos (diferentes DAGs que generan datos similares). Requiere infraestructura
  de mecanismos rivales (MechanismSpec v3, ver seccion correspondiente).
- `explain_anomaly` es especialmente interesante para casos con outliers:
  "el paciente tiene todos los sintomas de A, pero el tratamiento no funciona".

##### B. Evidence gathering / experimental design — "¿Como investigo mejor?"

| # | Eval type | Pregunta cientifica | Ground truth | Scoring | Status |
|---|---|---|---|---|---|
| 6 | `next_best_observation` | Que variable conviene medir ahora? | IG ranking de nodos restantes | IG ratio (elegido/optimo) | **Implementado** |
| 7 | `best_observation_under_cost` | Igual que NBO, pero con costos distintos por accion | IG/costo ranking | IG-per-cost ratio | Futuro (requiere rich actions) |
| 8 | `best_measurement_bundle` | Con budget=K, que combo de mediciones es optimo? | IG acumulada de combinaciones | Ratio vs optimo | Futuro |
| 9 | `best_experiment_to_disambiguate` | Tengo 2 hipotesis rivales. Que medicion las separa mejor? | IG sobre hipotesis (no sobre target) | IG ratio | Requiere mecanismos rivales |
| 10 | `sequential_design` | Elegir la mejor secuencia de acciones (no solo la primera) | Trayectoria optima del teacher | Entropy reduction ratio | Parcial (teacher trajectory) |
| 11 | `research_efficiency` | Que tan bien uso el budget para reducir incertidumbre? | Entropy reduction por unidad de budget | Ratio vs teacher | Metrica transversal |

**Notas:**
- `best_experiment_to_disambiguate` es brillante conceptualmente: no pregunta
  "que medicion reduce mas la incertidumbre sobre el target" sino "que medicion
  separa mejor dos explicaciones rivales". Es lo que hace un cientifico real
  cuando diseña un experimento. Requiere tener dos hipotesis formales (→ mecanismos
  rivales o dos distribuciones candidatas).
- `research_efficiency` no es un eval type en si, sino una metrica transversal
  que puede aplicarse a cualquier tarea con budget. Ya tenemos las piezas
  (entropy_reduction en QualitySuite).

##### C. Causal intervention — "¿Que pasa si intervengo?"

| # | Eval type | Pregunta cientifica | Ground truth | Scoring | Status |
|---|---|---|---|---|---|
| 12 | `causal_effect` | Si do(X=x), que pasa con Y? | P(Y \| do(X=x)) via graph surgery | KL divergence | **Implementado** |
| 13 | `compare_interventions` | Que cambia mas el outcome: do(X=x) o do(Z=z)? | Comparar P(Y\|do(X)) vs P(Y\|do(Z)) | Accuracy (eligio el mas fuerte?) | Proxima ola |
| 14 | `best_intervention` | Que intervencion maximiza/minimiza Y? | argmax/argmin sobre do() | Effect ratio (agente/optimo) | **Implementado** |
| 15 | `average_treatment_effect` | Cuanto cambia Y en promedio al intervenir? | E[Y\|do(X=1)] - E[Y\|do(X=0)] | Error absoluto | Futuro |
| 16 | `constrained_intervention` | Que accion conviene si solo puedo tocar ciertas variables? | Optimo sobre subconjunto permitido | Regret | Futuro |
| 17 | `mediation` | Que parte del efecto pasa por una variable intermedia? | NDE + NIE via multiples do() queries | Error en proporcion mediada | Despues |

**Notas:**
- `best_intervention` es el paso natural despues de `causal_effect`: en vez de
  "que pasa si do(X=x)", es "que X y que x maximizan Y". Builds directamente
  sobre `causal_query()`. pgmpy lo soporta (iterar sobre do() queries).
- `compare_interventions` es la version binaria mas accesible: "te conviene
  tratar con el medicamento A o el B?". Muy comun en medicina y economia.
- `mediation` descompone el efecto total en directo e indirecto:
  "el medicamento reduce el dolor directamente, o porque reduce la inflamacion
  que causa el dolor?". Computable con multiples do() queries.

##### D. Structure / model discovery — "¿Cual es la estructura causal?"

| # | Eval type | Pregunta cientifica | Ground truth | Scoring | Status |
|---|---|---|---|---|---|
| 18 | `adjustment_set` | Que variables debo controlar para estimar X→Y? | Backdoor adjustment sets validos | Validez del set propuesto | Proxima ola |
| 19 | `should_condition` | Alguien sugiere controlar por Z. Es correcto? | Rol de Z (confounder/mediador/collider) | Accuracy + justificacion | Proxima ola |
| 20 | `simpson_paradox` | Los datos dicen A, la causa dice B. Cual es? | Direccion de P(Y\|do(X)) vs correlacion | Accuracy (direccion correcta) | Despues |
| 21 | `confounder_detection` | Este analisis esta confundido? Por que? | Backdoor paths no bloqueados | Set match (precision/recall) | Despues |
| 22 | `structure_discovery` | Cual es la estructura causal? | DAG real | SHD, edge F1 | Futuro |
| 23 | `skeleton_recovery` | Que variables estan conectadas? (sin direccion) | Skeleton del DAG | F1 de edges | Futuro |

**Notas:**
- `adjustment_set` es LA pregunta central de McElreath. pgmpy la soporta
  directamente: `get_all_backdoor_adjustment_sets(X, Y)` devuelve todos los
  sets validos, `is_valid_backdoor_adjustment_set(X, Y, Z)` valida propuestas.
  Es una pregunta cientifica real ("por que variables ajusto mi regresion?").
- `should_condition` testea directamente los 4 elemental confounds de McElreath.
  La misma pregunta ("controlar por Z?") tiene respuestas OPUESTAS segun si Z
  es un confounder (SI), un mediador (depende), o un collider (NO).
  pgmpy lo soporta via d-separation tests y analisis de paths.
- `simpson_paradox` es la joya: el agente recibe datos que PARECEN decir una cosa,
  pero la estructura causal dice otra. Solo el razonamiento causal (escalon 2)
  permite resolver la paradoja. Computable: do-calculus da el efecto real,
  inferencia estandar da la correlacion engañosa.
- `structure_discovery` y `skeleton_recovery` son las mas ambiciosas.
  pgmpy tiene estructura learning (PC, HillClimb, GES) pero el formato
  de entrada/salida requiere diseno cuidadoso.

##### E. Prediction / forecasting — "¿Que va a pasar?"

| # | Eval type | Pregunta cientifica | Ground truth | Scoring | Status |
|---|---|---|---|---|---|
| 24 | `prediction` | Dado lo observado, que valor tendra Z? | Posterior de Z (no target) | KL divergence | Facil de agregar |
| 25 | `temporal_forecast` | Que pasa en el proximo paso de tiempo? | Posterior en BN temporal | KL o error | Futuro (requiere BN temporal) |
| 26 | `context_shift` | Que pasa si cambian condiciones externas? | Posterior con nuevas evidencias | KL divergence | Futuro |
| 27 | `counterfactual` | "Si hubiera sido X' en vez de X, que habria pasado con Y?" | SCM counterfactual query | KL divergence | Futuro (requiere SCM) |

**Notas:**
- `prediction` es el mas facil de agregar: es `infer_target` pero con un nodo
  distinto al target. La pregunta es "dado lo que sabes, que valor tendra Z?".
  Toda la infraestructura de scoring (KL divergence) ya existe.
- `counterfactual` es escalon 3 de Pearl. Requiere SCM con ecuaciones
  estructurales y variables de ruido, no solo CPDs. pgmpy tiene soporte
  parcial pero es significativamente mas complejo.

##### F. Process / scientific reasoning quality — "¿Como razona?"

| # | Eval type | Pregunta | Como se evalua | Status |
|---|---|---|---|---|
| 28 | `evidence_usage` | Actualizo creencias razonablemente con datos nuevos? | Comparar trayectoria vs teacher | Rubric / metrica |
| 29 | `alternative_hypotheses` | Exploro otras explicaciones? | Rubric sobre diversidad de hipotesis exploradas | LLM-as-judge |
| 30 | `causal_coherence` | El argumento es consistente con la estructura? | Rubric sobre coherencia causal | LLM-as-judge |
| 31 | `research_plan_quality` | Eligio buenas acciones en buen orden? | Comparar con teacher trajectory | Metrica (IG acumulada) |
| 32 | `calibration` | Cuando dice 70% realmente acierta ~70%? | Calibration curve sobre multiples episodios | Brier score, ECE |

**Notas:**
- La familia F es fundamentalmente distinta de las otras: son evaluaciones
  de **proceso**, no de **resultado**. No tienen ground truth puntual del BN.
- `evidence_usage` y `research_plan_quality` son parcialmente formalizables
  (comparar con la trayectoria del teacher). Las demas requieren LLM-as-judge.
- `calibration` requiere multiples episodios del mismo agente para medir.
- PROJECT.md ya contempla estas evaluaciones como futuras.
- **No son prioridad de implementacion** porque (a) no encajan en el patron
  TaskType → correct_answer → VerifierTool, y (b) son ortogonales: se pueden
  agregar encima de cualquier eval type existente.

#### Resumen: inventario de evaluaciones

| Familia | Implementadas | Proxima ola | Despues | Futuro | Total |
|---|---|---|---|---|---|
| A. Diagnosis | 2 | 1 | - | 2 | 5 |
| B. Strategy | 1 | - | - | 4 | 5 |
| C. Intervention | 2 | 1 | 1 | 2 | 6 |
| D. Structure | - | 2 | 2 | 2 | 6 |
| E. Prediction | - | - | - | 4 | 4 |
| F. Process | - | - | - | 5 | 5 |
| **Total** | **5** | **4** | **3** | **19** | **31** |

#### Mapa de implementacion por olas

**Ola 0 — Ya implementado (5 eval types):**
- `infer_target`, `next_best_observation`, `hypothesis_selection`, `causal_effect`, `best_intervention`
- Cubren escalones 1 y 2 de Pearl. Familias A, B, C.

**Ola 1 — Proxima (4 eval types, pgmpy los soporta HOY):**
- `compare_interventions` — binario: do(X) vs do(Z). Facil.
- `adjustment_set` — pgmpy: `get_all_backdoor_adjustment_sets()`.
- `should_condition` — los 4 elemental confounds. d-separation tests.
- `infer_latent_cause` — posterior sobre nodo LATENT. Igual que infer_target.

**Ola 2 — Despues (3 eval types, requieren mas diseno):**
- `simpson_paradox` — generar datos que exhiban la paradoja.
- `mediation` — multiples do() queries para NDE/NIE.
- `confounder_detection` — identificar backdoor paths no bloqueados.

**Ola 3 — Requieren infraestructura nueva:**
- `mechanism_selection` — MechanismSpec v3 (BNs rivales)
- `best_experiment_to_disambiguate` — requiere mecanismos rivales
- `structure_discovery` — formato de DAG como input/output
- `prediction`, `counterfactual`, `temporal_forecast` — varios niveles
- Familia F completa — LLM-as-judge, metricas de proceso

**Criterio de priorizacion (no solo "pgmpy lo soporta"):**

| Criterio | Peso | Razon |
|---|---|---|
| Se siente como pregunta cientifica real? | Alto | Regla de oro del catalogo |
| pgmpy puede computar el ground truth? | Alto | Sin ground truth formal no hay eval verificable |
| Builds on infraestructura existente? | Medio | Implementacion rapida, menos riesgo |
| Cubre una familia no representada? | Medio | Diversidad del catalogo |
| Requiere infraestructura nueva significativa? | Negativo | Retrasa, aumenta complejidad |

#### Soporte en pgmpy

Funciones de pgmpy que soportan evaluaciones del catalogo:

| Funcion pgmpy | Eval types que habilita |
|---|---|
| `VariableElimination.query()` | infer_target, prediction, infer_latent_cause, hypothesis_selection |
| `CausalInference.query(do=...)` | causal_effect, best_intervention, compare_interventions, mediation, ATE |
| `get_all_backdoor_adjustment_sets()` | adjustment_set |
| `is_valid_backdoor_adjustment_set()` | adjustment_set, should_condition |
| `get_all_frontdoor_adjustment_sets()` | adjustment_set (variante) |
| `nx.is_d_separator()` | should_condition, conditional_independence |
| `DAG.get_markov_blanket()` | markov_blanket (no priorizado) |
| `PC / HillClimb / GES` (structure learning) | structure_discovery, skeleton_recovery |

#### Como se conecta con CasePlan y el research case

Un research case realista usa MULTIPLES eval types del catalogo:

```
CasePlan: "Estudio de arenamiento en pozos de petroleo"
  |
  +-- Pregunta principal (eval_type=mechanism_selection):
  |     "Cual mecanismo explica mejor el arenamiento post-fractura?"
  |
  +-- Subtask 1 (eval_type=best_intervention):
  |     "Que tratamiento minimizaria la produccion de arena?"
  |
  +-- Subtask 2 (eval_type=next_best_observation):
  |     "Que dato pedirias para confirmar tu hipotesis?"
  |
  +-- Subtask 3 (eval_type=should_condition):
  |     "Tu colega ajusto por drawdown. Es correcto?"
  |
  +-- Evaluacion transversal (research_plan_quality):
        "Que tan eficiente fue tu proceso de investigacion?"
```

**Esto ya es posible con la arquitectura actual.** CasePlan acepta
una lista de EvalQuestionPlan, cada uno con su eval_type. Solo falta
implementar los eval types que faltan en TaskGenTool.

### Paper-seeded cases: la idea central

El flujo mas potente de SREG es usar investigaciones reales como seed:

```
Paper real ("Arenamiento post-frac hit en pozos de la Cuenca X")
  |
  v
Orchestrator lee el paper y extrae:
  - Variables relevantes (presion, completacion, arena, drawdown...)
  - Relaciones causales propuestas
  - Que datos tenian los investigadores
  - Que preguntas se hicieron
  - Que experimentos hicieron
  - Que conclusiones sacaron
  |
  v
Orchestrator diseña un caso SINTETICO inspirado:
  - Variables similares pero en un contexto ficticio
  - Relaciones causales que PUEDEN diferir del paper real
    (esto es clave — testea si el agente se adapta a la evidencia)
  - Datos generados del BN (no del paper)
  - Preguntas inspiradas en las del paper pero adaptadas
  - Acciones inspiradas en los experimentos del paper
  |
  v
Tools construyen y validan:
  - BN formal con las variables y relaciones propuestas
  - Cada pregunta tiene respuesta computable
  - Las evaluaciones no son triviales
  - El caso es interesante (QualitySuite)
  |
  v
ResearchCase listo para el agente
```

**Por que esto es poderoso:**
- Las preguntas son realistas porque nacen de investigaciones reales
- La verdad puede diferir del paper (el agente no puede memorizar)
- Los datos son frescos (sampleados del BN, no del paper original)
- La evaluacion es formal (el BN da la respuesta exacta)
- El orchestrator no inventa de cero — se inspira en investigaciones reales

### Principios de diseno (consolidados)

1. **El orchestrator propone, los tools validan.** El LLM tiene libertad
   creativa para diseñar el caso, pero cada pregunta debe pasar validacion
   formal (respuesta computable, evaluacion no trivial).

2. **ResearchCase generaliza TaskBundle, no lo reemplaza.** La transicion
   es incremental. TaskBundle sigue funcionando como caso degenerado
   (caso donde las 3 preguntas son las mismas siempre).

3. **Teacher como upper bound, no como baseline a superar.** El teacher es
   el optimo bayesiano — es la cota superior. Las metricas comparan al
   agente contra el teacher (que tan lejos esta del optimo) y contra el
   prior/random (que tanto mejoro sobre no hacer nada).

4. **El caso depende del mundo Y del objetivo de evaluacion.** No es solo
   "dado este BN, que preguntas hago". Es "dado este BN Y este objetivo
   de evaluacion (inferencia? decision? descubrimiento?), que caso armo".

5. **Anti-cheating no es prioridad pero no se descarta.** Los mundos
   sinteticos y la verdad formal reducen el riesgo. Pero a futuro podrian
   hacer falta mecanismos (e.g., el agente no debe poder inferir la
   estructura del BN por patrones en los datos).

### Preguntas abiertas

1. ~~**Granularidad del catalogo de eval types**~~: RESUELTO. El catalogo tiene
   31 eval types en 6 familias. Se implementan en 4 olas. Ver seccion
   "Catalogo de evaluaciones cientificas" arriba.

2. **Validacion de preguntas del orchestrator**: como verificamos que una
   pregunta propuesta por el LLM tiene respuesta computable desde el BN?
   Cada eval type necesita un "validator" que chequee precondiciones.

3. **Budget compartido vs independiente**: el agente usa budget para
   investigar y responder multiples preguntas? O cada pregunta tiene
   su propio contexto?
   Inclinacion: budget compartido (mas realista).

4. **Score compuesto**: como se combinan los scores de pregunta principal
   + subpreguntas? Media ponderada? La principal vale mas?
   Inclinacion: peso configurable, primary_weight > sub_weight.

5. **Hasta donde llega el orchestrator en el diseno del caso**: le damos
   libertad total o lo guiamos con templates de caso?
   Inclinacion: templates de caso como guia + libertad para adaptar.

### Plan de implementacion: Slice 1 (decision 2026-03-09)

**Objetivo**: probar que el orchestrator puede diseñar un case plan especifico
para un mundo, en vez de siempre generar las mismas 3 tasks.

**Alcance**: solo los 3 eval types existentes. No se toca el agent ni el scoring.

**Flujo del slice**:
```
1. Orchestrator genera mundo (como hoy)
2. Orchestrator llama `design_case` con su propuesta de preguntas
3. Tool valida el CasePlan (eval types validos, preguntas computables)
4. `generate_tasks_from_plan` genera solo las Tasks que el plan pide
5. Tasks listas para ser resueltas (agent no cambia)
```

**Modelo `CasePlan`** (nuevo, `src/sreg/models/case_plan.py`):
```
EvalQuestionPlan:
  question_text: str         # "Cual es la causa mas probable del declive?"
  eval_type: str             # "infer_target" | "next_best_observation" | "hypothesis_selection"
  is_primary: bool           # Es la pregunta principal?
  rationale: str             # Por que esta pregunta para este mundo

CasePlan:
  title: str                 # Titulo del caso
  research_context: str      # Contexto breve
  primary_question: EvalQuestionPlan
  sub_questions: list[EvalQuestionPlan]   # 0-N
  shared_budget: int
  rationale: str             # Por que este set de preguntas para este mundo
```

**Tool `design_case`** (nueva tool del orchestrator):
- El LLM llama `design_case` con parametros (como hace con `apply_semantics`)
- La tool recibe la propuesta del LLM y valida:
  - eval types son validos (del catalogo)
  - target existe en el mundo
  - preguntas no se repiten
  - al menos 1 pregunta primary
- Devuelve CasePlan validado o error con razon

**Validacion de computabilidad** (integrada o tool separada):
- Para cada pregunta del plan, verifica que sea computable y no degenerada
- `infer_target`: siempre computable (el BN siempre puede calcular posterior)
- `next_best_observation`: computable si hay observables disponibles;
  no degenerada si al menos 1 nodo tiene IG > 0
- `hypothesis_selection`: computable si se puede generar posterior;
  no degenerada si hipotesis son distinguibles (KL > threshold)
- Reutiliza logica que ya existe en TaskGenTool

**Generacion desde plan** (`generate_tasks_from_plan` en TaskGenTool):
- Recibe CasePlan + World + seed
- Solo genera las Tasks que el plan pide (no siempre las 3)
- La question_text del plan se pasa a la Task (no el texto generico de hoy)
- Devuelve lista de Tasks (no TaskBundle)

**Separacion clave**:
```
Orchestrator (LLM)     →  PROPONE el case plan (que preguntas, por que)
design_case tool       →  VALIDA estructura y consistencia
validate + generate    →  VALIDAN computabilidad y CONSTRUYEN las Tasks
```

**Lo que NO se toca en este slice**:
- Agent (sigue haciendo infer_target como hoy)
- Scoring (sigue siendo por task individual)
- Eval types (solo los 3 existentes)
- DataSampler / ProblemBuilder (no cambian)

**Archivos a crear/modificar**:
- CREAR: `src/sreg/models/case_plan.py` + tests
- MODIFICAR: `src/sreg/orchestrator/tools.py` (tool def de design_case)
- MODIFICAR: `src/sreg/orchestrator/orchestrator.py` (dispatch)
- MODIFICAR: `src/sreg/tools/task_gen.py` (generate_from_plan)
- MODIFICAR: orchestrator system prompt
- Tests + E2E validation

---

## Diseno de acciones de investigacion (research 2026-03-10)

> **Problema**: el modelo actual de acciones (budget = N, cada accion revela
> 1 nodo, cuesta 1) es mecanica de juego, no ciencia real. Ningun investigador
> "descubre" variables de a una con costo uniforme.
>
> **Principio rector**: pensar es gratis, actuar en el mundo cuesta.
> El agente puede analizar datos todo lo que quiera — lo que cuesta es
> adquirir evidencia nueva (experimentos, mediciones, datos adicionales).

### Como funciona la investigacion real

No todas las investigaciones funcionan igual. El tipo de acciones disponibles
depende del dominio:

**Paradigma 1: Dataset-first** (data science, epidemiologia, ciencias sociales)
- El investigador ya tiene los datos. Un dataset grande.
- El desafio es: que analisis correr, que hipotesis testear, que conclusiones sacar.
- "Acciones" de adquisicion: raras o inexistentes. Todo el valor esta en el analisis.
- Budget de adquisicion: bajo o cero.

**Paradigma 2: Experimental** (lab, clinical trials, ingenieria)
- El investigador tiene datos observacionales iniciales.
- Puede diseñar y correr experimentos (intervenciones controladas).
- Cada experimento cuesta plata, tiempo, muestras.
- Budget de adquisicion: limitado y real. "Tenes presupuesto para 3 ensayos."

**Paradigma 3: Field research** (ecologia, geologia, astronomia)
- El investigador va a medir cosas. Cada campaña cuesta.
- A veces una medicion trae muchas variables (una muestra de suelo da pH,
  humedad, minerales). A veces necesita equipo especializado.
- Budget de adquisicion: medio, por campaña mas que por variable.

**Paradigma 4: Hibrido** (lo mas comun en la realidad)
- Empieza con datos existentes (papers previos, datasets publicos).
- Analiza lo que hay (gratis).
- Diseña experimentos nuevos para lo que falta (caro).
- Diferentes acciones tienen diferentes costos.

### Distincion fundamental: adquisicion vs analisis

| Tipo | Que hace | Costo | Ejemplo |
|---|---|---|---|
| **Analisis** | Razona sobre datos existentes | Gratis | Correr regresion, buscar correlaciones |
| **Adquisicion** | Obtiene evidencia nueva del mundo | Cuesta budget | Medir variable, correr experimento |

**El analisis es trabajo del agente.** Es exactamente lo que evaluamos: su
capacidad de razonar con la informacion disponible. No tiene sentido cobrarlo.

**La adquisicion cambia el estado del mundo** (revela informacion nueva).
Eso si cuesta — como en la realidad.

### Catalogo de tipos de accion (propuesta)

Cada accion que el agente pueda tomar debe **mapear a una operacion formal
sobre el BN**. Si no podemos computar el resultado desde el BN, la accion
no puede existir. Esa es la regla de oro.

#### Acciones de observacion (revelar evidencia)

| Accion | Mapeo formal | Costo tipico | Ejemplo cientifico |
|---|---|---|---|
| Medir variable | Samplear valor de un nodo dado evidencia actual | Bajo (1) | "Medir pH del suelo en parcela 3" |
| Campaña de medicion | Samplear multiples nodos a la vez | Medio (2-3) | "Hacer analisis completo de muestra de agua" |
| Pedir dataset adicional | Generar N filas de subconjunto de variables | Medio (2-3) | "Solicitar registros hospitalarios de otra region" |
| Medir variable costosa | Samplear nodo que requiere equipo especial | Alto (3-5) | "Analisis de espectrometria de masas" |

Mapeo BN: `observe(node) → samplear valor segun P(node | evidencia_actual)`

#### Acciones de intervencion (do-operations)

| Accion | Mapeo formal | Costo tipico | Ejemplo cientifico |
|---|---|---|---|
| Experimento simple | do(variable=valor), observar target | Alto (3-5) | "Aplicar fertilizante X, medir crecimiento" |
| Ensayo controlado | do(variable=valor), samplear N observaciones | Muy alto (5-8) | "Clinical trial: droga Z, 50 pacientes" |
| Experimento multi-variable | do(var1=v1, var2=v2), observar resultado | Muy alto (5-10) | "Probar combinacion de tratamientos" |

Mapeo BN: `intervene(node=value) → P(target | do(node=value))` via CausalInference

#### Acciones de consulta (informacion teorica)

| Accion | Mapeo formal | Costo tipico | Ejemplo cientifico |
|---|---|---|---|
| Consultar literatura | Revelar informacion parcial sobre estructura | Bajo (1) | "Que dice la literatura sobre X→Y?" |
| Consultar experto | Revelar probabilidad condicional parcial | Medio (2) | "Un experto opina que X probablemente causa Y" |

Mapeo BN: estas acciones son mas complejas de formalizar. Podrian revelar
informacion parcial sobre la estructura del DAG (ej: "existe una arista X→Y")
o sobre las CPDs (ej: "P(Y=high|X=high) > 0.7"). Requieren diseño cuidadoso
para que la informacion revelada sea correcta sin dar demasiado.

**Nota**: las acciones de consulta son las mas dificiles de formalizar y
deberian implementarse despues de las de observacion e intervencion.

### Acciones fijas vs acciones diseñadas por el orchestrator

Asi como las **preguntas** de evaluacion siguen tipos formales (eval types)
pero el orchestrator elige cuales usar y como formularlas para cada caso,
las **acciones** deberian seguir el mismo patron:

```
TIPOS DE ACCION (fijos, como eval types):
  observe_single     → revelar 1 nodo
  observe_multi      → revelar N nodos (campaña)
  intervene          → do-operation
  request_dataset    → generar dataset adicional

ACCIONES CONCRETAS (diseñadas por orchestrator, como questions):
  "Medir pH del suelo en zona norte"        → observe_single(pH)       costo: 1
  "Correr analisis de laboratorio completo"  → observe_multi(pH, min, org) costo: 3
  "Aplicar fertilizante X en parcela este"  → intervene(fertilizer=X)  costo: 4
  "Pedir datos meteorologicos de 2024"      → request_dataset(weather) costo: 2
```

**El paralelismo con eval types es exacto:**

| | Preguntas | Acciones |
|---|---|---|
| **Tipos formales** | eval types (infer_target, adjustment_set, ...) | action types (observe, intervene, ...) |
| **Instancias concretas** | EvalQuestionPlan (texto + tipo + target) | ActionPlan (texto + tipo + nodos + costo) |
| **Quien diseña** | Orchestrator | Orchestrator |
| **Quien valida** | Tools (mapea al BN?) | Tools (nodos existen? costos validos?) |
| **Quien resuelve** | Teacher (respuesta golden) | BN (resultado de la accion) |

### Ejemplos de research cases con acciones ricas

#### Caso 1: Agricultura (hibrido)

```
Datos iniciales (gratis):
  - Dataset de 200 parcelas: suelo, clima, riego, rendimiento
  - 3 años de datos meteorologicos

Acciones disponibles:
  "Medir nutrientes del suelo en parcela nueva"    observe(nutrientes)    costo: 1
  "Instalar sensor de humedad continuo"            observe(humedad)       costo: 2
  "Aplicar riego por goteo en parcela test"         intervene(riego=goteo) costo: 3
  "Cambiar fertilizante a organico en sector B"     intervene(fert=org)    costo: 4
  "Pedir datos de parcelas vecinas"                 request_dataset(...)   costo: 2

Budget total: 8 unidades

Preguntas:
  1. "Que factor tiene mayor impacto causal en el rendimiento?" (best_intervention)
  2. "Si cambias el tipo de riego, cambia el rendimiento?" (causal_effect)
  3. "Que variables deberias controlar en tu analisis?" (adjustment_set)
```

#### Caso 2: Epidemiologia (data-first)

```
Datos iniciales (gratis):
  - Registros de 5000 pacientes: edad, sexo, tratamiento, comorbilidades, outcome
  - Estudio observacional publicado

Acciones disponibles:
  "Pedir registros de otro hospital"                request_dataset(...)   costo: 2
  "Correr ensayo clinico piloto (30 pacientes)"     intervene(droga=Z)     costo: 6
  "Consultar meta-analisis sobre droga Z"           consult(droga→outcome) costo: 1

Budget total: 6 unidades

Preguntas:
  1. "La droga Z reduce la mortalidad?" (causal_effect)
  2. "Que variables confunden la relacion droga-mortalidad?" (adjustment_set)
  3. "Vale la pena correr un ensayo clinico o los datos observacionales bastan?" (NBO adaptado)
```

#### Caso 3: Geologia (field research)

```
Datos iniciales (gratis):
  - 50 mediciones de superficie: temperatura, presion, composicion
  - Mapa geologico del area

Acciones disponibles:
  "Tomar muestra en punto X"                       observe(composicion, temp, presion) costo: 2
  "Perforacion exploratoria (revela capas profundas)" observe(capa_profunda)            costo: 5
  "Analisis isotopico de muestra existente"          observe(edad_isotopica)            costo: 3

Budget total: 10 unidades

Preguntas:
  1. "Cual es la causa del patron anomalo en la zona sur?" (infer_latent_cause)
  2. "Que medicion seria mas informativa a continuacion?" (NBO)
```

### Principios de diseno de acciones

1. **Co-diseño obligatorio: preguntas + acciones + evidencia van juntas.**
   No diseñar preguntas por un lado y acciones por otro. Si el case incluye
   `causal_effect`, deberia existir alguna accion de intervencion. Si incluye
   `best_intervention`, deberia haber mas de una intervencion plausible. Si
   incluye `adjustment_set`, deberia haber evidencia suficiente para que
   el agente pueda razonar sobre confounders. Coherencia interna del case.

2. **4 a 8 acciones por caso, no 25.** Pocas acciones con roles claros.
   Un mix tipico: 2-3 observaciones baratas, 1-2 experimentos caros,
   1 accion de datos adicionales. Si el agente tiene demasiadas opciones
   el case se vuelve inmanejable y la evaluacion pierde foco.

3. **Cada accion debe devolver algo concreto y computable.** Nunca algo
   vago como "investigar mas" o "explorar el sistema". Cada accion tiene
   output bien definido: un valor, un dataset, un resultado experimental.
   Si no mapea a una operacion sobre el BN, no existe.

4. **Cada accion debe responder a una necesidad del case:**
   - Que incertidumbre reduce?
   - Que hipotesis ayuda a distinguir?
   - Que mecanismo pone a prueba?
   Si una accion no ayuda a ninguna pregunta del case, sobra.

5. **Pensar es gratis, actuar cuesta.** El agente puede analizar datos,
   buscar correlaciones, formular hipotesis, todo sin costo. Lo que cuesta
   budget es adquirir evidencia nueva del mundo.

**Regla de oro (consolidada):**
> El research case define que preguntas valen la pena y que acciones son
> plausibles. El mundo formal define que respuestas y evidencias son
> realmente validas.

### Cadena de validacion: como asegurar consistencia

El riesgo principal es que el orchestrator diseñe acciones incoherentes.
La validacion sigue el patron ya establecido (orchestrator propone, tools validan):

```
Orchestrator propone acciones
  |
  v
Tool valida:
  [x] Cada accion referencia nodos que existen en el BN
  [x] Los estados de intervencion son validos para esos nodos
  [x] Los costos son > 0
  [x] Al menos una accion es de tipo "observe" (el agente debe poder medir algo)
  [x] El budget total permite al menos 2 acciones (investigacion no trivial)
  [x] No hay acciones sobre nodos LATENT (el agente no sabe que existen)
  [x] Las descripciones son coherentes con la narrativa del caso

  [!] WARN si todas las acciones son observe (no hay opcion de experimentar)
  [!] WARN si el budget es tan alto que puede hacer todo (no hay decision)
  [x] FAIL si una intervencion apunta a un nodo TARGET (no podes intervenir el outcome)

Validacion de coherencia con el case (no solo formal):
  [x] Cada accion ayuda a responder al menos una pregunta del case
  [x] No hay acciones redundantes (dos acciones que revelan lo mismo)
  [x] Ninguna accion "regala" la respuesta a una pregunta
      (ej: si la pregunta es infer_target y una accion observa el target directamente)
  [x] Si el case tiene causal_effect/best_intervention, hay al menos 1 accion interventional
  [x] Si el case tiene adjustment_set, hay suficientes observables para confounders
  [x] Las acciones son plausibles dentro de la narrativa del case
```

### Impacto en el teacher solver

El teacher hoy calcula: "que variable tiene mas information gain? Observo esa."

Con acciones ricas, el calculo cambia a: **"que accion tiene mas information
gain POR UNIDAD DE COSTO?"**

```
Medir humedad:     IG = 0.4 bits, costo 1 → ratio = 0.40 bits/unidad
Experimento riego: IG = 0.8 bits, costo 3 → ratio = 0.27 bits/unidad
Analisis de lab:   IG = 0.5 bits, costo 2 → ratio = 0.25 bits/unidad
```

Las intervenciones (do-operations) dan mas informacion porque **rompen
confounders** — ves el efecto causal directo, no la correlacion. Pero
cuestan mas. Esa tension es exactamente la que hace interesante la
decision del agente: ¿mido barato o experimento caro?

El teacher puede optimizar esto con un algoritmo greedy (IG/costo por paso)
o con una estrategia mas sofisticada (lookahead). Para v1, greedy es
suficiente y ya es la cota superior.

### Preguntas abiertas sobre acciones

1. **Acciones de consulta**: como formalizamos "consultar literatura"?
   Una opcion: revelar una arista del DAG ("X causa Y") o un rango de
   una CPD ("P(Y|X=high) esta entre 0.6 y 0.9"). Requiere diseño cuidadoso.

2. **Acciones adaptativas**: el resultado de una accion puede habilitar
   nuevas acciones? Ej: "si medis X y sale alto, ahora podes hacer el
   experimento Y". Esto añade complejidad pero es muy realista.

3. **Acciones parcialmente informativas**: una medicion podria tener ruido
   (no revela el valor exacto sino un rango). Mapeo: en vez de revelar
   el estado exacto, revelar una distribucion P(estado | medicion).

4. **Score de estrategia**: como evaluamos si el agente tomo buenas
   decisiones de accion (no solo si respondio bien las preguntas)?
   El teacher da la estrategia optima — pero comparar secuencias de
   acciones es mas complejo que comparar respuestas.

5. **Acciones que no revelan nada**: un experimento podria fallar o dar
   resultado inconcluso. Mapeo: la accion cuesta budget pero revela
   un "null result" (la distribucion no cambia mucho). Esto es realista
   pero frustrante — dosificar con cuidado.

### Plan de implementacion: acciones ricas (actualizado 2026-03-10)

> Ola 1 de eval types COMPLETA (9 tipos). Ahora si, implementar acciones ricas.

**Cuidados de diseño (feedback consolidado):**

1. **No generar acciones multi-nodo arbitrarias.** Cada accion multi-nodo
   debe tener semantica clara: "analisis de laboratorio" revela {pH, minerales,
   materia_organica}, no "observar 3 nodos random". La agrupacion de nodos
   responde a la logica del dominio, no a una optimizacion combinatoria.

2. **Agregar `action_type` desde el inicio.** No esperar al Slice B para
   tipar las acciones. El modelo debe tener `action_type: ActionType` (observe,
   intervene, request_dataset, consult) desde el Slice A, aunque el Slice A
   solo implemente `observe` y `request_dataset`. Esto prepara el modelo para
   que el orchestrator diseñe acciones tipadas sin refactoreo posterior.

3. **El costo NO depende solo de cuantos nodos revela.** Es un atributo
   semantico de la accion: un analisis espectrometrico cuesta 3 aunque solo
   revele 1 nodo; un muestreo basico cuesta 1 aunque revele 2 nodos.
   El costo refleja tiempo/dinero/complejidad del mundo real, no informacion.

4. **Diseñar pensando en el orchestrator.** El modelo debe ser lo
   suficientemente expresivo para que el orchestrator proponga acciones
   concretas como parte del research case. Esto significa que `AvailableAction`
   debe poder representar TODO lo que el orchestrator quiera proponer, no
   solo lo que `EpisodeGenTool` genera automaticamente.

**Plan en 2 slices:**

**Slice A — Modelo de acciones ricas (PROXIMO)**
Cambiar el modelo y la infraestructura. NO requiere orchestrator.
- `ActionType` enum: observe, intervene, request_dataset (consult reservado)
- `AvailableAction` ampliado: action_type + nodes: list[str] + cost variable
- `EpisodeRunner` procesa multi-nodo y cost > 1
- `ProblemBuilder` genera acciones con mix de tipos y costos
- Teacher solver: optimiza IG/costo (greedy)
- Ver TODO.md "Slice A" para checklist detallado.

**Slice B — Intervenciones + orchestrator (DESPUES)**
El agente puede INTERVENIR. El orchestrator diseña acciones.
- do-operations como acciones del agente (costo alto, info alta)
- ActionPlan model: orchestrator propone acciones tipadas
- Validacion de coherencia case-acciones
- Ver TODO.md "Slice B" para checklist detallado.

---

## Enriquecimiento de la presentacion de datos (implementado 2026-03-09)

> El nucleo formal (BN + generacion + teacher + QualitySuite) esta validado.
> El batch sweep confirmo que con 10-12 nodos y es=0.5-0.7 el sistema produce
> mundos con informacion util y estrategia real. El gap principal ya no esta
> en el world model sino en la **riqueza del case que ve el agente**.
>
> El foco se mueve de "generar mundos buenos" a "presentar casos ricos".

### Estado actual de la presentacion de datos

`DataSampler` (src/sreg/tools/data_sampler.py) genera datos de dos formas:

1. **Tabular**: N filas, todas las columnas visibles (observable + target), seed
   incremental. Una sola tabla plana.
2. **Observations**: 5 observaciones puntuales tipo "variable: value".

`DataAsset` (src/sreg/models/research_problem.py) modela un asset de datos con
nombre, descripcion, formato y filas. `ResearchProblem.data_assets` ya es una
lista, asi que el modelo soporta multiples datasets — **pero DataSampler solo
genera uno.**

`AvailableAction` tiene `node` (str), `description` (str) y `cost` (int >= 1).
Pero hoy cost=1 siempre y cada accion revela exactamente 1 nodo.

### Gap con PROJECT.md

PROJECT.md ejemplo de Nelvara tiene 3 data assets distintos:
- Dataset 1: 150 mediciones de 4 estaciones (tabular con subconjunto de columnas)
- Dataset 2: 12 muestras de sedimento (tabular diferente, menos filas)
- Observacion aislada: un hecho narrativo

Los dos ejemplos finales (pozos, material anticorrosivo) piden:
- Historial temporal
- Datos faltantes
- Observaciones contradictorias
- Metadata
- Acciones con costos variados (1, 2, 3)
- Acciones que revelan multiples variables

Nada de esto existe hoy.

### Plan de implementacion (3 prioridades)

**Prioridad 1: Dataset-rich evidence.** Extender DataSampler para generar
multiples DataAssets por mundo. El modelo ya lo soporta (data_assets es lista).
Lo que falta:
- Generar 2+ datasets con distintas columnas/filas/seeds
- Observaciones narrativas extraidas de samples
- Valores faltantes (omitir celdas aleatoriamente)
- Que ProblemBuilder use los nuevos assets

**Prioridad 2: Rich actions.** Extender AvailableAction para soportar
acciones multi-nodo con costos variados. El modelo casi lo soporta (cost ya
es int >= 1). Lo que falta:
- Agregar `nodes: list[str]` (hoy solo `node: str`)
- EpisodeRunner procesa acciones multi-nodo
- EpisodeGenTool genera acciones con costos 1-3

**Prioridad 3: CaseBundle multi-task.** Un case con budget compartido y
multiples preguntas conectadas. Es la pieza que cierra la distancia con
PROJECT.md pero requiere las dos anteriores.

### Que NO cambia

- La capa formal (BN + CPDs + DAGSpec) no se toca
- El teacher sigue funcionando igual (infiere sobre el BN)
- QualitySuite sigue midiendo calidad del mundo subyacente
- Los 3 task types actuales siguen siendo evaluaciones validas

Todo el enriquecimiento esta en la **capa semantica/presentacion**, no en la
capa formal. Es modular — se puede mejorar la presentacion sin tocar la
formalizacion.

---

## Dimension temporal (para despues)

El ejemplo de pozos de petroleo es claramente temporal: hay un "antes del
frac hit", "durante el evento", "despues del evento". Esto importa porque:

- Autocorrelacion: el valor de hoy depende del de ayer
- No estacionariedad: las relaciones cambian en el tiempo
- Muestreo irregular: no siempre se mide al mismo ritmo
- Missing data temporal: hay periodos sin datos

Opciones para el futuro:
1. **Dynamic Bayesian Networks (DBNs)**: el BN "desenrollado" en el tiempo
2. **Mundos multi-slice**: mismas variables, distintos momentos, con edges temporales
3. **Simple history**: dar datos de distintos momentos como datasets separados (sin modelar explicitamente la dinamica)

**Decision: esto es v3+. Primero mundos estaticos mas grandes y ricos.**

---

## Hallazgos experimentales

> Esta seccion registra los resultados concretos de las pruebas que hacemos.
> Cada vez que generamos mundos y observamos comportamiento interesante,
> problemas, o cosas inesperadas, se documenta aca. Esto es parte de la
> investigacion — no solo la teoria sino lo que realmente pasa cuando
> ejecutamos el sistema.

### Hallazgos de templates v1 (2026-03-07)

Estos hallazgos vienen del E2E testing con los 3 templates existentes,
antes de implementar DAGSpec:

**NBO trivial (25% promedio)**: cuando se da mucha evidencia, todos los nodos
restantes tienen IG=0 (0% en latent_preference, 28% en causal_chain, 48% en
fork_collider). Fork_collider es el peor porque su estructura compacta hace
que pocos nodos basten para inferir el target completamente.

**Hipotesis casi indistinguibles con edge_strength baja**: con es=0.3, la
posterior verdadera y la reversed pueden tener KL tan bajo como 0.0097. La
tarea se vuelve loteria. Threshold minimo razonable: es >= 0.5 para
hypothesis_selection.

**Agent peor que random en 8 nodos**: el agente LLM no escala bien con mas
variables (KL 4.21 vs random 0.30 en un caso de 8 nodos). Esto sugiere que
mundos mas grandes van a ser genuinamente desafiantes para los agentes.

### Hallazgos del prototipo DAGSpec (2026-03-09)

Prototipo implementado y validado con 7 configuraciones (4-15 nodos) x 3-20 seeds.

**La formula de CPDs aguanta con 4 padres**: si. Mundos con nodos de 4 padres
(16 combinaciones para 2-state, 81 para 3-state) generan CPDs validas. Con
edge_strength >= 0.6 las distribuciones siguen siendo peaked en el estado
dominante.

**Variable Elimination es viable con 12-15 nodos**: si. Tiempos de ~20ms para
mundos de 15 nodos. La clave es que los treewidths observados son bajos (1-4)
porque las topologias tipo arbol/sparse tienen pocos co-padres.

**Treewidth de los DAGs generados**: entre 1 (cadenas) y 4 (dense con 4 padres).
Ninguna configuracion probada supero treewidth 4. Para llegar a treewidth > 6-8
se necesitarian DAGs mucho mas densos (lo cual esta limitado por max_parents=4).

**NBO trivial en mundos grandes**: MEJORA respecto a v1. Con 12-15 nodos y 9-11
observables, NBO es no trivial en 80-90% de los casos (vs ~75% en v1 con 6-9 nodos).
Mas observables = mas opciones con IG > 0. La cadena de 8 nodos con es=0.6 es la
excepcion: 33% trivial, porque la informacion se pierde a lo largo de la cadena.

**Hipotesis distinguibles en mundos grandes**: razonable pero baja un poco.
Con 12 nodos y es=0.7: 90% distinguibles. Con 15 nodos y es=0.6-0.8: 75%.
La causa probable: en mundos mas grandes el target tiene mas padres, lo que
diluye la diferencia entre posterior y reversed-posterior. Threshold actual
(KL > 0.05) sigue siendo razonable.

**Teacher siempre mejora sobre prior y supera a random**: si, en 15/15 casos
probados (3 edge_strengths x 5 seeds). El teacher con budget=3 alcanza KL=0.0
en la mayoria de casos (3 observaciones optimas bastan para recuperar la
posterior exacta en estas topologias). Resultado robusto.

**Estados heterogeneos (2 + 3 estados) funcionan**: si, sin problemas.
La formula de CPDs maneja correctamente padres de 2 estados con hijos de 3
estados (wrapping via `p_state % num_child_states`). pgmpy valida todo ok.

**Resumen de tasas de tasks no degeneradas**:

| Config | NBO no-trivial | Hipotesis distinguibles |
|---|---|---|
| 12n, es=0.7 | 80% | 90% |
| 12n, es=0.5 | 80% | 80% |
| 15n, es=0.6 | 90% | 75% |
| 15n, es=0.8 | 90% | 75% |

Cumple los criterios del plan (~70% NBO, ~80% hipotesis) o esta muy cerca.
La distinguibilidad de hipotesis es el punto mas debil en mundos grandes --
investigar si cambiar la estrategia de generacion de distractores (e.g.,
usar Dirichlet random en vez de reversed-posterior) mejora esto.

**Preguntas abiertas post-prototipo**:
- Que topologias producen mundos "buenos" vs "malos"? (necesita expressive range analysis)
- El teacher con budget=3 ya llega a KL=0: necesitamos mundos donde el budget
  sea mas restrictivo (mas nodos, target mas lejano de observables)

### Batch sweep: regimenes de generacion (2026-03-09)

Sweep sistematico de 336 mundos (7 generators/templates x 4 node counts x 4 edge
strengths x 3 seeds), con QualitySuite v2 (3 rollouts por mundo). Objetivo: identificar
que configuraciones producen mundos con informacion util y estrategia real.

Script: `scripts/batch_sweep.py`

**Hallazgo principal: el numero de nodos determina si hay estrategia real.**

| Nodes | BudR | TbRR | NBO | Hyp | Bundle |
|-------|------|------|-----|-----|--------|
| 6 | 1.43 | 0.00 | 0.88 | 0.64 | 63% |
| 8 | 1.30 | 0.11 | 0.48 | 0.74 | 21% |
| 10 | 0.71 | 0.40 | 0.53 | 0.68 | 81% |
| 12 | 0.50 | 0.60 | 0.52 | 0.74 | 86% |

Con 6 nodos, budget=5 y ~4 observables: teacher y random ven todo. TbRR=0.00 — no
hay decision estrategica posible. Con 12 nodos: budget=5 y ~10 observables: budget
ratio 0.50, el teacher tiene que elegir y le gana al random 60% del tiempo.

**8 nodos es un "valle de muerte"**: budget ratio todavia alto pero NBO ya bajo.
Solo 21% useful_bundle. Peor que 6 y que 10.

**Regimen recomendado: 10-12 nodos.** Budget ratio < 0.8, entropy reduction solida,
useful_bundle 81-86%.

**edge_strength 0.9 mata la distinguibilidad de hipotesis.**

| ES | EntRd | Hyp | Bundle |
|----|-------|-----|--------|
| 0.3 | 0.42 | 0.70 | 70% |
| 0.5 | 0.61 | 0.80 | 72% |
| 0.7 | 0.81 | 0.87 | 73% |
| 0.9 | 1.04 | 0.43 | 35% |

A es=0.9, la evidencia confirma el prior tan fuertemente que el distractor "prior"
queda casi identico a la posterior verdadera (KL < 0.05). Hyp cae de 0.87 a 0.43.
**Regimen recomendado: es=0.5-0.7.**

**preferential_attachment: 0% WorldCheck en 48 mundos.**

Eliminable como generador activo. Los grafos hub-spoke densos que produce no tienen
d-separaciones. 100% de mundos fallan WorldCheck independientemente de num_nodes o
edge_strength.

**Ranking de generators/templates (agregado):**

| Generator/Template | Bundle | EntRd | BudR | TbRR | Nota |
|--------------------|--------|-------|------|------|------|
| layered | 71% | 0.73 | 1.45 | 0.15 | Mejor bundle pero budget_ratio alto |
| latent_preference | 69% | 0.60 | 0.74 | 0.45 | Equilibrado |
| spanning_tree | 65% | 0.73 | 0.74 | 0.33 | Solido |
| erdos_renyi | 59% | 0.58 | 1.51 | 0.28 | Budget_ratio problematico |
| fork_collider | 56% | 0.80 | 0.74 | 0.24 | Alta entropy_reduction |
| causal_chain | 56% | 0.87 | 0.74 | 0.23 | Mejor entropy_reduction |
| pref_attachment | 0% | - | - | - | Eliminable |

Nota: budget_ratio alto en erdos_renyi y layered se debe a que generan nodos sin
path al target (observables "sueltos"). No necesariamente malo — es un artifact del
budget formula actual que va a cambiar con rich actions.

**Mejores configs concretas (100% useful_bundle):**
- `causal_chain n=10-12, es=0.7` — EntRd ~1.0, Hyp 0.89-1.00
- `fork_collider n=12, es=0.7` — EntRd 0.96, Hyp 1.00
- `spanning_tree n=12, es=0.7` — EntRd 0.94, Hyp 0.89

**Decision (2026-03-09):** estos hallazgos cierran la validacion del core formal.
El regimen base para research cases es 10-12 nodos, es=0.5-0.7, con spanning_tree
o layered como generators por defecto. Mundos de 6-8 nodos quedan solo para unit
testing. El proximo foco se mueve a enriquecer el case (data, acciones, CaseBundle),
no a seguir calibrando el generador.

---

## Investigacion previa relevante

### BoxingGym (NeurIPS 2025)

**Paper**: "BoxingGym: Benchmarking Progress in Automated Experimental Design
and Model Discovery" — Kanishk Gandhi et al.
**Repo**: github.com/kanishkg/boxing-gym

**Que es**: 10 ambientes hand-crafted, cada uno implementado como un modelo
generativo probabilistico en PyMC. El agente disenya experimentos (elige inputs),
observa resultados, y debe descubrir el modelo subyacente.

**Detalles de implementacion**:
- Cada ambiente tiene: prior `p(theta)`, likelihood `p(y|theta,d)`, evaluacion
- El agente hace hasta 10 experimentos con formato `<observe>[inputs]</observe>`
- EIG se computa post-hoc con Nested Monte Carlo: `EIG(d) = E[log(p(y|theta_0,d) / E[p(y|theta_m,d)])]`
- EIG Regret: `max(EIG de 100 random) - EIG(eleccion del agente)`
- Standardized error: `(error - prior_error) / prior_std`
- Model discovery: scientist explica -> novice usa solo la explicacion para predecir
- Box's Apprentice: el LLM genera codigo PyMC para modelar el sistema

**Ambientes**: Location Finding, Hyperbolic Temporal Discounting, Death Process,
Item Response Theory, Dugongs, Peregrines, Mastectomy Survival, Predator-Prey,
Emotion from Outcome, Moral Machines. Todos de dominios cientificos reales.

**Hallazgos clave**:
- Prior knowledge a veces EMPEORA la performance (overfitting a assumptions)
- 32B > 7B. Instruction-tuned > reasoning-focused.
- Experimental design es debil: agentes eligen casi tan mal como random
- Box's Apprentice inconsistente: oversimplifica (modelos lineales para fenomenos no lineales)
- Explicaciones pierden informacion: novice siempre peor que scientist

**Que tomamos**: standardized prediction error, EIG como metrica post-hoc,
idea de scientist-novice evaluation.

### DiscoveryWorld (Allen AI, NeurIPS 2024)

**Paper**: "DiscoveryWorld: A Virtual Environment for Developing and
Benchmarking Systems for Scientific Discovery" — Peter Jansen et al.
**Repo**: github.com/allenai/discoveryworld

**Que es**: Mundo virtual 2D (Pygame, grid 32x32) con 8 temas cientificos,
3 dificultades, 5 seeds = 120 tareas. El agente navega, interactua con objetos,
hace experimentos, y debe descubrir reglas ocultas.

**Detalles de implementacion**:
- 14 acciones: Move, Take, Drop, Put, Open, Close, Activate, Use, Talk, Read,
  Eat, Feed, Wait, Teleport
- Observaciones: JSON con objetos cercanos, inventario, vision base64
- ~20,000 lineas de Python
- 60+ propiedades medibles por objeto (temperatura, densidad, pH, radiacion...)
- No tiene formalismo matematico unificado — cada tema tiene logica ad-hoc

**8 temas**: Proteomics (clustering), Combinatorial Chemistry (hill-climbing),
Archaeology Dating (regression), Reactor Lab (linear/quadratic fit),
Plant Nutrients (logic rules), Space Sick (causal investigation con distractores),
Rocket Science (physics equations), Lost in Translation (language grounding).

**Triple evaluacion**:
- Completion: binario (logro o no)
- Procedural process: scorecard normalizado (hizo las acciones correctas?)
- Explanatory knowledge: preguntas binarias evaluadas por GPT-4o

**Hallazgos clave**:
- Agentes IA: 38-56% completion en Easy, ~15-20% en Normal/Challenge
- Humanos (MSc/PhD): 66% completion promedio
- Gap humano-agente masivo en Normal/Challenge
- Costo: $3-10k por benchmark run completo
- Distractores son esenciales para evaluar razonamiento cientifico real

**Que tomamos**: triple evaluacion, distractores deliberados, variaciones via seeds,
consideracion de costos de evaluacion.

### Reasoning Core (2026)

**Paper**: "Reasoning Core: A Scalable Procedural Data Generation Suite for
Symbolic Pre-training and Post-Training" — Damien Sileo et al.
**Repo**: github.com/sileod/reasoning_core

**Que es**: Suite de 28-29 tipos de problemas generados proceduralmente,
cada uno con solver externo y reward verificable. Incluye razonamiento causal
sobre redes bayesianas aleatorias. Escala: 10M problemas, 5B tokens.

**Detalles de implementacion BN** (lo mas relevante para SREG):
- Usa pgmpy (igual que nosotros) con VariableElimination
- 4 metodos de DAG generation: Erdos-Renyi (default), spanning tree,
  preferential attachment, layered. Todos garantizan aciclicidad por construccion.
- CPDs tabulares via `TabularCPD.get_random()` + opcionalmente Noisy-OR/AND/MAX/MIN
  (Causal Influence Models). Noisy-OR: `p_active = 1 - prod(1 - mag[active_parents])`
- Variables binarias o multi-estado (max_domain_size configurable)
- Do-interventions: graph surgery (remover aristas entrantes + CPD punto masa)
- Inference traces via SemanticTraceVE (Variable Elimination paso a paso como texto)

**Dificultad**: stochastic rounding. Un `level` incrementa float params:
`n_nodes += 0.5, max_domain_size += 0.5, n_round += 0.5` por nivel. Al leer,
redondeo estocastico da variedad natural. Level 0: 3 nodos, 2 estados.
Level 5: ~6 nodos, ~5 estados.

**Scoring BN**: JS divergence con power=128: `reward = (1 - JS/ln(2))^128`.
Casi binario: near-perfect = 1.0, cualquier error significativo = 0.0.

**Limitaciones vs SREG**:
- Variables abstractas (X_0, X_1) — sin semantica
- One-shot (no hay loop de experimentacion)
- Solo pregunta "computa esta probabilidad" — no tiene NBO, hypothesis selection, etc.
- Problemas pequenos (3-6 nodos max)

**Que tomamos**: 4 metodos de DAG generation, Noisy-OR como CPD alternativa,
do-intervention via graph surgery, stochastic rounding para dificultad,
SemanticTraceVE para teacher traces, JS divergence como alternativa a KL.

### Procedural Content Generation (PCG) — teoria

**Surveys y papers clave**:
- Shaker, Togelius & Nelson (2016) — *Procedural Content Generation in Games:
  A Textbook*. El libro de referencia. pcgbook.com
- Togelius, Yannakakis, Stanley & Browne (2011) — *Search-Based PCG: A Taxonomy
  and Survey*, IEEE TCIAIG. Define SBPCG y generate-and-test.
- Smith & Mateas (2011) — *Answer Set Programming for PCG: A Design Space
  Approach*. PCG declarativo, el concepto de "design space".
- Gravina, Khalifa & Liapis (2019) — *PCG through Quality Diversity*.
  MAP-Elites aplicado a PCG.
- Liapis, Yannakakis & Togelius (2016) — *Mixed-Initiative Content Creation*.
- Maleki & Zhao (2024) — *PCG in Games: A Survey with Insights on Emerging
  LLM Integration*, AAAI AIIDE. El survey mas reciente, cubre LLMs como PCG.

**Principios clave adoptados**:

| Principio | Referencia | Aplicacion en SREG |
|---|---|---|
| Generate-Evaluate-Refine | Togelius 2011 | WorldGen + WorldCheck + feedback loop |
| Quality-Diversity (MAP-Elites) | Gravina 2019 | Cubrir espacio de problemas diversos |
| Expressive Range Analysis | Smith & Whitehead | Evaluar distribucion de outputs del generador |
| Mixed-Initiative | Liapis 2016 | LLM propone + tools validan |
| Constraint-Based Design Space | Smith & Mateas 2011 | Quality gates como restricciones |
| Simulation-Based Fitness | Togelius 2011 | Teacher solver como simulacion de calidad |
| Repair Loop | Maleki & Zhao 2024 | Feedback estructurado al LLM para regenerar |

### CausalProfiler (2025)
- **Space of Interest (SoI)**: define propiedades deseadas ANTES de generar.
- DAG generation: topological ordering + binomial parent sampling.
- CPDs: mecanismos discretos "regionales" (similar a edge_strength).
- Coverage guarantees: cubrir un espacio de propiedades.
- **Takeaway**: generacion guiada por propiedades, no generacion ciega.

### CausalBench (2024)
- Datasets reales de 2 a 109 nodos con ground truth de papers.
- LLMs tienen accuracy limitada en problemas reales (>10 nodos).
- **Takeaway**: escalar a mundos mas grandes va a ser genuinamente dificil.

### CauSciBench (2025)
- Pipeline causal completo: observacion -> hipotesis -> intervencion -> conclusion.
- LLMs logran 48.96% MRE en problemas reales.
- **Takeaway**: evaluacion multi-step es mas realista que preguntas aisladas.

### Bayesian Teaching (Nature Communications, 2025)
- LLMs aprenden Bayesian updating imitando un teacher.
- Generaliza a tareas nuevas.
- **Takeaway**: progresion simple->complejo es pedagogicamente valida.

### pgmpy get_random()
- `DiscreteBayesianNetwork.get_random(n_nodes, edge_prob, n_states, latents)`.
- Generador rapido, sin garantia de calidad.
- **Takeaway**: entrada al pipeline + quality filter, no generador principal.

### TimeGraph (KDD 2025)
- Benchmark temporal: autocorrelacion, no estacionariedad, muestreo irregular.
- **Takeaway**: referencia para mundos temporales (v3+).

### CausalGraphBench (ACL 2025)
- Evalua si LLMs pueden recuperar la estructura del DAG desde datos.
- **Takeaway**: futura task type: structure recovery evaluada con SHD.

### CauseMe
- Evaluacion de metodos de descubrimiento causal en series temporales.
- **Takeaway**: referencia para propiedades de mundos temporales.

---

## Referencias rapidas

| Proyecto | Que es | Que nos aporta | Prioridad |
|---|---|---|---|
| **BoxingGym** | Experimental design benchmark (10 envs, PyMC) | Standardized error, EIG post-hoc, scientist-novice | v2/v3 |
| **DiscoveryWorld** | Interactive science worlds (120 tasks, Pygame) | Triple eval, distractores, variaciones via seeds | v2/v3 |
| **Reasoning Core** | Procedural BN generation (28 tasks, pgmpy, 10M scale) | DAG generators, Noisy-OR CPDs, do-calculus, difficulty knob | v2/v3 |
| **PCG theory** | Procedural Content Generation principles | MAP-Elites, generate-evaluate-refine, repair loops | v2 |
| CausalProfiler | Space of Interest + DAG generation | Generacion guiada por propiedades | v2 |
| CausalBench | Real-world causal datasets (2-109 nodes) | Mundos grandes son dificiles de verdad | referencia |
| CauSciBench | Full causal pipeline eval | Evaluacion multi-step | referencia |
| Bayesian Teaching | LLMs learn from teacher | Progresion simple->complejo funciona | referencia |
| pgmpy get_random | Random BN generation | Generador rapido + quality filter | v2 |
| TimeGraph | Temporal causal benchmark | Referencia para mundos temporales | backlog |
| CausalGraphBench | Graph discovery eval | Futura task: recuperar estructura | v3 |
| CauseMe | Temporal causal eval platform | Referencia para mundos temporales | backlog |

## Links y repositorios

- BoxingGym: github.com/kanishkg/boxing-gym | arxiv.org/abs/2501.01540
- DiscoveryWorld: github.com/allenai/discoveryworld | arxiv.org/abs/2406.06769
- Reasoning Core: github.com/sileod/reasoning_core | arxiv.org/abs/2603.02208
- PCG Book: pcgbook.com (Shaker, Togelius & Nelson 2016)
- MAP-Elites for PCG: arxiv.org/abs/1907.04053
- PCG + LLMs survey: arxiv.org/abs/2410.15644 (Maleki & Zhao 2024)
- CausalProfiler: (2025, no public repo found)
- CausalBench: (2024)
- CauSciBench: (2025)
- Bayesian Teaching: nature.com/articles/s41467-025-67998-6
- TimeGraph: github.com/hferdous/TimeGraph
- CausalGraphBench: aclanthology.org/2025.acl-srw.16
