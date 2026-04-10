# Seed: Selection Bias in Body Camera Deployment

## Type
Selection bias as primary finding (scenario #11)

## Domain
Criminology / program evaluation / observational data

## Study design
A police department rolled out body-worn cameras (BWCs) to 600 officers over
two years. Deployment was NOT random: officers with more citizen complaints
were equipped first. A naive analysis shows BWC officers have MORE use-of-force
incidents, not fewer. The research question is whether this represents a real
effect or selection bias, and whether the data can distinguish the two.

## Variables
- Body camera deployed (0/1)
- Use-of-force incidents (count per quarter)
- Prior complaint history (continuous)
- Years of service
- Patrol zone risk score (continuous)
- Shift type (day/night/weekend)
- Civilian interaction volume (count)
- Officer performance rating (continuous)
- Disciplinary actions (count)

## Key findings to inspire
- Crude association: BWC officers have 40% MORE use-of-force incidents
- This is pure selection bias: high-complaint officers got cameras first
- After adjusting for prior complaints + zone risk: BWC reduces force by 15%
- The FINDING here is the bias mechanism itself, not just the adjusted effect
- Additional insight: the selection rule (complaint-based) creates a collider
  structure if conditioning on "currently under investigation"

## Why this is interesting for SREG
The claim the solver should make is NOT just "BWC reduces force" but
"the naive estimate is biased upward by selection, and the direction of
bias reverses the sign." This is a methodological finding about the data
generation process, not just a causal effect estimate. The SQs should
probe the selection mechanism, not just the treatment effect.
