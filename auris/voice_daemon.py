from __future__ import annotations

import ctypes
import os
import re
import threading
import time
from typing import Any

from auris.audit import record_event
from auris.database import get_background_voice_state, get_control_state, initialize_database
from auris.local_client import AurisLocalClient
from auris.voice import write_daemon_status


ERROR_ALREADY_EXISTS = 183
VOICE_CONVERSATION_ID = "auris-background-voice"
_IDLE_GUARD_STATE: str | None = None


def run() -> int:
    singleton = _acquire_singleton()
    if singleton is False:
        return 0

    initialize_database()
    client = AurisLocalClient()
    record_event("voice.daemon_started", {"pid": os.getpid(), "audio_storage": False})
    consecutive_errors = 0
    try:
        while True:
            try:
                _run_cycle(client)
                consecutive_errors = 0
            except Exception as error:
                consecutive_errors += 1
                delay = min(30, 2 ** min(consecutive_errors, 4))
                write_daemon_status(
                    "recovering",
                    enabled=bool(get_background_voice_state().get("enabled")),
                    error=str(error)[:300],
                    retry_in_seconds=delay,
                )
                if consecutive_errors == 1 or consecutive_errors % 10 == 0:
                    record_event(
                        "voice.daemon_recovering",
                        {"error": str(error)[:300], "consecutive_errors": consecutive_errors},
                    )
                time.sleep(delay)
    except KeyboardInterrupt:
        return 0
    finally:
        _stop_broker_speech(client)
        record_event("voice.daemon_stopped", {"pid": os.getpid()})
        _release_singleton(singleton)


def _run_cycle(client: AurisLocalClient | None = None) -> None:
    global _IDLE_GUARD_STATE
    client = client or AurisLocalClient()
    control = get_control_state()
    voice = get_background_voice_state()
    if control["stopped"]:
        if _IDLE_GUARD_STATE != "stopped":
            _stop_broker_speech(client)
        _IDLE_GUARD_STATE = "stopped"
        write_daemon_status("stopped", enabled=bool(voice["enabled"]))
        time.sleep(1)
        return
    if not voice["enabled"]:
        if _IDLE_GUARD_STATE != "disabled":
            _stop_broker_speech(client)
        _IDLE_GUARD_STATE = "disabled"
        write_daemon_status("disabled", enabled=False)
        time.sleep(1)
        return

    _IDLE_GUARD_STATE = None
    write_daemon_status("listening_for_wake_word", enabled=True, accepts_continuous_command=True)
    wake = client.listen_for_wake_word(timeout_seconds=5)
    if not wake.get("ok"):
        if wake.get("audio_signal_detected"):
            write_daemon_status(
                "wake_not_understood",
                enabled=True,
                error=str(wake.get("error") or "Wake phrase was not understood.")[:200],
                confidence=wake.get("confidence"),
                peak_audio_level=wake.get("peak_audio_level"),
            )
        time.sleep(0.15)
        return

    record_event(
        "voice.wake_detected",
        {
            "language": wake.get("language"),
            "confidence": wake.get("confidence"),
            "audio_stored": False,
        },
    )
    command = _command_after_wake(str(wake.get("recognized_as") or ""))
    if command:
        heard = wake
        record_event(
            "voice.continuous_command_detected",
            {"language": wake.get("language"), "confidence": wake.get("confidence"), "audio_stored": False},
        )
    else:
        if not _voice_allowed():
            return
        write_daemon_status("listening_for_command", enabled=True, acknowledgement="silent")
        record_event("voice.command_window_opened", {"acknowledgement": "silent", "audio_stored": False})
        heard = client.listen(timeout_seconds=12)
        if not heard.get("ok"):
            write_daemon_status(
                "command_not_understood",
                enabled=True,
                error=str(heard.get("error") or "Command was not understood.")[:200],
                confidence=heard.get("confidence"),
                peak_audio_level=heard.get("peak_audio_level"),
            )
            record_event(
                "voice.command_missed",
                {"language": heard.get("language"), "audio_stored": False},
            )
            return
        command = str(heard.get("text", "")).strip()
        if re.fullmatch(r"(?:(?:hey|okay|ok)\s+)?(?:auris|oris|iris|horace)[\s,.:;!-]*", command, flags=re.IGNORECASE):
            return
        command = _command_after_wake(command) or command
    if not command:
        return
    if not _voice_allowed():
        return
    record_event(
        "voice.command_received",
        {
            "language": heard.get("language"),
            "confidence": heard.get("confidence"),
            "audio_stored": False,
        },
    )
    turn_id = heard.get("turn_id")
    response = _process_with_heartbeat(command, client=client, voice_turn_id=turn_id)
    message = str(
        response.get("result", {}).get("message")
        or response.get("error")
        or "I could not complete that request."
    )
    task = response.get("plan") or {}
    record_event(
        "voice.command_finished",
        {"task_id": task.get("task_id"), "state": task.get("state"), "ok": bool(response.get("ok"))},
    )
    write_daemon_status("speaking", enabled=True, task_id=task.get("task_id"))
    spoken = client.speak(message, voice_turn_id=turn_id) if turn_id else client.speak(message)
    if spoken.get("ok") and not spoken.get("suppressed"):
        _monitor_spoken_response(client)


