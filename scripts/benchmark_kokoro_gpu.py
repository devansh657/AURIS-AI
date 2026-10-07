from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from pathlib import Path

import onnxruntime as ort
from kokoro_onnx import Kokoro


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "data" / "voice" / "kokoro" / "kokoro-v1.0.fp16.onnx"
VOICES = ROOT / "data" / "voice" / "kokoro" / "voices-v1.0.bin"
SAMPLE = (
    "AURIS voice integrity is verified. The single voice system is ready, "
    "and I am standing by."
)
_DLL_DIRECTORY_HANDLES: list[object] = []
_DLL_HANDLES: list[object] = []


def add_nvidia_dll_directories() -> None:
    if not hasattr(os, "add_dll_directory"):
        return
    nvidia_root = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
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


def run() -> int:
    print("phase=preload_cuda", file=sys.stderr, flush=True)
    add_nvidia_dll_directories()
    ort.preload_dlls(directory="")
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.log_severity_level = 3
    print("phase=load_model", file=sys.stderr, flush=True)
    started = time.perf_counter()
    session = ort.InferenceSession(
        str(MODEL),
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
            ),
            "CPUExecutionProvider",
        ],
    )
    load_ms = round((time.perf_counter() - started) * 1000)
    if not session.get_providers() or session.get_providers()[0] != "CUDAExecutionProvider":
        raise RuntimeError("Kokoro did not select the CUDA execution provider.")
    print(f"phase=model_ready load_ms={load_ms}", file=sys.stderr, flush=True)
    kokoro = Kokoro.from_session(session, str(VOICES))

    trials = []
    for text in ("AURIS is online.", SAMPLE, SAMPLE):
        print(f"phase=synthesize characters={len(text)}", file=sys.stderr, flush=True)
        trial_started = time.perf_counter()
        samples, sample_rate = kokoro.create(
            text,
            voice="bm_george",
            speed=1.0,
            lang="en-gb",
            sentence_pause=0.2,
            clause_pause=0.08,
        )
        synthesis_ms = round((time.perf_counter() - trial_started) * 1000)
        duration_seconds = round(len(samples) / sample_rate, 3)
        trials.append(
            {
                "characters": len(text),
                "synthesis_ms": synthesis_ms,
                "duration_seconds": duration_seconds,
                "real_time_factor": round((synthesis_ms / 1000) / duration_seconds, 3),
            }
        )
        if session.get_providers()[0] != "CUDAExecutionProvider":
            raise RuntimeError("Kokoro fell back from CUDA during synthesis.")

    provider = session.get_providers()[0]
    result = {
        "ok": True,
        "provider": provider,
        "voice": "bm_george",
        "model": MODEL.name,
        "model_load_ms": load_ms,
        "trials": trials,
        "warm_real_time_factor": trials[-1]["real_time_factor"],
        "meets_real_time_gate": (
            provider == "CUDAExecutionProvider"
            and trials[-1]["real_time_factor"] < 0.75
        ),
    }
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["meets_real_time_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(run())
