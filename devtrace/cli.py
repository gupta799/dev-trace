from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from devtrace.ml import (
    generate_synthetic_dataset,
    score_single_event,
    score_xgboost,
    train_xgboost,
    xgboost_runtime_available,
)
from devtrace.runner import run_command
from devtrace.storage import LocalStore

app = typer.Typer(help="DevTrace CLI")
ml_app = typer.Typer(help="XGBoost training and scoring")
console = Console()


def _store(path: Path) -> LocalStore:
    store = LocalStore(path)
    store.ensure_storage()
    return store


@app.command()
def init(
    path: Annotated[Path, typer.Option("--path", "-p", help="Storage directory")] = Path(
        ".devtrace"
    ),
) -> None:
    """Initialize local storage."""
    store = _store(path)
    console.print(f"Initialized DevTrace at {store.db_path}")


@app.command("run")
def run_cmd(
    command: Annotated[list[str], typer.Argument(help="Command to execute (pass with -- separator)")],
    agent: Annotated[str | None, typer.Option("--agent", "-a", help="Agent id")] = None,
    timeout: Annotated[float | None, typer.Option("--timeout", help="Timeout in seconds")] = None,
    path: Annotated[Path, typer.Option("--path", "-p", help="Storage directory")] = Path(".devtrace"),
    repo: Annotated[Path, typer.Option("--repo", "-r", help="Repository path")] = Path("."),
    model_dir: Annotated[
        Path | None,
        typer.Option("--model-dir", help="Model dir for automatic scoring (default: <path>/model-xgb)"),
    ] = None,
) -> None:
    """Run a command and capture minimal telemetry metrics."""
    if not command:
        raise typer.BadParameter("command is required")

    store = _store(path)
    metrics = run_command(command=command, repo_path=repo, timeout_s=timeout)
    resolved_model_dir = model_dir if model_dir is not None else path / "model-xgb"
    prediction = None
    model_path = resolved_model_dir / "model.json"
    if model_path.exists() and xgboost_runtime_available():
        prediction = score_single_event(
            model_dir=resolved_model_dir,
            row={
                "command_hash": metrics.command_hash,
                "duration_ms": str(metrics.duration_ms),
                "exit_code": str(metrics.exit_code),
                "timed_out": str(int(metrics.timed_out)),
                "files_touched_count": str(metrics.files_touched_count),
                "lines_added": str(metrics.lines_added),
                "lines_deleted": str(metrics.lines_deleted),
            },
        )
    event_id = store.insert_command_event(agent_id=agent, metrics=metrics, prediction=prediction)

    if event_id is None:
        console.print(
            "Skipped telemetry event: no file changes detected "
            "(files_touched_count=0, lines_added=0, lines_deleted=0)."
        )
        raise typer.Exit(code=metrics.exit_code)

    table = Table(title="Captured Metrics")
    table.add_column("field")
    table.add_column("value")
    table.add_row("event_id", event_id)
    table.add_row("command_hash", metrics.command_hash)
    table.add_row("duration_ms", str(metrics.duration_ms))
    table.add_row("exit_code", str(metrics.exit_code))
    table.add_row("timed_out", str(metrics.timed_out))
    table.add_row("files_touched_count", str(metrics.files_touched_count))
    table.add_row("lines_added", str(metrics.lines_added))
    table.add_row("lines_deleted", str(metrics.lines_deleted))
    if prediction is not None:
        table.add_row("predicted_productivity", f"{prediction.predicted_productivity:.4f}")
        table.add_row("top_contribution_feature", prediction.top_contribution_feature)
        table.add_row("top_contribution_value", f"{prediction.top_contribution_value:.4f}")
        table.add_row("model_ref", prediction.model_ref)
    console.print(table)

    raise typer.Exit(code=metrics.exit_code)


