# Related Work — Corral / "AI scientists produce results without reasoning scientifically"

**Status:** CANON. Synthesis document for thesis.

**Paper:** Ríos-García, Alampara, Gupta, Mandal, Mannan, Aghajani, Krishnan, Jablonka.
"AI scientists produce results without reasoning scientifically."
arXiv:2604.18805v1 [cs.AI], 20 April 2026 (109 páginas).

**Code:** https://github.com/lamalab-org/corral (MIT license)
**Web:** https://lamalab-org.github.io/corral/
**Data:** https://huggingface.co/collections/jablonkagroup/corral
**Zenodo:** https://doi.org/10.5281/zenodo.19659851
**Full text extraction:** `research/notes/corral_paper_fulltext.txt` (4822 líneas)

**Afiliaciones:**
- Friedrich Schiller University Jena (IOMC, Center for Energy & Env Chemistry, Helmholtz)
- IIT Delhi (Civil Eng, School of Interdisciplinary Research, Yardi School of AI)

---

## TL;DR

- Evaluación masiva (25,000+ runs) de LLM agents como "cientificos" en 8 dominios de quimica/fisica/materiales
- **Hallazgo central:** el base model explica 41.4% de la varianza, el scaffold solo 1.5%.
- **Hallazgo critico:** los agentes fallan en razonamiento epistemologico:
  - 68% de traces ignoran evidencia recolectada
  - Solo 26% hacen revision de creencia refutada
  - Solo 7% hacen convergent multi-test evidence
- **Conclusion textual:** *"Until reasoning itself becomes a training target, the scientific knowledge produced by such agents cannot be justified by the process that generated it."*
- **Proponen:** *"each environment provides a reproducible task, tools, and a scoring function over agent trajectories, sufficient to define training signals on the reasoning process itself."*

**Esto es, literalmente, el argumento de SREG publicado por otro equipo.** Son aliados naturales, no competidores.

---

## Parte 1 — Justificacion de SREG: fallas de LLMs en investigacion

### El hallazgo fundamental

El paper descompone el desempeno de un agente LLM en dos componentes via latent factor modeling:

```
overall(at | st) = f(LLM(at | st), scaffold(at | st))
```

donde **LLM** es el base model y **scaffold** es el prompt/tool-routing/orchestration.

Usaron Bayesian hierarchical GLMs (M1-M8, seleccionado M7 por PSIS-LOO CV) para decomponer la varianza:

| Fuente | % varianza explicada |
|---|---|
| **Reasoning ability** (IRT-derived) | **41.4%** |
| Environment-scope interaction | 30.1% |
| **Scaffold** (ReAct vs tool-calling) | **1.5%** |
| Verbosity (brief/workflow/comprehensive) | 0.1% |

**Implicacion:** Toda la ingenieria de prompt/scaffold apenas mueve la aguja. Lo que importa es la capacidad de razonamiento del modelo base.

### Los 3 fallos epistemologicos cuantificados

Anotaron 773 traces manualmente + pipeline automatico con Claude 4.5 Sonnet (validado contra humanos: 95.7% agreement). Resultados agregados:

| Fallo | Prevalencia global |
|---|---|
| **Evidence non-uptake** (reunir evidencia y no usarla) | **68%** |
| **Untested claims** (hipotesis sin experimentos que las prueben) | **53%** (63% en hypothesis-driven) |
| **Belief never updated** (creencia nunca revisada en todo el trace) | **71%** |
| **Refutation-driven belief revision** (productive, no fallo) | solo 26% |
| **Convergent multi-test evidence** (productive) | solo 7% |

Por modelo (Table H.16):

| Patron | Claude-4.5 | GPT-4o | GPT-OSS-120B |
|---|---|---|---|
| Refutation-driven belief revision | 17% | 7% | 4% |
| Untested claim | 41% | 21% | 13% |
| Contradiction without repair | 48% | 44% | 72% |
| Convergent multi-test | 6% | 13% | 9% |
| Precommitted test plan | 81% | 77% | 35% |

