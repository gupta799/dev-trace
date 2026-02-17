from __future__ import annotations

from pathlib import Path
from typing import Any

from devtrace.ml.constants import FEATURE_COLUMNS
from devtrace.ml.dataset import read_dataset_rows
from devtrace.ml.runtime import ensure_xgboost_runtime
from devtrace.ml.schemas import TrainingMetadata


def _mean_absolute_error(actual: list[float], predicted: list[float]) -> float:
    if not actual:
        return 0.0
    total = 0.0
    for idx, value in enumerate(actual):
        total += abs(value - predicted[idx])
    return total / len(actual)


def train_xgboost(
    dataset_path: Path,
    output_dir: Path,
    seed: int = 42,
    n_estimators: int = 280,
    max_depth: int = 5,
    learning_rate: float = 0.06,
) -> dict[str, Any]:
    """Train XGBoost regressor on telemetry dataset and persist artifacts."""
    ensure_xgboost_runtime()
    import xgboost as xgb

    rows = read_dataset_rows(dataset_path)
    if not rows:
        raise RuntimeError("dataset is empty")

    features = [row.to_feature_vector() for row in rows]
    labels = [row.require_label() for row in rows]

    dtrain = xgb.DMatrix(features, label=labels, feature_names=FEATURE_COLUMNS)
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
    train_mae = _mean_absolute_error(labels, predictions)

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "model.json"
    metadata_path = output_dir / "metadata.json"
    booster.save_model(model_path)

    has_supervised_labels = all(row.productivity_label is not None for row in rows)
    metadata = TrainingMetadata(
        model_type="xgboost_booster",
        feature_columns=FEATURE_COLUMNS,
        label_definition="productivity_label column",
        label_source="supervised_or_pseudo",
        has_supervised_labels=has_supervised_labels,
        training_rows=len(rows),
        train_mae=round(train_mae, 4),
        seed=seed,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        model_path=model_path.name,
    )
    metadata_path.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
    return metadata.model_dump()
