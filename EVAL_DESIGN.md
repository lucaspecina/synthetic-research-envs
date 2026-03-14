# EVAL_DESIGN.md — Como evaluar SREG

> **Documento de investigacion.** Define QUE queremos medir del sistema SREG,
> a que nivel, con que metricas, y con que comparaciones. Es el equivalente
> de WORLD_DESIGN.md pero para evaluacion.
>
> Este documento NO describe la implementacion del benchmark (eso va en el
> codigo). Describe la **estrategia de evaluacion**: que preguntas queremos
> responder y como las respondemos.
>
> Documento vivo — se actualiza a medida que aprendemos.

---

## Indice

| Seccion | Que contiene |
|---------|-------------|
| **Principios** | Reglas que toda evaluacion debe respetar |
| **Anatomia del sistema** | Las partes evaluables de SREG y sus interfaces |
| **Preguntas de evaluacion** | Que queremos saber, organizado por nivel |
| **Metricas** | Como medir cada pregunta, con definicion precisa |
| **Disenos experimentales** | Combinaciones concretas que responden preguntas |
| **Infraestructura** | Que necesita el runner para soportar todo esto |
| **Hallazgos** | Resultados de evaluaciones pasadas (se acumula) |

---

## Principios de evaluacion

### 1. Siempre con el sistema real

Toda evaluacion que pretenda medir la calidad del PRODUCTO debe usar el
sistema real: orchestrator con LLM, CasePlan, semantica, el pipeline completo.
No mundos de juguete, no templates programaticos, no inputs fabricados.

Si queremos medir una pieza aislada (ej: solo el solver), le damos como
input un SRC generado por el sistema real — no uno fabricado a mano.

### 2. Separar infraestructura de diseno experimental

La infraestructura de benchmark es un **runner general** que puede ejecutar
distintos disenos experimentales. No es un script monolitico que hace
"el benchmark". Es una herramienta con la que hacemos distintos experimentos.

### 3. Cada pregunta tiene una metrica

No medimos "calidad" en abstracto. Cada pregunta de evaluacion tiene una o
mas metricas concretas con definicion precisa, rango de valores, y criterio
de "bueno/malo".

### 4. Las partes se evaluan por separado Y en conjunto

El orchestrator puede generar buenos mundos pero mala narrativa. El solver
puede ser bueno en infer_target pero malo en causal_effect. El sistema completo
puede funcionar pero producir casos triviales. Cada nivel revela cosas distintas.

### 5. La pregunta estrella siempre presente

Todas las metricas de pipeline (completion rate, KL, submit rate, retries)
son utiles pero **no son el objetivo**. Son proxies. La pregunta real es:

> **¿Este case funciona como una mini-investigacion cientifica realista,
> verificable, y util para entrenar/evaluar agentes?**

Si un SRC tiene buen KL, buen submit rate, y el agente "gana", pero el
caso se siente como un ejercicio de grafos y no como investigacion, entonces
el sistema NO esta cumpliendo su proposito. Y al reves: si un caso tiene
metricas mediocres pero se siente como una investigacion real donde el agente
tuvo que pensar, eso es valioso.

Las metricas cuantitativas son necesarias para escalar y comparar. Pero
el benchmark no puede "achatar" la vision a numeros faciles. Siempre debe
haber espacio para inspeccion cualitativa de los casos.

### 6. Comparaciones, no absolutos

Una metrica aislada dice poco. Lo que importa son las comparaciones:
- Agent vs teacher (upper bound)
- Agent vs random (lower bound)
- Run N vs Run N-1 (evolucion temporal)
- Solver A vs Solver B (discriminacion)
- Goal X vs Goal Y (dificultad por dominio)

---

## Anatomia del sistema — las partes evaluables

