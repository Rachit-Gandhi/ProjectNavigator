"""Session handling and inline command parsing for the chat API."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Dict, List, Optional, Tuple
import re

COMMAND_CLEAR = "clear"

_TAG_PATTERN = re.compile(r"@([A-Za-z0-9_\-]+)")
_COMMAND_PATTERN = re.compile(r"^/(\w+)")


@dataclass
class ChatMessage:
    role: str
    content: str
    filters: Optional[List[str]] = None


@dataclass
class SessionState:
    session_id: str
    project_lock: Optional[str] = None
    history: List[ChatMessage] = field(default_factory=list)

    def append(
        self, role: str, content: str, filters: Optional[List[str]] = None
    ) -> None:
        self.history.append(ChatMessage(role=role, content=content, filters=filters))


class SessionStore:
    """In-memory session registry with minimal locking."""

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionState] = {}
        self._lock = RLock()

    def get(self, session_id: str) -> SessionState:
        with self._lock:
            return self._sessions.setdefault(
                session_id, SessionState(session_id=session_id)
            )

    def clear(self, session_id: str) -> SessionState:
        with self._lock:
            state = SessionState(session_id=session_id)
            self._sessions[session_id] = state
            return state

    def set_project(self, session_id: str, project_id: Optional[str]) -> SessionState:
        state = self.get(session_id)
        state.project_lock = project_id
        return state


def extract_filters(message: str) -> Tuple[str, List[str]]:
    """Return the cleaned message plus any ``@tag`` filters."""

    matches = _TAG_PATTERN.findall(message)
    cleaned = _TAG_PATTERN.sub("", message).strip()
    return cleaned, [tag.lower() for tag in matches]


def identify_command(message: str) -> Optional[str]:
    match = _COMMAND_PATTERN.match(message.strip())
    if not match:
        return None
    return match.group(1).lower()


def apply_command(store: SessionStore, session_id: str, command: str) -> str:
    """Execute a recognized slash command."""

    if command == COMMAND_CLEAR:
        store.clear(session_id)
        return "Session cleared."
    raise ValueError(f"Unsupported command: /{command}")


__all__ = [
    "ChatMessage",
    "SessionState",
    "SessionStore",
    "apply_command",
    "extract_filters",
    "identify_command",
]
