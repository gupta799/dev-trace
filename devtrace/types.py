from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CommandMetrics(BaseModel):
    """Captured metrics for a single command execution."""

    model_config = ConfigDict(extra="forbid")

    command_hash: str
    duration_ms: int
    exit_code: int
    timed_out: bool
    files_touched_count: int
    lines_added: int
    lines_deleted: int


class ModelPrediction(BaseModel):
    """Model inference output for a single command event."""

    model_config = ConfigDict(extra="forbid")

    predicted_productivity: float
    top_contribution_feature: str
    top_contribution_value: float
    model_ref: str
