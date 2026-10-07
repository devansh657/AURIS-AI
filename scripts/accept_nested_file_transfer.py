from __future__ import annotations

import hashlib
import json
import secrets
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


EXPECTED_VERSION = "0.8.34"
PARENT_NAME = "AURIS Voice Control Ready"


def main() -> int:
    with urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=5) as response_stream:
        health = json.loads(response_stream.read().decode("utf-8"))
    suffix = secrets.token_hex(3).upper()
    source_name = f"AURIS Nested Source {suffix}.txt"
    copied_name = f"AURIS Nested Copy {suffix}.txt"
    renamed_name = f"AURIS Nested Renamed {suffix}.txt"
    moved_name = f"AURIS Nested Moved {suffix}.txt"
    content = f"AURIS nested transfer verification {suffix}."
    commands = (
        f'AURIS, create a note called "{source_name}" in Documents saying "{content}"',
        f'AURIS, copy file "{source_name}" from Documents to folder "{PARENT_NAME}" on Desktop as "{copied_name}"',
        f'AURIS, rename file "{copied_name}" inside "{PARENT_NAME}" on Desktop to "{renamed_name}"',
        f'AURIS, move file "{renamed_name}" from folder "{PARENT_NAME}" on Desktop to Downloads as "{moved_name}"',
    )
    client = AurisLocalClient()
    responses = [
        client.command(command, conversation_id="accept-nested-file-transfer")
        for command in commands
    ]
    plans = [response.get("plan") or {} for response in responses]
    actions = [(response.get("result") or {}).get("device_action") or {} for response in responses]
    fabrics = [action.get("command_fabric") or {} for action in actions]
    source = Path.home() / "Documents" / source_name
    nested_copy = Path.home() / "Desktop" / PARENT_NAME / copied_name
    nested_renamed = Path.home() / "Desktop" / PARENT_NAME / renamed_name
    moved = Path.home() / "Downloads" / moved_name
    expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    checks = {
        "release": health.get("version") == EXPECTED_VERSION,
        "missions_completed": all(plan.get("state") == "completed" for plan in plans),
        "actions_ok": all(action.get("ok") is True for action in actions),
        "scopes": [fabric.get("permission_scope") for fabric in fabrics]
        == ["create_text_file", "copy_file", "rename_path", "move_file"],
        "signatures": all(fabric.get("signature_verified") is True for fabric in fabrics),
        "nonces": all(fabric.get("nonce_claimed") is True for fabric in fabrics),
        "source_preserved": source.is_file() and source.read_text(encoding="utf-8") == content,
        "nested_intermediates_absent": not nested_copy.exists() and not nested_renamed.exists(),
        "moved_content": moved.is_file() and moved.read_text(encoding="utf-8") == content,
        "hashes": actions[1].get("content_sha256") == expected_hash
        and actions[2].get("content_sha256") == expected_hash
        and actions[3].get("content_sha256") == expected_hash,
    }
    report = {
        "ok": all(checks.values()),
        "version": health.get("version"),
        "task_ids": [plan.get("task_id") for plan in plans],
        "messages": [(response.get("result") or {}).get("message") for response in responses],
        "source_path": str(source),
        "moved_path": str(moved),
        "checks": checks,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
