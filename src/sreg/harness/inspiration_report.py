"""Inspiration Report: compare seed vs generated SRC on 8 dimensions.

Evaluates how well the orchestrator captured the inspiration from a seed
(paper, business case, operational problem) when generating an SRC.

Two profiles are extracted:
- Seed profile: LLM reads the seed text and extracts structured dimensions
- SRC profile: extracted programmatically from the generated world/tasks

Then compared dimension by dimension with scores and assessments.

Usage:
    from sreg.harness.inspiration_report import generate_report
    report = generate_report(seed_text, world, tasks, client, model)
    print(report.to_markdown())
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from openai import OpenAI

from sreg.models.world import World

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class InspirationProfile:
    """Structured profile of a seed or SRC across the 8 dimensions."""

    narrative_summary: str = ""
    domain: str = ""
    problem_description: str = ""
    variable_count: int = 0
    variable_names: list[str] = field(default_factory=list)
    relationship_count: int = 0
    complexity_level: str = ""  # low / medium / high
    causal_features: list[str] = field(default_factory=list)
    latent_variables: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
    data_problems: list[str] = field(default_factory=list)
    work_type: str = ""  # observational / experimental / operational / mixed
    question_types: list[str] = field(default_factory=list)
    question_descriptions: list[str] = field(default_factory=list)
    signal_strength: str = ""  # weak / moderate / strong
    research_actions: list[str] = field(default_factory=list)
    # Justifications (WHY each value was extracted)
    justifications: dict[str, str] = field(default_factory=dict)


@dataclass
class DimensionScore:
    """Score for one inspiration dimension."""

    name: str
    seed_summary: str
    src_summary: str
    score: float  # 0.0 - 1.0
    label: str  # mismatch / weak / partial / strong / exact
    assessment: str


@dataclass
class InspirationReport:
    """Full comparison report between seed and SRC."""

    seed_profile: InspirationProfile
    src_profile: InspirationProfile
    dimensions: list[DimensionScore] = field(default_factory=list)
    overall_score: float = 0.0
    critical_failures: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Render as human-readable markdown — narrative and friendly."""
        lines = ["# Inspiration Report", ""]

        # Narrative intro
        if self.seed_profile.narrative_summary:
            lines.append("## What the seed is about")
            lines.append("")
            lines.append(self.seed_profile.narrative_summary)
            lines.append("")

        if self.src_profile.problem_description:
            lines.append("## What the SRC created")
            lines.append("")
            lines.append(
                f"**{self.src_profile.problem_description}** -- "
                f"{self.src_profile.variable_count} variables, "
                f"{len(self.src_profile.question_types)} research questions, "
                f"complexity: {self.src_profile.complexity_level}."
            )
            lines.append("")

        # Overall score
        label = _score_label(self.overall_score)
        bar = "#" * int(self.overall_score * 20)
        empty = "." * (20 - len(bar))
        lines.append(f"## Overall inspiration: {self.overall_score:.0%} ({label})")
        lines.append(f"`[{bar}{empty}]`")
        lines.append("")

        if self.critical_failures:
            lines.append("**Issues:**")
            for f in self.critical_failures:
                lines.append(f"- {f}")
            lines.append("")

        # Scorecard
        lines.append("## Scorecard")
        lines.append("")
        lines.append("| Dimension | Score | Verdict |")
        lines.append("|---|---|---|")
        for d in self.dimensions:
            icon = "v" if d.score >= 0.75 else ("~" if d.score >= 0.5 else "x")
            lines.append(f"| {d.name} | {d.score:.0%} | {icon} {d.label} |")
        lines.append("")

        # Detailed breakdown with justifications
        lines.append("## Detailed comparison")
        lines.append("")

        seed_just = self.seed_profile.justifications

        for d in self.dimensions:
            lines.append(f"### {d.name}")
            lines.append("")
            lines.append(f"**Score: {d.score:.0%} ({d.label})**")
            lines.append("")
            lines.append(f"**In the seed:** {d.seed_summary}")
            # Add justification if available
            dim_key = _dimension_to_key(d.name)
            if dim_key and dim_key in seed_just:
                lines.append(f"  - *Why:* {seed_just[dim_key]}")
            lines.append("")
            lines.append(f"**In the SRC:** {d.src_summary}")
            lines.append("")
            if d.assessment:
                lines.append(f"**Assessment:** {d.assessment}")
                lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)


