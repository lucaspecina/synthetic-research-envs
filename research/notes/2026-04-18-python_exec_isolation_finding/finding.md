# python_exec.py es incompatible con rollouts paralelos — diagnostico + plan

**Fecha:** 2026-04-18
**Contexto:** smoke RL en Azure H100 x2 (Issue #38, smoke run de Issue #24).
**Status:** diagnostico cerrado. Workaround aplicado (`max_concurrent: 1`).
Refactor a subprocess pendiente (este doc + Issue nueva).

## TL;DR

`src/sreg/agent/python_exec.py` ejecuta el codigo del solver con `exec()`
en el **mismo proceso** del trainer. `verifiers + verifiers-rl` paraleliza
los rollouts de un grupo GRPO con `concurrent.futures.ThreadPoolExecutor`,
o sea **N hilos en el mismo interprete** llamando `exec()` con codigos
distintos sobre namespaces distintos.

El problema: pandas (y otras libs cientificas con backend C/Cython)
**no son thread-safe**. Cuando dos hilos invocan simultaneamente
`DataFrame.__repr__()` (lo que pasa cuando el solver hace `print(df.head())`),
el codigo C de pandas tiene races en `IndexEngine` y revienta con SIGSEGV.

Resultado en nuestro smoke: el trainer crashea en step 0 con
`Segmentation fault (core dumped)` reproducible al 100% con
`max_concurrent: 8` y dataframes en el namespace.

**Workaround actual:** `configs/smoke_rl.yaml: max_concurrent: 1` —
serializa rollouts. Se completa step 0 con varianza no-cero
(rewards `-0.0598 / -0.0799`), pero pierde todo el throughput
que justifica usar vLLM continuous batching.

**Solucion definitiva:** mover el `exec()` a subprocess con namespace
serializado in/out. Es lo que hacen NeMo RL (worker isolation) y los
sandboxes de verifiers (`PythonEnv` / `SandboxEnv`). Costo: ~50-200ms
overhead por exec, que se amortiza completo con `max_concurrent>=2`.

## Diagnostico

### Paso 1 — sintoma

Smoke run en H100 (`scripts/train_sreg.py --config configs/smoke_rl.yaml --train`)
moria con `Segmentation fault (core dumped)` antes de completar step 0.
faulthandler dump apuntaba al stack del trainer en mitad de un rollout,
con `Current thread 0x...` cambiando entre runs.

### Paso 2 — captura del codigo del solver

Para saber **que** codigo del solver disparaba el crash, parche
`python_exec.py` para volcar cada `code` recibido a `/tmp/pyexec_dumps/`
antes del `exec(compile(...))`:

```python
if body:
    mod = ast.Module(body=body, type_ignores=[])
    _dd = "/tmp/pyexec_dumps"
    try:
        import os as _os, threading as _t, time as _tm
        _os.makedirs(_dd, exist_ok=True)
        _tid = _t.get_ident()
        _ts = _tm.strftime("%H%M%S")
        _idx = _os.path.join(_dd, _ts + "_" + str(_tid) + ".py")
        _wf = open(_idx, "w")
        _wf.write(code)
        _wf.close()
    except Exception:
        pass
    exec(compile(mod, "<python_exec>", "exec"), namespace, namespace)
```

(Patch aplicado en VM solo. Live en `/home/azureuser/sreg_smoke/repo/src/sreg/agent/python_exec.py`.)

### Paso 3 — el codigo culpable

`/tmp/pyexec_dumps/022500_123108988020288.py` (15 lineas, generado por
Qwen3-8B en el smoke):

```python
import pandas as pd
import numpy as np
print('\nOutliers in facility_data (using IQR method):')
for col in facility_data.columns:
    if facility_data[col].dtype == 'float64' or facility_data[col].dtype == 'int64':
        q1 = facility_data[col].quantile(0.25)
        q3 = facility_data[col].quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outliers = facility_data[(facility_data[col] < lower_bound) | (facility_data[col] > upper_bound)]
        print(f'\n{col}:')
        print(outliers.head())   # <- SIGSEGV aca
```

`outliers.head()` es un DataFrame; `print()` invoca `__repr__()`. Pandas
recorre el `IndexEngine` para formatear las celdas. **Si dos threads
estan haciendo esto al mismo tiempo sobre dataframes distintos, las
estructuras C compartidas (caches de tipo, formatters globales) se corrompen.**

### Paso 4 — confirmar la hipotesis "thread-safety pandas"

Probado:

1. `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
   NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1` -> sigue crasheando.
   Descarta race en BLAS.
2. `max_concurrent: 1` (serializa los 8 rollouts del grupo) -> step 0
   completa, varianza no-cero. Confirma que el race es entre hilos del
   mismo proceso.

## Investigacion externa

### Frameworks de RL para LLMs y como aislan el codigo

**verifiers (PrimeIntellect)** — el que usamos. Tiene built-in
`PythonEnv` y `SandboxEnv` justamente para esto. No los estamos usando
porque nuestro solver tiene un namespace persistente custom (numpy/pandas
preloaded + observations dict + datasets como `df`/`df_1`/...). El
camino "correcto" en verifiers es escribir un Env propio que extienda
`SandboxEnv` con namespace pickling, o adaptar nuestro `python_exec.py`
para que cumpla el mismo contrato.

**Prime Intellect Sandboxes (cerrado/SaaS)** — Rust-to-pod, escala a
4000+ concurrent para entrenar INTELLECT-3. Producto pago. Es lo que
verifiers asume por debajo cuando se corre a escala.

**NeMo RL (Nvidia, OSS)** — usa **worker process isolation** para
ejecutar el codigo del agente. Cada rollout corre en un worker separado
que recibe el codigo via IPC. Mismo patron que la solucion que proponemos.

**OpenRLHF (OSS)** — usa **Ray actors** para distribuir rollouts. Cada
actor es un proceso Python independiente, lo que evita el problema por
construccion.

**TRL (HuggingFace)** — para tool-use generalmente delega a sandboxes
externos (E2B, Modal). No ejecuta el codigo del agente in-process.

### Sandboxes OSS gratuitos para code execution

- **vndee/llm-sandbox** — wrapper Python sobre Docker/Podman/k8s,
  diseniado para LLMs. Activamente mantenido. ~150 LOC para integrar.
- **alibaba/OpenSandbox** — sandbox OSS de Alibaba para agentes,
  basado en gVisor. Mas complejo de operar.
- **DifySandbox** — runtime sandbox del proyecto Dify, OSS.
- **E2B self-hosted** — version OSS del producto E2B.

### Conclusion de la investigacion

**No estabamos haciendo algo raro al pensar que esto deberia funcionar
out-of-the-box.** El error fue asumir que `python_exec.py` (codigo
adaptado de Session C, donde se llamaba secuencialmente desde un solver
sincrono) era apto para el contexto de rollouts paralelos del trainer
RL. **Los frameworks que escalan rollouts (verifiers, NeMo RL, OpenRLHF)
asumen aislamiento por proceso, no por hilo.**

## Plan de fix

### Decision: subprocess isolation (gratis, OSS, simple)

**Por que subprocess y no Docker/Sandbox:**

- **Gratis.** Sin dependencias externas, sin servicios pagos.
- **Simple.** ~100 LOC de cambio en `_exec_code`. Reusa toda la logica
  de import-guard, namespace builder, ALLOWED_IMPORTS, etc.
- **Suficiente.** Nosotros controlamos el modelo (Qwen3-8B), no es un
  setting adversarial. No necesitamos sandbox de seguridad real.
- **Mismo patron que NeMo RL.** No estamos inventando nada raro.
- **Compatible con verifiers** sin tocar el contrato de `Tool`.

**Trade-offs aceptados:**

- ~50-200ms overhead por exec (subprocess startup + pickle namespace).
  Se amortiza completo con `max_concurrent>=2`.
- No es seguro contra codigo malicioso. **No relevante** — controlamos
  la policy.
- El namespace deja de ser literalmente persistente — se serializa.
  Esto puede romper objetos no pickleables (sklearn fitted models con
  closures, generators, file handles). Hay que decidir politica:
  o (a) conservar solo lo pickleable + warn, o (b) modelar namespace
  como "estado JSON-able" desde el principio (mas restrictivo pero
  mas honesto sobre que se puede compartir entre cells).

### Skeleton del refactor

```python
def _exec_code(code: str, namespace: dict) -> tuple[str, str, str | None]:
    """Execute code in a subprocess with serialized namespace in/out."""
    import pickle, subprocess, sys, tempfile, os

    with tempfile.TemporaryDirectory() as td:
        ns_in = os.path.join(td, "ns_in.pkl")
        ns_out = os.path.join(td, "ns_out.pkl")
        result_path = os.path.join(td, "result.pkl")

        # Pickle solo lo pickleable
        with open(ns_in, "wb") as f:
            pickle.dump(_picklable_subset(namespace), f)

        runner = _build_runner_script(ns_in, ns_out, result_path, code)
        try:
            proc = subprocess.run(
                [sys.executable, "-c", runner],
                capture_output=True,
                timeout=TIMEOUT_SECONDS,
                cwd=td,
            )
        except subprocess.TimeoutExpired:
            return "", f"Timeout after {TIMEOUT_SECONDS}s", None

        if not os.path.exists(ns_out):
            # subprocess murio — devolver stderr
            return proc.stdout.decode(), proc.stderr.decode(), None

        with open(ns_out, "rb") as f:
            new_ns = pickle.load(f)
        with open(result_path, "rb") as f:
            stdout, stderr, expr_result = pickle.load(f)

        # Mutar namespace in-place para conservar identidad
        namespace.update(new_ns)
        return stdout, stderr, expr_result
```

El runner script invoca el mismo `_check_imports` + `compile/exec` actual,
serializa stdout/stderr/expr_result y namespace nuevo a pickle. Toda la
logica de import guard sigue siendo identica.

### Pasos concretos

1. **Refactor `python_exec.py`** con subprocess isolation.
2. **Reactivar `max_concurrent: 8`** en `configs/smoke_rl.yaml`.
3. **Re-correr smoke en H100** y validar:
   - step 0 completa sin SIGSEGV;
   - varianza no-cero (gates de `audit_reward_variance.py`);
   - throughput >= step 0 actual (8x rollouts en menos del 8x del wall
     clock con `max_concurrent: 1`).
4. **Resolver el OOM de step 1** (problema separado: forward pass con
   batch_size=16 x max_seq_len=16384 no entra en H100 80GB; hay que
   bajar micro_batch_size o activar gradient checkpointing).

### Tests

- Unit (`tests/agent/test_python_exec.py`): asegurar contrato actual
  (output truncation, import guard, namespace persistence entre calls,
  ExecResult.ok semantics) sigue pasando con la implementacion subprocess.
- Mini stress test: 8 threads llamando `execute_code` con codigo que use
  `print(df.head())` en paralelo, sin SIGSEGV.

## Implicancia para el protocolo

Hasta que se aplique este fix, **el smoke + cualquier RL run en H100
debe correr con `max_concurrent: 1`**. Esto invalida el throughput
estimado en `sreg_training_transfer_protocol.md` para el caso N>1.

Despues del fix, el numero de rollouts paralelos en GRPO depende solo de
(a) capacidad de vLLM para servir requests concurrentes y (b) memoria
del trainer para acumular gradientes — ya no de la arquitectura de
`python_exec`.
