# SREG — Current State

> Qué hace el sistema hoy, cómo funciona cada parte, y cómo ejecutarlo.
> Actualizado: 2026-03-09

---

## Qué es SREG en una oración

SREG genera **problemas de investigación ficticios** donde la verdad oculta es una
red bayesiana. Un agente LLM intenta resolverlos, y el sistema evalúa automáticamente
qué tan bien razonó — sin necesidad de un humano que corrija.

**Estado actual: 552 tests. 4 familias de templates (3 curadas + custom). 4 DAG generators. 3 nuevos tools de orchestrator (dag_generate + dag_construct + design_case). 9 tipos de tarea (infer_target, NBO, hypothesis_selection, causal_effect, best_intervention, adjustment_set, compare_interventions, should_condition, infer_latent_cause). CasePlan (orchestrator diseña research cases). Multi-task bundles. QualitySuite v2 (capas A+B+C, multi-rollout + entropy reduction). Dataset-rich evidence (multi-dataset, missing data, narratives). Pipeline completo. v1 completo + v2 en progreso. Ola 1 de eval types COMPLETA.**

---

## Cómo funciona — el flujo completo

```
1. GENERAR EL MUNDO
   Le pedís al sistema un problema (o le das parámetros).
   El sistema construye una red bayesiana: variables, relaciones causales,
   y tablas de probabilidad. Todo con matemática exacta.

2. VESTIRLO CON SEMÁNTICA
   Un LLM le pone nombres reales a las variables ("water_temperature" en vez
   de "indicator_1"), inventa una narrativa ("Declive de algas en Nelvara"),
   y genera datos tabulares muestreando de la red bayesiana.

3. PRESENTAR AL AGENTE
   El agente recibe el problema como lo recibiría un investigador:
   contexto, datos, acciones posibles (cada una tiene un costo), y una pregunta.
   El agente NO ve la red bayesiana — solo ve el "paper".

4. EL AGENTE INVESTIGA
   El agente puede analizar los datos (gratis), razonar (gratis), pero si quiere
   hacer un "experimento" (observar una variable), le cuesta budget. Tiene que
   decidir qué medir y cuándo parar.

5. EVALUAR
   El sistema compara la respuesta del agente contra la verdad matemática
   de la red bayesiana. No hay ambigüedad: la respuesta correcta se calcula
   con exactitud.
```

---

## Las dos capas

### Capa formal (oculta — la verdad)

Una red bayesiana con:
- **Nodos**: variables del mundo. Algunas son **latentes** (el agente no las puede
  ver directamente), algunas son **observables** (el agente puede pagar para verlas),
  y una es el **target** (lo que tiene que descubrir).
- **Flechas**: relaciones causales. "La temperatura afecta la producción de algas."
- **Tablas de probabilidad (CPDs)**: cuánto influye cada padre en cada hijo.
  Controladas por `edge_strength`: 0.1 = casi no influye, 0.9 = influye mucho.

### Capa semántica (visible — lo que ve el agente)

- Nombres realistas: `coral_bleaching_severity` en vez de `target_outcome`
- Narrativa: "Investigadores del Instituto Oceánico reportaron..."
- Datos: tabla con 100 filas de mediciones (muestreadas de la red bayesiana)
- Acciones: "Solicitar análisis de sedimentos (costo: 2)"

La misma red bayesiana puede vestirse con distintas semánticas.

---

## Templates — las formas del mundo

Un template define **qué forma tiene la red bayesiana** y **cómo se generan las
probabilidades**. Cada forma testea un tipo de razonamiento diferente.

### `latent_preference` — La estrella

```
         hidden_cause (LATENT)
        ↙    ↓    ↓    ↘
  ind_1   ind_2  ind_3  ind_4   (OBSERVABLE)
                  ↓
           target_outcome       (TARGET)
```

**Qué es:** Una causa oculta que afecta a varios indicadores observables y al target.

**Qué testea:** Diagnóstico. Es como un médico: ves síntomas (indicadores) y tenés
que inferir la enfermedad oculta para predecir el resultado. Cuantos más síntomas
observás, mejor podés inferir la causa y predecir el target.

**Ejemplo real:** Hay un compuesto oculto en el suelo. Afecta el pH, la temperatura,
el nitrógeno, y la producción de algas. Si observás pH=alto y nitrógeno=bajo, ¿qué
le pasa a la producción?

**Dificultad:** La más fácil. El teacher acierte ~100%. Todos los indicadores ayudan.

### `causal_chain` — La cadena

