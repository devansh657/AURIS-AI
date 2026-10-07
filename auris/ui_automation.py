from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auris.device_agent import DeviceAction
from auris.windows_apps import InstalledApplication, resolve_application


ROOT = Path(__file__).resolve().parents[1]
UI_AUTOMATION_SCRIPT = ROOT / "scripts" / "ui_automation.ps1"
MAX_CONTROL_NAME = 120
MAX_APPLICATION_NAME = 120
PROTECTED_APPLICATION_NAMES = {
    "command prompt",
    "credential manager",
    "powershell",
    "registry editor",
    "regedit",
    "task manager",
    "terminal",
    "windows security",
    "windows terminal",
}
PROTECTED_PROCESS_NAMES = {
    "cmd.exe",
    "credentialui.exe",
    "lsass.exe",
    "powershell.exe",
    "pwsh.exe",
    "regedit.exe",
    "securityhealthsystray.exe",
    "taskmgr.exe",
    "windowsterminal.exe",
}
HIGH_CONSEQUENCE_CONTROL = re.compile(
    r"\b(?:accept|agree|allow|buy|change\s+password|confirm|delete|erase|format|install|"
    r"order|pay|permit|purchase|remove|reset|send|submit|uninstall|wipe|yes)\b",
    flags=re.IGNORECASE,
)
PROCESS_NAME_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,80}")


@dataclass(frozen=True)
class UiControlRequest:
    control_name: str
    application_name: str


def is_ui_control_intent(command: str) -> bool:
    return _parse_ui_control_command(command) is not None


def match_ui_control_command(command: str) -> UiControlRequest | None:
    parsed = _parse_ui_control_command(command)
    if parsed is None:
        return None
    control_name, application_name = parsed
    if _protected_application_name(application_name) or HIGH_CONSEQUENCE_CONTROL.search(control_name):
        return None
    return UiControlRequest(control_name, application_name)


def ui_control_refusal(command: str) -> str | None:
    parsed = _parse_ui_control_command(command)
    if parsed is None:
        return None
    control_name, application_name = parsed
    if _protected_application_name(application_name):
        return "AURIS does not automate controls inside security, credential, shell, registry, or task-management applications."
    if HIGH_CONSEQUENCE_CONTROL.search(control_name):
        return "That control could create a consequential commitment or irreversible change, so generic UI Automation will not invoke it."
    return None


def build_ui_control_action(
    request: UiControlRequest,
    applications: list[InstalledApplication] | None = None,
) -> tuple[DeviceAction | None, str | None]:
    application = resolve_application(request.application_name, applications)
    if application is None:
        return None, f"I could not resolve an installed application named {request.application_name}."
    if _protected_application(application):
        return None, "That application is outside the approved UI Automation boundary."
    canonical = f"{application.name.casefold()}\0{request.control_name.casefold()}"
    binding = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    app_slug = _slug(application.name)[:42]
    control_slug = _slug(request.control_name)[:42]
    return (
        DeviceAction(
            action_id=f"invoke_{app_slug}_{control_slug}"[:120],
            kind="invoke_control",
            label=f"Invoke {request.control_name} in {application.name}",
            target=f"app={app_slug};control_sha256={binding}",
            executable=application.launch_target,
            process_names=application.process_names,
            source=f"ui_automation:{application.source}",
        ),
        None,
    )


def ui_control_approval_details(command: str) -> tuple[str, str]:
    request = match_ui_control_command(command)
    if request is None:
        return "named Windows application control", "No UI control will be invoked unless the request resolves again after approval."
    return (
        request.application_name,
        f'Invoke the exact visible control "{request.control_name}" once. No typed text or screen image is persisted.',
    )


def execute_ui_control_request(request: UiControlRequest) -> dict[str, Any]:
    application = resolve_application(request.application_name)
    if application is None:
        return {"ok": False, "error": f"I could not resolve an installed application named {request.application_name}."}
    if _protected_application(application):
        return {"ok": False, "error": "That application is outside the approved UI Automation boundary."}
    process_names = sorted(
        {
            name.casefold()
            for name in application.process_names
            if PROCESS_NAME_PATTERN.fullmatch(name)
        }
    )
    if not process_names:
        return {"ok": False, "error": "The selected application has no bounded process identity for UI Automation."}
    payload = {
        "application_name": application.name,
        "control_name": request.control_name,
        "process_names": process_names[:8],
    }
    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(UI_AUTOMATION_SCRIPT),
    ]
    try:
        process = subprocess.run(
            command,
            cwd=ROOT,
            input=json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=15,
            check=False,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "ok": False,
            "error": f"Windows UI Automation could not complete safely: {error}",
            "verification": "No completed control invocation was observed.",
        }
    observed = _last_json_object(process.stdout)
    invoked = bool(process.returncode == 0 and observed and observed.get("invoked"))
    verified = bool(invoked and observed.get("observed"))
    result = {
        "ok": verified,
        "message": (
            f'{request.control_name} was invoked in {application.name} and a Windows UI change was observed.'
            if verified
            else f'Windows did not verify the full effect of invoking {request.control_name} in {application.name}.'
        ),
        "error": None if verified else str((observed or {}).get("error") or "The named control was unavailable, ambiguous, unsupported, or produced no observable UI change."),
        "verification": (
            "Confirmed: the exact enabled UI Automation control was invoked once and Windows reported "
            f"the observation {observed.get('observation')}. No screenshot, UI text, or state digest was retained."
            if verified and observed
            else "The operation is not marked complete because an exact post-action UI observation was unavailable."
        ),
        "application": application.name,
        "control_name": request.control_name,
        "control_type": (observed or {}).get("control_type"),
        "automation_pattern": (observed or {}).get("automation_pattern"),
        "observation": (observed or {}).get("observation"),
        "invoked": invoked,
        "observed": verified,
        "may_have_executed": invoked and not verified,
        "memory_only_automation_observation": bool((observed or {}).get("memory_only_automation_observation")),
        "temporary_capture_persisted": False,
    }
    return result


def _parse_ui_control_command(command: str) -> tuple[str, str] | None:
    text = _normalise(command)
    patterns = (
        r'^(?:click|press|activate)\s+["\'](.{1,120})["\']\s+(?:in|inside)\s+(?:the\s+)?(.{1,120})$',
        r"^(?:click|press|activate)\s+(?:the\s+)?(.{1,120}?)\s+(?:button|control|menu\s+item|tab)\s+(?:in|inside)\s+(?:the\s+)?(.{1,120})$",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, text, flags=re.IGNORECASE)
        if match:
            control_name = " ".join(match.group(1).split()).strip(" .")
            application_name = " ".join(match.group(2).split()).strip(" .")
            if control_name and application_name:
                return control_name[:MAX_CONTROL_NAME], application_name[:MAX_APPLICATION_NAME]
    return None


def _protected_application_name(name: str) -> bool:
    normalized = " ".join(name.casefold().split()).strip(" .")
    return normalized in PROTECTED_APPLICATION_NAMES


def _protected_application(application: InstalledApplication) -> bool:
    return _protected_application_name(application.name) or bool(
        {name.casefold() for name in application.process_names}.intersection(PROTECTED_PROCESS_NAMES)
    )


def _last_json_object(output: str) -> dict[str, Any] | None:
    for line in reversed(output.splitlines()):
        try:
            payload = json.loads(line.strip())
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_") or "control"


def _normalise(command: str) -> str:
    text = " ".join(command.strip().replace(",", " ").split())
    lowered = text.casefold()
    for prefix in ("hey auris ", "auris "):
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.strip(" .")
