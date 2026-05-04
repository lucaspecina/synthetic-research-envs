# SREG — Synthetic Research Environment Generator

Genera entornos de investigación científica sintética con **verdad matemática verificable**, para entrenar y evaluar agentes (LLMs) en juicio investigativo. Como un gym, pero para razonamiento científico.

SREG **genera entornos + computa rewards exactos**. NO entrena policies — eso lo hace otro sistema (RL framework + agente).

## Estado del proyecto (mayo 2026)

| Versión | Paradigma | Estado |
|---|---|---|
| **v1** | Open Investigation sobre SCM, compiler NL↔IR + LLM judge para relevancia. | Implementada, runnable en `main` (tag `pre-v1.5`). |
| **v1.5** | Rubric + LLM judge con answer keys grounded en Environment ejecutable. SCM + ODE (con observation noise opcional). | **Arquitectura definida, en desarrollo activo en `dev`.** |
| **v1.6** | Agrega SDE intrínseco (difusión, mercados, biofísica con ruido térmico). | Futuro. |
| **v2** | Investigación interactiva multi-turno tipo Sherlock (agente pide observaciones, interviene, simula). | Futuro post-v1.5. |

## Cómo navegar este repo

| Si querés... | Andá a |
|---|---|
| Entender por qué existe SREG y los invariantes del sistema | `PROJECT.md` |
| Ver el target del sistema (v1.5) — spec viva | `ARCHITECTURE.md` |
| Saber qué corre HOY y cómo usarlo | `CURRENT_STATE.md` |
| Operativa de Claude Code en este repo | `CLAUDE.md` |
| Roadmap y trabajo pendiente | [Project v2 "SREG Roadmap"](https://github.com/users/lucaspecina/projects/4) · `gh issue list` |
| Investigación, debates históricos, related work | `research/README.md` |
| Historial de cambios | `CHANGELOG.md` |

## Setup mínimo

```bash
conda create -n sreg python=3.11 -y && conda activate sreg
pip install -e ".[dev]"
```

Configurar credenciales LLM en `.env`:

```
AZURE_FOUNDRY_BASE_URL=https://your-resource.openai.azure.com/openai/v1
AZURE_INFERENCE_CREDENTIAL=your-api-key
AZURE_MODEL=gpt-5.4
AZURE_SOLVER_MODEL=gpt-5.2-codex
```

Para correr el sistema actual (v1) ver `CURRENT_STATE.md`.

## Estructura del repo

```
src/sreg/        # código Python (modelos, motor SCM, herramientas, agentes)
scripts/         # entry points (generate, run, rescore, benchmarks)
seeds/           # seeds de papers para generar casos
tests/           # tests pytest
research/        # análisis, decisiones, debates, ejemplos
docs/archive/    # historia legacy (architecture v1, TODOs viejos)
```

## Tests y lint

```bash
pytest tests/tools/test_X.py -v   # módulo específico (no correr la suite completa)
ruff check src/ tests/             # lint
```
