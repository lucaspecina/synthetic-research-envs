# Seed: Predicting Sanding Risk in Vaca Muerta Wells

## Type
Predictive / classification (scenario #15-like)

## Domain
Upstream oil & gas / hydraulic fracturing / operational risk

## Study design
Registry of 800 parent-child well interference events in Vaca Muerta shale.
Each record is a parent well exposed to fracturing operations on a nearby
child PAD. The goal is purely predictive: build the best classifier for
sanding events in the parent well BEFORE the child PAD operates. This is
NOT about causal attribution — it's about actionable early warning.

## Variables
- Sanding event (0/1) — TARGET, ~18% prevalence (imbalanced)
- Max pressure during child frac (kg/cm2)
- PEM pressure (kg/cm2)
- Pressure ratio (max/PEM)
- Parent well production time (months)
- Stimulated length (m)
- Proppant loading (lbs/ft)
- Child fluid volume (bbl/ft)
- PAD spacing distance (m)
- Min horizontal stress SHmin (kg/cm2)
- True vertical depth (m)
- Well inclination (degrees)
- Zone (categorical: A, B, C, D)
- Formation level (upper/middle/lower)
- Level match flag (parent level matches child PAD target)
- Historical zone risk score (continuous, 0-1)
- Historical coordinate risk score (continuous, 0-1)
- Historical level risk score (continuous, 0-1)
- Count of prior child PADs on this parent

## Key findings to inspire
- Best achievable AUC: ~0.82 (good but not perfect — irreducible uncertainty)
- Top 3 predictive features: pressure ratio, PAD spacing, historical zone risk
- Historical risk scores are strong predictors (past events predict future)
- Zone is important but interacts with depth — Zone B at shallow depth is safe,
  Zone B at deep is high risk
- Adding geological variables (SHmin, depth) improves AUC from 0.75 to 0.82
- Model performs well in Zones A/B (AUC 0.88) but poorly in Zone D (AUC 0.65)
  — Zone D has fewer samples and different geology
- Proppant loading has low marginal predictive value despite being operationally
  important (it's correlated with other features)
- A simple logistic regression with 5 features achieves AUC 0.78 — only
  modest gain from complex models

## Research questions
- What is the best achievable prediction accuracy (AUC) for sanding events?
- Which features are most predictive of sanding?
- Does the model generalize across zones, or does it need zone-specific models?
- Is there a subgroup where prediction fails (high uncertainty)?
- Do historical risk scores add value beyond operational/geological variables?
- How does a simple model (logistic regression) compare to a complex one?
- What is the minimum set of features for acceptable performance (AUC > 0.75)?

## Causal complexity
- This is PREDICTIVE, not causal — correlation is fine if it predicts well
- Feature importance != causal importance (historical risk scores predict
  but don't cause sanding)
- Confounders don't matter for prediction — only for intervention
- Class imbalance (18% positive) requires appropriate metrics (AUC, not accuracy)
- Zone D poor performance: is it data scarcity or genuinely different process?
- Calibration matters: predicted probabilities should match observed rates
- The value is in the RANKING of risk, not in understanding mechanism
