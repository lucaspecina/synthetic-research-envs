# Interactivity in SREG — Phase 1 Design

> **Status**: working canon para la interactividad del Investigator en
> Fase 1 de v1.5. Reemplaza a `sherlock_interactive_design.md` (archivado
> en `docs/archive/`), que fue escrito pre-rediseño v1.5 y quedó
> estructuralmente obsoleto.
>
> **Alcance**: diseño del loop interactivo agente-Environment para la
> Fase 1 del MVP de v1.5. **NO aplica al MVP Fase 0** (SCM estático sin
> interacción).
>
> **Rama**: `dev`. Se activa si los 3 tests de go/no-go de Fase 0 pasan.
>
> **Fecha**: 2026-04-24. Origen: debate ronda 1-9 en
> `research/notes/v1_5_debates.md`.

---

## 1. El problema que resuelve

En Fase 0 del MVP, el Investigator recibe un `ResearchCase` (brief +
dataset tabular + tools) y solo puede analizar lo que tiene. Toda la
data es estática. El agente hace python_exec sobre el DataFrame,
formula claims, submite. No hay experimentos, no hay data nueva, no
hay constraints realistas de costo.

Esto alcanza para validar que nuestro scoring (rubric + judge + SCM
answer keys) funciona sobre casos cerrados. Pero deja afuera la skill
central de investigación: **diseñar experimentos**. Un agente que
nunca tiene que elegir qué experimento vale la pena no aprende
priorización, no aprende timing de intervenciones, no aprende a usar
budget bien, no aprende a saber cuándo parar.

Fase 1 agrega interactividad: el Investigator puede pedir **data nueva
generada al vuelo por el Environment** mediante acciones (observar
más datos filtrados, intervenir sobre variables, estratificar,
simular trayectorias). Cada acción cuesta budget visible. Cuando el
budget se termina, solo queda submitir.

Esto materializa presiones evolutivas que Fase 0 no puede tocar
(PROJECT.md):

- Descomponer preguntas fine-grained y pedir data específica.
- Diseño experimental: elegir observacional vs intervencional.
- Plan dinámico: revisar la hipótesis después de cada experimento.
- Eficiencia: resolver con pocos experimentos, no con muchos.
- Saber cuándo parar: dejar budget o usarlo todo mal.

---

## 2. Comparativa con proyectos relacionados

### La distinción fundamental — ¿el agente genera data nueva?

Investigamos 7 proyectos del ecosistema. La distinción más importante
no es "usa tool-calling" o "tiene budget", sino **si los "experimentos"
del agente producen data nueva o solo analizan data existente**. Esa
distinción cambia por completo qué skill se entrena.

| Proyecto | Dominio | ¿Genera data nueva? | Cómo |
|---|---|---|---|
| **SciGym** | Biología de sistemas (SBML) | **SÍ, 100%** | Cada intervención corre solver de ODEs sobre el modelo oculto |
| **Corral** | Química/física/materiales (8 dominios) | **SÍ mixto** | LAMMPS real, AFM real, simuladores termodinámicos custom |
| **SciAgentGym** | STEM multi-dominio | **SÍ mixto** | Tools ejecutan librerías reales (RDKit, SciPy, BioPython) sobre inputs del agente |
| **DiscoveryWorld** | Ciencias variadas (8 tareas) | **SÍ** | Simulación text+2D con estado persistente |
| **ScienceWorld** | Ciencias de primaria | **SÍ** | Simulación text con engine Scala |
| **Asta / DataVoyager** | Data analysis (dataset fijo) | **NO** | Solo analiza el CSV que subiste |
| **DiscoveryBench** | Data-driven discovery | **NO** | Data estática, agente corre Python sobre CSVs |
| **ScienceAgentBench** | Data-driven (102 tareas) | **NO** | Escribe programa self-contained sobre datos provistos |
| **TextWorld** | Text adventures genérico | **SÍ** (pero no científico) | Juego de aventura generado |

**Los que se parecen a lo que queremos hacer son los de arriba** (SciGym,
Corral, SciAgentGym). Los que están abajo (Asta, DiscoveryBench,
ScienceAgentBench) son asistentes analíticos sobre data dada — buenos
para evaluar capacidad de análisis, no para investigación iterativa.

### El primo más cercano: SciGym

