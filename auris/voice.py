from __future__ import annotations

import atexit
import json
import os
import queue
import re
import subprocess
import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, TextIO
from uuid import uuid4

from auris.auth import harden_private_directory
from auris.database import get_background_voice_state
from auris.speech_text import SpeechPlan, prepare_speech


ROOT = Path(__file__).resolve().parents[1]
LISTEN_SCRIPT = ROOT / "scripts" / "listen_once.ps1"
WAKE_SCRIPT = ROOT / "scripts" / "listen_wake_word.ps1"
INTERRUPT_SCRIPT = ROOT / "scripts" / "listen_interrupt.ps1"
SPEAK_SCRIPT = ROOT / "scripts" / "speak.ps1"
PLAY_SCRIPT = ROOT / "scripts" / "play_voice.ps1"
VOICE_INPUT_WORKER_SCRIPT = ROOT / "scripts" / "voice_input_worker.ps1"
DAEMON_STATUS_PATH = ROOT / "data" / "voice-daemon-status.json"
VOICE_PYTHON = ROOT / ".voice-venv" / "Scripts" / "python.exe"
KOKORO_PYTHON = ROOT / ".voice-gpu-venv" / "Scripts" / "python.exe"
SPEECH_PYTHON = ROOT / ".speech-venv" / "Scripts" / "python.exe"
PIPER_MODEL = ROOT / "data" / "voice" / "piper" / "en_GB-northern_english_male-medium.onnx"
PIPER_CONFIG = PIPER_MODEL.with_suffix(".onnx.json")
KOKORO_MODEL = ROOT / "data" / "voice" / "kokoro" / "kokoro-v1.0.fp16.onnx"
KOKORO_VOICES = ROOT / "data" / "voice" / "kokoro" / "voices-v1.0.bin"
VOICE_RUNTIME_DIR = ROOT / "data" / "voice" / "runtime"
AURIS_VOICE_NAME = "AURIS Vale"
SAPI_VOICE_NAME = "Microsoft David Desktop - English (United States)"
NEURAL_PROVIDERS = {"local_kokoro", "local_piper"}

_SPEECH_LOCK = threading.RLock()
_CURRENT_PLAYBACK_PROCESS: subprocess.Popen[str] | None = None
_CURRENT_GENERATION = 0
_SPEECH_PHASE = "idle"
_SPEECH_SENTIMENT = "neutral"
_LAST_ERROR: str | None = None
_LAST_SYNTHESIS_MS: int | None = None
_LAST_AUDIO_SECONDS: float | None = None
_LAST_FIRST_AUDIO_MS: int | None = None
_LAST_STREAM_CHUNKS = 0
_SELECTED_PROVIDER = ""
_INPUT_PHASE = "idle"
_INPUT_PARTIAL_TEXT = ""
_INPUT_AUDIO_LEVEL = 0
_INPUT_DBFS: float | None = None
_LAST_INPUT_OBSERVATION: dict[str, Any] = {}
_LAST_INPUT_PEAK_AUDIO_LEVEL: int | None = None
_LAST_RECOGNITION_MS: int | None = None
_LAST_INPUT_ERROR: str | None = None
_INPUT_PRIORITY_PENDING = threading.Event()
_INPUT_PRIORITY_COUNT = 0
_INPUT_CAPTURE_GENERATION = 0
_VOICE_RUNTIME_PRIVATE = False
_NATIVE_PLAYBACK_OWNER: Any = None


def _signal_input_cancel(event_name: str, process_id: int) -> bool:
    if os.name != "nt" or not re.fullmatch(rf"Local\\AURISVoiceInputCancel-{process_id}-[0-9a-f-]{{36}}", event_name):
        return False
    import ctypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenEventW.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.OpenEventW.restype = ctypes.c_void_p
    kernel.SetEvent.argtypes = [ctypes.c_void_p]
    kernel.SetEvent.restype = ctypes.c_bool
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenEventW(0x0002, False, event_name)
    if not handle:
        return False
    try:
        return bool(kernel.SetEvent(handle))
    finally:
        kernel.CloseHandle(handle)


def _ensure_private_voice_runtime() -> None:
    global _VOICE_RUNTIME_PRIVATE
    with _SPEECH_LOCK:
        if not _VOICE_RUNTIME_PRIVATE:
            VOICE_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            if not harden_private_directory(VOICE_RUNTIME_DIR):
                raise RuntimeError("The temporary voice directory could not be made private.")
            _VOICE_RUNTIME_PRIVATE = True


class _NativeWavePlayback:
    """Cancelable Windows playback with the same wait contract as the fallback process."""

    def __init__(self, path: Path, duration: float, generation: int) -> None:
        import winsound
        global _NATIVE_PLAYBACK_OWNER
        self._winsound = winsound
        self._stopped = threading.Event()
        self.returncode: int | None = None
        self._deadline = time.monotonic() + max(0.1, duration) + 0.1
        with _SPEECH_LOCK:
            if generation != _CURRENT_GENERATION:
                self.returncode = 1
                self._stopped.set()
                return
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            self._deadline = time.monotonic() + max(0.1, duration) + 0.1
            _NATIVE_PLAYBACK_OWNER = self

    def poll(self) -> int | None:
        if self.returncode is None and time.monotonic() >= self._deadline:
            self.returncode = 0
        return self.returncode

    def communicate(self, *, timeout: float) -> tuple[str, str]:
        global _NATIVE_PLAYBACK_OWNER
        remaining = max(0.0, self._deadline - time.monotonic())
        self._stopped.wait(min(remaining, timeout))
        if not self._stopped.is_set() and remaining > timeout:
            raise subprocess.TimeoutExpired("AURIS native audio", timeout)
        if self.returncode is None:
            self.returncode = 0
        with _SPEECH_LOCK:
            if _NATIVE_PLAYBACK_OWNER is self:
                self._winsound.PlaySound(None, 0)
                _NATIVE_PLAYBACK_OWNER = None
        return "", ""

    def terminate(self) -> None:
        global _NATIVE_PLAYBACK_OWNER
        with _SPEECH_LOCK:
            if _NATIVE_PLAYBACK_OWNER is self:
                self._winsound.PlaySound(None, 0)
                _NATIVE_PLAYBACK_OWNER = None
            self.returncode = 1
            self._stopped.set()

    def wait(self, *, timeout: float) -> int:
        self.communicate(timeout=timeout)
        return int(self.returncode or 0)

    def kill(self) -> None:
        self.terminate()


