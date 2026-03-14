"""Tests for python_exec tool: persistent Python interpreter for data analysis."""

import asyncio

from sreg.agent.python_exec import _check_imports, _exec_code, _make_safe_builtins
from sreg.training.tools import python_exec


def _make_state():
    """Create a minimal state dict with python namespace initialized."""
    from sreg.training.env import _build_python_namespace

    ns = _build_python_namespace()
    return {
        "python_namespace": ns,
        "python_exec_count": 0,
        "invalid_action_count": 0,
        "tool_trace": [],
    }


# ── _check_imports ──


class TestCheckImports:
    def test_allowed_import(self):
        assert _check_imports("import numpy") is None
        assert _check_imports("import pandas") is None
        assert _check_imports("from scipy import stats") is None
        assert _check_imports("import math") is None
        assert _check_imports("import json") is None

    def test_blocked_import(self):
        err = _check_imports("import os")
        assert err is not None
        assert "os" in err

    def test_blocked_import_from(self):
        err = _check_imports("from subprocess import run")
        assert err is not None
        assert "subprocess" in err

    def test_no_imports(self):
        assert _check_imports("x = 1 + 2") is None

    def test_syntax_error_passes(self):
        # Syntax errors are caught later by exec
        assert _check_imports("def foo(:") is None


# ── _exec_code ──


class TestExecCode:
    def test_basic_print(self):
        ns = {"__builtins__": _make_safe_builtins(), "__name__": "__main__"}
        stdout, stderr, expr = _exec_code("print('hello')", ns)
        assert stdout.strip() == "hello"
        assert stderr == ""

    def test_expression_auto_display(self):
        ns = {"__builtins__": _make_safe_builtins(), "__name__": "__main__"}
        stdout, stderr, expr = _exec_code("2 + 3", ns)
        assert expr == "5"

    def test_persistent_namespace(self):
        ns = {"__builtins__": _make_safe_builtins(), "__name__": "__main__"}
        _exec_code("x = 42", ns)
        stdout, stderr, expr = _exec_code("print(x)", ns)
        assert stdout.strip() == "42"

    def test_syntax_error(self):
        ns = {"__builtins__": _make_safe_builtins(), "__name__": "__main__"}
        stdout, stderr, expr = _exec_code("def foo(:", ns)
        assert "SyntaxError" in stderr

    def test_runtime_error(self):
        ns = {"__builtins__": _make_safe_builtins(), "__name__": "__main__"}
        stdout, stderr, expr = _exec_code("1/0", ns)
        assert "ZeroDivisionError" in stderr

    def test_mixed_print_and_expr(self):
        ns = {"__builtins__": _make_safe_builtins(), "__name__": "__main__"}
        stdout, stderr, expr = _exec_code("print('hi')\n42", ns)
        assert "hi" in stdout
        assert expr == "42"


# ── python_exec tool function ──