def _dimension_to_key(dim_name: str) -> str:
    """Map dimension display name to justification key."""
    mapping = {
        "Domain & Problem": "work_type",
        "Scale & Complexity": "complexity",
        "Causal Structure": "causal_features",
        "Data & Problems": "data_problems",
        "Type of Work": "work_type",
        "Research Questions": "question_types",
        "Signal vs Noise": "signal_strength",
        "Research Actions": "research_actions",
    }
    return mapping.get(dim_name, "")


def _score_label(score: float) -> str:
    if score >= 0.9:
        return "excellent"
    elif score >= 0.75:
        return "strong"
    elif score >= 0.5:
        return "partial"
    elif score >= 0.25:
        return "weak"
    else:
        return "mismatch"


# ---------------------------------------------------------------------------
# SRC profile extraction (programmatic)
# ---------------------------------------------------------------------------


def extract_src_profile(world: World, tasks: list) -> InspirationProfile:
    """Extract InspirationProfile from a generated SRC — fully programmatic."""
    nodes = world.nodes
    edges = world.edges if hasattr(world, "edges") else []

    # Node analysis
    obs_nodes = [n for n in nodes if n.type.value == "observable"]
    latent_nodes = [n for n in nodes if n.type.value == "latent"]
    target_nodes = [n for n in nodes if n.type.value == "target"]

    # Causal features detection
    causal_features = []
    if latent_nodes:
        causal_features.append("latent_variables")

    # Check for colliders, confounders, mediators from DAG structure
    edge_list = []
    for e in edges:
        if isinstance(e, (list, tuple)):
            edge_list.append((e[0], e[1]))
        elif isinstance(e, dict):
            edge_list.append((e.get("from", ""), e.get("to", "")))

    # Build parent/child maps
    parents: dict[str, list[str]] = {}
    children: dict[str, list[str]] = {}
    for src, dst in edge_list:
        parents.setdefault(dst, []).append(src)
        children.setdefault(src, []).append(dst)

    # Detect colliders (nodes with 2+ parents)
    colliders = [n for n, p in parents.items() if len(p) >= 2]
    if colliders:
        causal_features.append("colliders")

    # Detect confounders (common cause of 2+ nodes)
    for node_name in [n.name for n in nodes]:
        if node_name in children and len(children[node_name]) >= 2:
            causal_features.append("confounders")
            break

    # Detect mediators (A->M->B where A->B also exists)
    for a, b in edge_list:
        for mid in children.get(a, []):
            if mid != b and b in children.get(mid, []):
                causal_features.append("mediators")
                break
        if "mediators" in causal_features:
            break

    # Complexity
    n_nodes = len(nodes)
    if n_nodes <= 6:
        complexity = "low"
    elif n_nodes <= 10:
        complexity = "medium"
    else:
        complexity = "high"

    # Task types
    question_types = []
    question_descs = []
    for t in tasks:
        if isinstance(t, dict):
            tt = t.get("task_type", "") or t.get("type", "")
            q = t.get("question", "")
        else:
            tt = getattr(t, "task_type", "") or getattr(t, "type", "")
            q = getattr(t, "question", "")
        # task_type may be an enum — convert to string
        tt_str = tt.value if hasattr(tt, "value") else str(tt) if tt else ""
        if tt_str:
            question_types.append(tt_str)
        if q:
            question_descs.append(q)

    return InspirationProfile(
        domain=world.domain or "",
        problem_description=world.scenario_title or "",
        variable_count=n_nodes,
        variable_names=[n.name for n in nodes],
        relationship_count=len(edge_list),
        complexity_level=complexity,
        causal_features=list(set(causal_features)),
        latent_variables=[n.name for n in latent_nodes],
        question_types=question_types,
        question_descriptions=question_descs,
        signal_strength="moderate",  # Can't determine programmatically yet
        research_actions=["observe", "intervene"],  # Default for current SRCs
    )


# ---------------------------------------------------------------------------
# Seed profile extraction (LLM-assisted)
# ---------------------------------------------------------------------------

