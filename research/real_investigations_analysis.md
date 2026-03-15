# What Makes REAL Scientific Investigations Different from Toy Benchmarks

> Deep analysis of 7 real papers across 6 domains. Focus: the WORKFLOW of
> investigation, not just the findings. What do researchers ACTUALLY DO?

---

## Executive Summary

After analyzing 7 real scientific investigations across epidemiology, ecology,
clinical medicine, social science/education, engineering/materials science, and
economics, several patterns emerge that fundamentally distinguish real research
from toy benchmarks:

1. **Data is never clean or complete.** Every study fights measurement error,
   missing values, incompatible coding systems, and spatial/temporal misalignment.
2. **The core challenge is identification, not computation.** The hard part is
   figuring out WHAT to compare to WHAT, not running the regression.
3. **Researchers make dozens of consequential decisions.** Model specification,
   confounder selection, sample restriction, sensitivity checks -- each one
   can reverse the conclusion.
4. **Multiple data sources are the norm.** Real studies combine 3-8 heterogeneous
   datasets that weren't designed to work together.
5. **Validation is multi-layered.** Not just "did I get the right answer" but
   "would the answer change if my assumptions were wrong?"
6. **Constraints shape the investigation.** Ethics, cost, data availability, and
   feasibility determine what questions can even be asked.
7. **The causal question is always lurking.** Even "descriptive" studies are
   motivated by a causal question they can't fully answer.

---

## Paper 1: Epidemiology -- Air Pollution and Cardiovascular Disease

### Citation
Wei Y, Wang Y, Di Q, et al. "Long-Term Exposure to Air Pollution Below
Regulatory Standards and Cardiovascular Diseases Among US Medicare Beneficiaries:
A Double Negative Control Approach." PMC10690329.

URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC10690329/

### Domain
Environmental epidemiology / large observational cohort

### 1. Type of Investigation
Large-scale retrospective cohort study using administrative health data linked
with satellite-derived pollution exposure models. Purely observational -- no
intervention possible.

### 2. What Data They Had

**6 distinct data sources merged together:**
- Medicare denominator files (demographics, death, ZIP code) -- ~63 million beneficiaries
- Medicare MEDPAR hospital discharge claims (hospitalizations by ICD code)
- Ensemble air pollution prediction models (1km x 1km grids, daily, from satellite + transport models)
- Census/American Community Survey (socioeconomic variables by ZIP)
- CDC BRFSS (behavioral risk factors by ZIP -- smoking, BMI)
- gridMET (meteorological data -- temperature, humidity)

**Data problems:**
- Exposure assigned at ZIP code level, not individual level -- people spend only
  ~69% of time at home (exposure misclassification)
- Hospital discharge diagnoses miss mild cases (non-differential bias toward null)
- ZIP codes don't have polygon boundaries -- some assigned by nearest grid cell
- Moderate correlation between PM2.5 and NO2 creates collinearity risk
- Building characteristics not captured by neighborhood metrics

### 3. What the Researchers ACTUALLY DID

**Step 1: Define the study population**
- Restricted to beneficiaries aged 65+ in areas with CONSISTENTLY low pollution
  for entire period 2000-2016
- Multiple thresholds tested: PM2.5<10 ug/m3, NO2<40 ppb, NO2<20 ppb, O3<45 ppb, O3<40 ppb
- Excluded areas that had higher exposure in ANY prior year

**Step 2: Build the exposure model**
- Aggregated daily 1km predictions to annual ZIP code averages
- Three ensemble machine learning models combined
- Validated via 10-fold cross-validation
- O3: warm-season only (Apr-Sep) because health impacts seasonal

**Step 3: Ascertain outcomes**
- Identified stroke, heart failure, atrial fibrillation using ICD-9 and ICD-10 codes
- Computed ZIP-level annual counts

**Step 4: Assemble 22 confounders**
- SES: percent Black/Hispanic, poverty, education, income, housing values, pop density
- Behavioral: lung cancer rate (smoking proxy), ever-smoker prevalence, BMI
- Meteorological: summer/winter temperature and humidity
- Healthcare access: HbA1c testing, lipid panels, eye exams, mammography rates,
  ambulatory visits, distance to nearest hospital
- Temporal: admission year as categorical (control for time trends)

**Step 5: Fit models**
- Quasi-Poisson regression with ZIP-level aggregated counts
- Single-pollutant and three-pollutant models
- THEN: the key innovation -- double negative control adjustment

**Step 6: Double negative control**
This is the creative methodological core:
- **Negative exposure control (Z):** Air pollution in the year AFTER the outcome.
  Cannot cause this year's hospitalization, but IS affected by unmeasured confounders.
- **Negative outcome control (W):** Hospitalizations in the year BEFORE current
  exposure. Cannot be caused by this year's exposure, but IS correlated with
  unmeasured confounders.
- Together, Z and W allow estimating the bias from unmeasured confounding and
  subtracting it out.

**Step 7: Stratified analyses**
- By age group (65-74, 75-84, 85+)
- By sex, race, Medicaid eligibility
- Pairwise coefficient comparisons tested statistically

### 4. What Experiments Could They Run?
**None.** You cannot randomize humans to pollution exposure. The entire
investigation is about extracting causal signal from observational data using
clever identification strategies (negative controls).

### 5. What Made This Investigation HARD
- **Unmeasured confounding is the central threat.** The double negative control
  exists precisely because you can never fully adjust for everything.
