"""OI Solver Prompt: system prompt template for Open Investigation mode.

Converts solver prompt design (research/notes/oi_solver_prompt_design.md)
into executable code. The prompt guides an LLM solver to investigate
freely and submit structured ClaimCards.

Key design decisions (from Codex review):
- No mention of scoring or how claims are evaluated (prevents gaming)
- Association vs causation guidance (anti-overclaiming)
- Epistemological closure criteria, not call count
- Artifact catalog shows full metadata (columns, source, num_rows)
"""

from __future__ import annotations

from typing import Any


def build_oi_system_prompt() -> str:
    """Build the system section of the OI solver prompt."""
    return (
        "You are a research scientist conducting an investigation. You have been "
        "given a research brief describing a phenomenon and access to datasets "
        "collected from real observations and studies.\n\n"
        "Your goal is to INVESTIGATE: discover how variables in this system "
        "relate, what patterns exist, and what mechanisms might be operating. "
        "Then report your findings as structured claim cards.\n\n"
        "IMPORTANT: Use causal language (\"X causes Y\") ONLY when your evidence "
        "supports it -- experimental or quasi-experimental design, or careful "
        "adjustment for confounders with explicit reasoning. Otherwise use "
        "associational language (\"X is associated with Y\", \"X predicts Y\"). "
        "Observational regression alone does not establish causation.\n\n"
        "You do NOT have predetermined questions to answer. You decide what to "
        "investigate, how to investigate it, and what conclusions to draw. The "
        "quality of your research depends on what you discover, how well you "
        "support your claims with evidence, and how much of the phenomenon you "
        "manage to characterize."
    )


def build_oi_tools_section(artifact_catalog: list[dict[str, Any]]) -> str:
    """Build the tools section listing available tools + artifact catalog."""
    catalog_lines = []
    for entry in artifact_catalog:
        line = f"  - **{entry['artifact_id']}**: {entry.get('description', '')}"
        if entry.get("num_rows"):
            line += f" ({entry['num_rows']} rows)"
        if entry.get("columns"):
            cols = ", ".join(entry["columns"][:10])
            if len(entry["columns"]) > 10:
                cols += f", ... ({len(entry['columns'])} total)"
            line += f"\n    Columns: {cols}"
        if entry.get("source"):
            line += f"\n    Source: {entry['source']}"
        catalog_lines.append(line)

    catalog_text = "\n".join(catalog_lines) if catalog_lines else "  (none)"

    return (
        "## Available tools\n\n"
        "### load_artifact(artifact_id)\n"
        "Load a dataset by its ID. Returns a pandas DataFrame.\n"
        "IMPORTANT: `load_artifact` is already in your namespace. Do NOT "
        "import it. Just call: `df = load_artifact('dataset_main')`\n\n"
        "Available artifacts:\n"
        f"{catalog_text}\n\n"
        "### python_exec(code)\n"
        "Execute Python code. The following are already available in your "
        "namespace -- do NOT import them:\n"
        "  - `pd` (pandas), `np` (numpy), `math`, `statistics`\n"
        "  - `load_artifact`, `save_artifact`\n\n"
        "You can also import: `statsmodels`, `linearmodels` (for IV/FE/panel), "
        "`sklearn`, `scipy`. **NOT available**: seaborn, matplotlib.\n\n"
        "Common analysis patterns:\n"
        "  df[['A', 'Y']].corr()                      # correlation\n"
        "  import statsmodels.api as sm                 # OLS regression\n"
        "  sm.OLS(df['Y'], sm.add_constant(df[['A', 'C']])).fit()\n"
        "  df.groupby('Z')['Y'].mean()                 # stratified means\n"
        "  aid = save_artifact(result_df, label='filtered')\n"
        "  # save_artifact prints '[save_artifact] saved as derived_filtered_xxxxxx'\n"
        "  # use that exact id (or `aid`) when citing in evidence_basis.\n\n"
        "### submit_claims(claims)\n"
        "Submit your research findings as structured claim cards. You can "
        "submit 1-5 claims. Fewer strong claims are better than many weak "
        "ones.\n"
        "Each claim must include:\n"
        "- claim_text: What you found (natural language, 15-800 chars)\n"
        "- focus_variables: Which variables are involved (1-12 variables)\n"
        "- confidence: How confident you are (0.0 to 1.0)\n"
        "- evidence_basis: What data supports this (artifact_id + rationale).\n"
        "  artifact_id MUST be one of:\n"
        "    * A base dataset id you loaded (e.g. 'dataset_bg', 'dataset_survey')\n"
        "    * The exact 'derived_X_hash' id printed/returned by save_artifact\n"
        "      (e.g. if you ran `aid = save_artifact(df, 'filtered')` and the\n"
        "      tool output showed `[save_artifact] saved as derived_filtered_a1b2c3`,\n"
        "      then evidence_basis.artifact_id MUST be 'derived_filtered_a1b2c3'.)\n"
        "  Do NOT cite 'python_exec', the label slug you passed to save_artifact,\n"
        "  or any name not present in the tool output.\n"
        "IMPORTANT: \"No significant effect\" is a valid finding. If you "
        "investigate a relationship and find it is absent or negligible, "
        "that is worth reporting.\n\n"
        "Call this ONCE at the end of your investigation."
    )