```
                    [SEED / GOAL]
                         |
                         v
               +-------------------+
               |   ORCHESTRATOR    |  <-- Parte 1: Generacion
               |  (LLM + tools)   |
               +-------------------+
                         |
                  produce un SRC:
                  - World (formal)
                  - Semantica
                  - CasePlan
                  - ResearchProblem
                  - Tasks
                         |
            +------------+------------+
            |                         |
            v                         v
   +-----------------+      +-----------------+
   | MUNDO FORMAL    |      | PRESENTACION    |  <-- Parte 2 y 3
   | (BN, CPDs, DAG) |      | (narrativa,     |
   |                 |      |  datos, acciones)|
   +-----------------+      +-----------------+
            |                         |
            |     +-------------------+
            |     |
            v     v
   +-----------------+
   |  AGENT SOLVER   |  <-- Parte 4: Interaccion
   |  (LLM que       |
   |   investiga)    |
   +-----------------+
            |
            v
   +-----------------+
   |  EVALUACION     |  <-- Parte 5: Scoring
   |  (verifier,     |
   |   teacher, KL)  |
   +-----------------+
```

**Interfaces clave (donde se puede "cortar" el sistema):**

- **Despues del orchestrator**: tenemos un SRC completo. Podemos evaluarlo
  sin correr ningun solver (calidad de generacion).
- **Despues del mundo formal**: tenemos la BN. Podemos medir propiedades
  estructurales sin ver la semantica.
- **Despues de la presentacion**: tenemos lo que ve el agente. Podemos
  analizar si es comprensible sin correr el solver.
- **Despues del solver**: tenemos una trayectoria. Podemos compararla
  con el teacher.

Esto significa que podemos disenar experimentos que evaluan **una parte**
manteniendo las otras fijas.

---

## Preguntas de evaluacion — por nivel

### Nivel 1: Orchestrator (generacion de SRCs)

> "¿El orchestrator produce buenos casos de investigacion?"

| ID | Pregunta | Que revela |
|----|----------|-----------|
| O.1 | ¿Completa el pipeline? (mundo + semantica + CasePlan + problema) | Robustez basica |
| O.2 | ¿Cuantos reintentos necesita? (world_check failures, apply_semantics retries) | Eficiencia |
| O.3 | ¿Los CasePlans son diversos? (variedad de eval types por caso) | Riqueza |
| O.4 | ¿Produce el mismo tipo de caso para goals distintos? | Sensibilidad al goal |
| O.5 | ¿Dado el mismo goal + seed, produce casos estructuralmente similares? (no igualdad exacta — los LLMs tienen variacion residual. Medir consistencia de estructura y semantica, no identidad) | Estabilidad aproximada |
| O.6 | ¿Dado el mismo goal + distinta seed, produce casos distintos? | Diversidad |

### Nivel 2: Mundo formal (calidad de la BN)

> "¿La red bayesiana subyacente es valida, interesante, no trivial?"

| ID | Pregunta | Que revela |
|----|----------|-----------|
| W.1 | ¿WorldCheck pasa? | Validez estructural |
| W.2 | ¿La entropia del target es adecuada? (ni 0 ni maxima) | No trivialidad |
| W.3 | ¿Hay signal? (entropy reduction > 0 con teacher) | Informatividad |
| W.4 | ¿El budget ratio es < 0.8? | Hay decisiones que tomar |
| W.5 | ¿Cada eval type del CasePlan es no-trivial? | Calidad por tipo |

**W.5 en detalle — que significa "no trivial" por eval type:**

| Eval type | No trivial si... |
|-----------|-----------------|
| infer_target | prior != posterior (hay signal) |
| next_best_observation | max(IG) > 0 (hay algo que medir) |
| hypothesis_selection | min KL entre distractores > 0.05 (distinguibles) |
| causal_effect | P(Y\|do(X)) != P(Y) (la intervencion cambia algo) |
| best_intervention | top intervention != second best (hay un ganador) |
| adjustment_set | set no vacio O no identificable (caso interesante) |
| should_condition | hay varianza (no siempre "yes" ni siempre "no") |
| compare_interventions | las dos opciones dan resultados diferentes |
| infer_latent_cause | posterior del latente != prior (evidencia informa) |

### Nivel 3: Presentacion (calidad de la capa semantica)

> "¿Lo que ve el agente se entiende como investigacion real?"

