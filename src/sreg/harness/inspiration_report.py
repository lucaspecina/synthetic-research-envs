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
    narrative_comparison: str = ""  # LLM-written qualitative comparison
    manifest: dict | None = None  # Orchestrator's self-reported intent

    def to_markdown(self) -> str:
        """Render as human-readable markdown — narrative and friendly."""
        lines = ["# Inspiration Report", ""]

        # ---- Narrative intro ----
        if self.seed_profile.narrative_summary:
            lines.append("## What the seed is about")
            lines.append("")
            lines.append(self.seed_profile.narrative_summary)
            lines.append("")
            # Seed research questions
            if self.seed_profile.question_descriptions:
                lines.append("**Research questions in the seed:**")
                for q in self.seed_profile.question_descriptions:
                    lines.append(f"- {q}")
                lines.append("")
            # Seed variables
            if self.seed_profile.variable_names:
                lines.append(
                    f"**Variables mentioned** ({self.seed_profile.variable_count}): "
                    + ", ".join(self.seed_profile.variable_names[:20])
                )
                if len(self.seed_profile.variable_names) > 20:
                    lines.append(f"  ... and {len(self.seed_profile.variable_names) - 20} more")
                lines.append("")

        if self.src_profile.problem_description:
            lines.append("## What the SRC created")
            lines.append("")
            lines.append(f"**{self.src_profile.problem_description}**")
            lines.append("")
            lines.append(
                f"- {self.src_profile.variable_count} variables "
                f"({self.src_profile.complexity_level} complexity)"
            )
            lines.append(f"- {self.src_profile.relationship_count} causal relationships")
            lines.append(
                f"- {len(self.src_profile.question_types)} research questions: "
                + ", ".join(self.src_profile.question_types)
            )
            if self.src_profile.latent_variables:
                lines.append(
                    f"- Latent (unobservable): "
                    + ", ".join(self.src_profile.latent_variables)
                )
            lines.append("")
            # SRC variables
            if self.src_profile.variable_names:
                lines.append(
                    "**SRC variables:** " + ", ".join(self.src_profile.variable_names)
                )
                lines.append("")
            # SRC questions
            if self.src_profile.question_descriptions:
                lines.append("**SRC research questions:**")
                for i, q in enumerate(self.src_profile.question_descriptions, 1):
                    qt = (
                        self.src_profile.question_types[i - 1]
                        if i <= len(self.src_profile.question_types) else "?"
                    )
                    lines.append(f"{i}. ({qt}) {q}")
                lines.append("")

        # ---- Orchestrator's intent (manifest) ----
        if self.manifest:
            lines.append("## What the orchestrator intended")
            lines.append("")
            m = self.manifest
            if m.get("seed_understanding"):
                lines.append(f"**Understanding of the seed:** {m['seed_understanding']}")
                lines.append("")
            if m.get("intended_scale"):
                s = m["intended_scale"]
                lines.append(
                    f"**Scale intent:** seed ~{s.get('seed_vars_estimate', '?')} vars "
                    f"-> target {s.get('target_src_nodes', '?')} nodes. "
                    f"{s.get('rationale', '')}"
                )
                lines.append("")
            if m.get("preserved_elements"):
                lines.append("**Preserved from seed:**")
                for p in m["preserved_elements"]:
                    lines.append(
                        f"- {p.get('seed_element', '?')} -> "
                        f"{p.get('src_element', '?')} ({p.get('dimension', '')})"
                    )
                lines.append("")
            if m.get("simplified_elements"):
                lines.append("**Simplified/dropped:**")
                for s in m["simplified_elements"]:
                    lines.append(
                        f"- {s.get('seed_element', '?')}: {s.get('why_dropped', '?')}"
                    )
                lines.append("")
            if m.get("intended_causal_patterns"):
                lines.append("**Intended causal patterns:**")
                for p in m["intended_causal_patterns"]:
                    lines.append(f"- {p}")
                lines.append("")
            if m.get("question_mapping"):
                lines.append("**Question mapping (seed -> SRC):**")
                for q in m["question_mapping"]:
                    lines.append(
                        f"- \"{q.get('seed_question', '?')}\" -> "
                        f"{q.get('src_eval_type', '?')} ({q.get('rationale', '')})"
                    )
                lines.append("")
            if m.get("intentional_changes"):
                lines.append(f"**Intentional changes:** {m['intentional_changes']}")
                lines.append("")

        # ---- Qualitative narrative comparison ----
        if self.narrative_comparison:
            lines.append("## Qualitative comparison")
            lines.append("")
            lines.append(self.narrative_comparison)
            lines.append("")

        # ---- Overall score ----
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

        # ---- Scorecard ----
        lines.append("## Scorecard")
        lines.append("")
        assessable = [d for d in self.dimensions if d.score >= 0]
        not_assessable = [d for d in self.dimensions if d.score < 0]

        lines.append("| Dimension | Score | Verdict |")
        lines.append("|---|---|---|")
        for d in assessable:
            icon = "v" if d.score >= 0.75 else ("~" if d.score >= 0.5 else "x")
            lines.append(f"| {d.name} | {d.score:.0%} | {icon} {d.label} |")
        for d in not_assessable:
            lines.append(f"| {d.name} | -- | ? {d.label} |")
        if not_assessable:
            lines.append("")
            lines.append(
                f"*{len(not_assessable)} dimensions not assessable "
                f"(SRC extraction limited). Not counted in overall score.*"
            )
        lines.append("")

        # ---- Detailed breakdown ----
        lines.append("## Detailed comparison")
        lines.append("")

        seed_just = self.seed_profile.justifications

        for d in self.dimensions:
            lines.append(f"### {d.name}")
            lines.append("")
            lines.append(f"**Score: {d.score:.0%} ({d.label})**")
            lines.append("")
            lines.append(f"**In the seed:** {d.seed_summary}")
            dim_key = _dimension_to_key(d.name)
            if dim_key and dim_key in seed_just:
                lines.append(f"> *Why:* {seed_just[dim_key]}")
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
        elif hasattr(e, "from_node"):
            # Edge object (Pydantic model)
            edge_list.append((e.from_node, e.to_node))

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


