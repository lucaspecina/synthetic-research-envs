# Seed: Confounding by Indication in Drug Efficacy

## Type
Confounding as primary objective (scenario #10)

## Domain
Pharmacoepidemiology / causal inference / observational studies

## Study design
Hospital registry of 1200 patients with a serious condition. Drug X is
prescribed at physician discretion (not randomized). Patients who receive
Drug X tend to have worse outcomes — but Drug X is preferentially given to
sicker patients. The research question is whether this is confounding, and
what the true causal effect is.

## Variables
- Baseline severity score (continuous)
- Drug X prescribed (0/1)
- Age
- Comorbidity count
- Clinical indication strength
- Hospital type (teaching/community)
- Clinical outcome (continuous, higher = better)
- Dosage (among treated)
- Time to treatment

## Key findings to inspire
- Crude association: Drug X users have WORSE outcomes (OR = 1.02, appears harmful)
- After adjusting for severity: Drug X has protective effect (OR = 0.72)
- Minimum adjustment set: {severity, comorbidities}
- The drug IS effective — it's just given to sicker patients
- Hospital type is NOT a confounder (doesn't affect both treatment and outcome)

## Research questions
- Is there confounding by indication in the Drug X → outcome relationship?
- What variables confound the association?
- What is the correct adjustment set for estimating the causal effect?
- What is the true causal effect of Drug X after proper adjustment?
- Are there variables that look like confounders but aren't?

## Causal complexity
- Core challenge: the naive analysis gives the WRONG conclusion
- The correct answer requires identifying the confounding mechanism
- Multiple potential adjustment sets (some valid, some not)
- Collider bias risk: adjusting for intermediate variables can introduce bias
- The research objective IS about causal identification, not just estimation
- Success = understanding WHY the naive estimate is biased + fixing it
