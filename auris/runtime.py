from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auris.audit import record_event
from auris.capabilities import capability_registry, capability_summary, collect_capability_observations
from auris.anticipation_service import build_operations_intelligence
from auris.application_state import (
    application_state_dashboard,
    continuation_approval_details,
    match_application_state_command,
    record_browser_application_state,
    resolve_browser_continuation,
)
from auris.browser_agent import (
    browser_approval_details,
    build_browser_device_action,
    execute_browser_action,
    match_browser_command,
)
from auris.coding_agent import (
    execute_coding_command,
    is_trusted_coding_root,
    match_coding_command,
)
from auris.codex_workspace_agent import (
    apply_codex_workspace_change,
    codex_cli_status,
    prepare_codex_workspace_change,
    codex_approval_details,
    discard_codex_workspace_change,
)
from auris.communications_agent import (
    communication_approval_details,
    execute_communication_request,
    match_communication_command,
)
from auris.database import (
    append_message,
    create_approval,
    DATABASE_PATH,
    ensure_conversation,
    get_control_state,
    get_conversation,
    get_project,
    get_task,
    get_workflow_run,
    list_messages,
    list_workflow_runs,
    register_managed_project,
    save_task,
    save_decision_case,
    set_application_state_status,
    set_control_state,
    update_workflow_checkpoint,
    update_workflow_state,
    update_task_state,
)
from auris.decision_intelligence import analyse_decision, match_decision_command
from auris.device_agent import (
    contextual_device_command,
    execute_device_action,
    match_device_command,
    match_device_commands,
    unmatched_device_message,
)
from auris.device_fabric import authorize_local_device_action
from auris.document_agent import match_document_command, run_document_request
from auris.file_agent import execute_file_search, match_file_search
from auris.event_engine import parse_reminder, schedule_reminder
from auris.proactive_agent import METRIC_LABELS, execute_watch_command, parse_watch_command
from auris.interaction_agent import (
    build_typing_device_action,
    execute_typing_request,
    match_typing_command,
    typing_approval_details,
)
from auris.model_gateway import generate_reply
from auris.memory_service import (
    MemoryValidationError,
    effective_memories,
    index_memory,
    memory_context_lines,
    semantic_search_memories,
    store_memory,
)
from auris.privacy import minimise_persisted_result
from auris.project_agent import match_project_open_command, resolve_project_open_action
from auris.schemas import RiskLevel, TaskState
from auris.screen_context import analyse_current_screen
from auris.research_agent import run_research
from auris.repair_agent import (
    apply_test_repair,
    discard_test_repair,
    repair_approval_details,
)
from auris.supervisor import create_task_plan
from auris.system_status import collect_system_status
from auris.ui_automation import (
    build_ui_control_action,
    execute_ui_control_request,
    match_ui_control_command,
    ui_control_approval_details,
)
from auris.verification import build_verification_report
from auris.workflow_engine import (
    execute_workflow,
    mark_workflow_terminal,
    mark_workflow_waiting,
    prepare_workflow,
)
from auris.workspace_service import build_daily_brief
from auris.work_product_agent import execute_work_product, match_work_product_command
from auris.voice_turns import VOICE_TURNS


SUPPORTED_MODES = {
    "command",
    "discussion",
    "research",
    "coding",
    "learning",
    "private",
    "presentation",
}
_CODEX_MISSION_SLOT = threading.BoundedSemaphore(1)


@dataclass(frozen=True)
class CommandContext:
    project_id: str | None = "auris-one"
    mode: str = "command"
    private: bool = False
    conversation_id: str = "auris-primary"
    voice_turn_id: str | None = None


@dataclass(frozen=True)
class MemoryCommand:
    operation: str
    content: str = ""
    query: str = ""
    category: str = "project"
    subject_key: str | None = None


def process_command(command: str, context: CommandContext) -> dict[str, Any]:
    if context.voice_turn_id and not VOICE_TURNS.claim(
        context.voice_turn_id, command, private=context.private or context.mode == "private"
    ):
        return {"ok": False, "error": "Voice input expired, changed, or was already executed. Please repeat the command."}
    try:
        response = _process_command(command, context)
    except Exception:
        VOICE_TURNS.finished(context.voice_turn_id, {"ok": False})
        raise
    VOICE_TURNS.finished(context.voice_turn_id, response)
    return response


def _process_command(command: str, context: CommandContext) -> dict[str, Any]:
    control_intent = _control_intent(command)
    if control_intent is not None:
        return _process_control_command(command, context, control_intent)

    control = get_control_state()
    if control["stopped"]:
        return {
            "ok": False,
            "error": "AURIS emergency stop is active. Resume the core before issuing commands.",
            "control": control,
        }

    mode = context.mode if context.mode in SUPPORTED_MODES else "command"
    private = context.private or mode == "private"
    project_id = None if private else context.project_id
    conversation_id = context.conversation_id or "auris-primary"
    if not private and project_id is None:
        project_id = (get_conversation(conversation_id) or {}).get("project_id") or "auris-one"
    original_command = command
    command, followup_source = _resolve_app_followup(command, conversation_id, project_id, private=private)
    plan = create_task_plan(command)
    plan_data = plan.to_dict()
    VOICE_TURNS.planned(context.voice_turn_id, plan_data)
    if followup_source:
        plan_data["context_resolution"] = {"source_task_id": followup_source, "original_command": original_command, "resolved_command": command}
    if not private:
        ensure_conversation(
            conversation_id,
            project_id=project_id,
            mode=mode,
            title="Primary AURIS conversation",
        )
        append_message(conversation_id, "user", original_command, source="voice_or_text")
    if not private:
        save_task(plan_data, project_id=project_id, mode=mode)
        prepare_workflow(plan_data, command)
    record_event(
        "task.created",
        {
            "command": "[private command]" if private else command,
            "task_id": plan.task_id,
            "task_type": plan.task_type,
            "risk_level": plan.risk_level.value,
            "project_id": project_id,
            "mode": mode,
            "private": private,
        },
    )

    if plan.state == TaskState.BLOCKED:
        result = {
            "message": "I blocked that request before execution because it conflicts with the AURIS security policy.",
            "verification": "Confirmed: no tool or device action was executed.",
        }
        result["verification_report"] = build_verification_report(
            plan_data, result, TaskState.BLOCKED, attempts=1, recovered=False
        )
        if not private:
            update_task_state(plan.task_id, TaskState.BLOCKED.value, result)
            mark_workflow_terminal(plan_data, TaskState.BLOCKED, result)
        _save_assistant_message(conversation_id, result, private, plan.task_id)
        record_event("task.blocked", {"task_id": plan.task_id, "risk_level": plan.risk_level.value})
        return _response(plan_data, result)

    if plan.state == TaskState.AWAITING_APPROVAL:
        if private:
            plan_data["state"] = TaskState.FAILED.value
            result = {
                "message": "Private mode cannot persist the approval record required for that sensitive action. Switch to a standard session to review it.",
                "verification": "Confirmed: no approval record was created and no sensitive action executed.",
            }
            result["verification_report"] = build_verification_report(
                plan_data, result, TaskState.FAILED, attempts=1, recovered=False
            )
            record_event(
                "private.approval_not_persisted",
                {"task_id": plan.task_id, "task_type": plan.task_type},
            )
            return _response(plan_data, result)
        continuation_state = None
        continuation_source = None
        if (
            plan.task_type == "application_state"
            and match_application_state_command(command) == "continue"
        ):
            continuation_state, continuation_source, continuation_error = resolve_browser_continuation(
                project_id
            )
            if continuation_error:
                plan_data["state"] = TaskState.FAILED.value
                result = {
                    "message": continuation_error,
                    "verification": "Confirmed: no browser mission was replayed and no approval was created.",
                }
                result["verification_report"] = build_verification_report(
                    plan_data, result, TaskState.FAILED, attempts=1, recovered=False
                )
                update_task_state(plan.task_id, TaskState.FAILED.value, result)
                mark_workflow_terminal(plan_data, TaskState.FAILED, result)
                _save_assistant_message(conversation_id, result, private, plan.task_id)
                record_event(
                    "application_state.continuation_refused",
                    {"task_id": plan.task_id, "project_id": project_id},
                )
                return _response(plan_data, result)
        target = _target_for(plan.task_type, command)
        data_summary = "The command and task plan. No secrets are included."
        if plan.task_type == "communications":
            target, data_summary = communication_approval_details(command)
        elif plan.task_type == "browser_workflow":
            target, data_summary = browser_approval_details(command)
        elif plan.task_type == "application_state":
            target, data_summary = continuation_approval_details(continuation_state)
        elif plan.task_type == "computer_interaction":
            target, data_summary = (
                ui_control_approval_details(command)
                if match_ui_control_command(command) is not None
                else typing_approval_details(command)
            )
        elif plan.task_type == "computer_operation":
            device_action = match_device_command(command)
            if device_action is not None and device_action.kind == "recycle_file":
                target = str(device_action.path or device_action.label)
                data_summary = (
                    "Move this exact preimage-bound file to the Windows Recycle Bin. "
                    "The original path will disappear, but the item is intended to remain recoverable."
                )
        approval = create_approval(
            task_id=plan.task_id,
            proposed_action=plan.objective,
            target=target,
            data_summary=data_summary,
            risk_level=plan.risk_level.value,
            reversible=plan.risk_level != RiskLevel.CRITICAL,
        )
        result = {
            "message": "The plan is ready, but execution is paused for your approval.",
            "verification": "Confirmed: the sensitive action has not executed.",
        }
        if continuation_state is not None and continuation_source is not None:
            result["application_state_reference"] = {
                "state_id": continuation_state["state_id"],
                "source_task_id": continuation_source["task_id"],
            }
        update_task_state(plan.task_id, TaskState.AWAITING_APPROVAL.value, result)
        record_event(
            "approval.requested",
            {"task_id": plan.task_id, "approval_id": approval["approval_id"]},
        )
        mark_workflow_waiting(plan_data)
        _save_assistant_message(conversation_id, result, private, plan.task_id)
        return _response(plan_data, result, approval=approval)

    product = match_work_product_command(command) if plan.task_type == "work_product" else None
    coding_product = product is not None and product.kind == "code_project" and not _scaffold_only(command)
    if not private and (coding_product or plan.task_type == "coding" and match_coding_command(command) == "codex_workspace"):
        if codex_cli_status(force=True)["ready"]:
            if not _CODEX_MISSION_SLOT.acquire(blocking=False):
                result = {
                    "message": "A Codex coding mission is already running. Wait for its proposal before starting another.",
                    "verification": "Confirmed: this request did not start a second coding worker or change source files.",
                }
                plan_data["state"] = TaskState.FAILED.value
                update_task_state(plan.task_id, TaskState.FAILED.value, result)
                mark_workflow_terminal(plan_data, TaskState.FAILED, result)
                return _response(plan_data, result)
            queued = {
                "message": "I have started the isolated Codex coding mission. You can keep using AURIS while it works; review the result in Missions and Approvals.",
                "verification": "Execution is in progress. No coding outcome has been verified and the selected project is unchanged.",
                "background": True,
                "task_id": plan.task_id,
            }
            plan_data["state"] = TaskState.RUNNING.value
            update_task_state(plan.task_id, TaskState.RUNNING.value, queued)
            update_workflow_state(plan.task_id, TaskState.RUNNING.value)
            VOICE_TURNS.finished(context.voice_turn_id, _response(plan_data, queued))
            worker = threading.Thread(
                target=_background_coding_mission,
                args=(dict(plan_data), command, project_id, mode, conversation_id, context.project_id),
                name=f"auris-codex-{plan.task_id[:8]}", daemon=True,
            )
            try:
                worker.start()
            except RuntimeError:
                _CODEX_MISSION_SLOT.release()
                result = {"message": "The coding worker could not start.", "verification": "No source files changed."}
                plan_data["state"] = TaskState.FAILED.value
                update_task_state(plan.task_id, TaskState.FAILED.value, result)
                mark_workflow_terminal(plan_data, TaskState.FAILED, result)
                return _response(plan_data, result)
            return _response(plan_data, queued)

    return _run_planned_command(plan_data, command, project_id, private, mode, conversation_id, context.project_id)