class TestPythonExec:
    def test_basic_execution(self):
        state = _make_state()
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="print(2 + 3)", state=state)
        )
        assert "5" in result
        assert state["python_exec_count"] == 1

    def test_persistent_state_between_calls(self):
        state = _make_state()
        asyncio.get_event_loop().run_until_complete(
            python_exec(code="x = 100", state=state)
        )
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="print(x * 2)", state=state)
        )
        assert "200" in result
        assert state["python_exec_count"] == 2

    def test_numpy_available(self):
        state = _make_state()
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="import numpy as np\nprint(np.pi)", state=state)
        )
        assert "3.14" in result

    def test_pandas_available(self):
        state = _make_state()
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(
                code="import pandas as pd\ndf = pd.DataFrame({'a': [1,2,3]})\nprint(df.shape)",
                state=state,
            )
        )
        assert "(3, 1)" in result

    def test_expression_auto_display(self):
        state = _make_state()
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="2 + 3", state=state)
        )
        assert "5" in result

    def test_observations_available(self):
        state = _make_state()
        state["python_namespace"]["observations"] = {"temperature": "high", "pressure": "low"}
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="print(observations)", state=state)
        )
        assert "temperature" in result
        assert "high" in result

    def test_blocked_import(self):
        state = _make_state()
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="import os", state=state)
        )
        assert "Error" in result
        assert "not allowed" in result
        assert state["invalid_action_count"] == 1

    def test_blocked_builtins(self):
        state = _make_state()
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="open('/etc/passwd')", state=state)
        )
        # Should fail because open is removed from builtins
        assert "Error" in result or "NameError" in result

    def test_syntax_error(self):
        state = _make_state()
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="def foo(:", state=state)
        )
        assert "SyntaxError" in result

    def test_runtime_error(self):
        state = _make_state()
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="1/0", state=state)
        )
        assert "ZeroDivisionError" in result

    def test_no_state_returns_error(self):
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="x = 1", state=None)
        )
        assert "Error" in result

    def test_code_too_long(self):
        state = _make_state()
        long_code = "x = 1\n" * 2000  # Well over 3000 chars
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code=long_code, state=state)
        )
        assert "Error" in result
        assert "maximum length" in result

    def test_tool_trace_recorded(self):
        state = _make_state()
        asyncio.get_event_loop().run_until_complete(
            python_exec(code="print('hello')", state=state)
        )
        assert len(state["tool_trace"]) == 1
        assert state["tool_trace"][0]["tool"] == "python_exec"
        assert state["tool_trace"][0]["ok"] is True

    def test_error_trace_recorded(self):
        state = _make_state()
        asyncio.get_event_loop().run_until_complete(
            python_exec(code="import os", state=state)
        )
        assert len(state["tool_trace"]) == 1
        assert state["tool_trace"][0]["ok"] is False

    def test_empty_code(self):
        state = _make_state()
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="", state=state)
        )
        assert "no output" in result.lower()

    def test_no_leakage_world(self):
        state = _make_state()
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="print(world)", state=state)
        )
        assert "NameError" in result

    def test_no_leakage_true_state(self):
        state = _make_state()
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="print(true_state)", state=state)
        )
        assert "NameError" in result

    def test_no_leakage_correct_answer(self):
        state = _make_state()
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="print(correct_answer)", state=state)
        )
        assert "NameError" in result

    def test_data_analysis_flow(self):
        """Simulate a realistic data analysis session."""
        state = _make_state()

        # Step 1: Create a dataset
        asyncio.get_event_loop().run_until_complete(
            python_exec(
                code="data = pd.DataFrame({'temp': [1,2,3,4,5], 'outcome': [0.1,0.3,0.5,0.7,0.9]})",
                state=state,
            )
        )

        # Step 2: Analyze it
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="print(data.describe())", state=state)
        )
        assert "mean" in result

        # Step 3: Compute correlation
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="data.corr()", state=state)
        )
        assert "temp" in result or "outcome" in result  # correlation matrix output

        # Step 4: Use numpy
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(
                code="corr = np.corrcoef(data.temp, data.outcome)[0,1]\nprint(f'r = {corr:.4f}')",
                state=state,
            )
        )
        assert "r = 1.0000" in result

        assert state["python_exec_count"] == 4


class TestPreloadedDataAssets:
    def test_dataframe_preloaded(self):
        """When data_assets are provided, df should be available."""
        from sreg.training.env import _build_python_namespace

        data_assets = [{"data": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]}]
        ns = _build_python_namespace(data_assets=data_assets)
        state = {
            "python_namespace": ns,
            "python_exec_count": 0,
            "invalid_action_count": 0,
            "tool_trace": [],
        }
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="print(df.shape)", state=state)
        )
        assert "(2, 2)" in result

    def test_multiple_dataframes(self):
        from sreg.training.env import _build_python_namespace

        data_assets = [
            {"data": [{"a": 1}]},
            {"data": [{"b": 2}, {"b": 3}]},
        ]
        ns = _build_python_namespace(data_assets=data_assets)
        state = {
            "python_namespace": ns,
            "python_exec_count": 0,
            "invalid_action_count": 0,
            "tool_trace": [],
        }
        result = asyncio.get_event_loop().run_until_complete(
            python_exec(code="print(df.shape, df_1.shape)", state=state)
        )
        assert "(1, 1)" in result
        assert "(2, 1)" in result