```
  root → stage_1 → stage_2 → stage_3 → stage_4 → target
```

**Qué es:** Una cadena lineal donde la info se propaga de nodo en nodo.

**Qué testea:** Propagación. Los nodos más cercanos al target son más informativos
que los lejanos. Si observás `stage_4` (pegado al target), sabés mucho. Si observás
`stage_1` (lejos), sabés poco — la info se "diluye" en el camino.

**Ejemplo real:** Una cadena de producción industrial. La materia prima afecta el
proceso 1, que afecta el proceso 2, que afecta la calidad final. Medir la calidad
del proceso 2 te dice más sobre el resultado que medir la materia prima.

**Dificultad:** Media. El teacher acierta ~95%. El agente tiene que entender que
la distancia importa.

### `fork_collider` — El más tramposo

```
    hidden_factor (LATENT)
      ↙          ↘
  branch_1(O)  branch_2(O)  [branch_3(O)]
      ↘          ↙
      collider(O)           ← acá está la trampa
          ↓
     [mediator(O)]
          ↓
     target_outcome(T)
```

**Qué es:** Combina dos patrones de razonamiento:

1. **Fork (arriba):** Una causa oculta afecta a varias ramas. Las ramas están
   correlacionadas AUNQUE no se causen entre sí (porque comparten la causa).

2. **Collider (medio):** Las ramas confluyen en el collider. Acá pasa algo
   contraintuitivo: si observás el collider, las ramas que antes eran
   independientes se VUELVEN dependientes. Esto se llama "explaining away"
   o paradoja de Berkson.

**Qué testea:** Razonamiento causal avanzado. El agente tiene que entender que
observar el collider cambia la relación entre las ramas. No alcanza con
"observar todo" — hay que entender la estructura.

**Ejemplo real:** Dos factores independientes (genética y dieta) ambos causan
una enfermedad. Si sabés que alguien tiene la enfermedad (observás el collider),
y descubrís que NO tiene predisposición genética, entonces es MÁS probable que
sea por la dieta. Observar el efecto cambia cómo interpretás las causas.

**Dificultad:** La más difícil. El teacher acierta ~85%. Requiere razonamiento
causal, no solo estadístico.

### Parámetros que controlan la dificultad

| Parámetro | Qué hace | Rango |
|---|---|---|
| `num_nodes` | Más nodos = más variables = más complejo | 3-20 |
| `num_states` | Más estados por variable (low/med/high vs 5 niveles) | 2-5 |
| `edge_strength` | Qué tan fuerte es la influencia entre variables | 0.1-1.0 |
| `seed` | Semilla para reproducibilidad | cualquier int |

---

## Task types — las preguntas que hacemos

Cada mundo puede generar distintos tipos de preguntas. Hoy hay 5:

### `infer_target` — "¿Cuál es la respuesta?"

**La pregunta:** "Dada la evidencia, ¿cuál es la distribución de probabilidad
del target?"

**Cómo funciona:**
1. El agente recibe datos + acciones disponibles
2. Elige qué observar (cada observación cuesta budget)
3. Al final, manda su estimación: `{low: 0.1, medium: 0.3, high: 0.6}`
4. Se compara con la posterior verdadera usando KL divergence (menor = mejor)

**Ejemplo:** "¿Cuál es la probabilidad de que la producción de algas sea baja,
media, o alta? Observá lo que necesites (tenés budget=4) y mandá tu estimación."

**Scoring:** KL divergence. 0.0 = perfecto. >2.0 = peor que random.

### `next_best_observation` — "¿Qué conviene medir?"

**La pregunta:** "Ya tenés esta evidencia. Si pudieras hacer UNA medición más,
¿cuál sería la más informativa?"

**Cómo funciona:**
1. El agente recibe evidencia parcial (ya se observaron algunos nodos)
2. Tiene que elegir qué nodo medir de los que quedan
3. Se compara su elección con la del teacher (que elige por information gain)

**Ejemplo:** "Ya sabés que temperature=high y pH=low. Podés medir: nitrogen,
luminosity, o sediment_compound. ¿Cuál medirías?"

**Scoring:** Ratio de IG. Si tu elección tiene IG=0.3 y la óptima tiene IG=0.5,
tu score es 0.6. Score=1.0 significa que elegiste la mejor opción.

**Por qué es interesante:** Testea una habilidad diferente. No es "¿sabés la
respuesta?" sino "¿sabés cómo buscar la respuesta eficientemente?".

