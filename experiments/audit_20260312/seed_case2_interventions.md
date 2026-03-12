# Research Seed: Intervention-Centric Case (Audit Case 2)

## Context

An agricultural experiment station on a fictional volcanic island studying crop
yield optimization. Researchers can intervene on irrigation method, fertilizer
type, and soil treatment. Multiple causal pathways exist between interventions
and yield, with intermediate variables like soil moisture, nutrient absorption,
and pest resistance.

## Variables of interest

- `irrigation_method`: drip/flood/sprinkler
- `fertilizer_type`: organic/synthetic/mixed
- `soil_treatment`: none/composting/biochar
- `soil_moisture`: low/medium/high
- `nutrient_absorption`: poor/moderate/efficient
- `pest_resistance`: weak/moderate/strong
- `root_health`: poor/fair/good
- `flowering_rate`: low/medium/high
- `crop_yield`: low/medium/high (target)
- `weather_pattern`: dry/normal/wet (exogenous)

## Research questions

- What is the causal effect of switching from flood to drip irrigation on crop yield?
- Which single intervention (irrigation, fertilizer, or soil treatment) would
  maximize the probability of high crop yield?
- Compare: does changing fertilizer_type or soil_treatment have a larger effect
  on crop_yield?
- What variables mediate the effect of irrigation_method on crop_yield?

## Constraints

- 10 nodes, no latent variables (all observable)
- Medium difficulty
- MUST include eval types: causal_effect, best_intervention, compare_interventions
- The case should feel like an agricultural field trial
- Multiple intervention points with different pathways to the outcome
