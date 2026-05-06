# Survey: técnicas de diseño de mundos y tareas (transferibles a SREG)

> **Doc canónico** del survey de técnicas de diseño tomadas de fuera de
> nuestro dominio (NO causal inference, NO scientific benchmarks — eso ya
> está cubierto en `related_work_*.md` y `external_benchmarks_transfer_analysis.md`).
>
> Foco: trabajos *estructuralmente* similares a SREG — generan mundos,
> derivan tareas, validan soluciones — pero en otros contextos (videojuegos,
> RL benchmarks, LLM systems, mystery design humano).
>
> Generado en 2026-05-05 con 4 agentes Explore en paralelo. Reportes
> detallados en `research/notes/world_design_*.md` (PCG, mystery, UED, LLM).

---

## 1. Por qué este doc

SREG resuelve un problema que se parece estructuralmente a problemas que game designers, RL researchers y LLM-system builders vienen atacando hace décadas:

> **Generar un mundo + derivar tareas verificables sobre él, donde un agente debe descubrir o resolver algo, y donde la verdad existe pero no se filtra al agente trivialmente.**

Esa abstracción cubre: niveles de Spelunky, mundos de Outer Wilds, escenarios de Gumshoe, environments de POET, tareas generadas por GenSim, simulaciones de AI Scientist. Cada uno aporta heurísticas distintas que SREG puede tomar prestadas.

Este survey identifica las 12 técnicas más transferibles, mapea cada una a una etapa del Designer SREG (Architect / Validators / Question Designer / Validator transversal), y marca cuáles ya implementamos vs. cuáles faltan.

## 2. Mapa de los 4 verticales

| Vertical | Foco | Reporte detallado |
|---|---|---|
| 1. **PCG en videojuegos** | Generación algorítmica de mundos: Wave Function Collapse, ASP, búsqueda evolutiva, L-systems, MAP-Elites; Spelunky, Dwarf Fortress, Caves of Qud, Minecraft, NMS | [world_design_pcg.md](../notes/world_design_pcg.md) |
| 2. **Mystery & Discovery design** | Investigaciones diseñadas por humanos: Obra Dinn, Outer Wilds, Disco Elysium, Tunic, Heaven's Vault, TTRPG (Three-Clue Rule, Gumshoe, Brindlewood Bay) | [world_design_mystery.md](../notes/world_design_mystery.md) |
| 3. **UED & Open-Endedness en RL** | Generación adaptativa de entornos al borde de la dificultad: POET, PAIRED, ACCEL, PLR, MAP-Elites, XLand, Voyager, Genie | [world_design_ued.md](../notes/world_design_ued.md) |
| 4. **LLM-as-environment-designer** | Estado del arte (2023-2026): GenSim, RoboGen, Eureka, Voyager, AI Scientist, Auto MC-Reward, AutoGen, CAMEL, ChatDev | [world_design_llm.md](../notes/world_design_llm.md) |

## 3. Convergencias entre verticales

Muchas ideas aparecen en múltiples verticales — eso es señal de que son robustas. Las identifico explícitamente porque son las que más fuerza tienen:

| Convergencia | Mystery | PCG | UED | LLM |
|---|---|---|---|---|
| **Sobre-determinación de la verdad** | Three Clue Rule, multi-channel | Validar solvability durante gen | Behavioral diversity | Multi-agent verification |
| **Generación multi-capa** | Discovery loop iterativo | Dwarf Fortress 6 capas | Mutation + archive | Pipeline propose→generate→learn |
| **Archivo + retrieval** | — | MAP-Elites | MAP-Elites, PLR | Voyager skill library |
| **Evolución sobre archive** | — | Búsqueda evolutiva | ACCEL, POET | Eureka |
| **Validación durante gen, no post-hoc** | Solvability through redundancy | Spelunky flood-fill | Regret-based selection | "LLM proposes, code verifies" |
| **Anti-leak por construcción** | Outer Wilds, Tunic | — | — | HoloDeck asset checks |
| **Feedback cuantitativo, no binary** | — | — | margin, fragility | Eureka reward reflection |

