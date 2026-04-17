# SREG — Claude Code Project Configuration

## 🚨 MODO DE TRABAJO ACTUAL: COLABORATIVO 🚨
*(Cambiar a "AUTORESEARCH" cuando se requiera trabajo autónomo sin frenar)*

Existen **DOS modos de trabajo completamente distintos**.

### MODO 1: COLABORATIVO (Con el usuario)
Este es el flujo de siempre. Es pausado, interactivo y requiere aprobación humana.
- **Ir contando lo que haces** paso a paso, amigablemente, en español.
- **Consultar antes de avanzar** — no hacer 3 pasos seguidos sin preguntar.
- **Explicar decisiones** — por qué elegiste este approach, qué alternativas descartaste.
- **Debatir con Codex** — buscar una segunda opinión técnica antes de implementar cambios grandes.
- **Esperar feedback** entre pasos significativos. No commitear sin OK explícito.

### MODO 2: AUTORESEARCH (Autónomo)
Este modo es para cuando el usuario te pide que investigues o implementes algo por tu cuenta, sin frenar.
- **NO frenar a menos que el usuario interrumpa.**
- **Registrar todo** a modo de logs y documentos en `research/`.
- **Ciclo Iterativo Autónomo:** PENSAR (hipótesis) -> PROBAR (scripts/experimentos) -> ANALIZAR (documentar resultados) -> PENSAR...

---

## 🚨 PRINCIPIOS RECTORES Y CHECKLIST DE DISEÑO 🚨

**OBLIGATORIO PARA AMBOS MODOS.** Antes de escribir código, debes demostrar (en el chat o en tus logs de autoresearch) que el diseño propuesto respeta estos principios.

### LA PREGUNTA (El filtro diagnóstico)
> **¿Por qué esto todavía no es una investigación real? ¿Qué le falta?**
>
> **¿Por qué un modelo entrenado con RL sobre SREG todavía no aprendería buen juicio científico?** Que le falta al sistema para enseñar: research taste, descomposición de problemas, generación de preguntas fine-grained, buen plan de investigación, saber qué es relevante para el objetivo y qué no, saber cuándo una conclusión es prematura vs bien fundada.

### PRESIONES EVOLUTIVAS (El criterio de diseño)
> **SREG debe estar diseñado para que las presiones evolutivas fuercen que
> los agentes bien puntuados tengan buen juicio científico** — porque NO
> tener estas habilidades produce en promedio scores más bajos.
>
> **Test de diseño:** para cada componente, ¿un agente SIN la propiedad X
> obtiene en promedio un score más bajo? Si no, hay que rediseñar.
>
> Lista completa de propiedades en `PROJECT.md` sección "Presiones evolutivas".

LA PREGUNTA y las presiones evolutivas son complementarias: LA PREGUNTA diagnostica ("¿qué falta?"), las presiones evolutivas son el criterio de diseño ("¿el scoring fuerza esto?").

Cada decisión pasa por este TRIPLE filtro:
1. ¿Se parece a investigación real? Si no, es un bug.
2. ¿Crea presión evolutiva hacia buen juicio científico? Si no, rediseñar. (Ver lista en `PROJECT.md`)
3. ¿Funciona para la MAYORÍA de los tipos de investigación? No solo "X causa Y" — system mapping, structure discovery, descriptivo, predictivo, epistemológico, optimización, multi-outcome, etc. Si solo funciona para causal simple, es un juguete. Repasar mentalmente los escenarios diversos ANTES de diseñar: `research/synthesis/investigation_scenarios_rubric.md`.

### El Checklist de Diseño (Responde estas 4 preguntas antes de codear):
1. **¿Estoy creando un parche hardcodeado o una regla universal?**
   *(Si escribes `if tipo == X` para manejar un caso borde, estás fallando. Busca la propiedad matemática subyacente. Ej: la verdad canónica es el output del SCM, no una aserción forzada).*
2. **¿Esto mete un LLM en el loop de scoring de VERDAD?**
   *(Prohibido. La Verdad es matemática contra el SCM. La Relevancia puede usar LLM hoy, pero debe ser reemplazable por feature-matching para RL).*
3. **¿Esto fuerza al sistema a un tipo de investigación específico?**
   *(Debe soportar causal simple, system mapping, descriptivo, epistemológico, etc).*
4. **¿El Solver podría hackear esto sin investigar los datos?**
   *(Si el Solver gana puntos adivinando o usando fuerza bruta textual, el reward es débil).*

