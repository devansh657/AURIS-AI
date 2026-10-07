from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


EXPECTED_VERSION = "0.8.34"
TARGET = Path.home() / "Documents" / "AURIS 089 Acceptance.txt"
APPEND_TEXT = "AURIS controlled append verification 0.8.14."


def main() -> int:
    client = AurisLocalClient()
    with urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=5) as response_stream:
        health = json.loads(response_stream.read().decode("utf-8"))
    response = client.command(
        f'AURIS, append "{APPEND_TEXT}" to note "{TARGET.name}" in Documents',
        conversation_id="accept-note-append",
    )
    plan = response.get("plan") or {}
    result = response.get("result") or {}
    action = result.get("device_action") or {}
    fabric = action.get("command_fabric") or {}
    content = TARGET.read_text(encoding="utf-8") if TARGET.is_file() else ""
    report = {
        "ok": bool(
            health.get("version") == EXPECTED_VERSION
            and plan.get("state") == "completed"
            and action.get("ok")
            and fabric.get("permission_scope") == "append_text_file"
            and fabric.get("signature_verified")
            and fabric.get("nonce_claimed")
            and content.rstrip("\r\n").endswith(APPEND_TEXT)
            and content.splitlines().count(APPEND_TEXT) == 1
            and action.get("preimage_sha256")
            and action.get("content_sha256")
            and action.get("append_sha256") == hashlib.sha256(APPEND_TEXT.encode("utf-8")).hexdigest()
        ),
        "version": health.get("version"),
        "task_id": plan.get("task_id"),
        "state": plan.get("state"),
        "message": result.get("message"),
        "verification": result.get("verification"),
        "permission_scope": fabric.get("permission_scope"),
        "signature_verified": fabric.get("signature_verified"),
        "nonce_claimed": fabric.get("nonce_claimed"),
        "observed_path": action.get("observed_path"),
        "appended": action.get("appended"),
        "exact_final_line_count": content.splitlines().count(APPEND_TEXT),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
