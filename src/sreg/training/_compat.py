"""Windows compatibility: patch missing Unix modules.

verifiers depends on prime_tunnel which uses fcntl (Unix-only).
This shim provides a no-op fcntl on Windows so that verifiers
can be imported for development and testing. Training runs on
Linux (H100) where real fcntl is available.
"""

from __future__ import annotations

import sys


def patch_fcntl_if_windows() -> None:
    """Install a no-op fcntl module on Windows."""
    if sys.platform != "win32":
        return
    if "fcntl" in sys.modules:
        return

    import types

    fcntl = types.ModuleType("fcntl")
    fcntl.flock = lambda *a, **kw: None  # type: ignore[attr-defined]
    fcntl.LOCK_EX = 2  # type: ignore[attr-defined]
    fcntl.LOCK_UN = 8  # type: ignore[attr-defined]
    fcntl.LOCK_NB = 4  # type: ignore[attr-defined]
    sys.modules["fcntl"] = fcntl
