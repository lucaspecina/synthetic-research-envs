"""Run the LLM orchestrator and show step-by-step what it does.

Usage:
    python scripts/test_orchestrator.py
    python scripts/test_orchestrator.py --goal "..." --seed 42
    python scripts/test_orchestrator.py --export output/case_001.json
    python scripts/test_orchestrator.py --goal "epidemiology" --seed 7 --export output/epi.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime

# -- display helpers (inline, no import from sreg.display to keep script standalone) --


def _c(code: str, text: str) -> str:
    if not sys.stdout.isatty():
        return str(text)
    return f"{code}{text}\033[0m"


def _safe(text: str) -> str:
    """Remove chars that can't be encoded in the terminal encoding (e.g. cp1252)."""
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


def _line(char: str = "-", width: int = 80) -> None:
    print(_c(DIM, char * width))


def _header(text: str) -> None:
    print()
    _line("=")
    print(_c(B + BLU, f"  {text}"))
    _line("=")


def _step_header(n: int, text: str) -> None:
    print()
    print(_c(B + CYN, f"  [{n}] {text}"))
    _line("-")


def _kv(key: str, value: str, indent: int = 4) -> None:
    pad = " " * indent
    print(f"{pad}{_c(DIM, key + ':')} {value}")


def _wrap(text: str, width: int = 76, indent: int = 6) -> str:
    """Word-wrap text for terminal display."""
    import textwrap

    return textwrap.fill(
        text, width=width, initial_indent=" " * indent, subsequent_indent=" " * indent
    )


# ------------------------------------------------------------------------------------


def _read_seed_file(path: str, required: bool = False) -> str | None:
    """Read a research seed markdown file, stripping comment lines (> ...)."""
    if not os.path.isfile(path):
        if required:
            print(_c(RED, f"  ERROR: seed file not found: {path}"))
            sys.exit(1)
        return None
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        return None
    # Strip blockquote lines (instructions/comments)
    lines = [ln for ln in content.splitlines() if not ln.strip().startswith(">")]
    return "\n".join(lines).strip() or None