| ID | Pregunta | Que revela |
|----|----------|-----------|
| P.1 | ¿Los nombres de variables son semanticos? (no "v0", "indicator_1") | Calidad de naming |
| P.2 | ¿La narrativa menciona el dominio y contexto? | Riqueza narrativa |
| P.3 | ¿La pregunta de investigacion se entiende sin conocer el DAG? | Claridad |
| P.4 | ¿Las acciones tienen descripciones comprensibles? | Accionabilidad |
| P.5 | ¿Los datos iniciales aportan sin regalar la respuesta? | Balance de evidencia |
| P.6 | ¿Hay leakage? (la respuesta se puede inferir sin investigar) | Integridad |

**Nota**: P.1-P.4 se pueden aproximar con heuristicas programaticas (regex,
conteo de palabras, patrones) pero la calidad semantica real probablemente
necesite revision cualitativa o un LLM-judge liviano. No asumir que regex
es suficiente — un nombre puede ser "semantico" y aun asi no tener sentido
en el dominio. Las heuristicas son un primer filtro, no la medicion final.
P.5 y P.6 son mas dificiles — probablemente requieren el solver como proxy
(si el agente resuelve sin observar, hay leakage).

### Nivel 4: Agent solver (interaccion con el entorno)

> "¿El agente puede interactuar con el caso de forma que se parezca a investigar?"

| ID | Pregunta | Que revela |
|----|----------|-----------|
| A.1 | ¿Submittea una respuesta? | Funcionalidad basica |
| A.2 | ¿En el formato correcto? | Robustez del prompt/harness |
| A.3 | ¿Mejor que random? | Minimo de utilidad |
| A.4 | ¿Que tan lejos del teacher? | Gap con el optimo |
| A.5 | ¿Usa el budget eficientemente? (budget_used / budget_total) | Estrategia de recursos |
| A.6 | ¿Observa variables relevantes? (overlap con teacher — diagnostico, no criterio: un agente puede diferir del teacher y resolver bien) | Inspeccion de estrategia |
| A.7 | ¿Su razonamiento menciona los datos? | Uso de evidencia |
| A.8 | ¿Mejora su estimacion con mas observaciones? | Aprendizaje incremental |

### Nivel 5: Sistema completo (E2E)

> "¿SREG como producto cumple su proposito?"

| ID | Pregunta | Que revela |
|----|----------|-----------|
| E.1 | ¿El sistema genera + resuelve sin errores? | Estabilidad E2E |
| E.2 | ¿Los casos generados discriminan entre buen y mal solver? | Poder discriminativo |
| E.3 | ¿Un mismo SRC produce resultados consistentes con distinta seed del solver? | Estabilidad de evaluacion |
| E.4 | ¿La dificultad varia con los parametros? (mas nodos = mas dificil?) | Controlabilidad |
| E.5 | ¿Los casos se sienten como investigacion real? (litmus test subjetivo) | Validez ecologica |

---

## Metricas — definiciones precisas

### Metricas del orchestrator

| Metrica | Definicion | Rango | Bueno |
|---------|-----------|-------|-------|
| `completion_rate` | SRCs completos / intentos totales | 0-1 | > 0.8 |
| `mean_retries` | promedio de tool calls fallidos por caso | 0+ | < 2 |
| `eval_type_diversity` | eval types unicos por CasePlan, promediado | 1-9 | > 2 |
| `goal_sensitivity` | 1 - jaccard(eval_types de goal A, eval_types de goal B) | 0-1 | > 0.3 |

### Metricas del mundo formal

| Metrica | Definicion | Rango | Bueno |
|---------|-----------|-------|-------|
| `worldcheck_pass_rate` | mundos que pasan WorldCheck / total | 0-1 | > 0.9 |
| `mean_target_entropy` | H(target) promedio en bits | 0+ | 0.5-2.0 |
| `mean_entropy_reduction` | H(prior) - H(teacher_posterior) promedio | 0+ | > 0.1 |
| `budget_ratio` | budget / observables con path al target | 0+ | < 0.8 |
| `eval_type_nontrivial_rate` | tasks no triviales / total de tasks | 0-1 | > 0.7 |

