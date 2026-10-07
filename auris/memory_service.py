from __future__ import annotations

import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from auris.database import (
    DATABASE_PATH,
    create_memory,
    create_memory_conflict,
    delete_memory,
    get_memory,
    get_memory_category_settings,
    get_memory_conflict,
    list_memories,
    list_memory_conflicts,
    list_memory_embeddings,
    list_memory_versions,
    resolve_memory_conflict_record,
    set_memory_category_enabled as persist_memory_category_enabled,
    update_memory,
    upsert_memory_embedding,
)
from auris.model_gateway import (
    generate_embeddings,
    is_loopback_endpoint,
    load_embedding_config,
    load_model_config,
)


MEMORY_CATEGORIES = (
    "profile",
    "working",
    "episodic",
    "project",
    "procedural",
    "relationship",
    "decision",
    "research",
    "device",
    "preference",
)
SOURCE_TYPES = (
    "user_confirmed",
    "directly_observed",
    "verified_document",
    "trusted_tool",
    "agent_inferred",
    "external_unverified",
)
SENSITIVITY_LEVELS = ("normal", "personal", "sensitive", "restricted")
SOURCE_QUALITY = {
    "user_confirmed": 6,
    "directly_observed": 5,
    "verified_document": 4,
    "trusted_tool": 3,
    "agent_inferred": 2,
    "external_unverified": 1,
}
STALE_AFTER_DAYS = {
    "working": 1,
    "device": 7,
    "research": 30,
    "project": 90,
    "relationship": 90,
    "decision": 180,
    "procedural": 180,
    "preference": 180,
    "profile": 365,
    "episodic": 365,
}
SECRET_PATTERNS = (
    r"\b(?:password|passcode|pin)\s*(?:is|=|:)\s*\S+",
    r"\b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|client[_ -]?secret)\s*(?:is|=|:)\s*\S+",
    r"\b(?:bearer|authorization)\s+[a-z0-9._~+/=-]{12,}",
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"\bsk-[a-z0-9_-]{16,}\b",
)


class MemoryValidationError(ValueError):
    pass


