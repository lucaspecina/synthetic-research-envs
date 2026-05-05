# World design — Vertical 4: LLM-as-environment-designer (2023-2026)

> Reporte de investigación generado por agente Explore (2026-05-05). Parte del
> survey en `research/synthesis/world_design_techniques_survey.md`.
>
> Foco: estado del arte donde LLMs son el motor que genera entornos, tareas,
> currículos o reward functions. Patterns probados y anti-patterns.

---

## 1. Panorama general y taxonomía

El período 2023-2026 ha visto una explosión de sistemas donde **LLMs actúan como motores de diseño generativo** — no solo ejecutando tareas, sino *escribiendo las especificaciones de los entornos, las tareas y los incentivos* para que otros agentes (robóticos, virtuales, humanos) aprendan.

Tres dimensiones de taxonomía:

- **Qué genera el LLM**: especificaciones de entornos (código de simuladores), descripciones de tareas, funciones de reward, currículos de aprendizaje, policies de control.
- **Arquitectura**: single-agent, multi-agent (Architect + Validator + Crítico), o LLM-as-oracle en pipelines híbridos.
- **Verificación**: "LLM proposes, code verifies", verificación formal, multi-agent debate, evaluación empírica.

## 2. Sistemas concretos del estado del arte

### 2.1 GenSim — Wang et al. 2023, [arxiv:2310.01361](https://arxiv.org/abs/2310.01361)

- **Qué genera**: código Python de simulaciones y especificaciones de tareas para robótica.
- **Cómo funciona**: GPT-4 escribe código que define escenas, objetos, objectives. Dos modos: (1) goal-directed — dado target, generar curriculum hacia ello; (2) exploratory — iterar a partir de tareas previas. Amplía benchmark ManipulationSim de ~10 a >100 tareas.
- **Verificación**: ejecución en simulador (Isaac Gym/Bullet). Si simulación corre sin errores y el policy entrena, se asume validez.
- **Resultados**: transfer real-world mejorado 25% vs. baseline.
- **Patrón**: "Generate + Execute" con feedback de error de simulación.

### 2.2 RoboGen — Wang et al. 2023, [arxiv:2311.01455](https://arxiv.org/abs/2311.01455)

- **Qué genera**: task proposals, scene configurations (object placement + physics), training supervision (trajectories).
- **Cómo funciona**: ciclo propose-generate-learn:
  1. LLM propone skill novel.
  2. Genera escena + configuración.
  3. Descompone en sub-tareas.
  4. Elige estrategia (RL/motion planning/trajectory opt).
  5. Genera supervisión.
  6. Entrena.
- **Verificación**: simulación real-time (Genesis engine, NVIDIA); mide success rate; feedback a LLM sobre qué falló.
- **Anti-pattern detectado**: task collapse (LLM propone siempre la misma skill) → mitigado con diversity reward en task proposal.

### 2.3 Eureka — Ma et al. 2023, [arxiv:2310.12931](https://arxiv.org/abs/2310.12931) [PATTERN CRÍTICO]

- **Qué genera**: funciones de reward (código Python ejecutable).
- **Cómo funciona**:
  1. Dado environment code + task description → LLM zero-shot genera ~100 reward candidates.
  2. Ejecuta en paralelo (NVIDIA Isaac Gym, GPU-accelerated).
  3. Recopila stats de training (learning curves, sample efficiency).
  4. **Reward reflection**: LLM recibe summary de qué funcionó/falló + reasoning.
  5. Genera variantes de winners; vuelve a paso 2.
- **Verificación**: métricas empíricas hard (reward cuantitativo vs. baseline humano); 29 entornos × 10 morphologies.
- **Resultados**: 83% de tasks → mejor que experto humano; avg. 52% improvement.
- **Patrón**: **evolutionary refinement con LLM como mutator + simulador como fitness evaluator**.

### 2.4 Voyager — Wang et al. 2023, [arxiv:2305.16291](https://arxiv.org/abs/2305.16291)

