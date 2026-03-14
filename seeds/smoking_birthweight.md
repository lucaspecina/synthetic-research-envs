# Paper Seed: Smoking and Birth Weight

## Source
Classic epidemiological finding, studied extensively since 1957 (Simpson et al.).
Modern causal analysis: Hernandez-Diaz, Schisterman, Hernan (2006) "The Birth Weight Paradox Uncovered?"
American Journal of Epidemiology.

## Domain
Perinatal epidemiology — fictional research station on island archipelago "Isla Serena"

## Research problem
Maternal smoking during pregnancy is associated with lower birth weight. Low birth weight
is associated with higher infant mortality. Yet paradoxically, among low birth weight infants,
maternal smoking appears PROTECTIVE — smokers' low-birth-weight babies have LOWER mortality
than non-smokers' low-birth-weight babies. This is the "birth weight paradox."

The resolution involves a collider bias: birth weight is a collider between smoking and
an unmeasured birth defect. Conditioning on low birth weight opens a non-causal path.

## Causal structure (ground truth for the BN)

### Variables
- `maternal_smoking`: observable, states: [nonsmoker, light, heavy]
- `birth_defect`: LATENT, states: [absent, present]  — unmeasured congenital condition
- `birth_weight`: observable, states: [very_low, low, normal, high]
- `prenatal_care`: observable, states: [none, basic, comprehensive]
- `maternal_age`: observable, states: [young, middle, advanced]
- `gestational_age`: observable, states: [preterm, early_term, full_term]
- `infant_mortality`: TARGET, states: [survived, deceased]

### Causal edges
- maternal_smoking -> birth_weight (smoking reduces weight)
- maternal_smoking -> gestational_age (smoking increases preterm risk)
- birth_defect -> birth_weight (defects reduce weight)
- birth_defect -> infant_mortality (defects increase mortality)
- maternal_smoking -> infant_mortality (direct small effect)
- birth_weight -> infant_mortality (low weight increases mortality)
- gestational_age -> birth_weight (preterm = lower weight)
- gestational_age -> infant_mortality (preterm increases mortality)
- maternal_age -> prenatal_care (older mothers get more care)
- maternal_age -> birth_defect (advanced age increases defect risk)
- prenatal_care -> birth_weight (better care improves weight)

### Key causal features
- birth_weight is a COLLIDER between smoking and birth_defect
- Conditioning on birth_weight creates spurious association (paradox)
- birth_defect is LATENT — cannot be directly observed
- prenatal_care is a mediator (maternal_age -> prenatal_care -> birth_weight)

## Research questions (for the SRC)
1. What is the probability distribution of infant_mortality given observed evidence? (infer_target)
2. If we could intervene on maternal_smoking (set to nonsmoker), how would infant_mortality change? (causal_effect)
3. Should we condition on birth_weight when estimating the effect of smoking on mortality? (should_condition — answer: NO, it's a collider)
4. What latent factor best explains why some low-birth-weight babies survive while others don't? (infer_latent_cause)
5. What variables should we control for when estimating smoking's effect on mortality? (adjustment_set)

## Expected difficulty
Medium-high. The collider bias is subtle and requires understanding of causal structure.
The latent birth_defect makes direct observation impossible.
