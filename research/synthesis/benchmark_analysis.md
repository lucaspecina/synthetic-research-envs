# Benchmarks externos para validar policies entrenadas con SREG

> Documento consolidado a partir de investigaciones independientes (Claude y GPT).
> Objetivo: identificar benchmarks externos que midan las capacidades que SREG
> entrena, para evaluar transferencia BEFORE/AFTER de una policy.
>
> Actualizado: 2026-03-11

---

## Por que benchmarks externos

SREG genera entornos de entrenamiento con reward signals exactos para razonamiento
cientifico. Pero que una policy mejore *dentro* de SREG no prueba que aprenda
ciencia de verdad -- podria estar explotando regularidades del generador (formato,
patrones de DAG, tipos de variables).

Para demostrar transferencia real, necesitamos evaluar la policy en benchmarks
que ella nunca vio durante el entrenamiento:

```
BEFORE: evaluar policy base en benchmarks externos
  |
TRAIN: entrenar policy en entornos SREG (SFT + RL)
  |
AFTER: evaluar policy entrenada en los MISMOS benchmarks
  |
COMPARAR: deltas, significancia, failure modes
```

Si sube en SREG pero no en benchmarks externos = sobreajuste.
Si sube en ambos = evidencia de habilidad cientifica transferible.

---

## Las 3 habilidades que SREG entrena

Para elegir benchmarks, primero hay que saber que habilidades mide SREG:

| Habilidad | Que entrena SREG | Eval types relacionados |
|---|---|---|
| **Razonamiento causal** | Distinguir correlacion vs causalidad, do-calculus, confounders, mediacion | causal_effect, adjustment_set, should_condition, compare_interventions |
| **Formulacion de hipotesis desde datos** | Analizar datos tabulares, inferir distribuciones, seleccionar explicaciones | infer_target, hypothesis_selection, infer_latent_cause |
| **Diseno experimental bajo presupuesto** | Elegir que medir, optimizar informacion por unidad de costo, saber cuando parar | next_best_observation, best_intervention |

Ningun benchmark externo cubre las 3 simultaneamente. La estrategia es usar un
**suite de 4-5 benchmarks complementarios**.

---

## Tier 1: Benchmarks primarios (alta alineacion con SREG)

### DiscoveryBench -- formulacion de hipotesis desde datos tabulares

**Fuente:** Allen AI, NeurIPS 2024
**Que hace:** El agente recibe datasets tabulares reales (CSVs) + un objetivo
de descubrimiento y debe producir una hipotesis en lenguaje natural.

| Aspecto | Detalle |
|---|---|
| **Tamano** | 264 tareas reales (DB-REAL, 6 dominios) + 903 sinteticas (DB-SYNTH) |
| **Scoring** | Hypothesis Match Score (HMS): contexto F1 + variables F1 + relacion accuracy. LLM-judge con prompts publicos |
| **SOTA** | ~25% HMS (Reflexion + GPT-4o). Amplio margen para mejora |
| **Alineacion** | Hipotesis desde datos, razonamiento causal (parcial), analisis estadistico |
| **Disponibilidad** | GitHub + HuggingFace, licencia ODC-BY |

**Por que es el #1:** Es lo mas cercano a lo que hace SREG -- partir de datos,
razonar sobre variables, y llegar a una conclusion. DB-SYNTH sirve para desarrollo
(mas tareas, dificultad controlable), DB-REAL para evaluacion final.

**Limitaciones:** Scoring por LLM-judge (no determinista). Algunas hipotesis gold
son correlacionales, no causales. El agente genera codigo Python, lo que mide
parcialmente capacidad de coding.

### CLadder -- razonamiento causal formal (Pearl)

**Fuente:** causalNLP, NeurIPS 2023
**Que hace:** Preguntas yes/no sobre los 3 niveles de Pearl (asociacion,
intervencion, contrafactual) con grafos causales + probabilidades en texto.

| Aspecto | Detalle |
|---|---|
| **Tamano** | 10,112 preguntas |
| **Scoring** | Accuracy binaria (exact match), completamente determinista |
| **SOTA** | 70.4% (GPT-4 + CausalCoT) |
| **Alineacion** | Razonamiento causal formal directo |
| **Disponibilidad** | GitHub + HuggingFace |