### `hypothesis_selection` — "¿Cuál de estas explicaciones es la correcta?"

**La pregunta:** "Dada la evidencia, ¿cuál de estas 4 hipótesis explica mejor
los datos?"

**Cómo funciona:**
1. El agente recibe evidencia parcial
2. Se le presentan 4 hipótesis (distribuciones sobre el target):
   - Una es la posterior verdadera (la correcta)
   - Las otras son distractores: el prior (sin evidencia), uniforme, y reversed
3. Tiene que elegir la más plausible

**Ejemplo:**
```
Ya observaste: temperature=high, pH=low.
¿Cuál hipótesis es más plausible?

  A: low=0.70, medium=0.20, high=0.10
  B: low=0.33, medium=0.33, high=0.34
  C: low=0.10, medium=0.20, high=0.70
  D: low=0.05, medium=0.25, high=0.70

Elegí A, B, C, o D.
```

**Scoring:** Accuracy. 1.0 = eligió la correcta. 0.0 = eligió otra.

**Por qué es interesante:** Es cómo funciona la investigación real. No te piden
calcular P(X=0.73) — te piden comparar teorías y elegir la que mejor explica
los datos.

### `causal_effect` — "¿Qué pasa si intervengo?"

**La pregunta:** "Si forzamos la variable X al valor v (intervención, do-calculus),
¿cuál es la distribución de probabilidad del target?"

**Cómo funciona:**
1. El sistema encuentra nodos con efecto causal real sobre el target
2. Elige un nodo y un estado para la intervención (ponderado: efectos más fuertes = más probable)
3. Calcula P(target | do(nodo=estado)) usando do-calculus exacto
4. El agente tiene que estimar esa distribución interventional

**Ejemplo:** "Si forzamos `soil_treatment` a `high`, ¿cuál es la distribución
de probabilidad de `crop_yield`? OJO: esto es una intervención (do), no una
observación. La diferencia importa."

**Scoring:** KL divergence. 0.0 = perfecto.

**Por qué es interesante:** Testea razonamiento causal, no solo estadístico.
`P(Y | do(X=x))` != `P(Y | X=x)` cuando hay confounders. El agente tiene que
entender la diferencia entre ver que algo pasa (observar) y hacer que pase (intervenir).

### `best_intervention` — "¿Qué tratamiento conviene?"

**La pregunta:** "Querés maximizar la probabilidad de que el target sea [estado_deseado].
Podés intervenir en UNA variable. ¿Cuál elegís y a qué valor la ponés?"

**Cómo funciona:**
1. Se elige un estado deseado del target (ej: "high")
2. Para cada variable observable, para cada estado posible, se calcula
   P(target=deseado | do(variable=estado))
3. La intervención óptima es la que maximiza esa probabilidad
4. El agente tiene que elegir la mejor intervención

**Ejemplo:** "Querés maximizar la probabilidad de que `crop_yield` sea `high`.
Podés intervenir en una variable: `soil_treatment`, `irrigation`, `fertilizer`.
¿Qué variable pondrías en qué valor?"

**Scoring:** Ratio de efecto. Si tu intervención logra P=0.6 y la óptima logra
P=0.9, tu score es 0.67. Score=1.0 = elegiste la mejor intervención.

**Por qué es interesante:** Es la pregunta de decisión por excelencia.
No es "¿qué pasa si intervengo?" (causal_effect) sino "¿qué intervención
me conviene?". Es lo que hace un médico al elegir tratamiento.

### `adjustment_set` — "¿Qué variables debo controlar?"

**La pregunta:** "Querés estimar el efecto causal de X sobre Y usando datos
observacionales. ¿Qué variables deberías controlar (incluir como covariables)
en tu análisis?"

**Cómo funciona:**
1. Se busca un par (treatment, target) donde exista confounding
2. Se computan todos los adjustment sets válidos via `get_all_backdoor_adjustment_sets`
3. Se filtran a sets que solo usen variables observables
4. El agente tiene que proponer el minimal set correcto

**Tres escenarios posibles:**
- **Confounded + identifiable**: Hay confounders observables → el agente debe encontrar
  el minimal adjustment set (ej: fork_collider, custom worlds)
- **No confounding**: No hay backdoor paths → la respuesta correcta es el conjunto vacío
  (ej: causal_chain)
- **Not identifiable**: El confounder es latente → no se puede identificar via backdoor
  criterion. El agente debe reconocer que el efecto no es identificable
  (ej: latent_preference con hidden_cause)

