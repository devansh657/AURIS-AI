from __future__ import annotations

import csv
import ctypes
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote_plus, urlparse

from auris.database import list_projects
from auris.windows_apps import (
    InstalledApplication,
    application_suggestions,
    discover_installed_applications,
    resolve_application,
)


ROOT = Path(__file__).resolve().parents[1]
OPEN_PROJECT_SCRIPT = ROOT / "scripts" / "open_project.ps1"
RECYCLE_FILE_SCRIPT = ROOT / "scripts" / "recycle_file.ps1"
USER_HOME = Path.home()
COMMON_FOLDERS = {
    "home": USER_HOME,
    "user folder": USER_HOME,
    "desktop": USER_HOME / "Desktop",
    "documents": USER_HOME / "Documents",
    "downloads": USER_HOME / "Downloads",
    "pictures": USER_HOME / "Pictures",
    "music": USER_HOME / "Music",
    "videos": USER_HOME / "Videos",
    "auris workspace": ROOT,
    "auris folder": ROOT,
}

WRITABLE_FOLDERS = {
    key: value
    for key, value in COMMON_FOLDERS.items()
    if key in {"desktop", "documents", "downloads", "pictures", "music", "videos", "auris workspace", "auris folder"}
}

WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}

SAFE_OPEN_EXTENSIONS = {
    ".csv", ".docx", ".gif", ".jpeg", ".jpg", ".json", ".md", ".mkv",
    ".mp3", ".mp4", ".pdf", ".png", ".pptx", ".txt", ".wav", ".webp", ".xlsx",
}
SAFE_RECYCLE_EXTENSIONS = SAFE_OPEN_EXTENSIONS
NOTEPAD_EXTENSIONS = {".csv", ".json", ".md", ".txt"}
PROTECTED_APPEND_TERMS = (
    "api key", "card number", "credit card", "cvv", "passcode", "password",
    "private key", "secret", "security code", "token",
)

PROTECTED_PROCESSES = {
    "audiodg.exe",
    "csrss.exe",
    "dwm.exe",
    "fontdrvhost.exe",
    "lsass.exe",
    "registry",
    "services.exe",
    "smss.exe",
    "svchost.exe",
    "system",
    "wininit.exe",
    "winlogon.exe",
}

MEDIA_COMMANDS = {
    "mute": ("toggle_mute", "Toggle mute", 0xAD),
    "mute volume": ("toggle_mute", "Toggle mute", 0xAD),
    "unmute": ("toggle_mute", "Toggle mute", 0xAD),
    "unmute volume": ("toggle_mute", "Toggle mute", 0xAD),
    "volume up": ("volume_up", "Increase volume", 0xAF),
    "increase volume": ("volume_up", "Increase volume", 0xAF),
    "turn volume up": ("volume_up", "Increase volume", 0xAF),
    "volume down": ("volume_down", "Decrease volume", 0xAE),
    "decrease volume": ("volume_down", "Decrease volume", 0xAE),
    "turn volume down": ("volume_down", "Decrease volume", 0xAE),
    "play music": ("play_pause", "Play or pause media", 0xB3),
    "pause music": ("play_pause", "Play or pause media", 0xB3),
    "play media": ("play_pause", "Play or pause media", 0xB3),
    "pause media": ("play_pause", "Play or pause media", 0xB3),
    "next track": ("next_track", "Play next track", 0xB0),
    "previous track": ("previous_track", "Play previous track", 0xB1),
}

KNOWN_WEB_DESTINATIONS = {
    "youtube": ("YouTube", "https://www.youtube.com/"),
    "google": ("Google", "https://www.google.com/"),
    "gmail": ("Gmail", "https://mail.google.com/"),
    "google maps": ("Google Maps", "https://maps.google.com/"),
    "github": ("GitHub", "https://github.com/"),
    "spotify": ("Spotify Web", "https://open.spotify.com/"),
}
SENSITIVE_URL_KEYS = {"access_token", "api_key", "apikey", "auth", "key", "password", "secret", "token"}


@dataclass(frozen=True)
class DeviceAction:
    action_id: str
    kind: str
    label: str
    target: str
    executable: str | None = None
    path: Path | None = None
    process_names: tuple[str, ...] = ()
    key_code: int | None = None
    content: str | None = None
    destination: Path | None = None
    arguments: tuple[str, ...] = ()
    source: str = "auris"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.path is not None:
            data["path"] = str(self.path)
        if self.destination is not None:
            data["destination"] = str(self.destination)
        data.pop("content", None)
        if self.content is not None:
            data["content_length"] = len(self.content)
            data["content_sha256"] = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        return data


def is_device_command(command: str) -> bool:
    text = _normalise(command)
    if match_device_commands(command) is not None:
        return True
    if re.fullmatch(r"open\s+(?:(?:my|the)\s+)?(?:.+?\s+)?project", text):
        return True
    if text in MEDIA_COMMANDS or text in {
        "open auris",
        "show auris",
        "open auris portal",
        "open the auris portal",
    }:
        return True
    if _browser_destination_action(_strip_wake_phrase(command)) is not None or _application_media_action(text) is not None:
        return True
    if (
        _create_folder_action(command) is not None
        or _is_folder_creation_intent(command)
        or _create_text_file_action(command) is not None
        or _is_text_file_creation_intent(command)
        or _path_transfer_action(command) is not None
        or _is_path_transfer_intent(command)
        or _recycle_file_action(command) is not None
        or _is_recycle_file_intent(command)
        or _open_file_action(command) is not None
        or _is_open_file_intent(command)
        or _append_text_file_action(command) is not None
        or _is_text_append_intent(command)
        or _folder_action(text) is not None
        or _list_folder_action(text) is not None
    ):
        return True
    return _parse_application_intent(text) is not None


def is_named_browser_command(command: str) -> bool:
    return _browser_destination_action(_strip_wake_phrase(command)) is not None


def match_device_command(
    command: str,
    applications: list[InstalledApplication] | None = None,
) -> DeviceAction | None:
    text = _normalise(command)

    creation = _create_folder_action(command)
    if creation is not None:
        return creation
    text_file = _create_text_file_action(command)
    if text_file is not None:
        return text_file
    recycle = _recycle_file_action(command)
    if recycle is not None:
        return recycle
    transfer = _path_transfer_action(command)
    if transfer is not None:
        return transfer
    file_open = _open_file_action(command)
    if file_open is not None:
        return file_open
    append = _append_text_file_action(command)
    if append is not None:
        return append

    browser_destination = _browser_destination_action(_strip_wake_phrase(command), applications)
    if browser_destination is not None:
        return browser_destination
    application_media = _application_media_action(text, applications)
    if application_media is not None:
        return application_media

    if text in {"open auris", "show auris", "open auris portal", "open the auris portal"}:
        return DeviceAction("open_auris", "open_url", "Open AURIS", "AURIS command centre")

    media = MEDIA_COMMANDS.get(text)
    if media:
        action_id, label, key_code = media
        return DeviceAction(action_id, "media_key", label, label, key_code=key_code)

    folder = _folder_action(text)
    if folder is not None:
        return folder
    listing = _list_folder_action(text)
    if listing is not None:
        return listing

    parsed = _parse_application_intent(text)
    if parsed is None:
        return None
    kind, requested_name = parsed
    app = resolve_application(requested_name, applications)
    if app is None:
        return None

    verbs = {
        "launch_app": "Open",
        "close_app": "Close",
        "focus_app": "Focus",
        "minimize_app": "Minimize",
        "maximize_app": "Maximize",
        "restore_app": "Restore",
    }
    slug = re.sub(r"[^a-z0-9]+", "_", app.name.casefold()).strip("_")
    action_prefix = {
        "launch_app": "open",
        "close_app": "close",
        "focus_app": "focus",
        "minimize_app": "minimize",
        "maximize_app": "maximize",
        "restore_app": "restore",
    }[kind]
    return DeviceAction(
        action_id=f"{action_prefix}_{slug}",
        kind=kind,
        label=f"{verbs[kind]} {app.name}",
        target=app.name,
        executable=app.launch_target,
        process_names=app.process_names,
        source=app.source,
    )


