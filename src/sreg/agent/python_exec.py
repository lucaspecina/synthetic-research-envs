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

# Allowed imports (agent can use these in python_exec)
ALLOWED_IMPORTS = frozenset({
    "numpy", "pandas", "scipy", "math", "statistics",
    "json", "collections", "itertools", "functools", "re",
})

MAX_OUTPUT_CHARS = 8000
MAX_CODE_CHARS = 4000
TIMEOUT_SECONDS = 5.0


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
            fmt = asset.format if hasattr(asset, "format") else asset.get("format", "")
            if fmt == "tabular" and data:
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


def execute_code(code: str, namespace: dict) -> str:
    """Execute Python code in the persistent namespace.

    Returns the output string (stdout + last expression + stderr).
    Like a Jupyter cell: if the last statement is an expression, its
    repr is returned as the output.
    """
    if len(code) > MAX_CODE_CHARS:
        return f"Error: code exceeds maximum length ({MAX_CODE_CHARS} chars)."

    # Import guard
    import_err = _check_imports(code)
    if import_err:
        return f"Error (sandbox): {import_err}"

    # Parse AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e}"

    # Split trailing expression for auto-display (like Jupyter)
    body = tree.body
    last_expr = None
    if body and isinstance(body[-1], ast.Expr):
        last_expr = body.pop()

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    expr_result = None

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

    # Build output
    parts: list[str] = []
    stdout = stdout_buf.getvalue()
    stderr = stderr_buf.getvalue()

    if stdout:
        parts.append(stdout.rstrip())
    if expr_result:
        parts.append(expr_result)
    if stderr:
        parts.append(stderr.rstrip())

    output = "\n".join(parts) if parts else "(no output)"

    # Truncate
    if len(output) > MAX_OUTPUT_CHARS:
        output = output[:MAX_OUTPUT_CHARS] + "\n... (output truncated)"

    return output


__all__ = [
    "ALLOWED_IMPORTS",
    "execute_code",
    "make_python_namespace",
]
