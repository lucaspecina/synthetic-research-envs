---
name: validate
description: Run E2E validation with diverse seeds. The REAL test of any change. Use after implementation to check if it actually works.
---

## Validacion E2E — la unica que importa

Unit tests confirman que el codigo no rompe. Esta skill confirma que el
sistema **produce investigacion real**. Es el paso PROBAR del ciclo
PENSAR -> PROBAR -> ANALIZAR.

## 7 seeds de referencia (diversidad maxima)

| Seed | Tipo | Para que |
|---|---|---|
| `vaca_muerta.md` | Causal clasico | Baseline — lo que ya funciona |
| `vaca_muerta_predictive.md` | Predictivo | Lo que NO funciona hoy |
| `social_media_profiles.md` | Descriptivo | Sin hipotesis causal |
| `identifiability_pollution.md` | Epistemologico | Pregunta de identificabilidad |
| `immunotherapy_tradeoff.md` | Multi-outcome | Trade-off supervivencia vs toxicidad |
| `microbiome_system_mapping.md` | System mapping | Red de relaciones |
| `selection_bias_police.md` | Selection bias | El sesgo ES el hallazgo |

## Como ejecutar

### Generar un caso (sin solver)
```bash
python scripts/generate_src.py --seed-file seeds/SEED.md -o results/NOMBRE/ --inspect
```

### Generar + solver completo
```bash
python scripts/generate_src.py --seed-file seeds/SEED.md -o results/NOMBRE/ --oi
```

### Evaluar calidad
Usar `/eval` sobre el resultado.

## Reglas

- **MINIMO 3 seeds distintas** por batch de validacion.
- **NUNCA solo causal simple.** Si solo probaste vaca_muerta, no validaste.
- Siempre incluir al menos 1 tipo que hoy NO funciona bien (descriptivo,
  epistemologico, system mapping).
- Documentar resultados en `results/` con nombre descriptivo.
- Si el cambio afecta SQs: comparar SQs v1 vs v2.
- Si el cambio afecta claims: comparar specs catalogo vs directo.

## Escenarios completos

Para la rubrica de 20 escenarios de validacion:
`research/synthesis/investigation_scenarios_rubric.md`