def store_memory(
    content: str,
    *,
    category: str = "project",
    project_id: str | None = None,
    subject_key: str | None = None,
    structured_data: dict[str, Any] | None = None,
    source_type: str = "user_confirmed",
    source_reference: str | None = None,
    sensitivity: str = "normal",
    confidence_score: float = 1.0,
    valid_from: str | None = None,
    valid_until: str | None = None,
    environment: str | None = None,
    supersedes: str | None = None,
    source: str = "user",
    reason: str = "explicit memory",
    actor: str = "user",
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    clean_content = _validated_content(content)
    clean_category = _choice(category, MEMORY_CATEGORIES, "memory category")
    settings = get_memory_category_settings(path=path)
    if not settings.get(clean_category, False):
        raise MemoryValidationError(f"The {clean_category} memory category is disabled.")
    clean_source_type = _choice(source_type, SOURCE_TYPES, "memory source type")
    clean_sensitivity = _choice(sensitivity, SENSITIVITY_LEVELS, "memory sensitivity")
    score = _confidence_score(confidence_score)
    clean_structured = _structured_data(clean_category, clean_content, structured_data)
    clean_subject = _subject_key(subject_key) or _derived_subject(clean_category, clean_content, clean_structured)
    clean_environment = _bounded_optional(environment, 80)
    clean_reference = _bounded_optional(source_reference, 500)
    if clean_reference and _contains_secret(clean_reference):
        raise MemoryValidationError("Secret material cannot be used as a memory source reference.")
    clean_valid_from = _iso_datetime(valid_from, "valid_from") or _now()
    clean_valid_until = _iso_datetime(valid_until, "valid_until")
    if clean_category == "working" and clean_valid_until is None:
        clean_valid_until = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    if clean_valid_until and datetime.fromisoformat(clean_valid_until) <= datetime.fromisoformat(clean_valid_from):
        raise MemoryValidationError("Memory expiry must be later than its valid-from time.")

    if supersedes:
        return _store_correction(
            supersedes,
            content=clean_content,
            category=clean_category,
            project_id=project_id,
            subject_key=clean_subject,
            structured_data=clean_structured,
            source_type=clean_source_type,
            source_reference=clean_reference,
            sensitivity=clean_sensitivity,
            confidence_score=score,
            valid_from=clean_valid_from,
            valid_until=clean_valid_until,
            environment=clean_environment,
            source=source,
            reason=reason,
            actor=actor,
            path=path,
        )

    candidates = _subject_candidates(
        clean_category,
        project_id,
        clean_subject,
        clean_environment,
        path=path,
    )
    for candidate in candidates:
        if _same_assertion(candidate, clean_content, clean_structured):
            return {
                "ok": True,
                "memory": enrich_memory(candidate),
                "duplicate": True,
                "conflicts": [],
                "requires_resolution": candidate.get("conflict_state") == "unresolved",
            }

    has_conflict = bool(candidates)
    memory = create_memory(
        clean_content,
        category=clean_category,
        project_id=project_id,
        sensitivity=clean_sensitivity,
        confidence=_confidence_label(score),
        source=source[:80],
        expires_at=clean_valid_until,
        structured_data=clean_structured,
        source_type=clean_source_type,
        source_reference=clean_reference,
        confidence_score=score,
        valid_from=clean_valid_from,
        status="conflicted" if has_conflict else "active",
        subject_key=clean_subject,
        environment=clean_environment,
        conflict_state="unresolved" if has_conflict else "clear",
        reason=reason,
        actor=actor,
        path=path,
    )
    conflicts: list[dict[str, Any]] = []
    for candidate in candidates:
        update_memory(
            candidate["memory_id"],
            {"conflict_state": "unresolved"},
            operation="conflict_detected",
            reason="A contradictory assertion with the same subject and context was stored.",
            actor="memory_guardian",
            path=path,
        )
        conflicts.append(
            create_memory_conflict(
                candidate["memory_id"],
                memory["memory_id"],
                clean_subject or "unspecified",
                "Same category, project, subject and environment contain different assertions.",
                path=path,
            )
        )
    return {
        "ok": True,
        "memory": enrich_memory(get_memory(memory["memory_id"], path=path) or memory),
        "duplicate": False,
        "conflicts": conflicts,
        "requires_resolution": has_conflict,
    }


def correct_memory(
    memory_id: str,
    *,
    content: str,
    reason: str,
    category: str | None = None,
    project_id: str | None = None,
    subject_key: str | None = None,
    structured_data: dict[str, Any] | None = None,
    sensitivity: str | None = None,
    confidence_score: float = 1.0,
    valid_until: str | None = None,
    environment: str | None = None,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    existing = get_memory(memory_id, path=path)
    if existing is None:
        raise MemoryValidationError("Memory not found.")
    clean_reason = " ".join(reason.split()).strip()
    if not clean_reason or len(clean_reason) > 300:
        raise MemoryValidationError("A bounded correction reason is required.")
    return store_memory(
        content,
        category=category or existing["category"],
        project_id=project_id if project_id is not None else existing.get("project_id"),
        subject_key=subject_key if subject_key is not None else existing.get("subject_key"),
        structured_data=structured_data if structured_data is not None else existing.get("structured_data"),
        source_type="user_confirmed",
        sensitivity=sensitivity or existing["sensitivity"],
        confidence_score=confidence_score,
        valid_until=valid_until,
        environment=environment if environment is not None else existing.get("environment"),
        supersedes=memory_id,
        source="memory_correction",
        reason=clean_reason,
        actor="Devansh",
        path=path,
    )


def resolve_memory_conflict(
    conflict_id: str,
    *,
    chosen_memory_id: str | None = None,
    keep_both: bool = False,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    conflict = get_memory_conflict(conflict_id, path=path)
    if conflict is None or conflict["status"] != "unresolved":
        raise MemoryValidationError("The unresolved memory conflict was not found.")
    memory_ids = {conflict["memory_id"], conflict["conflicting_memory_id"]}
    memories = {memory_id: get_memory(memory_id, path=path) for memory_id in memory_ids}
    if any(memory is None for memory in memories.values()):
        raise MemoryValidationError("A conflicting memory no longer exists.")

    if keep_both:
        environments = {str(memory.get("environment") or "").casefold() for memory in memories.values()}
        if "" in environments or len(environments) != 2:
            raise MemoryValidationError(
                "Both memories may remain current only when they have distinct explicit environments."
            )
        for memory_id in memory_ids:
            update_memory(
                memory_id,
                {"status": "active", "verified_at": _now()},
                operation="conflict_resolved",
                reason="Both assertions apply in distinct environments.",
                actor="Devansh",
                path=path,
            )
        resolution = "contextual_both"
        chosen_memory_id = None
    else:
        if chosen_memory_id not in memory_ids:
            raise MemoryValidationError("Choose one of the two conflicting memories.")
        for memory_id in memory_ids:
            fields = {"status": "active" if memory_id == chosen_memory_id else "superseded"}
            if memory_id == chosen_memory_id:
                fields["verified_at"] = _now()
            update_memory(
                memory_id,
                fields,
                operation="conflict_resolved",
                reason="Devansh explicitly selected the current assertion.",
                actor="Devansh",
                path=path,
            )
        resolution = "selected_current"

    resolved = resolve_memory_conflict_record(
        conflict_id,
        resolution,
        chosen_memory_id,
        path=path,
    )
    for memory_id in memory_ids:
        _refresh_conflict_state(memory_id, path=path)
    return {
        "ok": True,
        "conflict": resolved,
        "memories": [enrich_memory(get_memory(memory_id, path=path)) for memory_id in sorted(memory_ids)],
    }


def memory_dashboard(
    *,
    project_id: str | None = None,
    query: str = "",
    category: str | None = None,
    status: str | None = None,
    sensitivity: str | None = None,
    limit: int = 200,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    records = list_memories(
        query=query[:200],
        project_id=project_id,
        category=category,
        status=status,
        sensitivity=sensitivity,
        include_inactive=True,
        include_expired=True,
        limit=max(1, min(int(limit), 500)),
        path=path,
    )
    settings = get_memory_category_settings(path=path)
    memories = [enrich_memory(record, category_settings=settings) for record in records]
    conflicts = _enriched_conflicts(project_id=project_id, status="unresolved", path=path)
    return {
        "memories": memories,
        "conflicts": conflicts,
        "categories": settings,
        "summary": {
            "total": len(memories),
            "current": sum(item["temporal_state"] == "current" for item in memories),
            "stale": sum(item["temporal_state"] == "stale" for item in memories),
            "expired": sum(item["temporal_state"] == "expired" for item in memories),
            "unresolved_conflicts": len(conflicts),
            "disabled_categories": sum(not enabled for enabled in settings.values()),
        },
    }


def memory_history(memory_id: str, *, path: Path = DATABASE_PATH) -> dict[str, Any]:
    memory = get_memory(memory_id, path=path)
    if memory is None:
        raise MemoryValidationError("Memory not found.")
    return {
        "memory": enrich_memory(memory),
        "versions": list_memory_versions(memory_id, path=path),
        "conflicts": [
            item
            for item in _enriched_conflicts(status=None, path=path)
            if memory_id in {item["memory_id"], item["conflicting_memory_id"]}
        ],
    }


def export_memory_archive(
    *, project_id: str | None = None, path: Path = DATABASE_PATH
) -> dict[str, Any]:
    dashboard = memory_dashboard(project_id=project_id, limit=500, path=path)
    histories = {
        memory["memory_id"]: list_memory_versions(memory["memory_id"], limit=200, path=path)
        for memory in dashboard["memories"]
    }
    return {
        "schema_version": 1,
        "exported_at": _now(),
        "project_id": project_id,
        "memories": dashboard["memories"],
        "histories": histories,
        "conflicts": _enriched_conflicts(project_id=project_id, status=None, path=path),
        "categories": dashboard["categories"],
    }


def set_memory_category_enabled(
    category: str, enabled: bool, *, path: Path = DATABASE_PATH
) -> dict[str, bool]:
    clean_category = _choice(category, MEMORY_CATEGORIES, "memory category")
    return persist_memory_category_enabled(clean_category, enabled, path=path)


def delete_memory_record(memory_id: str, *, path: Path = DATABASE_PATH) -> bool:
    return delete_memory(memory_id, path=path)


def enrich_memory(
    memory: dict[str, Any] | None,
    *,
    category_settings: dict[str, bool] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if memory is None:
        return {}
    enriched = dict(memory)
    current_time = now or datetime.now(timezone.utc)
    expires_at = _parsed_datetime(memory.get("expires_at"))
    verified_at = _parsed_datetime(memory.get("verified_at")) or _parsed_datetime(memory.get("created_at"))
    if expires_at and expires_at <= current_time:
        temporal_state = "expired"
    elif memory.get("status") not in {"active", "conflicted"}:
        temporal_state = str(memory.get("status"))
    elif verified_at and current_time - verified_at > timedelta(days=STALE_AFTER_DAYS.get(memory["category"], 90)):
        temporal_state = "stale"
    else:
        temporal_state = "current"
    settings = category_settings or {category: True for category in MEMORY_CATEGORIES}
    enriched["temporal_state"] = temporal_state
    enriched["category_enabled"] = bool(settings.get(memory["category"], False))
    enriched["requires_resolution"] = memory.get("conflict_state") == "unresolved"
    return enriched


def effective_memories(
    *, project_id: str | None, limit: int = 200, path: Path = DATABASE_PATH
) -> list[dict[str, Any]]:
    settings = get_memory_category_settings(path=path)
    records = list_memories(project_id=project_id, limit=limit, path=path)
    return [
        item
        for item in (enrich_memory(record, category_settings=settings) for record in records)
        if item["category_enabled"] and item["temporal_state"] in {"current", "stale"}
    ]


def memory_context_lines(
    query: str, *, project_id: str | None, limit: int = 12, path: Path = DATABASE_PATH
) -> list[str]:
    memories = semantic_search_memories(query, project_id=project_id, limit=limit, path=path)
    lines: list[str] = []
    for memory in memories:
        if not _safe_for_model_context(memory):
            continue
        if memory.get("requires_resolution"):
            prefix = "UNRESOLVED MEMORY CONFLICT; ask Devansh before relying on this"
        elif memory.get("temporal_state") == "stale":
            prefix = "STALE MEMORY; verify before consequential use"
        else:
            prefix = f"{memory['category']} memory"
        context = f" ({memory['environment']})" if memory.get("environment") else ""
        lines.append(f"{prefix}{context}: {memory['content']}")
    return lines


def index_memory(memory_id: str, *, path: Path = DATABASE_PATH) -> dict[str, Any]:
    memory = get_memory(memory_id, path=path)
    if memory is None:
        return {"ok": False, "error": "Memory not found."}
    vectors, model, duration_ms = generate_embeddings([f"search_document: {memory['content']}"])
    upsert_memory_embedding(memory_id, model, vectors[0], path=path)
    return {
        "ok": True,
        "memory_id": memory_id,
        "model": model,
        "dimensions": len(vectors[0]),
        "duration_ms": duration_ms,
    }


def semantic_search_memories(
    query: str,
    *,
    project_id: str | None,
    limit: int = 12,
    path: Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    memories = effective_memories(project_id=project_id, limit=200, path=path)
    if not memories or not query.strip():
        return memories[:limit]

    config = load_embedding_config()
    memory_ids = [memory["memory_id"] for memory in memories]
    stored = list_memory_embeddings(memory_ids, path=path)
    missing = [
        memory
        for memory in memories
        if memory["memory_id"] not in stored
        or stored[memory["memory_id"]]["model"] != config.model
    ]
    if missing:
        vectors, model, _ = generate_embeddings(
            [f"search_document: {memory['content']}" for memory in missing]
        )
        for memory, vector in zip(missing, vectors, strict=True):
            upsert_memory_embedding(memory["memory_id"], model, vector, path=path)
            stored[memory["memory_id"]] = {
                "memory_id": memory["memory_id"],
                "model": model,
                "dimensions": len(vector),
                "vector": vector,
            }

    query_vectors, _, _ = generate_embeddings([f"search_query: {query}"])
    query_vector = query_vectors[0]
    ranked: list[dict[str, Any]] = []
    for memory in memories:
        embedding = stored.get(memory["memory_id"])
        if not embedding or len(embedding["vector"]) != len(query_vector):
            continue
        similarity = _cosine_similarity(query_vector, embedding["vector"])
        penalty = 0.08 if memory["temporal_state"] == "stale" else 0.0
        penalty += 0.15 if memory["requires_resolution"] else 0.0
        ranked.append(
            {
                **memory,
                "similarity": round(similarity, 6),
                "retrieval_score": round(similarity - penalty, 6),
                "embedding_model": embedding["model"],
            }
        )
    ranked.sort(key=lambda item: item["retrieval_score"], reverse=True)
    return ranked[: max(1, min(int(limit), 50))]


def _store_correction(
    supersedes: str,
    *,
    content: str,
    category: str,
    project_id: str | None,
    subject_key: str | None,
    structured_data: dict[str, Any],
    source_type: str,
    source_reference: str | None,
    sensitivity: str,
    confidence_score: float,
    valid_from: str,
    valid_until: str | None,
    environment: str | None,
    source: str,
    reason: str,
    actor: str,
    path: Path,
) -> dict[str, Any]:
    previous = get_memory(supersedes, path=path)
    if previous is None:
        raise MemoryValidationError("The memory being corrected no longer exists.")
    if previous.get("status") not in {"active", "conflicted"}:
        raise MemoryValidationError("Only a current or conflicted memory can be corrected.")
    replacement = create_memory(
        content,
        category=category,
        project_id=project_id,
        sensitivity=sensitivity,
        confidence=_confidence_label(confidence_score),
        source=source[:80],
        expires_at=valid_until,
        structured_data=structured_data,
        source_type=source_type,
        source_reference=source_reference,
        confidence_score=confidence_score,
        valid_from=valid_from,
        status="active",
        supersedes=supersedes,
        subject_key=subject_key,
        environment=environment,
        reason=reason,
        actor=actor,
        path=path,
    )
    update_memory(
        supersedes,
        {"status": "superseded", "conflict_state": "clear"},
        operation="superseded",
        reason=reason,
        actor=actor,
        path=path,
    )
    for conflict in list_memory_conflicts(status="unresolved", limit=200, path=path):
        if supersedes in {conflict["memory_id"], conflict["conflicting_memory_id"]}:
            resolve_memory_conflict_record(
                conflict["conflict_id"],
                "corrected",
                replacement["memory_id"],
                path=path,
            )
            other_id = (
                conflict["conflicting_memory_id"]
                if conflict["memory_id"] == supersedes
                else conflict["memory_id"]
            )
            update_memory(
                other_id,
                {"status": "superseded", "conflict_state": "clear"},
                operation="conflict_resolved",
                reason="Devansh supplied an explicit corrected assertion.",
                actor=actor,
                path=path,
            )
    return {
        "ok": True,
        "memory": enrich_memory(replacement),
        "superseded_memory_id": supersedes,
        "duplicate": False,
        "conflicts": [],
        "requires_resolution": False,
    }


def _subject_candidates(
    category: str,
    project_id: str | None,
    subject_key: str | None,
    environment: str | None,
    *,
    path: Path,
) -> list[dict[str, Any]]:
    if not subject_key:
        return []
    records = list_memories(
        project_id=project_id,
        category=category,
        include_inactive=False,
        include_expired=False,
        limit=500,
        path=path,
    )
    return [
        item
        for item in records
        if item.get("project_id") == project_id
        and str(item.get("subject_key") or "").casefold() == subject_key.casefold()
        and (
            not item.get("environment")
            or not environment
            or str(item.get("environment")).casefold() == str(environment).casefold()
        )
    ]


def _enriched_conflicts(
    *,
    project_id: str | None = None,
    status: str | None,
    path: Path,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for conflict in list_memory_conflicts(status=status, limit=200, path=path):
        left = get_memory(conflict["memory_id"], path=path)
        right = get_memory(conflict["conflicting_memory_id"], path=path)
        if left is None or right is None:
            continue
        if project_id is not None and left.get("project_id") != project_id and right.get("project_id") != project_id:
            continue
        results.append(
            {
                **conflict,
                "memory": enrich_memory(left),
                "conflicting_memory": enrich_memory(right),
                "analysis": _conflict_analysis(left, right),
            }
        )
    return results


def _refresh_conflict_state(memory_id: str, *, path: Path) -> None:
    unresolved = any(
        memory_id in {item["memory_id"], item["conflicting_memory_id"]}
        for item in list_memory_conflicts(status="unresolved", limit=200, path=path)
    )
    memory = get_memory(memory_id, path=path)
    if memory is None:
        return
    changes: dict[str, Any] = {"conflict_state": "unresolved" if unresolved else "clear"}
    if not unresolved and memory.get("status") == "conflicted":
        changes["status"] = "active"
    update_memory(
        memory_id,
        changes,
        operation="conflict_state_refreshed",
        reason="Conflict state was recalculated after an explicit resolution.",
        actor="memory_guardian",
        path=path,
    )


def _validated_content(content: str) -> str:
    clean = " ".join(str(content).split()).strip()
    if not clean or len(clean) > 4_000:
        raise MemoryValidationError("Memory content must contain between 1 and 4,000 characters.")
    if _contains_secret(clean):
        raise MemoryValidationError(
            "Passwords, passcodes, API keys, tokens, and private keys cannot be stored in ordinary memory."
        )
    return clean


def _structured_data(
    category: str, content: str, value: dict[str, Any] | None
) -> dict[str, Any]:
    if value is not None and not isinstance(value, dict):
        raise MemoryValidationError("Memory structured data must be an object.")
    data = dict(value or {})
    if category == "decision":
        data = {
            "decision": str(data.get("decision") or content)[:1_000],
            "alternatives": _bounded_string_list(data.get("alternatives")),
            "evidence": _bounded_string_list(data.get("evidence")),
            "assumptions": _bounded_string_list(data.get("assumptions")),
            "risks": _bounded_string_list(data.get("risks")),
            "reason": str(data.get("reason") or "")[:1_000],
            "outcome": str(data.get("outcome") or "")[:1_000] or None,
        }
    encoded = json.dumps(data, ensure_ascii=True, sort_keys=True)
    if _contains_secret(encoded):
        raise MemoryValidationError("Secret material cannot be stored in memory structured data.")
    if len(encoded) > 16_384:
        raise MemoryValidationError("Memory structured data exceeds 16 KiB.")
    return data


def _bounded_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 20:
        raise MemoryValidationError("Decision memory lists may contain at most 20 items.")
    return [" ".join(str(item).split())[:500] for item in value if str(item).strip()]


def _derived_subject(category: str, content: str, structured_data: dict[str, Any]) -> str | None:
    if category == "decision":
        return _subject_key(str(structured_data.get("decision") or "")[:160])
    if category == "relationship" and structured_data.get("contact"):
        return _subject_key(str(structured_data["contact"]))
    if category not in {"profile", "preference", "device", "project"}:
        return None
    match = re.match(r"^(.{2,120}?)(?:\s+is\s+|\s*=\s*|\s*:\s*)(.+)$", content, flags=re.IGNORECASE)
    return _subject_key(match.group(1)) if match else None


def _subject_key(value: str | None) -> str | None:
    clean = " ".join(str(value or "").split()).strip(" .:=").casefold()
    if not clean:
        return None
    if len(clean) > 160:
        raise MemoryValidationError("Memory subject must not exceed 160 characters.")
    return clean


def _choice(value: str, choices: tuple[str, ...], label: str) -> str:
    clean = str(value).strip().casefold().replace(" ", "_")
    if clean not in choices:
        raise MemoryValidationError(f"Unsupported {label}.")
    return clean


def _confidence_score(value: float) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError) as error:
        raise MemoryValidationError("Memory confidence must be a number from 0 to 1.") from error
    if not math.isfinite(score) or score < 0 or score > 1:
        raise MemoryValidationError("Memory confidence must be a number from 0 to 1.")
    return score


def _confidence_label(score: float) -> str:
    if score >= 0.9:
        return "confirmed"
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _iso_datetime(value: str | None, label: str) -> str | None:
    clean = str(value or "").strip()
    if not clean:
        return None
    try:
        parsed = datetime.fromisoformat(clean.replace("Z", "+00:00"))
    except ValueError as error:
        raise MemoryValidationError(f"{label} must be an ISO-8601 timestamp.") from error
    if parsed.tzinfo is None:
        raise MemoryValidationError(f"{label} must include a timezone.")
    return parsed.astimezone(timezone.utc).isoformat()


def _bounded_optional(value: str | None, limit: int) -> str | None:
    clean = " ".join(str(value or "").split()).strip()
    if not clean:
        return None
    if len(clean) > limit:
        raise MemoryValidationError(f"Memory metadata must not exceed {limit} characters.")
    return clean


def _same_assertion(
    memory: dict[str, Any], content: str, structured_data: dict[str, Any]
) -> bool:
    return (
        str(memory.get("content", "")).casefold() == content.casefold()
        and memory.get("structured_data", {}) == structured_data
    )


def _parsed_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _conflict_analysis(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_verified = _parsed_datetime(left.get("verified_at")) or datetime.min.replace(tzinfo=timezone.utc)
    right_verified = _parsed_datetime(right.get("verified_at")) or datetime.min.replace(tzinfo=timezone.utc)
    left_score = SOURCE_QUALITY.get(str(left.get("source_type")), 0)
    right_score = SOURCE_QUALITY.get(str(right.get("source_type")), 0)
    return {
        "source_quality": {
            left["memory_id"]: left_score,
            right["memory_id"]: right_score,
        },
        "more_recent_memory_id": (
            left["memory_id"] if left_verified > right_verified else right["memory_id"]
            if right_verified > left_verified else None
        ),
        "higher_confidence_memory_id": (
            left["memory_id"]
            if left.get("confidence_score", 0) > right.get("confidence_score", 0)
            else right["memory_id"]
            if right.get("confidence_score", 0) > left.get("confidence_score", 0)
            else None
        ),
        "user_confirmed_memory_ids": [
            item["memory_id"]
            for item in (left, right)
            if item.get("source_type") == "user_confirmed"
        ],
        "environments": {
            left["memory_id"]: left.get("environment"),
            right["memory_id"]: right.get("environment"),
        },
        "automatic_resolution": False,
        "required_action": "ask_user",
    }


def _safe_for_model_context(memory: dict[str, Any]) -> bool:
    if memory.get("sensitivity") == "normal":
        return True
    config = load_model_config()
    return config.provider == "ollama" and is_loopback_endpoint(config.endpoint)


def _contains_secret(value: str) -> bool:
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in SECRET_PATTERNS)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
