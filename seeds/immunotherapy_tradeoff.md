# Seed: Immunotherapy Survival vs Toxicity Trade-off

## Type
Multi-outcome trade-off (scenario #2)

## Domain
Oncology / cancer immunotherapy / clinical decision-making

## Study design
Observational registry of 800 advanced cancer patients receiving one of three
regimens: high-dose immunotherapy (A), moderate-dose (B), or standard
chemotherapy (control). Follow-up at 12 months with survival, toxicity, and
quality of life endpoints.

## Variables
- Treatment arm (A / B / control)
- Tumor stage (III / IV)
- Histologic subtype
- PD-L1 expression level (biomarker)
- Tumor mutation burden
- Age, performance status (ECOG)
- 1-year survival (binary)
- Severe toxicity grade 3+ (binary)
- Quality of life score (continuous)
- Immune-related adverse events
- Prior treatment lines

## Key findings to inspire
- Regimen A: best survival (+12pp) but worst toxicity (+18pp grade 3+)
- Regimen B: moderate gains (+8pp survival, +7pp toxicity)
- In high PD-L1 patients, A dominates (high survival, manageable toxicity)
- In low PD-L1 patients, B preferred (toxicity not justified by small gain)
- Quality of life: A worst short-term, catches up by month 6 in responders

## Research questions
- What is the survival benefit of each regimen vs control?
- What is the toxicity cost of each regimen?
- For which patient subgroups does the survival/toxicity trade-off favor A vs B?
- Does PD-L1 expression modify the treatment effect on both outcomes?
- Is there a biomarker threshold that separates "treat aggressively" from "don't"?

## Causal complexity
- Multi-outcome: survival and toxicity are both important, potentially competing
- Confounding by indication: sicker patients may get more aggressive treatment
- Effect modification: biomarker modulates treatment effect on BOTH outcomes
- Trade-off reasoning: the "right" answer depends on which outcome you prioritize
- No single correct conclusion: different value frameworks give different recommendations
