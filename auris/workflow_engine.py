from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from auris.audit import record_event
from auris.coding_agent import match_coding_command
from auris.database import (
    begin_workflow_attempt,
    create_workflow_run,
    DATABASE_PATH,
    get_workflow_run,
    update_task_state,
    update_workflow_checkpoint,
    update_workflow_state,
)
from auris.privacy import minimise_persisted_result
from auris.schemas import TaskState
from auris.work_product_agent import match_work_product_command
from auris.verification import build_verification_report, checkpoint_evidence


Executor = Callable[[], tuple[dict[str, Any], TaskState]]


def prepare_workflow(
    plan: dict[str, Any], command: str, *, path: Path = DATABASE_PATH
) -> dict[str, Any]:
    repair_continuation = (
        plan.get("task_type") == "coding"
        and match_coding_command(command) in {"repair_test", "codex_workspace"}
    )
    product = match_work_product_command(command) if plan.get("task_type") == "work_product" else None
    coding_product = product is not None and product.kind == "code_project"
    workflow = create_workflow_run(
        plan,
        command,
        max_attempts=2 if plan.get("risk_level") == "read_only" or repair_continuation or coding_product else 1,
        path=path,
    )
    planning = _checkpoint(plan, 0)
    if planning:
        update_workflow_checkpoint(
            plan["task_id"],
            planning["step_id"],
            "completed",
            evidence={
                "task_type": plan.get("task_type"),
                "risk_level": plan.get("risk_level"),
                "policy_evaluated": True,
            },
            path=path,
        )
    update_workflow_state(plan["task_id"], plan.get("state", "created"), path=path)
    return get_workflow_run(plan["task_id"], path=path) or workflow


def mark_workflow_waiting(plan: dict[str, Any], *, path: Path = DATABASE_PATH) -> None:
    execution = _checkpoint(plan, 1)
    if execution:
        update_workflow_checkpoint(
            plan["task_id"], execution["step_id"], "awaiting_approval", path=path
        )
    update_workflow_state(plan["task_id"], TaskState.AWAITING_APPROVAL.value, path=path)


def mark_workflow_terminal(
    plan: dict[str, Any],
    state: TaskState,
    result: dict[str, Any],
    *,
    path: Path = DATABASE_PATH,
) -> None:
    execution = _checkpoint(plan, 1)
    verification = _checkpoint(plan, -1)
    checkpoint_state = "blocked" if state == TaskState.BLOCKED else "cancelled"
    if execution:
        update_workflow_checkpoint(
            plan["task_id"], execution["step_id"], checkpoint_state,
            evidence=checkpoint_evidence(result, state),
            path=path,
        )
    if verification and verification != execution:
        update_workflow_checkpoint(
            plan["task_id"], verification["step_id"], "completed",
            evidence={"terminal_state": state.value, "execution_prevented": True},
            path=path,
        )
    update_workflow_state(plan["task_id"], state.value, path=path)


