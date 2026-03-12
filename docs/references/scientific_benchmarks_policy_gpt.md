# Benchmarks externos para validar transferencia de un solver entrenado en SREG

## Resumen ejecutivo

SREG (Synthetic Research Environment Generator) tiene una promesa fuerte: entrenar un solver (agente LLM) en **research cases sintéticos pero verificables** (mundo formal tipo BN/SCM + capa visible con narrativa/acciones/tasks) para que el solver adquiera **habilidades científicas transferibles**. Validar esa promesa requiere ir más allá del “mejoró en SREG” (in-domain) y demostrar **mejora BEFORE/AFTER** en benchmarks externos que midan capacidades lo más cercanas posible al comportamiento que SREG entrena (razonamiento causal, selección de experimentos/observaciones, análisis de datos, formulación/validación de hipótesis, uso eficiente de presupuesto/costo).

Tras revisar benchmarks recientes y “product-grade” orientados a ciencia y agentes, la recomendación práctica para un protocolo BEFORE/AFTER (con reproducibilidad y pipelines públicos) es:

- **Benchmark principal (transferencia cercana): _DiscoveryBench_**  
  Motivo: mide **data-driven discovery** (buscar/validar hipótesis desde datasets), exige **razonamiento estadístico + semántico científico**, y tiene **evaluación facetada** con scripts públicos.citeturn13view0turn25view1turn14view2  
  Métrica central: **Hypothesis Match Score (HMS)** y submétricas por **contexto/variables/relación**.citeturn14view2turn13view0

- **Benchmark secundario (transferencia cercana pero “habilidad núcleo”): _CLadder_**  
  Motivo: mide **razonamiento causal formal** (asociación → intervención → contrafactual), con dataset y código abiertos, y variantes que permiten tests de robustez (commonsense vs nonsense) útiles para separar “semántica” de “causalidad”.citeturn21view0turn2search5  
  Métricas: accuracy / log-loss por **rung** y por **tipo de query** (ATE, backdoor, NDE/NIE, counterfactual, etc.).citeturn21view0

- **Benchmark duro (transferencia lejana, agente + análisis real): _BixBench_**  
  Motivo: escenarios reales de bioinformática, trayectorias largas (notebooks), ejecución de código en entorno controlado (Docker), pipeline público de evaluación (agente o zero-shot).citeturn17view0turn16view1turn8view1  
  Métricas: accuracy (open-answer con grader LLM / MCQ con exact match + majority vote), más métricas de eficiencia/costo (tokens, número de ejecuciones, etc.).citeturn17view0turn16view1

Recomendación adicional (no pedida como parte del “top 3”, pero muy valiosa si querés un “duro++” o suite integral): **AstaBench** como mega-suite de evaluación científica con herramientas estandarizadas, control de costos y compatibilidad con agentes generales.citeturn23view0turn23view1turn23view2

Debajo vas a encontrar: tabla comparativa de benchmarks, mapeo detallado SREG ↔ métricas externas, y un protocolo BEFORE→TRAIN→AFTER con criterios de éxito, riesgos y una propuesta concreta de implementación (scripts/archivos/adapters) dentro de tu repo.

## Marco de evaluación de transferencia para SREG

Para validar “SREG realmente enseña ciencia”, conviene separar el problema en tres niveles (porque cada nivel responde una pregunta distinta):

- **In-domain (dentro de SREG):**  
  “¿El solver aprende a maximizar reward en research cases SREG, usando mejor el budget y aproximándose al teacher?”  
  Métricas típicas: KL vs teacher, regret vs teacher, eficiencia de budget, info gain realizado vs óptimo (si lo tenés), tasa de resolución, etc. (esto es propio de SREG; no requiere fuentes externas).