def main():
    parser = argparse.ArgumentParser(
        description="Run the SREG orchestrator and inspect the generated case"
    )
    parser.add_argument("--goal", type=str, default=None, help="Goal for the orchestrator")
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Seed hint for the LLM (appended to goal)"
    )
    parser.add_argument(
        "--seed-file", type=str, default=None,
        help="Path to research seed markdown file (default: research_seed.md if it exists)"
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Model name (default: from AZURE_MODEL env)"
    )
    parser.add_argument(
        "--export", type=str, default=None,
        help="Export full case to JSON file (e.g. output/case.json)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show raw HTTP logs")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s | %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    # Suppress httpx noise unless verbose
    if not args.verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)

    from sreg.orchestrator.orchestrator import Orchestrator

    model = args.model or os.environ.get("AZURE_MODEL", "gpt-4o")

    # Build goal: explicit --goal wins, otherwise read seed file
    seed_file = args.seed_file or "research_seed.md"
    seed_content = None
    if args.goal:
        goal = args.goal
    else:
        seed_content = _read_seed_file(seed_file, required=bool(args.seed_file))
        if seed_content:
            goal = (
                "Generate a synthetic research case based on the following context. "
                "Use dag_construct for the causal structure. "
                "Design a research case with multiple evaluation types.\n\n"
                f"--- RESEARCH SEED ---\n{seed_content}\n--- END SEED ---"
            )
        else:
            goal = (
                "Generate a research problem about marine ecology in a fictional "
                "archipelago, medium difficulty, 8 nodes. Use dag_construct for the "
                "causal structure. Design a research case with at least 3 different "
                "evaluation types."
            )
    if args.seed is not None:
        goal += f" Use seed {args.seed} for reproducibility."

    _header("SREG ORCHESTRATOR")
    _kv("Modelo", _c(B + YLW, model))
    # Show source of goal
    if args.goal:
        _kv("Goal source", "command line (--goal)")
    elif seed_content:
        _kv("Goal source", _c(B + GRN, f"seed file: {seed_file}"))
    else:
        _kv("Goal source", "default (no seed file found)")
    # Show goal (truncated if from seed file — full content is long)
    goal_display = goal
    if "--- RESEARCH SEED ---" in goal:
        goal_display = goal.split("--- RESEARCH SEED ---")[0].strip()
        _kv("Goal", _safe(goal_display))
        _kv("Seed content", f"{len(seed_content)} chars from {seed_file}")
    else:
        _kv("Goal", _safe(goal_display))
    if args.seed is not None:
        _kv("Seed hint", str(args.seed))

    # -- Monkey-patch the orchestrator to intercept each step --
    o = Orchestrator(model=model)
    original_dispatch = o._dispatch_tool
    iteration_count = [0]

    # Override run to show each iteration
    original_create = o._client.chat.completions.create

    def patched_create(**kwargs):
        iteration_count[0] += 1
        n = iteration_count[0]
        _step_header(n, f"LLM call (iteration {n})")
        print(f"    {_c(DIM, 'Enviando')} {len(kwargs.get('messages', []))} mensajes al LLM...")
        response = original_create(**kwargs)

        choice = response.choices[0]
        msg = choice.message

        if msg.content:
            content = _safe(msg.content[:300])
            if len(msg.content) > 300:
                content += "..."
            print(f"    {_c(DIM, 'LLM dice:')} {content}")

        if msg.tool_calls:
            print(f"    {_c(B + GRN, f'LLM quiere llamar {len(msg.tool_calls)} tool(s):')}")
            for tc in msg.tool_calls:
                fn = tc.function.name
                fn_args = json.loads(tc.function.arguments)
                # Show compact args for large calls
                args_str = _format_tool_args(fn, fn_args)
                print(f"      -> {_c(B + CYN, fn)}({args_str})")
        else:
            print(f"    {_c(DIM, 'Finish reason:')} {choice.finish_reason}")

        return response

    o._client.chat.completions.create = patched_create

    tool_results = []

    def patched_dispatch(name, fn_args, result):
        tool_result = original_dispatch(name, fn_args, result)
        tool_results.append((name, fn_args, tool_result))

        if "error" in tool_result:
            print(f"      {_c(RED, 'ERROR:')} {_safe(str(tool_result['error']))}")
        else:
            _show_tool_result(name, tool_result)

        return tool_result

    o._dispatch_tool = patched_dispatch

    # -- Run --
    _header("EJECUTANDO ORCHESTRATOR")
    print(f"    {_c(DIM, 'El LLM va a decidir que parametros usar y llamar las tools...')}")

    result = o.run(goal)

    # -- Process summary --
    _header("PROCESO")
    _kv("Iteraciones LLM", str(iteration_count[0]))
    _kv("Tools llamadas", str(len(tool_results)))

    tools_used = [name for name, _, _ in tool_results]
    for i, name in enumerate(tools_used, 1):
        print(f"      {i}. {name}")

    # -- World --
    if result.world:
        _header("MUNDO GENERADO")
        from sreg.display import show_world

        show_world(result.world)

    # -- Case plan --
    case_plan = None
    case_plan_result = None
    for name, fn_args, tr in tool_results:
        if name == "design_case" and "error" not in tr:
            case_plan_result = tr
            # Get the actual CasePlan object from orchestrator
            if result.world:
                case_plan = o._case_plans.get(result.world.id)
            break

    if case_plan_result:
        _header("CASO DE INVESTIGACION (design_case)")
        _kv("Titulo", _c(B + MAG, _safe(case_plan_result.get("title", ""))))
        _kv("Budget compartido", str(case_plan_result.get("shared_budget", "?")))
        _kv("Preguntas", str(case_plan_result.get("num_questions", "?")))
        _kv("Tasks generadas", str(case_plan_result.get("tasks_generated", "?")))
        _kv("Eval types", ", ".join(case_plan_result.get("eval_types", [])))
        print()

        # Show each question from the case plan
        if case_plan:
            for i, q in enumerate(case_plan.questions, 1):
                primary = " (PRIMARY)" if i == 1 else ""
                print(f"    {_c(B + YLW, f'Q{i}{primary}')}: {_c(B, str(q.eval_type))}")
                print(f"      Target: {q.target_node}")
                print(_wrap(_safe(q.question_text), indent=6))
                if q.rationale:
                    print(f"      {_c(DIM, 'Rationale:')} {_safe(q.rationale)}")
                print()

    # -- Tasks --
    if result.task and isinstance(result.task, list):
        _header(f"TASKS GENERADAS ({len(result.task)})")
        for i, task in enumerate(result.task, 1):
            print(f"    {_c(B + CYN, f'Task {i}')}: {_c(B, str(task.type))}")
            print(f"      ID: {task.id}")
            print(f"      Target: {task.target_node}")
            q = task.question
            if len(q) > 150:
                q = q[:150] + "..."
            print(f"      Pregunta: {_safe(q)}")
            if task.correct_answer:
                ans = task.correct_answer
                if isinstance(ans, dict) and len(str(ans)) > 200:
                    # Truncate long answers
                    ans_str = str(ans)[:200] + "..."
                else:
                    ans_str = str(ans)
                print(f"      Respuesta correcta: {ans_str}")
            print()

    # -- Research problem (what the agent sees) --
    if result.problem:
        _header("PROBLEMA DE INVESTIGACION (lo que ve el agente)")
        from sreg.display import show_research_problem

        show_research_problem(result.problem)

    # -- LLM final response --
    last_assistant = None
    for msg in reversed(result.messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            last_assistant = msg["content"]
            break

    if last_assistant:
        print()
        print(_c(B + BLU, "  RESPUESTA FINAL DEL LLM"))
        _line("-")
        print(f"    {_safe(last_assistant[:500])}")

    # -- Export --
    if args.export:
        export_data = _build_export(result, case_plan, tool_results, goal, model)
        export_path = args.export
        # Create directory if needed
        export_dir = os.path.dirname(export_path)
        if export_dir:
            os.makedirs(export_dir, exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        print()
        _header("EXPORTADO")
        _kv("Archivo", _c(B + GRN, export_path))
        _kv("Tamano", f"{os.path.getsize(export_path):,} bytes")

    print()


def _format_tool_args(fn_name: str, fn_args: dict) -> str:
    """Format tool args compactly for display."""
    if fn_name == "dag_construct":
        nodes = fn_args.get("nodes", [])
        edges = fn_args.get("edges", [])
        node_names = [n.get("name", "?") for n in nodes]
        return (
            f"{len(nodes)} nodes=[{', '.join(node_names)}], "
            f"{len(edges)} edges, "
            f"es={fn_args.get('edge_strength', '?')}, "
            f"seed={fn_args.get('seed', '?')}"
        )
    elif fn_name == "design_case":
        questions = fn_args.get("questions", [])
        types = [q.get("eval_type", "?") for q in questions]
        return (
            f"title={fn_args.get('title', '?')!r}, "
            f"{len(questions)} questions=[{', '.join(types)}], "
            f"budget={fn_args.get('shared_budget', '?')}"
        )
    elif fn_name == "apply_semantics":
        renames = fn_args.get("node_renames", {})
        return (
            f"world={fn_args.get('world_id', '?')}, "
            f"title={fn_args.get('scenario_title', '?')!r}, "
            f"{len(renames)} renames"
        )
    else:
        parts = []
        for k, v in fn_args.items():
            sv = str(v)
            if len(sv) > 60:
                sv = sv[:57] + "..."
            parts.append(f"{k}={sv}")
        return ", ".join(parts)


def _show_tool_result(name: str, result: dict) -> None:
    """Show a concise summary of a tool result."""
    if name in ("world_gen", "dag_generate", "dag_construct"):
        label = {"world_gen": "template", "dag_generate": "generator", "dag_construct": "custom"}
        print(
            f"      {_c(GRN, 'OK')} Mundo {_c(B, result['world_id'])} "
            f"creado ({label[name]})"
        )
        print(f"         {result['num_nodes']} nodos, {result['num_edges']} conexiones")
        print(f"         Dificultad: {_c(YLW, result.get('difficulty', '?'))}")
        for n in result.get("nodes", []):
            icon = {"latent": _c(RED, "*"), "observable": _c(GRN, "o"), "target": _c(YLW, "@")}
            print(
                f"         {icon.get(n['type'], '?')} {n['name']} "
                f"[{', '.join(n['states'])}]"
            )

    elif name == "world_check":
        if result["passed"]:
            print(f"      {_c(GRN, 'OK')} Validacion exitosa")
        else:
            print(f"      {_c(RED, 'FAIL')} Validacion fallida")
            for f in result["failures"]:
                print(f"         - {f}")
        for k, v in result.get("metrics", {}).items():
            label = k.replace("_", " ").title()
            if isinstance(v, float):
                print(f"         {label}: {v:.3f}")
            else:
                print(f"         {label}: {v}")

    elif name == "apply_semantics":
        print(
            f"      {_c(GRN, 'OK')} Semantica aplicada al mundo "
            f"{_c(B, result['world_id'])}"
        )
        title = result.get("scenario_title", "")
        print(f"         Titulo: {_c(B + MAG, _safe(title))}")
        print(f"         Dominio: {result.get('domain', '?')}")
        print(f"         Nodos renombrados: {result.get('nodes_renamed', 0)}")
        for n in result.get("nodes", []):
            icon = {"latent": _c(RED, "*"), "observable": _c(GRN, "o"), "target": _c(YLW, "@")}
            print(f"         {icon.get(n['type'], '?')} {n['name']}")

    elif name == "design_case":
        print(f"      {_c(GRN, 'OK')} Caso de investigacion disenado")
        print(f"         Titulo: {_c(B + MAG, _safe(result.get('title', '')))}")
        print(f"         Preguntas: {result.get('num_questions', '?')}")
        print(f"         Eval types: {', '.join(result.get('eval_types', []))}")
        print(f"         Budget: {result.get('shared_budget', '?')}")
        print(f"         Tasks generadas: {result.get('tasks_generated', '?')}")
        pq = result.get("primary_question", {})
        if pq:
            print(
                f"         Primary: {_c(B, pq.get('eval_type', '?'))} "
                f"-> {pq.get('target_node', '?')}"
            )

    elif name == "build_problem":
        print(f"      {_c(GRN, 'OK')} Problema de investigacion construido")
        print(f"         Titulo: {_c(B + MAG, _safe(result.get('title', '')))}")
        print(f"         Budget: {result.get('budget', '?')}")
        print(f"         Datasets: {result.get('num_data_assets', 0)}")
        print(f"         Acciones: {result.get('num_actions', 0)}")
        q = result.get("research_question", "")
        if len(q) > 120:
            q = q[:120] + "..."
        print(f"         Pregunta: {_safe(q)}")

    elif name == "episode_gen":
        print(f"      {_c(GRN, 'OK')} Episodio {_c(B, result['episode_id'])}")
        print(f"         Budget: {result['budget']}")
        print(
            f"         Variables observables: "
            f"{', '.join(result['available_nodes'])}"
        )

    elif name == "task_gen":
        print(f"      {_c(GRN, 'OK')} Task {_c(B, result['task_id'])}")
        print(f"         Tipo: {result['type']}")
        q = result.get("question", "")
        if len(q) > 100:
            q = q[:100] + "..."
        print(f"         Pregunta: {q}")


def _build_export(result, case_plan, tool_results, goal, model) -> dict:
    """Build a JSON-serializable export of the full case."""
    export: dict = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "goal": goal,
            "model": model,
        },
        "process": {
            "tools_called": [
                {"tool": name, "args": args, "result": tr}
                for name, args, tr in tool_results
            ],
        },
    }

    if result.world:
        w = result.world
        export["world"] = {
            "id": w.id,
            "template_family": w.template_family,
            "seed": w.seed,
            "scenario_title": w.scenario_title,
            "scenario_description": w.scenario_description,
            "domain": w.domain,
            "theoretical_context": w.theoretical_context,
            "difficulty": w.difficulty.level if w.difficulty else None,
            "nodes": [
                {"name": n.name, "type": str(n.type), "states": list(n.states),
                 "description": n.description}
                for n in w.nodes
            ],
            "edges": [
                {"from": e.from_node, "to": e.to_node, "mechanism": e.mechanism}
                for e in w.edges
            ],
        }

    if case_plan:
        export["case_plan"] = {
            "title": case_plan.title,
            "research_context": case_plan.research_context,
            "shared_budget": case_plan.shared_budget,
            "rationale": case_plan.rationale,
            "questions": [
                {
                    "question_text": q.question_text,
                    "eval_type": str(q.eval_type),
                    "target_node": q.target_node,
                    "rationale": q.rationale,
                }
                for q in case_plan.questions
            ],
        }

    if result.task and isinstance(result.task, list):
        export["tasks"] = [
            {
                "id": t.id,
                "type": str(t.type),
                "question": t.question,
                "target_node": t.target_node,
                "correct_answer": t.correct_answer,
                "scoring_method": t.scoring_method,
            }
            for t in result.task
        ]

    if result.problem:
        p = result.problem
        export["research_problem"] = {
            "title": p.title,
            "domain": p.domain,
            "description": p.description,
            "theoretical_context": p.theoretical_context,
            "budget": p.budget,
            "research_question": p.research_question,
            "target_node": p.target_node,
            "target_states": p.target_states,
            "num_data_assets": len(p.data_assets),
            "data_assets": [
                {
                    "name": da.name,
                    "format": da.format,
                    "description": da.description,
                    "num_rows": da.num_rows,
                    "source": da.source,
                    "columns": da.columns,
                }
                for da in p.data_assets
            ],
            "available_actions": [
                {
                    "action_type": str(a.action_type),
                    "nodes": a.nodes,
                    "description": a.description,
                    "cost": a.cost,
                }
                for a in p.available_actions
            ],
        }

    return export


if __name__ == "__main__":
    main()
