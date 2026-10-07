from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auris.coding_agent import validate_project_root
from auris.database import get_project, list_projects
from auris.device_agent import DeviceAction


@dataclass(frozen=True)
class ProjectOpenRequest:
    requested_name: str | None
    use_selected_project: bool


def match_project_open_command(command: str) -> ProjectOpenRequest | None:
    text = _normalise(command)
    if text in {
        "open current project",
        "open my current project",
        "open selected project",
        "open the selected project",
        "open this project",
    }:
        return ProjectOpenRequest(None, True)
    match = re.fullmatch(r"open\s+(?:my\s+|the\s+)?(.+?)\s+project", text)
    if not match:
        return None
    requested = match.group(1).strip()
    return ProjectOpenRequest(requested, False) if requested else None


def resolve_project_open_action(
    request: ProjectOpenRequest,
    *,
    selected_project_id: str | None,
    projects: list[dict[str, Any]] | None = None,
) -> tuple[DeviceAction | None, dict[str, Any] | None, str | None]:
    available = projects if projects is not None else list_projects()
    if request.use_selected_project:
        project = get_project(selected_project_id) if projects is None else next(
            (item for item in available if item.get("project_id") == selected_project_id), None
        )
    else:
        project = _match_project(request.requested_name or "", available)
    if project is None:
        return None, None, "I could not resolve that name to one AURIS project."
    configured_root = str(project.get("root_path") or "").strip()
    if not configured_root:
        return (
            None,
            project,
            f"{project.get('name', 'That project')} does not have a registered local root.",
        )
    try:
        root = validate_project_root(configured_root)
    except ValueError as error:
        return None, project, str(error)
    if len(str(root)) > 200:
        return None, project, "The registered project path exceeds the signed device-target limit."
    project_name = str(project.get("name") or project.get("project_id") or root.name)
    slug = re.sub(r"[^a-z0-9]+", "_", str(project.get("project_id") or project_name).casefold()).strip("_")
    return (
        DeviceAction(
            action_id=f"open_project_{slug}"[:120],
            kind="open_folder",
            label=f"Open {project_name} project",
            target=str(root),
            path=root,
            source="registered_project",
        ),
        project,
        None,
    )


def _match_project(requested: str, projects: list[dict[str, Any]]) -> dict[str, Any] | None:
    needle = _project_key(requested)
    if not needle:
        return None
    exact = [
        project
        for project in projects
        if needle
        in {
            _project_key(str(project.get("project_id") or "")),
            _project_key(str(project.get("name") or "")),
        }
    ]
    if len(exact) == 1:
        return exact[0]
    needle_tokens = set(needle.split())
    partial = []
    for project in projects:
        candidates = {
            _project_key(str(project.get("project_id") or "")),
            _project_key(str(project.get("name") or "")),
        }
        if any(needle_tokens and needle_tokens <= set(candidate.split()) for candidate in candidates):
            partial.append(project)
    return partial[0] if len(partial) == 1 else None


def _project_key(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _normalise(command: str) -> str:
    text = " ".join(command.casefold().strip().replace(",", " ").split())
    for prefix in ("hey auris ", "auris "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.strip(" .")
