from __future__ import annotations

import base64
import argparse
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
from auris.speech_input_worker import LocalSpeechInput, MODEL_DIR, verify_model_assets


def main() -> None:
    verify_model_assets()
    decoder = LocalSpeechInput.__new__(LocalSpeechInput)
    decoder.np = np
    parser = argparse.ArgumentParser()
    parser.add_argument("--beam-size", type=int, choices=(1, 3, 5), default=3)
    decoder.beam_size = parser.parse_args().beam_size
    decoder.model = WhisperModel(str(MODEL_DIR), device="cpu", compute_type="int8", cpu_threads=4, local_files_only=True)
    generated = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "synthetic_voice_cases.ps1")],
        capture_output=True, text=True, timeout=90, check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    results = []
    for case in json.loads(generated.stdout):
        pcm = base64.b64decode(case["audio"])
        result = decoder.decode(pcm, case["mode"])
        results.append({
            "voice": case["voice"], "input": case["text"], "mode": case["mode"],
            "expected_accept": case["accept"], "accepted": bool(result.get("ok")),
            "text": result.get("text") or result.get("tentative_text"), "error": result.get("error"), "decode_ms": result.get("decode_ms"),
        })
    silence = decoder.decode(bytes(32000), "wake")
    ok = len(results) == 26 and all(r["accepted"] == r["expected_accept"] for r in results) and not silence.get("ok")
    print(json.dumps({"ok": ok, "correct_cases": sum(r["accepted"] == r["expected_accept"] for r in results), "case_count": len(results), "input": "synthetic_audio_not_room_microphone", "audio_stored": False, "device_actions_executed": False, "cases": results, "silence_rejected": not silence.get("ok")}, indent=2))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