# Controlled vocabulary for research actions
_ACTION_ALIASES = {
    "observe variables": "observe_variables",
    "observe": "observe_variables",
    "measure": "observe_variables",
    "collect additional data": "collect_additional_data",
    "collect data": "collect_additional_data",
    "collect new data": "collect_additional_data",
    "recoleccion de datos": "collect_additional_data",
    "incorporate new measurements": "collect_additional_data",
    "nuevas mediciones": "collect_additional_data",
    "datos adicionales": "collect_additional_data",
    "estimate causal effect": "estimate_causal_effect",
    "causal inference": "estimate_causal_effect",
    "causal attribution": "estimate_causal_effect",
    "modelado causal": "estimate_causal_effect",
    "inferencia causal": "estimate_causal_effect",
    "counterfactual": "estimate_causal_effect",
    "contrafactual": "estimate_causal_effect",
    "compare interventions": "compare_interventions",
    "simulate interventions": "compare_interventions",
    "intervene": "compare_interventions",
    "intervention": "compare_interventions",
    "sensitivity analysis": "run_sensitivity_analysis",
    "sensibilidad": "run_sensitivity_analysis",
    "robustness": "run_sensitivity_analysis",
    "stratify": "stratify_subgroups",
    "subgroup": "stratify_subgroups",
    "estratificacion": "stratify_subgroups",
    "latent": "infer_latent_cause",
    "infer latent": "infer_latent_cause",
    "select next measurement": "select_next_measurement",
    "select next measurements": "select_next_measurement",
    "next best observation": "select_next_measurement",
    "prioritize measurement": "select_next_measurement",
    "value of information": "select_next_measurement",
    "measurement prioritization": "select_next_measurement",
    "risk assessment": "estimate_causal_effect",
    "causal attribution": "estimate_causal_effect",
    "intervention comparison": "compare_interventions",
}

# Parent categories for partial credit
_ACTION_CATEGORIES = {
    "observe_variables": "measure",
    "collect_additional_data": "measure",
    "select_next_measurement": "measure",
    "estimate_causal_effect": "analyze",
    "run_sensitivity_analysis": "analyze",
    "stratify_subgroups": "analyze",
    "infer_latent_cause": "analyze",
    "compare_interventions": "intervene",
}


