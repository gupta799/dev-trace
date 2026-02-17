from __future__ import annotations

import sqlite3
from pathlib import Path

from devtrace.storage import LocalStore
from devtrace.types import CommandMetrics, ModelPrediction


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


def test_insert_skips_zero_diff_snapshot(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / ".devtrace")
    store.ensure_storage()

    event_id = store.insert_command_event(
        agent_id="agent-1",
        metrics=CommandMetrics(
            command_hash="noop",
            duration_ms=5,
            exit_code=0,
            timed_out=False,
            files_touched_count=0,
            lines_added=0,
            lines_deleted=0,
        ),
    )

    assert event_id is None
    assert store.list_command_events() == []


def test_insert_and_list_with_prediction_fields(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / ".devtrace")
    store.ensure_storage()

    event_id = store.insert_command_event(
        agent_id="agent-1",
        metrics=CommandMetrics(
            command_hash="pred123",
            duration_ms=111,
            exit_code=0,
            timed_out=False,
            files_touched_count=2,
            lines_added=20,
            lines_deleted=4,
        ),
        prediction=ModelPrediction(
            predicted_productivity=88.42,
            top_contribution_feature="exit_code",
            top_contribution_value=14.03,
            model_ref=".devtrace/model-xgb",
        ),
    )

    rows = store.list_command_events()
    assert len(rows) == 1
    assert rows[0]["id"] == event_id
    assert rows[0]["predicted_productivity"] == 88.42
    assert rows[0]["top_contribution_feature"] == "exit_code"
    assert rows[0]["top_contribution_value"] == 14.03
    assert rows[0]["model_ref"] == ".devtrace/model-xgb"


def test_ensure_storage_migrates_existing_command_events_table(tmp_path: Path) -> None:
    base_path = tmp_path / ".devtrace"
    base_path.mkdir(parents=True, exist_ok=True)
    db_path = base_path / "devtrace.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE command_events (
                id TEXT PRIMARY KEY,
                agent_id TEXT,
                executed_at REAL NOT NULL,
                command_hash TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                exit_code INTEGER NOT NULL,
                timed_out INTEGER NOT NULL,
                files_touched_count INTEGER NOT NULL,
                lines_added INTEGER NOT NULL,
                lines_deleted INTEGER NOT NULL
            )
            """
        )
        conn.commit()

    store = LocalStore(base_path)
    store.ensure_storage()

    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(command_events)").fetchall()
        }

    assert "predicted_productivity" in columns
    assert "top_contribution_feature" in columns
    assert "top_contribution_value" in columns
    assert "model_ref" in columns
