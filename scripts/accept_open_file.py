from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


EXPECTED_VERSION = "0.8.34"
FILE_NAME = "AURIS 089 Acceptance.txt"


def main() -> int:
    with urlopen("http://127.0.0.1:8765/api/health", timeout=8) as response:
        health = json.loads(response.read().decode("utf-8"))
    client = AurisLocalClient()
    response = client.command(
        f'AURIS, open file "{FILE_NAME}" from Documents',
        conversation_id="accept-open-file",
    )
    plan = response.get("plan") or {}
    result = response.get("result") or {}
    action = result.get("device_action") or {}
    fabric = action.get("command_fabric") or {}
    expected_path = Path.home() / "Documents" / FILE_NAME
    checks = {
        "release": health.get("version") == EXPECTED_VERSION,
        "mission_completed": plan.get("state") == "completed",
        "action_ok": action.get("ok") is True,
        "permission_scope": fabric.get("permission_scope") == "open_file",
        "signature_verified": fabric.get("signature_verified") is True,
        "nonce_claimed": fabric.get("nonce_claimed") is True,
        "exact_path": action.get("observed_path") == str(expected_path),
        "visible_window": isinstance(action.get("window_handle"), int)
        and action.get("window_handle") > 0,
    }
    report = {
        "ok": all(checks.values()),
        "task_id": plan.get("task_id"),
        "state": plan.get("state"),
        "message": result.get("message"),
        "verification": result.get("verification"),
        "observed_path": action.get("observed_path"),
        "window_handle": action.get("window_handle"),
        "checks": checks,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
