from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from auris.schemas import TaskState


def build_verification_report(
    plan: dict[str, Any],
    result: dict[str, Any],
    state: TaskState,
    *,
    attempts: int,
    recovered: bool,
) -> dict[str, Any]:
    verification = str(result.get("verification") or "").strip()
    execution_succeeded = state in {TaskState.COMPLETED, TaskState.PARTIALLY_COMPLETED}
    evidence_present = bool(verification)
    unresolved = _unresolved_limits(result, state)
    if state in {TaskState.BLOCKED, TaskState.CANCELLED, TaskState.INTERRUPTED}:
        status = state.value
    elif state == TaskState.COMPLETED and evidence_present:
        status = "verified"
    elif state == TaskState.PARTIALLY_COMPLETED and evidence_present:
        status = "partial"
    else:
        status = "failed"
    return {
        "status": status,
        "method": "deterministic_runtime_checks",
        "checks": [
            {
                "name": "policy_evaluated",
                "passed": True,
                "evidence": f"Risk classified as {plan.get('risk_level', 'unknown')} before execution.",
            },
            {
                "name": "execution_outcome",
                "passed": execution_succeeded,
                "evidence": f"Runtime ended in state {state.value}.",
            },
            {
                "name": "verification_evidence_present",
                "passed": evidence_present,
                "evidence": verification or "No verification evidence was returned.",
            },
            {
                "name": "sensitive_replay_prevention",
                "passed": not recovered or plan.get("risk_level") == "read_only",
                "evidence": (
                    "Recovery replay was limited to a read-only workflow."
                    if recovered
                    else "This execution was not a restart recovery replay."
                ),
            },
        ],
        "attempts": max(1, int(attempts)),
        "recovered_after_restart": bool(recovered),
        "unresolved_limits": unresolved,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


def checkpoint_evidence(result: dict[str, Any], state: TaskState) -> dict[str, Any]:
    action_keys = sorted(key for key in result if key.endswith("_action"))
    item_count = 0
    for key in action_keys:
        action = result.get(key)
        if isinstance(action, dict) and isinstance(action.get("items"), list):
            item_count += len(action["items"])
    return {
        "state": state.value,
        "verification": str(result.get("verification") or "")[:1000],
        "action_types": action_keys,
        "item_count": item_count,
        "content_stored": False,
    }


def _unresolved_limits(result: dict[str, Any], state: TaskState) -> list[str]:
    unresolved: list[str] = []
    if state == TaskState.PARTIALLY_COMPLETED:
        unresolved.append("The objective was only partially completed.")
    if state in {TaskState.FAILED, TaskState.INTERRUPTED, TaskState.CANCELLED, TaskState.BLOCKED}:
        unresolved.append(str(result.get("message") or "Execution did not complete."))
    verification = str(result.get("verification") or "")
    if "cannot be independently guaranteed" in verification.casefold():
        unresolved.append("The remote service outcome could not be independently confirmed.")
    return unresolved
