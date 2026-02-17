from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from devtrace.ml.constants import SCORED_OUTPUT_COLUMNS
from devtrace.ml.schemas import ScoredOutputRow, TelemetryRow


def read_dataset_rows(dataset_path: Path) -> list[TelemetryRow]:
    """Load telemetry rows from CSV and normalize types."""
    with dataset_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [TelemetryRow.model_validate(row) for row in reader]


def write_scored_rows(output_path: Path, rows: Iterable[ScoredOutputRow]) -> int:
    """Write batch-scoring output CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    row_list = list(rows)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCORED_OUTPUT_COLUMNS)
        writer.writeheader()
        for row in row_list:
            writer.writerow(row.to_csv_dict())
    return len(row_list)