- **Transferencia cercana (benchmarks externos que comparten el *mismo tipo de habilidad*):**  
  “¿Después de entrenar en SREG, el solver mejora en tareas de descubrimiento/causalidad/selección de evidencia que se parecen al loop de investigación?”  
  Aquí entran **DiscoveryBench** y **CLadder** (y opcionalmente NeuroDiscoveryBench).citeturn13view0turn21view0turn24view1

- **Transferencia lejana (benchmarks externos ‘duros’, más abiertos y con workflows reales):**  
  “¿Mejora en escenarios largos con herramientas, datos reales y evaluación más parecida a investigación aplicada?”  
  Aquí entra **BixBench**.citeturn17view0turn8view1  
  En un escalón aún más duro/holístico, **AstaBench** (si querés consolidar evaluación multi-skill con control de confounders como herramientas y costo).citeturn23view0turn23view2

La lógica es: si solo ganás in-domain, puede ser sobreajuste a la “forma” de SREG; si ganás en transferencia cercana, es evidencia fuerte de skill real; si además ganás en transferencia lejana, es evidencia de que SREG mejora capacidades generalizables para “hacer ciencia” con herramientas y datos.

## Benchmarks candidatos y selección recomendada

### Tabla comparativa

> Nota sobre “URL”: por restricciones de formato, incluyo las URLs oficiales en un bloque al final de esta sección (y están referenciadas por fuentes oficiales en las citas).

| Benchmark | Foco | Qué mide (métricas principales) | Dificultad | Disponibilidad / reproducibilidad | Idioma típico | Esfuerzo de integración |
|---|---|---|---|---|---|---|
| DiscoveryBenchentity["organization","Allen Institute for AI","research institute seattle"] | Data-driven discovery desde datasets | Hypothesis Match Score (HMS) + submétricas (Context F1, Variables F1, Relation accuracy), evaluación facetada con scripts públicos.citeturn13view0turn14view2turn25view1 | Alta (mejor sistema ~25% reportado en paper)citeturn13view0 | Dataset + código + CLI públicos (GitHub + HF).citeturn25view1turn13view0 | Inglés | Medio (adaptar tu solver a “discovery agent I/O”; usar su evaluator) |
| CLadder | Causal reasoning formal (Pearl ladder) | Accuracy / log-loss por rung y query_type; permite análisis por estructura y variantes (commonsense/nonsense).citeturn21view0turn2search5 | Media–alta (según rung/variant)citeturn21view0 | Dataset + código abiertos (GitHub, zip, HF).citeturn21view0 | Inglés | Bajo (formato Q/A yes/no; fácil de “adaptar”) |
| BixBenchentity["organization","FutureHouse","nonprofit science sf"] | Agentes en bioinformática con notebooks reales | Accuracy (open-answer con graders LLM; MCQ exact + majority vote), trayectorias + postprocessing; ejecución en Docker; scripts de run.citeturn17view0turn16view1turn8view1 | Muy alta (trayectorias largas; coste)citeturn17view0turn8view1 | Dataset + repo públicos; versión actualizada (v1.5) con cambios en preguntas/formatos.citeturn17view0turn16view1 | Inglés | Medio–alto (necesitás pipeline/formatos de trayectorias + entorno Docker) |
| LAB-Bench | Capacidades de investigación en biología (MCQ + multimodal) | Accuracy por subtarea (LitQA2, DbQA, FigQA/TableQA, ProtocolQA, SeqQA, etc.); harness público; parte del test es privado para contaminación.citeturn16view2turn16view3 | Media (varía por subtask; cloning scenarios más difícil)citeturn16view3turn16view2 | Repo/harness públicos; dataset público ~80% + 20% private test para contamination.citeturn16view2turn16view3 | Inglés | Bajo–medio (MCQ; pero FigQA requiere handling de imágenes) |
| PaperBenchentity["company","OpenAI","ai research company"] | Replicar papers de investigación en AI (long-horizon) | Score por rúbricas jerárquicas; ejecución/replicación; tiene dataset y tooling; variante Code-Dev reduce costo (sin GPU) pero menos rigor.citeturn22search2turn4view2turn8view4 | Extremadamente alta | Dataset + código abiertos en repo; también integrado en Inspect Evals.citeturn4view2turn22search3turn22search5 | Inglés | Muy alto (infra + runtime + costo) |
| AstaBench | Suite holística para “science research agents” | Muchas métricas por benchmark + control de costo/tokens con agent-eval; entorno con tools estandarizadas.citeturn23view0turn23view1turn23view2 | Muy alta (suite) | Repos + leaderboard tooling; basado en InspectAI y agent-eval; pensado para reproducibilidad/cost accounting.citeturn23view0turn23view2 | Inglés | Alto (pero te da infraestructura ya armada) |
| NeuroDiscoveryBench | Data analysis QA en neurociencia con datasets reales | Matching de context/variables/relations vs gold; VLM scoring para figuras; ~70 Q/A pairs.citeturn24view1turn24view0 | Alta (pocos items pero pesados) | Repo público con baseline agents y scripts de eval; datasets descargables.citeturn24view0turn24view1 | Inglés | Medio (más chico que BixBench; útil como “smoke transfer”) |
| ResearchBench | Hypothesis discovery (inspiration retrieval + hypothesis ranking) | Métricas de retrieval/ranking/hypothesis; papers 2024 para evitar contaminación | Media | Paper disponible; disponibilidad de dataset/harness oficial menos clara (hay rehosts, pero no siempre oficial).citeturn8view0turn7view0turn6view5 | Inglés | Medio (si no hay harness oficial, lo pagás en ingeniería) |

