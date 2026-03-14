"""Persistent Python interpreter for the agent solver.

Provides a sandboxed exec() environment where variables persist between
calls (like a Jupyter notebook). The agent can analyze datasets, compute
statistics, and build on previous results.

Adapted from worktree rl-env-verifiers (Session C) for the diagnostic solver.
"""

from __future__ import annotations

import ast
import builtins
import contextlib
import io
import json
import traceback
from dataclasses import dataclass

# Allowed imports (agent can use these in python_exec)
ALLOWED_IMPORTS = frozenset({
    "numpy", "pandas", "scipy", "math", "statistics",
    "json", "collections", "itertools", "functools", "re",
})

MAX_OUTPUT_CHARS = 8000
MAX_CODE_CHARS = 4000
TIMEOUT_SECONDS = 5.0


@dataclass
class ExecResult:
    """Result of a python_exec call with tracking info."""

    output: str
    ok: bool
    truncated: bool


def make_python_namespace(
    data_assets: list | None = None,
    observations: dict[str, str] | None = None,
) -> dict:
    """Build a pre-loaded Python namespace for the agent.

    Pre-loads:
    - numpy (np), pandas (pd), scipy, math, statistics, json
    - collections, itertools, functools, re
    - df: first tabular dataset as DataFrame (if available)
    - df_1, df_2, ...: additional datasets
    - observations: dict of observed variable values (updated live)
    """
    import collections as _collections
    import functools as _functools
    import itertools as _itertools
    import math as _math
    import re as _re
    import statistics as _statistics

    import numpy as _np
    import pandas as _pd

    namespace: dict = {
        "__name__": "__main__",
        "__builtins__": _make_safe_builtins(),
        # Libraries
        "np": _np,
        "numpy": _np,
        "pd": _pd,
        "pandas": _pd,
        "math": _math,
        "statistics": _statistics,
        "json": json,
        "collections": _collections,
        "itertools": _itertools,
        "functools": _functools,
        "re": _re,
        # Agent state
        "observations": dict(observations or {}),
    }

    # Load datasets as DataFrames
    if data_assets:
        df_count = 0
        for asset in data_assets:
            data = asset.data if hasattr(asset, "data") else asset.get("data", [])
            fmt = asset.format if hasattr(asset, "format") else asset.get("format", "tabular")
            if fmt in ("tabular", "") and data:
                df = _pd.DataFrame(data)
                var_name = "df" if df_count == 0 else f"df_{df_count}"
                namespace[var_name] = df
                df_count += 1

    return namespace


def _make_safe_builtins() -> dict:
    """Restricted builtins: no open, eval, exec, input, breakpoint."""
    blocked = {"exec", "eval", "compile", "open", "input", "breakpoint"}
    safe = {k: v for k, v in vars(builtins).items() if k not in blocked}

    _real_import = builtins.__import__

    def _restricted_import(name: str, *args: object, **kwargs: object) -> object:
        root = name.split(".")[0]
        if root not in ALLOWED_IMPORTS:
            raise ImportError(f"Import '{name}' is not allowed.")
        return _real_import(name, *args, **kwargs)

    safe["__import__"] = _restricted_import
    return safe


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
                if root not in ALLOWED_IMPORTS:
                    return f"Import '{alias.name}' is not allowed."
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root not in ALLOWED_IMPORTS:
                    return f"Import from '{node.module}' is not allowed."
    return None


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
                exec(compile(mod, "<python_exec>", "exec"), namespace, namespace)  # noqa: S102
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


def execute_code(code: str, namespace: dict) -> ExecResult:
    """Execute Python code in the persistent namespace.

    Returns ExecResult with output string, ok flag, and truncation flag.
    Like a Jupyter cell: if the last statement is an expression, its
    repr is returned as the output.

    NOTE: no timeout enforcement. Thread-based timeouts in CPython cannot
    truly kill running code (GIL) and can corrupt shared namespace state.
    A real timeout requires a process boundary (future work).
    """
    if len(code) > MAX_CODE_CHARS:
        return ExecResult(
            output=f"Error: code exceeds maximum length ({MAX_CODE_CHARS} chars).",
            ok=False,
            truncated=False,
        )

    # Import guard
    import_err = _check_imports(code)
    if import_err:
        return ExecResult(
            output=f"Error (sandbox): {import_err}",
            ok=False,
            truncated=False,
        )

    # Execute directly (no timeout — see docstring)
    stdout, stderr, expr_result = _exec_code(code, namespace)

    # Build output
    parts: list[str] = []
    if stdout:
        parts.append(stdout.rstrip())
    if expr_result:
        parts.append(expr_result)
    if stderr:
        parts.append(stderr.rstrip())

    output = "\n".join(parts) if parts else "(no output)"

    # Truncate
    truncated = len(output) > MAX_OUTPUT_CHARS
    if truncated:
        output = output[:MAX_OUTPUT_CHARS] + "\n... (output truncated)"

    ok = not stderr or ("Error" not in stderr and "Traceback" not in stderr)

    return ExecResult(output=output, ok=ok, truncated=truncated)


__all__ = [
    "ALLOWED_IMPORTS",
    "ExecResult",
    "execute_code",
    "make_python_namespace",
]
