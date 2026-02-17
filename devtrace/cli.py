from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from devtrace.runner import run_command
from devtrace.storage import LocalStore

app = typer.Typer(help="DevTrace CLI")
console = Console()


def _store(path: Path) -> LocalStore:
    store = LocalStore(path)
    store.ensure_storage()
    return store


@app.command()
def init(path: Path = typer.Option(Path(".devtrace"), "--path", "-p")) -> None:
    """Initialize local storage."""
    store = _store(path)
    console.print(f"Initialized DevTrace at {store.db_path}")


@app.command("run")
def run_cmd(
    command: list[str] = typer.Argument(..., help="Command to execute (pass with -- separator)"),
    agent: str | None = typer.Option(None, "--agent", "-a", help="Agent id"),
    timeout: float | None = typer.Option(None, "--timeout", help="Timeout in seconds"),
    path: Path = typer.Option(Path(".devtrace"), "--path", "-p", help="Storage directory"),
    repo: Path = typer.Option(Path("."), "--repo", "-r", help="Repository path"),
) -> None:
    """Run a command and capture minimal telemetry metrics."""
    if not command:
        raise typer.BadParameter("command is required")

    store = _store(path)
    metrics = run_command(command=command, repo_path=repo, timeout_s=timeout)
    event_id = store.insert_command_event(agent_id=agent, metrics=metrics)

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
    console.print(table)

    raise typer.Exit(code=metrics.exit_code)


@app.command("events")
def events(
    path: Path = typer.Option(Path(".devtrace"), "--path", "-p", help="Storage directory"),
    limit: int | None = typer.Option(None, "--limit", "-n", help="Limit number of rows"),
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
        )
    console.print(table)


@app.command("export")
def export(
    out: Path = typer.Option(..., "--out", "-o", help="Output file path"),
    fmt: str = typer.Option("csv", "--format", "-f", help="csv|parquet|jsonl"),
    path: Path = typer.Option(Path(".devtrace"), "--path", "-p", help="Storage directory"),
) -> None:
    """Export command dataset for modeling."""
    normalized = fmt.lower()
    if normalized not in {"csv", "parquet", "jsonl"}:
        raise typer.BadParameter("format must be csv, parquet, or jsonl")

    store = _store(path)
    count = store.export_events(output_path=out, fmt=normalized)
    console.print(f"Exported {count} rows to {out}")


if __name__ == "__main__":
    app()
