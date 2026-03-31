# SREG — Claude Code Project Configuration

## AUTORESEARCH: ACTIVADO

No frenar a menos que el usuario interrumpa. Para desactivar: cambiar a
DESACTIVADO. Documentar en `research/`.

### Research workflow — ITERATIVO

El ciclo de research tiene dos fases que se alternan:

**Fase PENSAR:**
Reflexionar + buscar info + debatir (Codex, otras AIs, usuario) + generar
hipotesis o idea concreta. NO implementar durante esta fase. El output es
un spec, una propuesta, o una hipotesis documentada.

**Fase PROBAR:**
Implementar de manera controlada, con capacidad de revertir. Prototipos
acotados, scripts, experimentos. Medir resultados concretos. NO refactorear
el pipeline completo — probar primero en acotado.

**Fase ANALIZAR:**
Ver resultados + sacar conclusiones + documentar. Decidir si la hipotesis
se valido o no. Si se valido, integrar. Si no, volver a PENSAR.

```
PENSAR (reflexionar + info + debate + hipotesis)
   ↓
PROBAR (controlado, reversible, acotado)
   ↓
ANALIZAR (resultados + conclusiones + documentar)
   ↓
PENSAR ...
```

**Reglas:**
- Nunca solo debate — siempre probar cosas reales.
- Nunca solo implementar — siempre pensar antes.
- Los prototipos coexisten con el pipeline actual (no romper lo que funciona).
- Documentar en cada fase, no solo al final.

## LA PREGUNTA — el filtro de todo

> **Por que esto todavia no es una investigacion real? Que le falta?**
>
> **Por que un modelo entrenado con RL sobre SREG todavia no aprenderia
> buen juicio cientifico?** Que le falta al sistema para ensenar:
> research taste, descomposicion de problemas, generacion de preguntas
> fine-grained, buen plan de investigacion, saber que es relevante para
> el objetivo y que no, saber cuando una conclusion es prematura vs
> bien fundada.

Cada decision pasa por este TRIPLE filtro:
1. Se parece a investigacion real? Si no, es un bug.
2. Entrenaria buen juicio cientifico (incluida relevancia)? Si no, redisenar.
3. Funciona para la MAYORIA de los tipos de investigacion? No solo "X causa Y"
   — system mapping, structure discovery, descriptivo, predictivo, epistemologico,
   optimizacion, multi-outcome, etc. Si solo funciona para causal simple, es un
   juguete. Repasar mentalmente los escenarios diversos ANTES de disenar:
   `research/synthesis/investigation_scenarios_rubric.md`.

## Principios de scoring — NO NEGOCIABLE

1. **UN solo metodo para todo** — sin scoring profiles por tipo de investigacion.
2. **El sistema se adapta a los casos** — el scoring no fuerza una forma.
3. **El brief es libre** — una pregunta, varias, vagos, mixtos: todo valido.
4. **No construir un juego** — si necesita "roles", "slots", "pattern_weights"
   para funcionar, es un juego, no evaluacion de investigacion.
5. **Verificacion es el core** — el SCM verifica. El scoring solo pregunta:
   es verdad? es relevante? cubrio lo pedido? no spameo?
6. **Diversidad de investigacion** — todo diseno debe funcionar para los tipos
   diversos de investigacion (ver triple filtro arriba). No disenar para "X→Y".

## Donde buscar que

| Necesito... | Ir a... |
|---|---|
| Entender como funciona el sistema hoy | `CURRENT_STATE.md` |
| Entender la arquitectura tecnica | `ARCHITECTURE.md` |
| Vision, principios, invariantes | `PROJECT.md` |
| Que hacer / trabajo pendiente | `TODO.md` |
| Historial de cambios | `CHANGELOG.md` |
| Investigacion y hallazgos | `research/README.md` (indice) |
| 23 escenarios de validacion | `research/synthesis/investigation_scenarios_rubric.md` |
| Vision de Open Investigation | `research/synthesis/open_investigation_vision.md` |
| Scoring fundamentals | `research/synthesis/oi_scoring_fundamentals.md` |
| Taxonomia de investigacion | `research/synthesis/Doc1_Taxonomia_El_Mapa.md` |
| Scoring next design (sub-questions) | `research/synthesis/oi_scoring_next_design.md` |