def _normalize_actions(actions: list[str]) -> set[str]:
    """Normalize research action descriptions to controlled vocabulary."""
    normalized = set()
    for action in actions:
        action_lower = action.lower().strip()
        # Try exact match first
        if action_lower in _ACTION_ALIASES:
            normalized.add(_ACTION_ALIASES[action_lower])
            continue
        # Try ALL substring matches (one action can map to multiple types)
        matched = False
        for key, val in _ACTION_ALIASES.items():
            if key in action_lower or action_lower in key:
                normalized.add(val)
                matched = True
        if not matched:
            normalized.add(action_lower)
    return normalized


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
    manifest: dict | None = None,
) -> InspirationReport:
    """Compare seed and SRC profiles across all dimensions.

    If manifest is provided, uses it to fill gaps in SRC extraction
    (type_of_work, data_problems, signal_noise, research_actions).
    """
    dimensions = []
    m = manifest or {}

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

    # 3. Causal structure (scored on realization, not intent)
    d3 = _compare_causal(seed, src)
    # Add intent vs realization discrepancy note from manifest
    m_causal = m.get("intended_causal_patterns", [])
    if m_causal and d3.score < 0.75:
        intended_str = "; ".join(m_causal)
        d3.assessment += (
            f". NOTE: manifest intended [{intended_str}] "
            f"but DAG only realized [{', '.join(src.causal_features)}]. "
            f"This is a generation gap, not an extraction gap."
        )
    dimensions.append(d3)

    # 4. Data types/problems — use manifest if available
    m_data = m.get("data_problems", {})
    if m_data and m_data.get("preserved"):
        src_data_str = ", ".join(m_data["preserved"])
        d4 = _compare_simple(
            "Data & Problems",
            ", ".join(seed.data_problems) or "none",
            src_data_str,
            seed.data_problems,
            m_data["preserved"],
        )
        not_repr = m_data.get("not_representable", [])
        if not_repr:
            d4.assessment += f". Not representable yet: {', '.join(not_repr)}"
    elif src.data_problems:
        d4 = _compare_simple(
            "Data & Problems",
            ", ".join(seed.data_problems) or "none",
            ", ".join(src.data_problems),
            seed.data_problems,
            src.data_problems,
        )
    else:
        d4 = DimensionScore(
            name="Data & Problems",
            seed_summary=", ".join(seed.data_problems) or "none",
            src_summary="(no manifest or extraction available)",
            score=-1.0,
            label="not assessable",
            assessment="No manifest data_problems and SRC extraction limited",
        )
    dimensions.append(d4)

    # 5. Type of work — use manifest if available
    m_work = m.get("type_of_work", {})
    if m_work and m_work.get("src_style"):
        src_work = m_work["src_style"]
        d5 = _compare_simple("Type of Work", seed.work_type, src_work)
        d5.assessment = f"Seed: {seed.work_type}. SRC: {src_work}"
        activities = m_work.get("researcher_activities", [])
        if activities:
            d5.assessment += f". Activities: {', '.join(activities)}"
        d5.score = 0.75
        d5.label = _score_label(d5.score)
    else:
        src_work = src.work_type or (
            "observational + interventional" if "intervene" in src.research_actions else ""
        )
        d5 = _compare_simple("Type of Work", seed.work_type, src_work)
        d5.assessment = f"Seed: {seed.work_type}. SRC: {src_work or 'not specified'}"
        if seed.work_type and src_work:
            d5.score = 0.75
            d5.label = _score_label(d5.score)
    dimensions.append(d5)

    # 6. Research questions (most important)
    dimensions.append(_compare_questions(seed, src))

    # 7. Signal vs noise
    d7 = _compare_simple("Signal vs Noise", seed.signal_strength, src.signal_strength)
    d7.assessment = f"Seed: {seed.signal_strength}. SRC: {src.signal_strength}"
    dimensions.append(d7)

    # 8. Research actions
    # 7b. Signal vs Noise — enrich with manifest if available
    m_signal = m.get("signal_noise", {})
    if m_signal:
        src_signal = m_signal.get("intended_signal", src.signal_strength)
        detect = m_signal.get("detectability", "")
        d7_prev = dimensions[-1]  # last added was signal
        d7_prev.src_summary = f"{src_signal} (detectability: {detect})"
        d7_prev.assessment = f"Seed: {seed.signal_strength}. SRC intent: {src_signal}, {detect}"
        if m_signal.get("rationale"):
            d7_prev.assessment += f". {m_signal['rationale']}"

    # 8. Research Actions — normalize and compare
    src_actions_raw = (
        m.get("research_actions", {}).get("intended_actions", [])
        if m.get("research_actions") else
        src.research_actions
    )
    seed_norm = _normalize_actions(seed.research_actions)
    src_norm = _normalize_actions(src_actions_raw)

    if not seed_norm:
        d8 = DimensionScore(
            name="Research Actions",
            seed_summary="not specified",
            src_summary=", ".join(src_norm),
            score=0.5,
            label="partial",
            assessment="Seed didn't specify research actions",
        )
    else:
        # Direct overlap
        overlap = seed_norm & src_norm
        score = len(overlap) / max(len(seed_norm), 1)

        # Partial credit via parent categories
        if score < 1.0:
            seed_cats = {_ACTION_CATEGORIES.get(a, a) for a in seed_norm}
            src_cats = {_ACTION_CATEGORIES.get(a, a) for a in src_norm}
            cat_overlap = seed_cats & src_cats
            cat_score = len(cat_overlap) / max(len(seed_cats), 1)
            # Blend: 70% direct, 30% category
            score = 0.7 * score + 0.3 * cat_score

        missing = seed_norm - src_norm
        extra = src_norm - seed_norm
        assessment = f"Matched: {', '.join(overlap) or 'none'}"
        if missing:
            assessment += f". Missing: {', '.join(missing)}"
        if extra:
            assessment += f". Extra: {', '.join(extra)}"

        not_supported = m.get("research_actions", {}).get("not_supported", [])
        if not_supported:
            assessment += f". Not supported by SREG: {', '.join(not_supported)}"

        d8 = DimensionScore(
            name="Research Actions",
            seed_summary=", ".join(seed_norm),
            src_summary=", ".join(src_norm),
            score=score,
            label=_score_label(score),
            assessment=assessment,
        )
    dimensions.append(d8)

    # Overall score (weighted — exclude not-assessable dimensions)
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

    # Only count assessable dimensions (score >= 0)
    assessable = [d for d in dimensions if d.score >= 0]
    total_weight = sum(weights.get(d.name, 1.0) for d in assessable)
    overall = (
        sum(d.score * weights.get(d.name, 1.0) for d in assessable) / total_weight
        if total_weight > 0 else 0.0
    )

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
# Narrative comparison (LLM-generated)
# ---------------------------------------------------------------------------

