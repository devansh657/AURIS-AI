from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


EXPECTED_VERSION = "0.8.34"


def main() -> None:
    with urlopen("http://127.0.0.1:8765/api/health", timeout=8) as response:
        health = json.loads(response.read().decode("utf-8"))
    if health.get("version") != EXPECTED_VERSION:
        raise SystemExit(
            f"Expected AURIS {EXPECTED_VERSION}, received {health.get('version') or 'unknown'}."
        )

    client = AurisLocalClient()
    status = client.status()
    local_ipc = status.get("local_ipc") or {}
    voice = status.get("voice") or {}
    desktop = status.get("desktop_companion") or {}
    if not local_ipc.get("connected"):
        raise SystemExit("Authenticated native IPC is not connected.")

    evidence: dict[str, object] = {
        "ok": False,
        "version": health.get("version"),
        "transport": local_ipc.get("transport"),
    }
    try:
        opened = client.command(
            "AURIS, open Notepad",
            conversation_id="auris-live-ui-automation-acceptance",
        )
        requested = client.command(
            'AURIS, click "File" in Notepad',
            conversation_id="auris-live-ui-automation-acceptance",
        )
        approval = requested.get("approval") or {}
        approval_id = str(approval.get("approval_id") or "")
        if not approval_id:
            raise SystemExit("The UI Automation command did not pause for one-time approval.")
        approved = client.decide_approval(approval_id, approve=True)
        task = approved.get("task") or {}
        result = task.get("result") or {}
        interaction = result.get("interaction_action") or {}
        fabric = interaction.get("command_fabric") or {}
        checks = {
            "vale_voice_ready": voice.get("provider") == "local_kokoro" and voice.get("neural_worker_online") is True,
            "input_worker_ready": voice.get("input_worker_online") is True,
            "voice_daemon_online": voice.get("background_daemon_online") is True,
            "desktop_companion_online": desktop.get("online") is True,
            "application_opened": (opened.get("plan") or {}).get("state") == "completed",
            "approval_requested": (requested.get("plan") or {}).get("state") == "awaiting_approval",
            "approval_scope_once": approval.get("scope") == "once",
            "mission_completed": task.get("state") == "completed",
            "interaction_observed": interaction.get("observed") is True,
            "signature_verified": fabric.get("signature_verified") is True,
            "nonce_claimed": fabric.get("nonce_claimed") is True,
            "permission_scope": fabric.get("permission_scope") == "invoke_control",
            "no_capture_persisted": interaction.get("temporary_capture_persisted") is False,
        }
        evidence.update(
            {
                "ok": all(checks.values()),
                "task_type": task.get("task_type"),
                "mission_state": task.get("state"),
                "application": interaction.get("application"),
                "voice": voice.get("voice"),
                "voice_provider": voice.get("provider"),
                "voice_execution_provider": voice.get("neural_execution_provider"),
                "desktop_state": desktop.get("state"),
                "control_name": interaction.get("control_name"),
                "control_type": interaction.get("control_type"),
                "automation_pattern": interaction.get("automation_pattern"),
                "observation": interaction.get("observation"),
                "command_id": fabric.get("command_id"),
                "device_id": fabric.get("device_id"),
                "checks": checks,
            }
        )
    finally:
        try:
            client.command(
                "AURIS, close Notepad",
                conversation_id="auris-live-ui-automation-acceptance",
            )
        except Exception:
            evidence["cleanup_confirmed"] = False
        else:
            evidence["cleanup_confirmed"] = True

    print(json.dumps(evidence, ensure_ascii=True, sort_keys=True))
    if not evidence.get("ok") or evidence.get("cleanup_confirmed") is not True:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
