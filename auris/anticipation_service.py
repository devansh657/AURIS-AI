from __future__ import annotations

import re
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from auris.communications_agent import productivity_status
from auris.database import (
    DATABASE_PATH,
    list_approvals,
    list_projects,
    list_scheduled_events,
    list_tasks,
)
from auris.memory_service import memory_dashboard
from auris.system_status import collect_system_status


ACTIVE_STATES = {"created", "planning", "running", "verifying", "recovering", "awaiting_approval"}
FAILED_STATES = {"failed", "interrupted", "blocked"}
FINISHED_STATES = {"completed", "failed", "interrupted", "blocked", "cancelled"}
GRAPH_NODE_LIMIT = 180
GRAPH_EDGE_LIMIT = 320
QUERY_HOPS = 2

_LEVELS = ("LOG", "BRIEFING", "NOTIFY", "IMPORTANT", "URGENT", "CRITICAL")
_SECRET_VALUE = re.compile(
    r"(?i)(?:api[_ -]?key|token|password|secret|authorization)\s*[:=]\s*\S+"
)


def build_operations_intelligence(
    *,
    project_id: str | None = None,
    query: str = "",
    private: bool = False,
    focus_mode: bool = False,
    now: datetime | None = None,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    current = _normalise_now(now)
    context = _load_context(path=path)
    attention = _build_attention(
        context,
        project_id=project_id,
        private=private,
        focus_mode=focus_mode,
        now=current,
    )
    daily = _build_daily(
        context,
        attention,
        project_id=project_id,
        private=private,
        now=current,
    )
    evening = _build_evening(
        context,
        attention,
        project_id=project_id,
        private=private,
        now=current,
    )
    return {
        "generated_at": current.isoformat(),
        "project_id": project_id,
        "private_mode": private,
        "focus_mode": focus_mode,
        "attention": attention,
        "graph": _build_graph(
            context,
            project_id=project_id,
            query=query,
            private=private,
        ),
        "daily": daily,
        "evening": evening,
        "external_context": {
            "mailbox_loaded": False,
            "external_calendar_loaded": False,
            "live_weather": "not_connected",
            "travel_loaded": False,
            "financial_accounts_loaded": False,
        },
    }


def build_operations_graph(
    *,
    project_id: str | None = None,
    query: str = "",
    private: bool = False,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    return _build_graph(
        _load_context(path=path),
        project_id=project_id,
        query=query,
        private=private,
    )


def build_attention_snapshot(
    *,
    project_id: str | None = None,
    private: bool = False,
    focus_mode: bool = False,
    now: datetime | None = None,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    return _build_attention(
        _load_context(path=path),
        project_id=project_id,
        private=private,
        focus_mode=focus_mode,
        now=_normalise_now(now),
    )


def build_daily_intelligence(
    *,
    kind: str = "daily",
    project_id: str | None = None,
    private: bool = False,
    focus_mode: bool = False,
    now: datetime | None = None,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    if kind not in {"daily", "evening"}:
        raise ValueError("Briefing kind must be daily or evening.")
    intelligence = build_operations_intelligence(
        project_id=project_id,
        private=private,
        focus_mode=focus_mode,
        now=now,
        path=path,
    )
    return intelligence[kind]


def _load_context(*, path: Path) -> dict[str, Any]:
    return {
        "tasks": list_tasks(limit=500, path=path),
        "projects": list_projects(path=path),
        "events": list_scheduled_events(limit=500, path=path),
        "approvals": list_approvals(status="pending", path=path),
        "memory": memory_dashboard(limit=500, path=path),
        "integrations": productivity_status(),
        "system": collect_system_status(),
    }


def _build_graph(
    context: dict[str, Any],
    *,
    project_id: str | None,
    query: str,
    private: bool,
) -> dict[str, Any]:
    clean_query = _clean_graph_query(query)
    if private:
        return {
            "query": clean_query,
            "nodes": [],
            "edges": [],
            "matched_node_ids": [],
            "private_mode": True,
            "message": "Operations graph retrieval is suppressed in Private Session.",
            "provenance": "real_durable_state",
            "truncated": False,
        }

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    def add_node(
        node_id: str,
        node_type: str,
        label: str,
        *,
        status: str = "current",
        source: str,
        linked_project_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not node_id or node_id in nodes or len(nodes) >= GRAPH_NODE_LIMIT * 2:
            return
        nodes[node_id] = {
            "id": node_id,
            "type": node_type,
            "label": _safe_text(label, 180),
            "status": status,
            "source": source,
            "provenance": "real_durable_state",
            "project_id": linked_project_id,
            "metadata": metadata or {},
        }

    def add_edge(source_id: str, target_id: str, relation: str, source: str) -> None:
        if source_id not in nodes or target_id not in nodes:
            return
        edge_id = f"{source_id}|{relation}|{target_id}"
        if edge_id in edges or len(edges) >= GRAPH_EDGE_LIMIT * 2:
            return
        edges[edge_id] = {
            "id": edge_id,
            "source": source_id,
            "target": target_id,
            "relation": relation,
            "evidence_source": source,
            "provenance": "real_durable_state",
        }

    projects = [
        item
        for item in context["projects"]
        if project_id is None or item.get("project_id") == project_id
    ]
    project_ids = {item["project_id"] for item in projects}
    for project in projects:
        add_node(
            f"project:{project['project_id']}",
            "project",
            project.get("name") or project["project_id"],
            source="projects",
            linked_project_id=project["project_id"],
            metadata={"description": _safe_text(project.get("description"), 240)},
        )

    tasks = [
        item
        for item in context["tasks"]
        if project_id is None or item.get("project_id") == project_id
    ]
    task_ids = {item["task_id"] for item in tasks}
    for task in tasks:
        task_node = f"task:{task['task_id']}"
        add_node(
            task_node,
            "task",
            task.get("objective") or "Untitled task",
            status=str(task.get("state") or "unknown"),
            source="tasks",
            linked_project_id=task.get("project_id"),
            metadata={
                "task_type": task.get("task_type"),
                "risk_level": str(task.get("risk_level") or "read_only"),
                "updated_at": task.get("updated_at"),
            },
        )
        if task.get("project_id") in project_ids:
            add_edge(
                task_node,
                f"project:{task['project_id']}",
                "belongs_to",
                "tasks.project_id",
            )
        for agent in list(task.get("required_agents") or [])[:12]:
            agent_node = f"agent:{agent}"
            add_node(
                agent_node,
                "agent",
                str(agent).replace("_", " ").title(),
                status="assigned",
                source="tasks.plan.required_agents",
            )
            add_edge(agent_node, task_node, "assigned_to", "tasks.plan.required_agents")
        _add_result_nodes(task, add_node, add_edge)

    for approval in context["approvals"]:
        if approval.get("task_id") not in task_ids:
            continue
        approval_node = f"approval:{approval['approval_id']}"
        add_node(
            approval_node,
            "approval",
            approval.get("proposed_action") or "Pending approval",
            status="pending",
            source="approvals",
            metadata={
                "risk_level": approval.get("risk_level"),
                "reversible": bool(approval.get("reversible")),
                "created_at": approval.get("created_at"),
            },
        )
        add_edge(approval_node, f"task:{approval['task_id']}", "gates", "approvals.task_id")

    for event in context["events"]:
        if project_id is not None and event.get("project_id") != project_id:
            continue
        event_node = f"event:{event['event_id']}"
        add_node(
            event_node,
            "event",
            event.get("title") or "Scheduled event",
            status=str(event.get("status") or "scheduled"),
            source="scheduled_events",
            linked_project_id=event.get("project_id"),
            metadata={"due_at": event.get("due_at"), "event_source": event.get("source")},
        )
        if event.get("project_id") in project_ids:
            add_edge(
                event_node,
                f"project:{event['project_id']}",
                "scheduled_for",
                "scheduled_events.project_id",
            )

    categories = context["memory"].get("categories") or {}
    for memory in context["memory"].get("memories") or []:
        if project_id is not None and memory.get("project_id") != project_id:
            continue
        if not categories.get(memory.get("category"), False):
            continue
        if memory.get("temporal_state") not in {"current", "stale", "conflicted"}:
            continue
        memory_node = f"memory:{memory['memory_id']}"
        node_type, label = _memory_graph_identity(memory)
        add_node(
            memory_node,
            node_type,
            label,
            status=str(memory.get("temporal_state") or "current"),
            source="temporal_memory",
            linked_project_id=memory.get("project_id"),
            metadata={
                "category": memory.get("category"),
                "confidence": memory.get("confidence"),
                "sensitivity": "masked" if memory.get("sensitivity") != "normal" else "normal",
                "requires_resolution": bool(memory.get("requires_resolution")),
            },
        )
        if memory.get("project_id") in project_ids:
            add_edge(
                memory_node,
                f"project:{memory['project_id']}",
                "context_for",
                "memories.project_id",
            )

    for name, integration in context["integrations"].items():
        if not isinstance(integration, dict):
            continue
        add_node(
            f"integration:{name}",
            "application",
            str(name).replace("_", " ").title(),
            status=str(integration.get("state") or "unknown"),
            source="connector_status",
        )

    machine = context["system"].get("machine") or "This Windows device"
    add_node(
        "device:local",
        "device",
        machine,
        status="online",
        source="local_system_telemetry",
    )
    for name in context["integrations"]:
        add_edge(f"integration:{name}", "device:local", "available_on", "connector_status")

    all_nodes = list(nodes.values())
    all_edges = list(edges.values())
    matched_ids: set[str] = set()
    if clean_query:
        query_terms = [part for part in clean_query.casefold().split() if len(part) > 1]
        for node in all_nodes:
            haystack = " ".join(
                (
                    str(node.get("label") or ""),
                    str(node.get("type") or ""),
                    str(node.get("status") or ""),
                    str(node.get("project_id") or ""),
                )
            ).casefold()
            if query_terms and all(term in haystack for term in query_terms):
                matched_ids.add(node["id"])
        selected_ids = _connected_node_ids(matched_ids, all_edges, hops=QUERY_HOPS)
        all_nodes = [item for item in all_nodes if item["id"] in selected_ids]
        all_edges = [
            item
            for item in all_edges
            if item["source"] in selected_ids and item["target"] in selected_ids
        ]

    all_nodes.sort(key=lambda item: (item["type"], item["label"].casefold(), item["id"]))
    all_edges.sort(key=lambda item: (item["relation"], item["source"], item["target"]))
    truncated = len(all_nodes) > GRAPH_NODE_LIMIT or len(all_edges) > GRAPH_EDGE_LIMIT
    all_nodes = all_nodes[:GRAPH_NODE_LIMIT]
    allowed_ids = {item["id"] for item in all_nodes}
    all_edges = [
        item
        for item in all_edges
        if item["source"] in allowed_ids and item["target"] in allowed_ids
    ][:GRAPH_EDGE_LIMIT]
    return {
        "query": clean_query,
        "nodes": all_nodes,
        "edges": all_edges,
        "matched_node_ids": sorted(matched_ids & allowed_ids),
        "private_mode": False,
        "provenance": "real_durable_state",
        "truncated": truncated,
        "coverage": {
            "present_types": sorted({item["type"] for item in all_nodes}),
            "not_loaded": ["email_bodies", "call_transcripts", "external_calendar", "financial_accounts"],
        },
    }


def _add_result_nodes(task, add_node, add_edge) -> None:
    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    document = (result.get("document_action") or {}).get("document") or {}
    if isinstance(document, dict) and (document.get("name") or document.get("format")):
        document_id = f"document:{task['task_id']}"
        add_node(
            document_id,
            "file",
            document.get("name") or f"{document.get('format', 'Document')} output",
            status="observed",
            source="task_result.document_action",
            linked_project_id=task.get("project_id"),
            metadata={"format": document.get("format"), "bytes_read": document.get("bytes_read")},
        )
        add_edge(document_id, f"task:{task['task_id']}", "produced_by", "task_result")


def _memory_graph_identity(memory: dict[str, Any]) -> tuple[str, str]:
    category = str(memory.get("category") or "memory")
    sensitivity = str(memory.get("sensitivity") or "normal")
    subject = _safe_text(memory.get("subject_key"), 160)
    structured = memory.get("structured_data") if isinstance(memory.get("structured_data"), dict) else {}
    if sensitivity != "normal":
        return "memory", f"Protected {category} memory"
    entity_type = str(structured.get("entity_type") or "").casefold()
    explicit_name = _safe_text(structured.get("name") or structured.get("title"), 160)
    if category == "relationship" and entity_type in {"person", "contact"}:
        return "person", explicit_name or subject or "Known person"
    if category == "relationship" and entity_type in {"company", "organisation", "organization"}:
        return "organisation", explicit_name or subject or "Known organisation"
    if category == "decision":
        return "decision", subject or "Recorded decision"
    if category == "research":
        return "research", subject or "Research memory"
    if category == "procedural":
        return "skill", subject or "Recorded procedure"
    return "memory", subject or f"{category.title()} memory"


def _connected_node_ids(seed_ids: set[str], edges: list[dict[str, Any]], *, hops: int) -> set[str]:
    if not seed_ids:
        return set()
    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge["source"], set()).add(edge["target"])
        adjacency.setdefault(edge["target"], set()).add(edge["source"])
    selected = set(seed_ids)
    queue = deque((node_id, 0) for node_id in seed_ids)
    while queue:
        node_id, depth = queue.popleft()
        if depth >= hops:
            continue
        for neighbour in adjacency.get(node_id, set()):
            if neighbour in selected:
                continue
            selected.add(neighbour)
            queue.append((neighbour, depth + 1))
    return selected


def _build_attention(
    context: dict[str, Any],
    *,
    project_id: str | None,
    private: bool,
    focus_mode: bool,
    now: datetime,
) -> dict[str, Any]:
    if private:
        system_items = _system_attention_items(context["system"], focus_mode=focus_mode)
        return {
            "items": system_items,
            "risks": system_items,
            "opportunities": [],
            "counts": {
                level: sum(item["level"] == level for item in system_items) for level in _LEVELS
            },
            "delivery_counts": {
                delivery: sum(item["delivery"] == delivery for item in system_items)
                for delivery in (
                    "INTERRUPT NOW",
                    "NEXT BRIEFING",
                    "PASSIVE NOTIFICATION",
                    "LOG ONLY",
                )
            },
            "focus_mode": focus_mode,
            "private_mode": True,
            "suppressed_detail": True,
        }

    tasks = _project_items(context["tasks"], project_id)
    task_ids = {item["task_id"] for item in tasks}
    events = _project_items(context["events"], project_id)
    approvals = [
        item for item in context["approvals"] if not project_id or item.get("task_id") in task_ids
    ]
    items: list[dict[str, Any]] = []

    for approval in approvals:
        created = _parse_datetime(approval.get("created_at")) or now
        age_hours = max(0.0, (now - created).total_seconds() / 3600)
        risk = str(approval.get("risk_level") or "controlled_write").casefold()
        base = {
            "read_only": (52, 35, 45),
            "controlled_write": (72, 48, 70),
            "sensitive": (82, 55, 85),
            "critical": (92, 70, 96),
        }.get(risk, (68, 45, 68))
        urgency = min(95, base[1] + int(age_hours / 12) * 5)
        items.append(
            _attention_item(
                item_id=f"approval:{approval['approval_id']}",
                kind="approval",
                title=f"Approval required: {approval.get('proposed_action') or 'review action'}",
                detail=f"Target: {_safe_text(approval.get('target') or 'unspecified', 120)}",
                evidence_ids=[approval["approval_id"], approval.get("task_id")],
                source="approvals",
                importance=base[0],
                urgency=urgency,
                consequence=base[2],
                current_focus=75 if approval.get("task_id") in task_ids else 45,
                interruption_cost=25,
                deadline=None,
                focus_mode=focus_mode,
            )
        )

    scheduled = [item for item in events if item.get("status") == "scheduled"]
    for event in scheduled:
        due = _parse_datetime(event.get("due_at"))
        if due is None:
            continue
        hours = (due - now).total_seconds() / 3600
        if hours < 0:
            factors = (95, 100, 92, 80, 12)
            title = f"Overdue: {event.get('title') or 'scheduled event'}"
        elif hours <= 2:
            factors = (90, 92, 82, 78, 16)
            title = f"Due within two hours: {event.get('title') or 'scheduled event'}"
        elif hours <= 24:
            factors = (76, 76, 66, 70, 25)
            title = f"Due today: {event.get('title') or 'scheduled event'}"
        elif hours <= 168:
            factors = (58, 40, 50, 52, 35)
            title = f"Upcoming: {event.get('title') or 'scheduled event'}"
        else:
            continue
        items.append(
            _attention_item(
                item_id=f"event:{event['event_id']}",
                kind="deadline",
                title=title,
                detail=f"Scheduled for {due.astimezone().strftime('%a %d %b, %H:%M %Z')}",
                evidence_ids=[event["event_id"]],
                source="scheduled_events",
                importance=factors[0],
                urgency=factors[1],
                consequence=factors[2],
                current_focus=factors[3],
                interruption_cost=factors[4],
                deadline=due.isoformat(),
                focus_mode=focus_mode,
            )
        )

    gated_task_ids = {item.get("task_id") for item in approvals}
    for task in tasks:
        state = str(task.get("state") or "unknown")
        if state not in FAILED_STATES and not (
            state == "awaiting_approval" and task.get("task_id") not in gated_task_ids
        ):
            continue
        risk = str(task.get("risk_level") or "read_only").casefold()
        consequence = 82 if risk in {"sensitive", "critical"} else 68
        items.append(
            _attention_item(
                item_id=f"task:{task['task_id']}",
                kind="mission_risk",
                title=f"Mission {state}: {task.get('objective') or 'unnamed objective'}",
                detail=_task_failure_reason(task) or "Review recorded task evidence before retrying.",
                evidence_ids=[task["task_id"]],
                source="tasks",
                importance=74,
                urgency=58 if state == "failed" else 50,
                consequence=consequence,
                current_focus=68,
                interruption_cost=30,
                deadline=None,
                focus_mode=focus_mode,
            )
        )

    memory = context["memory"]
    unresolved = memory.get("conflicts") or []
    if unresolved:
        items.append(
            _attention_item(
                item_id="memory:unresolved_conflicts",
                kind="memory_risk",
                title=f"{len(unresolved)} memory conflict(s) need an explicit decision",
                detail="AURIS will not silently choose between conflicting assertions.",
                evidence_ids=[item.get("conflict_id") for item in unresolved[:20]],
                source="memory_conflicts",
                importance=72,
                urgency=38,
                consequence=72,
                current_focus=44,
                interruption_cost=35,
                deadline=None,
                focus_mode=focus_mode,
            )
        )
    stale_count = int((memory.get("summary") or {}).get("stale") or 0)
    if stale_count:
        items.append(
            _attention_item(
                item_id="memory:stale",
                kind="memory_maintenance",
                title=f"Verify {stale_count} stale memory record(s)",
                detail="Stale records remain labelled and are not treated as current facts.",
                evidence_ids=[],
                source="temporal_memory",
                importance=45,
                urgency=24,
                consequence=54,
                current_focus=25,
                interruption_cost=40,
                deadline=None,
                focus_mode=focus_mode,
            )
        )

    items.extend(_system_attention_items(context["system"], focus_mode=focus_mode))
    items.extend(_integration_attention_items(context["integrations"], focus_mode=focus_mode))
    opportunities = _opportunity_items(tasks, scheduled, focus_mode=focus_mode, now=now)
    items.extend(opportunities)
    items.sort(key=lambda item: (-item["score"], item["title"].casefold(), item["id"]))
    counts = {level: sum(item["level"] == level for item in items) for level in _LEVELS}
    delivery_counts = {
        delivery: sum(item["delivery"] == delivery for item in items)
        for delivery in ("INTERRUPT NOW", "NEXT BRIEFING", "PASSIVE NOTIFICATION", "LOG ONLY")
    }
    risks = [item for item in items if item["kind"] != "opportunity"]
    return {
        "items": items[:80],
        "risks": risks[:60],
        "opportunities": opportunities[:20],
        "counts": counts,
        "delivery_counts": delivery_counts,
        "focus_mode": focus_mode,
        "private_mode": False,
        "suppressed_detail": False,
        "batched_count": sum(bool(item.get("batched_by_focus")) for item in items),
        "scoring": {
            "factors": ["importance", "urgency", "consequence", "current_focus", "interruption_cost"],
            "policy": "deterministic_advisory_only",
        },
    }


def _attention_item(
    *,
    item_id: str,
    kind: str,
    title: str,
    detail: str,
    evidence_ids: list[Any],
    source: str,
    importance: int,
    urgency: int,
    consequence: int,
    current_focus: int,
    interruption_cost: int,
    deadline: str | None,
    focus_mode: bool,
) -> dict[str, Any]:
    factors = {
        "importance": _factor(importance),
        "urgency": _factor(urgency),
        "consequence": _factor(consequence),
        "current_focus": _factor(current_focus),
        "interruption_cost": _factor(interruption_cost),
    }
    score = round(
        factors["importance"] * 0.30
        + factors["urgency"] * 0.25
        + factors["consequence"] * 0.30
        + factors["current_focus"] * 0.15
        - factors["interruption_cost"] * 0.05,
        1,
    )
    level = _attention_level(score)
    delivery = _delivery_for(level)
    batched = False
    if kind == "opportunity" and delivery == "INTERRUPT NOW":
        delivery = "NEXT BRIEFING"
    if focus_mode and level not in {"CRITICAL", "URGENT", "IMPORTANT"}:
        batched = delivery != "LOG ONLY"
        delivery = "NEXT BRIEFING" if level == "NOTIFY" else "LOG ONLY"
    return {
        "id": item_id,
        "kind": kind,
        "title": _safe_text(title, 220),
        "detail": _safe_text(detail, 320),
        "score": score,
        "level": level,
        "delivery": delivery,
        "deadline": deadline,
        "factors": factors,
        "evidence_ids": [str(item) for item in evidence_ids if item],
        "source": source,
        "provenance": "real_durable_state",
        "batched_by_focus": batched,
        "advisory_only": True,
    }


def _system_attention_items(system: dict[str, Any], *, focus_mode: bool) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    disk_free = _number((system.get("disk") or {}).get("free_gb"))
    if disk_free is not None and disk_free < 20:
        critical = disk_free < 5
        items.append(
            _attention_item(
                item_id="system:storage",
                kind="device_risk",
                title=f"Device storage is low: {disk_free:.1f} GB free",
                detail="Free local storage before large downloads, updates, or model operations.",
                evidence_ids=["local_disk"],
                source="local_system_telemetry",
                importance=94 if critical else 76,
                urgency=92 if critical else 62,
                consequence=92 if critical else 74,
                current_focus=70,
                interruption_cost=18,
                deadline=None,
                focus_mode=focus_mode,
            )
        )
    memory_load = _number((system.get("memory") or {}).get("utilization_percent"))
    if memory_load is not None and memory_load >= 90:
        items.append(
            _attention_item(
                item_id="system:memory_pressure",
                kind="device_risk",
                title=f"Physical memory pressure is {memory_load:.0f}%",
                detail="Active local AI and desktop workloads may become unstable.",
                evidence_ids=["physical_memory"],
                source="local_system_telemetry",
                importance=78,
                urgency=70,
                consequence=72,
                current_focus=72,
                interruption_cost=15,
                deadline=None,
                focus_mode=focus_mode,
            )
        )
    gpu_temp = _number((system.get("gpu") or {}).get("temperature_c"))
    if gpu_temp is not None and gpu_temp >= 88:
        items.append(
            _attention_item(
                item_id="system:gpu_temperature",
                kind="device_risk",
                title=f"GPU temperature is elevated at {gpu_temp:.0f} C",
                detail="Reduce sustained GPU load and verify cooling before continuing heavy inference.",
                evidence_ids=["nvidia_smi"],
                source="local_system_telemetry",
                importance=86,
                urgency=82,
                consequence=86,
                current_focus=76,
                interruption_cost=10,
                deadline=None,
                focus_mode=focus_mode,
            )
        )
    return items


def _integration_attention_items(
    integrations: dict[str, Any], *, focus_mode: bool
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for name in ("outlook", "onedrive", "telephony"):
        detail = integrations.get(name) if isinstance(integrations.get(name), dict) else {}
        state = str(detail.get("state") or "not_connected")
        if state in {"connected", "local_sync_connected", "ready"}:
            continue
        items.append(
            _attention_item(
                item_id=f"integration:{name}",
                kind="capability_gap",
                title=f"{name.title()} is {state.replace('_', ' ')}",
                detail="This context is excluded from briefs until the connector is explicitly configured.",
                evidence_ids=[name],
                source="connector_status",
                importance=38 if name != "telephony" else 48,
                urgency=12,
                consequence=38 if name != "telephony" else 52,
                current_focus=20,
                interruption_cost=55,
                deadline=None,
                focus_mode=focus_mode,
            )
        )
    return items


def _opportunity_items(
    tasks: list[dict[str, Any]],
    scheduled: list[dict[str, Any]],
    *,
    focus_mode: bool,
    now: datetime,
) -> list[dict[str, Any]]:
    opportunities: list[dict[str, Any]] = []
    for event in scheduled:
        due = _parse_datetime(event.get("due_at"))
        if due is None:
            continue
        hours = (due - now).total_seconds() / 3600
        if 24 < hours <= 168:
            opportunities.append(
                _attention_item(
                    item_id=f"opportunity:event-prep:{event['event_id']}",
                    kind="opportunity",
                    title=f"Prepare early for {event.get('title') or 'upcoming event'}",
                    detail=f"The recorded event is {max(1, int(hours // 24))} day(s) away.",
                    evidence_ids=[event["event_id"]],
                    source="scheduled_events",
                    importance=58,
                    urgency=38,
                    consequence=52,
                    current_focus=50,
                    interruption_cost=42,
                    deadline=due.isoformat(),
                    focus_mode=focus_mode,
                )
            )
    for task in tasks:
        if task.get("task_type") != "research" or task.get("state") not in FINISHED_STATES:
            continue
        action = ((task.get("result") or {}).get("research_action") or {})
        if not action or action.get("definition_of_done_met"):
            continue
        opportunities.append(
            _attention_item(
                item_id=f"opportunity:research:{task['task_id']}",
                kind="opportunity",
                title=f"Close the evidence gap in {task.get('objective') or 'research mission'}",
                detail="The recorded research ledger did not meet its definition of done.",
                evidence_ids=[task["task_id"]],
                source="task_result.research_action",
                importance=64,
                urgency=30,
                consequence=58,
                current_focus=48,
                interruption_cost=40,
                deadline=None,
                focus_mode=focus_mode,
            )
        )
    opportunities.sort(key=lambda item: (-item["score"], item["title"].casefold()))
    return opportunities[:20]


def _build_daily(
    context: dict[str, Any],
    attention: dict[str, Any],
    *,
    project_id: str | None,
    private: bool,
    now: datetime,
) -> dict[str, Any]:
    tasks = _project_items(context["tasks"], project_id)
    events = _project_items(context["events"], project_id)
    approvals = [
        item
        for item in context["approvals"]
        if project_id is None or item.get("task_id") in {task["task_id"] for task in tasks}
    ]
    scheduled = sorted(
        (item for item in events if item.get("status") == "scheduled"),
        key=lambda item: item.get("due_at") or "",
    )
    if private:
        return {
            "kind": "daily",
            "local_date": now.astimezone().strftime("%A, %d %B %Y"),
            "location": "London, United Kingdom",
            "primary_objective": "Private Session is active",
            "supporting_objectives": [],
            "priorities": [],
            "schedule": [],
            "deadlines": [],
            "risks": attention.get("risks") or [],
            "opportunities": [],
            "approvals": [],
            "active_systems": _active_systems(context, [], [], []),
            "suggested_first_action": "Exit Private Session when durable operational context is needed.",
            "private_mode": True,
            **_external_context_flags(),
        }

    active = [item for item in tasks if item.get("state") in ACTIVE_STATES]
    primary = (
        active[0].get("objective")
        if active
        else scheduled[0].get("title")
        if scheduled
        else "Select the highest-value project objective"
    )
    supporting = [
        item.get("objective")
        for item in active
        if item.get("objective") and item.get("objective") != primary
    ][:2]
    if len(supporting) < 2:
        supporting.extend(
            item.get("title")
            for item in scheduled
            if item.get("title") and item.get("title") != primary and item.get("title") not in supporting
        )
    supporting = supporting[:2]
    priorities = []
    for item in (attention.get("risks") or [])[:4]:
        priorities.append(
            {
                "level": item["level"],
                "title": item["title"],
                "delivery": item["delivery"],
                "evidence_ids": item["evidence_ids"],
            }
        )
    if not priorities:
        priorities.append({"level": "BRIEFING", "title": primary, "delivery": "NEXT BRIEFING"})
    deadlines = [
        item for item in (attention.get("items") or []) if item.get("kind") == "deadline"
    ][:8]
    first_action = (
        f"Review {priorities[0]['title'].rstrip('.').casefold()}."
        if priorities
        else f"Begin {primary}."
    )
    return {
        "kind": "daily",
        "local_date": now.astimezone().strftime("%A, %d %B %Y"),
        "location": "London, United Kingdom",
        "primary_objective": primary,
        "supporting_objectives": supporting,
        "priorities": priorities,
        "schedule": scheduled[:8],
        "deadlines": deadlines,
        "risks": (attention.get("risks") or [])[:8],
        "opportunities": (attention.get("opportunities") or [])[:6],
        "approvals": [
            {
                "approval_id": item["approval_id"],
                "task_id": item.get("task_id"),
                "proposed_action": _safe_text(item.get("proposed_action"), 180),
                "risk_level": item.get("risk_level"),
                "created_at": item.get("created_at"),
            }
            for item in approvals[:8]
        ],
        "active_systems": _active_systems(context, active, approvals, scheduled),
        "attention_counts": attention.get("counts") or {},
        "delivery_counts": attention.get("delivery_counts") or {},
        "suggested_first_action": first_action,
        "private_mode": False,
        **_external_context_flags(),
    }


def _build_evening(
    context: dict[str, Any],
    attention: dict[str, Any],
    *,
    project_id: str | None,
    private: bool,
    now: datetime,
) -> dict[str, Any]:
    if private:
        return {
            "kind": "evening",
            "local_date": now.astimezone().strftime("%A, %d %B %Y"),
            "completed": [],
            "incomplete": [],
            "delay_reasons": [],
            "important_events": [],
            "decisions": [],
            "commitments": [],
            "lessons": [],
            "tomorrow_preparation": [],
            "outstanding_risks": attention.get("risks") or [],
            "private_mode": True,
        }
    tasks = _project_items(context["tasks"], project_id)
    events = _project_items(context["events"], project_id)
    local_date = now.astimezone().date()
    completed = [
        _task_summary(item)
        for item in tasks
        if item.get("state") == "completed" and _same_local_date(item.get("updated_at"), local_date)
    ]
    incomplete = [
        _task_summary(item)
        for item in tasks
        if item.get("state") in ACTIVE_STATES | FAILED_STATES
    ][:20]
    delay_reasons = [
        {"task_id": item["task_id"], "reason": reason}
        for item in tasks
        if item.get("state") in FAILED_STATES
        for reason in [_task_failure_reason(item)]
        if reason
    ][:20]
    memories = context["memory"].get("memories") or []
    decisions = [
        {
            "memory_id": item["memory_id"],
            "subject": _memory_graph_identity(item)[1],
            "status": item.get("temporal_state"),
            "source": "temporal_memory",
        }
        for item in memories
        if item.get("category") == "decision"
        and item.get("sensitivity") == "normal"
        and item.get("category_enabled")
        and _same_local_date(item.get("created_at"), local_date)
    ][:12]
    important_events = [
        {
            "event_id": item["event_id"],
            "title": _safe_text(item.get("title"), 180),
            "status": item.get("status"),
            "due_at": item.get("due_at"),
        }
        for item in events
        if item.get("status") == "delivered" and _same_local_date(item.get("delivered_at"), local_date)
    ][:12]
    tomorrow = local_date + timedelta(days=1)
    tomorrow_events = [
        item
        for item in events
        if item.get("status") == "scheduled" and _same_local_date(item.get("due_at"), tomorrow)
    ]
    lessons = [
        {
            "task_id": item["task_id"],
            "lesson": f"Do not retry until this recorded failure is addressed: {_task_failure_reason(item)}",
            "source": "task_failure_evidence",
        }
        for item in tasks
        if item.get("state") in FAILED_STATES and _task_failure_reason(item)
    ][:10]
    return {
        "kind": "evening",
        "local_date": now.astimezone().strftime("%A, %d %B %Y"),
        "completed": completed[:20],
        "incomplete": incomplete,
        "delay_reasons": delay_reasons,
        "important_events": important_events,
        "decisions": decisions,
        "commitments": [
            {
                "event_id": item["event_id"],
                "title": _safe_text(item.get("title"), 180),
                "due_at": item.get("due_at"),
            }
            for item in tomorrow_events[:12]
        ],
        "lessons": lessons,
        "tomorrow_preparation": [
            {
                "event_id": item["event_id"],
                "title": f"Prepare for {_safe_text(item.get('title'), 160)}",
                "due_at": item.get("due_at"),
                "source": "scheduled_events",
            }
            for item in tomorrow_events[:8]
        ],
        "outstanding_risks": (attention.get("risks") or [])[:10],
        "private_mode": False,
    }


def _active_systems(
    context: dict[str, Any],
    active: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
    scheduled: list[dict[str, Any]],
) -> dict[str, Any]:
    integrations = context["integrations"]
    return {
        "active_tasks": len(active),
        "pending_approvals": len(approvals),
        "scheduled_events": len(scheduled),
        "outlook": (integrations.get("outlook") or {}).get("state", "not_connected"),
        "onedrive": (integrations.get("onedrive") or {}).get("state", "not_connected"),
        "telephony": (integrations.get("telephony") or {}).get("state", "not_connected"),
        "device": {
            "machine": context["system"].get("machine"),
            "disk_free_gb": (context["system"].get("disk") or {}).get("free_gb"),
            "memory_utilization_percent": (context["system"].get("memory") or {}).get(
                "utilization_percent"
            ),
        },
    }


def _external_context_flags() -> dict[str, Any]:
    return {
        "live_weather": "not_connected",
        "external_calendar_loaded": False,
        "mailbox_loaded": False,
        "travel_loaded": False,
        "financial_accounts_loaded": False,
    }


def _project_items(items: list[dict[str, Any]], project_id: str | None) -> list[dict[str, Any]]:
    if project_id is None:
        return list(items)
    return [item for item in items if item.get("project_id") == project_id]


def _task_summary(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "objective": _safe_text(task.get("objective"), 220),
        "state": task.get("state"),
        "project_id": task.get("project_id"),
        "updated_at": task.get("updated_at"),
        "source": "tasks",
    }


def _task_failure_reason(task: dict[str, Any]) -> str | None:
    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    queue: deque[Any] = deque([result])
    visited = 0
    while queue and visited < 80:
        value = queue.popleft()
        visited += 1
        if isinstance(value, dict):
            for key in ("error", "last_error", "failure", "reason"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return _safe_text(candidate, 300)
            queue.extend(value.values())
        elif isinstance(value, list):
            queue.extend(value[:20])
    return None


def _attention_level(score: float) -> str:
    if score >= 88:
        return "CRITICAL"
    if score >= 74:
        return "URGENT"
    if score >= 58:
        return "IMPORTANT"
    if score >= 40:
        return "NOTIFY"
    if score >= 22:
        return "BRIEFING"
    return "LOG"


def _delivery_for(level: str) -> str:
    if level in {"CRITICAL", "URGENT"}:
        return "INTERRUPT NOW"
    if level in {"IMPORTANT", "BRIEFING"}:
        return "NEXT BRIEFING"
    if level == "NOTIFY":
        return "PASSIVE NOTIFICATION"
    return "LOG ONLY"


def _clean_graph_query(query: str) -> str:
    value = " ".join(str(query or "").strip().split())[:200]
    value = re.sub(
        r"(?i)^(?:auris[,:]?\s*)?(?:show|find|give)\s+me\s+(?:everything|all)\s+(?:related|connected)\s+to\s+",
        "",
        value,
    )
    return value.strip(" .?")


def _normalise_now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _same_local_date(value: Any, expected) -> bool:
    parsed = _parse_datetime(value)
    return bool(parsed and parsed.astimezone().date() == expected)


def _factor(value: Any) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_text(value: Any, limit: int) -> str:
    clean = " ".join(str(value or "").split())
    clean = _SECRET_VALUE.sub("[redacted secret]", clean)
    return clean[:limit]
