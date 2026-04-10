# Seed: Deep Treatment Effect Heterogeneity

## Type
Heterogeneity / personalized medicine (scenario #12)

## Domain
Precision medicine / clinical trials / subgroup analysis

## Study design
Registry of 1000 patients receiving a treatment with high average effect but
enormous variability. Genetic markers, demographics, and clinical features
available. The goal is to identify WHO benefits and who doesn't — not just
whether the treatment "works on average."

## Variables
- Treatment (0/1)
- Age
- Sex
- Genotype A (positive/negative)
- Genotype B (variant 1/2/3)
- Baseline biomarker X (continuous)
- Comorbidity score
- Primary outcome (continuous)
- Adverse event severity
- BMI, smoking status

## Key findings to inspire
- Average treatment effect: +5pp (modest, borderline significant)
- Genotype A positive + biomarker X high: effect = +18pp (strong benefit)
- Genotype A negative: effect = -1pp (no benefit at all)
- In elderly (>70) with comorbidities: adverse events outweigh benefit
- Biomarker X has a threshold (~60th percentile) above which treatment works
- The treatment is being given to everyone, but should only go to a subgroup

## Research questions
- What is the average treatment effect?
- Which patient characteristics modify the treatment effect?
- Can you define a subgroup that benefits significantly?
- Can you define a subgroup where treatment is harmful (net of adverse events)?
- Is there a biomarker threshold for treatment decisions?

## Causal complexity
- Effect modification is the core: the treatment works for SOME, not all
- Multiple interacting moderators (genotype x biomarker x age)
- Adverse events create a second outcome (benefit-risk trade-off in subgroups)
- Data-driven subgroup discovery risks overfitting — calibration matters
- The "right" answer is a decision rule, not a single number
