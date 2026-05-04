# SREG — Estado actual

> **Realidad runnable hoy = SREG v1** (Open Investigation sobre SCM con compiler NL↔IR). Congelado en `main` con tag `pre-v1.5`. Si querés correr SREG en este momento, este es el sistema.
>
> **v1.5** está en arquitectura definida pero **sin implementación** todavía. Rama `dev` contiene docs y planning; el código no arrancó. Para el target ver `ARCHITECTURE.md` y Epic [#63](https://github.com/lucaspecina/synthetic-research-envs/issues/63).
>
> **v2 (Sherlock multi-turno)** y **v1.6 (SDE)** son futuro.

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

v1.5 reemplaza el compiler NL↔IR por un esquema **rubric + LLM judge + answer key grounded en Environment ejecutable**:

- **Designer multi-rol** genera cada caso desde un seed paper: Paper Digestion → World Architect → Explorer → Question Designer → Case Writer + Validator transversal.
- **Multi-formalismo desde el inicio**: SCM (causal estático) + ODE (dinámica determinista, con observation noise opcional). SDE intrínseco se difiere a v1.6.
- **Investigator** sigue siendo single-turn (recibe dataset, responde, fin) — el multi-turno es v2.
- **Evaluator** es LLM judge sin acceso runtime al Environment: lee `AnswerKey` ya computado en design-time. Frontera limpia.
- **Diversidad de casos** como invariante: varios casos diversos por formalismo, no UN caso canónico único. Casos famosos = smoke tests.

**Estado actual de v1.5**:
- Arquitectura cerrada (11 rondas de debate documentadas en `research/notes/v1_5_debates.md`).
- Epic [#63](https://github.com/lucaspecina/synthetic-research-envs/issues/63) abierto con 8 sub-issues (#55-#62).
- Orden de implementación definido (`#55 → #56 → #61 → #60 → #57 → #58 → #59 → #62`) con checkpoints entre piezas.
- Cero código todavía. Próximo paso: arrancar #55 (contratos Pydantic).

Para detalles del target: `ARCHITECTURE.md`. Para historia de decisiones: `research/notes/v1_5_debates.md`. Para ejemplo canónico de un caso v1.5 escrito a mano: `research/examples/birth_weight_paradox.md`.

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