**Ejemplo:** "Querés estimar el efecto causal de `treatment_X` sobre `outcome_Y`.
Variables disponibles: `confounder_Z`, `mediator_M`, `collider_C`.
¿Qué variables deberías controlar?" → Respuesta: `{confounder_Z}`.
Controlar por el collider sería INCORRECTO (abre un nuevo path).

**Scoring:** Binario. 1.0 si el set propuesto es un valid minimal backdoor
adjustment set, 0.0 si no.

**Por qué es interesante:** Es LA pregunta central de McElreath
(Statistical Rethinking). Testea si el agente entiende la estructura causal
lo suficiente para saber qué controlar y qué NO controlar.

### `should_condition` — "¿Debería controlar por esta variable?"

**La pregunta:** "Estás analizando el efecto causal de X sobre Y con datos
observacionales. Un colega sugiere controlar por Z. ¿Es buena idea?"

**Cómo funciona:**
1. Para cada par (treatment, target), se computan los adjustment sets válidos
   via `get_all_backdoor_adjustment_sets`
2. Se clasifican las variables sugeridas:
   - **Should condition**: Z aparece en un adjustment set válido (es un confounder)
   - **Should NOT condition**: Z es descendiente del treatment en el DAG
     (mediator o descendiente de collider — condicionarlo introduce sesgo)
3. Se aleatoriza si la pregunta será "yes" o "no" (cuando hay ambos tipos)

**Tres patrones causales que testea:**
- **Confounder (fork)**: X ← Z → Y — SI, controlar por Z bloquea el backdoor path
- **Mediator (pipe)**: X → Z → Y — NO, controlar bloquea el efecto causal
- **Collider descendant**: X → C ← Y, Z descendiente de C — NO, abre path espurio

**Scoring:** Binario. 1.0 si la respuesta (yes/no) coincide, 0.0 si no.

**Por qué es interesante:** Es la pregunta más práctica de McElreath.
En cualquier análisis observacional, alguien sugiere "controlá por esto".
Saber cuándo SÍ y cuándo NO es la esencia del razonamiento causal.

### `compare_interventions` — "¿Cuál de estas dos intervenciones es mejor?"

**La pregunta:** "Tu equipo debate entre dos intervenciones posibles para
maximizar un outcome. Intervención A: fijar X en x. Intervención B: fijar
Z en z. ¿Cuál tiene mayor efecto causal?"

**Cómo funciona:**
1. Se elige un estado deseado para el target (aleatorio por seed)
2. Se computan los efectos causales de todas las intervenciones posibles
   via `causal_query(target, do={node: state})`
3. Se eligen dos intervenciones de nodos DIFERENTES con efectos distintos
   (la mejor y la peor entre los mejores de cada nodo)
4. Se aleatoriza el orden de presentación (A/B) para evitar sesgo posicional

**Ejemplo:** "Intervención A: fijar `stage_4` en `medium`. Intervención B:
fijar `stage_1` en `high`. ¿Cuál cambia más la probabilidad de
`target_outcome` = `high`?" → A tiene efecto 0.87, B tiene 0.59 → Respuesta: A.

**Scoring:** Binario. 1.0 si eligió la intervención con mayor efecto, 0.0 si no.
Si ambas tienen el mismo efecto, cualquier respuesta es correcta.

**Por qué es interesante:** Es la pregunta de decisión clínica o de política.
No es "¿cuál es la mejor?" (best_intervention, muchas opciones) sino "dados
estos dos tratamientos concretos, ¿cuál preferís?". Requiere razonamiento
causal comparativo, no búsqueda exhaustiva.

### `infer_latent_cause` — "¿Cuál es la causa oculta?"

**La pregunta:** "Dados estos síntomas observados, estimá la distribución de
probabilidad sobre los estados posibles de la variable oculta."

**Cómo funciona:**
1. Se elige una variable latente del mundo
2. Se samplea un estado verdadero y se da evidencia parcial (1 a N-2 observaciones)
3. Se computa la posterior exacta P(latente | evidencia) via inferencia bayesiana
4. El agente debe estimar esa posterior

**Ejemplo:** Mundo con `hidden_cause` (latente) → 6 indicators → target.
Se observa que `indicator_1 = high`, `indicator_4 = medium`.
Posterior: P(hidden_cause | evidence) = {low: 0.05, medium: 0.02, high: 0.93}.
El agente debe llegar a una distribución similar.

**Scoring:** KL divergence (mismo que infer_target). 0.0 = perfecto.

