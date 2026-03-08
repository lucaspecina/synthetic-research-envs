"""System prompts and tool definitions for the LLM agent solver."""

from __future__ import annotations

from sreg.models.research_problem import ResearchProblem


def build_agent_system_prompt(problem: ResearchProblem) -> str:
    """Build a system prompt presenting the research problem to the agent."""
    # Format data assets
    data_section = ""
    for asset in problem.data_assets:
        data_section += f"\n### {asset.name}\n{asset.description}\n"
        if asset.format == "tabular" and asset.data:
            # Show header + first rows
            headers = list(asset.data[0].keys())
            data_section += f"Columns: {', '.join(headers)}\n"
            data_section += f"Total rows: {len(asset.data)}\n\n"
            # Show first 10 rows as a table
            max_rows = min(10, len(asset.data))
            data_section += " | ".join(headers) + "\n"
            data_section += " | ".join(["---"] * len(headers)) + "\n"
            for row in asset.data[:max_rows]:
                data_section += " | ".join(str(row.get(h, "")) for h in headers) + "\n"
            if len(asset.data) > max_rows:
                data_section += f"... ({len(asset.data) - max_rows} more rows)\n"
        elif asset.format == "observations" and asset.data:
            for obs in asset.data[:10]:
                data_section += f"- {obs.get('observation', obs)}\n"

    # Format available actions
    actions_section = ""
    for action in problem.available_actions:
        actions_section += f"- **{action.node}**: {action.description} (cost: {action.cost})\n"

    # Format target states
    states_str = ", ".join(problem.target_states)

    theoretical = ""
    if problem.theoretical_context:
        theoretical = f"\n## Theoretical Context\n{problem.theoretical_context}\n"

    return f"""\
You are a research scientist investigating a NEW CASE. You have historical \
reference data AND the ability to run measurements on the current case.

## Research Problem: {problem.title}

{problem.description}
{theoretical}
## Historical Reference Data

The following is HISTORICAL data from previous cases. It shows patterns and \
correlations, but it is NOT data about the current case.
{data_section}
## Measurements on the Current Case

You are investigating a SPECIFIC NEW CASE. You do not know the actual values \
of any variable for this case yet. The historical data above shows general \
patterns, but the current case may differ.

You have a budget of **{problem.budget}** measurement(s). Each measurement \
reveals the TRUE VALUE of a variable for the current case. Use measurements \
strategically to narrow down your estimate of the target.

{actions_section}
## Research Question

{problem.research_question}

Your target variable is **{problem.target_node}** with possible states: \
{states_str}.

## Instructions

1. Study the historical data to understand correlations between variables.
2. Use the `observe` tool to measure variables FOR THE CURRENT CASE. Each \
observation reveals the true state and costs 1 budget point.
3. After each observation, update your beliefs about the target.
4. When ready, use the `submit` tool with your probability distribution.
5. Your distribution must sum to 1.0.

**Strategy tip**: The historical data shows correlations. Observing variables \
that are strongly correlated with the target will help you predict it better. \
Use your budget wisely.

You MUST eventually call `submit` with your answer. Do not stop without submitting."""


AGENT_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "observe",
            "description": (
                "Request a measurement of a variable. Returns the observed "
                "state. Costs 1 budget point per observation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "variable": {
                        "type": "string",
                        "description": "Name of the variable to observe",
                    },
                },
                "required": ["variable"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit",
            "description": (
                "Submit your final probability distribution over the target "
                "variable states. This ends the episode."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "distribution": {
                        "type": "object",
                        "description": (
                            "Probability distribution over target states. "
                            "Keys are state names, values are probabilities "
                            "that must sum to 1.0. "
                            "Example: {\"low\": 0.2, \"medium\": 0.5, \"high\": 0.3}"
                        ),
                        "additionalProperties": {"type": "number"},
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Your confidence in this answer (0-1)",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Brief explanation of your reasoning",
                    },
                },
                "required": ["distribution"],
            },
        },
    },
]


__all__ = ["AGENT_TOOL_DEFINITIONS", "build_agent_system_prompt"]
