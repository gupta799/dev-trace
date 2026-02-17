from __future__ import annotations

from pathlib import Path

from devtrace.storage import LocalStore
from devtrace.types import CommandMetrics


def test_insert_and_list_command_events(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / ".devtrace")
    store.ensure_storage()

    metrics = CommandMetrics(
        command_hash="abc",
        duration_ms=25,
        exit_code=0,
        timed_out=False,
        files_touched_count=1,
        lines_added=10,
        lines_deleted=2,
    )
    event_id = store.insert_command_event(agent_id="agent-1", metrics=metrics)

    rows = store.list_command_events()
    assert len(rows) == 1
    assert rows[0]["id"] == event_id
    assert rows[0]["command_hash"] == "abc"
    assert rows[0]["duration_ms"] == 25
    assert rows[0]["exit_code"] == 0
    assert rows[0]["timed_out"] is False


def test_export_csv_contains_minimal_columns(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / ".devtrace")
    store.ensure_storage()
    store.insert_command_event(
        agent_id=None,
        metrics=CommandMetrics(
            command_hash="xyz",
            duration_ms=40,
            exit_code=1,
            timed_out=True,
            files_touched_count=3,
            lines_added=4,
            lines_deleted=1,
        ),
    )

    output_path = tmp_path / "dataset.csv"
    count = store.export_events(output_path=output_path, fmt="csv")
    assert count == 1

    content = output_path.read_text(encoding="utf-8").splitlines()
    assert content[0] == (
        "command_hash,duration_ms,exit_code,timed_out,"
        "files_touched_count,lines_added,lines_deleted"
    )
    assert "xyz,40,1,1,3,4,1" in content[1]
