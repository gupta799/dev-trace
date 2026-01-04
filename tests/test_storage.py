from pathlib import Path

from devtrace.models import EventType, SessionStatus
from devtrace.storage import LocalStore


def test_create_session_and_note(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / ".devtrace")
    store.ensure_storage()

    session = store.create_session(agent="tester", label="demo")
    assert session.status == SessionStatus.ACTIVE
    assert store.current_session_id() == session.id

    event = store.record_event(session.id, EventType.NOTE, {"text": "hello"})
    assert event.payload["text"] == "hello"

    events = store.list_events(session_id=session.id)
    assert len(events) == 1
    assert events[0].id == event.id


def test_close_session_clears_current(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / ".devtrace")
    store.ensure_storage()
    session = store.create_session(agent=None, label=None)

    store.close_session(session.id)
    assert store.current_session_id() is None
    sessions = list(store.list_sessions())
    assert sessions[0].status == SessionStatus.CLOSED