SciGym (Duan et al. 2025, Toronto + SickKids) es la referencia más
directa para el loop mecánico. Verdad matemática oculta (modelo SBML
con reacciones removidas), intervención explícita, scoring
determinista, 20 turnos cap externo.

Pero es **acotado**, no general:
- Un solo dominio: biología de sistemas.
- Un solo tipo de pregunta: "reconstruí las reacciones faltantes".
- Ground truth específica: NTS / RMS / STE sobre networks bioquímicas.

SREG aspira a ser SciGym-like en mecánica del loop, pero general en
dominios + tipos de pregunta + formalismos.

#### Cómo funciona un episodio en SciGym (verificado en el repo `h4duan/SciGym`)

El agente recibe al inicio:
- System prompt: "sos un biólogo, descubrí las reacciones faltantes".
- Un SBML parcial con especies, parámetros, compartimentos — pero
  reacciones vacías.
- 3 acciones: `observe`, `change_initial_concentration`, `submit`.

Cada turno emite markdown con 2 secciones:
```
## Thoughts
Necesito ver la dinámica baseline primero.

## Action
{"action": "observe", "metadata": {}}
```

El Environment recibe eso, **corre el solver de ODEs sobre el SBML
completo oculto**, devuelve DataFrame con columnas `[Time, E, S, ES,
P]` y lo guarda en `experiment_history[i]`.

Turno siguiente el agente puede hacer:
- Python para analizar los DataFrames acumulados.
- Otro experimento (intervención + rerun).
- Submit final con SBML reconstruido.

**Lo que tomamos prestado de SciGym**:
- Formato markdown `## Thoughts / ## Action` con JSON single-block.
- Intervención explícita que regenera data nueva al vuelo.
- Cada experimento queda versionado en `experiment_history[i]`.
- Scoring determinista contra ground truth.

**Lo que NO copiamos**:
- Action space cerrado (solo 3 acciones) → nosotros queremos mayor
  expresividad para cubrir múltiples tipos de investigación.
- Una sola pregunta fija ("reconstruí reacciones") → nosotros tenemos
  brief libre + GoldQuestions diversas.
- Cap externo en lugar de budget interno → Codex nos marcó que el
  cap externo destruye la skill "saber cuándo parar" (ronda 3).

### Lo que tomamos de los otros

