from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

from devtrace.ml import score_xgboost, train_xgboost

HAS_XGBOOST = importlib.util.find_spec("xgboost") is not None


@pytest.mark.skipif(not HAS_XGBOOST, reason="xgboost not installed")
def test_train_and_score_pipeline(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.csv"
    with dataset.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "command_hash",
                "duration_ms",
                "exit_code",
                "timed_out",
                "files_touched_count",
                "lines_added",
                "lines_deleted",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "command_hash": "a",
                "duration_ms": 20,
                "exit_code": 0,
                "timed_out": 0,
                "files_touched_count": 1,
                "lines_added": 3,
                "lines_deleted": 1,
            }
        )
        writer.writerow(
            {
                "command_hash": "b",
                "duration_ms": 9000,
                "exit_code": 1,
                "timed_out": 0,
                "files_touched_count": 2,
                "lines_added": 1,
                "lines_deleted": 8,
            }
        )

    model_dir = tmp_path / "model"
    metadata = train_xgboost(dataset_path=dataset, output_dir=model_dir)
    assert metadata["training_rows"] == 2

    out = tmp_path / "scores.csv"
    count = score_xgboost(model_dir=model_dir, dataset_path=dataset, output_path=out)
    assert count == 2
    assert out.exists()
