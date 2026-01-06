"""HTTP surface for the Controlled RAG backend."""

from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.api.session import (
    SessionStore,
    apply_command,
    extract_filters,
    identify_command,
)
from src.core import ingest, rag, router

app = FastAPI(title="Controlled RAG", version="0.1.0")
sessions = SessionStore()


class ProjectRegistry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._projects: Dict[str, ingest.ProjectPlan] = {}

    def update(self, plans: List[ingest.ProjectPlan]) -> None:
        with self._lock:
            for plan in plans:
                self._projects[plan.project_id] = plan

    def get(self, project_id: str) -> Optional[ingest.ProjectPlan]:
        with self._lock:
            return self._projects.get(project_id)

    def list(self) -> List[ingest.ProjectPlan]:
        with self._lock:
            return list(self._projects.values())


registry = ProjectRegistry()


class IngestRequest(BaseModel):
    data_path: str = Field(
        default="data", description="Root directory containing project folders"
    )
    projects: Optional[List[str]] = Field(
        default=None, description="Subset of projects to ingest"
    )
    ensure_descriptions: bool = Field(
        default=False,
        description="Create missing description.txt files using provided text",
    )
    descriptions: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional mapping of project_id -> description text",
    )


class FilePreview(BaseModel):
    path: str
    tags: List[str]


class ProjectPreview(BaseModel):
    project_id: str
    description: str
    file_count: int
    files: List[FilePreview]


class IngestResponse(BaseModel):
    projects: List[ProjectPreview]


class LockRequest(BaseModel):
    session_id: str
    project_id: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    project_id: Optional[str] = Field(
        default=None, description="Explicitly lock session to this project"
    )
    auto_lock: bool = Field(
        default=False,
        description="Use router to lock the session when project is missing",
    )


class ChatResponse(BaseModel):
    session_id: str
    project_id: Optional[str]
    filters: List[str]
    response: str


@app.post("/v1/ingest", response_model=IngestResponse)
def ingest_projects(payload: IngestRequest) -> IngestResponse:
    data_root = Path(payload.data_path).resolve()
    rules = ingest.load_rules(Path("config/ingestion_rules.yaml"))
    provider = (
        _build_description_provider(payload) if payload.ensure_descriptions else None
    )
    try:
        plans = ingest.plan_all_projects(
            data_root=data_root,
            rules=rules,
            description_provider=provider,
            selected_projects=payload.projects,
        )
    except (FileNotFoundError, MissingDescriptionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not plans:
        raise HTTPException(status_code=404, detail="No projects discovered")
    registry.update(plans)
    project_payloads = [
        ProjectPreview(
            project_id=plan.project_id,
            description=plan.description,
            file_count=plan.file_count,
            files=[
                FilePreview(path=record.relative_path, tags=sorted(record.tags))
                for record in plan.files
            ],
        )
        for plan in plans
    ]
    return IngestResponse(projects=project_payloads)


@app.post("/v1/session/lock", response_model=ChatResponse)
def lock_session(payload: LockRequest) -> ChatResponse:
    state = sessions.set_project(payload.session_id, payload.project_id)
    return ChatResponse(
        session_id=state.session_id,
        project_id=state.project_lock,
        filters=[],
        response=f"Session locked to {payload.project_id}",
    )


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
            project_id=None,
            filters=[],
            response=response_text,
        )

    cleaned_message, filters = extract_filters(raw_message)
    if not cleaned_message:
        raise HTTPException(
            status_code=400, detail="Message cannot be empty after removing filters"
        )

    state = sessions.get(payload.session_id)

    project_id = payload.project_id or state.project_lock
    if project_id is None:
        if payload.auto_lock:
            project_id = _auto_lock_project(cleaned_message)
            sessions.set_project(payload.session_id, project_id)
        else:
            raise HTTPException(
                status_code=409, detail="Session is not locked to a project"
            )
    elif payload.project_id:
        sessions.set_project(payload.session_id, payload.project_id)

    state.append("user", cleaned_message, filters=filters)

    try:
        answer = rag.generate_answer(
            session_id=payload.session_id,
            project_id=project_id,
            message=cleaned_message,
            filters=filters or None,
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc

    state.append("assistant", answer, filters=filters)
    return ChatResponse(
        session_id=payload.session_id,
        project_id=project_id,
        filters=filters,
        response=answer,
    )


def _build_description_provider(payload: IngestRequest):
    descriptions = {k: v for k, v in (payload.descriptions or {}).items() if v}

    def provider(project_dir: Path) -> str:
        if project_dir.name in descriptions:
            return descriptions[project_dir.name]
        raise MissingDescriptionError(
            f"Missing description for project '{project_dir.name}'. Provide text via the API."
        )

    return provider


def _auto_lock_project(query: str) -> str:
    projects = registry.list()
    if not projects:
        raise HTTPException(status_code=404, detail="No projects available for routing")
    try:
        return router.select_project(query, projects)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


class MissingDescriptionError(RuntimeError):
    """Raised when a description.txt cannot be created automatically."""


__all__ = ["app"]