_NARRATIVE_PROMPT = """\
You are writing a qualitative comparison between a research seed and a \
synthetic research case (SRC) that was generated inspired by it.

Write 3-4 paragraphs in a friendly, clear style (in the same language as \
the seed if possible, otherwise English):

1. **What was preserved well**: What aspects of the original research did \
the SRC capture faithfully? Be specific — mention variables, relationships, \
question types that match.

2. **What was simplified or lost**: What complexity from the seed didn't \
make it into the SRC? Missing variables, data problems not represented, \
causal patterns lost. Explain WHY this matters.

3. **What the SRC added**: Did the SRC introduce things not in the seed? \
Extra question types, new variables? Are these additions good (enriching \
the case) or noise?

4. **Overall verdict**: In one paragraph, would a researcher working on the \
seed's problem recognize the SRC as a relevant synthetic version of their \
investigation? What's the single most important thing to improve?

Be specific, cite variable names and question types. Don't be generic.
"""


def _generate_narrative(
    seed: InspirationProfile,
    src: InspirationProfile,
    report: InspirationReport,
    client: OpenAI,
    model: str,
) -> str:
    """Generate a qualitative narrative comparing seed and SRC."""
    # Build a summary of both profiles for the LLM
    context = (
        f"SEED PROFILE:\n"
        f"- Domain: {seed.domain}\n"
        f"- Problem: {seed.problem_description}\n"
        f"- Summary: {seed.narrative_summary}\n"
        f"- Variables ({seed.variable_count}): {', '.join(seed.variable_names[:25])}\n"
        f"- Causal features: {', '.join(seed.causal_features)}\n"
        f"- Latent: {', '.join(seed.latent_variables)}\n"
        f"- Data problems: {', '.join(seed.data_problems)}\n"
        f"- Question types: {', '.join(seed.question_types)}\n"
        f"- Questions: {'; '.join(seed.question_descriptions[:5])}\n"
        f"- Research actions: {', '.join(seed.research_actions)}\n"
        f"\nSRC PROFILE:\n"
        f"- Title: {src.problem_description}\n"
        f"- Variables ({src.variable_count}): {', '.join(src.variable_names)}\n"
        f"- Causal features: {', '.join(src.causal_features)}\n"
        f"- Latent: {', '.join(src.latent_variables)}\n"
        f"- Question types: {', '.join(src.question_types)}\n"
        f"- Questions: {'; '.join(src.question_descriptions[:5])}\n"
        f"\nSCORES:\n"
    )
    for d in report.dimensions:
        context += f"- {d.name}: {d.score:.0%} ({d.label}) — {d.assessment}\n"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _NARRATIVE_PROMPT},
                {"role": "user", "content": context},
            ],
            temperature=0.7,
        )
    except Exception:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _NARRATIVE_PROMPT},
                    {"role": "user", "content": context},
                ],
            )
        except Exception as e:
            logger.warning("Failed to generate narrative: %s", e)
            return ""

    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_report(
    seed_text: str,
    world: World,
    tasks: list,
    client: OpenAI | None = None,
    model: str | None = None,
    manifest: dict | None = None,
) -> InspirationReport:
    """Generate a full Inspiration Report comparing seed vs SRC.

    If manifest is provided (from orchestrator's emit_inspiration_manifest),
    it's included in the report as the orchestrator's self-reported intent.
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

    # Ensure _client and _model are defined for narrative generation
    if client and model:
        _client = client
        _model = model

    # Compare
    report = compare_profiles(seed_profile, src_profile, manifest=manifest)

    # Attach manifest if available
    report.manifest = manifest

    # Generate qualitative narrative comparison
    _llm_client = client or _client
    _llm_model = model or _model
    report.narrative_comparison = _generate_narrative(
        seed_profile, src_profile, report, _llm_client, _llm_model
    )

    return report


__all__ = [
    "InspirationProfile",
    "InspirationReport",
    "compare_profiles",
    "extract_seed_profile",
    "extract_src_profile",
    "generate_report",
]
