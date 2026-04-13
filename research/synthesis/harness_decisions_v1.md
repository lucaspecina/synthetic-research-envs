# Harness Decisions v1 — BEFORE Oficiales de Tesis

> **Status:** BORRADOR — requiere aprobacion del usuario antes de congelar.
> **Fecha:** 2026-04-12
> **Aplica a:** todos los BEFORE runs del worktree `qwen-benchmarks`
> **Referencia:** `research/synthesis/sreg_training_transfer_protocol.md`

## Principio rector

**El harness de evaluacion debe ser identico al harness de training.**

BEFORE, TRAIN y AFTER usan el mismo scaffold. Los valores se toman
directamente del solver SREG real (`oi_driver.py:324-332`):

| Parametro | Valor solver SREG | Fuente |
|---|---|---|
| Tools | python_exec + think (+ submit_claims en SREG) | `oi_driver.py:45-177` |
| python_exec sandbox | numpy, pandas, scipy, statsmodels, sklearn, etc. | `python_exec.py:22-26` |
| Max iterations | **20** | `oi_driver.py:329` |
| Temperature | **0.0** | `oi_driver.py:330` |
| Max tokens | None (sin limite) | `oi_driver.py:331` |
| API | Responses API con `previous_response_id` chaining | `oi_driver.py:374-399` |
| MAX_CODE_CHARS | 4000 | `python_exec.py:29` |
| MAX_OUTPUT_CHARS | 8000 | `python_exec.py:28` |

Para benchmarks, `submit_claims` se reemplaza por el formato de respuesta
de cada benchmark (yes/no para CLadder, "Final answer:" para QRData, etc.).
Los helpers SREG-specific (`load_artifact`, `save_artifact`, `oi.corr`, etc.)
no aplican — los benchmarks tienen sus propios datos inyectados en el prompt.

El unico cambio entre BEFORE y AFTER son los pesos del modelo.

---

## Decisiones comunes a TODOS los benchmarks

### D-00: Tools siempre activas

**Decision:** `--with-tools` obligatorio en todos los runs oficiales.
**Razon:** el modelo tendra python_exec + think durante training (verifiers
MultiTurnEnv). Si el BEFORE no tiene tools, el delta BEFORE→AFTER mezcla
mejora del modelo con cambio de harness. No interpretable.
**Implicacion:** los scores seran distintos a los de marzo (que fueron
text-only para QRData). No son comparables. Los de marzo quedan como
referencia historica, no como baseline.

### D-01: Temperature

**Decision:** `temperature=0.0` (determinista) para todos los benchmarks.
**Excepcion:** si un modelo no soporta `temperature=0.0` (como gpt-5.2-chat
en marzo), el client ya hace fallback automatico (lineas 108-114 de
`openai_client.py`). En ese caso, documentar la excepcion en el reporte.
**Razon:** determinismo maximiza reproducibilidad. Un run con temp=0
y seed fijo produce exactamente los mismos resultados.

### D-02: Seeds

**Decision:** seed principal = **42**. No se corren seeds adicionales
para benchmarks deterministas (CLadder, QRData, CRB).
**Excepcion:** DiscoveryBench (HMS es LLM-judge no-determinista) requiere
**3 seeds** (42, 0, 7) con voting por mayoria. Ver D-DB abajo.
**Razon:** para benchmarks deterministas, un run con temp=0 y seed=42
es perfectamente reproducible. Correr 3 seeds multiplica costo sin ganancia
de informacion. Para DiscoveryBench, la varianza del judge necesita mitigacion.

### D-03: Modelos

**Decision:**
- **Reference:** `gpt-5.4` (AZURE_MODEL actual). Techo cualitativo + comparacion con literatura.
- **Target:** `Qwen3-8B` via vLLM en H100 Azure ML. Este es el modelo que se entrena con RL.

Ambos se evaluan con el mismo harness exacto.

### D-04: Max iterations (tool loop)