def _resolve_app_followup(
    command: str, conversation_id: str, project_id: str | None, *, private: bool
) -> tuple[str, str | None]:
    if private or contextual_device_command(command, "AURIS app context") == command:
        return command, None
    messages = list_messages(conversation_id, limit=1)
    if not messages or messages[-1].get("role") != "assistant":
        return command, None
    message = messages[-1]
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(message["created_at"])).total_seconds()
    except (KeyError, ValueError, TypeError):
        return command, None
    if not 0 <= age <= 300:
        return command, None
    task_id = (message.get("metadata") or {}).get("task_id")
    task = get_task(task_id) if task_id else None
    if not task or task.get("state") != "completed" or task.get("project_id") != project_id:
        return command, None
    result = task.get("result") or {}
    actions = result.get("device_actions") or ([result["device_action"]] if result.get("device_action") else [])
    if not actions:
        return command, None
    outcome = actions[-1]
    action = outcome.get("action") or {}
    fabric = outcome.get("command_fabric") or {}
    if not outcome.get("ok") or not fabric.get("signature_verified") or not fabric.get("nonce_claimed"):
        return command, None
    if action.get("kind") not in {"launch_app", "focus_app", "minimize_app", "maximize_app", "restore_app", "app_media"}:
        return command, None
    resolved = contextual_device_command(command, action.get("target"))
    return (resolved, task_id) if resolved != command else (command, None)


def _background_coding_mission(
    plan_data: dict[str, Any], command: str, project_id: str | None,
    mode: str, conversation_id: str, execution_project_id: str | None,
) -> None:
    try:
        _run_planned_command(plan_data, command, project_id, False, mode, conversation_id, execution_project_id)
    except Exception:
        result = {
            "message": "The background coding worker failed before a verified outcome was recorded.",
            "verification": "No successful coding outcome was verified. Check Activity before retrying.",
        }
        update_task_state(plan_data["task_id"], TaskState.FAILED.value, result)
        VOICE_TURNS.finish_task({**plan_data, "state": TaskState.FAILED.value}, result)
        mark_workflow_terminal(plan_data, TaskState.FAILED, result)
        record_event("coding.background_failed", {"task_id": plan_data["task_id"]})
    finally:
        _CODEX_MISSION_SLOT.release()


def _run_planned_command(
    plan_data: dict[str, Any], command: str, project_id: str | None,
    private: bool, mode: str, conversation_id: str, execution_project_id: str | None,
) -> dict[str, Any]:
    task_id = plan_data["task_id"]
    executor = lambda: _execute_supported(
        plan_data,
        command,
        project_id,
        private,
        mode,
        conversation_id,
        execution_project_id=execution_project_id,
    )
    if private:
        result, final_state = executor()
        result["verification_report"] = build_verification_report(
            plan_data, result, final_state, attempts=1, recovered=False
        )
    else:
        result, final_state = execute_workflow(plan_data, executor)
    plan_data["state"] = final_state.value
    VOICE_TURNS.finish_task(plan_data, result)
    if not private:
        update_task_state(task_id, final_state.value, minimise_persisted_result(result))
    if final_state == TaskState.AWAITING_APPROVAL and not private:
        coding_action = result.get("coding_action") or {}
        codex_change = coding_action.get("operation") == "prepare_codex_workspace_change"
        target, data_summary = (
            codex_approval_details(coding_action)
            if codex_change
            else repair_approval_details(coding_action)
        )
        approval = create_approval(
            task_id=task_id,
            proposed_action=(
                "Apply the exact signed Codex workspace diff"
                if codex_change
                else "Apply the exact signed, isolated failing-test repair diff"
            ),
            target=target,
            data_summary=data_summary,
            risk_level=plan_data["risk_level"],
            reversible=True,
        )
        record_event(
            "approval.requested",
            {
                "task_id": task_id,
                "approval_id": approval["approval_id"],
                "proposal_id": (coding_action.get("proposal") or {}).get("proposal_id"),
                "scope": "exact_signed_diff_once",
            },
        )
        _save_assistant_message(conversation_id, result, private, task_id)
        return _response(plan_data, result, approval=approval)
    record_event(
        "task.finished",
        {
            "task_id": task_id,
            "state": final_state.value,
            "verification": "[private result]" if private else result.get("verification", ""),
        },
    )
    _save_assistant_message(conversation_id, result, private, task_id)
    return _response(plan_data, result)


