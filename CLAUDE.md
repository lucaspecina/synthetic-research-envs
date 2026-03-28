# SREG — Claude Code Project Configuration

## MODO ACTUAL: AUTORESEARCH — Open Investigation Design

> **ATENCION: Esta sesion esta en modo AUTORESEARCH.**
> El usuario NO esta presente. Claude trabaja autonomamente con Codex.
> Branch: `autoresearch-open-investigation`
> Session file: `AUTORESEARCH_SESSION.md` — LEER DESPUES DE CADA COMPACT.

### Que cambia en autoresearch

1. **El usuario no esta.** No esperar aprobacion humana. Codex actua como
   reviewer critico en su lugar.
2. **NUNCA FRENAR.** Siempre hay algo que investigar, debatir, disenar o
   implementar. Si un camino se bloquea, ir al siguiente.
3. **Foco principal:** investigacion + pensamiento + debate + diseno.
   Implementacion viene DESPUES de que el diseno sobreviva escrutinio.
4. **LA PREGUNTA guia todo:** "Por que esto todavia no es una investigacion
   real? Que le falta?" — cada decision pasa por este filtro.
5. **No construir juguetes.** Si el resultado solo verifica 10 tipos de
   cosas, siempre sera un juguete. La gramatica composable debe ser ABIERTA.
6. **Documentar siempre.** Despues de cada milestone, actualizar docs y
   `AUTORESEARCH_SESSION.md`. Sin docs, el compact mata la continuidad.

### Commit workflow adaptado (sin usuario)

```
1. Desarrollo + Tests + Validation (igual)
2. Codex review + Fix (MANDATORIO — Codex es el reviewer)
3. Si Codex aprueba: commitear. Si tiene objeciones serias: resolver primero.
4. Actualizar docs + Commit + Push
5. Siguiente paso (nunca frenar)
```

### Principios inmutables del autoresearch

Ver `AUTORESEARCH_SESSION.md` para los 8 principios completos. Resumen:

0. LA PREGUNTA como filtro de todo
1. El solver INVESTIGA, no responde preguntas
2. Verificacion exacta contra SCM — sin excepciones
3. Subjetividad encapsulada, no eliminada
4. No construir juguetes
5. Un cientifico real haria esto?
6. Debate ANTES de codigo
7. Verificabilidad > realismo > elegancia
8. Documentar es parte del trabajo

---

## Documentacion del proyecto — donde buscar cada cosa


| Documento            | Responde                                               | Leer                                  |
| -------------------- | ------------------------------------------------------ | ------------------------------------- |
| `PROJECT.md`         | Por que existe SREG, que principios no pueden violarse | Siempre antes de decisiones de diseno |
| `ARCHITECTURE.md`    | Como esta organizado el sistema objetivo               | Antes de implementar algo nuevo       |
| `CURRENT_STATE.md`   | Que parte de la arquitectura existe hoy                | Para saber que hay y que falta        |
| `TODO.md`            | Que trabajo esta pendiente, que problemas hay, inbox de ideas | Para saber que hacer                  |
| `CHANGELOG.md`       | Historia de cambios                                    | Cuando necesites contexto historico   |
| `research/`          | Analisis, hallazgos, sintesis                          | Cuando investigues o explores         |
| `research/README.md` | Reglas + indice de que investiga cada archivo           | Para saber que research existe        |
| Escenarios rubric    | 20 escenarios de validacion + rubricas de scoring       | Antes de cambios de scoring/diseno    |
| Taxonomia (Doc1)     | Mapa completo de tipos de investigacion cientifica       | Para clasificar y evaluar cobertura   |


## Mantener la documentacion actualizada — CRITICO

**Esta es la regla mas importante de todo el archivo.** Si la documentacion
se desactualiza, todo lo demas deja de funcionar. Los otros docs se vuelven
mentira y las decisiones se toman sin informacion.

### Regla de promocion (TODO inbox → research → docs canonicos)

