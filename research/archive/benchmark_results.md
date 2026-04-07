# Benchmark BEFORE Scores

> **AVISO IMPORTANTE — NO VALIDO PARA TESIS**
>
> Estos numeros se corrieron con `gpt-5.2-chat`, NO con el modelo canonico
> de tesis (`Qwen3-8B`). Por lo tanto **NO sirven como BEFORE para el
> experimento de tesis**. Hay que re-correrlos con Qwen3-8B antes de
> considerarlos baseline valido.
>
> Ademas:
> - QRData se corrio text-only (sin code interpreter). El setup canonico
>   del paper usa code execution. Decidir harness antes de re-correr.
> - DiscoveryBench se corrio sin mitigacion documentada del LLM-judge
>   (judge model, prompt, version, seeds, voting). Cerrar antes de re-run.
>
> Decisiones canonicas: ver `research/synthesis/sreg_training_transfer_protocol.md`
> y `research/synthesis/thesis_evaluation_framework.md`.
>
> Este archivo queda como referencia historica de la primera pasada de
> baselines, no como evidencia activa.

> Raw note of baseline benchmark scores before training in SREG.
> Active benchmark selection rationale lives in
> `research/synthesis/sreg_training_transfer_protocol.md`.
> Background landscape de benchmarks: `research/archive/benchmark_analysis.md`.

## Modelo

- **Modelo**: `gpt-5.2-chat` (Azure AI Foundry, `gpt-5.2-chat-2025-12-11`)
- **Tipo**: Reasoning model (no soporta temperature != 1.0 ni max_tokens)
- **Endpoint**: Azure AI Foundry via OpenAI SDK
- **Fecha**: 2026-03-13

## Resumen

| Benchmark | Score | Metrica | N | Condicion |
|-----------|-------|---------|---|-----------|
| **CLadder** | **78.0%** | accuracy | 100 (dev) | zero-shot |
| **QRData** | **38.0%** | accuracy | 50 (dev) | CoT, text-only |
| **DiscoveryBench** | **0.299 HMS** | hypothesis match | 25 (train) | zero-shot, LLM-judge |

---

## CLadder (razonamiento causal)

