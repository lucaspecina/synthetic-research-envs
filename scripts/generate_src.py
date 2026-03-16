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
import itertools
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

def generate(goal: str, model: str | None = None, verbose: bool = False):
    """Run the orchestrator and return the result."""
    from sreg.orchestrator.orchestrator import Orchestrator

    _print(_c(B + BLU, "=== Generating SRC ==="))
    _print(f"  {_c(DIM, 'Model:')} {model or os.environ.get('AZURE_MODEL', 'gpt-4o')}")
    goal_preview = goal[:120] + "..." if len(goal) > 120 else goal
    _print(f"  {_c(DIM, 'Goal:')} {goal_preview}")
    _print()

    o = Orchestrator(model=model) if model else Orchestrator()

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
        n_nodes = len(result.world.nodes)
        n_tasks = len(result.task) if isinstance(result.task, list) else 0
        title = result.world.scenario_title or "?"
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
        export["world"] = result.world.model_dump(mode="json")

    if result.task and isinstance(result.task, list):
        export["tasks"] = [t.model_dump(mode="json") for t in result.task]

    if result.problem:
        export["problem"] = result.problem.model_dump(mode="json")

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

    if tasks:
        lines.append("## Research Questions")
        lines.append("")
        for i, t in enumerate(tasks, 1):
            lines.append(f"### Question {i} ({t.type})")
            lines.append("")
            lines.append(t.question)
            lines.append("")
            lines.append(f"Target variable: {t.target_node}")
            lines.append("")
    else:
        lines.append("## Research Question")
        lines.append("")
        lines.append(problem.research_question or "")
        lines.append("")

    lines.append("## Available Research Actions")
    lines.append("")
    lines.append(f"Budget: {problem.budget} units")
    lines.append("")
    for a in problem.available_actions:
        atype = a.action_type or "observe"
        desc = a.description or ""
        iv = a.intervention_values
        line = f"- ({atype}, cost {a.cost}): {desc}"
        if iv:
            line += f" [sets: {dict(iv)}]"
        lines.append(line)
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


