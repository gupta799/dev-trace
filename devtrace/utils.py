from __future__ import annotations

import hashlib
import time
import uuid


def now_ts() -> float:
    """Return current unix timestamp."""
    return time.time()


def monotonic_ms() -> int:
    """Return monotonic clock in milliseconds."""
    return int(time.monotonic() * 1000)


def new_id(prefix: str) -> str:
    """Create prefixed unique id."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def hash_command(command: list[str]) -> str:
    """Hash command tokens into stable identity string."""
    raw = "\x1f".join(command)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