**Incluso el mejor modelo (Claude 4.5):**
- 41% de sus traces tienen hipotesis nunca testeadas
- 81% de sus traces tienen planes de prueba comprometidos antes de recolectar evidencia
- Solo 17% tienen revision por refutacion

### Las interventions no arreglan el problema

Experimento critico (Section 4.9): les **inyectaron trayectorias exitosas previas** al contexto (hasta n-1 pasos de una corrida exitosa). En dominios workflow, 1-2 pasos inyectados alcanzan para superar baseline. En dominios hypothesis-driven, **ni siquiera trayectorias casi completas salvan el desempeno**. El modelo no aprende del contexto el buen razonamiento — ejecuta pero no adapta.

### Cita clave para la intro de tesis

> "Much current engineering effort focuses on scaffolding (prompting strategies, orchestration logic, tool interfaces), but the reasoning patterns we document persist across all scaffold conditions we tested, including extreme interventions. Addressing them will likely require changes to how base models are trained: a slower process than scaffold improvement, and one currently not guided by epistemic criteria. **The framework we introduce can supply such guidance: each environment provides a reproducible task, tools, and a scoring function over agent trajectories, sufficient to define training signals on the reasoning process itself.**"

**Accion para la tesis:** citar este paper en la Introduction como *la* motivacion empirica de por que entrenamos reasoning con RL. Es el paper mas reciente (abril 2026) con evidencia mas robusta (25K runs) que el training de razonamiento es necesario.

---

## Parte 2 — Los ejes de la ciencia y tipos de investigacion

El paper organiza 8 dominios en un espacio de dos ejes (Figure 1D). Esto es **util para pensar SREG** porque nuestras presiones evolutivas tambien cubren un espacio multidimensional.

### Eje 1: Epistemic demand (baja → alta)

Ordena dominios segun **que clase de razonamiento** requieren:

| Tipo | Definicion | Dominios Corral |
|---|---|---|
| **Workflow execution** | Solucion bien definida, agente ejecuta | ML pipeline, Adsorption Surface, AFM, Molecular Dynamics |
| **Strategic reasoning** | Busqueda combinatoria bajo constraints | Retrosynthetic Planning |
| **Hypothesis-driven inquiry** | Entender el espacio, formar hipotesis, probar, revisar | Spectroscopic Elucidation, Inorganic Qualitative Analysis, Circuit Inference |

**Mapeo a SREG:**
- **Workflow** → SREG no cubre esto (no es el punto)
- **Strategic** → parcialmente (solver elige que variables observar, pero no hay combinatoria compleja)
- **Hypothesis-driven** → **core de SREG**. Aca es donde entrenamos.

### Eje 2: Task scope (action space)

Dentro de cada dominio, escalan la dificultad modulando el **espacio de busqueda**:
- S1: pocas variables, respuesta directa
- S2, S3, S4: mas variables, ambiguedad, tradeoffs

**Mapeo a SREG:**
- Los seeds generan casos de distinta complejidad (cantidad de nodos SCM, heterogeneidad, confounding)
- **Podriamos adoptar explicitamente un eje "scope" en SREG:** S1=sistema simple, S4=sistema complejo multi-outcome

### Taxonomia de tareas en Corral (Figure 1D)

```
Low epistemic demand                                          High epistemic demand

ML-prediction, Adsorption,  Molecular    Retrosynthesis    Spectroscopic, Inorganic, Circuit
AFM, Molecular Sim          simulation                      Elucidation    Qualitative  Inference
[workflow execution]        [strategic]                     [hypothesis-driven inquiry]
```

### Relacion con nuestras presiones evolutivas

Nuestras 16 presiones (PROJECT.md) cubren cosas que el eje de epistemic demand NO distingue:
- Research taste
- Good research plan
- Knowing what's relevant
- Fine-grained question generation
- Knowing when a conclusion is premature vs well-founded

**Conclusion:** su eje es simpler que nuestras presiones, pero complementario. Podriamos **agregar una dimension "epistemic demand"** a nuestros escenarios de investigacion (`research/synthesis/investigation_scenarios_rubric.md`), clasificando cada uno segun si requiere workflow, strategic, o hypothesis-driven reasoning. Esto ayudaria a diagnosticar si SREG solo genera casos hypothesis-driven (bueno) o tambien workflow (malo — no genera presion).

