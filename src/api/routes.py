"""HTTP surface for the Controlled RAG backend."""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.api.session import (
    SessionStore,
    apply_command,
    identify_command,
)

app = FastAPI(title="Controlled RAG", version="0.1.0")
sessions = SessionStore()


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    response: str


@app.post("/v1/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    raw_message = payload.message.strip()
    if not raw_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    command = identify_command(raw_message)
    if command:
        try:
            response_text = apply_command(sessions, payload.session_id, command)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ChatResponse(
            session_id=payload.session_id,
            response=response_text,
        )

    state = sessions.get(payload.session_id)
    state.append("user", raw_message)

    # Static response placeholder
    answer = "Logic cleaned. Backend is ready for new implementation."

    state.append("assistant", answer)
    return ChatResponse(
        session_id=payload.session_id,
        response=answer,
    )


__all__ = ["app"]
