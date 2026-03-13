"""System prompts and tool definitions for the LLM agent solver."""

from __future__ import annotations

from sreg.models.research_problem import ResearchActionType, ResearchProblem
from sreg.models.task import Task, TaskType

# ---------------------------------------------------------------------------
# Task type → answer format mapping
# ---------------------------------------------------------------------------

# Types where the agent submits a probability distribution
DISTRIBUTION_TYPES = {
    TaskType.INFER_TARGET,
    TaskType.CAUSAL_EFFECT,
    TaskType.INFER_LATENT_CAUSE,
}

# Types where the agent submits a choice (letter or yes/no)
CHOICE_TYPES = {
    TaskType.HYPOTHESIS_SELECTION,
    TaskType.COMPARE_INTERVENTIONS,
    TaskType.SHOULD_CONDITION,
}

# ---------------------------------------------------------------------------
# Submit tool generation (dynamic per task type)
# ---------------------------------------------------------------------------

_RESEARCH_ACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "research_action",
        "description": (
            "Execute a research action from the available list. "
            "Each action has a cost in budget units and returns findings."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_id": {
                    "type": "string",
                    "description": "ID of the action to execute (from the available actions list)",
                },
            },
            "required": ["action_id"],
        },
    },
}

# Kept for backward compatibility with legacy tests
_OBSERVE_TOOL = _RESEARCH_ACTION_TOOL

_ACTION_KIND_LABELS = {
    ResearchActionType.OBSERVE: "Measurement",
    ResearchActionType.INTERVENE: "Experiment",
    ResearchActionType.REQUEST_DATASET: "Data request",
    ResearchActionType.CONSULT: "Consultation",
}

_CONFIDENCE_PROP = {
    "type": "number",
    "minimum": 0.0,
    "maximum": 1.0,
    "description": "Your confidence in this answer (0-1)",
}

_REASONING_PROP = {
    "type": "string",
    "description": "Brief explanation of your reasoning",
}


def _distribution_submit_tool(states: list[str]) -> dict:
    """Submit tool for distribution answers (infer_target, causal_effect, etc.)."""
    example_parts = ", ".join(f'"{s}": {1/len(states):.2f}' for s in states[:3])
    return {
        "type": "function",
        "function": {
            "name": "submit",
            "description": (
                "Submit your final probability distribution over the target states. "
                "IMPORTANT: pass a 'distribution' object (NOT flat keys). "
                f'Correct: {{"distribution": {{{example_parts}}}}}. '
                f"Wrong: {{{example_parts}}}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "distribution": {
                        "type": "object",
                        "description": (
                            f"Probability distribution. Keys: {', '.join(states)}. "
                            f"Values must sum to 1.0."
                        ),
                        "additionalProperties": {"type": "number"},
                    },
                    "confidence": _CONFIDENCE_PROP,
                    "reasoning": _REASONING_PROP,
                },
                "required": ["distribution"],
            },
        },
    }


def _choice_submit_tool(options: list[str], description: str) -> dict:
    """Submit tool for choice answers (hypothesis, compare, should_condition)."""
    return {
        "type": "function",
        "function": {
            "name": "submit",
            "description": (
                f"Submit your answer. You MUST include the 'choice' key. "
                f'{description}'
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "choice": {
                        "type": "string",
                        "description": f"Your answer. One of: {', '.join(options)}",
                        "enum": options,
                    },
                    "confidence": _CONFIDENCE_PROP,
                    "reasoning": _REASONING_PROP,
                },
                "required": ["choice"],
            },
        },
    }


def _intervention_submit_tool() -> dict:
    """Submit tool for best_intervention answers."""
    return {
        "type": "function",
        "function": {
            "name": "submit",
            "description": (
                "Submit your chosen intervention. You MUST include "
                "'node' (variable name) and 'state' (value to set it to)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "Variable to intervene on",
                    },
                    "state": {
                        "type": "string",
                        "description": "Value to set the variable to",
                    },
                    "confidence": _CONFIDENCE_PROP,
                    "reasoning": _REASONING_PROP,
                },
                "required": ["node", "state"],
            },
        },
    }


def _variable_set_submit_tool() -> dict:
    """Submit tool for adjustment_set answers."""
    return {
        "type": "function",
        "function": {
            "name": "submit",
            "description": (
                "Submit your answer. Include 'variables' (list of variable names "
                "to control for), or set 'not_identifiable' to true if the causal "
                "effect cannot be identified. Use an empty list if no adjustment needed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "variables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "List of variable names to control for. "
                            "Use [] (empty list) if no confounding exists."
                        ),
                    },
                    "not_identifiable": {
                        "type": "boolean",
                        "description": (
                            "True if the causal effect cannot be identified "
                            "from observational data"
                        ),
                    },
                    "confidence": _CONFIDENCE_PROP,
                    "reasoning": _REASONING_PROP,
                },
                "required": ["variables"],
            },
        },
    }


