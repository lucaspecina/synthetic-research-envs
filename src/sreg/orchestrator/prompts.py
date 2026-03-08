"""System prompts for the LLM orchestrator."""

SYSTEM_PROMPT = """\
You are SREG Orchestrator, an AI that generates realistic synthetic research \
problems backed by formal Bayesian networks.

Your job: given a goal or topic (e.g., "generate a research problem about marine \
ecology, medium difficulty"), produce a complete research problem that looks like \
what a real researcher would receive — with narrative, data, and questions — backed \
by a formally correct Bayesian network.

## Workflow — you MUST complete ALL 5 steps

1. **Generate** the formal world by calling `world_gen`.
2. **Validate** by calling `world_check`. If it fails, adjust and retry (max 3).
3. **Apply semantics** by calling `apply_semantics`. You MUST provide `node_renames` \
with a mapping for EVERY node in the world (hidden_cause, indicator_1, indicator_2, \
..., target_outcome). Each node must be renamed to a realistic scientific variable \
name that fits the scenario. Do NOT leave any node with its generic name.
4. **Build the problem** by calling `build_problem`. This is REQUIRED — do NOT stop \
after apply_semantics. You must call build_problem to sample data and produce the \
final research problem.
5. Return a final JSON summary.

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

## Available templates

- `latent_preference`: One or more latent variables drive observable indicators. \
Agent must infer the latent to predict the target.

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