0. Idea cruda, problema, pregunta abierta → seccion "Inbox" de `TODO.md`
1. Se procesa en sesion → `research/notes/` (si necesita investigacion)
   o directamente a la seccion de analisis/implementacion de `TODO.md`
2. Se consolida con evidencia → `research/synthesis/`
3. Se vuelve decision → se promueve a `PROJECT.md` o `ARCHITECTURE.md`
4. Se implementa → `CURRENT_STATE.md` + `CHANGELOG.md`

### Como leer y mantener `research/`

1. Empezar siempre por `research/README.md`
2. Leer `research/synthesis/` antes que `research/notes/`
3. Usar `research/notes/` para detalle, debate, legado o evidencia de apoyo
4. Si creas o mueves un doc de research, actualizar el indice en
   `research/README.md` en el mismo cambio
5. Si un note deja de ser referencia activa, agregar una nota corta arriba
   apuntando a la sintesis o al doc canonico que corresponda

### Que actualizar despues de cada cambio


| Que cambio                         | Actualizar                                                            |
| ---------------------------------- | --------------------------------------------------------------------- |
| Completaste una tarea              | `TODO.md` + `CHANGELOG.md` + `CURRENT_STATE.md` si cambia capacidades |
| Agregaste/moviste archivo o modulo | `CLAUDE.md` si cambia el mapa del repo + `CURRENT_STATE.md` si cambia capacidades |
| Agregaste/moviste research doc     | `research/README.md` + referencias cruzadas o nota de status si hace falta |
| Cambiaste vision o principios      | `PROJECT.md` primero, propagar a `ARCHITECTURE.md` y `TODO.md`        |
| Nuevo hallazgo de research         | `research/notes/` o `research/synthesis/` + actualizar indice en `research/README.md` |
| Nuevo eval type o task type        | `CURRENT_STATE.md` + `ARCHITECTURE.md` si cambia la superficie        |
| Cambiaste orchestrator/agent/env   | Re-correr diagnostico para verificar que no degradaron los entornos   |
| Cambiaste dependencia              | `pyproject.toml` + tech stack de este archivo                         |
| Cambiaste scoring o diseno de eval | Validar contra 20 escenarios (`investigation_scenarios_rubric.md`)     |
| Cambiaste convencion               | Este archivo, inmediatamente                                          |


### Commit workflow — MANDATORIO

```
1. Desarrollo + Tests + Validation
   Escribir codigo + pytest + ruff + E2E

2. Codex review + Fix     (MANDATORIO si MCP disponible, skip si trivial)
   Mandar a Codex para critica. Fixear hallazgos. Re-testear.
   Iterar hasta que Codex no tenga criticas graves.

3. Presentar al usuario   (SIEMPRE)
   Explicar en espanol. Pedir aprobacion.
   ESPERAR aprobacion. NO commitear sin ella.

4. Actualizar docs + Commit (solo DESPUES de aprobacion)

5. Sugerir proximos pasos
```

Ver `/precommit` skill para el protocolo completo.

## Principios de diseno del scoring — NO NEGOCIABLE

Estos principios aplican a CUALQUIER diseno de scoring, presente y futuro.
Surgen de la discusion sobre los 23 escenarios y de LA PREGUNTA.

### 1. UN solo metodo de scoring para todo

NO hay "scoring profiles" separados por tipo de investigacion. NO hay
switch/case entre "causal", "predictivo", "descriptivo". Hay UN metodo
general que funciona para cualquier caso. Si un caso particular tiene
una sola metrica puntual, el metodo general naturalmente se reduce a eso
— pero no porque lo hardcodeamos.

### 2. El sistema se adapta a los casos, no al reves

Si un paper seed produce un caso con una sola variable de interes, perfecto.
Si produce un caso con 5 outcomes en tension, perfecto. Si produce un caso
donde lo interesante es descubrir la estructura del sistema, perfecto.
El scoring no debe forzar a los casos a tener una forma particular.
**Los casos vienen de seeds reales — pueden ser cualquier cosa.**

### 3. El brief es libre y puede tener multiples objetivos