## Skills disponibles

| Skill | Cuando usarla |
|---|---|
| `/run` | Generar un caso de investigacion con LLM |
| `/eval` | Evaluar calidad de casos (L2, la que importa) |
| `/precommit` | Workflow completo de commit (el unico valido) |
| `/explain` | Presentar cambios al usuario antes de commit |
| `/codex-collab` | Consultar Codex como segunda opinion |
| `/plan` | Ver roadmap y estado del proyecto |
| `/status` | Resumen rapido de donde estamos |

### research/ — mantener limpio

- `synthesis/` = conclusiones. `notes/` = working docs. `archive/` = legacy.
- Siempre actualizar `research/README.md` cuando muevas o crees un doc.

## Antes de cada commit — QUE ACTUALIZAR

1. **CURRENT_STATE.md** — el cambio afecta como funciona el sistema? Actualizar.
2. **CHANGELOG.md** — agregar entrada describiendo el cambio (producto, no internals).
3. **TODO.md** — completaste algo? Marcarlo. Surgio algo nuevo? Agregarlo.
4. **research/README.md** — cambiaste o creaste docs de research? Actualizar indice.
5. **ARCHITECTURE.md** — cambiaste componentes, contratos o flows? Actualizar.
6. **Tests y scripts** — el cambio deja tests o scripts obsoletos? Eliminarlos.
7. **Skills, memorias, otros** — el cambio deja skills (`.claude/skills/`),
   memorias, o scripts con referencias obsoletas? Actualizarlos o eliminarlos.

**"Actualizar" no es solo docs del repo. Es TODO lo que referencia al sistema:
skills, memorias, scripts, configs. Si algo quedo desactualizado, arreglarlo.**

## Commit workflow — MANDATORIO

```
1. Desarrollo + Tests (pytest modulo afectado + ruff)
2. Codex review + Fix (MANDATORIO si MCP disponible, skip si trivial)
3. Presentar al usuario — explicar en espanol, pedir aprobacion
   ESPERAR aprobacion. NO commitear sin ella.
4. Actualizar docs (ver lista arriba) + Commit
5. Sugerir proximos pasos
```

## Validacion — LA UNICA QUE IMPORTA ES E2E

**La validacion real de CUALQUIER cambio es una evaluacion multi-nivel,
cualitativa, del end-to-end de la investigacion real.** Unit tests son un
check mecanico secundario — confirman que el codigo no rompe, nada mas.
NUNCA usar unit tests como evidencia de que un cambio "funciona". Para
saber si funciona: correr el pipeline E2E con LLM real (`/run --oi`) y
evaluar cualitativamente el resultado (`/eval`).

### Unit tests — MINIMO INDISPENSABLE

- **Solo correr tests DESPUES de cambiar codigo.** No como ritual, no como
  verificacion previa a commit, no "por si acaso". Si no cambiaste codigo,
  no corras tests.
- **NUNCA correr la suite completa** salvo que el usuario lo pida explicitamente.
- Si cambias un archivo, correr SOLO el test de ese archivo. UNA VEZ.
- Si falla un import, arreglar el import — no re-correr toda la suite.
- **NUNCA** correr tests en paralelo ni repetir la misma suite.
- En caso de duda: NO correr tests. Preguntar al usuario.

### 3 niveles de evaluacion

| Nivel | Que mide | Cuando | Importancia |
|-------|----------|--------|-------------|
| L1 Tests (`pytest`) | Codigo no rompe | Cada commit | Mecanico, secundario |
| L2 E2E + Eval (`/eval`) | Investigacion real? Buen juicio? | Post-cambio | **LA QUE IMPORTA** |
| L3 Transfer (futuro) | RL mejora policies | Cuando haya policies | Futura |