- **Qué genera**: (1) curriculum de tasks, (2) código de skills (JavaScript via Mineflayer API), (3) task sequencing.
- **Cómo funciona** [PATRÓN: skill accumulation]:
  1. LLM propone next objective (automatic curriculum basado en exploration potential).
  2. LLM intenta escribir código; ejecuta en Minecraft.
  3. Si falla → incorpora error feedback, retrieves relevant skills, reintenta.
  4. Si éxito → code se almacena en skill library (indexed by semantic embedding de GPT-3.5).
  5. Próxima task: retrieval-augmented LLM + k skills similar semánticamente.
- **Curriculum mechanism**: minimizar "state visitation entropy" — privilegia tareas que exploran regiones nuevas.
- **Resultados**: 3.3x items, 2.3x distance, 15.3x faster tech milestones.
- **Patrón**: **lifelong learning con skill library + semantic retrieval + feedback loops**.

### 2.5 HoloDeck — Yang et al. 2024, [arxiv:2312.09067](https://arxiv.org/abs/2312.09067)

- **Qué genera**: layouts de escenas 3D, configuraciones de objetos con constraints espaciales.
- **Cómo funciona**:
  1. User prompt → GPT-4 zero-shot describe escena.
  2. Selecciona 3D assets de Objaverse basado en descriptions.
  3. **LLM genera spatial relational constraints**.
  4. Optimiza layout para satisfacer constraints via constraint satisfaction solver.
- **Verificación**: user study (680 participantes); comparación vs. ProcTHOR; embodied agent evaluation.
- **Anti-pattern**: hallucinated objects (LLM imagina algo no en Objaverse) → mitigado con asset existence check.

### 2.6 Genie & Genie 2 — DeepMind, [arxiv:2402.15391](https://arxiv.org/abs/2402.15391) + Genie 2 (Dec 2024)

- **Qué genera**: entornos 3D interactivos, dinámicas físicas, personajes con animación.
- **Cómo funciona**: foundation world model (NO LLM-as-designer). Transformer autoregresivo en latent space de videos de internet sin label. Latent action space.
- **Genie 3 (Aug 2025)**: 24 fps real-time, consistency minutes-long, diverse environments.
- **Patrón novedoso**: **foundation world model** sin LLM explícito.
- **Ventaja vs. LLM-as-designer**: grounded en datos reales; menor risk de hallucinations.
- **Limitación**: solo genera, no entiende tareas abstractas.

### 2.7 AI Scientist — Lu et al. 2024, [arxiv:2408.06292](https://arxiv.org/abs/2408.06292)

- **Qué genera**: hipótesis científicas → código experimental → análisis → manuscripts.
- **Cómo funciona**:
  1. LLM propone hipótesis novedosa en ML.
  2. Genera código Python end-to-end.
  3. Ejecuta, recolecta resultados.
  4. LLM analiza datos → genera manuscript con figuras.
  5. Simulated peer review → feedback → iterate.
- **Verificación**: código se ejecuta; resultados validados numéricamente; peer review por otro LLM.
- **Anti-pattern**: trivial experiments → curriculum que incentiva novelty.
- **Patrón**: **scientific hypothesis generation con closed-loop empirical validation**.

### 2.8 Auto MC-Reward — Li et al. 2024, [arxiv:2312.09238](https://arxiv.org/abs/2312.09238)

- **Qué genera**: dense reward functions para Minecraft.
- **Cómo funciona**:
  1. Reward Designer (LLM) escribe código reward.
  2. Reward Critic (LLM) valida: sintaxis, semántica, consistency con task.
  3. Trajectory Analyzer (ejecuta RL agent) evalúa reward contra trajectory.
  4. Feedback loop → LLM refina reward.
- **Patrón**: **multi-agent verification pipeline** (Designer + Critic + Empirical evaluator).

### 2.9 AutoGen — Microsoft 2023, [arxiv:2308.08155](https://arxiv.org/abs/2308.08155)

