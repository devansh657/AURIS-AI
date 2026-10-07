from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


class CloudStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS enrolments (
                    code_hash TEXT PRIMARY KEY,
                    permissions_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS cloud_devices (
                    device_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    certificate_pem TEXT NOT NULL,
                    certificate_fingerprint TEXT NOT NULL UNIQUE,
                    certificate_expires_at TEXT NOT NULL,
                    permissions_json TEXT NOT NULL,
                    trust_state TEXT NOT NULL,
                    registered_at TEXT NOT NULL,
                    last_seen_at TEXT,
                    revoked_at TEXT
                );
                CREATE TABLE IF NOT EXISTS cloud_commands (
                    command_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL REFERENCES cloud_devices(device_id),
                    envelope_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    leased_at TEXT,
                    lease_expires_at TEXT,
                    acknowledged_at TEXT,
                    acknowledgement_json TEXT
                );
                CREATE TABLE IF NOT EXISTS device_auth_nonces (
                    nonce TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL REFERENCES cloud_devices(device_id),
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cloud_audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    device_id TEXT,
                    command_id TEXT,
                    metadata_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS phone_call_summaries (
                    call_id TEXT PRIMARY KEY,
                    caller_masked TEXT NOT NULL,
                    state TEXT NOT NULL,
                    importance TEXT NOT NULL,
                    transfer_requested INTEGER NOT NULL,
                    transfer_reason TEXT NOT NULL,
                    disclosure_delivered INTEGER NOT NULL,
                    audio_recorded INTEGER NOT NULL,
                    raw_transcript_persisted INTEGER NOT NULL,
                    summary_json TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_cloud_commands_queue
                    ON cloud_commands(device_id, state, created_at);
                CREATE INDEX IF NOT EXISTS idx_device_auth_nonces_expiry
                    ON device_auth_nonces(expires_at);
                CREATE INDEX IF NOT EXISTS idx_phone_calls_finished
                    ON phone_call_summaries(finished_at DESC);
                """
            )

    def create_enrolment(self, permissions: list[str], ttl_seconds: int) -> dict[str, Any]:
        code = secrets.token_urlsafe(48)
        now = _now()
        expires_at = _iso(now + timedelta(seconds=ttl_seconds))
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO enrolments VALUES (?, ?, ?, ?, NULL)",
                (_hash_code(code), json.dumps(permissions), _iso(now), expires_at),
            )
        self.audit("enrolment.created", metadata={"expires_at": expires_at})
        return {"code": code, "expires_at": expires_at, "permissions": permissions}

    def consume_enrolment(self, code: str) -> list[str] | None:
        now = _iso(_now())
        code_hash = _hash_code(code)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM enrolments WHERE code_hash = ?", (code_hash,)
            ).fetchone()
            if row is None or row["consumed_at"] or row["expires_at"] <= now:
                return None
            connection.execute(
                "UPDATE enrolments SET consumed_at = ? WHERE code_hash = ?",
                (now, code_hash),
            )
            return list(json.loads(row["permissions_json"]))

    def register_device(
        self,
        *,
        device_id: str,
        display_name: str,
        platform: str,
        certificate_pem: str,
        certificate_fingerprint: str,
        certificate_expires_at: str,
        permissions: list[str],
    ) -> dict[str, Any]:
        now = _iso(_now())
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO cloud_devices(
                        device_id, display_name, platform, certificate_pem,
                        certificate_fingerprint, certificate_expires_at,
                        permissions_json, trust_state, registered_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pinned_certificate', ?)
                    """,
                    (
                        device_id,
                        display_name,
                        platform,
                        certificate_pem,
                        certificate_fingerprint,
                        certificate_expires_at,
                        json.dumps(permissions),
                        now,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError("The device identity or certificate is already registered.") from error
        self.audit("device.registered", device_id=device_id)
        return self.public_device(self.get_device(device_id))

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM cloud_devices WHERE device_id = ?", (device_id,)
            ).fetchone()
        return _device(row) if row else None

    def list_devices(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM cloud_devices ORDER BY registered_at DESC"
            ).fetchall()
        return [self.public_device(_device(row)) for row in rows]

    def public_device(self, device: dict[str, Any] | None) -> dict[str, Any]:
        if device is None:
            return {}
        return {key: value for key, value in device.items() if key != "certificate_pem"}

    def revoke_device(self, device_id: str) -> dict[str, Any] | None:
        now = _iso(_now())
        with self._connect() as connection:
            changed = connection.execute(
                """
                UPDATE cloud_devices
                SET trust_state = 'revoked', revoked_at = ?
                WHERE device_id = ? AND revoked_at IS NULL
                """,
                (now, device_id),
            ).rowcount
        if not changed:
            return None
        self.audit("device.revoked", device_id=device_id)
        return self.public_device(self.get_device(device_id))

    def claim_auth_nonce(self, device_id: str, nonce: str, expires_at: str) -> bool:
        now = _iso(_now())
        try:
            with self._connect() as connection:
                connection.execute("DELETE FROM device_auth_nonces WHERE expires_at <= ?", (now,))
                connection.execute(
                    "INSERT INTO device_auth_nonces VALUES (?, ?, ?, ?)",
                    (nonce, device_id, expires_at, now),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def touch_device(self, device_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE cloud_devices SET last_seen_at = ? WHERE device_id = ?",
                (_iso(_now()), device_id),
            )

    def enqueue_command(self, device_id: str, envelope: dict[str, Any]) -> dict[str, Any]:
        command_id = str(envelope["command_id"])
        now = _iso(_now())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cloud_commands(
                    command_id, device_id, envelope_json, state, created_at
                ) VALUES (?, ?, ?, 'queued', ?)
                """,
                (command_id, device_id, json.dumps(envelope, ensure_ascii=True), now),
            )
        self.audit("command.queued", device_id=device_id, command_id=command_id)
        return self.get_command(command_id) or {}

    def lease_next_command(self, device_id: str, lease_seconds: int) -> dict[str, Any] | None:
        now_value = _now()
        now = _iso(now_value)
        lease_expires = _iso(now_value + timedelta(seconds=lease_seconds))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE cloud_commands
                SET state = 'queued', leased_at = NULL, lease_expires_at = NULL
                WHERE device_id = ? AND state = 'leased' AND lease_expires_at <= ?
                """,
                (device_id, now),
            )
            row = connection.execute(
                """
                SELECT command_id FROM cloud_commands
                WHERE device_id = ? AND state = 'queued'
                ORDER BY created_at ASC LIMIT 1
                """,
                (device_id,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                UPDATE cloud_commands
                SET state = 'leased', leased_at = ?, lease_expires_at = ?
                WHERE command_id = ? AND state = 'queued'
                """,
                (now, lease_expires, row["command_id"]),
            )
            command = connection.execute(
                "SELECT * FROM cloud_commands WHERE command_id = ?", (row["command_id"],)
            ).fetchone()
        result = _command(command)
        self.audit("command.leased", device_id=device_id, command_id=result["command_id"])
        return result

    def acknowledge_command(
        self,
        device_id: str,
        command_id: str,
        acknowledgement: dict[str, Any],
    ) -> dict[str, Any] | None:
        final_state = str(acknowledgement["state"])
        with self._connect() as connection:
            changed = connection.execute(
                """
                UPDATE cloud_commands
                SET state = ?, acknowledged_at = ?, acknowledgement_json = ?
                WHERE command_id = ? AND device_id = ? AND state = 'leased'
                """,
                (
                    final_state,
                    _iso(_now()),
                    json.dumps(acknowledgement, ensure_ascii=True),
                    command_id,
                    device_id,
                ),
            ).rowcount
        if not changed:
            return None
        self.audit(
            f"command.{final_state}", device_id=device_id, command_id=command_id
        )
        return self.get_command(command_id)

    def get_command(self, command_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM cloud_commands WHERE command_id = ?", (command_id,)
            ).fetchone()
        return _command(row) if row else None

    def list_commands(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM cloud_commands ORDER BY created_at DESC LIMIT ?",
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [_command(row) for row in rows]

    def save_phone_call_summary(self, summary: dict[str, Any]) -> dict[str, Any]:
        durable = {
            "call_id": str(summary["call_id"]),
            "caller": str(summary.get("caller") or "withheld"),
            "state": "transferred" if summary.get("transfer_requested") else "summarised",
            "importance": str(summary.get("importance") or "routine"),
            "transfer_requested": bool(summary.get("transfer_requested")),
            "transfer_reason": str(summary.get("transfer_reason") or "")[:120],
            "disclosure_delivered": bool(summary.get("disclosure_delivered")),
            "audio_recorded": False,
            "raw_transcript_persisted": False,
            "summary": str(summary.get("summary") or "")[:2_000],
            "caller_request": str(summary.get("caller_request") or "")[:1_000],
            "promised_actions": [],
            "urgency": str(summary.get("urgency") or "routine")[:40],
            "follow_up": str(summary.get("follow_up") or "")[:1_000],
            "turn_count": max(0, min(int(summary.get("turn_count") or 0), 40)),
            "started_at": str(summary.get("started_at") or _iso(_now())),
            "finished_at": str(summary.get("finished_at") or _iso(_now())),
        }
        payload = {
            key: durable[key]
            for key in ("summary", "caller_request", "promised_actions", "urgency", "follow_up", "turn_count")
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO phone_call_summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    durable["call_id"], durable["caller"], durable["state"], durable["importance"],
                    int(durable["transfer_requested"]), durable["transfer_reason"],
                    int(durable["disclosure_delivered"]), 0, 0,
                    json.dumps(payload, ensure_ascii=True), durable["started_at"], durable["finished_at"],
                ),
            )
        self.audit("telephony.call_summarised", metadata={"state": durable["state"], "importance": durable["importance"]})
        return durable

    def list_phone_call_summaries(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM phone_call_summaries ORDER BY finished_at DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        results = []
        for row in rows:
            data = dict(row)
            payload = json.loads(data.pop("summary_json"))
            data["caller"] = data.pop("caller_masked")
            for key in ("transfer_requested", "disclosure_delivered", "audio_recorded", "raw_transcript_persisted"):
                data[key] = bool(data[key])
            results.append({**data, **payload})
        return results

    def audit(
        self,
        event_type: str,
        *,
        device_id: str | None = None,
        command_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cloud_audit_events(
                    event_type, device_id, command_id, metadata_json, occurred_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    device_id,
                    command_id,
                    json.dumps(metadata or {}, ensure_ascii=True),
                    _iso(_now()),
                ),
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()


def _device(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["permissions"] = json.loads(data.pop("permissions_json"))
    data["revoked"] = bool(data.get("revoked_at"))
    return data


def _command(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["envelope"] = json.loads(data.pop("envelope_json"))
    acknowledgement = data.pop("acknowledgement_json")
    data["acknowledgement"] = json.loads(acknowledgement) if acknowledgement else None
    return data


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()
