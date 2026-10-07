from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import queue
import re
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data" / "voice" / "whisper-tiny.en"
MODEL_ASSETS = {
    "model.bin": ("sha256", "1a5afae06a4db91c975c9a9d78be5cc110ee4ea022ad57d55492e4550e936b2a"),
    "config.json": ("git", "4065bb3bed375b176d5465be117d2d202e210434"),
    "tokenizer.json": ("git", "15d7bdf9ba25718ca2504eec6a8f02bc55af0a6a"),
    "vocabulary.txt": ("git", "ee695b8d3e3c10d488304e04468efec4ca27554a"),
}
SAMPLE_RATE = 16000
FRAME_SAMPLES = 320
FRAME_BYTES = FRAME_SAMPLES * 2
WAKE_PREFIX = re.compile(r"^\s*(?:(?:hey|okay|ok)[,\s]+)?(?:auris|oris)\b[\s,.:;!?-]*", re.I)
WAKE_SPELLING_CANDIDATE = re.compile(r"^\s*(?:(?:(?:hey|okay|ok)[,\s]+)?(?:boris|or\s+(?:ease|us|is)|or(?:as|us|ies)|orie['\u2019]s)|(?:hey|okay|ok)[,\s]+worries)\b", re.I)
INTERRUPTS = {
    "stop", "pause", "cancel", "cancel that", "cancel response", "stop talking", "be quiet",
    "do not send it", "take no further action", "let me take over", "continue",
    "change the plan", "repeat that", "explain what you're doing",
}


