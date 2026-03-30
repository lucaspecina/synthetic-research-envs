# Seed: Which Estimator Handles Missing Data Better?

## Type
Methodology comparison / estimator evaluation (scenario #17)

## Domain
Biostatistics / clinical trials / missing data methods

## Study design
A clinical trial with 800 patients measured an outcome at 3 time points.
Dropout is non-random: sicker patients are more likely to drop out, and
dropout correlates with treatment assignment (treated patients with side
effects leave). Three estimators are commonly proposed: complete-case analysis,
last-observation-carried-forward (LOCF), and inverse probability weighting (IPW).
The question is NOT "what is the treatment effect" but "which estimator
gives the least biased answer given this dropout mechanism?"

## Variables
- Treatment assignment (0/1)
- Baseline severity (continuous)
- Outcome at time 1 (continuous)
- Outcome at time 2 (continuous, 20% missing)
- Outcome at time 3 (continuous, 35% missing)
- Dropout indicator (0/1)
- Side effect severity (continuous)
- Age
- Compliance score (continuous)
- Dropout reason (categorical: side_effect, moved, improved, unknown)

## Key findings to inspire
- True treatment effect (if no dropout): -4.2 units (beneficial)
- Complete-case estimate: -2.1 (attenuated — sicker treated patients drop out)
- LOCF estimate: -5.8 (biased in opposite direction — carries forward bad values)
- IPW estimate: -3.9 (closest to truth, but high variance)
- The PATTERN of bias depends on the dropout mechanism, not the method alone
- Key insight: when dropout correlates with both treatment and outcome (MNAR),
  no standard method is unbiased — but IPW is least wrong

## Why this is interesting for SREG
The claims here are about METHOD PROPERTIES, not about the treatment effect
itself. "Complete-case analysis underestimates the effect because dropout is
differential" is a methodological claim. "IPW recovers a less biased estimate
because it reweights for dropout probability" is about the estimator. These
claims don't fit "X causes Y" patterns at all.
