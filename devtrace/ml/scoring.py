from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from devtrace.ml.constants import FEATURE_COLUMNS
from devtrace.ml.dataset import read_dataset_rows, write_scored_rows
from devtrace.ml.featurization import strongest_contribution
from devtrace.ml.runtime import ensure_xgboost_runtime
from devtrace.ml.schemas import ScoredOutputRow, TelemetryRow
from devtrace.types import CommandMetrics, ModelPrediction


def _load_booster(model_dir: Path):
    ensure_xgboost_runtime()
    import xgboost as xgb

    booster = xgb.Booster()
    booster.load_model(model_dir / "model.json")
    return xgb, booster


def _predict_rows(model_dir: Path, rows: list[TelemetryRow]) -> list[ScoredOutputRow]:
    xgb, booster = _load_booster(model_dir)

    features = [row.to_feature_vector() for row in rows]
    dmatrix = xgb.DMatrix(features, feature_names=FEATURE_COLUMNS)
    predictions = booster.predict(dmatrix)
    contributions = booster.predict(dmatrix, pred_contribs=True)

    output_rows: list[ScoredOutputRow] = []
    for idx, row in enumerate(rows):
        top_feature, top_value = strongest_contribution(contributions[idx])
        output_rows.append(
            ScoredOutputRow(
                command_hash=row.command_hash,
                predicted_productivity=float(predictions[idx]),
                top_contribution_feature=top_feature,
                top_contribution_value=top_value,
            )
        )
    return output_rows


def score_single_event(model_dir: Path, row: Mapping[str, object]) -> ModelPrediction:
    """Score a single event row with a trained model."""
    normalized = TelemetryRow.model_validate(dict(row))
    output_rows = _predict_rows(model_dir=model_dir, rows=[normalized])
    output = output_rows[0]
    return ModelPrediction(
        predicted_productivity=output.predicted_productivity,
        top_contribution_feature=output.top_contribution_feature,
        top_contribution_value=output.top_contribution_value,
        model_ref=str(model_dir),
    )


def score_command_metrics(model_dir: Path, metrics: CommandMetrics) -> ModelPrediction:
    """Score command metrics object directly."""
    row = TelemetryRow.from_command_metrics(metrics)
    return score_single_event(model_dir=model_dir, row=row.model_dump())


def score_xgboost(model_dir: Path, dataset_path: Path, output_path: Path) -> int:
    """Score dataset with trained model and write prediction output CSV."""
    rows = read_dataset_rows(dataset_path)
    if not rows:
        raise RuntimeError("dataset is empty")

    output_rows = _predict_rows(model_dir=model_dir, rows=rows)
    return write_scored_rows(output_path=output_path, rows=output_rows)