_EXTRACT_PROMPT = """\
You are analyzing a research seed (a scientific paper, business case, operational \
problem, or dataset description). Extract a structured profile of the research.

Return ONLY valid JSON with these fields. For EVERY list field, include a \
"_why" field explaining WHY you extracted each item (cite evidence from the text).

{
  "narrative_summary": "2-3 sentence plain-language summary of what this research is about, written as if explaining to a colleague",
  "domain": "the research domain",
  "problem_description": "one-sentence core problem",
  "variable_count": <number of distinct variables/factors mentioned>,
  "variable_names": ["list", "of", "variable", "names"],
  "variable_names_why": "Why these variables: brief explanation of how you identified them",
  "relationship_count": <estimated number of causal/correlational relationships>,
  "complexity_level": "low | medium | high",
  "complexity_why": "Why this complexity level",
  "causal_features": ["confounders", "mediators", "colliders", "latent_variables", "chains"],
  "causal_features_why": "For each feature, explain which variables are involved. E.g. 'confounders: SES confounds the pollution-asthma relationship'",
  "latent_variables": ["variables that cannot be directly measured"],
  "latent_variables_why": "Why each is latent — what makes it unobservable",
  "data_sources": ["types of data sources mentioned"],
  "data_sources_why": "Evidence for each data source from the text",
  "data_problems": ["missing_data", "selection_bias", etc.],
  "data_problems_why": "For each problem, cite evidence from the text",
  "work_type": "observational | experimental | operational | mixed",
  "work_type_why": "Why this work type",
  "question_types": ["causal_effect", "prediction", "adjustment_set", etc.],
  "question_types_why": "For each question type, which research question from the seed maps to it",
  "question_descriptions": ["actual research questions from the seed"],
  "signal_strength": "weak | moderate | strong",
  "signal_strength_why": "Evidence for signal strength from the text",
  "research_actions": ["what researchers can do"],
  "research_actions_why": "For each action, why it's available or relevant"
}

Count ALL distinct variables mentioned, not just main ones. Include covariates, \
confounders, outcomes, intermediate variables, derived variables. Be exhaustive \
in counting — this is critical for scale matching.
"""


