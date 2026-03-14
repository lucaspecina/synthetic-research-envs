"""Async tool functions for the verifiers environment.

These functions are registered as tools in SregEnv. The model calls them
via tool_calls; verifiers dispatches to them and returns the result as
a ToolMessage.

Hidden args (runner, state) are injected by StatefulToolEnv.update_tool_args()
and are NOT visible in the tool schema shown to the model.

NOTE: The `distribution` parameter on submit() is typed as `str` (JSON string)
rather than `dict[str, float]` because the openai-agents strict schema validator
rejects `additionalProperties` on object types. The model passes a JSON string
like '{"low": 0.3, "high": 0.7}' and we parse it here.
"""

from __future__ import annotations

import ast
import asyncio
import builtins
import contextlib
import io
import json
import traceback

from sreg.env.episode import EpisodeRunner
from sreg.models.code_exec import CodeExecConfig
from sreg.models.episode import ActionDef
from sreg.training.adapters import (
    action_id_is_intervene,
    make_intervene_action,
    make_observe_action,
    step_result_to_text,
)
from sreg.training.types import SubmitPayload
from sreg.training.validators import validate_submit_payload

# Default config for python_exec
_EXEC_CONFIG = CodeExecConfig()
_ALLOWED_IMPORTS = set(_EXEC_CONFIG.allowed_imports)
_MAX_OUTPUT_CHARS = _EXEC_CONFIG.max_output_bytes
_TIMEOUT_SECONDS = _EXEC_CONFIG.timeout_ms / 1000.0


async def research_action(
    action_id: str,
    runner: EpisodeRunner | None = None,
    state: dict | None = None,
) -> str:
    """Execute a research action from the available list.

    Each action has a cost in budget units and returns findings about
    the variables under study.

    Args:
        action_id: ID of the action to execute (e.g. 'obs_temperature').
    """
    if runner is None or state is None:
        return "Error: environment not initialized."

    if runner.is_finished:
        state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1
        state["tool_trace"].append(
            {
                "tool": "research_action",
                "action_id": action_id,
                "ok": False,
                "error": "episode already finished",
            }
        )
        return "Error: episode already finished. Use submit to end."

    # Determine action type from action_defs
    action_defs: list[ActionDef] = list(runner.episode.action_defs)
    try:
        if action_id_is_intervene(action_id, action_defs):
            action = make_intervene_action(action_id)
        else:
            action = make_observe_action(action_id)
        result = runner.step(action)
    except (ValueError, RuntimeError) as e:
        state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1
        state["tool_trace"].append(
            {
                "tool": "research_action",
                "action_id": action_id,
                "ok": False,
                "error": str(e),
            }
        )
        return f"Error: {e}"

    state["budget_used"] = runner.episode.budget - runner.budget_remaining
    state["tool_trace"].append(
        {
            "tool": "research_action",
            "action_id": action_id,
            "ok": True,
        }
    )

    # Sync observations into python_exec namespace
    ns = state.get("python_namespace")
    if ns is not None:
        ns["observations"] = dict(runner.evidence)

    return step_result_to_text(result)


async def submit(
    choice: str | None = None,
    distribution: str | None = None,
    adjustment_set: list[str] | None = None,
    runner: EpisodeRunner | None = None,
    state: dict | None = None,
) -> str:
    """Submit your final answer to the research question.

    Provide exactly ONE of the following, depending on the question type:
    - choice: for questions asking you to pick an option (e.g. "A", "yes", "temperature")
    - distribution: JSON string with a probability distribution (e.g. '{"low": 0.3, "high": 0.7}')
    - adjustment_set: for questions asking which variables to control for (e.g. ["age", "income"])

    Args:
        choice: Single choice answer.
        distribution: JSON string mapping target states to probabilities.
        adjustment_set: List of variable names.
    """
    if state is None:
        return "Error: environment not initialized."

    if state.get("submitted", False):
        state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1
        state["tool_trace"].append(
            {
                "tool": "submit",
                "ok": False,
                "error": "already submitted",
            }
        )
        return "Error: you already submitted an answer."

    # Parse distribution from JSON string if provided
    dist_dict: dict[str, float] | None = None
    if distribution is not None:
        try:
            dist_dict = json.loads(distribution)
            if not isinstance(dist_dict, dict):
                state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1
                state["tool_trace"].append(
                    {
                        "tool": "submit",
                        "ok": False,
                        "error": "distribution is not a JSON object",
                    }
                )
                return "Error: distribution must be a JSON object mapping states to probabilities."
        except (json.JSONDecodeError, TypeError) as e:
            state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1
            state["tool_trace"].append(
                {
                    "tool": "submit",
                    "ok": False,
                    "error": f"invalid distribution JSON: {e}",
                }
            )
            return f"Error: invalid distribution JSON: {e}"

    payload = SubmitPayload(
        choice=choice,
        distribution=dist_dict,
        adjustment_set=adjustment_set,
    )

    eval_type = state.get("eval_type", "")
    try:
        validate_submit_payload(payload, eval_type)
    except ValueError as e:
        state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1
        state["tool_trace"].append(
            {
                "tool": "submit",
                "ok": False,
                "error": str(e),
            }
        )
        return f"Error: {e}"

    # Mark as submitted — scoring happens in the rubric
    state["submitted"] = True
    state["submission_payload"] = payload.model_dump()
    state["done_reason"] = "submit"
    state["tool_trace"].append(
        {
            "tool": "submit",
            "ok": True,
        }
    )

    return "Answer submitted. The episode is now complete."