**Decision:** `max_iterations=20` para todos los benchmarks.
**Razon:** el solver SREG usa 20 (`oi_driver.py:329`). `ToolEnrichedClient`
usa 8 por default — MUY distinto. `engine.solve_question()` usa 10 — tambien
distinto. Los benchmarks deben usar 20 para replicar el mismo budget de
interaccion que tendra el modelo durante training.
**Implicacion:** pasar `max_iterations=20` explicitamente desde
`run_benchmark.py`. NO depender de defaults de `ToolEnrichedClient`.

### D-05: Output directory

**Decision:** todos los runs oficiales van a
`experiments/benchmarks/before_v1/<benchmark>_<model>_<timestamp>/`.
**Razon:** separar claramente de los runs historicos de marzo.

---

## CLadder

### D-CL-01: Subset

**Decision:** `dev` (100 ejemplos, 10 por query_type, seed=42).
**Razon:** `all` son 10,112 ejemplos — viable con Qwen local en H100, pero
excesivo para gpt-5.4 (costo y tiempo). dev es el subset estandar usado en
el paper original para ablations.
**Alternativa descartada:** correr `all` solo con Qwen. Pero entonces el
BEFORE de Qwen y el de gpt-5.4 no serian comparables (distinto N).
Mantener dev para ambos.

### D-CL-02: Prompt

**Decision:** mantener prompt v1-zero-shot actual del adapter. System prompt
del paper original + "Start your answer with Yes or No".
**Razon:** alineado con la condicion reportada en la literatura para GPT-4.
No cambiar para mantener comparabilidad.

### D-CL-03: Tools

**Decision:** tools activas (`--with-tools`), pero CLadder es yes/no puro
sin datos tabulares. El modelo probablemente no use python_exec. Tenerlas
disponibles es inocuo y mantiene harness identico.

### D-CL-04: Scoring

**Decision:** exact match (yes/no), determinista. Sin cambios.

---

## QRData

### D-QR-01: Subset

**Decision:** `dev` (50 ejemplos, seed=42).
**Razon:** `all` son 411 ejemplos. Con tools activas, cada ejemplo puede
hacer multiples tool calls — costoso con gpt-5.4. dev es suficiente para
BEFORE y es lo que usamos en marzo (permite comparacion historica).
**Para Qwen:** tambien dev. Mismo N, comparabilidad directa.

### D-QR-02: Tools

**Decision:** `--with-tools` **obligatorio**. Es el cambio mas importante
vs marzo.
**Razon:** (1) el paper canonico usa code interpreter, (2) el harness de
training tendra python_exec, (3) sin tools las preguntas numericas son
practicamente imposibles (17.6% en marzo). Con tools, esperamos mejora
significativa.
**Implicacion:** los scores de QRData con tools NO son comparables con
los de marzo (text-only). Son dos condiciones distintas. El reporte
final debe documentar esto.

### D-QR-03: Data in prompt vs tools

**Decision:** mantener el CSV truncado en el prompt (actual) + tools
disponibles. El modelo puede (a) razonar sobre el texto, (b) usar
python_exec para analisis mas preciso, o (c) ambos.
**Razon:** esto replica lo que haria un investigador real: ve los datos
y puede correr codigo. No forzar un camino.

### D-QR-04: Tolerancia numerica

**Decision:** 3% relativa. Sin cambios. Alineado con eval.py oficial.

---

## DiscoveryBench

### D-DB-01: Subset

**Decision:** `all` (25 ejemplos, train split completo).
**Razon:** el train split solo tiene 25 ejemplos — es tan chico que no
tiene sentido subsamplear. El test split no tiene gold hypotheses.

### D-DB-02: Judge model (CRITICA)

**Decision:** el judge HMS usa **gpt-5.4** (AZURE_MODEL) para TODAS las
corridas, incluso cuando el generador es Qwen3-8B.
**Razon:** oracle separation. Si el generador y el judge son el mismo
modelo, hay sesgo de auto-validacion. Un judge fijo y fuerte es el
estandar en la literatura (DiscoveryBench paper usa GPT-4o como judge).
**Implicacion:** hay que modificar `run_discoverybench()` en
`run_benchmark.py` para aceptar un `--judge-model` separado.
Actualmente `adapter.score()` usa el mismo client que `adapter.run()`.

### D-DB-03: Seeds y voting

