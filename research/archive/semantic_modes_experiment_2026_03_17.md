# Experimento: Modos semanticos — Vaca Muerta + Football (2026-03-17)

> **Status:** hallazgo empirico activo. Informa A3, A10-A12, I2 en TODO.md.

## Setup

Dos seeds, 3 modos semanticos cada uno. Misma BN, mismos datos, mismas
preguntas — solo cambian nombres de variables.

- **Solver:** gpt-5.2-codex (reasoning model)
- **Orchestrator:** gpt-5.4
- Archivos: `experiments/{vaca_muerta,football}_{realistic,abstract,fictional}/`

### Vaca Muerta (primera corrida — CON research_actions, bugs activos)
- **DAG:** 21 nodos, 1 latente, 5 tasks
- **Eval types:** causal_effect, best_intervention, compare_interventions,
  next_best_observation, infer_latent_cause
- **Problemas activos:** verifier no validaba keys, verdict invertido para
  choice types, research_actions + budget activos, NBO incluido

### Football (corrida limpia — SIN research_actions, bugs fixeados)
- **DAG:** 16 nodos, 2 latentes, 4 tasks
- **Eval types:** causal_effect, infer_latent_cause, should_condition, infer_target
- **Fixes aplicados:** verifier keys validadas, verdict corregido, research_actions
  eliminadas, NBO deprioritizado, tabla de formatos en prompt

## Resultados

### Vaca Muerta (con research_actions — datos contaminados)

| Modo | Avg | causal_eff | best_int | compare | NBO | latent |
|---|---|---|---|---|---|---|
| Realistic | 0.425 | 1.07 POOR | 0.51 POOR | 0.0 GOOD | 0.0 GOOD* | 0.55 POOR |
| Fictional | **0.142** | **0.17 OK** | 0.0 GOOD | 0.0 GOOD | 0.0 GOOD* | 0.55 POOR |
| Abstract | 6.69 | 31.7 POOR** | 0.0 GOOD* | 0.0 GOOD* | 0.0 GOOD* | 1.71 POOR |

(*) Verdict invertido — 0.0 en choice types = INCORRECTO, no GOOD.
(**) Bug verifier: keys no validadas → KL=31.7 (ya fixeado).

### Football (limpio, sin research_actions)

| Modo | Avg | causal_eff | latent | should_cond | infer_target |
|---|---|---|---|---|---|
| Realistic | **0.094** | 0.264 OK | 0.105 OK | 0.0 POOR | **0.009 GOOD** |
| Abstract | 0.149 | **0.008 GOOD** | 0.296 OK | 0.0 POOR | 0.292 OK |
| Fictional | 0.166 | 0.023 GOOD | **0.085 GOOD** | 0.0 POOR | 0.556 POOR |

## Hallazgos

### 1. Sin research_actions, la diferencia entre modos se achica mucho

Con research_actions (Vaca Muerta): rango 0.14-6.69 (47x diferencia).
Sin research_actions (Football): rango 0.09-0.17 (1.8x diferencia).

Las research_actions contaminaban la comparacion: realistic gastaba budget en
observe/intervene, fictional usaba python_exec. Ahora todos tienen las mismas
herramientas y las diferencias vienen de como el solver interpreta las preguntas.

### 2. Fictional sigue siendo el modo con mejor razonamiento cualitativo

Aunque los scores son similares, el PROCESO es diferente:

**Vaca Muerta fictional:** unico modo con backdoor adjustment genuino.
Computo P(shedding|do(pulse_crest)) ajustando por disturbance_loading.

**Football fictional:** conditional independence por niveles (Cramer's V
estratificado por force_fade). Intento genuino de detectar confounding.

**Football realistic:** crosstabs y marginales. Score bueno por coincidencia
estadistica (marginal de tactical_drop ~ causal posterior de physical_drop).

### 3. Realistic puede ganar por coincidencia, no por razonamiento

Football realistic obtuvo 0.094 (el mejor) pero:
- Q1: computo marginal de la variable equivocada (tactical vs physical)
- Q4: computo marginal que coincide con la posterior causal
- Q3: respondio "pre_match_stress" en vez de "yes"/"no" → POOR

El score no captura la calidad del razonamiento. Un score bueno obtenido
por coincidencia estadistica no indica investigacion genuina.

### 4. should_condition falla en TODOS los modos (0.0 POOR x3)

Ninguno de los 3 solvers respondio "yes" o "no". Respuestas: "pre_match_stress",
"V10", "route_shift_turbulence=stable". El solver no entiende que es una
pregunta yes/no sobre si condicionar en una variable. Conecta con A10.

### 5. Abstract ya no es catastrofico (post-fix)

Con el verifier arreglado, abstract paso de 6.69 a 0.149. En football,
incluso gano en causal_effect (0.008 GOOD). El solver abstract puede
funcionar cuando las preguntas son claras, pero sigue siendo el peor en
tareas que requieren interpretacion (infer_latent, infer_target).

### 6. Priors de dominio: depende del dominio

- **Oil & gas (Vaca Muerta):** priors DANIAN — el solver invierte la direccion
  de la intervencion por conocimiento de pretraining.
- **Football:** priors son neutros o ligeramente utiles — no invierten la
  direccion pero tampoco fuerzan investigacion.

El efecto de contaminacion por priors no es universal. Depende de cuanto
el conocimiento de pretraining del solver conflicte con la BN sintetica.

## Bugs encontrados y fixeados durante el experimento

1. **Verifier: keys no validadas en case mode** → fixeado (agent.py)
2. **Verdict invertido para choice types** → fixeado (generate_src.py, solve_existing.py)
3. **MAX_PARENTS=4 insuficiente** → subido a 5 (dag_spec.py)
4. **max_iterations=10 insuficiente** → subido a 15 (orchestrator.py)
5. **Research_actions en case mode** → eliminadas (prompts.py, agent.py)
6. **NBO en orchestrator** → deprioritizado
7. **generate_from_plan falla si una task falla** → resiliencia per-task
8. **Budget en outputs** → eliminado

## Conclusiones

1. **fictional es el modo que mas fuerza investigacion genuina**, pero la
   ventaja en score es chica cuando las herramientas son iguales.
2. **El score numerico no captura calidad de razonamiento.** Realistic puede
   ganar por coincidencia. Necesitamos metricas de proceso.
3. **should_condition necesita mejor prompting** o rediseno del formato.
4. **Abstract es viable** post-fix, pero sigue siendo el peor en tareas
   que requieren interpretacion semantica.
5. **Las research_actions eran la mayor fuente de ruido** en la comparacion.
   Eliminarlas fue la decision correcta.

## Proximos pasos

- [ ] Replicar con un tercer seed (otro dominio) para confirmar patrones
- [ ] Mejorar should_condition (formato? rediseno de la pregunta?)
- [ ] Explorar metricas de proceso (no solo score funcional)
- [ ] Considerar si abstract tiene valor para training RL (sin priors)
