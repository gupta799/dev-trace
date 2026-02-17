from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from devtrace.types import CommandMetrics


class TelemetryRow(BaseModel):
    """Normalized telemetry row used across training and inference."""

    model_config = ConfigDict(extra="ignore")

    command_hash: str = ""
    duration_ms: float = 0.0
    exit_code: int = 0
    timed_out: bool = False
    files_touched_count: float = 0.0
    lines_added: float = 0.0
    lines_deleted: float = 0.0
    productivity_label: float | None = None

    @field_validator("command_hash", mode="before")
    @classmethod
    def _normalize_command_hash(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("duration_ms", "files_touched_count", "lines_added", "lines_deleted", mode="before")
    @classmethod
    def _normalize_float(cls, value: Any) -> float:
        if value in (None, ""):
            return 0.0
        return float(value)

    @field_validator("exit_code", mode="before")
    @classmethod
    def _normalize_exit_code(cls, value: Any) -> int:
        if value in (None, ""):
            return 0
        return int(float(value))

    @field_validator("timed_out", mode="before")
    @classmethod
    def _normalize_timed_out(cls, value: Any) -> bool:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"", "0", "false", "no", "off", "n"}:
                return False
            if lowered in {"1", "true", "yes", "on", "y"}:
                return True
        return bool(value)

    @field_validator("productivity_label", mode="before")
    @classmethod
    def _normalize_productivity_label(cls, value: Any) -> float | None:
        if value in (None, ""):
            return None
        return float(value)

    @classmethod
    def from_command_metrics(cls, metrics: CommandMetrics) -> TelemetryRow:
        return cls(
            command_hash=metrics.command_hash,
            duration_ms=metrics.duration_ms,
            exit_code=metrics.exit_code,
            timed_out=metrics.timed_out,
            files_touched_count=metrics.files_touched_count,
            lines_added=metrics.lines_added,
            lines_deleted=metrics.lines_deleted,
        )

    def to_feature_vector(self) -> list[float]:
        from devtrace.ml.featurization import build_feature_vector

        return build_feature_vector(
            command_hash=self.command_hash,
            duration_ms=self.duration_ms,
            exit_code=self.exit_code,
            timed_out=self.timed_out,
            files_touched_count=self.files_touched_count,
            lines_added=self.lines_added,
            lines_deleted=self.lines_deleted,
        )

    def require_label(self) -> float:
        if self.productivity_label is None:
            raise ValueError("productivity_label is required for training")
        return float(self.productivity_label)


class ScoredOutputRow(BaseModel):
    """CSV output row for batch scoring results."""

    command_hash: str
    predicted_productivity: float
    top_contribution_feature: str
    top_contribution_value: float

    def to_csv_dict(self) -> dict[str, str]:
        return {
            "command_hash": self.command_hash,
            "predicted_productivity": f"{self.predicted_productivity:.4f}",
            "top_contribution_feature": self.top_contribution_feature,
            "top_contribution_value": f"{self.top_contribution_value:.4f}",
        }


class TrainingMetadata(BaseModel):
    """Persisted metadata describing a trained XGBoost artifact."""

    model_type: str
    feature_columns: list[str]
    label_definition: str
    label_source: str
    has_supervised_labels: bool
    training_rows: int
    train_mae: float
    seed: int
    n_estimators: int
    max_depth: int
    learning_rate: float
    model_path: str
