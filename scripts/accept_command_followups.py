from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


def main() -> int:
    client = AurisLocalClient()
    conversation = f"accept-followup-{uuid4().hex[:12]}"
    folder = f"AURIS Verified 0833 {uuid4().hex[:8]}"
    note = "Working.txt"
    content = "AURIS created this note through a signed and verified Windows action."
    commands = [
        "open Notepad", "minimize it", "restore it",
        f'create a folder called "{folder}" on my Desktop',
        f'create a note called "{note}" inside "{folder}" on my Desktop saying "{content}"',
    ]
    checks = []
    for index, command in enumerate(commands):
        started = time.perf_counter()
        response = client.command(command, conversation_id=conversation, allow_failure=True)
        plan = response.get("plan") or {}
        result = response.get("result") or {}
        action = result.get("device_action") or {}
        fabric = action.get("command_fabric") or {}
        ok = bool(plan.get("state") == "completed" and action.get("ok") and fabric.get("signature_verified") and fabric.get("nonce_claimed"))
        if index in {1, 2}:
            ok = ok and bool(plan.get("context_resolution")) and action.get("action", {}).get("target") == "Notepad"
        if index == 3:
            path = Path(str(action.get("observed_path") or ""))
            ok = ok and path.name == folder and path.is_dir()
        if index == 4:
            path = Path(str(action.get("observed_path") or ""))
            ok = ok and path.name == note and path.parent.name == folder and path.is_file()
            if ok:
                ok = path.read_text(encoding="utf-8") == content and action.get("content_sha256") == hashlib.sha256(content.encode("utf-8")).hexdigest()
        checks.append({"command": command, "ok": ok, "state": plan.get("state"), "duration_ms": round((time.perf_counter() - started) * 1000),
                       "task_id": plan.get("task_id"), "verification": result.get("verification"), "observed_path": action.get("observed_path")})
        if not ok:
            break
    report = {"ok": len(checks) == len(commands) and all(check["ok"] for check in checks),
              "input": "text_commands_to_real_signed_pc_actions", "physical_speech_tested": False, "checks": checks}
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
