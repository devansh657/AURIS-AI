from __future__ import annotations

import json
import re
import threading
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

from auris.local_ipc import LocalIpcClient, LocalIpcUnavailable


ROOT = Path(__file__).resolve().parents[1]
TOKEN_PATH = ROOT / "data" / "portal.token"
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{40,128}")


class AurisClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AurisLocalClient:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8765",
        token_path: Path = TOKEN_PATH,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("AURIS desktop clients may connect only to the local loopback portal.")
        self.base_url = base_url.rstrip("/")
        self.token_path = token_path
        self._session_cookie = ""
        self._csrf_token = ""
        self._auth_lock = threading.Lock()
        self._ipc = (
            LocalIpcClient(token_path)
            if parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            and parsed.port in {None, 8765}
            else None
        )

    def status(self) -> dict[str, Any]:
        return self._request("/api/status", timeout=8)["status"]

    def command(
        self,
        text: str,
        *,
        private: bool = False,
        conversation_id: str = "auris-desktop-overlay",
        voice_turn_id: str | None = None,
        allow_failure: bool = False,
    ) -> dict[str, Any]:
        command = text.strip()
        if not command:
            raise AurisClientError("A command is required.")
        return self._request(
            "/api/command",
            method="POST",
            payload={
                "command": command[:4000],
                "project_id": None,
                "mode": "private" if private else "command",
                "private": private,
                "conversation_id": conversation_id,
                "voice_turn_id": voice_turn_id,
            },
            timeout=240,
            allow_failure=allow_failure,
        )

    def listen(self, *, timeout_seconds: int = 9, private: bool = False) -> dict[str, Any]:
        return self._request(
            "/api/voice/listen",
            method="POST",
            payload={"timeout_seconds": max(2, min(int(timeout_seconds), 20)), "private": private},
            timeout=max(45, timeout_seconds + 40),
            allow_failure=True,
        )["voice"]

    def listen_for_wake_word(self, *, timeout_seconds: int = 5) -> dict[str, Any]:
        return self._request(
            "/api/voice/wake",
            method="POST",
            payload={"timeout_seconds": max(5, min(int(timeout_seconds), 30))},
            timeout=max(45, timeout_seconds + 40),
            allow_failure=True,
        )["voice"]

    def listen_for_interrupt(self, *, timeout_seconds: int = 2) -> dict[str, Any]:
        return self._request(
            "/api/voice/interrupt",
            method="POST",
            payload={"timeout_seconds": max(2, min(int(timeout_seconds), 10))},
            timeout=max(45, timeout_seconds + 40),
            allow_failure=True,
        )["voice"]

    def speak(self, text: str, *, voice_turn_id: str | None = None) -> dict[str, Any]:
        spoken = " ".join(text.split())[:900]
        if not spoken:
            return {"ok": False, "error": "Speech text is empty."}
        return self._request(
            "/api/voice/speak",
            method="POST",
            payload={"text": spoken, "rate": 0, "voice_turn_id": voice_turn_id},
            timeout=90,
        )["voice"]

    def stop_speaking(self) -> dict[str, Any]:
        return self._request("/api/voice/stop", method="POST", payload={})["voice"]

    def set_background_voice(self, enabled: bool) -> dict[str, Any]:
        return self._request(
            "/api/voice/background",
            method="POST",
            payload={"enabled": bool(enabled)},
        )["voice"]

    def stop_automation(self, reason: str) -> dict[str, Any]:
        return self._request(
            "/api/control/stop",
            method="POST",
            payload={"reason": reason[:300]},
        )["control"]

    def resume_automation(self, reason: str) -> dict[str, Any]:
        return self._request(
            "/api/control/resume",
            method="POST",
            payload={"reason": reason[:300]},
        )["control"]

    def decide_approval(self, approval_id: str, *, approve: bool) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9a-f-]{36}", approval_id, re.IGNORECASE):
            raise AurisClientError("The approval identifier is invalid.")
        action = "approve" if approve else "reject"
        return self._request(
            f"/api/approvals/{approval_id}/{action}",
            method="POST",
            payload={"scope": "once"},
            timeout=60,
        )

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        timeout: int = 15,
        retry_auth: bool = True,
        allow_failure: bool = False,
    ) -> dict[str, Any]:
        ipc_operation = _ipc_operation(path, method)
        if self._ipc is not None and ipc_operation:
            ipc_payload = dict(payload or {})
            if ipc_operation == "approval.decide":
                parts = path.strip("/").split("/")
                ipc_payload.update(
                    {
                        "approval_id": parts[2],
                        "decision": "approved" if parts[3] == "approve" else "rejected",
                    }
                )
            try:
                response = self._ipc.request(ipc_operation, ipc_payload)
            except LocalIpcUnavailable:
                pass
            else:
                if response.get("ok") is False and not allow_failure:
                    raise AurisClientError(str(response.get("error") or "The AURIS request failed."))
                return response
        self._ensure_authenticated()
        headers = {
            "Accept": "application/json",
            "Cookie": self._session_cookie,
        }
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if method != "GET":
            headers["X-AURIS-CSRF"] = self._csrf_token
        request = Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                return _decode_json(response.read(), allow_failure=allow_failure)
        except HTTPError as error:
            if allow_failure and error.code in {408, 422, 423}:
                return _decode_json(error.read(), allow_failure=True)
            if error.code in {401, 403} and retry_auth:
                self._authenticate(force=True)
                return self._request(
                    path,
                    method=method,
                    payload=payload,
                    timeout=timeout,
                    retry_auth=False,
                    allow_failure=allow_failure,
                )
            details = _error_message(error.read(), fallback=f"AURIS returned HTTP {error.code}.")
            raise AurisClientError(details, status_code=error.code) from error
        except (URLError, TimeoutError, OSError) as error:
            raise AurisClientError("The local AURIS service is unavailable or did not respond in time.") from error

    def _ensure_authenticated(self) -> None:
        if not self._session_cookie or not self._csrf_token:
            self._authenticate()

    def _authenticate(self, *, force: bool = False) -> None:
        with self._auth_lock:
            if not force and self._session_cookie and self._csrf_token:
                return
            try:
                token = self.token_path.read_text(encoding="ascii").strip()
            except OSError as error:
                raise AurisClientError("The local AURIS portal token is unavailable.") from error
            if not TOKEN_PATTERN.fullmatch(token):
                raise AurisClientError("The local AURIS portal token is invalid.")

            jar = CookieJar()
            opener = build_opener(HTTPCookieProcessor(jar))
            try:
                with opener.open(f"{self.base_url}/?access_token={quote(token)}", timeout=8):
                    pass
                with opener.open(f"{self.base_url}/api/session", timeout=8) as response:
                    session = _decode_json(response.read())["session"]
            except (HTTPError, URLError, TimeoutError, OSError, KeyError) as error:
                raise AurisClientError("The local AURIS session could not be established.") from error

            cookie = next((item for item in jar if item.name == "auris_session"), None)
            csrf = str(session.get("csrf_token", ""))
            if cookie is None or not csrf:
                raise AurisClientError("The local AURIS session response was incomplete.")
            self._session_cookie = f"auris_session={cookie.value}"
            self._csrf_token = csrf


