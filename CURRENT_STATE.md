# SREG — Estado Actual

> Foto de lo implementado hoy. Compara contra `ARCHITECTURE.md` para ver
> la brecha, contra `TODO.md` para ver el trabajo pendiente.
>
> Actualizado: 2026-03-20 (SCMTaskGenTool)

---

## Resumen ejecutivo

- **1277 tests**, todos pasando
- Pipeline E2E funcional: seed/goal → orchestrator → world → case → solver → score
- 9 eval types implementados con scoring
- Solver diagnostico: python_exec + think + submit (sin budget ni research_actions)
- Paper-seeded SRCs funcionando (PDF + markdown)
- **Responses API**: toda la codebase migrada de Chat Completions a Responses API,
  soportando todos los modelos incluyendo reasoning models (codex, o-series).
- **Dual model**: orchestrator usa `AZURE_MODEL` (default gpt-5.4), solver usa
  `AZURE_SOLVER_MODEL` (default gpt-5.2-codex). Configurable via env vars.
- 3 backends de inferencia para el solver (Azure, vLLM, transformers).
- Benchmarks externos integrados (CLadder, QRData, DiscoveryBench)
- Training adapter experimental (SregEnv/verifiers)

**Ultima validacion relevante** (5-SRC + 3-mode experiment, 2026-03-16):

- **Codex como solver**: investiga con python_exec (crosstabs, Cramer's V,
  naive Bayes, backdoor adjustment) — comportamiento data-driven real.
  Necesita deadline nudge para submitir a tiempo (75% de iteraciones).
- **Semantic modes (Vaca Muerta)**: abstract (avg 0.62) > fictional (0.82)
  > realistic (8.30). Domain priors perjudican cuando el mundo es sintetico.
- **Inspiration reports**: el orchestrator preserva bien la estructura causal
  de los papers, pero faltan eval types (mediacion, effect modification,
  selection bias, source attribution).

---

## Estado por componente

### Capa formal / world model — Estable + SCM en desarrollo

**BN discreta (legacy, estable):**
- `World`: nodos, edges, CPDs. Red bayesiana discreta via pgmpy.
- `DAGSpec`: contrato universal para DAGs arbitrarios.
- 4 templates: latent_preference, causal_chain, fork_collider, custom (DAGSpec).
- 4 DAG generators: erdos_renyi, spanning_tree, preferential_attachment, layered.
- `cpd_gen`: generacion generica de CPDs con signed ordinal scoring.
  Soporta direction (positive/negative) por edge.
- `WorldCheckTool`: valida DAG aciclico, entropia, d-separaciones, max parents,
  treewidth.
- Regimen recomendado: 10-12 nodos, edge_strength 0.5-0.7 (ver research/).

**SCM engine (nuevo, branch `feature/scm-engine`):**
- `SCMWorld`: grafo causal + ecuaciones Python arbitrarias + ruido.
  Variables continuas con unidades reales (celsius, mL/kg/min, etc).
- `sample(n, seed, do)`: sampling observacional e interventional (do-operator).
- `interventional_distribution(target, do, n)`: P(Y|do(X=x)) via Monte Carlo.
- d-separation, adjustment_set: queries de grafo puras (via networkx).
- Scoring continuo: `kl_divergence_histogram`, `kl_divergence_gaussian`,
  `wasserstein_distance`.
- 33 tests: validacion, grafos, d-separation, sampling, do-calculus,
  adjustment sets, scoring, E2E no lineal (threshold + sigmoid).
- `SCMSolver`: teacher de Monte Carlo para SCMWorld.
  - `posterior_samples(target, evidence, strict)`: P(Y|evidencia) via rejection sampling.
  - `interventional_samples(target, do, evidence, strict)`: P(Y|do(X=x)) via sampling.
  - `information_gain()`: IG estimado via binned MI con bins fijos del target.
  - `optimal_action()` / `generate_trajectory()`: seleccion optima de observaciones.
    Stopping criterion: no recomienda si IG < 0.02 bits (above MC noise floor).
  - `strict=True`: raise en vez de fallback silencioso al marginal.
  - Entropy en bits (log2), consistente con ExactBayesSolver.
  - Validacion de variables, weight normalization conservadora en IG.
  - Evaluacion rigurosa: posteriors KS-test vs analitica (83-90% pass),
    interventional 100%, IG ranking 100% estable (5 seeds).
  - 60 tests: posteriors, interventions, entropy, IG, trajectories, validation,
    multi-evidence, grafos de 10 nodos, stopping criterion, strict mode.
