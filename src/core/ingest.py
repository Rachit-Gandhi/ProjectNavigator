"""Utilities for discovering and preparing project documents for ingestion.

Phase 2 focuses on deterministic metadata generation so downstream agents
(router, RAG) can remain simple. Heavy lifting such as actual embedding or
vector-store writes can build on the structures defined here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set

import yaml

DescriptionProvider = Callable[[Path], str]


@dataclass
class IngestionRule:
    """Match a filename (glob) and attach a tag."""

    match: str
    tag: str


@dataclass
class IngestionRules:
    patterns: List[IngestionRule] = field(default_factory=list)
    forced: Dict[str, Set[str]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> "IngestionRules":
        patterns = [
            IngestionRule(match=str(item["match"]), tag=str(item["tag"]))
            for item in data.get("patterns", [])
            if "match" in item and "tag" in item
        ]
        forced_map: Dict[str, Set[str]] = {}
        for entry in data.get("forced", []) or []:
            path = entry.get("path")
            tag = entry.get("tag")
            if not (path and tag):
                continue
            normalized = _normalize_rel_path(path)
            forced_map.setdefault(normalized, set()).add(str(tag))
        return cls(patterns=patterns, forced=forced_map)


@dataclass
class FileRecord:
    """Represents a candidate file for ingestion along with tags."""

    absolute_path: Path
    relative_path: str
    tags: Set[str] = field(default_factory=set)


@dataclass
class ProjectPlan:
    project_id: str
    root: Path
    description: str
    files: List[FileRecord] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.files)


def load_rules(config_path: Path) -> IngestionRules:
    if not config_path.exists():
        raise FileNotFoundError(f"Ingestion config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return IngestionRules.from_dict(data)


def discover_projects(data_root: Path) -> List[Path]:
    if not data_root.exists():
        raise FileNotFoundError(f"Data directory not found: {data_root}")
    return [p for p in data_root.iterdir() if p.is_dir() and not p.name.startswith(".")]


def ensure_description(
    project_dir: Path,
    provider: Optional[DescriptionProvider] = None,
    *,
    filename: str = "description.txt",
) -> str:
    """Read or create the project description.

    If the description file does not exist and a provider is supplied, the
    provider will be called to obtain text which is then persisted.
    """

    description_file = project_dir / filename
    if description_file.exists():
        return description_file.read_text(encoding="utf-8").strip()
    if provider is None:
        raise FileNotFoundError(
            f"Missing {filename} for project '{project_dir.name}'. Provide a description "
            "via the ingestion API or create the file manually."
        )
    generated = provider(project_dir).strip()
    if not generated:
        raise ValueError("Description provider returned empty text")
    description_file.write_text(generated, encoding="utf-8")
    return generated


def plan_project(
    project_dir: Path,
    rules: IngestionRules,
    description_provider: Optional[DescriptionProvider] = None,
) -> ProjectPlan:
    description = ensure_description(project_dir, provider=description_provider)
    files: List[FileRecord] = []
    for file_path in _iter_files(project_dir):
        rel_path = file_path.relative_to(project_dir).as_posix()
        tags = _collect_tags(rel_path, rules)
        files.append(
            FileRecord(absolute_path=file_path, relative_path=rel_path, tags=tags)
        )
    return ProjectPlan(
        project_id=project_dir.name,
        root=project_dir,
        description=description,
        files=files,
    )


def plan_all_projects(
    data_root: Path,
    rules: IngestionRules,
    description_provider: Optional[DescriptionProvider] = None,
    selected_projects: Optional[Sequence[str]] = None,
) -> List[ProjectPlan]:
    """Plan ingestion for every project under ``data_root``.

    Args:
        data_root: Directory containing project subfolders.
        rules: Tagging rules.
        description_provider: Optional callback for missing descriptions.
        selected_projects: Optional subset to limit processing.
    """

    projects = discover_projects(data_root)
    subset = {name for name in (selected_projects or [])}
    plans: List[ProjectPlan] = []
    for project_dir in projects:
        if subset and project_dir.name not in subset:
            continue
        plans.append(plan_project(project_dir, rules, description_provider))
    return plans


def _iter_files(project_dir: Path) -> Iterable[Path]:
    for path in project_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.name.lower() in {"description.txt", "readme.md"}:
            continue
        yield path


def _collect_tags(relative_path: str, rules: IngestionRules) -> Set[str]:
    tags: Set[str] = set()
    lowered = relative_path.lower()
    for pattern in rules.patterns:
        if fnmatch(lowered, pattern.match.lower()):
            tags.add(pattern.tag)
    forced_tags = rules.forced.get(_normalize_rel_path(relative_path))
    if forced_tags:
        tags.update(forced_tags)
    return tags


def _normalize_rel_path(rel_path: str) -> str:
    return rel_path.replace("\\", "/").strip().lower()


__all__ = [
    "DescriptionProvider",
    "FileRecord",
    "IngestionRule",
    "IngestionRules",
    "ProjectPlan",
    "discover_projects",
    "ensure_description",
    "load_rules",
    "plan_all_projects",
    "plan_project",
]
