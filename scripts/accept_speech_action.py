from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

import numpy as np
from faster_whisper import WhisperModel
from auris.local_client import AurisLocalClient
from auris.speech_input_worker import LocalSpeechInput, MODEL_DIR, verify_model_assets
from auris.voice_daemon import _command_after_wake


def main() -> None:
    verify_model_assets()
    generated = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "synthetic_voice_cases.ps1")],
        capture_output=True, text=True, timeout=90, check=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    case = next(c for c in json.loads(generated.stdout) if c["text"] == "Hey Auris open Notepad" and "Hazel" in c["voice"])
    decoder = LocalSpeechInput.__new__(LocalSpeechInput)
    decoder.np = np
    decoder.model = WhisperModel(str(MODEL_DIR), device="cpu", compute_type="int8", cpu_threads=4, local_files_only=True)
    heard = decoder.decode(base64.b64decode(case["audio"]), "wake")
    command = _command_after_wake(str(heard.get("recognized_as") or ""))
    if not heard.get("ok") or command.casefold().strip(" .") != "open notepad":
        raise RuntimeError("The acoustic decoder did not produce the exact intended command.")
    response = AurisLocalClient().command(command, conversation_id="accept-synthetic-speech-action")
    plan = response.get("plan") or {}
    result = response.get("result") or {}
    action = result.get("device_action") or {}
    fabric = action.get("command_fabric") or {}
    ok = bool(response.get("ok") and plan.get("state") == "completed" and action.get("ok") and fabric.get("signature_verified") and fabric.get("nonce_claimed"))
    print(json.dumps({
        "ok": ok, "input": "synthetic_audio_decoder_to_live_signed_pc_action",
        "physical_room_accuracy_tested": False, "microphone_audio_stored": False,
        "recognized_as": heard.get("recognized_as"), "executed_command": command,
        "state": plan.get("state"), "message": result.get("message"),
        "verification": result.get("verification"), "permission_scope": fabric.get("permission_scope"),
        "signature_verified": fabric.get("signature_verified"), "nonce_claimed": fabric.get("nonce_claimed"),
    }, indent=2))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
