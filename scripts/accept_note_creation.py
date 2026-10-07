from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


EXPECTED_VERSION = "0.8.34"
NOTE_NAME = "AURIS 089 Acceptance.txt"
NOTE_CONTENT = "AURIS verified note creation is operational."


def main() -> int:
    client = AurisLocalClient()
    with urlopen("http://127.0.0.1:8765/api/health", timeout=8) as response:
        health = json.loads(response.read().decode("utf-8"))
    response = client.command(
        f'AURIS, create a note called "{NOTE_NAME}" in Documents saying "{NOTE_CONTENT}"',
        conversation_id="accept-note-creation",
    )
    plan = response.get("plan") or {}
    result = response.get("result") or {}
    action = result.get("device_action") or {}
    fabric = action.get("command_fabric") or {}
    expected_path = Path.home() / "Documents" / NOTE_NAME
    expected_hash = hashlib.sha256(NOTE_CONTENT.encode("utf-8")).hexdigest()
    try:
        observed_content = expected_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        observed_content = None
    checks = {
        "release": health.get("version") == EXPECTED_VERSION,
        "mission_completed": plan.get("state") == "completed",
        "action_ok": action.get("ok") is True,
        "permission_scope": fabric.get("permission_scope") == "create_text_file",
        "signature_verified": fabric.get("signature_verified") is True,
        "nonce_claimed": fabric.get("nonce_claimed") is True,
        "exact_path": action.get("observed_path") == str(expected_path),
        "exact_content": observed_content == NOTE_CONTENT,
        "content_hash": action.get("content_sha256") == expected_hash,
    }
    report = {
        "ok": all(checks.values()),
        "task_id": plan.get("task_id"),
        "state": plan.get("state"),
        "message": result.get("message"),
        "verification": result.get("verification"),
        "observed_path": action.get("observed_path"),
        "checks": checks,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
