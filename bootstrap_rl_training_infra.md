# Bootstrap — worktree rl-training-infra

## Quien sos y donde estas

Sos una sesion de Claude Code corriendo en el worktree `rl-training-infra`
del proyecto SREG. Este worktree existe para llevar a SREG desde
"entorno de investigacion" a "entorno de training RL real" — correr el
primer SFT/RL sobre Qwen3-8B con SREG como fuente de reward verificable.

**Este worktree NO empieza de cero.** Hay un trabajo previo extenso
que tenes que recuperar y continuar (ver "Estado actual del repo").

## Por que este worktree existe

La tesis requiere demostrar que entrenar un modelo con RL sobre SREG
produce mejora real en benchmarks externos de razonamiento cientifico.
Eso implica tres cosas que hoy no estan en main:

1. Un **SregEnv** que envuelve SREG como entorno `verifiers`-compatible
   (PrimeIntellect-ai/verifiers) — cada step es una accion del solver
   (observar variable, razonar, submit), el reward terminal es
   `score.total`.
2. Un **dataset de training** (SFT + RL) generado a partir de los
   seeds SREG existentes, con split train/held-out congelado.
3. Un **primer run real** de entrenamiento que produce un checkpoint
   listo para evaluar AFTER en los benchmarks externos.

El **AFTER** NO lo corres vos. Lo corre el worktree hermano
`qwen-benchmarks`, que ya esta construyendo los BEFOREs oficiales.
Vos producis el checkpoint entrenado; ellos lo miden. Acordar el
contrato del checkpoint es parte del scope.

---

## Lo que ya se resolvio en `qwen-benchmarks` (sesion previa)

El worktree `qwen-benchmarks` (branch `worktree-qwen-benchmarks`) ya
resolvio varios problemas de infra que este worktree necesita. **No
redisenar, adoptar:**

### Inferencia dual-backend

