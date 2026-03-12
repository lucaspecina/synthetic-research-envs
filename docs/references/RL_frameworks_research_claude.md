# Frameworks de RL para entrenar LLMs: guía técnica para SREG

**GRPO con recompensas verificables es el algoritmo dominante en 2025 para vuestro caso**, y la combinación más práctica para 1-2 GPUs Azure con entorno multi-turn es **TRL + Unsloth para prototipar rápido y verifiers/prime-rl para multi-turn real**. Ningún framework resuelve perfectamente el escenario completo (multi-turn + escala pequeña + entorno custom) — todos requieren trade-offs. El coste estimado de un run de entrenamiento significativo oscila entre **$30-500 USD** en Azure con instancias spot, haciendo el proyecto económicamente viable. A continuación, el análisis exhaustivo de cada opción.

---

## GRPO se ha impuesto como el estándar para RLVR

Antes de evaluar frameworks, conviene entender por qué **GRPO (Group Relative Policy Optimization)** ha desplazado a PPO como algoritmo dominante para Reinforcement Learning from Verifiable Rewards. DeepSeek lo validó entrenando R1 desde cero, y prácticamente todos los frameworks lo han adoptado como método principal.

GRPO elimina la necesidad de un modelo critic/value (que en PPO típicamente tiene el mismo tamaño que el policy model), reduciendo el consumo de memoria a la mitad. En lugar de estimar ventajas con GAE, genera **G completions por prompt**, las puntúa con la función de reward, y normaliza las recompensas dentro del grupo: `A_i = (r_i - mean(r)) / std(r)`. Esto lo hace naturalmente ideal para rewards programáticos binarios o continuos como los de SREG (KL divergence, binary accuracy, IG ratio).

Para el caso multi-turn específico de SREG, un estudio empírico sistemático (Wang et al., 2025, "Practitioner's Guide to Multi-turn Agentic RL") demostró que **GRPO y PPO superan significativamente a REINFORCE++ y RLOO en entornos multi-turn**. Entre ambos, GRPO es más práctico en 1-2 GPUs por su menor footprint de memoria. La recomendación técnica es clara: **GRPO con QLoRA, G=8, KL coefficient >0.001**.

---

## Análisis detallado de cada framework

### TRL (Hugging Face) — el punto de entrada más accesible

TRL v0.29.0 es la librería de post-training más adoptada del ecosistema open-source, con **GRPOTrainer como trainer principal** (PPO fue relegado a experimental). Soporta GRPO, RLOO, DPO, KTO, y una docena más de métodos. Integrar una reward function custom de SREG es trivial:

```python
def sreg_reward(completions, **kwargs):
    return [compute_kl_divergence(c, kwargs["ground_truth"]) for c in completions]

trainer = GRPOTrainer(model="Qwen/Qwen2.5-7B-Instruct", 
                      reward_funcs=[sreg_reward], train_dataset=dataset)
```

Las columnas extra del dataset se pasan automáticamente como `**kwargs`, permitiendo acceso a ground truth, metadata del mundo bayesiano, etc. **Soporte multi-turn existe pero es experimental**: el parámetro `environment_factory` permite crear entornos con `reset()`/`step()`, y la integración con OpenEnv (Meta) añade soporte Gymnasium-style. Sin embargo, estas features son muy recientes y no están battle-tested.

En hardware, **7B con QLoRA GRPO cabe en 1× A100 80GB**. Con vLLM para generación rápida, el setup óptimo es 2× A100 (uno para training, otro para inference). Funciona en Azure sin modificaciones — existe documentación oficial de HuggingFace para Azure ML con TRL. Combinado con **Unsloth**, el consumo de VRAM se reduce drásticamente (de ~510GB a ~54GB para 8B con 8 generaciones), permitiendo entrenar modelos de 7B-14B en hardware mínimo.

| Aspecto | Valoración |
|---------|-----------|
| Algoritmos | GRPO, RLOO, DPO, KTO, PPO (experimental), +10 más |
| Multi-turn | Experimental (OpenEnv, environment_factory) |
| Custom reward | Trivial — función Python directa |
| Min hardware | 1× A100 80GB (QLoRA), 2× A100 (con vLLM) |
| Azure | Totalmente compatible, documentación oficial |
| Madurez | Alta para single-turn GRPO; baja para multi-turn |

**Limitación honesta**: el soporte multi-turn es el punto débil. Para episodios donde el solver de SREG hace 5-10 turnos de observar variables, razonar y decidir, TRL requiere implementar la lógica de rollout manualmente via `rollout_func` o `environment_factory`. Funcional, pero sin abstracción clean para vuestro caso.

### verifiers + prime-rl (Prime Intellect) — diseñado para multi-turn agentic RL

