# SREG Thesis Evaluation Framework

> **Status:** CANONICO para paper/tesis.  
> **Fecha:** 2026-04-06  
> **Objetivo:** unificar que hay que demostrar, como medirlo, y como se relacionan los docs existentes.

## Para que existe este documento

SREG ya tiene varios docs sobre:

- vision del producto;
- scoring;
- cobertura cientifica;
- escenarios de validacion;
- benchmarks externos.

Lo que faltaba era un documento que responda una pregunta mas concreta:

> **Que evidencia necesitamos para defender un paper o una tesis sobre SREG?**

Este doc fija esa respuesta. No reemplaza los otros docs; los organiza.

---

## Que lugar ocupa respecto a los otros docs

### Docs activos que siguen vigentes

| Doc | Rol |
|---|---|
| `research/synthesis/open_investigation_vision.md` | Vision de producto: que queremos que sea Open Investigation |
| `research/synthesis/oi_scoring_fundamentals.md` | Principios del scoring: verdad, relevancia, cobertura |
| `research/synthesis/sreg_scientific_coverage.md` | Que tipos de ciencia puede representar SREG hoy y cuales no |
| `research/synthesis/investigation_scenarios_rubric.md` | Checklist de escenarios para testear decisiones de diseno |
| `research/synthesis/scientific_research_taxonomy.md` | Framework general para clasificar tipos de investigacion |
| `research/synthesis/Doc1_Taxonomia_El_Mapa.md` | Mapa operativo para clasificar investigaciones y workflows |

### Docs heredados que quedan como insumo, no como canon

| Doc | Como tratarlo |
|---|---|
| `research/archive/benchmark_analysis.md` | Background util sobre benchmarks externos |
| `research/archive/scientific_benchmarks_policy_claude.md` | Research exploratorio; no canonico |
| `research/archive/scientific_benchmarks_policy_gpt.md` | Research exploratorio; no canonico |
| `research/archive/eval_strategy.md` y `research/archive/eval_design_notes.md` | Historia de decisiones previas; no referencia activa |

### Regla practica

- **Vision** vive en `open_investigation_vision.md`
- **Principios de scoring** viven en `oi_scoring_fundamentals.md`
- **Cobertura cientifica** vive en `sreg_scientific_coverage.md`
- **Plan de evaluacion para paper/tesis** vive aca

Si un tema cruza varios docs, este documento debe enlazar al doc especializado,
no duplicarlo entero.

---

## La claim defendible hoy

La claim mas defendible hoy no es:

> "SREG ya entrena agentes cientificos mejores en general."

Eso todavia requiere evidencia de entrenamiento y transferencia mas fuerte.

La claim defendible hoy es:

> **SREG puede construir entornos sinteticos de investigacion con verdad formal verificable, y podemos evaluar si esos entornos realmente fuerzan investigacion y si su reward esta alineado con calidad de investigacion.**

Para una tesis mas fuerte, queremos extenderla a:

> **Entrenar con SREG mejora el comportamiento del agente en casos SREG no vistos y produce al menos algo de transferencia a benchmarks externos relevantes.**

---

## Que hay que demostrar para paper/tesis

### P1. Los casos fuerzan investigacion real

Un agente sin datos, o con analisis superficial, debe rendir peor.

Pregunta central:
- el caso depende de evidencia de este mundo, o se puede responder por prior?

### P2. El reward esta alineado con mejor investigacion

Entre dos trayectorias del mismo caso, la mejor investigacion debe recibir
mejor score.

Pregunta central:
- el scoring crea la presion evolutiva correcta?

### P3. La cobertura cientifica es suficientemente amplia

SREG no tiene que cubrir toda la ciencia, pero si un espacio interesante y
explicito de investigaciones.

Pregunta central:
- que tipos de investigacion representa bien, cuales parcialmente y cuales no?

### P4. Para tesis fuerte: entrenar con SREG cambia algo real

No alcanza con que el entorno "parezca bueno". Hace falta mostrar que una
policy entrenada con SREG mejora:

- in-domain: casos SREG no vistos
- out-of-domain: benchmarks externos

---

## Unidad de evaluacion correcta

No alcanza con evaluar "el sistema" en abstracto. Hay tres unidades:

### 1. Caso

Pregunta:
- este caso obliga a investigar?

### 2. Trayectoria

Pregunta:
- esta trayectoria investigo mejor o peor que otra sobre el mismo caso?

### 3. Policy

Pregunta:
- despues de entrenar, la policy mejora en casos nuevos y en benchmarks externos?

---

## Artefactos que hay que construir

### A. Frozen case suite

Set canonico de casos congelados para evaluacion.

Cada caso deberia guardar, como minimo:

- `src.json`
- `briefing.md`
- `answer_key.md`
- `oi_result.json`
- `sub_questions_v2`
- `score_inputs_v2`

Esto es el prerequisito metodologico de P0: rescore controlado.

### B. Trajectory bank

Para cada caso, no solo una corrida. Idealmente varias trayectorias:

- `T0`: no-data / prior-only
- `T1`: superficial / correlacional
- `T2`: razonable
- `T3`: fuerte / bien calibrada

La unidad central del analisis de reward alignment es **caso + trayectoria**.

### C. Human comparison set

No para reemplazar el scorer, sino para auditarlo.

Formato recomendado:
- comparaciones pareadas entre trayectorias del mismo caso
- evaluacion ciega
- juicio sobre cual investigo mejor y por que

### D. External benchmark suite

Sirve para validar transferencia fuera de SREG.

---

## Metricas centrales

### M1. Reproducibilidad del score

- `reaggregate` debe reproducir score exacto
- `rejudge` debe mostrar drift chico y controlado
- `recompile` debe ser interpretable y estable

### M2. Investigation pressure

- `no_data_gap = score_with_data - score_no_data`

Si el gap es chico, el caso no fuerza investigacion.

### M3. Reward alignment

- **reward-order accuracy**

En cuantos pares el sistema rankea correctamente:

- `T3 > T2 > T1 > T0`

Esta es la metrica mas importante para `LA PREGUNTA`.

### M4. Human alignment

Coincidencia entre ranking humano y ranking del scorer sobre trayectorias.

### M5. Coverage by research type

Matriz de cobertura por tipo de investigacion:

- causal
- confounding
- heterogeneity
- epistemological
- methodological
- predictive
- trade-off
- mechanism discrimination

### M6. Transferencia

Para tesis fuerte:

- mejora en held-out SREG
- mejora en benchmarks externos

---

## Benchmarks externos: paquete recomendado

> **Update 2026-04-06:** la seleccion y el protocolo operativo de training +
> transfer quedaron fijados en
> `research/synthesis/sreg_training_transfer_protocol.md`.
> Este documento mantiene el marco de tesis; el otro fija la configuracion
> concreta.
>
> **Update 2026-04-07:** el analisis detallado de cada benchmark externo
> (que mide, ejemplos concretos, transferencia esperada de SREG, riesgos)
> vive en `research/synthesis/external_benchmarks_transfer_analysis.md`.
> Related work especifico: `related_work_sandmle.md` (entrenamiento) y
> `related_work_scigym.md` (loop iterativo / dry lab biologico).

### Tier 1: esenciales

| Benchmark | Que valida |
|---|---|
| `held-out SREG` | Mejora in-domain en casos no vistos |
| `CLadder` | Razonamiento causal formal en lenguaje natural (rungs 1-3) |
| `QRData` | Razonamiento estadistico y causal con datos tabulares reales |
| `DiscoveryBench` | Hypothesis generation / discovery desde datos |
| `CausalReasoningBenchmark` (CRB) | Identificacion vs estimacion sobre 173 queries en 138 datasets reales (arXiv:2602.20571). Baseline SOTA: 30.1% en spec completa |
| `SciGym` | Unico publico que mide **ciclo iterativo completo** (proponer-observar-refinar). Scoring determinista por graph edit distance. El mas cercano al loop Sherlock-type que SREG aspira a entrenar |