### Taxonomia de subtasks

Dentro de cada tarea, decomponen en subtasks ordenados por **complejidad cognitiva**:

1. **Retrieval** — traer informacion (knowledge lookup)
2. **Execution** — correr procedimientos
3. **Reasoning** — inferir de evidencia
4. **Validation** — chequear que la respuesta es correcta

Miden Pass@5 por subtask. Finding: **ambos scaffolds exhiben la misma caida** de retrieval → validation. Scaffold no ayuda en reasoning/validation.

**Mapeo SREG:** Nosotros tambien podriamos descomponer las trayectorias del solver en estos 4 subtasks y medir donde falla. Actualmente medimos score terminal; granular ayudaria al diagnostico.

---

## Parte 3 — Tipos de tareas: simuladores vs mundos inventados

### Como Corral construye tareas

Cada dominio se implementa como un **environment** con:
- **Simulator/engine** verificable (LAMMPS, simulador termodinamico, microscopio real, circuitos calculados)
- **Tools** estandarizadas (docstrings con tags [BRIEF], [DETAILED], [EXAMPLES])
- **Task prompt** (goal, formato submission)
- **Scoring function** deterministica (match exact, R2 threshold, SMILES match, etc.)

**Ejemplos concretos:**

| Dominio | Engine/simulator | Ground truth |
|---|---|---|
| Molecular Simulation | LAMMPS (real!) | Self-diffusivity de SiO2 molten dentro del 20% |
| Inorganic Qual Analysis | Simulador termodinamico custom (equilibrios reales) | Iones correctos identificados |
| Circuit Inference | Computo matematico exacto de redes de resistores | Topologia y valores |
| AFM | Microscopio real | Power-law behavior redescubierto |
| Spectroscopy | NMR/MS/IR simulados | SMILES exacto |
| ML Prediction | Materials Project DB | R2 threshold |

**Caracteristica clave:** todos los dominios tienen **ground truth concreto y verificable**. El simulador o la matematica lo provee. NO hay LLM-as-judge para la verdad.

### Como SREG construye tareas

- **SCM** (Structural Causal Model) sintetico + expression compiler
- **Tools:** python_exec + observe_variable (del solver)
- **Brief** generado por LLM desde seeds de papers reales
- **Ground truth:** derivado del SCM via simulacion determinista

**Caracteristica clave:** nosotros tambien evitamos LLM-as-judge para la verdad. La diferencia es que **no usamos simuladores fisicos reales** — construimos mundos sinteticos.

### La pregunta del usuario: ¿la logica es parecida?

**Si, la logica filosofica es la misma:**

| Dimension | Corral | SREG |
|---|---|---|
| Verdad verificable matematicamente | Si (simulator output) | Si (SCM output) |
| Tools del agente | Dominio-especificas | Generales (python_exec) |
| Brief/task spec | **Muy especificado** | **Libre** (brief abierto, SQ golden como referencia) |
| Agente decide QUE investigar | **No** (la tarea te dice) | **Si** (core de SREG) |
| Agente decide COMO investigar | Si (que tools usar) | Si (que variables observar) |
| Scoring | Outcome (task-specific) | Outcome (SCM match) + Salience (cobertura) + Spam (no redundancia) |

**Diferencia fundamental (respondiendo tu pregunta):**

Corral tiene **tareas bien armadas** porque el agente NO decide que investigar. Le dicen: "identifica este cation" o "determina esta molecula". La variabilidad esta en **como** investigar (que experimentos correr, en que orden, con que presupuesto).

SREG agrega **una capa adicional de dificultad**: el agente tambien debe **enmarcar el problema**. Dado un brief abierto, decidir:
- ¿Que preguntas hacer?
- ¿Que variables son relevantes?
- ¿Que es relevante y que es ruido?
- ¿Cuando parar de investigar?

Esto es **mas cercano a investigacion real** donde el cientifico decide que preguntas vale la pena hacer. Es nuestra ventaja diferencial.

### Trade-off