def build_oi_briefing(
    research_brief: str,
    artifact_catalog: list[dict[str, Any]],
) -> str:
    """Build the briefing section with research question + datasets."""
    dataset_lines = []
    for entry in artifact_catalog:
        dataset_lines.append(
            f"- **{entry['artifact_id']}** -- {entry.get('description', '')}"
        )
    datasets_text = "\n".join(dataset_lines) if dataset_lines else "(none)"

    return (
        f"## Research Brief\n\n{research_brief}\n\n"
        f"## Available Datasets\n\n{datasets_text}"
    )


def build_oi_strategy_section() -> str:
    """Build the investigation strategy guidance section."""
    return (
        "## Investigation Strategy\n\n"
        "1. EXPLORE: Load artifacts, examine distributions, check for missing "
        "data, identify key variables and their scales.\n\n"
        "2. INVESTIGATE: Test relationships -- correlations, conditional "
        "distributions, stratified analyses. Distinguish association from "
        "causation. Look for effects, mediators, moderators.\n\n"
        "3. VALIDATE: Check robustness, look for confounders, test alternative "
        "explanations. For any causal claim, ask: could this be confounded?\n\n"
        "4. REPORT: Submit when you have 1-5 specific claims, each tied to "
        "concrete artifacts, and any causal/mechanistic claim has at least "
        "one robustness or alternative-explanation check.\n\n"
        "## Association vs Causation\n\n"
        "- \"X and Y are correlated\" = observational association. Always valid "
        "if you computed it correctly.\n"
        "- \"X causes Y\" = causal claim. Requires either experimental design "
        "or careful adjustment for confounders + explicit reasoning.\n"
        "- When in doubt, use associational language. It is more honest and "
        "still scores well if the association is real.\n"
        "- A regression coefficient does NOT establish causation by itself."
    )


def build_oi_solver_prompt(
    research_brief: str,
    artifact_catalog: list[dict[str, Any]],
    title: str | None = None,
    domain: str | None = None,
) -> str:
    """Build the complete OI solver prompt.

    Combines system, tools, briefing, and strategy sections into a
    single prompt string ready for the solver LLM.

    Args:
        research_brief: The research question/brief.
        artifact_catalog: List of artifact metadata dicts.
        title: Optional investigation title.
        domain: Optional domain name.
    """
    parts = []

    # System
    parts.append(build_oi_system_prompt())

    # Title context if available
    if title:
        context = f"\n\n## Investigation: {title}"
        if domain:
            context += f" ({domain})"
        parts.append(context)

    # Tools
    parts.append("\n\n" + build_oi_tools_section(artifact_catalog))

    # Briefing
    parts.append("\n\n" + build_oi_briefing(research_brief, artifact_catalog))

    # Strategy
    parts.append("\n\n" + build_oi_strategy_section())

    return "".join(parts)


__all__ = [
    "build_oi_briefing",
    "build_oi_solver_prompt",
    "build_oi_strategy_section",
    "build_oi_system_prompt",
    "build_oi_tools_section",
]
