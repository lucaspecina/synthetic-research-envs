# Sherlock-Type Interactive Investigation — Design Document

> **Status:** CANON diseno v2. Research activo.
> **Date:** 2026-04-13
> **Issue:** #16
> **Related:** `related_work_scigym.md`, `open_investigation_vision.md`,
> `PROJECT.md` Horizonte 2

## El problema

SREG v1 es flat: el solver recibe todo upfront (dataset completo,
WorldSummary, catalogo de variables) y solo tiene que analizar y reportar.
Un agente puede resolverlo con "load CSV, correr 3 analisis, submit" sin
planificacion real, sin disenar experimentos, sin decidir cuando parar.

La investigacion real es long-horizon porque la informacion esta en capas.
Cada capa revela que hacer en la siguiente. Un cientifico no recibe todos
los datos de entrada — los va generando con experimentos, cada uno
informado por los anteriores.

**El salto de v1 a v2:** convertir el episodio de un paquete estatico a
un entorno interactivo con revelacion secuencial de informacion.

---

## Que cambia y que no

| Aspecto | v1 (actual) | v2 (Sherlock) |
|---|---|---|
| Datos disponibles | Todo upfront (CSV completo) | Inicialmente parcial, se gana con acciones |
| Interaccion | Solo python_exec sobre datos fijos | observe + intervene + counterfactual sobre SCM vivo |
| Budget | Ilimitado (de facto) | Limitado — cada accion cuesta |
| Scoring | Verdad vs SCM | **Igual** — verdad vs SCM |
| Presion evolutiva | Analisis de datos, claims correctas | + diseno experimental, + planificacion, + saber cuando parar |
| Backward compat | — | v1 = caso especial (budget infinito, solo observacional) |

**Lo que NO cambia:** el scoring. La verdad sigue siendo el SCM ground
truth. AtomicSpec, verifier, SQ v2, LLM judge — todo igual. Lo que cambia
es COMO el agente llega a la informacion que necesita para hacer claims
correctas.

---

## SciGym como inspiracion (y limites)

SciGym (Duan et al. 2025) es el unico benchmark publico que mide ciclo
iterativo completo de investigacion. 350 sistemas biologicos en SBML.
El agente interactua con un simulador vivo.

### El flujo de SciGym

```
Modelo oculto: circuito de 3 genes (A reprime B, B activa C, C activa A)

Lo que el agente recibe:
  <species id="A" initialConcentration="1.0"/>
  <species id="B" initialConcentration="1.0"/>
  <species id="C" initialConcentration="0.5"/>
  <!-- Las reacciones fueron borradas -->

Turno 1: run_experiment() sin cambios → ve oscilaciones
Turno 2: set_initial_concentration("A", 100) → B baja, C sube → "A reprime B"
Turno 3: set_initial_concentration("B", 100) → C sube, A baja → "B activa C"
Turno 4: codigo Python para correlaciones cruzadas con lag
Turno 5: submission del modelo inferido
```

Los "datos" no son un dataset — son un simulador. Cada experimento genera
datos nuevos. El agente decide que perturbar, cuanto, observa, piensa,
diseña el siguiente experimento. 20 turnos maximo.

### Comparacion SREG vs SciGym

| Dimension | SREG | SciGym |
|---|---|---|
| Verdad oculta | SCM (DAG + ecuaciones) | Modelo SBML (reacciones + ODEs) |
| Que se esconde | Estructura causal + mecanismos | Reacciones bioquimicas |
| Datos | Samples del SCM (tablas) | Series temporales del simulador |
| Interaccion | Hoy: ninguna. Futuro: observe/intervene/counterfactual | Perturbativa (cambiar concentraciones) |
| Dominio | Cualquiera (socio, eco, bio, abstracto) | Solo biologia de sistemas |
| Scoring | Vs SCM ground truth | Vs SBML ground truth (NTS/RMS/STE) |
| Diversidad | Infinitos escenarios, cualquier tipo de pregunta | 350 modelos de biologia, pregunta fija ("descubri reacciones") |

### Lo que SciGym NO puede hacer (y SREG si)

