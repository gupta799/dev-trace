from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


def now_ts() -> float:
    """Current time in seconds as float."""
    return time.time()


def new_id(prefix: str = "evt") -> str:
    """Generate a short-ish unique identifier."""
    return f"{prefix}_{uuid.uuid4().hex}"


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