def _start_audio_playback(path: Path, duration: float, generation: int) -> Any:
    if os.name == "nt":
        return _NativeWavePlayback(path, duration, generation)
    return subprocess.Popen(
        _powershell_command(PLAY_SCRIPT, "-Path", str(path)), cwd=ROOT,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, creationflags=_hidden_window_flag(),
    )


class SpeechInputPreempted(RuntimeError):
    pass


class _NeuralWorker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._ready = False
        self._details: dict[str, Any] = {}
        self._provider = ""

    def ready(self) -> bool:
        if not self._lock.acquire(blocking=False):
            return bool(self._ready and self._process and self._process.poll() is None)
        try:
            return bool(self._ready and self._process and self._process.poll() is None)
        finally:
            self._lock.release()

    def details(self) -> dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            return dict(self._details)
        try:
            return dict(self._details)
        finally:
            self._lock.release()

    def ensure_started(self, provider: str) -> dict[str, Any]:
        with self._lock:
            if (
                self._ready
                and self._provider == provider
                and self._process
                and self._process.poll() is None
            ):
                return dict(self._details)
            self._stop_locked()
            self._start_locked(provider)
            return dict(self._details)

    def synthesise(
        self,
        plan: SpeechPlan,
        output_path: Path,
        provider: str,
        *,
        should_run: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if (
                not self._ready
                or self._provider != provider
                or not self._process
                or self._process.poll() is not None
            ):
                self._start_locked(provider)
            if should_run is not None and not should_run():
                return {"ok": True, "stopped": True}
            process = self._process
            if process is None or process.stdin is None or process.stdout is None:
                raise RuntimeError("The local AURIS neural voice worker is unavailable.")
            request_id = str(uuid4())
            request = {
                "operation": "synthesise",
                "request_id": request_id,
                "text": plan.text,
                "speed": plan.speed,
                "sentiment": plan.sentiment,
                "output_path": str(output_path),
            }
            try:
                process.stdin.write(json.dumps(request, ensure_ascii=True, separators=(",", ":")) + "\n")
                process.stdin.flush()
                line = _readline_with_timeout(process.stdout, timeout_seconds=45)
                response = _last_json_object(line)
            except (BrokenPipeError, OSError, TimeoutError, RuntimeError):
                self._stop_locked()
                raise
            if not response or response.get("request_id") != request_id:
                self._stop_locked()
                raise RuntimeError("The local neural voice worker returned an invalid response.")
            return response

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def _start_locked(self, provider: str) -> None:
        self._stop_locked()
        if provider not in NEURAL_PROVIDERS or not _neural_assets_available(provider):
            raise RuntimeError("The local AURIS neural voice runtime is incomplete.")
        _ensure_private_voice_runtime()
        command = _neural_worker_command(provider)
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=_hidden_window_flag(),
        )
        self._process = process
        line = _readline_with_timeout(process.stdout, timeout_seconds=25)
        payload = _last_json_object(line)
        if (
            process.poll() is not None
            or not payload
            or payload.get("type") != "ready"
            or payload.get("provider") != provider
        ):
            self._stop_locked()
            raise RuntimeError("The local AURIS neural voice worker did not become ready.")
        self._ready = True
        self._provider = provider
        self._details = payload

    def _stop_locked(self) -> None:
        process = self._process
        self._process = None
        self._ready = False
        self._provider = ""
        self._details = {}
        if process is None or process.poll() is not None:
            return
        try:
            if process.stdin is not None:
                process.stdin.write('{"operation":"shutdown"}\n')
                process.stdin.flush()
            process.wait(timeout=2)
        except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
            _terminate_process(process)


