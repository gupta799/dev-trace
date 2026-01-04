from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from devtrace.models import EventType
from devtrace.storage import LocalStore

app = typer.Typer(help="DevTrace CLI: local-first provenance tracker.")
console = Console()


def _store(base_dir: Path) -> LocalStore:
    store = LocalStore(base_dir)
    store.ensure_storage()
    return store


@app.command()
def init(path: Path = typer.Option(Path(".devtrace"), "--path", "-p", help="Storage directory")) -> None:
    """Initialize local storage under the given path."""
    store = _store(path)
    console.print(f"Initialized DevTrace storage at {store.base_path}")


@app.command("session-start")
def session_start(
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent or user name"),
    label: Optional[str] = typer.Option(None, "--label", "-l", help="Human-friendly label"),
    path: Path = typer.Option(Path(".devtrace"), "--path", "-p", help="Storage directory"),
) -> None:
    """Start a new session and set it as current."""
    store = _store(path)
    session = store.create_session(agent=agent, label=label)
    console.print(f"Started session [bold]{session.id}[/bold] (agent={session.agent}, label={session.label})")


@app.command("session-close")
def session_close(
    session_id: Optional[str] = typer.Option(None, "--session-id", "-s", help="Session to close"),
    path: Path = typer.Option(Path(".devtrace"), "--path", "-p", help="Storage directory"),
) -> None:
    """Close a session."""
    store = _store(path)
    current = session_id or store.current_session_id()
    if not current:
        raise typer.BadParameter("No session id provided and no current session set.")
    session = store.close_session(current)
    console.print(f"Closed session {session.id}")


@app.command()
def note(
    text: str = typer.Argument(..., help="Note content"),
    session_id: Optional[str] = typer.Option(None, "--session-id", "-s", help="Attach to specific session"),
    path: Path = typer.Option(Path(".devtrace"), "--path", "-p", help="Storage directory"),
) -> None:
    """Record a freeform note event."""
    store = _store(path)
    sid = session_id or store.current_session_id()
    if not sid:
        raise typer.BadParameter("No session id provided and no current session set.")
    event = store.record_event(sid, EventType.NOTE, {"text": text})
    console.print(f"Note recorded as event {event.id} in session {sid}")


@app.command("events")
def list_events(
    session_id: Optional[str] = typer.Option(None, "--session-id", "-s", help="Filter by session"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Limit number of events"),
    path: Path = typer.Option(Path(".devtrace"), "--path", "-p", help="Storage directory"),
) -> None:
    """List recorded events."""
    store = _store(path)
    events = store.list_events(session_id=session_id, limit=limit)
    table = Table(title="Events")
    table.add_column("id")
    table.add_column("session")
    table.add_column("type")
    table.add_column("ts")
    table.add_column("payload")
    for evt in events:
        table.add_row(evt.id, evt.session_id, evt.type.value, f"{evt.ts:.3f}", json.dumps(evt.payload))
    console.print(table)


@app.command("sessions")
def list_sessions(
    path: Path = typer.Option(Path(".devtrace"), "--path", "-p", help="Storage directory"),
) -> None:
    """List sessions."""
    store = _store(path)
    table = Table(title="Sessions")
    table.add_column("id")
    table.add_column("agent")
    table.add_column("label")
    table.add_column("status")
    table.add_column("created")
    for sess in store.list_sessions():
        table.add_row(sess.id, str(sess.agent), str(sess.label), sess.status.value, f"{sess.created_at:.3f}")
    console.print(table)


if __name__ == "__main__":
    app()