def extract_seed_profile(
    seed_text: str,
    client: OpenAI,
    model: str,
) -> InspirationProfile:
    """Extract InspirationProfile from seed text using LLM."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _EXTRACT_PROMPT},
                {"role": "user", "content": seed_text[:12000]},
            ],
            temperature=0.0,
        )
    except Exception:
        # Reasoning models don't support temperature — retry without it
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _EXTRACT_PROMPT},
                {"role": "user", "content": seed_text[:12000]},
            ],
        )

    raw = response.choices[0].message.content or "{}"

    # Parse JSON from response (may be wrapped in ```json blocks)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse seed profile JSON: %s", raw[:200])
        return InspirationProfile()

    # Collect justifications
    justifications = {}
    for key in [
        "variable_names", "complexity", "causal_features", "latent_variables",
        "data_sources", "data_problems", "work_type", "question_types",
        "signal_strength", "research_actions",
    ]:
        why_key = f"{key}_why"
        if why_key in data:
            justifications[key] = data[why_key]

    return InspirationProfile(
        narrative_summary=data.get("narrative_summary", ""),
        domain=data.get("domain", ""),
        problem_description=data.get("problem_description", ""),
        variable_count=data.get("variable_count", 0),
        variable_names=data.get("variable_names", []),
        relationship_count=data.get("relationship_count", 0),
        complexity_level=data.get("complexity_level", ""),
        causal_features=data.get("causal_features", []),
        latent_variables=data.get("latent_variables", []),
        data_sources=data.get("data_sources", []),
        data_problems=data.get("data_problems", []),
        work_type=data.get("work_type", ""),
        question_types=data.get("question_types", []),
        question_descriptions=data.get("question_descriptions", []),
        signal_strength=data.get("signal_strength", ""),
        research_actions=data.get("research_actions", []),
        justifications=justifications,
    )


# ---------------------------------------------------------------------------
# Comparison and scoring
# ---------------------------------------------------------------------------


def _compare_scale(seed: InspirationProfile, src: InspirationProfile) -> DimensionScore:
    """Compare variable count and complexity."""
    if seed.variable_count == 0:
        return DimensionScore(
            name="Scale & Complexity",
            seed_summary="unknown",
            src_summary=f"{src.variable_count} nodes",
            score=0.5,
            label="partial",
            assessment="Seed didn't specify variable count",
        )

    ratio = src.variable_count / max(seed.variable_count, 1)
    if ratio >= 0.8:
        score = 1.0
    elif ratio >= 0.6:
        score = 0.75
    elif ratio >= 0.4:
        score = 0.5
    else:
        score = 0.25

    diff = seed.variable_count - src.variable_count
    assessment = (
        f"Seed has {seed.variable_count} variables, SRC has {src.variable_count} nodes"
    )
    if diff > 0:
        assessment += f" (missing {diff})"
    elif diff < 0:
        assessment += f" (added {-diff})"

    return DimensionScore(
        name="Scale & Complexity",
        seed_summary=f"{seed.variable_count} variables, {seed.complexity_level}",
        src_summary=f"{src.variable_count} nodes, {src.complexity_level}",
        score=score,
        label=_score_label(score),
        assessment=assessment,
    )


def _compare_causal(seed: InspirationProfile, src: InspirationProfile) -> DimensionScore:
    """Compare causal structure features."""
    seed_set = set(seed.causal_features)
    src_set = set(src.causal_features)

    if not seed_set:
        return DimensionScore(
            name="Causal Structure",
            seed_summary="not specified",
            src_summary=", ".join(src_set) or "none detected",
            score=0.5,
            label="partial",
            assessment="Seed didn't specify causal features",
        )

    overlap = seed_set & src_set
    total = seed_set | src_set
    score = len(overlap) / max(len(total), 1)

    missing = seed_set - src_set
    assessment = f"Matched: {', '.join(overlap) or 'none'}"
    if missing:
        assessment += f". Missing from SRC: {', '.join(missing)}"

    return DimensionScore(
        name="Causal Structure",
        seed_summary=", ".join(seed_set),
        src_summary=", ".join(src_set) or "none detected",
        score=score,
        label=_score_label(score),
        assessment=assessment,
    )


# Map common LLM-extracted question types to SREG eval types
_QUESTION_TYPE_ALIASES = {
    "prediction": "infer_target",
    "feature_importance": "next_best_observation",
    "counterfactual_analysis": "causal_effect",
    "counterfactual": "causal_effect",
    "variable_importance": "next_best_observation",
    "confounding_analysis": "adjustment_set",
    "confounder_identification": "adjustment_set",
    "intervention_comparison": "compare_interventions",
    "latent_cause": "infer_latent_cause",
    "diagnostic": "infer_latent_cause",
    "optimal_intervention": "best_intervention",
    "conditioning_bias": "should_condition",
}


def _normalize_question_types(types: list[str]) -> set[str]:
    """Normalize question type names to SREG eval types."""
    normalized = set()
    for t in types:
        t_lower = t.lower().strip()
        mapped = _QUESTION_TYPE_ALIASES.get(t_lower, t_lower)
        normalized.add(mapped)
    return normalized


def _compare_questions(seed: InspirationProfile, src: InspirationProfile) -> DimensionScore:
    """Compare research question types."""
    seed_types = _normalize_question_types(seed.question_types)
    src_types = _normalize_question_types(src.question_types)

    if not seed_types:
        return DimensionScore(
            name="Research Questions",
            seed_summary="not specified",
            src_summary=", ".join(src_types),
            score=0.5,
            label="partial",
            assessment="Seed didn't specify question types",
        )

    overlap = seed_types & src_types
    score = len(overlap) / max(len(seed_types), 1)
    # Bonus for having more questions
    if len(src_types) >= len(seed_types):
        score = min(score + 0.1, 1.0)

    missing = seed_types - src_types
    extra = src_types - seed_types
    assessment = f"{len(overlap)}/{len(seed_types)} seed types matched"
    if missing:
        assessment += f". Missing: {', '.join(missing)}"
    if extra:
        assessment += f". Extra: {', '.join(extra)}"

    return DimensionScore(
        name="Research Questions",
        seed_summary=f"{len(seed_types)} types: {', '.join(seed_types)}",
        src_summary=f"{len(src_types)} types: {', '.join(src_types)}",
        score=score,
        label=_score_label(score),
        assessment=assessment,
    )


def _compare_simple(
    name: str,
    seed_val: str,
    src_val: str,
    seed_list: list[str] | None = None,
    src_list: list[str] | None = None,
) -> DimensionScore:
    """Simple comparison for text-based dimensions."""
    if seed_list is not None and src_list is not None:
        seed_set = set(seed_list)
        src_set = set(src_list)
        if not seed_set:
            score = 0.5
        else:
            overlap = seed_set & src_set
            score = len(overlap) / max(len(seed_set), 1)
    else:
        # Just compare presence
        score = 0.75 if (seed_val and src_val) else 0.25

    return DimensionScore(
        name=name,
        seed_summary=seed_val or "not specified",
        src_summary=src_val or "not specified",
        score=score,
        label=_score_label(score),
        assessment="",
    )


def compare_profiles(
    seed: InspirationProfile,
    src: InspirationProfile,
) -> InspirationReport:
    """Compare seed and SRC profiles across all dimensions."""
    dimensions = []

    # 1. Domain (simple match)
    d1 = _compare_simple("Domain & Problem", seed.domain, src.domain)
    d1.assessment = (
        f"Seed: {seed.problem_description[:60]}. "
        f"SRC: {src.problem_description[:60]}"
    )
    d1.score = 0.75 if seed.domain and src.domain else 0.5
    d1.label = _score_label(d1.score)
    dimensions.append(d1)

    # 2. Scale
    dimensions.append(_compare_scale(seed, src))

    # 3. Causal structure
    dimensions.append(_compare_causal(seed, src))

    # 4. Data types/problems
    d4 = _compare_simple(
        "Data & Problems",
        ", ".join(seed.data_problems) or "none",
        "tabular dataset",
        seed.data_problems,
        src.data_problems,
    )
    dimensions.append(d4)

    # 5. Type of work
    d5 = _compare_simple("Type of Work", seed.work_type, src.work_type)
    d5.assessment = f"Seed: {seed.work_type}. SRC: observational + interventional"
    dimensions.append(d5)

    # 6. Research questions (most important)
    dimensions.append(_compare_questions(seed, src))

    # 7. Signal vs noise
    d7 = _compare_simple("Signal vs Noise", seed.signal_strength, src.signal_strength)
    d7.assessment = f"Seed: {seed.signal_strength}. SRC: {src.signal_strength}"
    dimensions.append(d7)

    # 8. Research actions
    d8 = _compare_simple(
        "Research Actions",
        ", ".join(seed.research_actions),
        "observe, intervene",
        seed.research_actions,
        src.research_actions,
    )
    dimensions.append(d8)

    # Overall score (weighted — questions and scale matter most)
    weights = {
        "Domain & Problem": 1.0,
        "Scale & Complexity": 2.0,  # Critical
        "Causal Structure": 1.5,
        "Data & Problems": 1.0,
        "Type of Work": 0.5,
        "Research Questions": 2.5,  # Most important
        "Signal vs Noise": 0.5,
        "Research Actions": 1.0,
    }

    total_weight = sum(weights.get(d.name, 1.0) for d in dimensions)
    overall = sum(d.score * weights.get(d.name, 1.0) for d in dimensions) / total_weight

    # Critical failures
    critical = []
    scale_dim = next((d for d in dimensions if d.name == "Scale & Complexity"), None)
    if scale_dim and scale_dim.score < 0.5:
        critical.append(
            f"Scale mismatch: seed has {seed.variable_count} variables "
            f"but SRC only has {src.variable_count} nodes"
        )

    questions_dim = next((d for d in dimensions if d.name == "Research Questions"), None)
    if questions_dim and questions_dim.score < 0.5:
        critical.append("Most seed question types not represented in SRC")

    return InspirationReport(
        seed_profile=seed,
        src_profile=src,
        dimensions=dimensions,
        overall_score=overall,
        critical_failures=critical,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_report(
    seed_text: str,
    world: World,
    tasks: list,
    client: OpenAI | None = None,
    model: str | None = None,
) -> InspirationReport:
    """Generate a full Inspiration Report comparing seed vs SRC.

    If client/model provided, uses LLM to extract seed profile.
    Otherwise, creates a minimal seed profile (less accurate).
    """
    import os

    # Extract SRC profile (programmatic)
    src_profile = extract_src_profile(world, tasks)

    # Extract seed profile
    if client and model:
        seed_profile = extract_seed_profile(seed_text, client, model)
    else:
        # Fallback: create client from env
        _client = OpenAI(
            base_url=os.environ.get("AZURE_FOUNDRY_BASE_URL", ""),
            api_key=os.environ.get("AZURE_INFERENCE_CREDENTIAL", ""),
        )
        _model = model or os.environ.get("AZURE_MODEL", "gpt-4o")
        seed_profile = extract_seed_profile(seed_text, _client, _model)

    # Compare
    return compare_profiles(seed_profile, src_profile)


__all__ = [
    "InspirationProfile",
    "InspirationReport",
    "compare_profiles",
    "extract_seed_profile",
    "extract_src_profile",
    "generate_report",
]