class _SpeechInputWorker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._ready = False
        self._details: dict[str, Any] = {}
        self._state_lock = threading.Lock()
        self._active_mode = ""
        self._generation = 0

    def ready(self) -> bool:
        if not self._lock.acquire(blocking=False):
            return bool(self._ready and self._process and self._process.poll() is None)
        try:
            return bool(self._ready and self._process and self._process.poll() is None)
        finally:
            self._lock.release()

    def details(self) -> dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            return dict(self._details)
        try:
            return dict(self._details)
        finally:
            self._lock.release()

    def ensure_started(self) -> dict[str, Any]:
        with self._lock:
            if self._ready and self._process and self._process.poll() is None:
                return dict(self._details)
            self._start_locked()
            return dict(self._details)

    def listen(
        self,
        mode: str,
        timeout_seconds: int,
        *,
        on_partial: Callable[[dict[str, Any]], None] | None = None,
        on_audio_level: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        if mode not in {"command", "wake", "interrupt"}:
            raise ValueError("The AURIS speech-input mode is unsupported.")
        with self._lock:
            if not self._ready or not self._process or self._process.poll() is not None:
                self._start_locked()
            process = self._process
            if process is None or process.stdin is None or process.stdout is None:
                raise RuntimeError("The AURIS speech-input worker is unavailable.")
            request_id = str(uuid4())
            request = {
                "operation": "listen",
                "request_id": request_id,
                "mode": mode,
                "timeout_seconds": timeout_seconds,
            }
            with self._state_lock:
                self._active_mode = mode
                generation = self._generation
            try:
                process.stdin.write(json.dumps(request, ensure_ascii=True, separators=(",", ":")) + "\n")
                process.stdin.flush()
                deadline = time.monotonic() + timeout_seconds + (36 if self._details.get("provider") == "local_whisper_stream" else 6)
                while True:
                    remaining = max(1, round(deadline - time.monotonic()))
                    if time.monotonic() >= deadline:
                        raise TimeoutError("The AURIS speech-input worker timed out.")
                    line = _readline_with_timeout(process.stdout, timeout_seconds=remaining)
                    response = _last_json_object(line)
                    if not response or response.get("request_id") != request_id:
                        raise RuntimeError("The AURIS speech-input worker returned an invalid response.")
                    if response.get("type") == "partial":
                        if on_partial is not None:
                            on_partial(response)
                        continue
                    if response.get("type") == "audio_level":
                        if on_audio_level is not None:
                            on_audio_level(response)
                        continue
                    if response.get("type") == "phase" and response.get("phase") == "interpreting_speech":
                        if on_partial is not None:
                            on_partial(response)
                        continue
                    if response.get("type") == "phase" and response.get("phase") == "listening":
                        if on_partial is not None:
                            on_partial(response)
                        continue
                    if response.get("type") != "result":
                        raise RuntimeError("The AURIS speech-input worker returned an unsupported event.")
                    if response.get("restart_required"):
                        provider = self._details.get("provider")
                        self._stop_locked()
                        return {**response, "input_provider": provider}
                    with self._state_lock:
                        if generation != self._generation:
                            raise SpeechInputPreempted("The wake listener yielded to a priority request.")
                    return response
            except SpeechInputPreempted:
                raise
            except (BrokenPipeError, OSError, TimeoutError, RuntimeError) as error:
                with self._state_lock:
                    preempted = generation != self._generation
                self._stop_locked()
                if preempted:
                    raise SpeechInputPreempted("The wake listener yielded to a priority request.") from error
                raise
            finally:
                with self._state_lock:
                    if generation == self._generation:
                        self._active_mode = ""

    def preempt_wake(self) -> bool:
        with self._state_lock:
            if self._active_mode != "wake":
                return False
            self._generation += 1
            self._active_mode = ""
            process = self._process
            event_name = str(self._details.get("cancel_event") or "")
            worker_pid = self._details.get("pid")
        if process is not None:
            actual_pid = worker_pid if isinstance(worker_pid, int) and 0 < worker_pid < 2**31 else process.pid
            if not _signal_input_cancel(event_name, actual_pid):
                _terminate_process(process)
        return True

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def _start_locked(self) -> None:
        self._stop_locked()
        if not VOICE_INPUT_WORKER_SCRIPT.exists():
            raise RuntimeError("The AURIS speech-input worker script is missing.")
        from auris.speech_input_worker import MODEL_DIR, MODEL_ASSETS
        candidates = []
        if SPEECH_PYTHON.is_file() and all((MODEL_DIR / name).is_file() for name in MODEL_ASSETS):
            candidates.append(("local_whisper_stream", [str(SPEECH_PYTHON), "-m", "auris.speech_input_worker"]))
        candidates.append(("windows_system_speech_stream", _powershell_command(VOICE_INPUT_WORKER_SCRIPT)))
        failures = []
        for provider, command in candidates:
            try:
                process = subprocess.Popen(
                    command, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                    bufsize=1, creationflags=_hidden_window_flag(),
                )
                self._process = process
                payload = _last_json_object(_readline_with_timeout(process.stdout, timeout_seconds=20))
                if process.poll() is not None or not payload or payload.get("type") != "ready" or payload.get("provider") != provider:
                    raise RuntimeError(str((payload or {}).get("error") or "The speech-input worker did not become ready."))
                self._ready = True
                self._details = {**payload, "fallback_reason": "; ".join(failures)[:300] or None}
                return
            except Exception as error:
                failures.append(f"{provider}: {str(error)[:200]}")
                self._stop_locked()
        raise RuntimeError("; ".join(failures)[:300])

    def _stop_locked(self) -> None:
        process = self._process
        self._process = None
        self._ready = False
        self._details = {}
        with self._state_lock:
            self._active_mode = ""
        if process is None or process.poll() is not None:
            return
        try:
            if process.stdin is not None:
                process.stdin.write('{"operation":"shutdown"}\n')
                process.stdin.flush()
            process.wait(timeout=3)
        except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
            _terminate_process(process)


_NEURAL_WORKER = _NeuralWorker()
_SPEECH_INPUT_WORKER = _SpeechInputWorker()


def listen_once(timeout_seconds: int = 8) -> dict[str, Any]:
    timeout_seconds = max(2, min(timeout_seconds, 20))
    return _listen_with_broker(
        "command",
        timeout_seconds,
        fallback_script=LISTEN_SCRIPT,
        fallback_error="Windows speech recognition returned no usable result.",
    )


def listen_for_wake_word(timeout_seconds: int = 20) -> dict[str, Any]:
    timeout_seconds = max(5, min(timeout_seconds, 30))
    return _listen_with_broker(
        "wake",
        timeout_seconds,
        fallback_script=WAKE_SCRIPT,
        fallback_error="Windows wake-word recognition returned no result.",
    )


def listen_for_interrupt(timeout_seconds: int = 5) -> dict[str, Any]:
    timeout_seconds = max(2, min(timeout_seconds, 10))
    return _listen_with_broker(
        "interrupt",
        timeout_seconds,
        fallback_script=INTERRUPT_SCRIPT,
        fallback_error="Windows interruption recognition returned no result.",
    )


def _listen_with_broker(
    mode: str,
    timeout_seconds: int,
    *,
    fallback_script: Path,
    fallback_error: str,
) -> dict[str, Any]:
    global _INPUT_PHASE, _INPUT_PARTIAL_TEXT, _INPUT_AUDIO_LEVEL, _INPUT_DBFS, _LAST_INPUT_OBSERVATION
    global _LAST_INPUT_PEAK_AUDIO_LEVEL, _LAST_RECOGNITION_MS, _LAST_INPUT_ERROR
    global _INPUT_PRIORITY_COUNT, _INPUT_CAPTURE_GENERATION
    phase = {
        "command": "listening_for_command",
        "wake": "listening_for_wake_word",
        "interrupt": "listening_for_interrupt",
    }[mode]
    priority_request = mode != "wake"
    capture_generation = None
    if priority_request:
        with _SPEECH_LOCK:
            _INPUT_PRIORITY_COUNT += 1
            _INPUT_PRIORITY_PENDING.set()
        _SPEECH_INPUT_WORKER.preempt_wake()
    elif _INPUT_PRIORITY_PENDING.is_set():
        return {
            "ok": False,
            "error": "Wake listening yielded to a priority voice request.",
            "preempted": True,
            "audio_stored": False,
            "input_provider": _SPEECH_INPUT_WORKER.details().get("provider") or "windows_system_speech_stream",
            "streaming": True,
        }

    def update_partial(event: dict[str, Any]) -> None:
        global _INPUT_PARTIAL_TEXT, _INPUT_PHASE
        text = " ".join(str(event.get("text") or "").split())[:500]
        with _SPEECH_LOCK:
            if capture_generation == _INPUT_CAPTURE_GENERATION:
                if event.get("phase") == "interpreting_speech":
                    _INPUT_PHASE = "interpreting_speech"
                elif event.get("phase") == "listening":
                    _INPUT_PHASE = phase
                _INPUT_PARTIAL_TEXT = text

    def update_audio_level(event: dict[str, Any]) -> None:
        global _INPUT_AUDIO_LEVEL, _LAST_INPUT_PEAK_AUDIO_LEVEL, _INPUT_DBFS
        level = max(0, min(100, int(event.get("level") or 0)))
        peak = max(level, min(100, int(event.get("peak") or 0)))
        with _SPEECH_LOCK:
            if capture_generation == _INPUT_CAPTURE_GENERATION:
                _INPUT_AUDIO_LEVEL = level
                dbfs = event.get("dbfs")
                _INPUT_DBFS = float(dbfs) if isinstance(dbfs, (int, float)) and -120 <= dbfs <= 0 else None
                _LAST_INPUT_PEAK_AUDIO_LEVEL = max(
                    peak,
                    int(_LAST_INPUT_PEAK_AUDIO_LEVEL or 0),
                )

    try:
        with _microphone_mutex(timeout_seconds + 8):
            with _SPEECH_LOCK:
                _INPUT_CAPTURE_GENERATION += 1
                capture_generation = _INPUT_CAPTURE_GENERATION
                _INPUT_PHASE = phase
                _INPUT_PARTIAL_TEXT = ""
                _INPUT_AUDIO_LEVEL = 0
                _INPUT_DBFS = None
                _LAST_INPUT_PEAK_AUDIO_LEVEL = 0
                _LAST_INPUT_ERROR = None
            try:
                payload = _SPEECH_INPUT_WORKER.listen(
                    mode,
                    timeout_seconds,
                    on_partial=update_partial,
                    on_audio_level=update_audio_level,
                )
                payload = {
                    key: value
                    for key, value in payload.items()
                    if key not in {"type", "request_id"}
                }
                payload["input_provider"] = payload.get("input_provider") or _SPEECH_INPUT_WORKER.details().get("provider") or "windows_system_speech_stream"
                payload["streaming"] = True
            except SpeechInputPreempted:
                payload = {
                    "ok": False,
                    "error": "Wake listening yielded to a priority voice request.",
                    "preempted": True,
                    "audio_stored": False,
                    "input_provider": _SPEECH_INPUT_WORKER.details().get("provider") or "windows_system_speech_stream",
                    "streaming": True,
                }
            except Exception as worker_error:
                with _SPEECH_LOCK:
                    _LAST_INPUT_ERROR = str(worker_error)[:300]
                payload = _legacy_listen(fallback_script, timeout_seconds, fallback_error)
                payload["input_provider"] = "windows_system_speech_legacy"
                payload["streaming"] = False
        recognition_ms = payload.get("recognition_ms")
        if recognition_ms is not None:
            with _SPEECH_LOCK:
                _LAST_RECOGNITION_MS = max(0, int(recognition_ms))
        peak_audio_level = payload.get("peak_audio_level")
        if peak_audio_level is not None:
            with _SPEECH_LOCK:
                _LAST_INPUT_PEAK_AUDIO_LEVEL = max(0, min(100, int(peak_audio_level)))
        if not payload.get("preempted"):
            with _SPEECH_LOCK:
                observation = {key: payload.get(key) for key in (
                    "signal_state", "peak_dbfs", "sampled_frames", "voiced_frames", "audio_level_kind", "error_code"
                )}
                observation.update(mode=mode, _observed=time.monotonic())
                prior_manual_issue = (_LAST_INPUT_OBSERVATION.get("mode") == "command" and _LAST_INPUT_OBSERVATION.get("error_code") == "input_too_quiet")
                if not (mode == "wake" and not payload.get("ok") and prior_manual_issue):
                    _LAST_INPUT_OBSERVATION = observation
                if not payload.get("ok") and (payload.get("error_code") in {"input_overflow", "input_stalled"} or (mode == "command" and payload.get("error_code") == "input_too_quiet")):
                    _LAST_INPUT_ERROR = str(payload.get("error") or "Microphone input requires attention.")[:300]
        return payload
    finally:
        with _SPEECH_LOCK:
            if priority_request:
                _INPUT_PRIORITY_COUNT = max(0, _INPUT_PRIORITY_COUNT - 1)
                if not _INPUT_PRIORITY_COUNT:
                    _INPUT_PRIORITY_PENDING.clear()
            if capture_generation == _INPUT_CAPTURE_GENERATION:
                _INPUT_PHASE = "idle"
                _INPUT_PARTIAL_TEXT = ""
                _INPUT_AUDIO_LEVEL = 0
                _INPUT_DBFS = None


def _legacy_listen(script: Path, timeout_seconds: int, fallback_error: str) -> dict[str, Any]:
    started = time.perf_counter()
    result = subprocess.run(
        _powershell_command(script, "-TimeoutSeconds", str(timeout_seconds)),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds + 8,
        check=False,
        creationflags=_hidden_window_flag(),
    )
    payload = _last_json_object(result.stdout) or {
        "ok": False,
        "error": result.stderr.strip() or fallback_error,
    }
    payload["recognition_ms"] = round((time.perf_counter() - started) * 1000)
    payload["audio_stored"] = False
    return payload


def speak(text: str, rate: int = 0, asynchronous: bool = True, *, voice_turn_id: str | None = None) -> dict[str, Any]:
    from auris.voice_turns import VOICE_TURNS

    plan = prepare_speech(text, requested_rate=rate)
    VOICE_TURNS.speech_queued(voice_turn_id, suppressed=not bool(plan.text))
    if not plan.text:
        return {"ok": True, "queued": False, "suppressed": True, "spoken_characters": 0}
    provider = selected_voice_provider()
    generation = _begin_speech(plan)
    base = {
        "ok": True,
        "voice": AURIS_VOICE_NAME if provider in NEURAL_PROVIDERS else SAPI_VOICE_NAME,
        "provider": provider,
        "queued": bool(asynchronous),
        "sentiment": plan.sentiment,
        "sentiment_confidence": plan.confidence,
        "energy": plan.energy,
        "speed": plan.speed,
        "spoken_characters": len(plan.text),
    }
    if asynchronous:
        worker = threading.Thread(
            target=_execute_speech,
            args=(plan, provider, generation, voice_turn_id),
            name="auris-speech-output",
            daemon=True,
        )
        worker.start()
        return base
    return {**base, **_execute_speech(plan, provider, generation, voice_turn_id), "queued": False}


def stop_speaking() -> dict[str, Any]:
    global _CURRENT_GENERATION, _CURRENT_PLAYBACK_PROCESS, _SPEECH_PHASE
    with _SPEECH_LOCK:
        process = _CURRENT_PLAYBACK_PROCESS
        active = _SPEECH_PHASE != "idle" or bool(process and process.poll() is None)
        _CURRENT_GENERATION += 1
        _CURRENT_PLAYBACK_PROCESS = None
        _SPEECH_PHASE = "idle"
    if process is not None:
        _terminate_process(process)
    return {
        "ok": True,
        "stopped": active,
        "message": "The active spoken response was stopped." if active else "No spoken response is active.",
    }


def speech_active() -> bool:
    with _SPEECH_LOCK:
        return _SPEECH_PHASE != "idle"


def prime_voice_engine(*, blocking: bool = False) -> None:
    provider = selected_voice_provider()

    def warm_output() -> None:
        global _LAST_ERROR, _SELECTED_PROVIDER
        candidates = [provider]
        if provider == "local_kokoro" and _piper_assets_available():
            candidates.append("local_piper")
        if provider in NEURAL_PROVIDERS:
            candidates.append("windows_sapi")

        failures: list[str] = []
        for candidate in candidates:
            if candidate in NEURAL_PROVIDERS:
                try:
                    _NEURAL_WORKER.ensure_started(candidate)
                except Exception as error:
                    failures.append(f"{candidate}: {str(error)[:180]}")
                    continue
            with _SPEECH_LOCK:
                _SELECTED_PROVIDER = candidate
                _LAST_ERROR = None
            return

        with _SPEECH_LOCK:
            _LAST_ERROR = "; ".join(failures)[:300] or "No AURIS speech output is available."

    def warm_input() -> None:
        global _LAST_INPUT_ERROR
        try:
            _SPEECH_INPUT_WORKER.ensure_started()
            with _SPEECH_LOCK:
                _LAST_INPUT_ERROR = None
        except Exception as error:
            with _SPEECH_LOCK:
                _LAST_INPUT_ERROR = str(error)[:300]

    output_needs_warmup = provider in NEURAL_PROVIDERS and not _NEURAL_WORKER.ready()
    input_needs_warmup = not _SPEECH_INPUT_WORKER.ready()
    if blocking:
        if output_needs_warmup:
            warm_output()
        if input_needs_warmup:
            warm_input()
        return
    if output_needs_warmup:
        threading.Thread(target=warm_output, name="auris-voice-warmup", daemon=True).start()
    if input_needs_warmup:
        threading.Thread(target=warm_input, name="auris-speech-input-warmup", daemon=True).start()


def selected_voice_provider() -> str:
    global _SELECTED_PROVIDER
    with _SPEECH_LOCK:
        if not _SELECTED_PROVIDER:
            configured = os.environ.get("AURIS_TTS_PROVIDER", "auto").strip().casefold()
            if configured not in {"auto", "kokoro", "piper", "sapi"}:
                configured = "auto"
            if configured == "kokoro":
                _SELECTED_PROVIDER = "local_kokoro"
            elif configured == "piper":
                _SELECTED_PROVIDER = "local_piper"
            elif configured == "sapi":
                _SELECTED_PROVIDER = "windows_sapi"
            else:
                if _kokoro_assets_available():
                    _SELECTED_PROVIDER = "local_kokoro"
                elif _piper_assets_available():
                    _SELECTED_PROVIDER = "local_piper"
                else:
                    _SELECTED_PROVIDER = "windows_sapi"
        return _SELECTED_PROVIDER


def voice_status() -> dict[str, Any]:
    from auris.voice_turns import VOICE_TURNS

    background = get_background_voice_state()
    daemon = _daemon_status()
    provider = selected_voice_provider()
    with _SPEECH_LOCK:
        phase = _SPEECH_PHASE
        sentiment = _SPEECH_SENTIMENT
        last_error = _LAST_ERROR
        synthesis_ms = _LAST_SYNTHESIS_MS
        audio_seconds = _LAST_AUDIO_SECONDS
        first_audio_ms = _LAST_FIRST_AUDIO_MS
        stream_chunks = _LAST_STREAM_CHUNKS
        input_phase = _INPUT_PHASE
        input_partial = _INPUT_PARTIAL_TEXT
        input_audio_level = _INPUT_AUDIO_LEVEL
        input_dbfs = _INPUT_DBFS
        observation = dict(_LAST_INPUT_OBSERVATION)
        observed = observation.pop("_observed", None)
        observation["age_seconds"] = round(max(0, time.monotonic() - observed), 1) if observed is not None else None
        peak_input_audio_level = _LAST_INPUT_PEAK_AUDIO_LEVEL
        recognition_ms = _LAST_RECOGNITION_MS
        input_error = _LAST_INPUT_ERROR
    worker = _NEURAL_WORKER.details()
    input_worker = _SPEECH_INPUT_WORKER.details()
    input_online = _SPEECH_INPUT_WORKER.ready()
    outputs = {
        "local_kokoro": "Local Kokoro CUDA neural TTS",
        "local_piper": "Local Piper neural TTS",
        "windows_sapi": "Windows SAPI fallback",
    }
    return {
        "input": "Local Whisper speech with WebRTC VAD" if input_online and input_worker.get("provider") == "local_whisper_stream" else "Persistent Windows System.Speech stream" if input_online else "Windows System.Speech fallback",
        "input_provider": input_worker.get("provider") or "windows_system_speech_legacy",
        "input_worker_online": input_online,
        "input_worker_pid": input_worker.get("pid"),
        "input_recognizer": input_worker.get("recognizer"),
        "input_recognizer_id": input_worker.get("recognizer_id"),
        "input_microphone": input_worker.get("microphone"),
        "input_fallback_reason": input_worker.get("fallback_reason"),
        "input_audio_storage": "memory_only",
        "input_streaming_mode": "vad_segmented_utterances" if input_worker.get("provider") == "local_whisper_stream" else "windows_events",
        "input_wake_strategy": input_worker.get("wake_strategy") or "legacy_keyword",
        "input_capture_active": input_phase != "idle",
        "input_phase": input_phase,
        "input_partial_transcript": input_partial,
        "input_audio_level": input_audio_level,
        "input_dbfs": input_dbfs,
        "input_observation": observation,
        "last_peak_audio_level": peak_input_audio_level,
        "last_recognition_ms": recognition_ms,
        "last_input_error": input_error,
        "output": outputs[provider],
        "provider": provider,
        "voice": AURIS_VOICE_NAME if provider in NEURAL_PROVIDERS else SAPI_VOICE_NAME,
        "persona": "AURIS Vale // composed British male",
        "languages": ["en-GB"],
        "push_to_talk": True,
        "wake_word": True,
        "wake_phrases": ["AURIS", "Hey AURIS", "Okay AURIS"],
        "continuous_mode": False,
        "wake_command_mode": "single_utterance_or_silent_two_stage" if input_worker.get("accepts_continuous_commands") else "silent_two_stage",
        "wake_acknowledgement": "silent",
        "continuous_wake_commands": bool(input_online and input_worker.get("accepts_continuous_commands")),
        "priority_input_without_reload": bool(input_worker.get("cancel_event")),
        "passive_acknowledgements_suppressed": True,
        "playback_engine": "windows_native_wave" if os.name == "nt" and provider in NEURAL_PROVIDERS else "powershell",
        "background_enabled": bool(background.get("enabled")),
        "background_daemon_online": daemon["online"],
        "background_daemon_pid": daemon.get("pid"),
        "background_state": daemon.get("state"),
        "natural_interruption": True,
        "interrupt_phrases": [
            "stop",
            "AURIS stop",
            "pause",
            "cancel",
            "do not send it",
            "let me take over",
            "change the plan",
        ],
        "voice_activity_detection": input_online,
        "speaker_turn_detection": input_online,
        "speaking": phase != "idle",
        "speech_phase": phase,
        "sentiment": sentiment,
        "emotion_aware_delivery": True,
        "spoken_markup_normalisation": True,
        "single_voice_broker": True,
        "provider_locked_for_session": True,
        "browser_voice_fallback": False,
        "audio_storage": "temporary_wav_deleted_after_playback",
        "neural_assets_installed": _neural_assets_available(provider),
        "neural_worker_online": _NEURAL_WORKER.ready(),
        "neural_worker_pid": worker.get("pid"),
        "neural_execution_provider": worker.get("engine"),
        "last_synthesis_ms": synthesis_ms,
        "last_audio_seconds": audio_seconds,
        "last_first_audio_ms": first_audio_ms,
        "last_stream_chunks": stream_chunks,
        "last_error": last_error,
        "streaming_input": input_online,
        "streaming_output": provider in NEURAL_PROVIDERS,
        "output_streaming_mode": "sentence_pipeline" if provider in NEURAL_PROVIDERS else "unavailable",
        "full_duplex": False,
        "recent_turns": VOICE_TURNS.snapshot()[:8],
        "diagnostic_storage": "memory_only_15_minutes",
    }


def write_daemon_status(state: str, **details: Any) -> None:
    payload = {
        "pid": os.getpid(),
        "state": state,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **details,
    }
    DAEMON_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = DAEMON_STATUS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=True), encoding="ascii")
    temporary.replace(DAEMON_STATUS_PATH)


