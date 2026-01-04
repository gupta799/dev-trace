from __future__ import annotations

from enum import Enum


class SessionStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class EventType(str, Enum):
    RUN_COMMAND = "run_command"
    NOTE = "note"
    SNAPSHOT = "snapshot"
    SHELL_START = "shell_start"
    SHELL_END = "shell_end"