### Metricas del solver

| Metrica | Definicion | Rango | Bueno |
|---------|-----------|-------|-------|
| `submit_rate` | agente envio respuesta / total | 0-1 | > 0.9 |
| `format_error_rate` | errores de formato / total de submits | 0-1 | < 0.1 |
| `mean_agent_kl` | KL divergence promedio del agente | 0+ | < 1.0 |
| `agent_beats_random_rate` | casos donde KL_agent < KL_random / total | 0-1 | > 0.6 |
| `mean_teacher_gap` | mean(KL_agent - KL_teacher) | 0+ | referencia |
| `budget_efficiency` | mean(budget_used / budget_total) | 0-1 | 0.5-0.9 |
| `teacher_overlap` | fraccion de observaciones del agente que el teacher tambien hizo | 0-1 | diagnostico (no criterio) |

### Metricas E2E

| Metrica | Definicion | Rango | Bueno |
|---------|-----------|-------|-------|
| `e2e_success_rate` | genera + resuelve sin error / total | 0-1 | > 0.7 |
| `verdict_distribution` | % EXCELLENT/GOOD/FAIR/POOR/NO_SUBMIT | - | mas GOOD+ que POOR+ |

---

## Disenos experimentales

Cada diseno experimental es una **pregunta de investigacion** que se responde
corriendo el benchmark con una configuracion especifica.

### Experimento 1: Estado del sistema (el benchmark base)

**Pregunta**: "¿Como esta el sistema hoy?"

**Diseno**:
- N = 20-30 SRCs generados con el orchestrator
- Goals variados (5+ dominios, 3+ tamaños)
- Un solver (el agent solver actual)
- Medir TODAS las metricas de todos los niveles

**Comparaciones**:
- Agent vs teacher vs random por caso
- Metricas por dominio y por tamaño
- Distribucion de failure modes

**Output**: reporte base para comparar con futuros runs.

**Cuando correrlo**: despues de cada cambio significativo al sistema.

### Experimento 2: Poder discriminativo

**Pregunta**: "¿El mismo SRC distingue entre un buen y un mal solver?"

**Diseno**:
- N = 10 SRCs fijos (generados una vez y guardados)
- Multiples solvers sobre los mismos SRCs:
  - Agent solver actual (LLM con observe/submit)
  - Random baseline (uniforme sin observar)
  - Informed random (observa al azar, usa posterior)
  - Teacher (upper bound)
- Medir KL, submit rate, budget efficiency por solver

**Comparaciones**:
- ¿Hay separacion clara entre solvers?
- ¿Los SRCs donde el agent falla son los mismos donde el informed random falla?
- ¿O hay SRCs que son faciles para todos o imposibles para todos?

**Lo que revela**: si SREG realmente discrimina calidad de razonamiento
o si todos los solvers dan resultados parecidos (caso trivial o imposible).

### Experimento 3: Sensibilidad al goal

**Pregunta**: "¿El orchestrator produce casos diferentes para goals diferentes?"

**Diseno**:
- 5 goals muy distintos (ecologia, epidemiologia, materiales, geologia, computacion)
- 5 SRCs por goal (distintas seeds)
- Sin solver — solo evaluar generacion

**Comparaciones**:
- ¿Los CasePlans varian entre dominios? (eval types, num preguntas)
- ¿Los mundos varian en estructura? (num nodos, density, depth)
- ¿La narrativa es especifica del dominio?

**Lo que revela**: si el orchestrator realmente adapta el caso al goal
o siempre produce lo mismo.

### Experimento 4: Dificultad controlable

**Pregunta**: "¿Podemos controlar la dificultad de los SRCs?"

**Diseno**:
- Mismo dominio, mismo solver
- Variar: num_nodes (6, 8, 10, 12), edge_strength, budget
- N = 5 por configuracion

**Comparaciones**:
- ¿Mas nodos = peor KL del agent?
- ¿Mas budget = mejor KL?
- ¿Edge strength afecta la dificultad?