def _begin_speech(plan: SpeechPlan) -> int:
    global _CURRENT_GENERATION, _CURRENT_PLAYBACK_PROCESS, _SPEECH_PHASE, _SPEECH_SENTIMENT
    global _LAST_FIRST_AUDIO_MS, _LAST_SYNTHESIS_MS, _LAST_AUDIO_SECONDS, _LAST_STREAM_CHUNKS
    with _SPEECH_LOCK:
        process = _CURRENT_PLAYBACK_PROCESS
        _CURRENT_PLAYBACK_PROCESS = None
        _CURRENT_GENERATION += 1
        generation = _CURRENT_GENERATION
        _SPEECH_PHASE = "queued"
        _SPEECH_SENTIMENT = plan.sentiment
        _LAST_FIRST_AUDIO_MS = None
        _LAST_SYNTHESIS_MS = None
        _LAST_AUDIO_SECONDS = None
        _LAST_STREAM_CHUNKS = 0
    if process is not None:
        _terminate_process(process)
    return generation


def _execute_speech(plan: SpeechPlan, provider: str, generation: int, voice_turn_id: str | None = None) -> dict[str, Any]:
    from auris.voice_turns import VOICE_TURNS

    global _LAST_ERROR
    try:
        if provider in NEURAL_PROVIDERS:
            outcome = _execute_neural_speech(plan, generation, provider, voice_turn_id=voice_turn_id) if voice_turn_id else _execute_neural_speech(plan, generation, provider)
        else:
            outcome = _execute_sapi_speech(plan, generation)
        if outcome.get("ok"):
            with _SPEECH_LOCK:
                _LAST_ERROR = None
        VOICE_TURNS.speech_finished(voice_turn_id, outcome)
        return outcome
    except Exception as error:
        message = str(error)[:300] or type(error).__name__
        with _SPEECH_LOCK:
            _LAST_ERROR = message
        outcome = {"ok": False, "error": message}
        VOICE_TURNS.speech_finished(voice_turn_id, outcome)
        return outcome
    finally:
        _finish_generation(generation)