1. **Solo un tipo de pregunta.** Siempre es "descubri las reacciones".
   No hay "X causa Y?", "que media este efecto?", "es confounding o
   causal?", "cuando es seguro concluir?". Es structure recovery, punto.

2. **No enseña juicio cientifico.** El agente no decide que estudiar, no
   evalua si una conclusion es prematura, no tiene que resistir la
   tentacion de over-claim. Solo busca reacciones.

3. **Un solo dominio.** Biologia de sistemas + ODEs. No cubre causalidad
   en economia, confounding en epidemiologia, mediacion en psicologia.

4. **No es entrenable de forma general.** Es un benchmark (mide, no
   entrena). SREG es un generador de entornos (produce infinitos
   escenarios diversos para training).

### Lo que SciGym hace mejor

1. **Interaccion real.** El agente interactua con el mundo, no solo lee
   una tabla.

2. **Modelos reales.** Los SBML vienen de papers publicados por biologos.
   Validez ecologica alta.

3. **Budget como presion.** 20 turnos crea presion real para eficiencia
   y planificacion.

**Conclusion:** SciGym valida el approach (simulador + interaccion +
scoring exacto funciona para RL). SREG puede adoptar la interactividad
pero con mas expresividad (3 tipos de queries vs 1, diversidad de
dominios, diversidad de preguntas).

---

## Las tres tools del "laboratorio SCM"

El SCM ya soporta las tres operaciones de la escalera causal de Pearl.
Solo hay que exponerlas al solver como tools.

| Tool | Que hace | Analogo SciGym | Que enseña |
|---|---|---|---|
| `observe(filter, n)` | Datos observacionales filtrados | — | Saber que subgrupo mirar |
| `intervene(do(X=x), n)` | Datos bajo intervencion | `set_initial_concentration` | Diseño experimental, distinguir causal de correlacional |
| `counterfactual(X=x', given)` | "Que hubiera pasado si...?" | — | Razonamiento contrafactual (SciGym no tiene esto) |

SciGym solo tiene la segunda. SREG tendria las tres — estrictamente mas
expresivo.

### Como cambia la experiencia del solver

**Hoy (v1):**
```
Recibe tabla de 500 filas → analiza con python_exec → reporta
```

**v2 (Sherlock):**
```
Recibe tabla inicial de 100 filas observacionales (budget limitado)
  → "Hmm, Education e Income correlacionan. Es causal?"
  → intervene(do(Education=16), n=50) → 50 samples intervenidos
  → "Income sube. Pero es directo o mediado por Occupation?"
  → intervene(do(Education=16, Occupation=current), n=50) → mediador fijado
  → "El efecto baja. Parte del efecto es mediado."
  → Reporta: "Education → Income, parcialmente mediado por Occupation"
```

---

## Tres modelos de information gating

### Modelo 1: Budget-gated interventions (v2 minimo viable)

- Solver recibe datos observacionales gratis (muestra reducida: N=100)
- Puede pedir datos intervenidos: `intervene(do(X=x), n=50)` — cuesta budget
- **v2.0:** solo `request_observation` + `request_intervention` (2 tools)
- **v2.1:** agrega `request_counterfactual` (3ra tool, deferred)
- Budget limitado: 5-10 "experimentos"
- **Presion:** diseño experimental, eficiencia, saber cuando parar