- Capa de datos realistas (`scm_data.py`):
  - `apply_realism()`: ruido de medicion (Gaussiano proporcional a std),
    rounding auto-inferido, outliers, missing data (MCAR/MAR).
  - `realistic_sample()`: sample + realism en un paso.
  - `multi_dataset_sample()`: 3 fuentes independientes (background, field
    survey, detailed analysis) con distinta calidad, cobertura y tamanio.
    Column split por distancia en el DAG al target.
  - MAR: probabilidad de missing depende de valores extremos del padre
    (z-score > 1.5 duplica la tasa). Target nunca missing.
  - 40 tests: transformaciones individuales, multi-dataset, helpers, E2E.
- `SCMTaskGenTool`: genera los 9 eval types desde SCMWorld + SCMSolver.
  - Distribuciones continuas discretizadas como histogramas (equal-width bins,
    mean +/- 4*std). Compatible con VerifierTool.kl_divergence sin cambios.
  - Intervenciones: "low" (p25) y "high" (p75) por variable.
  - Graph tasks (should_condition, adjustment_set) via SCMWorld.dag.
  - `get_all_backdoor_adjustment_sets()`: enumeracion exhaustiva de sets minimales.
  - 41 tests: 9 eval types + scoring + consistency.
- **Pendiente:** integracion con pipeline (EpisodeRunner, ProblemBuilder, generate_from_plan).
  Mediciones indirectas (senales proxy) documentadas como patron de diseno
  para cuando el orchestrator diseñe SCMs (Fase 3).
- **Limitacion conocida:** rejection sampling escala mal con >5 evidence variables.
  Futuro: importance weighting con ESS monitoring.

### Diseno del caso / orchestrator — Estable

- Orchestrator LLM con function calling: dag_generate, dag_construct,
  design_case, apply_semantics, build_problem, emit_inspiration_manifest.
- `CasePlan`: framing, research context, preguntas con hints (node hints
  end-to-end para alinear pregunta visible con respuesta formal).
- Paper-seeded: PDF via pymupdf, markdown directo. El paper inspira, no
  se replica. Prompt reescrito: preguntas causales como primarias,
  infer_target solo complementario, seed-first question design.
- Inspiration Report v2: 10 secciones cualitativas (domain, variables,
  estructura causal, data/evidence, preguntas con eval_type, signal,
  actions, assessment, limitaciones clasificadas). Sin score numerico.
- Edge directions extraidas de dag_construct y pasadas a cpd_gen.

### Capa semantica / problem builder — Estable

- `ResearchProblem`: narrativa, dominio, contexto, DataAssets, AvailableActions,
  budget, target.
- Multi-artifact datasets por defecto: background (~500 rows, pocas columnas),
  field survey (~66 rows, mas columnas), detailed analysis (~20 rows,
  especializadas).
- Measurement noise (5% misclassification) + MAR missingness (5%).
- Datasets pre-loaded como df, df_1, df_2 en python_exec.
- **Modos semanticos (prototipo):** `scripts/semantic_transform.py` transforma
  SRCs post-generacion a 3 modos (realistic/fictional/abstract). Misma BN,
  distinta capa visible. `theory_rich` es futuro. Experimento pendiente.

### Interaccion / episodes / actions — Parcial

- `Episode` + `EpisodeRunner`: acciones step-by-step con budget tracking.
- `ActionDef`: id, action_type, nodes, cost. Modo rico con acciones compuestas.
- `ResearchActionType`: observe, intervene, request_dataset, consult.
- Intervenciones implementadas: do-operations, sampling intervencional, conflict
  guards.
- **Estado**: la infraestructura de research_actions (observe, intervene,
  budget) existe en el codigo pero esta DESACTIVADA. Las acciones antiguas
  eran artificiales ("observar X cuesta 2 puntos"). El solver investiga
  libremente con python_exec + think + submit — no necesita acciones
  predefinidas para analizar datos. Las research actions futuras deben
  rediseniarse desde cero como interacciones ricas con el entorno
  (diseno experimental, campanas de datos, etc).

### Evaluacion / teacher / scoring — Estable

- `ExactBayesSolver`: posteriors, information gain, acciones optimas,
  causal_query (do-calculus).
- `VerifierTool`: scoring por tipo (KL, IG ratio, accuracy, match).
- `TeacherOutput`: posterior, recomendacion, IG, entropia.
- Per-type baseline scoring: KL(uniform) para distribution, 0.5 para binary,
  1/N para hypothesis.
- Trajectory comparison: agent vs teacher, verdicts EXCELLENT/GOOD/FAIR/POOR.

### Solver diagnostico — Estable

