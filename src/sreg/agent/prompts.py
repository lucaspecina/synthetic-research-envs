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

_THINK_TOOL = {
    "type": "function",
    "function": {
        "name": "think",
        "description": (
            "Record your reasoning, hypotheses, or analysis. Use this to explain "
            "what you've learned from the data, what you plan to do next, or why "
            "you're making a particular decision. This is free and has no effect "
            "on the environment — it just records your thought process."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "Your reasoning, analysis, or plan",
                },
            },
            "required": ["reasoning"],
        },
    },
}

_PYTHON_EXEC_TOOL = {
    "type": "function",
    "function": {
        "name": "python_exec",
        "description": (
            "Execute Python code in a persistent interpreter. Variables persist "
            "between calls (like a Jupyter notebook). FREE and unlimited. "
            "Pre-loaded: numpy (np), pandas (pd), scipy, math, statistics, json. "
            "Datasets are available as `df`, `df_1`, `df_2`, etc. "
            "Use this to analyze data quantitatively."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute",
                },
            },
            "required": ["code"],
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
    """Build the full tool list for the agent (research_action + python_exec + submit)."""
    return [_RESEARCH_ACTION_TOOL, _PYTHON_EXEC_TOOL, build_submit_tool(task, target_states)]


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

1. Use `python_exec` to analyze the historical data quantitatively. \
It is FREE (no budget cost). The dataset is pre-loaded as `df` (pandas DataFrame). \
Compute frequencies, conditional distributions, correlations — whatever helps.
2. Use the `research_action` tool to gather evidence about the CURRENT case. \
Each action costs budget units and returns findings.
   - **Measurements** passively observe a variable's current value.
   - **Experiments** actively set a variable to a specific value \
(a do-operation). This can reveal causal relationships that \
observations alone cannot. Note: experimenting on a variable \
may change the values of its downstream effects.
3. Use `python_exec` again to integrate new evidence with data analysis. \
Observations are available as the `observations` dict in the interpreter.
{submit_instruction}

**Strategy tip**: Analyze the data FIRST with python_exec (free), then \
spend your budget on the most informative research actions. \
Use your budget wisely — some actions cost more than others.

You MUST eventually call `submit` with your answer. Do not stop without submitting."""


# ---------------------------------------------------------------------------
# Multi-task (unified case) prompt + tools
# ---------------------------------------------------------------------------

_MULTI_SUBMIT_TOOL = {
    "type": "function",
    "function": {
        "name": "submit",
        "description": (
            "Submit your answer to ONE of the research questions. "
            "Call this once per question. You MUST include 'question' (the question number). "
            "Then provide exactly ONE of: 'distribution' (JSON string mapping states to "
            "probabilities), 'choice' (a single option), or 'variables' (list of variable names)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "integer",
                    "description": "Question number (1, 2, 3, ...)",
                },
                "distribution": {
                    "type": "object",
                    "description": (
                        "Probability distribution over target states. "
                        "Keys are state names, values are probabilities summing to 1.0."
                    ),
                    "additionalProperties": {"type": "number"},
                },
                "choice": {
                    "type": "string",
                    "description": (
                        "Single choice answer (e.g. 'A', 'B', 'yes', 'no', a variable name)"
                    ),
                },
                "variables": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of variable names (for adjustment set questions)",
                },
                "node": {
                    "type": "string",
                    "description": "Variable to intervene on (for best_intervention)",
                },
                "state": {
                    "type": "string",
                    "description": "Value to set the variable to (for best_intervention)",
                },
                "confidence": _CONFIDENCE_PROP,
                "reasoning": _REASONING_PROP,
            },
            "required": ["question"],
        },
    },
}


def build_case_tools() -> list[dict]:
    """Build tool list for multi-task case mode.

    NOTE: research_action is intentionally EXCLUDED. The old observe/intervene
    mechanic was an artificial game (see TODO.md "Horizonte siguiente").
    The solver investigates with python_exec only.
    """
    return [_THINK_TOOL, _PYTHON_EXEC_TOOL, _MULTI_SUBMIT_TOOL]


def _format_question(i: int, task: Task, problem: ResearchProblem) -> str:
    """Format a single question for the multi-task prompt."""
    lines = []
    lines.append(f"### Question {i}")
    lines.append("")
    lines.append(task.question)
    lines.append("")

    target_node = task.target_node
    if task.type in DISTRIBUTION_TYPES and task.correct_answer:
        states = list(task.correct_answer.keys())
        lines.append(f"Target: **{target_node}** (states: {', '.join(states)})")
        lines.append(f"Answer format: `submit(question={i}, distribution={{...}})`")
    elif task.type == TaskType.HYPOTHESIS_SELECTION:
        labels = sorted(task.hypotheses.keys()) if task.hypotheses else []
        lines.append(f"Options: {', '.join(labels)}")
        lines.append(f"Answer format: `submit(question={i}, choice=\"...\")`")
        if task.hypotheses:
            for label, dist in sorted(task.hypotheses.items()):
                dist_str = ", ".join(f"{s}={p:.2f}" for s, p in dist.items())
                lines.append(f"  {label}: {dist_str}")
    elif task.type == TaskType.COMPARE_INTERVENTIONS:
        lines.append(f"Answer format: `submit(question={i}, choice=\"A\" or \"B\")`")
    elif task.type == TaskType.SHOULD_CONDITION:
        lines.append(f"Answer format: `submit(question={i}, choice=\"yes\" or \"no\")`")
    elif task.type == TaskType.BEST_INTERVENTION:
        lines.append(
            f"Answer format: `submit(question={i}, node=\"...\", state=\"...\")`"
        )
    elif task.type == TaskType.ADJUSTMENT_SET:
        lines.append(
            f"Answer format: `submit(question={i}, variables=[...])`"
        )
    elif task.type == TaskType.NEXT_BEST_OBSERVATION:
        if task.correct_answer:
            options = list(task.correct_answer.keys())
            lines.append(f"Options: {', '.join(options)}")
        lines.append(f"Answer format: `submit(question={i}, choice=\"...\")`")
    else:
        lines.append(f"Target: **{target_node}**")

    return "\n".join(lines)


def build_case_system_prompt(
    problem: ResearchProblem, tasks: list[Task],
) -> str:
    """Build system prompt for multi-task case mode (all questions at once)."""
    # Data section (same as single-task)
    data_section = ""
    for asset in problem.data_assets:
        data_section += f"\n### {asset.name}\n{asset.description}\n"
        if asset.source:
            data_section += f"Source: {asset.source}\n"
        if asset.format == "tabular" and asset.data:
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

    theoretical = ""
    if problem.theoretical_context:
        theoretical = f"\n## Theoretical Context\n{problem.theoretical_context}\n"

    # Questions section
    questions_section = ""
    for i, task in enumerate(tasks, 1):
        questions_section += "\n" + _format_question(i, task, problem) + "\n"

    # Build format summary table
    format_rows = []
    for i, task in enumerate(tasks, 1):
        tt = task.type
        if tt in DISTRIBUTION_TYPES and task.correct_answer:
            keys = ", ".join(task.correct_answer.keys())
            fmt = f'`submit(question={i}, distribution={{"{keys.split(", ")[0]}": 0.X, ...}})`'
        elif tt == TaskType.SHOULD_CONDITION:
            fmt = f'`submit(question={i}, choice="yes")` or `choice="no"`'
        elif tt == TaskType.COMPARE_INTERVENTIONS:
            fmt = f'`submit(question={i}, choice="A")` or `choice="B"`'
        elif tt == TaskType.BEST_INTERVENTION:
            fmt = f'`submit(question={i}, node="...", state="...")`'
        elif tt == TaskType.ADJUSTMENT_SET:
            fmt = f'`submit(question={i}, variables=[...])`'
        else:
            fmt = f'`submit(question={i}, choice="...")`'
        format_rows.append(f"| Q{i} | {tt.value} | {fmt} |")

    format_table = "| Q | Type | Required format |\n|---|---|---|\n"
    format_table += "\n".join(format_rows)

    # Count tabular datasets for the intro
    tabular_count = sum(1 for a in problem.data_assets if a.format == "tabular")
    if tabular_count > 1:
        dataset_intro = (
            f"You have {tabular_count} historical datasets from different sources, "
            f"pre-loaded as `df`, `df_1`, `df_2`, etc. in the Python interpreter. "
            f"Each has different variables, sample sizes, and quality. "
            f"Use `python_exec` to explore ALL of them."
        )
    else:
        dataset_intro = (
            "The full dataset is pre-loaded as `df` (pandas DataFrame) in the Python "
            "interpreter — it has ALL rows, not just the preview shown below."
        )

    # Research brief section (Fase 5: brief/eval separation)
    brief_section = ""
    if problem.research_question:
        brief_section = f"""
## Research Brief

{problem.research_question}
"""

    return f"""\
You are a research scientist analyzing datasets to answer research questions. \
You have historical datasets from multiple sources and a Python interpreter \
for data analysis. {dataset_intro}

## Research Problem: {problem.title}

{problem.description}
{theoretical}{brief_section}
## Available Data

The following datasets contain historical records from the research domain. \
Analyze them to answer the research questions below.
{data_section}
## Research Questions

You must answer ALL of the following questions. \
Analyze the data systematically — what you learn for one question \
may help answer others.
{questions_section}
## Tools available

- **`think(reasoning)`** — Record your reasoning, hypotheses, or analysis plan. \
FREE. Use this to explain what you learned and what you plan to do next.
- **`python_exec(code)`** — Run Python code. FREE and unlimited. \
Datasets are pre-loaded as `df`, `df_1`, `df_2`, etc. \
Libraries available: pandas (pd), numpy (np), scipy, math, statistics, json.
- **`submit(question=N, ...)`** — Submit your answer for a question. \
You must call this for EVERY question (one call per question).

## Submission formats -- READ CAREFULLY

Each question requires a SPECIFIC format. Using the wrong format will be rejected.
{format_table}
## Notes

- The dataset previews above show only 10 rows. Use `python_exec` with `df` \
to access and analyze ALL rows.
- `python_exec` is free and unlimited. Use it to compute statistics, \
explore patterns, test hypotheses, compare subgroups — whatever you need.
- Analyze the data BEFORE answering. Do not rely on general domain knowledge alone.\
cases and compute conditional probabilities.
- You MUST use the `submit` tool for each answer. Answers written as text \
are not recorded."""


__all__ = [
    "AGENT_TOOL_DEFINITIONS",
    "CHOICE_TYPES",
    "DISTRIBUTION_TYPES",
    "build_agent_system_prompt",
    "build_agent_tools",
    "build_case_system_prompt",
    "build_case_tools",
    "build_submit_tool",
]
