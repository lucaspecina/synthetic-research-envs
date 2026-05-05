# World design — Vertical 3: UED, auto-curriculum y open-endedness en RL

> Reporte de investigación generado por agente Explore (2026-05-05). Parte del
> survey en `research/synthesis/world_design_techniques_survey.md`.
>
> Foco: research de RL sobre generación automática de entornos al borde de la
> dificultad del agente. Mecanismos transferibles a SREG.

---

## 1. Mapa del campo: tres olas

**Ola 1: Domain Randomization (2017-2018)**
[Tobin et al. 1703.06907](https://arxiv.org/abs/1703.06907) establece la línea base: entrenar agentes en una distribución amplificada de variaciones de parámetros simulados los hace robustos a la realidad. Mecanismo pasivo: sample uniformemente. Efectivo pero crudo.

**Ola 2: Curriculum adaptativo & UED (2019-2021)**
Aparecen métodos que **optimizan qué entornos entrenar**: POET, PAIRED, PLR. Se reemplaza "muestra uniformemente" por "diseña entornos que maximicen arrepentimiento (regret)". Co-evolución agente↔entorno; el currículo emerge dinámicamente.

**Ola 3: Open-endedness & Quality-Diversity (2021-2024)**
XLand, Voyager, Genie, Craftax. El objetivo pivota: no solo "entrenar bien a un agente" sino **generar entornos irreduciblemente diversos que fuerzan innovación**. Mecanismos: MAP-Elites, novelty search, co-evolution a escala.

**Hilo conductor**: regret-based selection → behavioral characterization (novelty + calidad) → population-based ensembles of worlds.

## 2. Doce sistemas concretos

### 2.1 POET: Paired Open-Ended Trailblazer

- **Cita**: Wang, Lehman, Clune, Stanley. [1901.01753](https://arxiv.org/abs/1901.01753) (GECCO 2019), Enhanced POET [2003.08536](https://arxiv.org/abs/2003.08536) (ICML 2020)
- **Mecanismo**: Mantiene una población de (agente, entorno) pareado. Genera nuevos entornos mutando entornos existentes, entrena agentes con RL estándar. Las soluciones pueden **transferir** entre entornos si mejoran fitness allí.
- **Selección**: **Minimal criteria** para preservar parejas: si un entorno es "fácil" (agente converge), genera variantes más difíciles; si es "imposible", descarta o relaja.
- **Evitar degeneración**: transfer entre problemas actúa como regularización. Enhanced POET añade una **medida de novedad dominio-general**.
- **Crítica**: original POET sufre degeneración en BipedalWalker — agentes aprenden a "freezar antes del obstáculo". Requiere sintonización delicada.

### 2.2 PAIRED: Protagonist-Antagonist Induced Regret

- **Cita**: Dennis, Jaques et al. NeurIPS 2020.
- **Mecanismo**: Tres jugadores: **Protagonist** (agente a entrenar), **Antagonist** (segunda copia), **Adversary** (generador de entornos). El adversario recibe recompensa = `regret = max(reward_antagonist - reward_protagonist)`.
- **Selección**: minimax regret explícito. Adversario imposible → ambos fallan → regret=0. Adversario fácil → ambos resuelven → regret=0. Incentivo: encontrar la frontera.
- **Evitar degeneración**: dos agentes en paralelo *estabilizan* el curriculum.
- **Crítica**: en CarRacing entra en ciclos donde antagonista nunca alcanza al protagonista.

### 2.3 ACCEL: Adversarially Compounding Complexity by Editing Levels

- **Cita**: Parker-Holder et al. [2203.01302](https://arxiv.org/abs/2203.01302) (ICML 2022)
- **Mecanismo**: **mutación evolutiva de niveles**. Mantiene archivo. Evalúa agente, mide TD-error (regret proxy), toma K niveles con mayor regret, muta cada uno (añade/quita obstáculos), evalúa, agrega buenas al archivo.
- **Selección**: regret-based. Niveles de alta regret = mucho gap entre lo que el agente hace y lo que pudo. ACCEL explota mutaciones locales.
- **Avance sobre PLR**: opera *sobre niveles pasados conocidamente interesantes*; mutaciones son pasos pequeños que mantienen coherencia.

### 2.4 PLR: Prioritized Level Replay

- **Cita**: Jiang, Grefenstette, Rocktäschel. [2010.03934](https://arxiv.org/abs/2010.03934) (ICML 2021)
- **Mecanismo**: **curriculum a través de re-sampling adaptativo**. Sample nivel con probabilidad ∝ TD-error estimado durante últimas N rollouts.
- **Selección**: TD-error cuantifica "si revisitamos este nivel, el agente aprendería más". Heurístico elegante: no requiere modelo de *por qué* es difícil, solo observa disparidad temporal.
- **Evitar degeneración**: a medida que el agente mejora, TD-errors en niveles fáciles → 0. **Emergent curriculum** automático.
- **Resultado**: 76% improvement over baselines en Procgen.

### 2.5 Procgen

- **Cita**: Cobbe, Hilton, Schulman, Hesse. [1912.01588](https://arxiv.org/abs/1912.01588) (ICML 2020)
- **Mecanismo**: **PCG como benchmark**. Usa PRNG con seed para 16 juegos. Demuestra que entrenar en *múltiples seeds* generaliza mejor.
- **Crítica**: útil para evaluar, pero no propone cómo generar mejor. Motivó PLR, ACCEL, etc.

### 2.6 Domain Randomization & variantes

- **Cita base**: Tobin et al. [1703.06907](https://arxiv.org/abs/1703.06907) (ICLR 2017)
- **ADR (Active Domain Randomization)**: [1904.04762](https://arxiv.org/abs/1904.04762). Aprende la distribución de sampling. RL sub-problema: adversario (parámetro sampler) recibe reward si causa mayor discrepancia entre agentes en simulador canonical vs. randómico.
- **Críticas** [2110.03239]: DR falla en fenómenos no modelados. Sim2real gap escala ~O(H) con horizonte.

### 2.7 BabyAI

- **Cita**: Chevalier-Boisvert et al. [1810.08272](https://arxiv.org/abs/1810.08272) (ICLR 2019); [2007.12770](https://arxiv.org/abs/2007.12770) (ICML 2021)
- **Mecanismo**: **19 niveles de dificultad** basados en descomposición de competencias. Composición de instrucciones en Baby Language: "go to red door", "go to red door then pick up ball". Cada nivel introduce nueva construcción sintáctica.
- **Hallazgo**: deep learning actual no es suficientemente sample-efficient en ambientes composicionales con lenguaje.

### 2.8 XLand

- **Cita**: Jaderberg et al. [2107.12808](https://arxiv.org/abs/2107.12808) (ICML 2021)
- **Mecanismo**: **procedural game generation masivo** (4,000 mundos, 700,000+ juegos diferentes) en 3D. Multiplayer (hide-and-seek, capture-the-flag). Arquitectura GOAT (goal-attentive).
- **Selección**: curriculum automático basado en task relevance. Adapta cuáles juegos exponer según progress.
- **Resultado**: agente capaz de jugar 700K+ juegos nuevos sin entrenamiento específico.

### 2.9 MiniHack

- **Cita**: Küttler et al. [2109.13202](https://arxiv.org/abs/2109.13202) (NeurIPS 2021)
- **Mecanismo**: **sandbox de descripción de entornos** usando DSL heredado de NetHack. Construir laberinto: `MAZEWALK`, `RANDOM_CORRIDORS`. Archivo de configuración declarativo.

### 2.10 Voyager

- **Cita**: Wang et al. [2305.16291](https://arxiv.org/abs/2305.16291) (2023)
- **Mecanismo**: **auto-curriculum + skill library + LLM iteration**. LLM (GPT-4) propone tasks nuevas basadas en items en inventory, landmarks descubiertos, skill library. Iteración: ejecutar, fallar, re-prompting con error feedback.
- **Selección**: LLM-driven, "qué skill próximo es aprendible dado lo que ya sé".
- **Resultado**: 3.3x items, 2.3x distancia, 15.3x speedup en tech tree vs. baselines.

### 2.11 Eureka

- **Cita**: Ma et al. [2310.12931](https://arxiv.org/abs/2310.12931) (ICLR 2024)
- **Mecanismo**: **generación evolutiva de funciones de reward mediante LLM**. LLM genera candidato reward function. Evalúa. Propone mutaciones. Itera.
- **Selección**: fitness = task performance under evolved reward.

### 2.12 Genie & Genie 2

- **Cita**: Genie [2402.15391](https://arxiv.org/abs/2402.15391) (ICLR 2024); Genie 2 (Dec 2024)
- **Mecanismo**: **foundation world model** entrenado sin supervisión en vídeos de internet. Autoregressive dynamics model. Latent action space.
- **Implicación para UED**: si Genie escala, tenemos una "máquina" de generar mundos interactivos. El siguiente paso: *qué mundos generar para entrenar agentes* (UED sobre Genie's latent).

## 3. Mecanismos transversales

### A) Regret-based environment selection

Aparece en: PAIRED, ACCEL, PLR (implícitamente).

`Regret = V*(environment) - V_agent(environment)`. Mide brecha de desempeño. Alto regret = agente podría mejorar.

**Crítica reportada** [2408.15099]: aproximaciones de regret (TD-error) no siempre correlacionan con regret teórico.

### B) Behavioral characterization & novelty

Aparece en: Novelty Search (Lehman & Stanley), MAP-Elites (Mouret & Clune).

**Novelty Search**: evolucionar no por fitness objetivo sino por novedad comportamental.

**MAP-Elites** [[1504.04909](https://arxiv.org/abs/1504.04909)]: mantener un archivo de soluciones indexadas por nicho comportamental. Cada celda = rango de descriptor values. Guardar mejor solución en cada celda.

### C) Quality-Diversity grids & archives

Mantener population de (entorno, agente, performance) tuplas. Indexar por (descriptor_1, descriptor_2). Preservar Pareto frontier.

### D) Mutation operators sobre entornos

Aparece en: ACCEL (level edits), POET (environment mutations).

Small, local mutations mantienen coherencia mientras exploran vecindad.

### E) Co-evolution agente ↔ entorno

Aparece en: POET, PAIRED, XLand.

Optimizar simultáneamente agente y entorno. Red Queen dynamics: ambos corren para no quedarse atrás.

**Crítica**: en dominios con stochasticity, co-evolution diverge. Requiere mecanismos de "goal-switching" o "replay".

### F) Population-based training de niveles

Mantener población P de entornos. Evaluar, rankear, reproducir top-K, reemplazar bottom-K.

**Ventaja**: paralelizable. Evita degeneración local.

## 4. Top 5 mecanismos transferibles a SREG

### 1. MAP-Elites archive con indexing multidimensional
SREG Designer mantiene un archivo de WorldSpecs previos con métricas (generalizacion del agente, learnability, complejidad, tipo de fenómeno).

**Implementación**:
- Descriptor_1 (formalismo): SCM graph structure
- Descriptor_2 (fenómeno): tipo de relación causal (confounder, mediator, collider)
- Descriptor_3 (dominio): epidemiología vs. economía vs. ecología

Mantener grilla 3D de "best WorldSpec" per nicho. Si nuevo spec cae en nicho saturado, rechazar o mutar.

**Beneficio**: detección automática de "recipe convergence". SREG sabe cuándo está re-inventando.

### 2. Regret-based learnability ranking para GoldQuestions
Un GoldQuestion tiene "learnability regret" = `V*(AnswerKey) - V_student(AnswerKey | WorldSpec)`. Proxy: human expert solves easily, student fails.

**Implementación**: ejecutar un agente de referencia imparcial; medir gaps; aquellos con gaps altos son prioridad.

### 3. Mutación compositiva de SCM descriptions
SREG Designer no genera SCMs from scratch, sino **muta anteriores** usando operadores: add node, remove node, reverse edge, add non-linearity, add latent confounder.

Parametrizar WorldSpec via AST. Mutación = token-level edits. Evaluar validity, identifiability. Si valid + aprendible, añadir a archive.

### 4. Behavioral characterization de worlds: signature vector
Cada WorldSpec → signature vector 10-20D capturando propiedades:
- Causal graph metrics: density, transitivity, in/out degrees
- Identifiability: número de causal queries identificables
- Noise model: heteroscedasticity, skewness
- Temporal: dinámico? latency?

Novelty score = distancia en signature space a closest archive member.

### 5. Co-evolution ligera: Designer ↔ Solver multi-agent
Entrenar en paralelo Designer (genera) y Solvers (resuelven). Si un Solver mejora mucho, Designer genera desafíos mayores. Si un Solver estanca, Designer relaja.

Mecanismo simple: `regret(Solver_i) → recompensa Designer`. Designer optimiza para regret máximo (sin imposibilidad).

## 5. Failure modes documentados

### A) Regret stagnation [2408.15099]
Métricas de regret se decorrelacionan del true regret. Nivel con alto TD-error pero agente ya sabe cómo actuar sub-optimalmente stable = nunca mejora.

**Para SREG**: validar learnability con N>1 agentes de architectures diversas.

### B) Degeneracy en co-evolution
Convergencia prematura a estrategias degenerate. Agente "freeze". Entorno imposible.

**Para SREG**: agregar constraint de validación causal (FOCI checks). Antagonist secundario que valide understanding genuine.

### C) Mode collapse en mutation
Mutations convergen a tipo de desafío que explota una vulnerabilidad específica.

**Para SREG**: diversity enforcement. Reset periódico con muestreo aleatorio.

### D) Impossible environments
Adversario demasiado fuerte → regret always maximal pero no learning.

**Para SREG**: probabilidad de éxito del agente de referencia debe ser > ε (ej: 5%).

### E) Overfitting a distribución de entrenamiento
Test distribution distinta → 0% generalization.

**Para SREG**: cross-validation. Train/test gap < 30% threshold.

### F) Lack of novelty measure
Sin medida domain-general, sistema genera repetitions disfrazadas.

**Para SREG**: signature vector + novelty score. Manual editorial review periódico.

## 6. Síntesis: arquitectura sugerida

```
Designer (multi-agent):
├─ WorldSpec Generator (mutación + evolutionary)
├─ GoldQuestion Composer
├─ Archive (MAP-Elites indexed by signature)
└─ Learnability Validator (regret + antagonist)

Training Loop:
1. Sample WorldSpec from frontier (high novelty OR high uncertainty)
2. Sample GoldQuestion (regret-based ranking)
3. Train Solver (RL/symbolic) on (World, Task)
4. Measure: regret, learnability, signature vector
5. Update archive, feedback Designer
6. If diversity_gap > threshold: mutate random archive member
7. If regret_stagnation: inject antagonist validation
```

## 7. Referencias clave

- [1504.04909](https://arxiv.org/abs/1504.04909) — MAP-Elites (Mouret, Clune)
- [1703.06907](https://arxiv.org/abs/1703.06907) — Domain Randomization (Tobin et al.)
- [1810.08272](https://arxiv.org/abs/1810.08272) — BabyAI
- [1901.01753](https://arxiv.org/abs/1901.01753) — POET
- [1904.04762](https://arxiv.org/abs/1904.04762) — Active Domain Randomization
- [1912.01588](https://arxiv.org/abs/1912.01588) — Procgen
- [2003.08536](https://arxiv.org/abs/2003.08536) — Enhanced POET
- [2010.03934](https://arxiv.org/abs/2010.03934) — PLR
- [2107.12808](https://arxiv.org/abs/2107.12808) — XLand
- [2109.13202](https://arxiv.org/abs/2109.13202) — MiniHack
- [2110.03239](https://arxiv.org/abs/2110.03239) — DR limits (ICLR 2022)
- [2203.01302](https://arxiv.org/abs/2203.01302) — ACCEL
- [2305.16291](https://arxiv.org/abs/2305.16291) — Voyager
- [2310.12931](https://arxiv.org/abs/2310.12931) — Eureka
- [2402.15391](https://arxiv.org/abs/2402.15391) — Genie
- [2402.16801](https://arxiv.org/abs/2402.16801) — Craftax
- [2406.04268](https://arxiv.org/abs/2406.04268) — Open-Endedness is Essential for ASI (Hughes et al., DeepMind)
- **Stanley & Lehman**: *Why Greatness Cannot Be Planned* (libro)
