from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auris.anticipation_service import build_daily_intelligence, build_operations_intelligence
from auris.coding_agent import execute_coding_command
from auris.codex_workspace_agent import codex_cli_status
from auris.communications_agent import productivity_status
from auris.database import (
    DATABASE_PATH,
    list_approvals,
    list_memories,
    list_projects,
    list_scheduled_events,
    list_tasks,
)
from auris.system_status import collect_system_status


ACTIVE_STATES = {"created", "planning", "running", "verifying", "recovering", "awaiting_approval"}
FAILED_STATES = {"failed", "interrupted", "blocked"}


def workspace_snapshot(
    *, project_id: str | None = "auris-one", path: Path = DATABASE_PATH
) -> dict[str, Any]:
    tasks = list_tasks(limit=200, path=path)
    projects = list_projects(path=path)
    memories = list_memories(limit=500, path=path)
    events = list_scheduled_events(limit=200, path=path)
    approvals = list_approvals(status="pending", path=path)
    integrations = productivity_status()
    intelligence = build_operations_intelligence(project_id=project_id, path=path)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "projects": _project_workspace(projects, tasks, memories, events),
        "research": _research_workspace(tasks),
        "engineering": _engineering_workspace(
            tasks,
            next((project for project in projects if project["project_id"] == project_id), None),
        ),
        "documents": _document_workspace(tasks),
        "daily": intelligence["daily"],
        "operations": {
            "attention": intelligence["attention"],
            "graph": intelligence["graph"],
            "evening": intelligence["evening"],
            "external_context": intelligence["external_context"],
        },
    }