- `AgentSolver.solve_case()`: todas las tasks en un solo episodio.
- Tools del solver: python_exec (persistent, sandboxed, df pre-loaded),
  think (razonamiento explicito), submit (por pregunta).
- Prompt: presenta datasets + preguntas. Sin budget, sin research_actions,
  sin pistas sobre eval type.
- 9 eval types soportados en submit + scoring.
- Backend configurable: Azure, vLLM, transformers.
- Genera full_case.md: system prompt + conversacion + evaluacion.

### Harness / diagnostic runner — Parcial

- `DiagnosticRunner`: N SRCs E2E con LLM, verdicts type-aware, failure modes,
  baseline scoring.
- Agent trajectory extraction + JSONL export.
- `QualitySuite` v2: metricas estructurales del motor formal. **Desactualizado**:
  solo cubre 3/9 eval types, no usa LLM.
- 15-SRC diagnostic (bench_20260311): 14/15 completados, 57 tasks, 9/9 tipos.
- 7-SRC eval (2026-03-16): 7 dominios sin budget. Hallazgo critico sobre
  preguntas data-indexed.

### Benchmarks externos — Estable

- Adaptadores: CLadder, QRData, DiscoveryBench.
- `ToolEnrichedClient`: wraps ModelClient, agrega python_exec + think.
- BEFORE scores documentados en research/notes/benchmark_results.md.
- `run_benchmark.py`: --with-tools, --base-url, --api-key.

### Training / RL integration — Experimental

- `SregEnv`: adaptador sobre EpisodeRunner para framework verifiers.
- python_exec unificado: training importa desde agent/python_exec.py.
- Rubric usa VerifierTool (BN = fuente de verdad).
- Dataset generation via WorldGenTool/TaskGenTool/ProblemBuilder.
- **No testeado end-to-end con training real.** Verifiers no es dependencia
  formal en pyproject.toml.

---

## Eval types implementados

| Tipo | Scoring | Estado | Nota |
|------|---------|--------|------|
| infer_target | KL divergence | Estable | Fuerza analisis de datos |
| next_best_observation | IG ratio | Estable | 25% triviales (IG=0) |
| hypothesis_selection | Accuracy | Estable | Peor que azar en diagnostic (17%) |
| causal_effect | KL divergence | Estable | Solver usa datos parcialmente |
| best_intervention | Effect ratio | Estable | NBO sospechoso (100% ZERO_OBS) |
| adjustment_set | Match | Estable | Respondido desde priors |
| compare_interventions | Match | Estable | Beats baseline 71% |
| should_condition | Match | Estable | Respondido desde priors |
| infer_latent_cause | KL divergence | Estable | 0% beats baseline |

**Hallazgo critico**: los tipos distribution (infer_target, causal_effect)
fuerzan analisis de datos. Los tipos structural-causal (should_condition,
adjustment_set) se responden desde conocimiento de dominio sin investigar.

---

## Limitaciones conocidas

- **Preguntas no data-indexed**: las preguntas causales no fuerzan investigacion.
  El solver responde desde priors de pretraining.
- **Eval types insuficientes**: faltan mediacion, effect modification, selection
  bias assessment y source attribution. Los papers reales preguntan estos tipos
  y el orchestrator los fuerza en los 9 tipos existentes, perdiendo lo mas
  interesante. (Hallazgo de inspiration reports 2026-03-16.)
- **Solver no usa research_actions**: budget y acciones existen en la
  infraestructura pero estan desactivadas en el solver por ser artificiales.
- Orchestrator ignora dificultad pedida (siempre genera "easy").
- QualitySuite desactualizada: solo 3/9 eval types.
- python_exec sin timeout real (thread-based no funciona en CPython).

---

## Como ejecutar

```bash
# Setup
conda activate sreg  # Python 3.11
pip install -e ".[dev]"

# Tests
pytest tests/ -v

# Generar un SRC
python scripts/generate_src.py --goal "marine ecology" -o output/ --inspect

# Desde un paper PDF
python scripts/generate_src.py --seed-file seeds/paper.pdf -o output/ --inspect --report

# Con evaluacion del solver
python scripts/generate_src.py --seed-file seeds/paper.pdf -o output/ --solve

# Benchmarks
python scripts/run_benchmark.py -b cladder --subset dev

# Diagnostic (N SRCs)
python scripts/run_diagnostic.py
```

---

## Tests

- **1277 tests** en todos los modulos
- Mirrors: `src/sreg/tools/X.py` → `tests/tools/test_X.py`
- Coverage clave: 100 mundos por template, 50 configs E2E DAG generators,
  cross-template para los 9 eval types, rich actions, CasePlan hints,
  python_exec sandboxing.