def _execute_supported(
    plan: dict[str, Any],
    command: str,
    project_id: str | None,
    private: bool,
    mode: str,
    conversation_id: str,
    execution_project_id: str | None = None,
) -> tuple[dict[str, Any], TaskState]:
    task_type = plan["task_type"]

    if task_type == "application_state":
        operation = match_application_state_command(command)
        if private:
            return (
                {
                    "message": "Private mode does not expose or persist application checkpoints.",
                    "verification": "Confirmed: no durable application state was read or changed.",
                },
                TaskState.FAILED,
            )
        if operation != "show":
            return (
                {
                    "message": "That application-state request could not be resolved safely.",
                    "verification": "Confirmed: no browser mission was replayed.",
                },
                TaskState.FAILED,
            )
        dashboard = application_state_dashboard(project_id)
        active = dashboard.get("active")
        if active is None:
            message = "There is no interrupted browser mission in this project."
        else:
            checkpoint = active.get("checkpoint") or {}
            message = (
                f"The active browser mission is {active['status']}. "
                f"{checkpoint.get('completed_steps', 0)} of {checkpoint.get('total_steps', 0)} steps were verified."
            )
        return (
            {
                "message": message,
                "verification": "Application state was read from the selected project's durable checkpoint ledger; no page action executed.",
                "application_state": dashboard,
            },
            TaskState.COMPLETED,
        )

    if task_type == "system_status":
        status = collect_system_status()
        return (
            {
                "message": _status_message(status),
                "system_status": status,
                "verification": "Confirmed: device status was collected from this Windows session.",
            },
            TaskState.COMPLETED,
        )

    if task_type == "daily_brief":
        kind = "evening" if "evening" in command.casefold() else "daily"
        brief = build_daily_brief(
            kind=kind,
            project_id=project_id,
            private=private,
        )
        if kind == "evening":
            completed = len(brief.get("completed") or [])
            incomplete = len(brief.get("incomplete") or [])
            risk_count = len(brief.get("outstanding_risks") or [])
            return (
                {
                    "message": (
                        f"Evening debrief: {completed} mission(s) completed today, "
                        f"{incomplete} still incomplete, and {risk_count} outstanding risk signal(s)."
                    ),
                    "evening_debrief": brief,
                    "verification": (
                        "Confirmed: the debrief used recorded AURIS task, event, decision-memory, "
                        "and local-system evidence. Missing mailbox, external calendar, weather, "
                        "travel, and financial context was not invented."
                    ),
                },
                TaskState.COMPLETED,
            )
        priorities = brief.get("priorities", [])
        priority_text = "; ".join(
            f"{item.get('level', 'P2')} {item.get('title')}" for item in priorities[:3]
        )
        return (
            {
                "message": (
                    f"Primary objective: {brief['primary_objective']}. "
                    f"Priorities: {priority_text}. "
                    f"Recommended first action: {brief['suggested_first_action']}"
                ),
                "daily_brief": brief,
                "verification": (
                    "Confirmed: the briefing was assembled from current AURIS missions, approvals, "
                    "local reminders, connector state, and device telemetry. Mailbox, external calendar, "
                    "weather, and travel content were not silently loaded."
                ),
            },
            TaskState.COMPLETED,
        )

    if task_type == "operations_intelligence":
        intelligence = build_operations_intelligence(
            project_id=project_id,
            query=command,
            private=private,
        )

    if task_type == "decision_analysis":
        decision_input = match_decision_command(command) or {
            "objective": command,
            "options": [],
        }
        analysis = analyse_decision(decision_input)
        decision_case = None
        if not private:
            decision_case = save_decision_case(
                decision_input,
                analysis,
                project_id=project_id,
            )
        recommendation = analysis["recommendation"]
        if recommendation["status"] == "supported":
            message = (
                f"The evidence currently supports {recommendation['option']}. "
                f"Confidence is {analysis['confidence']}."
            )
            state = TaskState.COMPLETED
        else:
            missing = analysis["missing_evidence"][:3]
            detail = "; ".join(missing) if missing else recommendation["reason"]
            message = f"The decision remains inconclusive. {detail}"
            state = TaskState.PARTIALLY_COMPLETED
        record_event(
            "decision.analysed",
            {
                "task_id": plan["task_id"],
                "case_id": (decision_case or {}).get("case_id"),
                "project_id": project_id,
                "private": private,
                "recommendation_status": recommendation["status"],
                "confidence": analysis["confidence"],
                "content_stored_in_audit": False,
            },
        )
        return (
            {
                "message": message,
                "decision_analysis": analysis,
                "decision_case": decision_case,
                "verification": analysis["verification"],
            },
            state,
        )
        lowered = command.casefold()
        if "opportunit" in lowered:
            opportunities = intelligence["attention"].get("opportunities") or []
            message = (
                f"I found {len(opportunities)} evidence-backed opportunity signal(s). "
                + (opportunities[0]["title"] if opportunities else "No current opportunity is supported by recorded evidence.")
            )
        elif "graph" in lowered or "related to" in lowered or "connected to" in lowered:
            graph = intelligence["graph"]
            message = (
                f"The operations graph contains {len(graph['nodes'])} related node(s) and "
                f"{len(graph['edges'])} evidence link(s)."
            )
        else:
            attention = intelligence["attention"]
            items = attention.get("items") or []
            interrupts = (attention.get("delivery_counts") or {}).get("INTERRUPT NOW", 0)
            message = (
                f"{len(items)} current attention signal(s); {interrupts} qualify for immediate interruption. "
                + (items[0]["title"] if items else "No current signal requires action.")
            )
        return (
            {
                "message": message,
                "operations_intelligence": intelligence,
                "verification": (
                    "Confirmed: every graph link, risk, and opportunity was derived from durable local "
                    "AURIS evidence or live device telemetry. The result is advisory and executed no action."
                ),
            },
            TaskState.COMPLETED,
        )

    if task_type == "memory":
        request = _memory_command(command)
        if private:
            return (
                {
                    "message": "Private mode is active, so I did not create or retrieve persistent memory.",
                    "verification": "Confirmed: no memory record was written.",
                },
                TaskState.COMPLETED,
            )
        if request.operation == "store":
            try:
                stored = store_memory(
                    request.content,
                    category=request.category,
                    project_id=project_id,
                    subject_key=request.subject_key,
                    source_type="user_confirmed",
                    source="explicit_user_command",
                    reason="Explicit voice or text memory command.",
                    actor="Devansh",
                )
                memory = stored["memory"]
            except MemoryValidationError as error:
                return (
                    {
                        "message": str(error),
                        "verification": "Confirmed: no ordinary memory record was created or overwritten.",
                    },
                    TaskState.FAILED,
                )
            try:
                semantic_index = index_memory(memory["memory_id"])
            except RuntimeError as error:
                semantic_index = {"ok": False, "error": str(error)}
            record_event(
                "memory.stored",
                {
                    "memory_id": memory["memory_id"],
                    "category": memory["category"],
                    "project_id": memory.get("project_id"),
                    "duplicate": stored["duplicate"],
                    "requires_resolution": stored["requires_resolution"],
                },
            )
            if stored["requires_resolution"]:
                message = (
                    "I preserved both assertions and opened a memory conflict. "
                    "I will not choose between them until you resolve it in Memory."
                )
            elif stored["duplicate"]:
                message = "That assertion is already in current memory, so I did not create a duplicate."
            else:
                message = f"{memory['category'].title()} memory saved to the selected context."
            return (
                {
                    "message": message,
                    "memory": memory,
                    "memory_conflicts": stored["conflicts"],
                    "requires_resolution": stored["requires_resolution"],
                    "semantic_index": semantic_index,
                    "verification": (
                        "Confirmed: the typed memory and temporal version exist in the AURIS control database, "
                        "the semantic vector is indexed, and contradictory current facts were not overwritten."
                        if semantic_index.get("ok")
                        else "Confirmed: the typed memory and temporal version exist; semantic indexing is pending because the embedding model was unavailable."
                    ),
                },
                TaskState.COMPLETED,
            )
        if request.operation == "retrieve":
            try:
                memories = semantic_search_memories(
                    request.query,
                    project_id=project_id,
                    limit=8,
                )
            except RuntimeError as error:
                record_event("memory.semantic_unavailable", {"reason": str(error)[:300]})
                memories = effective_memories(project_id=project_id, limit=8)
            conflicts = sum(bool(item.get("requires_resolution")) for item in memories)
            stale = sum(item.get("temporal_state") == "stale" for item in memories)
            summary = "; ".join(item["content"] for item in memories[:4])
            record_event(
                "memory.retrieved",
                {
                    "project_id": project_id,
                    "result_count": len(memories),
                    "conflict_count": conflicts,
                    "stale_count": stale,
                    "content_stored_in_audit": False,
                },
            )
            return (
                {
                    "message": (
                        f"I found {len(memories)} relevant current memories. {summary}"
                        if memories
                        else "I found no current memory for that context."
                    ),
                    "memories": memories,
                    "memory_warning": {
                        "unresolved_conflicts": conflicts,
                        "stale_records": stale,
                        "consequential_use_requires_verification": bool(conflicts or stale),
                    },
                    "verification": (
                        "Confirmed: retrieval excluded expired, superseded, deleted-category, and disabled-category records; "
                        "stale and conflicting evidence is explicitly marked."
                    ),
                },
                TaskState.COMPLETED,
            )
        return (
            {
                "message": "I could not resolve that into a bounded memory store or retrieval request.",
                "verification": "Confirmed: no persistent memory changed.",
            },
            TaskState.FAILED,
        )

    if task_type == "project_operation":
        request = match_project_open_command(command)
        if request is None:
            return (
                {
                    "message": "I could not resolve that into a bounded project-open command.",
                    "verification": "Confirmed: no Windows action was executed.",
                },
                TaskState.FAILED,
            )
        action, project, error = resolve_project_open_action(
            request,
            selected_project_id=execution_project_id or project_id,
        )
        if action is None:
            return (
                {
                    "message": error or "The selected project could not be opened.",
                    "verification": "Confirmed: no Windows action was executed.",
                },
                TaskState.FAILED,
            )
        fabric = authorize_local_device_action(action)
        record_event(
            "device.command_validated",
            {
                "task_id": plan["task_id"],
                "command_id": fabric.get("command_id"),
                "device_id": fabric.get("device_id"),
                "permission_scope": fabric.get("permission_scope"),
                "signature_verified": fabric.get("signature_verified"),
                "nonce_claimed": fabric.get("nonce_claimed"),
                "project_id": (project or {}).get("project_id"),
            },
        )
        if not fabric.get("ok"):
            return (
                {
                    "message": fabric.get("error", "The device command fabric rejected the project action."),
                    "verification": "Confirmed: project launch did not begin because device trust validation failed.",
                    "command_fabric": fabric,
                },
                TaskState.BLOCKED,
            )
        outcome = execute_device_action(action)
        outcome["command_fabric"] = fabric
        outcome["project_id"] = (project or {}).get("project_id")
        outcome["project_name"] = (project or {}).get("name")
        if outcome.get("ok"):
            return (
                {
                    "message": outcome["message"],
                    "verification": outcome["verification"],
                    "project_action": outcome,
                },
                TaskState.COMPLETED,
            )
        return (
            {
                "message": outcome.get("error") or outcome.get("message", "The project did not open."),
                "verification": outcome.get("verification", "The project window was not confirmed."),
                "project_action": outcome,
            },
            TaskState.FAILED,
        )

    if task_type == "computer_operation":
        actions = match_device_commands(command)
        if actions is None:
            return (
                {
                    "message": unmatched_device_message(command),
                    "verification": "Confirmed: no device action was executed.",
                },
                TaskState.FAILED,
            )
        outcomes: list[dict[str, Any]] = []
        for index, action in enumerate(actions, 1):
            fabric = authorize_local_device_action(action)
            record_event(
                "device.command_validated",
                {
                    "task_id": plan["task_id"],
                    "step": index,
                    "step_count": len(actions),
                    "command_id": fabric.get("command_id"),
                    "device_id": fabric.get("device_id"),
                    "permission_scope": fabric.get("permission_scope"),
                    "signature_verified": fabric.get("signature_verified"),
                    "nonce_claimed": fabric.get("nonce_claimed"),
                },
            )
            if not fabric.get("ok"):
                state = TaskState.PARTIALLY_COMPLETED if outcomes else TaskState.BLOCKED
                return (
                    {
                        "message": fabric.get("error", "The local device command fabric rejected the action."),
                        "verification": (
                            f"{len(outcomes)} of {len(actions)} actions completed; the next Windows action was withheld because device trust validation failed."
                            if outcomes
                            else "Confirmed: Windows execution did not begin because device trust validation failed."
                        ),
                        "command_fabric": fabric,
                        "device_actions": outcomes,
                        "device_action": outcomes[-1] if outcomes else None,
                    },
                    state,
                )
            outcome = execute_device_action(action)
            outcome["command_fabric"] = fabric
            outcome["sequence_step"] = index
            outcome["sequence_size"] = len(actions)
            outcomes.append(outcome)
            if not outcome.get("ok"):
                state = TaskState.PARTIALLY_COMPLETED if index > 1 else TaskState.FAILED
                return (
                    {
                        "message": outcome.get("error", "The Windows action failed."),
                        "verification": (
                            f"{index - 1} of {len(actions)} actions completed. Step {index} was attempted but not verified: "
                            + outcome.get("verification", "the requested Windows state was not confirmed.")
                        ),
                        "device_actions": outcomes,
                        "device_action": outcome,
                    },
                    state,
                )
        return (
            {
                "message": " ".join(str(item.get("message") or "").strip() for item in outcomes).strip(),
                "verification": (
                    f"Confirmed: all {len(outcomes)} signed Windows actions completed in order. "
                    + " ".join(str(item.get("verification") or "").strip() for item in outcomes)
                ),
                "device_actions": outcomes,
                "device_action": outcomes[-1],
            },
            TaskState.COMPLETED,
        )

    if task_type == "screen_understanding":
        record_event("screen.capture_started", {"task_id": plan["task_id"], "temporary": True})
        outcome = analyse_current_screen(command)
        record_event(
            "screen.capture_finished",
            {
                "task_id": plan["task_id"],
                "success": bool(outcome.get("ok")),
                "temporary_image_deleted": True,
            },
        )
        if outcome.get("ok"):
            return (outcome, TaskState.COMPLETED)
        return (
            {
                "message": outcome.get("error", "Screen analysis failed."),
                "verification": outcome.get(
                    "verification", "The visible desktop was not successfully analysed."
                ),
            },
            TaskState.FAILED,
        )

    if task_type == "browser_workflow":
        if private:
            return (
                {
                    "message": "Private mode will not use the persistent isolated browser profile. Switch to a standard session for browser automation.",
                    "verification": "Confirmed: the browser worker was not started and no page was accessed.",
                },
                TaskState.FAILED,
            )
        action = match_browser_command(command)
        if action is None:
            return (
                {
                    "message": "I could not resolve that into a safe browser navigation command.",
                    "verification": "Confirmed: no browser request was sent.",
                },
                TaskState.FAILED,
            )
        fabric = authorize_local_device_action(build_browser_device_action(action))
        record_event(
            "browser.command_validated",
            {
                "task_id": plan["task_id"],
                "command_id": fabric.get("command_id"),
                "permission_scope": fabric.get("permission_scope"),
                "signature_verified": fabric.get("signature_verified"),
                "nonce_claimed": fabric.get("nonce_claimed"),
            },
        )
        if not fabric.get("ok"):
            return (
                {
                    "message": fabric.get("error", "The signed browser command was rejected."),
                    "verification": "Confirmed: the isolated browser worker did not execute because device trust validation failed.",
                    "command_fabric": fabric,
                },
                TaskState.BLOCKED,
            )
        outcome = execute_browser_action(action)
        outcome["command_fabric"] = fabric
        application_state = record_browser_application_state(
            plan["task_id"], project_id, action, outcome
        )
        if outcome.get("ok"):
            return (
                {
                    "message": outcome["message"],
                    "verification": outcome["verification"],
                    "browser_action": outcome,
                    "application_state": application_state,
                },
                TaskState.COMPLETED,
            )
        return (
            {
                "message": outcome.get("error", "Browser navigation failed."),
                "verification": outcome.get("verification", "Browser navigation was not confirmed."),
                "browser_action": outcome,
                "application_state": application_state,
            },
            TaskState.FAILED,
        )

    if task_type == "file_workflow":
        search = match_file_search(command)
        if search is not None:
            outcome = execute_file_search(search)
            return (
                {
                    "message": outcome["message"],
                    "verification": outcome["verification"],
                    "file_action": outcome,
                },
                TaskState.COMPLETED,
            )

    if task_type == "work_product":
        if private:
            return (
                {
                    "message": "Private mode cannot persist generated projects or documents. Switch to a standard session to create the artifact.",
                    "verification": "Confirmed: no managed work-product directory or file was created.",
                },
                TaskState.FAILED,
            )
        request = match_work_product_command(command)
        if request is None:
            return (
                {
                    "message": "I could not resolve the requested project or document into a bounded work product.",
                    "verification": "Confirmed: no managed artifact was created.",
                },
                TaskState.FAILED,
            )
        outcome = execute_work_product(request)
        artifact = outcome.get("artifact") or {}
        record_event(
            "artifact.generated",
            {
                "task_id": plan["task_id"],
                "kind": artifact.get("kind"),
                "path": artifact.get("path"),
                "sha256": artifact.get("sha256") or artifact.get("manifest_sha256"),
                "success": bool(outcome.get("ok")),
                "complete": bool(outcome.get("complete")),
                "generated_code_executed": artifact.get("generated_code_executed"),
            },
        )
        result = {
            "message": outcome.get("message") or outcome.get("error", "The work product could not be created."),
            "verification": outcome.get("verification", "No artifact verification was returned."),
            "artifact_action": outcome,
        }
        if outcome.get("ok") and request.kind == "code_project":
            project = register_managed_project(Path(artifact["path"]), str(artifact.get("name") or "AURIS Project"))
            ensure_conversation(conversation_id, project_id=project["project_id"], mode=mode, title="AURIS project conversation")
            result["generated_project"] = project
            if not _scaffold_only(command):
                status = codex_cli_status(force=True)
                if status["ready"]:
                    coding = prepare_codex_workspace_change(
                        request.brief, root=Path(project["root_path"]), project_name=project["name"], trusted_execution=True,
                    )
                    coding["generated_project_id"] = project["project_id"]
                    result["coding_action"] = coding
                    result["message"] = coding.get("message") or coding.get("error", "Custom coding did not finish.")
                    result["verification"] = coding.get("verification", "No custom implementation was verified.")
                    return result, TaskState.AWAITING_APPROVAL if coding.get("ok") else TaskState.FAILED
                result["message"] += " Custom implementation has not run: " + status["detail"]
                result["verification"] += " This is a starter scaffold, not the completed custom logic."
                return result, TaskState.PARTIALLY_COMPLETED
        if outcome.get("research_action"):
            result["research_action"] = outcome["research_action"]
        if outcome.get("ok"):
            return result, TaskState.COMPLETED if outcome.get("complete") else TaskState.PARTIALLY_COMPLETED
        return result, TaskState.FAILED

    if task_type == "research":
        outcome = run_research(command)
        if outcome.get("ok"):
            return (
                {
                    "message": outcome["message"],
                    "verification": outcome["verification"],
                    "research_action": outcome,
                },
                TaskState.COMPLETED
                if outcome.get("definition_of_done_met")
                else TaskState.PARTIALLY_COMPLETED,
            )
        return (
            {
                "message": outcome.get("error", "The research workflow failed."),
                "verification": outcome.get("verification", "No research result was verified."),
                "research_action": outcome,
            },
            TaskState.FAILED,
        )

    if task_type == "document_workflow":
        request = match_document_command(command)
        if request is None:
            return (
                {
                    "message": "I could not resolve the requested local document.",
                    "verification": "Confirmed: no document content was read.",
                },
                TaskState.FAILED,
            )
        outcome = run_document_request(request)
        if outcome.get("ok"):
            return (
                {
                    "message": outcome["message"],
                    "verification": outcome["verification"],
                    "document_action": outcome,
                },
                TaskState.COMPLETED,
            )
        return (
            {
                "message": outcome.get("error", "Document analysis failed."),
                "verification": "The requested document was not successfully analysed.",
                "document_action": outcome,
            },
            TaskState.FAILED,
        )

    if task_type == "coding":
        operation = match_coding_command(command)
        if operation is None:
            return (
                {
                    "message": "Describe a new app with 'build an app that ...', or use 'implement ... in this project' for the selected repository. I can delegate its implementation to Codex and show the exact diff for approval.",
                    "verification": "Confirmed: no source file was changed and no command was executed.",
                },
                TaskState.PARTIALLY_COMPLETED,
            )
        project = get_project(execution_project_id or project_id)
        configured_root = str((project or {}).get("root_path") or "").strip()
        if not project or not configured_root:
            return (
                {
                    "message": "The selected project does not have a registered local root yet.",
                    "verification": "Confirmed: no project directory was scanned and no command was executed.",
                },
                TaskState.FAILED,
            )
        if operation in {"repair_test", "codex_workspace"} and private:
            return (
                {
                    "message": "Private mode cannot create the durable one-time approval required for a source-code change.",
                    "verification": "Confirmed: no coding engine started, no test process ran, and no proposal file or source write began.",
                    "coding_action": {
                        "ok": False,
                        "operation": "prepare_repair",
                        "source_project_modified": False,
                    },
                },
                TaskState.FAILED,
            )
        outcome = execute_coding_command(
            operation,
            root=Path(configured_root),
            project_name=str(project.get("name") or project.get("project_id")),
            trusted_execution=is_trusted_coding_root(configured_root),
            command=command,
        )
        if outcome.get("ok") and outcome.get("approval_required"):
            return (
                {
                    "message": outcome["message"],
                    "verification": outcome["verification"],
                    "coding_action": outcome,
                },
                TaskState.AWAITING_APPROVAL,
            )
        if outcome.get("ok"):
            return (
                {
                    "message": outcome["message"],
                    "verification": outcome["verification"],
                    "coding_action": outcome,
                },
                TaskState.COMPLETED,
            )
        return (
            {
                "message": outcome.get("error") or outcome.get("message", "The coding check failed."),
                "verification": outcome.get("verification", "The coding operation was not verified."),
                "coding_action": outcome,
            },
            TaskState.FAILED,
        )

    if task_type == "reminder":
        if private:
            return (
                {
                    "message": "Private mode does not persist reminders. Switch to a standard session to schedule it.",
                    "verification": "Confirmed: no reminder record was written.",
                },
                TaskState.FAILED,
            )
        request = parse_reminder(command)
        if request is None:
            return (
                {
                    "message": "I could not understand the reminder time.",
                    "verification": "Confirmed: no reminder record was written.",
                },
                TaskState.FAILED,
            )
        event = schedule_reminder(request, project_id=project_id)
        local_due = datetime.fromisoformat(event["due_at"]).astimezone()
        return (
            {
                "message": f"Reminder set for {local_due.strftime('%A %d %B at %H:%M')}: {event['title']}.",
                "verification": "Confirmed: the reminder is persisted and visible to the AURIS event engine.",
                "event": event,
            },
            TaskState.COMPLETED,
        )

    if task_type == "proactive_watch":
        if private:
            return (
                {
                    "message": "Private mode does not persist proactive watches. Switch to a standard session to create or manage them.",
                    "verification": "Confirmed: no durable watch record was changed.",
                },
                TaskState.FAILED,
            )
        request = parse_watch_command(command)
        if request is None:
            return (
                {
                    "message": "I could not resolve that into a bounded predictive watch.",
                    "verification": "Confirmed: no durable watch record was changed.",
                },
                TaskState.FAILED,
            )
        outcome = execute_watch_command(request, project_id=project_id or "auris-one")
        if not outcome.get("ok"):
            return (
                {
                    "message": outcome.get("error", "The proactive watch could not be changed."),
                    "verification": "Confirmed: no matching watch was changed.",
                    "proactive_action": outcome,
                },
                TaskState.FAILED,
            )
        if outcome["operation"] == "list":
            count = len(outcome["watches"])
            message = f"You have {count} proactive watch{'es' if count != 1 else ''} in this project."
        elif outcome["operation"] == "cancel":
            message = f"The {METRIC_LABELS[outcome['watch']['metric']]} watch is disabled."
        else:
            watch = outcome["watch"]
            relation = "at or above" if watch["operator"] == "gte" else "at or below"
            message = (
                f"I will watch {METRIC_LABELS[watch['metric']]} and alert you when it is "
                f"{relation} {watch['threshold']:.0f}. I will not take action automatically."
            )
        return (
            {
                "message": message,
                "verification": "Confirmed: the proactive watch state is durably recorded and advisory-only.",
                "proactive_action": outcome,
            },
            TaskState.COMPLETED,
        )

    if task_type == "communications":
        request = match_communication_command(command)
        if request is None:
            return (
                {
                    "message": "I could not resolve that into a bounded email, calendar, contact, or call operation.",
                    "verification": "Confirmed: no productivity account content was accessed or changed.",
                },
                TaskState.FAILED,
            )
        outcome = execute_communication_request(request)
        if outcome.get("ok"):
            return (
                {
                    "message": outcome["message"],
                    "verification": outcome["verification"],
                    "communications_action": outcome,
                },
                TaskState.PARTIALLY_COMPLETED if request.kind == "send" else TaskState.COMPLETED,
            )
        return (
            {
                "message": outcome.get("error", "The productivity connector failed."),
                "verification": outcome.get("verification", "No productivity result was verified."),
                "communications_action": outcome,
            },
            TaskState.FAILED,
        )

    if task_type == "general_assistance":
        instant = _instant_response(command)
        if instant is not None:
            return (
                {
                    "message": instant,
                    "intelligence": {
                        "provider": "auris_instant_kernel",
                        "model": "deterministic_local",
                        "duration_ms": 0,
                        "route": "instant",
                    },
                    "verification": (
                        "Confirmed: AURIS answered from a deterministic local conversational intent; "
                        "no model wait or device action was required."
                    ),
                },
                TaskState.COMPLETED,
            )
        model_result = _model_response(command, project_id, private, mode, conversation_id)
        if model_result is not None:
            return (
                {
                    "message": model_result["text"],
                    "intelligence": model_result,
                    "verification": (
                        f"Confirmed: response generated by configured {model_result['provider']} "
                        f"model {model_result['model']}; no device action was executed."
                    ),
                },
                TaskState.COMPLETED,
            )
        return (
            {
                "message": _local_response(command),
                "intelligence": {"provider": "deterministic_fallback", "connected": False},
                "verification": "Confirmed: fallback response produced locally because no AI model is connected; no device action was executed.",
            },
            TaskState.COMPLETED,
        )

    return (
        {
            "message": (
                f"I created and policy-checked the {task_type.replace('_', ' ')} plan. "
                "Its execution worker is not connected in this first release, so I stopped after planning."
            ),
            "verification": "Confirmed: the plan is persisted and no unavailable worker was represented as successful.",
        },
        TaskState.PARTIALLY_COMPLETED,
    )