**Por que importa:** Si SREG entrena causalidad "real", CLadder lo detecta.
Tiene variantes clave para diagnostico:
- `q-commonsense` vs `q-anticommonsense` vs `q-nonsense`: si la policy mejora
  en nonsense (nombres aleatorios), aprendio razonamiento causal, no asociaciones
  semanticas. Esto es exactamente lo que SREG deberia lograr.

**Limitaciones:** Puramente textual -- no involucra datos tabulares. Mide si el
modelo "sabe" do-calculus, no si puede aplicarlo a datos reales.

**Metricas recomendadas:** Accuracy por rung (1/2/3) y query type (ATE, backdoor,
NDE/NIE). Opcionalmente: log-loss/Brier si la policy produce distribuciones
(alineado con SREG).

### QRData -- razonamiento causal con datos reales

**Fuente:** ACL Findings 2024
**Que hace:** Preguntas de razonamiento estadistico y causal acompanadas de
CSVs reales. Incluye intervalos de confianza, tests de hipotesis, regresion,
e **inferencia causal** (tratamientos, confounders, causal discovery).

| Aspecto | Detalle |
|---|---|
| **Tamano** | 411 preguntas (+ 290 solo texto como control) |
| **Scoring** | Accuracy automatica (exact match, MC + numerico). Determinista |
| **SOTA** | 58% (GPT-4). Rendimiento cae dramaticamente en subset causal |
| **Alineacion** | Razonamiento causal CON datos -- exactamente lo que hace SREG |
| **Disponibilidad** | GitHub |

**Por que importa:** Es el unico benchmark que separa explicitamente razonamiento
estadistico vs causal con datos. Si SREG mejora especificamente lo causal, QRData
lo revela.

**Limitaciones:** Solo 411 preguntas (subset causal mas chico). Formato Q&A
estatico, no multi-step agentivo. Preguntas estilo textbook.

### SciGym -- ciclo completo de investigacion (el mas parecido a SREG)

**Fuente:** julio 2025
**Que hace:** El agente actua como cientifico en sistemas biologicos simulados.
Propone experimentos de perturbacion, observa resultados simulados (series
temporales), e iterativamente recupera la estructura causal.

| Aspecto | Detalle |
|---|---|
| **Tamano** | 350 sistemas biologicos (137 evaluados, 213 adicionales) |
| **Scoring** | Graph edit distance vs ground-truth. Completamente determinista |
| **Alineacion** | Ciclo proponer-observar-inferir (loop completo como SREG) |
| **Disponibilidad** | GitHub + HuggingFace |

**Por que importa:** Es el benchmark mas cercano al loop de SREG: decidir que
medir, observar, actualizar creencias, refinar. Captura las 3 habilidades.

**Limitaciones:** Datos son series temporales biologicas, no tablas discretas.
Dominio exclusivamente biologia de sistemas. Infraestructura mas compleja.

---

## Tier 2: Benchmarks secundarios (alineacion parcial, complementarios)

### BixBench -- agente cientifico con tool-use real

**Fuente:** FutureHouse, 2025
**Que hace:** Tareas reales de bioinformatica. El agente explora datasets,
ejecuta codigo (Python/R/Bash), genera hipotesis y las valida. Soporta
trayectorias agentivas y modo zero-shot.

| Aspecto | Detalle |
|---|---|
| **Tamano** | 205 preguntas de notebooks reales |
| **Scoring** | Accuracy (grader LLM para open-ended, exact match para MCQ). Majority vote k=5 |
| **Alineacion** | Tool-use cientifico, trayectorias, planificacion |
| **Disponibilidad** | GitHub + HuggingFace (v1.5) |

**Valor:** Prueba de transferencia **lejana** -- sale de mundos sinteticos y pone
a la policy en datos reales con tools. Si mejora aca, la habilidad es generalizable.
Tiene formato de trayectorias compatible con SREG.

### HypoBench -- generacion de hipotesis rigurosa