- "Investiga que afecta la recuperacion" → valido (un objetivo, un foco)
- "Investiga el sistema hospitalario" → valido (objetivo amplio, sin foco unico)
- "Investiga: (1) si el tratamiento funciona, (2) a traves de que mecanismo,
  (3) si hay confounding por severidad" → valido (3 objetivos especificos)
- Una pregunta vaga, varias preguntas, objetivos mixtos → todo valido.

### 4. No construir un juego estructurado

Si el scoring requiere que el caso defina "roles", "slots", "pattern_weights",
"investigation_type" y 10 campos de metadata para funcionar, estamos
construyendo un juego, no evaluando investigacion. El scoring debe ser
lo mas simple y general posible, y la complejidad debe estar en la
VERIFICACION (que ya es general via SCM), no en el framework de scoring.

### 5. La verificacion es el core, el scoring es un wrapper

El SCM puede verificar cualquier claim sobre cualquier par de variables.
ESO es lo valioso y general. El scoring solo necesita responder:
- Es verdad? (SCM)
- Es relevante a lo que se pidio? (brief)
- Cubrio lo que se pidio? (completitud)
- No spameo? (anti-shotgun)

---

## LA PREGUNTA — el ordenador de todo el proyecto

> **¿POR QUE ESTO TODAVIA NO ES UNA INVESTIGACION REAL? ¿QUE LE FALTA?**

**Esta pregunta debe estar presente en CADA decision, CADA evaluacion, CADA
linea de codigo.** No es un principio aspiracional — es el filtro operativo
diario. Si no podes responder "que le falta para ser investigacion real",
no entendes el problema.

### Como aplicarla

- **Al evaluar un SRC**: Se parece a un problema de investigacion real? Las preguntas
  son las que un investigador haria? Los datos tienen la estructura que tendria un
  dataset real? **Que le falta para que un cientifico lo confunda con un caso real?**
- **Al evaluar al solver**: Esta investigando como investigaria una persona? Usa los
  datos? Razona causalmente? O responde desde priors de pretraining? **Que le falta
  al entorno para FORZAR investigacion genuina?**
- **Al disenar cambios**: Este cambio acerca el entorno a investigacion real, o lo
  aleja? **Resuelve alguna de las brechas conocidas, o es cosmético?**
- **Al interpretar scores**: Un score bajo significa que el solver fallo como
  investigador, o que el caso estaba mal disenado? **El score captura calidad de
  investigacion o solo coincidencia numerica?**
- **Al priorizar trabajo**: Entre dos tareas, priorizar la que cierra una brecha
  mas grande entre SREG y la investigacion real.

### La respuesta evoluciona

La respuesta a "que le falta" cambia a medida que SREG mejora. Hoy las brechas
principales estan documentadas en `research/synthesis/sreg_scientific_coverage.md`.
Cada vez que se cierra una brecha, actualizar ese documento y re-preguntar:
**¿y ahora que le falta?**

### La regla de oro

Si algo no se parece a investigacion real, es un bug — no importa si los tests
pasan. Si algo se parece a un juego artificial (budgets de juguete, acciones
predefinidas, preguntas que se responden sin datos), hay que eliminarlo o
rediseniarlo.

## Validacion contra escenarios diversos — NO NEGOCIABLE

> **Cada decision de diseno importante (scoring, entornos, prompts, contratos)
> debe validarse mentalmente contra los 20 escenarios de investigacion.**
> Ver `research/synthesis/investigation_scenarios_rubric.md`.

### Por que existe esta regla

Es muy facil concentrarse en UN tipo de investigacion (ej: causal con un
target) y disenar algo que funciona perfecto para ese caso pero falla para
todos los demas. Los 20 escenarios cubren 11 tipos de investigacion con
3 tipos de espacio de respuesta (unica, acotada, abierta). Si un diseno
solo funciona para 3 de 20, es un juguete disfrazado.

### Como aplicarla