**verifiers** (MIT, ~3.9k stars) es una librería de componentes modulares para crear entornos RL y entrenar agentes LLM. **prime-rl** (Apache 2.0, ~1.1k stars) es el framework de training asíncrono que lo acompaña, probado entrenando INTELLECT-3 (106B MoE en 512 H200s). Ambos son **completamente independientes de la plataforma de Prime Intellect** — se clonan y corren en cualquier máquina con GPUs NVIDIA.

El soporte multi-turn es **first-class**: `MultiTurnEnv` implementa un loop de rollout que alterna entre respuestas del modelo y respuestas del entorno hasta una condición de terminación. Esto mapea directamente al flujo de SREG: el solver recibe dataset → observa variable (acción) → recibe resultado → razona → repite → submit. La integración de reward custom es elegante via `Rubric`:

```python
rubric = vf.Rubric(reward_funcs=[kl_reward, budget_penalty], weights=[1.0, 0.3])
```

prime-rl puede correr en **1 GPU con LoRA** (ejemplo: Alphabet Sort en 1× H100 en ~1 hora). verifiers requiere **mínimo 2 GPUs** para training (una para vLLM, una para training). El algoritmo es exclusivamente **GRPO asíncrono (CISPO)** — no hay soporte nativo para PPO o REINFORCE.

| Aspecto | Valoración |
|---------|-----------|
| Algoritmos | GRPO (async CISPO) únicamente |
| Multi-turn | First-class — `MultiTurnEnv` con tool calls, sandboxes |
| Custom reward | Muy fácil — `Rubric` con funciones Python |
| Min hardware | 1 GPU (prime-rl con LoRA), 2 GPUs (verifiers trainer) |
| Azure | Totalmente compatible, sin dependencias de Prime Intellect |
| Madurez | Production-proven (INTELLECT-3), pero API en flux (v0.1.x) |

**Sobre el programa de funding**: Prime Intellect ofrece Fast Compute Grants ($500-$100K) en forma de **créditos de compute en su propia plataforma** — no son créditos Azure ni cash. También tienen bounties de $100-$5K en efectivo por construir entornos. Si os dan funding, el compute corre en sus servidores (H100s agregados de 50+ datacenters). Para correr en Azure propio, simplemente usáis el código open-source sin ninguna dependencia en Prime Intellect.

**Limitación honesta**: GRPO-only, API inestable (4 releases con breaking changes en 3 meses), y el trainer integrado es intencionalmente "nano" (~1000 líneas). Para features avanzadas como curriculum learning o logging complejo, requiere más trabajo manual.

### veRL (ByteDance) — el framework más completo pero complejo

veRL (~17.9k stars, mantenido por ByteDance Seed team) es el framework con más features y mayor ecosistema. Soporta **PPO, GRPO, DAPO, REINFORCE++, RLOO, VAPO, PRIME, PF-PPO** — la lista más amplia de cualquier framework. Usa FSDP/FSDP2 para training y vLLM o SGLang para inference, orquestado por Ray.

Su soporte multi-turn es extenso desde v0.5+, con **AgentLoop** (abstracción client-side para tareas agénticas) y **server-based rollout** (v0.7, donde el LLM opera como endpoint de serving con dynamic batching por request). Múltiples proyectos de multi-turn RL se han construido sobre veRL: RAGEN, VerlTool, ReTool, DeepResearcher, VAGEN. Es el framework con mayor tracción en la comunidad para RL agéntico.

| Aspecto | Valoración |
|---------|-----------|
| Algoritmos | PPO, GRPO, DAPO, REINFORCE++, RLOO, VAPO, +5 más |
| Multi-turn | Extenso — AgentLoop, server mode, ecosistema RAGEN |
| Custom reward | Bien soportado — RewardLoop con rewards rule-based y model-based |
| Min hardware | 4× GPUs típico (demostrado en 4× L4 para 3B) |
| Azure | Compatible, sin lock-in |
| Madurez | Alta — usado por ByteDance para Doubao-1.5-pro |

**Limitación honesta para vuestro caso**: el mínimo práctico demostrado es **4 GPUs** (4× L4 para 3B con LoRA). Para 7B-14B en 1-2 A100s, veRL es una apuesta arriesgada — su arquitectura está optimizada para clusters de 8+ GPUs. La curva de aprendizaje es significativa (32K+ líneas de código vs 8.5K de OpenRLHF). Además, hay breaking changes frecuentes entre versiones.

### OpenRLHF — balance entre simplicidad y potencia

OpenRLHF (~9.1k stars) usa Ray + vLLM + DeepSpeed y destaca por su **codebase conciso (~8.5K líneas)** y su paradigma unificado de agentes: los algoritmos (PPO, GRPO, REINFORCE++) se desacoplan de los modos de ejecución (SingleTurnExecutor, MultiTurnExecutor). Esto significa que **cualquier algoritmo funciona con multi-turn** sin código adicional.

