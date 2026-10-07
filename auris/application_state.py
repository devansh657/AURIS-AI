from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from auris.browser_agent import BrowserAction, BrowserStep
from auris.database import (
    DATABASE_PATH,
    get_application_state,
    get_task,
    list_application_states,
    save_application_state,
)


SHOW_PATTERNS = (
    r"(?:show|describe) (?:the )?(?:active|current|last) browser mission",
    r"where did (?:the )?browser mission stop",
    r"what(?:'s| is) (?:the )?(?:active|current) browser mission(?: state)?",
)
CONTINUE_PATTERNS = (
    r"continue",
    r"continue (?:the )?browser mission",
    r"resume (?:the )?browser mission",
    r"retry (?:the )?(?:failed )?browser mission",
)


def match_application_state_command(command: str) -> str | None:
    text = _normalise(command)
    if any(re.fullmatch(pattern, text, flags=re.IGNORECASE) for pattern in SHOW_PATTERNS):
        return "show"
    if any(re.fullmatch(pattern, text, flags=re.IGNORECASE) for pattern in CONTINUE_PATTERNS):
        return "continue"
    return None


def record_browser_application_state(
    task_id: str,
    project_id: str | None,
    action: BrowserAction,
    outcome: dict[str, Any],
    *,
    path=DATABASE_PATH,
) -> dict[str, Any] | None:
    if action.kind != "workflow" or not action.steps:
        return None
    if get_task(task_id, path=path) is None:
        return None
    completed_count = max(0, min(int(outcome.get("completed_steps") or 0), len(action.steps)))
    failed_step = outcome.get("failed_step")
    failed_index = int(failed_step) if isinstance(failed_step, int) else None
    safe_to_retry = bool(not outcome.get("ok") and failed_index and failed_index < len(action.steps))
    status = "completed" if outcome.get("ok") else "resumable" if safe_to_retry else "manual_review"
    public_steps = [_step_summary(step, index) for index, step in enumerate(action.steps, start=1)]
    page = outcome.get("page") or {}
    return save_application_state(
        {
            "state_id": str(uuid4()),
            "task_id": task_id,
            "project_id": project_id,
            "application": "Microsoft Edge",
            "workflow_type": "browser_mission",
            "status": status,
            "completed": public_steps[:completed_count],
            "remaining": public_steps[completed_count:],
            "checkpoint": {
                "failed_step": failed_index,
                "completed_steps": completed_count,
                "total_steps": len(action.steps),
                "safe_to_retry": safe_to_retry,
                "page": {
                    "url": str(page.get("url") or "")[:1000],
                    "title": str(page.get("title") or "")[:200],
                    "body_digest": str(page.get("body_digest") or "")[:128],
                    "content_trust": "untrusted_web_content",
                },
            },
        },
        path=path,
    )


def application_state_dashboard(
    project_id: str | None, *, path=DATABASE_PATH
) -> dict[str, Any]:
    states = (
        list_application_states(project_id=project_id, limit=20, path=path)
        if project_id is not None
        else []
    )
    active = next((state for state in states if state["status"] in {"resumable", "manual_review"}), None)
    return {
        "active": active,
        "states": states,
        "policy": {
            "automatic_resume": False,
            "replay_after_uncertain_final_control": False,
            "approval_required": True,
        },
    }


def resolve_browser_continuation(
    project_id: str | None, *, state_id: str | None = None, path=DATABASE_PATH
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    if project_id is None:
        return None, None, "No project-scoped browser checkpoint is available."
    if state_id:
        state = get_application_state(state_id, path=path)
        candidates = [state] if state else []
    else:
        candidates = list_application_states(
            project_id=project_id, statuses=("resumable", "manual_review"), limit=20, path=path
        )
    state = next((item for item in candidates if item and item.get("project_id") == project_id), None)
    if state is None:
        return None, None, "No incomplete browser mission is available in this project."
    if state["status"] != "resumable" or not state["checkpoint"].get("safe_to_retry"):
        return state, None, "The last browser mission may have invoked its final control, so AURIS requires manual review instead of replay."
    task = get_task(state["task_id"], path=path)
    if task is None or task.get("task_type") != "browser_workflow":
        return state, None, "The source mission record is unavailable, so AURIS cannot reconstruct it safely."
    return state, task, None


def continuation_approval_details(state: dict[str, Any] | None) -> tuple[str, str]:
    if state is None:
        return "incomplete browser mission", "No mission will replay unless its exact durable checkpoint resolves again after approval."
    checkpoint = state["checkpoint"]
    return (
        f"{state['application']} checkpoint {state['state_id'][:8]}",
        f"Retry the exact digest-bound browser mission from its initial navigation because it stopped before the final control. {len(state['completed'])} of {checkpoint.get('total_steps', 0)} steps were verified; no uncertain final control will be replayed.",
    )


def _step_summary(step: BrowserStep, index: int) -> dict[str, Any]:
    if step.kind == "navigate":
        target = urlparse(step.url).hostname or "approved website"
    else:
        target = step.accessible_name
    return {"index": index, "kind": step.kind, "target": target[:160]}


def _normalise(command: str) -> str:
    text = " ".join(command.strip().split())
    lowered = text.casefold()
    for prefix in ("hey auris, ", "hey auris ", "auris, ", "auris "):
        if lowered.startswith(prefix):
            text = text[len(prefix):]
            break
    return text.strip(" .")
