from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from auris.audit import record_event
from auris.database import (
    DATABASE_PATH,
    create_proactive_watch,
    delete_proactive_watch,
    get_project,
    list_proactive_alerts,
    list_proactive_watches,
    record_proactive_watch_evaluation,
    set_proactive_watch_enabled,
)
from auris.predictive_intelligence import build_predictive_intelligence


METRIC_LABELS = {
    "project_delay_risk": "project delay risk",
    "deadline_risk": "deadline risk",
    "workload_pressure": "workload pressure",
    "resource_conflicts": "resource conflicts",
    "follow_up_likelihood": "follow-up likelihood",
    "mission_failure_probability": "mission failure rate",
    "opportunity_relevance": "opportunity relevance",
}
METRIC_ALIASES = {
    alias: metric
    for metric, aliases in {
        "project_delay_risk": ("project delay risk", "delay risk", "project delays"),
        "deadline_risk": ("deadline risk", "deadlines"),
        "workload_pressure": ("workload pressure", "workload"),
        "resource_conflicts": ("resource conflicts", "resource conflict"),
        "follow_up_likelihood": ("follow up likelihood", "follow-up likelihood", "follow ups"),
        "mission_failure_probability": ("mission failure rate", "mission failure probability", "failure rate"),
        "opportunity_relevance": ("opportunity relevance", "opportunities"),
    }.items()
    for alias in aliases
}
MIN_INTERVAL_SECONDS = 60
MAX_INTERVAL_SECONDS = 86400
MIN_COOLDOWN_SECONDS = 300
MAX_COOLDOWN_SECONDS = 604800


class ProactiveWatchValidationError(ValueError):
    pass


@dataclass(frozen=True)
class WatchCommand:
    action: str
    metric: str | None = None
    operator: str = "gte"
    threshold: int = 0
    interval_seconds: int = 300


