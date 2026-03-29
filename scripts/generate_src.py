#!/usr/bin/env python3
"""Generate a Synthetic Research Case (SRC) — the official SREG entry point.

Creates a complete SRC via the LLM orchestrator and exports all artifacts.

Usage:
    python scripts/generate_src.py --goal "marine ecology, 8 nodes" --output experiments/reef/
    python scripts/generate_src.py --seed-file research_seed.md --output experiments/case1/
    python scripts/generate_src.py --seed-file seeds/paper.pdf --output experiments/from_paper/
    python scripts/generate_src.py --goal "football analytics" --output experiments/football/ --inspect

Outputs (always):
    <output>/src.json        Full SRC (world, problem, tasks, metadata)

Outputs (with --inspect):
    <output>/briefing.md     What the agent sees (narrative + questions)
    <output>/dataset.csv     Full dataset
    <output>/answer_key.md   Ground truth BN + quick guide + correct answers
    <output>/dag.png         Causal DAG visualization
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import textwrap
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Terminal display helpers
# ---------------------------------------------------------------------------

def _c(code: str, text: str) -> str:
    if not sys.stdout.isatty():
        return str(text)
    return f"{code}{text}\033[0m"


def _safe(text: str) -> str:
    enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
    return text.encode(enc, errors="replace").decode(enc)


B = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GRN = "\033[92m"
YLW = "\033[93m"
BLU = "\033[94m"
MAG = "\033[95m"
CYN = "\033[96m"


def _print(text: str = "") -> None:
    _safe_text = _safe(text) if text else ""
    print(_safe_text)


# ---------------------------------------------------------------------------
# 1. Generate: run orchestrator
# ---------------------------------------------------------------------------

def generate(
    goal: str, model: str | None = None, verbose: bool = False, oi_mode: bool = False
):
    """Run the orchestrator and return the result."""
    from sreg.orchestrator.orchestrator import Orchestrator

    mode_label = "OI" if oi_mode else "SRC"
    _print(_c(B + BLU, f"=== Generating {mode_label} ==="))
    _print(f"  {_c(DIM, 'Model:')} {model or os.environ.get('AZURE_MODEL', 'gpt-4o')}")
    goal_preview = goal[:120] + "..." if len(goal) > 120 else goal
    _print(f"  {_c(DIM, 'Goal:')} {goal_preview}")
    if oi_mode:
        _print(f"  {_c(DIM, 'Mode:')} Open Investigation (no predefined questions)")
    _print()

    o = Orchestrator(model=model, oi_mode=oi_mode) if model else Orchestrator(oi_mode=oi_mode)

    # Intercept tool calls for display
    original_dispatch = o._dispatch_tool
    steps = []

    def patched_dispatch(name, fn_args, result):
        tool_result = original_dispatch(name, fn_args, result)
        steps.append((name, fn_args, tool_result))

        if "error" in tool_result:
            _print(f"  {_c(RED, 'x')} {name} -> {_c(RED, 'ERROR')}")
            if verbose:
                _print(f"    {str(tool_result['error'])[:120]}")
        else:
            _print(f"  {_c(GRN, 'v')} {name} -> OK")
            if name == "apply_semantics":
                title = tool_result.get("scenario_title", "")
                _print(f"    {_c(MAG, _safe(title))}")

        return tool_result

    o._dispatch_tool = patched_dispatch
    result = o.run(goal)

    _print()
    if result.world and result.problem:
        from sreg.world.scm import SCMWorld
        if isinstance(result.world, SCMWorld):
            n_nodes = len(result.world.variables)
            title = result.problem.title or result.world.id
        else:
            n_nodes = len(result.world.nodes)
            title = getattr(result.world, "scenario_title", None) or "?"
        n_tasks = len(result.task) if isinstance(result.task, list) else 0
        _print(f"  {_c(GRN, 'OK')} {_c(B, _safe(title))}")
        _print(f"  {n_nodes} nodes, {n_tasks} tasks, {len(steps)} tool calls")
    else:
        _print(f"  {_c(RED, 'FAIL')} Orchestrator did not complete")

    return result, steps


# ---------------------------------------------------------------------------
# 2. Export: save all artifacts
# ---------------------------------------------------------------------------

def export_json(result, steps, goal: str, model: str, output_dir: str) -> str:
    """Export the full SRC as JSON. Returns the path."""
    from sreg.models.world import World

    export: dict = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "goal": goal,
            "model": model,
        },
        "process": {
            "tools_called": [
                {"tool": name, "args": args, "result": tr}
                for name, args, tr in steps
            ],
        },
    }

    if result.world:
        from sreg.world.scm import SCMWorld
        if isinstance(result.world, SCMWorld):
            from dataclasses import asdict
            export["world"] = {
                "type": "scm",
                "id": result.world.id,
                "variables": result.world.variables,
                "graph": result.world.graph,
                "latent_variables": list(result.world.latent_variables),
                "variable_meta": {
                    k: {"unit": v.unit, "range": list(v.range), "description": v.description}
                    for k, v in result.world.variable_meta.items()
                },
            }
        else:
            export["world"] = result.world.model_dump(mode="json")

    if result.task and isinstance(result.task, list):
        export["tasks"] = [t.model_dump(mode="json") for t in result.task]

    if result.problem:
        export["problem"] = result.problem.model_dump(mode="json")

    if result.sub_questions:
        export["sub_questions"] = [
            sq.model_dump(mode="json") for sq in result.sub_questions
        ]

    path = os.path.join(output_dir, "src.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(export, f, indent=2, ensure_ascii=False, default=str)

    return path


def export_csv(result, output_dir: str) -> str | None:
    """Export the tabular dataset as CSV."""
    if not result.problem:
        return None

    for asset in result.problem.data_assets:
        if asset.format == "tabular" and asset.data:
            headers = list(asset.data[0].keys())
            path = os.path.join(output_dir, "dataset.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=headers)
                w.writeheader()
                w.writerows(asset.data)
            return path
    return None


def export_briefing(result, output_dir: str) -> str | None:
    """Export what the agent sees: narrative + questions + actions."""
    if not result.problem:
        return None

    problem = result.problem
    tasks = result.task if isinstance(result.task, list) else []

    lines = []
    lines.append(f"# Research Case: {problem.title}")
    lines.append("")
    lines.append("## Background")
    lines.append("")
    lines.append(problem.description or "")
    lines.append("")

    if problem.theoretical_context:
        lines.append("## Theoretical Context")
        lines.append("")
        lines.append(problem.theoretical_context)
        lines.append("")

    # Research brief + deliverables (Fase 5 / I10: brief/eval separation)
    # The research_question field contains the brief + deliverables when
    # generated via CasePlan. Show it as the primary research assignment.
    if problem.research_question:
        lines.append("## Research Assignment")
        lines.append("")
        lines.append(problem.research_question)
        lines.append("")

    if tasks:
        lines.append("## Research Questions")
        lines.append("")
        for i, t in enumerate(tasks, 1):
            lines.append(f"### Question {i}")
            lines.append("")
            lines.append(t.question)
            lines.append("")
    elif not problem.research_question:
        lines.append("## Research Question")
        lines.append("")
        lines.append("(No research question provided)")
        lines.append("")

    lines.append("## Dataset")
    lines.append("")
    lines.append("The dataset is provided as a separate CSV file: dataset.csv")
    lines.append("")
    if problem.data_assets:
        asset = problem.data_assets[0]
        lines.append(asset.description or "")
        if asset.data:
            headers = [k for k in asset.data[0].keys() if k != "sample_id"]
            lines.append(f"Variables: {', '.join(headers)}")
    lines.append("")

    path = os.path.join(output_dir, "briefing.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def _build_scm_dag_section(world, tasks=None) -> list[str]:
    """Build mermaid DAG section for SCMWorld (no ExactBayesSolver needed)."""
    lines = []
    lines.append("## Causal DAG (ground truth)")
    lines.append("")
    lines.append("```mermaid")
    lines.append("graph TD")
    for var in world.variables:
        label = var.replace("_", " ")
        if var in world.latent_variables:
            lines.append(f'    {var}(["{label}"]):::latent')
        else:
            lines.append(f'    {var}["{label}"]:::observable')
    lines.append("")
    for child, parents in world.graph.items():
        for parent in parents:
            lines.append(f"    {parent} --> {child}")
    lines.append("")
    lines.append("    classDef latent fill:#FF6B6B,stroke:#333,color:#000,stroke-width:2px")
    lines.append("    classDef observable fill:#51CF66,stroke:#333,color:#000")
    lines.append("```")
    lines.append("")

    # Variable metadata
    lines.append("## Variables")
    lines.append("")
    for var in world.variables:
        meta = world.variable_meta.get(var)
        role = "LATENT" if var in world.latent_variables else "observable"
        unit = meta.unit if meta else ""
        desc = meta.description if meta else ""
        eq_fn = world.equations.get(var)
        eq_str = eq_fn.__doc__ if eq_fn and eq_fn.__doc__ else "(structural equation)"
        lines.append(f"- **{var}** [{role}] ({unit}): {desc}")
        lines.append(f"  Equation: `{eq_str}`")
    lines.append("")

    # Tasks summary
    if tasks:
        lines.append("## Scoring Agenda (hidden from investigator)")
        lines.append("")
        for i, t in enumerate(tasks, 1):
            q_short = t.question[:120] + "..." if len(t.question) > 120 else t.question
            lines.append(f"**Q{i}** [{t.type}]: {q_short}")
            if t.correct_answer:
                for k, v in t.correct_answer.items():
                    if isinstance(v, float):
                        lines.append(f"  - {k}: {v:.4f}")
                    else:
                        lines.append(f"  - {k}: {v}")
            lines.append("")

    return lines


def _export_scm_answer_key(result, output_dir: str) -> str | None:
    """Export SCM answer key: graph structure + correct answers."""
    world = result.world
    tasks = result.task if isinstance(result.task, list) else []

    lines = []
    lines.append(f"# Answer Key: {result.problem.title}")
    lines.append("")

    # Graph structure
    lines.append("## Causal Graph (SCM)")
    lines.append("")
    lines.append("```mermaid")
    lines.append("graph TD")
    for var in world.variables:
        label = var.replace("_", " ")
        if var in world.latent_variables:
            lines.append(f'    {var}(["{label}"]):::latent')
        else:
            lines.append(f'    {var}["{label}"]:::observable')
    lines.append("")
    for child, parents in world.graph.items():
        for parent in parents:
            lines.append(f"    {parent} --> {child}")
    lines.append("")
    lines.append("    classDef latent fill:#FF6B6B,stroke:#333,color:#000,stroke-width:2px")
    lines.append("    classDef observable fill:#51CF66,stroke:#333,color:#000")
    lines.append("```")
    lines.append("")

    # Variable metadata
    lines.append("## Variables")
    lines.append("")
    for var in world.variables:
        meta = world.variable_meta.get(var)
        role = "LATENT" if var in world.latent_variables else "observable"
        unit = meta.unit if meta else ""
        desc = meta.description if meta else ""
        eq_fn = world.equations.get(var)
        eq_str = eq_fn.__doc__ if eq_fn and eq_fn.__doc__ else "?"
        lines.append(f"- **{var}** [{role}] ({unit}): {desc}")
        lines.append(f"  Equation: `{eq_str}`")
    lines.append("")

    # Correct answers (internal scoring agenda)
    if tasks:
        lines.append("## Scoring Agenda (hidden from investigator)")
        lines.append("")
        for i, t in enumerate(tasks, 1):
            lines.append(f"### Q{i} [{t.type}]: {t.question[:120]}")
            lines.append(f"- Eval type: `{t.type}`")
            lines.append(f"- Target node: `{t.target_node}`")
            lines.append(f"- Scoring method: `{t.scoring_method}`")
            if t.estimand:
                lines.append(f"- Estimand: {t.estimand}")
            if t.correct_answer:
                lines.append("- Correct answer:")
                for k, v in t.correct_answer.items():
                    if isinstance(v, float):
                        lines.append(f"    {k}: {v:.4f}")
                    else:
                        lines.append(f"    {k}: {v}")
            lines.append("")

    path = os.path.join(output_dir, "answer_key.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def export_answer_key(result, output_dir: str) -> str | None:
    """Export answer key (delegates to SCM version)."""
    if not result.world or not result.problem:
        return None
    return _export_scm_answer_key(result, output_dir)


def export_dag_png(result, output_dir: str) -> str | None:
    """Export DAG visualization as PNG."""
    if not result.world:
        return None

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import networkx as nx
    except ImportError:
        return None

    from sreg.world.scm import SCMWorld as _SCMWorld
    world = result.world

    G = nx.DiGraph()
    node_types = {}
    node_states = {}
    if isinstance(world, _SCMWorld):
        for var in world.variables:
            G.add_node(var)
            if var in world.latent_variables:
                node_types[var] = "latent"
            else:
                node_types[var] = "observable"
            node_states[var] = []
        for child, parents in world.graph.items():
            for parent in parents:
                G.add_edge(parent, child)
    else:
        for n in world.nodes:
            G.add_node(n.name)
            node_types[n.name] = str(n.type)
            node_states[n.name] = n.states
        for e in world.edges:
            G.add_edge(e.from_node, e.to_node)

    # Layered layout via topological sort
    layers = {}
    for node in nx.topological_sort(G):
        preds = list(G.predecessors(node))
        if not preds:
            layers[node] = 0
        else:
            layers[node] = max(layers[p] for p in preds) + 1

    layer_groups: dict[int, list[str]] = {}
    for node, layer in layers.items():
        layer_groups.setdefault(layer, []).append(node)

    max_layer = max(layer_groups.keys()) if layer_groups else 0
    pos = {}
    for layer, layer_nodes in layer_groups.items():
        n = len(layer_nodes)
        for i, node in enumerate(layer_nodes):
            x = (i - (n - 1) / 2) * 3.5
            y = (max_layer - layer) * 2.8
            pos[node] = (x, y)

    color_map = {"latent": "#FF6B6B", "observable": "#69DB7C", "target": "#FFD43B"}

    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    ax.set_facecolor("#16213e")
    fig.set_facecolor("#16213e")

    nx.draw_networkx_edges(
        G, pos, ax=ax, edge_color="#8899aa", arrows=True, arrowsize=25,
        arrowstyle="-|>", connectionstyle="arc3,rad=0.08", width=2,
        min_source_margin=45, min_target_margin=45,
    )

    for name in G.nodes():
        x, y = pos[name]
        ntype = node_types[name]
        color = color_map.get(ntype, "#aaa")
        size = 1.1 if ntype == "target" else 0.9

        circle = plt.Circle(
            (x, y), size, facecolor=color, edgecolor="white", linewidth=2.5, zorder=3,
        )
        ax.add_patch(circle)

        label = textwrap.fill(name.replace("_", " "), width=12)
        ax.text(
            x, y + 0.15, label, ha="center", va="center",
            fontsize=9, fontweight="bold", color="#1a1a2e", zorder=4,
        )

        states_str = ", ".join(node_states[name])
        if len(states_str) > 25:
            states_str = textwrap.fill(states_str, width=20)
        ax.text(
            x, y - 0.45, states_str, ha="center", va="center",
            fontsize=6, color="#333", style="italic", zorder=4,
        )

    legend_elements = [
        mpatches.Patch(facecolor="#FF6B6B", edgecolor="white", label="Latent (hidden)"),
        mpatches.Patch(facecolor="#69DB7C", edgecolor="white", label="Observable"),
        mpatches.Patch(facecolor="#FFD43B", edgecolor="white", label="Target"),
    ]
    ax.legend(
        handles=legend_elements, loc="upper left", fontsize=11,
        facecolor="#1a1a2e", edgecolor="#555", labelcolor="white", framealpha=0.9,
    )

    title = getattr(world, "scenario_title", None) or "Causal DAG"
    ax.set_title(
        f"Causal DAG: {title}", fontsize=15, fontweight="bold", color="white", pad=20,
    )

    ax.set_aspect("equal")
    ax.axis("off")
    all_x = [p[0] for p in pos.values()]
    all_y = [p[1] for p in pos.values()]
    margin = 2
    ax.set_xlim(min(all_x) - margin, max(all_x) + margin)
    ax.set_ylim(min(all_y) - margin, max(all_y) + margin)

    plt.tight_layout()
    path = os.path.join(output_dir, "dag.png")
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    return path



# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _read_seed_file(path: str) -> str | None:
    """Read a research seed file (markdown or PDF), stripping comment lines."""
    if not os.path.isfile(path):
        return None

    # PDF support
    if path.lower().endswith(".pdf"):
        try:
            import pymupdf
        except ImportError:
            _print(f"  {_c(RED, 'x')} pymupdf not installed. Run: pip install pymupdf")
            return None
        doc = pymupdf.open(path)
        pages = []
        for page in doc:
            pages.append(page.get_text())
        content = "\n\n".join(pages).strip()
        doc.close()
        if not content:
            return None
        # Truncate to ~15000 chars to fit in LLM context
        if len(content) > 15000:
            content = content[:15000] + "\n\n[... paper truncated for context ...]"
        return content

    # Markdown / text
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        return None
    lines = [ln for ln in content.splitlines() if not ln.strip().startswith(">")]
    return "\n".join(lines).strip() or None


def main():
    parser = argparse.ArgumentParser(
        description="Generate a Synthetic Research Case (SRC)"
    )
    parser.add_argument(
        "--goal", type=str, default=None,
        help="Research goal for the orchestrator",
    )
    parser.add_argument(
        "--seed-file", type=str, default=None,
        help="Path to research seed file (markdown or PDF)",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Seed hint (appended to goal)",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Model name (default: AZURE_MODEL env)",
    )
    parser.add_argument(
        "--output", "-o", type=str, required=True,
        help="Output directory (created if needed)",
    )
    parser.add_argument(
        "--inspect", action="store_true",
        help="Generate full analysis package (briefing, CSV, answer key, DAG)",
    )
    parser.add_argument(
        "--oi", action="store_true",
        help="Open Investigation mode: vague brief, free-form investigation, claim-based scoring",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show detailed orchestrator output",
    )
    # Solver backend (for --oi): defaults to same as orchestrator (Azure)
    parser.add_argument(
        "--solver-model", type=str, default=None,
        help="Model for the solver (default: same as --model)",
    )
    parser.add_argument(
        "--solver-base-url", type=str, default=None,
        help="Base URL for solver backend (default: AZURE_FOUNDRY_BASE_URL). "
             "Use http://localhost:8000/v1 for vLLM",
    )
    parser.add_argument(
        "--solver-api-key", type=str, default=None,
        help="API key for solver backend (default: AZURE_INFERENCE_CREDENTIAL). "
             "Use 'none' for vLLM",
    )
    args = parser.parse_args()

    if not args.verbose:
        logging.basicConfig(level=logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
    else:
        logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

    # Build goal
    if args.goal:
        goal = args.goal
    else:
        seed_file = args.seed_file or "research_seed.md"
        seed_content = _read_seed_file(seed_file)
        if seed_content:
            goal = (
                "You are reading a real research case (a scientific paper, business case, "
                "operational problem, or dataset description). Your job is to create a "
                "SYNTHETIC research case INSPIRED by it — NOT a replica.\n\n"
                "Extract and MATCH these dimensions from the seed:\n\n"
                "1. DOMAIN AND PROBLEM: What is being studied? Why does it matter? "
                "Create a fictional setting in a SIMILAR domain.\n\n"
                "2. SCALE — THIS IS CRITICAL: Count how many distinct variables/factors "
                "are mentioned in the seed. Your synthetic case MUST have a COMPARABLE "
                "number of nodes. If the seed mentions 15-20 variables, create 12-18 nodes. "
                "If it mentions 8-10, create 8-10. Do NOT simplify to fewer nodes than "
                "the seed implies. More variables = richer, more realistic case.\n\n"
                "3. CAUSAL STRUCTURE: Identify confounders, mediators, colliders, and "
                "latent variables in the seed. Your DAG should have SIMILAR structural "
                "patterns (not necessarily the same edges, but the same types of "
                "causal complexity).\n\n"
                "4. RESEARCH QUESTIONS — THIS DRIVES THE TASKS: First, list the actual "
                "research questions from the seed. What do the researchers REALLY want to know? "
                "Then map each question to the closest eval_type. The PRIMARY question of the "
                "case should be CAUSAL (causal_effect, best_intervention, compare_interventions), "
                "not predictive (infer_target). Use infer_target only as a complementary question. "
                "If the seed asks about mediation, effect modification, or selection bias, "
                "pick the closest available type and note what is lost.\n\n"
                "5. SIGNAL DIFFICULTY: Are the effects strong and obvious, or subtle and "
                "hard to detect? Set edge_strength accordingly (0.4-0.5 for subtle, "
                "0.6-0.8 for strong).\n\n"
                "6. RESEARCH ACTIONS: What can the researcher DO? Can they only observe, "
                "or also intervene/experiment? Match the action types.\n\n"
                "7. DATA CHARACTERISTICS: Multiple data sources? Missing values? "
                "Request rich data format in build_problem if the seed implies complex data.\n\n"
                "Use dag_construct. Create variable names that sound scientific and "
                "domain-appropriate (NOT generic like 'variable_1').\n\n"
                f"--- RESEARCH SEED ---\n{seed_content}\n--- END SEED ---"
            )
        else:
            goal = (
                "Generate a research problem about marine ecology in a fictional "
                "archipelago, medium difficulty, 8 nodes. Use dag_construct. "
                "Design a research case with at least 3 different evaluation types."
            )
    if args.seed is not None:
        goal += f" Use seed {args.seed} for reproducibility."

    model = args.model or os.environ.get("AZURE_MODEL", "gpt-4o")

    # Generate
    result, steps = generate(goal, model=model, verbose=args.verbose, oi_mode=args.oi)

    if not result.world or not result.problem:
        _print(f"\n{_c(RED + B, 'Generation failed. Aborting.')}")
        sys.exit(1)

    do_inspect = args.inspect

    # Export
    os.makedirs(args.output, exist_ok=True)

    _print()
    _print(_c(B + BLU, "=== Exporting ==="))

    json_path = export_json(result, steps, goal, model, args.output)
    _print(f"  {_c(GRN, 'v')} {json_path}")

    if do_inspect:
        csv_path = export_csv(result, args.output)
        if csv_path:
            n_rows = len(result.problem.data_assets[0].data)
            _print(f"  {_c(GRN, 'v')} {csv_path} ({n_rows} rows)")

        briefing_path = export_briefing(result, args.output)
        if briefing_path:
            _print(f"  {_c(GRN, 'v')} {briefing_path}")

        ak_path = export_answer_key(result, args.output)
        if ak_path:
            _print(f"  {_c(GRN, 'v')} {ak_path}")

        dag_path = export_dag_png(result, args.output)
        if dag_path:
            _print(f"  {_c(GRN, 'v')} {dag_path}")

    # OI mode: run Open Investigation with LLM solver
    if args.oi:
        _print()
        _print(_c(B + BLU, "=== Open Investigation ==="))

        from sreg.world.scm import SCMWorld as _OI_SCMWorld
        if not isinstance(result.world, _OI_SCMWorld):
            _print(f"  {_c(RED, 'x')} OI mode requires SCMWorld (not BN)")
        elif not result.problem:
            _print(f"  {_c(RED, 'x')} No problem generated")
        else:
            from openai import OpenAI  # noqa: E402

            from sreg.tools.oi_driver import run_oi_investigation
            from sreg.tools.oi_runner import OIEpisodeRunner

            solver_model = args.solver_model or os.environ.get(
                "AZURE_SOLVER_MODEL", os.environ.get("AZURE_MODEL", "gpt-5.2-codex")
            )
            compiler_model = os.environ.get("AZURE_MODEL", "gpt-5.4")

            solver_client = OpenAI(
                base_url=args.solver_base_url or os.environ.get("AZURE_FOUNDRY_BASE_URL", ""),
                api_key=args.solver_api_key or os.environ.get("AZURE_INFERENCE_CREDENTIAL", ""),
            )

            # Build LLM compiler callable
            compiler_client = OpenAI(
                base_url=os.environ.get("AZURE_FOUNDRY_BASE_URL", ""),
                api_key=os.environ.get("AZURE_INFERENCE_CREDENTIAL", ""),
            )

            def llm_compiler(messages: list[dict[str, str]]) -> str:
                instructions = messages[0]["content"] if messages else ""
                # Pass full conversation (few-shot exemplars + actual claim)
                input_items = [
                    {"role": m["role"], "content": m["content"]}
                    for m in messages[1:]
                ]
                resp = compiler_client.responses.create(
                    model=compiler_model,
                    instructions=instructions,
                    input=input_items,
                )
                for item in resp.output:
                    if item.type == "message":
                        for part in item.content:
                            if hasattr(part, "text"):
                                return part.text
                return ""

            _print(f"  Solver: {solver_model}")
            _print(f"  Compiler: {compiler_model}")

            oi_seed = args.seed if args.seed is not None else 42
            runner = OIEpisodeRunner(
                result.problem, result.world,
                seed=oi_seed, n_mc=20_000, llm_call=llm_compiler,
            )

            # Wire orchestrator-generated sub-questions if available
            if result.sub_questions:
                runner.set_subquestions(result.sub_questions)
                _print(f"  SQs: {len(result.sub_questions)} from orchestrator")

            import time as _time
            t0 = _time.time()
            oi_result = run_oi_investigation(
                runner, solver_client, solver_model, max_iterations=20,
            )
            elapsed = _time.time() - t0

            _print(f"  Steps: {oi_result.n_steps} | Time: {elapsed:.0f}s")
            _print(f"  Submitted: {oi_result.submitted}")
            if oi_result.score:
                s = oi_result.score
                _print(f"  Score: total={s.total:.3f} correct={s.correctness:.3f} "
                       f"coverage={s.coverage:.3f}")

            # Save results (include conversation for debugging)
            # Extract solver tool calls for analysis
            solver_tool_calls = []
            for msg in oi_result.messages:
                if msg.get("role") == "assistant" and msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        fn = tc.get("function", {})
                        entry = {"name": fn.get("name", ""), "step": len(solver_tool_calls)}
                        # For submit_claims, include the claims
                        if fn.get("name") == "submit_claims":
                            try:
                                entry["args"] = json.loads(fn.get("arguments", "{}"))
                            except json.JSONDecodeError:
                                entry["args"] = fn.get("arguments", "")
                        solver_tool_calls.append(entry)

            oi_json = {
                "world": result.world.id,
                "solver_model": solver_model,
                "compiler_model": compiler_model,
                "elapsed": elapsed,
                "n_steps": oi_result.n_steps,
                "submitted": oi_result.submitted,
                "score": oi_result.score.model_dump() if oi_result.score else None,
                "solver_tool_calls": solver_tool_calls,
                "conversation": oi_result.messages,
            }
            oi_path = os.path.join(args.output, "oi_result.json")
            with open(oi_path, "w") as f:
                json.dump(oi_json, f, indent=2)
            _print(f"  {_c(GRN, 'v')} {oi_path}")

            # Generate full_case_oi.md report
            # NOTE: No salience map in E2E — SQ scoring is the primary
            # evaluation. Salience map is available for periodic diagnostics
            # via oi_demo_case.py standalone (not in the critical path).
            try:
                import sys as _sys
                _sys.path.insert(0, os.path.join(
                    os.path.dirname(__file__), "..", "tests", "tools"))
                _sys.path.insert(0, os.path.dirname(__file__))
                from oi_demo_case import build_report
                report = build_report(
                    oi_result, result.world, result.problem,
                    elapsed=elapsed,
                    solver_model=solver_model,
                    compiler_model=compiler_model,
                    runner=runner,
                    sub_questions=result.sub_questions,
                )
                report_path = os.path.join(args.output, "full_case_oi.md")
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(report)
                _print(f"  {_c(GRN, 'v')} {report_path}")
            except Exception as e:
                import traceback
                _print(f"  {_c(YLW, '!')} Report generation failed: {e}")
                traceback.print_exc()

    _print()
    title = getattr(result.world, "scenario_title", None) or result.world.id
    n_tasks = len(result.task) if isinstance(result.task, list) else 0
    _print(f"  {_c(B, _safe(title))}")
    from sreg.world.scm import SCMWorld as _SW
    n_vars = len(result.world.variables) if isinstance(result.world, _SW) else len(result.world.nodes)
    _print(f"  {n_vars} nodes, {n_tasks} tasks")
    _print()


if __name__ == "__main__":
    main()
