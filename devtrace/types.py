from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CommandMetrics:
    """Captured metrics for a single command execution."""

    command_hash: str
    duration_ms: int
    exit_code: int
    timed_out: bool
    files_touched_count: int
    lines_added: int
    lines_deleted: int


@dataclass(slots=True)
class ModelPrediction:
    """Model inference output for a single command event."""

    predicted_productivity: float
    top_contribution_feature: str
    top_contribution_value: float
    model_ref: str