La integración de reward custom es directa: un archivo Python con `reward_func(queries, prompts, labels)` que se pasa via `--remote_rm_url /path/to/reward.py`. Alternativamente, se despliega como servidor HTTP. Soporta async multi-turn y se integra con NeMo Gym para entornos externos.

| Aspecto | Valoración |
|---------|-----------|
| Algoritmos | PPO, REINFORCE++, GRPO, RLOO, DAPO, DPO, KTO |
| Multi-turn | Nativo — `MultiTurnExecutor`, NeMo Gym |
| Custom reward | Fácil — archivo Python o servidor HTTP |
| Min hardware | 4+ RTX 4090 (7B), 8× A100 recomendado |
| Azure | Compatible |
| Madurez | Alta — usado por Google, ByteDance, Microsoft, HKUST |

**Limitación honesta**: como veRL, **4+ GPUs es el mínimo práctico para 7B**. El Hybrid Engine (`--colocate_all_models`) permite menos GPUs, pero los docs recomiendan 8× A100 para 8B. Para 1-2 GPUs es una opción forzada.

### Otros frameworks relevantes

**Unsloth** merece mención especial: envuelve TRL con kernels Triton optimizados y logra **GRPO en 7B-8B con QLoRA en una sola GPU de 15GB** (Colab gratis). Es la opción de menor barrera de entrada, pero **no soporta multi-turn RL**. Para prototipar single-turn RLVR, es imbatible.

**RAGEN** (construido sobre veRL) es el único framework específicamente diseñado para multi-turn agent RL, implementando StarPO (trajectory-level optimization). Sin embargo, sus autores documentan el **"Echo Trap"**: colapso de varianza de reward y spikes de gradiente que hacen que los agentes converjan en templates repetitivos. Es un warning importante para SREG.

**LLaMA-Factory** soporta PPO y DPO pero su RL es básico. **NeMo RL** (NVIDIA) es enterprise-grade pero overkill para 1-2 GPUs. **DeepSpeed-Chat** (Microsoft) solo soporta PPO y está esencialmente abandonado.

---

## El reto real: multi-turn en escala pequeña

El problema central de vuestro setup es la intersección de tres requisitos: **multi-turn + 1-2 GPUs + entorno custom**. Ningún framework resuelve esto out-of-the-box de forma madura:

- **TRL/Unsloth** escalan a 1 GPU pero el multi-turn es experimental
- **verifiers/prime-rl** tienen multi-turn first-class pero necesitan mínimo 2 GPUs
- **veRL/OpenRLHF** tienen multi-turn maduro pero necesitan 4-8+ GPUs

La investigación reciente sobre multi-turn RL para LLMs revela desafíos adicionales. El "Echo Trap" documentado por RAGEN muestra que sin rewards granulares por turno, los modelos colapsan en patrones repetitivos. Las mejores prácticas identificadas incluyen:

- **SFT warm-start es crítico**: inicializar con un modelo que ya siga el formato de SREG (observar, razonar, submit) antes de aplicar RL
- **Tasa de éxito base ≥20%**: si el modelo pre-RL no logra al menos 20% de éxito en los episodios, la exploración es demasiado difícil
- **Reward design para multi-turn**: reward final dominante (+1/-1 por outcome) + penalización por paso (-0.05 por turno para incentivar eficiencia) + penalización por acciones inválidas
- **KL coefficient >0.001** para estabilidad en multi-turn
- **G=8 generaciones por prompt** para ventajas estables (G=2 ahorra 75-85% tiempo con accuracy similar)

---

## Costes estimados en Azure

Los costes son sorprendentemente manejables gracias a QLoRA y spot instances.

| Escenario | VM Azure | Horas est. | Coste on-demand | Coste spot |
|-----------|----------|-----------|-----------------|------------|
| 7B, QLoRA GRPO, 1K steps | 1× NC24ads A100 | 8-25h | $29-92 | **$6-18** |
| 7B, QLoRA GRPO, 5K steps | 1× NC24ads A100 | 40-125h | $147-459 | **$30-92** |
| 14B, QLoRA GRPO, 1K steps | 2× NC24ads A100 | 17-50h | $125-367 | **$25-74** |
| 14B, QLoRA GRPO, 5K steps | 2× NC24ads A100 | 85-250h | $624-1,835 | **$125-368** |
| 7B, LoRA GRPO, 1K steps | 1× NC H100 v5 | 5-15h | $35-105 | N/A |