- **Qué genera**: orchestration of multi-agent conversation.
- **Cómo funciona**: roles (AssistantAgent, UserProxyAgent, code executor). Agents comunican en dialogue, se delegan tareas. Tool use integrado en conversation loop.
- **Aplicación a SREG**: blueprint para diseñar conversation protocol entre Architect, Validators, Question Designer.

### 2.10 CAMEL — Li et al. 2023, [arxiv:2303.17760](https://arxiv.org/abs/2303.17760)

- **Qué genera**: task instances y conversational data via role-playing.
- **Cómo funciona**: dos agents (AI Assistant + AI User) con roles complementarios. User instruye al Assistant; Assistant responde. LLM guía interacción via inception prompting.
- **Patrón**: **role-playing as data generation mechanism** + inception prompting para quality control.

### 2.11 ChatDev — Qian et al. 2023, [arxiv:2307.07924](https://arxiv.org/abs/2307.07924)

- **Qué genera**: software completo (design docs, code, tests) via multi-agent team.
- **Cómo funciona**: organization roles (CEO, CTO, Programmer, Tester, PM). Chat chain especifica qué comunica cada role. LLM instances ejecutan roles, comunican en NL.
- **Verificación**: code se compila/ejecuta; test suite valida; reproducible outputs.
- **Patrón**: **organizational hierarchy encoded en chat chain** (similar a SREG).

## 3. Patterns transversales probados

### Pattern 1: "LLM proposes, code verifies"
- LLM genera especificación.
- Sistema híbrido ejecuta/simula.
- Feedback: compilación, ejecución, métricas.
- Ejemplos: GenSim, Eureka, RoboGen, Auto MC-Reward.
- **Fortaleza**: grounding rápido en realidad; detecta hallucinations sintácticos.
- **Debilidad**: hallucinations semánticas pasan (task plausible pero incorrecta).

### Pattern 2: Evolutionary refinement (Eureka-style)
- Generación batch de candidates.
- Ejecución paralela en GPU-accelerated simulator.
- Recopila observables (learning curves, convergence).
- LLM recibe *structured feedback* con reflection.
- Genera mutantes de winners; repite.
- **Transferible a SREG**: Architect genera WorldSpec batch → Validators evalúan → envían structured feedback → Architect breeds top specs.

### Pattern 3: Multi-agent debate & verification
- Architect propone.
- Múltiples Validators (different heuristics) evalúan.
- Conflict resolution via discussion o formal voting.
- Ejemplos: Auto MC-Reward, ChatDev.
- **Beneficio**: detecta subtler errors; diversidad reduce single-bias.

### Pattern 4: Skill library accumulation (Voyager)
- Successful outputs se almacenan con embeddings semánticos.
- Novo task → retrieval de k-nearest skills.
- LLM compone/adapt existing skills antes de generar de novo.
- **Transferible a SREG**: biblioteca de WorldSpecs ganadores; LLM diseñador retrieves similares antes de generar nuevo.

### Pattern 5: Curriculum learning & task proposal
- LLM propone qué task es interesante/solvable ahora.
- Optimiza para exploration potential, diversity, solvability.
- Feedback loop: agent's performance informa próxima proposal.
- Ejemplos: Voyager (entropy minimization), RoboGen (skill diversity).

### Pattern 6: Semantic retrieval & indexing
- Cada output → embeds (CLIP, sentence transformers).
- Novo input → retrieve relevant priors.
- Ejemplos: Voyager (skill library), HoloDeck (asset selection).

## 4. Top 5 patterns transferibles a SREG

### 1. Eureka's evolutionary refinement of specifications
Architect genera batch (5-10) de WorldSpecs en lugar de uno solo. Validators ejecutan cada uno en paralelo → recopilan cuantitativas (¿cuántas soluciones existen? ¿cuán difíciles? ¿varianza?). Devuelven structured feedback: `{stability: 0.8, diversity: 0.6, solvability: 0.9, anomalies: ["trivial_path"]}`. Architect recibe + utiliza breeding entre top-2 specs. Repeat 2-3 ciclos.