- **Al disenar scoring**: Funciona para predictivo (metrica puntual)?
  Para system mapping (sin target)? Para confounding (el hallazgo ES el sesgo)?
  Para multi-outcome (trade-offs)? Para epistemologico ("no se puede saber")?
- **Al agregar un concepto** (target_node, salience_map, relevance): Aplica
  a los 20? O solo a los causales con single-target? Si solo aplica a algunos,
  eso esta OK pero debe ser explicitamente acotado, no asumido como universal.
- **Al evaluar un cambio**: Mejora 3 escenarios pero rompe 5? No vale.
  Mejora 10 sin romper ninguno? Si vale.

### Los 20 escenarios en una linea

1. Causal simple (sepsis) | 2. Trade-off (inmuno) | 3. Policy+equidad (azucar)
4. Eco+socio (pesca) | 5. Ingenieria+risk (baterias) | 6. Diagnostico (logistica)
7. Multi-outcome (microbioma) | 8. Red/vulnerabilidad (electrica) | 9. Estructura (cerebro)
10. Confounding (farmaco) | 11. Seleccion (camaras) | 12. Heterogeneidad (personalizada)
13. Risk+subgrupos (calor) | 14. Descriptivo (redes) | 15. Predictivo (clima)
16. Screening (drug) | 17. Metodologico (estimadores) | 18. Optimizacion (reactor)
19. Taxonomia (depresion) | 20. Epistemologico (identificabilidad)
21. Transportabilidad (farmaco 2 poblaciones) | 22. Discriminacion de modelos (2 teorias)
23. Value-of-information (que medir siguiente)

### Referencia rapida

| Tipo de respuesta | Escenarios | Implicacion para scoring |
|---|---|---|
| Unica (metrica) | 15, 18 | Score = distancia al optimo |
| Acotada | 1, 4, 8, 10, 11, 16, 17, 20, 21, 23 | Claims verificables, conjunto finito |
| Abierta | 2, 3, 5, 6, 7, 9, 12, 13, 14, 19, 22 | Multiples investigaciones correctas |

### Taxonomia de investigacion

Los tipos de objetivos de investigacion estan documentados en
`research/synthesis/Doc1_Taxonomia_El_Mapa.md`. Esa es la referencia canonica
para clasificar cualquier investigacion. Los 23 escenarios son instancias
concretas de esa taxonomia.

### Diseno del proximo scoring (sub-preguntas ocultas)

El diseno de la proxima version del scoring esta en
`research/synthesis/oi_scoring_next_design.md`. Es un documento vivo
que se actualiza durante implementacion. La idea central: el orchestrator
genera sub-preguntas ocultas (inspiradas en el seed) que son el criterio
real de evaluacion. Claims y sub-preguntas pasan por el mismo pipeline
de compilacion formal.

## Harness de evaluacion — como sabemos si SREG funciona

Tres niveles fundamentalmente distintos. Cada uno responde una pregunta
diferente y se corre en momentos diferentes.

### Nivel 1: Tests automaticos (`pytest`)

**Pregunta:** "El codigo funciona?"
**Cuando:** antes de cada commit. Siempre.
**Como:** `pytest tests/ -v` + `ruff check src/ tests/`

### Nivel 2: Diagnostico de entornos (`/eval`)

**Pregunta:** "Los entornos generados son buenos?"
**Cuando:** despues de cambios que afecten generacion (templates, prompts,
orchestrator, data pipeline, problem builder).
**Como:** generar SRCs reales con el sistema completo y evaluarlos.

Tiene dos componentes igualmente importantes:

#### 2a. Cuantitativo (DiagnosticRunner)
Metricas automaticas: KL, submit rate, baseline comparison por eval type,
budget efficiency, failure modes. Ver `/eval` skill.

#### 2b. Cualitativo (Rubrica + descubrimiento abierto)
**LEER los casos generados.** Esto no es opcional ni secundario — es donde
se encontraron TODOS los problemas fundamentales de SREG hasta ahora.

Dos fases:
1. **Rubrica estructurada**: evaluar dimensiones conocidas (0-1-2) y
   critical failures (si/no). Ver `research/synthesis/qualitative_eval_rubric.md`.