def build_submit_tool(
    task: Task | None = None, target_states: list[str] | None = None
) -> dict:
    """Generate the submit tool definition based on task type.

    If task is None, defaults to distribution format (backward compat).
    """
    if task is None:
        return _distribution_submit_tool(target_states or ["state_a", "state_b"])

    if task.type in DISTRIBUTION_TYPES:
        states = list(task.correct_answer.keys())
        return _distribution_submit_tool(states)
    elif task.type == TaskType.HYPOTHESIS_SELECTION:
        options = sorted(task.hypotheses.keys())
        return _choice_submit_tool(
            options, f"Choose the most plausible hypothesis: {', '.join(options)}."
        )
    elif task.type == TaskType.COMPARE_INTERVENTIONS:
        return _choice_submit_tool(
            ["A", "B"], "Choose which intervention has a larger effect: A or B."
        )
    elif task.type == TaskType.SHOULD_CONDITION:
        return _choice_submit_tool(
            ["yes", "no"], "Answer whether you should control for this variable."
        )
    elif task.type == TaskType.BEST_INTERVENTION:
        return _intervention_submit_tool()
    elif task.type == TaskType.ADJUSTMENT_SET:
        return _variable_set_submit_tool()
    elif task.type == TaskType.NEXT_BEST_OBSERVATION:
        variables = list(task.correct_answer.keys()) if task.correct_answer else []
        return _choice_submit_tool(
            variables,
            f"Choose which variable to observe next: {', '.join(variables)}.",
        )
    else:
        # Unknown type — fall back to distribution
        states = list(task.correct_answer.keys()) if task.correct_answer else []
        return _distribution_submit_tool(states or target_states or ["state_a", "state_b"])


def build_agent_tools(
    task: Task | None = None, target_states: list[str] | None = None
) -> list[dict]:
    """Build the full tool list for the agent (research_action + submit)."""
    return [_RESEARCH_ACTION_TOOL, build_submit_tool(task, target_states)]


# Legacy constant for backward compat
AGENT_TOOL_DEFINITIONS = build_agent_tools()


# ---------------------------------------------------------------------------
# Format-specific submit instructions for the system prompt
# ---------------------------------------------------------------------------


def _submit_instruction(task: Task | None, problem: ResearchProblem) -> str:
    """Generate the submit instruction for the system prompt."""
    if task is None or task.type in DISTRIBUTION_TYPES:
        if task and task.correct_answer:
            states = list(task.correct_answer.keys())
        else:
            states = problem.target_states
        s0 = states[0]
        s1 = states[-1]
        return (
            f"4. When ready, use the `submit` tool. You MUST include a "
            f"`distribution` key with probabilities that sum to 1.0. "
            f'Example: {{"distribution": {{"{s0}": 0.5, "{s1}": 0.5}}}}'
        )
    elif task.type == TaskType.HYPOTHESIS_SELECTION:
        labels = sorted(task.hypotheses.keys())
        return (
            f"4. When ready, use the `submit` tool with your `choice` "
            f"({', '.join(labels)})."
        )
    elif task.type == TaskType.COMPARE_INTERVENTIONS:
        return (
            '4. When ready, use the `submit` tool with your `choice` ("A" or "B"). '
            "Pick the intervention with a larger causal effect."
        )
    elif task.type == TaskType.SHOULD_CONDITION:
        return (
            '4. When ready, use the `submit` tool with your `choice` ("yes" or "no").'
        )
    elif task.type == TaskType.BEST_INTERVENTION:
        return (
            "4. When ready, use the `submit` tool with `node` and `state` — "
            "the variable and value you would intervene on."
        )
    elif task.type == TaskType.ADJUSTMENT_SET:
        return (
            "4. When ready, use the `submit` tool with `variables` — the list "
            "of variables to control for (empty list if none needed, or set "
            "`not_identifiable` to true)."
        )
    elif task.type == TaskType.NEXT_BEST_OBSERVATION:
        return (
            "4. When ready, use the `submit` tool with your `choice` — "
            "the variable you would observe next."
        )
    # Unknown fallback
    return "4. When ready, use the `submit` tool with your answer."


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


