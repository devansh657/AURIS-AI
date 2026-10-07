from __future__ import annotations

import base64
import json
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from auris.database import DATABASE_PATH, claim_device_command_nonce, get_device


NONCE_PATTERN = re.compile(r"[A-Za-z0-9_-]{32,160}")
ACTION_ID_PATTERN = re.compile(r"[a-z0-9_]{2,120}")
TOOL_NAME = "windows.device_action"
EXACT_ENVELOPE_KEYS = {
    "command_id",
    "device_id",
    "tool",
    "parameters",
    "permission_scope",
    "issued_at",
    "expires_at",
    "nonce",
    "signature",
}


@dataclass(frozen=True)
class RemoteCommandDecision:
    ok: bool
    command_id: str = ""
    error: str = ""
    signature_verified: bool = False
    nonce_claimed: bool = False


class CloudChannelError(RuntimeError):
    pass


Transport = Callable[[str, str, bytes, dict[str, str]], tuple[int, bytes]]


class CloudChannelClient:
    def __init__(
        self,
        *,
        endpoint: str,
        device_id: str,
        device_private_key: Ed25519PrivateKey,
        transport: Transport | None = None,
    ) -> None:
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("The AURIS cloud endpoint must use HTTPS.")
        self.endpoint = endpoint.rstrip("/")
        self.device_id = str(UUID(device_id))
        self.device_private_key = device_private_key
        self.transport = transport or self._https_transport

    def poll(self) -> dict[str, Any] | None:
        status, raw = self._request("GET", "/v1/device/commands/next")
        if status == 204:
            return None
        response = _json_object(raw)
        if status != 200 or response.get("ok") is not True:
            raise CloudChannelError(_response_error(response, status))
        command = response.get("command")
        if not isinstance(command, dict):
            raise CloudChannelError("The cloud returned an invalid command envelope.")
        return command

    def acknowledge(
        self,
        command_id: str,
        *,
        state: str,
        verification_summary: str,
    ) -> dict[str, Any]:
        if state not in {"completed", "failed", "rejected"}:
            raise ValueError("The remote acknowledgement state is invalid.")
        body = json.dumps(
            {
                "state": state,
                "verification_summary": " ".join(verification_summary.split())[:500],
            },
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        status, raw = self._request(
            "POST", f"/v1/device/commands/{UUID(command_id)}/ack", body
        )
        response = _json_object(raw)
        if status != 200 or response.get("ok") is not True:
            raise CloudChannelError(_response_error(response, status))
        return response

    def _request(self, method: str, path: str, body: bytes = b"") -> tuple[int, bytes]:
        issued_at = datetime.now(timezone.utc).isoformat()
        nonce = secrets.token_urlsafe(32)
        proof = remote_request_proof(
            method, path, self.device_id, issued_at, nonce, body
        )
        signature = _b64url(self.device_private_key.sign(proof))
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-AURIS-Device-ID": self.device_id,
            "X-AURIS-Timestamp": issued_at,
            "X-AURIS-Nonce": nonce,
            "X-AURIS-Signature": signature,
        }
        return self.transport(method, path, body, headers)

    def _https_transport(
        self, method: str, path: str, body: bytes, headers: dict[str, str]
    ) -> tuple[int, bytes]:
        request = Request(
            f"{self.endpoint}{path}",
            data=body if method != "GET" else None,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=35) as response:
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()
        except (URLError, TimeoutError, OSError) as error:
            raise CloudChannelError("The outbound AURIS cloud channel is unavailable.") from error


