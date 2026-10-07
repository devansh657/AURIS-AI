from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auris.telephony_agent import telephony_status

from auris.audit import record_event
from auris.windows_apps import discover_installed_applications

try:
    import winreg
except ImportError:  # pragma: no cover - AURIS targets Windows.
    winreg = None


ROOT = Path(__file__).resolve().parents[1]
OUTLOOK_SCRIPT = ROOT / "scripts" / "outlook_connector.ps1"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass(frozen=True)
class CommunicationRequest:
    kind: str
    query: str = ""
    days: int = 7
    recipient: str = ""
    subject: str = ""
    body: str = ""
    channel: str = ""
    contact: str = ""


def match_communication_command(command: str) -> CommunicationRequest | None:
    text = _strip_prefix(command)
    phone_status = re.fullmatch(
        r"(?:check|show|what(?:'s| is))\s+(?:the\s+)?(?:auris\s+)?"
        r"(?:phone|call|telephony)(?:\s+(?:status|readiness))?\.?",
        text,
        flags=re.IGNORECASE,
    )
    if phone_status:
        return CommunicationRequest("phone_status")

    outbound_call = re.fullmatch(
        r"(?:(?:make|place|start)\s+)?(?:an?\s+)?"
        r"(?:(whatsapp|normal|phone)\s+)?(?:audio\s+|voice\s+)?"
        r"call(?:\s+to)?\s+(.+?)\.?",
        text,
        flags=re.IGNORECASE,
    )
    if outbound_call:
        channel_token = (outbound_call.group(1) or "phone").casefold()
        channel = "whatsapp" if channel_token == "whatsapp" else "phone"
        contact = " ".join(outbound_call.group(2).strip(" .\"").split())[:120]
        if contact and not re.search(r"[\r\n<>]", contact):
            return CommunicationRequest("start_call", channel=channel, contact=contact)

    status = re.fullmatch(
        r"(?:check|show|list)\s+(?:my\s+)?(?:productivity\s+)?(?:connections|integrations)\.?",
        text,
        flags=re.IGNORECASE,
    )
    if status:
        return CommunicationRequest("status")

    search = re.fullmatch(
        r"(?:search|find)\s+(?:my\s+)?emails?\s+(?:for|about)\s+(.+)",
        text,
        flags=re.IGNORECASE,
    )
    if search:
        query = search.group(1).strip(" .\"")[:200]
        return CommunicationRequest("search_mail", query=query) if len(query) >= 2 else None

    contacts = re.fullmatch(
        r"(?:search|find|look\s+up|show)\s+(?:my\s+)?contacts?\s+"
        r"(?:(?:for|named)\s+)?(.+)",
        text,
        flags=re.IGNORECASE,
    )
    if contacts:
        query = contacts.group(1).strip(" .\"")[:200]
        return CommunicationRequest("search_contacts", query=query) if len(query) >= 2 else None

    calendar = re.fullmatch(
        r"(?:show|list|check)\s+(?:my\s+)?calendar(?:\s+for)?(?:\s+the)?\s*"
        r"(?:(?:next\s+)?(\d{1,2})\s+days?|today|tomorrow|this\s+week)?\.?",
        text,
        flags=re.IGNORECASE,
    )
    if calendar:
        lowered = text.casefold()
        days = int(calendar.group(1) or (1 if "today" in lowered else 2 if "tomorrow" in lowered else 7))
        return CommunicationRequest("calendar", days=max(1, min(days, 31)))

    email = re.fullmatch(
        r"(draft|send)(?:\s+an?)?\s+email\s+to\s+([^\s]+)\s+"
        r"subject\s+(.+?)\s+(?:saying|body|message)\s+(.+)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if email:
        recipient = email.group(2).strip(" <>\"")
        subject = email.group(3).strip(" .\"")[:200]
        body = email.group(4).strip()[:5000]
        if EMAIL_PATTERN.fullmatch(recipient) and subject and body:
            return CommunicationRequest(email.group(1).casefold(), recipient=recipient, subject=subject, body=body)
    return None


def productivity_status() -> dict[str, Any]:
    applications = discover_installed_applications()
    outlook_available = any("outlook" in app.name.casefold() for app in applications)
    classic_available = _classic_outlook_available()
    outlook_profile = _classic_outlook_profile_exists()
    one_drive_roots = onedrive_roots()
    return {
        "outlook": {
            "available": outlook_available,
            "classic_available": classic_available,
            "connected": classic_available and outlook_profile,
            "state": (
                "connected"
                if classic_available and outlook_profile
                else "profile_required"
                if classic_available
                else "oauth_required"
                if outlook_available
                else "not_installed"
            ),
            "permissions": [
                "search_mail",
                "read_calendar",
                "search_contacts",
                "create_draft",
                "approved_send",
            ],
            "write_requires_approval": True,
        },
        "onedrive": {
            "available": bool(one_drive_roots),
            "connected": bool(one_drive_roots),
            "state": "local_sync_connected" if one_drive_roots else "not_configured",
            "mode": "read_only_local_sync",
            "root_count": len(one_drive_roots),
            "permissions": ["search_filenames", "read_supported_documents"],
        },
        "telephony": telephony_status(),
    }


def onedrive_roots() -> tuple[Path, ...]:
    candidates = (
        os.environ.get("OneDrive"),
        os.environ.get("OneDriveConsumer"),
        os.environ.get("OneDriveCommercial"),
    )
    roots: list[Path] = []
    seen: set[Path] = set()
    for value in candidates:
        if not value:
            continue
        path = Path(value).expanduser()
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved.exists() and resolved not in seen:
            roots.append(resolved)
            seen.add(resolved)
    return tuple(roots)


def execute_communication_request(request: CommunicationRequest) -> dict[str, Any]:
    if request.kind == "phone_status":
        status = telephony_status()
        connected = bool(status.get("connected"))
        return {
            "ok": True,
            "message": (
                "AURIS phone answering is connected and ready."
                if connected
                else "AURIS phone answering is not connected yet. A dedicated provider number and trusted voice endpoint are still required."
            ),
            "verification": (
                "Confirmed: the inbound provider, signed relay, handoff, and summary configuration are ready."
                if connected
                else "Confirmed: no live inbound provider is connected, so AURIS cannot currently receive or answer real calls."
            ),
            "operation": "phone_status",
            "telephony": status,
        }

    if request.kind == "start_call":
        return _execute_outbound_call(request)

    if request.kind == "status":
        status = productivity_status()
        connected = [name for name, connector in status.items() if connector["connected"]]
        return {
            "ok": True,
            "message": f"{len(connected)} productivity connector{'s are' if len(connected) != 1 else ' is'} connected.",
            "verification": "Confirmed: connector availability and authorization state were inspected without reading account content.",
            "connectors": status,
            "operation": "status",
        }

    payload = {
        "mode": request.kind,
        "query": request.query,
        "days": request.days,
        "recipient": request.recipient,
        "subject": request.subject,
        "body": request.body,
        "limit": 20,
    }
    outcome = _invoke_outlook(payload)
    record_event(
        "communications.operation_finished",
        {
            "connector": "outlook_classic",
            "operation": request.kind,
            "success": bool(outcome.get("ok")),
            "item_count": len(outcome.get("items", [])),
            "content_logged": False,
        },
    )
    if not outcome.get("ok"):
        error = str(outcome.get("error", "The Outlook connector failed."))
        return {
            "ok": False,
            "error": error,
            "retryable": request.kind in {"search_mail", "calendar", "search_contacts"}
            and _transient_outlook_error(error),
            "verification": "No Outlook result was verified and no external communication was represented as complete.",
            "operation": request.kind,
        }

    items = outcome.get("items", [])
    if request.kind == "search_mail":
        message = f"I found {len(items)} matching Outlook message{'s' if len(items) != 1 else ''}."
        verification = f"Confirmed: {outcome.get('scanned', 0)} recent Inbox items were scanned read-only; no message was changed."
    elif request.kind == "calendar":
        message = f"I found {len(items)} Outlook calendar event{'s' if len(items) != 1 else ''} in the requested window."
        verification = "Confirmed: Outlook calendar items were read without creating or changing an event."
    elif request.kind == "search_contacts":
        message = f"I found {len(items)} matching Outlook contact{'s' if len(items) != 1 else ''}."
        verification = (
            f"Confirmed: {outcome.get('scanned', 0)} Outlook contacts were scanned read-only; "
            "contact details were not added to durable task history."
        )
    elif request.kind == "draft":
        message = f"The Outlook draft for {request.recipient} is saved."
        verification = "Confirmed: Outlook assigned the item a Drafts entry identifier; nothing was sent."
    else:
        message = f"Outlook accepted the approved message to {request.recipient} for sending."
        verification = "Confirmed: Outlook accepted the message into its send pipeline; remote delivery cannot be independently guaranteed."
    return {**outcome, "message": message, "verification": verification}


def communication_approval_details(command: str) -> tuple[str, str]:
    request = match_communication_command(command)
    if request is not None and request.kind == "start_call":
        return (
            request.contact,
            f"Start one {request.channel} audio call to the exact named contact after connector readiness is verified.",
        )
    if request is None or request.kind != "send":
        return "external communication service", "The command and task plan. No secrets are included."
    return (
        request.recipient,
        f"SUBJECT: {request.subject}\nBODY: {request.body}",
    )


def _execute_outbound_call(request: CommunicationRequest) -> dict[str, Any]:
    if request.channel == "whatsapp":
        applications = discover_installed_applications()
        installed = any("whatsapp" in app.name.casefold() for app in applications)
        if not installed:
            return {
                "ok": False,
                "error": (
                    "WhatsApp Desktop is not installed or linked on this PC, so I did not attempt the call. "
                    "Install and link WhatsApp Desktop before enabling verified contact-and-call control."
                ),
                "verification": "Confirmed: no WhatsApp call was started and no contact was messaged.",
                "operation": "start_call",
                "channel": "whatsapp",
                "connector_state": "application_required",
                "contact_resolved": False,
                "call_started": False,
            }
        return {
            "ok": False,
            "error": (
                "WhatsApp Desktop is present, but the verified contact-selection and audio-call adapter is not enabled yet. "
                "I stopped before opening a chat or placing a call."
            ),
            "verification": "Confirmed: no WhatsApp audio-call state was observed, so the call was not represented as started.",
            "operation": "start_call",
            "channel": "whatsapp",
            "connector_state": "automation_required",
            "contact_resolved": False,
            "call_started": False,
        }

    status = telephony_status()
    return {
        "ok": False,
        "error": (
            "Outbound phone calling is not connected. AURIS currently has only the guarded inbound-call contract; "
            "a provider account, dedicated number, outbound permission, and trusted public voice endpoint are required."
        ),
        "verification": "Confirmed: no normal phone call was placed.",
        "operation": "start_call",
        "channel": "phone",
        "connector_state": status.get("state", "configuration_required"),
        "contact_resolved": False,
        "call_started": False,
    }


def _invoke_outlook(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(OUTLOOK_SCRIPT),
            ],
            input=json.dumps(payload, ensure_ascii=True),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "error": f"The Outlook connector did not respond: {error}"}
    parsed = _last_json_object(result.stdout)
    if parsed is None:
        return {"ok": False, "error": result.stderr.strip() or "Outlook returned no readable result."}
    return parsed


