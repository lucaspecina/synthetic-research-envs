"""System prompts for the LLM orchestrator."""

SYSTEM_PROMPT = """\
You are SREG Orchestrator, an AI that generates realistic synthetic research \
problems backed by formal Bayesian networks.

Your job: given a goal or topic (e.g., "generate a research problem about marine \
ecology, medium difficulty"), produce a complete research problem that looks like \
what a real researcher would receive — with narrative, data, and questions — backed \
by a formally correct Bayesian network.

## Workflow — you MUST complete ALL 6 steps in order

1. **Generate** the formal world using ONE of these approaches:
   - `dag_construct` — specify the exact nodes and edges manually. **Best for \
domain-specific structures or when the goal describes specific variables.** \
You control the causal story directly.
   - `dag_generate` — choose an algorithm (erdos_renyi, spanning_tree, layered) \
to generate a random DAG structure. Good for generic topics where you don't \
need precise control.
   - `world_gen` — use a template (latent_preference). Simple, proven structure.
2. **Validate** by calling `world_check`. If it fails, adjust and retry (max 3).
3. **Apply semantics** by calling `apply_semantics`. Rename ALL nodes to realistic \
scientific variable names, write the scenario narrative, domain, and theoretical \
context. You MUST provide `node_renames` with a mapping for EVERY node. \
Even if nodes already have semantic names (from dag_construct), pass identity \
mappings like `{"water_temperature": "water_temperature", ...}`. NEVER omit \
`node_renames` or pass it empty — the call WILL fail.
4. **Design the research case** by calling `design_case`. This is the most \
important step — design evaluation questions that a real researcher would ask \
given this scenario. See "Evaluation types" below for guidance on choosing \
the right eval_type for each question.
5. **Inspiration manifest** (ONLY when generating from a research seed/paper): \
call `emit_inspiration_manifest` to record what you understood from the seed, \
what you preserved, what you simplified, and how seed questions map to eval types. \
Skip this step if the goal is a free-form topic (not a seed).
6. **Build the problem** by calling `build_problem`. This samples data from the \
Bayesian network and produces the final research problem. It automatically uses \
the research case you designed in step 4 (the primary question text becomes the \
visible research question, and actions get realistic costs).
7. Return a final JSON summary.

## Evaluation types — when to use each one

Each question in `design_case` must have an `eval_type`. Choose based on \
what a researcher would naturally ask:

- **`infer_target`**: "What is the most likely state of Y given what we know?" \
Use as the primary question when the case is about diagnosing or predicting an \
outcome. Scored by KL divergence against the true posterior.

- **`causal_effect`**: "If we force X to value x (intervene), what happens to Y?" \
Use when the research question involves interventions, policy changes, or \
counterfactuals. Computes P(Y | do(X=x)) via do-calculus. \
Example: "If we increase pad spacing, how does sanding risk change?"

- **`best_intervention`**: "Which single intervention maximizes a desired outcome?" \
Use when comparing multiple possible actions to find the optimal one. \
Example: "Which variable should we intervene on to minimize mortality?"

- **`compare_interventions`**: "Is intervening on X better than intervening on Z?" \
Use for pairwise comparison of two specific interventions. \
Example: "Does reducing pressure help more than increasing spacing?"

- **`next_best_observation`**: "What should we measure next to learn the most?" \
Use when the case involves resource-constrained data collection. \
Scored by information gain.

- **`adjustment_set`**: "What variables should we control for in our analysis?" \
Use when the case involves confounding or observational data analysis. \
Scored by set F1 against the valid backdoor adjustment set.

- **`should_condition`**: "Someone suggests controlling for Z — is that correct?" \
Use when there's a risk of conditioning on a collider or mediator. \
Binary yes/no answer.

- **`hypothesis_selection`**: "Which of these hypotheses best explains the data?" \
Use when the case involves competing theories. Scored by binary match.

- **`infer_latent_cause`**: "What is the hidden factor behind the observed symptoms?" \
Use when there's a latent variable and the case involves diagnostic reasoning. \
Scored by KL divergence against the true posterior over the latent node.

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

For `infer_target`, `next_best_observation`, `hypothesis_selection`, and \
`infer_latent_cause`, no hints are needed — just question_text and target_node.

**Guidelines for question design:**
- Use 3-5 questions per case. Don't use all types — pick the ones that fit naturally.
- The first question is the PRIMARY one (shown to the agent as the main research question).
- Every question must feel like something a scientist would ask, not a graph theory exercise.
- Don't repeat the same eval_type + target_node combination.
- Write question_text as a natural research question, not as a formal instruction.
- For node-sensitive types, always provide the required hints (see above).

## How to choose a generation method

- **`dag_construct`** (PREFERRED): When the goal mentions specific variables or a \
domain with known causal relationships. You specify exact nodes (name, type, \
states) and edges. Node names should be semantic from the start (e.g., \
'water_temperature', not 'v0'). When using dag_construct with semantic names, \
use identity mappings in apply_semantics.
- **`dag_generate`**: When you want varied topologies without a specific causal story.
  - `erdos_renyi` — random edges, diverse structures
  - `spanning_tree` — connected/tree-like, guaranteed connectivity
  - `layered` — staged/pipeline processes, causes flow forward through layers
- **`world_gen`**: Simple latent_preference template. Use only for basic structures.

Do NOT use `preferential_attachment` — it has known quality issues.

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
            "name": "world_gen",
            "description": (
                "Generate a Bayesian network world from a predefined template. "
                "Use this for simple, well-tested structures. The template creates "
                "a standard latent variable problem where hidden causes drive "
                "observable indicators. Returns a world with generic node names "
                "(hidden_cause, indicator_1, etc.) that must be renamed via "
                "apply_semantics. Prefer dag_construct for domain-specific cases."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "template_family": {
                        "type": "string",
                        "enum": ["latent_preference"],
                        "description": (
                            "latent_preference: one or more latent variables drive "
                            "observable indicators. Agent must infer the latent to "
                            "predict the target. This is the only available template."
                        ),
                    },
                    "num_nodes": {
                        "type": "integer",
                        "minimum": 3,
                        "maximum": 20,
                        "description": (
                            "Total number of nodes in the world. "
                            "Recommended: 8-12 for good complexity."
                        ),
                    },
                    "num_latent": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Number of latent (hidden) nodes. Default: 1.",
                    },
                    "num_states": {
                        "type": "integer",
                        "minimum": 2,
                        "maximum": 5,
                        "description": (
                            "Number of discrete states per node. "
                            "2 = binary, 3 = low/medium/high. Default: 3."
                        ),
                    },
                    "edge_strength": {
                        "type": "number",
                        "minimum": 0.1,
                        "maximum": 1.0,
                        "description": (
                            "How deterministic the causal relationships are. "
                            "0.1 = very noisy, 0.9 = nearly deterministic. "
                            "Recommended: 0.6-0.7 for medium difficulty."
                        ),
                    },
                    "seed": {
                        "type": "integer",
                        "description": "Random seed for reproducibility. Always provide one.",
                    },
                },
                "required": ["template_family", "num_nodes", "edge_strength", "seed"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dag_generate",
            "description": (
                "Generate a Bayesian network world using an algorithmic DAG generator. "
                "Use this when you want varied topologies without specifying exact "
                "structure. The generator creates a random DAG, then CPDs are "
                "auto-generated from edge_strength. Nodes are named v0, v1, v2, ... "
                "and MUST be renamed via apply_semantics. Do NOT use "
                "preferential_attachment (known quality issues). "
                "Prefer dag_construct when the goal describes specific variables."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "generator": {
                        "type": "string",
                        "enum": [
                            "erdos_renyi",
                            "spanning_tree",
                            "preferential_attachment",
                            "layered",
                        ],
                        "description": (
                            "erdos_renyi: random edges with probability edge_prob, "
                            "good for diverse structures. "
                            "spanning_tree: connected tree + optional extra edges, "
                            "guarantees every node is reachable. "
                            "layered: staged/pipeline process, causes in first layer "
                            "flow forward to effects in last layer. "
                            "preferential_attachment: DO NOT USE (0% quality pass rate)."
                        ),
                    },
                    "num_nodes": {
                        "type": "integer",
                        "minimum": 3,
                        "maximum": 20,
                        "description": (
                            "Total number of nodes (for erdos_renyi, spanning_tree, "
                            "preferential_attachment). Ignored for layered. "
                            "Recommended: 8-12."
                        ),
                    },
                    "num_latent": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Number of latent (hidden) nodes. Default: 1.",
                    },
                    "num_target": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Number of target nodes. Default: 1.",
                    },
                    "num_states": {
                        "type": "integer",
                        "minimum": 2,
                        "maximum": 5,
                        "description": "Number of discrete states per node. Default: 3.",
                    },
                    "edge_strength": {
                        "type": "number",
                        "minimum": 0.1,
                        "maximum": 1.0,
                        "description": (
                            "How deterministic the causal relationships are. "
                            "Recommended: 0.6-0.7 for medium difficulty."
                        ),
                    },
                    "seed": {
                        "type": "integer",
                        "description": "Random seed for reproducibility.",
                    },
                    "edge_prob": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Edge probability (erdos_renyi only, default 0.3)",
                    },
                    "extra_edge_prob": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": (
                            "Extra edge probability beyond tree "
                            "(spanning_tree only, default 0.1)"
                        ),
                    },
                    "num_edges_per_node": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 4,
                        "description": (
                            "Edges per new node "
                            "(preferential_attachment only, default 2)"
                        ),
                    },
                    "num_layers": {
                        "type": "integer",
                        "minimum": 2,
                        "description": "Number of layers (layered only, default 4)",
                    },
                    "nodes_per_layer": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Nodes per layer (layered only, default 3)",
                    },
                    "inter_layer_prob": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": (
                            "Edge probability between adjacent layers "
                            "(layered only, default 0.5)"
                        ),
                    },
                    "skip_layer_prob": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": (
                            "Edge probability skipping one layer "
                            "(layered only, default 0.1)"
                        ),
                    },
                },
                "required": ["generator", "edge_strength", "seed"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dag_construct",
            "description": (
                "Construct a Bayesian network world by specifying the exact DAG "
                "structure: nodes (name, type, states) and directed edges. "
                "This is the PREFERRED method when the goal describes specific "
                "variables or a domain with known causal relationships. You have "
                "full control over the causal story. "
                "Constraints: DAG must be acyclic, have at least 1 target and "
                "1 observable node, each node can have at most 4 parents. "
                "Use semantic names directly (e.g., 'water_temperature') — "
                "then use identity mappings in apply_semantics. "
                "Include at least 1 latent node for diagnostic reasoning tasks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "description": (
                            "List of nodes in the DAG. Each node needs a name, "
                            "type, and discrete states. Use 8-12 nodes for good "
                            "complexity. Include at least 1 latent node."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": (
                                        "Semantic variable name using snake_case. "
                                        "E.g., 'water_temperature', 'fracture_pressure', "
                                        "'enzyme_concentration'. NOT 'v0' or 'indicator_1'."
                                    ),
                                },
                                "type": {
                                    "type": "string",
                                    "enum": ["observable", "latent", "target"],
                                    "description": (
                                        "observable: the agent can choose to measure this. "
                                        "latent: hidden variable, never directly observed. "
                                        "target: the outcome variable the agent must predict "
                                        "(exactly 1 required)."
                                    ),
                                },
                                "states": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": (
                                        "2-4 discrete states. Use meaningful labels. "
                                        "E.g., ['low', 'medium', 'high'] or "
                                        "['no', 'yes'] or ['type_A', 'type_B', 'type_C']."
                                    ),
                                },
                            },
                            "required": ["name", "type", "states"],
                        },
                    },
                    "edges": {
                        "type": "array",
                        "description": (
                            "Directed causal edges (cause -> effect). Each edge means "
                            "'from' causally influences 'to'. The resulting graph must "
                            "be a DAG (no cycles). Each node can have at most 4 parents."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "from": {
                                    "type": "string",
                                    "description": "Source node name (the cause)",
                                },
                                "to": {
                                    "type": "string",
                                    "description": "Destination node name (the effect)",
                                },
                            },
                            "required": ["from", "to"],
                        },
                    },
                    "edge_strength": {
                        "type": "number",
                        "minimum": 0.1,
                        "maximum": 1.0,
                        "description": (
                            "How deterministic the causal relationships are. "
                            "0.6-0.7 recommended for medium difficulty."
                        ),
                    },
                    "seed": {
                        "type": "integer",
                        "description": "Random seed for reproducibility.",
                    },
                },
                "required": ["nodes", "edges", "edge_strength", "seed"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "world_check",
            "description": (
                "Validate a generated world for quality. Checks: DAG validity "
                "(acyclic, connected), entropy (not too low/high), d-separation "
                "(latent nodes provide information), path from observables to "
                "target, max parents per node, treewidth. Returns pass/fail with "
                "specific failure reasons and metrics. Call this immediately after "
                "generating the world. If it fails, adjust parameters and regenerate."
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
                "Design a research case with evaluation questions for a specific "
                "world. This is the most important step — you choose WHAT questions "
                "to ask and WHY. Each question has an eval_type that determines how "
                "it will be scored mathematically. The tool validates that questions "
                "are computable from the Bayesian network and non-degenerate. "
                "The first question is the PRIMARY one — its question_text becomes "
                "the visible research question the agent sees. "
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
                    "questions": {
                        "type": "array",
                        "description": (
                            "Evaluation questions. First question is the PRIMARY one "
                            "(its text becomes the agent's visible research question). "
                            "Each must specify question_text, eval_type, and target_node. "
                            "Use 3-5 questions with different eval_types."
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
                                    ],
                                    "description": (
                                        "Type of evaluation. Choose based on the question: "
                                        "infer_target: predict/diagnose an outcome. "
                                        "causal_effect: what happens if we intervene on X? "
                                        "best_intervention: which intervention maximizes Y? "
                                        "compare_interventions: is do(X) better than do(Z)? "
                                        "next_best_observation: what to measure next? "
                                        "adjustment_set: what to control for in analysis? "
                                        "should_condition: is controlling for Z correct? "
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
                "data from the Bayesian network and packages narrative, datasets, "
                "available actions, and budget. If you called design_case first "
                "(recommended), this tool automatically uses your research case: "
                "the primary question text becomes the visible research question, "
                "and actions get realistic varied costs based on the DAG structure. "
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
