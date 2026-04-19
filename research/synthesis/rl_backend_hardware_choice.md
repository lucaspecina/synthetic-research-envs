# RL Backend + Hardware Choice

> **Status:** CANONICO operativo (training infra).
> **Fecha:** 2026-04-18.
> **Por que existe:** en 2026-04-18, intentando un smoke del loop RL en
> una T4 VM single-GPU, chocamos con un error `NCCL invalid usage` al
> hacer `init_communicator`. Despues de verificar en el repo de
> `verifiers`, el mantenedor (willccbb) confirma explicitamente que
> `verifiers-rl` **no soporta single-GPU y no lo va a soportar**. Este
> doc registra la lesson learned, el mapa del ecosistema y la decision
> de hardware para tesis.
>
> **Sirve para:** decidir backend de training + hardware target antes
> de pedir VM / gastar cluster credits.

## Ecosistema Prime Intellect (para no confundirse)

Prime Intellect mantiene VARIAS piezas que comparten naming y se
confunden facil. Este es el mapa:

| Pieza | Repo / PyPI | Que es | Que NO es |
|---|---|---|---|
| **`verifiers`** | [PrimeIntellect-ai/verifiers](https://github.com/PrimeIntellect-ai/verifiers) — `pip: verifiers` | **Env library.** Define `vf.Environment`, `vf.MultiTurnEnv`, rubrics, rollout engine. | No es el trainer. |
| **`verifiers-rl`** | mismo repo, `packages/verifiers-rl/` — `pip: verifiers-rl` | **Trainer "nano" + `vf-vllm` server.** Provee `vf.RLTrainer` (antes `GRPOTrainer`), cliente NCCL, binario `vf-vllm` (wrapper de vLLM con endpoints RL). accelerate/deepspeed-based. | No soporta single-GPU (ver mas abajo). |
| **`prime-rl`** | [PrimeIntellect-ai/prime-rl](https://github.com/PrimeIntellect-ai/prime-rl) — repo separado | **Trainer production.** FSDP2-first, async off-policy, escala 1->2048+ GPUs, weight sync por DISCO (no NCCL), soporta single-GPU desde PR #971. | No soporta LoRA (todavia). |
| **Environments Hub** | docs.primeintellect.ai | **Registry** de envs versionadas instalables como modulos. | No es un trainer. |
| **ART** (OpenPipe) | [OpenPipe/ART](https://github.com/OpenPipe/ART) | Trainer single-GPU agent. Alternativa no-PrimeIntellect. | Otro ecosistema. |

## Por que RL de LLMs pide (casi) siempre >= 2 GPUs

El patron estandar en RL de LLMs separa **rollout** (generacion) de
**training** (forward + backward + optim). No es una decision de
framework — es una consecuencia de las asimetrias:

### 1. Memoria: los dos componentes pelean por VRAM

| Componente | Que necesita en VRAM |
|---|---|
| vLLM (rollout) | Pesos del modelo (fp16/bf16) + KV cache de todas las secuencias en vuelo. El KV cache crece lineal con `max_concurrent * max_seq_len`. |
| Trainer (forward+backward) | Pesos + gradientes (1x params) + optimizer state (Adam = 2x params por momentum/varianza) + activaciones guardadas para backward. |

Con LoRA se alivia un poco (grad y optim solo para los LoRA params, no
para los congelados), pero las activaciones siguen ocupando mucho.
**En una sola GPU los dos se pisan** — no hay memoria para tener a
los dos calientes a la vez.

### 2. vLLM y el trainer viven en procesos separados

vLLM usa kernels CUDA custom (PagedAttention, continuous batching) y
espera los pesos en un layout propio. El trainer usa `transformers` +
accelerate, con otro layout. Son dos contextos CUDA distintos en el
mismo proceso o en procesos separados — en la practica lo mas robusto
es procesos separados.

### 3. Despues de cada step de training hay que propagar los pesos nuevos a vLLM

Hay dos mecanismos:

| Mecanismo | Como funciona | Pro | Contra |
|---|---|---|---|
| **NCCL in-memory** (lo que usa `verifiers-rl`) | El trainer y vLLM son dos ranks NCCL. Despues de cada step, `broadcast` GPU->GPU de los LoRA deltas. | Rapido, bajo overhead. | **Requiere `world_size >= 2`** — dos GPUs distintas, una por rank. |
| **Disk swap** (lo que usa `prime-rl` y recomienda willccbb) | El trainer guarda los pesos nuevos a disco, vLLM los recarga entre rollouts. | Funciona en single-GPU (alternan en tiempo). | Mas lento (I/O) salvo con LoRAs, y hay que hacerlo en 2 steps async para esconder la latencia. |

**El error NCCL del 2026-04-18** es exactamente (3) con mecanismo
NCCL y `world_size=1` — el cliente del trainer y el server vLLM
piensan que son 2 ranks pero corren en la misma GPU fisica.

### 4. Historicamente, RLHF clasico pedia 4 GPUs

PPO-RLHF = actor + critic + ref model + reward model. 4 modelos, 4
GPUs minimas. **GRPO** (lo que usa SREG) elimina el critic (usa group
relative advantage) y para SREG el reward es externo (Azure scorer),
asi que nos queda:

- **actor (training)** — GPU A
- **rollout inference** — GPU B

Esto es el minimo. Si tuvieramos reward local (LLM-judge on-device)
serian 3 GPUs.

## Evidencia: que dice el mantenedor de verifiers

[Issue #104 "Possible to train on a single GPU?"](https://github.com/PrimeIntellect-ai/verifiers/issues/104) — willccbb (maintainer):

> "Yeah, sorry, **no single-GPU support at the moment + not planned
> for the current trainer**. ART is your best bet for single-GPU agent
> training."

Otro usuario en el mismo issue (EndlessReform) despues de perder 2-3
horas:

> "I wasted 2-3 hours trying to get NCCL to allow the weight transfer
> from vLLM server to client, before figuring out that **there's no
> way the connection can work without world size >=2**."

[Issue #139 "Single-GPU vllm server crash due to NCCL"](https://github.com/PrimeIntellect-ai/verifiers/issues/139) — willccbb:

> "the main way to avoid this entirely is forgoing NCCL and just
> swapping weights via disk. this is super cheap to do with LoRAs...
> support for verifiers environments is now added to prime-rl, which
> takes this approach."

**Conclusion cerrada:** si queremos mantener `verifiers-rl` como
trainer, necesitamos **>= 2 GPUs fisicas, siempre**. No hay workaround.

## Decision de tesis (2026-04-18)

| Opcion | Hardware | Backend | Viable? | Comentario |
|---|---|---|---|---|
| A | 1x T4 16GB | verifiers-rl + LoRA | No | NCCL bloquea |
| B | 1x T4 16GB | prime-rl (sin LoRA) | No | Qwen3-8B no entra sin LoRA |
| C | 1x H100 80GB | verifiers-rl + LoRA | No | NCCL bloquea |
| D | 1x H100 80GB | prime-rl (sin LoRA) | Tight | 8B full-finetune en 80GB, sin margen para activaciones |
| **E** | **2x H100 80GB** | **verifiers-rl + LoRA** | **Si** | **El path natural** |
| F | 1x H100 80GB | ART | Pendiente evaluar | No es stack PrimeIntellect |

**Decision:** opcion **E** — **2x H100 80GB**, `verifiers + verifiers-rl`
con LoRA. Es el path que minimiza cambios en el harness, mantiene LoRA
(que ya esta en el YAML y en el codigo) y no obliga a migrar a
`prime-rl` sin razon clara.

El transfer protocol (`sreg_training_transfer_protocol.md`) menciona
`verifiers + prime-rl` pero ese texto es previo a esta investigacion.
Se mantiene `verifiers + verifiers-rl` como stack v1 hasta que haya
razon tecnica para migrar (ver "Cuando reabrir esta decision").

## Cuando reabrir esta decision

Migrar a `prime-rl` tiene sentido si:

1. **Necesitamos full-finetune**, no LoRA. `prime-rl` todavia no
   soporta LoRA, pero la pregunta inversa (LoRA para tesis) ya es
   una decision cerrada — LoRA es v1.
2. **Necesitamos escala >= 8 GPUs.** `verifiers-rl` escala mal mas
   alla de 1 node; `prime-rl` esta hecho para clusters.
3. **El weight sync NCCL se vuelve el bottleneck.** Si eso pasa,
   disk-swap puede ser igual o mas rapido en la practica para LoRAs.
4. **willccbb deprecia `verifiers-rl`.** Hoy dice "switch to prime-rl"
   como recomendacion, no como deprecation. Ojo con eso.

## Lesson learned (proceso)

- **NO dar "imposible" como conclusion sin verificar.** El 2026-04-18
  concluimos "single-GPU impossible" antes de buscar en el repo. La
  verificacion (gh issue search) tomo 5 minutos y daba evidencia
  canonica. Costo de verificar << costo de frenar al usuario con una
  conclusion premature.
- **Antes de pedir hardware, mapear el stack.** El orden correcto es:
  (1) que framework, (2) que hardware requiere ese framework, (3)
  pedir hardware. Nosotros invertimos (1) y (2).
- **`verifiers` vs `verifiers-rl` vs `prime-rl` son TRES cosas.**
  No son sinonimos. Este doc existe para evitar la confusion otra vez.

## Referencias

- [verifiers Issue #104: Possible to train on a single GPU?](https://github.com/PrimeIntellect-ai/verifiers/issues/104)
- [verifiers Issue #139: Single-GPU vllm server crash due to NCCL](https://github.com/PrimeIntellect-ai/verifiers/issues/139)
- [verifiers Issue #339: NCCL error when launching training with vLLM](https://github.com/PrimeIntellect-ai/verifiers/issues/339) (open)
- [prime-rl PR #971: Allow RL on single GPU from `rl` entrypoint](https://github.com/PrimeIntellect-ai/prime-rl/pull/971)
- [HF blog: co-located vLLM in TRL](https://huggingface.co/blog/vllm-colocate) — describe el patron colocate que TRL ofrece y `verifiers-rl` no.
- vLLM RFC [#11399](https://github.com/vllm-project/vllm/issues/11399) — weight sync design space.