# ── python_exec: persistent Python interpreter ──


def _check_imports(code: str) -> str | None:
    """Return error message if disallowed imports found, None if OK."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None  # Let exec handle syntax errors

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in _ALLOWED_IMPORTS:
                    return f"Import '{alias.name}' is not allowed."
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root not in _ALLOWED_IMPORTS:
                    return f"Import from '{node.module}' is not allowed."
    return None


def _make_safe_builtins() -> dict:
    """Create a restricted builtins dict with a whitelisted __import__."""
    blocked = {"exec", "eval", "compile", "open", "input", "breakpoint"}
    safe = {k: v for k, v in vars(builtins).items() if k not in blocked}

    # Replace __import__ with a restricted version that only allows whitelisted modules.
    # The AST check catches disallowed imports early, but exec() needs __import__ to work.
    _real_import = builtins.__import__

    def _restricted_import(name: str, *args: object, **kwargs: object) -> object:
        root = name.split(".")[0]
        if root not in _ALLOWED_IMPORTS:
            raise ImportError(f"Import '{name}' is not allowed in this sandbox.")
        return _real_import(name, *args, **kwargs)

    safe["__import__"] = _restricted_import
    return safe


def _exec_code(code: str, namespace: dict) -> tuple[str, str, str | None]:
    """Execute code in namespace, return (stdout, stderr, expr_result).

    Uses AST split: if the last statement is an expression, eval it
    separately and return its repr (like Jupyter's Out[N]).
    """
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    expr_result = None

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return "", f"SyntaxError: {e}", None

    # Split trailing expression for auto-display
    body = tree.body
    last_expr = None
    if body and isinstance(body[-1], ast.Expr):
        last_expr = body.pop()

    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        try:
            if body:
                mod = ast.Module(body=body, type_ignores=[])
                exec(compile(mod, "<python_exec>", "exec"), namespace, namespace)
            if last_expr:
                val = eval(  # noqa: S307
                    compile(ast.Expression(body=last_expr.value), "<python_exec>", "eval"),
                    namespace,
                    namespace,
                )
                if val is not None:
                    expr_result = repr(val)
        except Exception:
            stderr_buf.write(traceback.format_exc())

    return stdout_buf.getvalue(), stderr_buf.getvalue(), expr_result


def _truncate(text: str, max_chars: int = _MAX_OUTPUT_CHARS) -> tuple[str, bool]:
    """Truncate text to max_chars, return (text, was_truncated)."""
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n... (output truncated)", True


async def python_exec(
    code: str,
    state: dict | None = None,
) -> str:
    """Execute Python code in a persistent interpreter.

    Variables, imports, and data persist between calls within the same
    episode (like a Jupyter notebook). The observations from research_action
    calls are available as the `observations` dict.

    Pre-loaded in the namespace: numpy (np), pandas (pd), scipy, math,
    statistics, json, collections, itertools, functools, re.
    Datasets from the research case are available as `df` (if provided).

    Args:
        code: Python code to execute.
    """
    if state is None:
        return "Error: environment not initialized."

    namespace = state.get("python_namespace")
    if namespace is None:
        return "Error: python interpreter not initialized."

    # Code length check
    if len(code) > _EXEC_CONFIG.max_code_chars:
        state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1
        state["tool_trace"].append(
            {
                "tool": "python_exec",
                "ok": False,
                "error": "code too long",
            }
        )
        return f"Error: code exceeds maximum length ({_EXEC_CONFIG.max_code_chars} chars)."

    # Import guard
    import_err = _check_imports(code)
    if import_err:
        state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1
        state["tool_trace"].append(
            {
                "tool": "python_exec",
                "ok": False,
                "error": f"sandbox: {import_err}",
            }
        )
        return f"Error (sandbox): {import_err}"

    # Execute with timeout
    try:
        stdout, stderr, expr_result = await asyncio.wait_for(
            asyncio.to_thread(_exec_code, code, namespace),
            timeout=_TIMEOUT_SECONDS,
        )
    except (asyncio.TimeoutError, TimeoutError):
        state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1
        state["tool_trace"].append(
            {
                "tool": "python_exec",
                "ok": False,
                "error": "timeout",
            }
        )
        return f"Error (timeout): Code execution exceeded {_TIMEOUT_SECONDS:.0f} seconds."

    # Build output
    exec_count = state.get("python_exec_count", 0) + 1
    state["python_exec_count"] = exec_count

    parts: list[str] = []
    if stdout:
        parts.append(stdout.rstrip())
    if expr_result:
        parts.append(f"Out[{exec_count}]: {expr_result}")
    if stderr:
        parts.append(stderr.rstrip())

    output = "\n".join(parts) if parts else "(no output)"
    output, was_truncated = _truncate(output)

    ok = "Error" not in stderr and "Traceback" not in stderr
    state["tool_trace"].append(
        {
            "tool": "python_exec",
            "ok": ok,
            "exec_count": exec_count,
            "truncated": was_truncated,
        }
    )

    return output
