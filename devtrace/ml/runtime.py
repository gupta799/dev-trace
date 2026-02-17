from __future__ import annotations

import importlib.util
import platform
from pathlib import Path

_DARWIN_LIBOMP_CANDIDATES = [
    Path("/opt/homebrew/opt/libomp/lib/libomp.dylib"),
    Path("/usr/local/opt/libomp/lib/libomp.dylib"),
]


def xgboost_runtime_available() -> bool:
    """Check whether xgboost and required native runtime are available."""
    if importlib.util.find_spec("xgboost") is None:
        return False

    if platform.system() != "Darwin":
        return True

    return any(path.exists() for path in _DARWIN_LIBOMP_CANDIDATES)


def ensure_xgboost_runtime() -> None:
    """Raise a clear error when xgboost runtime dependencies are missing."""
    if not xgboost_runtime_available():
        raise RuntimeError("xgboost runtime unavailable; install xgboost and libomp")
