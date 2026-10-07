from __future__ import annotations

import ctypes
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "data" / "voice" / "kokoro" / "kokoro-v1.0.fp16.onnx"
VOICES_PATH = ROOT / "data" / "voice" / "kokoro" / "voices-v1.0.bin"
RUNTIME_DIR = ROOT / "data" / "voice" / "runtime"
ALLOWED_SENTIMENTS = {"neutral", "positive", "concerned", "reassuring", "urgent"}
VOICE_ID = "bm_george"
_DLL_DIRECTORY_HANDLES: list[object] = []
_DLL_HANDLES: list[object] = []


def run() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    _remove_stale_audio()
    started = time.perf_counter()
    kokoro, session = _load_engine()
    kokoro.create(
        "Auris is ready.",
        voice=VOICE_ID,
        speed=0.95,
        lang="en-gb",
        sentence_pause=0.2,
        clause_pause=0.08,
    )
    if session.get_providers()[0] != "CUDAExecutionProvider":
        raise RuntimeError("The AURIS Kokoro worker did not retain CUDA during warm-up.")
    _emit(
        {
            "type": "ready",
            "provider": "local_kokoro",
            "engine": "CUDAExecutionProvider",
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
            response = _synthesise(kokoro, session, request)
        except Exception as error:
            response = {
                "ok": False,
                "request_id": _safe_request_id(locals().get("request")),
                "error": f"{type(error).__name__}: {str(error)[:240]}",
            }
        _emit(response)
    return 0


def _load_engine() -> tuple[Any, Any]:
    _preload_nvidia_libraries()
    import onnxruntime as ort
    from kokoro_onnx import Kokoro

    ort.preload_dlls(directory="")
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.log_severity_level = 3
    session = ort.InferenceSession(
        str(MODEL_PATH),
        sess_options=options,
        providers=[
            (
                "CUDAExecutionProvider",
                {
                    "device_id": 0,
                    "gpu_mem_limit": 1024 * 1024 * 1024,
                    "arena_extend_strategy": "kSameAsRequested",
                    "cudnn_conv_algo_search": "HEURISTIC",
                },
            )
        ],
    )
    session.disable_fallback()
    if not session.get_providers() or session.get_providers()[0] != "CUDAExecutionProvider":
        raise RuntimeError("The AURIS Kokoro worker could not select CUDA.")
    return Kokoro.from_session(session, str(VOICES_PATH)), session


def _preload_nvidia_libraries() -> None:
    nvidia_root = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    if hasattr(os, "add_dll_directory"):
        for bin_dir in sorted(nvidia_root.glob("*/bin")):
            _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(bin_dir)))
    for package in (
        "cuda_runtime",
        "cublas",
        "nvjitlink",
        "cudnn",
        "cufft",
        "curand",
        "cuda_nvrtc",
    ):
        for dll in sorted((nvidia_root / package / "bin").glob("*.dll")):
            _DLL_HANDLES.append(ctypes.WinDLL(str(dll)))


def _synthesise(kokoro: Any, session: Any, request: dict[str, Any]) -> dict[str, Any]:
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
    sentence_pause, clause_pause = {
        "urgent": (0.12, 0.04),
        "concerned": (0.30, 0.13),
        "reassuring": (0.34, 0.14),
        "positive": (0.20, 0.08),
        "neutral": (0.24, 0.10),
    }[sentiment]
    started = time.perf_counter()
    samples, sample_rate = kokoro.create(
        text,
        voice=VOICE_ID,
        speed=speed,
        lang="en-gb",
        sentence_pause=sentence_pause,
        clause_pause=clause_pause,
    )
    if session.get_providers()[0] != "CUDAExecutionProvider":
        raise RuntimeError("The AURIS Kokoro worker left the CUDA provider.")
    import soundfile as sf

    sf.write(str(output_path), samples, sample_rate, subtype="PCM_16", format="WAV")
    return {
        "ok": True,
        "request_id": request_id,
        "output_path": str(output_path),
        "duration_seconds": round(len(samples) / sample_rate, 3),
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
