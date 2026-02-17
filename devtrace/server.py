from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class TelemetryBatch(BaseModel):
    """Ingest request payload for telemetry batches."""

    events: list[dict[str, Any]] = Field(default_factory=list)


class CentralStore:
    """Simple SQLite-backed storage for ingested telemetry events."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def ensure_storage(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingested_events (
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

    def insert_batch(self, events: list[dict[str, Any]]) -> int:
        accepted = 0
        with self._connect() as conn:
            for event in events:
                if not self._is_valid_event(event):
                    continue
                conn.execute(
                    """
                    INSERT OR IGNORE INTO ingested_events (
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
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event["id"],
                        event.get("agent_id"),
                        float(event["executed_at"]),
                        str(event["command_hash"]),
                        int(event["duration_ms"]),
                        int(event["exit_code"]),
                        int(bool(event["timed_out"])),
                        int(event["files_touched_count"]),
                        int(event["lines_added"]),
                        int(event["lines_deleted"]),
                    ),
                )
                accepted += 1
            conn.commit()
        return accepted

    def _is_valid_event(self, event: dict[str, Any]) -> bool:
        required = [
            "id",
            "executed_at",
            "command_hash",
            "duration_ms",
            "exit_code",
            "timed_out",
            "files_touched_count",
            "lines_added",
            "lines_deleted",
        ]
        return all(key in event for key in required)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)


def create_app(db_path: Path) -> Any:
    """Create FastAPI app for telemetry ingestion."""
    import fastapi

    store = CentralStore(db_path)
    store.ensure_storage()
    app = fastapi.FastAPI(title="DevTrace Ingestion API", version="0.1.0")

    @app.get("/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/telemetry/batch")
    def ingest(batch: TelemetryBatch) -> dict[str, int]:
        accepted = store.insert_batch(batch.events)
        return {"accepted": accepted}

    @app.get("/v1/model/active")
    def model_active() -> dict[str, Any]:
        return {
            "model_version": None,
            "message": "no active model registered",
        }

    return app
