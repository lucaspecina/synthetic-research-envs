"""Persistent Python interpreter for the agent solver.

Provides a sandboxed exec() environment where variables persist between
calls (like a Jupyter notebook). The agent can analyze datasets, compute
statistics, and build on previous results.

Adapted from worktree rl-env-verifiers (Session C) for the diagnostic solver.
"""

from __future__ import annotations

import ast
import builtins
import json
import pickle
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Allowed imports (agent can use these in python_exec)
# Analytical libraries only — no I/O, networking, or system access.
ALLOWED_IMPORTS = frozenset({
    "numpy", "pandas", "scipy", "math", "statistics",
    "statsmodels", "linearmodels", "sklearn",
    "json", "collections", "itertools", "functools", "re",
})

# Keys in the namespace owned by make_python_namespace(). These are
# rebuilt fresh in each subprocess call (they are not pickled across the
# process boundary). The same set is replicated in _pyexec_runner.py —
# keep them in sync.
INFRASTRUCTURE_KEYS = frozenset({
    "__name__", "__builtins__",
    "np", "numpy", "pd", "pandas",
    "math", "statistics", "json",
    "collections", "itertools", "functools", "re",
})

MAX_OUTPUT_CHARS = 8000
MAX_CODE_CHARS = 4000
# Subprocess wall clock limit per call. Includes ~300-500ms of process +
# numpy/pandas import startup, so effective user code budget is ~9.5s.
# Bumped from 5.0 (the pre-subprocess value that was never enforced).
TIMEOUT_SECONDS = 10.0


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
    """Execute code in an isolated subprocess, return (stdout, stderr, expr_result).

    The subprocess reads the current user state from pickle, rebuilds
    infrastructure, executes the code, and writes the new state back.
    Parent updates `namespace` in place so callers keep the same dict
    identity across calls (important for engine.py).

    Subprocess isolation prevents thread-level races in pandas / numpy
    C internals when multiple rollouts run concurrently (#47).
    """
    # Separate user state (picklable) from infrastructure (rebuilt fresh).
    user_state = {k: v for k, v in namespace.items() if k not in INFRASTRUCTURE_KEYS}
    picklable_state = _filter_picklable(user_state)

    with tempfile.TemporaryDirectory(prefix="sreg_pyexec_") as td:
        state_in = Path(td) / "state_in.pkl"
        code_path = Path(td) / "code.py"
        state_out = Path(td) / "state_out.pkl"

        state_in.write_bytes(pickle.dumps(picklable_state))
        code_path.write_text(code, encoding="utf-8")

        cmd = [
            sys.executable,
            "-m", "sreg.agent._pyexec_runner",
            str(state_in), str(code_path), str(state_out),
        ]

        try:
            proc = subprocess.run(
                cmd, capture_output=True, timeout=TIMEOUT_SECONDS, check=False,
            )
        except subprocess.TimeoutExpired:
            return "", f"TimeoutError: execution exceeded {TIMEOUT_SECONDS:.0f}s", None

        if not state_out.exists():
            # Subprocess crashed before writing results (segfault, OOM, etc.)
            err = proc.stderr.decode(errors="replace").strip()
            return "", err or "Subprocess died without output", None

        stdout, stderr, expr_result, new_user_state = pickle.loads(
            state_out.read_bytes(),
        )

    # Update namespace in place to preserve dict identity (engine.py
    # holds references to it across turns).
    for k in list(namespace.keys()):
        if k not in INFRASTRUCTURE_KEYS:
            del namespace[k]
    namespace.update(new_user_state)

    return stdout, stderr, expr_result


def _filter_picklable(state: dict) -> dict:
    """Drop values that fail to pickle.

    Non-picklable user vars (closures, generators, file handles) are
    silently lost between calls. Acceptable trade-off — the solver's
    state is DataFrames + dicts + scalars, all of which pickle cleanly.
    """
    out: dict = {}
    for k, v in state.items():
        try:
            pickle.dumps(v)
        except Exception:
            continue
        out[k] = v
    return out


def execute_code(code: str, namespace: dict) -> ExecResult:
    """Execute Python code in the persistent namespace.

    Returns ExecResult with output string, ok flag, and truncation flag.
    Like a Jupyter cell: if the last statement is an expression, its
    repr is returned as the output.

    Each call spawns a fresh subprocess (see _exec_code) so concurrent
    callers do not share mutable C-extension state (#47). Wall-clock
    limit is TIMEOUT_SECONDS; code exceeding that is killed at the
    process boundary. Non-picklable values in the namespace are dropped
    between calls — the solver state (DataFrames, dicts, scalars)
    pickles fine.
    """
    if len(code) > MAX_CODE_CHARS:
        return ExecResult(
            output=f"Error: code exceeds maximum length ({MAX_CODE_CHARS} chars).",
            ok=False,
            truncated=False,
        )

    # Static import guard (runtime guard lives inside the subprocess).
    import_err = _check_imports(code)
    if import_err:
        return ExecResult(
            output=f"Error (sandbox): {import_err}",
            ok=False,
            truncated=False,
        )

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
