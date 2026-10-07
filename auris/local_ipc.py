from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from multiprocessing.connection import AuthenticationError, Client, Listener
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4


PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 256 * 1024


class LocalIpcUnavailable(RuntimeError):
    pass


def pipe_address(access_token: str) -> str:
    suffix = hashlib.sha256(access_token.encode("ascii")).hexdigest()[:16]
    return rf"\\.\pipe\auris-one-{suffix}"


def derive_pipe_authkey(access_token: str) -> bytes:
    return hmac.new(
        access_token.encode("ascii"),
        b"auris-authenticated-local-ipc-v1",
        hashlib.sha256,
    ).digest()


class LocalIpcClient:
    def __init__(self, token_path: Path) -> None:
        self.token_path = token_path

    def request(self, operation: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if os.name != "nt":
            raise LocalIpcUnavailable("Windows named pipes are unavailable.")
        token = self._token()
        request = {
            "version": PROTOCOL_VERSION,
            "request_id": str(uuid4()),
            "operation": operation,
            "payload": payload or {},
        }
        encoded = _encode(request)
        if len(encoded) > MAX_MESSAGE_BYTES:
            raise ValueError("The local IPC request is too large.")
        connection = None
        try:
            connection = Client(
                pipe_address(token),
                family="AF_PIPE",
                authkey=derive_pipe_authkey(token),
            )
            connection.send_bytes(encoded)
            response = _decode(connection.recv_bytes(MAX_MESSAGE_BYTES))
        except (AuthenticationError, EOFError, OSError) as error:
            raise LocalIpcUnavailable("The authenticated AURIS named pipe is unavailable.") from error
        finally:
            if connection is not None:
                connection.close()
        if response.get("request_id") != request["request_id"]:
            raise LocalIpcUnavailable("The AURIS named-pipe response did not match the request.")
        body = response.get("body")
        if not isinstance(body, dict):
            raise LocalIpcUnavailable("The AURIS named-pipe response was invalid.")
        return body

    def _token(self) -> str:
        try:
            token = self.token_path.read_text(encoding="ascii").strip()
        except OSError as error:
            raise LocalIpcUnavailable("The local AURIS portal token is unavailable.") from error
        if len(token) < 40:
            raise LocalIpcUnavailable("The local AURIS portal token is invalid.")
        return token


class LocalIpcServer:
    def __init__(
        self,
        access_token: str,
        dispatcher: Callable[[str, dict[str, Any]], dict[str, Any]],
    ) -> None:
        if os.name != "nt":
            raise RuntimeError("AURIS named-pipe IPC requires Windows.")
        self.access_token = access_token
        self.dispatcher = dispatcher
        self.address = pipe_address(access_token)
        self.authkey = derive_pipe_authkey(access_token)
        self._listener: Listener | None = None
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._listener = Listener(self.address, family="AF_PIPE", authkey=self.authkey)
        self._stopping.clear()
        self._thread = threading.Thread(target=self._serve, name="auris-local-ipc", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        try:
            # Only wake a pending accept; the serving loop may have already exited.
            # An authenticated shutdown client would then wait forever for its challenge.
            wake = Client(self.address, family="AF_PIPE", authkey=None)
            wake.close()
        except (AuthenticationError, OSError):
            pass
        if self._thread:
            self._thread.join(timeout=3)
        if self._listener:
            self._listener.close()
        self._listener = None
        self._thread = None

    def _serve(self) -> None:
        while not self._stopping.is_set():
            try:
                if self._listener is None:
                    return
                connection = self._listener.accept()
            except (AuthenticationError, EOFError, OSError):
                if self._stopping.is_set():
                    return
                continue
            worker = threading.Thread(
                target=self._handle_connection,
                args=(connection,),
                name="auris-local-ipc-request",
                daemon=True,
            )
            worker.start()

    def _handle_connection(self, connection) -> None:
        request_id = ""
        try:
            request = _decode(connection.recv_bytes(MAX_MESSAGE_BYTES))
            request_id = str(request.get("request_id") or "")
            error = _validate_request(request)
            if error:
                body = {"ok": False, "error": error}
            else:
                body = self.dispatcher(request["operation"], request["payload"])
                if not isinstance(body, dict):
                    body = {"ok": False, "error": "The local operation returned an invalid response."}
            connection.send_bytes(_encode({"request_id": request_id, "body": body}))
        except (EOFError, OSError, ValueError, json.JSONDecodeError):
            try:
                connection.send_bytes(
                    _encode(
                        {
                            "request_id": request_id,
                            "body": {"ok": False, "error": "The local IPC request was invalid."},
                        }
                    )
                )
            except OSError:
                pass
        finally:
            connection.close()


def _validate_request(request: dict[str, Any]) -> str:
    if set(request) != {"version", "request_id", "operation", "payload"}:
        return "The local IPC request schema is invalid."
    if request.get("version") != PROTOCOL_VERSION:
        return "The local IPC protocol version is unsupported."
    try:
        UUID(str(request.get("request_id") or ""))
    except (TypeError, ValueError):
        return "The local IPC request identifier is invalid."
    operation = request.get("operation")
    if not isinstance(operation, str) or not operation or len(operation) > 80:
        return "The local IPC operation is invalid."
    if not isinstance(request.get("payload"), dict):
        return "The local IPC payload is invalid."
    return ""


def _encode(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def _decode(value: bytes) -> dict[str, Any]:
    decoded = json.loads(value.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("A JSON object is required.")
    return decoded
