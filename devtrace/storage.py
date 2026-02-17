from __future__ import annotations

import csv
import importlib.util
import json
import sqlite3
from pathlib import Path
from typing import Any

from devtrace.types import CommandMetrics
from devtrace.utils import new_id, now_ts


class LocalStore:
    """SQLite-backed local storage for command telemetry."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.db_path = base_path / "devtrace.db"

    def ensure_storage(self) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS command_events (
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_queue (
                    event_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_attempt_at REAL,
                    last_error TEXT,
                    FOREIGN KEY (event_id) REFERENCES command_events(id)
                )
                """
            )
            conn.commit()

    def insert_command_event(self, agent_id: str | None, metrics: CommandMetrics) -> str | None:
        if (
            metrics.files_touched_count == 0
            and metrics.lines_added == 0
            and metrics.lines_deleted == 0
        ):
            return None

        event_id = new_id("evt")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO command_events (
                    id, agent_id, executed_at, command_hash, duration_ms, exit_code, timed_out,
                    files_touched_count, lines_added, lines_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    agent_id,
                    now_ts(),
                    metrics.command_hash,
                    metrics.duration_ms,
                    metrics.exit_code,
                    int(metrics.timed_out),
                    metrics.files_touched_count,
                    metrics.lines_added,
                    metrics.lines_deleted,
                ),
            )
            conn.execute("INSERT INTO sync_queue (event_id, status) VALUES (?, 'pending')", (event_id,))
            conn.commit()
        return event_id

    def list_command_events(self, limit: int | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT
                id,
                agent_id,
                executed_at,
                command_hash,
                duration_ms,
                exit_code,
                timed_out,
                files_touched_count,
                lines_added,
                lines_deleted
            FROM command_events
            ORDER BY executed_at ASC
        """
        params: tuple[Any, ...] = ()
        if limit is not None:
            query += " LIMIT ?"
            params = (limit,)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        keys = [
            "id",
            "agent_id",
            "executed_at",
            "command_hash",
            "duration_ms",
            "exit_code",
            "timed_out",
            "files_touched_count",
            "lines_added",
            "lines_deleted",
        ]
        result: list[dict[str, Any]] = []
        for row in rows:
            record = dict(zip(keys, row, strict=True))
            record["timed_out"] = bool(record["timed_out"])
            result.append(record)
        return result

    def export_events(self, output_path: Path, fmt: str) -> int:
        rows = self.list_command_events()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "csv":
            with output_path.open("w", encoding="utf-8", newline="") as handle:
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
                for row in rows:
                    writer.writerow(
                        {
                            "command_hash": row["command_hash"],
                            "duration_ms": row["duration_ms"],
                            "exit_code": row["exit_code"],
                            "timed_out": int(row["timed_out"]),
                            "files_touched_count": row["files_touched_count"],
                            "lines_added": row["lines_added"],
                            "lines_deleted": row["lines_deleted"],
                        }
                    )
            return len(rows)

        if fmt == "parquet":
            if importlib.util.find_spec("pandas") is None or importlib.util.find_spec("pyarrow") is None:
                raise RuntimeError("parquet export requires pandas and pyarrow")
            import pandas as pd

            payload = [
                {
                    "command_hash": row["command_hash"],
                    "duration_ms": row["duration_ms"],
                    "exit_code": row["exit_code"],
                    "timed_out": int(row["timed_out"]),
                    "files_touched_count": row["files_touched_count"],
                    "lines_added": row["lines_added"],
                    "lines_deleted": row["lines_deleted"],
                }
                for row in rows
            ]
            frame = pd.DataFrame(payload)
            frame.to_parquet(output_path, index=False)
            return len(rows)

        if fmt == "jsonl":
            with output_path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    payload = {
                        "command_hash": row["command_hash"],
                        "duration_ms": row["duration_ms"],
                        "exit_code": row["exit_code"],
                        "timed_out": int(row["timed_out"]),
                        "files_touched_count": row["files_touched_count"],
                        "lines_added": row["lines_added"],
                        "lines_deleted": row["lines_deleted"],
                    }
                    handle.write(json.dumps(payload) + "\n")
            return len(rows)

        raise ValueError(f"unsupported format: {fmt}")

    def pending_sync_events(self, batch_size: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    ce.id,
                    ce.agent_id,
                    ce.executed_at,
                    ce.command_hash,
                    ce.duration_ms,
                    ce.exit_code,
                    ce.timed_out,
                    ce.files_touched_count,
                    ce.lines_added,
                    ce.lines_deleted,
                    sq.attempts
                FROM command_events ce
                JOIN sync_queue sq ON sq.event_id = ce.id
                WHERE sq.status = 'pending'
                ORDER BY ce.executed_at ASC
                LIMIT ?
                """,
                (batch_size,),
            ).fetchall()

        result = []
        for row in rows:
            result.append(
                {
                    "id": row[0],
                    "agent_id": row[1],
                    "executed_at": row[2],
                    "command_hash": row[3],
                    "duration_ms": row[4],
                    "exit_code": row[5],
                    "timed_out": bool(row[6]),
                    "files_touched_count": row[7],
                    "lines_added": row[8],
                    "lines_deleted": row[9],
                    "attempts": row[10],
                }
            )
        return result

    def mark_synced(self, event_ids: list[str]) -> None:
        if not event_ids:
            return
        with self._connect() as conn:
            conn.executemany(
                "UPDATE sync_queue SET status = 'synced', last_attempt_at = ? WHERE event_id = ?",
                [(now_ts(), event_id) for event_id in event_ids],
            )
            conn.commit()

    def mark_sync_failed(self, event_ids: list[str], error: str) -> None:
        if not event_ids:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                UPDATE sync_queue
                SET attempts = attempts + 1,
                    last_attempt_at = ?,
                    last_error = ?
                WHERE event_id = ?
                """,
                [(now_ts(), error[:500], event_id) for event_id in event_ids],
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)