def verify_remote_command(
    envelope: dict[str, Any],
    *,
    cloud_public_key_b64: str,
    expected_device_id: str,
    database_path: Path = DATABASE_PATH,
    now: datetime | None = None,
) -> RemoteCommandDecision:
    command_id = str(envelope.get("command_id") or "")
    if set(envelope) != EXACT_ENVELOPE_KEYS:
        return RemoteCommandDecision(False, command_id, "The remote command schema is invalid.")
    try:
        UUID(command_id)
        expected_device_id = str(UUID(expected_device_id))
    except ValueError:
        return RemoteCommandDecision(False, command_id, "The remote command identity is invalid.")
    if envelope.get("device_id") != expected_device_id:
        return RemoteCommandDecision(False, command_id, "The remote command targets another device.")
    device = get_device(expected_device_id, path=database_path)
    if device is None or device.get("revoked_at") or device.get("trust_state") == "revoked":
        return RemoteCommandDecision(False, command_id, "The local device trust is unavailable or revoked.")
    if envelope.get("tool") != TOOL_NAME:
        return RemoteCommandDecision(False, command_id, "The remote device tool is not allowlisted.")
    parameters = envelope.get("parameters")
    if not isinstance(parameters, dict) or set(parameters) != {"action_id", "kind", "target"}:
        return RemoteCommandDecision(False, command_id, "The remote command parameters are invalid.")
    scope = str(envelope.get("permission_scope") or "")
    if scope != parameters.get("kind") or scope not in device.get("permissions", []):
        return RemoteCommandDecision(False, command_id, "The remote permission scope is denied locally.")
    if not ACTION_ID_PATTERN.fullmatch(str(parameters.get("action_id") or "")):
        return RemoteCommandDecision(False, command_id, "The remote action identifier is invalid.")
    target = str(parameters.get("target") or "")
    if not target or len(target) > 200:
        return RemoteCommandDecision(False, command_id, "The remote action target is invalid.")
    current = now or datetime.now(timezone.utc)
    issued_at = _timestamp(envelope.get("issued_at"))
    expires_at = _timestamp(envelope.get("expires_at"))
    if issued_at is None or expires_at is None:
        return RemoteCommandDecision(False, command_id, "The remote command timestamps are invalid.")
    if issued_at > current + timedelta(seconds=30) or expires_at <= current:
        return RemoteCommandDecision(False, command_id, "The remote command is expired or not yet valid.")
    if expires_at - issued_at > timedelta(seconds=120):
        return RemoteCommandDecision(False, command_id, "The remote validity window is too broad.")
    unsigned = {key: value for key, value in envelope.items() if key != "signature"}
    try:
        public_key = Ed25519PublicKey.from_public_bytes(_b64url_decode(cloud_public_key_b64))
        public_key.verify(
            _b64url_decode(str(envelope.get("signature") or "")), canonical_json(unsigned)
        )
    except (InvalidSignature, ValueError, TypeError):
        return RemoteCommandDecision(False, command_id, "The cloud command signature is invalid.")
    nonce = str(envelope.get("nonce") or "")
    if not NONCE_PATTERN.fullmatch(nonce):
        return RemoteCommandDecision(
            False, command_id, "The remote command nonce is invalid.", True
        )
    claimed = claim_device_command_nonce(
        nonce,
        expected_device_id,
        command_id,
        expires_at.isoformat(),
        path=database_path,
    )
    if not claimed:
        return RemoteCommandDecision(
            False, command_id, "The remote command was already consumed.", True
        )
    return RemoteCommandDecision(True, command_id, signature_verified=True, nonce_claimed=True)


def cloud_channel_status() -> dict[str, Any]:
    endpoint = os.environ.get("AURIS_CLOUD_ENDPOINT", "").strip()
    signing_key = os.environ.get("AURIS_CLOUD_SIGNING_PUBLIC_KEY", "").strip()
    configured = bool(endpoint and signing_key)
    return {
        "configured": configured,
        "connected": False,
        "transport": "outbound_https_poll",
        "device_authentication": "ed25519_certificate_proof",
        "cloud_command_signing": "ed25519_pinned_key",
        "endpoint": "configured" if endpoint else "not_configured",
        "cloud_signing_key": "configured" if signing_key else "not_configured",
        "execution": "disabled_until_enrolment_and_visible_control",
        "mtls": "not_configured",
    }


def remote_request_proof(
    method: str,
    path: str,
    device_id: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> bytes:
    import hashlib

    body_hash = hashlib.sha256(body).hexdigest()
    return "\n".join(
        [method.upper(), path, str(UUID(device_id)), timestamp, nonce, body_hash]
    ).encode("utf-8")


def canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _json_object(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CloudChannelError("The cloud channel returned unreadable data.") from error
    if not isinstance(value, dict):
        raise CloudChannelError("The cloud channel returned an invalid response.")
    return value


def _response_error(response: dict[str, Any], status: int) -> str:
    detail = response.get("detail") or response.get("error")
    return str(detail or f"The cloud channel returned HTTP {status}.")


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
