from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


EXPECTED_VERSION = "0.8.34"


def main() -> int:
    with urlopen("http://127.0.0.1:8765/api/health", timeout=8) as response:
        health = json.loads(response.read().decode("utf-8"))
    client = AurisLocalClient()
    commands = ("minimize Notepad", "maximize Notepad", "restore Notepad")
    responses = [
        client.command(f"AURIS, {command}", conversation_id="accept-window-state")
        for command in commands
    ]
    plans = [response.get("plan") or {} for response in responses]
    actions = [((response.get("result") or {}).get("device_action") or {}) for response in responses]
    fabrics = [(action.get("command_fabric") or {}) for action in actions]
    expected_states = ["minimized", "maximized", "restored"]
    expected_scopes = ["minimize_app", "maximize_app", "restore_app"]
    checks = {
        "release": health.get("version") == EXPECTED_VERSION,
        "missions_completed": all(plan.get("state") == "completed" for plan in plans),
        "actions_ok": all(action.get("ok") is True for action in actions),
        "window_states": [action.get("window_state") for action in actions] == expected_states,
        "permission_scopes": [fabric.get("permission_scope") for fabric in fabrics]
        == expected_scopes,
        "signatures": all(fabric.get("signature_verified") is True for fabric in fabrics),
        "nonces": all(fabric.get("nonce_claimed") is True for fabric in fabrics),
        "window_handles": all(isinstance(action.get("window_handle"), int) for action in actions),
    }
    report = {
        "ok": all(checks.values()),
        "task_ids": [plan.get("task_id") for plan in plans],
        "messages": [(response.get("result") or {}).get("message") for response in responses],
        "checks": checks,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