def _response(
    plan: dict[str, Any],
    result: dict[str, Any],
    approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "plan": plan, "result": result}
    if approval is not None:
        payload["approval"] = approval
    if "system_status" in result:
        payload["system_status"] = result["system_status"]
    workflow = get_workflow_run(plan["task_id"])
    if workflow is not None:
        payload["workflow"] = {
            key: value for key, value in workflow.items() if key != "command_text"
        }
    return payload


def execute_approved_task(task: dict[str, Any]) -> tuple[dict[str, Any], TaskState]:
    plan = task.get("plan") or task
    return execute_workflow(plan, lambda: _execute_approved_supported(task))


def _execute_approved_supported(task: dict[str, Any]) -> tuple[dict[str, Any], TaskState]:
    prior_action = (task.get("result") or {}).get("coding_action") or {}
    if task["task_type"] == "coding" or task["task_type"] == "work_product" and prior_action.get("operation") == "prepare_codex_workspace_change":
        proposal_id = str((prior_action.get("proposal") or {}).get("proposal_id") or "")
        project = get_project(prior_action.get("generated_project_id") or task.get("project_id"))
        configured_root = str((project or {}).get("root_path") or "").strip()
        if not proposal_id or not project or not configured_root:
            return (
                {
                    "message": "The approved coding change no longer has a complete signed proposal and project binding.",
                    "verification": "Confirmed: no source file was changed.",
                    "coding_action": {"ok": False, "operation": "apply_coding_change"},
                },
                TaskState.FAILED,
            )
        is_codex_change = prior_action.get("operation") == "prepare_codex_workspace_change"
        if is_codex_change:
            outcome = apply_codex_workspace_change(
                proposal_id,
                root=Path(configured_root),
                trusted_execution=is_trusted_coding_root(configured_root),
            )
        else:
            outcome = apply_test_repair(
                proposal_id,
                root=Path(configured_root),
                trusted_execution=is_trusted_coding_root(configured_root),
            )
        result = {
                "message": outcome.get("message") or outcome.get("error", "The approved repair failed."),
                "verification": outcome.get("verification", "No source repair was verified."),
                "coding_action": outcome,
            }
        if task["task_type"] == "work_product":
            result["generated_project"] = project
            result["message"] += f" Project: {project['root_path']}"
        return result, TaskState.COMPLETED if outcome.get("ok") else TaskState.FAILED
    if task["task_type"] == "computer_interaction":
        typing_request = match_typing_command(task["objective"])
        ui_request = match_ui_control_command(task["objective"])
        if typing_request is not None:
            action, action_error = build_typing_device_action(typing_request)
            execute_interaction = lambda: execute_typing_request(typing_request)
        elif ui_request is not None:
            action, action_error = build_ui_control_action(ui_request)
            execute_interaction = lambda: execute_ui_control_request(ui_request)
        else:
            action, action_error, execute_interaction = None, None, None
        if action is None or execute_interaction is None:
            return (
                {
                    "message": action_error or "The approved interaction could not be resolved or is outside the bounded UI policy.",
                    "verification": "Confirmed: no keyboard input or UI Automation invocation was emitted.",
                },
                TaskState.FAILED,
            )
        fabric = authorize_local_device_action(action)
        record_event(
            "device.command_validated",
            {
                "task_id": task["task_id"],
                "command_id": fabric.get("command_id"),
                "device_id": fabric.get("device_id"),
                "permission_scope": fabric.get("permission_scope"),
                "signature_verified": fabric.get("signature_verified"),
                "nonce_claimed": fabric.get("nonce_claimed"),
                "approved_interaction": True,
            },
        )
        if not fabric.get("ok"):
            return (
                {
                    "message": fabric.get("error", "The signed device fabric rejected the approved interaction."),
                    "verification": "Confirmed: Windows interaction did not begin because device trust validation failed.",
                    "command_fabric": fabric,
                },
                TaskState.BLOCKED,
            )
        outcome = execute_interaction()
        outcome["command_fabric"] = fabric
        if outcome.get("ok"):
            return (
                {
                    "message": outcome["message"],
                    "verification": outcome["verification"],
                    "interaction_action": outcome,
                },
                TaskState.COMPLETED,
            )
        return (
            {
                "message": outcome.get("error", "The approved Windows interaction failed."),
                "verification": outcome.get("verification", "No completed keyboard interaction was verified."),
                "interaction_action": outcome,
            },
            TaskState.FAILED,
        )
    if task["task_type"] == "application_state":
        reference = (task.get("result") or {}).get("application_state_reference") or {}
        state_id = str(reference.get("state_id") or "")
        source_task_id = str(reference.get("source_task_id") or "")
        if not state_id or not source_task_id:
            return (
                {
                    "message": "The approved continuation no longer has an exact checkpoint binding.",
                    "verification": "Confirmed: no browser mission was replayed.",
                },
                TaskState.FAILED,
            )
        state, source_task, continuation_error = resolve_browser_continuation(
            task.get("project_id"), state_id=state_id
        )
        if continuation_error or source_task is None or source_task.get("task_id") != source_task_id:
            return (
                {
                    "message": continuation_error or "The approved checkpoint no longer matches its source mission.",
                    "verification": "Confirmed: the exact checkpoint was revalidated after approval and no browser action executed.",
                },
                TaskState.FAILED,
            )
        request = match_browser_command(source_task["objective"])
        if request is None or request.kind != "workflow":
            return (
                {
                    "message": "The source browser mission can no longer be reconstructed as an exact bounded workflow.",
                    "verification": "Confirmed: no browser mission was replayed.",
                },
                TaskState.FAILED,
            )
        fabric = authorize_local_device_action(build_browser_device_action(request))
        record_event(
            "browser.continuation_validated",
            {
                "task_id": task["task_id"],
                "continued_from_state_id": state_id,
                "command_id": fabric.get("command_id"),
                "permission_scope": fabric.get("permission_scope"),
                "signature_verified": fabric.get("signature_verified"),
                "nonce_claimed": fabric.get("nonce_claimed"),
            },
        )
        if not fabric.get("ok"):
            return (
                {
                    "message": fabric.get("error", "The signed continuation was rejected."),
                    "verification": "Confirmed: the prior checkpoint remains resumable because device trust validation failed before browser execution.",
                    "command_fabric": fabric,
                },
                TaskState.BLOCKED,
            )
        outcome = execute_browser_action(request)
        outcome["command_fabric"] = fabric
        new_state = record_browser_application_state(
            task["task_id"], task.get("project_id"), request, outcome
        )
        set_application_state_status(state_id, "superseded")
        return (
            {
                "message": outcome.get("message") or outcome.get("error", "The continued browser mission failed."),
                "verification": outcome.get("verification", "The continued browser mission was not verified."),
                "browser_action": outcome,
                "application_state": new_state,
                "continued_from": {"state_id": state_id, "task_id": source_task_id},
            },
            TaskState.COMPLETED if outcome.get("ok") else TaskState.FAILED,
        )
    if task["task_type"] == "browser_workflow":
        request = match_browser_command(task["objective"])
        if request is None or request.kind not in {"fill", "click", "workflow"}:
            return (
                {
                    "message": "The approved browser request no longer matches one bounded field, control, or exact multi-step mission.",
                    "verification": "Confirmed: the isolated browser worker did not change the page.",
                },
                TaskState.FAILED,
            )
        fabric = authorize_local_device_action(build_browser_device_action(request))
        record_event(
            "browser.command_validated",
            {
                "task_id": task["task_id"],
                "command_id": fabric.get("command_id"),
                "permission_scope": fabric.get("permission_scope"),
                "signature_verified": fabric.get("signature_verified"),
                "nonce_claimed": fabric.get("nonce_claimed"),
                "approved_browser_interaction": True,
            },
        )
        if not fabric.get("ok"):
            return (
                {
                    "message": fabric.get("error", "The signed browser interaction was rejected."),
                    "verification": "Confirmed: the page was not changed because device trust validation failed.",
                    "command_fabric": fabric,
                },
                TaskState.BLOCKED,
            )
        outcome = execute_browser_action(request)
        outcome["command_fabric"] = fabric
        application_state = record_browser_application_state(
            task["task_id"], task.get("project_id"), request, outcome
        )
        return (
            {
                "message": outcome.get("message") or outcome.get("error", "The approved browser interaction failed."),
                "verification": outcome.get("verification", "No browser page-state change was verified."),
                "browser_action": outcome,
                "application_state": application_state,
            },
            TaskState.COMPLETED if outcome.get("ok") else TaskState.FAILED,
        )
    if task["task_type"] == "computer_operation":
        action = match_device_command(task["objective"])
        if action is None or action.kind != "recycle_file":
            return (
                {
                    "message": "The approved Windows request no longer matches one bounded Recycle Bin action.",
                    "verification": "Confirmed: no filesystem action was executed.",
                },
                TaskState.FAILED,
            )
        fabric = authorize_local_device_action(action)
        record_event(
            "device.command_validated",
            {
                "task_id": task["task_id"],
                "command_id": fabric.get("command_id"),
                "device_id": fabric.get("device_id"),
                "permission_scope": fabric.get("permission_scope"),
                "signature_verified": fabric.get("signature_verified"),
                "nonce_claimed": fabric.get("nonce_claimed"),
                "approved_recycle_action": True,
            },
        )
        if not fabric.get("ok"):
            return (
                {
                    "message": fabric.get("error", "The signed device fabric rejected the approved Recycle Bin action."),
                    "verification": "Confirmed: Windows execution did not begin because device trust validation failed.",
                    "command_fabric": fabric,
                },
                TaskState.BLOCKED,
            )
        outcome = execute_device_action(action)
        outcome["command_fabric"] = fabric
        return (
            {
                "message": outcome.get("message") or outcome.get("error", "The Recycle Bin action failed."),
                "verification": outcome.get("verification", "The exact file removal was not verified."),
                "device_action": outcome,
            },
            TaskState.COMPLETED if outcome.get("ok") else TaskState.FAILED,
        )
    if task["task_type"] == "communications":
        request = match_communication_command(task["objective"])
        if request is None or request.kind not in {"send", "start_call"}:
            return (
                {
                    "message": "The approved communication no longer matches a bounded send or call request.",
                    "verification": "Confirmed: no message was sent and no call was started.",
                },
                TaskState.FAILED,
            )
        outcome = execute_communication_request(request)
        if outcome.get("ok"):
            return (
                {
                    "message": outcome["message"],
                    "verification": outcome["verification"],
                    "communications_action": outcome,
                },
                TaskState.PARTIALLY_COMPLETED,
            )
        return (
            {
                "message": outcome.get("error", "The approved communication failed."),
                "verification": outcome.get("verification", "No external communication was verified."),
                "communications_action": outcome,
            },
            TaskState.FAILED,
        )
    return (
        {
            "message": "Approval recorded. This task does not yet have a resumable execution worker.",
            "verification": "Confirmed: the approval is persisted and no unavailable action was represented as executed.",
        },
        TaskState.PARTIALLY_COMPLETED,
    )