2. **Descubrimiento abierto**: leer el caso con ojos frescos y buscar
   CUALQUIER cosa que no se sienta como investigacion real. Los problemas
   nuevos no estan en la rubrica — hay que buscarlos activamente.

**No-data baseline probe**: darle el brief + preguntas a un LLM SIN dataset.
Si responde bien, el SRC no fuerza investigacion. Es el test mas poderoso.

#### Evolucion de la rubrica

La rubrica es un piso, no un techo. Se evoluciona asi:

1. **Descubrimiento**: durante evaluacion cualitativa se encuentra un
   problema nuevo (no cubierto por las dimensiones/CF existentes)
2. **Registro**: se documenta en `research/synthesis/qualitative_eval_rubric.md`
   seccion "Registro de hallazgos" con fecha, evidencia, y caso donde aparecio
3. **Promocion**: si el problema aparece en 2+ evaluaciones independientes,
   se promueve a nueva dimension o critical failure
4. **Refinamiento**: las dimensiones existentes se detallan con sub-criterios
   cuando la escala 0-1-2 no captura suficiente matiz

**Regla clave**: si encontras un problema y no esta en la rubrica, el
problema es real y la rubrica esta incompleta. Nunca ignorar un problema
porque "no esta en el checklist".

### Nivel 3: Transfer benchmark (FUTURO, SEPARADO)

**Pregunta:** "Entrenar en SREG mejora las policies?"
**Cuando:** cuando haya policies entrenadas.
**Como:** benchmarks externos (CLadder, QRData, DiscoveryBench).
No es parte de SREG core. Ver `research/synthesis/benchmark_analysis.md`.

### Referencia rapida

| Nivel | Skill | Frecuencia | Que mide |
|-------|-------|------------|----------|
| L1 Tests | `/test` | Cada commit | Codigo funciona |
| L2 Cuanti | `/eval` | Post-cambio generacion | Metricas de entornos |
| L2 Cuali | `/eval` | Post-cambio generacion | Realismo, coherencia, problemas nuevos |
| L3 Transfer | — | Futuro | Mejora de policies |

## Project overview

SREG genera entornos sinteticos de investigacion con reward signals exactos,
para entrenar razonamiento cientifico via RL. Ver `PROJECT.md` para la
vision completa, `ARCHITECTURE.md` para el diseno del sistema.

**Terminologia clave:**

- **SRC** (Synthetic Research Case): la unidad de producto — world + problem + tasks + data
- **Teacher**: policy optima (upper bound del reward)
- **SCM** (Structural Causal Model): la verdad formal oculta de cada SRC.
  Grafo causal + ecuaciones + ruido. Engine principal del pipeline E2E.
  Ver `research/synthesis/scm_migration_rationale.md` para los fundamentos.
- **BN** (legacy): red bayesiana discreta. Disponible pero ya no se usa en
  el pipeline principal. Se mantiene por backward compatibility.

## Environment setup

```bash
conda activate sreg
```

Python 3.11. Recrear: `conda create -n sreg python=3.11 -y && conda activate sreg && pip install -e ".[dev]"`

## Tech stack

- **pgmpy** — BN construction + inference (`DiscreteBayesianNetwork`, NOT `BayesianNetwork`)
- **networkx** — DAG validation (`nx.is_d_separator()`, NOT `nx.d_separated`)
- **numpy / scipy** — sampling, distributions
- **pydantic v2** — data contracts (`BaseModel`, not dataclass)
- **openai SDK** — LLM via Azure AI Foundry, Responses API (`client.responses.create`, NOT `chat.completions`)
- **pytest** + **ruff** (line length 100)

Env vars: `AZURE_INFERENCE_CREDENTIAL`, `AZURE_FOUNDRY_BASE_URL`, `AZURE_MODEL` (orchestrator),
`AZURE_SOLVER_MODEL` (solver, defaults to AZURE_MODEL)

## Project structure