def verify_model_assets() -> None:
    if MODEL_DIR.is_symlink() or MODEL_DIR.is_junction():
        raise RuntimeError("The local speech model directory cannot be a link.")
    for name, (algorithm, expected) in MODEL_ASSETS.items():
        path = MODEL_DIR / name
        if not path.is_file() or path.is_symlink() or path.is_junction():
            raise RuntimeError(f"The local speech model asset is unavailable: {name}")
        digest = hashlib.sha256() if algorithm == "sha256" else hashlib.sha1()
        if algorithm == "git":
            digest.update(f"blob {path.stat().st_size}\0".encode("ascii"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise RuntimeError(f"The local speech model asset failed verification: {name}")


def route_transcript(text: str, mode: str, *, avg_logprob: float, no_speech_prob: float) -> dict[str, Any]:
    if mode not in {"wake", "command", "interrupt"}:
        raise ValueError("Unsupported speech input mode.")
    text = " ".join(text.split()).strip()
    if not text or len(text) > 4000 or not math.isfinite(avg_logprob) or not math.isfinite(no_speech_prob):
        return {"ok": False, "error_code": "no_usable_speech", "error": "No usable speech was recognized."}
    if avg_logprob < -0.85 or no_speech_prob >= 0.6:
        return {"ok": False, "error_code": "speech_unclear", "error": "Speech was not clear enough to execute.", "tentative_text": text}
    result: dict[str, Any] = {
        "ok": True, "text": text, "language": "en-GB",
        "confidence": round(math.exp(min(0, avg_logprob)), 3),
        "confidence_kind": "uncalibrated_decoder_score",
    }
    prefix = WAKE_PREFIX.match(text)
    if mode == "wake":
        if not prefix:
            return {"ok": False, "error_code": "wake_phrase_missing", "error": "No leading AURIS wake phrase was recognized.", "tentative_text": text}
        canonical = "AURIS " + text[prefix.end():]
        result.update(recognized_as=canonical.strip(), text=canonical.strip(), wake_word="AURIS")
    elif mode == "interrupt":
        phrase = (text[prefix.end():] if prefix else text).casefold().strip(" .,!?:;-")
        if phrase not in INTERRUPTS:
            return {"ok": False, "error_code": "interrupt_phrase_missing", "error": "No interruption phrase was recognized."}
        result["phrase"] = phrase
    return result


class SpeechTurn:
    """Bounded utterance framing around the library's WebRTC VAD decisions."""

    def __init__(self, *, end_silence_frames: int = 30) -> None:
        self.preroll: deque[bytes] = deque(maxlen=15)
        self.frames: list[bytes] = []
        self.voiced_frames = 0
        self.silent_frames = 0
        self.end_silence_frames = end_silence_frames

    def feed(self, frame: bytes, voiced: bool) -> str:
        if len(frame) != FRAME_BYTES:
            raise ValueError("Speech input requires exactly 20 ms of mono PCM.")
        if not self.frames and not voiced:
            self.preroll.append(frame)
            return "waiting"
        if not self.frames:
            self.frames.extend(self.preroll)
            self.preroll.clear()
        self.frames.append(frame)
        self.voiced_frames += int(voiced)
        self.silent_frames = 0 if voiced else self.silent_frames + 1
        if len(self.frames) >= 1500:
            return "too_long"
        if self.silent_frames >= self.end_silence_frames:
            if self.voiced_frames >= 6:
                return "complete"
            self.frames.clear()
            self.voiced_frames = self.silent_frames = 0
            return "waiting"
        return "speaking"

    def pcm(self) -> bytes:
        return b"".join(self.frames)


class InputSignal:
    """Audio health numbers only; never retain PCM or tentative transcripts."""

    def __init__(self) -> None:
        self.frames = 0
        self.max_rms = 0.0
        self.voiced_frames = 0

    def observe(self, rms: float, voiced: bool) -> tuple[int, float]:
        self.frames += 1
        self.max_rms = max(self.max_rms, rms)
        self.voiced_frames += int(voiced)
        dbfs = self.dbfs(rms)
        return max(0, min(100, round((dbfs + 75) * 100 / 75))), dbfs

    @staticmethod
    def dbfs(rms: float) -> float:
        return round(max(-120.0, min(0.0, 20 * math.log10(max(rms, 0.001) / 32768))), 1)

    def details(self) -> dict[str, Any]:
        peak = self.dbfs(self.max_rms)
        state = "no_frames" if not self.frames else "weak_signal" if peak < -65 else "speech_detected" if self.voiced_frames >= 6 else "no_speech"
        return {"signal_state": state, "peak_dbfs": peak, "sampled_frames": self.frames,
                "voiced_frames": self.voiced_frames, "audio_level_kind": "dbfs_scaled_meter",
                "audio_signal_detected": state == "speech_detected"}


class CancelEvent:
    def __init__(self) -> None:
        self.name = f"Local\\AURISVoiceInputCancel-{os.getpid()}-{uuid4()}"
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_bool, ctypes.c_wchar_p]
        self.kernel.CreateEventW.restype = ctypes.c_void_p
        self.kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.kernel.WaitForSingleObject.restype = ctypes.c_uint32
        self.kernel.ResetEvent.argtypes = [ctypes.c_void_p]
        self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self.handle = self.kernel.CreateEventW(None, False, False, self.name)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "Could not create the speech cancellation event.")

    def signaled(self) -> bool:
        return self.kernel.WaitForSingleObject(self.handle, 0) == 0

    def reset(self) -> None:
        self.kernel.ResetEvent(self.handle)

    def close(self) -> None:
        self.kernel.CloseHandle(self.handle)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")), flush=True)


