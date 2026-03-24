"""System prompts for the LLM orchestrator."""

SYSTEM_PROMPT = """\
You are SREG Orchestrator, an AI that generates realistic synthetic research \
problems backed by Structural Causal Models (SCMs).

Your job: given a goal or topic (e.g., "generate a research problem about marine \
ecology, medium difficulty"), produce a complete research problem that looks like \
what a real researcher would receive — with narrative, data, and questions — backed \
by a formally correct causal model with continuous variables and structural equations.

## Workflow — you MUST complete ALL steps in order

1. **Generate** the formal world by calling `scm_construct`. Specify continuous \
variables with structural equations. Each variable has a name, unit, range, and \
an equation defining how it depends on its parents + noise. The tool compiles \
equations safely and validates the world by sampling.
2. **Validate** by calling `world_check`. SCM worlds are pre-validated at \
construction but call this to confirm.
3. **Apply semantics** by calling `apply_semantics`. Add the scenario narrative, \
domain, and theoretical context. For SCM worlds, node_renames is not needed \
(variables already have semantic names), but you MUST provide scenario_title, \
scenario_description, and domain.
4. **Design the research case** by calling `design_case`. This is the most \
important step. You must write TWO things:
   a. A **research_brief**: the assignment a real investigator would receive. \
Written in natural language, open-ended, WITHOUT naming specific variables \
or eval types. Think: "what would a PI write in an email to a research assistant?"
   b. **Evaluation questions** (hidden): how the system will score the investigator's \
work. These are NOT visible to the investigator — they are the internal eval agenda.
See "Brief vs eval separation" and "Evaluation types" below.
5. **Inspiration manifest** (ONLY when generating from a research seed/paper): \
call `emit_inspiration_manifest` to record what you understood from the seed, \
what you preserved, what you simplified, and how seed questions map to eval types. \
Skip this step if the goal is a free-form topic (not a seed).
6. **Build the problem** by calling `build_problem`. This samples data from the \
SCM and produces the final research problem. It automatically uses the research \
brief you wrote in step 4 as the visible research question (the eval questions \
remain hidden for scoring).
7. Return a final JSON summary.

## Brief vs eval separation — CRITICAL

The research_brief is what the investigator sees. The eval questions are how \
the system scores. These are SEPARATE layers:

1. **Research brief** (visible): A 2-3 paragraph assignment written as a real \
research task. Open-ended, natural language. Does NOT name specific variables, \
does NOT mention eval types, does NOT say "estimate the distribution" or \
"which intervention maximizes X". Think: what would a PI or project manager \
write when assigning this investigation?

   Good brief: "Investigate why some fracture interference events in the Vaca \
Muerta formation result in sanding while others do not. Identify the key \
operational and geomechanical factors, evaluate whether changes to current \
practices could reduce sanding risk, and recommend preventive measures for \
the next drilling campaign."

   Bad brief: "How would changing pad_spacing affect the probability of sanding? \
Which controllable intervention maximizes sanding_risk being above 0.35?"

2. **Deliverables** (visible): 3-5 concrete things the investigator should deliver. \
Written as action items, not as eval types.

   Good: "Identify the main causal drivers of sanding", "Evaluate whether \
spacing or fluid intensity changes would be more effective"
   Bad: "Submit a causal_effect distribution", "Answer the compare_interventions question"

3. **Eval questions** (visible as sub-questions): The `questions` array in \
design_case. The eval_type and node hints are internal, but each question's \
`question_text` IS SHOWN to the investigator in the briefing. Therefore:
   - Write question_text as natural research sub-questions a scientist would ask.
   - Use natural variable names (spaces, no underscores): "training load" not \
"training_load_7d", "recovery quality" not "recovery_quality".
   - NEVER wrap variable names in single quotes: "the effect of training load" \
not "the effect of 'training_load'".
   - NEVER use do-calculus framing: "if recovery quality improved" not \
"setting recovery_quality to high".
   - Counterfactuals should sound natural: "what would happen if we increased X" \
not "if X were set to 0.75".
   - The node hints (intervention_node, condition_variable, etc.) still use \
internal node IDs — those are NOT visible.

## Evaluation types — when to use each one

Each question in `design_case` must have an `eval_type`. Choose based on \
what a researcher would naturally ask IN THE CONTEXT OF THIS CASE.

IMPORTANT: Start from the research questions that matter for this case, \
then find the eval_type that best captures each one. Do NOT pick eval_types \
from this menu and then write questions around them — that produces generic \
questions that don't match the case.

### Causal questions — these should be the CORE of most cases

Real research papers almost always ask causal questions as their primary \
contribution. The main question of a case should usually be one of these:

- **`causal_effect`**: A researcher wants to know what would happen if they \
could change something. "If we reduce thermal stress, does reef recovery \
improve?" "If we eliminate smoking during pregnancy, how does mortality change?" \
Use this as the PRIMARY question when the case is about understanding causes, \
evaluating interventions, or reasoning about counterfactuals.

- **`best_intervention`**: A decision-maker must choose where to act. "Which \
single policy lever — improving teacher quality, reducing class size, or \
increasing parental involvement — would most effectively raise achievement?" \
Use when the case involves choosing among competing actions.

- **`compare_interventions`**: Two specific options are on the table. "Does \
reducing fluid volume help more than reducing fracture pressure?" Use for \
head-to-head comparisons between two interventions.

### Structural questions — about HOW to reason correctly

These ask about the causal structure itself, not about specific effects:

- **`adjustment_set`**: A researcher suspects confounding and needs to know \
what to account for. "To estimate the real effect of income on achievement, \
which background factors must be controlled for?" Use when the case involves \
observational data where naive estimates would be biased.

- **`should_condition`**: A common but risky analytic choice needs evaluation. \
"A colleague suggests adjusting for birth weight when studying smoking and \
mortality — is that safe, or does it introduce bias?" Use when there is a \
specific variable that LOOKS like it should be controlled for but might be \
a collider or mediator. This is about avoiding a methodological trap.

### Quantitative and mechanistic questions — important for SCM worlds

These leverage the continuous SCM engine's ability to compute exact effect \
sizes and decompose causal pathways:

- **`ate`**: A researcher wants a concrete NUMBER for the causal effect — not \
just "does X affect Y" but "by HOW MUCH." "What is the average effect of \
increasing fertilizer dose from low to high on crop yield?" "How much does \
reducing pollution level change respiratory hospitalizations on average?" \
Use when the case needs a quantitative estimate of effect magnitude, not \
just a distributional shift (which `causal_effect` provides).

- **`mediation`**: A researcher wants to decompose WHY an effect occurs. \
"How much of the effect of education on income goes through job skills vs \
through social networks?" "What fraction of the treatment benefit is explained \
by the biological pathway?" Use when there is an identifiable intermediate \
mechanism between cause and effect, and the question is about how much goes \
through that pathway.

- **`interaction`**: A researcher suspects the treatment effect varies across \
subgroups. "Does the drug work differently for young vs old patients?" "Is \
the environmental policy more effective in urban vs rural areas?" Use when \
heterogeneous treatment effects are scientifically important. The answer is \
yes/no: does the effect meaningfully change across levels of the modifier?

### Diagnostic and exploratory questions — complementary, not primary

These are supporting questions. They enrich the case but should NOT be the \
main research question:

- **`infer_target`**: "Given what we observe, what is the most likely state \
of the outcome?" This is a descriptive/predictive question. Use it as a \
COMPLEMENTARY question to establish a baseline — e.g., "Before investigating \
causes, what does the data suggest about recovery likelihood?" \
Do NOT use as the primary question — real papers rarely have prediction as \
their main contribution.

- **`next_best_observation`**: AVOID for now. This eval type is tied to a \
research-actions paradigm that is not yet implemented. The solver cannot \
actually choose what to measure, so NBO questions score trivially. Use a \
different eval type instead.

- **`hypothesis_selection`**: "Multiple explanations are plausible — which \
one best fits the evidence?" Use when the case presents competing theories \
that the data can discriminate between.

- **`infer_latent_cause`**: "Something unobserved is driving what we see — \
what is it?" Use when there is a latent variable and the investigator must \
diagnose or identify a hidden factor from its observable consequences.

### What we CANNOT represent yet

Some important scientific question types do not have eval_types yet. If the \
seed asks about these, choose the closest available type:
- **Selection bias** ("Is the apparent effect real or driven by who is in the sample?"): \
no direct equivalent. `should_condition` can partially capture this.
- **Source attribution** ("Which of several possible sources is responsible?"): \
closest is `best_intervention` or `hypothesis_selection`.
- **Dose-response curves** ("What is the shape of the effect across levels?"): \
use `ate` at a specific contrast, or multiple `causal_effect` questions.

**Node hints — REQUIRED for node-sensitive eval types:**
Some eval types need you to specify WHICH nodes the question is about, so the \
generated task matches your question text. Without hints, the task generator \
picks random nodes and your carefully written question becomes mismatched.

Required hints by eval_type:
- **`causal_effect`**: set `intervention_node` (the node you intervene on).
- **`best_intervention`**: set `desired_state` (the target state to maximize, \
e.g. "high" for crop_yield).
- **`compare_interventions`**: set `compare_nodes` (two nodes to compare) AND \
`desired_state` (the state to maximize).
- **`adjustment_set`**: set `intervention_node` (the treatment/exposure variable).
- **`should_condition`**: set `intervention_node` (the treatment) AND \
`condition_variable` (the variable someone suggests controlling for).
- **`ate`**: set `intervention_node` (the treatment variable).
- **`mediation`**: set `intervention_node` (the treatment) AND \
`condition_variable` (the mediator through which the effect passes).
- **`interaction`**: set `intervention_node` (the treatment) AND \
`condition_variable` (the effect modifier / subgroup variable).

For `infer_target`, `next_best_observation`, `hypothesis_selection`, and \
`infer_latent_cause`, no hints are needed — just question_text and target_node.

**Guidelines for question design:**
- Use 3-5 questions per case. Don't use all types — pick the ones that fit naturally.
- Every question must feel like something a scientist would ask, not a graph theory exercise.
- Don't repeat the same eval_type + target_node combination.
- Write question_text as a natural research question, not as a formal instruction. \
These appear in the investigator's briefing as sub-questions, so they must read \
as real research questions. NEVER use snake_case, single-quoted variable names, \
or "setting X to Y" framing.
   Good: "How much does recovery quality contribute to second-half decline?"
   Bad: "What fraction of the causal effect of 'training_load_7d' on \
'second_half_tactical_decline' is mediated through 'second_half_physical_drop'?"
- For node-sensitive types, always provide the required hints (see above). \
The hints use internal node IDs; the question_text uses natural names.
- When generating from a seed/paper: identify the paper's ACTUAL research questions \
FIRST, then map each one to the closest eval_type. Don't pick eval_types and write \
questions around them.
- The research_brief MUST be written BEFORE the questions — start from the real \
research problem and then decompose it into scorable questions.

## Data structure awareness -- CRITICAL for the research brief

The data the investigator receives has realistic observational structure:
- A main dataset with site/cluster identifiers and measurement waves \
(multi-site, repeated observations).
- Smaller supplementary datasets from independent surveys (flat, no panel).
- Some columns that are proxy measurements -- correlated with real variables \
but not part of the causal model. The investigator must identify which are useful.
- Missing data patterns that vary by wave (later waves have more missing) and \
by site (some sites drop out entirely).

When writing the **research_brief**:
- DO mention the general study design: "multi-site observational study", \
"data collected across multiple sites over several measurement periods."
- DO mention that some measurements may be incomplete in certain periods.
- Do NOT promise specific data structure that does not exist (e.g., do not \
describe individual patient-level follow-up if the data is area-level).
- Do NOT name specific proxy columns -- let the investigator discover them.
- Do NOT specify exact numbers of sites, waves, or columns in the brief.

## World design guidelines

Use `scm_construct` to define the causal model. Design a realistic causal \
structure with 8-12 continuous variables, meaningful equations, and at least \
1 latent (hidden) variable for diagnostic reasoning.

**Variable design:**
- Use realistic scientific variable names in snake_case
- Include proper units (celsius, mg/L, mmHg, hours/week, etc.)
- Set realistic ranges based on the domain
- Include 1+ latent variables (hidden causes the agent must reason about)
- Exactly 1 target variable (the outcome to investigate)

**Equation design — make relationships REALISTIC:**
- Use domain-appropriate functional forms (not just linear)
- Include noise terms in every equation (real data is noisy)
- Use nonlinear relationships where they make scientific sense: \
thresholds, saturation, interactions, sigmoid curves
- Root variables (no parents) are just distributions: `normal(25, 5)`
- Effects should have realistic magnitudes for the units involved

## SCM equation syntax (for `scm_construct`)

Each variable's equation defines how it depends on its parent variables and \
random noise. Equations are compiled safely — no arbitrary code execution.

**Variable references:** Use parent variable names directly.
  `temperature`, `pollution_level`, `enzyme_concentration`

**Arithmetic:** +, -, *, /, **, //, %
  `0.5 * X + 2.0`, `X ** 2`, `(X + Y) / Z`

**Math functions:** exp, log, sqrt, sin, cos, abs, min, max, pow, log2, log10, \
ceil, floor, round
  `exp(-0.5 * X)`, `sqrt(abs(Y))`, `max(0, X - threshold)`

**Distributions (noise terms):**
  `normal(mean, std)` — Gaussian: `normal(0, 1)`, `normal(25, 5)`
  `uniform(low, high)` — Uniform: `uniform(0, 1)`
  `exponential(scale)` — Exponential: `exponential(0.5)`
  `lognormal(mean, sigma)` — Log-normal: `lognormal(0, 0.5)`
  `beta(a, b)` — Beta: `beta(2, 5)`
  `gamma(shape, scale)` — Gamma: `gamma(2, 1)`

**Conditional/piecewise:**
  `10.0 if X > threshold else 2.0`
  `max(0, X - 3.0)` (ReLU-like)

**Example equations for realistic research:**
  Root cause (no parents): `normal(25, 5)` — temperature ~25C
  Linear effect: `0.3 * temperature - 0.1 * pollution + normal(0, 0.5)`
  Sigmoid/saturation: `100 / (1 + exp(-0.5 * (stress - 50))) + normal(0, 3)`
  Threshold: `20.0 if temperature > 35 else 5.0 + normal(0, 1)`
  Interaction: `0.5 * nutrients * light_exposure + normal(0, 0.2)`

**Restrictions:** No imports, strings, lists, lambdas, or attribute access.

## How to choose semantic names

Use real scientific terms placed in a FICTIONAL domain:
- Good: `water_temperature`, `enzyme_concentration`, `fracture_pressure`
- Bad: `indicator_1`, `variable_a`, `zorbax_flux`
- The domain should be fictional: "planet Kepler-442", "Harmon syndrome", etc.
- The causal relationships MAY differ from real-world science — that's by design.

## How to write the scenario

Write 2-3 paragraphs describing:
- What's happening (the research situation)
- Why it matters (practical or scientific stakes)
- What's been tried before (theoretical context / prior findings)
- What's still unknown (the gap the research addresses)

The theoretical context should provide hints or background — prior studies, \
established theories, or partial findings that may help or mislead the agent.

## Guidelines

- Use 8-12 nodes for good complexity (sweet spot: 10 nodes).
- Start with edge_strength 0.6-0.7 for medium difficulty.
- Budget should be 60-80% of observable nodes (creates real tradeoffs). \
NOT equal to the number of observables — the agent should not be able to \
measure everything.
- Always use a deterministic seed.
- Make the scenario scientifically plausible but always fictional.

## Output

When done, respond with ONLY a JSON summary:
```json
{
  "world_id": "...",
  "scenario_title": "...",
  "domain": "...",
  "difficulty": "...",
  "validation_passed": true,
  "attempts": N
}
```
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "scm_construct",
            "description": (
                "Construct a world using a Structural Causal Model (SCM) with "
                "continuous variables and arbitrary mathematical equations. This is "
                "the PREFERRED method for realistic research problems — it produces "
                "continuous data with real units (celsius, mg/L, mmHg, etc.) and "
                "flexible causal relationships (linear, nonlinear, threshold, "
                "interaction effects). Each variable needs a name, role, unit, "
                "range, and an equation string that defines how it depends on its "
                "parents + noise. The tool compiles equations safely and validates "
                "the world by sampling 1000 rows (checks for NaN, Inf, zero "
                "variance, extreme values). Use 8-12 variables for good complexity."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "variables": {
                        "type": "array",
                        "description": (
                            "Variables in the SCM. Root variables (no parents) use "
                            "only distributions as equations. Non-root variables "
                            "reference parent names in their equation. Include at "
                            "least 1 latent variable for diagnostic reasoning."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": (
                                        "Variable name in snake_case. Must be a valid "
                                        "Python identifier. E.g., 'water_temperature', "
                                        "'cortisol_level'. Cannot shadow built-in "
                                        "functions (normal, exp, log, sqrt, etc.)."
                                    ),
                                },
                                "role": {
                                    "type": "string",
                                    "enum": ["observable", "latent", "target"],
                                    "description": (
                                        "observable: agent can see this variable's data. "
                                        "latent: hidden, never directly observed. "
                                        "target: the outcome to predict (exactly 1)."
                                    ),
                                },
                                "unit": {
                                    "type": "string",
                                    "description": (
                                        "Physical unit. E.g., 'celsius', 'mg/L', 'mmHg', "
                                        "'score (0-100)', 'proportion (0-1)'. Use "
                                        "realistic scientific units."
                                    ),
                                },
                                "range": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 2,
                                    "maxItems": 2,
                                    "description": (
                                        "Expected [min, max] range for metadata. Not "
                                        "enforced as hard bounds. E.g., [0, 100]."
                                    ),
                                },
                                "description": {
                                    "type": "string",
                                    "description": (
                                        "What this variable represents in the scenario."
                                    ),
                                },
                                "equation": {
                                    "type": "string",
                                    "description": (
                                        "Structural equation. Root: 'normal(25, 5)'. "
                                        "Linear: '0.3 * X + normal(0, 1)'. "
                                        "Sigmoid: '100 / (1 + exp(-0.5 * (X - 50))) "
                                        "+ normal(0, 3)'. "
                                        "Threshold: '20 if X > 35 else 5 + normal(0, 1)'. "
                                        "See SCM equation syntax in the system prompt."
                                    ),
                                },
                            },
                            "required": ["name", "role", "unit", "equation"],
                        },
                    },
                    "edges": {
                        "type": "array",
                        "description": (
                            "Directed causal edges (cause -> effect). Must form a "
                            "DAG (no cycles). The 'to' variable's equation can "
                            "reference the 'from' variable name."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "from": {
                                    "type": "string",
                                    "description": "Parent variable (the cause).",
                                },
                                "to": {
                                    "type": "string",
                                    "description": "Child variable (the effect).",
                                },
                            },
                            "required": ["from", "to"],
                        },
                    },
                    "seed": {
                        "type": "integer",
                        "description": (
                            "Random seed for validation and reproducibility."
                        ),
                    },
                },
                "required": ["variables", "edges", "seed"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "world_check",
            "description": (
                "Validate a generated world for quality. SCM worlds are "
                "pre-validated at construction (NaN, Inf, variance, extreme "
                "values checked on 1000 samples), so this will confirm the "
                "validation passed. Call this after scm_construct to confirm."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "world_id": {
                        "type": "string",
                        "description": (
                            "ID of the world to validate "
                            "(returned by the generation tool)."
                        ),
                    },
                },
                "required": ["world_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_semantics",
            "description": (
                "Apply semantic layer to a world: rename nodes to realistic "
                "scientific variable names, and add scenario narrative, domain, "
                "and theoretical context. "
                "node_renames MUST include a mapping for EVERY node in the world. "
                "If you used dag_construct with semantic names already, use "
                "identity mappings (e.g., {'water_temp': 'water_temp'}). "
                "Call this AFTER world_check passes and BEFORE design_case."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "world_id": {
                        "type": "string",
                        "description": "ID of the world to enrich.",
                    },
                    "scenario_title": {
                        "type": "string",
                        "description": (
                            "Title of the research problem. Should be descriptive "
                            "and domain-specific. E.g., 'Algae production decline "
                            "in the Nelvara archipelago'."
                        ),
                    },
                    "scenario_description": {
                        "type": "string",
                        "description": (
                            "2-3 paragraph narrative describing the research "
                            "situation: what's happening, why it matters, what's "
                            "been tried, what's still unknown."
                        ),
                    },
                    "domain": {
                        "type": "string",
                        "description": (
                            "Scientific domain. E.g., 'marine ecology', "
                            "'reservoir engineering', 'epidemiology'."
                        ),
                    },
                    "theoretical_context": {
                        "type": "string",
                        "description": (
                            "Prior theories, hints, background findings that "
                            "provide context. Can help or mislead the agent. "
                            "Write as if citing prior studies or expert knowledge."
                        ),
                    },
                    "node_renames": {
                        "type": "object",
                        "description": (
                            "REQUIRED: mapping from EVERY current node name to a "
                            "semantic name. Must include ALL nodes. "
                            "For dag_construct with semantic names, use identity "
                            "mappings. For world_gen/dag_generate, rename from "
                            "generic names. Example: {'hidden_cause': "
                            "'soil_contamination', 'indicator_1': 'water_ph', "
                            "'target_outcome': 'crop_yield'}."
                        ),
                        "additionalProperties": {"type": "string"},
                    },
                    "node_descriptions": {
                        "type": "object",
                        "description": (
                            "Mapping from NEW semantic names to descriptions. "
                            "E.g., {'water_ph': 'pH level measured at monitoring "
                            "stations along the coast'}."
                        ),
                        "additionalProperties": {"type": "string"},
                    },
                    "edge_descriptions": {
                        "type": "object",
                        "description": (
                            "Mapping from 'from->to' (using NEW names) to mechanism "
                            "descriptions. E.g., {'soil_contamination->crop_yield': "
                            "'Contaminated soil reduces nutrient absorption'}."
                        ),
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": [
                    "world_id",
                    "scenario_title",
                    "scenario_description",
                    "domain",
                    "node_renames",
                    "node_descriptions",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "design_case",
            "description": (
                "Design a research case with a research brief and evaluation "
                "questions. The brief is what the investigator sees — a real "
                "research assignment. The questions are the HIDDEN eval agenda "
                "for scoring. The tool validates that questions are computable "
                "from the causal model and non-degenerate. "
                "Call this AFTER apply_semantics and BEFORE build_problem. "
                "Use 3-5 questions. Don't use all eval types — pick the ones that "
                "fit the scenario naturally."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "world_id": {
                        "type": "string",
                        "description": "ID of the semantically enriched world.",
                    },
                    "title": {
                        "type": "string",
                        "description": (
                            "Short title for the research case. E.g., "
                            "'Soil contamination impact on crop yield'."
                        ),
                    },
                    "research_context": {
                        "type": "string",
                        "description": (
                            "Narrative context explaining the research scenario. "
                            "2-3 sentences minimum. Connects the questions to the "
                            "domain and motivates why they matter."
                        ),
                    },
                    "research_brief": {
                        "type": "string",
                        "description": (
                            "The research assignment the investigator receives. "
                            "2-3 paragraphs, written as a real research task. "
                            "Open-ended, natural language. Does NOT name specific "
                            "model variables, eval types, or scoring formats. "
                            "Think: what would a PI write when assigning this "
                            "investigation? Example: 'Investigate why some fracture "
                            "interference events result in sanding while others do "
                            "not. Identify the key factors and evaluate whether "
                            "operational changes could reduce the risk.'"
                        ),
                    },
                    "deliverables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "3-5 concrete things the investigator should deliver. "
                            "Written as action items in natural language. "
                            "Good: 'Identify the main causal drivers of the outcome'. "
                            "Bad: 'Submit a causal_effect distribution'."
                        ),
                    },
                    "questions": {
                        "type": "array",
                        "description": (
                            "Hidden evaluation questions (the scoring agenda). The "
                            "investigator sees the research_brief, NOT these. Each "
                            "must specify question_text, eval_type, and target_node. "
                            "Use 3-5 questions. Pick eval_types that fit the "
                            "scenario naturally -- repeating a type is fine if "
                            "the research warrants it. Write question_text as "
                            "natural sub-questions a researcher would ask."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "question_text": {
                                    "type": "string",
                                    "description": (
                                        "Natural language research question. Write as a "
                                        "scientist would ask it, not as a formal instruction. "
                                        "Good: 'What factors explain why some wells experience "
                                        "sanding after nearby fracturing operations?' "
                                        "Bad: 'Estimate P(target | evidence)'."
                                    ),
                                },
                                "eval_type": {
                                    "type": "string",
                                    "enum": [
                                        "infer_target",
                                        "next_best_observation",
                                        "hypothesis_selection",
                                        "causal_effect",
                                        "best_intervention",
                                        "adjustment_set",
                                        "compare_interventions",
                                        "should_condition",
                                        "infer_latent_cause",
                                        "ate",
                                        "mediation",
                                        "interaction",
                                    ],
                                    "description": (
                                        "Type of evaluation. The PRIMARY question should almost "
                                        "always be causal (causal_effect, best_intervention, "
                                        "compare_interventions, ate). Use infer_target only as a "
                                        "complementary descriptive question, not the main one. "
                                        "causal_effect: what happens if we intervene on X? "
                                        "best_intervention: which intervention maximizes Y? "
                                        "compare_interventions: is do(X) better than do(Z)? "
                                        "ate: how MUCH does Y change when we set X high vs low? "
                                        "mediation: what fraction of X->Y goes through M? "
                                        "interaction: does the effect of X on Y depend on Z? "
                                        "adjustment_set: what to control for in analysis? "
                                        "should_condition: is controlling for Z correct? "
                                        "infer_target: descriptive baseline (complementary). "
                                        "next_best_observation: AVOID — not yet supported. "
                                        "hypothesis_selection: which hypothesis fits best? "
                                        "infer_latent_cause: what hidden factor explains this?"
                                    ),
                                },
                                "target_node": {
                                    "type": "string",
                                    "description": (
                                        "Which node this question evaluates. Must exist in "
                                        "the world. For most types, this is the target node. "
                                        "For infer_latent_cause, use a latent node."
                                    ),
                                },
                                "rationale": {
                                    "type": "string",
                                    "description": (
                                        "Why this question matters for this specific case. "
                                        "E.g., 'Understanding causal drivers is critical "
                                        "for designing preventive interventions'."
                                    ),
                                },
                                "intervention_node": {
                                    "type": "string",
                                    "description": (
                                        "Node to intervene on / treat. REQUIRED for "
                                        "causal_effect, adjustment_set, should_condition. "
                                        "Must be an observable node in the world."
                                    ),
                                },
                                "desired_state": {
                                    "type": "string",
                                    "description": (
                                        "Target state to maximize (e.g. 'high', 'healthy'). "
                                        "REQUIRED for best_intervention and "
                                        "compare_interventions. Must be a valid state of "
                                        "the target node."
                                    ),
                                },
                                "compare_nodes": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": (
                                        "Exactly two node names to compare interventions "
                                        "on. REQUIRED for compare_interventions. Both must "
                                        "be observable nodes in the world."
                                    ),
                                },
                                "condition_variable": {
                                    "type": "string",
                                    "description": (
                                        "Variable someone suggests controlling for. "
                                        "REQUIRED for should_condition (along with "
                                        "intervention_node). Must exist in the world."
                                    ),
                                },
                            },
                            "required": ["question_text", "eval_type", "target_node"],
                        },
                    },
                    "shared_budget": {
                        "type": "integer",
                        "minimum": 1,
                        "description": (
                            "Total observation budget shared across all questions. "
                            "Should be 60-80% of observable nodes to create real "
                            "tradeoffs. E.g., for 8 observables, use budget 5-6."
                        ),
                    },
                    "rationale": {
                        "type": "string",
                        "description": (
                            "Why this set of questions for this world. Explain your "
                            "reasoning for the combination of eval types chosen."
                        ),
                    },
                },
                "required": [
                    "world_id",
                    "title",
                    "research_context",
                    "research_brief",
                    "deliverables",
                    "questions",
                    "shared_budget",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_problem",
            "description": (
                "Build the final ResearchProblem that the agent will see. Samples "
                "data from the causal model and packages narrative, datasets, "
                "available actions, and budget. If you called design_case first "
                "(recommended), the research_brief becomes the visible research "
                "question, and the eval questions remain hidden for scoring. "
                "This is the LAST tool you must call — do NOT stop before this step."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "world_id": {
                        "type": "string",
                        "description": "ID of the semantically enriched world.",
                    },
                    "budget": {
                        "type": "integer",
                        "minimum": 1,
                        "description": (
                            "Research budget (in investigation units). Each action "
                            "costs 1 or more units depending on complexity. "
                            "Use the same value as shared_budget from design_case. "
                            "Should be 60-80% of observable nodes."
                        ),
                    },
                    "data_format": {
                        "type": "string",
                        "enum": ["tabular", "observations", "both"],
                        "description": (
                            "How to present sampled data. "
                            "tabular: CSV-like table with rows and columns. "
                            "observations: individual field observations as text. "
                            "both: a tabular dataset plus narrative observations."
                        ),
                    },
                    "num_data_rows": {
                        "type": "integer",
                        "minimum": 5,
                        "maximum": 500,
                        "description": (
                            "Number of rows to sample for tabular data. "
                            "50-100 is typical. More rows = more statistical power "
                            "for the agent but larger context."
                        ),
                    },
                },
                "required": ["world_id", "budget", "data_format"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "emit_inspiration_manifest",
            "description": (
                "ONLY call this when generating from a research seed (paper, case, "
                "problem description). Call AFTER design_case and BEFORE build_problem. "
                "Explain what you understood from the seed and what you intended to "
                "preserve, simplify, or change. This is NOT called for free-form goals."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "seed_understanding": {
                        "type": "string",
                        "description": (
                            "2-3 sentences: what is the seed fundamentally about? "
                            "What is the core research challenge?"
                        ),
                    },
                    "intended_scale": {
                        "type": "object",
                        "description": "How many variables from the seed you targeted",
                        "properties": {
                            "seed_vars_estimate": {"type": "integer"},
                            "target_src_nodes": {"type": "integer"},
                            "rationale": {"type": "string"},
                        },
                    },
                    "preserved_elements": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "seed_element": {"type": "string"},
                                "src_element": {"type": "string"},
                                "dimension": {"type": "string"},
                            },
                        },
                        "description": (
                            "Key elements preserved from seed. Each entry: what from "
                            "the seed, what in the SRC, which dimension (domain, scale, "
                            "causal_structure, questions, etc.)"
                        ),
                    },
                    "simplified_elements": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "seed_element": {"type": "string"},
                                "why_dropped": {"type": "string"},
                            },
                        },
                        "description": "Elements from the seed that were simplified or dropped",
                    },
                    "intended_causal_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Causal patterns you intended to include. E.g. "
                            "'confounder: geologic zone affects both operations and outcome', "
                            "'latent: geomechanical susceptibility is unobservable'"
                        ),
                    },
                    "question_mapping": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "seed_question": {"type": "string"},
                                "src_eval_type": {"type": "string"},
                                "rationale": {"type": "string"},
                            },
                        },
                        "description": "How seed research questions map to SRC eval types",
                    },
                    "type_of_work": {
                        "type": "object",
                        "description": "What type of research this is",
                        "properties": {
                            "seed_style": {
                                "type": "string",
                                "description": "observational | experimental | operational | mixed",
                            },
                            "src_style": {
                                "type": "string",
                                "description": "How the SRC represents this",
                            },
                            "researcher_activities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "What the researcher does (e.g. identify drivers, compare interventions)",
                            },
                        },
                    },
                    "data_problems": {
                        "type": "object",
                        "description": "Data quality issues from the seed",
                        "properties": {
                            "preserved": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Data problems preserved in the SRC",
                            },
                            "not_representable": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Data problems from the seed that SREG cannot represent yet",
                            },
                        },
                    },
                    "signal_noise": {
                        "type": "object",
                        "description": "How strong/subtle the effects are",
                        "properties": {
                            "intended_signal": {
                                "type": "string",
                                "description": "weak | moderate | strong",
                            },
                            "detectability": {
                                "type": "string",
                                "description": "easy | moderate | hard",
                            },
                            "rationale": {"type": "string"},
                        },
                    },
                    "research_actions": {
                        "type": "object",
                        "description": "What the researcher can do",
                        "properties": {
                            "intended_actions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Actions available in the SRC",
                            },
                            "not_supported": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Actions from the seed that SREG cannot support yet",
                            },
                        },
                    },
                    "intentional_changes": {
                        "type": "string",
                        "description": "What you changed on purpose from the seed and why",
                    },
                },
                "required": ["seed_understanding", "preserved_elements", "question_mapping"],
            },
        },
    },
]


__all__ = ["SYSTEM_PROMPT", "TOOL_DEFINITIONS"]
