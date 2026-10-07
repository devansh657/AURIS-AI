from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient
from auris.voice_daemon import _command_after_wake


EXPECTED_VERSION = "0.8.34"
FOLDER_NAME = "AURIS Voice Control Ready"


def main() -> int:
    client = AurisLocalClient()
    with urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=5) as response_stream:
        health = json.loads(response_stream.read().decode("utf-8"))
    recognized = f"Hey Oris create a folder on my Desktop called {FOLDER_NAME}"
    command = _command_after_wake(recognized)
    response = client.command(command, conversation_id="accept-voice-file-control")
    plan = response.get("plan") or {}
    result = response.get("result") or {}
    action = result.get("device_action") or {}
    fabric = action.get("command_fabric") or {}
    expected = Path.home() / "Desktop" / FOLDER_NAME
    report = {
        "ok": bool(
            health.get("version") == EXPECTED_VERSION
            and command == f"create a folder on my Desktop called {FOLDER_NAME}"
            and plan.get("state") == "completed"
            and action.get("ok")
            and fabric.get("permission_scope") == "create_folder"
            and fabric.get("signature_verified")
            and fabric.get("nonce_claimed")
            and expected.is_dir()
        ),
        "version": health.get("version"),
        "recognized_as": recognized,
        "extracted_command": command,
        "task_id": plan.get("task_id"),
        "state": plan.get("state"),
        "message": result.get("message"),
        "verification": result.get("verification"),
        "permission_scope": fabric.get("permission_scope"),
        "signature_verified": fabric.get("signature_verified"),
        "nonce_claimed": fabric.get("nonce_claimed"),
        "observed_path": action.get("observed_path"),
        "directory_exists": expected.is_dir(),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
