from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auris.anticipation_service import build_operations_graph
from auris.database import DATABASE_PATH


MAX_ACTIONS = 120
MAX_IMPACTED_ENTITIES = 12


class WorldModelValidationError(ValueError):
    pass


def build_world_model(
    *,
    project_id: str | None = None,
    private: bool = False,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    graph = build_operations_graph(project_id=project_id, private=private, path=path)
    if private:
        return {
            "snapshot_id": None,
            "generated_at": _now(),
            "project_id": project_id,
            "private_mode": True,
            "entities": [],
            "relationships": [],
            "events": [],
            "possible_actions": [],
            "constraints": _constraints(),
            "message": "Operational world-model state is suppressed in Private Session.",
            "provenance": "real_durable_state",
        }

    entities = [
        {
            "id": node["id"],
            "type": node["type"],
            "label": node["label"],
            "state": node["status"],
            "project_id": node.get("project_id"),
            "source": node["source"],
            "provenance": node.get("provenance", "real_durable_state"),
            "attributes": node.get("metadata") or {},
        }
        for node in graph.get("nodes", [])
    ]
    relationships = [
        {
            "id": edge["id"],
            "source": edge["source"],
            "target": edge["target"],
            "relation": edge["relation"],
            "evidence_source": edge["evidence_source"],
            "provenance": edge.get("provenance", "real_durable_state"),
        }
        for edge in graph.get("edges", [])
    ]
    actions = []
    for entity in entities:
        actions.extend(_actions_for(entity))
        if len(actions) >= MAX_ACTIONS:
            actions = actions[:MAX_ACTIONS]
            break
    events = [
        {
            "entity_id": entity["id"],
            "label": entity["label"],
            "state": entity["state"],
            "due_at": entity["attributes"].get("due_at"),
            "source": entity["source"],
        }
        for entity in entities
        if entity["type"] == "event"
    ]
    canonical = {
        "project_id": project_id,
        "entities": entities,
        "relationships": relationships,
        "events": events,
        "possible_actions": actions,
        "constraints": _constraints(),
    }
    snapshot_id = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()[:24]
    return {
        "snapshot_id": snapshot_id,
        "generated_at": _now(),
        "project_id": project_id,
        "private_mode": False,
        **canonical,
        "coverage": graph.get("coverage") or {},
        "truncated": bool(graph.get("truncated")) or len(actions) >= MAX_ACTIONS,
        "provenance": "real_durable_state",
        "model_type": "structured_operational_world_model",
        "learned_model": False,
    }


def simulate_world_action(
    snapshot: dict[str, Any], *, action_id: str, expected_snapshot_id: str
) -> dict[str, Any]:
    if snapshot.get("private_mode"):
        raise WorldModelValidationError("World-model simulation is unavailable in Private Session.")
    if not expected_snapshot_id or expected_snapshot_id != snapshot.get("snapshot_id"):
        raise WorldModelValidationError(
            "The world-model snapshot changed. Refresh it before running this simulation."
        )
    action = next(
        (item for item in snapshot.get("possible_actions", []) if item["action_id"] == action_id),
        None,
    )
    if action is None:
        raise WorldModelValidationError("The requested action is not present in this snapshot.")
    entity = next(
        (item for item in snapshot.get("entities", []) if item["id"] == action["entity_id"]),
        None,
    )
    if entity is None:
        raise WorldModelValidationError("The action target is no longer present in this snapshot.")

    connected = []
    for relationship in snapshot.get("relationships", []):
        if relationship["source"] == entity["id"]:
            connected.append(relationship["target"])
        elif relationship["target"] == entity["id"]:
            connected.append(relationship["source"])
    connected = sorted(set(connected))[:MAX_IMPACTED_ENTITIES]
    return {
        "simulation_id": hashlib.sha256(
            f"{expected_snapshot_id}|{action_id}".encode("utf-8")
        ).hexdigest()[:24],
        "snapshot_id": expected_snapshot_id,
        "action": action,
        "target": {
            "id": entity["id"],
            "type": entity["type"],
            "label": entity["label"],
        },
        "before": {"state": entity["state"]},
        "after": {"state": action["predicted_state"]},
        "impacted_entity_ids": connected,
        "preconditions": action["preconditions"],
        "constraints": action["constraints"],
        "unknowns": _simulation_unknowns(action, connected),
        "confidence": "contractual" if action["risk_level"] == "read_only" else "bounded_inference",
        "executed": False,
        "approval_requested": False,
        "advisory_only": True,
        "verification": (
            "No task, file, application, approval, event, or device state was changed. "
            "Execution must return to the ordinary policy, approval, tool, and verifier pipeline."
        ),
    }


def analyse_causal_intervention(
    snapshot: dict[str, Any],
    *,
    action_id: str,
    expected_snapshot_id: str,
    alternative_action_id: str | None = None,
) -> dict[str, Any]:
    intervention = simulate_world_action(
        snapshot,
        action_id=action_id,
        expected_snapshot_id=expected_snapshot_id,
    )
    alternative = None
    if alternative_action_id:
        if alternative_action_id == action_id:
            raise WorldModelValidationError("The alternative action must differ from the intervention.")
        alternative = simulate_world_action(
            snapshot,
            action_id=alternative_action_id,
            expected_snapshot_id=expected_snapshot_id,
        )

    action = intervention["action"]
    mediator_path = ["policy_authorization"]
    if action["approval_required"]:
        mediator_path.append("human_approval")
    if action["risk_level"] != "read_only":
        mediator_path.extend(["tool_execution", "post_action_verification"])
    else:
        mediator_path.append("read_only_observation")
    causal_nodes = [
        {"id": f"intervention:{action_id}", "type": "intervention", "observed": False},
        {"id": f"state:{action['entity_id']}", "type": "state_variable", "observed": True},
    ]
    causal_edges = [
        {
            "source": f"intervention:{action_id}",
            "target": f"state:{action['entity_id']}",
            "mechanism": "declared_action_transition_contract",
            "identification": "contractual_direct_effect",
        }
    ]
    comparison = {
        "observed_state": intervention["before"]["state"],
        "no_action_state": intervention["before"]["state"],
        "intervention_state": intervention["after"]["state"],
        "alternative_state": alternative["after"]["state"] if alternative else None,
        "changed_assumptions": (
            ["The alternative action is selected instead of the intervention."]
            if alternative
            else []
        ),
    }
    return {
        "analysis_id": hashlib.sha256(
            f"causal|{expected_snapshot_id}|{action_id}|{alternative_action_id or ''}".encode(
                "utf-8"
            )
        ).hexdigest()[:24],
        "snapshot_id": expected_snapshot_id,
        "observation": {
            "entity_id": action["entity_id"],
            "state": intervention["before"]["state"],
            "causal_claim": False,
        },
        "intervention": {
            "notation": f"do({action['action_type']})",
            "action_id": action_id,
            "direct_effect": comparison["intervention_state"],
        },
        "alternative_intervention": (
            {
                "notation": f"do({alternative['action']['action_type']})",
                "action_id": alternative_action_id,
                "direct_effect": comparison["alternative_state"],
            }
            if alternative
            else None
        ),
        "causal_graph": {
            "acyclic": True,
            "nodes": causal_nodes,
            "edges": causal_edges,
            "scope": "immediate declared transition only",
        },
        "mediators": mediator_path,
        "confounders": [
            "unobserved external state",
            "concurrent user or system actions",
            "tool availability and provider behavior",
        ],
        "colliders_assessed": False,
        "downstream_associations": intervention["impacted_entity_ids"],
        "downstream_causal_effects": [],
        "counterfactual": comparison,
        "identifiability": {
            "direct_transition": "identified_by_action_contract",
            "downstream_outcomes": "not_identified",
            "probability_estimate": None,
        },
        "assumptions": [
            "The snapshot remains current until execution begins.",
            "The declared transition contract correctly describes the immediate target-state change.",
        ],
        "uncertainty": [
            "Graph relationships outside the declared transition are associations, not causal edges.",
            "No downstream effect or success probability is inferred without intervention evidence.",
            *intervention["unknowns"],
        ],
        "correlation_treated_as_causation": False,
        "executed": False,
        "advisory_only": True,
        "simulation": intervention,
        "alternative_simulation": alternative,
    }


def _actions_for(entity: dict[str, Any]) -> list[dict[str, Any]]:
    node_type = entity["type"]
    state = str(entity["state"]).casefold()
    specifications: list[tuple[str, str, str, bool, list[str]]] = []
    if node_type == "task":
        specifications.append(("inspect_task", state, "read_only", False, ["task remains present"]))
        if state in {"created", "planning", "running", "verifying", "recovering"}:
            specifications.append(("pause_task", "paused", "controlled_write", True, ["task is active"]))
        elif state in {"failed", "interrupted", "blocked"}:
            specifications.append(("retry_task", "planning", "controlled_write", True, ["failure evidence is retained"]))
    elif node_type == "event":
        specifications.append(("inspect_event", state, "read_only", False, ["event remains present"]))
        if state == "scheduled":
            specifications.append(("cancel_event", "cancelled", "controlled_write", True, ["event is scheduled"]))
    elif node_type == "approval" and state == "pending":
        specifications.extend(
            [
                ("approve_action", "approved", "sensitive", True, ["human authority is present"]),
                ("reject_action", "rejected", "sensitive", True, ["human authority is present"]),
            ]
        )
    elif node_type == "project":
        specifications.append(("focus_project", "focused", "reversible", False, ["project exists"]))
    elif node_type == "application":
        specifications.append(("inspect_integration", state, "read_only", False, ["connector status is current"]))
        if state not in {"connected", "local_sync_connected", "online"}:
            specifications.append(("configure_integration", "configuration_pending", "sensitive", True, ["provider credentials are supplied by the user"]))
    elif node_type == "device":
        specifications.append(("inspect_device_health", state, "read_only", False, ["local telemetry is available"]))
    else:
        specifications.append(("inspect_context", state, "read_only", False, ["entity remains present"]))

    return [
        {
            "action_id": f"action:{entity['id']}:{action_type}",
            "action_type": action_type,
            "entity_id": entity["id"],
            "label": f"{action_type.replace('_', ' ').title()}: {entity['label']}",
            "current_state": entity["state"],
            "predicted_state": predicted_state,
            "risk_level": risk_level,
            "approval_required": approval_required,
            "preconditions": preconditions,
            "constraints": ["simulation_only", "fresh_snapshot_required", "ordinary_policy_applies_to_execution"],
            "executable": False,
        }
        for action_type, predicted_state, risk_level, approval_required, preconditions in specifications
    ]


def _constraints() -> list[dict[str, Any]]:
    return [
        {"id": "no_side_effects", "rule": "Simulation cannot execute tools or mutate durable state."},
        {"id": "fresh_snapshot", "rule": "The supplied snapshot identifier must match current durable state."},
        {"id": "approval_boundary", "rule": "Simulation never grants approval or bypasses user authority."},
        {"id": "policy_boundary", "rule": "Every real action must re-enter policy, authorization, and verification."},
        {"id": "no_probability_invention", "rule": "No probability is emitted without empirical data and provenance."},
    ]


def _simulation_unknowns(action: dict[str, Any], connected: list[str]) -> list[str]:
    unknowns = [
        "External state may change after this snapshot.",
        "The simulation does not predict unobserved human or provider behavior.",
    ]
    if action["risk_level"] != "read_only":
        unknowns.append("Execution outcome depends on a fresh tool-specific verification step.")
    if connected:
        unknowns.append("Only directly connected entities are included in the bounded impact set.")
    return unknowns


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