> **Nota (Codex review 2026-04-13):** `request_counterfactual` se difiere a
> v2.1 por tres razones: (1) complejidad semantica prematura — counterfactuals
> requieren twin networks y el agente primero debe aprender a usar observe +
> intervene bien; (2) riesgo de oracle leak — counterfactuals mal disenados
> pueden revelar estructura causal directamente; (3) observe + intervene ya son
> suficientes para razonamiento causal completo (Pearl's do-calculus). Agregar
> counterfactuals antes de validar las 2 tools basicas es gold-plating.

**Ventajas:**
- No hay que redisenar los mundos
- El SCM engine ya lo soporta (do-operator existe)
- Backward compat (v1 = budget infinito, solo observacional)
- Path de menor friccion

**Desventajas:**
- El agente todavia "ve" todas las variables desde el inicio
- Menos Sherlock, mas "laboratorio con presupuesto"

### Modelo 2: Progressive revelation

- Solver empieza con muestra chica (N=50) de un subconjunto de variables
- Puede pedir: mas datos (cuesta), datos de nuevas variables (cuesta),
  intervenciones (cuesta mas)
- Algunas variables estan "locked" — hay que pedir acceso
- **Presion extra:** priorizacion de que variables mirar, hipotesis antes
  de observar

**Ventajas:**
- Mas parecido a investigacion real (no ves todo de entrada)
- Fuerza hipotesis previas a observacion

**Desventajas:**
- Requiere metadatos nuevos en el mundo (que variables estan visibles)
- Mas complejo de disenar y balancear

### Modelo 3: Layered worlds (full Sherlock)

- Variables tienen "profundidad de descubrimiento"
- Solver ve solo outcomes y features iniciales
- Descubre mediadores, confounders, moderadores investigando
- Cada capa revela mas estructura
- Dead ends y honey traps como parte del diseño del mundo
- **Presion maxima:** exploracion vs explotacion, planificacion multi-step

**Ventajas:**
- La experiencia mas parecida a investigacion real
- Crea presion para TODAS las propiedades evolutivas

**Desventajas:**
- Requiere redisenar como se generan los mundos
- Balance de dificultad es hard
- Riesgo de "juego" si las capas son artificiales

### Recomendacion

**Implementar Modelo 1 primero.** Es el v2 minimo viable, validable en
semanas. Si funciona, escalar a Modelo 2. Modelo 3 es horizonte largo.

---

## Diseño concreto del Modelo 1

### Nuevas tools del solver (v2.0: 2 tools)

```python
# Datos observacionales filtrados
request_observation(
    filter: dict[str, ConditionPredicate],  # reusar predicados P1
    n: int = 100,
)  # costo: 1 budget unit (base, escalado por n — ver budget model)

# Datos bajo intervencion
request_intervention(
    interventions: dict[str, float],  # do(X=x)
    filter: dict[str, ConditionPredicate] | None = None,
    n: int = 100,
)  # costo: 2 budget units (base, escalado por n — ver budget model)

# [DEFERRED v2.1] Datos contrafactuales
# request_counterfactual(
#     interventions: dict[str, float],  # X hubiera sido x'
#     condition: dict[str, float],  # dado que observamos esto
#     n: int = 50,
# )  # costo: 3 budget units
```

### Budget model

```python
class ExperimentBudget:
    total: int = 10           # budget total
    observation_cost: int = 1
    intervention_cost: int = 2
    # counterfactual_cost: int = 3  # DEFERRED v2.1
    remaining: int            # decrements con cada request
```

Cuando `remaining == 0`, el solver solo puede hacer `submit_claims()`.
No hay mas datos nuevos.

> **CRITICAL FIX (Codex review 2026-04-13): cost must scale with n.**
> Si n=100 cuesta lo mismo que n=10000, el agente simplemente pide samples
> enormes y elimina la varianza estadistica sin costo. Esto destruye la
> presion por diseño experimental eficiente. Dos opciones:
>
> - **Opcion A: n fijo por tier.** `observe` siempre da n=100, `intervene`
>   siempre da n=50. El agente no elige n, solo que preguntar. Mas simple,
>   pero menos expresivo.
> - **Opcion B: cost proporcional a n.** `cost = base_cost * ceil(n / n_unit)`.
>   Ej: n_unit=50, observe base=1 → pedir n=200 cuesta 4 budget units.
>   Mas expresivo, el agente decide precision vs cobertura.
>
> **Recomendacion:** Opcion A para v2.0 (simplicidad), Opcion B para v2.1.
> Pero NUNCA cost flat con n libre — es un exploit trivial.

### WARNING: WorldSummary leakage (Codex review 2026-04-13)

Si el solver recibe un WorldSummary rico gratis al inicio del episodio
(lista de variables, descripciones, metadata de distribuciones), se
reintroducen los shortcuts de v1: el agente puede inferir estructura
causal del metadata sin gastar budget. Esto anula la presion por diseño
experimental.

**Necesita decision:** que metadata es gratis vs ganado.
- **Gratis:** nombre de las variables, brief de investigacion, unidades.
- **Ganado (requiere observe/intervene):** distribuciones, correlaciones,
  relaciones entre variables, descripciones semanticas ricas.
- **Prohibido:** cualquier hint de estructura causal (ej: "X es un
  confounder", "Y depende de Z").

Si el WorldSummary actual es demasiado rico, hay que reducirlo para v2
o el budget es cosmetic — el agente ya tiene la informacion.

### Cambios en OIEpisodeRunner

- `__init__` recibe `experiment_budget: int = 10` (default 10)
- Nuevos metodos: `request_observation()`, `request_intervention()`,
  `request_counterfactual()` — cada uno decrementa budget y llama al SCM
- `submit_claims()` sigue igual
- `initial_dataset` reducido a N=100 (configurable)

### Cambios en el agent framework

Dos tools nuevas en `src/sreg/agent/` (v2.0):
- `request_observation` → llama `runner.request_observation()`
- `request_intervention` → llama `runner.request_intervention()`
- ~~`request_counterfactual`~~ → **deferred to v2.1**

Cada una retorna un DataFrame que el solver puede analizar con
`python_exec`.

### Scoring: efficiency como componente

```python
# Opcion A: efficiency como factor multiplicativo
efficiency = 1.0 - (budget_used / budget_total) * penalty_rate
score.total = correctness * coverage * max(efficiency, 0.5)

# Opcion B: efficiency como componente aditivo (como v1 tenia)
score.total = W_CORRECT * correctness + W_COVERAGE * coverage + W_EFF * efficiency

# Opcion C: no agregar efficiency al score, dejar que el budget
# cree presion indirectamente (menos datos → peor analisis → menos truth)
```

**Opcion C es la mas limpia** y la mas alineada con los principios de
scoring ("la verdad es matematica contra el SCM"). El budget crea
presion indirecta: un agente que desperdicia experiments no tiene los
datos para hacer claims correctas. No necesitas premiarlo por ahorrar
— el castigo por no tener datos es suficiente.

**Decision: Option C (indirecta) confirmada (Codex review 2026-04-13).**
Adicionalmente, reportar `budget_spent` (y `budget_remaining`) como
**metrica diagnostica secundaria** — util para analisis y debugging,
pero NO incluida en el reward signal. Esto permite estudiar la
correlacion entre eficiencia y score sin contaminar el reward.

---

## El problema dificil: reward y diseño experimental

### El reward terminal es suficiente?

En v1, el reward solo ve el resultado final (claims). El agente no recibe
signal sobre si sus intervenciones fueron buenas o malas — solo si la
conclusion final fue correcta.

**Riesgo:** el agente aprende a ignorar las tools de intervencion y
simplemente adivinar desde datos observacionales (que es lo que ya hace
en v1). Si puede sacar 0.5 sin gastar budget, para que gastar?

### Mitigaciones

1. **Mundos donde la respuesta correcta requiere intervencion.**
   Confounders fuertes, mediacion oculta, efectos que se cancelan
   observacionalmente. El agente que no interviene saca 0.2 y el que
   interviene saca 0.6. La presion se crea sola.

2. **Claims que requieren evidencia interventional.**
   "X causa Y" sin evidencia interventional → score penalizado (la
   claim dice "causal" pero la evidence_basis es solo correlacional).

3. **Preguntas que son irrespondibles sin intervencion.**
   Briefs del tipo "determina si X causa Y o si la correlacion es
   espuria" — sin do-calculus empirico, la respuesta es necesariamente
   "no se".

4. **NO mitigacion artificial.** No forzar budget minimo, no premiar por
   usar tools, no dar bonus por "buen diseño experimental". Eso son
   reglas de juego, no presion real. La presion debe emerger de que SIN
   intervencion la verdad es inalcanzable en suficientes mundos.

### Diseño de mundos "intervention-requiring"

Tipos de mundos donde la observacion pura no alcanza:

- **Confounding fuerte:** X←C→Y, correlacion alta pero X no causa Y.
  Solo `intervene(do(X=x))` distingue.
- **Mediacion oculta:** X→M→Y, efecto directo ≈ 0 pero efecto total > 0.
  Sin intervenir en M, no se puede separar directo de indirecto.
- **Collider bias:** X→C←Y, condicionar en C crea correlacion espuria.
  Intervenir bypasea el collider.
- **Efecto cancelado:** X→Y positivo + X→M→Y negativo, efecto neto ≈ 0
  observacionalmente. Intervenir revela los paths separados.
- **Heterogeneidad:** efecto de X en Y depende de Z. Sin condicionar
  en Z, el efecto promedio es chico. Pero `observe(filter={Z: range})`
  + `intervene` en cada subgrupo revela el efecto real.

La clave: el **mix** de mundos en el training tiene que incluir
suficientes mundos intervention-requiring para que el agente que no
interviene obtenga reward sistematicamente mas bajo.

> **CRITICAL (Codex review 2026-04-13): SQ v2 MUST include
> intervention-requiring targets.** No alcanza con que los MUNDOS requieran
> intervencion — las PREGUNTAS (sub-questions) tambien deben requerirla.
> Si las SQs se pueden responder con correlaciones solas, el agente no
> tiene razon para usar las nuevas tools, sin importar la estructura del
> mundo. Ejemplo: un mundo con confounding fuerte pero cuya SQ es "cual
> es la correlacion entre X e Y?" no fuerza intervencion. La SQ debe ser
> "X causa Y, o la correlacion es espuria?" — eso SI requiere intervenir.
> Esto no es solo sobre mundos, es sobre las PREGUNTAS.

---

## Riesgos identificados (Codex review 2026-04-13)

1. **Statistical variance with small budgets.** Con budget=10 y n pequeño,
   la varianza muestral domina. Un agente puede hacer el experiment correcto
   y sacar datos ruidosos que llevan a conclusiones erroneas. El reward
   depende en parte de "suerte muestral", no solo de skill. **Mitigacion:**
   evaluar promediando sobre replicas (mismo mundo, mismo agente, multiples
   runs). El reward esperado debe reflejar la calidad de la estrategia, no
   un sample particular.

2. **Budget/complexity mismatch.** 10 experiments fijos: son demasiados para
   un grafo de 3 variables (el agente puede explorar exhaustivamente sin
   planificar) y muy pocos para un grafo de 15 variables (el agente no puede
   cubrir el espacio). **Mitigacion:** budget variable por complejidad del
   mundo, o al menos 2-3 tiers (small/medium/large).

3. **Filter expressiveness leakage.** Si `request_observation(filter=...)`
   permite filtros muy expresivos (ej: rangos arbitrarios, combinaciones
   complejas), el agente puede aproximar intervenciones sin gastar budget
   de intervencion — es un shortcut via API, reintroduce v1 via la
   backdoor del filtro. **Mitigacion:** limitar la expresividad de los
   filtros, o cobrar mas por filtros complejos.

4. **Need to evaluate averaged over replicas.** Dado (1), NUNCA evaluar
   un agente con un solo run por mundo. El resultado es ruido. Siempre
   promediar sobre N replicas del mismo episodio para obtener expected
   reward confiable.

---

## Backward compatibility con v1

v1 es un caso especial de v2:
- `experiment_budget = infinity` (o un numero muy alto)
- `initial_dataset_size = N_full` (toda la muestra)
- Solo `request_observation` disponible (sin intervene/counterfactual)

Esto significa:
- Los seeds v1 siguen funcionando en v2
- El harness v2 puede correr casos v1 sin cambios
- El scoring es identico

Para el training, se pueden mezclar episodios v1 y v2 en el mismo
batch — curriculum learning natural.

---

## Relacion con presiones evolutivas

El Sherlock-type investigation crea presion directa para las propiedades
mas dificiles de forzar:

| Propiedad (PROJECT.md) | Sin Sherlock | Con Sherlock |
|---|---|---|
| 1. Descomposicion de preguntas | Util pero opcional | **Necesaria** — hay que planificar que preguntar |
| 3. Workflow iterativo | No forzado (flat) | **Forzado** — plan cambia con cada dato nuevo |
| 4. Plan de investigacion | No necesario | **Critico** — budget limitado fuerza planificar |
| 5. Distinguir evidencia | Opcional | **Necesario** — observacional vs interventional |
| 12. Saber cuando parar | No forzado | **Forzado** — budget finito |
| 14. Diseño experimental | No existe | **Core** — que intervencion hacer |
| 15. Efficiency | No forzada | **Forzada** — budget escaso |

---

## Open questions (decisiones pendientes)

### D1: Efficiency en el scoring?
**Option C (indirecta via budget) confirmada.** `budget_spent` se reporta
como metrica diagnostica secundaria, pero NO forma parte del reward.
Necesita validacion empirica para confirmar que la presion indirecta
es suficiente.

### D2: Budget fijo o variable por mundo?
Budget fijo (10 para todos) es mas simple. Budget variable (mundos
complejos tienen mas) es mas realista pero agrega un hyperparametro.

### D3: Contrafactuales como tool del solver?
**Deferred to v2.1 (confirmed).** El do-operator es standard.
Contrafactuales (twin network) son mas exoticos y agregan complejidad
semantica prematura + riesgo de oracle leak. v2.0 solo incluye
observe + intervene. Counterfactual se agrega en v2.1 despues de validar
que las 2 tools basicas crean la presion esperada.

### D4: Dataset inicial — cuanto dar gratis?
N=100? N=50? N=0 (el agente tiene que pedir todo)? N=0 es mas
Sherlock pero puede ser frustrante. N=100 observacionales gratis es
razonable — alcanza para explorar correlaciones, no para concluir
causalidad.

### D5: Como se integra con SQ v2?
Las sub-questions siguen siendo la answer key. La diferencia es que
algunas SQs pueden ser "intervention-requiring" — el solver necesita
datos intervenidos para responderlas correctamente. No cambia el
scoring, solo la dificultad.

### D6: Training curriculum
Mezclar episodios v1 (flat) y v2 (interactive) en el training?
Ratio? Progression? SandMLE usó solo un tipo de entorno — nosotros
tenemos la oportunidad de hacer curriculum (empezar con flat, escalar
a interactive).

**Recomendacion (Codex review 2026-04-13):** short warmup phase con
episodios v1 (flat), luego transicion rapida a v2 como modo predominante.
El warmup permite que el agente aprenda analisis basico de datos y
claims sin la complejidad adicional del budget. Una vez estable, v2
debe ser la mayoria del training (80%+) para que la presion por diseño
experimental domine el aprendizaje.

### D7: Temporal extension — cuando y como?
SCMs temporales (v2.5) son el paso natural despues de v2. Pero:
- ¿Cuando incorporar? ¿Despues de validar v2 o en paralelo?
- Expression compiler: ¿extender con `var_t`, `var_{t-1}` o usar
  notacion distinta?
- Semantica de intervencion: pulse vs persistent vs ramp — ¿cual
  primero?
- Horizonte de observacion: ¿fijo o decidido por el agente?
- Scoring: ¿claims sobre trayectorias o sobre estados puntuales?
- Ground truth: ¿el verifier compara snapshot final o path completo?

**Prerequisito:** v2 Modelo 1 validado con piloto E2E.

---

## Series temporales y roadmap v1→v2→v3

### SCMs y temporalidad — que puede y que no puede nuestro engine

**Distincion clave:** los SCMs como formalismo **si** pueden representar
dinamica temporal. Una ecuacion estructural con lags es perfectamente
valida:

```
Y_t = β₁·X_{t-1} + β₂·Y_{t-1} + noise_t
```

El do-calculus de Pearl aplica igual: `do(X_t = x)` tiene semantica bien
definida. Dynamic Causal Models, Granger causal graphs, PCMCI — todos
trabajan con SCMs temporales. **La limitacion no es del formalismo, es de
nuestra implementacion.**

Nuestro engine hoy usa ecuaciones estaticas sin indice temporal:
`Y = f(parents) + noise`. Genera datos cross-sectional (N individuos,
una observacion cada uno). Es una tabla, no una serie temporal.

**SciGym** va mas alla de SCMs temporales: sus mundos son **ODEs** (SBML
models) con estado continuo y trayectorias. Eso es otro paradigma — no
solo SCMs con tiempo, sino ecuaciones diferenciales con integracion
numerica.

### Dos tipos de extension (no confundir)

Es critico distinguir entre:

1. **Time-indexed data (context shifts):** re-muestrear el SCM bajo
   condiciones distintas que representan "momentos". Los datos tienen un
   indice temporal, pero NO hay dependencia causal entre tiempos. No hay
   estado latente que evoluciona. El agente ve snapshots, no trayectorias.
   Es un SCM estatico ejecutado multiples veces.

2. **True temporal dynamics:** ecuaciones estructurales con lags. El
   estado en `t` causa el estado en `t+1`. Hay persistencia, inercia,
   efectos retardados. El agente puede intervenir en `t` y observar
   consecuencias en `t+1, t+2, ...`. Es un SCM genuinamente temporal.

Panel data y repeated cross-sections son tipo (1). Dynamic SCMs y ODEs
son tipo (2). La diferencia importa porque las habilidades que entrenan
son distintas: (1) entrena razonamiento bajo cambio de contexto, (2)
entrena planificacion temporal y diseño de trayectorias.

### Roadmap de extension

| Version | Que es | Engine | Scoring/API | Complejidad |
|---|---|---|---|---|
| **v2** (este doc) | SCM estatico interactivo. observe + intervene. Cross-sectional | Actual | Actual | — |
| **v2.x** | Context shifts temporales. Panel data, repeated cross-sections. Mismo SCM con parametros que varian por "momento" | Baja — loop externo sobre engine actual | **Media** — verdades indexadas por condicion, SQ v2 necesita entender "trend vs causal effect", leakage por estructura de panel | Engine facil, benchmark no trivial |
| **v2.5** | **Dynamic SCM discreto.** Ecuaciones con lags: `X_t → Y_{t+1}`. Trayectorias finitas. Intervenciones pulse vs persistent | **Media** — extender expression compiler para lags, sampler iterativo por timestep | **Alta** — semantica de intervencion temporal (cuando, cuanto dura), observacion de trayectorias, reward sobre paths | El salto real. Sigue siendo SCM |
| **v3** | ODEs / continuous-time simulator (SciGym-like). Estado continuo, integracion numerica | **Alta** — motor nuevo (scipy.integrate o similar) | **Alta** — continuous state/action, ruido numerico, nuevo paradigma de observacion | Otro paradigma |

### v2.5 — el paso natural que no requiere ODEs

El nivel v2.5 (Dynamic SCM discreto) es particularmente interesante
porque:

- **Mantiene el formalismo SCM.** Misma semantica de do-operator, misma
  verificacion contra ground truth. No cambia el paradigma de scoring.
- **Introduce temporalidad real.** Lags, persistencia, efectos que se
  propagan en el tiempo. El agente debe planificar CUANDO intervenir,
  no solo QUE intervenir.
- **Abre nuevos tipos de investigacion.** Causalidad temporal, efectos
  retardados, feedback loops, inercia. Cosas que un SCM estatico no
  puede representar.
- **Nuevas decisiones de diseño experimental.** Intervenciones pulse
  (una vez) vs persistent (sostenida). Horizonte de observacion (cuantos
  timesteps esperar). Start time (cuando intervenir).
- **No necesita integracion numerica.** Pasos discretos, algebraicos.
  El expression compiler actual se extiende naturalmente con `var_t`
  y `var_{t-1}`.

Ejemplo de mundo v2.5:
```
# Politica educativa con efecto retardado
funding_t     = base_funding + policy_shock_t + noise
teacher_quality_{t+1} = 0.7·teacher_quality_t + 0.3·funding_t + noise
test_scores_{t+2}     = 0.5·teacher_quality_{t+1} + 0.3·funding_t + noise
```
El agente que interviene `do(funding_t=high)` y solo mide en `t+1` ve
poco efecto. El que planifica medir en `t+2` descubre el path completo.
**Eso es diseño experimental temporal** — y emerge naturalmente del SCM.

### Implicacion para el training — curriculum natural

La progresion v1→v3 es un curriculum donde cada nivel es prerequisito
del siguiente:

1. **v1:** analisis de datos estaticos (ya implementado). Aprender a
   hacer claims correctas sobre datos tabulares.
2. **v2:** diseño experimental sobre SCM estatico (este doc). Aprender
   a planificar, gestionar budget, decidir cuando parar.
3. **v2.x:** mismos skills + razonamiento bajo cambio de contexto.
   Entender que parametros cambian entre condiciones.
4. **v2.5:** planificacion temporal. Decidir cuando intervenir, cuanto
   esperar, que horizonte observar. Dynamic SCMs discretos.
5. **v3:** dinámica continua, integracion numerica, trayectorias.
   Solo tiene sentido si v2.5 ya funciona.

**No saltar a ODEs (v3) sin validar v2.5 primero.** V3 mezcla demasiadas
fuentes de dificultad (dinamica temporal + continuous state + ruido
numerico + nueva semantica de observacion). Si el agente falla en v3,
no sabemos si es porque no aprendio diseño experimental o porque no
puede manejar el simulador. V2→v2.5 aisla cada skill.

---

## Path de implementacion sugerido

1. **Research:** este documento + consulta con Codex
2. **Prototype:** 1 mundo toy con 3 variables, budget=5, observe+intervene
   solo. Validar que el SCM engine produce datos correctos bajo do().
3. **Agent integration:** tools nuevas en `src/sreg/agent/`, conectar
   con OIEpisodeRunner.
4. **Piloto:** 3 mundos diversos (confounding, mediacion, heterogeneidad)
   con el modelo reference. Ver si usa las tools y si mejora score.
5. **Training:** agregar episodios v2 al dataset de RL.
6. **Scaling:** Modelo 2 (progressive revelation) si Modelo 1 funciona.

---

## Codex review (2026-04-13)

Este documento fue revisado por Codex (OpenAI) como segunda opinion
tecnica. Cambios principales incorporados:

1. **Tool set reducido a 2 para v2.0.** `request_counterfactual` deferred
   a v2.1 por complejidad semantica prematura y riesgo de oracle leak.
2. **Cost must scale with n.** Gap critico: si n es libre y el costo es
   flat, el agente pide samples enormes sin penalizacion. Agregado modelo
   de costo escalado.
3. **WorldSummary leakage warning.** Metadata rico gratis reintroduce
   shortcuts de v1. Necesita decision sobre que es gratis vs ganado.
4. **D1 scoring: Option C confirmada.** `budget_spent` como metrica
   diagnostica secundaria, fuera del reward.
5. **SQ v2 debe incluir targets intervention-requiring.** No solo los
   mundos — las preguntas mismas deben requerir intervencion.
6. **Riesgos identificados:** varianza estadistica con budgets chicos,
   budget/complexity mismatch, filter expressiveness leakage, necesidad
   de evaluar promediando sobre replicas.
7. **D3 confirmado deferred a v2.1.** D6: warmup con v1, luego v2
   predominante.

### Codex review #2 — temporal extension (2026-04-13)

Seccion de series temporales revisada. Cambios incorporados:

8. **Distincion "time-indexed data" vs "true temporal dynamics".**
   Panel data y repeated cross-sections son context shifts (tipo 1),
   no dinamica temporal real (tipo 2). Aclarado para no sobreprometer.
9. **Nivel intermedio v2.5: Dynamic SCM discreto.** Ecuaciones con lags
   (`X_t → Y_{t+1}`), trayectorias finitas, intervenciones pulse vs
   persistent. Llena el hueco entre v2.x y v3 sin necesitar ODEs.
10. **Complejidad de panel data corregida.** "Baja en engine, media en
    scoring/API/truth semantics" — verdades indexadas por condicion,
    leakage por estructura de panel, SQ v2 necesita entender trends.
11. **SCMs SI pueden ser temporales.** La limitacion es de nuestra
    implementacion (ecuaciones estaticas), no del formalismo. Corregido
    el framing del roadmap.

---

## Referencias

- `research/synthesis/related_work_scigym.md` — SciGym analisis completo
- `research/synthesis/open_investigation_vision.md` — vision de OI
- `PROJECT.md` Horizonte 2 — donde encaja en el roadmap
- GitHub Issue #16 — issue de tracking
- SciGym paper: Duan et al. 2025, `github.com/h4duan/SciGym`
- Pearl's causal hierarchy: observational < interventional < counterfactual