@app.command("events")
def events(
    path: Annotated[Path, typer.Option("--path", "-p", help="Storage directory")] = Path(".devtrace"),
    limit: Annotated[int | None, typer.Option("--limit", "-n", help="Limit number of rows")] = None,
) -> None:
    """List captured command events."""
    store = _store(path)
    rows = store.list_command_events(limit=limit)

    table = Table(title="Command Events")
    for column in [
        "id",
        "agent_id",
        "command_hash",
        "duration_ms",
        "exit_code",
        "timed_out",
        "files_touched_count",
        "lines_added",
        "lines_deleted",
        "predicted_productivity",
        "top_contribution_feature",
        "top_contribution_value",
        "model_ref",
    ]:
        table.add_column(column)

    for row in rows:
        table.add_row(
            str(row["id"]),
            str(row["agent_id"]),
            str(row["command_hash"]),
            str(row["duration_ms"]),
            str(row["exit_code"]),
            str(row["timed_out"]),
            str(row["files_touched_count"]),
            str(row["lines_added"]),
            str(row["lines_deleted"]),
            "" if row["predicted_productivity"] is None else f"{float(row['predicted_productivity']):.4f}",
            "" if row["top_contribution_feature"] is None else str(row["top_contribution_feature"]),
            "" if row["top_contribution_value"] is None else f"{float(row['top_contribution_value']):.4f}",
            "" if row["model_ref"] is None else str(row["model_ref"]),
        )
    console.print(table)


@app.command("export")
def export(
    out: Annotated[Path, typer.Option("--out", "-o", help="Output file path")],
    fmt: Annotated[str, typer.Option("--format", "-f", help="csv|parquet|jsonl")] = "csv",
    path: Annotated[Path, typer.Option("--path", "-p", help="Storage directory")] = Path(".devtrace"),
) -> None:
    """Export command dataset for modeling."""
    normalized = fmt.lower()
    if normalized not in {"csv", "parquet", "jsonl"}:
        raise typer.BadParameter("format must be csv, parquet, or jsonl")

    store = _store(path)
    count = store.export_events(output_path=out, fmt=normalized)
    console.print(f"Exported {count} rows to {out}")


@ml_app.command("generate")
def ml_generate(
    out: Annotated[Path, typer.Option("--out", "-o", help="Output CSV dataset path")],
    rows: Annotated[int, typer.Option("--rows", "-n", help="Number of synthetic rows")] = 10000,
    seed: Annotated[int, typer.Option("--seed", help="Random seed")] = 42,
) -> None:
    """Generate synthetic telemetry dataset with labels for XGBoost training."""
    count = generate_synthetic_dataset(output_path=out, rows=rows, seed=seed)
    console.print(f"Generated {count} synthetic rows at {out}")


@ml_app.command("train")
def ml_train(
    dataset: Annotated[Path, typer.Option("--dataset", "-d", help="Input CSV dataset")],
    out_dir: Annotated[Path, typer.Option("--out-dir", "-o", help="Model output dir")] = Path("model"),
    seed: Annotated[int, typer.Option("--seed", help="Random seed")] = 42,
    n_estimators: Annotated[int, typer.Option("--n-estimators", help="XGBoost trees")] = 280,
    max_depth: Annotated[int, typer.Option("--max-depth", help="XGBoost max tree depth")] = 5,
    learning_rate: Annotated[float, typer.Option("--learning-rate", help="XGBoost learning rate")] = 0.06,
) -> None:
    """Train an XGBoost regressor and write model + metadata."""
    metadata = train_xgboost(
        dataset_path=dataset,
        output_dir=out_dir,
        seed=seed,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
    )
    console.print(f"Trained model with {metadata['training_rows']} rows at {out_dir}")
    console.print(f"train_mae={metadata['train_mae']}")


@ml_app.command("score")
def ml_score(
    model_dir: Annotated[Path, typer.Option("--model-dir", "-m", help="Model directory")],
    dataset: Annotated[Path, typer.Option("--dataset", "-d", help="Input CSV dataset")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Output CSV predictions")],
) -> None:
    """Score a dataset with a trained model."""
    count = score_xgboost(model_dir=model_dir, dataset_path=dataset, output_path=out)
    console.print(f"Scored {count} rows into {out}")


app.add_typer(ml_app, name="ml")


if __name__ == "__main__":
    app()
