# SREG — TODO

> Single source of truth for task tracking.
> Statuses: `[ ]` pending | `[~]` in progress | `[x]` done | `[-]` cancelled
> Vision and scope: see PROJECT.md

## Done — v0+v1 (Etapa 1: motifs curados)
- [x] Pydantic data contracts (World, Episode, Task, Score, etc.)
- [x] World generation + validation (latent_preference template, WorldCheckTool)
- [x] Teacher solver (exact Bayesian inference, optimal actions, >90% accuracy)
- [x] Episodes, tasks, verifier, EpisodeRunner
- [x] LLM Orchestrator (world generation via tool calling)
- [x] Semantic layer (names, narrative, data presentation, ResearchProblem)
- [x] LLM Agent solver (observe/submit loop, comparison with teacher/random)
- [x] End-to-end pipeline: orchestrator -> agent -> score (scripts/test_e2e.py)
- [x] Teacher trajectory export as JSONL (problem, actions, observations, posteriors)
- [x] Batch evaluation: generate N problems programmatically, run agent + teacher, collect metrics
- [x] Summary report: agent vs teacher vs random across difficulty levels
- [x] Causal chain template (with semantic layer from start)
- [x] Fork/collider template (with semantic layer from start)
- [x] `next_best_observation` task type
- [x] `hypothesis_selection` task type
- [x] Multiple evaluations per problem: same world generates all 3 task types together

## Loose ends (v0+v1)
- [ ] Update demo script and notebook
- [ ] Run batch eval across varying parameters (nodes, edge_strength, budget)

## Known issues (from E2E testing, 2026-03-07)
- [ ] Agent submit format: LLM sends flat keys instead of `{"distribution": {...}}`, wastes 1 turn on retry every time
- [ ] Agent worse than random on 8-node worlds: bad inference when more variables are involved (soil case KL 4.21 vs random 0.30)
- [ ] Orchestrator ignores difficulty in goal: always generates "easy" regardless of "hard difficulty" in prompt
- [ ] `apply_semantics` always fails first call: LLM sends empty `node_renames`, then retries correctly (wastes 1 API call)
- [ ] Agent variable selection suboptimal: doesn't pick most informative variables (different order than teacher)
- [ ] NBO trivial tasks (25%): when enough evidence is given, all remaining nodes have IG=0 (0% in latent_preference, 28% in causal_chain, 48% in fork_collider). Should filter or regenerate so at least one node has IG > 0
  - **Fix**: in `_next_best_observation_task`, after sampling evidence, check `max(ig_ranking.values()) > 0`. If not, resample with less evidence (loop until at least one remaining node is informative). Cap retries to avoid infinite loop on degenerate worlds.
- [ ] Hypothesis near-indistinguishable with low edge_strength: at es=0.3, true posterior vs reversed can have KL as low as 0.0097, making the task nearly impossible to solve correctly
  - **Fix**: after generating hypotheses, check min KL between true posterior and nearest distractor is above a threshold (e.g., 0.05). If not, either regenerate with different evidence, replace the reversed distractor with a different one (e.g., sample from a Dirichlet), or skip hypothesis_selection for that world/seed combo.

## v2 — Composicion controlada + research cases (Etapa 2)

> Estrategia de investigacion y diseno detallado en **`WORLD_DESIGN.md`**.

### Prototipo DAGSpec (slice minimo — completo)
- [x] `DAGSpec` + `DAGNodeSpec` models: Pydantic contract with validations (acyclic, max parents <=4, required types)
- [x] `cpd_gen.py`: extract shared CPD generation from 3 templates (eliminate copy-paste)
- [x] `CustomTemplate`: accepts DAGSpec, generates valid CPDs using generic edge_strength logic → World
- [x] WorldCheck extended: max parents check + treewidth metric (warning, not failure)
- [x] `generate_custom()` method in WorldGenTool (separate from `generate()` — API to be unified, but both input paths are permanent)
- [x] All 3 task types work with custom worlds (TaskGenTool + TaskBundle)
- [x] Tests: custom worlds with 5-15 nodes, heterogeneous states, multiple latents (81 new tests)
- [x] E2E validation: 12-15 node worlds, teacher improves over prior + beats random, documented findings in WORLD_DESIGN.md

### QualitySuite v2 — metricas rediseñadas (PRIORIDAD)
> Hallazgo critico: la metrica original teacher_beats_prior (KL vs one-hot del true state)
> castiga inferencia correcta cuando el sample es atipico. Ver WORLD_DESIGN.md "Hallazgo critico".

