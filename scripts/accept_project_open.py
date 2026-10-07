from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


EXPECTED_VERSION = "0.8.34"


def main() -> None:
    with urlopen("http://127.0.0.1:8765/api/health", timeout=8) as response:
        health = json.loads(response.read().decode("utf-8"))
    if health.get("version") != EXPECTED_VERSION:
        raise SystemExit(
            f"Expected AURIS {EXPECTED_VERSION}, received {health.get('version') or 'unknown'}."
        )

    client = AurisLocalClient()
    status = client.status()
    local_ipc = status.get("local_ipc") or {}
    if not local_ipc.get("connected"):
        raise SystemExit("Authenticated native IPC is not connected.")

    response = client.command(
        "AURIS, open this project",
        conversation_id="auris-live-project-open-acceptance",
    )
    plan = response.get("plan") or {}
    result = response.get("result") or {}
    action = result.get("project_action") or {}
    fabric = action.get("command_fabric") or {}
    expected_root = str(ROOT.resolve())
    observed_root = str(action.get("observed_path") or "")

    checks = {
        "mission_completed": plan.get("state") == "completed",
        "project_action_ok": action.get("ok") is True,
        "signature_verified": fabric.get("signature_verified") is True,
        "nonce_claimed": fabric.get("nonce_claimed") is True,
        "permission_scope": fabric.get("permission_scope") == "open_folder",
        "exact_root_observed": observed_root.casefold() == expected_root.casefold(),
        "explorer_observed": action.get("application") == "File Explorer",
    }
    evidence = {
        "ok": all(checks.values()),
        "version": health.get("version"),
        "transport": local_ipc.get("transport"),
        "task_type": plan.get("task_type"),
        "mission_state": plan.get("state"),
        "project_id": action.get("project_id"),
        "application": action.get("application"),
        "observed_path": observed_root,
        "command_id": fabric.get("command_id"),
        "device_id": fabric.get("device_id"),
        "checks": checks,
    }
    print(json.dumps(evidence, ensure_ascii=True, sort_keys=True))
    if not evidence["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