Se creo `src/sreg/inference/chat_client.py` con un `ChatCompletionsClient`
para hablar con vLLM via Chat Completions API (vLLM **NO soporta**
Responses API — PR #16720 fue cerrada sin merge). Tambien se refactoreo
`tool_client.py` con un `ToolEnrichedClient` dual-backend que detecta
automaticamente:

- **Path A (Responses API):** usa `previous_response_id` chaining.
  Para Azure/OpenAI nativo. `OpenAIClient.supports_previous_response_id = True`.
- **Path B (Chat Completions):** reconstruye historial completo cada turno.
  Para vLLM y cualquier servidor Chat Completions. 
  `ChatCompletionsClient.supports_previous_response_id = False`.

Se agrego `Message.tool_calls: list[ToolCall] | None` en `protocol.py`
para soportar la reconstruccion de historial en Path B.

**OJO:** Este codigo es para el harness de benchmarks (`run_benchmark.py`).
El **training** usa `verifiers` que tiene su propia integracion con vLLM
via `ClientConfig` + `SamplingArgs`. No son lo mismo.

### vLLM tool calling — lo que aprendimos

- vLLM solo soporta Chat Completions API (`/v1/chat/completions`)
- Tool calling requiere dos flags en el servidor:
  `--enable-auto-tool-choice --tool-call-parser hermes`
- Qwen3-8B tiene "thinking mode" que **debe desactivarse** para tool
  calling: `extra_body={"chat_template_kwargs": {"enable_thinking": False}}`
- **Fallo silencioso**: vLLM puede no parsear tool calls y devolver
  texto plano. El modelo "intenta" llamar tools pero el servidor no lo
  estructura. Hay warnings implementados en `tool_client.py` pero hay
  que monitorear. Si ves texto mencionando `python_exec` o `function`
  sin tool_calls parseados, revisar flags de vLLM.

### `serve_model.sh` actualizado (CANONICO)

La version de `qwen-benchmarks` es la canonica. Cambios vs el branch
viejo (`worktree-rl-env-verifiers`):

| Parametro | Branch viejo | Version actual (canonica) |
|---|---|---|
| Modelo default | `Qwen/Qwen2.5-0.5B-Instruct` | `Qwen/Qwen3-8B` |
| `--max-model-len` | `4096` | `16384` |
| `--gpu-memory-utilization` | `0.85` | `0.90` |
| `--max-len` CLI arg | no existia | agregado |

Ambas versiones ya usan `--enable-auto-tool-choice --tool-call-parser hermes`.

### Bugs corregidos

1. `extra_body` con `enable_thinking: False` solo se inyecta cuando
   `--base-url` esta explicitamente seteado (= servidor vLLM real, no Azure)
2. Retry logic en `chat_client.py` ahora cubre errores de `"max"` tokens
   (alineado con `openai_client.py`)
3. Warning cuando el modelo devuelve texto mencionando tools pero no se
   parsearon tool_calls (ambos paths: chaining y history replay)

---

## Infra GPU — H100 Azure ML

### Skills de conexion

- **Skill general**: `C:/Users/YT40432/.claude/skills/azure-ml-connect/SKILL.md`
- **Skill detallada (workflow)**: `C:/Users/YT40432/Desktop/lp/research/lucaspecina/grubrics-science/.claude/skills/h100-workflow/SKILL.md`

### Conexion SSH

```bash
# Directo
ssh azure-ml   # Host azure-ml, Port 50000, key ~/.ssh/aml-ci-lucas.pem

# One-liner (ejecutar comando remoto)
ssh azure-ml 'source $HOME/miniconda3/etc/profile.d/conda.sh && conda activate RL && cd <path> && <CMD>'

# Sesion persistente
ssh azure-ml
tmux new -s training
# ... trabajo ...
# Ctrl+B, D para detach
# tmux attach -t training para reconectar
```

### Setup en la H100

```bash
# Clonar repo (primera vez)
cd /afh/projects/ai-coscientist-agents-f4775a1e-a13a-4809-8622-a559fef7a1e6/shared/Users/lucas.pecina/
git clone <repo-url> synthetic-research-envs
cd synthetic-research-envs

# Activar entorno
conda activate RL

# Instalar SREG
pip install -e ".[dev]"

# Instalar vLLM (para servir Qwen3-8B)
pip install vllm
# O usar: bash scripts/serve_model.sh --setup

# Servir modelo
bash scripts/serve_model.sh
# API disponible en http://localhost:8000/v1
```

### Costos y disponibilidad

- **Costo estimado**: ~$6.98/h (verificar tarifa actual en Azure Portal)
- **Estado actual (2026-04-13)**: provisioning fallo en East US con error
  "Allocation failed — VM Size constraint". Puede requerir otra region
  (East US 2, South Central US, West US 3) o esperar disponibilidad.
- **Username SSH**: `lucas` (configurado al crear la instancia)
- **Clave publica**: extraida de `~/.ssh/aml-ci-lucas.pem` via
  `ssh-keygen -y -f C:\Users\YT40432\.ssh\aml-ci-lucas.pem`

---

## Testing sin GPU (para desbloquear Pieza 3)

Para smoke tests del `dry_run.py` y del `SregEnv` sin esperar la H100,
hay dos opciones:

### Opcion A: Hosted API (Together AI / Fireworks)

Together AI y Fireworks AI sirven Qwen3-8B con API OpenAI-compatible.
El `ChatCompletionsClient` funciona directo:

```bash
# Together AI
python scripts/dry_run.py --backend vllm \
    --api-url https://api.together.xyz/v1 \
    --api-key $TOGETHER_KEY \
    --model Qwen/Qwen3-8B
```

Free tier disponible. Suficiente para smoke tests (no para training).

### Opcion B: Azure Chat Completions

Azure soporta Chat Completions ademas de Responses API. Se puede testear
el `ChatCompletionsClient` contra Azure sin GPU. **No inyectar
`enable_thinking` extra_body** (eso es solo para vLLM + Qwen).

### Lo que NO se puede testear sin GPU

- Training real (SFT/GRPO) — requiere GPU dedicada
- Throughput y latencia de vLLM local
- Concurrencia de rollouts (G=8 por prompt)
- Benchmarks oficiales de Qwen3-8B (esos los corre `qwen-benchmarks`)

---

## Contexto: que hay de trabajo previo

Hay un branch remoto **`origin/worktree-rl-env-verifiers`** con 5
commits (~4000 lineas) que NO estan en main. Fue el primer pase de
esta integracion, iniciado en sesiones anteriores. Los commits son:

1. `6f32ae1` Session C setup: worktree identity + training integration plan
2. `d192f49` Training adapter layer: types, validators, adapters, rubric, prompts (T1.1-T1.5)
3. `d053f42` SregEnv: complete verifiers environment + integration tests (T1.4-T1.9)
4. `a2d53fa` python_exec tool: persistent Python interpreter for RL agent data analysis
5. `4b47706` Dataset generation + dual-backend dry run (T2.1, T2.2, T3.1)

### Estado real del branch (leido directamente)

Segun `TRAINING_SESSION.md` y `TODO_TRAINING.md` del branch:

**Completo (Phase 1-2 + parte de Phase 3):**
- `SregEnv(vf.StatefulToolEnv)` funcional con 3 tools (observe_variable, python_exec, submit)
- Rubric con `reward_funcs` (reward terminal exacto via score)
- Dataset loader (`dataset.py`)
- Dual-backend dry run (`dry_run.py`) — probado en RTX 4000 Ada con Qwen2.5-0.5B-Instruct
- 168 tests passing
- python_exec con namespace persistente (numpy, pandas, scipy)

**Pendiente (Phase 3 incompleta + Phase 4-5):**
- T2.3: Teacher trajectories para SFT
- T2.4: Dataset validation
- T3.2: Reward para todos los 9 eval types
- T3.3: Failure modes testing
- T3.4: vLLM en Linux nativo (solo se probo local en Windows)
- Phase 4: Training config, SFT warm-start, primer GRPO run
- Phase 5: Difficulty curriculum, eval-type curriculum (futuro)

**Riesgos conocidos (del branch):**
- API de `verifiers` inestable (pinneada a version especifica)
- python_exec sandbox es soft (aceptado para v1)
- Qwen 0.5B tiene submit rate bajo → necesita SFT + upgrade a 8B

### Archivos del branch (no estan en main)

Produccion:
- `src/sreg/training/__init__.py`
- `src/sreg/training/_compat.py` — Windows fcntl patch
- `src/sreg/training/types.py` (57 lineas)
- `src/sreg/training/validators.py` (80 lineas)
- `src/sreg/training/adapters.py` (100 lineas)
- `src/sreg/training/prompts.py` (100 lineas)
- `src/sreg/training/rubric.py` (128 lineas) — **Rubric con reward_funcs**
- `src/sreg/training/dataset.py` (181 lineas) — **dataset loader**
- `src/sreg/training/env.py` (258 lineas) — **SregEnv (StatefulToolEnv)**
- `src/sreg/training/tools.py` (384 lineas) — **python_exec + think**
- `scripts/dry_run.py` (534 lineas) — **dual-backend dry run**
- `scripts/serve_model.sh` (85 lineas) — **vLLM serve (VERSION VIEJA)**

Tests (~1800 lineas): `tests/training/test_*.py` con cobertura de
adapters, dataset, env, integration, python_exec, rubric, tools,
types, validators.

Docs locales al branch (**no mergear a main tal cual**, revisar):
- `TRAINING_SESSION.md` (127 lineas) — identidad del worktree + plan
- `TODO_TRAINING.md` (72 lineas) — board del training
- `CLAUDE.md` updates (3 lineas)

### Que esta desactualizado en el branch

1. **`scripts/serve_model.sh`** — usa Qwen2.5-0.5B, max-len 4096.
   La version canonica esta en `qwen-benchmarks` (Qwen3-8B, 16384).
2. **`scripts/dry_run.py`** — usa transformers + verifiers.evaluate()
   para inference. No usa `ChatCompletionsClient`. Esto esta BIEN
   para training (verifiers maneja su propia conexion a vLLM), pero
   si queres hacer smoke tests standalone necesitas el nuevo cliente.
3. **`rubric.py`** — puede tener formula de scoring vieja si main
   evoluciono el scoring desde que se creo el branch. VERIFICAR.
4. **Modelo target** — el branch apuntaba a Qwen2.5-0.5B para dev y
   Qwen3-8B para prod. Ahora es Qwen3-8B directo.

**Lo primero que haces en este worktree es recuperar ese branch y
leer TRAINING_SESSION.md + TODO_TRAINING.md + el codigo de
src/sreg/training/. No reinventes la rueda.**

---

## Que NO es este worktree

- **NO es el worktree de BEFOREs externos.** Ese es `qwen-benchmarks`,
  trabajando I-010/011/012/013. Vos dependes de que ellos congelen
  el harness y sirvan Qwen3-8B — COORDINAR, no duplicar.
- **NO es el worktree de AFTER.** Cuando termine el training,
  `qwen-benchmarks` (o su sucesor) corre el AFTER con el checkpoint
  que vos entregas.
- **NO es el worktree de eval suites.** Ese es `eval-suite` (I-006/007/009).
  Podes usar Suite 1 (Core Correctness) si existe como fixture de
  sanity, pero no la construis.
- **NO es el worktree del audit-cleanup.** Si encontras codigo muerto
  en el branch previo, anotalo pero no lo borres aca.
- **NO es el worktree de la extension del grammar.** Si el training
  expone un bug del compiler, abri un issue separado.

---

## Que vas a construir (scope concreto)

### Pieza 0 — Recuperar y triar el trabajo previo

Antes de cualquier codigo nuevo:

1. `git fetch origin` y verificar que `origin/worktree-rl-env-verifiers`
   existe localmente.
2. Decidir con el usuario el **modo de trabajo**:
   - Opcion A: `git checkout -b rl-training-infra origin/worktree-rl-env-verifiers`
     (continuar arriba del branch previo, dentro de este worktree).
   - Opcion B: merge del branch a main primero, despues seguir arriba
     de main.
   - Opcion C: cherry-pick selectivo (si hay commits que no se quieren).
   - Recomendacion inicial: **A** — mantener branch separado hasta que
     el dry run pase y el usuario apruebe merge a main.
3. Leer, en este orden:
   - `TRAINING_SESSION.md` (del branch)
   - `TODO_TRAINING.md` (del branch)
   - `src/sreg/training/env.py` (SregEnv)
   - `src/sreg/training/rubric.py` (Rubric + reward_funcs)
   - `src/sreg/training/tools.py` (python_exec)
   - `src/sreg/training/dataset.py`
   - `scripts/dry_run.py`
4. **Verificar compatibilidad con main actual:**
   - Comparar `rubric.py` con el scoring actual de main (`score.total`).
     Si la formula cambio, actualizar rubric.
   - Verificar que los imports de `src/sreg/training/` siguen funcionando
     contra los modulos de main actual.
   - Correr los 168 tests del branch: `pytest tests/training/ -v`
5. **Incorporar `serve_model.sh` canonico de `qwen-benchmarks`:**
   - El branch tiene una version vieja. Reemplazar con la version
     actualizada (Qwen3-8B, max-len 16384, gpu-mem 0.90).
   - Fuente: `origin/worktree-qwen-benchmarks:scripts/serve_model.sh`
6. Producir `research/notes/rl_training_infra_triage.md`:
   - Que esta hecho y funciona
   - Que esta empezado pero incompleto
   - Que falta completamente
   - Que necesita actualizacion (scoring, imports, serve_model.sh, etc.)
   - Propuesta de orden de piezas

**Deliverable Pieza 0:** doc de triage + decision de modo A/B/C
aprobada por el usuario.

### Pieza 1 — Congelar held-out SREG split (I-014)

Training no puede arrancar sin un split train/test congelado. Sin eso,
cualquier numero "in-domain" es evaluacion sobre datos vistos.

**IMPORTANTE: el split es sobre CASOS GENERADOS, no sobre seeds.**
SREG usa LLM en la generacion, asi que el mismo seed no produce el
mismo caso dos veces. Hay que:

1. **Pre-generar** N casos usando los 12+ seeds canonicos (multiples
   casos por seed si es necesario).
2. **Congelar los JSON** resultantes (SRC + WorldSummary + datasets)
   en `data/training_v1/`.
3. Proponer un split: e.g. 80% train / 20% held-out. Criterio:
   held-out debe cubrir diversidad de tipos de investigacion (causal
   simple, system mapping, heterogeneity, descriptivo, etc — ver
   `research/synthesis/investigation_scenarios_rubric.md`).
4. Fijar parametros frozen para eval:
   - temperatura (0.0 para reproducibilidad)
   - max iterations / budget
   - timeout
5. Hash de los archivos generados (SHA256) para verificar integridad.
6. Documentar en `research/synthesis/held_out_split_v1.md` (canon).
7. Cerrar I-014.

**Deliverable Pieza 1:** doc canon + datos frozen + hashes + I-014 cerrado.

**No avances a Pieza 2 hasta tener Pieza 1 aprobada.**

### Pieza 2 — Adoptar infra de Qwen3-8B (ya resuelta en `qwen-benchmarks`)

La infra de inferencia para Qwen3-8B **ya fue diseñada y testeada**
en el worktree `qwen-benchmarks`. Este worktree la adopta, no la
rediseña:

1. **Verificar con el usuario** el estado de `qwen-benchmarks`:
   - Harness decisions cerrado? (I-013)
   - BEFOREs ejecutados con exito?
   - H100 disponible?
2. **Adoptar `serve_model.sh` canonico** (ya hecho en Pieza 0).
3. **Verificar que `verifiers` framework habla correctamente con
   vLLM** via su ClientConfig. El `dry_run.py` del branch ya tiene
   un path para esto — verificar que funciona con Qwen3-8B y los
   flags actualizados (hermes parser, enable-auto-tool-choice).
4. **Smoke test**: levantar Qwen3-8B (en H100 o via hosted API) y
   correr 1 rollout del `dry_run.py` existente.

**Nota sobre arquitectura de inferencia:**
- **Para benchmarks** (qwen-benchmarks): usa `ChatCompletionsClient`
  + `ToolEnrichedClient` Path B → `run_benchmark.py`
- **Para training** (este worktree): usa `verifiers` framework →
  `ClientConfig` + `SamplingArgs` → `SregEnv.step()` → `dry_run.py`
- **Comparten**: el servidor vLLM (`serve_model.sh`) y los flags de
  tool calling. El modelo se sirve una vez, ambos worktrees lo usan.

**Deliverable Pieza 2:** smoke test verde + `research/notes/rl_infra_setup.md`
con comandos reproducibles.

### Pieza 3 — Dry run SregEnv end-to-end

1. Correr `scripts/dry_run.py` con el setup congelado en Pieza 2.
2. Verificar:
   - SregEnv.reset() retorna estado valido
   - step() avanza, acepta tool calls (observe_variable, python_exec)
   - Reward se computa al final via Rubric
   - Reward numerico coincide con `score.total` que SREG calcula
     cuando corres el mismo caso por `scripts/run_oi.py`
3. Si algo no coincide (esperable dado que main evoluciono desde el
   branch), fijar **en el branch**, no en SREG core. Ejemplo: si
   `Rubric` calcula score con una formula vieja, actualizarla para
   que use la nueva.
4. Agregar al menos 1 test de integracion que verifique que el reward
   del env coincide con el score de `score_inputs.json` para el mismo
   episodio.
5. Verificar los **9 eval types** pendientes (T3.2 del branch).

**Deliverable Pieza 3:** `scripts/dry_run.py` corre verde, reward
matches SREG score, test de consistencia commitado.

### Pieza 4 — Cerrar decision SFT+RL vs RL-from-base (I-015)

Esta es una decision cara y el precedente SandMLE sugiere que RL-from-base
generaliza mejor en transfer. Opciones:

- (a) SFT+RL como v1 (config actual del protocol)
- (b) RL-from-base como v1, SFT+RL como ablacion
- (c) Ambas en paralelo

1. Consultar con Codex y usuario cual corre segun budget.
2. Si budget permite (c): diseñar los dos configs y ejecutarlos en
   serie (no paralelo literal, para no saturar 1 GPU).
3. Si budget limita a (b): ejecutar RL-from-base primero. SFT+RL
   queda como follow-up.
4. La decision se cierra con **evidencia empirica del dry run** +
   estimacion de costo, no solo con argumentos teoricos.
5. Actualizar `research/synthesis/sreg_training_transfer_protocol.md`
   con la decision final (es canon).
6. Cerrar I-015 con el razonamiento.

**Deliverable Pieza 4:** decision documentada + I-015 cerrado + protocol
actualizado.

### Pieza 5 — Dataset de training

Reusar `src/sreg/training/dataset.py` que ya existe en el branch.
Completar si falta:

1. **Dataset de SFT** (si se usa — depende de Pieza 4):
   demostraciones SREG de alta calidad. Fuentes posibles:
   - Runs del modelo reference fuerte sobre los seeds train
     (teacher distillation con gpt-5.4)
   - Trayectorias hand-crafted si fueran necesarias
   - Esto es T2.3 del branch (pendiente)
2. **Dataset de RL**: prompts + conexion al reward function.
   - Prompt: brief de investigacion + WorldSummary
   - Reward: `rubric.reward_funcs` retorna `score.total`
   - Filtrado de dificultad: excluir casos donde el modelo base ya
     saca 0% o 100% (rango 30-70% ideal para exploracion)
3. Verificar formato compatible con `verifiers` (el branch ya
   deberia hacer esto, validar con T2.4).
4. **Freeze del dataset**: los JSON pre-generados de Pieza 1 son la
   fuente. Hash + ruta en `data/training_v1/`.

**Deliverable Pieza 5:** dataset frozen + hash en `research/notes/
training_dataset_v1.md`.

### Pieza 6 — Primer RL run real

Config conservadora, informada por research doc y SandMLE:

- **Modelo**: Qwen3-8B
- **Algoritmo**: GRPO (via `verifiers` / prime-rl)
- **LoRA**: rank-16 o rank-32 en H100 80GB. **No necesita QLoRA** —
  Qwen3-8B es ~16GB en bf16, con LoRA rank-32 + optimizer + activaciones
  cabe holgadamente en 80GB. QLoRA solo si el batch size deseado
  requiere mas VRAM.
- **G** = 8 generaciones por prompt (precedente SandMLE)
- **KL coefficient** > 0.001
- **Reward**: `score.total` terminal + **penalizacion por turno**
  (-0.05 por step, anti echo-trap)
- **Checkpointing**: cada N steps, guardar en ruta versionada
- **Logging**: loss, reward medio, reward varianza, longitud promedio
  de trayectoria, timeouts, errores de tool

**Antes de correr el run completo**:
1. **Calcular costo estimado** — a ~$6.98/h, un run de 1K steps de
   ~X horas = ~$Y. Estimar y confirmar con usuario.
2. Correr **50 steps como smoke** (verificar que no explota) antes de
   escalar a 1K+.
3. Monitorear **Echo Trap**: si la varianza del reward colapsa en los
   primeros 100 steps, parar y reajustar (probablemente KL muy bajo
   o reward shaping insuficiente). RAGEN documento que multi-turn RL
   colapsa en templates repetitivos sin reward por turno.
4. Monitorear **submit rate**: si el modelo deja de usar `submit` tool,
   el training esta divergiendo. Esto fue un problema con Qwen 0.5B
   en el branch previo.

**Deliverable Pieza 6:** checkpoint entrenado + logs + reporte de
training en `research/notes/rl_run_v1_results.md`.

### Pieza 7 — Handoff a `qwen-benchmarks`

1. El checkpoint debe ser consumible por el harness de benchmarks.
   Acordar con `qwen-benchmarks` como cargarlo:
   - **Formato**: LoRA adapter (safetensors) — vLLM puede servir
     Qwen3-8B + LoRA adapter directamente con `--lora-modules`.
   - **Alternativa**: merge LoRA → full weights → servir como modelo
     independiente.
2. Documentar contrato del checkpoint:
   - Ruta del checkpoint
   - Formato (LoRA adapter vs full weights)
   - Config de inferencia (temperatura, max_tokens, stop tokens)
   - Hash SHA256 del checkpoint
   - Comando exacto de `serve_model.sh` para servirlo
3. Pasar el checkpoint al worktree `qwen-benchmarks` para que corra
   AFTER sobre los mismos 4-5 benchmarks con el mismo harness.
4. **NO corras vos el AFTER.** No es tu scope.

**Deliverable Pieza 7:** checkpoint + contrato documentado + handoff
explicito al usuario para ejecutarlo en `qwen-benchmarks`.

### Pieza 8 — Docs + cierre

1. Merge del branch a main (si no se hizo antes).
2. Actualizar CURRENT_STATE.md, ARCHITECTURE.md, CHANGELOG.md.
3. Actualizar `research/README.md` con los docs nuevos.
4. Mover I-010, I-014, I-015 a estado correcto en TODO.md.
5. Cerrar el worktree.

---

## Principios no negociables

1. **No reinventes lo del branch previo.** Tiene 4000 lineas y 168 tests.
   Si algo esta roto, arreglalo; si falta, agregalo; pero el codigo
   `src/sreg/training/` es tu punto de partida.

2. **Protocolo canonico es `sreg_training_transfer_protocol.md`.**
   Cualquier cambio al protocolo (framework, modelo, benchmarks,
   reward) es una **decision** que requiere consulta con el usuario
   + Codex, y actualizacion del doc canon.

3. **Mismo servidor vLLM que `qwen-benchmarks`.** Si ellos congelaron
   `serve_model.sh`, vos usas eso. Si necesitas cambiar algo, para,
   coordina, y actualizan ambos. El servidor se comparte, los clientes
   son diferentes (verifiers vs ChatCompletionsClient).

4. **Costos visibles antes de cada run.** Un RL run de 1K steps
   puede costar $30-$200+ en H100. Antes de apretar enter, estima
   y confirma.

5. **No mockees training.** Los tests del branch ya mockean lo que
   corresponde. Los **runs oficiales** son con GPU real y Qwen3-8B
   real.

6. **Echo Trap awareness.** RAGEN documento que multi-turn RL
   colapsa en templates repetitivos sin reward por turno. Reward
   shaping minimo: reward final dominante + penalizacion por step.
   Si ves colapso de varianza, parar.

7. **No toques SREG core** salvo que training exponga un bug real.
   Si el rubric calcula score distinto a `score.total` oficial,
   **arregla el rubric**, no el scoring. El scoring de main es
   canon v1.

8. **No saltes piezas.** Sin held-out split no hay eval. Sin dry run
   verde no hay training. Sin decision I-015 no hay config. Respeta
   el orden.

---

## Metodo por fases

- **Fase 0 (Pieza 0):** recuperar branch + triage + decision modo A/B/C.
- **Fase 1 (Pieza 1):** held-out split frozen.
- **Fase 2 (Pieza 2):** adoptar infra Qwen de qwen-benchmarks + smoke.
- **Fase 3 (Pieza 3):** dry run SregEnv verde.
- **Fase 4 (Pieza 4):** decision SFT+RL vs RL-from-base cerrada.
- **Fase 5 (Pieza 5):** dataset training frozen.
- **Fase 6 (Pieza 6):** primer RL run real.
- **Fase 7 (Pieza 7):** handoff a qwen-benchmarks.
- **Fase 8 (Pieza 8):** docs + cierre.

Cada fase tiene **gate explicito con el usuario**. No saltes a la
siguiente sin OK.

---

## Workflow

- **Modo colaborativo.** Paso a paso. No corras 3 piezas seguidas.
- **Español.**
- **Commits por pieza.** Un commit por pieza cerrada, minimo. Piezas
  grandes (Pieza 3, 5, 6) pueden tener varios commits internos.
- **Antes de cada commit:** CLAUDE.md seccion "Antes de cada commit —
  QUE ACTUALIZAR". Actualiza I-010/I-014/I-015 segun aplique.
- **Validacion E2E es un RL run real**, no unit tests. Los tests
  existentes del branch son piso, no techo.
- **Coordinacion con `qwen-benchmarks`:** deja notas explicitas en
  `research/notes/rl_training_infra_triage.md` cada vez que tomes
  una decision que afecta el otro worktree.

---

## Codex como segunda opinion — IMPORTANTE

Este worktree tiene decisiones caras (framework RL, config de training,
reward shaping, costo de runs) y codigo multi-turn que es frontera de
investigacion. Codex como segunda opinion es obligatorio.

1. **Al arrancar este worktree**, abri una sesion nueva con Codex via
   `mcp__codex__codex`. Pedile que actue como segunda opinion tecnica
   sobre RL training infra de SREG. Dale el contexto: worktree
   `rl-training-infra`, trabajando sobre I-014/I-015 y continuando
   `origin/worktree-rl-env-verifiers`, el canon es
   `research/synthesis/sreg_training_transfer_protocol.md`, y el
   research background esta en `research/archive/RL_frameworks_research_claude.md`.

2. **Guarda el `threadId`** en `_codex_thread.md` en el root del
   worktree:
   ```
   thread_id: <id>
   opened: 2026-04-13
   purpose: rl-training-infra worktree — continue worktree-rl-env-verifiers, I-014/I-015
   ```

3. **Agrega `_codex_thread.md` a `.git/info/exclude`** del worktree.
   Local, no mergea.

4. **Durante el worktree, usa `mcp__codex__codex-reply`** con ese
   `threadId`. Reusa el hilo, no abras sesiones nuevas.

5. **Cuando consultar a Codex (obligatorio):**
   - Antes de cerrar Pieza 0 (modo A/B/C de recuperacion del branch).
   - Antes de cerrar Pieza 1 (held-out split — criterio de diversidad).
   - Antes de escribir o actualizar Rubric reward function (Pieza 3).
   - Antes de cerrar Pieza 4 (decision SFT+RL vs RL-from-base).
   - Antes del primer RL run real (Pieza 6) — review de config GRPO,
     KL coefficient, reward shaping, anti echo-trap.
   - Si ves señales de Echo Trap durante el run.
   - Antes del handoff a `qwen-benchmarks` (Pieza 7) — contrato del
     checkpoint.
   - Cualquier momento en que dudes de si un cambio al entorno rompe
     la reproducibilidad.

6. **Claude lidera, Codex asesora.** Forma tu propia opinion PRIMERO,
   mostrasela al usuario, despues consultas a Codex. No adoptes
   propuestas de Codex que contradigan el protocol canonico sin
   debatirlas con el usuario.

7. **Cuando termine el worktree**, `_codex_thread.md` se queda local.

---

## Referencias obligatorias

### Documentos canon
- `research/synthesis/sreg_training_transfer_protocol.md` — protocol de training
- `research/synthesis/thesis_evaluation_framework.md` — marco tesis
- `research/synthesis/related_work_sandmle.md` — precedente Qwen3-8B + SFT+RL
- `research/synthesis/investigation_scenarios_rubric.md` — diversidad para held-out
- `research/synthesis/held_out_split_v1.md` — (se crea en Pieza 1)

### Research background
- `research/archive/RL_frameworks_research_claude.md` — research framework
- `research/archive/agent_harness_research_gpt.md` — research harness

### Issues
- `issues/I-010-qwen-before-benchmarks.md` — BEFORE (otro worktree)
- `issues/I-014-held-out-sreg-split.md` — Pieza 1
- `issues/I-015-sft-rl-decision.md` — Pieza 4

### Branch previo (`origin/worktree-rl-env-verifiers`)
- `TRAINING_SESSION.md` — identidad + plan (Phase T1-T5)
- `TODO_TRAINING.md` — board training con estado por task
- `src/sreg/training/env.py` — SregEnv (StatefulToolEnv)
- `src/sreg/training/rubric.py` — Rubric con reward_funcs
- `src/sreg/training/tools.py` — python_exec + think
- `src/sreg/training/dataset.py` — dataset loader HF-compatible
- `scripts/dry_run.py` — dual-backend dry run (transformers + verifiers.evaluate)
- `scripts/serve_model.sh` — vLLM serve (VERSION VIEJA, reemplazar con canonica)

### Infra (skills y configs)
- `C:/Users/YT40432/.claude/skills/azure-ml-connect/SKILL.md` — H100 conexion
- `C:/Users/YT40432/Desktop/lp/research/lucaspecina/grubrics-science/.claude/skills/h100-workflow/SKILL.md` — H100 workflow detallado
- `~/.ssh/aml-ci-lucas.pem` — clave SSH para H100
- `~/.ssh/config` — alias `azure-ml` configurado

### Worktree hermano
- `qwen-benchmarks` (branch `worktree-qwen-benchmarks`):
  - `src/sreg/inference/chat_client.py` — ChatCompletionsClient
  - `src/sreg/inference/tool_client.py` — ToolEnrichedClient dual-backend
  - `src/sreg/inference/protocol.py` — Message.tool_calls field
  - `scripts/serve_model.sh` — VERSION CANONICA
  - `scripts/run_benchmark.py` — harness con --backend flag
- `CLAUDE.md` — workflow + commit rules

---

## Primer mensaje al usuario

Arranca la sesion diciendo, en español:

> "Estoy en el worktree rl-training-infra. Voy a continuar el trabajo
> del branch origin/worktree-rl-env-verifiers (SregEnv, Rubric,
> python_exec, dataset, dry_run — ~4000 lineas, 168 tests) y llevarlo
> hasta el primer RL run real sobre Qwen3-8B con SREG como fuente de
> reward. El AFTER NO lo corro yo, se lo paso a qwen-benchmarks.
>
> Antes de escribir nada necesito:
> (1) git fetch del branch y leer TRAINING_SESSION.md + TODO_TRAINING.md
>     + el codigo de src/sreg/training/;
> (2) clarificar con vos — seguimos arriba del branch (modo A), merge a
>     main primero (modo B), o cherry-pick (C)?;
> (3) verificar compatibilidad: el scoring de main puede haber cambiado
>     desde que se creo el branch — rubric.py necesita validacion;
> (4) adoptar el serve_model.sh canonico de qwen-benchmarks (Qwen3-8B,
>     16384 max-len, hermes parser);
> (5) estado de la H100 — esta disponible o seguimos con hosted API
>     para smoke tests?;
> (6) presupuesto de GPU para runs.
>
> Voy a dejar el triage en research/notes/rl_training_infra_triage.md
> y abrir sesion de Codex como segunda opinion. Arranco por Fase 0?"

Y espera la respuesta.

---

## Notas fuera del prompt

1. El bootstrap asume que Pieza 6 es UN run (no dos en paralelo). Si
   queres que el worktree corra SFT+RL y RL-from-base como dos runs
   comparables (opcion (c) de I-015), decime y expando Pieza 6 a dos
   sub-piezas — multiplica costo por ~2 pero te da evidencia directa
   para la decision del protocol.

2. El prompt no fija si el split held-out requiere generar seeds nuevos
   o usa los existentes. Hoy hay 12+ seeds canonicos — hay que
   **pre-generar** casos concretos a partir de ellos y congelar los
   JSON (no los seeds). Si queres un N especifico de casos, decime.

3. El branch usa `verifiers` (PrimeIntellect-ai) como framework RL.
   Su API es inestable y esta pinneada. Si `verifiers` cambio
   significativamente desde que se creo el branch, puede requerir
   actualizacion. Pieza 0 triage debe verificar esto.

4. Si la H100 sigue sin provisionar, las Piezas 0-4 se pueden avanzar
   con hosted API (Together AI / Fireworks) para smoke tests. Solo
   Pieza 6+ requiere GPU dedicada.