- [x] QualitySuite v1: Capas A+B+C implementadas con metricas originales (44 tests)
- [x] Documentar hallazgo critico y metricas rediseñadas en WORLD_DESIGN.md
- [~] Rediseñar Capa B con multi-rollout:
  - [ ] Cambiar `compute_task_quality()` para aceptar lista de seeds (K=5-10 rollouts)
  - [ ] Agregar metricas de diseno: `budget_ratio` (budget / observables con path al target)
  - [ ] Agregar `mean_entropy_reduction` como metrica principal de belief quality
  - [ ] Agregar `mean_nll_improvement`, `mean_teacher_nll`, `mean_prior_nll`, `mean_random_nll`
  - [ ] Agregar `teacher_beats_random_rate` (fraccion de rollouts)
  - [ ] Agregar `nbo_nontrivial_rate` y `hyp_distinguishable_rate` (multi-rollout)
  - [ ] Renombrar metricas viejas: `teacher_kl` → `sampled_nll_teacher`, etc. (diagnostico)
  - [ ] Redefinir `useful_bundle`: entropy_reduction > 0.1 AND 2 de 3 (nbo, hyp, budget_ratio)
- [ ] Ajustar Capa C: reemplazar `ig_gap_std` por `entropy_reduction_std`
- [ ] Actualizar tests para nuevas metricas
- [ ] E2E con LLM: verificar que las metricas nuevas dan resultados coherentes
- [ ] Recorrer batches grandes y comparar generators/templates con metricas v2

### Composicion de motifs (siguiente — despues del prototipo)
- [ ] Motif composer: combine chain+fork+collider into a single DAGSpec
- [x] DAG generators: Erdos-Renyi, spanning tree, preferential attachment, layered (inspired by Reasoning Core)
- [ ] Expressive range analysis: generate 100+ worlds, measure distributions, detect biases

### Integracion LLM orchestrator + DAGSpec
- [x] `dag_generate` tool: LLM elige generador (erdos_renyi, layered, etc.) + parametros -> DAGSpec automatico
- [x] `dag_construct` tool: LLM especifica nodos y aristas manualmente -> DAGSpec custom
- [ ] Unificar `generate()` y `generate_custom()` en una sola API de WorldGenTool
- [ ] Seeds desde papers: LLM extrae estructura causal de texto -> `dag_construct`

### Datos mas ricos
- [ ] Multiple datasets per problem (tabular + observations + partial data)
- [ ] Missing data / incomplete observations
- [ ] Variable action costs (not all cost 1)
- [ ] Richer data sampler: multiple formats, metadata

### Semantic mode (pregunta abierta — ver WORLD_DESIGN.md #5)
- [ ] Decidir: semantic_mode configurable (full / abstract / fictional)
- [ ] Implementar modo abstracto (sin apply_semantics, variables genéricas)
- [ ] Experimentar: comparar respuestas del agent en cada modo

### Narrativa elaborada
- [ ] Theoretical context: prior studies, hints, misleading context
- [ ] Richer semantic layer: apply_semantics generates multi-paragraph narrative
- [ ] Domain-specific action descriptions (not just "observe X")

## v3 — Mechanism-first + evaluacion profunda (Etapa 3)

### Mechanism-first design
- [ ] `MechanismSpec` model: subgraph + semantics + shared variables
- [ ] Mechanism library: 5-10 reusable base mechanisms
- [ ] `WorldComposer`: combines mechanisms into a world (resolves conflicts, shared vars)
- [ ] Rival mechanisms as competing hypotheses (structure selection tasks)
- [ ] Generator health metrics: acceptance rate, structural diversity, distinguishability
- [ ] `CaseBundle` concept: world + semantics + evidence + actions + multiple evaluations

### Research cases integrados
- [ ] Integrated multi-question problems: one budget, multiple evaluation points
- [ ] Seeds from papers or documents (LLM extracts DAG structure → CustomTemplate)

### Evaluacion avanzada
- [ ] Intervention tasks (do-calculus via graph surgery)
- [ ] Structure recovery tasks (SHD evaluation)

## Backlog
- [ ] Continuous variables (Gaussian CPDs, mixed worlds)
- [ ] Synthetic document artifacts (papers, reports, notes)
- [ ] Process rubrics (evaluate reasoning quality, not just answer)
- [ ] Approximate inference teacher (larger worlds)
- [ ] Complex agent actions (multi-node, conditional)
- [ ] Curriculum over world complexity
- [ ] RL training loop with verifier as reward
