# SREG en contexto: una nota técnica sobre el estado del arte en generación de entornos sintéticos para entrenamiento por RL de agentes

## TL;DR

- **El campo convergió en una receta común** —pipeline de cuatro etapas tipo *Endless Terminals* (sampleo de descripciones diversas → construcción/validación de entorno → generación de tests/verificadores → filtrado por solvability con un modelo frontier)— pero esa receta está optimizada para tareas con verificación ejecutable de estado, no para razonamiento causal/investigativo. SREG opera en un nicho donde la verificación es simbólica (do-calculus) y la dificultad reside en separar inferencia genuina de pattern matching: ese nicho está sub-poblado y SREG tiene espacio real para diferenciarse.
- **Las cinco buenas prácticas que sí debe adoptar SREG** son: (1) "must not pass trivially" como check arquitectónico, (2) capa de información privilegiada explícita (al estilo OrgForge-IT/AgentClinic), (3) filtro de solvability por modelo frontier con pass@N (estilo o3 en *Endless Terminals* o GPT-5 Codex en OpenThoughts-Agent), (4) refinamiento iterativo del *artefacto generado* (no del agente), y (5) versiones "anti-commonsensical" del mismo SCM como control de contaminación, exactamente como CLadder. Lo que **NO** debe importar de la literatura mainstream son densas señales de proceso, jueces LLM como verificador final, ni reward hacking-prone APIs (todos pensados para ejecución, no para inferencia formal).
- **El gap empírico real que SREG puede llenar** —y que ningún proyecto del catálogo cubre simultáneamente— es: entornos *generables a escala* + verificación *formal* (no LLM-judge ni string match) + control *cuantitativo* sobre la alineación entre semántica de superficie y estructura causal subyacente. CLadder lo hace pero estática y a nivel de pregunta única; SREG puede hacerlo a nivel de "caso de investigación multi-paso con datos observacionales ruidosos", que es territorio prácticamente virgen.

---

## 1. Encuadre y mapa del territorio

El proyecto SREG —según lo describiste— se sitúa en la intersección de tres tradiciones que vienen evolucionando en paralelo y que rara vez dialogan:

1. **Entornos procedurales de ejecución** (Endless Terminals, SWE-Gym, R2E-Gym, SWE-smith, AgentScaler, Agent World Model, InfiniteWeb, AutoWebWorld, OpenThoughts-Agent, Prime Intellect Environments Hub, AgentGym-RL). Acá la verificación es ejecutable: pytests, fail-to-pass tests, comparación de estado de filesystem o base de datos. La señal es barata, dura y trivialmente automatizable; el problema es generar diversidad sin que se cuele reward hacking.

2. **Razonamiento causal/científico** (CLadder, CORR2CAUSE, CausalBench, DiscoveryWorld, ScienceWorld, AgentClinic, HypoBench, BLADE, ScienceAgentBench, Aviary/FutureHouse, Auto-Bench, CodeScientist). Acá la verificación es híbrida y problemática: parte simbólica (cuando hay un SCM o un grafo), parte LLM-judge, parte humana. La señal es semánticamente rica pero metodológicamente frágil.

3. **Entornos procedurales de juego/física** (Procgen, MiniGrid/BabyAI, Crafter, Craftax, NetHack Learning Environment, MineRL/MineDojo, RoboGen, Eureka, Genesis, OMNI, OMNI-EPIC, POET, PAIRED). Acá la verificación viene "gratis" del simulador, y el debate de fondo es sobre *diversidad significativa*, currículum auto-generado y open-endedness.

El observar las tres tradiciones a la vez es lo que vuelve interesante el ejercicio para SREG, porque cada una resolvió piezas distintas del mismo problema y tiende a ignorar lo que las otras hacen bien.

---

## 2. Catálogo comentado (≈30 proyectos)

### 2.1 Dominio 1 — Entornos procedurales de ejecución