def match_device_commands(
    command: str,
    applications: list[InstalledApplication] | None = None,
) -> list[DeviceAction] | None:
    """Resolve one command into a fail-closed sequence of bounded device actions."""
    exact = match_device_command(command, applications)
    if exact is not None:
        return [exact]

    clean = _strip_wake_phrase(command)
    clauses = [
        clause.strip(" ,.")
        for clause in re.split(r"\s+(?:and\s+then|then|and)\s+", clean, flags=re.IGNORECASE)
        if clause.strip(" ,.")
    ]
    if not 2 <= len(clauses) <= 4:
        return None
    if not all(_looks_like_device_clause(clause) for clause in clauses):
        return None

    installed = applications if applications is not None else discover_installed_applications()
    actions: list[DeviceAction] = []
    active_application: str | None = None
    for clause in clauses:
        contextual = contextual_device_command(clause, active_application)
        action = match_device_command(contextual, installed)
        if action is None:
            return None
        actions.append(action)
        if action.kind in {
            "launch_app", "focus_app", "minimize_app", "maximize_app", "restore_app", "app_media"
        }:
            active_application = action.target
    return actions


def contextual_device_command(clause: str, active_application: str | None) -> str:
    if not active_application:
        return clause
    text = _normalise(_strip_wake_phrase(clause))
    if active_application.casefold().startswith("spotify") and text in {
        "play music", "play songs", "play song", "resume music", "resume songs", "resume song"
    }:
        return f"{text} on Spotify"
    pronoun = re.fullmatch(
        r"(focus(?:\s+on)?|switch\s+to|bring\s+to\s+front|minimi[sz]e|maximi[sz]e|restore)\s+(?:it|the\s+app|the\s+application|the\s+window)",
        text,
    )
    if pronoun:
        return f"{pronoun.group(1)} {active_application}"
    return clause


def _looks_like_device_clause(clause: str) -> bool:
    text = _normalise(clause)
    return bool(
        re.match(
            r"^(?:open|show|launch|start|run|close|quit|exit|terminate|stop|focus|switch|bring|"
            r"minimi[sz]e|maximi[sz]e|restore|mute|unmute|volume|increase|decrease|turn|play|pause|"
            r"resume|next|previous|create|make|append|add|rename|copy|move|recycle|list)\b",
            text,
        )
    )


def unmatched_device_message(command: str) -> str:
    if contextual_device_command(command, "AURIS app context") != command:
        return "Which application should I control? Name it explicitly; I do not have a recent verified app in this conversation."
    if _is_folder_creation_intent(command):
        return (
            "I can create one folder directly inside Desktop, Documents, Downloads, "
            "Pictures, Music, Videos, or the AURIS workspace, or inside one existing direct child folder. "
            "Use plain Windows-safe folder names."
        )
    if _is_text_file_creation_intent(command):
        return (
            "I can create new TXT or Markdown notes directly inside Desktop, Documents, "
            "Downloads, Pictures, Music, Videos, or the AURIS workspace. I will not overwrite a different file."
        )
    if _is_path_transfer_intent(command):
        return (
            "I can rename one direct file or folder, or copy and move one regular file, "
            "between approved user locations. Existing destinations and links are never replaced."
        )
    if _is_recycle_file_intent(command):
        return (
            "I can move one named document or media file directly inside Desktop, Documents, Downloads, "
            "Pictures, Music, Videos, or the AURIS workspace to the Windows Recycle Bin after one-time approval."
        )
    if _is_open_file_intent(command):
        return (
            "I can open a named document, image, audio, or video file directly inside an approved "
            "user folder. Executables, scripts, links, and nested paths are blocked."
        )
    if _is_text_append_intent(command):
        return (
            "I can append up to 1,000 non-secret characters to an existing TXT or Markdown note "
            "directly inside an approved user folder. Other formats and nested paths are blocked."
        )
    parsed = _parse_application_intent(_normalise(command))
    if parsed is None:
        return "I understood this as a Windows command, but no supported action matched it."
    _, requested_name = parsed
    suggestions = application_suggestions(requested_name)
    suffix = f" Closest installed matches: {', '.join(suggestions)}." if suggestions else ""
    return f"I could not find an installed application named {requested_name}.{suffix}"


def execute_device_action(action: DeviceAction) -> dict[str, Any]:
    started_at = time.monotonic()
    try:
        if action.kind == "launch_app":
            result = _launch_application(action)
        elif action.kind == "close_app":
            result = _close_application(action)
        elif action.kind == "focus_app":
            result = _focus_application(action)
        elif action.kind in {"minimize_app", "maximize_app", "restore_app"}:
            result = _set_application_window_state(action)
        elif action.kind == "open_folder":
            result = _open_folder(action)
        elif action.kind == "open_file":
            result = _open_file(action)
        elif action.kind == "open_url":
            result = _open_auris()
        elif action.kind == "list_folder":
            result = _list_folder(action)
        elif action.kind == "create_folder":
            result = _create_folder(action)
        elif action.kind == "create_text_file":
            result = _create_text_file(action)
        elif action.kind == "append_text_file":
            result = _append_text_file(action)
        elif action.kind in {"rename_path", "copy_file", "move_file"}:
            result = _transfer_path(action)
        elif action.kind == "recycle_file":
            result = _recycle_file(action)
        elif action.kind == "media_key":
            result = _send_media_key(action)
        elif action.kind == "app_media":
            result = _play_media_in_application(action)
        else:
            result = {"ok": False, "error": "Unsupported device action."}
    except OSError as error:
        result = {"ok": False, "error": f"Windows could not complete the action: {error}"}

    result.update(
        {
            "action": action.to_dict(),
            "duration_ms": round((time.monotonic() - started_at) * 1000),
            "device": os.environ.get("COMPUTERNAME", "Windows device"),
        }
    )
    return result


def device_capabilities() -> list[dict[str, str]]:
    applications = discover_installed_applications()
    folder_count = sum(path.exists() for path in set(COMMON_FOLDERS.values()))
    project_count = sum(bool(str(project.get("root_path") or "").strip()) for project in list_projects())
    return [
        {
            "id": "installed_application_control",
            "label": f"Open, close, focus, minimize, maximize, and restore {len(applications)} discovered Windows apps",
            "risk": "reversible",
        },
        {"id": "media_control", "label": "Volume, media playback, and target-app playback control", "risk": "reversible"},
        {"id": "named_browser_destination", "label": "Open an allowlisted web destination in a named installed browser", "risk": "reversible"},
        {
            "id": "user_folder_access",
            "label": f"Open, inspect, create, rename, copy, move, and approval-recycle bounded items in {folder_count} approved user locations",
            "risk": "reversible",
        },
        {
            "id": "registered_project_control",
            "label": f"Open {project_count} registered project roots with exact-window verification",
            "risk": "reversible",
        },
        {
            "id": "managed_work_products",
            "label": "Create statically verified code projects and validated Word documents in AURIS Work",
            "risk": "controlled_write",
        },
        {"id": "open_auris", "label": "Open AURIS", "risk": "reversible"},
        {"id": "system_status", "label": "Read Windows system health", "risk": "read_only"},
        {
            "id": "screen_understanding",
            "label": "Temporarily capture and locally understand the visible desktop",
            "risk": "explicit_read_only",
        },
        {
            "id": "approved_ui_automation",
            "label": "Invoke one exact benign control in a named visible app with approval and observation",
            "risk": "sensitive",
        },
    ]


def installed_applications() -> list[dict[str, Any]]:
    return [app.to_dict() for app in discover_installed_applications()]


