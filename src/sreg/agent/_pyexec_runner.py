"""Subprocess entry point for python_exec isolation (#47).

Spawned by python_exec._exec_code() as a fresh Python process per call.
Reads a pickled user state + code from disk, rebuilds a safe namespace,
executes the code, and writes the results back as pickle.

Runs as: python -m sreg.agent._pyexec_runner <state_in> <code_path> <state_out>

Must stay a self-contained script — the whole point of this file is to
isolate exec() from the parent process, so any shared-state bug in the
parent should not reach here.
"""

from __future__ import annotations

import ast
import contextlib
import io
import pickle
import sys
import traceback
from pathlib import Path

# Keys owned by make_python_namespace() that are rebuilt fresh in each
# subprocess rather than pickled across. Must match the set used by the
# parent when filtering user state before pickling.
INFRASTRUCTURE_KEYS = frozenset({
    "__name__", "__builtins__",
    "np", "numpy", "pd", "pandas",
    "math", "statistics", "json",
    "collections", "itertools", "functools", "re",
})


def main() -> None:
    state_in = Path(sys.argv[1])
    code_path = Path(sys.argv[2])
    state_out = Path(sys.argv[3])

    user_state: dict = pickle.loads(state_in.read_bytes())
    code: str = code_path.read_text(encoding="utf-8")

    # Rebuild namespace: infrastructure fresh, user state restored.
    from sreg.agent.python_exec import make_python_namespace
    namespace = make_python_namespace()
    namespace.update(user_state)

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    expr_result: str | None = None

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        stderr_buf.write(f"SyntaxError: {e}")
        _save_result(
            state_out, stdout_buf.getvalue(), stderr_buf.getvalue(), None, user_state,
        )
        return

    # Split trailing expression for Jupyter-like auto-display.
    body = tree.body
    last_expr = None
    if body and isinstance(body[-1], ast.Expr):
        last_expr = body.pop()

    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        try:
            if body:
                mod = ast.Module(body=body, type_ignores=[])
                exec(  # noqa: S102
                    compile(mod, "<python_exec>", "exec"), namespace, namespace,
                )
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

    new_user_state = _extract_picklable_user_state(namespace)
    _save_result(
        state_out,
        stdout_buf.getvalue(),
        stderr_buf.getvalue(),
        expr_result,
        new_user_state,
    )


def _extract_picklable_user_state(namespace: dict) -> dict:
    """Return just the user-owned, picklable values.

    Drops infrastructure (rebuilt by parent) and anything that does not
    pickle (closures, generators, live file handles). Losing a non-
    picklable value between calls is the accepted trade-off for process
    isolation; the solver primarily deals with DataFrames and dicts,
    which pickle fine.
    """
    out: dict = {}
    for k, v in namespace.items():
        if k in INFRASTRUCTURE_KEYS:
            continue
        try:
            pickle.dumps(v)
        except Exception:
            continue
        out[k] = v
    return out


def _save_result(
    path: Path,
    stdout: str,
    stderr: str,
    expr_result: str | None,
    user_state: dict,
) -> None:
    payload = (stdout, stderr, expr_result, user_state)
    path.write_bytes(pickle.dumps(payload))


if __name__ == "__main__":
    main()