def _classic_outlook_available() -> bool:
    paths = (
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft Office" / "root" / "Office16" / "OUTLOOK.EXE",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft Office" / "root" / "Office16" / "OUTLOOK.EXE",
    )
    return any(path.exists() for path in paths) or _registry_outlook_path_exists()


def _registry_outlook_path_exists() -> bool:
    if winreg is None:
        return False
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, r"Software\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE") as key:
                value = str(winreg.QueryValue(key, None)).strip('"')
                if value and Path(value).exists():
                    return True
        except OSError:
            continue
    return False


def _classic_outlook_profile_exists() -> bool:
    if winreg is None:
        return False
    for version in ("16.0", "15.0"):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\Office\{version}\Outlook\Profiles") as key:
                if winreg.QueryInfoKey(key)[0] > 0:
                    return True
        except OSError:
            continue
    return False


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


def _strip_prefix(command: str) -> str:
    text = " ".join(command.strip().replace(",", " ").split())
    lowered = text.casefold()
    for prefix in ("hey auris ", "auris "):
        if lowered.startswith(prefix):
            return text[len(prefix) :].strip()
    return text.strip()


def _transient_outlook_error(error: str) -> bool:
    lowered = error.casefold()
    return any(
        marker in lowered
        for marker in (
            "server execution failed",
            "call was rejected by callee",
            "rpc server",
            "temporarily unavailable",
            "did not respond",
            "operation unavailable",
        )
    )
