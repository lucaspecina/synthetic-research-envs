# Seed: Competing Mechanisms for Antibiotic Resistance Spread

## Type
Model discrimination / equifinality (scenario #22)

## Domain
Microbiology / epidemiology / causal model comparison

## Study design
Hospital surveillance data on antibiotic-resistant infections across 150
facilities. Two competing hypotheses explain the observed spread pattern:
(A) resistance spreads primarily through patient transfers between hospitals,
(B) resistance emerges independently due to local antibiotic prescribing
pressure. Both mechanisms produce similar aggregate trends, but they have
different observable implications for the correlation structure. The question
is which mechanism dominates, or whether both contribute.

## Variables
- Resistance prevalence (continuous, per facility)
- Antibiotic prescribing intensity (continuous)
- Patient transfer volume (continuous)
- Facility size (beds)
- ICU proportion (continuous)
- Regional clustering index (continuous)
- Infection control spending (continuous)
- Staff-to-patient ratio (continuous)
- Neighboring facility resistance (spatial lag)
- Facility type (teaching/community/rural)

## Key findings to inspire
- Both mechanisms contribute, but transfer dominates (60/40 split)
- Key discriminating evidence: neighboring_resistance predicts local resistance
  EVEN after controlling for local prescribing (supports transfer mechanism)
- Prescribing intensity explains within-facility temporal variation but NOT
  between-facility spatial variation (supports local mechanism for emergence,
  transfer for spread)
- The correlation between prescribing and resistance is partly confounded by
  facility type (teaching hospitals prescribe more AND receive more transfers)

## Why this is interesting for SREG
The SQs here should be about DISCRIMINATING between mechanisms, not estimating
a single effect. "Does the spatial pattern support transfer over independent
emergence?" is a model comparison question. "Is the prescribing-resistance
correlation confounded by facility type?" helps discriminate. These are
claims about model structure, not about individual variable effects.
