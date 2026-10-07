from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


EXPECTED_VERSION = "0.8.34"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    with urlopen("http://127.0.0.1:8765/api/health", timeout=8) as response:
        health = json.loads(response.read().decode("utf-8"))
    require(health.get("version") == EXPECTED_VERSION, f"Expected AURIS {EXPECTED_VERSION}.")

    client = AurisLocalClient()
    response = client.command(
        "AURIS, open Notepad and minimize it",
        conversation_id="compound-sequence-live-acceptance",
    )
    require(response["plan"]["task_type"] == "computer_operation", "Compound command was misrouted.")
    require(response["plan"]["state"] == "completed", "Compound command did not complete.")
    actions = response["result"].get("device_actions") or []
    require(len(actions) == 2, "Compound command did not produce exactly two actions.")
    require([item["action"]["kind"] for item in actions] == ["launch_app", "minimize_app"], "Compound action order changed.")
    for item in actions:
        fabric = item.get("command_fabric") or {}
        require(fabric.get("signature_verified") is True, "A compound step lacks a verified signature.")
        require(fabric.get("nonce_claimed") is True, "A compound step lacks a claimed nonce.")
        require(item.get("ok") is True, "A compound step was not verified.")
    require(actions[1].get("window_state") == "minimized", "Notepad was not observed as minimized.")

    cleanup = client.command(
        "AURIS, close Notepad",
        conversation_id="compound-sequence-live-acceptance",
    )
    require(cleanup["plan"]["state"] == "completed", "Notepad cleanup did not complete.")

    print(
        json.dumps(
            {
                "ok": True,
                "version": health["version"],
                "command": "open Notepad and minimize it",
                "sequence": [
                    {
                        "step": item["sequence_step"],
                        "kind": item["action"]["kind"],
                        "scope": item["command_fabric"]["permission_scope"],
                        "verified": item["ok"],
                    }
                    for item in actions
                ],
                "observed_final_state": actions[1]["window_state"],
                "cleanup": "Notepad closed",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