def _execute_neural_speech(plan: SpeechPlan, generation: int, provider: str, *, voice_turn_id: str | None = None) -> dict[str, Any]:
    from auris.voice_turns import VOICE_TURNS

    global _CURRENT_PLAYBACK_PROCESS, _LAST_SYNTHESIS_MS, _LAST_AUDIO_SECONDS
    global _LAST_FIRST_AUDIO_MS, _LAST_STREAM_CHUNKS
    if not _set_phase(generation, "generating"):
        return {"ok": True, "stopped": True}
    _ensure_private_voice_runtime()
    chunks = _speech_chunks(plan.text)
    output_paths = [VOICE_RUNTIME_DIR / f"{uuid4()}.wav" for _ in chunks]
    total_synthesis_ms = 0
    total_audio_seconds = 0.0
    first_audio_ms: int | None = None
    pipeline_started = time.perf_counter()
    prefetch_thread: threading.Thread | None = None

    def synthesise_chunk(index: int) -> dict[str, Any]:
        return _NEURAL_WORKER.synthesise(
            replace(plan, text=chunks[index]),
            output_paths[index],
            provider,
            should_run=lambda: _is_current_generation(generation),
        )

    try:
        current_result = synthesise_chunk(0)
        for index, output_path in enumerate(output_paths):
            if current_result.get("stopped") or not _is_current_generation(generation):
                return {"ok": True, "stopped": True}
            if not current_result.get("ok"):
                raise RuntimeError(str(current_result.get("error") or "Local neural synthesis failed."))
            if not output_path.exists() or output_path.stat().st_size < 44:
                raise RuntimeError("Local neural synthesis produced no playable audio.")
            total_synthesis_ms += int(current_result.get("synthesis_ms") or 0)
            total_audio_seconds += float(current_result.get("duration_seconds") or 0)

            process = _start_audio_playback(output_path, float(current_result.get("duration_seconds") or 0), generation)
            with _SPEECH_LOCK:
                if generation != _CURRENT_GENERATION:
                    _terminate_process(process)
                    return {"ok": True, "stopped": True}
                _CURRENT_PLAYBACK_PROCESS = process
                _set_phase_locked("playing")
                if first_audio_ms is None:
                    first_audio_ms = round((time.perf_counter() - pipeline_started) * 1000)
                    _LAST_FIRST_AUDIO_MS = first_audio_ms
                    VOICE_TURNS.audio_started(voice_turn_id)
                _LAST_SYNTHESIS_MS = total_synthesis_ms
                _LAST_AUDIO_SECONDS = round(total_audio_seconds, 3)
                _LAST_STREAM_CHUNKS = len(chunks)

            prefetch: dict[str, Any] = {}
            prefetch_thread = None
            if index + 1 < len(chunks):
                def run_prefetch(next_index: int = index + 1) -> None:
                    try:
                        prefetch["result"] = synthesise_chunk(next_index)
                    except BaseException as error:
                        prefetch["error"] = error

                prefetch_thread = threading.Thread(
                    target=run_prefetch,
                    name="auris-voice-prefetch",
                    daemon=True,
                )
                prefetch_thread.start()

            try:
                _, stderr = process.communicate(timeout=180)
            except subprocess.TimeoutExpired as error:
                _terminate_process(process)
                raise RuntimeError("Local voice playback exceeded its safety timeout.") from error
            finally:
                with _SPEECH_LOCK:
                    if _CURRENT_PLAYBACK_PROCESS is process:
                        _CURRENT_PLAYBACK_PROCESS = None

            if prefetch_thread is not None:
                prefetch_thread.join(timeout=50)
                if prefetch_thread.is_alive():
                    raise RuntimeError("Local neural voice prefetch exceeded its safety timeout.")
            if process.returncode != 0:
                if not _is_current_generation(generation):
                    return {"ok": True, "stopped": True}
                raise RuntimeError(stderr.strip() or "Local neural voice playback failed.")
            if not _is_current_generation(generation):
                return {"ok": True, "stopped": True}
            if prefetch.get("error") is not None:
                raise prefetch["error"]
            if index + 1 < len(chunks):
                current_result = prefetch.get("result") or {
                    "ok": False,
                    "error": "Local neural voice prefetch returned no result.",
                }

        with _SPEECH_LOCK:
            _LAST_SYNTHESIS_MS = total_synthesis_ms
            _LAST_AUDIO_SECONDS = round(total_audio_seconds, 3)
        return {
            "ok": True,
            "stopped": False,
            "synthesis_ms": total_synthesis_ms,
            "audio_seconds": round(total_audio_seconds, 3),
            "first_audio_ms": first_audio_ms,
            "stream_chunks": len(chunks),
        }
    finally:
        if prefetch_thread is not None and prefetch_thread.is_alive():
            prefetch_thread.join(timeout=50)
        for output_path in output_paths:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass


def _speech_chunks(text: str, *, max_characters: int = 180) -> list[str]:
    normalized = " ".join(str(text or "").split()).strip()
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_characters:
            chunks.append(current)
            current = ""
        if len(sentence) <= max_characters:
            current = f"{current} {sentence}".strip()
            continue
        if current:
            chunks.append(current)
            current = ""
        remainder = sentence
        while len(remainder) > max_characters:
            window = remainder[: max_characters + 1]
            boundaries = [window.rfind(mark) for mark in ("; ", ": ", ", ", " ")]
            boundary = max(boundaries)
            if boundary < max_characters // 2:
                boundary = max_characters
            else:
                boundary += 1
            chunks.append(remainder[:boundary].strip())
            remainder = remainder[boundary:].strip()
        current = remainder
    if current:
        chunks.append(current)
    return chunks


def _execute_sapi_speech(plan: SpeechPlan, generation: int) -> dict[str, Any]:
    global _CURRENT_PLAYBACK_PROCESS
    if not _set_phase(generation, "playing"):
        return {"ok": True, "stopped": True}
    sapi_rate = max(-4, min(4, round((plan.speed - 0.95) / 0.035)))
    process = subprocess.Popen(
        _powershell_command(
            SPEAK_SCRIPT,
            "-Text",
            plan.text,
            "-Rate",
            str(sapi_rate),
            "-VoiceName",
            SAPI_VOICE_NAME,
        ),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=_hidden_window_flag(),
    )
    with _SPEECH_LOCK:
        if generation != _CURRENT_GENERATION:
            _terminate_process(process)
            return {"ok": True, "stopped": True}
        _CURRENT_PLAYBACK_PROCESS = process
    try:
        _, stderr = process.communicate(timeout=90)
    except subprocess.TimeoutExpired as error:
        _terminate_process(process)
        raise RuntimeError("Windows fallback speech exceeded its safety timeout.") from error
    if process.returncode != 0:
        if not _is_current_generation(generation):
            return {"ok": True, "stopped": True}
        raise RuntimeError(stderr.strip() or "Windows fallback speech failed.")
    return {"ok": True, "stopped": False}