**Por qué es interesante:** Es la pregunta de diagnóstico por excelencia.
Un médico ve síntomas e infiere la enfermedad. Un ingeniero ve fallos e
infiere la causa raíz. Es como infer_target pero al revés — de efectos
observados a causas ocultas.

### Diferencias clave entre los 9 task types

| | infer_target | NBO | hypothesis_sel | causal_effect | best_intervention | adjustment_set | compare_interv | should_condition | infer_latent |
|---|---|---|---|---|---|---|---|---|---|
| **Qué mide** | Estimación | Estrategia | Comparación | Razonamiento causal | Decisión óptima | Comprensión causal | Comparación causal | Confound awareness | Diagnóstico |
| **Output** | Distribución | Un nodo | Una letra (A-D) | Distribución interventional | Nodo + estado | Set de variables | A o B | yes/no | Distribución |
| **Scoring** | KL (continuo) | IG ratio (continuo) | Accuracy (binario) | KL (continuo) | Effect ratio (continuo) | Match (binario) | Match (binario) | Match (binario) | KL (continuo) |
| **Interactúa?** | Sí | No | No | No | No | No | No | No | No |

---

## Cómo ejecutar

### Setup
```bash
conda create -n sreg python=3.11 -y
conda activate sreg
pip install -e ".[dev]"
```

### Correr tests
```bash
pytest tests/ -v                          # Todos (511 tests)
pytest tests/tools/test_task_gen.py -v    # Solo task generation
pytest tests/tools/test_fork_collider.py  # Solo fork_collider template
```

### Generar un mundo y verlo
```python
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool

world = WorldGenTool().generate(WorldGenConfig(
    template_family="fork_collider",  # o "latent_preference" o "causal_chain"
    seed=42,
    num_nodes=7,
    edge_strength=0.7,
))

print(f"Nodes: {[n.name for n in world.nodes]}")
print(f"Edges: {[(e.from_node, e.to_node) for e in world.edges]}")
```

### Generar los 3 tipos de tarea para un mundo

**Opción 1: Todos juntos (recomendado)**
```python
from sreg.tools.task_gen import TaskGenTool

bundle = TaskGenTool().generate_all(world, target_node="target_outcome", max_budget=4, seed=42)

# Acceder a cada tarea
bundle.infer_target          # → Task (KL divergence)
bundle.next_best_observation # → Task (IG ratio)
bundle.hypothesis_selection  # → Task (accuracy)

# Todos comparten el mismo world_id
assert bundle.infer_target.world_id == bundle.hypothesis_selection.world_id
```

**Opción 2: Uno a uno**
```python
from sreg.tools.task_gen import TaskGenTool
from sreg.models.task import TaskSpec, TaskType

tool = TaskGenTool()

# Tarea 1: inferir el target
task = tool.generate(world, TaskSpec(
    type=TaskType.INFER_TARGET, target_node="target_outcome", max_budget=4
))

# Tarea 2: mejor próxima observación
task = tool.generate(world, TaskSpec(
    type=TaskType.NEXT_BEST_OBSERVATION, target_node="target_outcome", max_budget=4
), seed=42)

# Tarea 3: selección de hipótesis
task = tool.generate(world, TaskSpec(
    type=TaskType.HYPOTHESIS_SELECTION, target_node="target_outcome", max_budget=4
), seed=42)
```

### Correr el teacher (solver bayesiano exacto)
```python
from sreg.solver.exact_bayes import ExactBayesSolver

solver = ExactBayesSolver(world)

# Samplear un estado del mundo
true_state = solver.sample_state(seed=42)

# Calcular posterior dado evidencia
posterior = solver.posterior("target_outcome", {"branch_1": "low"})

# Cuál es la mejor variable para observar
out = solver.optimal_action("target_outcome", evidence={}, available=["branch_1", "branch_2"])
print(f"Observar: {out.recommended_action.node}, IG: {out.information_gain:.4f}")
```

### Batch evaluation (N problemas, agente vs teacher)
```bash
# Evaluar 10 problemas con fork_collider
python scripts/batch_eval.py --template fork_collider --problems 10 --nodes 7

# Exportar trayectorias del teacher como JSONL
python scripts/batch_eval.py --export-trajectories output.jsonl --problems 20
```

### Pipeline completo (con LLM)
```bash
# Necesita: AZURE_INFERENCE_CREDENTIAL, AZURE_FOUNDRY_BASE_URL en .env

# Orchestrator genera mundo con semántica, agent lo resuelve
python scripts/test_e2e.py

# Agent vs teacher vs random en un mundo
python scripts/test_agent.py
```

