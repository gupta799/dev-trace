from __future__ import annotations

from collections.abc import Sequence

from devtrace.ml.constants import FEATURE_COLUMNS


def command_hash_bucket(command_hash: str, buckets: int = 1024) -> int:
    """Map command hash into a fixed-size numeric bucket for tree features."""
    hex_chars = "".join(ch for ch in command_hash.lower() if ch in "0123456789abcdef")
    if not hex_chars:
        return 0
    return int(hex_chars[:16], 16) % buckets


def build_feature_vector(
    *,
    command_hash: str,
    duration_ms: float,
    exit_code: int,
    timed_out: bool,
    files_touched_count: float,
    lines_added: float,
    lines_deleted: float,
) -> list[float]:
    """Build model feature vector from telemetry metrics."""
    return [
        float(command_hash_bucket(command_hash)),
        float(duration_ms),
        float(exit_code),
        float(int(timed_out)),
        float(files_touched_count),
        float(lines_added),
        float(lines_deleted),
    ]


def strongest_contribution(contributions: Sequence[float]) -> tuple[str, float]:
    """Return the feature with highest absolute SHAP-style contribution."""
    feature_pairs = list(zip(FEATURE_COLUMNS, contributions[:-1], strict=True))
    top_feature, top_value = max(feature_pairs, key=lambda item: abs(float(item[1])))
    return top_feature, float(top_value)