def execute_workflow(
    plan: dict[str, Any],
    executor: Executor,
    *,
    recovered: bool = False,
    path: Path = DATABASE_PATH,
) -> tuple[dict[str, Any], TaskState]:
    task_id = plan["task_id"]
    workflow = get_workflow_run(task_id, path=path)
    if workflow is None:
        raise RuntimeError("The durable workflow record is missing.")
    execution = _checkpoint(plan, 1)
    verification = _checkpoint(plan, -1)
    attempt_history = _attempt_history(workflow, execution)

    update_task_state(task_id, TaskState.RUNNING.value, path=path)
    update_workflow_state(
        task_id,
        "recovering" if recovered else TaskState.RUNNING.value,
        increment_recovery=recovered,
        path=path,
    )
    result: dict[str, Any]
    state: TaskState
    while True:
        attempt = begin_workflow_attempt(task_id, path=path)
        if attempt is None:
            result = {
                "message": "The workflow attempt budget was exhausted before execution completed.",
                "verification": "Confirmed: AURIS stopped without replaying the operation again.",
            }
            state = TaskState.INTERRUPTED
            break
        attempt_number = int(attempt["attempts"])
        if execution:
            update_workflow_checkpoint(
                task_id,
                execution["step_id"],
                "running",
                evidence={"attempt_history": attempt_history, "content_stored": False},
                increment_attempt=True,
                path=path,
            )
        try:
            result, state = executor()
        except Exception as error:
            result = {
                "message": "The execution worker encountered a recoverable runtime error.",
                "verification": "No successful outcome was verified for this attempt.",
                "retryable": plan.get("risk_level") == "read_only",
            }
            state = TaskState.FAILED
            error_text = str(error)[:1000]
        else:
            error_text = str(result.get("message") or "")[:1000] if state == TaskState.FAILED else ""

        attempt_history.append(
            {
                "attempt": attempt_number,
                "state": state.value,
                "retryable": bool(result.get("retryable")),
                "error": error_text,
            }
        )
        current = get_workflow_run(task_id, path=path) or attempt
        can_retry = (
            state == TaskState.FAILED
            and bool(result.get("retryable"))
            and plan.get("risk_level") == "read_only"
            and int(current["attempts"]) < int(current["max_attempts"])
        )
        if not can_retry:
            break
        update_workflow_state(task_id, "retrying", last_error=error_text, path=path)
        record_event(
            "workflow.retry_scheduled",
            {
                "task_id": task_id,
                "attempt": attempt_number,
                "max_attempts": current["max_attempts"],
                "read_only": True,
            },
        )

    if state == TaskState.AWAITING_APPROVAL:
        if execution:
            update_workflow_checkpoint(
                task_id,
                execution["step_id"],
                "awaiting_approval",
                evidence={
                    **checkpoint_evidence(result, state),
                    "attempt_history": attempt_history,
                    "source_project_modified": False,
                },
                path=path,
            )
        update_workflow_state(task_id, TaskState.AWAITING_APPROVAL.value, path=path)
        update_task_state(
            task_id,
            TaskState.AWAITING_APPROVAL.value,
            minimise_persisted_result(result),
            path=path,
        )
        record_event(
            "workflow.awaiting_approval",
            {"task_id": task_id, "attempts": len(attempt_history), "content_stored": False},
        )
        return result, state

    if execution:
        update_workflow_checkpoint(
            task_id,
            execution["step_id"],
            "completed" if state in {TaskState.COMPLETED, TaskState.PARTIALLY_COMPLETED} else "failed",
            evidence={
                **checkpoint_evidence(result, state),
                "attempt_history": attempt_history,
            },
            error=str(result.get("message") or "") if state == TaskState.FAILED else None,
            path=path,
        )
    update_task_state(task_id, TaskState.VERIFYING.value, path=path)
    update_workflow_state(task_id, TaskState.VERIFYING.value, path=path)
    workflow = get_workflow_run(task_id, path=path) or workflow
    report = build_verification_report(
        plan,
        result,
        state,
        attempts=int(workflow["attempts"]),
        recovered=recovered,
    )
    result["verification_report"] = report
    if verification:
        update_workflow_checkpoint(
            task_id,
            verification["step_id"],
            "completed",
            evidence={"report": report, "content_stored": False},
            path=path,
        )
    update_workflow_state(
        task_id,
        state.value,
        last_error=str(result.get("message") or "") if state == TaskState.FAILED else None,
        path=path,
    )
    update_task_state(task_id, state.value, minimise_persisted_result(result), path=path)
    record_event(
        "workflow.verified",
        {
            "task_id": task_id,
            "state": state.value,
            "verification_status": report["status"],
            "attempts": report["attempts"],
            "recovered": recovered,
        },
    )
    return result, state


def _checkpoint(plan: dict[str, Any], index: int) -> dict[str, Any] | None:
    steps = plan.get("steps") or []
    if not steps or index >= len(steps) or index < -len(steps):
        return None
    return steps[index]


def _attempt_history(
    workflow: dict[str, Any], execution: dict[str, Any] | None
) -> list[dict[str, Any]]:
    if execution is None:
        return []
    checkpoint = next(
        (
            item
            for item in workflow.get("checkpoints", [])
            if item["step_id"] == execution["step_id"]
        ),
        None,
    )
    if checkpoint is None:
        return []
    history = checkpoint.get("evidence", {}).get("attempt_history", [])
    return list(history) if isinstance(history, list) else []
