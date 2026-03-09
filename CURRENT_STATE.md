# SREG — Current State

> Qué hace el sistema hoy, cómo funciona cada parte, y cómo ejecutarlo.
> Actualizado: 2026-03-07

---

## Qué es SREG en una oración

SREG genera **problemas de investigación ficticios** donde la verdad oculta es una
red bayesiana. Un agente LLM intenta resolverlos, y el sistema evalúa automáticamente
qué tan bien razonó — sin necesidad de un humano que corrija.

**Estado actual: 350 tests. 4 familias de templates (3 curadas + custom). 4 DAG generators. 3 tipos de tarea. Multi-task bundles. Pipeline completo. v1 completo + prototipo DAGSpec + generadores (v2).**

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

Cada mundo puede generar distintos tipos de preguntas. Hoy hay 3:

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

### Diferencias clave entre los 3 task types

| | infer_target | next_best_observation | hypothesis_selection |
|---|---|---|---|
| **Qué mide** | Calidad de la estimación | Calidad de la estrategia | Capacidad de comparar |
| **Input** | Datos + acciones | Evidencia parcial + opciones | Evidencia parcial + 4 hipótesis |
| **Output** | Distribución de probabilidad | Un nodo (cuál medir) | Una letra (A/B/C/D) |
| **Scoring** | KL divergence (continuo) | IG ratio (continuo) | Accuracy (binario) |
| **Agente interactúa?** | Sí, hace observaciones | No, solo elige | No, solo elige |

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
pytest tests/ -v                          # Todos (220 tests)
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
| **Models** | `src/sreg/models/` | Contratos de datos (Pydantic): World, Episode, Task, Score, ResearchProblem, DAGSpec |
| **DAGSpec** | `src/sreg/models/dag_spec.py` | Contrato universal para DAGs arbitrarios (validaciones: acíclico, max parents, tipos) |
| **CPD gen** | `src/sreg/world/cpd_gen.py` | Generación genérica de CPDs (extraída de templates, soporta estados heterogéneos) |
| **Templates** | `src/sreg/world/templates/` | 4 generadores: latent_preference, causal_chain, fork_collider + **custom** (DAGSpec) |
| **DAG generators** | `src/sreg/world/dag_generators.py` | 4 generadores de DAGs: Erdos-Renyi, spanning tree, preferential attachment, layered |
| **World check** | `src/sreg/tools/world_check.py` | Valida mundos: DAG acíclico, entropía, d-separaciones, max parents, treewidth |
| **Teacher solver** | `src/sreg/solver/exact_bayes.py` | Inferencia bayesiana exacta: posteriors, information gain, acciones óptimas |
| **Episode gen** | `src/sreg/tools/episode_gen.py` | Crea episodios: budget, nodos disponibles, costos por observación |
| **Task gen** | `src/sreg/tools/task_gen.py` | Genera los 3 tipos de tarea con su respuesta correcta |
| **Verifier** | `src/sreg/tools/verifier.py` | Puntúa al agente: KL divergence, IG ratio, hypothesis accuracy |
| **Episode runner** | `src/sreg/env/` | Interfaz paso a paso: el agente observa → el runner responde |
| **Semantic tools** | `src/sreg/tools/problem_builder.py` | Renombra nodos, genera narrativa, empaqueta como ResearchProblem |
| **Data sampler** | `src/sreg/tools/data_sampler.py` | Samplea datos de la red bayesiana en formato tabular |
| **Orchestrator** | `src/sreg/orchestrator/` | Loop LLM con function calling (genera mundos con semántica) |
| **Agent solver** | `src/sreg/agent/` | Agente LLM que recibe un problema y lo resuelve observando/enviando |
| **Batch eval** | `src/sreg/harness/eval.py` | Evalúa N problemas: agente vs teacher vs random, métricas agregadas |
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
```

### Problem builder + episode
```python
problem = ProblemBuilder().build(world, budget=4)  # → ResearchProblem
# problem.target_node, problem.target_states, problem.budget
# problem.available_actions → list[AvailableAction] (.node, .description, .cost)

episode = EpisodeGenTool().generate(world, EpisodeGenConfig(budget=4))  # → Episode
# episode.budget, episode.available_nodes, episode.node_costs
```

---

## Test coverage

- **350 tests** en todos los módulos
- Tests espejean la estructura de src: `src/sreg/tools/X.py` → `tests/tools/test_X.py`
- Validaciones clave:
  - 100 mundos validados por template (todos pasan)
  - Teacher >90% accuracy en latent_preference, >70% en chain, >60% en fork_collider
  - Nodos más cercanos son más informativos que lejanos (causal_chain)
  - Estructura fork/collider verificada: topología, padres del collider, cadena de mediadores
  - 3 task types funcionan en los 3 templates (45 configs E2E probadas)
  - 4 DAG generators: 40 tests (estructura, edge cases, world gen, 15 nodos, cross-generator)
  - E2E validation DAG generators: 50 configs (10x5 seeds), teacher>prior 94%, NBO 76%, hyp 80%

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
