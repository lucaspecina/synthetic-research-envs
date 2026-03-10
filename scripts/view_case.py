"""View an exported SREG case JSON file, section by section.

Usage:
    python scripts/view_case.py output/case.json
    python scripts/view_case.py output/case.json --section world
    python scripts/view_case.py output/case.json --section tasks
    python scripts/view_case.py output/case.json --sections
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap

# -- display helpers --


def _c(code: str, text: str) -> str:
    if not sys.stdout.isatty():
        return str(text)
    return f"{code}{text}\033[0m"


B = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GRN = "\033[92m"
YLW = "\033[93m"
BLU = "\033[94m"
MAG = "\033[95m"
CYN = "\033[96m"


def _line(char: str = "-", width: int = 80) -> None:
    print(_c(DIM, char * width))


def _header(text: str) -> None:
    print()
    _line("=")
    print(_c(B + BLU, f"  {text}"))
    _line("=")


def _kv(key: str, value: str, indent: int = 4) -> None:
    pad = " " * indent
    print(f"{pad}{_c(DIM, key + ':')} {value}")


def _wrap(text: str, width: int = 76, indent: int = 6) -> str:
    return textwrap.fill(
        text, width=width, initial_indent=" " * indent, subsequent_indent=" " * indent
    )


def _safe(text: str) -> str:
    enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
    return text.encode(enc, errors="replace").decode(enc)


# -- section viewers --


def show_metadata(data: dict) -> None:
    meta = data.get("metadata", {})
    _header("METADATA")
    _kv("Timestamp", meta.get("timestamp", "?"))
    _kv("Model", meta.get("model", "?"))
    goal = meta.get("goal", "")
    if "--- RESEARCH SEED ---" in goal:
        _kv("Goal", "from research seed file")
        seed = goal.split("--- RESEARCH SEED ---")[1].split("--- END SEED ---")[0].strip()
        print(_wrap(_safe(seed[:300] + ("..." if len(seed) > 300 else ""))))
    else:
        _kv("Goal", _safe(goal))


def show_process(data: dict) -> None:
    process = data.get("process", {})
    tools = process.get("tools_called", [])
    _header(f"PROCESS ({len(tools)} tool calls)")
    for i, tc in enumerate(tools, 1):
        name = tc.get("tool", "?")
        result = tc.get("result", {})
        status = _c(GRN, "OK") if "error" not in result else _c(RED, "ERROR")
        print(f"    {i}. {_c(B + CYN, name)} {status}")
        # Show key result info
        if name in ("dag_construct", "world_gen", "dag_generate"):
            nn = result.get("num_nodes", "?")
            ne = result.get("num_edges", "?")
            print(f"       {nn} nodes, {ne} edges")
        elif name == "apply_semantics":
            print(f"       {_safe(result.get('scenario_title', '?'))}")
        elif name == "design_case":
            types = result.get("eval_types", [])
            nq = result.get("num_questions", "?")
            print(f"       {nq} questions: {', '.join(types)}")
        elif name == "build_problem":
            bgt = result.get("budget", "?")
            nda = result.get("num_data_assets", 0)
            print(f"       budget={bgt}, datasets={nda}")
        elif "error" in result:
            err = str(result["error"])
            print(f"       {_safe(err[:120])}")


def show_world(data: dict) -> None:
    world = data.get("world", {})
    if not world:
        print("  (no world in export)")
        return
    _header("WORLD")
    _kv("ID", world.get("id", "?"))
    _kv("Scenario", _c(B + MAG, _safe(world.get("scenario_title", "?"))))
    _kv("Domain", world.get("domain", "?"))
    _kv("Difficulty", world.get("difficulty", "?"))
    _kv("Template", world.get("template_family", "?"))
    _kv("Seed", str(world.get("seed", "?")))

    desc = world.get("scenario_description", "")
    if desc:
        print()
        print(_wrap(_safe(desc)))

    print()
    print(f"    {_c(B, 'Nodes')} ({len(world.get('nodes', []))}):")
    for n in world.get("nodes", []):
        ntype = n.get("type", "?")
        icon = {"latent": _c(RED, "*"), "observable": _c(GRN, "o"), "target": _c(YLW, "@")}
        states = ", ".join(n.get("states", []))
        desc_str = ""
        if n.get("description"):
            desc_str = f" -- {_safe(n['description'][:60])}"
        print(f"      {icon.get(ntype, '?')} {_c(B, n['name'])} [{states}]{desc_str}")

    print()
    print(f"    {_c(B, 'Edges')} ({len(world.get('edges', []))}):")
    for e in world.get("edges", []):
        mech = ""
        if e.get("mechanism"):
            mech = f" -- {_safe(e['mechanism'][:50])}"
        print(f"      {e['from']} -> {e['to']}{mech}")


def show_case_plan(data: dict) -> None:
    plan = data.get("case_plan", {})
    if not plan:
        print("  (no case plan in export)")
        return
    _header("CASE PLAN")
    _kv("Title", _c(B + MAG, _safe(plan.get("title", "?"))))
    _kv("Budget", str(plan.get("shared_budget", "?")))
    _kv("Questions", str(len(plan.get("questions", []))))

    ctx = plan.get("research_context", "")
    if ctx:
        print()
        print(_wrap(_safe(ctx)))

    rationale = plan.get("rationale", "")
    if rationale:
        print()
        print(f"    {_c(DIM, 'Rationale:')} {_safe(rationale)}")

    print()
    for i, q in enumerate(plan.get("questions", []), 1):
        primary = " (PRIMARY)" if i == 1 else ""
        print(f"    {_c(B + YLW, f'Q{i}{primary}')}: {_c(B, q.get('eval_type', '?'))}")
        print(f"      Target: {q.get('target_node', '?')}")
        print(_wrap(_safe(q.get("question_text", ""))))
        if q.get("rationale"):
            print(f"      {_c(DIM, 'Rationale:')} {_safe(q['rationale'])}")
        print()


def show_tasks(data: dict) -> None:
    tasks = data.get("tasks", [])
    if not tasks:
        print("  (no tasks in export)")
        return
    _header(f"TASKS ({len(tasks)})")
    for i, t in enumerate(tasks, 1):
        print(f"    {_c(B + CYN, f'Task {i}')}: {_c(B, t.get('type', '?'))}")
        _kv("ID", t.get("id", "?"), indent=6)
        _kv("Target", t.get("target_node", "?"), indent=6)
        _kv("Scoring", t.get("scoring_method", "?"), indent=6)

        q = t.get("question", "")
        print()
        print(_wrap(_safe(q)))

        ans = t.get("correct_answer")
        if ans:
            print()
            if isinstance(ans, dict):
                print(f"      {_c(B + GRN, 'Correct answer:')}")
                for k, v in ans.items():
                    if isinstance(v, float):
                        print(f"        {k}: {v:.4f}")
                    else:
                        print(f"        {k}: {v}")
            else:
                print(f"      {_c(B + GRN, 'Correct answer:')} {ans}")
        print()


def show_problem(data: dict) -> None:
    prob = data.get("research_problem", {})
    if not prob:
        print("  (no research problem in export)")
        return
    _header("RESEARCH PROBLEM (what the agent sees)")
    _kv("Title", _c(B + MAG, _safe(prob.get("title", "?"))))
    _kv("Domain", prob.get("domain", "?"))
    _kv("Target", prob.get("target_node", "?"))
    _kv("Target states", ", ".join(prob.get("target_states", [])))
    _kv("Budget", str(prob.get("budget", "?")))

    desc = prob.get("description", "")
    if desc:
        print()
        print(f"    {_c(B, 'Description:')}")
        print(_wrap(_safe(desc)))

    ctx = prob.get("theoretical_context", "")
    if ctx:
        print()
        print(f"    {_c(B, 'Theoretical context:')}")
        print(_wrap(_safe(ctx)))

    rq = prob.get("research_question", "")
    if rq:
        print()
        print(f"    {_c(B + YLW, 'Research question:')}")
        print(_wrap(_safe(rq)))

    # Data assets
    assets = prob.get("data_assets", [])
    if assets:
        print()
        print(f"    {_c(B, f'Data assets ({len(assets)}):')}")
        for da in assets:
            print(f"      - {_c(B + CYN, da.get('name', '?'))}")
            _kv("Format", da.get("format", "?"), indent=8)
            _kv("Rows", str(da.get("num_rows", "?")), indent=8)
            _kv("Source", da.get("source", "?"), indent=8)
            cols = da.get("columns", [])
            if cols:
                _kv("Columns", ", ".join(cols), indent=8)
            desc_da = da.get("description", "")
            if desc_da:
                print(textwrap.fill(
                    _safe(desc_da), width=72,
                    initial_indent=" " * 8, subsequent_indent=" " * 8,
                ))

    # Actions
    actions = prob.get("available_actions", [])
    if actions:
        print()
        print(f"    {_c(B, f'Available actions ({len(actions)}):')}")
        for a in actions:
            atype = a.get("action_type", "?")
            cost = a.get("cost", 1)
            nodes = ", ".join(a.get("nodes", []))
            desc_a = a.get("description", "")
            print(f"      - [{atype}] cost={cost} nodes=[{nodes}]")
            if desc_a:
                print(f"        {_safe(desc_a[:80])}")


SECTIONS = {
    "metadata": show_metadata,
    "process": show_process,
    "world": show_world,
    "case_plan": show_case_plan,
    "tasks": show_tasks,
    "problem": show_problem,
}


def main():
    parser = argparse.ArgumentParser(description="View an exported SREG case JSON file")
    parser.add_argument("file", help="Path to the exported JSON file")
    parser.add_argument(
        "--section", "-s", type=str, default=None,
        help=f"Show only this section ({', '.join(SECTIONS.keys())})"
    )
    parser.add_argument(
        "--sections", action="store_true",
        help="List available sections and exit"
    )
    args = parser.parse_args()

    with open(args.file, encoding="utf-8") as f:
        data = json.load(f)

    if args.sections:
        print("Available sections:")
        for name in SECTIONS:
            has = name in data or (name == "problem" and "research_problem" in data)
            mark = _c(GRN, "v") if has else _c(RED, "x")
            print(f"  {mark} {name}")
        return

    if args.section:
        if args.section not in SECTIONS:
            print(f"Unknown section: {args.section}")
            print(f"Available: {', '.join(SECTIONS.keys())}")
            sys.exit(1)
        SECTIONS[args.section](data)
    else:
        # Show all sections
        for name, viewer in SECTIONS.items():
            viewer(data)

    print()


if __name__ == "__main__":
    main()
