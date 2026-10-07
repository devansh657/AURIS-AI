from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import NAMESPACE_URL, uuid4, uuid5


ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = ROOT / "data" / "auris.db"

INITIAL_PROJECTS = (
    ("auris-one", "AURIS One", "Build the supervised personal AI operating system."),
    ("infraguard-ai", "InfraGuard AI", "Security and anomaly-detection work."),
    ("smart-parking", "Smart Parking System", "Smart parking research and implementation."),
    ("msc-ai", "MSc Artificial Intelligence", "Coursework and academic planning."),
    ("dissertation", "Dissertation", "Dissertation research, writing, and evaluation."),
    ("career", "Career Applications", "Roles, CVs, applications, and interview preparation."),
    ("portfolio", "Portfolio Website", "Portfolio content and engineering."),
    ("fitness", "Fitness and Personal Development", "Fitness planning and personal development."),
)


def initialize_database(path: Path = DATABASE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                objective TEXT NOT NULL,
                task_type TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                state TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                result_json TEXT,
                project_id TEXT,
                mode TEXT NOT NULL DEFAULT 'command',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS approvals (
                approval_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                proposed_action TEXT NOT NULL,
                target TEXT NOT NULL,
                data_summary TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                reversible INTEGER NOT NULL,
                status TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT 'once',
                created_at TEXT NOT NULL,
                decided_at TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id)
            );

            CREATE TABLE IF NOT EXISTS workflow_runs (
                task_id TEXT PRIMARY KEY,
                command_text TEXT NOT NULL,
                state TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 1,
                recovery_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS workflow_checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                title TEXT NOT NULL,
                agent TEXT NOT NULL,
                state TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                evidence_json TEXT NOT NULL DEFAULT '{}',
                error TEXT,
                started_at TEXT,
                completed_at TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(task_id, step_id),
                FOREIGN KEY(task_id) REFERENCES workflow_runs(task_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                machine_name TEXT NOT NULL,
                platform TEXT NOT NULL,
                trust_state TEXT NOT NULL,
                permissions_json TEXT NOT NULL,
                key_fingerprint TEXT NOT NULL,
                certificate_state TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                revoked_at TEXT
            );

            CREATE TABLE IF NOT EXISTS device_command_nonces (
                nonce TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                command_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                consumed_at TEXT NOT NULL,
                FOREIGN KEY(device_id) REFERENCES devices(device_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                project_id TEXT,
                sensitivity TEXT NOT NULL,
                confidence TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                verified_at TEXT NOT NULL,
                expires_at TEXT
            );

            CREATE TABLE IF NOT EXISTS memory_embeddings (
                memory_id TEXT PRIMARY KEY,
                model TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                vector_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(memory_id) REFERENCES memories(memory_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS memory_versions (
                version_id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                operation TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                reason TEXT NOT NULL,
                actor TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(memory_id, version_number),
                FOREIGN KEY(memory_id) REFERENCES memories(memory_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS memory_conflicts (
                conflict_id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                conflicting_memory_id TEXT NOT NULL,
                subject_key TEXT NOT NULL,
                status TEXT NOT NULL,
                rationale TEXT NOT NULL,
                resolution TEXT,
                chosen_memory_id TEXT,
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                UNIQUE(memory_id, conflicting_memory_id),
                FOREIGN KEY(memory_id) REFERENCES memories(memory_id) ON DELETE CASCADE,
                FOREIGN KEY(conflicting_memory_id) REFERENCES memories(memory_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                instructions TEXT NOT NULL DEFAULT '',
                root_path TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                project_id TEXT,
                mode TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id)
            );

            CREATE TABLE IF NOT EXISTS scheduled_events (
                event_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                due_at TEXT NOT NULL,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                project_id TEXT,
                created_at TEXT NOT NULL,
                delivered_at TEXT,
                cancelled_at TEXT
            );

            CREATE TABLE IF NOT EXISTS decision_cases (
                case_id TEXT PRIMARY KEY,
                objective TEXT NOT NULL,
                project_id TEXT,
                status TEXT NOT NULL,
                input_json TEXT NOT NULL,
                analysis_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS decision_outcomes (
                outcome_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                actual_success INTEGER NOT NULL,
                actual_summary TEXT NOT NULL,
                expected_summary TEXT NOT NULL DEFAULT '',
                difference_summary TEXT NOT NULL DEFAULT '',
                root_cause TEXT NOT NULL DEFAULT '',
                lesson TEXT NOT NULL DEFAULT '',
                confidence_update TEXT NOT NULL DEFAULT 'unchanged',
                observed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES decision_cases(case_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS proactive_watches (
                watch_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                metric TEXT NOT NULL,
                operator TEXT NOT NULL,
                threshold REAL NOT NULL,
                interval_seconds INTEGER NOT NULL,
                cooldown_seconds INTEGER NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                condition_active INTEGER NOT NULL DEFAULT 0,
                last_value REAL,
                last_evaluated_at TEXT,
                last_notified_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(project_id)
            );

            CREATE TABLE IF NOT EXISTS proactive_alerts (
                alert_id TEXT PRIMARY KEY,
                watch_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                metric TEXT NOT NULL,
                observed_value REAL NOT NULL,
                threshold REAL NOT NULL,
                operator TEXT NOT NULL,
                classification TEXT NOT NULL,
                evidence_json TEXT NOT NULL DEFAULT '[]',
                delivered_at TEXT NOT NULL,
                FOREIGN KEY(watch_id) REFERENCES proactive_watches(watch_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS application_states (
                state_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL UNIQUE,
                project_id TEXT,
                application TEXT NOT NULL,
                workflow_type TEXT NOT NULL,
                status TEXT NOT NULL,
                completed_json TEXT NOT NULL DEFAULT '[]',
                remaining_json TEXT NOT NULL DEFAULT '[]',
                checkpoint_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_scheduled_events_due
            ON scheduled_events(status, due_at);

            CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
            ON messages(conversation_id, created_at);

            CREATE INDEX IF NOT EXISTS idx_workflow_runs_state
            ON workflow_runs(state, updated_at);

            CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_task
            ON workflow_checkpoints(task_id, ordinal);

            CREATE INDEX IF NOT EXISTS idx_device_command_nonces_expiry
            ON device_command_nonces(expires_at);

            CREATE INDEX IF NOT EXISTS idx_memory_versions_memory
            ON memory_versions(memory_id, version_number DESC);

            CREATE INDEX IF NOT EXISTS idx_memory_conflicts_status
            ON memory_conflicts(status, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_decision_cases_project
            ON decision_cases(project_id, updated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_decision_outcomes_case
            ON decision_outcomes(case_id, observed_at DESC);

            CREATE INDEX IF NOT EXISTS idx_proactive_watches_enabled
            ON proactive_watches(enabled, last_evaluated_at);

            CREATE INDEX IF NOT EXISTS idx_proactive_alerts_watch
            ON proactive_alerts(watch_id, delivered_at DESC);

            CREATE INDEX IF NOT EXISTS idx_application_states_project
            ON application_states(project_id, status, updated_at DESC);
            """
        )
        project_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(projects)").fetchall()
        }
        if "root_path" not in project_columns:
            connection.execute("ALTER TABLE projects ADD COLUMN root_path TEXT")
        memory_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(memories)").fetchall()
        }
        memory_migrations = {
            "structured_data_json": "TEXT NOT NULL DEFAULT '{}'",
            "source_type": "TEXT NOT NULL DEFAULT 'user_confirmed'",
            "source_reference": "TEXT",
            "confidence_score": "REAL NOT NULL DEFAULT 1.0",
            "valid_from": "TEXT",
            "status": "TEXT NOT NULL DEFAULT 'active'",
            "supersedes": "TEXT",
            "subject_key": "TEXT",
            "environment": "TEXT",
            "updated_at": "TEXT",
            "conflict_state": "TEXT NOT NULL DEFAULT 'clear'",
        }
        for column, definition in memory_migrations.items():
            if column not in memory_columns:
                connection.execute(f"ALTER TABLE memories ADD COLUMN {column} {definition}")
        outcome_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(decision_outcomes)").fetchall()
        }
        outcome_migrations = {
            "expected_summary": "TEXT NOT NULL DEFAULT ''",
            "difference_summary": "TEXT NOT NULL DEFAULT ''",
            "root_cause": "TEXT NOT NULL DEFAULT ''",
            "lesson": "TEXT NOT NULL DEFAULT ''",
            "confidence_update": "TEXT NOT NULL DEFAULT 'unchanged'",
        }
        for column, definition in outcome_migrations.items():
            if column not in outcome_columns:
                connection.execute(
                    f"ALTER TABLE decision_outcomes ADD COLUMN {column} {definition}"
                )
        now = _now()
        connection.execute(
            "UPDATE memories SET valid_from = COALESCE(valid_from, created_at), "
            "updated_at = COALESCE(updated_at, verified_at)"
        )
        connection.execute("UPDATE memories SET category = 'project' WHERE category = 'saved'")
        existing_memories = connection.execute(
            "SELECT m.* FROM memories m "
            "LEFT JOIN memory_versions v ON v.memory_id = m.memory_id "
            "WHERE v.memory_id IS NULL"
        ).fetchall()
        for row in existing_memories:
            _append_memory_version(
                connection,
                _memory_from_row(row),
                "migrated",
                "Initial temporal snapshot created during schema migration.",
                "system_migration",
            )
        connection.executemany(
            """
            INSERT OR IGNORE INTO projects(
                project_id, name, description, instructions, root_path, created_at
            )
            VALUES (?, ?, ?, '', NULL, ?)
            """,
            [(project_id, name, description, now) for project_id, name, description in INITIAL_PROJECTS],
        )
        connection.execute(
            "UPDATE projects SET root_path = ? WHERE project_id = 'auris-one'",
            (str(ROOT),),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO settings(key, value_json, updated_at)
            VALUES ('control', ?, ?)
            """,
            (json.dumps({"stopped": False, "reason": "", "changed_by": "system"}), now),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO settings(key, value_json, updated_at)
            VALUES ('background_voice', ?, ?)
            """,
            (json.dumps({"enabled": True}), now),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO settings(key, value_json, updated_at)
            VALUES ('memory_categories', ?, ?)
            """,
            (
                json.dumps(
                    {
                        "profile": True,
                        "working": True,
                        "episodic": True,
                        "project": True,
                        "procedural": True,
                        "relationship": True,
                        "decision": True,
                        "research": True,
                        "device": True,
                        "preference": True,
                    },
                    ensure_ascii=True,
                ),
                now,
            ),
        )
    return path


def save_task(
    plan: dict[str, Any],
    *,
    result: dict[str, Any] | None = None,
    project_id: str | None = None,
    mode: str = "command",
    path: Path = DATABASE_PATH,
) -> None:
    initialize_database(path)
    now = _now()
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO tasks(
                task_id, objective, task_type, risk_level, state, plan_json,
                result_json, project_id, mode, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                state=excluded.state,
                plan_json=excluded.plan_json,
                result_json=excluded.result_json,
                project_id=excluded.project_id,
                mode=excluded.mode,
                updated_at=excluded.updated_at
            """,
            (
                plan["task_id"],
                plan["objective"],
                plan["task_type"],
                plan["risk_level"],
                plan["state"],
                json.dumps(plan, ensure_ascii=True),
                json.dumps(result, ensure_ascii=True) if result is not None else None,
                project_id,
                mode,
                now,
                now,
            ),
        )


def update_task_state(
    task_id: str,
    state: str,
    result: dict[str, Any] | None = None,
    path: Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    task = get_task(task_id, path=path)
    if task is None:
        return None
    plan = task["plan"]
    plan["state"] = state
    save_task(
        plan,
        result=result if result is not None else task.get("result"),
        project_id=task.get("project_id"),
        mode=task.get("mode", "command"),
        path=path,
    )
    return get_task(task_id, path=path)


def list_tasks(limit: int = 20, path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT * FROM tasks ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_task_from_row(row) for row in rows]


def get_task(task_id: str, path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    return _task_from_row(row) if row else None


def save_application_state(
    state: dict[str, Any], *, path: Path = DATABASE_PATH
) -> dict[str, Any]:
    initialize_database(path)
    now = _now()
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO application_states(
                state_id, task_id, project_id, application, workflow_type, status,
                completed_json, remaining_json, checkpoint_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                project_id=excluded.project_id,
                application=excluded.application,
                workflow_type=excluded.workflow_type,
                status=excluded.status,
                completed_json=excluded.completed_json,
                remaining_json=excluded.remaining_json,
                checkpoint_json=excluded.checkpoint_json,
                updated_at=excluded.updated_at
            """,
            (
                state["state_id"], state["task_id"], state.get("project_id"),
                state["application"], state["workflow_type"], state["status"],
                json.dumps(state.get("completed", []), ensure_ascii=True),
                json.dumps(state.get("remaining", []), ensure_ascii=True),
                json.dumps(state.get("checkpoint", {}), ensure_ascii=True),
                state.get("created_at") or now, now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM application_states WHERE task_id = ?", (state["task_id"],)
        ).fetchone()
    return _application_state_from_row(row)


def get_application_state(state_id: str, path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM application_states WHERE state_id = ?", (state_id,)
        ).fetchone()
    return _application_state_from_row(row) if row else None


def list_application_states(
    *, project_id: str | None = None, statuses: tuple[str, ...] = (),
    limit: int = 20, path: Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    initialize_database(path)
    clauses: list[str] = []
    parameters: list[Any] = []
    if project_id is not None:
        clauses.append("project_id = ?")
        parameters.append(project_id)
    if statuses:
        clauses.append(f"status IN ({','.join('?' for _ in statuses)})")
        parameters.extend(statuses)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    parameters.append(max(1, min(int(limit), 100)))
    with _connect(path) as connection:
        rows = connection.execute(
            f"SELECT * FROM application_states {where} ORDER BY updated_at DESC LIMIT ?",
            parameters,
        ).fetchall()
    return [_application_state_from_row(row) for row in rows]


def set_application_state_status(
    state_id: str, status: str, *, path: Path = DATABASE_PATH
) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        cursor = connection.execute(
            "UPDATE application_states SET status = ?, updated_at = ? WHERE state_id = ?",
            (status, _now(), state_id),
        )
    return get_application_state(state_id, path=path) if cursor.rowcount else None


def delete_application_state(state_id: str, *, path: Path = DATABASE_PATH) -> bool:
    initialize_database(path)
    with _connect(path) as connection:
        cursor = connection.execute(
            "DELETE FROM application_states WHERE state_id = ?", (state_id,)
        )
    return bool(cursor.rowcount)


def create_workflow_run(
    plan: dict[str, Any],
    command: str,
    *,
    max_attempts: int,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    initialize_database(path)
    now = _now()
    bounded_attempts = max(1, min(int(max_attempts), 3))
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO workflow_runs(
                task_id, command_text, state, attempts, max_attempts,
                recovery_count, created_at, updated_at
            ) VALUES (?, ?, 'created', 0, ?, 0, ?, ?)
            """,
            (plan["task_id"], command[:4000], bounded_attempts, now, now),
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO workflow_checkpoints(
                checkpoint_id, task_id, step_id, ordinal, title, agent,
                state, attempts, evidence_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', 0, '{}', ?)
            """,
            [
                (
                    str(uuid4()),
                    plan["task_id"],
                    step["step_id"],
                    ordinal,
                    step["title"],
                    step["agent"],
                    now,
                )
                for ordinal, step in enumerate(plan.get("steps", []), start=1)
            ],
        )
    return get_workflow_run(plan["task_id"], path=path) or {}


def get_workflow_run(task_id: str, path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        run = connection.execute(
            "SELECT * FROM workflow_runs WHERE task_id = ?", (task_id,)
        ).fetchone()
        if run is None:
            return None
        checkpoints = connection.execute(
            """
            SELECT * FROM workflow_checkpoints
            WHERE task_id = ? ORDER BY ordinal ASC
            """,
            (task_id,),
        ).fetchall()
    return {
        **dict(run),
        "checkpoints": [_workflow_checkpoint_from_row(row) for row in checkpoints],
    }


def list_workflow_runs(
    *,
    states: tuple[str, ...] | None = None,
    limit: int = 100,
    path: Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    initialize_database(path)
    bounded_limit = max(1, min(int(limit), 200))
    query = "SELECT task_id FROM workflow_runs"
    parameters: list[Any] = []
    if states:
        placeholders = ",".join("?" for _ in states)
        query += f" WHERE state IN ({placeholders})"
        parameters.extend(states)
    query += " ORDER BY updated_at ASC LIMIT ?"
    parameters.append(bounded_limit)
    with _connect(path) as connection:
        rows = connection.execute(query, tuple(parameters)).fetchall()
    return [
        workflow
        for row in rows
        if (workflow := get_workflow_run(row["task_id"], path=path)) is not None
    ]


def update_workflow_state(
    task_id: str,
    state: str,
    *,
    last_error: str | None = None,
    increment_recovery: bool = False,
    path: Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    initialize_database(path)
    now = _now()
    with _connect(path) as connection:
        cursor = connection.execute(
            """
            UPDATE workflow_runs
            SET state = ?, last_error = ?,
                recovery_count = recovery_count + ?, updated_at = ?
            WHERE task_id = ?
            """,
            (state, last_error[:1000] if last_error else None, int(increment_recovery), now, task_id),
        )
    return get_workflow_run(task_id, path=path) if cursor.rowcount else None


def begin_workflow_attempt(task_id: str, path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    initialize_database(path)
    now = _now()
    with _connect(path) as connection:
        cursor = connection.execute(
            """
            UPDATE workflow_runs
            SET attempts = attempts + 1, state = 'running', last_error = NULL, updated_at = ?
            WHERE task_id = ? AND attempts < max_attempts
            """,
            (now, task_id),
        )
    return get_workflow_run(task_id, path=path) if cursor.rowcount else None


def update_workflow_checkpoint(
    task_id: str,
    step_id: str,
    state: str,
    *,
    evidence: dict[str, Any] | None = None,
    error: str | None = None,
    increment_attempt: bool = False,
    path: Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    initialize_database(path)
    now = _now()
    terminal = state in {"completed", "failed", "blocked", "cancelled", "interrupted"}
    with _connect(path) as connection:
        cursor = connection.execute(
            """
            UPDATE workflow_checkpoints
            SET state = ?, attempts = attempts + ?, evidence_json = ?, error = ?,
                started_at = CASE
                    WHEN ? = 'running' AND started_at IS NULL THEN ?
                    ELSE started_at
                END,
                completed_at = CASE WHEN ? THEN ? ELSE completed_at END,
                updated_at = ?
            WHERE task_id = ? AND step_id = ?
            """,
            (
                state,
                int(increment_attempt),
                json.dumps(evidence or {}, ensure_ascii=True),
                error[:1000] if error else None,
                state,
                now,
                int(terminal),
                now,
                now,
                task_id,
                step_id,
            ),
        )
    if not cursor.rowcount:
        return None
    workflow = get_workflow_run(task_id, path=path)
    if workflow is None:
        return None
    return next(
        (checkpoint for checkpoint in workflow["checkpoints"] if checkpoint["step_id"] == step_id),
        None,
    )


def upsert_device(
    device: dict[str, Any], path: Path = DATABASE_PATH
) -> dict[str, Any]:
    initialize_database(path)
    now = _now()
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO devices(
                device_id, display_name, machine_name, platform, trust_state,
                permissions_json, key_fingerprint, certificate_state,
                registered_at, last_seen_at, revoked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(device_id) DO UPDATE SET
                display_name=excluded.display_name,
                machine_name=excluded.machine_name,
                platform=excluded.platform,
                permissions_json=excluded.permissions_json,
                key_fingerprint=excluded.key_fingerprint,
                certificate_state=excluded.certificate_state,
                last_seen_at=excluded.last_seen_at
            """,
            (
                device["device_id"],
                device["display_name"],
                device["machine_name"],
                device["platform"],
                device["trust_state"],
                json.dumps(device.get("permissions", []), ensure_ascii=True),
                device["key_fingerprint"],
                device["certificate_state"],
                device.get("registered_at") or now,
                now,
            ),
        )
    return get_device(device["device_id"], path=path) or {}


def get_device(device_id: str, path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM devices WHERE device_id = ?", (device_id,)
        ).fetchone()
    return _device_from_row(row) if row else None


def list_devices(path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT * FROM devices ORDER BY registered_at ASC"
        ).fetchall()
    return [_device_from_row(row) for row in rows]


def revoke_device(device_id: str, path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    initialize_database(path)
    now = _now()
    with _connect(path) as connection:
        cursor = connection.execute(
            """
            UPDATE devices SET trust_state = 'revoked', revoked_at = ?, last_seen_at = ?
            WHERE device_id = ? AND revoked_at IS NULL
            """,
            (now, now, device_id),
        )
    return get_device(device_id, path=path) if cursor.rowcount else None


def claim_device_command_nonce(
    nonce: str,
    device_id: str,
    command_id: str,
    expires_at: str,
    *,
    path: Path = DATABASE_PATH,
) -> bool:
    initialize_database(path)
    now = _now()
    with _connect(path) as connection:
        connection.execute(
            "DELETE FROM device_command_nonces WHERE expires_at < ?", (now,)
        )
        try:
            connection.execute(
                """
                INSERT INTO device_command_nonces(
                    nonce, device_id, command_id, expires_at, consumed_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (nonce, device_id, command_id, expires_at, now),
            )
        except sqlite3.IntegrityError:
            return False
    return True


def create_approval(
    task_id: str,
    proposed_action: str,
    target: str,
    data_summary: str,
    risk_level: str,
    reversible: bool,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    initialize_database(path)
    approval_id = str(uuid4())
    created_at = _now()
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO approvals(
                approval_id, task_id, proposed_action, target, data_summary,
                risk_level, reversible, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                approval_id,
                task_id,
                proposed_action,
                target,
                data_summary,
                risk_level,
                int(reversible),
                created_at,
            ),
        )
    return get_approval(approval_id, path=path) or {}


def list_approvals(status: str | None = None, path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    initialize_database(path)
    query = "SELECT * FROM approvals"
    parameters: tuple[Any, ...] = ()
    if status:
        query += " WHERE status = ?"
        parameters = (status,)
    query += " ORDER BY created_at DESC"
    with _connect(path) as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [_approval_from_row(row) for row in rows]


def get_approval(approval_id: str, path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
        ).fetchone()
    return _approval_from_row(row) if row else None


def decide_approval(
    approval_id: str,
    decision: str,
    scope: str = "once",
    path: Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    if decision not in {"approved", "rejected"}:
        raise ValueError("Decision must be approved or rejected")
    if scope not in {"once", "session"}:
        raise ValueError("Scope must be once or session")
    initialize_database(path)
    with _connect(path) as connection:
        cursor = connection.execute(
            """
            UPDATE approvals SET status = ?, scope = ?, decided_at = ?
            WHERE approval_id = ? AND status = 'pending'
            """,
            (decision, scope, _now(), approval_id),
        )
    if cursor.rowcount == 0:
        return None
    return get_approval(approval_id, path=path)


def create_memory(
    content: str,
    category: str = "project",
    project_id: str | None = None,
    sensitivity: str = "normal",
    confidence: str = "confirmed",
    source: str = "user",
    expires_at: str | None = None,
    *,
    structured_data: dict[str, Any] | None = None,
    source_type: str = "user_confirmed",
    source_reference: str | None = None,
    confidence_score: float = 1.0,
    valid_from: str | None = None,
    status: str = "active",
    supersedes: str | None = None,
    subject_key: str | None = None,
    environment: str | None = None,
    conflict_state: str = "clear",
    reason: str = "created",
    actor: str = "user",
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    initialize_database(path)
    memory_id = str(uuid4())
    now = _now()
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO memories(
                memory_id, content, category, project_id, sensitivity,
                confidence, source, created_at, verified_at, expires_at,
                structured_data_json, source_type, source_reference,
                confidence_score, valid_from, status, supersedes,
                subject_key, environment, updated_at, conflict_state
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                content,
                category,
                project_id,
                sensitivity,
                confidence,
                source,
                now,
                now,
                expires_at,
                json.dumps(structured_data or {}, ensure_ascii=True, sort_keys=True),
                source_type,
                source_reference,
                float(confidence_score),
                valid_from or now,
                status,
                supersedes,
                subject_key,
                environment,
                now,
                conflict_state,
            ),
        )
        row = connection.execute(
            "SELECT * FROM memories WHERE memory_id = ?", (memory_id,)
        ).fetchone()
        memory = _memory_from_row(row)
        _append_memory_version(connection, memory, "created", reason, actor)
    return memory


def list_memories(
    query: str = "",
    project_id: str | None = None,
    limit: int = 100,
    path: Path = DATABASE_PATH,
    *,
    category: str | None = None,
    status: str | None = None,
    sensitivity: str | None = None,
    include_inactive: bool = False,
    include_expired: bool = False,
) -> list[dict[str, Any]]:
    initialize_database(path)
    clauses: list[str] = []
    parameters: list[Any] = []
    if query:
        clauses.append("(content LIKE ? OR subject_key LIKE ?)")
        parameters.extend((f"%{query}%", f"%{query}%"))
    if project_id:
        clauses.append("project_id = ?")
        parameters.append(project_id)
    if category:
        clauses.append("category = ?")
        parameters.append(category)
    if sensitivity:
        clauses.append("sensitivity = ?")
        parameters.append(sensitivity)
    if status:
        clauses.append("status = ?")
        parameters.append(status)
    elif not include_inactive:
        clauses.append("status IN ('active', 'conflicted')")
    if not include_expired:
        clauses.append("(expires_at IS NULL OR expires_at > ?)")
        parameters.append(_now())
    sql = "SELECT * FROM memories"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"
    parameters.append(limit)
    with _connect(path) as connection:
        rows = connection.execute(sql, parameters).fetchall()
    return [_memory_from_row(row) for row in rows]


def get_memory(memory_id: str, path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM memories WHERE memory_id = ?", (memory_id,)
        ).fetchone()
    return _memory_from_row(row) if row else None


def update_memory(
    memory_id: str,
    changes: dict[str, Any],
    *,
    operation: str = "updated",
    reason: str = "user correction",
    actor: str = "user",
    path: Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    initialize_database(path)
    allowed = {
        "content", "category", "project_id", "sensitivity", "confidence", "source",
        "expires_at", "structured_data", "source_type", "source_reference",
        "confidence_score", "valid_from", "status", "supersedes", "subject_key",
        "environment", "conflict_state", "verified_at",
    }
    if not changes or any(key not in allowed for key in changes):
        raise ValueError("Memory update contains unsupported fields")
    columns: list[str] = []
    parameters: list[Any] = []
    for key, value in changes.items():
        column = "structured_data_json" if key == "structured_data" else key
        if key == "structured_data":
            value = json.dumps(value or {}, ensure_ascii=True, sort_keys=True)
        if key == "confidence_score":
            value = float(value)
        columns.append(f"{column} = ?")
        parameters.append(value)
    columns.append("updated_at = ?")
    parameters.append(_now())
    parameters.append(memory_id)
    with _connect(path) as connection:
        cursor = connection.execute(
            f"UPDATE memories SET {', '.join(columns)} WHERE memory_id = ?",
            parameters,
        )
        if cursor.rowcount == 0:
            return None
        row = connection.execute(
            "SELECT * FROM memories WHERE memory_id = ?", (memory_id,)
        ).fetchone()
        memory = _memory_from_row(row)
        _append_memory_version(connection, memory, operation, reason, actor)
    return memory


def list_memory_versions(
    memory_id: str, *, limit: int = 100, path: Path = DATABASE_PATH
) -> list[dict[str, Any]]:
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT * FROM memory_versions WHERE memory_id = ? "
            "ORDER BY version_number DESC LIMIT ?",
            (memory_id, max(1, min(int(limit), 200))),
        ).fetchall()
    return [
        {**dict(row), "snapshot": json.loads(row["snapshot_json"])}
        for row in rows
    ]


def create_memory_conflict(
    memory_id: str,
    conflicting_memory_id: str,
    subject_key: str,
    rationale: str,
    *,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    initialize_database(path)
    left, right = sorted((memory_id, conflicting_memory_id))
    conflict_id = str(uuid4())
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO memory_conflicts(
                conflict_id, memory_id, conflicting_memory_id, subject_key,
                status, rationale, created_at
            ) VALUES (?, ?, ?, ?, 'unresolved', ?, ?)
            """,
            (conflict_id, left, right, subject_key, rationale, _now()),
        )
        row = connection.execute(
            "SELECT * FROM memory_conflicts WHERE memory_id = ? AND conflicting_memory_id = ?",
            (left, right),
        ).fetchone()
    return dict(row)


def get_memory_conflict(
    conflict_id: str, *, path: Path = DATABASE_PATH
) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM memory_conflicts WHERE conflict_id = ?", (conflict_id,)
        ).fetchone()
    return dict(row) if row else None


def list_memory_conflicts(
    *, status: str | None = None, limit: int = 100, path: Path = DATABASE_PATH
) -> list[dict[str, Any]]:
    initialize_database(path)
    sql = "SELECT * FROM memory_conflicts"
    parameters: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        parameters.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    parameters.append(max(1, min(int(limit), 200)))
    with _connect(path) as connection:
        rows = connection.execute(sql, parameters).fetchall()
    return [dict(row) for row in rows]


def resolve_memory_conflict_record(
    conflict_id: str,
    resolution: str,
    chosen_memory_id: str | None,
    *,
    path: Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        cursor = connection.execute(
            """
            UPDATE memory_conflicts
            SET status = 'resolved', resolution = ?, chosen_memory_id = ?, resolved_at = ?
            WHERE conflict_id = ? AND status = 'unresolved'
            """,
            (resolution, chosen_memory_id, _now(), conflict_id),
        )
        if cursor.rowcount == 0:
            return None
        row = connection.execute(
            "SELECT * FROM memory_conflicts WHERE conflict_id = ?", (conflict_id,)
        ).fetchone()
    return dict(row)


def get_memory_category_settings(path: Path = DATABASE_PATH) -> dict[str, bool]:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT value_json FROM settings WHERE key = 'memory_categories'"
        ).fetchone()
    return {key: bool(value) for key, value in json.loads(row["value_json"]).items()}


def set_memory_category_enabled(
    category: str, enabled: bool, *, path: Path = DATABASE_PATH
) -> dict[str, bool]:
    settings = get_memory_category_settings(path=path)
    if category not in settings:
        raise ValueError("Unknown memory category")
    settings[category] = bool(enabled)
    with _connect(path) as connection:
        connection.execute(
            "UPDATE settings SET value_json = ?, updated_at = ? WHERE key = 'memory_categories'",
            (json.dumps(settings, ensure_ascii=True, sort_keys=True), _now()),
        )
    return settings


def delete_memory(memory_id: str, path: Path = DATABASE_PATH) -> bool:
    initialize_database(path)
    with _connect(path) as connection:
        cursor = connection.execute("DELETE FROM memories WHERE memory_id = ?", (memory_id,))
    return cursor.rowcount > 0


def upsert_memory_embedding(
    memory_id: str,
    model: str,
    vector: list[float],
    path: Path = DATABASE_PATH,
) -> None:
    if not vector:
        raise ValueError("Memory embedding vector cannot be empty")
    initialize_database(path)
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO memory_embeddings(memory_id, model, dimensions, vector_json, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(memory_id) DO UPDATE SET
                model=excluded.model,
                dimensions=excluded.dimensions,
                vector_json=excluded.vector_json,
                updated_at=excluded.updated_at
            """,
            (memory_id, model, len(vector), json.dumps(vector), _now()),
        )


def list_memory_embeddings(
    memory_ids: list[str],
    path: Path = DATABASE_PATH,
) -> dict[str, dict[str, Any]]:
    if not memory_ids:
        return {}
    initialize_database(path)
    placeholders = ",".join("?" for _ in memory_ids)
    with _connect(path) as connection:
        rows = connection.execute(
            f"SELECT * FROM memory_embeddings WHERE memory_id IN ({placeholders})",
            tuple(memory_ids),
        ).fetchall()
    return {
        row["memory_id"]: {
            "memory_id": row["memory_id"],
            "model": row["model"],
            "dimensions": row["dimensions"],
            "vector": json.loads(row["vector_json"]),
            "updated_at": row["updated_at"],
        }
        for row in rows
    }


def list_projects(path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute("SELECT * FROM projects ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def get_project(project_id: str | None, path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    if not project_id:
        return None
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
    return dict(row) if row else None


def set_project_root(
    project_id: str,
    root_path: str | None,
    *,
    path: Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        cursor = connection.execute(
            "UPDATE projects SET root_path = ? WHERE project_id = ?",
            (root_path, project_id),
        )
        if cursor.rowcount != 1:
            return None
        row = connection.execute(
            "SELECT * FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
    return dict(row) if row else None


def register_managed_project(
    root: Path, name: str, *, path: Path = DATABASE_PATH,
    managed_root: Path | None = None,
) -> dict[str, Any]:
    resolved = root.resolve(strict=True)
    boundary = (managed_root or Path.home() / "Documents" / "AURIS Work" / "Projects").resolve(strict=True)
    if not resolved.is_dir() or resolved == boundary or boundary not in resolved.parents:
        raise ValueError("Only an existing AURIS-managed project can be registered automatically.")
    project_id = "work-" + uuid5(NAMESPACE_URL, resolved.as_uri()).hex[:20]
    initialize_database(path)
    with _connect(path) as connection:
        connection.execute(
            """INSERT INTO projects(project_id, name, description, instructions, root_path, created_at)
               VALUES (?, ?, ?, '', ?, ?) ON CONFLICT(project_id) DO NOTHING""",
            (project_id, name.strip()[:120] or resolved.name, "AURIS-managed code project.", str(resolved), _now()),
        )
    return get_project(project_id, path=path) or {}


def ensure_conversation(
    conversation_id: str,
    *,
    project_id: str | None,
    mode: str,
    title: str = "AURIS conversation",
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    initialize_database(path)
    now = _now()
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO conversations(
                conversation_id, project_id, mode, title, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                project_id=excluded.project_id,
                mode=excluded.mode,
                updated_at=excluded.updated_at
            """,
            (conversation_id, project_id, mode, title[:160], now, now),
        )
    return get_conversation(conversation_id, path=path) or {}


def get_conversation(
    conversation_id: str,
    path: Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM conversations WHERE conversation_id = ?", (conversation_id,)
        ).fetchone()
    return dict(row) if row else None


def list_conversations(limit: int = 50, path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def append_message(
    conversation_id: str,
    role: str,
    content: str,
    *,
    source: str,
    metadata: dict[str, Any] | None = None,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    if role not in {"user", "assistant", "system"}:
        raise ValueError("Message role must be user, assistant, or system")
    if not content.strip():
        raise ValueError("Message content is required")
    initialize_database(path)
    message_id = str(uuid4())
    now = _now()
    with _connect(path) as connection:
        conversation = connection.execute(
            "SELECT conversation_id FROM conversations WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        if conversation is None:
            raise ValueError("Conversation does not exist")
        connection.execute(
            """
            INSERT INTO messages(
                message_id, conversation_id, role, content, source, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                conversation_id,
                role,
                content.strip(),
                source,
                json.dumps(metadata or {}, ensure_ascii=True),
                now,
            ),
        )
        connection.execute(
            "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
            (now, conversation_id),
        )
    return get_message(message_id, path=path) or {}


def get_message(message_id: str, path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM messages WHERE message_id = ?", (message_id,)
        ).fetchone()
    return _message_from_row(row) if row else None


def list_messages(
    conversation_id: str,
    limit: int = 50,
    path: Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM (
                SELECT * FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at DESC LIMIT ?
            ) ORDER BY created_at ASC
            """,
            (conversation_id, limit),
        ).fetchall()
    return [_message_from_row(row) for row in rows]


def create_scheduled_event(
    title: str,
    due_at: str,
    *,
    source: str = "user",
    project_id: str | None = None,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    initialize_database(path)
    event_id = str(uuid4())
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO scheduled_events(
                event_id, title, due_at, status, source, project_id, created_at
            ) VALUES (?, ?, ?, 'scheduled', ?, ?, ?)
            """,
            (event_id, title[:500], due_at, source, project_id, _now()),
        )
    return get_scheduled_event(event_id, path=path) or {}


def get_scheduled_event(event_id: str, path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM scheduled_events WHERE event_id = ?", (event_id,)
        ).fetchone()
    return dict(row) if row else None


def list_scheduled_events(
    *,
    status: str | None = None,
    limit: int = 100,
    path: Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    initialize_database(path)
    sql = "SELECT * FROM scheduled_events"
    parameters: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        parameters.append(status)
    sql += " ORDER BY due_at ASC LIMIT ?"
    parameters.append(limit)
    with _connect(path) as connection:
        rows = connection.execute(sql, tuple(parameters)).fetchall()
    return [dict(row) for row in rows]


def claim_due_events(now: str, *, path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    initialize_database(path)
    claimed_at = _now()
    with _connect(path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM scheduled_events
            WHERE status = 'scheduled' AND due_at <= ?
            ORDER BY due_at ASC LIMIT 20
            """,
            (now,),
        ).fetchall()
        event_ids = [row["event_id"] for row in rows]
        if event_ids:
            placeholders = ",".join("?" for _ in event_ids)
            connection.execute(
                f"UPDATE scheduled_events SET status = 'delivered', delivered_at = ? WHERE event_id IN ({placeholders}) AND status = 'scheduled'",
                (claimed_at, *event_ids),
            )
    return [get_scheduled_event(event_id, path=path) for event_id in event_ids]


def cancel_scheduled_event(event_id: str, *, path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        connection.execute(
            """
            UPDATE scheduled_events SET status = 'cancelled', cancelled_at = ?
            WHERE event_id = ? AND status = 'scheduled'
            """,
            (_now(), event_id),
        )
    return get_scheduled_event(event_id, path=path)


def create_proactive_watch(
    project_id: str,
    metric: str,
    operator: str,
    threshold: float,
    *,
    interval_seconds: int,
    cooldown_seconds: int,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    initialize_database(path)
    watch_id = str(uuid4())
    now = _now()
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO proactive_watches(
                watch_id, project_id, metric, operator, threshold,
                interval_seconds, cooldown_seconds, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                watch_id,
                project_id,
                metric,
                operator,
                threshold,
                interval_seconds,
                cooldown_seconds,
                now,
                now,
            ),
        )
    return get_proactive_watch(watch_id, path=path) or {}


def get_proactive_watch(watch_id: str, *, path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM proactive_watches WHERE watch_id = ?", (watch_id,)
        ).fetchone()
    return _proactive_watch_from_row(row) if row else None


def list_proactive_watches(
    *, project_id: str | None = None, enabled: bool | None = None,
    limit: int = 200, path: Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    initialize_database(path)
    clauses: list[str] = []
    parameters: list[Any] = []
    if project_id:
        clauses.append("project_id = ?")
        parameters.append(project_id)
    if enabled is not None:
        clauses.append("enabled = ?")
        parameters.append(int(enabled))
    sql = "SELECT * FROM proactive_watches"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"
    parameters.append(limit)
    with _connect(path) as connection:
        rows = connection.execute(sql, tuple(parameters)).fetchall()
    return [_proactive_watch_from_row(row) for row in rows]


def set_proactive_watch_enabled(
    watch_id: str, enabled: bool, *, path: Path = DATABASE_PATH
) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        connection.execute(
            """
            UPDATE proactive_watches
            SET enabled = ?, condition_active = CASE WHEN ? = 0 THEN 0 ELSE condition_active END,
                updated_at = ?
            WHERE watch_id = ?
            """,
            (int(enabled), int(enabled), _now(), watch_id),
        )
    return get_proactive_watch(watch_id, path=path)


def delete_proactive_watch(watch_id: str, *, path: Path = DATABASE_PATH) -> bool:
    initialize_database(path)
    with _connect(path) as connection:
        cursor = connection.execute(
            "DELETE FROM proactive_watches WHERE watch_id = ?", (watch_id,)
        )
    return cursor.rowcount == 1


def record_proactive_watch_evaluation(
    watch_id: str,
    *,
    observed_value: float,
    condition_active: bool,
    classification: str,
    evidence_ids: list[str],
    evaluated_at: str,
    notify: bool,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    initialize_database(path)
    alert_id = str(uuid4()) if notify else None
    with _connect(path) as connection:
        watch = connection.execute(
            "SELECT * FROM proactive_watches WHERE watch_id = ?", (watch_id,)
        ).fetchone()
        if watch is None:
            return {"watch": None, "alert": None}
        connection.execute(
            """
            UPDATE proactive_watches
            SET last_value = ?, condition_active = ?, last_evaluated_at = ?,
                last_notified_at = CASE WHEN ? = 1 THEN ? ELSE last_notified_at END,
                updated_at = ?
            WHERE watch_id = ?
            """,
            (
                observed_value,
                int(condition_active),
                evaluated_at,
                int(notify),
                evaluated_at,
                evaluated_at,
                watch_id,
            ),
        )
        if alert_id:
            connection.execute(
                """
                INSERT INTO proactive_alerts(
                    alert_id, watch_id, project_id, metric, observed_value,
                    threshold, operator, classification, evidence_json, delivered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert_id,
                    watch_id,
                    watch["project_id"],
                    watch["metric"],
                    observed_value,
                    watch["threshold"],
                    watch["operator"],
                    classification,
                    json.dumps(sorted(set(evidence_ids))[:50]),
                    evaluated_at,
                ),
            )
    return {
        "watch": get_proactive_watch(watch_id, path=path),
        "alert": get_proactive_alert(alert_id, path=path) if alert_id else None,
    }


def get_proactive_alert(alert_id: str | None, *, path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    if not alert_id:
        return None
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM proactive_alerts WHERE alert_id = ?", (alert_id,)
        ).fetchone()
    return _proactive_alert_from_row(row) if row else None


def list_proactive_alerts(
    *, project_id: str | None = None, limit: int = 100, path: Path = DATABASE_PATH
) -> list[dict[str, Any]]:
    initialize_database(path)
    sql = "SELECT * FROM proactive_alerts"
    parameters: list[Any] = []
    if project_id:
        sql += " WHERE project_id = ?"
        parameters.append(project_id)
    sql += " ORDER BY delivered_at DESC LIMIT ?"
    parameters.append(limit)
    with _connect(path) as connection:
        rows = connection.execute(sql, tuple(parameters)).fetchall()
    return [_proactive_alert_from_row(row) for row in rows]


def _proactive_watch_from_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["enabled"] = bool(item["enabled"])
    item["condition_active"] = bool(item["condition_active"])
    return item


def _proactive_alert_from_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["evidence_ids"] = json.loads(item.pop("evidence_json") or "[]")
    item["advisory_only"] = True
    item["automatic_action"] = False
    return item


def get_control_state(path: Path = DATABASE_PATH) -> dict[str, Any]:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute("SELECT value_json, updated_at FROM settings WHERE key = 'control'").fetchone()
    state = json.loads(row["value_json"])
    state["updated_at"] = row["updated_at"]
    return state


def set_control_state(
    stopped: bool,
    reason: str,
    changed_by: str = "user",
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    initialize_database(path)
    now = _now()
    value = {"stopped": stopped, "reason": reason, "changed_by": changed_by}
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO settings(key, value_json, updated_at) VALUES ('control', ?, ?)
            ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at
            """,
            (json.dumps(value, ensure_ascii=True), now),
        )
    return get_control_state(path=path)


def get_background_voice_state(path: Path = DATABASE_PATH) -> dict[str, Any]:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT value_json, updated_at FROM settings WHERE key = 'background_voice'"
        ).fetchone()
    state = json.loads(row["value_json"])
    state["updated_at"] = row["updated_at"]
    return state


def set_background_voice_state(enabled: bool, path: Path = DATABASE_PATH) -> dict[str, Any]:
    initialize_database(path)
    now = _now()
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO settings(key, value_json, updated_at) VALUES ('background_voice', ?, ?)
            ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at
            """,
            (json.dumps({"enabled": bool(enabled)}), now),
        )
    return get_background_voice_state(path=path)


def save_decision_case(
    decision_input: dict[str, Any],
    analysis: dict[str, Any],
    *,
    project_id: str | None = None,
    case_id: str | None = None,
    path: Path = DATABASE_PATH,
) -> dict[str, Any]:
    initialize_database(path)
    identifier = case_id or str(uuid4())
    now = _now()
    status = str((analysis.get("recommendation") or {}).get("status") or "inconclusive")
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO decision_cases(
                case_id, objective, project_id, status, input_json,
                analysis_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_id) DO UPDATE SET
                objective=excluded.objective,
                project_id=excluded.project_id,
                status=excluded.status,
                input_json=excluded.input_json,
                analysis_json=excluded.analysis_json,
                updated_at=excluded.updated_at
            """,
            (
                identifier,
                str(analysis.get("objective") or "")[:1000],
                project_id,
                status,
                json.dumps(decision_input, ensure_ascii=True, sort_keys=True),
                json.dumps(analysis, ensure_ascii=True, sort_keys=True),
                now,
                now,
            ),
        )
    return get_decision_case(identifier, path=path) or {}


def get_decision_case(case_id: str, path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM decision_cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        outcomes = connection.execute(
            "SELECT * FROM decision_outcomes WHERE case_id = ? ORDER BY observed_at DESC",
            (case_id,),
        ).fetchall()
    if row is None:
        return None
    decision = _decision_case_from_row(row)
    decision["outcomes"] = [_decision_outcome_from_row(item) for item in outcomes]
    return decision


def list_decision_cases(
    *,
    project_id: str | None = None,
    limit: int = 50,
    path: Path = DATABASE_PATH,
) -> list[dict[str, Any]]:
    initialize_database(path)
    bounded_limit = max(1, min(int(limit), 200))
    query = "SELECT case_id FROM decision_cases"
    parameters: list[Any] = []
    if project_id:
        query += " WHERE project_id = ?"
        parameters.append(project_id)
    query += " ORDER BY updated_at DESC LIMIT ?"
    parameters.append(bounded_limit)
    with _connect(path) as connection:
        rows = connection.execute(query, tuple(parameters)).fetchall()
    return [
        decision
        for row in rows
        if (decision := get_decision_case(row["case_id"], path=path)) is not None
    ]


def record_decision_outcome(
    case_id: str,
    *,
    actual_success: bool,
    actual_summary: str,
    expected_summary: str = "",
    difference_summary: str = "",
    root_cause: str = "",
    lesson: str = "",
    confidence_update: str = "unchanged",
    observed_at: str | None = None,
    path: Path = DATABASE_PATH,
) -> dict[str, Any] | None:
    initialize_database(path)
    if get_decision_case(case_id, path=path) is None:
        return None
    outcome_id = str(uuid4())
    now = _now()
    confidence_update = confidence_update.strip().casefold()
    if confidence_update not in {"increased", "decreased", "unchanged", "unknown"}:
        raise ValueError(
            "confidence_update must be increased, decreased, unchanged, or unknown."
        )
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO decision_outcomes(
                outcome_id, case_id, actual_success, actual_summary, expected_summary,
                difference_summary, root_cause, lesson, confidence_update,
                observed_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                outcome_id,
                case_id,
                int(actual_success),
                actual_summary[:1000],
                expected_summary[:1000],
                difference_summary[:1000],
                root_cause[:1000],
                lesson[:1000],
                confidence_update,
                observed_at or now,
                now,
            ),
        )
        connection.execute(
            "UPDATE decision_cases SET status = 'observed', updated_at = ? WHERE case_id = ?",
            (now, case_id),
        )
        row = connection.execute(
            "SELECT * FROM decision_outcomes WHERE outcome_id = ?", (outcome_id,)
        ).fetchone()
    return _decision_outcome_from_row(row)


def decision_calibration_summary(path: Path = DATABASE_PATH) -> dict[str, Any]:
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute(
            """
            SELECT c.case_id, c.analysis_json, o.actual_success
            FROM decision_cases c
            JOIN decision_outcomes o ON o.case_id = c.case_id
            ORDER BY o.observed_at DESC
            """
        ).fetchall()
    forecasts: list[tuple[float, bool]] = []
    for row in rows:
        analysis = json.loads(row["analysis_json"])
        probability = (analysis.get("recommendation") or {}).get("forecast_probability")
        if probability is not None:
            forecasts.append((float(probability), bool(row["actual_success"])))
    brier = None
    if forecasts:
        brier = sum((probability - float(actual)) ** 2 for probability, actual in forecasts) / len(forecasts)
    return {
        "outcomes_recorded": len(rows),
        "probabilistic_forecasts_scored": len(forecasts),
        "brier_score": round(brier, 6) if brier is not None else None,
        "calibrated": len(forecasts) >= 20,
        "minimum_sample_size": 20,
        "warning": (
            "Calibration is not claimed until at least 20 user-supplied probabilistic forecasts have observed outcomes."
            if len(forecasts) < 20
            else "The Brier score is empirical, but should still be interpreted by decision domain."
        ),
    }


def decision_outcome_learning_summary(path: Path = DATABASE_PATH) -> dict[str, Any]:
    """Return bounded empirical feedback without changing policy or model weights."""
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute(
            """
            SELECT o.actual_success, o.lesson, o.root_cause, o.confidence_update,
                   c.analysis_json
            FROM decision_outcomes o
            JOIN decision_cases c ON c.case_id = o.case_id
            ORDER BY o.observed_at DESC
            LIMIT 200
            """
        ).fetchall()
    by_option: dict[str, dict[str, int]] = {}
    lessons: list[str] = []
    root_causes: list[str] = []
    confidence_updates = {key: 0 for key in ("increased", "decreased", "unchanged", "unknown")}
    for row in rows:
        analysis = json.loads(row["analysis_json"])
        option = str((analysis.get("recommendation") or {}).get("option") or "withheld")[:180]
        counts = by_option.setdefault(option, {"observations": 0, "successes": 0})
        counts["observations"] += 1
        counts["successes"] += int(bool(row["actual_success"]))
        if row["lesson"] and row["lesson"] not in lessons:
            lessons.append(row["lesson"])
        if row["root_cause"] and row["root_cause"] not in root_causes:
            root_causes.append(row["root_cause"])
        update = row["confidence_update"] or "unknown"
        confidence_updates[update if update in confidence_updates else "unknown"] += 1
    option_performance = []
    for option, counts in sorted(by_option.items()):
        sample_sufficient = counts["observations"] >= 5
        option_performance.append(
            {
                "option": option,
                **counts,
                "observed_success_rate": (
                    round(counts["successes"] / counts["observations"], 4)
                    if sample_sufficient
                    else None
                ),
                "sample_sufficient": sample_sufficient,
            }
        )
    return {
        "observations": len(rows),
        "minimum_option_sample_size": 5,
        "option_performance": option_performance,
        "recent_lessons": lessons[:10],
        "recent_root_causes": root_causes[:10],
        "confidence_updates": confidence_updates,
        "automatic_policy_changes": False,
        "automatic_model_weight_changes": False,
        "warning": (
            "Outcome feedback is advisory. AURIS does not change security policy or model weights automatically."
        ),
    }


@contextmanager
def _connect(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _task_from_row(row: sqlite3.Row) -> dict[str, Any]:
    plan = json.loads(row["plan_json"])
    return {
        **plan,
        "plan": plan,
        "result": json.loads(row["result_json"]) if row["result_json"] else None,
        "project_id": row["project_id"],
        "mode": row["mode"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _approval_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["reversible"] = bool(data["reversible"])
    return data


def _message_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["metadata"] = json.loads(data.pop("metadata_json"))
    return data


def _workflow_checkpoint_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["evidence"] = json.loads(data.pop("evidence_json"))
    return data


def _application_state_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["completed"] = json.loads(data.pop("completed_json"))
    data["remaining"] = json.loads(data.pop("remaining_json"))
    data["checkpoint"] = json.loads(data.pop("checkpoint_json"))
    return data


def _device_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["permissions"] = json.loads(data.pop("permissions_json"))
    return data


def _memory_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    try:
        data["structured_data"] = json.loads(data.pop("structured_data_json"))
    except (json.JSONDecodeError, TypeError):
        data.pop("structured_data_json", None)
        data["structured_data"] = {}
    data["confidence_score"] = float(data.get("confidence_score", 0.0))
    return data


def _decision_case_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["input"] = json.loads(data.pop("input_json"))
    data["analysis"] = json.loads(data.pop("analysis_json"))
    return data


def _decision_outcome_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["actual_success"] = bool(data["actual_success"])
    return data


def _append_memory_version(
    connection: sqlite3.Connection,
    memory: dict[str, Any],
    operation: str,
    reason: str,
    actor: str,
) -> None:
    row = connection.execute(
        "SELECT COALESCE(MAX(version_number), 0) AS current "
        "FROM memory_versions WHERE memory_id = ?",
        (memory["memory_id"],),
    ).fetchone()
    connection.execute(
        """
        INSERT INTO memory_versions(
            version_id, memory_id, version_number, operation,
            snapshot_json, reason, actor, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid4()),
            memory["memory_id"],
            int(row["current"]) + 1,
            operation,
            json.dumps(memory, ensure_ascii=True, sort_keys=True),
            reason[:300],
            actor[:80],
            _now(),
        ),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
