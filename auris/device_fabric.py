from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from auris.auth import harden_private_file
from auris.database import (
    DATABASE_PATH,
    claim_device_command_nonce,
    get_device,
    upsert_device,
)
from auris.device_agent import DeviceAction
from auris.windows_secrets import (
    DPAPI_PREFIX,
    dpapi_available,
    protect_for_current_user,
    unprotect_for_current_user,
)


ROOT = Path(__file__).resolve().parents[1]
DEVICE_KEY_PATH = ROOT / "data" / "device.key"
DEVICE_IDENTITY_PATH = ROOT / "data" / "device-identity.json"
TOOL_NAME = "windows.device_action"
ALLOWED_PERMISSIONS = (
    "launch_app",
    "close_app",
    "focus_app",
    "minimize_app",
    "maximize_app",
    "restore_app",
    "open_folder",
    "open_file",
    "open_url",
    "list_folder",
    "create_folder",
    "create_text_file",
    "append_text_file",
    "rename_path",
    "copy_file",
    "move_file",
    "recycle_file",
    "media_key",
    "app_media",
    "type_text",
    "invoke_control",
    "browser_navigate",
    "browser_inspect",
    "browser_fill",
    "browser_click",
    "browser_workflow",
)
ACTION_ID_PATTERN = re.compile(r"[a-z0-9_]{2,120}")
NONCE_PATTERN = re.compile(r"[A-Za-z0-9_-]{32,160}")


@dataclass(frozen=True)
class FabricDecision:
    ok: bool
    command_id: str = ""
    device_id: str = ""
    error: str = ""
    signature_verified: bool = False
    nonce_claimed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "command_id": self.command_id,
            "device_id": self.device_id,
            "error": self.error,
            "signature_verified": self.signature_verified,
            "nonce_claimed": self.nonce_claimed,
        }


def initialize_device_identity(
    *,
    key_path: Path = DEVICE_KEY_PATH,
    identity_path: Path = DEVICE_IDENTITY_PATH,
    database_path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key = _load_or_create_key(key_path)
    identity = _load_or_create_identity(identity_path)
    harden_private_file(key_path)
    harden_private_file(identity_path)
    record = upsert_device(
        {
            **identity,
            "display_name": identity.get("display_name") or os.environ.get("COMPUTERNAME", "AURIS Windows device"),
            "machine_name": os.environ.get("COMPUTERNAME", platform.node() or "Windows device"),
            "platform": platform.platform(),
            "trust_state": "local_hmac",
            "permissions": list(ALLOWED_PERMISSIONS),
            "key_fingerprint": hashlib.sha256(key).hexdigest(),
            "certificate_state": "not_configured",
        },
        path=database_path,
    )
    return record


def issue_device_command(
    action: DeviceAction,
    *,
    ttl_seconds: int = 30,
    key_path: Path = DEVICE_KEY_PATH,
    identity_path: Path = DEVICE_IDENTITY_PATH,
    database_path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    identity = initialize_device_identity(
        key_path=key_path, identity_path=identity_path, database_path=database_path
    )
    now = datetime.now(timezone.utc)
    ttl = max(5, min(int(ttl_seconds), 120))
    envelope: dict[str, Any] = {
        "command_id": str(uuid4()),
        "device_id": identity["device_id"],
        "tool": TOOL_NAME,
        "parameters": {
            "action_id": action.action_id,
            "kind": action.kind,
            "target": action.target[:200],
        },
        "permission_scope": action.kind,
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=ttl)).isoformat(),
        "nonce": secrets.token_urlsafe(32),
    }
    envelope["signature"] = _sign(envelope, _read_key(key_path))
    return envelope