- **Corral wins:** dominios reales con fisica/quimica verificable, transferencia directa a aplicaciones
- **SREG wins:** agente debe framear el problema, no solo ejecutarlo → presion evolutiva mas profunda
- **Juntos:** complementarios, no excluyentes

### Implicacion de diseño

Podriamos considerar un modo de SREG con **brief mas especificado** (tipo Corral) para ablation studies:
- "Dado este SCM, ¿cual es el efecto causal de X sobre Y?"
- Vs el brief libre: "Investiga este sistema"
- Comparar scores y behavioral patterns entre ambos → ver que presion agrega el brief abierto

---

## Parte 4 — Evaluacion del procedimiento via grafos epistemologicos

**Esta es la parte mas aplicable directamente a SREG.** Es la metodologia de behavioral analysis del paper.

### Pipeline de anotacion

1. **Sample traces** balanceadas por environment, modelo, scope (solo ReAct porque tiene reasoning explicito)
2. **Claude 4.5 Sonnet** anota en 2 stages con temperature 0.7:
   - Stage 1: labels de nodos (H/T/E/J/U/C) en ventanas de mensajes
   - Stage 2: labels de edges entre nodos
3. **Cada nodo incluye quote de soporte** + indice del mensaje fuente (grounding)
4. **Validacion automatica:** quote aparece en mensaje citado, edges conectan nodos validos
5. **Validacion humana:** 2 expertos anotaron 25 traces representativas
6. **Agreement:**
   - Human-Human: 92.6% (PABAK 0.853 — substantial)
   - Human-LLM: 95.7% (!)

### Los 6 tipos de nodos epistemologicos

| Simbolo | Nodo | Definicion |
|---|---|---|
| **H** | Hypothesis | Explicacion propuesta para el sistema |
| **T** | Test | Procedimiento experimental/analitico diseñado |
| **E** | Evidence | Observacion o resultado computacional |
| **J** | Judgment | Evaluacion cualitativa sobre evidencia |
| **U** | Update | Revision de creencia previa |
| **C** | Commitment | Decision o conclusion final |

### Los 6 tipos de edges

- **testing** — H usa T para probarse
- **observing** — T produce E
- **using / informing** — E informa J o H
- **contradicting** — E contradice H o J
- **competing** — H1 compite con H2
- **updating** — U transforma H en H2

### Los 7 productive motifs (Table H.14)

Templates de grafos que indican **razonamiento disciplinado**:

| Motif | Grupo | Grafo |
|---|---|---|
| **Evidence-led hypothesis generation** | Hypothesis handling | E → ... → H (evidencia antes, hipotesis despues) |
| **Hypothesis reranking** | Hypothesis handling | H1 competes-with H2 bajo nueva E |
| **Refutation-driven belief revision** | Hypothesis handling | H → T → E → U → H2 (Popperian!) |
| **Explore-then-test transition** | Inquiry control | Exploracion libre → formacion de H → testing |
| **Convergent multi-test evidence** | Inquiry control | H con T1, T2, T3 independientes → E |
| **Fixed hypothesis test tuning** | Inquiry control | H fijo, T iterativamente refinado |
| **Evidence-guided test redesign** | Inquiry control | J motiva nuevo T → nueva E |

### Los 10 reasoning breakdowns (Table H.15)

Templates de grafos que indican **razonamiento roto**:

**Hypothesis handling:**
| Breakdown | Definicion |
|---|---|
| **Untested claim** | H sin edge tests a ningun T |
| **One-sided confirmation** | C sin evidencia contradictoria considerada |
| **Contradiction without repair** | E contradicts H pero sin U ni H2 |
| **Premature commitment** | C sin T antes (compromiso sin prueba) |

**Evidence handling:**
| Breakdown | Definicion |
|---|---|
| **Evidence non-uptake** | E recolectada, sin edges usandola |
| **Disconnected evidence** | E sin ningun edge |
| **Unsupported judgment** | J sin E que la soporte |
| **Uninformative test** | T sin E observada |

**Inquiry control:**
| Breakdown | Definicion |
|---|---|
| **Fixed belief trace** | Trace sin ningun U |
| **Precommitted test plan** | C antes de recolectar E |
| **Stalled revision** | U genera H2 pero H2 nunca se testea |

