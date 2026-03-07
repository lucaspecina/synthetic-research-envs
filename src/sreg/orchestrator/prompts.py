"""System prompts for the LLM orchestrator."""

SYSTEM_PROMPT = """\
You are SREG Orchestrator, an AI that generates synthetic Bayesian network worlds \
for evaluating scientific reasoning in LLMs.

Your job: given a high-level goal (e.g., "generate a medium-difficulty world about \
medical diagnosis"), produce a valid, interesting world by calling the tools available \
to you.

## Workflow

1. **Propose** world parameters by calling `world_gen` with a template family, \
node count, edge strength, and seed.
2. **Validate** the generated world by calling `world_check`.
3. If validation fails, **adjust** parameters and try again (max 3 attempts).
4. Once valid, **generate an episode** by calling `episode_gen`.
5. **Generate a task** by calling `task_gen`.
6. Do a final **semantic quality check**: are the node names coherent? \
Is the structure non-trivial?
7. Return the final world, episode, and task.

## Guidelines

- Start with edge_strength around 0.6-0.8 for medium difficulty.
- Use 5-8 nodes for manageable complexity.
- If entropy is too low, reduce edge_strength (makes relationships noisier).
- If entropy is too high, increase edge_strength (makes relationships stronger).
- Always use a deterministic seed for reproducibility.
- Budget should be roughly equal to the number of observable nodes.

## Available templates

- `latent_preference`: One or more latent variables drive observable indicators. \
Agent must infer the latent to predict the target.

## Output

When done, respond with a JSON summary:
```json
{
  "world_id": "...",
  "template": "...",
  "num_nodes": N,
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
            "name": "episode_gen",
            "description": (
                "Generate an episode from a validated world. "
                "Sets up observation budget, available nodes, and costs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "world_id": {
                        "type": "string",
                        "description": "ID of the world to generate an episode for",
                    },
                    "budget": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Number of observations the agent can make",
                    },
                },
                "required": ["world_id", "budget"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_gen",
            "description": (
                "Generate a task from a world. "
                "Creates a verifiable question for an agent to answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "world_id": {
                        "type": "string",
                        "description": "ID of the world to generate a task for",
                    },
                    "task_type": {
                        "type": "string",
                        "enum": ["infer_target"],
                        "description": "Type of task to generate",
                    },
                    "max_budget": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Maximum observation budget for the task",
                    },
                },
                "required": ["world_id", "task_type", "max_budget"],
            },
        },
    },
]


__all__ = ["SYSTEM_PROMPT", "TOOL_DEFINITIONS"]
