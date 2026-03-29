# SREG — Arquitectura
## Synthetic Research Environment Generator

> Este documento define como deberia estar organizado SREG dentro del alcance
> arquitectonico hoy seleccionado.
>
> `PROJECT.md` define la vision.
> `ARCHITECTURE.md` define el sistema objetivo para este horizonte.
> `CURRENT_STATE.md` describe que parte de eso existe hoy realmente.
> `TODO.md` describe la brecha y el trabajo pendiente.

---

## 1. Proposito

Este documento fija:

- la unidad central de producto,
- las piezas principales del sistema,
- los contratos de dominio que las conectan,
- los flujos canonicos de generacion, interaccion y evaluacion,
- y los limites de responsabilidad de SREG.

No deberia usarse para documentar estado actual, backlog, bugs o research
abierto.

---

## 2. Horizonte arquitectonico

### Alcance seleccionado

La arquitectura actual apunta a **research cases estructurados y verificables**
donde:

- la verdad del caso vive en un SCM (modelo causal estructural con ecuaciones
  y variables continuas),
- el caso visible se presenta como un problema de investigacion con datos,
  contexto y herramientas de analisis,
- el orchestrator diseña el caso como conjunto,
- el solver investiga libre y entrega hallazgos (claim cards en OI),
- y la evaluacion se ancla a verificacion formal contra el SCM.

### Debe soportar crecimiento hacia

- artefactos de evidencia mas ricos,
- material teorico sintetico,
- acciones de investigacion mas expresivas,
- briefs y casos menos cerrados,
- y paradigmas cientificos mas diversos,

sin romper el nucleo verificable del sistema.

### Fuera de alcance de esta version

- training loops de RL,
- simulacion cientifica totalmente abierta sin estructura formal,
- evaluacion cuyo nucleo dependa solo de jueces humanos o LLM-as-judge,
- y un salto inmediato a cualquier idea futura del `PROJECT.md` sin pasar por
  contratos y flujos estables.

---

## 3. Vista general del sistema

SREG se organiza alrededor de tres piezas:

1. **Generador de entornos**
   Convierte un goal, seed o paper en un caso de investigacion sintetico
   verificable.

2. **Teacher / evaluador**
   Usa la verdad formal del mundo para computar respuestas correctas,
   posteriors, efectos, recomendaciones y rewards.

3. **Policy diagnostica**
   Un solver de referencia usado para validar que los casos generados funcionen
   realmente como entornos de investigacion y no como puzzles triviales o
   shortcutteables.

```text
goal / seed / paper
        |
        v
  Orchestrator + tools
        |
        v
       SRC
        |
   +----+----+
   |         |
   v         v
solver    teacher
   |         |
   +----+----+
        |
        v
   reward / diagnostico
```

---

## 4. La unidad central: el SRC

La unidad de producto de SREG es el **SRC** (`Synthetic Research Case`).

Un SRC no es solo un grafo ni solo un prompt. Es un caso de investigacion
completo con dos capas coordinadas:

- una **capa formal oculta**, donde vive la verdad matematica del mundo,
- una **capa visible**, donde ese mundo aparece como research case para un
  solver.

Hoy el SRC es un artefacto compuesto, no una clase unica. Sus piezas centrales
son:

- `SCMWorld`
- `CasePlan`
- `ResearchProblem`
- una o mas `Task` (SRC mode) o `SubQuestionIntent` (OI mode)
- scores, trayectorias y artefactos exportables

Arquitectonicamente, el SRC debe tratarse como un producto coherente aunque se
represente con varios contratos.

---

## 5. Contratos centrales

### `SCMWorld`

Contrato del mundo formal completo.

Structural Causal Model — grafo + ecuaciones estructurales + ruido. Variables
continuas. Ver seccion 6.1.

### `CasePlan`

Contrato de diseno del caso.

Define framing, research context, preguntas planeadas, budget compartido y
hints para mantener alineadas pregunta visible y respuesta formal.

### `ResearchProblem`

Contrato de la presentacion visible del caso.

Contiene narrativa, dominio, contexto teorico, `DataAsset`s,
`AvailableAction`s, budget y pregunta principal. Es lo que el solver ve.

### `DataAsset`

Contrato de un artefacto de evidencia visible.

Representa datasets, observaciones o activos narrativos que el solver puede
inspeccionar como parte del caso.

Arquitectonicamente, esto permite que la evidencia visible no se reduzca a un
solo CSV plano.