**Ventaja vs. SREG actual**: explota parallelism; feedback cuantitativo (no solo "passes/fails").

### 2. Multi-agent verification pipeline (Auto MC-Reward style)
Architect genera WorldSpec. Validators con expertise distinto:
- **Validator 1 (sintaxis)**: parsea, type-checks, compila.
- **Validator 2 (semántica)**: ejecuta small-scale; detecta NaN, infinities, divergence.
- **Validator 3 (matemática)**: ODEs well-posed (Picard-Lindelöf, stability); SCMs son DAG.
- **Validator 4 (research intent)**: ¿realmente explora el fenómeno reclamado?

Resolution: multi-agent debate con LLM arbiter si hay conflicto.

**Ventaja**: cada validator es especialista; reduce single-point-of-failure.

### 3. Skill library de winning WorldSpecs
Persistent store de `{WorldSpec, performance_metrics, semantic_embedding, date_created}`. Cuando Architect genera nueva tarea, primero retrieves top-5 similar specs from history. Architect puede: (a) reuse, (b) adapt (mutate), (c) combine múltiples.

**Beneficio**: histórico institucional de buenas specs; accelera future design; detecta if trying to re-generate known world.

**Implementación**: SQLite + faiss indexing for embedding search.

### 4. Curriculum learning para research tasks
Insight de Voyager: task proposal debe maximizar "exploration potential", no ser random. Question Designer propone qué fenómeno es "interesting NOW" basado en:
- Solver performance trajectory
- Diversity of solved tasks
- Known difficulty (easier → harder)
- Skill composition (¿puede construir sobre discovers anteriores?)

**Output**: next task es adaptive; no fixed curriculum.

### 5. Closed-loop empirical validation (AI Scientist style)
No confiar solo en simulación forward-checking; generar solver, ejecutar, evaluar solver outputs.

WorldSpec genera task → Solver LLM intenta → evalúa solución contra ground truth o emergent properties → feedback: "Solver got stuck", "Solver hallucinated", "Task too easy" → devuelve a Architect.

**Ventaja**: captura "plausible pero incorrecto" tasks que forward-checking miss.

## 5. Anti-patterns documentados y mitigaciones

### Anti-pattern 1: hallucinated/ungrounded specifications
- **Síntoma**: LLM genera spec que parsea/simula pero no es realista.
- **Causa**: LLM trained on papers, no necesariamente on grounded physics.
- **Detección**: parsing + type checking; sanity checks; empirical validator (si diverge rápido → hallucination).
- **Mitigación**: provide LLM con curated library de "valid components"; LLM compone antes de generar de novo.

### Anti-pattern 2: specification gaming / reward hacking
- **Síntoma**: Solver descubre loophole en task spec.
- **Causa**: spec incompleta; LLM no anticipó edge case.
- **Detección**: Validator ejecuta "adversarial solver"; observa si solution es "spirit of intent".
- **Mitigación**: iterative refinement; diverse solvers reveal different gaming vectors; formal specification.

### Anti-pattern 3: task collapse / mode collapse
- **Síntoma**: Architect genera siempre la misma task.
- **Causa**: gradient local; reward signal por "valid task" sin diversity penalty.
- **Detección**: embedding similarity de generated specs.
- **Mitigación**: diversity reward; curriculum que explicitly proposes novel phenomena; skill library diversity metric.

### Anti-pattern 4: task contamination via training data
- **Síntoma**: LLM-generated task muy similar a known benchmark.
- **Causa**: LLM trained on open internet; memorizes papers.
- **Detección**: BERTScore / embedding similarity contra existing benchmarks.
- **Mitigación**: blacklist known benchmarks; explicit instruction "avoid these phenomena".

