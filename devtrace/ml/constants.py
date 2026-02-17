from __future__ import annotations

RAW_DATASET_COLUMNS = [
    "command_hash",
    "duration_ms",
    "exit_code",
    "timed_out",
    "files_touched_count",
    "lines_added",
    "lines_deleted",
]

FEATURE_COLUMNS = [
    "command_hash_bucket",
    "duration_ms",
    "exit_code",
    "timed_out",
    "files_touched_count",
    "lines_added",
    "lines_deleted",
]

SCORED_OUTPUT_COLUMNS = [
    "command_hash",
    "predicted_productivity",
    "top_contribution_feature",
    "top_contribution_value",
]