**Fuente:** U. Chicago, arXiv abril 2025
**Que hace:** El agente recibe datos tabulares/estructurados y genera hipotesis
sobre patrones explicativos. 194 datasets en 12 dominios (7 reales + 5 sinteticos).

| Aspecto | Detalle |
|---|---|
| **Scoring** | Hypothesis Discovery Rate (HDR) = Feature Discovery Rate x Relationship Correctness. LLM-judge validado (kappa 0.80-0.86) |
| **Alineacion** | Descubrimiento de features y relaciones (causales y no causales) |
| **Disponibilidad** | GitHub + HuggingFace |

**Valor:** Datasets sinteticos con dificultad controlable son ideales para curvas
BEFORE/AFTER. Scoring multidimensional (no solo accuracy).

### BLADE -- decisiones analiticas con datos

**Fuente:** UW, EMNLP 2024 Findings
**Que hace:** El agente recibe dataset tabular + pregunta de investigacion y debe
formular variables (IV, DV, controles), transformar datos, e implementar modelos.
Se compara contra decisiones de 500+ expertos humanos.

| Aspecto | Detalle |
|---|---|
| **Tamano** | 12 datasets reales |
| **Scoring** | Automatico, comparacion contra ground-truth multi-experto |
| **Alineacion** | Decidir que variables medir y como analizarlas |
| **Disponibilidad** | GitHub |

**Valor:** Evalua decisiones intermedias (no solo respuesta final) -- relevante
porque SREG entrena el *proceso* de investigacion.

**Limitacion:** Solo 12 tareas -- N muy bajo para comparaciones estadisticas robustas.

### CORR2CAUSE -- correlacion a causacion

**Fuente:** ICLR 2024
**Que hace:** El modelo recibe correlaciones textuales entre variables abstractas
y determina si una hipotesis causal es valida. ~4,500 instancias test.

| Aspecto | Detalle |
|---|---|
| **Scoring** | Binario automatico. LLMs rinden cerca del azar |
| **Alineacion** | Inferir causalidad desde correlaciones (core de SREG) |

**Valor:** Test rapido, sensible a mejoras. Pero variables abstractas sin
semantica de dominio, y correlaciones son textuales, no derivadas de datos.

### CausalBench (CausalBN-Bench) -- descubrimiento causal con datos en prompts

**Fuente:** arXiv 2024
**Que hace:** 15 redes bayesianas reales (Bnlearn). 4 formatos de prompt
progresivos: solo nombres, + background, + datos numericos, + todo. Evalua
correlaciones, esqueleto causal, y direccion causal.

| Aspecto | Detalle |
|---|---|
| **Hallazgo clave** | LLMs entienden causalidad por asociaciones SEMANTICAS con nombres, no por distribuciones numericas |

**Valor para SREG:** Si SREG logra que la policy realmente USE datos numericos
(no solo nombres), este benchmark lo detectaria.

### HypoSpace -- hipotesis bajo indeterminacion

**Fuente:** NUS/Meta, octubre 2025
**Que hace:** Evalua si modelos pueden generar SETS de hipotesis validas bajo
datos insuficientes. Incluye dominio de inferencia de grafos causales.

| Aspecto | Detalle |
|---|---|
| **Scoring** | Determinista: validez, unicidad, cobertura del espacio de hipotesis |
| **Alineacion** | Razonamiento bajo evidencia parcial (core de SREG) |

**Valor:** Mide exactamente la capacidad de razonar con incertidumbre.
Los autores lo llaman "diagnostic probe" -- settings abstractos.

### CauSciBench -- pipeline causal end-to-end (emergente)

**Fuente:** ETH Zurich, NeurIPS 2025 Workshop
**Que hace:** Pipeline completo: formulacion -> seleccion de variables -> eleccion
de metodo (IPW, IV, DID, RDD) -> implementacion -> interpretacion. 305-367
tareas en 9 disciplinas.

**Valor:** Seria el benchmark mas alineado con la parte de estimacion causal de
SREG. Pero es de un workshop, menos establecido. Verificar disponibilidad del
repositorio.

---

## Tier 3: Evaluados pero poco relevantes para SREG