### Como aplicar esto a SREG

**Paso 1: Adoptar su pipeline de anotacion.**
- Los traces del solver SREG ya son mensajes + tool calls + observations (mismo formato que Corral)
- Podemos correr Claude 4.5 Sonnet con sus prompts para anotar nuestros traces
- El pipeline es MIT license, codigo en `lamalab-org/corral/analysis/`

**Paso 2: Medir productive motifs vs breakdowns en trazas SREG.**
- Baseline: Qwen3-8B sin entrenar sobre SREG
- Target: Qwen3-8B post-RL-training sobre SREG
- Metrica: delta en prevalencia de cada motif/breakdown

**Paso 3: Reportar en la tesis.**
Un resultado tipo "Nuestro training RL reduce untested claims de 41% a X% y aumenta refutation-driven belief revision de 17% a Y%" seria MUY fuerte. Mas fuerte que solo "mejora accuracy en CLadder".

**Paso 4: Usar los motifs como reward shaping (opcional, fase posterior).**
Una vez validado que el behavioral analysis es confiable, podriamos agregar un bonus de reward por productive motifs y penalty por breakdowns. Esto fue lo que el propio paper sugiere: *"define training signals on the reasoning process itself."*

**Cuidado:** meter behavioral analysis en el loop de training es caro (LLM annotation cada rollout) y potencialmente hackeable. Empezar solo como **evaluacion offline** post-training.

### Relacion con nuestro Salience Map

Nuestro Salience Map dice "que preguntas son relevantes para el brief y el SCM". Es mas bien un piso de cobertura.

Su grafo epistemologico dice "que patron de razonamiento siguio el agente". Es mas bien estructura del proceso.

**Son complementarios:**
- Salience: ¿cubrio lo relevante? (what to investigate)
- Epistemic graph: ¿lo investigo bien? (how to investigate)

Podriamos reportar ambas metricas en la eval final de la tesis.

---

## Parte 5 — Corral como benchmark externo de SREG

### Por que integrarlo

1. **Es el unico benchmark que mide patrones epistemologicos**, no solo outcomes.
2. **Tiene 8 dominios con simuladores reales** (LAMMPS, microscopio AFM, etc.) — transferencia mas fuerte que CLadder/QRData.
3. **Complementa nuestros Tier 1 actuales:**
   - CLadder: causal formal, outcome-based
   - QRData: statistical/causal con datos, outcome-based
   - DiscoveryBench: hypothesis generation, LLM-judge
   - CRB: causal estimation, outcome-based
   - **Corral: full investigation process, process-based + outcome-based**
4. **Open-source, MIT, reproducible.**
5. **Tienen baselines publicos** (Claude 4.5, GPT-4o, GPT-OSS-120B) para comparar contra Qwen3-8B.

### Estructura de Corral como benchmark

```
Corral
  ├─ 8 environments (15+ scopes, 90+ tools)
  ├─ Standardized tools con docstrings tagged
  ├─ Scoring function por environment (deterministica en la mayoria)
  ├─ Framework REST API microservices:
  │    - CorralServer (host del environment)
  │    - CorralRunner (ejecuta agent, orquesta lifecycle)
  ├─ Agents soportados: ReAct, ToolCalling, LLMPlanner, Reflexion
  └─ Models via litellm (cualquier Chat Completions)
```

### Como integrarlo en qwen-benchmarks

**Opcion A: Integracion minima (outcome-only).**
- Instalar `corral` como dep, correr `CorralRunner` con Qwen3-8B via vLLM
- Scores terminales de los 8 environments
- Reportar como 5to benchmark externo
- Esfuerzo: ~1-2 dias

**Opcion B: Integracion completa (outcome + behavioral).**
- Todo A + correr pipeline de anotacion (Claude 4.5 sobre traces)
- Comparar productive motifs/breakdowns BEFORE vs AFTER
- Esfuerzo: ~1 semana

**Opcion C: Subset chico como smoke test.**
- Solo Circuit Inference (isolates logical reasoning, sin domain knowledge)
- O solo Inorganic Qualitative Analysis (el mas hypothesis-driven puro)
- Esfuerzo: ~2-3 dias