**Lo que revela**: si podemos generar curriculos de dificultad.

### Experimento 5: Estabilidad de evaluacion

**Pregunta**: "¿El mismo SRC da resultados consistentes al evaluarlo multiples veces?"

**Diseno**:
- 5 SRCs fijos
- Correr el solver 5 veces por SRC (distintas seeds de sampling)
- Medir varianza intra-SRC

**Comparaciones**:
- ¿El verdict cambia entre runs?
- ¿El KL tiene mucha varianza?

**Lo que revela**: que tan confiable es una sola evaluacion.

### Experimentos futuros (no implementar todavia)

- **Narrativa matters**: mismo mundo formal, distintas semanticas → ¿cambia el resultado?
- **Eval type difficulty**: ¿que eval types son mas faciles/dificiles para el agent?
- **Paper-seeded vs free**: ¿los SRCs seeded desde papers son mejores?
- **Multi-solver tournament**: comparar distintos LLMs como solvers

---

## Infraestructura necesaria

El runner de benchmark necesita ser **general**, no atado a un solo diseno.

### Capacidades del runner

1. **Generar SRCs**: dado un goal + seed, producir un caso completo via orchestrator
2. **Cargar SRCs**: dado un JSON guardado, cargar un caso sin regenerar
3. **Correr solver**: dado un SRC + solver config, producir trayectoria
4. **Medir**: dado un SRC + trayectoria, calcular todas las metricas
5. **Agregar**: dado un batch de resultados, calcular metricas agregadas
6. **Persistir**: guardar todo en un directorio con formato consistente
7. **Comparar**: dado dos runs, mostrar deltas

### Separacion de responsabilidades

```
src/sreg/harness/
  benchmark.py    # Logica: BenchmarkRunner, BenchmarkResult, metricas
  eval.py         # BatchEvaluator (existente, se refactoriza o absorbe)
  trajectory.py   # Teacher trajectories (se queda)
  agent_trajectory.py  # Agent trajectories (se queda)
  comparison.py   # Comparaciones (se queda)
  quality.py      # Metricas estructurales (se queda como herramienta interna)

scripts/
  benchmark.py    # CLI: parsea args, instancia runner, ejecuta, reporta
```

### Formato de persistencia

```
experiments/
  index.md                     # Indice de todos los experimentos
  exp_YYYYMMDD_HHMMSS_name/
    config.json                # Parametros del run
    summary.json               # Metricas agregadas
    report.txt                 # Reporte legible (metricas + failure modes)
    cases/
      case_001_src.json        # El SRC completo (mundo, problema, CasePlan, tasks)
      case_001_result.json     # Trayectoria del agente + comparacion + metricas
      ...
```

---

## Hallazgos

> Esta seccion se va llenando con los resultados de cada experimento.
> Cada hallazgo referencia el experimento que lo produjo.

### Hallazgos previos (pre-benchmark, de toy diagnostic — OBSOLETOS)

**Nota**: estos hallazgos vienen de mundos programaticos (toy) usando el script
`diagnostic_batch.py` (eliminado). Se incluyen como referencia historica pero
estan SUPERADOS por el diagnostico real con orchestrator (DIAG.4, 15 SRCs).

- 72% submit format errors -> CORREGIDO en P0 cleanup (auto-correccion de formato)
- 100% sin thinking text -> MITIGADO con think() tool (S.5.3)
- 88% distribuciones planas -> MEJORADO con python_exec (S.5.1, el agente ahora analiza datos)

**Hallazgos actuales**: ver DIAG.4 en TODO.md y `experiments/` para resultados reales.

---

## Decisiones de diseno abiertas

- [ ] ¿Necesitamos un "SRC registry" para guardar y reusar SRCs entre experimentos?
- [ ] ¿Como medimos P.5 (leakage) de forma automatica?
- [ ] ¿Definimos targets numericos para todas las metricas o solo para las criticas?
- [ ] ¿El runner debe soportar multiples solvers en un mismo run?
- [ ] ¿Como versionamos los resultados cuando el sistema cambia?