**L2 es la evaluacion que decide si un cambio esta bien o mal.** Incluye:
generacion E2E con LLM, rubrica cualitativa de 7 dimensiones, 6 critical
failures, no-data baseline probe, y LA PREGUNTA doble. Ver `/eval`.

**Escenarios diversos — NO NEGOCIABLE**: los E2E SIEMPRE deben cubrir tipos
variados de investigacion. NUNCA correr solo causal simple. Cada batch de
validacion debe incluir al menos 3 tipos distintos de:
`research/synthesis/investigation_scenarios_rubric.md` (system mapping,
heterogeneidad, confounding, descriptivo, multi-outcome, epistemologico, etc.).
Si solo probaste "X causa Y", NO validaste nada. Usar seeds de `seeds/`
para generar casos diversos: `python scripts/generate_src.py --seed-file seeds/X.md -o ... --oi`.

## Environment setup

```bash
conda activate sreg  # Python 3.11
pip install -e ".[dev]"
```

## Azure LLM — SIEMPRE DISPONIBLE

**Las credenciales de Azure estan en `.env` en la raiz del repo.** Se cargan
automaticamente via `python-dotenv` en todos los scripts y el orchestrator.
**NUNCA asumir que Azure no esta disponible.** Si necesitas el LLM, usalo.

Modelos: `gpt-5.4` (orchestrator), `gpt-5.2-codex` (solver). Ver `.env` para
lista completa y advertencias de costo.

## Tech stack

- **networkx** — DAG: `nx.is_d_separator()` (NOT `nx.d_separated`)
- **numpy / scipy / pydantic v2** — sampling, distributions, contracts
- **openai SDK** — Responses API: `client.responses.create` (NOT `chat.completions`)
- **pytest** + **ruff** (line length 100)

Env vars (en `.env`, cargados por dotenv): `AZURE_INFERENCE_CREDENTIAL`,
`AZURE_FOUNDRY_BASE_URL`, `AZURE_MODEL`, `AZURE_SOLVER_MODEL`

## Project structure

```
src/sreg/
  models/        # Pydantic contracts (SCM, OI, tasks, episodes)
  inference/     # LLM protocol (ModelClient, Responses API)
  world/         # SCM engine (scm.py, expression compiler, scm_data)
  solver/        # SCMSolver (teacher / ground truth)
  tools/         # SCM pipeline + OI pipeline (compiler, verifier, salience, runner)
  orchestrator/  # LLM orchestrator (function calling, SCM-only)
  agent/         # python_exec + tool-calling engine (for OI solver)
  benchmarks/    # CLadder, QRData, DiscoveryBench
scripts/         # generate_src.py, run_benchmark.py
seeds/           # Research seeds (.md/.pdf) for diverse E2E generation
tests/           # Mirrors src/ structure
research/        # Analisis y sintesis (ver research/README.md)
```

## Code conventions

- Type hints on public functions
- `__all__` exports in every `__init__.py`
- Tests mirror src: `src/sreg/tools/X.py` -> `tests/tools/test_X.py`
- Imports: stdlib -> third-party -> local, separated by blank lines
- Terminal output: ASCII-safe (Windows cp1252)
- Communicate with the user in **Spanish**

## Commands

`pytest tests/ -v` | `pytest tests/tools/test_X.py -v` | `ruff check src/ tests/` | `ruff format src/ tests/`

## Git + Codex

- Branch naming: `feature/<name>`, `fix/<name>`, `refactor/<name>`
- Always ask user before pushing. Multiple sessions: `claude --worktree <name>`.
- **Codex** (when MCP available): mandatory for code review, recommended for design.
  Reusar `threadId` con `codex-reply`. Sesion nueva solo si el tema cambio.
- **CLAUDE LIDERA, CODEX ASESORA.** Formar opinion propia ANTES de consultar.
  Presentar ambas opiniones, argumentar desacuerdos. El usuario decide.