### Tier 2: soporte fuerte

| Benchmark | Que valida |
|---|---|
| `CauSciBench` | Causal inference cientifica end-to-end |
| `CaLM Lite` | Suite causal mas amplia y estandarizada |

### Tier 3: transferencia mas dura

| Benchmark | Que valida |
|---|---|
| `DiscoveryBench` | Debe quedarse tambien aca como comparacion longitudinal |
| `ScienceAgentBench` | Agentes que hacen workflows cientificos con codigo |
| `BixBench` | Transferencia agentica con tool-use real (bioinformatica) |

### Por que SciGym esta en Tier 1

El research previo (`archive/benchmark_analysis.md`) lo identifico como el
unico benchmark publico que cierra el gap del loop iterativo. La suite
canonica anterior lo habia descartado por costo operativo (Linux/Docker,
SBML, series temporales). La decision se reabrio porque sin SciGym la suite
mide razonamiento causal estatico y generacion single-shot, pero **no mide
nada del loop iterativo Sherlock-type que SREG dice que entrena**. Mantener
ese gap haria la claim del paper indefendible. Costo de integracion aceptado.

### Watchlist

| Benchmark | Status |
|---|---|
| `DeepCausa` | Interesante para causal transfer, pero no deberia ser benchmark principal hasta tener release publica estable y facil de integrar |

---

## Protocolo minimo para una tesis defendible

### Fase 0. Higiene metodologica

- terminar P0
- congelar eval set
- asegurar rescore controlado

### Fase 1. Evaluacion interna de SREG

- medir `no_data_gap`
- medir `reward-order accuracy`
- auditar failure modes
- reportar cobertura por tipo de investigacion

### Fase 2. Entrenamiento

- entrenar una policy con SREG
- usar `SFT + RL`, no solo SFT
- comparar `base` vs `base + SFT` vs `base + SFT + RL`
- evaluar en held-out SREG

### Fase 3. Transferencia externa

- BEFORE/AFTER en benchmarks externos
- mismo modelo base
- mismo scaffolding
- mismo budget

### Fase 4. Auditoria cualitativa

- comparar trayectorias buenas vs malas
- documentar donde el scorer acierta y donde no

---

## Decisiones operativas ya cerradas

Estas decisiones ya no estan en modo brainstorming.

- **Modelo principal:** `Qwen3-8B`
- **Framework de training:** `verifiers + prime-rl`
- **Training de tesis:** `SFT + RL`
- **Reward RL v1:** `score.total` terminal de SREG
- **Suite final v1:** `held-out SREG + CLadder + QRData + DiscoveryBench + CausalReasoningBenchmark + SciGym`
- **Comparaciones minimas:** `base`, `base + SFT`, `base + SFT + RL`
- **Regla de evaluacion:** mismo harness del solver en BEFORE, TRAIN y AFTER

La especificacion exacta de estas decisiones vive en:

- `research/synthesis/sreg_training_transfer_protocol.md`

---

## Bloqueos conocidos hoy

### B1. P0 todavia es prerequisito

Sin rescore controlado, no podemos atribuir mejoras con rigor.

### B2. Hay gaps reales de representacion

`poverty` mostro que ciertas investigaciones validas no son expresables hoy
en la grammar.

### B3. Hay issues reales de credit assignment

`microbiome` mostro que el scorer actual puede asignar credito de forma
incorrecta aunque haya piezas correctas disponibles.

### B4. La evaluacion externa todavia no es canonica

Hay research previo sobre benchmarks, pero falta una seleccion cerrada y un
protocolo BEFORE/AFTER estable.

---

## Decision documental

Desde ahora:

- este documento es la referencia canonica para **paper/tesis + evaluacion**
- los docs activos especializados siguen vigentes en su scope
- los docs de `archive/` quedan como evidencia historica y background, no como
  fuente de verdad

Si este framework cambia una decision operativa del proyecto:

- resumir en `PROJECT.md`
- bajar trabajo pendiente a GitHub Issues
- registrar implementaciones en `CURRENT_STATE.md`