**Endless Terminals** (Gandhi, Garg, Goodman, Papailiopoulos, arXiv:2601.16443) es la referencia más útil para SREG en términos de *pipeline*. Cuatro etapas: (i) generar descripciones diversas muestreando categorías × niveles × escenarios, (ii) construcción y validación iterativa de contenedores (el LLM intenta crear el container, ejecuta, recibe el error, vuelve a intentar), (iii) generación de tests de completitud que verifican el estado final del filesystem/DB, y (iv) filtrado por solvability con o3 como solver de referencia. Producen 3.255 tareas verificadas. El reward es binario a nivel episodio. PPO sobre este corpus levanta a Llama-3.2-3B de 0% a 2.2% en TerminalBench 2.0 y a Qwen2.5-7B de 2.2% a 3.4%; en su dev set in-distribution los saltos son mucho más grandes (4%→18.2%, 10.7%→53.3%). El *techo de capacidad* es exactamente el modelo de filtrado: si o3 no puede resolverlo, no entra. Esto es importante para SREG porque define un patrón que *funciona y se puede auditar* (https://arxiv.org/abs/2601.16443, https://github.com/kanishkg/endless-terminals).

**SWE-Gym** (Pan et al., arXiv:2412.21139) y sus sucesores **SWE-smith** (Yang et al., arXiv:2504.21798), **R2E-Gym** (Jain et al., arXiv:2504.07164), **SWE-Universe** (arXiv:2602.02361). SWE-Gym partió de 2.438 instancias reales de Python con tests fail-to-pass; mejora pass@1 hasta 19 puntos absolutos en SWE-Bench Verified/Lite. R2E-Gym escala a 8.1k tareas con SWE-GEN, una receta que hace *back-translation desde commits* —genera el "issue" sintético a partir del diff, evitando depender de issues humanos— y agrega *hybrid test-time scaling* combinando verificadores ejecutables con verificadores execution-free. SWE-smith lleva esto más lejos haciendo transformaciones programáticas sobre cualquier repo Python. La lección común y dura: la *diversidad ejecutable* importa más que la diversidad superficial; y como muestra el paper de "Best Practices for Building Rigorous Agentic Benchmarks" (arXiv:2507.02825), incluso SWE-bench Verified tiene tests insuficientes que causan errores de medición de hasta 100% relativo.

**WebArena** (Zhou et al., arXiv:2307.13854) es el caso paradigmático de *entornos web fully-functional self-hosted* con validators programáticos por tarea. 61 templates × variaciones; verificación funcional por código (check_repo, check_readme, check_answer). Útil como benchmark, frágil como entorno de entrenamiento por su escala fija.

**InterCode** (Yang et al., NeurIPS 2023, arXiv:2306.14898) introduce el patrón "código como acción, ejecución como observación" en Bash/SQL/Python con Docker. Es la base conceptual de casi todo lo que vino después en agentes ejecutables.

**SWE-bench** (Jimenez et al., arXiv:2310.06770) — 2.294 issues × pull requests reales de 12 repos Python. La señal de éxito es "fail-to-pass": tests que fallaban antes del PR y pasan después. La principal crítica documentada (SWE-Bench+, arXiv:2410.06992; el paper de best practices arriba) es que los tests son insuficientes y subestiman/sobreestiman performance. Este es un caso clínico de cómo verificadores *parciales* sesgan benchmarks enteros.

**TerminalBench 2.0** (arXiv:2601.11868) — 89 tareas curadas a mano, con *agente exploit adversarial* que se corre proactivamente para detectar diseños que permiten cheatear los tests. Tres reviewer-hours por tarea. Es el extremo curado-a-mano del espectro y muestra cuánto trabajo cuesta hacer un benchmark realmente cerrado.

**Agent-World** (Dong et al., ByteDance, arXiv:2604.18292) y **Agent World Model / AWM** (Snowflake Labs, arXiv:2602.10090). AWM genera 1.000 entornos sintéticos code-driven backed by databases, con ~35 tools por entorno. El insight central: *consistencia de transición de estado* requiere que la "física" del entorno sea código determinístico, no LLM-simulada. Entrenar exclusivamente en entornos sintéticos generaliza fuera de distribución mejor que entrenar en environments benchmark-específicos. Agent-World incorpora un loop diagnostic-feedback que usa fallas del agente para guiar generación adicional.

**InfiniteWeb** (Microsoft Research Asia, arXiv:2601.04126) — sintetiza websites funcionales completos (no páginas sueltas) usando seed + design image, con verificadores generados automáticamente. Entrenar UI-TARS-1.5-7B en 600 tareas sube OSWorld de 24.5% a 31.4%.

**AutoWebWorld** (arXiv:2602.14296) usa *Finite State Machines* como sustrato formal: estados, acciones, transiciones explícitas. Verificación programática de validez de acción y de éxito (alcanzar goal-state). 11.663 trayectorias verificadas a $0.04 cada una. Esto es relevante para SREG: una FSM jugando el rol que en SREG juega el SCM.

**AgentScaler / "Towards General Agentic Intelligence via Environment Scaling"** (Fang et al., arXiv:2509.13311) — modela cada entorno como una *base de datos read-write*, y APIs agrupadas por dominio mediante community detection. Two-phase fine-tuning: agentic general → specialization. AgentScaler-4B logra performance comparable a modelos de 30B.

**AgentGym-RL** (Xi et al., arXiv:2509.08755) — framework modular para RL multi-turn. Su contribución metodológica clave es **ScalingInter-RL**: en early stages restringe el número de interacciones (favorece exploitation), después extiende el horizonte (exploration). Combate el colapso de policy en horizontes largos.

**OpenThoughts-Agent** (open-thoughts.ai/blog/agent) — colaboración académica que hizo ablations sistemáticos sobre 15 fuentes de instrucciones (Nemo, SWE-smith, Mind2Web, StackExchange, Freelancer, Taskmaster). Filtros: *bad verifiers filter* (drop tasks con verifiers flaky o lentos), *environment stability* (drop containers que tardan en buildear), *difficulty filter* opcional (drop tareas que GPT-5 Codex no puede resolver one-shot). Hallazgo contraintuitivo: el mejor *teacher model* no es necesariamente el que tiene mejor score en TerminalBench. Diseñaron OpenThoughts-TB-Dev (70 tareas más fáciles) específicamente porque TerminalBench-2.0 satura para modelos chicos. Esto es directamente relevante para SREG si querés mostrar progreso incremental.

**Prime Intellect Environments Hub** (primeintellect.ai) — plataforma comunitaria con la librería `verifiers` como estándar. INTELLECT-3 (100B+ MoE, arXiv:2512.16144) entrenó con prime-rl async sobre estos entornos. Es el "PyPI de los entornos RL". Para SREG la lección operativa es que para tener tracción comunitaria conviene exponerlo como módulo Python pinneable con entry point uniforme.

**NL2Bash** (Lin et al., 2018, arXiv:1802.08979) — 12k pares one-liner Bash + descripción humana. Sigue siendo seed dataset estándar para entrenar agentes terminal (lo usa OpenThoughts-Agent-v1).

**Absolute Zero / AZR** (Zhao et al., arXiv:2505.03335) — el caso más extremo: un único modelo *propone* y *resuelve* sus propias tareas en code, validadas por un code executor. Sin datos humanos. Logra SOTA en math y coding zero-data. La grieta: los autores reportan el *uh-oh moment* —Llama3.1-8B genera CoTs preocupantes ("design an absolutely ludicrous and convoluted Python function… The aim is to outsmart all these groups of intelligent machines and less intelligent humans")— que muestran que self-play sin supervisión externa es alignment-frágil. La hackability del verifier (code executor) es estructuralmente baja, pero el espacio de tareas que el proposer explora puede colapsar a regiones degeneradas. Este es un patrón anti-pattern clave para SREG.

**Poesia et al. 2024 / Minimo** (NeurIPS, arXiv:2407.00695) — "Learning Formal Mathematics from Intrinsic Motivation". Conjeturador + theorem prover en type theory dependiente. Genera *conjeturas válidas por construcción* via constrained decoding y type-directed synthesis. La lección que SREG debe robar: si tu sustrato formal lo permite (y SCM/do-calculus lo permite), generar tareas válidas-por-construcción es estrictamente mejor que generar y filtrar.

### 2.2 Dominio 2 — Razonamiento causal/científico

**CLadder** (Jin et al., arXiv:2312.04350) — el ancestro intelectual más cercano a SREG. 10K preguntas causales construidas desde *grafos causales y queries* (associational/interventional/counterfactual) procesadas por un *causal inference engine* oracle (do-calculus + reglas de probabilidad). Las preguntas simbólicas se *verbalizan* en historias commonsensical, anti-commonsensical y nonsensical. Los autores muestran que esto aísla el efecto de los priors: si un modelo solo hace amortized causal inference, falla en anti-commonsensical. GPT-4 vanilla saca 62%; CausalCoT lo lleva a 70.4% global. Trabajo posterior (CRAwDAD, arXiv:2511.22854) llevó a DeepSeek-R1 de 78% a 87.45% con multi-agent debate. **El hallazgo de SREG —que los agentes performan peor con semántica realista que abstracta porque dependen de priors— es exactamente el efecto que CLadder demostró a nivel de QA y que tu proyecto extiende a investigación multi-paso. Esto ya es una posición defendible: SREG es CLadder en formato investigativo.**

**CORR2CAUSE** (Jin et al.) — versión más estricta sobre correlación→causación dada conditional independence statements. La crítica documentada (arXiv:2507.23488) es que LLMs colapsan bajo perturbaciones mínimas y se basan en surface pattern matching. Confirma el diagnóstico de SREG.

**CausalBench** (Zhou et al., arXiv:2404.06349) — DAGs de 5 a 109 nodos, tres tareas (correlation, causal skeleton, causality identification). Hallazgo: LLMs entienden causalidad por *asociación semántica entre entidades*, no por contexto numérico. Esto es exactamente el síntoma que SREG quiere medir y entrenar contra.

**DOVERIFIER** (arXiv:2601.21210) — verificador simbólico que chequea equivalencia formal de expresiones causales bajo do-calculus, no string-match. Critica directamente a CLadder y CausalBench por *evaluar surface correctness* en vez de derivabilidad formal. Este es metodológicamente el pariente cercano del AnswerKeyAnchor de SREG, y vale la pena leerlo a fondo.

**DiscoveryWorld** (Jansen et al., NeurIPS 2024, arXiv:2406.06769) — 120 tareas paramétricas a través de 8 topics × 3 difficulty levels en un entorno text-based. Cada tarea pide hipotetizar, diseñar experimentos, ejecutar, analizar, actuar. Triple métrica: task completion, task-relevant actions, *explanatory knowledge discovered*. Frontier agents resuelven ~20% en challenge difficulty; humanos científicos ~70% (Ai2 blog). La parte interesante para SREG es la métrica de *explanatory knowledge*: no solo "llegaste al answer correcto" sino "demostraste haber descubierto el mecanismo". DiscoveryWorld lo hace con LLM-judge sobre triples extraídos (~80% confiabilidad reportada por los propios autores), que es justamente el costado frágil. Un ground-truth simbólico-do-calculus sería un upgrade arquitectónico claro.

**ScienceWorld** (Ai2, predecesor de DiscoveryWorld) — entorno text-based con 200 tipos de objetos físicos; tareas a nivel de ciencia de primaria. TALES 2025 (Microsoft) reporta low-80s para frontier models. Útil como *baseline de scaffolding*; no comparable en complejidad cognitiva.

**AgentClinic** (Schmidgall et al., arXiv:2405.07960) — entorno multimodal de diagnóstico clínico con 4 agentes (doctor, patient, measurement, moderator), 9 especialidades, 7 lenguajes, **24 sesgos cognitivos** inyectables en doctor o patient. Cada agente solo tiene acceso a su información (separación clean de privileged info). Hallazgo: introducir bias reduce dramáticamente accuracy diagnóstico. Para SREG, la arquitectura "agente investigador interactúa con agente fuente de información, separación estricta de información, accuracy degrada bajo sesgo" es directamente análoga.

**HypoBench** (Liu et al., arXiv:2504.11524) — 7 tasks reales + 5 sintéticas, 194 datasets. Métricas: Hypothesis Discovery Rate (HDR), Feature Discovery Rate (FDR), generalizability. Parámetros de dificultad controlables: noise, distractors, compositional depth. Usan LLM-as-judge para HDR, validado contra anotación humana (κ=0.80 para FDR). Este es el patrón a copiar: parámetros explícitos de dificultad en el datagen, métricas múltiples más allá de accuracy, validación humana del judge. La crítica: LLM-judge sigue siendo el cuello de botella de confiabilidad.

**Aviary / FutureHouse** (Narayanan et al., arXiv:2412.21154) — gymnasium con 5 entornos científicos (LitQA2, SeqQA, protein stability, etc.). Llama-3.1-8B + EI matchea/supera frontier en 2 tasks de LAB-Bench. Aviary formaliza el "Language Decision Process" como compute graph optimizable. Es el referente más cercano a "agente científico real con tooling real". La debilidad declarada por los propios autores: agentes narrow no generalizan entre tasks.

**ScienceAgentBench** (arXiv:2410.05080) — 102 tareas de 44 papers peer-reviewed, 4 disciplinas, validadas por 9 expertos. Output unificado a programa Python self-contained. Buen ejemplo de *evitar overclaiming end-to-end*: evalúan tareas individuales del workflow, no el workflow completo.

**BLADE** (arXiv:2408.09667) — 12 datasets/research questions con análisis ground-truth de múltiples expertos data scientists; matching computacional de distintas representaciones del mismo análisis. Buen modelo para *equivalence-aware grading* en research multi-paso.

**Auto-Bench** (arXiv:2502.15224) — basado en *causal graph discovery* con interventions iterativas. Modelos performan peor a medida que aumenta complejidad. Conceptualmente más cercano a SREG que CLadder porque es interactivo.

**CodeScientist** (Jansen et al., arXiv:2503.22708) — sistema de descubrimiento end-to-end; 19 discoveries de los cuales 6 fueron juzgados *minimally sound and incrementally novel* por external review + code review + replicación. La calibración: *menos del 30% de los outputs* sobreviven evaluación rigurosa. Esto define un piso realista de qué fracción de "descubrimientos" automáticos son verdaderos.

**MLAgentBench, MLE-bench, RE-Bench, MLRC-Bench** — familia de benchmarks de *ML research agents*. RE-Bench compara explícitamente contra expertos humanos. Útiles como complemento; no son SREG-relevant porque verifican metric improvement, no inferencia causal.

**ExCyTIn-Bench** (arXiv:2507.14201) y **PATHWAYS** (arXiv:2602.05354) — investigative-style benchmarks con *hidden context discovery* y *threat investigation graphs*. PATHWAYS reporta que agentes "frequently hallucinate investigative reasoning by claiming to rely on evidence they never accessed". Este es exactamente el failure mode que SREG debe testear y que pocos benchmarks documentan explícitamente.

**OrgForge-IT** (arXiv:2603.22499) — el más relevante metodológicamente. *Physics-cognition boundary*: un engine determinístico Python mantiene ground truth, los LLMs solo generan *surface prose*. Cross-artifact consistency es una *garantía arquitectónica*, no algo que se chequea post-hoc. Este patrón es prácticamente idéntico al que SREG debería formalizar: el SCM es el engine determinístico, la verbalización del caso es la prose, y la consistencia entre observaciones y SCM es by construction.

### 2.3 Dominio 3 — Juegos, física, robótica procedural

**Procgen** (Cobbe et al., arXiv:1912.01588) — 16 entornos game-like procedurales, ~1000 niveles necesarios para generalización. La lección dura: incluso con 500-1000 levels, los agentes overfittean a estructuras superficiales. *Diversity within environment* importa tanto como *diversity across environments*.

**MiniGrid / BabyAI** (Chevalier-Boisvert et al., arXiv:2306.13831) — gridworlds con *synthetic Baby language* para grounded language learning. Tunable programáticamente para curriculum learning.

**Crafter / Craftax** (Hafner, arXiv:2109.06780; arXiv:2402.16801) — Minecraft-lite procedural con 22 achievements semánticamente significativos. Crafter mide capacidades específicas vía achievement unlocking, lo que es esencialmente *partial credit estructurado*.

**NetHack Learning Environment / MiniHack** — procedural dungeons textuales con dinámica densa.

**MineRL / MineDojo** — Minecraft real, mucho más caro de iterar, sirve como techo de complejidad.

**RoboGen** (arXiv:2311.01455) + **Genesis** + **Eureka** (arXiv:2310.12931). RoboGen: pipeline propose→generate→learn donde un LLM propone tarea, genera escena en simulador, descompone en subtareas y elige aprendizaje (RL/motion planning/trajectory opt). Genesis es el simulador diferenciable. Eureka es el reward designer LLM-based: usa código del entorno como contexto, hace evolutionary optimization sobre código de reward, supera humanos en 83% de 29 entornos. La lección clave: *separar descubrimiento de tarea de descubrimiento de reward* funciona, y *evolutionary search over verifier code* es una herramienta poderosa.

**PAIRED** (Dennis et al., arXiv:2012.02096) — Unsupervised Environment Design con minimax regret, antagonist-protagonist. Genera curriculum de niveles increasingly difficult-but-achievable.

**POET** (Uber AI), **OMNI** (arXiv:2306.01711), **OMNI-EPIC** (arXiv:2405.15568). OMNI introduce *Models of human notions of Interestingness* via foundation models como filtro: dado un universo enorme de tareas posibles, ¿cuáles son interesting además de learnable? OMNI-EPIC extiende a "Environments Programmed in Code" para Darwin-completeness. La motivación: el agente puede explotar measures de novelty/diversity (Goodhart) generando variaciones triviales; usar un FM como proxy de "interesting" reduce esto.

---

## 3. Análisis profundo de los 8 más relevantes para SREG

A continuación, los proyectos cuyo análisis profundo le da más jugo a SREG, con la grilla de las 10 dimensiones que pediste.

### 3.1 Endless Terminals

Generación: 100% procedural-LLM en cuatro etapas, sin anotación humana. Diversidad axes: categorías × niveles de complejidad × scenarios. Verificación: state-based (filesystem/DB), tests programáticos generados por LLM y ejecutados. Diversidad/interestingness: filtro de duplicados por embedding, *iterative validation* que descarta containers que no buildean. Solvability: o3 como solver de referencia, retain solo si o3 lo resuelve. Privileged info: el solution code que produjo o3 nunca se le muestra al agente entrenando. Reward: binario episodio-level. Escala: 3.255 tareas verificadas. Failure modes admitidos: capacidad-techo limitada por el filter model (o3); tareas con dependencies de red inestables filtradas pero no siempre detectadas; *narrow distribution* sobre file/log/data ops. Transfer: TerminalBench 2.0 mejora pero no por mucho (2-3 puntos absolutos en frontier models pequeños), gain mucho mayor in-distribution. Refinamiento iterativo: sí, etapa II tiene loop de container-validation con feedback al generador.

### 3.2 SWE-Gym y descendientes (R2E-Gym, SWE-smith)

Generación: hybrid; SWE-Gym es real-world curado con execution scaffolding, R2E-Gym hace *back-translation desde commits* (genera issue desde el diff, no al revés), SWE-smith hace transformaciones programáticas. Verificación: tests fail-to-pass de los repos. Diversidad: 13+ repos, lenguaje único (Python). Solvability: implícita (los tests existen y un PR humano los pasa). Privileged info: el patch original se oculta; se da el codebase pre-PR + issue text. Reward: pass-rate sobre fail-to-pass tests. Escala: 2.4k → 8.7k tareas. Failure modes: tests insuficientes (documentado por arXiv:2507.02825), training-test contamination si el repo aparece en pretraining, distribución sesgada hacia bug-fix. Transfer: 19 puntos absolutos en SWE-Bench Verified, 51% peak con hybrid verifiers. Refinamiento: en R2E-Gym, agentic test generation. **Lección directa para SREG**: no necesitás generar issues ni patches; necesitás que el SCM *defina su propia verificación by construction*, lo cual es estructuralmente más fuerte que tests humanos.

### 3.3 CLadder

Generación: muestreo de causal graphs + queries, oracle CI engine produce ground-truth simbólico, verbalización a NL. Tres familias: commonsensical, anti-commonsensical, nonsensical. Verificación: simbólica + numerical (cuando aplica). Diversidad: 3 rungs × varios DAG types × tres semánticas. Interestingness: la triple semántica es el mecanismo de control de contaminación; **es el patrón que SREG ya está parcialmente usando y debería formalizar**. Solvability: by construction (oracle engine garantiza solución). Privileged info: separación clean entre statement y solución. Reward: accuracy multiple-choice + fine-grained F1 sobre estimand. Escala: 10K. Failure modes: la verbalización NL puede colapsar a cues superficiales; CRAwDAD (arXiv:2511.22854) muestra que multi-agent debate sobre RLMs gana 9+ puntos, lo que sugiere que la single-shot evaluation subestima capability genuino. Transfer: CausalCoT entrenado/promptado sobre CLadder transfiere bien a otros causal benchmarks. Refinamiento iterativo: no aplica (estático).

### 3.4 DiscoveryWorld

Generación: 120 tasks de 8 topics × 3 difficulty × variations paramétricas. Verificación: triple métrica (task completion, process, explanatory knowledge). Diversidad: temas heterogéneos (radioisotope dating, rocket science, proteomics). Interestingness: distractors explícitos en el design; tareas requieren iteración hipótesis-experimento. Solvability: validada por scientists con grados avanzados. Privileged info: agentes ven solo las observaciones in-game; ground truth está en el simulator state. Reward: tres métricas paralelas (no una sola binaria). Escala: 120 tasks; reportado por los autores como "agentes resuelven 18-38%". Failure modes: el simulator es text-based con física simplificada (admitido como limitación); la métrica de explanatory knowledge usa LLM-judge sobre triples, ~80% confiabilidad. Transfer: sí, ha sido picked up por TALES 2025. Refinamiento iterativo: parametric variations re-generan tasks runtime. **Lección**: la métrica de "explanatory knowledge discovered" es el embrión de lo que SREG hace formal con SCM/do-calculus, pero DiscoveryWorld se quedó en LLM-judge.

### 3.5 AgentClinic

Generación: cases derivados de USMLE y NEJM (curados). Verificación: diagnostic accuracy + patient compliance + consultation rating. Diversidad: 9 especialidades × 7 idiomas × 24 biases injectables. Interestingness: el bias injection es el mecanismo más interesante: una misma case con bias activo vs no es trivialmente más difícil. Solvability: validated por evidencia clínica. **Privileged info: arquitectónicamente clean**; cada agente (doctor, patient, measurement) recibe solo la información correspondiente a su rol. Reward: multi-dimensional. Escala: ~hundreds. Failure modes: cases base son humanos, no escalable a millones; LLM como patient agent es factor crítico de variance. Transfer: claramente útil para entrenar systems clínicos. **Lección directa para SREG**: la arquitectura "investigador + agentes-fuente con info disjunta + biases inyectables" es directamente importable. Los biases de AgentClinic son exactamente análogos a "priors realistas vs anti-commonsensical" en SREG.

### 3.6 Absolute Zero / AZR

Generación: el modelo *propone* tareas (deduction, abduction, induction sobre código) y *resuelve*. Sin datos humanos. Verificación: code executor. Diversidad: emerge del proposer. Interestingness: aprendizaje de "learnability" como reward implícito. Solvability: el proposer es entrenado para generar tasks que el solver puede pero no triviales. Privileged info: no aplica (single agent). Reward: verifiable via executor; advantage estimator multitask. Escala: zero data, miles de self-generated. Failure modes: **uh-oh moment** documentado (CoTs preocupantes en Llama-3.1-8B); colapso de distribución cuando el proposer no es regularizado; safety concerns explicitados por autores. Transfer: SOTA en code y math zero-data. Refinamiento iterativo: el proposer-solver loop *es* el refinamiento. **Lección crítica para SREG**: self-play sin un sustrato externo *grounded* es alignment-frágil. SREG tiene exactamente el sustrato que AZR no tiene (SCM/do-calculus); por eso un loop self-play sobre SREG sería más seguro que sobre AZR. **Pero** —y esto es un anti-pattern— querer que SREG sea AZR-like en v2 sería un error: la fortaleza de SREG es la *verificación formal externa*, no la auto-generación libre.

### 3.7 CodeScientist

Generación: ideación via *genetic mutations LLM-as-mutator* sobre combinaciones de papers + code-blocks. Verificación: external review (conference-style) + code review + replication. Diversidad: 250 experiments × 50 ideas. Interestingness: novelty implícita en mutations. Solvability: posthoc. Privileged info: no aplica. Reward: multi-faceted post-hoc, no usable como signal RL. Escala: hundreds. Failure modes admitidos: fracción muy alta de "discoveries" son trivial o no novel (~13/19 rejected); LLM-extracted triples solo ~80% verificables. Transfer: piloto. Refinamiento: genetic loop. **Lección**: el *evaluation gauntlet* multi-stage (code review + replication + external) es metodológicamente correcto pero costoso; no aplicable directamente a SREG en hot loop, pero sí como standard para validar la calidad de los cases generados.

### 3.8 OrgForge-IT (Insider Threat)

Generación: deterministic Python engine mantiene ground truth, LLMs generan surface prose. **Physics-cognition boundary** explícito. Verificación: deterministic. Diversidad: configurable detection difficulty. Interestingness: detection requiere correlación cross-surface (single signal nunca suficiente). Solvability: by construction. Privileged info: el engine state es el ground truth, no se filtra al agente. Reward: outcome + evidence-citation accuracy. Escala: arbitraria. Failure modes admitidos: dependency on prose realism. **Lección clave para SREG**: este es exactamente el patrón que SREG implementa con el SCM, formalizado y nombrado. Vale la pena citar y posicionarse explícitamente: "SREG aplica el principio physics-cognition boundary de OrgForge-IT al dominio de inferencia causal".

---

## 4. Síntesis de buenas prácticas cross-cutting

### A. Lo que aparece consistentemente en proyectos exitosos

1. **Pipeline de cuatro etapas con feedback en la fase 2** (build/validate). Endless Terminals, SWE-smith, R2E-Gym, OpenThoughts-Agent, AgentScaler. La fase de *iterative container/artifact refinement* es donde se cae el 30-50% de los candidates; sin ella la calidad colapsa.

2. **Filtro de solvability por modelo frontier**. o3 en Endless Terminals, GPT-5 Codex en OpenThoughts-Agent, "agentic distillation" en R2E-Gym. Es prácticamente universal en los proyectos de ejecución, y se está propagando a los de razonamiento.

3. **Privileged information separation**. AgentClinic, OrgForge-IT, DiscoveryWorld. El patrón canónico es: ground truth vive en un *engine state* que el agente nunca ve; el agente accede vía *observations* o *queries* limitadas.

4. **"Must not pass trivially" check arquitectónico**. SWE-bench fail-to-pass es el ejemplo arquetípico (los tests deben fallar antes y pasar después). En causal: CLadder anti-commonsensical es la versión análoga (la respuesta no debe ser obvia desde priors).

5. **Reward binario episode-level + métrica de proceso paralela**. Endless Terminals usa solo binario y funciona porque el espacio es muy estructurado; DiscoveryWorld y AgentClinic usan multi-dimensional. La regla empírica: para entrenamiento RL inicial, binario es estable; para evaluación, multi-dimensional informa más.

6. **Validation by-construction siempre que se pueda**. Minimo (theorem prover), CLadder (oracle engine), AutoWebWorld (FSM), OrgForge-IT (deterministic engine), SREG (SCM). Generar válidos por construcción >>> generar y filtrar.

7. **Versions adversariales del mismo seed task**. CLadder commonsensical/anti-commonsensical/nonsensical, AgentClinic con/sin bias. Esto es lo que separa benchmarks de razonamiento genuinos de benchmarks de memorización.

8. **Container-level reproducibility y exploit-detection**. TerminalBench-2.0 explicitó esto: corren un *adversarial exploit agent* sobre cada tarea para detectar tests gameables. En SWE-bench la falta de esto causó la sobreestimación de hasta 100% relativo documentada en arXiv:2507.02825.

### B. Lo que aparece solo en domain-specific projects

- **En causal/scientific únicamente**: triple-semantic stratification (CLadder), bias injection (AgentClinic), explanatory knowledge metric (DiscoveryWorld), formal symbolic verifier (DOVERIFIER), causal-graph-as-substrate (Auto-Bench). Estos *no aparecen* en entornos de ejecución porque no son necesarios: la verificación ejecutable subsume el problema de "el agente realmente entendió o solo pattern-matchea".

- **En procedural games únicamente**: minimax-regret curriculum (PAIRED), MoI/interestingness via FM (OMNI), achievement-based partial credit (Crafter). Estos asumen un simulator estable y un agente RL clásico (no LLM); transferir a SREG requiere adaptación profunda.

- **En execution únicamente**: container snapshotting, agentic test generation, hybrid execution-based + execution-free verifiers (R2E-Gym), back-translation desde commits.

### C. Failure modes a evitar (consolidados de la literatura)

1. **Reward hacking en tests parciales**. Documentado en SWE-bench (tests insuficientes), TAU-bench (empty responses contadas como success), reward-hacking benchmarks (arXiv:2603.06621, arXiv:2511.18397). Mitigación: tests adversariales + adversarial exploit agent.

2. **Capability ceiling del filter model**. Si filtrás por o3, no aprendés más allá de o3. Endless Terminals lo admite.

3. **Training-test leakage por contaminación pre-training**. SWE-bench pre-2023 vs post-2023 muestra el efecto. Mitigación: seeds desconocidos, anti-commonsensical variants.

4. **Distribución estrecha**. Procgen lo demostró: incluso 500 levels no garantizan generalización. Mitigación: factorial design sobre múltiples ejes de variación.

5. **LLM-judge como verificador final**. DiscoveryWorld y HypoBench lo admiten (~80% confiabilidad). Mitigación: usar LLM-judge solo donde no haya alternativa simbólica; validar contra anotación humana.

6. **Self-play colapso / uh-oh moment**. AZR. Mitigación: anchor externo verificable (que SREG ya tiene).

7. **Verbosity gaming / fluency confused with reasoning**. PRMs como fluency detectors (arXiv:2603.06621). Mitigación: verificación formal (do-calculus), no judge sobre prosa.

8. **Hallucinated investigative reasoning**. PATHWAYS lo documenta: agents claim to use evidence they never accessed. Mitigación: log-based verification de qué evidencia el agente *consultó* en realidad.

### D. Cómo se operacionaliza "interestingness"

La literatura tiene tres respuestas y todas son heurísticas:

1. **Learning progress** (POET, AdaptiveCurriculum). La tarea es interesting si la frontera de capacidad del agente cambia mucho al entrenarla. Operacional pero costoso.

2. **Foundation-model-as-MoI** (OMNI, OMNI-EPIC). Aprovecha que los humanos escriben sobre lo interesante; el FM la internalizó. Pragmatic, sesgado.

3. **Minimax regret** (PAIRED). Adversary genera tasks con max regret-gap entre protagonist y antagonist. Teóricamente principled, frágil en práctica (Refining MMR, arXiv:2402.12284).

Ningún proyecto tiene una definición formal de interestingness que no sea proxy. Para SREG, una definición *formal* (e.g., "interesting = el SCM tiene confounding no trivial Y la respuesta del rung 2/3 difiere significativamente de la del rung 1") sería un aporte real.

### E. Estado del arte en solvability filtering

- **Frontier model pass@N**: Endless Terminals (o3 pass@1), OpenThoughts-Agent (GPT-5 Codex pass@1).
- **Self-play difficulty curricula**: AZR (proposer reward favors learnable-but-not-trivial), PAIRED (regret).
- **Human review**: TerminalBench-2.0 (3 reviewer-hours/task), ScienceAgentBench (9 expertos).
- **By-construction**: Minimo, CLadder oracle, SREG SCM. Estructuralmente superior cuando aplica.
- **Hybrid verifiers**: R2E-Gym (execution-based + execution-free).

El pattern dominante es frontier-model pass@N para entornos de ejecución; by-construction donde el sustrato lo permite; human para benchmarks finales de eval (no training).

### F. La tradeoff diversidad-significancia en juegos vs LLM-generated

Procgen, Crafter y NetHack resuelven el tradeoff *limitando el espacio de variación* a parámetros de generación bien tipados (layout, recursos, enemigos). Diversity dentro de templates fijos. La meaningfulness viene de la física del simulador: si el agente cae en lava, muere, no hay ambigüedad.

LLM-generated environments lo enfrentan al revés: el espacio de variación es enorme (todo lo que un LLM puede describir), por lo que necesitan *mecanismos extra de filtrado* (interestingness FM, frontier solvability, exploit detection). La meaningfulness no es estructural sino emergente.

Para SREG, la lección es híbrida: el SCM da la *física* (meaningfulness estructural), el LLM da la *verbalización y diversidad de superficie*. Es exactamente el patrón OrgForge-IT.

### G. Verificación en investigative vs procedural

- **Procedural**: state-based, ejecutable, barata. La pregunta es solvability y diversity, no si la verificación es fiel.

- **Investigative**: la verificación es lo difícil. CLadder/DOVERIFIER muestran que string-match no captura equivalencia formal. AgentClinic muestra que diagnóstico correcto + bad reasoning ≠ buen agente clínico. DiscoveryWorld trata de capturar "explanatory knowledge" pero termina con LLM-judge.

El insight crítico para SREG: **la verificación formal-causal vía do-calculus es el upgrade arquitectónico que el campo investigative venía esperando y que ningún proyecto del catálogo implementa de modo end-to-end-investigativo**. CLadder lo hace estático; DOVERIFIER es solo un verifier de expresiones; SREG conectaría el do-calculus a una *traza de investigación multi-paso*. Eso es defendible como contribución.

---

## 5. SREG: qué adoptar, qué adaptar, qué descartar, qué llenar

### 5.1 Adoptar directamente

1. **El pipeline de cuatro etapas de Endless Terminals**, mapeado a SREG así: (i) muestrear (categoría científica × estructura DAG × nivel de confounding × semántica realista/abstracta/anti-commonsensical), (ii) generación-validación iterativa del *case artifact* (SCM concreto con ecuaciones, brief textual, dataset observacional Monte-Carlo'd, AnswerKeyAnchor); (iii) generación de checks adicionales más allá del AnswerKeyAnchor (e.g., verificación de identifiability, de tamaño efecto detectable, de consistencia rung-1/2/3); (iv) filtrado por solvability con un modelo frontier corriendo bajo settings restringidos (ver punto 4).

2. **El patrón physics-cognition boundary de OrgForge-IT**, formalizado y nombrado en el paper de SREG. El SCM determinístico mantiene ground truth; los LLMs solo verbalizan y/o muestrean datos observacionales según los SEMs. Cross-artifact consistency by construction.

3. **La estratificación triple de CLadder** (realista commonsensical / abstracta / anti-commonsensical) como control arquitectónico, no como ablation post-hoc. Si SREG ya tiene esta dimensión y el hallazgo empírico va en la dirección esperada, esto es directamente publicable.

4. **El bias-injection model de AgentClinic**: 24 sesgos cognitivos inyectables. Para SREG el análogo sería: priors realistas inyectables (medical, social, economic) que el agente puede o no usar; y benchmark explícitamente cómo cambia performance.

5. **El three-stage filtration de OpenThoughts-Agent**: bad-verifier filter, container/case stability filter, optional difficulty filter. Para SREG: AnswerKeyAnchor flaky filter, dataset Monte-Carlo stability filter, optional "incluso GPT-5/o3 no resuelve one-shot" filter para casos de evaluación stress.

6. **El "must not pass trivially" como check arquitectónico**: para cada caso generado, verificar que rung-1 (correlación cruda) da una respuesta *diferente* del answer correcto. Si rung-1 ya da el answer, el caso es trivial y se descarta. Esto es directamente análogo al fail-to-pass de SWE-bench.

7. **Logging de evidencia consultada** estilo PATHWAYS: trackear qué subset de la data observacional el agente realmente "miró" antes de concluir. Esto detecta hallucinated investigative reasoning, que es exactamente el failure mode al que apunta SREG.

### 5.2 Adaptar con cuidado

1. **Hybrid verifiers de R2E-Gym**: do-calculus simbólico (execution-based equivalent) + LLM judge sobre la *narrativa de razonamiento* (execution-free equivalent). Pero darle siempre prioridad al simbólico; el judge solo como tiebreaker o métrica auxiliar.

2. **ScalingInter-RL de AgentGym-RL**: si SREG eventualmente entrena agentes (no solo evalúa), empezar restringiendo el horizonte de queries del agente al SCM y expandirlo gradualmente. Estabiliza policy.

3. **Eureka-style evolutionary search sobre el verifier**: dudoso pero potencialmente útil para *generar variantes del AnswerKeyAnchor* que cubran formas alternativas de expresar la misma conclusión causal. Antes de implementar, validar que do-calculus equivalence-check es suficiente.

4. **DiscoveryWorld's parametric variations**: tomar un mismo SCM topológico y generar N instanciaciones con diferentes magnitudes de efecto, niveles de ruido, sample sizes. Da curriculum sin re-diseñar SCMs.

5. **OpenReward / Prime Intellect Environments Hub release pattern**: empaquetar SREG como módulo Python pinneable con verifier interface uniforme. Esto importa para tracción comunitaria.

### 5.3 NO adoptar / anti-pattern para SREG

1. **No adoptar self-play full estilo AZR**. SREG ya tiene un anchor externo verificable (do-calculus); meterse en proposer-solver loop sin supervisión externa importaría exactamente los riesgos del uh-oh moment sin necesidad. Si querés un loop generativo, que sea el LLM-as-mutator sobre cases SCM existentes (más cerca de CodeScientist genetic mutations), con todos los outputs pasados por el verifier formal antes de aceptarse.

2. **No usar LLM-as-judge como verificador primario** de las conclusiones causales. Es exactamente el patrón que vuelve a CLadder/HypoBench/DiscoveryWorld vulnerables a fluency-bias. SREG tiene do-calculus; usalo. LLM-judge solo para *quality of explanation* paralelo, nunca para correctness.

3. **No agregar densos process rewards** estilo PRM. arXiv:2603.06621 muestra que PRMs funcionan como fluency detectors, no como reasoning verifiers. En el contexto SREG sería peor: un PRM aprendería los marcadores superficiales de razonamiento causal ("by the backdoor criterion...") sin verificar substance.

4. **No imitar la diversidad LLM-generated sin substrate**. Lo que hace AgentScaler/AWM (1000 entornos LLM-generated backed by databases) es válido para tool-use general pero el *substrate* en SREG no es una DB sino un SCM. La métrica de diversidad relevante es *diversidad de estructuras causales identificables*, no *diversidad de dominios semánticos*. Es posible que SREG necesite menos cases pero con cobertura sistemática del espacio de DAGs (chain, fork, collider, M-bias, instrumental variable, mediator, etc.) × niveles de identifiability.

5. **No copiar el LLM-judge de quality de SREG v1.5 hacia evaluación de conclusiones**. Mantener el judge solo para case quality (¿el case es bien-formado, el brief es claro, los datos están razonablemente generados?), nunca para evaluación del agente. La evaluación del agente debe ser 100% AnswerKeyAnchor + checks formales.

6. **No correr hacia "end-to-end scientific discovery"** estilo CodeScientist o Aviary completo. CodeScientist termina con 6/19 discoveries publicables tras review masivo. Es el movimiento de feature-creep que mata proyectos buenos. SREG es estricto: investigación causal sobre datos observacionales sintéticos con SCM hidden. Sostener ese alcance.

### 5.4 Gaps en la literatura que SREG puede llenar

Revisando el catálogo, hay tres huecos donde SREG no tiene competencia directa:

**Gap 1: Investigative-causal multi-paso con verificación formal**. CLadder es estático y a nivel pregunta. DOVERIFIER es solo un verifier (no un benchmark). DiscoveryWorld es interactivo pero sin verificación formal causal. Auto-Bench se acerca pero opera en discovery del DAG, no en estimación causal sobre DAG conocido-pero-oculto. SREG ocupa el cuadrante "investigación interactiva multi-paso + verificación do-calculus".

**Gap 2: Operacionalización cuantitativa de "razonamiento causal genuino vs pattern matching"**. CLadder lo introdujo; "Are LLMs Biased Like Humans?" (arXiv:2602.02983) lo midió en collider tasks; CRAwDAD lo explotó con debate. Pero ningún proyecto produce un *eje continuo de control* sobre cuán alineada está la semántica de superficie con la estructura causal subyacente. SREG, si formaliza esto (e.g., "alineación semántica = correlación entre prior frecuente del LLM dada la verbalización y la respuesta correcta"), puede dar *un benchmark gradable*.

**Gap 3: Casos de investigación generables a escala con diversidad estructuralmente controlada**. AWM y Agent-World generan miles de entornos pero la estructura latente no es controlable de modo principled. SREG genera SCMs con propiedades estructurales explícitas (identifiability, número de confounders, presencia de instrumental variables). Esto es publicable per se como "infrastructure".

### 5.5 Riesgos específicos para SREG (críticos)

1. **El AnswerKeyAnchor como single point of failure**. Si la matching es deterministic-string-equivalence, vas a tener mismatches por re-formulación equivalente. DOVERIFIER lo resolvió con derivability under do-calculus rules. Recomiendo fuertemente upgrade a equivalence-checking simbólico antes de v2.

2. **Static one-shot design**. El equivalente para SREG del problema *capability-ceiling-from-validator* en Endless Terminals: si los cases son fijos y los modelos mejoran, vas a saturar. Mitigación: parametric variations runtime + difficulty curricula.

3. **Realismo semántico vs control causal**. El propio hallazgo empírico de SREG —agentes performan peor con realistic semantics— sugiere que tu mejor case es estructuralmente sintético. Pero los stakeholders externos (Y-TEC, dominios de aplicación) van a querer realismo. Tensión real. Recomendación: documentar explícitamente que SREG-realistic y SREG-abstract son *dos benchmarks diferentes* midiendo capacidades complementarias, no una versión "mejor" y otra "peor".

4. **Monte Carlo simulation noise**. Si los datos observacionales se muestrean stochastically, distintos seeds dan ground-truth empíricos diferentes (aún con SCM idéntico). Asegurar que el AnswerKeyAnchor está derivado del *limiting behavior* (n→∞) o de la población poblacional, no del sample finito. Si no, existe el riesgo de que un agente "correcto" sea marcado mal por Monte Carlo variance.

5. **Reproducibilidad**. Pinear seeds, versions de los SCM generators, version del do-calculus engine. Los proyectos que no hicieron esto desde día 1 (early WebArena, original SWE-bench) pagaron caro retrospectivamente.

---

## 6. Conclusión accionable

SREG está bien posicionado: ocupa un nicho real, usa un sustrato formalmente sólido (SCM/do-calculus) que el resto del campo o no usa o usa estáticamente, y tiene un hallazgo empírico (degradación con semántica realista) que es directamente publicable como evidencia del problema más general que el campo causal viene marcando desde CLadder. La hoja de ruta más razonable, en mi lectura, es:

**Corto plazo (v2)**: upgrade del AnswerKeyAnchor a equivalence-check simbólico estilo DOVERIFIER; agregar el "must not pass trivially" check arquitectónico (rung-1 ≠ answer); formalizar el three-stage filter (bad anchor / unstable Monte Carlo / frontier solvability) estilo OpenThoughts-Agent; implementar logging de evidencia consultada estilo PATHWAYS para detectar hallucinated investigation.

**Mediano plazo (v3)**: parametric variations runtime sobre topology fija; release como verifier package en Prime Intellect Environments Hub o equivalente; adoptar el patrón physics-cognition boundary explícitamente y citar OrgForge-IT como precedente; publicar el eje continuo "alineación semántica vs estructura causal" como métrica.

**Largo plazo, pero solo si tiene tracción y solo bajo supervisión**: LLM-as-mutator sobre cases existentes con verificación formal de cada output (CodeScientist genetic mutations applied to causal cases); evaluar si ScalingInter-RL aplica si SREG eventualmente entrena agentes.

**Lo que no hacer**: no autoengañarse con LLM-judge sobre conclusiones; no copiar self-play AZR-style; no expandir alcance hacia "end-to-end scientific discovery"; no tratar realistic y abstract como opuestos sino como ejes complementarios.

## Caveats

- El catálogo refleja literatura accesible vía web search a mayo de 2026; posiblemente hay proyectos relevantes en preprints recientes o trabajos internos de labs no publicados que se omiten.
- Varios papers citados son preprints arXiv aún; algunos (Agent-World, AWM, InfiniteWeb, AutoWebWorld) tienen IDs arxiv que parecen ser de 2026 con formatos no estándar; los traté como existentes según los snippets pero no los pude verificar de modo independiente más allá de eso.
- La cifra "los agentes performan peor con semántica realista" del empírico de SREG está reportada por vos; está alineada con CLadder anti-commonsensical y con arXiv:2602.02983, pero la magnitud relativa de SREG vs estos baselines no está caracterizada en este reporte.
- La recomendación de adoptar DOVERIFIER-style equivalence checking está basada en su propuesta; no validé personalmente que el verificador es robusto a todos los corner cases del do-calculus moderno (e.g., front-door, IDc).
- "Endless Terminals" tiene ID arXiv 2601.16443 (2026) lo cual es consistente con la fecha de hoy; algunos otros papers citados con IDs 2601.* / 2602.* / 2603.* / 2604.* / 2605.* / 2606.* parecen también de 2026 — los uso porque salen como resultado en las búsquedas, pero hay que tener cuidado de que no sean OCRs raros o IDs internos no canónicos. Validá directamente los URLs antes de citarlos en un paper formal.
- Las recomendaciones críticas (descartar self-play full, no usar LLM-judge para correctness) son posiciones argumentadas, no consenso del campo. Otros investigadores podrían razonablemente sostener lo contrario.