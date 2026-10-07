from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from auris.database import (
    DATABASE_PATH,
    list_approvals,
    list_projects,
    list_scheduled_events,
    list_tasks,
)


MIN_FAILURE_SAMPLE = 20
ACTIVE_STATES = {"created", "planning", "running", "verifying", "recovering", "awaiting_approval", "partially_completed"}
FAILED_STATES = {"failed", "blocked", "interrupted"}
TERMINAL_STATES = {"completed", *FAILED_STATES}


def build_predictive_intelligence(
    *,
    project_id: str | None = None,
    private: bool = False,
    now: datetime | None = None,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    current = _normalise_now(now)
    if private:
        return {
            "generated_at": current.isoformat(),
            "private_mode": True,
            "project_id": project_id,
            "forecasts": [],
            "portfolio": [],
            "message": "Predictive operational intelligence is suppressed in Private Session.",
            "provenance": "real_durable_state",
        }

    projects = list_projects(path=path)
    if project_id:
        projects = [item for item in projects if item["project_id"] == project_id]
    tasks = list_tasks(limit=1000, path=path)
    events = list_scheduled_events(limit=1000, path=path)
    approvals = list_approvals(status="pending", path=path)
    portfolio = [
        _project_forecast(
            project,
            [item for item in tasks if item.get("project_id") == project["project_id"]],
            [item for item in events if item.get("project_id") == project["project_id"]],
            [
                item
                for item in approvals
                if any(
                    task.get("task_id") == item.get("task_id")
                    and task.get("project_id") == project["project_id"]
                    for task in tasks
                )
            ],
            current,
        )
        for project in projects
    ]
    forecasts = [item for project in portfolio for item in project["forecasts"]]
    ranked = sorted(
        forecasts,
        key=lambda item: (item["score"], item["metric"], item["project_id"]),
        reverse=True,
    )
    return {
        "generated_at": current.isoformat(),
        "private_mode": False,
        "project_id": project_id,
        "forecasts": ranked,
        "portfolio": portfolio,
        "top_signal": ranked[0] if ranked else None,
        "method": {
            "risk_scores": "Deterministic 0-100 operational indicators, not probabilities.",
            "mission_failure_probability": (
                f"Observed failed/blocked/interrupted share with Wilson 95% interval after {MIN_FAILURE_SAMPLE} terminal missions."
            ),
            "automatic_action": False,
        },
        "provenance": "real_durable_state",
    }


def _project_forecast(
    project: dict[str, Any],
    tasks: list[dict[str, Any]],
    events: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    active = [item for item in tasks if str(item.get("state")) in ACTIVE_STATES]
    terminal = [item for item in tasks if str(item.get("state")) in TERMINAL_STATES]
    failed = [item for item in terminal if str(item.get("state")) in FAILED_STATES]
    overdue = [item for item in events if item.get("status") == "scheduled" and _parse_time(item.get("due_at")) < now]
    due_day = [
        item
        for item in events
        if item.get("status") == "scheduled"
        and now <= _parse_time(item.get("due_at")) <= now + timedelta(hours=24)
    ]
    due_week = [
        item
        for item in events
        if item.get("status") == "scheduled"
        and now < _parse_time(item.get("due_at")) <= now + timedelta(days=7)
    ]
    stale_active = [
        item
        for item in active
        if _parse_time(item.get("updated_at"), fallback=now) <= now - timedelta(days=7)
    ]
    agent_counts = Counter(
        str(agent)
        for task in active
        for agent in (task.get("required_agents") or [])
        if str(agent)
    )
    overloaded_agents = sorted(agent for agent, count in agent_counts.items() if count > 2)
    overlapping_events = _overlapping_events(events)

    project_id = project["project_id"]
    deadline_evidence = [item["event_id"] for item in overdue + due_day]
    workload_evidence = [item["task_id"] for item in active] + [item["approval_id"] for item in approvals]
    delay_score = min(100, len(overdue) * 30 + len(stale_active) * 20 + len(failed[-5:]) * 8)
    deadline_score = min(100, len(overdue) * 40 + len(due_day) * 18)
    workload_score = min(100, len(active) * 9 + len(approvals) * 16 + len(due_week) * 5)
    conflict_score = min(100, len(overlapping_events) * 30 + len(overloaded_agents) * 22)
    follow_up_score = min(100, len(stale_active) * 25 + len(approvals) * 18 + len(failed[-5:]) * 8)
    opportunity_score = min(100, max(0, 60 - workload_score // 2 - deadline_score // 3))

    forecasts = [
        _score_forecast(project_id, "project_delay_risk", delay_score, [item["task_id"] for item in stale_active + failed[-5:]] + [item["event_id"] for item in overdue], "Overdue events, stale active missions, and recent failed terminal missions."),
        _score_forecast(project_id, "deadline_risk", deadline_score, deadline_evidence, "Overdue and next-24-hour scheduled events."),
        _score_forecast(project_id, "workload_pressure", workload_score, workload_evidence, "Active missions, pending approvals, and seven-day scheduled load."),
        _score_forecast(project_id, "resource_conflicts", conflict_score, overlapping_events + overloaded_agents, "Overlapping events and agents assigned to more than two active missions."),
        _score_forecast(project_id, "follow_up_likelihood", follow_up_score, [item["task_id"] for item in stale_active + failed[-5:]] + [item["approval_id"] for item in approvals], "Stale missions, pending approvals, and recent failures indicate follow-up demand."),
        _score_forecast(project_id, "opportunity_relevance", opportunity_score, [item["task_id"] for item in active], "Available operational capacity after workload and deadline pressure."),
        _failure_forecast(project_id, terminal, failed),
    ]
    return {
        "project_id": project_id,
        "project_name": project.get("name") or project_id,
        "forecasts": forecasts,
        "evidence_counts": {
            "active_tasks": len(active),
            "terminal_tasks": len(terminal),
            "failed_tasks": len(failed),
            "overdue_events": len(overdue),
            "due_within_24_hours": len(due_day),
            "pending_approvals": len(approvals),
            "overloaded_agents": len(overloaded_agents),
        },
    }


def _score_forecast(
    project_id: str, metric: str, score: int, evidence_ids: list[str], method: str
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "metric": metric,
        "score": int(score),
        "classification": _classification(score),
        "probability": None,
        "interval": None,
        "sample_size": len(set(evidence_ids)),
        "sample_sufficient": bool(evidence_ids),
        "evidence_ids": sorted(set(str(item) for item in evidence_ids if item))[:50],
        "method": method,
        "source": "durable_operational_state",
        "provenance": "real_durable_state",
        "uncertainty": "This is a deterministic operational score, not a calibrated probability.",
        "advisory_only": True,
    }


def _failure_forecast(
    project_id: str, terminal: list[dict[str, Any]], failed: list[dict[str, Any]]
) -> dict[str, Any]:
    sample = len(terminal)
    sufficient = sample >= MIN_FAILURE_SAMPLE
    probability = len(failed) / sample if sufficient else None
    interval = _wilson_interval(len(failed), sample) if sufficient else None
    return {
        "project_id": project_id,
        "metric": "mission_failure_probability",
        "score": round(probability * 100) if probability is not None else 0,
        "classification": _classification(round(probability * 100)) if probability is not None else "insufficient_data",
        "probability": round(probability, 6) if probability is not None else None,
        "interval": interval,
        "sample_size": sample,
        "minimum_sample_size": MIN_FAILURE_SAMPLE,
        "sample_sufficient": sufficient,
        "evidence_ids": [item["task_id"] for item in terminal[-50:]],
        "method": "Observed terminal mission outcomes; failed, blocked, and interrupted count as failures.",
        "source": "durable_task_outcomes",
        "provenance": "real_durable_state",
        "uncertainty": (
            "Wilson 95% interval over observed outcomes; it does not establish causation or future stationarity."
            if sufficient
            else f"Probability withheld until {MIN_FAILURE_SAMPLE} terminal missions exist for this project."
        ),
        "advisory_only": True,
    }


def _wilson_interval(failures: int, sample: int) -> list[float]:
    if sample <= 0:
        return []
    z = 1.959963984540054
    p = failures / sample
    denominator = 1 + z * z / sample
    center = (p + z * z / (2 * sample)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * sample)) / sample) / denominator
    return [round(max(0.0, center - margin), 6), round(min(1.0, center + margin), 6)]


def _overlapping_events(events: list[dict[str, Any]]) -> list[str]:
    scheduled = sorted(
        (
            (_parse_time(item.get("due_at")), str(item.get("event_id")))
            for item in events
            if item.get("status") == "scheduled"
        ),
        key=lambda item: item[0],
    )
    overlaps = set()
    for index, (left_time, left_id) in enumerate(scheduled):
        for right_time, right_id in scheduled[index + 1 :]:
            if right_time - left_time > timedelta(hours=1):
                break
            overlaps.update((left_id, right_id))
    return sorted(overlaps)


def _classification(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 45:
        return "elevated"
    if score >= 20:
        return "guarded"
    return "low"


def _parse_time(value: Any, *, fallback: datetime | None = None) -> datetime:
    if not value:
        return fallback or datetime.max.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return fallback or datetime.max.replace(tzinfo=timezone.utc)


def _normalise_now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current if current.tzinfo else current.replace(tzinfo=timezone.utc)
