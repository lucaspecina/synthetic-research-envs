# SREG — Estado actual

> **Realidad runnable hoy** = dos cosas en paralelo:
> - **SREG v1** (Open Investigation sobre SCM con compiler NL↔IR) congelado en `main` con tag `pre-v1.5`. Si querés correr el sistema completo end-to-end hoy, este es. Ver §2.
> - **SREG v1.5** **EN IMPLEMENTACIÓN ACTIVA** en rama `dev`. Diseño cerrado (Ronda 13 + Ronda 14 filosófica). Pipeline parcial ya funcional: contratos, compile_scm, Paper Digestion agent, Architect agent + lints. Falta: Validators, Discovery Designer, Case Writer, Validator transversal, Investigator runtime, Evaluator. Ver §3 con tabla de fases. Para detalle de cada fase ver `CHANGELOG.md`.
>
> **v2 (Sherlock multi-turno)** y **v1.6 (SDE intrínseco)** son futuro.

---

## 1. Qué corre HOY

SREG v1 genera entornos de investigación científica sintética con verdad matemática verificable:

- **WorldModel** = SCM (Structural Causal Model). Grafo causal + ecuaciones estructurales + ruido + capacidad de samplear, intervenir y condicionar.
- **ResearchCase** = brief abierto + datasets observacionales + herramientas (`python_exec`, `load_artifact`).
- **Investigator** = LLM agente que recibe el caso, analiza datos libremente, entrega `ClaimCard`s en prosa.
- **Pipeline de scoring** = compiler NL↔IR (`grammar-direct`) traduce las claims a `AtomicSpec`s formales; el verifier las ejecuta contra el SCM; un LLM judge calcula relevancia contra una agenda oculta de `SubQuestionIntentV2`.
- **Output** = score multi-componente (`correctness × weighted_coverage`).

**Tipos de investigación cubiertos** (parcial, sin pretensión de exhaustividad): causal, confounding, mediación, heterogeneidad, epistemológico, descriptivo, system mapping, multi-outcome. v1 funciona bien para causal clásico; SQ v2 extendió a más tipos pero con techo conocido (~82% en Suite 2).

**Limitaciones documentadas**: el compiler NL→AtomicSpec es frágil — esa es la razón por la que v1.5 lo elimina.

### Config v1 congelada (2026-04-09)

| Parámetro | Valor |
|---|---|
| Solver model | `gpt-5.2-codex` (env `AZURE_SOLVER_MODEL`) |
| Compiler/judge model | `gpt-5.4` (env `AZURE_MODEL`) |
| Claim cap | 15 |
| Max iterations | 20 |
| Temperature | 0.0 |
| Score formula | `total = correctness × weighted_coverage` |

Cualquier cambio a estos valores es un cambio de versión, no un bugfix.

---

## 2. Cómo usar SREG v1 hoy

Tres pasos, tres scripts. Cada uno independiente del anterior.

### Paso 1 — Generar un caso

```bash
# Desde un seed (.md describiendo el problema; ejemplos en seeds/)
python scripts/generate_src.py \
    --seed-file seeds/mi_caso.md \
    -o results/mi_caso \
    --oi          # opcional: corre el solver en el mismo paso
```

Output: `results/mi_caso/src.json` (mundo, problema, datasets, SQs) + opcionalmente `oi_result.json`.

### Paso 2 — Correr el solver sobre un caso existente

```bash
python scripts/run_oi.py results/mi_caso/
```

Toma `src.json`, reconstruye el mundo, carga las sub-questions y corre el solver LLM. Produce `oi_result.json` con claims, scores y conversación completa.

### Paso 3 — Reproducibilidad y rescore

```bash
python scripts/rescore.py results/mi_caso/ --reaggregate   # solo aritmética
python scripts/rescore.py results/mi_caso/ --rejudge       # re-evalúa relevancia
python scripts/rescore.py results/mi_caso/ --recompile     # full pipeline
```

Útil para verificar que el scoring es determinista o re-evaluar después de cambios.

### Setup

```bash
conda create -n sreg python=3.11 -y && conda activate sreg
pip install -e ".[dev]"
```

`.env` con credenciales Azure:

```
AZURE_FOUNDRY_BASE_URL=https://your-resource.openai.azure.com/openai/v1
AZURE_INFERENCE_CREDENTIAL=your-api-key
AZURE_MODEL=gpt-5.4
AZURE_SOLVER_MODEL=gpt-5.2-codex
```

---

## 3. Qué se está construyendo (v1.5)

v1.5 reemplaza el compiler NL↔IR por un esquema **rubric + LLM judge + answer key grounded en Environment ejecutable**.

**Reformulación filosófica clave (Ronda 14, 2026-05-06)**: las "GoldQuestions" se reinterpretan como **DiscoveryTargets** — descubrimientos centrales ocultos que el mundo fue diseñado para contener, NO preguntas a responder. Cada caso está construido para que una buena investigación libre recupere esos descubrimientos. Apertura está en el proceso; verificabilidad está en los anchors formales. Ver `PROJECT.md` §"Investigación abierta vs examen cerrado" para las 4 protecciones contra el regreso al examen cerrado. Internamente, el schema `GoldQuestion` se renombra a `DiscoveryTarget` cuando se implemente Fase 3 (no antes — Fases 1.x ya commiteadas siguen válidas).

**Diseño cerrado en Ronda 13** (`research/notes/multi_explorer_redesign.md`, con extensión filosófica en Ronda 14). Flujo del Designer:

```
Paper crudo
  → [Paper Digestion]      → PaperInsights (con narrative_capsule saneada anti-leak)
  → [World Architect]      → WorldSpec + intended_phenomena (multi-iter, hard cap 3)
       loop con N Validators (verifican que intended_phenomena se materializan)
  → [Discovery Designer]   → DiscoveryBundle (descubrimientos esperados, mapping N:M; no 1:1)
  → [Case Writer]          → ResearchCase (CIEGO al DiscoveryBundle: brief sin
                                 referenciar textos de DiscoveryTargets)
  → [Validator transversal] → ValidationReport (12 checks; único árbitro)
                           ↓
                    Investigator (LLM single-turn) → Claims
                           ↓
                    Evaluator (LLM judge) → score
```

- **Multi-formalismo**: SCM (causal estático) + ODE (dinámica determinista, opcional `observation_noise`). SDE intrínseco va en v1.6.
- **Frontera anti-leak con Discovery semántica** (Ronda 14): `narrative_capsule` saneada con `forbidden_phrases`. Discovery Designer NO ve el paper crudo. Case Writer NO ve el `DiscoveryBundle` — solo `WorldSpec` (variables visibles) + `narrative_capsule` + lista de `DiscoveryTarget.kind` a alto nivel. Si el brief leyera los textos de los targets, el agente parafrasearía y no investigaría.
- **Knowledge-first, capability-secondary**: v1.5 evalúa claims/conclusiones científicas. Capability-as-evidence permitido como `role="support"` con peso capado, NUNCA `required`. Hidden test sets, ROC AUC programático, optimizadores ejecutables → v2+.
- **Diversidad de casos** como invariante: varios casos diversos por formalismo, no UN caso canónico único. Casos famosos = smoke tests.

### Estado de implementación de v1.5 (rama `dev`)