def _launch_application(action: DeviceAction) -> dict[str, Any]:
    target = action.executable or ""
    target_path = Path(target)
    if action.source.startswith("named_browser_destination:"):
        url = action.arguments[0] if len(action.arguments) == 1 else ""
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
        if f"url_sha256={digest}" not in action.target or not _public_web_url_allowed(url, resolve_dns=True):
            return {"ok": False, "error": "The named-browser destination failed its signed public-network validation."}
    is_shell_target = target_path.suffix.casefold() in {".lnk", ".url", ".appref-ms"}
    if is_shell_target or target.casefold().startswith("ms-settings:"):
        if action.arguments:
            return {"ok": False, "error": f"{action.target} does not expose an executable launch target for a verified destination."}
        if is_shell_target and not target_path.exists():
            return {"ok": False, "error": f"The Windows shortcut for {action.target} no longer exists."}
        os.startfile(target)
        process_id = None
    else:
        executable = shutil.which(target) or (target if target_path.exists() else None)
        if not executable:
            return {"ok": False, "error": f"{action.target} is no longer available on this device."}
        process = subprocess.Popen(
            [executable, *action.arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        process_id = process.pid
    verified_processes: list[int] = []
    deadline = time.monotonic() + 6
    expected_names = {name.casefold() for name in action.process_names}
    visible_window = False
    while time.monotonic() < deadline:
        if expected_names:
            verified_processes = [
                pid for name, pid in _running_processes() if name.casefold() in expected_names
            ]
        visible_window = _find_application_window(action) is not None
        if verified_processes or visible_window:
            break
        time.sleep(0.35)
    confirmed = bool(verified_processes or visible_window)
    display = action.label.removeprefix("Open ") or action.target
    return {
        "ok": confirmed,
        "message": (
            f"{display} opened and is running."
            if confirmed
            else f"Windows started the {action.target} launch target, but AURIS could not confirm a running process or visible window."
        ),
        "error": None if confirmed else f"{action.target} did not become visibly available within six seconds.",
        "verification": (
            f"Confirmed: a matching {action.target} process or visible window is present."
            if confirmed
            else "Launch was attempted, but the requested application state was not independently confirmed."
        ),
        "process_id": process_id,
        "verified_process_ids": verified_processes,
        "launch_arguments_bound": bool(action.arguments),
    }


def _close_application(action: DeviceAction) -> dict[str, Any]:
    process_names = {name.casefold() for name in action.process_names}
    if not process_names:
        return {
            "ok": False,
            "error": f"I found {action.target}, but its running process identity is not known yet.",
        }
    protected = process_names & PROTECTED_PROCESSES
    if protected:
        return {
            "ok": False,
            "error": f"AURIS will not terminate the protected Windows process for {action.target}.",
        }

    matches = [item for item in _running_processes() if item[0].casefold() in process_names]
    if not matches:
        return {
            "ok": False,
            "error": f"{action.target} is not currently running.",
            "verification": "Confirmed: no matching user application process was found.",
        }

    closed: list[int] = []
    for _, process_id in matches:
        result = subprocess.run(
            ["taskkill.exe", "/PID", str(process_id), "/T"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if result.returncode == 0:
            closed.append(process_id)
    if not closed:
        return {
            "ok": False,
            "error": f"Windows denied the request to close {action.target}.",
            "verification": "No matching process confirmed a successful close request.",
        }
    return {
        "ok": True,
        "message": f"{action.target} closed.",
        "verification": f"Confirmed: Windows closed {len(closed)} matching process tree(s).",
        "process_ids": closed,
    }


def _focus_application(action: DeviceAction) -> dict[str, Any]:
    window = _find_application_window(action)
    if window is None:
        return {
            "ok": False,
            "error": f"I could not find a visible {action.target} window. Try opening it first.",
            "verification": "Confirmed: no matching visible application window was found.",
        }
    user32 = ctypes.windll.user32
    user32.ShowWindow(window, 9)
    focused = bool(user32.SetForegroundWindow(window))
    return {
        "ok": focused,
        "message": f"{action.target} is in focus." if focused else f"Windows found {action.target} but denied foreground focus.",
        "verification": (
            "Confirmed: Windows moved the matching application window to the foreground."
            if focused
            else "The window was restored, but Windows did not confirm foreground focus."
        ),
    }


def _set_application_window_state(action: DeviceAction) -> dict[str, Any]:
    window = _find_application_window(action)
    if window is None:
        return {
            "ok": False,
            "error": f"I could not find a visible {action.target} window. Try opening it first.",
            "verification": "Confirmed: no matching application window was found.",
        }
    user32 = ctypes.windll.user32
    show_codes = {"minimize_app": 6, "maximize_app": 3, "restore_app": 9}
    user32.ShowWindow(window, show_codes[action.kind])
    deadline = time.monotonic() + 2
    observed = False
    while time.monotonic() < deadline:
        if action.kind == "minimize_app":
            observed = bool(user32.IsIconic(window))
        elif action.kind == "maximize_app":
            observed = bool(user32.IsZoomed(window))
        else:
            observed = bool(user32.IsWindowVisible(window) and not user32.IsIconic(window))
        if observed:
            break
        time.sleep(0.1)
    state = {
        "minimize_app": "minimized",
        "maximize_app": "maximized",
        "restore_app": "restored",
    }[action.kind]
    return {
        "ok": observed,
        "message": f"{action.target} {state}." if observed else f"Windows did not confirm {action.target} as {state}.",
        "error": None if observed else f"The {action.target} window did not reach the requested state.",
        "verification": (
            f"Confirmed: Win32 reports the matching {action.target} window as {state}."
            if observed
            else "The state command was sent, but its Win32 observation did not match."
        ),
        "window_handle": window,
        "window_state": state if observed else "unconfirmed",
    }


def _send_media_key(action: DeviceAction) -> dict[str, Any]:
    if action.key_code is None:
        return {"ok": False, "error": "The media command is missing its Windows key code."}
    ctypes.windll.user32.keybd_event(action.key_code, 0, 0, 0)
    ctypes.windll.user32.keybd_event(action.key_code, 0, 2, 0)
    return {
        "ok": True,
        "message": f"{action.label} command sent.",
        "verification": "Confirmed: the fixed Windows media key event was emitted.",
    }


def _play_media_in_application(action: DeviceAction) -> dict[str, Any]:
    process_names = {name.casefold() for name in action.process_names}
    running = any(name.casefold() in process_names for name, _ in _running_processes())
    launched = False
    if not running:
        launch = _launch_application(
            DeviceAction(
                action_id=f"open_{_slug(action.target)}",
                kind="launch_app",
                label=f"Open {action.target}",
                target=action.target,
                executable=action.executable,
                process_names=action.process_names,
                source=action.source,
            )
        )
        if not launch.get("ok"):
            return launch
        launched = True
    focus_deadline = time.monotonic() + (10 if launched else 4)
    focus = _focus_application(action)
    while not focus.get("ok") and time.monotonic() < focus_deadline:
        time.sleep(0.35)
        focus = _focus_application(action)
    if not focus.get("ok") and not launched:
        reveal = _launch_application(
            DeviceAction(
                action_id=f"open_{_slug(action.target)}",
                kind="launch_app",
                label=f"Open {action.target}",
                target=action.target,
                executable=action.executable,
                process_names=action.process_names,
                source=action.source,
            )
        )
        if reveal.get("ok"):
            launched = True
            focus_deadline = time.monotonic() + 8
            while not focus.get("ok") and time.monotonic() < focus_deadline:
                time.sleep(0.35)
                focus = _focus_application(action)
    if not focus.get("ok"):
        return {
            "ok": False,
            "error": focus.get("error", f"Windows could not focus {action.target}."),
            "verification": "The play command was withheld because the intended media application was not confirmed in the foreground.",
            "application_launched": launched,
            "application_focused": False,
            "media_key_emitted": False,
        }
    media = _send_media_key(action)
    return {
        "ok": bool(media.get("ok")),
        "message": f"{action.target} is focused and received the Windows play command.",
        "verification": f"Confirmed: {action.target} was visible in the foreground before the fixed play media key was emitted.",
        "application_launched": launched,
        "application_focused": True,
        "media_key_emitted": bool(media.get("ok")),
        "playback_session_observed": False,
    }


def _open_folder(action: DeviceAction) -> dict[str, Any]:
    path = action.path
    registered_project = action.source == "registered_project"
    approved = (
        _is_registered_project_root(path)
        if path is not None and registered_project
        else path is not None and _is_approved_path(path)
    )
    if path is None or not path.exists() or not approved:
        return {"ok": False, "error": "The requested folder is unavailable or outside approved roots."}
    if registered_project:
        return _open_registered_project(action, path)
    os.startfile(str(path))
    display = action.label.removeprefix("Open ") or action.target
    return {
        "ok": True,
        "message": f"{display} opened in File Explorer.",
        "verification": f"Confirmed: the user folder exists and Windows accepted the open request: {path}",
    }


def _open_file(action: DeviceAction) -> dict[str, Any]:
    path = action.path
    if (
        path is None
        or action.target != str(path)
        or not _is_approved_direct_child(path)
        or not path.is_file()
        or path.is_symlink()
        or path.suffix.casefold() not in SAFE_OPEN_EXTENSIONS
    ):
        return {"ok": False, "error": "The requested file is unavailable or outside the safe open-file boundary."}
    process_id = None
    if path.suffix.casefold() in NOTEPAD_EXTENSIONS:
        notepad = shutil.which("notepad.exe") or str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "notepad.exe")
        if not Path(notepad).exists():
            return {"ok": False, "error": "The safe Notepad viewer is unavailable on this device."}
        process = subprocess.Popen(
            [notepad, str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        process_id = process.pid
    else:
        os.startfile(str(path))
    deadline = time.monotonic() + 6
    observed_window = None
    while time.monotonic() < deadline:
        observed_window = _find_window_with_title(path.name)
        if observed_window is not None:
            break
        time.sleep(0.25)
    confirmed = observed_window is not None
    return {
        "ok": confirmed,
        "message": (
            f"Opened {path.name}."
            if confirmed
            else f"Windows accepted the request for {path.name}, but AURIS could not observe its window."
        ),
        "error": None if confirmed else "The matching file window was not observed within six seconds.",
        "verification": (
            f"Confirmed: a visible Windows application title contains the exact filename {path.name}."
            if confirmed
            else "The file exists and the shell request was sent, but visible-window verification failed."
        ),
        "observed_path": str(path) if confirmed else None,
        "window_handle": observed_window,
        "process_id": process_id,
    }


def _open_registered_project(action: DeviceAction, path: Path) -> dict[str, Any]:
    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(OPEN_PROJECT_SCRIPT),
        "-Path",
        str(path),
    ]
    try:
        process = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=12,
            check=False,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "ok": False,
            "error": f"Windows could not open and observe the registered project: {error}",
            "verification": "The project window was not confirmed.",
        }
    payload = _last_json_object(process.stdout)
    confirmed = bool(process.returncode == 0 and payload and payload.get("ok"))
    project_name = action.label.removeprefix("Open ").removesuffix(" project")
    return {
        "ok": confirmed,
        "message": (
            f"{project_name} opened in File Explorer."
            if confirmed
            else f"Windows received the {project_name} project request, but AURIS could not confirm the exact folder window."
        ),
        "error": None if confirmed else "The exact registered project window was not observed within eight seconds.",
        "verification": (
            f"Confirmed: File Explorer reported the exact registered project root {path}."
            if confirmed
            else "The project path exists, but the expected File Explorer location was not independently confirmed."
        ),
        "application": "File Explorer",
        "observed_path": str(path) if confirmed else None,
        "process_exit_code": process.returncode,
    }


def _open_auris() -> dict[str, Any]:
    accepted = webbrowser.open("http://127.0.0.1:8765/", new=1)
    return {
        "ok": bool(accepted),
        "message": "AURIS command centre opened." if accepted else "Windows did not confirm the browser request.",
        "verification": "Confirmed: the AURIS portal URL was handed to the default browser." if accepted else "Browser launch was not confirmed.",
    }


def _list_folder(action: DeviceAction) -> dict[str, Any]:
    path = action.path
    if path is None or not path.exists() or not _is_approved_path(path):
        return {"ok": False, "error": "The requested folder is unavailable or outside the current user profile."}
    items = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold()))[:30]
    names = [f"{item.name}{'/' if item.is_dir() else ''}" for item in items]
    return {
        "ok": True,
        "message": f"I found {len(names)} visible items in {action.target}.",
        "verification": f"Confirmed: {path} was read without changing files.",
        "items": names,
    }


def _create_folder(action: DeviceAction) -> dict[str, Any]:
    target = action.path
    if target is None or not _valid_folder_name(target.name):
        return {"ok": False, "error": "The requested folder name is invalid."}
    if len(str(target)) > 200:
        return {"ok": False, "error": "The requested folder path is too long for the signed device command."}

    try:
        parent = target.parent.resolve(strict=True)
    except OSError:
        return {"ok": False, "error": "The requested parent folder is unavailable."}
    if not _is_approved_creation_parent(target.parent, parent):
        return {
            "ok": False,
            "error": "Folder creation is limited to an approved user location or one existing direct child folder.",
        }
    if target.exists() and not target.is_dir():
        return {"ok": False, "error": f"A file named {target.name} already exists in {parent.name}."}

    existed = target.is_dir()
    target.mkdir(exist_ok=True)
    observed = target.is_dir() and target.parent.resolve(strict=True) == parent
    if not observed:
        return {
            "ok": False,
            "error": "Windows did not confirm the requested folder after creation.",
            "verification": f"The expected directory was not observed at {target}.",
        }
    return {
        "ok": True,
        "message": (
            f"The folder {target.name} already exists in {parent.name}."
            if existed
            else f"Created the folder {target.name} in {parent.name}."
        ),
        "verification": f"Confirmed: the directory exists at {target}.",
        "created": not existed,
        "observed_path": str(target),
    }


def _create_text_file(action: DeviceAction) -> dict[str, Any]:
    target = action.path
    content = action.content if action.content is not None else ""
    if target is None or not _valid_text_file_name(target.name) or len(content) > 2000:
        return {"ok": False, "error": "The requested note name or content is invalid."}
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    expected_target = f"path={target};content_sha256={content_hash}"
    if action.target != expected_target or len(action.target) > 200:
        return {"ok": False, "error": "The signed note target does not match the requested content."}

    try:
        parent = target.parent.resolve(strict=True)
    except OSError:
        return {"ok": False, "error": "The requested parent folder is unavailable."}
    if not _is_approved_creation_parent(target.parent, parent):
        return {
            "ok": False,
            "error": "Note creation is limited to an approved user location or one existing direct child folder.",
        }
    if target.exists():
        if not target.is_file():
            return {"ok": False, "error": f"A folder named {target.name} already exists in {parent.name}."}
        try:
            existing = target.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return {"ok": False, "error": f"AURIS will not replace the existing file {target.name}."}
        if existing != content:
            return {"ok": False, "error": f"AURIS will not overwrite the existing file {target.name}."}
        created = False
    else:
        try:
            with target.open("x", encoding="utf-8", newline="") as stream:
                stream.write(content)
        except FileExistsError:
            return {"ok": False, "error": f"AURIS will not overwrite the existing file {target.name}."}
        created = True

    try:
        observed_content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        observed_content = None
    observed = target.is_file() and observed_content == content
    if not observed:
        return {
            "ok": False,
            "error": "Windows did not confirm the requested note content after creation.",
            "verification": f"The expected UTF-8 content was not observed at {target}.",
        }
    return {
        "ok": True,
        "message": (
            f"The note {target.name} already exists with the requested content in {parent.name}."
            if not created
            else f"Created the note {target.name} in {parent.name}."
        ),
        "verification": f"Confirmed: the UTF-8 file and exact content exist at {target}.",
        "created": created,
        "observed_path": str(target),
        "content_length": len(content),
        "content_sha256": content_hash,
    }


def _append_text_file(action: DeviceAction) -> dict[str, Any]:
    path = action.path
    content = action.content or ""
    try:
        valid_existing_file = bool(
            path is not None
            and _valid_text_file_name(path.name)
            and _is_approved_direct_child(path)
            and path.is_file()
            and not path.is_symlink()
        )
        file_size = path.stat().st_size if valid_existing_file and path is not None else 0
    except OSError:
        valid_existing_file = False
        file_size = 0
    if (
        not valid_existing_file
        or not content.strip()
        or len(content) > 1000
        or _contains_protected_append_data(content)
    ):
        return {"ok": False, "error": "The requested note append is unavailable or outside the controlled-write boundary."}
    if file_size > 1024 * 1024:
        return {"ok": False, "error": "The note exceeds the 1 MB controlled append limit."}
    try:
        original_bytes = path.read_bytes()
        original_text = original_bytes.decode("utf-8")
    except (OSError, UnicodeError):
        return {"ok": False, "error": "The note is not a readable UTF-8 text file."}

    preimage_hash = hashlib.sha256(original_bytes).hexdigest()
    append_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    expected_target = f"path={path};pre={preimage_hash[:32]};append={append_hash[:32]}"
    if action.target != expected_target or len(action.target) > 200:
        return {"ok": False, "error": "The signed append binding does not match the current file and exact text."}

    existing_lines = original_text.rstrip("\r\n").splitlines()
    if existing_lines and existing_lines[-1] == content:
        return {
            "ok": True,
            "message": f"{path.name} already ends with the requested note.",
            "verification": f"Confirmed: the exact final line already exists at {path}.",
            "appended": False,
            "observed_path": str(path),
            "preimage_sha256": preimage_hash,
            "content_sha256": preimage_hash,
            "append_sha256": append_hash,
        }

    separator = "" if not original_text or original_text.endswith(("\n", "\r")) else "\n"
    updated_text = f"{original_text}{separator}{content}"
    updated_bytes = updated_text.encode("utf-8")
    expected_hash = hashlib.sha256(updated_bytes).hexdigest()
    try:
        _atomic_replace_bytes(path, updated_bytes)
    except OSError as error:
        return {"ok": False, "error": f"Windows could not append the note atomically: {error}"}
    try:
        observed_bytes = path.read_bytes()
    except OSError:
        observed_bytes = None
    if observed_bytes is None or hashlib.sha256(observed_bytes).hexdigest() != expected_hash or observed_bytes != updated_bytes:
        rollback_ok = False
        try:
            _atomic_replace_bytes(path, original_bytes)
            rollback_ok = path.read_bytes() == original_bytes
        except OSError:
            rollback_ok = False
        return {
            "ok": False,
            "error": "The appended note failed exact read-back verification and was rolled back." if rollback_ok else "The appended note failed verification and automatic rollback could not be confirmed.",
            "verification": "The preimage was restored exactly." if rollback_ok else "Manual inspection is required.",
            "rolled_back": rollback_ok,
        }
    return {
        "ok": True,
        "message": f"Appended the approved text to {path.name}.",
        "verification": f"Confirmed: the exact appended UTF-8 bytes exist at {path} with SHA-256 {expected_hash}.",
        "appended": True,
        "observed_path": str(path),
        "preimage_sha256": preimage_hash,
        "content_sha256": expected_hash,
        "append_sha256": append_hash,
    }


def _atomic_replace_bytes(path: Path, content: bytes) -> None:
    temporary_path: Path | None = None
    original_mode = path.stat().st_mode
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=".auris-write-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, original_mode)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _transfer_path(action: DeviceAction) -> dict[str, Any]:
    source = action.path
    destination = action.destination
    if source is None or destination is None:
        return {"ok": False, "error": "The filesystem action is missing its exact source or destination."}
    expected_target = f"source={source};destination={destination}"
    if action.target != expected_target or len(action.target) > 200:
        return {"ok": False, "error": "The signed filesystem paths do not match the requested action."}
    if not _is_approved_bounded_item(source) or not _is_approved_bounded_item(destination):
        return {"ok": False, "error": "The filesystem action is outside approved root or one-parent-deep user locations."}
    if str(source).casefold() == str(destination).casefold():
        return {"ok": False, "error": "The source and destination are the same."}
    if not source.exists() or source.is_symlink():
        return {"ok": False, "error": f"The source {source.name} is unavailable or is a link."}
    if destination.exists() or destination.is_symlink():
        return {"ok": False, "error": f"A destination named {destination.name} already exists."}

    source_was_file = source.is_file()
    source_was_dir = source.is_dir()
    if action.kind in {"copy_file", "move_file"} and not source_was_file:
        return {"ok": False, "error": "Copy and move currently accept regular files only."}
    if not source_was_file and not source_was_dir:
        return {"ok": False, "error": "The source is not a regular file or folder."}
    if source_was_file and source.stat().st_size > 100 * 1024 * 1024:
        return {"ok": False, "error": "The source exceeds the 100 MB bounded file-operation limit."}

    before_hash = _file_sha256(source) if source_was_file else None
    if action.kind == "copy_file":
        created_destination = False
        try:
            with destination.open("xb") as output_stream:
                created_destination = True
                with source.open("rb") as input_stream:
                    shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
        except OSError as error:
            if created_destination and destination.exists() and destination.is_file():
                destination.unlink(missing_ok=True)
            return {"ok": False, "error": f"Windows could not copy the file safely: {error}"}
    else:
        try:
            source.rename(destination)
        except OSError as error:
            operation = "rename" if action.kind == "rename_path" else "move"
            return {"ok": False, "error": f"Windows could not {operation} the item safely: {error}"}

    destination_ok = destination.is_file() if source_was_file else destination.is_dir()
    content_ok = not source_was_file or _file_sha256(destination) == before_hash
    source_ok = source.exists() if action.kind == "copy_file" else not source.exists()
    observed = destination_ok and content_ok and source_ok
    verb = {"rename_path": "renamed", "copy_file": "copied", "move_file": "moved"}[action.kind]
    if not observed:
        return {
            "ok": False,
            "error": f"The {verb} state could not be independently confirmed.",
            "verification": "The expected source, destination, or content-hash state was not observed.",
        }
    return {
        "ok": True,
        "message": f"{source.name} was {verb} to {destination}.",
        "verification": (
            f"Confirmed: destination {destination} exists"
            + (f" with SHA-256 {before_hash}" if before_hash else " with the original item type")
            + (" and the source remains." if action.kind == "copy_file" else " and the source path is absent.")
        ),
        "observed_source": str(source),
        "observed_path": str(destination),
        "content_sha256": before_hash,
    }


def _recycle_file(action: DeviceAction) -> dict[str, Any]:
    path = action.path
    if (
        path is None
        or not _is_approved_direct_child(path)
        or path.is_symlink()
        or not path.is_file()
        or Path(path.name).suffix.casefold() not in SAFE_RECYCLE_EXTENSIONS
    ):
        return {"ok": False, "error": "The requested file is unavailable or outside the recoverable-removal boundary."}
    if path.stat().st_size > 100 * 1024 * 1024:
        return {"ok": False, "error": "The file exceeds the 100 MB Recycle Bin action limit."}
    preimage_hash = _file_sha256(path)
    expected_target = f"path={path};pre={preimage_hash[:32]}"
    if action.target != expected_target or len(action.target) > 200:
        return {"ok": False, "error": "The signed Recycle Bin binding does not match the current file."}

    outcome = _send_file_to_recycle_bin(path)
    if not outcome.get("ok"):
        return outcome
    deadline = time.monotonic() + 3
    while path.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    if path.exists():
        return {
            "ok": False,
            "error": "Windows accepted the Recycle Bin request, but the original file is still present.",
            "verification": f"The source remained at {path}.",
        }
    return {
        "ok": True,
        "message": f"Moved {path.name} to the Windows Recycle Bin.",
        "verification": f"Confirmed: the exact preimage-bound file is no longer present at {path}; Windows reported a Recycle Bin operation.",
        "recycled": True,
        "original_path": str(path),
        "source_absent": True,
        "preimage_sha256": preimage_hash,
        "provider": outcome.get("provider"),
    }


def _send_file_to_recycle_bin(path: Path) -> dict[str, Any]:
    try:
        process = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(RECYCLE_FILE_SCRIPT),
                "-Path",
                str(path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=20,
            check=False,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "error": f"Windows could not complete the Recycle Bin request: {error}"}
    payload = _last_json_object(process.stdout)
    if process.returncode != 0 or not payload or not payload.get("ok"):
        error = str((payload or {}).get("error") or process.stderr.strip() or "The Recycle Bin operation failed.")
        return {"ok": False, "error": error[:500]}
    return {"ok": True, "provider": str(payload.get("provider") or "windows_recycle_bin")}


def _folder_action(text: str) -> DeviceAction | None:
    for phrase, path in COMMON_FOLDERS.items():
        if text in {f"open {phrase}", f"show {phrase}", f"open my {phrase}"}:
            return DeviceAction(
                f"open_{_slug(phrase)}",
                "open_folder",
                f"Open {phrase.title()}",
                phrase.title(),
                path=path,
            )
    return None


def _create_folder_action(command: str) -> DeviceAction | None:
    text = _strip_wake_phrase(command)
    location_pattern = r"desktop|documents|downloads|pictures|music|videos|auris workspace|auris folder"
    patterns = (
        (
            r"^(?:create|make)\s+(?:me\s+)?(?:(?:a|the)\s+)?(?:new\s+)?folder"
            r"(?:\s+(?:named|called)\s+|\s+and\s+name\s+it\s+|\s+)"
            r"(?P<name>.+?)\s+inside\s+(?:(?:the|a)\s+)?(?:folder\s+)?(?P<parent>.+?)\s+"
            rf"(?:on|in)\s+(?:(?:my|the)\s+)?(?P<location>{location_pattern})$"
        ),
        (
            r"^(?:create|make)\s+(?:me\s+)?(?:(?:a|the)\s+)?(?:new\s+)?folder"
            r"(?:\s+(?:named|called)\s+|\s+and\s+name\s+it\s+|\s+)"
            rf"(?P<name>.+?)\s+(?:on|in)\s+(?:(?:my|the)\s+)?(?P<location>{location_pattern})$"
        ),
        (
            r"^(?:create|make)\s+(?:me\s+)?(?:(?:a|the)\s+)?(?:new\s+)?folder\s+"
            rf"(?:on|in)\s+(?:(?:my|the)\s+)?(?P<location>{location_pattern})\s+"
            r"(?:named|called|and\s+name\s+it)\s+(?P<name>.+)$"
        ),
    )
    match = next(
        (candidate for pattern in patterns if (candidate := re.fullmatch(pattern, text, flags=re.IGNORECASE))),
        None,
    )
    if match is None:
        return None
    name = match.group("name").strip().strip('"\'')
    parent_name = str(match.groupdict().get("parent") or "").strip().strip('"\'')
    location = match.group("location").casefold()
    if not _valid_folder_name(name) or (parent_name and not _valid_folder_name(parent_name)):
        return None
    target = WRITABLE_FOLDERS[location] / parent_name / name if parent_name else WRITABLE_FOLDERS[location] / name
    if len(str(target)) > 200:
        return None
    return DeviceAction(
        action_id=f"create_folder_{_slug(location)}_{_slug(name)[:60] or 'named'}",
        kind="create_folder",
        label=f"Create folder {name}",
        target=str(target),
        path=target,
        source="approved_user_root",
    )


def _is_folder_creation_intent(command: str) -> bool:
    text = _strip_wake_phrase(command)
    return bool(
        re.match(
            r"^(?:create|make)\s+(?:me\s+)?(?:(?:a|the)\s+)?(?:new\s+)?folder\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def _create_text_file_action(command: str) -> DeviceAction | None:
    text = _strip_wake_phrase(command)
    location_pattern = r"desktop|documents|downloads|pictures|music|videos|auris workspace|auris folder"
    prefix = (
        r"^(?:create|make|write)\s+(?:(?:a|the)\s+)?(?P<kind>(?:text|markdown)\s+file|note)"
        r"(?:\s+(?:named|called)\s+|\s+)"
    )
    suffix = r"(?:\s+(?:saying|containing|with\s+content)\s+(?P<content>.+))?$"
    patterns = (
        prefix
        + r"(?P<name>.+?)\s+inside\s+(?:(?:the|a)\s+)?(?:folder\s+)?(?P<parent>.+?)\s+"
        + rf"(?:on|in)\s+(?:(?:my|the)\s+)?(?P<location>{location_pattern})"
        + suffix,
        prefix
        + r"(?P<name>.+?)\s+(?:on|in)\s+(?:(?:my|the)\s+)?"
        + rf"(?P<location>{location_pattern})"
        + suffix,
    )
    match = next(
        (candidate for pattern in patterns if (candidate := re.fullmatch(pattern, text, flags=re.IGNORECASE))),
        None,
    )
    if match is None:
        return None
    name = match.group("name").strip().strip('"\'')
    kind = match.group("kind").casefold()
    if Path(name).suffix.casefold() not in {"", ".txt", ".md"}:
        return None
    if not Path(name).suffix:
        name += ".md" if kind.startswith("markdown") else ".txt"
    if not _valid_text_file_name(name):
        return None
    parent_name = str(match.groupdict().get("parent") or "").strip().strip('"\'')
    if parent_name and not _valid_folder_name(parent_name):
        return None
    content = (match.group("content") or "").strip()
    if len(content) >= 2 and content[0] == content[-1] and content[0] in {'"', "'"}:
        content = content[1:-1]
    if len(content) > 2000:
        return None
    location = match.group("location").casefold()
    target = WRITABLE_FOLDERS[location] / parent_name / name if parent_name else WRITABLE_FOLDERS[location] / name
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    signed_target = f"path={target};content_sha256={content_hash}"
    if len(signed_target) > 200:
        return None
    return DeviceAction(
        action_id=f"create_note_{_slug(location)}_{_slug(name)[:60] or 'named'}",
        kind="create_text_file",
        label=f"Create note {name}",
        target=signed_target,
        path=target,
        content=content,
        source="approved_user_root",
    )


def _is_text_file_creation_intent(command: str) -> bool:
    text = _strip_wake_phrase(command)
    return bool(
        re.match(
            r"^(?:create|make|write)\s+(?:(?:a|the)\s+)?(?:(?:text|markdown)\s+file|note)\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def _append_text_file_action(command: str) -> DeviceAction | None:
    text = _strip_wake_phrase(command)
    patterns = (
        r"^(?:append|add)\s+([\"'])(?P<content>.{1,1000})\1\s+to\s+(?:(?:the|my)\s+)?(?:file|note)\s+(?P<name>.+?)\s+(?:in|on)\s+(?:(?:my|the)\s+)?(?P<location>desktop|documents|downloads|pictures|music|videos|auris workspace|auris folder)$",
        r"^append\s+to\s+(?:(?:the|my)\s+)?(?:file|note)\s+(?P<name>.+?)\s+(?:in|on)\s+(?:(?:my|the)\s+)?(?P<location>desktop|documents|downloads|pictures|music|videos|auris workspace|auris folder)\s+(?:saying|with)\s+(?P<content>.+)$",
    )
    match = next(
        (candidate for pattern in patterns if (candidate := re.fullmatch(pattern, text, flags=re.IGNORECASE))),
        None,
    )
    if match is None:
        return None
    name = _clean_path_name(match.group("name"))
    content = match.group("content").strip()
    if (
        not _valid_text_file_name(name)
        or not content
        or len(content) > 1000
        or _contains_protected_append_data(content)
    ):
        return None
    location = match.group("location").casefold()
    path = WRITABLE_FOLDERS[location] / name
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 1024 * 1024:
        return None
    try:
        original_bytes = path.read_bytes()
        original_bytes.decode("utf-8")
    except (OSError, UnicodeError):
        return None
    preimage_hash = hashlib.sha256(original_bytes).hexdigest()
    append_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    target = f"path={path};pre={preimage_hash[:32]};append={append_hash[:32]}"
    if len(target) > 200:
        return None
    return DeviceAction(
        action_id=f"append_note_{_slug(location)}_{_slug(name)[:64]}"[:120],
        kind="append_text_file",
        label=f"Append to note {name}",
        target=target,
        path=path,
        content=content,
        source="approved_user_root",
    )


def _is_text_append_intent(command: str) -> bool:
    text = _strip_wake_phrase(command)
    return bool(re.match(r"^(?:append|add)\b", text, flags=re.IGNORECASE))


def _contains_protected_append_data(content: str) -> bool:
    lowered = content.casefold()
    return any(term in lowered for term in PROTECTED_APPEND_TERMS)


def _path_transfer_action(command: str) -> DeviceAction | None:
    text = _strip_wake_phrase(command)
    location_pattern = r"desktop|documents|downloads|pictures|music|videos|auris workspace|auris folder"
    nested_rename_pattern = (
        r"^rename\s+(?:(?:the|a)\s+)?(?:(?:file|folder)\s+)?(?P<source>.+?)\s+"
        r"inside\s+(?:(?:the|a)\s+)?(?:folder\s+)?(?P<parent>.+?)\s+(?:on|in)\s+"
        rf"(?:(?:my|the)\s+)?(?P<location>{location_pattern})\s+to\s+(?P<destination>.+)$"
    )
    match = re.fullmatch(nested_rename_pattern, text, flags=re.IGNORECASE)
    if match is not None:
        source_name = _clean_path_name(match.group("source"))
        destination_name = _clean_path_name(match.group("destination"))
        parent_name = _clean_path_name(match.group("parent"))
        if not all(_valid_folder_name(value) for value in (source_name, destination_name, parent_name)):
            return None
        if Path(source_name).suffix and not Path(destination_name).suffix:
            destination_name += Path(source_name).suffix
        location = match.group("location").casefold()
        parent = WRITABLE_FOLDERS[location] / parent_name
        return _build_transfer_action(
            "rename_path", parent / source_name, parent / destination_name
        )

    rename_pattern = (
        r"^rename\s+(?:(?:the|a)\s+)?(?:(?:file|folder)\s+)?"
        r"(?P<source>.+?)\s+(?:on|in)\s+(?:(?:my|the)\s+)?"
        rf"(?P<location>{location_pattern})"
        r"\s+to\s+(?P<destination>.+)$"
    )
    match = re.fullmatch(rename_pattern, text, flags=re.IGNORECASE)
    if match is not None:
        source_name = _clean_path_name(match.group("source"))
        destination_name = _clean_path_name(match.group("destination"))
        if not _valid_folder_name(source_name) or not _valid_folder_name(destination_name):
            return None
        if Path(source_name).suffix and not Path(destination_name).suffix:
            destination_name += Path(source_name).suffix
        location = match.group("location").casefold()
        source = WRITABLE_FOLDERS[location] / source_name
        destination = WRITABLE_FOLDERS[location] / destination_name
        return _build_transfer_action("rename_path", source, destination)

    endpoint_source = (
        r"(?:(?:the\s+)?folder\s+(?P<source_parent>.+?)\s+(?:on|in)\s+)?"
        rf"(?:(?:my|the)\s+)?(?P<source_location>{location_pattern})"
    )
    endpoint_destination = (
        r"(?:(?:the\s+)?folder\s+(?P<destination_parent>.+?)\s+(?:on|in)\s+)?"
        rf"(?:(?:my|the)\s+)?(?P<destination_location>{location_pattern})"
    )
    transfer_pattern = (
        r"^(?P<verb>copy|move)\s+(?:(?:the|a)\s+)?(?:file\s+)?"
        r"(?P<source>.+?)\s+from\s+"
        + endpoint_source
        + r"\s+to\s+"
        + endpoint_destination
        + r"(?:\s+as\s+(?P<destination>.+))?$"
    )
    match = re.fullmatch(transfer_pattern, text, flags=re.IGNORECASE)
    if match is None:
        return None
    source_name = _clean_path_name(match.group("source"))
    destination_name = _clean_path_name(match.group("destination") or source_name)
    if not _valid_folder_name(source_name) or not _valid_folder_name(destination_name):
        return None
    source_parent = _clean_path_name(str(match.group("source_parent") or ""))
    destination_parent = _clean_path_name(str(match.group("destination_parent") or ""))
    if (source_parent and not _valid_folder_name(source_parent)) or (
        destination_parent and not _valid_folder_name(destination_parent)
    ):
        return None
    if Path(source_name).suffix and not Path(destination_name).suffix:
        destination_name += Path(source_name).suffix
    source_location = match.group("source_location").casefold()
    destination_location = match.group("destination_location").casefold()
    source_root = WRITABLE_FOLDERS[source_location]
    destination_root = WRITABLE_FOLDERS[destination_location]
    source = source_root / source_parent / source_name if source_parent else source_root / source_name
    destination = (
        destination_root / destination_parent / destination_name
        if destination_parent
        else destination_root / destination_name
    )
    return _build_transfer_action(f"{match.group('verb').casefold()}_file", source, destination)


def _build_transfer_action(kind: str, source: Path, destination: Path) -> DeviceAction | None:
    target = f"source={source};destination={destination}"
    if len(target) > 200:
        return None
    verb = {"rename_path": "Rename", "copy_file": "Copy", "move_file": "Move"}[kind]
    return DeviceAction(
        action_id=f"{kind}_{_slug(source.name)[:48]}_{_slug(destination.name)[:48]}"[:120],
        kind=kind,
        label=f"{verb} {source.name} to {destination.name}",
        target=target,
        path=source,
        destination=destination,
        source="approved_user_root",
    )


def _is_path_transfer_intent(command: str) -> bool:
    text = _strip_wake_phrase(command)
    return bool(re.match(r"^(?:rename|copy|move)\b", text, flags=re.IGNORECASE))


def _recycle_file_action(command: str) -> DeviceAction | None:
    text = _strip_wake_phrase(command)
    location_pattern = r"desktop|documents|downloads|pictures|music|videos|auris workspace|auris folder"
    patterns = (
        rf"^(?:move|send)\s+(?:(?:the|a)\s+)?(?:file\s+)?(?P<name>.+?)\s+from\s+(?:(?:my|the)\s+)?(?P<location>{location_pattern})\s+to\s+(?:the\s+)?recycle bin$",
        rf"^recycle\s+(?:(?:the|a)\s+)?(?:file\s+)?(?P<name>.+?)\s+(?:from|in|on)\s+(?:(?:my|the)\s+)?(?P<location>{location_pattern})$",
    )
    match = next(
        (candidate for pattern in patterns if (candidate := re.fullmatch(pattern, text, flags=re.IGNORECASE))),
        None,
    )
    if match is None:
        return None
    name = _clean_path_name(match.group("name"))
    if not _valid_folder_name(name) or Path(name).suffix.casefold() not in SAFE_RECYCLE_EXTENSIONS:
        return None
    location = match.group("location").casefold()
    path = WRITABLE_FOLDERS[location] / name
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 100 * 1024 * 1024:
            return None
        preimage_hash = _file_sha256(path)
    except OSError:
        return None
    target = f"path={path};pre={preimage_hash[:32]}"
    if len(target) > 200:
        return None
    return DeviceAction(
        action_id=f"recycle_file_{_slug(location)}_{_slug(name)[:72]}"[:120],
        kind="recycle_file",
        label=f"Move {name} to Recycle Bin",
        target=target,
        path=path,
        source="approved_user_root",
    )


def _is_recycle_file_intent(command: str) -> bool:
    text = _strip_wake_phrase(command)
    return bool(
        re.match(r"^(?:recycle\b|(?:move|send)\b.+\brecycle bin\b)", text, flags=re.IGNORECASE)
    )


def _clean_path_name(value: str) -> str:
    return value.strip().strip('"\'').strip()


def _open_file_action(command: str) -> DeviceAction | None:
    text = _strip_wake_phrase(command)
    pattern = (
        r"^open\s+(?:(?:the|a)\s+)?(?:(?:file|document|image|photo|video|audio)\s+)?"
        r"(?P<name>.+?)\s+(?:from|in|on)\s+(?:(?:my|the)\s+)?"
        r"(?P<location>desktop|documents|downloads|pictures|music|videos|auris workspace|auris folder)$"
    )
    match = re.fullmatch(pattern, text, flags=re.IGNORECASE)
    if match is None:
        return None
    name = _clean_path_name(match.group("name"))
    if not _valid_folder_name(name) or Path(name).suffix.casefold() not in SAFE_OPEN_EXTENSIONS:
        return None
    location = match.group("location").casefold()
    path = WRITABLE_FOLDERS[location] / name
    if len(str(path)) > 200:
        return None
    return DeviceAction(
        action_id=f"open_file_{_slug(location)}_{_slug(name)[:72]}"[:120],
        kind="open_file",
        label=f"Open file {name}",
        target=str(path),
        path=path,
        source="approved_user_root",
    )


def _is_open_file_intent(command: str) -> bool:
    text = _strip_wake_phrase(command)
    return bool(
        re.match(
            r"^open\s+(?:(?:the|a)\s+)?(?:(?:file|document|image|photo|video|audio)\b|.+\s+(?:from|in|on)\s+)",
            text,
            flags=re.IGNORECASE,
        )
    )


def _list_folder_action(text: str) -> DeviceAction | None:
    for phrase, path in COMMON_FOLDERS.items():
        if text in {f"list files in {phrase}", f"show files in {phrase}", f"list my {phrase}"}:
            return DeviceAction(
                f"list_{_slug(phrase)}",
                "list_folder",
                f"List {phrase.title()}",
                phrase.title(),
                path=path,
            )
    return None


def _browser_destination_action(
    text: str,
    applications: list[InstalledApplication] | None = None,
) -> DeviceAction | None:
    label = ""
    url = ""
    browser_name = ""
    search = re.fullmatch(
        r"search\s+(?:(youtube|google|the\s+web|web)\s+)?(?:for\s+)?(.{1,300}?)\s+(?:on|in|using|with)\s+(?:the\s+)?(.{1,80}?)(?:\s+browser)?",
        text,
        flags=re.IGNORECASE,
    )
    if search:
        provider = " ".join((search.group(1) or "web").casefold().split())
        query = " ".join(search.group(2).split()).strip(" .")
        browser_name = " ".join(search.group(3).split()).strip(" .")
        if not query or _contains_protected_web_data(query):
            return None
        if provider == "youtube":
            label = f"YouTube search for {query}"
            url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        else:
            label = f"Web search for {query}"
            url = f"https://www.google.com/search?q={quote_plus(query)}"
    else:
        opened = re.fullmatch(
            r"open\s+(?:the\s+)?(.{1,500}?)\s+(?:on|in|using|with)\s+(?:the\s+)?(.{1,80}?)(?:\s+browser)?",
            text,
            flags=re.IGNORECASE,
        )
        if not opened:
            return None
        raw_destination = " ".join(opened.group(1).split()).strip(" .")
        browser_name = " ".join(opened.group(2).split()).strip(" .")
        destination = KNOWN_WEB_DESTINATIONS.get(raw_destination.casefold())
        if destination is not None:
            label, url = destination
        else:
            url = _normalise_public_web_url(raw_destination)
            if not url:
                return None
            label = urlparse(url).hostname or "website"
    browser = resolve_application(browser_name, applications)
    if browser is None or not browser.process_names:
        return None
    if not any(name.casefold() in {"brave.exe", "chrome.exe", "firefox.exe", "msedge.exe"} for name in browser.process_names):
        return None
    if not _public_web_url_allowed(url, resolve_dns=False):
        return None
    browser_slug = _slug(browser.name)[:42]
    url_digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
    return DeviceAction(
        action_id=f"open_{_slug(label)}_in_{browser_slug}"[:120],
        kind="launch_app",
        label=f"Open {label} in {browser.name}",
        target=f"browser={browser_slug};url_sha256={url_digest}",
        executable=browser.launch_target,
        process_names=browser.process_names,
        arguments=(url,),
        source=f"named_browser_destination:{browser.source}",
    )


def _normalise_public_web_url(value: str) -> str:
    candidate = value.strip()
    if not candidate or any(character.isspace() for character in candidate):
        return ""
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    return candidate if _public_web_url_allowed(candidate, resolve_dns=False) else ""


def _public_web_url_allowed(value: str, *, resolve_dns: bool) -> bool:
    try:
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 80, 443}
        or hostname == "localhost"
        or hostname.endswith((".local", ".localhost", ".internal"))
        or any(key.casefold() in SENSITIVE_URL_KEYS for key, _ in parse_qsl(parsed.query, keep_blank_values=True))
    ):
        return False
    try:
        literal = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        return False
    if not resolve_dns:
        return True
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(hostname, port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        }
    except OSError:
        return False
    if not addresses:
        return False
    try:
        return all(ipaddress.ip_address(address).is_global for address in addresses)
    except ValueError:
        return False


def _contains_protected_web_data(value: str) -> bool:
    lowered = value.casefold()
    return any(term in lowered for term in PROTECTED_APPEND_TERMS)


def _application_media_action(
    text: str,
    applications: list[InstalledApplication] | None = None,
) -> DeviceAction | None:
    if not (
        re.fullmatch(
            r"(?:play|resume)\s+(?:(?:some|my)\s+)?(?:music|songs?|audio)\s+(?:on|in|using)\s+(?:the\s+)?spotify(?:\s+app)?",
            text,
            flags=re.IGNORECASE,
        )
        or re.fullmatch(r"(?:play|resume)\s+(?:the\s+)?spotify(?:\s+app)?", text, flags=re.IGNORECASE)
    ):
        return None
    application = resolve_application("Spotify", applications)
    if application is None:
        return None
    return DeviceAction(
        action_id="play_spotify",
        kind="app_media",
        label="Play media in Spotify",
        target=application.name,
        executable=application.launch_target,
        process_names=application.process_names,
        key_code=0xB3,
        source=f"targeted_media:{application.source}",
    )


def _parse_application_intent(text: str) -> tuple[str, str] | None:
    patterns = (
        ("launch_app", r"^(?:open|launch|start|run)\s+(?:the\s+)?(.+?)$"),
        ("close_app", r"^(?:close|quit|exit|terminate|stop)\s+(?:the\s+)?(.+?)$"),
        ("focus_app", r"^(?:focus|focus on|switch to|bring up|bring to front)\s+(?:the\s+)?(.+?)$"),
        ("minimize_app", r"^(?:minimize|minimise)\s+(?:the\s+)?(.+?)(?:\s+window)?$"),
        ("maximize_app", r"^(?:maximize|maximise)\s+(?:the\s+)?(.+?)(?:\s+window)?$"),
        ("restore_app", r"^restore\s+(?:the\s+)?(.+?)(?:\s+window)?$"),
    )
    for kind, pattern in patterns:
        match = re.fullmatch(pattern, text)
        if match:
            requested = match.group(1).strip(" .")
            if requested and not requested.startswith(("http://", "https://")):
                return kind, requested
    return None


def _running_processes() -> list[tuple[str, int]]:
    result = subprocess.run(
        ["tasklist.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=10,
        check=False,
    )
    processes: list[tuple[str, int]] = []
    for row in csv.reader(result.stdout.splitlines()):
        if len(row) < 2:
            continue
        try:
            processes.append((row[0], int(row[1])))
        except ValueError:
            continue
    return processes


def _find_application_window(action: DeviceAction) -> int | None:
    user32 = ctypes.windll.user32
    process_names = {name.casefold() for name in action.process_names}
    target_words = set(action.target.casefold().split())
    found: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(window: int, _: int) -> bool:
        if not user32.IsWindowVisible(window):
            return True
        length = user32.GetWindowTextLengthW(window)
        title_buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(window, title_buffer, length + 1)
        process_id = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(window, ctypes.byref(process_id))
        process_name = _process_name(process_id.value)
        title_words = set(title_buffer.value.casefold().split())
        if process_name in process_names or (target_words and target_words <= title_words):
            found.append(window)
            return False
        return True

    user32.EnumWindows(callback, 0)
    return found[0] if found else None


def _find_window_with_title(fragment: str) -> int | None:
    user32 = ctypes.windll.user32
    needle = fragment.casefold()
    found: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(window: int, _: int) -> bool:
        if not user32.IsWindowVisible(window):
            return True
        length = user32.GetWindowTextLengthW(window)
        if length <= 0:
            return True
        title_buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(window, title_buffer, length + 1)
        if needle in title_buffer.value.casefold():
            found.append(window)
            return False
        return True

    user32.EnumWindows(callback, 0)
    return found[0] if found else None


def _process_name(process_id: int) -> str:
    kernel32 = ctypes.windll.kernel32
    process = kernel32.OpenProcess(0x1000, False, process_id)
    if not process:
        return ""
    try:
        size = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
            return Path(buffer.value).name.casefold()
        return ""
    finally:
        kernel32.CloseHandle(process)


def _is_approved_path(path: Path) -> bool:
    resolved = path.resolve()
    roots = (USER_HOME.resolve(), ROOT.resolve())
    return any(resolved == root or resolved.is_relative_to(root) for root in roots)


def _is_registered_project_root(path: Path) -> bool:
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return False
    for project in list_projects():
        configured = str(project.get("root_path") or "").strip()
        if not configured:
            continue
        try:
            if Path(configured).resolve(strict=True) == resolved:
                return True
        except OSError:
            continue
    return False


def _last_json_object(output: str) -> dict[str, Any] | None:
    for line in reversed(output.splitlines()):
        try:
            payload = json.loads(line.strip())
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _normalise(command: str) -> str:
    text = " ".join(command.casefold().strip().replace(",", " ").split())
    for prefix in ("hey auris ", "auris "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = re.sub(
        r"^(?:please\s+|(?:(?:can|could|would|will)\s+you\s+)(?:please\s+)?|i\s+want\s+you\s+to\s+)",
        "",
        text,
    )
    return text.strip(" .")


def _strip_wake_phrase(command: str) -> str:
    text = " ".join(command.strip().split()).strip(" .")
    text = re.sub(r"^(?:hey\s+)?auris\s*,?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"^(?:please\s+|(?:(?:can|could|would|will)\s+you\s+)(?:please\s+)?|i\s+want\s+you\s+to\s+)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip(" .")


def _valid_folder_name(name: str) -> bool:
    if not name or len(name) > 80 or name in {".", ".."}:
        return False
    if name.startswith(".") or name.endswith((" ", ".")):
        return False
    if any(ord(character) < 32 or character in '<>:"/\\|?*' for character in name):
        return False
    return name.split(".", 1)[0].casefold() not in WINDOWS_RESERVED_NAMES


def _valid_text_file_name(name: str) -> bool:
    return _valid_folder_name(name) and Path(name).suffix.casefold() in {".txt", ".md"}


def _is_approved_direct_child(path: Path) -> bool:
    if not _valid_folder_name(path.name):
        return False
    try:
        parent = path.parent.resolve(strict=True)
        roots = {root.resolve(strict=True) for root in WRITABLE_FOLDERS.values()}
    except OSError:
        return False
    return parent in roots


def _is_approved_bounded_item(path: Path) -> bool:
    if not _valid_folder_name(path.name):
        return False
    try:
        resolved_parent = path.parent.resolve(strict=True)
    except OSError:
        return False
    return _is_approved_creation_parent(path.parent, resolved_parent)


def _is_approved_creation_parent(original_parent: Path, resolved_parent: Path) -> bool:
    try:
        if original_parent.is_symlink() or not original_parent.is_dir():
            return False
        roots = {root.resolve(strict=True) for root in WRITABLE_FOLDERS.values()}
    except OSError:
        return False
    if resolved_parent in roots:
        return True
    return any(resolved_parent.parent == root for root in roots)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
