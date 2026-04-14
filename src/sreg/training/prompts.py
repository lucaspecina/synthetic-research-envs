"""Prompt rendering for SregEnv training.

Builds the initial prompt (system + user messages) from a frozen SRC.
Uses the same OI prompt builders as the production solver, ensuring
train/eval parity.
"""

from __future__ import annotations

from typing import Any

from sreg.tools.oi_prompts import (
    build_oi_briefing,
    build_oi_strategy_section,
    build_oi_system_prompt,
    build_oi_tools_section,
)


def render_oi_prompt(
    research_brief: str,
    artifact_catalog: list[dict[str, Any]],
    claim_cap: int = 15,
) -> list[dict[str, str]]:
    """Render the full OI solver prompt as a message list.

    Returns:
        List of message dicts [{role, content}, ...] suitable for
        the dataset 'prompt' column or verifiers State.
    """
    system = build_oi_system_prompt()

    user_parts = [
        build_oi_briefing(research_brief, artifact_catalog),
        build_oi_tools_section(artifact_catalog, claim_cap=claim_cap),
        build_oi_strategy_section(),
    ]
    user = "\n\n".join(user_parts)

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def render_prompt_from_src(src: dict, claim_cap: int = 15) -> list[dict[str, str]]:
    """Render prompt directly from a src.json dict.

    Convenience wrapper that extracts problem and data_assets from
    the SRC structure.
    """
    from sreg.models.research_problem import ResearchProblem

    problem = ResearchProblem(**src["problem"])

    catalog = []
    for asset in problem.data_assets:
        entry: dict[str, Any] = {
            "artifact_id": asset.artifact_id or f"dataset_{len(catalog)}",
            "description": asset.description,
        }
        if asset.columns:
            entry["columns"] = asset.columns
        if asset.num_rows is not None:
            entry["num_rows"] = asset.num_rows
        if asset.source:
            entry["source"] = asset.source
        catalog.append(entry)

    return render_oi_prompt(
        research_brief=problem.research_question,
        artifact_catalog=catalog,
        claim_cap=claim_cap,
    )