def build_daily_brief(
    *,
    kind: str = "daily",
    project_id: str | None = None,
    private: bool = False,
    focus_mode: bool = False,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    return build_daily_intelligence(
        kind=kind,
        project_id=project_id,
        private=private,
        focus_mode=focus_mode,
        path=path,
    )


def _project_workspace(
    projects: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    memories: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = []
    for project in projects:
        project_id = project["project_id"]
        project_tasks = [task for task in tasks if task.get("project_id") == project_id]
        rows.append(
            {
                "project_id": project_id,
                "name": project["name"],
                "description": project["description"],
                "root_connected": bool(project.get("root_path")),
                "task_count": len(project_tasks),
                "active_tasks": sum(task.get("state") in ACTIVE_STATES for task in project_tasks),
                "completed_tasks": sum(task.get("state") == "completed" for task in project_tasks),
                "memory_count": sum(memory.get("project_id") == project_id for memory in memories),
                "scheduled_events": sum(
                    event.get("project_id") == project_id and event.get("status") == "scheduled"
                    for event in events
                ),
                "last_activity": max(
                    (task.get("updated_at", "") for task in project_tasks), default=""
                ),
            }
        )
    return {"items": rows, "active_count": sum(item["active_tasks"] > 0 for item in rows)}


def _research_workspace(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    research_tasks = [task for task in tasks if task.get("task_type") == "research"]
    campaigns: list[dict[str, Any]] = []
    source_stream: list[dict[str, Any]] = []
    claim_stream: list[dict[str, Any]] = []
    for task in research_tasks[:20]:
        action = (task.get("result") or {}).get("research_action") or {}
        sources = action.get("sources") if isinstance(action.get("sources"), list) else []
        claims = action.get("claims") if isinstance(action.get("claims"), list) else []
        ledger = action.get("coverage_ledger") if isinstance(action.get("coverage_ledger"), dict) else {}
        plan = action.get("research_plan") if isinstance(action.get("research_plan"), dict) else {}
        campaigns.append(
            {
                "task_id": task["task_id"],
                "topic": action.get("query") or task.get("objective"),
                "state": task.get("state"),
                "mode": action.get("mode") or "rapid",
                "source_count": len(sources),
                "claim_count": len(claims),
                "query_count": ledger.get("queries_planned") or len(plan.get("queries") or []),
                "counterevidence_count": ledger.get("counterevidence_queries", 0),
                "duplicate_count": ledger.get("duplicate_count", action.get("duplicate_count", 0)),
                "branch_coverage_percent": ledger.get("branch_coverage_percent", 0),
                "definition_of_done_met": bool(action.get("definition_of_done_met")),
                "definition_of_done": action.get("definition_of_done") or [],
                "citations_present": bool(action.get("citations_present")),
                "duration_ms": action.get("duration_ms"),
                "updated_at": task.get("updated_at"),
                "verification_status": (task.get("result") or {})
                .get("verification_report", {})
                .get("status"),
            }
        )
        for source in sources:
            source_stream.append(
                {
                    "source_id": source.get("source_id"),
                    "title": source.get("title"),
                    "url": source.get("url"),
                    "publisher": source.get("publisher"),
                    "source_type": source.get("source_type") or "web",
                    "primary": bool(source.get("primary")),
                    "retrieval_date": source.get("retrieval_date"),
                    "task_id": task["task_id"],
                }
            )
        for claim in claims:
            claim_stream.append(
                {
                    "claim_id": claim.get("claim_id"),
                    "claim": claim.get("claim"),
                    "source_ids": claim.get("source_ids") or [],
                    "counterevidence_source_ids": claim.get("counterevidence_source_ids") or [],
                    "status": claim.get("status") or "uncertain",
                    "task_id": task["task_id"],
                }
            )
    latest = campaigns[0] if campaigns else None
    latest_action = {}
    if research_tasks:
        latest_action = (research_tasks[0].get("result") or {}).get("research_action") or {}
    latest_ledger = latest_action.get("coverage_ledger") if isinstance(latest_action.get("coverage_ledger"), dict) else {}
    return {
        "campaigns": campaigns,
        "sources": source_stream[:30],
        "claims": claim_stream[:60],
        "metrics": {
            "campaigns": len(research_tasks),
            "sources_processed": sum(item["source_count"] for item in campaigns),
            "claims": sum(item["claim_count"] for item in campaigns),
            "verified": sum(item["definition_of_done_met"] for item in campaigns),
            "failed": sum(item["state"] in FAILED_STATES for item in campaigns),
        },
        "coverage_dimensions": [
            {"name": "public_web", "state": "connected"},
            {"name": "source_provenance", "state": "preserved" if source_stream else "awaiting_mission"},
            {"name": "primary_sources", "state": "identified" if latest_ledger.get("primary_source_count", 0) else "incomplete"},
            {"name": "claim_evidence", "state": "linked" if claim_stream else "incomplete"},
            {"name": "counterevidence", "state": "searched" if latest_ledger.get("counterevidence_queries", 0) else "incomplete"},
            {"name": "deduplication", "state": "resolved" if latest_ledger.get("ledger_complete") else "incomplete"},
            {"name": "coverage_ledger", "state": "complete" if latest and latest["definition_of_done_met"] else "partial"},
        ],
    }


def _engineering_workspace(
    tasks: list[dict[str, Any]], project: dict[str, Any] | None
) -> dict[str, Any]:
    configured_root = str((project or {}).get("root_path") or "").strip()
    repository = (
        execute_coding_command(
            "analyze_project",
            root=Path(configured_root),
            project_name=str((project or {}).get("name") or "Selected project"),
        )
        if configured_root
        else {
            "ok": False,
            "error": "No local project root is registered.",
            "extensions": {},
        }
    )
    coding_tasks = [
        task
        for task in tasks
        if (task.get("task_type") == "coding" or (task.get("result") or {}).get("coding_action"))
        and (
            project is None
            or (
                ((task.get("result") or {}).get("generated_project") or {}).get("project_id")
                or ((task.get("result") or {}).get("coding_action") or {}).get("generated_project_id")
                or task.get("project_id")
            )
            == project.get("project_id")
        )
    ]
    recent_runs = []
    for task in coding_tasks[:20]:
        action = (task.get("result") or {}).get("coding_action") or {}
        if not action.get("operation"):
            continue
        proposal = action.get("proposal") if isinstance(action.get("proposal"), dict) else {}
        verified_targeted = proposal.get("verified_targeted") or action.get("targeted_test") or {}
        verified_full = proposal.get("verified_full") or action.get("full_test") or action.get("reproduction") or {}
        proposal_files = proposal.get("files") or [
            {"path": path} for path in (action.get("applied_files") or [])
        ]
        recent_runs.append(
            {
                "task_id": task["task_id"],
                "objective": task.get("objective"),
                "state": task.get("state"),
                "operation": action.get("operation"),
                "exit_code": action.get("exit_code", verified_full.get("exit_code")),
                "test_count": action.get("test_count", verified_full.get("test_count")),
                "duration_ms": action.get("duration_ms"),
                "snapshot_id": action.get("snapshot_id"),
                "component_count": len(action.get("components") or []),
                "risk_count": len(action.get("risks") or []),
                "proposal_id": proposal.get("proposal_id") or action.get("proposal_id"),
                "proposal_status": proposal.get("status") or (
                    "applied"
                    if action.get("operation") in {"apply_repair", "apply_codex_workspace_change"}
                    and action.get("ok")
                    else None
                ),
                "approval_required": bool(action.get("approval_required")),
                "isolation_kind": proposal.get("isolation_kind"),
                "diagnosis": proposal.get("diagnosis"),
                "files": proposal_files,
                "diff": proposal.get("diff") or action.get("diff"),
                "diff_stats": proposal.get("diff_stats") or action.get("diff_stats") or {},
                "targeted_passed": verified_targeted.get("passed"),
                "full_passed": verified_full.get("passed"),
                "rolled_back": action.get("rolled_back"),
                "updated_at": task.get("updated_at"),
            }
        )
    extensions = repository.get("extensions", {}) if repository.get("ok") else {}
    return {
        "coding_engine": codex_cli_status(),
        "repository": {
            "name": (project or {}).get("name") or "Unselected project",
            "project_id": (project or {}).get("project_id"),
            "root": repository.get("root"),
            "root_connected": bool(configured_root and repository.get("ok")),
            "analysis_error": repository.get("error"),
            "snapshot_id": repository.get("snapshot_id"),
            "file_count": repository.get("file_count", 0),
            "text_line_count": repository.get("text_line_count", 0),
            "extensions": [
                {"extension": extension, "count": count}
                for extension, count in list(extensions.items())[:12]
            ],
            "largest_files": repository.get("largest_files", []),
            "languages": repository.get("languages", []),
            "components": repository.get("components", []),
            "instructions": repository.get("instructions", []),
            "manifests": repository.get("manifests", []),
            "manifest_details": repository.get("manifest_details", []),
            "entry_points": repository.get("entry_points", []),
            "tests": repository.get("tests", {"file_count": 0, "commands": []}),
            "risks": repository.get("risks", []),
            "scan": repository.get("scan", {}),
            "version_control": (repository.get("version_control") or {}).get(
                "state", "not_configured"
            ),
            "version_control_detail": repository.get("version_control") or {},
        },
        "recent_runs": recent_runs,
        "metrics": {
            "test_runs": sum(item["operation"] == "run_tests" for item in recent_runs),
            "last_test_count": next(
                (item["test_count"] for item in recent_runs if item["test_count"] is not None),
                None,
            ),
            "last_exit_code": next(
                (item["exit_code"] for item in recent_runs if item["exit_code"] is not None),
                None,
            ),
            "repair_proposals": sum(bool(item["proposal_id"]) for item in recent_runs),
            "pending_repairs": sum(item["state"] == "awaiting_approval" for item in recent_runs),
            "verified_repairs": sum(item["proposal_status"] == "applied" for item in recent_runs),
            "autonomous_edits": "approval_gated",
            "security_policy": "enforced",
            "root_connected": bool(configured_root and repository.get("ok")),
            "latest_snapshot": repository.get("snapshot_id"),
            "test_files": (repository.get("tests") or {}).get("file_count", 0),
            "review_signals": len(repository.get("risks") or []),
        },
    }


def _document_workspace(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    relevant = [
        task for task in tasks if task.get("task_type") in {"document_workflow", "file_workflow"}
    ]
    recent = []
    formats: Counter[str] = Counter()
    for task in relevant[:30]:
        result = task.get("result") or {}
        document = (result.get("document_action") or {}).get("document") or {}
        if document.get("format"):
            formats[str(document["format"])] += 1
        recent.append(
            {
                "task_id": task["task_id"],
                "objective": task.get("objective"),
                "state": task.get("state"),
                "name": document.get("name"),
                "format": document.get("format"),
                "bytes_read": document.get("bytes_read"),
                "updated_at": task.get("updated_at"),
            }
        )
    return {
        "recent": recent,
        "formats_processed": [
            {"format": name, "count": count} for name, count in formats.most_common()
        ],
        "supported_read_formats": [
            "CSV", "DOCX", "HTML", "JSON", "LOG", "MARKDOWN", "PDF", "PYTHON", "TEXT", "XLSX"
        ],
        "write_worker": "not_connected",
        "original_files_preserved": True,
    }


def _daily_workspace(
    tasks: list[dict[str, Any]],
    events: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
    integrations: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now().astimezone()
    scheduled = sorted(
        (event for event in events if event.get("status") == "scheduled"),
        key=lambda event: event.get("due_at", ""),
    )
    active = [task for task in tasks if task.get("state") in ACTIVE_STATES]
    failed = [task for task in tasks if task.get("state") in FAILED_STATES]
    primary = (
        active[0].get("objective")
        if active
        else scheduled[0].get("title")
        if scheduled
        else "Select the highest-value project objective"
    )
    priorities = []
    if approvals:
        priorities.append({"level": "P1", "title": f"Review {len(approvals)} pending approval(s)"})
    for event in scheduled[:2]:
        priorities.append({"level": "P1", "title": event.get("title"), "due_at": event.get("due_at")})
    if failed:
        priorities.append({"level": "P2", "title": f"Review {len(failed)} failed or interrupted mission(s)"})
    if not priorities:
        priorities.append({"level": "P2", "title": primary})
    device = collect_system_status()
    risks = []
    if failed:
        risks.append({"level": "amber", "title": f"{len(failed)} mission(s) require review"})
    if device.get("disk", {}).get("free_gb", 100) < 10:
        risks.append({"level": "amber", "title": "Device storage is below 10 GB free"})
    if not risks:
        risks.append({"level": "green", "title": "No immediate local-system risk detected"})
    return {
        "local_date": now.strftime("%A, %d %B %Y"),
        "location": "London, United Kingdom",
        "primary_objective": primary,
        "priorities": priorities[:4],
        "schedule": scheduled[:8],
        "risks": risks,
        "active_systems": {
            "active_tasks": len(active),
            "pending_approvals": len(approvals),
            "scheduled_events": len(scheduled),
            "outlook": integrations.get("outlook", {}).get("state", "not_connected"),
            "onedrive": integrations.get("onedrive", {}).get("state", "not_connected"),
            "telephony": integrations.get("telephony", {}).get("state", "not_connected"),
        },
        "suggested_first_action": (
            "Review the oldest pending approval."
            if approvals
            else f"Prepare for {scheduled[0].get('title')}."
            if scheduled
            else "Choose a project objective and start a focused mission."
        ),
        "live_weather": "not_connected",
        "external_calendar_loaded": False,
        "mailbox_loaded": False,
    }
