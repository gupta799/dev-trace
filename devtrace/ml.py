from __future__ import annotations

import csv
import importlib.util
import json
import platform
import random
from pathlib import Path
from typing import Any

from devtrace.types import ModelPrediction

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


def xgboost_runtime_available() -> bool:
    if importlib.util.find_spec("xgboost") is None:
        return False

    if platform.system() != "Darwin":
        return True

    return any(
        Path(candidate).exists()
        for candidate in [
            "/opt/homebrew/opt/libomp/lib/libomp.dylib",
            "/usr/local/opt/libomp/lib/libomp.dylib",
        ]
    )


def _read_csv_rows(dataset_path: Path) -> list[dict[str, str]]:
    with dataset_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader]


def _to_float(value: str) -> float:
    lowered = value.lower()
    if lowered == "true":
        return 1.0
    if lowered == "false":
        return 0.0
    if value == "":
        return 0.0
    return float(value)


def _command_hash_bucket(command_hash: str, buckets: int = 1024) -> int:
    hex_chars = "".join(ch for ch in command_hash.lower() if ch in "0123456789abcdef")
    if not hex_chars:
        return 0
    return int(hex_chars[:16], 16) % buckets


def _row_features(row: dict[str, str]) -> list[float]:
    return [
        float(_command_hash_bucket(row.get("command_hash", ""))),
        _to_float(row.get("duration_ms", "0")),
        _to_float(row.get("exit_code", "0")),
        _to_float(row.get("timed_out", "0")),
        _to_float(row.get("files_touched_count", "0")),
        _to_float(row.get("lines_added", "0")),
        _to_float(row.get("lines_deleted", "0")),
    ]


def _rules_score(row: dict[str, str]) -> float:
    duration_ms = _to_float(row.get("duration_ms", "0"))
    exit_code = int(_to_float(row.get("exit_code", "0")))
    timed_out = int(_to_float(row.get("timed_out", "0")))
    files_touched = _to_float(row.get("files_touched_count", "0"))
    lines_changed = _to_float(row.get("lines_added", "0")) + _to_float(row.get("lines_deleted", "0"))

    score = 70.0
    score -= min(duration_ms / 30000.0, 18.0)
    score -= 30.0 if exit_code != 0 else 0.0
    score -= 35.0 if timed_out else 0.0
    score += min(files_touched, 20.0) * 0.7
    score += min(lines_changed / 120.0, 16.0)
    if exit_code != 0 and lines_changed > 150:
        score -= 8.0
    return max(0.0, min(score, 100.0))


def _outcome_score(row: dict[str, str]) -> float:
    exit_code = int(_to_float(row.get("exit_code", "0")))
    timed_out = int(_to_float(row.get("timed_out", "0")))
    if timed_out:
        return 10.0
    if exit_code == 0:
        return 95.0
    return 30.0


def _labels(rows: list[dict[str, str]]) -> list[float]:
    labels: list[float] = []
    for row in rows:
        if row.get("productivity_label", "") != "":
            labels.append(_to_float(row["productivity_label"]))
            continue
        rule = _rules_score(row)
        outcome = _outcome_score(row)
        labels.append((0.7 * rule) + (0.3 * outcome))
    return labels


def _mean_absolute_error(actual: list[float], predicted: list[float]) -> float:
    if not actual:
        return 0.0
    total = 0.0
    for idx, value in enumerate(actual):
        total += abs(value - predicted[idx])
    return total / len(actual)


def score_single_event(model_dir: Path, row: dict[str, str]) -> ModelPrediction:
    """Score a single event row with a trained model."""
    if not xgboost_runtime_available():
        raise RuntimeError("xgboost runtime unavailable; install xgboost and libomp")
    import xgboost as xgb

    x = [_row_features(row)]
    dmatrix = xgb.DMatrix(x, feature_names=FEATURE_COLUMNS)
    booster = xgb.Booster()
    booster.load_model(model_dir / "model.json")

    prediction = float(booster.predict(dmatrix)[0])
    contributions = booster.predict(dmatrix, pred_contribs=True)[0]
    feature_pairs = list(zip(FEATURE_COLUMNS, contributions[:-1], strict=True))
    top_feature, top_value = max(feature_pairs, key=lambda item: abs(float(item[1])))
    return ModelPrediction(
        predicted_productivity=prediction,
        top_contribution_feature=top_feature,
        top_contribution_value=float(top_value),
        model_ref=str(model_dir),
    )


