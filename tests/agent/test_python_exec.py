"""Tests for the persistent Python interpreter (agent/python_exec.py)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from sreg.agent.python_exec import (
    ExecResult,
    execute_code,
    make_python_namespace,
)


def test_basic_execution():
    ns = make_python_namespace()
    result = execute_code("x = 2 + 3\nx", ns)
    assert isinstance(result, ExecResult)
    assert "5" in result.output
    assert result.ok
    assert not result.truncated


def test_namespace_persistence():
    ns = make_python_namespace()
    execute_code("a = 42", ns)
    result = execute_code("a * 2", ns)
    assert "84" in result.output


def test_pandas_preloaded():
    ns = make_python_namespace()
    result = execute_code("type(pd.DataFrame()).__name__", ns)
    assert "DataFrame" in result.output
    assert result.ok


def test_numpy_preloaded():
    ns = make_python_namespace()
    result = execute_code("np.array([1,2,3]).sum()", ns)
    assert "6" in result.output


def test_dataset_loaded_as_df():
    data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    assets = [{"data": data, "format": "tabular"}]
    ns = make_python_namespace(data_assets=assets)
    result = execute_code("len(df)", ns)
    assert "2" in result.output


def test_observations_in_namespace():
    ns = make_python_namespace(observations={"temp": "high"})
    result = execute_code("observations['temp']", ns)
    assert "high" in result.output


def test_import_guard_blocks_os():
    ns = make_python_namespace()
    result = execute_code("import os", ns)
    assert "not allowed" in result.output
    assert not result.ok


def test_import_guard_allows_numpy():
    ns = make_python_namespace()
    result = execute_code("import numpy as np2\nnp2.pi", ns)
    assert "3.14" in result.output
    assert result.ok


def test_syntax_error():
    ns = make_python_namespace()
    result = execute_code("def foo(", ns)
    assert "SyntaxError" in result.output
    assert not result.ok


def test_runtime_error():
    ns = make_python_namespace()
    result = execute_code("1/0", ns)
    assert "ZeroDivisionError" in result.output
    assert not result.ok


def test_code_too_long():
    ns = make_python_namespace()
    result = execute_code("x = 1\n" * 5000, ns)
    assert "exceeds maximum" in result.output
    assert not result.ok


def test_output_truncation():
    ns = make_python_namespace()
    result = execute_code("print('x' * 20000)", ns)
    assert result.truncated
    assert "truncated" in result.output


def test_exec_result_fields():
    ns = make_python_namespace()
    result = execute_code("2 + 2", ns)
    assert isinstance(result, ExecResult)
    assert result.ok is True
    assert result.truncated is False
    assert "4" in result.output


def test_no_output():
    ns = make_python_namespace()
    result = execute_code("x = 1", ns)
    assert result.output == "(no output)"
    assert result.ok


def test_print_output():
    ns = make_python_namespace()
    result = execute_code("print('hello world')", ns)
    assert "hello world" in result.output
    assert result.ok


def test_blocked_builtins():
    ns = make_python_namespace()
    result = execute_code("open('test.txt')", ns)
    assert not result.ok


def test_multiple_datasets():
    assets = [
        {"data": [{"x": 1}], "format": "tabular"},
        {"data": [{"y": 2}], "format": "tabular"},
    ]
    ns = make_python_namespace(data_assets=assets)
    r1 = execute_code("list(df.columns)", ns)
    assert "x" in r1.output
    r2 = execute_code("list(df_1.columns)", ns)
    assert "y" in r2.output


def test_parallel_pandas_no_sigsegv():
    """Stress test: the bug that motivated #47.

    Before subprocess isolation, 8 threads calling ``print(df.head())``
    at the same time would race inside pandas' C-side IndexEngine and
    SIGSEGV the parent process (verifiers-rl's ThreadPoolExecutor puts
    rollouts in the same interpreter).

    After subprocess isolation, each call runs in its own process, so
    the C internals cannot corrupt across threads. This test fails hard
    if the regression comes back — the parent dies, pytest reports no
    result, and the harness surfaces the crash.
    """
    data = [{"val": i} for i in range(50)]
    assets = [{"data": data, "format": "tabular"}]

    code = (
        "q1 = df['val'].quantile(0.25)\n"
        "q3 = df['val'].quantile(0.75)\n"
        "iqr = q3 - q1\n"
        "outliers = df[(df['val'] < q1 - 1.5*iqr) | (df['val'] > q3 + 1.5*iqr)]\n"
        "print(df.head())\n"
        "print(outliers.head())\n"
        "df.describe()"
    )

    def one_call() -> ExecResult:
        ns = make_python_namespace(data_assets=assets)
        return execute_code(code, ns)

    n_threads = 8
    with ThreadPoolExecutor(max_workers=n_threads) as ex:
        futures = [ex.submit(one_call) for _ in range(n_threads)]
        results = [f.result() for f in as_completed(futures)]

    assert len(results) == n_threads
    for r in results:
        assert isinstance(r, ExecResult)
        assert r.ok, f"parallel call failed: {r.output[:200]}"
        assert "val" in r.output