**Decision:** **3 seeds** (42, 0, 7). Cada ejemplo se genera 3 veces
(hipotesis). Se toma la **mediana** de los 3 HMS scores por ejemplo.
El reporte incluye mean + std entre seeds.
**Razon:** HMS es no-determinista (LLM judge). Un solo run tiene varianza
inaceptable. 3 seeds es el minimo para estimar varianza sin triplicar
costo de manera absurda.
**Alternativa descartada:** 5 seeds con voting — overkill para 25 ej.

### D-DB-04: Prompt del judge

**Decision:** prompts actuales de `hms.py` (DECOMPOSE_PROMPT,
CONTEXT_MATCH_PROMPT, VARIABLE_OVERLAP_PROMPT, RELATIONSHIP_PROMPT).
Congelados en esta version. Cualquier cambio invalida el BEFORE.
**Version tag:** v1-hms-2026-04-12.

### D-DB-05: Tools

**Decision:** `--with-tools` activas. El modelo puede usar python_exec
para analizar las columnas del dataset antes de formular su hipotesis.
Esto es mas realista que zero-shot puro.

---

## CausalReasoningBenchmark (CRB)

### D-CRB-01: Dataset

**Decision:** dataset completo de HuggingFace (173 queries, 138 datasets).
**Razon:** no es tan grande. Scoring es determinista. Correr todo.

### D-CRB-02: Metricas

**Decision:** (del protocolo canon)
- Accuracy de identificacion: strategy, treatment, outcome, controls
- Accuracy de spec completa (full identification)
- Accuracy de estimacion (point estimate + SE)

### D-CRB-03: Scoring

**Decision:** determinista contra gold del dataset publicado.
No necesita LLM judge.

### D-CRB-04: Tools

**Decision:** `--with-tools`. CRB incluye datasets reales — el modelo
puede necesitar python_exec para calcular estimaciones.

---

## SciGym

### D-SG-01: Infra

**Decision:** corre en la H100 de Azure ML (Linux + Docker disponible).
SciGym requiere Docker + SBML stack, que no esta disponible en Windows
local pero SI en la VM de Azure ML donde corre Qwen3-8B.
**Setup:** Docker compose del repo h4duan/SciGym + vLLM en la misma
maquina. El adapter conecta al modelo via API local.

### D-SG-02: Metricas

**Decision:** (del protocolo canon)
- Graph edit distance vs ground-truth (final)
- Graph edit distance vs n_iterations (curva)
- Recovery rate

### D-SG-03: Tools

**Decision:** `--with-tools`. SciGym es iterativo (proponer experimento,
observar, actualizar). El modelo necesita python_exec para analizar
series temporales y resultados de simulacion.

### D-SG-04: Subset

**Decision:** por definir una vez el adapter exista. El dataset tiene
350 sistemas SBML. Definir un subset representativo en la implementacion.

---

## Cambios de codigo requeridos

Antes de correr el primer run oficial, hay que hacer estos cambios:

1. **`run_benchmark.py`:** pasar `max_iterations=20` explicitamente al
   `ToolEnrichedClient` (hoy usa default=8, solver usa 20).

2. **`run_benchmark.py`:** agregar `--judge-model` flag para DiscoveryBench.
   Default: AZURE_MODEL (gpt-5.4). Se usa para HMS scoring, separado del
   modelo generador. Requiere crear un segundo client en `run_discoverybench()`.

3. **`run_benchmark.py`:** output dir cambia a
   `experiments/benchmarks/before_v1/` en vez de `experiments/benchmarks/`.

4. **DiscoveryBench adapter:** multi-seed support. Correr 3 seeds por
   ejemplo y agregar mediana + varianza al reporte.

5. **`run_benchmark.py`:** agregar `--benchmark crb` (Pieza 4) y
   `--benchmark scigym` (Pieza 5).

6. **SciGym adapter:** implementar desde cero. Setup Docker en H100.

---

## Hash de este documento

Este archivo se congela una vez aprobado. Cualquier cambio post-aprobacion
invalida todos los runs previos y obliga a re-correr desde cero.

Fecha de congelacion: PENDIENTE (requiere aprobacion del usuario).
