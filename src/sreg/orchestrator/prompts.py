"""System prompts for the LLM orchestrator."""

SYSTEM_PROMPT = """\
You are SREG Orchestrator, an AI that generates realistic synthetic research \
problems backed by formal Bayesian networks.

Your job: given a goal or topic (e.g., "generate a research problem about marine \
ecology, medium difficulty"), produce a complete research problem that looks like \
what a real researcher would receive — with narrative, data, and questions — backed \
by a formally correct Bayesian network.

## Workflow — you MUST complete ALL 6 steps

1. **Generate** the formal world using ONE of these approaches:
   - `world_gen` — choose a template (latent_preference) for a standard structure
   - `dag_generate` — choose an algorithm (erdos_renyi, spanning_tree, \
preferential_attachment, layered) to generate a random DAG structure
   - `dag_construct` — specify the exact nodes and edges manually for full control
2. **Validate** by calling `world_check`. If it fails, adjust and retry (max 3).
3. **Apply semantics** by calling `apply_semantics`. You MUST provide `node_renames` \
with a mapping for EVERY node in the world. Each node must be renamed to a realistic \
scientific variable name that fits the scenario. Do NOT leave any node with its \
generic name. (If you used `dag_construct` with semantic names, use identity mappings.)
4. **Design the research case** by calling `design_case`. Based on the world you just \
built, design a set of evaluation questions that are specific to this scenario. \
Don't just ask generic questions — think about what a researcher would actually want \
to know given this causal structure and domain. Each question must specify an eval_type \
(infer_target, next_best_observation, hypothesis_selection, causal_effect, best_intervention, adjustment_set, compare_interventions, should_condition, or infer_latent_cause) and a target_node. \
The first question is the primary one. You choose the shared_budget.
5. **Build the problem** by calling `build_problem`. This is REQUIRED — do NOT stop \
after design_case. You must call build_problem to sample data and produce the \
final research problem.
6. Return a final JSON summary.

## How to choose a generation method

- **`world_gen`**: Simple, proven template. Good default for standard latent variable \
problems. Use when you want a well-tested structure.
- **`dag_generate`**: When you want varied topologies. Choose a generator:
  - `erdos_renyi` — random edges, good for diverse structures
  - `spanning_tree` — connected/tree-like, guaranteed connectivity
  - `preferential_attachment` — hub-spoke, a few root causes drive many effects
  - `layered` — staged/pipeline processes, causes in first layer, effects in last
- **`dag_construct`**: When you have a specific causal story in mind. You specify \
the exact nodes, types, states, and edges. Best for domain-specific structures, \
or when seeding from a research description.

## How to choose semantic names

The nodes in the formal world have generic names (hidden_cause, indicator_1, etc.). \
You must rename them to realistic scientific vocabulary that fits the scenario:

- Use real scientific terms: `water_temperature`, `enzyme_concentration`, `growth_rate`
- Place them in a FICTIONAL domain: "planet Kepler-442", "Harmon syndrome", \
"Nelvara archipelago"
- The causal relationships MAY differ from real-world science — that's by design

## How to write the scenario

Write 2-3 paragraphs that describe:
- What's happening (the research situation)
- Why it matters
- What's been tried before (theoretical context / prior findings)
- What's still unknown

Write a theoretical context that provides hints or background — this can include \
prior studies, established theories, or partial findings that may help or mislead.

## Guidelines

- Start with edge_strength around 0.6-0.8 for medium difficulty.
- Use 5-8 nodes for manageable complexity.
- If entropy is too low, reduce edge_strength (more noise).
- If entropy is too high, increase edge_strength (stronger relationships).
- Always use a deterministic seed.
- Budget should roughly equal the number of observable nodes.
- Make the scenario scientifically plausible but always fictional.

## Available templates (for world_gen)

- `latent_preference`: One or more latent variables drive observable indicators. \
Agent must infer the latent to predict the target.

## Available generators (for dag_generate)

- `erdos_renyi`: Random DAG — each edge included with probability `edge_prob`. \
Use `num_nodes` and `edge_prob` (default 0.3).
- `spanning_tree`: Connected tree + optional extra edges. Guarantees every node \
is reachable. Use `num_nodes` and `extra_edge_prob` (default 0.1).
- `preferential_attachment`: Hub-spoke structure. Early nodes get more connections. \
Use `num_nodes` and `num_edges_per_node` (default 2).
- `layered`: Pipeline/staged structure. Edges go forward between layers. \
Use `num_layers` and `nodes_per_layer` instead of `num_nodes`.

## Output

When done, respond with ONLY a JSON summary. No extra text, no follow-up \
suggestions, no explanations — just the JSON block:
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
                "Generate a synthetic Bayesian network world from a template. "
                "Returns a World object with DAG structure, CPDs, and metadata."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "template_family": {
                        "type": "string",
                        "enum": ["latent_preference"],
                        "description": "Template family to use",
                    },
                    "num_nodes": {
                        "type": "integer",
                        "minimum": 3,
                        "maximum": 20,
                        "description": "Total number of nodes in the world",
                    },
                    "num_latent": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Number of latent (hidden) nodes",
                    },
                    "num_states": {
                        "type": "integer",
                        "minimum": 2,
                        "maximum": 5,
                        "description": "Number of discrete states per node",
                    },
                    "edge_strength": {
                        "type": "number",
                        "minimum": 0.1,
                        "maximum": 1.0,
                        "description": "How deterministic the causal relationships are",
                    },
                    "seed": {
                        "type": "integer",
                        "description": "Random seed for reproducibility",
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
                "Choose a generator method and its parameters. The generator creates a "
                "random DAG structure, then CPDs are auto-generated. Nodes are named "
                "v0, v1, v2, ... and must be renamed via apply_semantics."
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
                        "description": "Which DAG generation algorithm to use",
                    },
                    "num_nodes": {
                        "type": "integer",
                        "minimum": 3,
                        "maximum": 20,
                        "description": (
                            "Total number of nodes (for erdos_renyi, spanning_tree, "
                            "preferential_attachment). Ignored for layered."
                        ),
                    },
                    "num_latent": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Number of latent (hidden) nodes (default 1)",
                    },
                    "num_target": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Number of target nodes (default 1)",
                    },
                    "num_states": {
                        "type": "integer",
                        "minimum": 2,
                        "maximum": 5,
                        "description": "Number of discrete states per node (default 3)",
                    },
                    "edge_strength": {
                        "type": "number",
                        "minimum": 0.1,
                        "maximum": 1.0,
                        "description": "How deterministic the causal relationships are",
                    },
                    "seed": {
                        "type": "integer",
                        "description": "Random seed for reproducibility",
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
                "structure: nodes (name, type, states) and directed edges. Use this "
                "when you want precise control over the causal structure. The DAG "
                "must be acyclic, have at least one target and one observable node, "
                "and each node can have at most 4 parents. Node names should be "
                "semantic (e.g., 'water_temperature', not 'v0')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "description": "List of nodes in the DAG",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Variable name (e.g., 'water_temperature')",
                                },
                                "type": {
                                    "type": "string",
                                    "enum": ["observable", "latent", "target"],
                                    "description": "Node type",
                                },
                                "states": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": (
                                        "Discrete states "
                                        "(e.g., ['low', 'medium', 'high'])"
                                    ),
                                },
                            },
                            "required": ["name", "type", "states"],
                        },
                    },
                    "edges": {
                        "type": "array",
                        "description": "List of directed edges (cause -> effect)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from": {
                                    "type": "string",
                                    "description": "Source node name (cause)",
                                },
                                "to": {
                                    "type": "string",
                                    "description": "Target node name (effect)",
                                },
                            },
                            "required": ["from", "to"],
                        },
                    },
                    "edge_strength": {
                        "type": "number",
                        "minimum": 0.1,
                        "maximum": 1.0,
                        "description": "How deterministic the causal relationships are",
                    },
                    "seed": {
                        "type": "integer",
                        "description": "Random seed for reproducibility",
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
                "Validate a generated world for quality: DAG validity, entropy, "
                "d-separation, latent nodes, and path to target."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "world_id": {
                        "type": "string",
                        "description": "ID of the world to validate",
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
                "Apply semantic layer to a world: rename ALL nodes from generic "
                "names (hidden_cause, indicator_1, etc.) to realistic scientific "
                "variable names, and add scenario narrative, domain, and "
                "theoretical context. node_renames MUST include every node. "
                "After this, you MUST call build_problem."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "world_id": {
                        "type": "string",
                        "description": "ID of the world to enrich",
                    },
                    "scenario_title": {
                        "type": "string",
                        "description": (
                            "Title of the research problem, e.g. "
                            "'Algae production decline in the Nelvara archipelago'"
                        ),
                    },
                    "scenario_description": {
                        "type": "string",
                        "description": "2-3 paragraph narrative context describing the problem",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Scientific domain, e.g. 'marine ecology'",
                    },
                    "theoretical_context": {
                        "type": "string",
                        "description": (
                            "Prior theories, hints, background findings that "
                            "provide context (can help or mislead the agent)"
                        ),
                    },
                    "node_renames": {
                        "type": "object",
                        "description": (
                            "REQUIRED: mapping from EVERY generic node name to a "
                            "semantic name. Must include ALL nodes from world_gen "
                            "(hidden_cause, indicator_1, indicator_2, ..., "
                            "target_outcome). Example: {'hidden_cause': "
                            "'soil_contamination', 'indicator_1': 'water_ph', "
                            "'indicator_2': 'nitrogen_level', 'indicator_3': "
                            "'microbial_activity', 'indicator_4': 'crop_density', "
                            "'target_outcome': 'crop_yield'}"
                        ),
                        "additionalProperties": {"type": "string"},
                    },
                    "node_descriptions": {
                        "type": "object",
                        "description": (
                            "Mapping from NEW semantic names to descriptions. "
                            "E.g. {'water_ph': 'pH level measured at monitoring stations'}"
                        ),
                        "additionalProperties": {"type": "string"},
                    },
                    "edge_descriptions": {
                        "type": "object",
                        "description": (
                            "Mapping from 'from->to' (using NEW names) to mechanism descriptions. "
                            "E.g. {'soil_contamination->crop_yield': "
                            "'Contaminated soil reduces nutrient absorption'}"
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
                "Design a research case for a specific world. Instead of always "
                "generating the same 3 tasks, you design evaluation questions that "
                "are specific to this scenario. The tool validates that questions are "
                "computable from the Bayesian network and non-degenerate. "
                "Call this AFTER apply_semantics and BEFORE build_problem."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "world_id": {
                        "type": "string",
                        "description": "ID of the semantically enriched world",
                    },
                    "title": {
                        "type": "string",
                        "description": (
                            "Short title for the research case, e.g. "
                            "'Soil contamination impact on crop yield'"
                        ),
                    },
                    "research_context": {
                        "type": "string",
                        "description": (
                            "Narrative context explaining the research scenario "
                            "(2-3 sentences minimum)"
                        ),
                    },
                    "questions": {
                        "type": "array",
                        "description": (
                            "Evaluation questions. First question is the primary one. "
                            "Each must specify question_text, eval_type, and target_node."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "question_text": {
                                    "type": "string",
                                    "description": (
                                        "Natural language question, e.g. "
                                        "'What is the most likely soil contamination level?'"
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
                                    "description": "Type of evaluation",
                                },
                                "target_node": {
                                    "type": "string",
                                    "description": (
                                        "Which node this question targets "
                                        "(must exist in the world)"
                                    ),
                                },
                                "rationale": {
                                    "type": "string",
                                    "description": "Why this question matters for this case",
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
                            "Should roughly equal the number of observable nodes."
                        ),
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Why this set of questions for this world",
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
                "Build a ResearchProblem from a semantically enriched world. "
                "Samples data from the Bayesian network and packages everything "
                "the agent will see: narrative, data, actions, question, budget."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "world_id": {
                        "type": "string",
                        "description": "ID of the semantically enriched world",
                    },
                    "budget": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Number of observations the agent can make",
                    },
                    "data_format": {
                        "type": "string",
                        "enum": ["tabular", "observations", "both"],
                        "description": "How to present the sampled data",
                    },
                    "num_data_rows": {
                        "type": "integer",
                        "minimum": 5,
                        "maximum": 500,
                        "description": "Number of rows to sample for tabular data",
                    },
                },
                "required": ["world_id", "budget", "data_format"],
            },
        },
    },
]


__all__ = ["SYSTEM_PROMPT", "TOOL_DEFINITIONS"]