- **Exposure misclassification:** ZIP code averages != personal exposure
- **Low-concentration signal:** Effects are tiny (2.25% increase per 1 ug/m3),
  requiring enormous samples to detect reliably
- **Multiple comparisons:** Testing 3 pollutants x 3 outcomes x multiple thresholds
- **Ecological fallacy:** ZIP-level analysis may not reflect individual risk
- **Co-pollutant confounding:** PM2.5 and NO2 correlated, hard to separate

### 6. Questions Asked
- **Causal:** Does low-level air pollution CAUSE cardiovascular hospitalizations?
- **Dose-response:** Is there a threshold below which pollution is safe?
- **Effect modification:** Does the effect differ by age/sex/race/SES?

### 7. Validation
- Models with vs. without negative controls (compare bias magnitude)
- Single vs. three-pollutant models
- Multiple exposure thresholds
- Stratified analyses for consistency

### What Makes This REAL vs. Toy
A toy version: "Given this dataset, estimate the effect of X on Y controlling
for Z." Real version: You have to DECIDE which of 22 potential confounders to
include, INVENT a novel identification strategy (double negative control),
WORRY about whether your exposure model is biased, TEST whether results are
robust to different analytic choices, and ACKNOWLEDGE that you still can't be
fully sure it's causal.

---

## Paper 2: Ecology -- Biodiversity and Ecosystem Productivity

### Citation
Dee LE, et al. "Clarifying the effect of biodiversity on productivity in
natural ecosystems with longitudinal data and methods for causal inference."
Nature Communications, 2023.

URL: https://www.nature.com/articles/s41467-023-37194-5

### Domain
Ecology / biodiversity-ecosystem functioning (BEF)

### 1. Type of Investigation
Observational study of natural grassland ecosystems using longitudinal data
with econometric causal inference methods borrowed from economics. NOT a
controlled experiment.

### 2. What Data They Had
- Global grassland dataset with plot-level species richness and productivity
  measured over multiple years
- Longitudinal panel structure: same plots observed repeatedly over time
- Natural variation in biodiversity (not experimentally manipulated)

**Data problems:**
- Non-random assignment: biodiversity is endogenous (plots with more species
  may differ systematically from those with fewer)
- Reverse causality: productivity might cause biodiversity changes, not just
  the reverse
- Confounders: soil quality, climate, disturbance history all affect both
  biodiversity and productivity
- Spatial autocorrelation between nearby plots

### 3. What the Researchers ACTUALLY DID
This is remarkable because they IMPORTED methods from economics into ecology:

**Step 1: Frame the identification problem**
- Recognized that experimental BEF studies (randomly planting different numbers
  of species) show positive effects, but observational studies are ambiguous
- Core challenge: in nature, biodiversity isn't randomly assigned -- it's a
  consequence of environmental conditions

**Step 2: Apply fixed effects estimation**
- Plot-level fixed effects absorb all time-invariant confounders (soil type,
  elevation, baseline fertility)
- Year fixed effects absorb all common temporal shocks (weather events, regional trends)
- This isolates within-plot, within-year variation

**Step 3: Apply instrumental variables**
- Found instruments that predict biodiversity changes but don't directly
  affect productivity except through biodiversity
- This addresses remaining endogeneity from time-varying confounders

**Step 4: Interpret the surprise result**
- Found NEGATIVE effect: 10% increase in richness DECREASED productivity by 2.4%
- This contradicts decades of experimental BEF literature
- Explained by: in nature, species gains often come from non-native/rare species
  that don't contribute to productivity

### 4. What Experiments Could They Run?
In principle, you could run randomized biodiversity experiments (and many exist),
but they have two problems:
- **Artificial conditions:** Planted gardens don't replicate natural assembly processes
- **Selection of species pools:** Experimenters choose which species to include,
  but in nature, assembly is endogenous

The whole point of this paper was to move BEYOND experiments to observational
causal inference.

### 5. What Made This Investigation HARD
- **Endogeneity is the core problem.** Biodiversity is not randomly assigned
  in nature -- it's caused by the same things that cause productivity.
- **Reverse causality:** Productive sites may accumulate species over time
- **Measurement:** Species richness is a crude measure -- composition matters more
- **Spatial confounding:** Nearby plots share unmeasured environmental drivers
- **Contradicts prior experiments:** The negative result challenges a well-established
  finding, requiring extra scrutiny

### 6. Questions Asked
- **Causal:** Does biodiversity CAUSE productivity in natural systems? (Not just:
  "Is it correlated?")
- **Mechanistic:** Why do observational and experimental results disagree?
- **Policy:** Should conservation efforts focus on species richness per se?

### 7. Validation
- Comparison of naive OLS vs. fixed effects vs. IV estimates (showing how
  estimates change with better identification)
- Testing instrument validity
- Robustness to different species richness measures
- Comparison with experimental results as external validation

### What Makes This REAL vs. Toy
Toy: "Given biodiversity and productivity data, run a regression." Real: The
entire paper is about WHY you can't just run a regression. The researchers had
to import methods from a different field (economics), construct instruments,
argue about identification assumptions, and explain why their result
contradicts 25 years of experimental evidence. The analysis is 10% computation,
90% argumentation about identification.

---

## Paper 3: Clinical Medicine -- RECOVERY Trial (Dexamethasone for COVID-19)