---

## Modules — qué hace cada parte

| Módulo | Ubicación | Qué hace |
|--------|----------|----------|
| **Models** | `src/sreg/models/` | Contratos de datos (Pydantic): World, Episode, Task, Score, ResearchProblem, DAGSpec, CasePlan |
| **DAGSpec** | `src/sreg/models/dag_spec.py` | Contrato universal para DAGs arbitrarios (validaciones: acíclico, max parents, tipos) |
| **CPD gen** | `src/sreg/world/cpd_gen.py` | Generación genérica de CPDs (extraída de templates, soporta estados heterogéneos) |
| **Templates** | `src/sreg/world/templates/` | 4 generadores: latent_preference, causal_chain, fork_collider + **custom** (DAGSpec) |
| **DAG generators** | `src/sreg/world/dag_generators.py` | 4 generadores de DAGs: Erdos-Renyi, spanning tree, preferential attachment, layered |
| **World check** | `src/sreg/tools/world_check.py` | Valida mundos: DAG acíclico, entropía, d-separaciones, max parents, treewidth |
| **Teacher solver** | `src/sreg/solver/exact_bayes.py` | Inferencia bayesiana exacta: posteriors, information gain, acciones óptimas |
| **Episode gen** | `src/sreg/tools/episode_gen.py` | Crea episodios: budget, nodos disponibles, costos por observación |
| **Task gen** | `src/sreg/tools/task_gen.py` | Genera los 6 tipos de tarea con su respuesta correcta + `generate_from_plan` (plan-driven) |
| **Verifier** | `src/sreg/tools/verifier.py` | Puntúa al agente: KL divergence, IG ratio, hypothesis accuracy |
| **Episode runner** | `src/sreg/env/` | Interfaz paso a paso: el agente observa → el runner responde |
| **Semantic tools** | `src/sreg/tools/problem_builder.py` | Renombra nodos, genera narrativa, empaqueta como ResearchProblem |
| **Data sampler** | `src/sreg/tools/data_sampler.py` | Samplea datos de la BN: multi-dataset (primary+secondary), missing data, narrativas |
| **Orchestrator** | `src/sreg/orchestrator/` | Loop LLM con function calling (genera mundos con semántica + diseña research cases via design_case) |
| **Agent solver** | `src/sreg/agent/` | Agente LLM que recibe un problema y lo resuelve observando/enviando |
| **Batch eval** | `src/sreg/harness/eval.py` | Evalúa N problemas: agente vs teacher vs random, métricas agregadas |
| **QualitySuite** | `src/sreg/harness/quality.py` | Suite de evaluación en 3 capas: world quality, task quality, generator diversity |
| **Trajectory export** | `src/sreg/harness/trajectory.py` | Exporta trayectorias del teacher como JSONL |
| **Display** | `src/sreg/display.py` | Pretty printing para terminal y notebooks |

---

## Key APIs — referencia rápida

### Generar mundos
```python
config = WorldGenConfig(template_family="fork_collider", seed=42, num_nodes=7, edge_strength=0.7)
world = WorldGenTool().generate(config)  # → World
```

### Teacher solver
```python
solver = ExactBayesSolver(world)
state = solver.sample_state(seed=42)                      # → dict[str, str]
post = solver.posterior("target_outcome", evidence)        # → dict[str, float]
ig = solver.information_gain("target", evidence, node)     # → float
out = solver.optimal_action("target", evidence, nodes)     # → TeacherOutput
do_dist = solver.causal_query("target", do={"node": "val"})  # → dict[str, float] (do-calculus)
# out.recommended_action.node → str, out.information_gain → float
```