| Fase | Componente | Estado | Commit / detalle |
|---|---|:-:|---|
| **#55** | Contratos Pydantic v1.5 (25 modelos: WorldSpec, IntendedPhenomenon, EvidenceArtifact, ValidatedPhenomenon, ValidatorVote, GoldQuestion *(será DiscoveryTarget en Fase 3)*, Rubric, AnswerKey, ResearchCase, etc.) | ✅ | `bfacb22` + ronda 13 endurecida en `890d735` |
| **#56** | Environment SCM ejecutable + adapter al `SCMEnvironment` Protocol | ✅ | parte de `48ba341`; bug fix latentes en `3841ffd` |
| **Fase 1.1** | `compile_scm(WorldSpec) → SCMWorld` + Birth Weight Paradox E2E hardcoded | ✅ | `3841ffd` |
| **Fase 1.2.a** | `PaperDigestionAgent` con LLM real + 3 seeds digeridos + tests wiring | ✅ | `4e16b19` |
| **Fase 1.2.b** | `ArchitectAgent` con LLM real + 3 lints deterministas + harness con diagnósticos | ✅ | `378662f` |
| **Fase 2.b** | `ValidatorAgent` LLM por intended_phenomenon (scripts Python libres contra `env`, emite `ValidatorVote` via function call; margin/fragility autoevaluación gruesa, sin DSL ni fórmula universal). Plomería reusable: `make_python_namespace` acepta `extras`; `ToolEnrichedClient` acepta `namespace_factory` + para el loop ante terminal tools custom. 14 tests wiring pasan. | ✅ | `<pending>` |
| **Fase 2.c** | Loop Architect ↔ N Validators con cap=3 iters, paralelización + promoción a `ValidatedPhenomenon`, script `run_validator.py` para E2E real, parametric variations | ⏳ | **PRÓXIMO** |
| **Fase 3** | Discovery Designer (consume `list[ValidatedPhenomenon]`, mapping N:M no 1:1; produce `DiscoveryBundle` con descubrimientos esperados, no preguntas). Incluye renombre de schemas `GoldQuestion`→`DiscoveryTarget`, `QuestionsBundle`→`DiscoveryBundle`, campo `identification_hint`→`claim_match_hint`, agregar `source_validated_ids`. | ❌ | pendiente |
| **Fase 4** | Case Writer (`ResearchCase` desde `WorldSpec` público + `narrative_capsule` + lista de `DiscoveryTarget.kind`; **CIEGO al DiscoveryBundle**, sin acceso a los textos de los targets — Ronda 14) | ❌ | pendiente |
| **Fase 5** | Validator transversal (12 checks, único árbitro con `target_to_reiterate`). Los 10 originales + 2 nuevos del SOTA review (post `sota_synthetic_envs_for_rl.md`): **shortcut resistance** (batería de baselines naive vs target — caso rechazado si baseline pasa demasiado alto) y **difficulty band** (reference investigator estándar; banda 0.4-0.7 esperada, ni trivial ni imposible). Fusión con check Three-Clue Rule (#11) bajo gate "discoverability + shortcut resistance". | ❌ | pendiente |
| **Fase 6** | Investigator runtime + Evaluator (2 pasos, alpha=0.8). Incluye **evidence-consulted logging** (PATHWAYS-style) con 3 estados (`supported`/`underspecified`/`fabricated`); penalización dura solo a claims `fabricated`. Tratado como integrity gate, no trace scoring completo. | ❌ | pendiente — issues #60/#61 |
| **Fase 7** | Casos diversos por formalismo + 3 tests go/no-go + pilot humano | ❌ | pendiente — issue #62 |

### Cómo retomar v1.5 después de un break

1. Leer **`CHANGELOG.md`** secciones 2026-05-05 y 2026-05-06 (entradas detalladas por fase).
2. Leer Epic **[#63](https://github.com/lucaspecina/synthetic-research-envs/issues/63)** body para roadmap actualizado.
3. Doc canónico del Designer: **`research/notes/multi_explorer_redesign.md`** (Ronda 13).
4. Estado de outputs reales: **`experiments/architect/<timestamp>/<seed>.summary.txt`** (gitignored, regenerar con `scripts/run_architect.py`).
5. Próxima fase: **Fase 2.c (loop Architect↔Validators + run_validator.py para E2E real)** — ver Issue #58 body.

Para detalles del target arquitectónico: `ARCHITECTURE.md`. Para historia de decisiones: `research/notes/v1_5_debates.md` (12 rondas). Para ejemplo canónico hand-authored: `research/examples/birth_weight_paradox.md`.

---

## 4. Donde mirar para qué

| Si querés... | Andá a |
|---|---|
| Vision e invariantes del proyecto | `PROJECT.md` |
| Target del sistema (v1.5) | `ARCHITECTURE.md` |
| Operativa Claude Code en este repo | `CLAUDE.md` |
| Trabajo pendiente y backlog | [Project v2 "SREG Roadmap"](https://github.com/users/lucaspecina/projects/4) |
| Historia de cambios | `CHANGELOG.md` |
| Análisis y debates | `research/README.md` |
| Postmortem del compiler v1 (por qué v1.5) | `research/notes/compiler_v1_postmortem.md` |
| Arquitectura v1 detallada | `docs/archive/architecture_v1.md` |