def export_answer_key(result, output_dir: str) -> str | None:
    """Export BN truth + quick guide + correct answers."""
    if not result.world or not result.problem:
        return None

    from sreg.solver.exact_bayes import ExactBayesSolver

    import networkx as nx

    world = result.world
    tasks = result.task if isinstance(result.task, list) else []
    solver = ExactBayesSolver(world)

    target = next(n for n in world.nodes if n.type == "target")
    latents = [n for n in world.nodes if n.type == "latent"]

    dag = nx.DiGraph()
    for n in world.nodes:
        dag.add_node(n.name)
    for e in world.edges:
        dag.add_edge(e.from_node, e.to_node)

    lines = []

    # --- Header ---
    lines.append(f"# Answer Key: {world.scenario_title or world.id}")
    lines.append("")

    # --- Mermaid diagram ---
    lines.append("## Causal DAG")
    lines.append("")
    lines.append("```mermaid")
    lines.append("graph TD")
    for n in world.nodes:
        label = n.name.replace("_", " ")
        if n.type == "latent":
            lines.append(f'    {n.name}(["{label}"]):::latent')
        elif n.type == "target":
            lines.append(f'    {n.name}{{{{"{label}"}}}}:::target')
        else:
            lines.append(f'    {n.name}["{label}"]:::observable')
    lines.append("")
    for e in world.edges:
        lines.append(f"    {e.from_node} --> {e.to_node}")
    lines.append("")
    lines.append("    classDef latent fill:#FF6B6B,stroke:#333,color:#000,stroke-width:2px")
    lines.append("    classDef observable fill:#51CF66,stroke:#333,color:#000")
    lines.append("    classDef target fill:#FFD43B,stroke:#333,color:#000,stroke-width:3px")
    lines.append("```")
    lines.append("")

    # --- Quick guide ---
    tname = target.name.replace("_", " ")
    lines.append("## Quick Guide")
    lines.append("")
    lines.append(f"Predicting **{tname}** ({', '.join(target.states)}).")
    lines.append("")

    # Hidden variables
    if latents:
        lines.append("### Hidden (latent) variables")
        lines.append("")
        for n in latents:
            children = list(dag.successors(n.name))
            cstr = ", ".join(c.replace("_", " ") for c in children)
            lines.append(
                f"- **{n.name.replace('_', ' ')}** ({', '.join(n.states)})"
                f" -- cannot be measured. Affects: {cstr}"
            )
        lines.append("")

    # Information gain ranking
    lines.append("### Variable importance for predicting " + tname)
    lines.append("")
    ig_scores = {}
    for n in world.nodes:
        if n.type == "latent" or n.name == target.name:
            continue
        try:
            ig = solver.information_gain(target.name, {}, n.name)
            ig_scores[n.name] = ig
        except Exception:
            ig_scores[n.name] = 0.0

    sorted_ig = sorted(ig_scores.items(), key=lambda x: -x[1])
    max_ig = max(ig_scores.values()) if ig_scores else 1

    for rank, (name, ig) in enumerate(sorted_ig, 1):
        label = name.replace("_", " ")
        bars = int((ig / max_ig) * 20) if max_ig > 0 else 0
        bar_str = "#" * bars + "." * (20 - bars)
        if ig > max_ig * 0.6:
            strength = "STRONG"
        elif ig > max_ig * 0.2:
            strength = "moderate"
        else:
            strength = "weak"
        lines.append(f"{rank}. **{label}**: {ig:.4f} bits [{bar_str}] -- {strength}")
    lines.append("")

    # Causal relationships
    lines.append("### Causal relationships")
    lines.append("")
    for e in world.edges:
        pn, cn = e.from_node, e.to_node
        pl = pn.replace("_", " ")
        cl = cn.replace("_", " ")
        pnode = next(n for n in world.nodes if n.name == pn)
        cnode = next(n for n in world.nodes if n.name == cn)

        effects = []
        for state in pnode.states:
            try:
                post = solver.posterior(cn, {pn: state})
                effects.append((state, post))
            except Exception:
                pass

        if len(effects) < 2:
            continue

        max_shift = 0
        for cs in cnode.states:
            vals = [d.get(cs, 0) for _, d in effects]
            diff = max(vals) - min(vals)
            if diff > max_shift:
                max_shift = diff

        if max_shift > 0.3:
            sw = "STRONG"
        elif max_shift > 0.1:
            sw = "Moderate"
        else:
            sw = "Weak"

        lines.append(f"**{pl} --> {cl}** ({sw}, {max_shift:.0%} max shift)")
        for state, post in effects:
            dist_str = ", ".join(
                f"{cs}={post.get(cs, 0):.0%}" for cs in cnode.states
            )
            lines.append(f"  - When {pl} = {state}: [{dist_str}]")
        lines.append("")

    # Baseline
    prior = solver.posterior(target.name, {})
    lines.append("### Baseline (no evidence)")
    lines.append("")
    for s in target.states:
        lines.append(f"- {s}: {prior[s]:.1%}")
    lines.append("")

    # --- Formal BN specification ---
    lines.append("---")
    lines.append("")
    lines.append("## Formal BN Specification")
    lines.append("")

    lines.append("### Nodes")
    lines.append("")
    for n in world.nodes:
        lines.append(f"- **{n.name}** ({n.type}): [{', '.join(n.states)}]")
    lines.append("")

    lines.append("### Edges")
    lines.append("")
    for e in world.edges:
        mech = f" -- {e.mechanism}" if e.mechanism else ""
        lines.append(f"- {e.from_node} -> {e.to_node}{mech}")
    lines.append("")

    lines.append("### CPDs")
    lines.append("")
    for cpd in world.cpds:
        lines.append(f"#### {cpd.node}")
        states = cpd.state_names[cpd.node]
        if not cpd.parents:
            lines.append("(root node)")
            lines.append(f"| State | P |")
            lines.append(f"| --- | --- |")
            for i, s in enumerate(states):
                lines.append(f"| {s} | {cpd.table[i][0]:.4f} |")
        else:
            lines.append(f"Parents: {', '.join(cpd.parents)}")
            parent_states_list = [cpd.state_names[p] for p in cpd.parents]
            combos = list(itertools.product(*parent_states_list))
            header = " | ".join(cpd.parents) + " | " + " | ".join(
                f"P({s})" for s in states
            )
            lines.append(f"| {header} |")
            sep = " | ".join(["---"] * (len(cpd.parents) + len(states)))
            lines.append(f"| {sep} |")
            for col_idx, combo in enumerate(combos):
                vals = [f"{cpd.table[row][col_idx]:.3f}" for row in range(len(states))]
                row_str = " | ".join(combo) + " | " + " | ".join(vals)
                lines.append(f"| {row_str} |")
        lines.append("")

    # --- Correct answers ---
    if tasks:
        lines.append("## Correct Answers")
        lines.append("")
        for i, t in enumerate(tasks, 1):
            lines.append(f"### Question {i}: {t.type}")
            lines.append("")
            lines.append(f"**Question:** {t.question}")
            lines.append("")
            lines.append(f"**Target:** {t.target_node}")
            lines.append("")

            if isinstance(t.correct_answer, dict):
                lines.append("**Correct answer:**")
                lines.append("")
                for k, v in sorted(t.correct_answer.items()):
                    if isinstance(v, float):
                        lines.append(f"- {k}: {v:.6f}")
                    else:
                        lines.append(f"- {k}: {v}")
            else:
                lines.append(f"**Correct answer:** {t.correct_answer}")
            lines.append("")

    path = os.path.join(output_dir, "answer_key.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


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

    world = result.world

    G = nx.DiGraph()
    node_types = {}
    node_states = {}
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

    title = world.scenario_title or "Causal DAG"
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
# 3. Solve: run agent + teacher on each task
# ---------------------------------------------------------------------------

def solve_tasks(
    result,
    output_dir: str,
    seed: int = 42,
    solver_model: str | None = None,
    solver_base_url: str | None = None,
    solver_api_key: str | None = None,
) -> tuple[str, str] | None:
    """Run agent on the full case (all tasks together). Export evaluation + trajectory."""
    if not result.world or not result.problem:
        return None

    from openai import OpenAI

    from sreg.agent.agent import AgentSolver

    world = result.world
    problem = result.problem
    tasks = result.task if isinstance(result.task, list) else []
    if not tasks:
        _print(f"  {_c(YLW, '!')} No tasks to solve")
        return None

    _print(f"  Solving {len(tasks)} tasks in a single episode...")

    # Build solver client — configurable backend (Azure, vLLM, etc.)
    base_url = solver_base_url or os.environ.get("AZURE_FOUNDRY_BASE_URL", "")
    api_key = solver_api_key or os.environ.get("AZURE_INFERENCE_CREDENTIAL", "")
    if api_key.lower() == "none":
        api_key = "not-needed"
    client = OpenAI(base_url=base_url, api_key=api_key)

    model = solver_model or os.environ.get(
        "AZURE_SOLVER_MODEL", os.environ.get("AZURE_MODEL", "gpt-4o")
    )
    agent = AgentSolver(model=model, max_iterations=40, client=client)

    if solver_base_url:
        _print(f"  Backend: {solver_base_url} | Model: {model}")
    case_result = agent.solve_case(world, problem, tasks, seed=seed)

    # Build evaluation.md
    eval_lines = []
    eval_lines.append(f"# Evaluation: {world.scenario_title or world.id}")
    eval_lines.append("")
    eval_lines.append(f"Seed: {seed}")
    eval_lines.append(f"Budget: {case_result.budget_used}/{case_result.budget_total}")
    eval_lines.append("")

    eval_lines.append("## Summary")
    eval_lines.append("")
    eval_lines.append("| # | Type | Score | Verdict | Agent Answer |")
    eval_lines.append("| --- | --- | --- | --- | --- |")

    task_details = []
    for i, task in enumerate(tasks, 1):
        tr = case_result.task_results.get(i)
        if tr is None or tr.submitted_answer is None:
            eval_lines.append(f"| {i} | {task.type} | - | NO SUBMIT | - |")
            task_details.append((i, task, tr, "NO SUBMIT", "-"))
            continue

        score = tr.score
        if score is None:
            verdict, score_str = "NO SCORE", "-"
        else:
            score_str = f"{score.functional_score:.4f}"
            if score.functional_score < 0.1:
                verdict = "GOOD"
            elif score.functional_score < 0.5:
                verdict = "OK"
            else:
                verdict = "POOR"

        ans = tr.submitted_answer
        ans_str = str(ans)
        ans_summary = ans_str[:57] + "..." if len(ans_str) > 60 else ans_str
        eval_lines.append(f"| {i} | {task.type} | {score_str} | {verdict} | {ans_summary} |")
        task_details.append((i, task, tr, verdict, score_str))

    # Detailed evaluation
    eval_lines.append("")
    eval_lines.append("## Details")
    eval_lines.append("")
    for i, task, tr, verdict, score_str in task_details:
        eval_lines.append(f"### Question {i}: {task.type}")
        eval_lines.append("")
        q = task.question
        if len(q) > 200:
            q = q[:200] + "..."
        eval_lines.append(f"**Question:** {q}")
        eval_lines.append("")

        correct = task.correct_answer
        eval_lines.append("**Correct answer:**")
        if isinstance(correct, dict):
            for k, v in sorted(correct.items()):
                eval_lines.append(f"- {k}: {v:.4f}" if isinstance(v, float) else f"- {k}: {v}")
        else:
            eval_lines.append(f"- {correct}")
        eval_lines.append("")

        eval_lines.append("**Agent answer:**")
        ans = tr.submitted_answer if tr else None
        if isinstance(ans, dict):
            for k, v in sorted(ans.items()):
                eval_lines.append(f"- {k}: {v:.4f}" if isinstance(v, float) else f"- {k}: {v}")
        elif ans is not None:
            eval_lines.append(f"- {ans}")
        else:
            eval_lines.append("- (no answer submitted)")
        eval_lines.append("")

        eval_lines.append(f"**Score:** {verdict} ({score_str})")
        if tr and tr.reasoning:
            reasoning = tr.reasoning[:300] + "..." if len(tr.reasoning) > 300 else tr.reasoning
            eval_lines.append(f"**Reasoning:** {reasoning}")
        eval_lines.append("")

    eval_path = os.path.join(output_dir, "evaluation.md")
    with open(eval_path, "w", encoding="utf-8") as f:
        f.write("\n".join(eval_lines))

    # Build trajectory.md — single conversation for the whole case
    traj_lines = []
    traj_lines.append(f"# Agent Trajectory: {world.scenario_title or world.id}")
    traj_lines.append("")
    traj_lines.append(f"Seed: {seed}")
    traj_lines.append(f"Budget: {case_result.budget_used}/{case_result.budget_total}")
    traj_lines.append(f"Tasks: {len(tasks)}")
    traj_lines.append("")
    traj_lines.append("## Full conversation")
    traj_lines.append("")

    for msg in case_result.messages:
        role = msg.get("role", "?")

        if role == "system":
            content = msg.get("content", "")
            traj_lines.append(f"> **[SYSTEM]** ({len(content)} chars)")
            traj_lines.append("")

        elif role == "user":
            content = msg.get("content", "")
            traj_lines.append(f"> **[USER]** {content}")
            traj_lines.append("")

        elif role == "assistant":
            content = msg.get("content")
            tool_calls = msg.get("tool_calls", [])

            if content:
                traj_lines.append(f"**[AGENT THINKS]**")
                traj_lines.append("")
                traj_lines.append(content)
                traj_lines.append("")

            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "?")
                fn_args_raw = fn.get("arguments", "{}")
                try:
                    fn_args = json.loads(fn_args_raw)
                except (json.JSONDecodeError, TypeError):
                    fn_args = {"raw": fn_args_raw}

                if fn_name == "think":
                    reasoning = fn_args.get("reasoning", "")
                    traj_lines.append(f"**[AGENT THINKS]**")
                    traj_lines.append("")
                    traj_lines.append(f"> {reasoning}")
                elif fn_name == "python_exec" and "code" in fn_args:
                    traj_lines.append(f"**[AGENT CALLS]** `python_exec`")
                    traj_lines.append("```python")
                    traj_lines.append(fn_args["code"])
                    traj_lines.append("```")
                elif fn_name == "submit":
                    traj_lines.append(f"**[AGENT CALLS]** `submit`")
                    traj_lines.append("```json")
                    traj_lines.append(json.dumps(fn_args, indent=2, ensure_ascii=False))
                    traj_lines.append("```")
                elif fn_name == "research_action":
                    action_id = fn_args.get("action_id", "?")
                    traj_lines.append(f"**[AGENT CALLS]** `research_action` -> `{action_id}`")
                else:
                    traj_lines.append(f"**[AGENT CALLS]** `{fn_name}`")
                    traj_lines.append("```json")
                    traj_lines.append(json.dumps(fn_args, indent=2, ensure_ascii=False))
                    traj_lines.append("```")
                traj_lines.append("")

        elif role == "tool":
            content_raw = msg.get("content", "{}")
            try:
                content = json.loads(content_raw)
            except (json.JSONDecodeError, TypeError):
                content = {"raw": content_raw}

            if isinstance(content, dict) and content.get("status") == "noted":
                pass  # think tool response — reasoning already shown above
            elif isinstance(content, dict) and "output" in content and len(content) == 1:
                output = content["output"]
                if len(output) > 800:
                    output = output[:800] + "\n... (truncated)"
                traj_lines.append(f"**[OUTPUT]**")
                traj_lines.append("```")
                traj_lines.append(output)
                traj_lines.append("```")
            elif isinstance(content, dict) and "findings" in content:
                findings = content["findings"]
                budget = content.get("remaining_budget", "?")
                traj_lines.append(f"**[RESULT]** {findings} (budget left: {budget})")
            elif isinstance(content, dict) and content.get("status") == "submitted":
                q = content.get("question", "?")
                msg_text = content.get("message", "")
                traj_lines.append(f"**[SUBMITTED Q{q}]** {msg_text}")
            elif isinstance(content, dict) and "error" in content:
                traj_lines.append(f"**[ERROR]** {content['error']}")
            else:
                content_str = json.dumps(content, indent=2, ensure_ascii=False)
                if len(content_str) > 500:
                    content_str = content_str[:500] + "\n... (truncated)"
                traj_lines.append("```json")
                traj_lines.append(content_str)
                traj_lines.append("```")
            traj_lines.append("")

    # Per-question results at the end
    traj_lines.append("## Results per question")
    traj_lines.append("")
    for i, task, tr, verdict, score_str in task_details:
        ans = tr.submitted_answer if tr else None
        traj_lines.append(f"### Question {i}: {task.type} ({verdict})")
        traj_lines.append(f"- **Agent:** {ans}")
        traj_lines.append(f"- **Correct:** {task.correct_answer}")
        traj_lines.append(f"- **Score:** {score_str}")
        if tr and tr.reasoning:
            traj_lines.append(f"- **Reasoning:** {tr.reasoning}")
        traj_lines.append("")

    traj_md_path = os.path.join(output_dir, "trajectory.md")
    with open(traj_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(traj_lines))

    # Build full_case.md — everything in one place
    full_lines = []
    full_lines.append(f"# Full Case Report: {world.scenario_title or world.id}")
    full_lines.append("")
    full_lines.append(f"Seed: {seed}")
    full_lines.append(f"Budget: {case_result.budget_used}/{case_result.budget_total}")
    full_lines.append(f"Tasks: {len(tasks)}")
    full_lines.append("")

    # Part 1: What the solver received
    full_lines.append("---")
    full_lines.append("")
    full_lines.append("# Part 1: What the solver received")
    full_lines.append("")

    # System prompt
    from sreg.agent.prompts import build_case_system_prompt as _build_prompt
    system_prompt = _build_prompt(problem, tasks)
    full_lines.append("## System prompt")
    full_lines.append("")
    full_lines.append("```")
    full_lines.append(system_prompt)
    full_lines.append("```")
    full_lines.append("")

    # Dataset summary
    full_lines.append("## Dataset available as `df`")
    full_lines.append("")
    for asset in problem.data_assets:
        if asset.format == "tabular" and asset.data:
            headers = [k for k in asset.data[0].keys() if k != "sample_id"]
            full_lines.append(f"- **{len(asset.data)} rows**, {len(headers)} variables")
            full_lines.append(f"- Columns: {', '.join(headers)}")
            full_lines.append(f"- Pre-loaded in python_exec as `df` (pandas DataFrame)")
            full_lines.append(f"- The solver sees only 10 rows in the prompt but `df` has all {len(asset.data)}")
    full_lines.append("")

    # Part 2: What the solver did
    full_lines.append("---")
    full_lines.append("")
    full_lines.append("# Part 2: What the solver did")
    full_lines.append("")

    for msg in case_result.messages:
        role = msg.get("role", "?")

        if role == "system":
            full_lines.append("> *(system prompt — shown above)*")
            full_lines.append("")

        elif role == "user":
            content = msg.get("content", "")
            full_lines.append(f"> **[USER]** {content}")
            full_lines.append("")

        elif role == "assistant":
            content = msg.get("content")
            tool_calls = msg.get("tool_calls", [])

            if content:
                full_lines.append("**[SOLVER THINKS]**")
                full_lines.append("")
                full_lines.append(content)
                full_lines.append("")

            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "?")
                fn_args_raw = fn.get("arguments", "{}")
                try:
                    fn_args = json.loads(fn_args_raw)
                except (json.JSONDecodeError, TypeError):
                    fn_args = {"raw": fn_args_raw}

                if fn_name == "think":
                    reasoning = fn_args.get("reasoning", "")
                    full_lines.append("**[SOLVER REASONS]**")
                    full_lines.append("")
                    full_lines.append(f"> {reasoning}")
                elif fn_name == "python_exec" and "code" in fn_args:
                    full_lines.append("**[SOLVER RUNS CODE]**")
                    full_lines.append("```python")
                    full_lines.append(fn_args["code"])
                    full_lines.append("```")
                elif fn_name == "submit":
                    full_lines.append("**[SOLVER SUBMITS]**")
                    full_lines.append("```json")
                    full_lines.append(json.dumps(fn_args, indent=2, ensure_ascii=False))
                    full_lines.append("```")
                elif fn_name == "research_action":
                    action_id = fn_args.get("action_id", "?")
                    full_lines.append(f"**[SOLVER MEASURES]** `{action_id}`")
                else:
                    full_lines.append(f"**[SOLVER CALLS]** `{fn_name}`")
                    full_lines.append("```json")
                    full_lines.append(json.dumps(fn_args, indent=2, ensure_ascii=False))
                    full_lines.append("```")
                full_lines.append("")

        elif role == "tool":
            content_raw = msg.get("content", "{}")
            try:
                content = json.loads(content_raw)
            except (json.JSONDecodeError, TypeError):
                content = {"raw": content_raw}

            if isinstance(content, dict) and content.get("status") == "noted":
                pass  # think tool response — reasoning already shown above
            elif isinstance(content, dict) and "output" in content and len(content) == 1:
                output = content["output"]
                if len(output) > 1200:
                    output = output[:1200] + "\n... (truncated)"
                full_lines.append("**[CODE OUTPUT]**")
                full_lines.append("```")
                full_lines.append(output)
                full_lines.append("```")
            elif isinstance(content, dict) and "findings" in content:
                findings = content["findings"]
                budget = content.get("remaining_budget", "?")
                full_lines.append(f"**[FINDING]** {findings} *(budget left: {budget})*")
            elif isinstance(content, dict) and content.get("status") == "submitted":
                q = content.get("question", "?")
                msg_text = content.get("message", "")
                full_lines.append(f"**[RECORDED Q{q}]** {msg_text}")
            elif isinstance(content, dict) and "error" in content:
                full_lines.append(f"**[ERROR]** {content['error']}")
            else:
                content_str = json.dumps(content, indent=2, ensure_ascii=False)
                if len(content_str) > 500:
                    content_str = content_str[:500] + "\n... (truncated)"
                full_lines.append("```json")
                full_lines.append(content_str)
                full_lines.append("```")
            full_lines.append("")

    # Part 3: Evaluation
    full_lines.append("---")
    full_lines.append("")
    full_lines.append("# Part 3: How the solver did (evaluation)")
    full_lines.append("")

    full_lines.append("| # | Type | Score | Verdict | Agent Answer | Correct Answer |")
    full_lines.append("| --- | --- | --- | --- | --- | --- |")

    for i, task, tr, verdict, score_str in task_details:
        ans = tr.submitted_answer if tr else None
        ans_str = str(ans)[:40] if ans else "-"
        correct_str = str(task.correct_answer)[:40]
        full_lines.append(f"| {i} | {task.type} | {score_str} | {verdict} | {ans_str} | {correct_str} |")
    full_lines.append("")

    for i, task, tr, verdict, score_str in task_details:
        full_lines.append(f"### Question {i}: {task.type} — {verdict}")
        full_lines.append("")
        q = task.question
        if len(q) > 300:
            q = q[:300] + "..."
        full_lines.append(f"**Question:** {q}")
        full_lines.append("")

        full_lines.append("**Correct answer:**")
        correct = task.correct_answer
        if isinstance(correct, dict):
            for k, v in sorted(correct.items()):
                full_lines.append(f"- {k}: {v:.4f}" if isinstance(v, float) else f"- {k}: {v}")
        else:
            full_lines.append(f"- {correct}")
        full_lines.append("")

        full_lines.append("**Solver answer:**")
        ans = tr.submitted_answer if tr else None
        if isinstance(ans, dict):
            for k, v in sorted(ans.items()):
                full_lines.append(f"- {k}: {v:.4f}" if isinstance(v, float) else f"- {k}: {v}")
        elif ans is not None:
            full_lines.append(f"- {ans}")
        else:
            full_lines.append("- *(no answer)*")
        full_lines.append("")

        if tr and tr.reasoning:
            full_lines.append(f"**Solver reasoning:** {tr.reasoning}")
            full_lines.append("")

    full_path = os.path.join(output_dir, "full_case.md")
    with open(full_path, "w", encoding="utf-8") as f:
        f.write("\n".join(full_lines))

    return eval_path, traj_md_path


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
        "--solve", action="store_true",
        help="Run agent solver on each task (implies --inspect). Generates evaluation.md + trajectory.md",
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Generate Inspiration Report comparing seed vs SRC (requires --seed-file)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show detailed orchestrator output",
    )
    # Solver backend (for --solve): defaults to same as orchestrator (Azure)
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
    result, steps = generate(goal, model=model, verbose=args.verbose)

    if not result.world or not result.problem:
        _print(f"\n{_c(RED + B, 'Generation failed. Aborting.')}")
        sys.exit(1)

    # --solve implies --inspect
    do_inspect = args.inspect or args.solve

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

        answer_path = export_answer_key(result, args.output)
        if answer_path:
            _print(f"  {_c(GRN, 'v')} {answer_path}")

        dag_path = export_dag_png(result, args.output)
        if dag_path:
            _print(f"  {_c(GRN, 'v')} {dag_path}")

    # Inspiration Report
    if args.report and seed_content:
        _print()
        _print(_c(B + BLU, "=== Inspiration Report ==="))

        from sreg.harness.inspiration_report import generate_report

        tasks = result.task if isinstance(result.task, list) else []
        manifest = result.inspiration_manifest
        report = generate_report(seed_content, result.world, tasks, manifest=manifest)

        # Export manifest if available
        if manifest:
            import json as _json
            manifest_path = os.path.join(args.output, "inspiration_manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                _json.dump(manifest, f, indent=2, ensure_ascii=False)
            _print(f"  {_c(GRN, 'v')} {manifest_path}")

        report_path = os.path.join(args.output, "inspiration_report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report.to_markdown())
        _print(f"  {_c(GRN, 'v')} {report_path}")

        _print(f"  Report generated (see {report_path})")
    elif args.report and not seed_content:
        _print(f"  {_c(YLW, '!')} --report requires --seed-file")

    if args.solve:
        _print()
        _print(_c(B + BLU, "=== Solving tasks ==="))

        solve_seed = args.seed if args.seed is not None else 42
        solver_kwargs = {}
        if args.solver_model:
            solver_kwargs["solver_model"] = args.solver_model
        if args.solver_base_url:
            solver_kwargs["solver_base_url"] = args.solver_base_url
        if args.solver_api_key:
            solver_kwargs["solver_api_key"] = args.solver_api_key
        solve_result = solve_tasks(result, args.output, seed=solve_seed, **solver_kwargs)
        if solve_result:
            eval_path, traj_md_path = solve_result
            jsonl_path = os.path.join(args.output, "trajectories.jsonl")
            _print(f"  {_c(GRN, 'v')} {eval_path}")
            _print(f"  {_c(GRN, 'v')} {traj_md_path}")
            full_path = os.path.join(args.output, "full_case.md")
            if os.path.exists(full_path):
                _print(f"  {_c(GRN, 'v')} {full_path} (complete report)")
            _print(f"  {_c(GRN, 'v')} {jsonl_path} (structured)")

    _print()
    title = result.world.scenario_title or result.world.id
    n_tasks = len(result.task) if isinstance(result.task, list) else 0
    _print(f"  {_c(B, _safe(title))}")
    _print(f"  {len(result.world.nodes)} nodes, {n_tasks} tasks")
    _print()


if __name__ == "__main__":
    main()
