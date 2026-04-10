# SREG Training And Transfer Protocol

> **Status:** CANONICO para training + transfer de tesis.  
> **Fecha:** 2026-04-06  
> **Relacion con otros docs:** este archivo fija la configuracion operativa.
> El marco conceptual sigue viviendo en
> `research/synthesis/thesis_evaluation_framework.md`.

## Para que sirve este archivo

Este archivo responde:

> **Con que modelo, con que harness, con que benchmarks y con que comparaciones
> vamos a probar si entrenar con SREG produce mejora real?**

Usarlo cuando haya que:

- correr `BEFORE`;
- definir el setup de training;
- correr `AFTER`;
- decidir si un cambio entra o no en la evaluacion de tesis.

No usarlo para:

- principios generales de scoring;
- vision de producto;
- ideas exploratorias de benchmarks.

## Decisiones cerradas

- **Modelo principal:** `Qwen3-8B`
- **Framework de training:** `verifiers + prime-rl`
- **Training v1:** `SFT + RL` (con reapertura — ver "Decisiones reabiertas")
- **Reward RL v1:** `score.total` terminal de SREG
- **Harness:** el mismo solver stack en solver eval, BEFORE, TRAIN y AFTER

## Decisiones reabiertas (2026-04-07)

### SFT+RL vs RL-from-base — pendiente de evidencia empirica

SandMLE (Zhou et al. 2026) reporta empiricamente en su dominio que
**SFT-only colapsa fuera del scaffold de generacion** (17.7% valid
submission en MLE-Dojo para el modelo 30B), mientras que **RL desde
base mantiene 83.9%** en el mismo benchmark. Su variante hibrida
SFT+RL no es la que reportan como primaria.

Esto **no invalida** nuestra eleccion de `SFT + RL`, pero la convierte
en una hipotesis a validar empiricamente, no en una decision cerrada.

Tres opciones abiertas:

1. **Mantener SFT+RL como v1** — asumir que SREG es lo suficientemente
   distinto a SandMLE como para que el patron no se replique.
2. **Cambiar a RL-from-base como v1** — y SFT+RL como ablacion.
3. **Correr ambas en paralelo** — la mas honesta y la mas cara.

Recomendacion: opcion 3 si el costo lo permite, opcion 2 si no. La
razon es asimetria de riesgo — si SREG via SFT memoriza nuestro
scaffold (compiler + sub-questions + claim format), va a colapsar en
transfer exactamente como Seed-SFT colapso en MLE-Dojo. Y los
benchmarks externos NO comparten nuestro scaffold.

Decision pendiente. Ver `research/synthesis/related_work_sandmle.md`
seccion "Reabrir la decision SFT+RL vs RL-only".

## Que significa "mismo harness"

Debe mantenerse fijo:

- mismo modelo base;
- mismo scaffold del agente;
- mismo manejo de estado y memoria;
- mismo `python_exec`;
- misma interfaz OpenAI-compatible;
- misma politica de tool use;
- mismo formato de logging.

Lo que puede cambiar:

- el entorno;
- los datos/herramientas visibles;
- el reward durante training;
- el formato de salida exigido por cada benchmark.

## Comparaciones canonicas

Las comparaciones minimas de tesis son:

- `base`
- `base + SFT`
- `base + SFT + RL`
- `base + RL` (RL-from-base, agregada 2026-04-07 por reapertura ver
  "Decisiones reabiertas")

La pregunta central es:

- cuanto aporta imitacion;
- cuanto aporta RL con reward verificable de SREG;
- **el SFT inicial ayuda al RL o lo contamina (riesgo de overfit al
  scaffold de generacion).**

## Suite final v1

### In-domain

- `held-out SREG`

### External

- `CLadder`
- `QRData`
- `DiscoveryBench`
- `CausalReasoningBenchmark` (CRB)
- `SciGym`

## Rol de cada benchmark

- `held-out SREG`: mejora in-domain en casos no vistos
- `CLadder`: razonamiento causal formal (rungs 1-3) en lenguaje natural,
  scoring determinista yes/no
- `QRData`: razonamiento causal/estadistico con datos tabulares reales,
  scoring determinista
- `DiscoveryBench`: generacion de hipotesis desde datos, scoring por
  Hypothesis Match Score (LLM-judge)
- `CausalReasoningBenchmark` (CRB): 173 queries sobre 138 datasets reales
  curados de 85 papers peer-reviewed + 4 libros de causal inference. Separa
  explicitamente identificacion (estrategia, treatment, outcome, controles)
  de estimacion (point estimate + SE). Baseline SOTA: 84.4% en estrategia,
  pero solo 30.1% en spec completa (benchmark duro). Publico en Hugging Face.
  Paper: arXiv:2602.20571
