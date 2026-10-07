from __future__ import annotations

import ctypes
import hashlib
import re
import time
from dataclasses import dataclass
from typing import Any

from auris.device_agent import DeviceAction, execute_device_action, match_device_command
from auris.windows_apps import resolve_application


SENSITIVE_TEXT_TERMS = (
    "api key",
    "card number",
    "credit card",
    "cvv",
    "passcode",
    "password",
    "private key",
    "secret",
    "security code",
    "token",
)
TYPING_PATTERN = re.compile(
    r"^type\s+([\"'])(.{1,500})\1\s+(?:in|into)\s+(?:the\s+)?(.+?)$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class TypingRequest:
    text: str
    application_name: str


def is_typing_intent(command: str) -> bool:
    return TYPING_PATTERN.fullmatch(_normalise(command)) is not None


def contains_sensitive_typing_data(command: str) -> bool:
    text = _normalise(command).casefold()
    return is_typing_intent(command) and any(term in text for term in SENSITIVE_TEXT_TERMS)


def match_typing_command(command: str) -> TypingRequest | None:
    text = _normalise(command)
    match = TYPING_PATTERN.fullmatch(text)
    if not match or contains_sensitive_typing_data(command):
        return None
    value = match.group(2)
    application_name = match.group(3).strip(" .")[:120]
    if not value.strip() or not application_name:
        return None
    return TypingRequest(value, application_name)


def build_typing_device_action(request: TypingRequest) -> tuple[DeviceAction | None, str | None]:
    application = resolve_application(request.application_name)
    if application is None:
        return None, f"I could not resolve an installed application named {request.application_name}."
    binding = hashlib.sha256(
        f"{application.name.casefold()}\0{request.text}".encode("utf-8")
    ).hexdigest()[:32]
    slug = re.sub(r"[^a-z0-9]+", "_", application.name.casefold()).strip("_") or "application"
    return (
        DeviceAction(
            action_id=f"type_text_{slug}"[:120],
            kind="type_text",
            label=f"Type approved text in {application.name}",
            target=f"app={slug[:60]};text_sha256={binding}",
            executable=application.launch_target,
            process_names=application.process_names,
            source=f"approved_interaction:{application.source}",
        ),
        None,
    )


def typing_approval_details(command: str) -> tuple[str, str]:
    request = match_typing_command(command)
    if request is None:
        return "named Windows application", "No keyboard input will be emitted unless the exact request resolves again after approval."
    return request.application_name, f'Enter the exact approved text once: "{request.text}"'


def execute_typing_request(request: TypingRequest) -> dict[str, Any]:
    application = resolve_application(request.application_name)
    if application is None:
        return {"ok": False, "error": f"I could not resolve an installed application named {request.application_name}."}
    focus_action = match_device_command(f"focus {application.name}")
    if focus_action is None:
        return {"ok": False, "error": f"I could not create a focus action for {application.name}."}
    focus = execute_device_action(focus_action)
    if not focus.get("ok"):
        return {
            "ok": False,
            "error": focus.get("error") or focus.get("message", f"I could not focus {application.name}."),
            "focus": focus,
        }
    time.sleep(0.25)
    emitted = _send_unicode_text(request.text)
    expected_units = len(request.text.encode("utf-16-le")) // 2
    completed = emitted == expected_units
    return {
        "ok": completed,
        "message": f"Typed the approved text into {application.name}.",
        "error": None if completed else "Windows did not accept every approved Unicode input unit.",
        "verification": (
            f"Confirmed: AURIS focused a matching {application.name} window and Windows accepted "
            f"{emitted} Unicode keyboard input unit(s). The resulting field content was not independently read back."
        ),
        "application": application.name,
        "characters": len(request.text),
        "input_units_emitted": emitted,
        "focus": focus,
    }


def _send_unicode_text(text: str) -> int:
    if not text:
        return 0
    user32 = ctypes.windll.user32

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.c_long),
            ("dy", ctypes.c_long),
            ("mouseData", ctypes.c_ulong),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", ctypes.c_ulong),
            ("wParamL", ctypes.c_ushort),
            ("wParamH", ctypes.c_ushort),
        ]

    class INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("union",)
        _fields_ = [("type", ctypes.c_ulong), ("union", INPUTUNION)]

    user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = ctypes.c_uint
    encoded = text.encode("utf-16-le")
    units = [int.from_bytes(encoded[index : index + 2], "little") for index in range(0, len(encoded), 2)]
    emitted = 0
    for unit in units:
        inputs = (INPUT * 2)(
            INPUT(type=1, ki=KEYBDINPUT(0, unit, 0x0004, 0, 0)),
            INPUT(type=1, ki=KEYBDINPUT(0, unit, 0x0004 | 0x0002, 0, 0)),
        )
        if user32.SendInput(2, inputs, ctypes.sizeof(INPUT)) == 2:
            emitted += 1
    return emitted


def _normalise(command: str) -> str:
    text = " ".join(command.strip().replace(",", " ").split())
    lowered = text.casefold()
    for prefix in ("hey auris ", "auris "):
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.strip(" .")