### Selección final recomendada para BEFORE/AFTER

- **Principal: DiscoveryBench** (transferencia cercana “hacer discovery con datos”).citeturn13view0turn25view1turn14view2  
- **Secundario: CLadder** (transferencia cercana “razonamiento causal formal”).citeturn21view0turn2search5  
- **Duro: BixBench** (transferencia lejana “agente científico real con tool-use y trayectorias largas”).citeturn17view0turn8view1turn16view1  

Por qué esta combinación funciona bien:

- Cubre **descubrimiento desde datos** (DiscoveryBench) y **causalidad formal** (CLadder) que están muy alineados con el “core” de SREG (world-model + inferencia/acciones).citeturn13view0turn21view0  
- Agrega un benchmark duro que exige **tool-use + análisis real + narrativa científica + trayectorias** (BixBench), que se parece a “investigación aplicada” mucho más que un set de Q/A.citeturn17view0turn8view1  
- Los tres tienen **repos/pipelines públicos** (o al menos dataset + harness), lo que permite reproducibilidad y automatización.

### URLs oficiales de referencia

Las siguientes URLs salen de repos/páginas oficiales citadas arriba (DiscoveryBench, CLadder, BixBench, y opcionales).citeturn25view1turn21view0turn17view0turn23view0turn4view2

```text
DiscoveryBench
- Paper (arXiv HTML): https://arxiv.org/abs/2407.01725
- Repo: https://github.com/allenai/discoverybench
- Dataset (HF): https://huggingface.co/datasets/allenai/discoverybench

CLadder
- Repo: https://github.com/causalNLP/cladder
- Dataset (HF): https://huggingface.co/datasets/causalnlp/CLadder
- Paper (arXiv): https://arxiv.org/abs/2312.04350

BixBench
- Repo: https://github.com/Future-House/BixBench
- Dataset (HF): https://huggingface.co/datasets/futurehouse/BixBench
- Paper (arXiv): https://arxiv.org/abs/2503.00096
- Announcement: https://www.futurehouse.org/research-announcements/bixbench

Opcionales “duros++”
- PaperBench (blog): https://openai.com/index/paperbench/
- PaperBench (repo): https://github.com/openai/frontier-evals/tree/main/paperbench
- AstaBench (repo): https://github.com/allenai/asta-bench
- AstaBench (site): https://allenai.org/asta/bench
```