def parse_watch_command(command: str) -> WatchCommand | None:
    text = " ".join(command.casefold().replace(",", " ").split()).strip(" .")
    for prefix in ("hey auris ", "auris "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    if re.fullmatch(r"(?:show|list)(?: my| the)? (?:proactive )?(?:watches|monitors)", text):
        return WatchCommand("list")

    cancel = re.fullmatch(
        r"(?:stop|cancel|disable)(?: the)? (.+?)(?: watch| monitor)", text
    )
    if cancel:
        metric = _resolve_metric(cancel.group(1))
        return WatchCommand("cancel", metric=metric) if metric else None

    create = re.fullmatch(
        r"(?:watch|monitor|notify me when) (.+?) "
        r"(?:is |goes )?(above|over|at least|below|under|at most) (\d{1,3})"
        r"(?: percent|%)?"
        r"(?: every (\d{1,4}) (minutes?|hours?))?",
        text,
    )
    if not create:
        return None
    metric = _resolve_metric(create.group(1))
    if not metric:
        return None
    threshold = int(create.group(3))
    if threshold > 100:
        return None
    operator = "gte" if create.group(2) in {"above", "over", "at least"} else "lte"
    interval = 300
    if create.group(4):
        amount = int(create.group(4))
        interval = amount * (3600 if create.group(5).startswith("hour") else 60)
    if not MIN_INTERVAL_SECONDS <= interval <= MAX_INTERVAL_SECONDS:
        return None
    return WatchCommand("create", metric, operator, threshold, interval)


def create_watch(
    *,
    project_id: str,
    metric: str,
    operator: str,
    threshold: float,
    interval_seconds: int = 300,
    cooldown_seconds: int = 3600,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    if metric not in METRIC_LABELS:
        raise ProactiveWatchValidationError("Unsupported predictive metric.")
    if operator not in {"gte", "lte"}:
        raise ProactiveWatchValidationError("Watch operator must be gte or lte.")
    if not 0 <= threshold <= 100:
        raise ProactiveWatchValidationError("Watch threshold must be between 0 and 100.")
    if not MIN_INTERVAL_SECONDS <= interval_seconds <= MAX_INTERVAL_SECONDS:
        raise ProactiveWatchValidationError("Watch interval must be between 60 and 86400 seconds.")
    if not MIN_COOLDOWN_SECONDS <= cooldown_seconds <= MAX_COOLDOWN_SECONDS:
        raise ProactiveWatchValidationError("Watch cooldown must be between 300 and 604800 seconds.")
    if get_project(project_id, path=path) is None:
        raise ProactiveWatchValidationError("Unknown project.")
    watch = create_proactive_watch(
        project_id,
        metric,
        operator,
        threshold,
        interval_seconds=interval_seconds,
        cooldown_seconds=cooldown_seconds,
        path=path,
    )
    record_event(
        "proactive_watch.created",
        {"watch_id": watch["watch_id"], "project_id": project_id, "metric": metric},
    )
    return watch


def execute_watch_command(
    request: WatchCommand, *, project_id: str, path: Path = DATABASE_PATH
) -> dict[str, Any]:
    if request.action == "list":
        watches = list_proactive_watches(project_id=project_id, path=path)
        return {"ok": True, "operation": "list", "watches": watches}
    if request.action == "cancel":
        matches = [
            item
            for item in list_proactive_watches(project_id=project_id, enabled=True, path=path)
            if item["metric"] == request.metric
        ]
        if not matches:
            return {"ok": False, "operation": "cancel", "error": "No matching active watch exists."}
        watch = set_proactive_watch_enabled(matches[0]["watch_id"], False, path=path)
        record_event("proactive_watch.disabled", {"watch_id": watch["watch_id"]})
        return {"ok": True, "operation": "cancel", "watch": watch}
    watch = create_watch(
        project_id=project_id,
        metric=str(request.metric),
        operator=request.operator,
        threshold=request.threshold,
        interval_seconds=request.interval_seconds,
        path=path,
    )
    return {"ok": True, "operation": "create", "watch": watch}


class ProactiveWatchEngine:
    def __init__(
        self,
        *,
        notifier: Callable[[str], None] | None = None,
        path: Path = DATABASE_PATH,
        predictor: Callable[..., dict[str, Any]] = build_predictive_intelligence,
    ) -> None:
        self.notifier = notifier
        self.path = path
        self.predictor = predictor

    def poll_once(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        current = _normalise_now(now)
        due = [item for item in list_proactive_watches(enabled=True, path=self.path) if _is_due(item, current)]
        forecasts_by_project: dict[str, dict[str, dict[str, Any]]] = {}
        alerts: list[dict[str, Any]] = []
        for watch in due:
            project_id = watch["project_id"]
            if project_id not in forecasts_by_project:
                intelligence = self.predictor(project_id=project_id, private=False, now=current, path=self.path)
                forecasts_by_project[project_id] = {
                    item["metric"]: item for item in intelligence.get("forecasts", [])
                }
            forecast = forecasts_by_project[project_id].get(watch["metric"])
            if not forecast:
                continue
            value = float(forecast["score"])
            evidence_ids = list(forecast.get("evidence_ids") or [])
            threshold_met = value >= watch["threshold"] if watch["operator"] == "gte" else value <= watch["threshold"]
            active = bool(evidence_ids) and threshold_met
            transitioned = active and not watch["condition_active"]
            cooldown_clear = _cooldown_clear(watch, current)
            stored_active = active and (not transitioned or cooldown_clear)
            result = record_proactive_watch_evaluation(
                watch["watch_id"],
                observed_value=value,
                condition_active=stored_active,
                classification=str(forecast.get("classification") or "unknown"),
                evidence_ids=evidence_ids,
                evaluated_at=current.isoformat(),
                notify=transitioned and cooldown_clear,
                path=self.path,
            )
            alert = result.get("alert")
            if alert:
                alerts.append(alert)
                message = _alert_message(alert)
                if self.notifier:
                    self.notifier(message)
                record_event(
                    "proactive_watch.alerted",
                    {"watch_id": watch["watch_id"], "alert_id": alert["alert_id"], "metric": watch["metric"]},
                )
        return alerts


def watch_dashboard(*, project_id: str | None = None, path: Path = DATABASE_PATH) -> dict[str, Any]:
    return {
        "watches": list_proactive_watches(project_id=project_id, path=path),
        "alerts": list_proactive_alerts(project_id=project_id, path=path),
        "policy": {
            "advisory_only": True,
            "automatic_action": False,
            "minimum_interval_seconds": MIN_INTERVAL_SECONDS,
            "minimum_cooldown_seconds": MIN_COOLDOWN_SECONDS,
            "trigger": "inactive_to_active_threshold_transition",
        },
    }


def remove_watch(watch_id: str, *, path: Path = DATABASE_PATH) -> bool:
    deleted = delete_proactive_watch(watch_id, path=path)
    if deleted:
        record_event("proactive_watch.deleted", {"watch_id": watch_id})
    return deleted


def _resolve_metric(text: str) -> str | None:
    normalized = " ".join(text.replace("-", " ").split())
    return METRIC_ALIASES.get(normalized)


def _is_due(watch: dict[str, Any], now: datetime) -> bool:
    if not watch.get("last_evaluated_at"):
        return True
    last = _parse_time(watch["last_evaluated_at"])
    return now >= last + timedelta(seconds=int(watch["interval_seconds"]))


def _cooldown_clear(watch: dict[str, Any], now: datetime) -> bool:
    if not watch.get("last_notified_at"):
        return True
    return now >= _parse_time(watch["last_notified_at"]) + timedelta(seconds=int(watch["cooldown_seconds"]))


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _normalise_now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current if current.tzinfo else current.replace(tzinfo=timezone.utc)


def _alert_message(alert: dict[str, Any]) -> str:
    relation = "at or above" if alert["operator"] == "gte" else "at or below"
    return (
        f"Proactive alert, Devansh. {METRIC_LABELS[alert['metric']]} is "
        f"{alert['observed_value']:.0f}, {relation} your {alert['threshold']:.0f} threshold."
    )
