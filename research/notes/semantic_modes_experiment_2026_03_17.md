# Experimento: 3 modos semanticos de Vaca Muerta (2026-03-17)

> **Status:** hallazgo empirico. Informar decisiones en A3 y I2 de TODO.md.

## Setup

- **Seed:** Vaca Muerta (frac-driven sanding, oil & gas)
- **DAG:** 21 nodos, 1 latente (geomechanical_susceptibility), 5 tasks
- **Eval types:** causal_effect, best_intervention, compare_interventions,
  next_best_observation, infer_latent_cause
- **Solver:** gpt-5.2-codex (reasoning model)
- **Orchestrator:** gpt-5.4
- **Misma BN, mismos datos, mismas preguntas.** Solo cambian nombres de variables.
- Archivos: `experiments/vaca_muerta_{realistic,abstract,fictional}/`

## Resultados

| Modo | Avg score | Budget | causal_eff | best_int | compare | NBO | latent |
|---|---|---|---|---|---|---|---|
| Realistic | 0.425 | 12/12 | 1.07 POOR | 0.51 POOR | 0.0 GOOD | 0.0 GOOD | 0.55 POOR |
| Fictional | **0.142** | 11/12 | **0.17 OK** | 0.0 GOOD | 0.0 GOOD | 0.0 GOOD | 0.55 POOR |
| Abstract | 6.69 | **0/12** | 31.7 POOR* | 0.0 GOOD* | 0.0 GOOD* | 0.0 GOOD* | 1.71 POOR |

(*) Abstract Q1 = 31.7 por bug del verifier (keys no validadas, ya fixeado).
(*) Abstract Q2-Q4 GOOD = artefacto del verifier: respuestas como "mediator"
y "0.1875" no deberian scored GOOD.

## Hallazgos

### 1. Priors de dominio envenenan el razonamiento causal (realistic)

El solver "sabe" de oil & gas:
- **Q2:** Elige `fracture_peak_pressure=high` como mejor intervencion. DIRECCION
  INVERTIDA. High pressure AUMENTA sanding (P(no)=0.376). La correcta es
  `interference_loading=low` (P(no)=0.731).
- **Q1:** Encuentra sample_id 63 que matchea, declara P(sanding=no)=1.0.
  Un investigador real JAMAS daria un point estimate de un solo caso.

### 2. Fictional fuerza investigacion genuina

Sin priors de dominio, el solver no puede recurrir a conocimiento de pretraining:
- **Unico modo con backdoor adjustment.** Computo P(shedding|do(pulse_crest))
  ajustando por disturbance_loading. Razonamiento causal genuino.
- **Q2:** Eligio `disturbance_loading=low` — direccion correcta, basada en datos.
- **Q1:** Filtro a 21 filas que matchean → P(no)=0.714 (score 0.17 vs 1.07
  del realistic). Mucho mas razonable.

### 3. Abstract no quita priors — quita comprension

El solver no puede parsear las preguntas con variables V1/V2/V3:
- **Q1:** Respondio con P(V2) — la variable EQUIVOCADA. Keys {medium, high,
  low, not_measured} cuando necesitaba {no, yes}. Score 31.7 (bug aparte).
- **Budget 0/12:** No intento ni una sola research_action.
- **Q2-Q4:** Submissions invalidas: "mediator", "0.1875", "V20=not_measured".

### 4. Errores de formato son transversales

En los 3 modos el solver lucha con formatos de submission. 2-4 iteraciones
perdidas en errores de formato antes de lograr submitir.

### 5. infer_latent_cause falla en todos los modos

Score 0.55 en realistic y fictional, 1.71 en abstract. El solver siempre
responde con point mass (P(high)=1.0). No expresa incertidumbre. Esto
sugiere un problema del eval type, no del modo semantico.

## Conclusion preliminar

**fictional > realistic > abstract** para evaluar razonamiento cientifico.

- Fictional quita priors de dominio pero mantiene estructura semantica.
  El solver entiende las preguntas y se ve forzado a investigar con datos.
- Realistic permite shortcuts por conocimiento de pretraining.
- Abstract rompe la capacidad de parsear preguntas.

**Limitacion:** N=1 (solo Vaca Muerta). Necesitamos replicar con football
y otros dominios para confirmar el patron.

## Bugs encontrados

1. **Verifier: keys no validadas en case mode** → fixeado (agent.py:921-929)
2. **Verifier: scoring GOOD para respuestas de formato invalido** → pendiente
3. **MAX_PARENTS=4 insuficiente** para football (5-6 padres naturales)

## Proximos pasos

- [ ] Replicar con football (3 modos)
- [ ] Investigar si abstract mejora con mejor prompting
- [ ] Investigar infer_latent_cause (falla en todos los modos)