### Principios de Scoring — NO NEGOCIABLES
1. **UN solo método para todo** — sin scoring profiles por tipo de investigación.
2. **El sistema se adapta a los casos** — el scoring no fuerza una forma.
3. **El brief es libre** — una pregunta, varias, vagos, mixtos: todo válido.
4. **No construir un juego** — si necesita "roles", "slots", "pattern_weights" para funcionar, es un juego, no evaluación de investigación.
5. **Verificación es el core** — el SCM verifica. El scoring solo pregunta: ¿es verdad? ¿es relevante? ¿cubrió lo pedido? ¿no spameó?
6. **Diversidad de investigación** — todo diseño debe funcionar para los tipos diversos de investigación. No diseñar solo para "X→Y".

## Donde buscar que

| Necesito... | Ir a... |
|---|---|
| Entender como funciona el sistema hoy (usuario, explicacion AMIGABLE) | `CURRENT_STATE.md` |
| Entender la arquitectura tecnica | `ARCHITECTURE.md` |
| Vision, principios, invariantes | `PROJECT.md` |
| Que hacer / trabajo pendiente | [Project "SREG Roadmap"](https://github.com/users/lucaspecina/projects/4) + GitHub Issues. Ver seccion "Git + GitHub Issues + Project + Codex" abajo. |
| Historial de cambios | `CHANGELOG.md` |
| Historico TODO v1 | `docs/archive/todo_v1_history.md` |
| Indice de research (que doc es canon, cual no) | `research/README.md` |
| **Tesis/paper: que hay que demostrar** | `research/synthesis/thesis_evaluation_framework.md` |
| **Tesis/paper: config operativa (modelo, harness, suite)** | `research/synthesis/sreg_training_transfer_protocol.md` |
| **Tesis/paper: related work (SandMLE)** | `research/synthesis/related_work_sandmle.md` |
| **Tesis/paper: related work (SciGym)** | `research/synthesis/related_work_scigym.md` |
| **Tesis/paper: related work (SciAgentGym)** | `research/synthesis/related_work_sciagentgym.md` |
| **Tesis/paper: benchmarks externos, ejemplos y transfer** | `research/synthesis/external_benchmarks_transfer_analysis.md` |
| 23 escenarios de validacion | `research/synthesis/investigation_scenarios_rubric.md` |
| Vision de Open Investigation | `research/synthesis/open_investigation_vision.md` |
| Scoring fundamentals | `research/synthesis/oi_scoring_fundamentals.md` |
| Taxonomia de investigacion | `research/synthesis/Doc1_Taxonomia_El_Mapa.md` |
| Scoring next design (sub-questions) | `research/synthesis/oi_scoring_next_design.md` |
| **Eval suites (4 suites sistematicas)** | `research/synthesis/eval_suite_framework.md` |
| **Science Coverage suite (diseño)** | `research/synthesis/eval_suite_science_coverage.md` |

## Skills disponibles

| Skill | Cuando usarla |
|---|---|
| `/run` | Generar un caso de investigacion con LLM |
| `/eval` | Evaluar calidad de casos (L2, la que importa) |
| `/rescore` | Re-evaluar casos congelados sin regenerar (P0) |
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
3. **GitHub Issues** — completaste algo? Cerrar issue con `gh issue close`. Surgio algo nuevo? Crear con `gh issue create` + labels (`lane:*`, `type:*`, `prio:*`).
4. **research/README.md** — cambiaste o creaste docs de research? Actualizar indice.
5. **ARCHITECTURE.md** — cambiaste componentes, contratos o flows? Actualizar.
6. **Tests y scripts** — el cambio deja tests o scripts obsoletos? Eliminarlos.
7. **Skills, memorias, otros** — el cambio deja skills (`.claude/skills/`),
 memorias, o scripts con referencias obsoletas? Actualizarlos o eliminarlos.

**"Actualizar" no es solo docs del repo. Es TODO lo que referencia al sistema:
skills, memorias, scripts, configs. Si algo quedo desactualizado, arreglarlo.**

## Validacion — LA UNICA QUE IMPORTA ES E2E

**La validacion real de CUALQUIER cambio es una evaluacion multi-nivel,
cualitativa, del end-to-end de la investigacion real.** Unit tests son un
check mecanico secundario — confirman que el codigo no rompe, nada mas.
NUNCA usar unit tests como evidencia de que un cambio "funciona". Para
saber si funciona: correr el pipeline E2E con LLM real (`/run --oi`) y
evaluar cualitativamente el resultado (`/eval`).

**Escenarios diversos — NO NEGOCIABLE**: los E2E SIEMPRE deben cubrir tipos
variados de investigacion. NUNCA correr solo causal simple. Cada batch de
validacion debe incluir al menos 3 tipos distintos de:
`research/synthesis/investigation_scenarios_rubric.md` (system mapping,
heterogeneidad, confounding, descriptivo, multi-outcome, epistemologico, etc.).
Si solo probaste "X causa Y", NO validaste nada. Usar seeds de `seeds/`
para generar casos diversos: `python scripts/generate_src.py --seed-file seeds/X.md -o ... --oi`.

**Unit tests - MINIMO INDISPENSABLE**
- **Solo correr tests DESPUES de cambiar codigo.** No como ritual, no como
  verificacion previa a commit, no "por si acaso". Si no cambiaste codigo,
  no corras tests.
- **NUNCA correr la suite completa** salvo que el usuario lo pida explicitamente.
- Si cambias un archivo, correr SOLO el test de ese archivo. UNA VEZ.
- Si falla un import, arreglar el import — no re-correr toda la suite.
- **NUNCA** correr tests en paralelo ni repetir la misma suite.
- En caso de duda: NO correr tests. Preguntar al usuario.

## Environment setup

```bash
conda activate sreg # Python 3.11
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
 models/ # Pydantic contracts (SCM, OI, tasks, episodes)
 inference/ # LLM protocol (ModelClient, Responses API)
 world/ # SCM engine (scm.py, expression compiler, scm_data)
 solver/ # SCMSolver (teacher / ground truth)
 tools/ # SCM pipeline + OI pipeline (compiler, verifier, salience, runner)
 orchestrator/ # LLM orchestrator (function calling, SCM-only)
 agent/ # python_exec + tool-calling engine (for OI solver)
 benchmarks/ # CLadder, QRData, DiscoveryBench
scripts/ # generate_src.py, run_oi.py, rescore.py, run_benchmark.py
seeds/ # Research seeds (.md/.pdf) for diverse E2E generation
tests/ # Mirrors src/ structure
research/ # Analisis y sintesis (ver research/README.md)
docs/archive/ # Historico (todo_v1_history.md, issue-tracker/, etc.)
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

## Git + GitHub Issues + Project + Codex

### Modelo mental (CRITICO — no confundir los 3 conceptos)

| Concepto | Que es | Vida util |
|---|---|---|
| **Epic** | Meta concreta con criterio de cierre. El QUE y el POR QUE. Unit of thought. | Semanas/meses |
| **Worktree** | Directorio fisico donde corre una sesion de Claude aislada. Mecanismo de paralelizacion. | Finito, se borra tras merge |
| **Issue** | Unidad atomica = 1 PR | Dias |

Reglas:
- **Epic NO es un label ni un tema paraguas**. Es una meta cerrable con criterio explicito.
- **Worktree es detalle de ejecucion**, no de planificacion. Un epic PUEDE spanear varios worktrees; un worktree PUEDE tocar varios epics. En la practica son 1:1 la mayoria del tiempo, pero es coincidencia.
- **Un issue puede ser standalone** (sin epic padre). Reservado para one-offs: bugs, docs, research parkeado.

### Cuando crear un epic (reactivo, no predictivo)

Crear epic SOLO si:
- Podes identificar 3+ sub-issues concretos, cada uno un PR separado
- El trabajo va a spanear semanas
- Hay criterio claro de cierre

**Reactivo**: si Suite 2 descubre que el compiler falla, abrís issues individuales. Si despues de 3+ fixes relacionados aparece un patron, promoves a epic y re-parenteas. **No crees epics para trabajo que no descubriste todavia.**

### Template de body (OBLIGATORIO para epic o issue)

Dos publicos: el humano (vos) y Claude (sesiones futuras).

```
## Contexto (para humanos)

<1-3 frases en español plano: que es, por que importa, cuando lo harias>

## Detalle tecnico (para Claude / sesiones)

<jerga, refs a codigo, decisiones, edge cases, links a docs de research/>

## Criterio de cierre

<que tiene que pasar para que esto este hecho>
```

### Epics activos (SREG)

| Epic | # | Worktree dominante | Cierra cuando |
|---|---|---|---|
| Suites de correctness del sistema (1, 2, 4) | #26 | eval-suite | Las 3 suites pasan baseline |
| Science coverage — mapeo del sistema | #29 | eval-suite | Cobertura mapeada + report |
| Benchmarkear Qwen3-8B con benchmarks externos | #30 | qwen-benchmarks | Qwen3-8B corrio en los 4 benchmarks |
| Infra de entrenamiento RL con Qwen sobre SREG | #31 | rl-training-infra | Infra completa + primer RL run valida |
| Investigacion secuencial tipo Sherlock (parked) | #16 | (por definir) | A definir cuando se retome |

### Standalones activos (no pertenecen a ningun epic)

- Verifier: hacerlo mas robusto (#1)
- Scoring por unidad / credit assignment (#2)
- Modos semanticos — ficticio/abstracto (#18, parkeado, retomar despues)
- Consolidar docs post-v1 (#21)
- Bug: world fingerprint inestable (#22)

**Tesis v1 NO es epic**. Es la motivacion north-star. Los epics concretos la alimentan cuando cierran.

### Labels (3 — todo lo demas fue eliminado)

| Label | Cuando |
|---|---|
| `bug` | Es un bug real (default GitHub) |
| `blocked` | Esperando dependencia |
| `parked` | Idea abierta pero no activa (ej: Sherlock, modos semanticos) |

**Nada mas**. Sin `lane:*`, `type:*`, `area:*`, `prio:*`. La info vive en:
- Titulo del epic padre (ya te dice el "que")
- Worktree del Project (ya te dice el "donde")
- Body del issue con template de 3 secciones (te dice el por que y el como)

### Project v2 "SREG Roadmap"

URL: https://github.com/users/lucaspecina/projects/4

**Campos**:
- **Status** (default GitHub): Todo / In Progress / Done. Auto-update al cerrar issue.
- **Worktree** (custom): `eval-suite`, `qwen-benchmarks`, `rl-training-infra`, `main`, `none`.

**Views recomendadas**:
- **Epics** — Board, Group by `Parent issue`. Ves progreso por epic + standalones ("no parent").
- **Worktrees** — Board, Group by `Worktree`. Ves que esta activo en cada worktree fisico.

**Prioridad** = orden manual en la columna Todo (drag&drop). NO es label.

### Issue workflow

- **1 issue = 1 PR**. Worktree puede agrupar varios issues si estan en el mismo stream.
- **Epics + sub-issues nativos** (API de GitHub, NO "Part of #N" en body).
- Branch naming: `issue/NNN-short-slug`.
- PR body empieza con `Closes #NNN` para cierre automatico.
- Squash merge preferido.
- Commits referencian con `Refs #NNN descripcion` (no cierra; `Closes` solo en PR body).

### Flujo para empezar un issue

1. Abrir Project board (view Epics) → elegir lo que esta arriba de la columna Todo
2. Mover card a Status=In Progress (drag, o `gh project item-edit`)
3. Ver Worktree del Project → si es `main`, trabajar en main. Si es otro, `cd` ahi (o `claude --worktree <nombre>`)
4. Commitear con `Refs #NNN ...`
5. PR con `gh pr create` + body `Closes #NNN`
6. Tras merge: GitHub cierra issue, Project lo mueve a Done automaticamente

### Flujo para crear un issue nuevo

1. Decidir: ¿sub-issue de un epic existente o standalone?
2. `gh issue create --title "..." --body "..."` con template de 3 secciones
3. Labels: agregar `bug` si aplica. No agregar mas salvo `blocked` o `parked`.
4. Agregar al Project: `gh project item-add 4 --owner lucaspecina --url <issue-url>`
5. Setear campo Worktree
6. Si es sub-issue: linkear al epic via API de sub-issues (NO "Part of #N" en body)

### gh CLI

`gh` en PATH. Authenticated as `lucaspecina`. Scopes: `project, read:project`.
Si falla auth: `gh auth refresh -s project,read:project`.

### Git general

- Always ask user before pushing. Multiple sessions: `claude --worktree <name>`.
- Worktrees legacy (`worktree-*`, `eval-suite`) mantienen naming viejo.
  Work nuevo usa `issue/NNN-*`.
- Worktrees existentes deben mergear main para traer docs actualizados.

### Codex

- **Codex** (when MCP available): mandatory for code review, recommended for design.
  Reusar `threadId` con `codex-reply`. Sesion nueva solo si el tema cambio.
- **CLAUDE LIDERA, CODEX ASESORA.** Formar opinion propia ANTES de consultar.
  Presentar ambas opiniones, argumentar desacuerdos. El usuario decide.