## Mapeo detallado capacidades SREG ↔ benchmarks y métricas

### Capacidades que SREG pretende entrenar

Asumiendo el diseño que describiste (mundo formal BN/SCM + capa visible con narrativa + acciones + budget + tasks verificables), las capacidades “target” típicas son:

- **Razonamiento bajo incertidumbre**: actualizar creencias y calibrar confianza (distribuciones, no solo argmax).
- **Causalidad**: distinguir correlación vs causalidad; razonar con intervenciones (do), confounding, mediación.
- **Active learning científico**: elegir observaciones/intervenciones informativas bajo budget/costo.
- **Planificación de investigación**: decidir qué evidencia recolectar y cuándo “submitir” una conclusión.
- **Tool-use controlado**: ejecutar análisis/consultas (si tu capa visible lo permite) sin explotar tooling de forma espuria.
- **Robustez a semántica/narrativa**: que el solver use contexto y no quede “atrapado” por nombres arbitrarios.

Debajo, para cada benchmark recomendado, detallo cómo mapear estas capacidades a métricas específicas.

### DiscoveryBench como benchmark principal

**Qué es y por qué mapea bien**  
DiscoveryBench formaliza el proceso de “data-driven discovery”: dado un goal y dataset(s), producir una hipótesis en lenguaje natural (contexto, variables, relación) y opcionalmente un workflow.citeturn13view0turn25view1  
El paper enfatiza que las tareas requieren **análisis estadístico** y además **razonamiento semántico científico**, como elegir técnicas apropiadas y mapear términos del goal a columnas del dataset.citeturn13view0turn25view0

**Ejemplo de tarea (del propio paper, para entender el tipo de input)**  
En el texto aparece un ejemplo del estilo: “¿Cómo afectó el uso de suelo urbano la invasión de plantas introducidas…?” y se discute que hay que decidir análisis apropiados (p.ej. autocorrelación espacial) y mapear conceptos (“land use” → “habitat type”).citeturn26view0turn13view0

**Métricas nativas del benchmark**  
DiscoveryBench usa un evaluador basado en LLM que descompone hipótesis gold y predicha en sub-hipótesis (context/variables/relations) y calcula **Hypothesis Match Score (HMS)** con F1/accuracy por dimensión.citeturn14view2turn13view0  
Esto te da:
- HMS global
- F1 de contextos
- F1 de variables
- accuracy (o score heurístico) de la relación (relación exacta vs más general vs incorrecta)citeturn14view2

**Cómo mapear outputs de tu solver a DiscoveryBench**  
Tu solver, en SREG, devuelve distribuciones y toma acciones. En DiscoveryBench, el output requerido es “hipótesis” (+ workflow opcional). Para no “cambiar el solver” de forma injusta, la recomendación es:

- Mantener la **misma arquitectura de agente** (misma scaffolding: planner→act→reflect, o ReAct-like), pero cambiar:
  - herramienta: acceso al dataset local en vez de tools de SREG,
  - formato final: `pred_hypo` (texto) y opcional `pred_workflow` (texto/JSON).
- Registrar trayectoria como en SREG (mensajes + tool calls) y al final compilar el `pred_hypo`.

**Métricas extra que conviene agregar (además de HMS)**  
Para alinear con SREG, agregá:

- “Eficiencia”: tokens / HMS, ejecuciones de código / HMS (si el agente usa Python).  
- “Tiempo a solución”: pasos hasta primera hipótesis válida.
- “Robustez al budget”: si implementás un “budget artificial” en DiscoveryBench (p.ej., máximo de ejecuciones de código o máximo de tool calls), podés medir degradación controlada.

**Puntos de riesgo (y por qué no invalidan el benchmark)**  
DiscoveryBench usa LLM-as-judge para HMS. Esto es un riesgo de estabilidad, pero el paper publica prompts y el evaluator CLI; eso te permite **fijar** versión del judge y prompt para comparaciones BEFORE/AFTER consistentes.citeturn14view1turn25view1

