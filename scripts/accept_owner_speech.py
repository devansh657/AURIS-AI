from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


def main() -> int:
    client = AurisLocalClient()
    prior = bool(client.status()["voice"]["background_enabled"])
    client.set_background_voice(False)
    client.stop_speaking()
    try:
        print('Opening a private 20-second microphone window for "open Calculator".', flush=True)
        voice = client.listen(timeout_seconds=20, private=True)
        text = str(voice.get("text") or "")
        matched = bool(voice.get("ok") and re.fullmatch(r"(?:open|launch) (?:the )?calculator[.!]?", text.strip(), re.I))
        report = {"kind": "owner_prompted_live_microphone_test", "recognition_ok": voice.get("ok"),
                  "expected_command_matched": matched, "audio_stored": False, "transcript_stored": False,
                  "device_action_executed": False, "ok": False,
                  **{key: voice.get(key) for key in ("error_code", "signal_state", "peak_dbfs", "sampled_frames", "decode_ms", "recognition_ms")}}
        if matched:
            response = client.command(text, private=True, voice_turn_id=voice.get("turn_id"), allow_failure=True)
            action = response.get("result", {}).get("device_action", {})
            fabric = action.get("command_fabric", {})
            report.update(device_action_executed=True, action_ok=action.get("ok"),
                          task_state=response.get("plan", {}).get("state"),
                          signature_verified=fabric.get("signature_verified"), nonce_claimed=fabric.get("nonce_claimed"))
            report["ok"] = bool(action.get("ok") and fabric.get("signature_verified") and fabric.get("nonce_claimed") and report["task_state"] == "completed")
        output = ROOT / "data" / "acceptance" / "owner-microphone-0834.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1
    finally:
        client.set_background_voice(prior)


if __name__ == "__main__":
    raise SystemExit(main())