### `AvailableAction`

Contrato de una accion de investigacion visible para el solver.

Representa que se puede hacer dentro del caso, con que costo y, cuando aplica,
sobre que nodos o con que valores de intervencion.

Es la traduccion semantica de la interfaz investigativa del caso: medir,
intervenir, pedir datos o, a futuro, otras formas de accion guiadas por el
propio research case.

### `Task`

Contrato de una evaluacion concreta derivada del mundo.

Contiene tipo, pregunta, target, evidencia visible, respuesta correcta oculta y
metodo de scoring.

La superficie de evaluacion seleccionada para este horizonte es una superficie
tipada de preguntas cientificas. Incluye:

- `infer_target`
- `next_best_observation`
- `hypothesis_selection`
- `causal_effect`
- `best_intervention`
- `adjustment_set`
- `compare_interventions`
- `should_condition`
- `infer_latent_cause`

### `Episode`

Contrato de la interaccion ejecutable.

Define budget, evidencia inicial, acciones disponibles y pasos ejecutados.

### `Score`

Contrato del resultado de evaluacion.

Separa al menos calidad funcional, eficiencia informativa y uso de budget.

### `TeacherOutput`

Contrato del teacher paso a paso: posterior verdadera, recomendacion de accion,
information gain y entropia.

---

## 6. Capas del sistema

### 6.1 Capa formal

Modela la verdad del caso. Todo reward central debe anclarse aca.

Incluye:

- variables y tipos de nodo,
- estructura causal (DAG),
- relaciones cuantitativas entre variables,
- y consultas exactas o precisas sobre el mundo.

#### Sustrato formal: SCM (Structural Causal Model)

El mundo oculto de cada SRC se define como un **SCM**: un grafo causal +
ecuaciones estructurales + ruido. Esto reemplaza la BN discreta anterior
(CPD tables con 3 estados `low/medium/high`).

Un SCM se define con dos cosas:

**1. El grafo: QUE causa QUE**

```
carga_semanal ---+
                 +--> ejercicio --> temperatura --> riesgo
fitness ---------+
```

**2. Las ecuaciones: COMO lo causa**

Cada variable es una funcion Python arbitraria de sus padres + ruido:

```python
world = SCMWorld(
    graph={
        "carga":       [],                          # raiz
        "fitness":     [],                          # raiz
        "ejercicio":   ["carga", "fitness"],
        "temperatura": ["ejercicio"],
        "riesgo":      ["temperatura"],
    },
    equations={
        "carga":       lambda p, rng: rng.uniform(2, 15),        # horas/semana
        "fitness":     lambda p, rng: rng.normal(50, 10),        # VO2max
        "ejercicio":   lambda p, rng: min(p["carga"]*0.7 + p["fitness"]*0.01, 10)
                                      + rng.normal(0, 0.5),
        "temperatura": lambda p, rng: (                          # threshold a 7
            36.5
            + (2.0 * sqrt(p["ejercicio"] - 7) if p["ejercicio"] > 7
               else 0.3 * p["ejercicio"])
            + rng.normal(0, 0.3)
        ),
        "riesgo":      lambda p, rng: sigmoid(p["temperatura"] - 39)
                                      + rng.normal(0, 0.02),
    },
)
```

**Como funciona el sampling:**

Se procesan las variables en orden topologico. Para cada muestra:

1. Tirar dado: `carga = 8.3` horas/semana
2. Tirar dado: `fitness = 47.2` mL/kg/min
3. Calcular: `ejercicio = min(8.3*0.7 + 47.2*0.01, 10) + ruido = 6.28`
4. Calcular: ejercicio < 7, asi que `temperatura = 36.5 + 0.3*6.28 + ruido = 38.48`
5. Calcular: `riesgo = sigmoid(38.48 - 39) + ruido = 0.37`

Repetir N veces. El resultado es un DataFrame con datos continuos realistas:

```
   carga   fitness  ejercicio  temperatura  riesgo
0   8.3     47.2      6.28       38.48      0.37
1  12.1     55.0      9.02       40.12      0.85
2   3.7     42.8      3.02       37.41      0.17
```

**do-calculus (intervenciones de Pearl):**

Para computar P(riesgo | do(ejercicio=9)):
- Se **fija** ejercicio = 9 (constante, no se usa su ecuacion)
- Se **cortan** los edges de carga y fitness hacia ejercicio
- Se simula el resto muchas veces (Monte Carlo)