def build_agent_system_prompt(
    problem: ResearchProblem, task: Task | None = None
) -> str:
    """Build a system prompt presenting the research problem to the agent.

    If task is provided, uses the task's question and generates format-specific
    submit instructions. Otherwise defaults to infer_target behavior.
    """
    # Format data assets
    data_section = ""
    for asset in problem.data_assets:
        data_section += f"\n### {asset.name}\n{asset.description}\n"
        if asset.source:
            data_section += f"Source: {asset.source}\n"
        if asset.format == "tabular" and asset.data:
            # Show header + first rows
            headers = list(asset.data[0].keys())
            data_section += f"Columns: {', '.join(headers)}\n"
            data_section += f"Total rows: {asset.num_rows or len(asset.data)}\n\n"
            max_rows = min(10, len(asset.data))
            data_section += " | ".join(headers) + "\n"
            data_section += " | ".join(["---"] * len(headers)) + "\n"
            for row in asset.data[:max_rows]:
                data_section += " | ".join(str(row.get(h, "")) for h in headers) + "\n"
            if len(asset.data) > max_rows:
                data_section += f"... ({len(asset.data) - max_rows} more rows)\n"
        elif asset.format == "narrative" and asset.data:
            for obs in asset.data[:10]:
                src = obs.get("source", "unknown")
                data_section += f"- [{src}] {obs.get('observation', obs)}\n"
        elif asset.format == "observations" and asset.data:
            for obs in asset.data[:10]:
                data_section += f"- {obs.get('observation', obs)}\n"

    # Format available actions with IDs
    actions_section = ""
    for action in problem.available_actions:
        kind = _ACTION_KIND_LABELS.get(action.action_type, "Action")
        actions_section += (
            f"- **{action.id}** ({kind}, cost: {action.cost}): {action.description}\n"
        )

    # Format target states
    states_str = ", ".join(problem.target_states)

    theoretical = ""
    if problem.theoretical_context:
        theoretical = f"\n## Theoretical Context\n{problem.theoretical_context}\n"

    # Use task question if provided, otherwise problem's research_question
    research_question = task.question if task else problem.research_question

    # For hypothesis_selection: append the candidate distributions to the question
    # so the agent sees them even when the orchestrator overwrote the question
    # with a narrative version that omits the distributions.
    hypotheses_section = ""
    if task and task.type == TaskType.HYPOTHESIS_SELECTION and task.hypotheses:
        hyp_lines = []
        for label, dist in sorted(task.hypotheses.items()):
            dist_str = ", ".join(f"{s}={p:.2f}" for s, p in dist.items())
            hyp_lines.append(f"  {label}: {dist_str}")
        hypotheses_section = (
            "\n\n## Candidate Hypotheses\n"
            "Each hypothesis is a probability distribution over the target variable.\n\n"
            + "\n".join(hyp_lines)
        )

    # Use task's target node when it differs from problem (e.g. infer_latent_cause)
    target_node = task.target_node if task else problem.target_node

    # Only override states_str for distribution types — for choice/intervention/etc.
    # the correct_answer keys are options, not "possible states" of a variable.
    if (
        task
        and task.correct_answer
        and (task.type is None or task.type in DISTRIBUTION_TYPES)
    ):
        states_str = ", ".join(task.correct_answer.keys())

    # Format-specific submit instruction
    submit_instruction = _submit_instruction(task, problem)

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

You have a research budget of **{problem.budget}** units. Each action \
returns findings about the current case, but costs budget \
units (see the action list below — costs may vary).

### Available Research Actions
{actions_section}
## Research Question

{research_question}
{hypotheses_section}

Your target variable is **{target_node}** with possible states: \
{states_str}.

## Instructions

1. Study the historical data to understand correlations between variables.
2. Use the `research_action` tool to execute actions from the list above. \
Each action costs budget units and returns findings about the current case.
   - **Measurements** passively observe a variable's current value.
   - **Experiments** actively set a variable to a specific value \
(a do-operation). This can reveal causal relationships that \
observations alone cannot. Note: experimenting on a variable \
may change the values of its downstream effects.
3. After each action, update your beliefs about the target.
{submit_instruction}

**Strategy tip**: Use your budget wisely — some actions cost more than others. \
Choose actions that will help you answer the research question.

You MUST eventually call `submit` with your answer. Do not stop without submitting."""


__all__ = [
    "AGENT_TOOL_DEFINITIONS",
    "CHOICE_TYPES",
    "DISTRIBUTION_TYPES",
    "build_agent_system_prompt",
    "build_agent_tools",
    "build_submit_tool",
]