def _set_phase(generation: int, phase: str) -> bool:
    with _SPEECH_LOCK:
        if generation != _CURRENT_GENERATION:
            return False
        _set_phase_locked(phase)
        return True


def _set_phase_locked(phase: str) -> None:
    global _SPEECH_PHASE
    _SPEECH_PHASE = phase


def _finish_generation(generation: int) -> None:
    global _CURRENT_PLAYBACK_PROCESS, _SPEECH_PHASE
    with _SPEECH_LOCK:
        if generation != _CURRENT_GENERATION:
            return
        _CURRENT_PLAYBACK_PROCESS = None
        _SPEECH_PHASE = "idle"


def _is_current_generation(generation: int) -> bool:
    with _SPEECH_LOCK:
        return generation == _CURRENT_GENERATION


def _piper_assets_available() -> bool:
    return all(path.exists() for path in (VOICE_PYTHON, PIPER_MODEL, PIPER_CONFIG, PLAY_SCRIPT))


def _kokoro_assets_available() -> bool:
    return all(path.exists() for path in (KOKORO_PYTHON, KOKORO_MODEL, KOKORO_VOICES, PLAY_SCRIPT))


def _neural_assets_available(provider: str) -> bool:
    if provider == "local_kokoro":
        return _kokoro_assets_available()
    if provider == "local_piper":
        return _piper_assets_available()
    return False