def discard_pending_task_action(task: dict[str, Any] | None) -> bool:
    if not task or task.get("task_type") != "coding":
        return False
    action = (task.get("result") or {}).get("coding_action") or {}
    proposal_id = str((action.get("proposal") or {}).get("proposal_id") or "")
    if not proposal_id:
        return False
    if action.get("operation") == "prepare_codex_workspace_change":
        return discard_codex_workspace_change(proposal_id)
    return discard_test_repair(proposal_id)


def recover_incomplete_workflows(path: Path = DATABASE_PATH) -> dict[str, int]:
    summary = {"recovered": 0, "interrupted": 0}
    incomplete = list_workflow_runs(
        states=("running", "retrying", "verifying", "recovering"), limit=100, path=path
    )
    for workflow in incomplete:
        task = get_task(workflow["task_id"], path=path)
        if task is None:
            update_workflow_state(
                workflow["task_id"], "interrupted", last_error="The task record is missing.", path=path
            )
            summary["interrupted"] += 1
            continue
        can_replay = (
            task.get("risk_level") == RiskLevel.READ_ONLY.value
            and int(workflow["attempts"]) < int(workflow["max_attempts"])
        )
        if not can_replay:
            result = {
                "message": "AURIS detected an interrupted workflow that cannot be replayed safely.",
                "verification": "Confirmed: no sensitive or write operation was replayed after restart; manual review is required.",
                "verification_report": build_verification_report(
                    task.get("plan") or task,
                    {
                        "message": "Manual review is required after interruption.",
                        "verification": "Confirmed: the operation was not replayed.",
                    },
                    TaskState.INTERRUPTED,
                    attempts=max(1, int(workflow["attempts"])),
                    recovered=True,
                ),
            }
            _interrupt_open_checkpoints(task.get("plan") or task, result, path=path)
            update_workflow_state(
                workflow["task_id"],
                TaskState.INTERRUPTED.value,
                last_error="Automatic replay denied by workflow safety policy.",
                path=path,
            )
            update_task_state(workflow["task_id"], TaskState.INTERRUPTED.value, result, path=path)
            record_event(
                "workflow.recovery_blocked",
                {
                    "task_id": workflow["task_id"],
                    "risk_level": task.get("risk_level"),
                    "attempts": workflow["attempts"],
                },
            )
            summary["interrupted"] += 1
            continue
        plan = task.get("plan") or task
        result, state = execute_workflow(
            plan,
            lambda: _execute_supported(
                plan,
                workflow["command_text"],
                task.get("project_id"),
                False,
                task.get("mode", "command"),
                "auris-recovery",
            ),
            recovered=True,
            path=path,
        )
        update_task_state(
            workflow["task_id"],
            state.value,
            minimise_persisted_result(result),
            path=path,
        )
        record_event(
            "workflow.recovered",
            {
                "task_id": workflow["task_id"],
                "state": state.value,
                "attempts": (get_workflow_run(workflow["task_id"], path=path) or workflow)["attempts"],
            },
        )
        summary["recovered"] += 1
    return summary