Esto responde: "que pasaria si FORZAMOS ejercicio = 9?" — distinto de
observar ejercicio = 9 (que da informacion sobre carga y fitness).

**Reward via Monte Carlo:**

El reward ya no es analitico-exacto sino estadisticamente preciso:
con N=100K simulaciones, el error es ~0.001. Para RL, este ruido es
ordenes de magnitud menor que el del training.

**Que se preserva del grafo:**

| Propiedad | Depende de |
|---|---|
| d-separation | Solo del grafo |
| Identifiability | Solo del grafo |
| Adjustment sets | Solo del grafo |
| should_condition | Solo del grafo |
| do-calculus | Grafo + ecuaciones (simular) |

**Caracteristicas del SCM:**

| Aspecto | Detalle |
|---|---|
| Variables | Continuas, con unidades reales |
| Relaciones | Ecuaciones arbitrarias (threshold, sigmoid, sqrt, etc.) |
| Escalabilidad | Lineal con padres (no exponencial) |
| Datos generados | `38.48 C`, `6.28 intensidad` |
| Reward | Monte Carlo preciso (~0.001 con N=20K) |

### 6.2 Capa de diseno del caso

Traduce un mundo posible a un research case investigable.

Su funcion es decidir:

- que preguntas importan,
- como se presenta el caso,
- que acciones existen,
- y que restricciones organizan la investigacion.

`CasePlan` vive principalmente en esta capa.

### 6.3 Capa semantica visible

Empaqueta el caso como problema para el solver:

- narrativa,
- dominio,
- contexto teorico,
- datasets y otros artefactos,
- acciones disponibles,
- budget visible.

`ResearchProblem` vive principalmente en esta capa.

La generacion de evidencia visible forma parte de esta capa: sampling de datos,
multi-asset packaging, missingness, measurement noise y otras propiedades que
hacen que el caso se parezca mas a investigacion real que a un input limpio y
unico.

### 6.4 Capa de interaccion

Convierte las acciones visibles del caso en una interfaz de investigacion.

En OI, el solver interactua via herramientas (python_exec, think, submit_claims)
gestionadas por el OI driver. No hay EpisodeRunner ni budget de acciones.

### 6.5 Capa de evaluacion

Compara lo que hizo el solver contra lo que implica el mundo formal.

`Task`, `TeacherOutput` y `Score` viven aca.

---

## 7. Flujos canonicos

### 7.1 Generacion

El flujo canonico de generacion es:

1. recibir un `goal`, seed o paper,
2. proponer estructura y framing del caso,
3. generar un `SCMWorld` con grafo + ecuaciones,
4. validar el mundo,
5. enriquecerlo semanticamente,
6. disenar el `CasePlan` con brief y sub-preguntas,
7. generar datasets realistas,
8. construir el `ResearchProblem`,
9. empaquetar todo como SRC.

### 7.2 Interaccion

El solver recibe el `ResearchProblem` y una o mas `Task`s visibles.

Puede:

- inspeccionar datos y contexto,
- razonar libremente,
- usar herramientas de analisis y pensamiento abiertas al solver,
- ejecutar acciones de investigacion con costo,
- y finalmente enviar respuestas o decisiones.

El runner valida acciones y devuelve observaciones o resultados consistentes con
la verdad formal del caso.

En este horizonte, la interfaz del solver separa dos cosas:

- herramientas libres de razonamiento y analisis, como `python_exec` o `think`,
- y acciones de investigacion propias del caso, que consumen budget o modifican
  el estado del episodio.

### 7.3 Evaluacion

La evaluacion compara lo que hizo el solver contra lo que implica el `SCMWorld`.

Segun la task, esto puede involucrar:

- distribuciones verdaderas,
- information gain optima,
- efectos intervencionales,
- seleccion de hipotesis,
- o decisiones estructurales correctas.

El teacher define el upper bound interno del entorno.

---

## 8. Orchestrator y stack de herramientas

El orchestrator es una policy LLM que diseña casos usando herramientas
programaticas.

Su trabajo arquitectonico es:

- proponer estructura y caso,
- llamar tools para construir y validar,
- iterar cuando una propuesta falla checks,
- y terminar en un SRC coherente.

La decision importante no es el nombre de cada tool sino esta:

> El LLM diseña el caso, pero la verdad del entorno y la validacion fuerte
> viven en contratos estructurados y herramientas programaticas.

### Modelo dual y API de inferencia