class LocalSpeechInput:
    def __init__(self) -> None:
        import numpy as np
        import sounddevice as sd
        import webrtcvad
        from faster_whisper import WhisperModel

        verify_model_assets()
        self.np = np
        self.model = WhisperModel(str(MODEL_DIR), device="cpu", compute_type="int8", cpu_threads=4, local_files_only=True)
        self.decode(bytes(SAMPLE_RATE * 2), "command")
        self.vad = webrtcvad.Vad(2)
        self.cancel = CancelEvent()
        self.capture = threading.Event()
        self.frames: queue.Queue[bytes] = queue.Queue(maxsize=100)
        self.overflow = threading.Event()
        self.stream = sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=FRAME_SAMPLES, channels=1, dtype="int16", callback=self._capture_frame)
        self.stream.start()
        self.microphone = str(sd.query_devices(self.stream.device, "input")["name"])

    def ensure_capture_active(self) -> None:
        if not self.stream.active:
            self.stream.start()

    def _capture_frame(self, data: Any, _frames: int, _time: Any, status: Any) -> None:
        if not self.capture.is_set():
            return
        if status:
            self.overflow.set()
        try:
            self.frames.put_nowait(bytes(data))
        except queue.Full:
            self.overflow.set()

    def decode(self, pcm: bytes, mode: str, *, already_segmented: bool = False) -> dict[str, Any]:
        audio = self.np.frombuffer(pcm, dtype="<i2").astype(self.np.float32) / 32768.0
        started = time.perf_counter()
        def transcribe(*, vocabulary: bool) -> list[Any]:
            segments, _info = self.model.transcribe(
                audio, language="en", beam_size=getattr(self, "beam_size", 3), temperature=0, condition_on_previous_text=False,
                initial_prompt="Names: Auris, Oris, Iris, Boris. Applications: Notepad, Spotify, Brave, YouTube." if vocabulary else None,
                vad_filter=not already_segmented, vad_parameters={"min_silence_duration_ms": 300},
            )
            return list(segments)

        # A wake-only vocabulary can rewrite other names into AURIS. Refine only
        # candidate prefixes, include competing names, and reject Iris immediately.
        segments = transcribe(vocabulary=mode != "wake")
        if not segments:
            return {"ok": False, "error_code": "no_usable_speech", "error": "No speech was recognized.",
                    "decode_ms": round((time.perf_counter() - started) * 1000)}
        text = " ".join(segment.text for segment in segments)
        if mode == "wake" and not WAKE_PREFIX.match(text):
            candidate = WAKE_SPELLING_CANDIDATE.match(text)
            if not candidate:
                result = route_transcript(text, mode, avg_logprob=min(s.avg_logprob for s in segments), no_speech_prob=max(s.no_speech_prob for s in segments))
                result["decode_ms"] = round((time.perf_counter() - started) * 1000)
                return result
            if max(s.no_speech_prob for s in segments) >= 0.6 or any(not math.isfinite(s.avg_logprob) for s in segments):
                return {"ok": False, "error_code": "speech_unclear", "error": "The wake phrase was not clear enough to confirm."}
            segments = transcribe(vocabulary=True)
            if not segments:
                return {"ok": False, "error_code": "wake_phrase_missing", "error": "The wake phrase could not be confirmed."}
            text = " ".join(segment.text for segment in segments)
        # A bad segment must not be hidden by averaging it into a good wake phrase.
        result = route_transcript(text, mode, avg_logprob=min(s.avg_logprob for s in segments), no_speech_prob=max(s.no_speech_prob for s in segments))
        result["decode_ms"] = round((time.perf_counter() - started) * 1000)
        return result

    def listen(self, request: dict[str, Any]) -> dict[str, Any]:
        mode = str(request.get("mode"))
        if mode not in {"command", "wake", "interrupt"}:
            raise ValueError("Unsupported speech input mode.")
        timeout = max(2, min(30, int(request.get("timeout_seconds", 5))))
        request_id = str(request.get("request_id", ""))
        if not re.fullmatch(r"[0-9a-f-]{36}", request_id):
            raise ValueError("Invalid speech request correlation ID.")
        if mode != "wake":
            self.cancel.reset()
        self.capture.clear()
        self.ensure_capture_active()
        while not self.frames.empty():
            try:
                self.frames.get_nowait()
            except queue.Empty:
                break
        self.overflow.clear()
        turn = SpeechTurn(end_silence_frames=20 if mode == "interrupt" else 30)
        started = time.perf_counter()
        peak = 0
        signal = InputSignal()
        last_failure: dict[str, Any] | None = None
        last_level = 0.0
        self.capture.set()
        try:
            while time.perf_counter() - started < timeout + 30:
                if mode == "wake" and self.cancel.signaled():
                    return {"ok": False, "preempted": True}
                if self.overflow.is_set():
                    return {"ok": False, **signal.details(), "signal_state": "overflow",
                            "error_code": "input_overflow", "error": "Microphone audio overflowed; this command was not executed."}
                if not signal.frames and time.perf_counter() - started >= 1.5:
                    return {"ok": False, **signal.details(), "error_code": "input_stalled",
                            "error": "The microphone stream returned no audio frames. Reconnect the microphone or reopen audio settings.",
                            "restart_required": True}
                if not turn.frames and time.perf_counter() - started >= timeout:
                    break
                try:
                    frame = self.frames.get(timeout=0.05)
                except queue.Empty:
                    continue
                values = self.np.frombuffer(frame, dtype="<i2").astype(self.np.float32)
                rms = float(self.np.sqrt(self.np.mean(values * values)))
                voiced = self.vad.is_speech(frame, SAMPLE_RATE)
                level, dbfs = signal.observe(rms, voiced)
                peak = max(peak, level)
                if time.perf_counter() - last_level >= 0.15:
                    emit({"type": "audio_level", "request_id": request_id, "level": level, "peak": peak,
                          "dbfs": dbfs, "audio_level_kind": "dbfs_scaled_meter"})
                    last_level = time.perf_counter()
                state = turn.feed(frame, voiced)
                if state == "too_long":
                    return {"ok": False, "error": "The utterance exceeded 30 seconds; no command was executed."}
                if state == "complete":
                    self.capture.clear()
                    if signal.details()["signal_state"] == "weak_signal":
                        result = {"ok": False, "error_code": "input_too_quiet",
                                  "error": "Microphone input is too quiet. Check the selected input, microphone level, and distance; no command was executed."}
                    else:
                        emit({"type": "phase", "request_id": request_id, "phase": "interpreting_speech"})
                        result = self.decode(turn.pcm(), mode, already_segmented=True)
                    if mode == "wake" and self.cancel.signaled():
                        return {"ok": False, "preempted": True}
                    result.update(**signal.details(), peak_audio_level=peak, recognition_ms=round((time.perf_counter() - started) * 1000))
                    if result.get("ok"):
                        return result
                    # An early noise burst or rejected wake must not consume the
                    # whole listening window before the user begins their command.
                    last_failure = {key: result[key] for key in ("error", "error_code", "decode_ms") if key in result}
                    turn = SpeechTurn(end_silence_frames=20 if mode == "interrupt" else 30)
                    emit({"type": "phase", "request_id": request_id, "phase": "listening"})
                    self.capture.set()
            details = signal.details()
            error = "Microphone input is too quiet. Check the selected input, microphone level, and distance; no command was executed." if details["signal_state"] == "weak_signal" else "No completed speech was detected."
            return {"ok": False, **(last_failure or {}), **details, "error": error if details["signal_state"] == "weak_signal" else (last_failure or {}).get("error", error),
                    "error_code": "input_too_quiet" if details["signal_state"] == "weak_signal" else (last_failure or {}).get("error_code", "speech_not_recognized"),
                    "peak_audio_level": peak, "recognition_ms": round((time.perf_counter() - started) * 1000)}
        finally:
            self.capture.clear()
            turn.frames.clear()
            turn.preroll.clear()
            while not self.frames.empty():
                try:
                    self.frames.get_nowait()
                except queue.Empty:
                    break

    def close(self) -> None:
        self.capture.clear()
        self.stream.stop()
        self.stream.close()
        self.cancel.close()


def main() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    listener = None
    try:
        listener = LocalSpeechInput()
        emit({
            "type": "ready", "provider": "local_whisper_stream", "pid": os.getpid(),
            "recognizer": "Whisper tiny.en / CPU int8", "language": "en-GB",
            "wake_strategy": "paired_local_transcription_final_leading_keyword", "microphone": listener.microphone,
            "cancel_event": listener.cancel.name, "accepts_continuous_commands": True,
            "wake_acknowledgement": "silent", "audio_stored": False,
        })
        for line in sys.stdin:
            request = json.loads(line)
            if request.get("operation") == "shutdown":
                break
            if request.get("operation") != "listen":
                raise ValueError("Unsupported speech input operation.")
            try:
                result = listener.listen(request)
            except Exception as error:
                result = {"ok": False, "error": str(error)[:300], "restart_required": True}
            emit({**result, "type": "result", "request_id": request.get("request_id"), "audio_stored": False})
    except Exception as error:
        emit({"type": "error", "error": str(error)[:300]})
    finally:
        if listener is not None:
            listener.close()


if __name__ == "__main__":
    main()
