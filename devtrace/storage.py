from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from devtrace.models import Event, EventType, Session, SessionStatus
from devtrace.utils import new_id, now_ts, read_json, write_json


class LocalStore:
    """Local JSONL-backed storage plus in-memory caches."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.sessions_path = self.base_path / "sessions.jsonl"
        self.events_path = self.base_path / "events.jsonl"
        self.state_path = self.base_path / "state.json"
        self._sessions: Dict[str, Session] = {}
        self._events: List[Event] = []

    def ensure_storage(self) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)
        for path in (self.sessions_path, self.events_path, self.state_path):
            if not path.exists():
                if path.suffix == ".jsonl":
                    path.write_text("", encoding="utf-8")
                else:
                    write_json(path, {"current_session": None})
        self._load()

    def _load(self) -> None:
        if self.sessions_path.exists():
            with self.sessions_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        session = Session.model_validate_json(line)
                        self._sessions[session.id] = session
        if self.events_path.exists():
            with self.events_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        event = Event.model_validate_json(line)
                        self._events.append(event)

    def create_session(self, agent: Optional[str], label: Optional[str]) -> Session:
        session = Session(
            id=new_id("sess"),
            created_at=now_ts(),
            agent=agent,
            label=label,
            status=SessionStatus.ACTIVE,
        )
        self._sessions[session.id] = session
        self._append_jsonl(self.sessions_path, session.model_dump_json())
        self.set_current_session(session.id)
        return session

    def close_session(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"unknown session {session_id}")
        session.status = SessionStatus.CLOSED
        self._rewrite_sessions()
        state = read_json(self.state_path) or {}
        if state.get("current_session") == session_id:
            write_json(self.state_path, {"current_session": None})
        return session

    def current_session_id(self) -> Optional[str]:
        state = read_json(self.state_path) or {}
        return state.get("current_session")

    def set_current_session(self, session_id: Optional[str]) -> None:
        write_json(self.state_path, {"current_session": session_id})

    def record_event(self, session_id: str, event_type: EventType, payload: Dict[str, Any]) -> Event:
        if session_id not in self._sessions:
            raise ValueError(f"unknown session {session_id}")
        event = Event(id=new_id("evt"), session_id=session_id, ts=now_ts(), type=event_type, payload=payload)
        self._events.append(event)
        self._append_jsonl(self.events_path, event.model_dump_json())
        return event

    def list_sessions(self) -> Iterable[Session]:
        return list(self._sessions.values())

    def list_events(self, session_id: Optional[str] = None, limit: Optional[int] = None) -> List[Event]:
        events = [evt for evt in self._events if session_id is None or evt.session_id == session_id]
        if limit:
            return events[-limit:]
        return events

    def _rewrite_sessions(self) -> None:
        with self.sessions_path.open("w", encoding="utf-8") as handle:
            for session in self._sessions.values():
                handle.write(session.model_dump_json() + "\n")

    def _append_jsonl(self, path: Path, line: str) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