**Recomendacion:** empezar por **C** (Circuit Inference) para validar que el harness funciona, despues escalar a B.

### Consideraciones tecnicas

- **LLM backend:** Corral usa litellm, compatible con cualquier Chat Completions. Nuestro `ChatCompletionsClient` + vLLM encaja directo.
- **Tool calling:** Corral usa tool-calling nativo o ReAct. vLLM con `--tool-call-parser hermes` + Qwen3-8B deberia funcionar.
- **Sandbox:** algunos environments (LAMMPS, AFM) requieren setup pesado. **Skip esos para la primera integracion.**
- **Licencia:** MIT, sin issues.

### Comparacion con otros benchmarks Tier 1

| | CLadder | QRData | Discovery | CRB | **Corral** |
|---|---|---|---|---|---|
| Tamaño | 10K | 411 | 264 | 173 | 115 tasks, 786 subtasks |
| Dominios | Causal formal | Real data | Multi-domain | Causal | 8 quimica/fisica |
| Scoring | Deterministic | Deterministic | LLM-judge | Deterministic | **Deterministic + optional process** |
| Ground truth | Pearl 3 rungs | Numeric/MC | HMS | Causal est. | **Simulator/math** |
| Process eval | No | No | No | No | **Yes (epistemic graph)** |
| Reproducible | Si | Si | Parcial | Si | Si |
| Open source | Si | Si | Si | Si | Si (MIT) |

**Corral suma la unica dimension faltante: evaluacion del proceso.**

---

## Sobre la pregunta: verificabilidad y tarea bien armada

**Tu pregunta:** *"¿ellos siempre tienen algo verificable y dentro de todo esta bien armada ya la tarea no? no es como nosotros que tenemos SQ golden y despues un brief y una de las cosas a medir es si se hace bien las preguntas de investigacion"*

### Respuesta corta

Si, tenes razon. Corral es **mas acotado** que SREG. Pero comparten la filosofia core de verdad verificable (no LLM-as-judge para la verdad).

### Respuesta detallada

**Lo que comparten:**
- Ground truth matematico/deterministico (Corral via simulators, SREG via SCM)
- Scoring determinista para outcome
- Uso de LLM SOLO para anotacion/juicio cualitativo, NO para verdad

**Lo que NOS diferencia (a favor de SREG):**

En Corral:
- La tarea te dice **exactamente que investigar**: "identifica este cation", "determina esta molecula"
- La variabilidad esta en **como** investigar (que experimentos, que orden, que budget)
- Premia principalmente **razonamiento sobre un problema definido**

En SREG:
- El brief es **abierto**: "investiga este sistema" o "¿por que varia Y?"
- El agente decide **que preguntas hacer** (no se las dan)
- Premia ademas:
  - **Framing** — enmarcar el problema correctamente
  - **Question generation** — generar preguntas fine-grained relevantes
  - **Research taste** — saber que vale la pena investigar
  - **Salience coverage** — cubrir lo relevante sin spam irrelevante

### Implicacion filosofica

Corral mide una pieza: **razonamiento sobre un problema bien definido**. 

SREG mide esa pieza mas una adicional: **capacidad de definir el problema**.

La segunda es **mas cerca de investigacion cientifica real**, donde el cientifico no solo ejecuta un protocolo, sino que decide **que preguntas vale la pena formular**.

### Implicacion practica

1. **Corral es un piso util**: si no pasas Corral, definitivamente no podes hacer SREG. Corral valida que el modelo puede razonar cuando le das el problema.

2. **SREG es el techo**: pasar SREG implica razonar ademas de framear.

3. **Juntos forman una jerarquia de evaluacion:**
   - CLadder (razonamiento causal formal, problema cerrado) — nivel 1
   - QRData (analisis de datos con tareas especificas) — nivel 2
   - DiscoveryBench (generar hipotesis desde datos con goal dado) — nivel 3
   - Corral (investigacion completa con tarea definida) — nivel 4
   - SREG (investigacion abierta, agente define preguntas) — nivel 5