def train_xgboost(
    dataset_path: Path,
    output_dir: Path,
    seed: int = 42,
    n_estimators: int = 280,
    max_depth: int = 5,
    learning_rate: float = 0.06,
) -> dict[str, Any]:
    """Train xgboost regressor on the exported feature dataset."""
    if not xgboost_runtime_available():
        raise RuntimeError("xgboost runtime unavailable; install xgboost and libomp")
    import xgboost as xgb

    rows = _read_csv_rows(dataset_path)
    if not rows:
        raise RuntimeError("dataset is empty")

    x = [_row_features(row) for row in rows]
    y = _labels(rows)

    dtrain = xgb.DMatrix(x, label=y, feature_names=FEATURE_COLUMNS)
    booster = xgb.train(
        params={
            "objective": "reg:squarederror",
            "max_depth": max_depth,
            "eta": learning_rate,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "seed": seed,
        },
        dtrain=dtrain,
        num_boost_round=n_estimators,
    )
    predictions = [float(value) for value in booster.predict(dtrain)]
    train_mae = _mean_absolute_error(y, predictions)

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "model.json"
    metadata_path = output_dir / "metadata.json"
    booster.save_model(model_path)

    has_supervised_labels = any(row.get("productivity_label", "") != "" for row in rows)
    metadata = {
        "model_type": "xgboost_booster",
        "feature_columns": FEATURE_COLUMNS,
        "label_definition": (
            "productivity_label column when present; "
            "otherwise weak-label 0.7*rules_score + 0.3*outcome_score"
        ),
        "label_source": "supervised_or_weak",
        "has_supervised_labels": has_supervised_labels,
        "training_rows": len(rows),
        "train_mae": round(train_mae, 4),
        "seed": seed,
        "n_estimators": n_estimators,
        "max_depth": max_depth,
        "learning_rate": learning_rate,
        "model_path": model_path.name,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def score_xgboost(model_dir: Path, dataset_path: Path, output_path: Path) -> int:
    """Score dataset with trained xgboost model and write prediction output CSV."""
    if not xgboost_runtime_available():
        raise RuntimeError("xgboost runtime unavailable; install xgboost and libomp")
    import xgboost as xgb

    rows = _read_csv_rows(dataset_path)
    if not rows:
        raise RuntimeError("dataset is empty")

    x = [_row_features(row) for row in rows]
    dmatrix = xgb.DMatrix(x, feature_names=FEATURE_COLUMNS)
    booster = xgb.Booster()
    booster.load_model(model_dir / "model.json")
    predictions = booster.predict(dmatrix)
    contributions = booster.predict(dmatrix, pred_contribs=True)

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


def _sample_profile(rng: random.Random) -> dict[str, int]:
    draw = rng.random()

    if draw < 0.50:
        return {
            "duration_ms": rng.randint(120, 3500),
            "exit_code": 0,
            "timed_out": 0,
            "files_touched_count": rng.randint(1, 8),
            "lines_added": rng.randint(2, 120),
            "lines_deleted": rng.randint(0, 60),
        }

    if draw < 0.72:
        return {
            "duration_ms": rng.randint(2500, 26000),
            "exit_code": 0,
            "timed_out": 0,
            "files_touched_count": rng.randint(6, 45),
            "lines_added": rng.randint(80, 900),
            "lines_deleted": rng.randint(30, 650),
        }

    if draw < 0.90:
        return {
            "duration_ms": rng.randint(200, 10000),
            "exit_code": 1,
            "timed_out": 0,
            "files_touched_count": rng.randint(1, 14),
            "lines_added": rng.randint(1, 200),
            "lines_deleted": rng.randint(0, 220),
        }

    return {
        "duration_ms": rng.randint(10000, 120000),
        "exit_code": rng.choice([124, 137]),
        "timed_out": 1,
        "files_touched_count": rng.randint(0, 6),
        "lines_added": rng.randint(0, 40),
        "lines_deleted": rng.randint(0, 50),
    }


def _synthetic_label(row: dict[str, int], rng: random.Random) -> float:
    score = 65.0
    score += 20.0 if row["exit_code"] == 0 else -20.0
    score -= 28.0 if row["timed_out"] else 0.0
    score += min(row["files_touched_count"], 20) * 0.75
    score += min((row["lines_added"] + row["lines_deleted"]) / 120.0, 17.0)
    score -= min(row["duration_ms"] / 24000.0, 18.0)
    if row["exit_code"] != 0 and (row["lines_added"] + row["lines_deleted"]) > 240:
        score -= 8.0
    score += rng.uniform(-6.0, 6.0)
    return max(0.0, min(score, 100.0))


def generate_synthetic_dataset(output_path: Path, rows: int, seed: int = 42) -> int:
    """Generate synthetic training data for bootstrapping the XGBoost pipeline."""
    if rows <= 0:
        raise ValueError("rows must be > 0")

    rng = random.Random(seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*RAW_DATASET_COLUMNS, "productivity_label"])
        writer.writeheader()

        for _ in range(rows):
            profile = _sample_profile(rng)
            writer.writerow(
                {
                    "command_hash": f"{rng.getrandbits(64):016x}",
                    "duration_ms": profile["duration_ms"],
                    "exit_code": profile["exit_code"],
                    "timed_out": profile["timed_out"],
                    "files_touched_count": profile["files_touched_count"],
                    "lines_added": profile["lines_added"],
                    "lines_deleted": profile["lines_deleted"],
                    "productivity_label": f"{_synthetic_label(profile, rng):.4f}",
                }
            )

    return rows