## 4. Las 12 técnicas más transferibles a SREG

Ordenadas por aplicabilidad inmediata × valor.

### 4.1 Three-Clue Rule (Justin Alexander, mystery design)

**Origen**: TTRPG mystery design. "Para cualquier conclusión crítica del misterio, incluir mínimo 3 pistas independientes que la sostengan." Asume que los investigadores fallarán, ignorarán o malinterpretarán.

**Mapeo a SREG**: cada `GoldQuestion` debe ser respondible por **≥2 caminos independientes** de evidencia en el dataset visible. Si solo un camino lleva a la conclusión, y el LLM no lo explora, queda stuck.

**Etapa**: Validator transversal — agregar como check #11.

**Estado actual**: NO implementado. El check #6 (answerability pública) verifica que la GQ sea respondible, pero NO que tenga ≥2 caminos.

**Cómo implementarlo**: para cada GQ, contar cuántos subsets disjuntos de variables del dataset visible permiten estimar el AnswerKey. Si solo 1 → flag para reformular o agregar variables.

### 4.2 Multi-channel evidence (Obra Dinn)

**Origen**: Lucas Pope sobre Obra Dinn. La identidad de un personaje se revela por uniforme + acento + ubicación + rol mencionado. Cualquier subconjunto de 2+ específicos es suficiente.

**Mapeo a SREG**: cada parámetro estructural θ del SCM/ODE debe afectar ≥3 variables observables, y de **formas distintas** (pendiente, magnitud, varianza, dependencia condicional). Si θ solo afecta una variable, el LLM no puede triangular.

**Etapa**: Architect — al diseñar el WorldSpec.

**Estado actual**: NO implementado explícitamente. Es accidental hoy.

**Cómo implementarlo**: nuevo `IntendedPhenomenon.observability_signature` con lista de canales por los cuales el fenómeno se manifiesta. Validator verifica diversity ≥3.

### 4.3 Generación multi-capa con retroactive coherence (Dwarf Fortress + Caves of Qud)

**Origen**: Dwarf Fortress genera en 6 capas: topografía → geología → biomas → civs → historia → leyendas. Cada capa es input de la siguiente. Caves of Qud agrega *retroactive coherence*: genera eventos primero, los racionaliza narrativamente después.

**Mapeo a SREG**: el flujo actual ya es multi-capa (PaperInsights → WorldSpec → Validators → ValidatedPhenomena → QuestionsBundle → ResearchCase). Pero no aprovechamos *retroactive coherence*: el Question Designer podría descubrir fenómenos no anticipados por el Architect (ej. heterogeneidad por decil que el wildcard challenger reportaba) y formular GQs sobre ellos.

**Etapa**: Question Designer — extender input para incluir "fenómenos emergentes detectados por Validators más allá de los `IntendedPhenomenon`".

**Estado actual**: PARCIALMENTE implementado (multi-capa sí; retroactive coherence no, lo eliminamos al sacar el wildcard).

**Cómo implementarlo**: cuando un Validator escribe scripts contra el Environment, registrar también "incidental findings" (correlaciones fuertes no anticipadas). El Question Designer puede usarlos como base para GQs adicionales — opcionalmente reservado a v1.6.

### 4.4 Solvability validation DURANTE la generación (Spelunky + LLM proposes/code verifies)

**Origen**: Spelunky valida connectivity con flood-fill DURANTE la generación, no al final. Ejemplos LLM (Eureka, GenSim, RoboGen) usan "LLM proposes, code verifies" — generación + ejecución en loop.

**Mapeo a SREG**: ya es el corazón del flujo — Validators ejecutan scripts contra el Environment y dan feedback al Architect. Esto está bien.