**Esta jerarquia es buen material para la tesis.** Argumenta que SREG entrena el nivel mas alto de la piramide y los otros benchmarks validan los niveles inferiores.

### Una posible convergencia futura

Podriamos agregar un modo "Corral-like" a SREG donde el brief sea mas especifico:
- Modo libre (actual): "Investiga este sistema"
- Modo dirigido (nuevo): "Estima el efecto causal de X sobre Y"
- Modo guiado (nuevo): "Determina si X es un confounder de Y→Z"

Esto nos permitiria **ablation studies**: ¿cuanta de la presion evolutiva viene del brief abierto, y cuanta del scoring multi-dimensional?

---

## Action items para SREG

### Inmediato (este worktree)

- [x] **Leer paper completo** → hecho, texto en `research/notes/corral_paper_fulltext.txt`
- [x] **Documentar en canon** → este doc
- [ ] Actualizar `research/README.md` para indexar este doc
- [ ] Actualizar `research/synthesis/thesis_evaluation_framework.md` para agregar Corral como Tier 1
- [ ] Actualizar `research/synthesis/external_benchmarks_transfer_analysis.md` con analisis comparativo

### Corto plazo (sprint de benchmarks)

- [ ] Clonar Corral en environment de testing: `git clone https://github.com/lamalab-org/corral.git`
- [ ] Correr Circuit Inference con GPT-4o (Azure) como smoke test — validar que el harness funciona
- [ ] Correr Circuit Inference con Qwen3-8B (cuando H100 disponible) — primer BEFORE run
- [ ] Decidir scope: Opcion A (outcome), B (outcome+behavioral), o C (subset)

### Medio plazo (post-entrenamiento RL)

- [ ] Correr mismo subset con Qwen3-8B post-SREG — AFTER
- [ ] Pipeline de anotacion epistemologica sobre traces BEFORE/AFTER
- [ ] Reportar delta en productive motifs y breakdowns

### Largo plazo (tesis writing)

- [ ] Cita critica en Introduction: "Ríos-Garcia et al. (2026) demuestran empiricamente que..."
- [ ] Seccion en Related Work comparando Corral vs SREG
- [ ] Figura conceptual: jerarquia de benchmarks (niveles 1-5)
- [ ] Resultados: tabla con behavioral metrics antes/despues de SREG training

---

## Referencias

### Paper
```bibtex
@article{rios-garcia2026ai,
  title   = {AI scientists produce results without reasoning scientifically},
  author  = {Mart{\~n}o R{\'i}os-Garc{\'i}a and Nawaf Alampara and Chandan Gupta and
             Indrajeet Mandal and Sajid Mannan and Ali Asghar Aghajani and
             N. M. Anoop Krishnan and Kevin Maik Jablonka},
  year    = {2026},
  journal = {arXiv preprint arXiv:2604.18805}
}
```

### Datasets HuggingFace (license MIT)
- `jablonkagroup/corral-environment-tasks` — tareas y especificaciones
- `jablonkagroup/corral-traces` — 80.9k traces de ejecucion (revision 67293e5)
- `jablonkagroup/corral-intervention-traces` — 6.4k intervention ablation
- `jablonkagroup/corral_runs_reports` — reports agregados
- `jablonkagroup/corral-QAs` — diagnostic knowledge + reasoning QAs
- `jablonkagroup/corral-QAs-reports` — resultados de QAs por modelo
- `jablonkagroup/corral-QAs-topic_reports` — breakdown por topico
- `jablonkagroup/corral-oss-trace-logprobs` — log-probabilidades token-level de GPT-OSS
- `jablonkagroup/rise_ai_scientists` — 227k papers de AI4Science (related work corpus)

### Codigo
- https://github.com/lamalab-org/corral (MIT)
- https://lamalab-org.github.io/corral/ (docs + interactive environment explorer + trace browser)
- https://doi.org/10.5281/zenodo.19659851 (Zenodo archive)

### Contactos
- Kevin Jablonka: mail@kjablonka.com (first author correspondence)
- N.M. Anoop Krishnan: krishnan@iitd.ac.in (second correspondence)

Ambos son potencialmente interesados en colaboracion dado el alineamiento filosofico.
