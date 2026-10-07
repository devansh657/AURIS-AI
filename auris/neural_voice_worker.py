from __future__ import annotations

import json
import os
import re
import sys
import time
import wave
from pathlib import Path
from typing import Any
from uuid import UUID

from piper.config import SynthesisConfig
from piper.voice import PiperVoice


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "data" / "voice" / "piper" / "en_GB-northern_english_male-medium.onnx"
CONFIG_PATH = MODEL_PATH.with_suffix(".onnx.json")
RUNTIME_DIR = ROOT / "data" / "voice" / "runtime"
ALLOWED_SENTIMENTS = {"neutral", "positive", "concerned", "reassuring", "urgent"}


def run() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    _remove_stale_audio()
    started = time.perf_counter()
    voice = PiperVoice.load(MODEL_PATH, config_path=CONFIG_PATH)
    _emit(
        {
            "type": "ready",
            "provider": "local_piper",
            "voice": "AURIS Vale",
            "model_load_ms": round((time.perf_counter() - started) * 1000),
            "pid": os.getpid(),
        }
    )
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("A JSON object is required.")
            if request.get("operation") == "shutdown":
                return 0
            response = _synthesise(voice, request)
        except Exception as error:
            response = {
                "ok": False,
                "request_id": _safe_request_id(locals().get("request")),
                "error": f"{type(error).__name__}: {str(error)[:240]}",
            }
        _emit(response)
    return 0


def _synthesise(voice: PiperVoice, request: dict[str, Any]) -> dict[str, Any]:
    if set(request) != {"operation", "request_id", "text", "speed", "sentiment", "output_path"}:
        raise ValueError("The synthesis request schema is invalid.")
    if request.get("operation") != "synthesise":
        raise ValueError("The synthesis operation is unsupported.")
    request_id = str(UUID(str(request.get("request_id") or "")))
    text = str(request.get("text") or "").strip()
    if not text or len(text) > 1200:
        raise ValueError("Speech text must contain between 1 and 1200 characters.")
    speed = float(request.get("speed"))
    if not 0.84 <= speed <= 1.12:
        raise ValueError("Speech speed is outside the supported range.")
    sentiment = str(request.get("sentiment") or "")
    if sentiment not in ALLOWED_SENTIMENTS:
        raise ValueError("Speech sentiment is unsupported.")
    output_path = _validated_output_path(str(request.get("output_path") or ""))
    noise_scale, noise_width = {
        "urgent": (0.43, 0.58),
        "concerned": (0.48, 0.65),
        "reassuring": (0.53, 0.69),
        "positive": (0.58, 0.74),
        "neutral": (0.54, 0.70),
    }[sentiment]
    config = SynthesisConfig(
        length_scale=round(1.0 / speed, 4),
        noise_scale=noise_scale,
        noise_w_scale=noise_width,
        normalize_audio=True,
        volume=1.0,
    )
    started = time.perf_counter()
    with wave.open(str(output_path), "wb") as wav_file:
        voice.synthesize_wav(text, wav_file, config)
    with wave.open(str(output_path), "rb") as wav_file:
        duration_seconds = wav_file.getnframes() / wav_file.getframerate()
    return {
        "ok": True,
        "request_id": request_id,
        "output_path": str(output_path),
        "duration_seconds": round(duration_seconds, 3),
        "synthesis_ms": round((time.perf_counter() - started) * 1000),
    }


def _validated_output_path(value: str) -> Path:
    path = Path(value).resolve()
    if path.parent != RUNTIME_DIR.resolve():
        raise ValueError("Speech output must remain inside the AURIS runtime directory.")
    if not re.fullmatch(r"[0-9a-f-]{36}\.wav", path.name, flags=re.IGNORECASE):
        raise ValueError("The speech output filename is invalid.")
    return path


def _remove_stale_audio() -> None:
    cutoff = time.time() - 3600
    for path in RUNTIME_DIR.glob("*.wav"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


def _safe_request_id(request: object) -> str:
    if isinstance(request, dict):
        return str(request.get("request_id") or "")[:36]
    return ""


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    raise SystemExit(run())