**De Corral** (ecosystem con 8 dominios + metodología de anotación
epistemológica): nada nuevo del loop interactivo porque la mecánica
específica de cada dominio es ad-hoc. Lo que sí tomamos es la
**metodología de evaluación behavioral** (grafos H/T/E/J/U/C, 7
motifs, 10 breakdowns) — pero eso es para scoring procedural futuro
(issue #53), no para Fase 1.

**De SciAgentGym**: el patrón de **action templates con combinatoria**
(25 verbos × muchos objetos = ~200k acciones válidas por step en
ScienceWorld, que SciAgentGym hereda). Para nosotros traduce a "pocos
verbos, params ricos" — nuestras 4 acciones con argumentos expresivos
cubren mucho espacio sin inflar el catálogo.

**De DiscoveryWorld**: reportar múltiples métricas separadas en lugar
de una score única. Ya lo teníamos con nuestro score 8-dim.

**Anti-patrones que NO copiamos**:
- DataVoyager / DiscoveryBench: no generan data nueva → no aplica al
  modelo Sherlock.
- Asta AutoDiscovery usando Bayesian surprise del propio LLM para
  priorizar hipótesis → mete al LLM en el loop de "qué vale la pena".
- DiscoveryWorld usando GPT-4o como juez final → hackeable para RL.
- ScienceWorld con scorecard procedural predefinida por tarea →
  fuerza un solo camino válido.

---

## 3. Ejemplo concreto del loop — Birth Weight Paradox

Para aterrizar qué significa todo esto en la práctica, seguimos un
episodio completo del caso canónico (Birth Weight Paradox, Hernández-
Díaz et al. 2006).

### Setup inicial

El Investigator recibe:

- **Brief**: "Analizá el efecto del tabaquismo materno sobre mortalidad
  infantil en esta cohorte perinatal". No menciona "collider", "paradox",
  "mediation" — lenguaje de reporte real, no textbook.
- **Dataset inicial**: 500 madres, columnas `smoking`, `ses`,
  `maternal_age`, `birth_weight`, `mortality`. Samples observacionales.
- **Budget**: 10 créditos visibles.
- **Catálogo de acciones disponibles**: observe, intervene, stratify.
  (Simulate NO está — es SCM estático, no ODE.) El Case Writer podría
  además haber restringido intervene si fuera un caso "observacional
  puro" — ver Sección 6.
- **Tools estándar**: python_exec, load_artifact, save_artifact,
  think, submit_claims.

### Trace turno por turno

**Turno 1 — Análisis observacional baseline**

```python
python_exec("df.groupby('smoking')['mortality'].mean()")
→ stdout: smoking=Yes: 0.018, smoking=No: 0.009
```

Observacional: fumadoras tienen el doble de mortalidad infantil. No
gasta budget (análisis sobre dataset inicial).

**Turno 2 — Hipotetizar + pedir data ajustada**

Rationale del agente: "la asociación puede ser confounding por SES.
Vamos a ver si se sostiene dentro de un nivel de SES."

```
observe(vars=['smoking', 'mortality', 'ses'], n=300, condition={ses: 'Low'})
```

El Environment usa el SCM para samplear 300 registros de madres de SES
bajo, devuelve un DataFrame nuevo. **Data nueva** que no estaba en el
dataset inicial. Cost: 1 crédito. Remaining: 9.

**Turno 3 — Análisis condicional**

```python
python_exec("new_df.groupby('smoking')['mortality'].mean()")
→ smoking=Yes: 0.019, smoking=No: 0.010
```

Dentro de SES bajo sigue apareciendo el doble. Descarta "todo es SES".
Sigue con nueva hipótesis: *"quizás el paradox aparece al estratificar
por birth weight"*.

**Turno 4 — Estratificación por mediador sospechoso**

```
stratify(outcome='mortality', by='birth_weight_quartile',
         condition={smoking: 'Yes'})
→ Tabla:
  Q1 (bajo peso):      mortalidad 0.040
  Q2, Q3, Q4:          mortalidades 0.015, 0.012, 0.010

stratify(outcome='mortality', by='birth_weight_quartile',
         condition={smoking: 'No'})
→ Tabla:
  Q1 (bajo peso):      mortalidad 0.060
  Q2, Q3, Q4:          mortalidades 0.010, 0.008, 0.008
```

Cost: 2 créditos (1 por cada stratify). Remaining: 7.

El paradox aparece. En el cuartil de bajo peso, fumadoras tienen MENOR
mortalidad que no fumadoras (0.040 vs 0.060). Opuesto a la asociación
global.

**Turno 5 — Distinguir confounding de selection bias**

Hipótesis rival:
- (H1) Birth weight es **confounder** (algo lo causa a él y a mortalidad
  independiente de smoking) → ajustar por birth_weight sería correcto
  y daría el efecto causal.
- (H2) Birth weight es **mediador / collider** (smoking causa bajo
  peso, bajo peso causa mortalidad) → estratificar por birth weight
  introduce sesgo de selección.

Para distinguir, el agente pide un experimento:

```
intervene(do={smoking: 'No'}, n=200,
          match_covariates=['maternal_age', 'ses'])
```

El Environment usa el SCM con do-operator: samplea 200 registros bajo
la distribución contrafactual donde forzamos smoking=No, con el resto
de covariables matched a la distribución de fumadoras reales.

Cost: 3 créditos. Remaining: 4.

**Data experimental nueva** que permite comparar el efecto directo.

**Turno 6 — Análisis comparativo**

```python
python_exec("""
# Mortalidad real entre fumadoras (500 casos originales):
obs_yes = df[df.smoking=='Yes']['mortality'].mean()  # 0.018

# Mortalidad contrafactual (las mismas mujeres si no hubiesen fumado):
cf_no = intervened_df['mortality'].mean()  # 0.012

# Efecto causal directo ≈ 0.006
# Mucho menor que el efecto observacional agrupado de 0.009
""")
```

La diferencia observacional "fumar vs no fumar" es 0.009 (0.018 vs
0.009), pero el efecto causal directo es 0.006. Confirma H2: birth
weight media mucha de la asociación. Rechaza H1.

**Turno 7 — Submit**

```
submit_claims([
    Claim("tabaquismo materno aumenta mortalidad infantil (efecto
           causal ≈ 0.006-0.008, menor que asociación cruda)"),
    Claim("la inversión en el estrato de bajo peso al nacer NO
           implica beneficio — es artefacto de condicionar en un
           descendiente del tratamiento"),
    Claim("birth_weight actúa como mediador post-treatment, no
           como confounder pre-treatment")
])
```

Budget remaining: 4. No gastó todo — señal positiva de eficiencia.

### Lo que este episodio muestra

- La **secuencia** hipótesis → data → análisis → nueva hipótesis emerge
  naturalmente.
- Cada acción tiene **propósito específico**, atado a una pregunta
  que el agente tiene en mente.
- El agente **pivota** cuando los datos contradicen la hipótesis
  inicial (SES confounder → birth weight mediador).
- **Budget actúa como presión real**: el intervene cuesta 3 créditos,
  el agente lo usa en el momento decisivo, no antes.
- El **anchor matemático** (answer keys computados por el Verifier en
  design-time) permite al Evaluator juzgar si los claims finales son
  correctos sin tener que ejecutar queries nuevas en runtime.

---

## 4. Las acciones primitivas

Cuatro acciones, familias semánticas, no álgebra composicional. Cada
una mapea a una skill investigativa específica.

### 4.1 `observe(vars, n, condition=None)`

**Qué es**: samplear registros del SCM con filtro opcional.

**Argumentos**:
- `vars: list[str]` — variables a observar.
- `n: int` — tamaño de muestra requerido.
- `condition: dict[str, ConditionPredicate] | None` — filtro
  opcional (ej. `{ses: 'Low'}` o `{maternal_age: range(25, 35)}`).

**Qué devuelve**: DataFrame de N filas × len(vars) columnas, con
samples observacionales del SCM bajo la condición especificada.

**Costo**: 1 crédito (base). Escalado con N (ver Sección 5).

**Skill que entrena**:
- Elegir qué subgrupo mirar.
- Priorizar variables relevantes.
- Entender distribuciones condicionales.

**Cuándo el agente la usa**:
- Exploración inicial.
- Chequear asociaciones en subgrupos.
- Validar distribución de confounders.

### 4.2 `intervene(do, n, condition=None, match_covariates=None)`

**Qué es**: samplear registros del SCM bajo el do-operator de Pearl
(intervención formal).

**Argumentos**:
- `do: dict[str, value]` — variables a fijar con valor específico.
- `n: int` — tamaño de muestra.
- `condition: dict[str, ConditionPredicate] | None` — filtro
  post-intervención (menos común).
- `match_covariates: list[str] | None` — variables a matchear a
  la distribución de una condición de referencia (para efectos
  contrafactuales controlados).

**Qué devuelve**: DataFrame de N filas donde las variables en `do`
están fijas y el resto se samplea desde la distribución interventional
implicada por el SCM.

**Costo**: 3 créditos (base). Escalado con N.

**Skill que entrena**:
- Diseño experimental (RCT formal).
- Distinguir causalidad de asociación.
- Identificar efectos causales directos.

**Cuándo el agente la usa**:
- Cuando análisis observacional deja hipótesis rivales sin resolver.
- Para estimar efectos causales sin assumption de identifiability.
- Para validar mecanismos (intervenir sobre mediador propuesto).

### 4.3 `stratify(outcome, by, condition=None)`

**Qué es**: azúcar sintáctica — equivale a observe + groupby, devuelve
tabla resumen.

**Argumentos**:
- `outcome: str` — variable cuyo promedio queremos por subgrupo.
- `by: str` — variable de stratificación.
- `condition: dict | None` — filtro opcional.

**Qué devuelve**: Tabla de outcome means + SEs por subgrupo de `by`.

**Costo**: 2 créditos (base — más que observe, menos que intervene).

**Skill que entrena**:
- Detectar heterogeneidad.
- Identificar paradojas de Simpson / Yule.
- Verificar invariancia de efectos.

**Cuándo el agente la usa**:
- Cuando sospecha que el efecto varía por subgrupo.
- Para detectar mediación / moderación.
- Para encontrar collider bias.

### 4.4 `simulate(initial, t_eval, do=None)` (SOLO ODE/SDE)

**Qué es**: correr trayectoria temporal del WorldModel desde
condiciones iniciales, con intervención opcional sostenida.

**Argumentos**:
- `initial: dict[str, value]` — estado inicial del sistema.
- `t_eval: list[float]` — tiempos en los que observar el estado.
- `do: Intervention | None` — intervención (point, sustained,
  time-varying).

**Qué devuelve**: DataFrame con columnas `[Time, var1, var2, ...]`,
trayectoria del sistema bajo esas condiciones.

**Costo**: 5 créditos (base — lo más caro).

**Skill que entrena**:
- Razonamiento dinámico.
- Identificar escalas temporales.
- Control experimental en tiempo.

**Cuándo el agente la usa**:
- Cuando el WorldModel tiene dinámica temporal.
- Para detectar steady states, oscilaciones, bifurcaciones.
- Para diseñar protocolos de intervención dependientes del tiempo.

### 4.5 Regla de no-proliferación

Codex (ronda 8) nos marcó: si la API empieza a crecer con 15+ acciones,
volvemos a AtomicSpec-lite por la ventana. Disciplina:

- Nuevas acciones solo nacen de patrones recurrentes en GoldQuestions
  reales que no se pueden expresar con las 4 existentes.
- Nuevas acciones no nacen de ad-hoc "sería lindo tener X".
- Cada acción nueva requiere (a) justificación de qué skill entrena y
  (b) ejemplo concreto de GoldQuestion que la necesita.

---

## 5. Budget model

### Principio

Budget **visible y explícito**. El Investigator ve `remaining: N` en
cada observation del Environment. Esto fuerza priorización:

> ¿Vale la pena gastar 3 créditos en este intervene, o puedo resolver
> lo mismo con 1 observe + análisis?

Sin visibilidad, el agente no aprende a gestionar costo.

### Budget por caso

Cada ResearchCase tiene `total_budget: int` configurado por el Case
Writer según complejidad del caso:

- Casos simples (4-6 GoldQuestions, fenómenos lineales): 6-8 créditos.
- Casos medios (6-8 GoldQuestions, algunos fenómenos no triviales):
  10-15 créditos.
- Casos complejos (8-12 GoldQuestions, dinámica o heterogeneidad):
  15-25 créditos.

### Cost scaling con N (rescate del sherlock viejo)

Sin esta regla, el agente pide `n=100000` y saturando saca la
incertidumbre por muestreo. Budget sin scaling es cosmético.

**MVP Fase 1 — Opción A (n fijo por tier)**:
- `observe` siempre devuelve N=100.
- `intervene` siempre devuelve N=50.
- `stratify` siempre usa N=200 por subgrupo.
- `simulate` siempre usa t_eval fijo según formalismo.
- El agente no elige N, solo qué pedir.
- Más simple, menos expresivo.

**Fase 1.5 — Opción B (cost proporcional a N)**:
- `cost(observe, n) = 1 * ceil(n / 100)`.
- `cost(intervene, n) = 3 * ceil(n / 50)`.
- Etc.
- El agente decide precision vs cobertura.
- Más expresivo, requiere más prompting cuidadoso.

Arrancamos con Opción A. Pasamos a B solo si vemos que la restricción
de N fijo bloquea casos legítimos.

### Terminación por budget

Cuando `remaining <= 0`, las acciones observe/intervene/stratify/simulate
devuelven error y el agente solo puede `submit_claims`. No hay "un
crédito de gracia" — la disciplina es parte del diseño.

---

## 6. Case Writer restringe acciones disponibles (Opción B)

### Rationale

No todos los casos en ciencia real admiten todas las acciones. Un
estudio retrospectivo no puede intervenir. Un estudio de observación
natural no puede asignar tratamientos al azar. Ciencias ambientales
sobre ecosistemas complejos a veces no permiten replicación.

Si el Case Writer expone siempre las 4 acciones en todos los casos,
perdemos realismo y perdemos una skill: saber cómo investigar bajo
constraints operativos reales.

### Mecanismo

El ResearchCase tiene un campo `access_policy`:

```python
class AccessPolicy(BaseModel):
    available_actions: list[Literal["observe", "intervene",
                                     "stratify", "simulate"]]
    max_n_per_call: dict[str, int]  # opcional, si se quiere fijar
    forbidden_variables: list[str]  # variables sobre las que no se
                                     # puede intervenir (ej. edad)
    rationale: str  # por qué estos constraints (reportable al agente)
```

### Ejemplos concretos

**Caso observacional puro** (Birth Weight Paradox histórico):
```python
AccessPolicy(
    available_actions=["observe", "stratify"],
    rationale="Estudio retrospectivo de cohorte hospitalaria. No se
               pueden asignar tratamientos aleatoriamente — los datos
               ya existen. Se puede muestrear con filtros, no
               experimentar."
)
```

El agente no tiene `intervene` disponible. Tiene que inferir el
efecto causal vía métodos observacionales (stratification, ajuste por
covariables). Más duro, más realista.

**Caso experimental parcial** (farmacología con constraint ético):
```python
AccessPolicy(
    available_actions=["observe", "intervene", "stratify"],
    forbidden_variables=["pregnancy_status"],
    rationale="Se pueden hacer RCTs sobre la dosis, pero no
               experimentar sobre el status gestacional de las
               pacientes (ético). Las condiciones deben matchear
               naturalmente."
)
```

El agente puede intervenir, pero no sobre `pregnancy_status`. Tiene
que estratificar u observar distribución natural.

**Caso experimental completo** (ODE farmacocinética):
```python
AccessPolicy(
    available_actions=["observe", "intervene", "stratify", "simulate"],
    rationale="Estudio in vitro / in silico. Todas las intervenciones
               están permitidas."
)
```

### Visibilidad al agente

El `rationale` se le muestra al Investigator al inicio. Sabe qué puede
y qué no puede hacer, y por qué. El Evaluator lo tiene en cuenta al
juzgar el reporte: si el agente dice "no pude estimar el efecto
causal porque los datos son observacionales y hay confounders no
medidos", eso acredita la GoldQuestion de identificabilidad.

---

## 7. Qué hooks dejamos en Fase 0 MVP

Codex (ronda 8) nos marcó que ciertos hooks son "casi gratis" en el
MVP Fase 0 y evitan refactor grande cuando activemos Fase 1. Los
dejamos:

1. **`EnvironmentSession` como contract abstracto** (no implementado
   en Fase 0, pero el tipo existe):
   ```python
   class EnvironmentSession(Protocol):
       seed: int
       step: int
       budget_remaining: int | None = None  # None = ilimitado (Fase 0)
       def observe(self, ...) -> Data: ...
       def intervene(self, ...) -> Data: ...
       def stratify(self, ...) -> Data: ...
   ```

2. **`InvestigatorAction` con tipos abiertos** (ya lo agregamos a
   ARCHITECTURE.md §5):
   ```python
   kind: Literal["python_exec", "observe", "intervene",
                  "hypothesis", "pivot", "submit"]
   ```
   En MVP solo usamos `python_exec` y `submit`. El schema admite los
   demás sin refactor.

3. **Artifacts derivados de acciones**: cada `observe`/`intervene`/etc
   debe producir un `artifact_id` igual que `load_artifact`/
   `save_artifact`. Ya tenemos el framework de artifacts con IDs; se
   extiende naturalmente.

4. **`ResearchCase.access_policy`** como campo opcional. En Fase 0
   queda `None` o default estático (solo python_exec). Fase 1 lo llena.

5. **Queries stateless por default**: cada call independiente. Stateful
   (acciones cambian lo que viene después) queda para v2 (layered
   worlds).

6. **Rubrics no acopladas a "dataset fijo"**: las escribimos en
   términos de findings ("reconoce X", "cuantifica Y") que sobreviven
   al cambio observacional → experimental. Ya lo hacemos.

---

## 8. Rescates del sherlock viejo

El doc predecesor `sherlock_interactive_design.md` (archivado en
`docs/archive/`) tenía ideas valiosas que migran a este diseño.

### Warning sobre WorldSummary leakage

Si el Case Writer incluye en el brief descripciones ricas de variables
y sus relaciones, el Investigator puede inferir estructura causal sin
gastar budget — y el budget se vuelve cosmético.

**Política operativa**:
- **Gratis**: nombres de variables, brief en prosa, unidades,
  rationale del access_policy, catálogo de acciones disponibles.
- **Ganado con observe/intervene**: distribuciones, correlaciones,
  relaciones estructurales, proporciones.
- **Prohibido incluir en el brief**: cualquier hint explícito de
  estructura causal (ej. "SES es un confounder", "X media Y").

El Validator debe chequear esto: adversarial check con agente sin
data intenta responder GoldQuestions desde solo el brief. Si acierta,
hay leakage y el Case Writer tiene que regenerar el brief sin hints.

### Dead ends y honey traps (roadmap futuro, NO en Fase 1)

El sherlock viejo proponía que el Case Writer diseñara **explícitamente**
algunas variables "interesantes pero sin valor causal" para que el
agente las persiga y gaste budget. Esto es diseño adversarial del
entorno.

En Fase 1 no lo metemos — ya es bastante complejidad. Pero lo
anotamos para Fase 1.5 o v2: variables señuelo con alta correlación
pero sin rol causal, que el agente tiene que aprender a descartar.

### Modelos 2 y 3 como roadmap post-Fase 1

- **Modelo 1 (Fase 1 actual)**: budget-gated access. El agente ve
  todas las variables, tiene 4 acciones disponibles, presupuesto
  limitado.
- **Modelo 2 (Fase 1.5)**: progressive revelation. El agente no ve
  todas las variables de entrada — algunas están "locked" y tiene
  que pedirlas. Fuerza hipótesis previas a observación.
- **Modelo 3 (v2)**: layered worlds con estructura de revelación
  diseñada. Cada capa revela nuevas variables + nuevas acciones. Los
  dead ends y honey traps viven acá.

Fase 1 implementa Modelo 1 solo. Si valida, Modelo 2 en Fase 1.5.
Modelo 3 queda como horizonte v2 (issue #16).

---

## 9. Qué es un experimento bueno vs malo

No toda acción es buen uso del budget. El agente entrenable debería
internalizar qué diferencia una buena de una mala.

### Un experimento bueno:

**Diagnóstico**: distingue al menos 2 hipótesis rivales que el agente
tiene en mente. Ejemplo: `intervene(do=smoking=No, match=covariates)`
distingue "confounding clásico" de "mediator selection bias".

**Formulado después de hipotetizar**: el agente tiene una pregunta
específica en mente antes de llamar la acción. No pide "a ver qué
pasa".

**Cost-efficient**: se elige la acción más barata que pueda resolver
la pregunta. `observe` antes que `intervene` si `observe` alcanza.

**Tiene predicción implícita**: "si H1 es cierta, el resultado debería
ser X; si H2, debería ser Y".

### Un experimento malo:

**Fishing expedition**: pedir muchos observe random sin hipótesis.

**Over-intervention**: pedir intervene cuando observe + análisis
alcanzaba.

**Duplicación**: pedir lo mismo dos veces o pedir data redundante.

**Brute force**: pedir `n=100000` para eliminar varianza en vez de
diseñar mejor.

**No-diagnostic**: pedir data que no distingue entre las hipótesis
que tengo, solo confirma una.

### Cómo lo evalúa el Evaluator

En el MVP Fase 1 no evaluamos directamente "bueno vs malo". Evaluamos
vía proxy: el score final sobre GoldQuestions + el presupuesto que
usó. Un agente con score alto y budget sobrante hizo experimentos
buenos. Un agente con score bajo y budget agotado hizo experimentos
malos.

Futuro (issue #53): evaluación procedural explícita de la trayectoria
con Corral-style behavioral analysis.

---

## 10. Roadmap de fases

### Fase 0 — SCM estático (MVP actual)

- Solo python_exec + submit_claims.
- Dataset estático en el ResearchCase.
- InvestigationLog registra cada tool call pero no se evalúa.
- 3 tests de go/no-go al final: necessity ablation, judge adversarial,
  style/leak invariance.

### Fase 1 — SCM estático + interactividad (4-6 semanas post Fase 0)

- 3 acciones activas: observe, intervene, stratify (simulate no aplica
  a SCM estático).
- Budget visible por caso.
- Opción A de cost scaling (N fijo por tier).
- Case Writer puede restringir acciones vía `access_policy`.
- Se corre el mismo MVP Birth Weight Paradox con las 3 tests de
  go/no-go **más** un test nuevo: "con acciones disponibles, ¿el agente
  mejora claro sobre el mismo caso sin acciones?".

### Fase 1.5 — ODE/SDE + Modelo 2 (4-6 semanas post Fase 1)

- 4 acciones: agregamos simulate.
- Opción B de cost scaling (proporcional a N).
- Modelo 2: progressive revelation (algunas variables locked).
- Nuevo dominio: farmacocinética (ODE) o eutrophication (ODE).

### Fase 2 — Paper y distilación

- SDE support.
- Distilación del Evaluator a classifier chico.
- Experimentos before/after con RL training.

### v2 — Sherlock completo (fuera de scope v1.5)

- Modelo 3: layered worlds.
- Dead ends / honey traps.
- Statefulness entre queries.
- Issue #16.

---

## 11. 3 tests de go/no-go para cerrar Fase 1

Análogos a los 3 tests de Fase 0 (necessity / adversarial / style)
pero adaptados a interactividad:

### Test 1 — Interactivity adds information

Correr el mismo caso con y sin acciones disponibles. Esperamos que
el agente con acciones saque **significativamente mejor** score que
el agente solo con dataset inicial. Criterio: mejora ≥ 15 puntos
percentil.

Si la mejora es pequeña, las acciones no están agregando señal — o
el caso es demasiado fácil, o las acciones son redundantes con
python_exec.

### Test 2 — Budget discrimination

Correr el mismo caso con budget 5, budget 10, budget 20. Esperamos que
el agente con budget alto saque mejor score, pero no linealmente —
retornos decrecientes. Criterio: score(budget=20) > score(budget=5) y
score(budget=20) - score(budget=10) < score(budget=10) - score(budget=5).

Si la curva es plana (budget no importa) o lineal (más budget =
siempre proporcionalmente mejor), el agente no internalizó la
economía de experimentos.

### Test 3 — Access policy respeto

Correr casos con access_policy restrictiva (solo observe + stratify)
y casos con access policy libre. Esperamos que el agente:
- Con access restrictiva: abstiene con claims calibradas cuando no
  puede identificar el efecto causal.
- Con access libre: usa intervene cuando corresponde.

Criterio: los claims del agente cambian coherentemente según la
access_policy. Si responde lo mismo con y sin intervene, está
ignorando las constraints del caso.

---

## 12. Dudas abiertas

- **¿Cost scaling opción A vs B en MVP Fase 1?** Arrancamos con A (N
  fijo). Pasamos a B si Test 2 muestra discriminación débil.

- **¿Budget visible o hidden?** Visible en MVP Fase 1. Hidden para
  investigar en Fase 1.5 — puede forzar planning más explícito.

- **¿stratify es primitiva o composición?** En MVP la tratamos como
  primitiva por conveniencia operativa, pero bajo el capot es
  observe + groupby. Si vemos que el agente la usa raro, la quitamos.

- **¿Cuántos créditos por caso?** Intuición: 10 para caso simple, 20
  para caso complejo. Calibrar con pilot humano.

- **¿Observe costea menos si las variables ya fueron observadas antes
  en el mismo episodio?** Incentivo dudoso — podría favorecer
  persistencia de hipótesis iniciales. Dejar cost fijo en MVP.

- **¿`intervene` con `match_covariates` es una primitiva o un argumento
  más del mismo intervene?** Lo dejamos como argumento opcional;
  complica pero es la forma natural de pedir matched intervention.

---

## Referencias

- `ARCHITECTURE.md` — arquitectura v1.5 canon. §5 contratos Pydantic,
  §12 fases, este doc se articula con la Fase 1.
- `research/notes/v1_5_debates.md` — rondas 1-9 de debate. Ronda 8
  (Sherlock / hooks) y ronda 9 (investigación comparativa) son las
  más relacionadas con este diseño.
- `research/notes/rethink_sreg_2026-04-23.md` — working doc con
  historia del rediseño.
- `docs/archive/sherlock_interactive_design_v2.md` — predecesor de
  este doc, pre-rediseño v1.5. Conserva ideas rescatadas (WorldSummary
  leak, modelos 2/3).
- `research/synthesis/related_work_scigym.md` — primo más cercano
  mecánico.
- `research/synthesis/related_work_corral.md` — validación empírica
  del approach "LLM-as-judge con anchor".
- `research/synthesis/related_work_sciagentgym.md` — larga-horizonte
  task-use analysis.

Papers citados:
- Duan et al. 2025, SciGym, arXiv:2507.02083.
- Ríos-García / Jablonka et al. 2026, Corral, arXiv:2604.18805.
- Shen et al. 2026, SciAgentGym, arXiv:2602.12984.
- Hernández-Díaz, Schisterman, Hernán 2006, "The Birth Weight Paradox
  Uncovered?", American Journal of Epidemiology 164(11):1115-1120.