Toda la codebase usa la **Responses API** de OpenAI (no Chat Completions).
Esto soporta modelos de razonamiento (codex, o-series) ademas de modelos
conversacionales clasicos.

El orchestrator y el solver usan `AZURE_MODEL` por defecto. Los scripts
aceptan `AZURE_SOLVER_MODEL` como override para el solver, permitiendo
usar un modelo de razonamiento optimizado para investigar.

---

## 9. Modelo de QA y validacion

La calidad de SREG se valida en tres niveles.

### Nivel 1: tests

Responde:

> "El codigo funciona?"

Valida contratos, invariantes, tools, episodios, solver formal e integraciones.

### Nivel 2: diagnostico de entornos

Responde:

> "Los SRCs generados funcionan como entornos de investigacion?"

Detecta trivialidad, imposibilidad, leakage, narrativa confusa y desalineacion
entre caso visible y verdad formal.

### Nivel 3: transferencia externa

Responde:

> "Entrenar con SREG mejora una policy fuera de SREG?"

Es la validacion final del producto, aunque los benchmarks externos no formen
parte del nucleo del entorno.

---

## 10. Invariantes arquitectonicas

### Alineacion entre capas

La capa visible del caso no puede contradecir la capa formal.

### El caso se diseña como conjunto

`SCMWorld`, `CasePlan`, `ResearchProblem` y `Task`s/`SubQuestionIntent`s deben
construirse como partes coordinadas de un mismo SRC.

### El reward central se ancla a la verdad formal

La semantica visible puede crecer en riqueza, pero la evaluacion central no
puede romper su anclaje en la verdad del mundo.

### La policy tiene libertad; el entorno tiene reglas

SREG no impone un procedimiento de razonamiento, pero si impone las reglas del
caso: que acciones existen, que cuestan y como impactan el mundo.

### El caso debe depender del episodio

La experiencia del solver debe depender de la evidencia y decisiones del caso,
no solo del conocimiento general del dominio.

---

## 11. Extension y limites

La arquitectura debe permitir crecimiento en:

- generadores estructurales nuevos,
- artefactos visibles mas ricos,
- acciones de investigacion mas expresivas,
- casos mas abiertos,
- y distintos niveles de realismo semantico,

sin romper coherencia ni evaluabilidad fuerte.

### Open Investigation — implementado (Alpha-0)

El modo principal de evaluacion. Separa la evaluacion en 3 capas:

1. **Solver** — investiga libre, entrega claim cards (max 5).
   Cada card tiene: texto, variables foco, confianza, evidencia.
   El solver NO ve categorias de scoring ni patrones esperados.
2. **Compiler** — traduce claim cards a specs ejecutables. Usa una
   GRAMATICA COMPOSABLE de 4 piezas (Simulacion + Medicion + Comparacion +
   Asercion). El compiler NO juzga calidad — solo traduce.
3. **SCM Verifier** — ejecuta specs contra el SCM (determinista, sin LLM).

**Gramatica composable:**
- ~24 piezas atomicas que se combinan en cientos de verificaciones posibles
- Simulacion: do, do+condicion, sweep, bundle, baseline
- Medicion: mean, variance, quantile, tail_risk, correlation, distribution
- Comparacion: difference, ratio, ranking, piecewise_fit, gap, proportion
- Asercion: positive, negative, near_zero, A>B, changepoint, sign_flip

**Modos de evaluacion:**
- **Open** (principal, Alpha-0): brief abierto, claim cards, compilacion + verificacion SCM
- **Full Open** (futuro): solo brief, sin ninguna guia

**Honestidad sobre reward:** modo Guided = exacto. Modo Open = verificacion
SCM exacta DESPUES de compilacion. La compilacion tiene subjetividad
encapsulada. Es mucho mas riguroso que LLM judge pero no 100% mecanico.

**Bottleneck actual:** el compiler (LLM extraction) es el cuello de botella.
Claims correctas del solver se traducen mal y reciben score 0. Esto es el
problema a resolver, no el solver ni el verifier.

Ver `research/synthesis/open_investigation_vision.md` para la vision completa.

SREG incluye como responsabilidad central:

- generacion de casos,
- verdad formal,
- packaging visible,
- interaccion del entorno,
- teacher / scoring,
- y QA del generador.

SREG no incluye como responsabilidad central:

- entrenamiento RL,
- optimizacion de policies,
- serving de modelos,
- ni una simulacion cientifica completamente abierta sin contratos formales.