| Benchmark | Por que no | Tipo |
|---|---|---|
| **ScienceAgentBench** (ICLR 2025, 102 tareas) | Fundamentalmente generacion de codigo cientifico, no razonamiento causal | Coding |
| **PaperBench** (OpenAI, ICML 2025, 20 papers) | Replicacion de papers de ML. 8,316 sub-tareas de implementacion | Engineering |
| **MLAgentBench** (ICML 2024, 13 tareas) | Ingenieria ML pura -- optimizar modelos, pipelines | ML ops |
| **MLE-bench** (OpenAI, ICLR 2025, 75 Kaggle) | Competencias de data science y ML | ML ops |
| **DSBench** (ICLR 2025, 540 tareas) | Competencias ModelOff + Kaggle. Habilidad analitica, no causal | Data science |
| **ResearchGym** (febrero 2026, 5 entornos) | Solo dominio AI/ML, infraestructura compleja, muy reciente | ML research |
| **DiscoveryWorld** (Allen AI, NeurIPS 2024 Spotlight) | Conceptualmente alineado pero formato text-adventure 2D, mide navegacion ademas de ciencia | Simulation |
| **LAB-Bench** (MCQ biologia) | Capacidades de investigacion en biologia, pero formato MCQ multimodal, parcialmente privado | Biology |

---

## El gap: por que no existe el benchmark perfecto

SREG combina 3 capacidades que los benchmarks existentes tratan por separado:

1. **Benchmarks de razonamiento causal** (CLadder, CORR2CAUSE, CausalBench) son
   predominantemente **textuales** -- presentan grafos y probabilidades en lenguaje
   natural, no en datasets. Miden si el modelo "sabe" do-calculus, no si puede
   descubrir estructura causal desde datos ruidosos.

2. **Benchmarks de analisis de datos** (DiscoveryBench, QRData, BLADE) dan datos
   tabulares pero evaluan **formulacion de hipotesis o respuestas estadisticas**,
   sin componente explicito de "elige que medir" o "disena el siguiente experimento
   bajo presupuesto limitado".

3. **Benchmarks de diseno experimental** (SciGym, DiscoveryWorld) si tienen ciclos
   iterativos de experimentacion, pero operan en **dominios especializados** con
   formatos de datos muy diferentes a tablas discretas.

La **seleccion de experimentos bajo presupuesto** -- una habilidad central de
SREG -- simplemente no tiene un benchmark dedicado con datos publicos y scoring
automatico. Este es el gap mas significativo.

---

## Suite recomendada

### Core (4 benchmarks, cubren las 3 habilidades)

| Benchmark | Habilidad principal | Tipo de scoring | Costo de ejecucion |
|---|---|---|---|
| **DiscoveryBench** | Hipotesis desde datos | LLM-judge (HMS) | Medio |
| **CLadder** | Razonamiento causal formal | Determinista (accuracy) | Bajo |
| **QRData** | Causalidad con datos reales | Determinista (accuracy) | Bajo |
| **SciGym** | Ciclo experimental completo | Determinista (graph edit distance) | Medio-alto |

### Complementarios (segun necesidad)

| Benchmark | Cuando usarlo |
|---|---|
| **BixBench** | Transferencia lejana -- validar que la mejora se transfiere a datos/tools reales |
| **HypoBench** | Mas granularidad en generacion de hipotesis (scoring multidimensional) |
| **CORR2CAUSE** | Test rapido de correlacion -> causacion (4,500 instancias) |
| **CauSciBench** | Pipeline causal end-to-end (si se confirma disponibilidad publica) |
| **CausalBench** | Diagnostico: la policy usa datos numericos o solo nombres? |

### Mapeo habilidades -> benchmarks

```
SREG entrena                    Benchmark que lo mide
-----------                     ---------------------
Razonamiento causal        -->  CLadder (formal), QRData (con datos), CausalBench (diagnostico)
Hipotesis desde datos      -->  DiscoveryBench (principal), HypoBench (complementario)
Diseno experimental        -->  SciGym (ciclo completo)
Tool-use cientifico        -->  BixBench (transferencia lejana)
Calibracion/incertidumbre  -->  CLadder (Brier score), QRData (numericas)
```

---

## Protocolo BEFORE/AFTER

### Flujo general