def verify_and_claim_device_command(
    envelope: dict[str, Any],
    *,
    key_path: Path = DEVICE_KEY_PATH,
    identity_path: Path = DEVICE_IDENTITY_PATH,
    database_path: Path = DATABASE_PATH,
    now: datetime | None = None,
) -> FabricDecision:
    identity = initialize_device_identity(
        key_path=key_path, identity_path=identity_path, database_path=database_path
    )
    command_id = str(envelope.get("command_id") or "")
    device_id = str(envelope.get("device_id") or "")
    required = {
        "command_id", "device_id", "tool", "parameters", "permission_scope",
        "issued_at", "expires_at", "nonce", "signature",
    }
    if set(envelope) != required:
        return FabricDecision(False, command_id, device_id, "The signed command schema is invalid.")
    if not _valid_uuid(command_id) or device_id != identity["device_id"]:
        return FabricDecision(False, command_id, device_id, "The command targets the wrong device identity.")
    device = get_device(device_id, path=database_path)
    if device is None or device.get("revoked_at") or device.get("trust_state") == "revoked":
        return FabricDecision(False, command_id, device_id, "The device identity is unavailable or revoked.")
    if envelope.get("tool") != TOOL_NAME:
        return FabricDecision(False, command_id, device_id, "The requested device tool is not allowlisted.")
    parameters = envelope.get("parameters")
    if not isinstance(parameters, dict) or set(parameters) != {"action_id", "kind", "target"}:
        return FabricDecision(False, command_id, device_id, "The typed device parameters are invalid.")
    scope = str(envelope.get("permission_scope") or "")
    if (
        scope != parameters.get("kind")
        or scope not in ALLOWED_PERMISSIONS
        or scope not in device.get("permissions", [])
    ):
        return FabricDecision(False, command_id, device_id, "The device permission scope is missing or denied.")
    if not ACTION_ID_PATTERN.fullmatch(str(parameters.get("action_id") or "")):
        return FabricDecision(False, command_id, device_id, "The device action identifier is invalid.")
    target = str(parameters.get("target") or "")
    if not target or len(target) > 200:
        return FabricDecision(False, command_id, device_id, "The device action target is invalid.")
    current = now or datetime.now(timezone.utc)
    issued_at = _timestamp(envelope.get("issued_at"))
    expires_at = _timestamp(envelope.get("expires_at"))
    if issued_at is None or expires_at is None:
        return FabricDecision(False, command_id, device_id, "The command timestamps are invalid.")
    if issued_at > current + timedelta(seconds=30) or expires_at <= current:
        return FabricDecision(False, command_id, device_id, "The signed command is expired or not yet valid.")
    if expires_at - issued_at > timedelta(seconds=120):
        return FabricDecision(False, command_id, device_id, "The command validity window is too broad.")
    signature = str(envelope.get("signature") or "")
    expected = _sign({key: value for key, value in envelope.items() if key != "signature"}, _read_key(key_path))
    if not signature or not hmac.compare_digest(signature, expected):
        return FabricDecision(False, command_id, device_id, "The device command signature is invalid.")
    nonce = str(envelope.get("nonce") or "")
    if not NONCE_PATTERN.fullmatch(nonce):
        return FabricDecision(False, command_id, device_id, "The device command nonce is invalid.", True)
    claimed = claim_device_command_nonce(
        nonce,
        device_id,
        command_id,
        expires_at.isoformat(),
        path=database_path,
    )
    if not claimed:
        return FabricDecision(False, command_id, device_id, "The device command nonce was already consumed.", True)
    return FabricDecision(True, command_id, device_id, signature_verified=True, nonce_claimed=True)


def authorize_local_device_action(action: DeviceAction) -> dict[str, Any]:
    envelope = issue_device_command(action)
    decision = verify_and_claim_device_command(envelope)
    return {
        **decision.to_dict(),
        "tool": envelope["tool"],
        "permission_scope": envelope["permission_scope"],
        "issued_at": envelope["issued_at"],
        "expires_at": envelope["expires_at"],
        "transport": "local_authenticated_fabric",
    }


def device_trust_status() -> dict[str, Any]:
    identity = _default_device_identity()
    device = get_device(identity["device_id"]) or identity
    return {
        "device_id": device["device_id"],
        "display_name": device["display_name"],
        "machine_name": device["machine_name"],
        "trust_state": device["trust_state"],
        "permissions": device["permissions"],
        "key_fingerprint": device["key_fingerprint"],
        "certificate_state": device["certificate_state"],
        "revoked": bool(device.get("revoked_at")),
        "transport": "local_authenticated_fabric",
        "key_storage": "windows_dpapi" if dpapi_available() else "restricted_file",
        "remote_channel": "not_configured",
        "public_inbound_port": False,
    }


@lru_cache(maxsize=1)
def _default_device_identity() -> dict[str, Any]:
    return initialize_device_identity()


def _load_or_create_key(path: Path) -> bytes:
    if path.exists():
        return _read_key(path)
    key = secrets.token_bytes(32)
    _write_key(path, key)
    return key


def _read_key(path: Path) -> bytes:
    try:
        encoded = path.read_text(encoding="ascii").strip()
        if encoded.startswith(DPAPI_PREFIX):
            key = unprotect_for_current_user(encoded, purpose="auris-device-command-key-v1")
        else:
            key = bytes.fromhex(encoded)
            if dpapi_available():
                _write_key(path, key)
    except (OSError, ValueError) as error:
        raise RuntimeError("The AURIS device key is unreadable.") from error
    if len(key) != 32:
        raise RuntimeError("The AURIS device key has an invalid length.")
    return key


def _write_key(path: Path, key: bytes) -> None:
    encoded = (
        protect_for_current_user(key, purpose="auris-device-command-key-v1")
        if dpapi_available()
        else key.hex()
    )
    path.write_text(encoded, encoding="ascii")


def _load_or_create_identity(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            identity = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError("The AURIS device identity is unreadable.") from error
        if isinstance(identity, dict) and _valid_uuid(str(identity.get("device_id") or "")):
            return identity
        raise RuntimeError("The AURIS device identity is invalid.")
    identity = {
        "device_id": str(uuid4()),
        "display_name": os.environ.get("COMPUTERNAME", "AURIS Windows device"),
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(identity, ensure_ascii=True, indent=2), encoding="utf-8")
    return identity


def _sign(envelope: dict[str, Any], key: bytes) -> str:
    canonical = json.dumps(envelope, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _valid_uuid(value: str) -> bool:
    try:
        UUID(value)
    except (ValueError, TypeError):
        return False
    return True
