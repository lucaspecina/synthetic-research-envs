# Benchmark BEFORE Scores

> Scores de referencia **antes** de entrenar en SREG.
> Despues del entrenamiento, la diferencia con estos scores es la evidencia de transferencia.

## Modelo

- **Modelo**: `gpt-5.2-chat` (Azure AI Foundry, `gpt-5.2-chat-2025-12-11`)
- **Tipo**: Reasoning model (no soporta temperature != 1.0 ni max_tokens)
- **Endpoint**: Azure AI Foundry via OpenAI SDK
- **Fecha**: 2026-03-13

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

### Interpretacion

- Rung 1 (asociacion) es trivial para el modelo: 100%.
- Rung 2 (intervencion) empieza a costar: 70%. ATE y backdoor adjustment requieren razonamiento causal real.
- Rung 3 (contrafactual) es el mas dificil: 67.5%. NIE (indirect effects) es particularmente dificil (50% = random).
- Patron consistente con la literatura: dificultad escala con el rung de Pearl.

### Datos guardados

- `experiments/benchmarks/cladder_20260313_165322/benchmark.json` — metricas agregadas
- `experiments/benchmarks/cladder_20260313_165322/results.jsonl` — 100 resultados individuales con respuestas crudas

---

## QRData (razonamiento cuantitativo + causal con datos)

- **Paper**: [Quantitative Reasoning with Data](https://arxiv.org/abs/2309.07263)
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

### Interpretacion

- El modelo es mejor en causal (43.8%) que en estadistica pura (27.8%).
- Multiple choice es mas facil (48.5%) que numerico (17.6%) — esperado, MC tiene opciones.
- Accuracy numerica baja (17.6%) sugiere que el modelo no puede computar resultados exactos sin ejecutar codigo.
- **Importante**: QRData requiere analisis de datos reales. Sin code execution, el modelo solo puede estimar.
  Esto es una limitacion del setup actual (text-only, sin herramientas de calculo).

### Datos guardados

- `experiments/benchmarks/qrdata_20260313_170007/benchmark.json` — metricas agregadas
- `experiments/benchmarks/qrdata_20260313_170007/results.jsonl` — 50 resultados individuales

---

## Contexto: por que estos benchmarks

Estos benchmarks miden **razonamiento causal y cientifico** — exactamente lo que SREG entrena.

- **CLadder**: razonamiento causal puro (Pearl's causal hierarchy). Si SREG mejora la capacidad causal, deberia subir rung 2 y 3.
- **QRData**: razonamiento cuantitativo con datos reales. Si SREG mejora la capacidad de analisis, deberia subir especialmente en preguntas causales.

El experimento de transferencia sera:
1. BEFORE: estos scores (ya tenemos)
2. TRAIN: entrenar en entornos SREG (SFT + RL)
3. AFTER: re-evaluar en los mismos benchmarks con los mismos seeds
4. DELTA: la diferencia es la evidencia de que SREG funciona

## Proximos pasos

- [ ] Correr con Qwen3-8B (cuando haya acceso) — el modelo target para RL training
- [ ] Correr subsets mas grandes (all) para scores mas robustos
- [ ] DiscoveryBench adapter (requiere LLM-judge scoring)
- [ ] Comparar con scores publicados en papers originales