**Etapa**: Architect ↔ Validators (loop ya implementado).

**Estado actual**: IMPLEMENTADO. Es el feedback loop con hard cap 3.

**Refuerzo**: el `ValidatorVote.margin` y `fragility` ya capturan esto bien.

### 4.5 Feedback estructurado y cuantitativo (Eureka reward reflection)

**Origen**: Eureka, en cada iteración, da al LLM resúmenes estructurados (learning curves, sample efficiency) + reasoning sobre por qué funcionó. NO solo "pass/fail".

**Mapeo a SREG**: nuestro `ValidatorVote` ya tiene `margin + fragility + delta_from_previous + failure_reason`. Pero podríamos enriquecer: incluir también "qué scripts probó el Validator", "qué N samples usaba", "qué CI obtuvo".

**Etapa**: Validators output.

**Estado actual**: PARCIALMENTE implementado.

**Refuerzo**: agregar a `ValidatorVote` un campo `diagnostics: dict` libre con metadata de la verificación (sample size, CI, varianza muestral). Útil para futuro tuning.

### 4.6 Discovery loop iterativo + knowledge-based progression (Outer Wilds + Voyager)

**Origen**: Outer Wilds — el progreso es saber, no items. El bloqueo es epistémico, no mecánico. Voyager — el LLM agente avanza por minimización de "state visitation entropy".

**Mapeo a SREG**: el Investigator (en runtime) tiene loop `observe → hipótesis → verifica → refina`. SREG debe garantizar que cada paso del loop genera información nueva, NO que el agente se atasque en preguntas que el dataset no puede responder.

**Etapa**: Validator transversal — check #6 (answerability pública) ya cubre esto, pero podría enriquecerse.

**Estado actual**: PARCIALMENTE implementado. El check #6 verifica "respondible con dataset visible", pero no verifica que haya un camino *iterativo* claro.

**Cómo implementarlo**: simular el loop con un "reference investigator" — si el agente puede formular ≥3 preguntas progresivamente más específicas y avanzar, el caso pasa el check de "discovery loop válido".

### 4.7 MAP-Elites archive con behavioral characterization (Quality-Diversity, Voyager skill library)

**Origen**: MAP-Elites mantiene archive de soluciones indexadas por nicho behavioral. Voyager mantiene biblioteca de skills con embeddings semánticos.

**Mapeo a SREG**: archivo persistente de WorldSpecs validados, indexados por (formalismo × tipo de fenómeno × dominio). Permite:
- Detectar convergencia a "recetas".
- Retrieval de specs anteriores antes de generar nuevas (Architect puede mutar en lugar de generar from scratch).
- Diversity score corpus-level.

**Etapa**: nivel sistema (no por etapa). Hook reservado a v1.6.

**Estado actual**: NO implementado. Hook reservado en `multi_explorer_redesign.md` §7.

**Cómo implementarlo en v1.6**: SQLite + embeddings (sentence-transformers). Cada WorldSpec validado se guarda con su signature vector. Antes de generar nuevo, el Architect retrieves top-K similares.

### 4.8 Mutación compositiva sobre archive (ACCEL + Eureka)

**Origen**: ACCEL muta niveles existentes con regret alta (mejor que generar from scratch). Eureka muta reward functions ganadoras.

**Mapeo a SREG**: una vez que el archive de la idea 4.7 existe, el Architect puede:
- Tomar un WorldSpec exitoso del archive
- Aplicar operadores de mutación: add latent confounder, reverse edge, perturb coef, change formalism
- Validar y archivar nueva variante

**Etapa**: Architect en v1.6.

**Estado actual**: NO implementado.

**Cómo implementarlo en v1.6**: definir conjunto de mutation operators sobre WorldSpec (similar a operadores genéticos). Cada operador es un transform validable. Architect puede ejecutar `mutate(world_spec, operator)` antes de pedir Validators.

### 4.9 Anti-leak por construcción: knowledge-based, no léxico (Outer Wilds + Tunic + The Witness)