def _command_after_wake(recognized_text: str) -> str:
    match = re.fullmatch(
        r"\s*(?:(?:hey|okay|ok)\s+)?(?:auris|oris|iris|horace)\b[\s,.:;!-]*(?P<command>.*?)\s*",
        recognized_text,
        flags=re.IGNORECASE,
    )
    return match.group("command").strip() if match else ""


def _process_with_heartbeat(
    command: str, *, client: AurisLocalClient | None = None, voice_turn_id: str | None = None
) -> dict[str, Any]:
    client = client or AurisLocalClient()
    result: dict[str, Any] = {}
    failure: list[BaseException] = []

    def invoke() -> None:
        try:
            result.update(
                client.command(
                    command,
                    private=False,
                    conversation_id=VOICE_CONVERSATION_ID,
                    voice_turn_id=voice_turn_id,
                    allow_failure=True,
                )
            )
        except BaseException as error:
            failure.append(error)

    worker = threading.Thread(target=invoke, name="auris-voice-command", daemon=True)
    worker.start()
    while worker.is_alive():
        write_daemon_status("processing", enabled=True)
        worker.join(timeout=3)
    if failure:
        raise failure[0]
    return result


def _monitor_spoken_response(client: AurisLocalClient | None = None) -> None:
    client = client or AurisLocalClient()
    while _broker_speech_active(client):
        if not _voice_allowed():
            _stop_broker_speech(client)
            return
        interruption = client.listen_for_interrupt(timeout_seconds=2)
        if interruption.get("ok"):
            stopped = _stop_broker_speech(client)
            record_event(
                "voice.response_interrupted",
                {
                    "phrase": interruption.get("phrase"),
                    "confidence": interruption.get("confidence"),
                    "stopped": stopped.get("stopped"),
                },
            )
            return


def _wait_for_broker_speech(client: AurisLocalClient, *, timeout_seconds: int) -> None:
    deadline = time.monotonic() + max(1, timeout_seconds)
    while time.monotonic() < deadline and _broker_speech_active(client):
        if not _voice_allowed():
            _stop_broker_speech(client)
            return
        time.sleep(0.1)


def _broker_speech_active(client: AurisLocalClient) -> bool:
    try:
        return bool(client.status().get("voice", {}).get("speaking"))
    except Exception:
        return False


def _stop_broker_speech(client: AurisLocalClient) -> dict[str, Any]:
    try:
        return client.stop_speaking()
    except Exception:
        return {"ok": False, "stopped": False, "message": "The AURIS speech broker was unavailable."}


def _voice_allowed() -> bool:
    return bool(get_background_voice_state()["enabled"]) and not bool(get_control_state()["stopped"])


def _acquire_singleton() -> int | None | bool:
    if os.name != "nt":
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool
    handle = kernel32.CreateMutexW(None, False, "Local\\AURISVoiceDaemon")
    if not handle:
        raise OSError(ctypes.get_last_error(), "Could not create the AURIS voice daemon mutex.")
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    return int(handle)


def _release_singleton(handle: int | None | bool) -> None:
    if os.name == "nt" and isinstance(handle, int) and not isinstance(handle, bool):
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool
        kernel32.CloseHandle(handle)


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
