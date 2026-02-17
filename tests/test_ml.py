from __future__ import annotations

import csv
from pathlib import Path

import pytest

from devtrace.ml import (
    generate_synthetic_dataset,
    score_single_event,
    score_xgboost,
    train_xgboost,
    xgboost_runtime_available,
)

HAS_XGBOOST = xgboost_runtime_available()


def test_generate_synthetic_dataset_creates_rows(tmp_path: Path) -> None:
    dataset = tmp_path / "synthetic.csv"
    count = generate_synthetic_dataset(output_path=dataset, rows=250, seed=9)
    assert count == 250
    assert dataset.exists()

    with dataset.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 250
    assert "productivity_label" in rows[0]
    assert any(float(row["productivity_label"]) > 80 for row in rows)


@pytest.mark.skipif(not HAS_XGBOOST, reason="xgboost not installed")
def test_train_requires_productivity_label(tmp_path: Path) -> None:
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
                "command_hash": "abc",
                "duration_ms": 50,
                "exit_code": 0,
                "timed_out": 0,
                "files_touched_count": 1,
                "lines_added": 1,
                "lines_deleted": 0,
            }
        )

    with pytest.raises(ValueError, match="productivity_label is required for training"):
        train_xgboost(dataset_path=dataset, output_dir=tmp_path / "model")


@pytest.mark.skipif(not HAS_XGBOOST, reason="xgboost not installed")
def test_train_and_score_pipeline(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.csv"
    generate_synthetic_dataset(output_path=dataset, rows=300, seed=13)

    model_dir = tmp_path / "model"
    metadata = train_xgboost(dataset_path=dataset, output_dir=model_dir)
    assert metadata["training_rows"] == 300
    assert "train_mae" in metadata
    assert (model_dir / "metadata.json").exists()
    assert (model_dir / "model.json").exists()

    out = tmp_path / "scores.csv"
    count = score_xgboost(model_dir=model_dir, dataset_path=dataset, output_path=out)
    assert count == 300
    assert out.exists()

    single = score_single_event(
        model_dir=model_dir,
        row={
            "command_hash": "abc123",
            "duration_ms": "250",
            "exit_code": "0",
            "timed_out": "0",
            "files_touched_count": "3",
            "lines_added": "18",
            "lines_deleted": "2",
        },
    )
    assert 0.0 <= single.predicted_productivity <= 100.0
    assert single.top_contribution_feature != ""
