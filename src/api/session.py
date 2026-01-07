"""Session handling and inline command parsing for the chat API."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Dict, List, Optional
import re

COMMAND_CLEAR = "clear"

_COMMAND_PATTERN = re.compile(r"^/(\w+)")


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class SessionState:
    session_id: str
    history: List[ChatMessage] = field(default_factory=list)

    def append(self, role: str, content: str) -> None:
        self.history.append(ChatMessage(role=role, content=content))


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
    "identify_command",
]