### Citation
RECOVERY Collaborative Group. "Dexamethasone in Hospitalized Patients with
Covid-19 -- Preliminary Report." NEJM, 2020. PMC7383595.

URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC7383595/

### Domain
Clinical medicine / adaptive platform RCT during a pandemic

### 1. Type of Investigation
Multi-center, open-label, adaptive platform randomized controlled trial.
176 NHS hospital sites across UK, enrolling ~15% of ALL hospitalized COVID
patients.

### 2. What Data They Had
- 11,303 randomized patients (6,425 in dexamethasone comparison)
- 2,104 dexamethasone, 4,321 usual care
- Minimal data collection by design (pandemic urgency)
- Follow-up: single online form at discharge/death/28 days
- Supplemented with linkage to NHS registries and national vital statistics

**Data problems:**
- Open-label (no blinding) -- knowledge of assignment could affect behavior
- "Appropriate sample sizes could not be estimated when the trial was being
  planned at the start of the Covid-19 pandemic"
- Minimal data collection: no physiologic, laboratory, or virologic measures collected
- 8% contamination: controls who received dexamethasone anyway

### 3. What the Researchers ACTUALLY DID

**Step 1: Pragmatic protocol design (~days, not months)**
- Protocol drafted to results in ~100 days
- Designed for simplicity: only essential data collected
- Web-based randomization with concealed assignment
- 2:1 ratio (dexamethasone:usual care) -- unusual ratio to increase drug group size

**Step 2: Adaptive multi-arm structure**
- Simultaneously evaluated 6 treatments (dexamethasone, hydroxychloroquine,
  lopinavir-ritonavir, azithromycin, tocilizumab, convalescent plasma)
- Arms opened and closed as evidence accumulated
- 4.5% of dexamethasone group also randomized to tocilizumab

**Step 3: Enrollment with broad criteria**
- Anyone hospitalized with suspected/confirmed COVID-19
- Age restriction removed midway (May 9, 2020)
- Pregnant women eligible
- Only excluded if clinician judged drug definitely indicated or contraindicated

**Step 4: Treatment**
- Dexamethasone 6mg oral or IV, once daily, up to 10 days
- 95% adherence (received >= 1 dose)
- Median 7 days treatment

**Step 5: Primary analysis**
- ITT with Cox regression for mortality, age-adjusted (three categories)
- Kaplan-Meier survival curves
- P-value threshold: 0.01 (not 0.05) to account for multiple comparisons

**Step 6: Pre-specified subgroup analyses**
- By respiratory support level at randomization (the KEY finding)
- By age, sex, days since symptom onset, predicted mortality risk
- Interaction tests for subgroup x treatment

**Step 7: Outcome ascertainment from multiple sources**
- Hospital forms, NHS records, public health registries, national death records
- 98.8-99.0% follow-up completion

