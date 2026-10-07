from __future__ import annotations

import json
import secrets
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


EXPECTED_VERSION = "0.8.34"


def main() -> int:
    with urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=5) as response_stream:
        health = json.loads(response_stream.read().decode("utf-8"))
    suffix = secrets.token_hex(3).upper()
    target = Path.home() / "Documents" / f"AURIS Recycle Acceptance {suffix}.txt"
    content = f"AURIS recoverable removal acceptance {suffix}."
    target.write_text(content, encoding="utf-8")

    client = AurisLocalClient()
    requested = client.command(
        f'AURIS, move file "{target.name}" from Documents to the Recycle Bin',
        conversation_id="accept-recycle-file",
    )
    approval = requested.get("approval") or {}
    approval_id = str(approval.get("approval_id") or "")
    approved = client.decide_approval(approval_id, approve=True) if approval_id else {}
    task = approved.get("task") or {}
    result = task.get("result") or {}
    action = result.get("device_action") or {}
    fabric = action.get("command_fabric") or {}
    report = {
        "ok": bool(
            health.get("version") == EXPECTED_VERSION
            and (requested.get("plan") or {}).get("state") == "awaiting_approval"
            and approval.get("scope") == "once"
            and approval.get("target") == str(target)
            and task.get("state") == "completed"
            and action.get("ok")
            and action.get("recycled")
            and action.get("source_absent")
            and action.get("provider") == "Microsoft.VisualBasic.FileIO.RecycleBin"
            and fabric.get("permission_scope") == "recycle_file"
            and fabric.get("signature_verified")
            and fabric.get("nonce_claimed")
            and not target.exists()
        ),
        "version": health.get("version"),
        "task_id": task.get("task_id"),
        "requested_state": (requested.get("plan") or {}).get("state"),
        "approval_scope": approval.get("scope"),
        "approval_target": approval.get("target"),
        "final_state": task.get("state"),
        "message": result.get("message"),
        "verification": result.get("verification"),
        "permission_scope": fabric.get("permission_scope"),
        "signature_verified": fabric.get("signature_verified"),
        "nonce_claimed": fabric.get("nonce_claimed"),
        "provider": action.get("provider"),
        "source_absent": not target.exists(),
        "fixture_path": str(target),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
