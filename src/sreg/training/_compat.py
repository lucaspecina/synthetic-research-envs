"""Windows compatibility for verifiers.

verifiers depends on prime_tunnel which uses fcntl (Unix-only).
This module patches fcntl on Windows so verifiers can be imported.
Must be called before importing verifiers.
"""

from __future__ import annotations

import sys


def patch_fcntl_if_windows() -> None:
    """Patch fcntl module on Windows so verifiers can be imported."""
    if sys.platform != "win32":
        return
    if "fcntl" in sys.modules:
        return

    import types

    mock = types.ModuleType("fcntl")
    mock.LOCK_EX = 2
    mock.LOCK_NB = 4
    mock.LOCK_UN = 8
    mock.flock = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["fcntl"] = mock
