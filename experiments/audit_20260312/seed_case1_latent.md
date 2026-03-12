# Research Seed: Latent/Confounding Case (Audit Case 1)

## Context

A study of neonatal health outcomes in rural hospitals across a fictional tropical region.
Some hospitals report unexpectedly high rates of jaundice despite similar demographics.
Researchers suspect an unobserved environmental factor (water contamination from
nearby mining operations) may confound several observed relationships.

## Variables of interest

- `birth_weight`: newborn weight at delivery (low/normal/high)
- `gestational_age`: weeks at delivery (preterm/term/post_term)
- `maternal_nutrition`: nutritional status during pregnancy (poor/adequate/good)
- `hospital_altitude`: elevation of the hospital (low/medium/high)
- `prenatal_visits`: number of prenatal checkups (few/moderate/many)
- `jaundice_severity`: neonatal jaundice outcome (none/mild/severe)
- `breastfeeding_initiation`: time to first breastfeed (early/delayed)
- `delivery_method`: type of delivery (vaginal/cesarean)
- `maternal_anemia`: iron levels during pregnancy (normal/low/deficient)
- LATENT: `water_contamination` — unobserved environmental exposure affecting
  both maternal health and neonatal outcomes, creating confounding

## Research questions

- Is the association between hospital_altitude and jaundice_severity confounded
  by water_contamination?
- What variables should be controlled for when estimating the effect of
  maternal_nutrition on birth_weight?
- What hidden factor could explain why hospitals at similar altitudes have
  different jaundice rates?
- Should we condition on delivery_method when studying the effect of
  gestational_age on jaundice_severity?

## Constraints

- 10-12 nodes, at least 1 latent variable
- Medium-high difficulty
- MUST include eval types: infer_latent_cause, adjustment_set, should_condition
- The case should feel like a perinatal epidemiology study
- Strong confounding paths through the latent variable
