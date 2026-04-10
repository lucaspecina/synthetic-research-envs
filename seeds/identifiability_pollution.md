# Seed: Is the Causal Effect Identifiable? Pollution and Asthma

## Type
Epistemological / identifiability (scenario #20)

## Domain
Environmental epidemiology / causal inference methodology

## Study design
Ecological study with aggregate data on air pollution and childhood asthma
prevalence across 200 neighborhoods. Only proxy measures of exposure available.
The research question is epistemological: CAN the causal effect be estimated
with available data, or is additional measurement needed?

## Variables
- PM2.5 proxy (neighborhood-level estimate, not individual exposure)
- Childhood asthma prevalence (aggregate, not individual)
- Traffic density
- Industrial zone proximity
- Wind patterns (instrument candidate)
- Temperature
- Socioeconomic status
- Healthcare access
- Green space coverage
- Indoor exposure habits (NOT measured — latent)
- Genetic susceptibility (NOT measured — latent)

## Key findings to inspire
- The causal effect of PM2.5 on asthma is NOT identifiable with current data
- Reason 1: PM2.5 proxy has measurement error correlated with industrial zone
  (which directly affects asthma via other pollutants)
- Reason 2: aggregate data can't separate individual-level effect from
  ecological fallacy
- Wind variation could serve as an instrument for PM2.5 exposure
- Individual exposure monitoring would solve both problems
- Genetic susceptibility is a latent effect modifier but not a confounder

## Research questions
- Is the PM2.5 → asthma causal effect identifiable from available data?
- If not, WHY not? What specific threats to identification exist?
- What additional measurements would make it identifiable?
- Can wind patterns serve as an instrumental variable?
- Is the inability to identify the effect the same as the effect not existing?

## Causal complexity
- The ANSWER is about identification, not estimation
- Measurement error in exposure creates bias that can't be removed by adjustment
- Ecological fallacy: neighborhood-level associations ≠ individual-level effects
- Latent variables that CAN'T be adjusted for
- Instrument validity depends on exclusion restriction (does wind affect asthma
  only through PM2.5?)
- The correct answer may be "we can't know with this data" — which is
  scientifically valuable
- Distinguishing "not identifiable" from "no effect" is key