### CLadder como benchmark secundario

**Qué es y por qué mapea bien**  
CLadder es un benchmark para evaluar **causal reasoning formal** en lenguaje natural, con preguntas yes/no que requieren inferencia estadística/causal.citeturn21view0turn2search5  
Incluye rungs (asociación/intervención/contrafactual), tipologías (ATE, backdoor, NDE/NIE, counterfactual, etc.) y metadatos por story/graph/model.citeturn21view0

**Por qué es clave para SREG**  
Si SREG se basa en un world-model causal/probabilístico, CLadder te permite medir si el entrenamiento mejora:
- el “núcleo” de inferencia causal (no solo heurística),
- la generalización a escenarios verbalizados,
- y la robustez a semántica (por su variante “nonsense” donde los nombres se vuelven aleatorios).citeturn21view0

**Métricas recomendadas**  
CLadder es naturalmente scorabeable programáticamente:

- Accuracy global (yes/no)
- Accuracy por rung (1/2/3) y por query_type (ATE, backdoor, NDE, NIE, etc.)citeturn21view0  
- Log-loss o Brier score si hacés que el solver produzca `P(yes)` y `P(no)` (esto calza perfecto con tu orientación “distribución” en SREG).

**Cómo mapear outputs de tu solver a CLadder**  
Dos opciones:

- **Opción A (simple):** el solver responde “yes/no”.  
- **Opción B (mejor, porque respeta SREG):** el solver produce distribución `{yes: p, no: 1-p}` + decisión argmax.  
  Así podés medir calibración (Brier/log-loss) y no solo accuracy.

**Diseño experimental potente dentro de CLadder (muy alineado con SREG)**  
Usá las variantes incluidas:

- `q-commonsense` vs `q-anticommonsense` vs `q-nonsense` para ver si el solver depende de asociaciones semánticas en vez de razonamiento causal.citeturn21view0  
Si SREG entrena causalidad “real”, deberías ver:
- mejora significativa en `q-hard` y `q-anticommonsense`,
- poca caída relativa en `q-nonsense` (o al menos menor que el baseline), lo que sugiere menor dependencia de semántica.

### BixBench como benchmark duro

**Qué es y por qué es “duro”**  
BixBench evalúa agentes en tareas reales de bioinformática y análisis en notebooks; el repo describe que el agente debe explorar datasets, ejecutar código (Python/R/Bash), generar hipótesis científicas y validarlas.citeturn17view0turn8view1  
El dataset actual público incluye **205 preguntas** derivadas de notebooks reales (“capsules”) y soporta modo open-ended o multiple-choice.citeturn17view0turn16view1

**Detalle importante: versionado del dataset**  
El dataset en HF indica un update importante (revisión y cambio de formato, y versiones `v1.0` vs `v1.5`). Para un BEFORE/AFTER serio, hay que **pinnear la versión** (ej. `v1.5`) y registrar el hash/tag en el experimento.citeturn16view1turn17view0

**Métricas nativas del benchmark (según repo)**  
El repo documenta:

- Evaluaciones **agentic**: generar trayectorias + postprocessing (incluye majority vote para MCQ con k réplicas).citeturn17view0  
- Evaluaciones **zero-shot**: generar respuestas y luego **grade_outputs** con graders LLM para open-ended o exact match para MCQ.citeturn17view0

Esto te da:

- Accuracy open-answer (grader)
- Accuracy MCQ
- Majority-vote accuracy (k=5 típico reportado en scripts)citeturn17view0

**Cómo mapear outputs/trajectories de tu solver a BixBench**  
BixBench está bien preparado para “trajectories”; incluso su README propone un camino explícito para “usar tu propio agente” implementando un `custom_rollout` que produzca trayectorias en el formato esperado, y luego reaprovechar su `postprocessing.py`.citeturn17view0

Eso encaja muy bien con tu estilo SREG, porque:

- ya tenés infraestructura de trayectorias (mensajes + tool calls),
- podés exportar a su JSON de trayectorias,
- y dejás el scoring al harness oficial.

**Qué métricas extra conviene capturar por alineación con SREG**  
BixBench introduce de facto “costo de investigación” por:

- cantidad de ejecuciones de notebook/código,
- tokens,
- tiempo de ejecución,
- número de archivos/datasets tocados.

Agregá:

- Score vs costo: accuracy / tokens, accuracy / ejecuciones de código.
- “Curva de mejora con réplicas”: accuracy@1 vs accuracy@k (k=3/5). Esto mide “robustez” y sensibilidad a sampling.citeturn17view0

**Por qué BixBench es una buena prueba de transferencia lejana**  
Porque te saca de:
- mundos generados y verificables con teacher exacto (SREG),
y te pone en:
- datos reales + tool-use + interpretación científica,
donde la habilidad de planificar evidencia y analizar resultados es central.citeturn17view0turn8view1

## Protocolo experimental BEFORE→TRAIN→AFTER

### Flujo general

```mermaid
flowchart TD
  A[Definir solver S0 (baseline) + scaffolding fija] --> B[BEFORE: evaluar S0 en benchmarks externos]
  B --> C[Entrenar en SREG: S0 -> S1 (SFT y/o RL)]
  C --> D[AFTER: evaluar S1 en los mismos benchmarks y splits]
  D --> E[Comparar: deltas, significancia, failure modes, costo]
  E --> F[Decisiones: qué tocar en SREG/solver; nuevo ciclo]
```

### Diseños experimentales mínimos y “controlables”

Para que el BEFORE/AFTER sea interpretable, necesitás aislar cambios.

**Constantes a fijar (si no las fijás, el resultado se vuelve dudoso):**

- Misma scaffolding (plan/act/reflect; mismas tools salvo las del benchmark).
- Misma política de sampling (temperature/top_p) o, si no, **múltiples seeds** por tarea.
- Misma infraestructura de logs (guardar conversaciones y tool calls).
- Mismo evaluador/judge cuando el benchmark use LLM-as-judge (p.ej., DiscoveryBench HMS).citeturn14view2turn14view1

**Controles recomendados:**

- **Control negativo:** “entrenamiento placebo” (p.ej. más pasos de SFT en datos no relacionados, o RL con reward random) para verificar que mejoras no surgen por “drift” o mayor compute.  
- **Ablación de semántica:** usar CLadder `q-nonsense` vs `q-commonsense` para ver si la mejora es causal o semántica.citeturn21view0  
- **NoData baselines** (cuando existan): DiscoveryBench incluye el baseline de “NoDataGuess” para medir memorization.citeturn14view3turn13view0

### Entrenamiento en SREG

Como no pediste un método único, propongo un protocolo escalonado que se alinea con tu entorno verificable:

- **Fase SFT (supervisada)**: usar teacher trajectories / optimal policies de SREG para enseñar:
  - formato correcto de herramientas,
  - patrones de investigación (observar → actualizar → decidir),
  - y outputs calibrados (distribución).  
  Esto reduce errores de harness y crea base estable para RL.

- **Fase RL (o RLAIF) en SREG**: optimizar:
  - selección de acciones bajo budget,
  - stopping (cuándo “submit”),
  - calibración de confianza (si reward penaliza mala calibración).  
  Aquí SREG es ideal porque tiene verdad formal y reward definible.

Esto respeta el objetivo: SREG como “gimnasio” de investigación.

### Configuración por benchmark en BEFORE/AFTER

**DiscoveryBench (principal)**citeturn25view1turn14view2  
- Unidad de evaluación: task (goal + dataset(s) + metadata).  
- Runs: al menos 3 seeds (si no fijás temp=0).  
- Output: `pred_hypo` + (opcional) `pred_workflow`.  
- Score: HMS global + breakdown (contexts/variables/relations).  
- Reportar también tokens y ejecuciones (si tu agente usa Python) por task.

