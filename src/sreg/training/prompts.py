"""Prompt rendering for training: converts ResearchProblem into agent-visible text."""

from __future__ import annotations

from sreg.models.research_problem import AvailableAction, DataAsset, ResearchProblem

SYSTEM_PROMPT = (
    "You are a research agent solving a synthetic scientific investigation. "
    "Use research actions to gather evidence, and python_exec to analyze data "
    "(numpy, pandas, scipy are pre-loaded). Each research action costs budget; "
    "python_exec is free. Observations are available as the `observations` dict. "
    "Datasets (if any) are pre-loaded as `df`. Submit your final answer when ready."
)


def render_case_prompt(problem: ResearchProblem) -> str:
    """Render a ResearchProblem as the user prompt for the agent."""
    sections = [
        f"# {problem.title}",
        "",
        problem.description,
    ]

    if problem.theoretical_context:
        sections.extend(["", "## Background", "", problem.theoretical_context])

    if problem.data_assets:
        sections.extend(["", "## Available Data"])
        for asset in problem.data_assets:
            sections.append(f"\n### {asset.name}")
            sections.append(asset.description)
            if asset.num_rows:
                sections.append(f"Rows: {asset.num_rows}")
            if asset.data:
                sections.append(_render_data_preview(asset))

    sections.extend(
        [
            "",
            "## Available Research Actions",
            f"Budget: {problem.budget} units",
            "",
        ]
    )
    for action in problem.available_actions:
        sections.append(_render_action(action))

    sections.extend(
        [
            "",
            "## Research Question",
            "",
            problem.research_question,
            "",
            f"Target variable: {problem.target_node}",
            f"Possible states: {', '.join(problem.target_states)}",
        ]
    )

    return "\n".join(sections)


def _render_action(action: AvailableAction) -> str:
    """Render a single available action."""
    action_type = (
        action.action_type.value
        if hasattr(action.action_type, "value")
        else str(action.action_type)
    )
    parts = [f"- **{action.id}** [{action_type}, cost: {action.cost}]: {action.description}"]
    if action.intervention_values:
        effects = ", ".join(f"{k}={v}" for k, v in action.intervention_values.items())
        parts.append(f"  Sets: {effects}")
    return "\n".join(parts)


def _render_data_preview(asset: DataAsset, max_rows: int = 5) -> str:
    """Render a preview of data rows."""
    if not asset.data:
        return ""

    rows = asset.data[:max_rows]
    if not rows:
        return ""

    # Get column names from first row
    columns = asset.columns or list(rows[0].keys())

    # Build simple table
    header = " | ".join(str(c) for c in columns)
    separator = " | ".join("---" for _ in columns)
    lines = [header, separator]
    for row in rows:
        line = " | ".join(str(row.get(c, "")) for c in columns)
        lines.append(line)

    if len(asset.data) > max_rows:
        lines.append(f"... ({len(asset.data) - max_rows} more rows)")

    return "\n".join(lines)
