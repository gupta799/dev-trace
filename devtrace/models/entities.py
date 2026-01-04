from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from devtrace.models.enums import EventType, SessionStatus


class Session(BaseModel):
    id: str
    created_at: float
    agent: Optional[str] = None
    label: Optional[str] = None
    status: SessionStatus = SessionStatus.ACTIVE
    meta: Dict[str, Any] = Field(default_factory=dict)


class Event(BaseModel):
    id: str
    session_id: str
    ts: float
    type: EventType
    payload: Dict[str, Any] = Field(default_factory=dict)