**CLadder (secundario)**citeturn21view0  
- Unidad: pregunta yes/no.  
- Split recomendado: sample estratificado por rung y query_type, p.ej. 1.000 ítems (para costos) + un “full run” ocasional.  
- Score: accuracy + log-loss/Brier (si guardás probas).  
- Análisis clave: delta por rung (1→2→3) y por variant (`q-hard`, `q-anticommonsense`, `q-nonsense`).citeturn21view0

**BixBench (duro)**citeturn17view0turn16view1  
- Unidad: pregunta (row) + capsule asociada.  
- Dos modos recomendables:
  - “Quick”: zero-shot + grading (rápido para iterar).citeturn17view0  
  - “Real”: agentic trajectories + postprocessing (más caro; el que querés para claims fuertes).citeturn17view0  
- Runs: k réplicas por pregunta (k=3/5) o al menos 2 semillas.  
- Score: open-answer accuracy (grader) y MCQ accuracy; reportar majority vote.  
- Reportar costo: tokens, runtime, ejecuciones de código y número de celdas generadas.

### Criterios de éxito

Proponé criterios cuantitativos “mínimos” y cualitativos “diagnósticos”. Ejemplo:

**Cuantitativos (mínimos, para decir “hay transferencia”)**
- DiscoveryBench: +ΔHMS relativo ≥ 10% (o +X puntos absolutos) con CIs que no crucen cero.  
- CLadder: mejora significativa en rung 2 y 3 (intervención y contrafactual) y especialmente en `q-nonsense` o `q-anticommonsense`.citeturn21view0  
- BixBench: +Δaccuracy (open-answer o MCQ) con igual o menor costo relativo (accuracy per token).

**Cualitativos (diagnóstico)**
- Menos “acciones de pánico” (ejecuciones irrelevantes).
- Trayectorias más cortas para igual score (mejor planificación).
- Mejor alineación entre hipótesis y evidencia (menos contradicciones).

## Riesgos, mitigaciones y recomendaciones de implementación en SREG

### Riesgo de sobreajuste a SREG

**Problema**: un solver puede mejorar en SREG explotando regularidades de la generación (formato, tipos de variables, patrones de tasks) sin adquirir habilidad científica general.

**Mitigaciones concretas**
- Holdouts fuertes dentro de SREG: dominios, tipos de DAG, plantillas, “semánticas” nunca vistas.
- Evaluaciones de robustez: CLadder `q-nonsense` como indicador de dependencia semántica.citeturn21view0  
- “Cross-benchmark sanity”: si sube SREG y no sube CLadder/DiscoveryBench, es señal de sobreajuste.

### Riesgo de sesgo e inestabilidad de LLM-as-judge

DiscoveryBench y BixBench usan judges LLM en partes del scoring (HMS, open-answer).citeturn14view2turn17view0

**Mitigaciones**
- Fijar: judge model, prompt, temperatura, y versionado.
- Votación: 3 judges o 3 runs (majority vote).
- Auditoría humana puntual para calibrar (muestra de 50 tareas y comparar con judge).
- Loggear “judge traces” igual que agent traces.

Si más adelante adoptás PaperBench, ese benchmark explícitamente discute judges y tiene recursos auxiliares para evaluar exactitud del judge (JudgeEval).citeturn22search4turn4view2turn15search11

### Riesgo de drift por versiones de datasets

BixBench cambia versiones y formato (v1.0 → v1.5), y eso puede romper comparaciones BEFORE/AFTER si no fijás versioning.citeturn16view1turn17view0

**Mitigación**: cada experimento debe registrar:
- benchmark name + version/tag/commit,
- hash del dataset descargado,
- docker image tag (BixBench),
- y config YAML.

### Recomendaciones prácticas de implementación

La meta es que “correr BEFORE/AFTER” sea un comando reproducible y que guarde todo para diagnóstico.

