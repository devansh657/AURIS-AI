from __future__ import annotations

import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    client = AurisLocalClient()
    suppressed = client.speak("Yes, Devansh, I am listening.")
    require(suppressed.get("suppressed") is True and not suppressed.get("queued"), "The passive acknowledgement reached audio output.")
    deadline = time.monotonic() + 15
    before = {}
    while time.monotonic() < deadline:
        before = client.status()["voice"]
        if not before["speaking"] and before["input_capture_active"] and before["input_phase"] == "listening_for_wake_word":
            break
        time.sleep(0.1)
    require(before.get("continuous_wake_commands") and before.get("priority_input_without_reload"), "The new voice-input worker is not active.")
    started = time.perf_counter()
    heard = client.listen_for_interrupt(timeout_seconds=2)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    after = client.status()["voice"]
    require(before["input_worker_pid"] == after["input_worker_pid"], "Priority listening reloaded the warm recognizer.")
    require(heard.get("input_provider") == "local_whisper_stream", "Priority input did not use the local speech model.")
    require(after.get("last_input_error") is None, "The native handover produced an input error.")
    require(elapsed_ms < 3500, f"The two-second priority listening window took {elapsed_ms} ms.")
    require(after.get("playback_engine") == "windows_native_wave", "Native Windows playback is unavailable.")
    print(json.dumps({
        "ok": True,
        "acknowledgement_silent": True,
        "continuous_wake_commands": after["continuous_wake_commands"],
        "recognizer_pid_preserved": after["input_worker_pid"],
        "priority_window_ms": elapsed_ms,
        "requested_window_ms": 2000,
        "input_provider": heard["input_provider"],
        "playback_engine": after["playback_engine"],
        "audio_stored": heard.get("audio_stored"),
        "physical_command_accuracy_tested": False,
    }, indent=2))


if __name__ == "__main__":
    main()