**Origen**: Outer Wilds enseña conceptos sin texto. The Witness enseña reglas mediante puzzles que se auto-explican. Tunic: el manual del juego ES el descubrimiento.

**Mapeo a SREG**: el brief no debe leakear conceptos clave del paper. El `narrative_capsule` saneada que ya tenemos va en esta dirección. Más fuerte aún: el brief debe describir qué se observa (variables, dataset) sin dar la *interpretación* (mecanismo, paradoja).

**Etapa**: Case Writer + Validator transversal (check #3 ya cubre leak).

**Estado actual**: IMPLEMENTADO. Refuerzo posible: hacer el check de leak más sofisticado (no solo regex; usar LLM judge entrenado en detectar filtración semántica).

### 4.10 Manejo de dificultad sin bloqueo absoluto (Gumshoe + ACCEL regret + AI Scientist closed-loop)

**Origen**: Gumshoe — las pistas se entregan automáticamente; la dificultad está en interpretación. ACCEL — regret-based selection mantiene niveles "al borde". AI Scientist — closed-loop con feedback.

**Mapeo a SREG**: el Validator transversal check #4 (trivialness con lazy investigator) y #10 (salience threshold) cubren los extremos (trivial / imposible). Falta: medir dificultad *intermedia* — cuán cerca del borde está el caso.

**Etapa**: Validator transversal — extender check #4.

**Estado actual**: PARCIALMENTE implementado. Hoy es trivialness binaria.

**Cómo implementarlo**: en lugar de "lazy investigator scorea < 0.3", correr un "reference investigator" estándar (no lazy) y medir su score. Casos óptimos: 0.4 < score < 0.7 (no trivial, no imposible). Más caro pero mejor calibración.

### 4.11 Skill library con retrieval-augmented generation (Voyager + LLM patterns)

**Origen**: Voyager almacena código de skills exitosos con embeddings. Cuando hay nueva task, retrieve k-nearest. El LLM compone/adapta antes de generar de novo.

**Mapeo a SREG**: paralelo al 4.7 pero a nivel scripts. La biblioteca de "scripts canónicos para verificar fenómenos" (ej: estimar ATE, detectar bifurcación, medir confounding) puede crecer iter-a-iter. Validators retrievean templates antes de escribir nuevo código.

**Etapa**: Validators en v1.6.

**Estado actual**: NO implementado.

**Cómo implementarlo en v1.6**: cada `EvidenceArtifact` exitoso se guarda con `tag` semántico. Antes de escribir nuevo script, Validator hace embedding del intended_phenomenon y retrievea top-3 EvidenceArtifacts similares como ejemplos.

### 4.12 Adversarial / "antagonist" validator (PAIRED + Auto MC-Reward critic)

**Origen**: PAIRED introduce protagonist + antagonist + adversary. Auto MC-Reward tiene Reward Designer + Reward Critic.

**Mapeo a SREG**: además del Validator transversal con 10 checks, podría haber un "adversarial Validator" que intenta romper el caso. Por ejemplo: ejecuta un solver que hace **specification gaming** (busca soluciones triviales que pasan checks pero no entienden el fenómeno). Si lo logra, el caso necesita reforzarse.

**Etapa**: Validator transversal — opcional adicional.

**Estado actual**: NO implementado. El check #4 (lazy investigator) es algo similar pero pasivo.

**Cómo implementarlo**: agregar un "red team validator" que recibe el ResearchCase y trata de obtener score > 0.7 sin entender el mecanismo verdadero. Si lo logra → caso vulnerable a gaming → re-iterar con `target="case"` o `target="designer"`.

## 5. Estado de adopción en SREG

| Técnica | Estado en v1.5 | Acción |
|---|---|---|
| 4.1 Three-Clue Rule (≥2 caminos a GQ) | NO | **Agregar a Validator transversal como check #11 — v1.5 final** |
| 4.2 Multi-channel evidence | NO | **Agregar `observability_signature` a IntendedPhenomenon — v1.5 final** |
| 4.3 Retroactive coherence (incidental findings) | PARCIAL | Reservado v1.6 (ya está como hook "open scoring") |
| 4.4 Solvability durante gen | SÍ | Mantener |
| 4.5 Feedback cuantitativo | PARCIAL | **Agregar `diagnostics: dict` a ValidatorVote — v1.5 final** |
| 4.6 Discovery loop iterativo | PARCIAL | **Mejorar check #6 con reference investigator multi-step — v1.5 final** |
| 4.7 MAP-Elites archive | NO | Reservado v1.6 |
| 4.8 Mutación compositiva | NO | Reservado v1.6 |
| 4.9 Anti-leak por construcción | SÍ (con narrative_capsule) | Mantener |
| 4.10 Dificultad calibrada (no solo trivialness) | PARCIAL | **Mejorar check #4 con reference investigator — v1.5 final** |
| 4.11 Skill library de scripts | NO | Reservado v1.6 |
| 4.12 Antagonist validator | NO | Reservado v1.6 (cuando RL training entre) |

**4 ítems para incorporar al diseño v1.5 final ANTES de implementar contratos**:
1. Check #11 al Validator transversal: ≥2 caminos por GQ (Three-Clue Rule).
2. `IntendedPhenomenon.observability_signature` para forzar multi-channel.
3. `ValidatorVote.diagnostics: dict` libre.
4. Check #6 + #4 enriquecidos con "reference investigator multi-step" (no solo lazy).

**5 ítems explícitamente reservados a v1.6+**:
- 4.3 retroactive coherence (incidental findings),
- 4.7 MAP-Elites archive corpus-level,
- 4.8 mutación compositiva,
- 4.11 skill library scripts,
- 4.12 antagonist validator.

---

## 5.b Adiciones del SOTA review (2026-05-06)

Tras el catálogo de ~30 proyectos del estado del arte (`sota_synthetic_envs_for_rl.md`) y la revisión post-Ronda 14 con Codex, se priorizan 5 técnicas que el survey original no cubría con el peso correcto. Se agregan al roadmap (los ítems 1, 2 y 4 absorben/extienden los items 4.6 y 4.10 originales que estaban marcados como "PARCIAL").

| Técnica | Origen | Estado | Acción |
|---|---|---|---|
| 5.b.1 **Shortcut resistance** (batería de baselines naive) | SWE-bench fail-to-pass + CLadder anti-commonsensical | NO | **Agregar al Validator transversal** como gate compuesto. Por cada caso generado, scorear baselines (`brief/prior-only`, `crude marginal`, `single pooled regression`, `wrong-but-standard adjustment`) contra los `DiscoveryTarget`s con los mismos anchors/rubric. Si un baseline pasa demasiado alto → caso rechazado. Reemplaza la versión simple "lazy investigator < 0.3" del check #4 original. |
| 5.b.2 **Difficulty band** (reference investigator) | UED + ACCEL + literatura RL | NO | **Agregar al Validator transversal**. Reference investigator estándar (no naive baseline) corrido contra el caso; banda esperada 0.4-0.7 sobre la rubric (ni trivial ni imposible). Distinto de 5.b.1: shortcut resistance descarta casos que un *naive* resuelve; difficulty band descarta casos que un *standard* no puede ni intentar. Los dos son necesarios. |
| 5.b.3 **Evidence-consulted logging** (3 estados) | PATHWAYS, AgentClinic, OrgForge-IT | NO | **Agregar al Investigator runtime + Evaluator** (Fase 6). Trackear qué variables/subsets el Investigator efectivamente leyó en `python_exec` antes de cada claim. 3 estados: `supported` (claim cita evidence presente en trace), `underspecified` (claim correcta pero genérica, OK), `fabricated` (claim afirma evidence que nunca consultó, penalizar duro). Solo claims cuantitativas/comparativas/exclusionarias/mecanísticas fuertes requieren cita explícita. **Integrity gate, no trace scoring completo.** Probable adelantar `EvidenceArtifact.access_mode` (hoy hook v1.6) para diferenciar evidencia public vs latente. |
| 5.b.4 **Parametric variations** (mismo SCM, variar N/ruido/effect size) | DiscoveryWorld parametric variations + Procgen seeds | NO | **Agregar al Architect / Designer** (Fase 2-3). Sobre un SCM topológico ya validado, generar N instancias variando: tamaño de muestra, magnitud del efecto, nivel de ruido, prevalencia de subgrupos. Da curriculum sin re-diseñar mundos desde cero. Reemplaza "muchos SCMs distintos" por "pocos SCMs explorados profundamente". |
| 5.b.5 **Semantic triplets** (suite de evaluación pareada) | CLadder commonsensical/abstract/anti-commonsensical | NO | **Agregar al Discovery Designer / Case Writer** (Fases 3-4). Tripletes `same world, same targets, same data distribution, different surface semantics`. Mide contaminación semántica limpiamente (priors LLM vs estructura causal real). NO triplicar todos los casos del generator (sesga distribución, infla costo); implementar primero como **eval suite separada**, después samplear `semantic_mode` estocásticamente si entra al training. Agregar `ResearchCase.semantic_mode: Literal["realistic","abstract","anti_commonsensical"]` desde ya para trazabilidad. |

**Nuevo orden de prioridad operativa** (post-Codex):

1. **Shortcut resistance** acoplado a **difficulty band** (los dos van juntos: shortcut filtra "casos triviales" + difficulty band filtra "casos imposibles"). Sin esta dupla, SREG sigue exponiendo casos no-triviales pero tampoco didácticos.
2. **Evidence logging liviano** (citas a steps, no variable-level perfecto).
3. **Parametric variations** sobre SCM validado.
4. **Semantic triplets** como eval suite (no flag global del generator).
5. **DoVerifier-style symbolic equivalence**: dejar `match="causal_equiv"` como hook futuro, NO bloquear v1.5 por esto. El paper existe (ACL 2026) pero el repo está verde (3 commits, sin packaging).

**Resultado en Validator transversal**: pasa de **10 checks** a **12 checks** (los 10 originales + shortcut resistance + difficulty band; nota que los #4 y #6 originales se compactan/refactorizan al fusionarse con los nuevos).

**Anti-pattern crítico que el SOTA review confirma**: NO usar self-play estilo Absolute Zero (uh-oh moment), NO densos process rewards (PRMs son fluency detectors según arXiv:2603.06621), NO LLM-as-judge como verificador primario, NO expansión hacia "end-to-end scientific discovery" estilo CodeScientist (6/19 minimal soundness rate documenta el ceiling).

## 6. Anti-patterns consolidados

De los 4 verticales, anti-patterns que SREG debe evitar:

1. **Falta de validación early** (PCG): generar sin verificar solvability hasta el final es costoso. ✅ ya cubierto con feedback loop.
2. **Mode collapse / task collapse** (LLM, RL): Designer genera siempre la misma receta. ⚠️ requiere archive corpus-level (4.7) — v1.6.
3. **Plausible but wrong specifications** (LLM): spec parsea, simula, pero intent es incorrecto. ✅ parcialmente cubierto con 10 checks; refuerzo con antagonist (4.12) en v1.6.
4. **Specification gaming / reward hacking** (LLM, RL): Solver descubre loophole que viola intent. ⚠️ requiere antagonist validator — v1.6.
5. **Hill-climbing ciego** (UED): cambiar coef para arreglar fenómeno A rompe fenómeno B. ✅ parcialmente cubierto con `delta_from_previous` y hard cap 3.
6. **Single-clue gating** (mystery): si el LLM no encuentra "la" pista clave, queda stuck. ⚠️ requiere Three-Clue Rule (4.1) — v1.5 final.
7. **Trivialness disfrazada** (mystery + RL): caso pasa checks pero respuesta es trivial. ✅ check #4 lo intenta; refuerzo con reference investigator multi-step (4.10) — v1.5 final.
8. **Leak léxico residual** (mystery): brief no menciona "collider" pero menciona "ten cuidado con confounders no observados". ✅ con narrative_capsule + LLM judge para leak semántico.
9. **Overfitting a distribución de training** (RL): test distribution distinta → 0% generalization. ⚠️ requiere diversidad corpus-level (4.7) — v1.6.
10. **Hallucinated specifications** (LLM): WorldSpec con coefs no físicos / ODE que diverge. ✅ parcialmente cubierto con check #2 (provenance).

## 7. Roadmap sugerido

**Antes de cerrar diseño v1.5** (próxima ronda):
- Agregar 4 ítems de §5 al diseño (3-Clue check, observability_signature, diagnostics, reference investigator multi-step).
- Codex review final.
- Aplicar a contratos Pydantic.

**v1.5 implementación**:
- Implementar Designer + Validators con 11 checks + `ValidatorVote` enriquecido.
- Pilot humano con 5-10 casos diversos.

**v1.6 (post-MVP)**:
- MAP-Elites archive corpus-level + signature vectors.
- Mutación compositiva sobre archive.
- Skill library de EvidenceArtifacts.
- Antagonist validator opcional.
- Open scoring del Solver con `extra_claims`.

**v2 (Sherlock multi-turn)**:
- Investigator interactivo (observe / intervene / simulate como acciones).
- Co-evolution Designer ↔ Solver para RL training.

## 8. Referencias top consolidadas

**Mystery design (lo más rico para principios de investigación)**:
- [The Alexandrian — Three Clue Rule + Node-Based Design](https://thealexandrian.net)
- [Pelgrane Press — GUMSHOE system](https://pelgranepress.com/2018/02/14/gumshoe/)
- [Obra Dinn / Outer Wilds / Heaven's Vault interviews — Game Developer + 80.lv]

**PCG (técnicas formales)**:
- [Shaker, Togelius & Nelson 2016, "PCG in Games" textbook](https://www.pcgbook.com/)
- [Smith & Mateas 2011, "ASP for PCG"](https://adamsmith.as/papers/tciaig-asp4pcg.pdf)
- [Maxim Gumin, WaveFunctionCollapse](https://github.com/mxgmn/WaveFunctionCollapse)

**UED & Open-Endedness**:
- [POET — 1901.01753](https://arxiv.org/abs/1901.01753)
- [PAIRED — Dennis et al. NeurIPS 2020]
- [ACCEL — 2203.01302](https://arxiv.org/abs/2203.01302)
- [PLR — 2010.03934](https://arxiv.org/abs/2010.03934)
- [MAP-Elites — 1504.04909](https://arxiv.org/abs/1504.04909)
- [Open-Endedness is Essential for ASI — 2406.04268](https://arxiv.org/abs/2406.04268)

**LLM-as-environment-designer**:
- [Eureka — 2310.12931](https://arxiv.org/abs/2310.12931)
- [Voyager — 2305.16291](https://arxiv.org/abs/2305.16291)
- [GenSim — 2310.01361](https://arxiv.org/abs/2310.01361)
- [RoboGen — 2311.01455](https://arxiv.org/abs/2311.01455)
- [AI Scientist — 2408.06292](https://arxiv.org/abs/2408.06292)
- [Auto MC-Reward — 2312.09238](https://arxiv.org/abs/2312.09238)

**Reportes detallados**:
- `research/notes/world_design_pcg.md`
- `research/notes/world_design_mystery.md`
- `research/notes/world_design_ued.md`
- `research/notes/world_design_llm.md`
