from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


EXPECTED_VERSION = "0.8.34"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    with urlopen("http://127.0.0.1:8765/api/health", timeout=8) as response:
        health = json.loads(response.read().decode("utf-8"))
    require(health.get("version") == EXPECTED_VERSION, f"Expected AURIS {EXPECTED_VERSION}.")

    client = AurisLocalClient()
    status = client.command("show AURIS phone status", conversation_id="auris-call-acceptance")
    results = []
    for command in ("call MOM", "make a WhatsApp audio call to MOM"):
        response = client.command(command, conversation_id="auris-call-acceptance")
        plan = response.get("plan") or {}
        approval = response.get("approval") or {}
        require(plan.get("task_type") == "communications", f"Call fell through for: {command}")
        require(plan.get("risk_level") == "sensitive", f"Call was not sensitive: {command}")
        require(plan.get("state") == "awaiting_approval", f"Call did not pause: {command}")
        require(approval.get("target") == "MOM", f"Approval target changed: {command}")
        require(approval.get("approval_id"), f"Approval was not created: {command}")
        rejected = client.decide_approval(approval["approval_id"], approve=False)
        require(rejected.get("ok") is True, f"Acceptance approval was not rejected: {command}")
        results.append({"command": command, "task_type": plan["task_type"], "state": plan["state"]})

    phone = ((status.get("result") or {}).get("communications_action") or {}).get("telephony") or {}
    print(
        json.dumps(
            {
                "ok": True,
                "version": health.get("version"),
                "provider_state": phone.get("state"),
                "live_provider_connected": phone.get("connected") is True,
                "commands": results,
                "test_approvals_rejected": True,
                "real_call_attempted": False,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