```
1. Definir policy base (S0) + scaffolding fija
2. BEFORE: evaluar S0 en los 4 benchmarks core
3. TRAIN: entrenar S0 en entornos SREG -> S1 (SFT + RL)
4. AFTER: evaluar S1 en los MISMOS benchmarks, MISMOS splits
5. COMPARAR: deltas, significancia, failure modes, costo
```

### Que mantener constante (si no, el resultado es dudoso)

- Misma scaffolding (plan/act/reflect, mismas tools salvo las del benchmark)
- Misma politica de sampling (temperature/top_p) o multiples seeds
- Misma infraestructura de logs
- Mismo evaluador/judge cuando el benchmark use LLM-judge
- Misma version del dataset (pinnear version/tag/commit/hash)

### Controles recomendados

- **Control negativo:** entrenamiento placebo (SFT en datos no relacionados, o RL
  con reward random) para verificar que mejoras no surgen por drift o mayor compute.
- **Ablacion de semantica:** CLadder `q-nonsense` vs `q-commonsense` para ver si
  la mejora es causal o semantica. Si SREG entrena causalidad real, deberia mejorar
  en `q-nonsense` (nombres aleatorios).
- **NoData baselines:** DiscoveryBench incluye "NoDataGuess" para medir memorizacion.

### Criterios de exito

**Cuantitativos (minimos para declarar transferencia):**
- DiscoveryBench: +HMS relativo >= 10% con CIs que no crucen cero
- CLadder: mejora significativa en rung 2 (intervencion) y 3 (contrafactual),
  especialmente en variante `q-nonsense` o `q-anticommonsense`
- QRData: mejora en subset causal sin degradar subset estadistico
- SciGym: menor graph edit distance con igual o menos iteraciones

**Cualitativos (diagnostico):**
- Menos acciones irrelevantes (mejor planificacion)
- Trayectorias mas cortas para igual score
- Mejor alineacion entre hipotesis y evidencia

### Riesgo de sobreajuste a SREG

Si sube en SREG pero no en benchmarks externos, puede ser que la policy explota
regularidades del generador. Mitigaciones:

- Holdouts fuertes dentro de SREG: dominios, tipos de DAG, semanticas nunca vistas
- CLadder `q-nonsense` como indicador de dependencia semantica
- Cross-benchmark: si sube SREG y no CLadder/DiscoveryBench, es senial de sobreajuste

---

## URLs de referencia

```
DiscoveryBench
  Paper:   https://arxiv.org/abs/2407.01725
  Repo:    https://github.com/allenai/discoverybench
  Dataset: https://huggingface.co/datasets/allenai/discoverybench

CLadder
  Paper:   https://arxiv.org/abs/2312.04350
  Repo:    https://github.com/causalNLP/cladder
  Dataset: https://huggingface.co/datasets/causalnlp/CLadder

QRData
  Repo:    https://github.com/xxxiaol/QRData

SciGym
  Repo:    https://github.com/h4duan/SciGym
  Dataset: https://huggingface.co/h4duan/scigym-sbml

BixBench
  Paper:   https://arxiv.org/abs/2503.00096
  Repo:    https://github.com/Future-House/BixBench
  Dataset: https://huggingface.co/datasets/futurehouse/BixBench

HypoBench
  Repo:    https://github.com/ChicagoHAI/HypoBench-datasets

CORR2CAUSE
  HuggingFace + GitHub (ICLR 2024)

CausalBench (CausalBN-Bench)
  Repo:    https://github.com/Rainy-ZhouYu/CausalBN-Bench

CauSciBench
  Repo:    https://github.com/causalNLP/CauSciBench (verificar disponibilidad)

AstaBench
  Repo:    https://github.com/allenai/asta-bench
  Site:    https://allenai.org/asta/bench
```

---

## Fuentes

Este documento consolida investigacion de dos fuentes independientes:
- `research/archive/scientific_benchmarks_policy_claude.md` -- analisis de 20+ benchmarks
- `research/archive/scientific_benchmarks_policy_gpt.md` -- seleccion de top 3 + protocolo BEFORE/AFTER

Ambos archivos se mantienen como referencia con el analisis completo original.