### 4. What Experiments Could They Run?
This IS the experiment. But the constraints were severe:
- Open-label (couldn't manufacture placebo fast enough)
- Adaptive design (arms closing/opening in real time)
- Minimal monitoring (pandemic overwhelmed normal trial infrastructure)
- Competing interventions (patients in multiple arms simultaneously)
- Equipoise shifting in real time as evidence accumulated

### 5. What Made This Investigation HARD
- **Pandemic context:** Everything had to be done at unprecedented speed
- **Open-label bias:** Patients and clinicians knew the assignment
- **Adaptive complexity:** Multiple arms, sequential stopping, changing enrollment criteria
- **Clinical heterogeneity:** COVID-19 severity varies enormously -- the drug
  helps severe cases but may HARM mild cases (heterogeneous treatment effects)
- **Contamination:** 8% of controls received the drug anyway
- **Mechanism ambiguity:** Is dexamethasone working via immunosuppression?
  Anti-inflammation? Diuresis? Unclear.
- **Subgroup-specific effects:** Main result masks that benefit is concentrated
  in mechanically ventilated patients (RR 0.64) and absent in those not receiving
  oxygen at randomization (RR 1.19)

### 6. Questions Asked
- **Causal:** Does dexamethasone reduce 28-day mortality?
- **Effect modification:** Does the effect depend on disease severity?
- **Safety:** Does it harm mild cases?
- **Policy (immediate):** Should guidelines change NOW? (They did, same day.)

### 7. Validation
- Sensitivity: analysis restricted to PCR-confirmed cases (89%)
- Adjusted vs. unadjusted estimates
- Subgroup consistency checks
- External replication (other trials confirmed findings)

### What Makes This REAL vs. Toy
Toy: "Treatment group has lower mortality, p < 0.05, drug works." Real: The
AVERAGE effect masks critical heterogeneity -- the drug helps ventilated
patients enormously but may harm mild cases. The open-label design, 8%
contamination, adaptive structure, and impossibility of proper power
calculations all complicate interpretation. The real intellectual work is in
the subgroup analysis, the speed-rigor tradeoff, and translating uncertain
evidence into immediate policy.

---

## Paper 4: Social Science / Education -- School Funding and Achievement

### Citation
"Methodological decisions and their impacts on the perceived relations between
school funding and educational achievement." PMC11583220.

URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC11583220/

### Domain
Education research / quantile regression / ecological fallacy

### 1. Type of Investigation
Cross-sectional observational study using administrative education data from
Florida. Not causal -- the paper's contribution is showing how METHODOLOGICAL
CHOICES change conclusions.

### 2. What Data They Had
- Florida PMRN: 573,869 students in 1,446 public elementary schools (grades 1-6)
- Florida DOE Program Cost Analysis: per-pupil expenditures by school
- 2009-2010 school year
- Student demographics, free/reduced lunch status, reading achievement (FAIR test)

**Data problems:**
- Cannot measure per-student spending -- only school-level aggregates
- Reading assessment has low reliability in grades 1-2 (test-retest r=0.50)
- Cross-sectional: no temporal variation to exploit for causal identification
- Free/reduced lunch as SES proxy is crude (dichotomous, eligibility-based)

### 3. What the Researchers ACTUALLY DID

**Step 1: Operationalize variables (each choice matters)**
- Funding: total program costs per pupil (sum of salaries, benefits, services,
  supplies, capital outlay)
- SES: free/reduced lunch (student-level: binary; school-level: proportion)
- Achievement: standardized residual change scores (Fall to Spring), separately
  by grade

**Step 2: Run three nested models**
- Model 1: Funding only --> NEGATIVE correlation with achievement (Simpson's paradox!)
- Model 2: Funding + SES --> Correlation shifts positive in upper quantiles
- Model 3: Funding + SES + interaction --> Reveals differential effects

**Step 3: Test at multiple quantiles (not just the mean)**
- 5th, 10th, 25th, 50th, 75th, 90th, 95th percentiles
- Used quantile regression (school-level) and linear quantile mixed models
  (student-level, accounting for school nesting)

**Step 4: Compare school-level vs. student-level analyses**
- School-level: higher funding associated with LARGER SES gaps
- Student-level: higher funding associated with SMALLER SES gaps
- OPPOSITE conclusions from the same data at different levels!

**Step 5: Diagnose the ecological fallacy**
- 96.95% of achievement variance is between students, only 3.05% between schools
- Aggregating to school level creates compositional confounding
- "The ecological fallacy appears to be at play when trying to generalize
  school-level results to student outcomes"

### 4. What Experiments Could They Run?
In principle, you could randomly assign funding levels to schools. Some states
have done this through court-ordered finance reforms (used as natural experiments
by other researchers). But this study is purely observational.

### 5. What Made This Investigation HARD
- **Endogeneity:** High-poverty schools get more funding (Title I), creating
  reverse causation -- funding doesn't cause low achievement, low-SES causes both
- **Simpson's paradox:** Without SES control, funding appears harmful
- **Ecological fallacy:** School-level and student-level analyses give
  OPPOSITE answers
- **Measurement:** Low-reliability tests, crude SES proxies, no individual spending data
- **Cross-sectional design:** Cannot track changes over time
- **Quantile heterogeneity:** Mean effects mask that funding may help the bottom
  of the distribution but not the top

### 6. Questions Asked
- **Methodological:** Do analytic choices change the conclusion?
- **Distributional:** Does funding help low-achievers differently from high-achievers?
- **Moderation:** Does SES moderate the funding-achievement relationship?
- **Aggregation:** Do school-level patterns replicate at the student level?

### 7. Validation
- Dual-level analysis (school and student) as internal check
- Progressive model complexity (Models 1-3)
- Multiple quantile points to test consistency
- Reliability analysis of the outcome measure

### What Makes This REAL vs. Toy
Toy: "Run a regression of achievement on funding." Real: The same data gives
OPPOSITE conclusions depending on (a) whether you control for SES, (b) whether
you look at mean vs. quantiles, (c) whether you aggregate to school or analyze
at student level. EVERY methodological decision changes the policy implication.
The paper is essentially a demonstration that "the question" is not enough --
HOW you answer it determines WHAT you find.

---

## Paper 5: Engineering / Materials Science -- Bayesian Optimization for Materials Discovery

### Citation
Multiple papers synthesized, primary reference:
"Knowledge-driven learning, optimization, and experimental design under
uncertainty for materials discovery." PMC10682757.

Also: Bayesian optimization with active learning of design constraints
(npj Computational Materials, 2023).
https://www.nature.com/articles/s41524-023-01006-7

### Domain
Materials science / Bayesian optimization / iterative experimental design

### 1. Type of Investigation
Active learning / sequential experimental design. The researcher CHOOSES
which experiment to run next based on model predictions and uncertainty.
Physical lab experiments are conducted in closed-loop cycles.

### 2. What Data They Had

**Starting data is extremely sparse:**
- BaTiO3 piezoelectrics: only 20 initial characterized compounds
- Shape Memory Alloys: small existing literature data
- MAX phases: ~1,500 DFT-calculated structures (computational, not experimental)

**Data problems:**
- "Limited amount of data (if any) for investigating new materials systems"
- "Data of varying and inconsistent quality because of technical limitations"
- Composition spaces are enormous (5+ element systems with continuous concentrations)
- Each experiment is expensive (synthesis + characterization = days to weeks)
- Prior knowledge is incomplete: physics gives guidance but not full prediction

### 3. What the Researchers ACTUALLY DID

**The closed-loop experimental workflow:**

1. **Encode prior knowledge:** Physical theories (e.g., Landau-Devonshire free
   energy for piezoelectrics) converted into Bayesian priors
2. **Train surrogate model:** Gaussian process or other probabilistic model on
   sparse initial data
3. **Quantify objective-relevant uncertainty (MOCU):** Not generic entropy --
   uncertainty that matters for the specific optimization goal
4. **Select next experiment:** Acquisition function (MOCU-based) identifies
   the composition/processing point that maximally reduces decision-relevant
   uncertainty
5. **Conduct physical experiment:** Actually synthesize the material, characterize
   its properties (this takes days or weeks)
6. **Update model:** Incorporate new observation into posterior
7. **Check convergence:** Has the optimal material been found? If not, go to step 4.

**Key example - BaTiO3 study:**
- Started with 20 compounds
- Bayesian model fusion (multiple surrogate models averaged)
- Discovered novel piezoelectric composition in minimal iterations
- Result: (Ba0.5Ca0.5)TiO3-Ba(Ti0.7Zr0.3)O3 with better temperature
  reliability than anything in training data

**Key example - SMA dopant optimization:**
- MOCU-based selection found optimal dopant in 2 iterations average
- Random selection: couldn't find optimal after 10+ iterations
- Exploitation-only: same poor performance

### 4. What Experiments Could They Run?
This domain is unique: **experiments are the core action, but they are expensive.**
- Each experiment: synthesize an alloy at specific composition + process at specific
  temperature/pressure + characterize properties (tensile test, phase analysis, etc.)
- Cost: hours to weeks per experiment
- Constraints: some compositions infeasible (won't form), safety (high temperatures),
  equipment availability
- Design variables: 4-6 continuous (element concentrations) + categorical (crystal
  structure, processing route)

### 5. What Made This Investigation HARD
- **Enormous design space:** 5+ elements, each with continuous concentration range
- **Expensive experiments:** Each point in the space costs days of lab work
- **Incomplete physics:** Theory gives qualitative guidance but can't predict
  exact properties from first principles
- **Multiple objectives:** Often optimizing strength AND ductility AND cost
  simultaneously (Pareto front, not single optimum)
- **Model uncertainty:** With 20 starting points in a million-dimensional space,
  the model is highly uncertain everywhere
- **Non-linear composition-property relationships:** Small compositional changes
  can cause phase transitions (discontinuous property changes)
- **Feasibility constraints:** Not all compositions can be synthesized
- **Traditional DOE is inefficient:** Full factorial design in 5D is astronomical

### 6. Questions Asked
- **Optimization:** What composition/processing gives the best properties?
- **Uncertainty reduction:** Where should I experiment next to learn the most?
- **Multi-objective:** What is the Pareto front of competing properties?
- **Mechanistic:** Why does this composition work? (post hoc interpretation)

### 7. Validation
- Compare predicted vs. actual experimental results
- Compare Bayesian approach vs. random sampling vs. exploitation-only
- 5-50x reduction in required experiments vs. traditional approaches
- Physical synthesis of predicted optimal material confirms properties

### What Makes This REAL vs. Toy
Toy: "Given this dataset of material properties, fit a model." Real: You START
with almost no data and must DECIDE which experiment to run next. Each decision
costs real money and time. The investigator is actively constructing the dataset,
not just analyzing a pre-existing one. The uncertainty IS the problem -- you
don't know what you don't know, and you have budget for perhaps 15 experiments
total in a space with millions of possible compositions.

---

## Paper 6: Economics -- Neighborhood Effects on Economic Mobility

### Citation
Chetty R, Hendren N. "The Impacts of Neighborhoods on Intergenerational
Mobility I: Childhood Exposure Effects." Quarterly Journal of Economics, 2018.

URL: https://academic.oup.com/qje/article/133/3/1107/4850660

### Domain
Economics / quasi-experimental / natural experiment using movers

### 1. Type of Investigation
Quasi-experimental study exploiting geographic mobility as a natural experiment.
Uses administrative tax data on 5+ million children whose families moved across
counties.

### 2. What Data They Had
- De-identified IRS tax records on >5 million children (1996-2012)
- Complete tax filing history: earnings, addresses, family structure
- Census/ACS data linked at county level
- Outcome measured at age 26: adult earnings, college attendance, marriage,
  teen birth rates

**Data quality advantages (rare):**
- Administrative data: no self-report bias, no attrition, complete population
- Exact income measures (not self-reported)
- Geographic tracking through address changes

**Data problems:**
- Tax records don't capture non-filers (though most people file)
- Can't observe WHY families moved (selection problem)
- County is a coarse geographic unit
- Income at 26 is an early snapshot (lifetime earnings may differ)

### 3. What the Researchers ACTUALLY DID

**The identification strategy (the intellectual core):**

The ideal experiment: randomly assign children to different neighborhoods.
This actually exists (Moving to Opportunity, or MTO), but it's small and
specific. Chetty and Hendren find a much larger "natural experiment":

**Step 1: Define the estimand**
- For each county c, estimate its causal effect on children's adult outcomes
- This is the "place effect" -- how much better/worse your outcomes would be
  if you grew up in county c vs. county c'

**Step 2: Exploit age-at-move variation**
- Among families who move from county A to county B, compare children who
  moved at age 5 (13 years of exposure to B) vs. children who moved at age 15
  (3 years of exposure to B)
- If neighborhoods matter through childhood exposure, younger movers should
  have outcomes more similar to county B "natives"
- KEY INSIGHT: Within the SAME family, children of different ages get different
  "doses" of the new neighborhood

**Step 3: Fixed effects structure**
- Origin-by-destination fixed effects: compare children within families that
  made the SAME move, varying only the child's age at move
- Parental income controls: flexible function of family income
- Year fixed effects: control for macroeconomic conditions

**Step 4: Estimate the exposure effect**
- Found linear relationship: each additional year of childhood exposure to a
  better county improves outcomes by ~4%
- Effect operates from birth through early 20s
- No effect for adult movers (confirming childhood-specific mechanism)

**Step 5: Placebo tests and falsification**
- Used teenage labor force participation (age 16) as pre-treatment outcome
- If a family moves when child is age 17 to a county with higher mobility,
  the child's LFP at age 16 should NOT be affected (it's before the move)
- Confirmed: placebo estimates uncorrelated with actual place effects

**Step 6: Sibling comparison**
- Within-family comparison: older sibling gets less exposure to new county
  than younger sibling
- This holds family characteristics FIXED

### 4. What Experiments Could They Run?
**None directly.** The MTO experiment existed but was small (~4,600 families).
This study's power comes from 5+ million families who moved "naturally."
The challenge is that natural moves are NOT random -- families who move to
good neighborhoods may be systematically different.

### 5. What Made This Investigation HARD
- **Selection bias is the central threat:** Families who move to better
  neighborhoods may have unobserved advantages (motivation, health, networks)
- **The counterfactual is unobservable:** You can never observe the same child
  growing up in two different places
- **Scale of data:** Processing tax records on millions of families requires
  extraordinary computational infrastructure
- **Definition of "neighborhood quality":** Using average outcomes of
  permanent residents as a proxy for causal effects (circularity risk)
- **Multiple hypothesis testing:** Estimating effects for 3,000+ counties
  raises multiple comparison concerns

### 6. Questions Asked
- **Causal:** Do neighborhoods CAUSE differences in economic mobility?
  (vs. "Do they merely reflect pre-existing family differences?")
- **Mechanism:** Is the effect through childhood exposure or immediate
  adult labor market effects?
- **Policy:** Should anti-poverty policy focus on people or places?
- **Dose-response:** How much exposure is needed for the full effect?

### 7. Validation
- Placebo tests (pre-move outcomes)
- Sibling comparisons
- Comparison with experimental MTO results
- Dose-response linearity (hard to fake)
- Gender-specific effects (boys more affected than girls, consistent with
  prior literature)

### What Makes This REAL vs. Toy
Toy: "Regress adult income on childhood county." Real: That regression tells you
nothing causal because families sort into counties. The entire paper is a 50-page
argument about identification -- using within-family age-at-move variation,
origin-by-destination fixed effects, placebo tests, and sibling comparisons to
slowly build a case for causality. The identification strategy IS the contribution.

---

## Paper 7: Ecology -- Coral Reef Bleaching and Multiple Stressors

### Citation
"Estimating the effect of multiple environmental stressors on coral bleaching
and mortality." PMC5417430.

URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC5417430/

### Domain
Marine ecology / multiple stressor analysis / field observations

### 1. Type of Investigation
Observational field study analyzing the 2005 Caribbean mass bleaching event.
No experimental manipulation -- uses "natural variation" across 2,945 coral
observations to estimate stressor effects.

### 2. What Data They Had

**5 data sources merged:**
- Primary: 2,945 coral health observations (bleaching severity + mortality)
  from field surveys across the Caribbean basin (May 2005 - Jan 2007)
- NOAA Coral Reef Watch: Degree Heating Weeks (DHW) at 50km resolution
- NASA MODIS Aqua satellite: photosynthetically active radiation (PAR)
- NCEP-DOE reanalysis: wind speed
- UN Gridded Population: population density within 50km (anthropogenic proxy)

**Data problems:**
- "The sampling campaign did not follow a strict probabilistic approach"
  -- non-random sampling
- Two different measurement methods used (area coverage vs. colony counts)
  -- had to composite them
- Mortality was extremely sparse: median = 0%, mean = 2%
- Spatial autocorrelation between nearby observations
- Environmental data at different resolutions (50km satellite vs. point observations)
- Hurricane effects ambiguous (could increase OR decrease stress)

### 3. What the Researchers ACTUALLY DID

**Step 1: Temporal filtering**
- Only included observations between first thermal stress warning and 90
  days after last "no stress" alert
- This prevents attributing bleaching to disease or hurricanes

**Step 2: Construct variables with alternatives**
- Temperature: both "observed DHW" and "maximum DHW" formulations tested
- PAR: both 12-week average and monthly maximum deviation tested
- Depth x stressor interactions constructed
- Regional dummies for 9 Marine Ecoregions of the World (MEOW)

**Step 3: Model selection via cross-validation**
- Tested OLS, Tobit, and Fractional Logit models
- 1,000 simulations of k-fold cross-validation for each
- Selected Fractional Logit (handles bounded 0-100% outcome appropriately)
- Wind speed kept despite non-significance because it improved CV performance

**Step 4: Relative importance analysis**
- Varied each stressor between 5th and 95th percentiles, holding others at means
- Found temperature effects ~4x larger than population density for both
  bleaching and mortality
- Climate stressors "far outweighed direct anthropogenic stressors"

**Step 5: Regional heterogeneity**
- Spatial fixed effects for 9 ecoregions
- Bermuda corals significantly more robust than other regions
- In some regions, bleaching started shallow and moved deep; in others, opposite

### 4. What Experiments Could They Run?
**Almost none.** You cannot experimentally heat a coral reef to study bleaching.
Small-scale aquarium experiments exist but don't capture ecosystem-level dynamics.
The researchers must work with whatever nature provides.

### 5. What Made This Investigation HARD
- **Non-random sampling:** The field survey wasn't designed as a statistical sample
- **Multiple causal pathways:** Temperature, light, pollution, depth all interact
- **Spatial confounding:** Nearby corals share unmeasured environmental drivers
- **Sparse outcomes:** Mortality extremely rare (median 0%) -- modeling challenges
- **Scale mismatch:** Satellite data at 50km, coral observations at point level
- **Unexpected patterns:** Bleaching depth patterns differ by region, suggesting
  unmeasured mediators
- **Cannot randomize treatment:** Temperature stress is not manipulable at reef scale
- **Temporal confounding:** The study spans 2005-2007, but the event was in 2005
  -- later observations may reflect recovery, not initial stress

### 6. Questions Asked
- **Predictive (primary):** Can we forecast bleaching given environmental stressors?
- **Attribution:** What proportion of bleaching is temperature vs. anthropogenic?
- **Interaction:** Do stressors combine additively or synergistically?
- **Heterogeneity:** Do corals in different regions respond differently?

### 7. Validation
- k-fold cross-validation (1,000 iterations)
- Three competing model specifications
- Multiple variable formulations (observed vs. max DHW)
- Regional marginal effects for spatial robustness

### What Makes This REAL vs. Toy
Toy: "Fit a model of bleaching as a function of temperature." Real: You have
five different data sources at different spatial/temporal resolutions, non-random
sampling, a bounded outcome with extreme sparsity (most corals didn't die),
spatial autocorrelation, and the fundamental impossibility of experimentation.
You must construct interactions from theory, select models via cross-validation,
and argue about whether your "anthropogenic stressor" proxy (population density)
actually measures what you think it does.

---

## Cross-Cutting Patterns: What Makes Real Research REAL

### Pattern 1: Data Assembly is Half the Work

| Study | Data Sources Combined | Data Problems |
|-------|----------------------|---------------|
| Air Pollution | 6 (Medicare, claims, satellite, Census, BRFSS, meteorology) | Exposure misclassification, ecological fallacy, collinearity |
| Biodiversity | Global grassland panel + environmental covariates | Endogeneity, reverse causality, spatial autocorrelation |
| RECOVERY Trial | Hospital forms + NHS registries + national death records | Minimal collection, open-label, contamination |
| School Funding | Student achievement + school expenditure + demographics | Low-reliability test, no individual spending, cross-sectional |
| Materials | Initial sparse experiments + physics theory + DFT calculations | 20 data points in million-dimensional space, inconsistent quality |
| Neighborhoods | IRS tax records + Census + county characteristics | Selection bias in movers, coarse geography |
| Coral Reefs | Field surveys + satellite (3 types) + population grids | Non-random sampling, scale mismatch, sparse mortality |

**SREG implication:** A single clean CSV dataset is unrealistic. Real investigations
involve merging heterogeneous sources with different granularities, coding systems,
and quality levels.

### Pattern 2: Identification Strategy > Statistical Method

In every study, the intellectual core is NOT the statistical model but the
IDENTIFICATION STRATEGY -- the argument for why the analysis isolates a causal effect:

| Study | Identification Strategy |
|-------|----------------------|
| Air Pollution | Double negative control (future exposure + past outcome as proxies for unmeasured confounding) |
| Biodiversity | Fixed effects + instrumental variables (from economics) |
| RECOVERY | Randomization (but complicated by open-label, contamination, heterogeneous effects) |
| School Funding | None claimed -- shows how conclusions change without proper identification |
| Materials | Sequential experimental design (YOU choose the next experiment) |
| Neighborhoods | Age-at-move variation within families (childhood exposure effects) |
| Coral Reefs | Spatial fixed effects + temporal restriction (weak identification) |

**SREG implication:** The "action" in a real investigation is not running an analysis
but DESIGNING the comparison. What is compared to what? Why is that comparison valid?

### Pattern 3: Sensitivity Analysis is Multi-Dimensional

No study reports a single result. Every study asks "would my conclusion change if...":

- ...I used a different model? (coral reefs: OLS vs. Tobit vs. Fractional Logit)
- ...I defined the sample differently? (air pollution: multiple exposure thresholds)
- ...I included different confounders? (school funding: Models 1, 2, 3)
- ...I analyzed at a different level? (school funding: student vs. school)
- ...my key assumption was wrong? (neighborhoods: placebo tests)
- ...my core result is fragile? (RECOVERY: subgroup analysis by severity)

**SREG implication:** A real investigator doesn't just submit one answer. They
explore the space of answers across analytic choices, and the PATTERN of results
across specifications is what builds confidence.

### Pattern 4: Constraints Define the Investigation

| Study | Key Constraint | How It Shaped the Research |
|-------|---------------|---------------------------|
| Air Pollution | Can't randomize exposure | Had to invent negative control approach |
| Biodiversity | Can't randomize species in nature | Imported IV methods from economics |
| RECOVERY | Pandemic speed | Open-label, minimal data, adaptive design |
| School Funding | Cross-sectional data | Cannot claim causality, focuses on method sensitivity |
| Materials | Each experiment costs days | Must optimize experiment selection |
| Neighborhoods | Can't randomize families to counties | Used within-family age-at-move variation |
| Coral Reefs | Can't heat a reef experimentally | Relied on natural event (2005 bleaching) |

**SREG implication:** Real investigations are shaped by what you CAN'T do as much
as what you can. Budget, ethics, feasibility, and data availability constrain the
space of possible investigations.

### Pattern 5: The Answer Often Depends on the Question's Framing

- **School funding:** Appears harmful (Model 1), neutral (Model 2), or
  beneficial-for-low-achievers (Model 3) depending on confounders and quantiles
- **Biodiversity:** Positive effect (experiments) vs. negative effect (observational
  with proper identification) depending on data source
- **RECOVERY:** Drug helpful (overall) vs. drug harmful (mild cases) depending
  on subgroup
- **Air pollution:** Significant (single pollutant) vs. attenuated (three-pollutant
  model) depending on model specification

**SREG implication:** Real research questions don't have a single right answer.
The investigator must navigate a space of defensible answers and explain why
different specifications give different results.

### Pattern 6: Real Investigations Have a Temporal/Sequential Structure

Real research unfolds over time with decision points:

1. **Formulate question** (often refined after seeing data)
2. **Acquire/assemble data** (often the hardest part)
3. **Explore data** (descriptive statistics, visualizations, anomaly detection)
4. **Choose identification strategy** (the intellectual contribution)
5. **Specify model(s)** (multiple specifications to test robustness)
6. **Run primary analysis** (often iterative -- results suggest new analyses)
7. **Conduct sensitivity analyses** (challenge your own results)
8. **Interpret and reconcile** (explain unexpected findings, compare with prior work)

In the materials science case, this is literally an iterative loop where each
experiment informs the next.

**SREG implication:** A static "here is the data, answer the question" format
misses the sequential, adaptive nature of real investigation.

---

## Implications for SREG Design

Based on this analysis, here are the key dimensions where SREG environments
should evolve to better capture real scientific investigation:

### 1. Multi-Source Data with Quality Issues
Real studies combine 3-8 heterogeneous data sources. SREG should generate:
- Multiple datasets with different variable subsets
- Different granularities (individual vs. aggregate)
- Missing data patterns that are non-random (MNAR, not MCAR)
- Measurement error in key variables
- Incompatible coding systems requiring alignment

### 2. Identification as a Task
The hardest part of real research is figuring out the right comparison.
SREG should evaluate:
- Can the agent identify the right adjustment set (not just the right answer)?
- Does the agent recognize when a naive analysis is biased?
- Can the agent propose an identification strategy (IV, DiD, matching)?

### 3. Sensitivity Analysis as a Required Step
Real investigators don't submit one answer. They explore the robustness space:
- Multiple model specifications
- Different confounder sets
- Different sample definitions
- Different outcome measures
- The agent should be evaluated on whether it CHECKS its own answer

### 4. Constrained Action Spaces
Real experiments have costs, ethical limits, and feasibility constraints:
- Budget that forces prioritization
- Some variables that CANNOT be intervened on (ethics)
- Experiments that take "time" (sequential, not parallel)
- Information that must be purchased (consulting an expert, running a lab test)

### 5. Heterogeneous Treatment Effects
Real effects are rarely constant. The agent should:
- Look for effect modification (does the effect differ by subgroup?)
- Recognize Simpson's paradox
- Understand that average effects can mask opposite subgroup effects

### 6. The Question is Not Enough
The same data + question can yield different valid answers depending on:
- Level of analysis (individual vs. aggregate)
- Confounder inclusion
- Model specification
- Sample restriction

SREG should evaluate whether the agent makes DEFENSIBLE analytic choices,
not just whether it gets "the" answer.

---

## Sources

- [Air Pollution and CV Disease - Double Negative Control](https://pmc.ncbi.nlm.nih.gov/articles/PMC10690329/)
- [Biodiversity and Productivity - Causal Inference](https://www.nature.com/articles/s41467-023-37194-5)
- [Modern Causal Inference in BEF](https://www.nature.com/articles/s41467-023-37546-1)
- [RECOVERY Trial - Dexamethasone](https://pmc.ncbi.nlm.nih.gov/articles/PMC7383595/)
- [DAPA-HF Trial](https://www.nejm.org/doi/full/10.1056/NEJMoa1911303)
- [School Funding and Achievement](https://pmc.ncbi.nlm.nih.gov/articles/PMC11583220/)
- [Materials Discovery - Knowledge-Driven BO](https://pmc.ncbi.nlm.nih.gov/articles/PMC10682757/)
- [Bayesian Optimization with Design Constraints](https://www.nature.com/articles/s41524-023-01006-7)
- [Magnesium Alloy Design](https://www.nature.com/articles/s41598-024-59100-9)
- [Coral Bleaching and Multiple Stressors](https://pmc.ncbi.nlm.nih.gov/articles/PMC5417430/)
- [Neighborhood Effects on Mobility](https://academic.oup.com/qje/article/133/3/1107/4850660)
- [Federated Causal Inference - SARS-CoV-2](https://pmc.ncbi.nlm.nih.gov/articles/PMC10594731/)
- [Asian Cohorts - Air Pollution Mortality](https://pmc.ncbi.nlm.nih.gov/articles/PMC10330956/)
- [Difference-in-Differences Methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC11305929/)
- [Card & Krueger - Minimum Wage](https://www.nber.org/papers/w4509)
- [Nobel Natural Experiments](https://www.nature.com/articles/d41586-021-02799-7)