def _interrupt_open_checkpoints(
    plan: dict[str, Any], result: dict[str, Any], *, path: Path = DATABASE_PATH
) -> None:
    workflow = get_workflow_run(plan["task_id"], path=path)
    if workflow is None:
        return
    for checkpoint in workflow.get("checkpoints", []):
        if checkpoint["state"] in {"pending", "running", "retrying", "verifying"}:
            update_workflow_checkpoint(
                plan["task_id"],
                checkpoint["step_id"],
                "interrupted",
                evidence={
                    "verification": result["verification"],
                    "automatic_replay": False,
                    "content_stored": False,
                },
                path=path,
            )


def _memory_command(command: str) -> MemoryCommand:
    text = command.strip()
    lowered = text.casefold()
    store_prefixes = (
        ("auris, record decision ", "decision"),
        ("record decision ", "decision"),
        ("auris, remember preference ", "preference"),
        ("remember preference ", "preference"),
        ("auris, remember relationship ", "relationship"),
        ("remember relationship ", "relationship"),
        ("auris, remember profile ", "profile"),
        ("remember profile ", "profile"),
        ("auris, remember procedure ", "procedural"),
        ("remember procedure ", "procedural"),
        ("auris, remember that ", "project"),
        ("auris remember that ", "project"),
        ("remember that ", "project"),
        ("remember ", "project"),
        ("save to memory ", "project"),
    )
    for prefix, category in store_prefixes:
        if lowered.startswith(prefix):
            content = text[len(prefix) :].strip(" .")
            subject = None
            explicit_subject = re.match(r"^\[([^\]]{1,160})\]\s*(.+)$", content)
            if explicit_subject:
                subject = explicit_subject.group(1).strip()
                content = explicit_subject.group(2).strip()
            return MemoryCommand("store", content=content, category=category, subject_key=subject)
    retrieval_prefixes = (
        "auris, what do you remember about ",
        "what do you remember about ",
        "auris, recall ",
        "recall ",
        "search memory for ",
        "show memory for ",
    )
    for prefix in retrieval_prefixes:
        if lowered.startswith(prefix):
            return MemoryCommand("retrieve", query=text[len(prefix) :].strip(" ."))
    if "memory" in lowered:
        return MemoryCommand("retrieve", query="")
    return MemoryCommand("unknown")