### Generar tareas
```python
# Todos juntos (TaskBundle)
bundle = TaskGenTool().generate_all(world, seed=42)
# bundle.infer_target, bundle.next_best_observation, bundle.hypothesis_selection

# O uno a uno:
# infer_target
spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="target_outcome", max_budget=5)
task = TaskGenTool().generate(world, spec)
# task.correct_answer → {"low": 0.7, "medium": 0.2, "high": 0.1}  (prior distribution)

# next_best_observation
spec = TaskSpec(type=TaskType.NEXT_BEST_OBSERVATION, target_node="target_outcome", max_budget=5)
task = TaskGenTool().generate(world, spec, seed=42)
# task.given_evidence → {"branch_1": "low", "collider": "high"}
# task.correct_answer → {"branch_2": 0.42, "mediator_1": 0.15}  (IG ranking)

# hypothesis_selection
spec = TaskSpec(type=TaskType.HYPOTHESIS_SELECTION, target_node="target_outcome", max_budget=5)
task = TaskGenTool().generate(world, spec, seed=42)
# task.hypotheses → {"A": {"low": 0.7, ...}, "B": {...}, "C": {...}, "D": {...}}
# task.correct_answer → {"A": 0.0, "B": 1.5, "C": 0.8, "D": 2.0}  (KL from true)

# causal_effect
spec = TaskSpec(type=TaskType.CAUSAL_EFFECT, target_node="target_outcome", max_budget=5)
task = TaskGenTool().generate(world, spec, seed=42)
# task.intervention → {"indicator_4": "low"}  (the do() operation)
# task.correct_answer → {"low": 0.6, "medium": 0.3, "high": 0.1}  (P(target | do()))

# best_intervention
spec = TaskSpec(type=TaskType.BEST_INTERVENTION, target_node="target_outcome", max_budget=5)
task = TaskGenTool().generate(world, spec, seed=42)
# task.intervention → {"stage_4": "high"}  (optimal intervention)
# task.correct_answer → {"stage_4:high": 0.95, "stage_4:low": 0.05, ...}  (all effects)

# adjustment_set
spec = TaskSpec(type=TaskType.ADJUSTMENT_SET, target_node="outcome_Y", max_budget=5)
task = TaskGenTool().generate(world, spec, seed=42)
# task.intervention → {"treatment_X": "treatment"}  (treatment variable)
# task.correct_answer → {"confounder_Z": 1.0}  (valid minimal adjustment sets)
# Or: {"_empty_": 1.0} (no confounding) or {"_not_identifiable_": 1.0} (latent confounder)

# compare_interventions
spec = TaskSpec(type=TaskType.COMPARE_INTERVENTIONS, target_node="target_outcome", max_budget=5)
task = TaskGenTool().generate(world, spec, seed=42)
# task.intervention → {"mediator_1": "high"}  (the better intervention)
# task.correct_answer → {"branch_1:medium": 0.46, "mediator_1:high": 0.78}  (effects of both)

# should_condition
spec = TaskSpec(type=TaskType.SHOULD_CONDITION, target_node="target_outcome", max_budget=5)
task = TaskGenTool().generate(world, spec, seed=42)
# task.intervention → {"branch_1": "branch_2"}  ({treatment: suggested_control_var})
# task.correct_answer → {"yes": 1.0} or {"no": 1.0}

# infer_latent_cause
spec = TaskSpec(type=TaskType.INFER_LATENT_CAUSE, target_node="target_outcome", max_budget=5)
task = TaskGenTool().generate(world, spec, seed=42)
# task.target_node → "hidden_cause"  (the latent variable, NOT the world target)
# task.given_evidence → {"indicator_1": "high", "indicator_4": "medium"}
# task.correct_answer → {"low": 0.05, "medium": 0.02, "high": 0.93}  (posterior)
```

### Scoring
```python
verifier = VerifierTool()

# infer_target: KL divergence
score = verifier.score(agent_posterior, true_posterior)  # → Score
# score.functional_score → float (0.0 = perfecto)

# next_best_observation: IG ratio
ratio = verifier.score_nbo("branch_2", ig_ranking)  # → float (0.0 to 1.0)

# hypothesis_selection: accuracy
acc = verifier.score_hypothesis("B", kl_scores)  # → 1.0 or 0.0

# adjustment_set: match against valid sets
match = verifier.score_adjustment_set(["confounder_Z"], valid_sets)  # → 1.0 or 0.0

# compare_interventions: binary comparison
score = verifier.score_compare_interventions("A", effects)  # → 1.0 or 0.0

# should_condition: yes/no match
score = verifier.score_should_condition("yes", {"yes": 1.0})  # → 1.0 or 0.0
```

### Plan-driven task generation (CasePlan)
```python
from sreg.models.case_plan import CasePlan, EvalQuestionPlan
from sreg.models.task import TaskType
from sreg.tools.task_gen import TaskGenTool

plan = CasePlan(
    title="Alien Agriculture Study",
    research_context="A team analyzing crop growth on a newly colonized planet.",
    questions=[
        EvalQuestionPlan(
            question_text="What is the expected crop yield level?",
            eval_type=TaskType.INFER_TARGET,
            target_node="crop_yield",
        ),
        EvalQuestionPlan(
            question_text="What soil measurement would most improve our prediction?",
            eval_type=TaskType.NEXT_BEST_OBSERVATION,
            target_node="crop_yield",
        ),
    ],
    shared_budget=5,
)

tasks = TaskGenTool().generate_from_plan(world, plan, seed=42)
# tasks[0].question → "What is the expected crop yield level?"
# tasks[1].question → "What soil measurement would most improve our prediction?"
```