```
src/sreg/
├── models/          # Pydantic contracts (World, Episode, Task, Score, DAGSpec, CasePlan...)
├── inference/       # LLM protocol (ModelClient, OpenAIClient, ToolEnrichedClient, responses_utils)
├── world/           # Templates, cpd_gen, DAG generators, pgmpy utils
├── solver/          # Teacher (exact Bayesian inference)
├── tools/           # WorldGen, WorldCheck, EpisodeGen, TaskGen, Verifier, ProblemBuilder
├── env/             # EpisodeRunner
├── orchestrator/    # LLM orchestrator (function calling, case design)
├── agent/           # Solver diagnostico (python_exec, engine, solve_case)
├── benchmarks/      # CLadder, QRData, DiscoveryBench adapters
├── training/        # SregEnv/verifiers adapter (experimental)
├── harness/         # DiagnosticRunner, trajectories, comparison
└── display.py

scripts/
├── generate_src.py        # Generar SRCs (--inspect, --solve, --report, PDF seeds)
├── run_benchmark.py       # Benchmarks externos (--with-tools, --base-url)
├── run_diagnostic.py      # N SRCs + metricas + failure modes
├── serve_model.sh         # vLLM setup
├── demo.py                # Demo sin LLM
├── view_case.py           # Inspeccionar casos exportados
├── view_trajectory.py     # Inspeccionar trayectorias
├── batch_sweep.py         # Parameter sweep
├── semantic_transform.py  # Transformar SRC a modo abstract/fictional
└── run_inspiration_reports.py  # Batch inspiration reports

seeds/               # Paper seeds (PDF, markdown)
experiments/         # Resultados de diagnostico
research/            # Analisis, hallazgos, sintesis (ver research/README.md)
tests/               # Mirrors src/ structure
.claude/skills/      # /plan, /status, /test, /review, /phase, /codex-collab
```

## Code conventions

- Type hints on public functions
- `__all__` exports in every `__init__.py`
- Tests mirror src: `src/sreg/tools/X.py` → `tests/tools/test_X.py`
- Imports: stdlib → third-party → local, separated by blank lines
- Terminal output: ASCII-safe (Windows cp1252)
- Communicate with the user in **Spanish**

## Commands

```bash
pytest tests/ -v                          # All tests
pytest tests/tools/test_world_gen.py -v   # Specific file
ruff check src/ tests/                    # Lint
ruff format src/ tests/                   # Format
```

## Git conventions

- Branch naming: `feature/<name>`, `fix/<name>`, `refactor/<name>`
- Commit messages: imperative mood, concise
- Always ask user before pushing

## Codex collaboration

**Only when Codex MCP is available.** Codex = critical collaborator, not yes-man.

- **Mandatory**: code review after implementation
- **Recommended**: strategy, design, problem-solving (use judgment)
- **Skip**: doc-only, trivial fixes

Claude leads, Codex advises. Present BOTH perspectives when disagreeing.
See `/codex-collab` skill for full protocol.

### Thread management — NON-NEGOTIABLE

**SIEMPRE usar `codex-reply` con el `threadId` existente para continuar una
conversacion.** Solo usar `mcp__codex__codex` (sesion nueva) cuando el tema
sea genuinamente diferente. Codex retiene todo el contexto en el thread —
re-explicar desperdicia tokens y produce respuestas mas superficiales.

- Guardar el `threadId` de la primera llamada y reutilizarlo en TODOS los
  follow-ups del mismo tema o sesion. El tool requiere el threadId explicito
  — es responsabilidad de Claude trackearlo, NO del usuario.
- Si no hay threadId previo o el tema cambio completamente → sesion nueva.
- En caso de duda, USAR REPLY.

## Worktrees

Multiple Claude Code sessions MUST use worktrees (`claude --worktree <name>`).
Each worktree gets its own branch and working directory. Check at session start:

```bash
git rev-parse --git-dir   # "worktrees/" = you're in one
git branch --show-current
```

Rules: each session owns specific files, shared docs are danger zones,
merge via main session review (not blind merge). No active worktrees currently.