- **Paper**: [CLadder: Assessing Causal Reasoning in Language Models](https://arxiv.org/abs/2312.04350) (NeurIPS 2023)
- **Dataset**: `cladder-v1-q-balanced.json` (10,112 preguntas yes/no)
- **Subset**: dev (100 ejemplos, 10 por query_type, seed=42)
- **Prompt**: zero-shot con system prompt del paper original
- **Scoring**: exact match (yes/no), determinista

| Metrica | Score |
|---------|-------|
| **Overall accuracy** | **78.0%** |
| Rung 1 (association) | 100.0% |
| Rung 2 (intervention) | 70.0% |
| Rung 3 (counterfactual) | 67.5% |
| Unparseable | 0 |
| Errors | 0 |

### Por query type

| Query type | Rung | Accuracy |
|------------|------|----------|
| correlation | 1 | 100% |
| marginal | 1 | 100% |
| exp_away | 1 | 100% |
| nde | 2 | 90% |
| ate | 2 | 80% |
| backadj | 2 | 70% |
| det-counterfactual | 3 | 70% |
| collider_bias | 3 | 60% |
| ett | 3 | 60% |
| nie | 3 | 50% |

### Validacion vs literatura

| Modelo | Score | Condicion | Fuente |
|--------|-------|-----------|--------|
| GPT-4 vanilla | 62% | zero-shot | CLadder paper (NeurIPS 2023) |
| GPT-4 + CoT | 70.4% | chain-of-thought | CLadder paper |
| **gpt-5.2-chat (nuestro)** | **78%** | zero-shot | Este proyecto |

**Veredicto**: Resultado razonable. gpt-5.2-chat supera a GPT-4+CoT, esperado para un
reasoning model mas reciente. El patron rung1>rung2>rung3 coincide con la literatura.

### Datos guardados

- `experiments/benchmarks/cladder_20260313_165322/benchmark.json`
- `experiments/benchmarks/cladder_20260313_165322/results.jsonl`

---

## QRData (razonamiento cuantitativo + causal con datos)

- **Paper**: [Are LLMs Capable of Data-based Statistical and Causal Reasoning?](https://arxiv.org/abs/2402.17644) (ACL 2024 Findings)
- **Dataset**: `QRData.json` (411 preguntas) + 195 CSVs
- **Subset**: dev (50 ejemplos, seed=42)
- **Prompt**: CoT con datos CSV truncados (max 50 filas, 3500 chars) + "Final answer:" format
- **Scoring**: numerico (3% tolerancia relativa) + multiple choice (prefix match case-insensitive)

| Metrica | Score |
|---------|-------|
| **Overall accuracy** | **38.0%** |
| Causal accuracy | 43.8% |
| Statistical accuracy | 27.8% |
| Multiple choice | 48.5% |
| Numerical | 17.6% |
| Unparseable | 0 |
| Errors | 0 |

### Validacion vs literatura

| Modelo | Score | Condicion | Fuente |
|--------|-------|-----------|--------|
| GPT-4 + code interpreter | 57.9% | **con ejecucion de codigo** | QRData paper |
| GPT-3.5 + code interpreter | 41.4% | con ejecucion de codigo | QRData paper |
| **gpt-5.2-chat (nuestro)** | **38%** | **text-only, sin code** | Este proyecto |

**Veredicto**: Resultado esperado. La diferencia clave: los publicados usan **code interpreter**
(el modelo ejecuta Python para calcular). Nosotros enviamos el CSV truncado como texto.
Las preguntas numericas (17.6%) son casi imposibles sin ejecutar codigo. Esto no es un bug
sino una limitacion del setup text-only. Cuando agreguemos code execution al harness,
esperamos que suba significativamente.

### Datos guardados

- `experiments/benchmarks/qrdata_20260313_170007/benchmark.json`
- `experiments/benchmarks/qrdata_20260313_170007/results.jsonl`

---

## DiscoveryBench (descubrimiento de hipotesis desde datos)

- **Paper**: [DiscoveryBench: Towards Data-Driven Discovery with Large Language Models](https://arxiv.org/abs/2407.01725)
- **Dataset**: `discoverybench_train.csv` (25 ejemplos con gold hypotheses, de HuggingFace `allenai/discoverybench`)
- **Subset**: all (25 ejemplos, train split completo — test split no tiene gold hypotheses)
- **Dominios**: sociology (11), biology (10), economics (4)
- **Prompt**: zero-shot con descripcion de dominio + dataset + columnas + pregunta
- **Scoring**: HMS (Hypothesis Matching Score) via LLM-judge. No determinista.
  Descompone hipotesis en sub-hipotesis (contexto, variables, relacion), compara
  alineacion semantica. Rango 0.0-1.0.

| Metrica | Score |
|---------|-------|
| **Mean HMS** | **0.299** |
| Median HMS | 0.250 |
| Above 0.50 | 6/25 (24%) |
| Above 0.25 | 12/25 (48%) |
| Errors | 0 |

### Por dominio

| Dominio | HMS | N |
|---------|-----|---|
| biology | 0.427 | 10 |
| variables (sociology) | 0.398 | — |
| economics | 0.215 | 4 |
| sociology | 0.213 | 11 |

### Por tipo de pregunta

| Tipo | HMS |
|------|-----|
| relationship | 0.259-0.800 |
| variables | 0.398 |
| context | 0.228 |
| variable | 0.213 |

### Validacion vs literatura

| Sistema | Score | Condicion | Fuente |
|---------|-------|-----------|--------|
| Reflexion + Oracle (GPT-4o) | 24.5% HMS | DB-Real, con Oracle feedback | DiscoveryBench paper |
| Reflexion + Oracle (GPT-4o) | 15.7% HMS | DB-Synth | DiscoveryBench paper |
| **gpt-5.2-chat (nuestro)** | **29.9% HMS** | train split, zero-shot | Este proyecto |

**Veredicto**: Resultado plausible. 29.9% HMS supera el best publicado (24.5%), lo cual es
razonable para un reasoning model mas potente (gpt-5.2 vs GPT-4o). Sin embargo:
- Nuestro subset es train (25 ej.), el publicado usa DB-Real test (264 ej.) — no directamente comparables
- HMS no es determinista (usa LLM-judge), hay varianza entre corridas
- El modelo genera y evalua con el mismo LLM, lo cual podria sesgar ligeramente

### Datos guardados

- `experiments/benchmarks/discoverybench_20260313_234939/benchmark.json`
- `experiments/benchmarks/discoverybench_20260313_234939/results.jsonl`

---

## Contexto: por que estos benchmarks

Estos benchmarks miden **razonamiento causal y cientifico** — exactamente lo que SREG entrena.

- **CLadder**: razonamiento causal puro (Pearl's causal hierarchy). Si SREG mejora la capacidad causal, deberia subir rung 2 y 3.
- **QRData**: razonamiento cuantitativo con datos reales. Si SREG mejora la capacidad de analisis, deberia subir especialmente en preguntas causales y numericas.
- **DiscoveryBench**: descubrimiento de hipotesis desde datos tabulares. El benchmark mas alineado con SREG — generar hipotesis es exactamente lo que un agente SREG hace.

El experimento de transferencia sera:
1. BEFORE: estos scores (ya tenemos para gpt-5.2-chat)
2. TRAIN: entrenar en entornos SREG (SFT + RL)
3. AFTER: re-evaluar en los mismos benchmarks con los mismos seeds
4. DELTA: la diferencia es la evidencia de que SREG funciona

## Proximos pasos

- [ ] Correr con Qwen3-8B (cuando haya acceso) — el modelo target para RL training
- [ ] Correr CLadder/QRData subsets mas grandes (all) para scores mas robustos
- [ ] Agregar code execution a QRData para comparar text-only vs con code
- [ ] SciGym adapter (futuro, requiere Linux/Docker por stack SBML)