#### Archivos y directorios a crear

- `EVAL_DESIGN.md`  
  Documento “de investigación” donde quedan:
  - qué capabilities medimos,
  - benchmarks elegidos y por qué,
  - métricas y protocolos,
  - decisiones de versionado/judges.

- `experiments/`  
  Con plantilla por experimento:
  - `experiments/YYYYMMDD_<name>/`
    - `config.yaml`
    - `summary.json`
    - `summary.md`
    - `runs/` (jsonl de mensajes y tool calls)
    - `scores.csv`
    - `failure_modes.md`

Esto es coherente con lo que ya estabas armando en SREG para no perder hallazgos.

#### Interfaz de “benchmark adapter”

Crear una interfaz única en tu repo (pseudo-diseño):

- `BenchmarkAdapter.load_tasks(split, limit, seed)`
- `BenchmarkAdapter.run_task(task, solver, run_cfg) -> RunRecord`
- `BenchmarkAdapter.score_task(task, run_record) -> ScoreRecord`
- `BenchmarkAdapter.aggregate(score_records) -> Summary`

Y que todo produzca un formato común:

- `RunRecord`: trayectoria (mensajes + tool calls), outputs finales, costos (tokens), timestamps.
- `ScoreRecord`: métricas del benchmark (HMS, accuracy…), más métricas comunes (tokens, steps).
- `Summary`: agregaciones + intervalos + breakdown por tipo.

#### Scripts sugeridos

- `scripts/eval_external.py`  
  CLI unificada:
  - `--bench discoverybench|cladder|bixbench`
  - `--solver baseline|sreg_trained_ckpt_X`
  - `--split test`
  - `--seeds 3`
  - `--limit 100` (modo rápido)
  - `--output experiments/...`

- `scripts/compare_before_after.py`  
  Lee dos experimentos y produce:
  - deltas,
  - CIs (bootstrap),
  - breakdown por tags,
  - top failure modes antes vs después.

#### Cómo adaptar el solver a cada benchmark sin “hacer trampa”

Idea clave: **no hardcodear eval-types** ni reglas ad hoc; el solver debe operar como un agente general que:
- lee el caso,
- usa tools disponibles,
- actúa,
- entrega output según la interfaz del benchmark.

“Adaptar” debería significar:
- cambiar tool definitions / entorno,
- cambiar formato final requerido,
- mantener el mismo policy/scaffolding.

### Visualización del mapeo capability↔benchmark

```mermaid
flowchart LR
  subgraph SREG[Capacidades objetivo entrenadas por SREG]
    A[Active info gathering\n(obs/intervenciones)]
    B[Causal reasoning\n(do/confounding/mediation)]
    C[Uncertainty & calibration\n(distribuciones)]
    D[Hypothesis management\n(formular/validar)]
    E[Tool-use científico\n(análisis, evidencias)]
  end

  subgraph BENCH[Benchmarks externos]
    DB[DiscoveryBench\n(HMS + facets)]
    CL[CLadder\n(acc/logloss por rung)]
    BX[BixBench\n(acc + trayectorias)]
  end

  A --> DB
  D --> DB
  E --> DB

  B --> CL
  C --> CL

  A --> BX
  D --> BX
  E --> BX
  C --> BX
```

Esta estructura también te ayuda a diagnosticar: si solo mejora en CLadder pero no en DiscoveryBench/BixBench, probablemente entrenaste “razonamiento causal verbal” pero no planificación/evidencia; si mejora en DiscoveryBench pero no en CLadder, quizá mejoraste data analysis/semántica pero no causalidad formal; si mejora en BixBench pero no en los otros, puede ser robustez de tool-use y heurísticas de notebooks.

---

Si querés, el próximo paso lógico (ya con este marco) es redactar en `EVAL_DESIGN.md` una “primera versión” con: benchmarks elegidos, métricas exactas, configs fijas (jueces/versiones), y el primer set de scripts/adapters a implementar.