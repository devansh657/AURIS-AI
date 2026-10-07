from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


def main() -> int:
    client = AurisLocalClient()
    client.resume_automation("Folder creation acceptance requested by Devansh")
    response = client.command(
        "AURIS, create a folder named DON on Desktop",
        conversation_id="accept-folder-creation",
    )
    plan = response.get("plan") or {}
    result = response.get("result") or {}
    action = result.get("device_action") or {}
    fabric = action.get("command_fabric") or {}
    expected = Path.home() / "Desktop" / "DON"
    report = {
        "ok": bool(
            plan.get("state") == "completed"
            and action.get("ok")
            and fabric.get("signature_verified")
            and fabric.get("nonce_claimed")
            and expected.is_dir()
        ),
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
