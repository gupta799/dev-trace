from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from typing import Any

FEATURE_COLUMNS = [
    "duration_ms",
    "exit_code",
    "timed_out",
    "files_touched_count",
    "lines_added",
    "lines_deleted",
]


def _read_csv_rows(dataset_path: Path) -> list[dict[str, str]]:
    with dataset_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader]


def _to_float(value: str) -> float:
    if value == "":
        return 0.0
    return float(value)


def _row_features(row: dict[str, str]) -> list[float]:
    return [_to_float(row[column]) for column in FEATURE_COLUMNS]


def _rules_score(row: dict[str, str]) -> float:
    duration_ms = _to_float(row["duration_ms"])
    exit_code = int(_to_float(row["exit_code"]))
    timed_out = int(_to_float(row["timed_out"]))
    files_touched = _to_float(row["files_touched_count"])
    lines_changed = _to_float(row["lines_added"]) + _to_float(row["lines_deleted"])

    score = 100.0
    score -= min(duration_ms / 5000.0, 20.0)
    score -= 30.0 if exit_code != 0 else 0.0
    score -= 35.0 if timed_out else 0.0
    score += min(files_touched, 10.0) * 0.8
    score += min(lines_changed / 50.0, 10.0)
    return max(0.0, min(score, 100.0))


def _outcome_score(row: dict[str, str]) -> float:
    exit_code = int(_to_float(row["exit_code"]))
    timed_out = int(_to_float(row["timed_out"]))
    if timed_out:
        return 10.0
    if exit_code == 0:
        return 95.0
    return 30.0


def _labels(rows: list[dict[str, str]]) -> list[float]:
    labels: list[float] = []
    for row in rows:
        rule = _rules_score(row)
        outcome = _outcome_score(row)
        labels.append((0.7 * rule) + (0.3 * outcome))
    return labels


def train_xgboost(dataset_path: Path, output_dir: Path) -> dict[str, Any]:
    """Train xgboost regressor on the exported feature dataset."""
    if importlib.util.find_spec("xgboost") is None:
        raise RuntimeError("xgboost is required for training")
    import xgboost as xgb

    rows = _read_csv_rows(dataset_path)
    if not rows:
        raise RuntimeError("dataset is empty")

    x = [_row_features(row) for row in rows]
    y = _labels(rows)

    model = xgb.XGBRegressor(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.08,
        subsample=1.0,
        colsample_bytree=1.0,
        objective="reg:squarederror",
        random_state=42,
        n_jobs=1,
    )
    model.fit(x, y)

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "model.json"
    metadata_path = output_dir / "metadata.json"
    model.save_model(model_path)

    metadata = {
        "model_type": "xgboost_regressor",
        "feature_columns": FEATURE_COLUMNS,
        "label_definition": "0.7*rules_score + 0.3*outcome_score",
        "training_rows": len(rows),
        "model_path": model_path.name,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def score_xgboost(model_dir: Path, dataset_path: Path, output_path: Path) -> int:
    """Score dataset with trained xgboost model and write prediction output CSV."""
    if importlib.util.find_spec("xgboost") is None:
        raise RuntimeError("xgboost is required for scoring")
    import xgboost as xgb

    rows = _read_csv_rows(dataset_path)
    if not rows:
        raise RuntimeError("dataset is empty")

    model = xgb.XGBRegressor()
    model.load_model(model_dir / "model.json")

    x = [_row_features(row) for row in rows]
    predictions = model.predict(x)

    booster = model.get_booster()
    contributions = booster.predict(xgb.DMatrix(x, feature_names=FEATURE_COLUMNS), pred_contribs=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "command_hash",
                "predicted_productivity",
                "top_contribution_feature",
                "top_contribution_value",
            ],
        )
        writer.writeheader()

        for idx, row in enumerate(rows):
            contrib_row = contributions[idx]
            feature_pairs = list(zip(FEATURE_COLUMNS, contrib_row[:-1], strict=True))
            top_feature, top_value = max(feature_pairs, key=lambda item: abs(float(item[1])))
            writer.writerow(
                {
                    "command_hash": row.get("command_hash", ""),
                    "predicted_productivity": f"{float(predictions[idx]):.4f}",
                    "top_contribution_feature": top_feature,
                    "top_contribution_value": f"{float(top_value):.4f}",
                }
            )

    return len(rows)