### Problem builder + episode
```python
problem = ProblemBuilder().build(world, budget=4)  # legacy: all cost=1
problem = ProblemBuilder().build(world, budget=4, rich_data=True)  # multi-dataset
problem = ProblemBuilder().build(world, budget=8, rich_actions=True)  # varied costs + compound actions
# problem.available_actions -> list[AvailableAction]
#   .action_type (ResearchActionType: observe/intervene/request_dataset/consult)
#   .nodes (list[str]), .node (str, backward-compat = nodes[0])
#   .description (str), .cost (int, >= 1)

episode = EpisodeGenTool().generate(world, EpisodeGenConfig(budget=4))  # legacy
episode = EpisodeGenTool().generate(  # rich: ActionDefs from AvailableActions
    world, EpisodeGenConfig(budget=8), available_actions=problem.available_actions
)
# episode.action_defs -> list[ActionDef] (id, action_type, nodes, cost)
# episode.available_nodes, episode.node_costs (backward-compat)

# Teacher with IG/cost optimization:
solver.optimal_action(target, evidence, available, costs=node_costs)
solver.generate_trajectory(target, available, budget, costs=node_costs)
```

---

## Test coverage

- **578 tests** en todos los modulos
- Tests espejean la estructura de src: `src/sreg/tools/X.py` -> `tests/tools/test_X.py`
- Validaciones clave:
  - 100 mundos validados por template (todos pasan)
  - Teacher >90% accuracy en latent_preference, >70% en chain, >60% en fork_collider
  - Nodos mas cercanos son mas informativos que lejanos (causal_chain)
  - Estructura fork/collider verificada: topologia, padres del collider, cadena de mediadores
  - 3 task types funcionan en los 3 templates (45 configs E2E probadas)
  - 4 DAG generators: 40 tests (estructura, edge cases, world gen, 15 nodos, cross-generator)
  - E2E validation DAG generators: 50 configs (10x5 seeds), teacher>prior 94%, NBO 76%, hyp 80%
  - QualitySuite v2: 48 tests (capas A, B multi-rollout, C + runner + report + cross-template + cross-generator)
  - CasePlan + design_case: 35 tests (model validation, generate_from_plan, orchestrator dispatch)
  - causal_effect: 14 tests (solver causal_query + task generation + cross-template + weighted selection)
  - best_intervention: 13 tests (generation, ranking, scoring, cross-template, determinism)
  - adjustment_set: 20 tests (generation, confounding detection, identifiability, scoring, cross-template)
  - compare_interventions: 15 tests (generation, two-option format, scoring, cross-template, node diversity)
  - should_condition: 14 tests (generation, binary answer, mediator detection, confounder detection, scoring)
  - infer_latent_cause: 12 tests (generation, latent targeting, posterior validity, evidence, scoring via KL)
  - Rich actions: 26 tests (model backward-compat, compound observe, multi-node, IG/cost, cross-template)

---

## Known issues

- Agent submit format: el LLM manda keys planos en vez de `{"distribution": {...}}`, pierde 1 turno
- Agent peor que random en mundos de 8 nodos (mala inferencia con más variables)
- Orchestrator ignora la dificultad pedida (siempre genera "easy")
- `apply_semantics` falla en la primera llamada (manda `node_renames` vacío, reintenta)
- Agent elige variables en orden subóptimo (distinto al teacher)
- NBO triviales (25%): cuando se da mucha evidencia, todos los nodos restantes tienen IG=0 (0% en latent_preference, 28% en causal_chain, 48% en fork_collider). Debería filtrarse para que al menos un nodo tenga IG > 0
- Hipótesis casi indistinguibles con edge_strength baja: con es=0.3 la posterior verdadera y la reversed pueden tener KL=0.0097, haciendo la tarea casi imposible

---

## Dependencies

- Python 3.11, pgmpy (DiscreteBayesianNetwork), networkx, numpy/scipy, pydantic v2
- openai SDK (Azure AI Foundry, NOT AzureOpenAI), python-dotenv
- Dev: pytest, ruff
- LLM: configurable via `AZURE_MODEL` env var
