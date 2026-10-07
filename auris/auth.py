from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import subprocess
import threading
import time
from dataclasses import dataclass
from http.cookies import SimpleCookie
from pathlib import Path


@dataclass(frozen=True)
class PortalAuth:
    access_token: str
    session_token: str
    csrf_token: str
    token_path: Path
    acl_hardened: bool


class BootstrapCodeStore:
    def __init__(self, *, ttl_seconds: float = 30) -> None:
        self.ttl_seconds = max(1, min(float(ttl_seconds), 120))
        self._codes: dict[str, float] = {}
        self._lock = threading.Lock()

    def issue(self) -> dict[str, object]:
        code = secrets.token_urlsafe(32)
        with self._lock:
            self._purge_expired()
            self._codes[code] = time.monotonic() + self.ttl_seconds
        return {"code": code, "expires_in_seconds": int(self.ttl_seconds)}

    def consume(self, candidate: str) -> bool:
        if not candidate:
            return False
        with self._lock:
            self._purge_expired()
            expires_at = self._codes.pop(candidate, None)
        return expires_at is not None and expires_at > time.monotonic()

    def _purge_expired(self) -> None:
        current = time.monotonic()
        expired = [code for code, expires_at in self._codes.items() if expires_at <= current]
        for code in expired:
            self._codes.pop(code, None)


def initialize_portal_auth(token_path: Path) -> PortalAuth:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    access_token = ""
    if token_path.exists():
        access_token = token_path.read_text(encoding="ascii", errors="ignore").strip()
    if len(access_token) < 40:
        access_token = secrets.token_urlsafe(48)
        token_path.write_text(access_token, encoding="ascii")
    try:
        os.chmod(token_path, 0o600)
    except OSError:
        pass
    acl_hardened = _harden_windows_acl(token_path)
    return PortalAuth(
        access_token=access_token,
        session_token=_derive(access_token, "auris-local-session"),
        csrf_token=_derive(access_token, "auris-csrf"),
        token_path=token_path,
        acl_hardened=acl_hardened,
    )


def access_token_valid(candidate: str, auth: PortalAuth) -> bool:
    return bool(candidate) and hmac.compare_digest(candidate, auth.access_token)


def session_cookie_valid(cookie_header: str, auth: PortalAuth) -> bool:
    cookie = SimpleCookie()
    try:
        cookie.load(cookie_header or "")
    except Exception:
        return False
    value = cookie.get("auris_session")
    return value is not None and hmac.compare_digest(value.value, auth.session_token)


def csrf_token_valid(candidate: str, auth: PortalAuth) -> bool:
    return bool(candidate) and hmac.compare_digest(candidate, auth.csrf_token)


def session_cookie_header(auth: PortalAuth) -> str:
    return (
        f"auris_session={auth.session_token}; Path=/; HttpOnly; SameSite=Strict; "
        "Max-Age=28800"
    )


def harden_private_file(path: Path) -> bool:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return _harden_windows_acl(path)


def harden_private_directory(path: Path) -> bool:
    if not path.is_dir() or path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        return False
    try:
        os.chmod(path, 0o700)
    except OSError:
        return False
    return _harden_windows_acl(path, inherit_children=True)


def _derive(secret: str, purpose: str) -> str:
    return hmac.new(secret.encode("ascii"), purpose.encode("ascii"), hashlib.sha256).hexdigest()


def _harden_windows_acl(path: Path, *, inherit_children: bool = False) -> bool:
    if os.name != "nt":
        return True
    principal = _windows_current_principal()
    if not principal:
        return False
    try:
        result = subprocess.run(
            [
                "icacls.exe",
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"{principal}:{'(OI)(CI)' if inherit_children else ''}(F)",
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _windows_current_principal() -> str:
    try:
        result = subprocess.run(
            ["whoami.exe"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""