### Anti-pattern 5: plausible but wrong (PBW) task specs
- **Síntoma**: spec sounds reasonable, simulator runs, but task intent es incorrecto.
- **Causa**: forward validation insuficiente; LLM-as-judge fooled.
- **Detección**: empirical solver evaluation; sanity test contra closed-form solutions; multiple independent verifiers.
- **Mitigación**: require ground truth o formal proof; SMT solvers / theorem provers como validadores auxiliares.

### Anti-pattern 6: shallow / trivial tasks
- **Síntoma**: tasks too easy.
- **Causa**: LLM biased toward solvable specs (cautious).
- **Detección**: medir solver convergence time, solution complexity.
- **Mitigación**: explicit difficulty target; solver feedback (si too fast → reject); curriculum gradual.

## 6. Conclusión y recomendaciones para SREG

SREG ya implementa varios patrones clave (multi-agent validation, feedback loops). La oportunidad está en:

1. **Adoptar evolutionary refinement**: generar batches; evaluación paralela; structured feedback al Architect.
2. **Especializar validators**: cada uno con expertise (sintaxis, semántica, matemática, intent).
3. **Mantener skill library histórico**: embeddings de buenas specs; retrieval para future design.
4. **Implementar closed-loop empirical testing**: ejecutar solver realmente; capturar PBW.
5. **Formalizar anti-patterns como red-team checklist**: systematic testing contra hallucinations, gaming, collapse, contamination.

El campo converge en que **la verificación es cuello de botella crítico**. Las soluciones más robustas combinan LLM-generated specs con simulación empírica + formal methods + multi-agent consensus.

## 7. Fuentes consolidadas

**Task generation & environment design**:
- [GenSim — arxiv:2310.01361](https://arxiv.org/abs/2310.01361)
- [RoboGen — arxiv:2311.01455](https://arxiv.org/abs/2311.01455)
- [HoloDeck — arxiv:2312.09067](https://arxiv.org/abs/2312.09067)

**Reward function design**:
- [Eureka — arxiv:2310.12931](https://arxiv.org/abs/2310.12931)
- [Auto MC-Reward — arxiv:2312.09238](https://arxiv.org/abs/2312.09238)

**Embodied agents & curriculum**:
- [Voyager — arxiv:2305.16291](https://arxiv.org/abs/2305.16291)
- [MineDojo — arxiv:2206.08853](https://arxiv.org/abs/2206.08853)
- [Inner Monologue — arxiv:2207.05608](https://arxiv.org/abs/2207.05608)
- [RoboCasa — arxiv:2406.02523](https://arxiv.org/abs/2406.02523)

**Code & policy generation**:
- [Code as Policies — arxiv:2209.07753](https://arxiv.org/abs/2209.07753)
- [ProgPrompt](https://link.springer.com/article/10.1007/s10514-023-10135-3)

**World models & foundation models**:
- [Genie — arxiv:2402.15391](https://arxiv.org/abs/2402.15391)
- [Genie 2 (DeepMind blog)](https://deepmind.google/blog/genie-2-a-large-scale-foundation-world-model/)

**Multi-agent systems & orchestration**:
- [AutoGen — arxiv:2308.08155](https://arxiv.org/abs/2308.08155)
- [CAMEL — arxiv:2303.17760](https://arxiv.org/abs/2303.17760)
- [ChatDev — arxiv:2307.07924](https://arxiv.org/abs/2307.07924)
- [MetaGPT — arxiv:2308.00352](https://arxiv.org/abs/2308.00352)

**Scientific discovery & hypothesis generation**:
- [AI Scientist — arxiv:2408.06292](https://arxiv.org/abs/2408.06292)
- [Reflexion — arxiv:2303.11366](https://arxiv.org/abs/2303.11366)

**Data generation & task bootstrapping**:
- [Self-Instruct — arxiv:2212.10560](https://arxiv.org/abs/2212.10560)

**Verification & robustness**:
- [Formal Verification of LLM Code — arxiv:2507.13290](https://arxiv.org/abs/2507.13290)
- [LLM Red-Teaming — arxiv:2508.04451](https://arxiv.org/abs/2508.04451)