- `SciGym`: el unico benchmark publico que mide **ciclo iterativo completo**
  de investigacion (proponer experimento -> observar -> actualizar creencias
  -> refinar). 350 sistemas biologicos en SBML. Scoring determinista por
  graph edit distance vs ground-truth causal. Es el benchmark mas cercano
  al loop Sherlock-type que SREG aspira a entrenar. Costo de integracion:
  Linux/Docker, formato SBML, series temporales (no tablas).
  Repo: github.com/h4duan/SciGym

## Reglas de evaluacion

En BEFORE y AFTER:

- mismo modelo base;
- mismos splits;
- mismas seeds;
- misma temperatura;
- mismo judge cuando el benchmark use LLM-as-judge;
- mismo harness.

Si no se mantiene eso, el delta no cuenta como evidencia limpia.

## Configuracion de training v1

- **Warm start:** SFT sobre trayectorias / demostraciones SREG
- **RL:** `verifiers + prime-rl`
- **Signal principal:** reward terminal `score.total`

No agregar shaping complejo en v1 salvo necesidad clara.
La primera pregunta es si SREG funciona como fuente de reward RL, no si el
reward fue optimizado al maximo.

## Metricas minimas a reportar

### Held-out SREG

- `score.total`
- `no_data_gap`
- `reward-order accuracy`

### CLadder

- accuracy global
- accuracy por rung

### QRData

- accuracy global
- causal accuracy
- statistical accuracy
- con tools vs sin tools

### DiscoveryBench

- HMS
- judge model fijado, prompt fijado, version fijada, multiple seeds + voting
  (mitigacion de no-determinismo)

### CausalReasoningBenchmark

- accuracy de identificacion (strategy, treatment, outcome, controls)
- accuracy de spec completa (full identification)
- accuracy de estimacion (point estimate dentro de margen + SE)

### SciGym

- graph edit distance vs ground-truth (final)
- graph edit distance vs n_iterations (curva de eficiencia)
- recovery rate (sistemas resueltos completamente)

## Lo que todavia falta fijar

Estas piezas siguen abiertas y deben cerrarse antes del primer run canonico:

- split exacto de `held-out SREG`
- seeds finales
- temperatura final
- budget / max iterations del agente
- dataset/split exacto para cada benchmark
- criterio exacto de exito para la tesis

## Regla de cambios

Si cambia cualquiera de estas decisiones:

- actualizar este archivo;
- resumir el cambio en `thesis_evaluation_framework.md` si afecta la tesis;
- bajar tareas concretas a `TODO.md`;
- registrar implementacion en `CURRENT_STATE.md`.

## Precedente externo

SandMLE (Zhou et al. 2026, arXiv:2604.04872) es el precedente publico mas
cercano a este protocolo. Aplica el mismo approach (entornos sinteticos +
ground truth programatico + RL trajectory-wise) a un dominio adyacente
(ML engineering), entrenando Qwen3-8B/14B/30B con SFT+RL y reportando
+20.3% a +66.9% en medal rate vs SFT baseline y hasta +32.4% en transfer
a benchmarks externos (MLE-Dojo).

Implicancias para este protocolo:

- **Modelo base validado.** Qwen3-8B es entrenable con SFT+RL y produce
  mejoras significativas en su setup. Refuerza nuestra eleccion.
- **Vara de magnitud.** ~20-67% relative improvement es la referencia
  externa de cuanto deberia mover RL on-policy con reward exacto. Nuestro
  delta `base + SFT + RL` vs `base + SFT` deberia caer en ese rango si
  el approach esta bien aplicado.
- **Eval transfer alineado.** Su `MLE-bench-lite (in-domain) + MLE-Dojo
  (out-of-distribution)` es estructuralmente analogo a nuestro
  `held-out SREG + CLadder/QRData/DiscoveryBench/CausalReasoningBenchmark`.
- **Riesgo conocido.** Test-time context overflow en horizonte largo
  (loops repetitivos). El harness debe disenarse anticipandose a esto,
  especialmente para OI runs largos.
- **Convencion de reporte.** Util adoptar "relative improvement vs SFT
  baseline" como una de las metricas de presentacion para facilitar
  comparacion cruzada con papers similares.

Analisis completo y detalle de coincidencias/divergencias en
`research/synthesis/related_work_sandmle.md`.