def _decode_json(raw: bytes, *, allow_failure: bool = False) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AurisClientError("AURIS returned an unreadable response.") from error
    if not isinstance(payload, dict):
        raise AurisClientError("AURIS returned an unexpected response.")
    if payload.get("ok") is False and not allow_failure:
        raise AurisClientError(str(payload.get("error") or "The AURIS request failed."))
    return payload


def _error_message(raw: bytes, *, fallback: str) -> str:
    try:
        payload = json.loads(raw.decode("utf-8"))
        message = payload.get("error") if isinstance(payload, dict) else None
        if not message and isinstance(payload, dict) and isinstance(payload.get("voice"), dict):
            message = payload["voice"].get("error")
        return str(message or fallback)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return fallback


def _ipc_operation(path: str, method: str) -> str:
    routes = {
        ("GET", "/api/status"): "status",
        ("POST", "/api/command"): "command",
        ("POST", "/api/voice/listen"): "voice.listen",
        ("POST", "/api/voice/wake"): "voice.wake",
        ("POST", "/api/voice/interrupt"): "voice.interrupt",
        ("POST", "/api/voice/speak"): "voice.speak",
        ("POST", "/api/voice/stop"): "voice.stop",
        ("POST", "/api/voice/background"): "voice.background",
        ("POST", "/api/control/stop"): "control.stop",
        ("POST", "/api/control/resume"): "control.resume",
    }
    if method == "POST" and re.fullmatch(r"/api/approvals/[0-9a-f-]{36}/(?:approve|reject)", path, re.IGNORECASE):
        return "approval.decide"
    return routes.get((method, path), "")
