"""Placeholder routing logic.

Fill in ``select_project`` with your preferred agent or heuristic. The API will
surface ``NotImplementedError`` responses until this module is completed.
"""

from __future__ import annotations

from typing import List

from .ingest import ProjectPlan


def select_project(query: str, projects: List[ProjectPlan]) -> str:
    raise NotImplementedError("Project router not implemented.")
