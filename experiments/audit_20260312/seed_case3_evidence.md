# Research Seed: Evidence-Gathering/Diagnosis Case (Audit Case 3)

## Context

Marine biologists studying coral reef degradation in a fictional archipelago.
Several reefs are showing unexplained bleaching patterns. Researchers have
limited budget to conduct underwater surveys and must decide which observations
to make to diagnose the primary cause of degradation.

## Variables of interest

- `water_temperature`: cool/warm/hot
- `ocean_acidity`: low/moderate/high
- `algae_overgrowth`: absent/moderate/severe
- `fish_diversity`: high/moderate/low
- `coral_coverage`: healthy/stressed/bleached (target)
- `nutrient_runoff`: low/moderate/high
- `tourism_pressure`: minimal/moderate/heavy
- `predator_presence`: abundant/moderate/scarce
- `light_penetration`: good/moderate/poor
- `sediment_load`: low/moderate/high

## Research questions

- Given initial observations, what is the most likely state of coral_coverage?
- What single observation would be most informative to make next to determine
  the state of coral_coverage?
- Which hypothesis best explains the observed pattern: (A) thermal stress is
  the primary driver, (B) nutrient pollution is the primary driver, or
  (C) tourism-related physical damage is the primary driver?

## Constraints

- 10 nodes, all observable
- Medium difficulty
- MUST include eval types: infer_target, next_best_observation, hypothesis_selection
- The case should feel like marine ecology fieldwork with budget constraints
- Clear information gain structure: some observations much more informative than others