def _local_response(command: str) -> str:
    text = command.lower()
    if any(word in text for word in ("hello", "hi ", "hey auris", "good morning", "good evening")):
        return "Online, Devansh. The supervised local core is ready. What are we working on?"
    if "who are you" in text or "your name" in text:
        return "I am AURIS: Autonomous Understanding and Reasoning Intelligence System."
    if "what can you do" in text or "help" in text:
        return (
            "I can plan and classify commands, report device health, keep project-scoped memories, "
            "queue approvals, preserve an audit trail, accept push-to-talk input, and stop instantly."
        )
    return (
        "I recorded the request, but a conversational AI model is not connected yet. "
        "Device commands, memory, policy, and system status remain available."
    )


def _scaffold_only(command: str) -> bool:
    return bool(re.search(r"\bscaffold\b|\bstarter\s+(?:template|project)\b", command, re.IGNORECASE))


def _instant_response(command: str) -> str | None:
    clean = " ".join(command.strip().split())
    clean = re.sub(r"(?i)^(?:hey\s+|okay\s+)?auris\s*[,.:]?\s*", "", clean).strip(" .?!")
    lowered = clean.casefold()
    if re.fullmatch(r"(?:hello|hi|hey|good morning|good afternoon|good evening)", lowered):
        return "Online, Devansh. What is the objective?"
    if re.fullmatch(r"(?:are you (?:there|online|ready)|you (?:there|online|ready))", lowered):
        return "Online and ready."
    if re.fullmatch(r"(?:are you listening|can you hear me|listening)", lowered):
        return "Your command reached me."
    if re.fullmatch(r"(?:thanks|thank you|cheers)", lowered):
        return "Of course."
    if re.fullmatch(r"(?:okay|ok|understood|got it)", lowered):
        return "Ready."
    if re.fullmatch(r"(?:goodbye|good night|bye|see you later)", lowered):
        return "Standing by."
    if re.fullmatch(r"(?:who are you|what is your name|what's your name)", lowered):
        return "I am AURIS, the Autonomous Understanding and Reasoning Intelligence System."
    if re.fullmatch(r"(?:what can you do|what are your capabilities|capabilities)", lowered):
        try:
            observations = collect_capability_observations()
        except Exception:
            observations = {}
        return capability_summary(capability_registry(observations))
    if re.fullmatch(r"(?:how are you|how are things)", lowered):
        return "Standing by. What is the objective?"
    if re.fullmatch(r"(?:what time is it|tell me the time|current time)", lowered):
        return f"It is {datetime.now().astimezone().strftime('%H:%M')}."
    if re.fullmatch(r"(?:what(?:'s| is) the date|what day is it|today's date)", lowered):
        return datetime.now().astimezone().strftime("Today is %A, %d %B %Y.")
    return None


