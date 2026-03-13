"""Code execution contracts for the python_exec agent tool.

Interface only — implementation lives in a sandbox module (TBD).
The sandbox must be stateful per episode (like a notebook kernel)
and restricted (no network, no shell, no pip install).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ExecStatus(StrEnum):
    OK = "ok"
    TIMEOUT = "timeout"
    MEMORY = "memory"
    SYNTAX = "syntax"
    RUNTIME = "runtime"
    SANDBOX = "sandbox"  # sandbox violation (import, network, etc.)


class CodeExecResult(BaseModel):
    """Result of executing a code snippet in the sandbox."""

    status: ExecStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    exec_time_ms: int = 0
    stdout_truncated: bool = False
    stderr_truncated: bool = False


class CodeExecConfig(BaseModel):
    """Configuration for the code execution sandbox."""

    timeout_ms: int = 5000
    max_output_bytes: int = 8192
    max_code_chars: int = 3000
    max_memory_mb: int = 1024
    allowed_imports: list[str] = Field(
        default_factory=lambda: [
            "numpy",
            "pandas",
            "scipy",
            "statsmodels",
            "networkx",
            "math",
            "statistics",
            "collections",
            "itertools",
            "functools",
            "json",
            "re",
        ]
    )
