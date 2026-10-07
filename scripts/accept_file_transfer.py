from __future__ import annotations

import hashlib
import json
import secrets
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
    suffix = secrets.token_hex(3).upper()
    source_name = f"AURIS Transfer {suffix}.txt"
    renamed_name = f"AURIS Renamed {suffix}.txt"
    copied_name = f"AURIS Copied {suffix}.txt"
    moved_name = f"AURIS Moved {suffix}.txt"
    content = f"AURIS verified filesystem transfer {suffix}."
    commands = (
        f'AURIS, create a note called "{source_name}" in Documents saying "{content}"',
        f'AURIS, rename file "{source_name}" in Documents to "{renamed_name}"',
        f'AURIS, copy file "{renamed_name}" from Documents to Desktop as "{copied_name}"',
        f'AURIS, move file "{copied_name}" from Desktop to Downloads as "{moved_name}"',
    )
    responses = [
        client.command(command, conversation_id="accept-file-transfer") for command in commands
    ]
    actions = [((response.get("result") or {}).get("device_action") or {}) for response in responses]
    plans = [(response.get("plan") or {}) for response in responses]
    fabrics = [(action.get("command_fabric") or {}) for action in actions]
    documents = Path.home() / "Documents"
    desktop = Path.home() / "Desktop"
    downloads = Path.home() / "Downloads"
    renamed = documents / renamed_name
    copied = desktop / copied_name
    moved = downloads / moved_name
    expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    checks = {
        "release": health.get("version") == EXPECTED_VERSION,
        "missions_completed": all(plan.get("state") == "completed" for plan in plans),
        "actions_ok": all(action.get("ok") is True for action in actions),
        "scopes": [fabric.get("permission_scope") for fabric in fabrics]
        == ["create_text_file", "rename_path", "copy_file", "move_file"],
        "signatures": all(fabric.get("signature_verified") is True for fabric in fabrics),
        "nonces": all(fabric.get("nonce_claimed") is True for fabric in fabrics),
        "source_renamed": not (documents / source_name).exists() and renamed.is_file(),
        "copy_moved": not copied.exists() and moved.is_file(),
        "renamed_content": renamed.read_text(encoding="utf-8") == content,
        "moved_content": moved.read_text(encoding="utf-8") == content,
        "verified_hashes": actions[2].get("content_sha256") == expected_hash
        and actions[3].get("content_sha256") == expected_hash,
    }
    report = {
        "ok": all(checks.values()),
        "release": health.get("version"),
        "task_ids": [plan.get("task_id") for plan in plans],
        "messages": [(response.get("result") or {}).get("message") for response in responses],
        "renamed_path": str(renamed),
        "moved_path": str(moved),
        "checks": checks,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