def _neural_worker_command(provider: str) -> list[str]:
    if provider == "local_kokoro":
        return [str(KOKORO_PYTHON), "-u", "-m", "auris.kokoro_voice_worker"]
    if provider == "local_piper":
        return [str(VOICE_PYTHON), "-u", "-m", "auris.neural_voice_worker"]
    raise ValueError("The selected AURIS neural voice provider is unsupported.")


def _powershell_command(script: Path, *arguments: str) -> list[str]:
    return [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        *arguments,
    ]


def _last_json_object(output: str) -> dict[str, Any] | None:
    for line in reversed(output.splitlines()):
        line = line.strip().lstrip("\ufeff")
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _readline_with_timeout(stream: TextIO | None, *, timeout_seconds: int) -> str:
    if stream is None:
        raise RuntimeError("The local voice worker stream is unavailable.")
    result: queue.Queue[str] = queue.Queue(maxsize=1)

    def read() -> None:
        try:
            result.put(stream.readline())
        except (OSError, ValueError):
            result.put("")

    thread = threading.Thread(target=read, name="auris-voice-worker-read", daemon=True)
    thread.start()
    try:
        line = result.get(timeout=max(1, timeout_seconds))
    except queue.Empty as error:
        raise TimeoutError("The local neural voice worker timed out.") from error
    if not line:
        raise RuntimeError("The local neural voice worker closed its output stream.")
    return line


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
        except OSError:
            pass


def _daemon_status() -> dict[str, Any]:
    try:
        payload = json.loads(DAEMON_STATUS_PATH.read_text(encoding="ascii"))
        updated = datetime.fromisoformat(payload["updated_at"])
        age = (datetime.now(timezone.utc) - updated).total_seconds()
        return {**payload, "online": age < 45}
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return {"online": False}


@contextmanager
def _microphone_mutex(timeout_seconds: int) -> Iterator[None]:
    if os.name != "nt":
        yield
        return

    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]
    kernel32.ReleaseMutex.restype = ctypes.c_bool
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool

    handle = kernel32.CreateMutexW(None, False, "Local\\AURISMicrophone")
    if not handle:
        raise OSError(ctypes.get_last_error(), "Could not create the AURIS microphone mutex.")
    wait_result = kernel32.WaitForSingleObject(handle, max(1, int(timeout_seconds * 1000)))
    if wait_result not in {0, 0x80}:
        kernel32.CloseHandle(handle)
        raise TimeoutError("The AURIS microphone is busy with another local voice request.")
    try:
        yield
    finally:
        kernel32.ReleaseMutex(handle)
        kernel32.CloseHandle(handle)


def _hidden_window_flag() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _shutdown_voice_engine() -> None:
    stop_speaking()
    _SPEECH_INPUT_WORKER.stop()
    _NEURAL_WORKER.stop()


atexit.register(_shutdown_voice_engine)
