# Seed: Gut Microbiome and Multiple Health Markers

## Type
System mapping / multi-outcome (scenario #7)

## Domain
Biology / microbiome science / systems health

## Study design
Cross-sectional cohort of 600 adults. Gut microbiome composition measured via
16S sequencing, plus blood markers, mood questionnaires, and dietary logs.
No single target variable — the goal is to map the network of relationships
among bacterial features and health outcomes.

## Variables
- Bacterial diversity index (Shannon)
- Firmicutes/Bacteroidetes ratio
- Specific taxa abundance (Lactobacillus, Bifidobacterium, Prevotella)
- Dietary fiber intake
- Recent antibiotic use (0/1)
- Inflammation marker (CRP)
- Glucose metabolism (HbA1c)
- Immune function score
- Mood/wellbeing score
- Digestive symptom score
- Age, BMI, exercise frequency

## Key findings to inspire
- Diversity has causal effect on digestion and immunity, but NOT on mood
  (mood association confounded by diet)
- Antibiotics reduce diversity, indirectly worsening immunity
- Firmicutes/Bacteroidetes ratio affects glucose metabolism but not other markers
- Fiber intake is a confounder (affects both microbiome composition and health directly)
- Some relationships are bidirectional (inflammation affects microbiome too)

## Research questions
- Which bacterial features causally affect which health outcomes?
- Are the observed associations direct or mediated through intermediate markers?
- Does diet confound the microbiome-health associations?
- What is the network structure (who influences who)?
- Which relationships are robust to controlling for lifestyle factors?

## Causal complexity
- NO single target: 5 health outcomes, each with different bacterial drivers
- System mapping: the goal is to discover the network, not test one hypothesis
- Confounders: diet and exercise affect both microbiome and health
- Mediation: diversity -> immune function -> inflammation (chain)
- Bidirectionality: inflammation may also affect microbiome (not just reverse)
- Calibration: many associations will be null — knowing what's NOT connected matters