Las instancias spot de A100 en Azure cuestan **~$0.74/hora** (vs $3.67 on-demand), un 80% de descuento. Requiere checkpointing robusto para tolerar preemption. Alternativas como Lambda ($2.99/hr H100), RunPod ($1.99/hr), o Vast.ai ($1.49/hr) reducirían costes aún más si Azure no es requisito estricto.

**Optimizaciones clave de coste**: QLoRA reduce 4-10× la memoria vs full fine-tuning. El variant 2-GRPO (G=2) ahorra 75-85% de wall-clock time con accuracy casi idéntica. Filtrado de dificultad (seleccionar ejemplos donde el modelo tiene 30-70% pass@k) reduce compute un 60-70%.

---

## Recomendación concreta para SREG

Dada la restricción de **1-2 GPUs Azure, 7B-14B, multi-turn con reward exacto**, propongo una estrategia en dos fases:

**Fase 1 — Validación rápida (1-2 semanas, ~$50-200)**. Usar **TRL GRPOTrainer + Unsloth** en 1× A100 con QLoRA. Simplificar temporalmente SREG a single-turn: pre-generar episodios completos como pares (prompt, respuesta_final) donde el prompt incluye todo el contexto del episodio concatenado (dataset + narrativa + observaciones pre-seleccionadas). La reward function de SREG se conecta directamente como callable Python. Esto valida que el RL mejora la calidad de las respuestas del solver antes de invertir en multi-turn complejo. TRL es el camino de menor fricción, con documentación excelente, integración directa con Azure ML, y la mayor comunidad. Unsloth hace viable el training en 1 GPU.

**Fase 2 — Multi-turn real (2-4 semanas, ~$200-800)**. Migrar a **verifiers + prime-rl** en 2× A100 (o 2× H100 si el budget lo permite). verifiers es el único framework que combina multi-turn first-class, escala mínima de 2 GPUs, y facilidad de integración con entornos custom. Definir SREG como un `MultiTurnEnv` donde cada `step()` representa una acción del solver (observar variable, submit respuesta), y el `Rubric` encapsula la KL divergence / binary accuracy / IG ratio. prime-rl gestiona el training loop asíncrono con GRPO. El coste adicional de la segunda GPU es marginal (~$0.74/hr extra en spot).

**Alternativa si necesitáis máxima flexibilidad algorítmica**: veRL con RAGEN como patrón de referencia. Requiere 4 GPUs como mínimo práctico (posiblemente viable en 2× H100 con LoRA agresivo para 7B), pero ofrece PPO, GRPO, DAPO y el ecosistema multi-turn más grande. Solo recomendable si 4 GPUs están en el presupuesto.

**Lo que NO recomiendo**: OpenRLHF (escala mínima demasiado alta para 1-2 GPUs), NeMo RL (overkill empresarial), DeepSpeed-Chat (abandonado, solo PPO), LLaMA-Factory (RL demasiado básico).

---

## Resumen de trade-offs por framework

| Framework | Mejor para | Peor para | Viabilidad 1-2 GPUs |
|-----------|-----------|-----------|---------------------|
| **TRL + Unsloth** | Prototipado rápido, single-turn RLVR | Multi-turn maduro | ✅ Excelente |
| **verifiers + prime-rl** | Multi-turn agentic RL, entornos custom | Diversidad de algoritmos (solo GRPO) | ✅ Viable (2 GPUs) |
| **veRL** | Flexibilidad algorítmica, escala | Equipos pequeños, 1-2 GPUs | ⚠️ Difícil (<4 GPUs) |
| **OpenRLHF** | Balance simplicidad/potencia | Hardware limitado | ⚠️ Difícil (<4 GPUs) |
| **Unsloth solo** | Mínimo coste, 1 GPU | Multi-turn, features avanzadas | ✅ Excelente |
| **RAGEN (veRL)** | Multi-turn agent RL investigación | Producción, escala pequeña | ⚠️ Difícil (<4 GPUs) |

## Conclusión

El ecosistema de RL para LLMs en 2025-2026 ha convergido en GRPO como algoritmo estándar para rewards verificables, pero **el multi-turn agentic RL sigue siendo frontera de investigación** — todos los frameworks lo soportan en algún grado, ninguno lo resuelve trivialmente. La estrategia más pragmática para SREG es empezar con TRL+Unsloth validando que el RL funciona en una versión simplificada, y luego escalar a verifiers+prime-rl para el loop multi-turn completo. El presupuesto total para llegar a resultados significativos está en el rango de **$100-$500 en Azure spot**, asumiendo 7B con QLoRA. El mayor riesgo no es el framework ni el coste, sino los desafíos intrínsecos del multi-turn RL (Echo Trap, credit assignment, colapso de exploración) — por eso la fase de validación single-turn es crítica antes de añadir complejidad.