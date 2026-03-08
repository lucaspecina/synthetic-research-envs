"""Run the LLM orchestrator and show step-by-step what it does."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

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


def _line(char: str = "-", width: int = 70) -> None:
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


# ------------------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Test the LLM orchestrator")
    parser.add_argument("--goal", type=str, default=None, help="Goal for the orchestrator")
    parser.add_argument(
        "--model", type=str, default=None, help="Model name (default: from AZURE_MODEL env)"
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
    goal = args.goal or (
        "Generate a research problem about marine ecology in a fictional archipelago, "
        "medium difficulty, 6 nodes"
    )

    _header("SREG ORCHESTRATOR")
    _kv("Modelo", _c(B + YLW, model))
    _kv("Goal", goal)

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
            # Truncate long content, sanitize for terminal encoding
            content = _safe(msg.content[:300])
            if len(msg.content) > 300:
                content += "..."
            print(f"    {_c(DIM, 'LLM dice:')} {content}")

        if msg.tool_calls:
            print(f"    {_c(B + GRN, f'LLM quiere llamar {len(msg.tool_calls)} tool(s):')}")
            for tc in msg.tool_calls:
                fn = tc.function.name
                fn_args = json.loads(tc.function.arguments)
                args_str = ", ".join(f"{k}={v}" for k, v in fn_args.items())
                print(f"      -> {_c(B + CYN, fn)}({args_str})")
        else:
            print(f"    {_c(DIM, f'Finish reason:')} {choice.finish_reason}")

        return response

    o._client.chat.completions.create = patched_create

    tool_results = []

    def patched_dispatch(name, fn_args, result):
        tool_result = original_dispatch(name, fn_args, result)
        tool_results.append((name, fn_args, tool_result))

        if "error" in tool_result:
            print(f"      {_c(RED, 'ERROR:')} {tool_result['error']}")
        else:
            _show_tool_result(name, tool_result)

        return tool_result

    o._dispatch_tool = patched_dispatch

    # -- Run --
    _header("EJECUTANDO ORCHESTRATOR")
    print(f"    {_c(DIM, 'El LLM va a decidir que parametros usar y llamar las tools...')}")

    result = o.run(goal)

    # -- Summary --
    _header("RESUMEN")
    _kv("Iteraciones LLM", str(iteration_count[0]))
    _kv("Tools llamadas", str(len(tool_results)))
    _kv("Mundo generado", _c(B, "Si" if result.world else "No"))
    _kv("Validacion paso", _c(GRN, "Si") if result.validation_passed else _c(RED, "No"))
    _kv("Semantica aplicada", _c(B, "Si" if result.world and result.world.scenario_title else "No"))
    _kv("Problema construido", _c(B, "Si" if result.problem else "No"))

    if result.world:
        print()
        from sreg.display import show_world

        show_world(result.world)

    if result.problem:
        print()
        from sreg.display import show_research_problem

        show_research_problem(result.problem)

    # -- Show what the LLM said at the end --
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

    print()


def _show_tool_result(name: str, result: dict) -> None:
    """Show a concise summary of a tool result."""
    if name == "world_gen":
        print(f"      {_c(GRN, 'OK')} Mundo {_c(B, result['world_id'])} creado")
        print(f"         {result['num_nodes']} nodos, {result['num_edges']} conexiones")
        print(f"         Dificultad: {_c(YLW, result['difficulty'])}")
        for n in result.get("nodes", []):
            icon = {"latent": _c(RED, "*"), "observable": _c(GRN, "o"), "target": _c(YLW, "@")}
            print(f"         {icon.get(n['type'], '?')} {n['name']} [{', '.join(n['states'])}]")

    elif name == "world_check":
        if result["passed"]:
            print(f"      {_c(GRN, 'OK')} Validacion exitosa")
        else:
            print(f"      {_c(RED, 'FAIL')} Validacion fallida")
            for f in result["failures"]:
                print(f"         - {f}")
        for k, v in result.get("metrics", {}).items():
            label = k.replace("_", " ").title()
            print(f"         {label}: {v:.3f}")

    elif name == "episode_gen":
        print(f"      {_c(GRN, 'OK')} Episodio {_c(B, result['episode_id'])}")
        print(f"         Budget: {result['budget']}")
        print(f"         Variables observables: {', '.join(result['available_nodes'])}")

    elif name == "task_gen":
        print(f"      {_c(GRN, 'OK')} Task {_c(B, result['task_id'])}")
        print(f"         Tipo: {result['type']}")
        q = result.get("question", "")
        if len(q) > 100:
            q = q[:100] + "..."
        print(f"         Pregunta: {q}")

    elif name == "apply_semantics":
        print(f"      {_c(GRN, 'OK')} Semantica aplicada al mundo {_c(B, result['world_id'])}")
        title = result.get("scenario_title", "")
        print(f"         Titulo: {_c(B + MAG, _safe(title))}")
        print(f"         Dominio: {result.get('domain', '?')}")
        print(f"         Nodos renombrados: {result.get('nodes_renamed', 0)}")
        for n in result.get("nodes", []):
            icon = {"latent": _c(RED, "*"), "observable": _c(GRN, "o"), "target": _c(YLW, "@")}
            print(f"         {icon.get(n['type'], '?')} {n['name']}")

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


if __name__ == "__main__":
    main()