def _response_latency_tier(command: str, mode: str) -> str:
    if mode not in {"command", "private"}:
        return "quality"
    clean = " ".join(command.strip().split())
    clean = re.sub(r"(?i)^(?:hey\s+|okay\s+)?auris\s*[,.:]?\s*", "", clean).strip()
    lowered = clean.casefold()
    if not lowered or len(lowered) > 240:
        return "quality"

    consequential_markers = (
        "research",
        "source",
        "citation",
        "verify",
        "fact check",
        "calculate",
        "solve",
        "analyse",
        "analyze",
        "compare",
        "explain",
        "code",
        "security",
        "password",
        "legal",
        "medical",
        "financial",
        "investment",
        "diagnose",
        "suicid",
        "self harm",
        "chest pain",
        "emergency",
    )
    if any(marker in lowered for marker in consequential_markers):
        return "quality"

    casual_patterns = (
        r"(?:tell|give) me (?:a|another|one) (?:joke|riddle|fun fact)",
        r"(?:say|give me) (?:something )?(?:encouraging|motivational|funny)",
        r"(?:can we|let's|let us) (?:chat|talk)",
        r"(?:keep me company|cheer me up)",
        r"(?:i am|i'm|i feel|i had|i have had) .+",
    )
    return "fast" if any(re.fullmatch(pattern, lowered) for pattern in casual_patterns) else "quality"


def _model_response(
    command: str,
    project_id: str | None,
    private: bool,
    mode: str,
    conversation_id: str,
) -> dict[str, Any] | None:
    if private:
        history = [{"role": "user", "content": command}]
    else:
        history = [
            {"role": item["role"], "content": item["content"]}
            for item in list_messages(conversation_id, limit=24)
            if item["role"] in {"user", "assistant"}
        ]
    project = get_project(project_id)
    if private:
        memories = []
    else:
        try:
            memories = memory_context_lines(command, project_id=project_id, limit=12)
        except RuntimeError as error:
            record_event("memory.semantic_unavailable", {"reason": str(error)[:300]})
            memories = [
                f"{item['category']} memory: {item['content']}"
                for item in effective_memories(project_id=project_id, limit=12)
            ]
    try:
        reply = generate_reply(
            history,
            mode=mode,
            project_name=project["name"] if project else None,
            project_instructions=project["instructions"] if project else "",
            memories=memories,
            latency_tier=_response_latency_tier(command, mode),
        )
    except RuntimeError as error:
        record_event("model.unavailable", {"reason": str(error)[:300]})
        return None
    return reply.to_dict()


def _save_assistant_message(
    conversation_id: str,
    result: dict[str, Any],
    private: bool,
    task_id: str,
) -> None:
    if private or not result.get("message"):
        return
    append_message(
        conversation_id,
        "assistant",
        str(result["message"]),
        source="auris_runtime",
        metadata={"task_id": task_id},
    )


def _status_message(status: dict[str, Any]) -> str:
    disk = status["disk"]
    return (
        f"{status['machine']} is online. I can see {status['cpu_count']} logical CPU cores and "
        f"{disk['free_gb']} GB free disk space."
    )


def _target_for(task_type: str, command: str = "") -> str:
    targets = {
        "communications": "external communication service",
        "browser_workflow": "browser session",
        "application_state": "durable browser checkpoint",
        "career_workflow": "career application workflow",
        "file_workflow": "approved project workspace",
        "document_workflow": "approved local document",
        "screen_understanding": "temporary visible desktop capture",
        "reminder": "local AURIS event engine",
        "computer_interaction": "named Windows application",
        "project_operation": "registered local project root",
    }
    if task_type == "computer_interaction":
        ui_request = match_ui_control_command(command)
        if ui_request is not None:
            return ui_request.application_name
        typing_request = match_typing_command(command)
        return typing_request.application_name if typing_request else "named Windows application"
    if task_type == "computer_operation":
        action = match_device_command(command)
        return str(action.path) if action is not None and action.path is not None else "bounded Windows action"
    return targets.get(task_type, "requested external target")


def _control_intent(command: str) -> bool | None:
    text = " ".join(command.lower().replace(",", " ").split()).strip(" .")
    for prefix in ("hey auris ", "auris "):
        if text.startswith(prefix):
            text = text[len(prefix) :].strip(" .")
            break
    if text in {"stop", "emergency stop", "stop everything"}:
        return True
    if text in {"resume", "resume operations", "resume auris"}:
        return False
    return None


def _process_control_command(
    command: str,
    context: CommandContext,
    stopped: bool,
) -> dict[str, Any]:
    plan = create_task_plan(command)
    plan_data = plan.to_dict()
    private = context.private or context.mode == "private"

    def execute_control() -> tuple[dict[str, Any], TaskState]:
        control = set_control_state(
            stopped,
            "Emergency stop activated by command" if stopped else "Operations resumed by command",
        )
        return (
            {
                "message": (
                    "Emergency stop active. New operations are blocked."
                    if stopped
                    else "AURIS operations resumed."
                ),
                "verification": "Confirmed: the global control state was persisted.",
                "control": control,
            },
            TaskState.COMPLETED,
        )

    if private:
        result, final_state = execute_control()
        result["verification_report"] = build_verification_report(
            plan_data, result, final_state, attempts=1, recovered=False
        )
    else:
        save_task(plan_data, project_id=context.project_id, mode=context.mode)
        prepare_workflow(plan_data, command)
        result, final_state = execute_workflow(plan_data, execute_control)
        update_task_state(plan.task_id, final_state.value, minimise_persisted_result(result))
    plan_data["state"] = final_state.value
    record_event(
        "control.stopped" if stopped else "control.resumed",
        {
            "task_id": plan.task_id,
            "source": "voice_or_text_command",
            "private": private,
        },
    )
    return _response(plan_data, result)
