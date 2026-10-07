from __future__ import annotations

import argparse
import json
import mimetypes
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from auris.anticipation_service import build_operations_intelligence
from auris.application_state import application_state_dashboard
from auris.audit import DEFAULT_AUDIT_PATH, record_event
from auris.auth import (
    BootstrapCodeStore,
    PortalAuth,
    access_token_valid,
    csrf_token_valid,
    initialize_portal_auth,
    session_cookie_header,
    session_cookie_valid,
)
from auris.browser_agent import browser_status
from auris.capabilities import capability_registry, collect_capability_observations
from auris.codex_workspace_agent import codex_cli_status
from auris.communications_agent import productivity_status
from auris.cloud_channel import cloud_channel_status
from auris.coding_agent import validate_project_root
from auris.codex_workspace_agent import cleanup_expired_codex_proposals
from auris.database import (
    decision_calibration_summary,
    decision_outcome_learning_summary,
    decide_approval,
    get_decision_case,
    get_control_state,
    get_approval,
    get_workflow_run,
    set_background_voice_state,
    set_project_root,
    get_task,
    initialize_database,
    list_approvals,
    list_conversations,
    list_decision_cases,
    list_messages,
    list_scheduled_events,
    list_projects,
    list_tasks,
    list_workflow_runs,
    set_control_state,
    save_decision_case,
    record_decision_outcome,
    update_task_state,
    cancel_scheduled_event,
)
from auris.decision_intelligence import DecisionValidationError, analyse_decision
from auris.device_agent import device_capabilities, installed_applications
from auris.device_fabric import device_trust_status, initialize_device_identity
from auris.desktop_state import companion_status
from auris.event_engine import EventEngine
from auris.model_gateway import model_status, prime_model_engine, wait_for_model_prime
from auris.model_gateway import embedding_status
from auris.model_council import CouncilValidationError, council_status, run_model_council
from auris.memory_service import (
    MemoryValidationError,
    correct_memory,
    delete_memory_record,
    export_memory_archive,
    index_memory,
    memory_dashboard,
    memory_history,
    resolve_memory_conflict,
    set_memory_category_enabled,
    store_memory,
)
from auris.local_ipc import LocalIpcServer
from auris.repair_agent import cleanup_expired_test_repairs
from auris.predictive_intelligence import build_predictive_intelligence
from auris.proactive_agent import (
    ProactiveWatchEngine,
    ProactiveWatchValidationError,
    create_watch,
    remove_watch,
    set_proactive_watch_enabled,
    watch_dashboard,
)
from auris.runtime import (
    CommandContext,
    discard_pending_task_action,
    execute_approved_task,
    process_command,
    recover_incomplete_workflows,
)
from auris.schemas import TaskState
from auris.storage import read_jsonl
from auris.world_model import (
    WorldModelValidationError,
    analyse_causal_intervention,
    build_world_model,
)
from auris.system_status import collect_system_status
from auris.voice import (
    listen_for_interrupt,
    listen_for_wake_word,
    listen_once,
    prime_voice_engine,
    speak,
    stop_speaking,
    voice_status,
)
from auris.workspace_service import workspace_snapshot
from auris.voice_turns import VOICE_TURNS


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
STARTED_AT = datetime.now(timezone.utc).isoformat()
TOKEN_PATH = ROOT / "data" / "portal.token"
PORTAL_AUTH: PortalAuth | None = None
BOOTSTRAP_CODES = BootstrapCodeStore(ttl_seconds=30)
LOCAL_IPC_STATUS: dict[str, Any] = {
    "connected": False,
    "transport": "authenticated_named_pipe",
    "native_clients": "http_fallback",
}


class AurisHandler(BaseHTTPRequestHandler):
    server_version = "AURIS/0.8.34"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            return
        if parsed.path == "/api/health":
            self._send_json({"ok": True, "service": "AURIS", "version": "0.8.34"})
            return
        if parsed.path in {"/browser-acceptance.html", "/browser-acceptance.css"}:
            self._serve_static(parsed.path)
            return
        if self._establish_session(parsed):
            return
        if not self._require_session():
            return

        if parsed.path == "/api/session":
            auth = _portal_auth()
            self._send_json(
                {
                    "ok": True,
                    "session": {
                        "authenticated": True,
                        "owner": "Devansh",
                        "csrf_token": auth.csrf_token,
                        "local_only": True,
                    },
                }
            )
            return

        if parsed.path == "/api/status":
            self._send_json({"ok": True, "status": _platform_status()})
            return

        if parsed.path == "/api/capabilities":
            self._send_json({"ok": True, "registry": capability_registry(collect_capability_observations())})
            return

        if parsed.path == "/api/tasks":
            limit = _limit_from_query(parsed.query, default=20)
            self._send_json({"ok": True, "tasks": list_tasks(limit=limit)})
            return

        if parsed.path.startswith("/api/tasks/"):
            task_id = parsed.path.rsplit("/", 1)[-1]
            task = get_task(task_id)
            if task is not None:
                task["workflow"] = _public_workflow(get_workflow_run(task_id))
            self._send_json({"ok": task is not None, "task": task}, status=200 if task else 404)
            return

        if parsed.path == "/api/workflows":
            limit = _limit_from_query(parsed.query, default=50)
            self._send_json(
                {
                    "ok": True,
                    "workflows": [
                        _public_workflow(item) for item in list_workflow_runs(limit=limit)
                    ],
                }
            )
            return

        if parsed.path == "/api/projects":
            self._send_json({"ok": True, "projects": list_projects()})
            return

        if parsed.path == "/api/conversations":
            limit = _limit_from_query(parsed.query, default=30)
            self._send_json({"ok": True, "conversations": list_conversations(limit=limit)})
            return

        if parsed.path.startswith("/api/conversations/") and parsed.path.endswith("/messages"):
            parts = parsed.path.strip("/").split("/")
            if len(parts) != 4:
                self._send_json({"ok": False, "error": "Invalid conversation path"}, status=404)
                return
            limit = _limit_from_query(parsed.query, default=50)
            self._send_json(
                {"ok": True, "messages": list_messages(parts[2], limit=limit)}
            )
            return

        if parsed.path == "/api/memories/export":
            query = parse_qs(parsed.query)
            project_id = query.get("project_id", [None])[0]
            archive = export_memory_archive(project_id=project_id)
            record_event(
                "memory.exported",
                {
                    "project_id": project_id,
                    "memory_count": len(archive["memories"]),
                    "content_stored_in_audit": False,
                },
            )
            self._send_json({"ok": True, "archive": archive})
            return

        if parsed.path.startswith("/api/memories/") and parsed.path.endswith("/history"):
            parts = parsed.path.strip("/").split("/")
            if len(parts) != 4:
                self._send_json({"ok": False, "error": "Invalid memory history path"}, status=404)
                return
            try:
                history = memory_history(parts[2])
            except MemoryValidationError as error:
                self._send_json({"ok": False, "error": str(error)}, status=404)
                return
            self._send_json({"ok": True, "history": history})
            return

        if parsed.path == "/api/memories":
            query = parse_qs(parsed.query)
            dashboard = memory_dashboard(
                query=query.get("q", [""])[0],
                project_id=query.get("project_id", [None])[0],
                category=query.get("category", [None])[0],
                status=query.get("status", [None])[0],
                sensitivity=query.get("sensitivity", [None])[0],
                limit=_limit_from_query(parsed.query, default=200),
            )
            self._send_json(
                {
                    "ok": True,
                    **dashboard,
                }
            )
            return

        if parsed.path == "/api/approvals":
            query = parse_qs(parsed.query)
            status = query.get("status", [None])[0]
            self._send_json({"ok": True, "approvals": _approval_views(status)})
            return

        if parsed.path == "/api/events":
            query = parse_qs(parsed.query)
            status = query.get("status", [None])[0]
            self._send_json({"ok": True, "events": list_scheduled_events(status=status, limit=100)})
            return

        if parsed.path == "/api/integrations":
            self._send_json({"ok": True, "integrations": productivity_status()})
            return

        if parsed.path == "/api/workspaces":
            query = parse_qs(parsed.query)
            self._send_json(
                {
                    "ok": True,
                    "workspaces": workspace_snapshot(
                        project_id=query.get("project_id", ["auris-one"])[0]
                    ),
                }
            )
            return

        if parsed.path == "/api/anticipation":
            query = parse_qs(parsed.query)
            project_id = query.get("project_id", [None])[0]
            private = query.get("private", ["false"])[0].casefold() == "true"
            focus_mode = query.get("focus", ["false"])[0].casefold() == "true"
            intelligence = build_operations_intelligence(
                project_id=project_id,
                query=query.get("q", [""])[0],
                private=private,
                focus_mode=focus_mode,
            )
            self._send_json({"ok": True, "operations": intelligence})
            return

        if parsed.path == "/api/decisions":
            query = parse_qs(parsed.query)
            private = query.get("private", ["false"])[0].casefold() == "true"
            self._send_json(
                {
                    "ok": True,
                    "decisions": []
                    if private
                    else list_decision_cases(
                        project_id=query.get("project_id", [None])[0],
                        limit=_limit_from_query(parsed.query, default=50),
                    ),
                    "calibration": decision_calibration_summary(),
                    "outcome_learning": decision_outcome_learning_summary(),
                    "private_mode": private,
                }
            )
            return

        if parsed.path == "/api/world-model":
            query = parse_qs(parsed.query)
            self._send_json(
                {
                    "ok": True,
                    "world_model": build_world_model(
                        project_id=query.get("project_id", [None])[0],
                        private=query.get("private", ["false"])[0].casefold() == "true",
                    ),
                }
            )
            return

        if parsed.path == "/api/predictions":
            query = parse_qs(parsed.query)
            self._send_json(
                {
                    "ok": True,
                    "predictive_intelligence": build_predictive_intelligence(
                        project_id=query.get("project_id", [None])[0],
                        private=query.get("private", ["false"])[0].casefold() == "true",
                    ),
                }
            )
            return

        if parsed.path == "/api/watches":
            query = parse_qs(parsed.query)
            private = query.get("private", ["false"])[0].casefold() == "true"
            dashboard = (
                {
                    "watches": [],
                    "alerts": [],
                    "policy": {"advisory_only": True, "automatic_action": False},
                    "private_mode": True,
                }
                if private
                else {
                    **watch_dashboard(project_id=query.get("project_id", [None])[0]),
                    "private_mode": False,
                }
            )
            self._send_json({"ok": True, "proactive": dashboard})
            return

        if parsed.path.startswith("/api/decisions/"):
            parts = parsed.path.strip("/").split("/")
            if len(parts) == 3:
                decision = get_decision_case(parts[2])
                self._send_json(
                    {"ok": decision is not None, "decision": decision},
                    status=200 if decision else 404,
                )
                return

        if parsed.path == "/api/voice/status":
            self._send_json({"ok": True, "voice": voice_status()})
            return

        if parsed.path == "/api/voice/turns":
            self._send_json({"ok": True, "turns": VOICE_TURNS.snapshot()})
            return

        if parsed.path == "/api/council/status":
            self._send_json({"ok": True, "council": council_status()})
            return

        if parsed.path == "/api/device/capabilities":
            self._send_json({"ok": True, "capabilities": device_capabilities()})
            return

        if parsed.path == "/api/browser/status":
            self._send_json({"ok": True, "browser": browser_status()})
            return

        if parsed.path == "/api/application-state":
            query = parse_qs(parsed.query)
            private = query.get("private", ["false"])[0].casefold() == "true"
            project_id = query.get("project_id", [None])[0]
            dashboard = application_state_dashboard(None if private else project_id)
            dashboard["private_mode"] = private
            self._send_json({"ok": True, "application_state": dashboard})
            return

        if parsed.path == "/api/device/trust":
            self._send_json({"ok": True, "device_trust": device_trust_status()})
            return

        if parsed.path == "/api/device/applications":
            self._send_json({"ok": True, "applications": installed_applications()})
            return

        if parsed.path == "/api/audit":
            limit = _limit_from_query(parsed.query, default=50)
            self._send_json({"ok": True, "events": read_jsonl(DEFAULT_AUDIT_PATH, limit=limit)})
            return

        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        if not self._require_session() or not self._require_csrf():
            return
        parsed = urlparse(self.path)
        body = self._read_json_body()

        if parsed.path == "/api/command":
            self._handle_command(body)
            return

        if parsed.path == "/api/session/bootstrap":
            bootstrap = BOOTSTRAP_CODES.issue()
            record_event("portal.bootstrap_issued", {"expires_in_seconds": bootstrap["expires_in_seconds"]})
            self._send_json({"ok": True, "bootstrap": bootstrap}, status=201)
            return

        if parsed.path == "/api/client/ready":
            ui_version = str(body.get("ui_version", "unknown"))[:32]
            renderer = str(body.get("renderer", "pending"))[:40]
            record_event(
                "portal.client_ready",
                {"ui_version": ui_version, "renderer": renderer, "authenticated": True},
            )
            self._send_json(
                {"ok": True, "backend": "online", "version": "0.8.34"}
            )
            return

        if parsed.path == "/api/memories":
            self._handle_memory(body)
            return

        if parsed.path == "/api/decisions/analyse":
            self._handle_decision_analysis(body)
            return

        if parsed.path == "/api/council/analyse":
            self._handle_model_council(body)
            return

        if parsed.path == "/api/world-model/simulate":
            self._handle_world_model_simulation(body)
            return

        if parsed.path == "/api/watches":
            if bool(body.get("private", False)):
                self._send_json(
                    {"ok": False, "error": "Private Session cannot create durable watches."},
                    status=409,
                )
                return
            try:
                watch = create_watch(
                    project_id=str(body.get("project_id") or "auris-one"),
                    metric=str(body.get("metric") or ""),
                    operator=str(body.get("operator") or "gte"),
                    threshold=float(body.get("threshold")),
                    interval_seconds=_bounded_int(
                        body.get("interval_seconds"), default=300, minimum=60, maximum=86400
                    ),
                    cooldown_seconds=_bounded_int(
                        body.get("cooldown_seconds"), default=3600, minimum=300, maximum=604800
                    ),
                )
            except (TypeError, ValueError, ProactiveWatchValidationError) as error:
                self._send_json({"ok": False, "error": str(error)}, status=400)
                return
            self._send_json({"ok": True, "watch": watch}, status=201)
            return

        if parsed.path.startswith("/api/watches/") and parsed.path.endswith("/state"):
            parts = parsed.path.strip("/").split("/")
            enabled = body.get("enabled")
            if len(parts) != 4 or not isinstance(enabled, bool):
                self._send_json({"ok": False, "error": "A boolean enabled value is required."}, status=400)
                return
            watch = set_proactive_watch_enabled(parts[2], enabled)
            self._send_json({"ok": watch is not None, "watch": watch}, status=200 if watch else 404)
            return

        if parsed.path.startswith("/api/decisions/") and parsed.path.endswith("/outcomes"):
            self._handle_decision_outcome(parsed.path, body)
            return

        if parsed.path.startswith("/api/memories/") and parsed.path.endswith("/correct"):
            self._handle_memory_correction(parsed.path, body)
            return

        if parsed.path.startswith("/api/memory/conflicts/") and parsed.path.endswith("/resolve"):
            self._handle_memory_conflict_resolution(parsed.path, body)
            return

        if parsed.path.startswith("/api/memory/categories/"):
            self._handle_memory_category(parsed.path, body)
            return

        if parsed.path == "/api/projects/root":
            self._handle_project_root(body)
            return

        if parsed.path == "/api/voice/listen":
            timeout_seconds = _bounded_int(
                body.get("timeout_seconds"), default=8, minimum=2, maximum=20
            )
            result = _capture_voice("command", timeout_seconds, private=bool(body.get("private", False)))
            record_event(
                "voice.listened",
                {
                    "success": bool(result.get("ok")),
                    "language": result.get("language"),
                    "confidence": result.get("confidence"),
                    "audio_signal_detected": bool(result.get("audio_signal_detected")),
                    "peak_audio_level": result.get("peak_audio_level"),
                },
            )
            self._send_json(
                {"ok": bool(result.get("ok")), "voice": result},
                status=200 if result.get("ok") else 408,
            )
            return

        if parsed.path == "/api/voice/wake":
            timeout_seconds = _bounded_int(
                body.get("timeout_seconds"), default=20, minimum=5, maximum=30
            )
            result = _capture_voice("wake", timeout_seconds)
            record_event(
                "voice.wake_listened",
                {
                    "success": bool(result.get("ok")),
                    "language": result.get("language"),
                    "confidence": result.get("confidence"),
                    "audio_signal_detected": bool(result.get("audio_signal_detected")),
                    "peak_audio_level": result.get("peak_audio_level"),
                },
            )
            self._send_json(
                {"ok": bool(result.get("ok")), "voice": result},
                status=200 if result.get("ok") else 408,
            )
            return

        if parsed.path == "/api/voice/interrupt":
            timeout_seconds = _bounded_int(
                body.get("timeout_seconds"), default=2, minimum=2, maximum=10
            )
            result = listen_for_interrupt(timeout_seconds=timeout_seconds)
            record_event(
                "voice.interruption_listened",
                {
                    "success": bool(result.get("ok")),
                    "language": result.get("language"),
                    "confidence": result.get("confidence"),
                    "audio_signal_detected": bool(result.get("audio_signal_detected")),
                    "peak_audio_level": result.get("peak_audio_level"),
                },
            )
            self._send_json(
                {"ok": bool(result.get("ok")), "voice": result},
                status=200 if result.get("ok") else 408,
            )
            return

        if parsed.path == "/api/voice/speak":
            text = str(body.get("text", "")).strip()
            if not text:
                self._send_json({"ok": False, "error": "Speech text is required"}, status=400)
                return
            result = speak(
                text,
                rate=_bounded_int(body.get("rate"), default=0, minimum=-4, maximum=4),
                asynchronous=True,
                voice_turn_id=_optional_text(body.get("voice_turn_id")),
            )
            self._send_json(
                {"ok": bool(result.get("ok")), "voice": result},
                status=200 if result.get("ok") else 500,
            )
            return

        if parsed.path == "/api/voice/background":
            enabled = body.get("enabled")
            if not isinstance(enabled, bool):
                self._send_json({"ok": False, "error": "A boolean enabled value is required."}, status=400)
                return
            state = set_background_voice_state(enabled)
            record_event("voice.background_changed", {"enabled": enabled})
            self._send_json({"ok": True, "voice": {**voice_status(), **state}})
            return

        if parsed.path == "/api/voice/stop":
            result = stop_speaking()
            record_event("voice.stopped", {"stopped": result["stopped"]})
            self._send_json({"ok": True, "voice": result})
            return

        if parsed.path.startswith("/api/approvals/"):
            self._handle_approval(parsed.path, body)
            return

        if parsed.path == "/api/control/stop":
            stop_speaking()
            state = set_control_state(True, str(body.get("reason", "Emergency stop activated")))
            record_event("control.stopped", {"reason": state["reason"]})
            self._send_json({"ok": True, "control": state})
            return

        if parsed.path == "/api/control/resume":
            state = set_control_state(False, str(body.get("reason", "Resumed by Devansh")))
            record_event("control.resumed", {"reason": state["reason"]})
            self._send_json({"ok": True, "control": state})
            return

        self._send_json({"ok": False, "error": "Unknown endpoint"}, status=404)

    def do_DELETE(self) -> None:
        if not self._require_session() or not self._require_csrf():
            return
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/events/"):
            event_id = parsed.path.rsplit("/", 1)[-1]
            event = cancel_scheduled_event(event_id)
            if event:
                record_event("reminder.cancelled", {"event_id": event_id})
            self._send_json({"ok": event is not None, "event": event}, status=200 if event else 404)
            return
        if parsed.path.startswith("/api/watches/"):
            watch_id = parsed.path.rsplit("/", 1)[-1]
            deleted = remove_watch(watch_id)
            self._send_json({"ok": deleted, "deleted": deleted}, status=200 if deleted else 404)
            return
        if not parsed.path.startswith("/api/memories/"):
            self._send_json({"ok": False, "error": "Unknown endpoint"}, status=404)
            return
        memory_id = parsed.path.rsplit("/", 1)[-1]
        deleted = delete_memory_record(memory_id)
        if deleted:
            record_event("memory.deleted", {"memory_id": memory_id})
        self._send_json(
            {"ok": deleted, "deleted": deleted},
            status=200 if deleted else 404,
        )

    def _handle_command(self, body: dict[str, Any]) -> None:
        command = str(body.get("command", "")).strip()
        if not command:
            self._send_json({"ok": False, "error": "Command is required"}, status=400)
            return
        context = CommandContext(
            project_id=_optional_text(body.get("project_id")),
            mode=str(body.get("mode", "command")),
            private=bool(body.get("private", False)),
            conversation_id=_safe_identifier(body.get("conversation_id"), "auris-primary"),
            voice_turn_id=_optional_text(body.get("voice_turn_id")),
        )
        response = process_command(command, context)
        self._send_json(response, status=200 if response.get("ok") else 423)

    def _handle_memory(self, body: dict[str, Any]) -> None:
        content = str(body.get("content", "")).strip()
        if not content:
            self._send_json({"ok": False, "error": "Memory content is required"}, status=400)
            return
        try:
            stored = store_memory(
                content,
                category=str(body.get("category", "project")),
                project_id=_optional_text(body.get("project_id")),
                subject_key=_optional_text(body.get("subject_key")),
                structured_data=body.get("structured_data"),
                source_type="user_confirmed",
                sensitivity=str(body.get("sensitivity", "normal")),
                confidence_score=body.get("confidence_score", 1.0),
                valid_until=_optional_text(body.get("valid_until")),
                environment=_optional_text(body.get("environment")),
                source="memory_dashboard",
                reason="Created from the authenticated memory dashboard.",
                actor="Devansh",
            )
        except MemoryValidationError as error:
            self._send_json({"ok": False, "error": str(error)}, status=400)
            return
        memory = stored["memory"]
        try:
            semantic_index = index_memory(memory["memory_id"])
        except RuntimeError as error:
            semantic_index = {"ok": False, "error": str(error)}
        record_event(
            "memory.created",
            {
                "memory_id": memory["memory_id"],
                "category": memory["category"],
                "project_id": memory.get("project_id"),
                "duplicate": stored["duplicate"],
                "requires_resolution": stored["requires_resolution"],
                "content_stored_in_audit": False,
            },
        )
        self._send_json(
            {"ok": True, **stored, "semantic_index": semantic_index},
            status=200 if stored["duplicate"] else 201,
        )

    def _handle_decision_analysis(self, body: dict[str, Any]) -> None:
        decision_input = body.get("decision") if isinstance(body.get("decision"), dict) else body
        try:
            analysis = analyse_decision(decision_input)
        except DecisionValidationError as error:
            self._send_json({"ok": False, "error": str(error)}, status=400)
            return
        council_request = body.get("council") if isinstance(body.get("council"), dict) else {}
        if council_request.get("requested"):
            analysis["model_council"] = run_model_council(
                analysis["objective"],
                context={
                    "recommendation": analysis["recommendation"],
                    "options": analysis["options"],
                    "hypotheses": analysis["hypotheses"],
                    "missing_evidence": analysis["missing_evidence"],
                },
                requested=True,
                complexity=float(council_request.get("complexity", 0.8)),
                risk=str(council_request.get("risk") or "medium"),
                max_calls=int(council_request.get("max_calls", 5)),
                token_budget=int(council_request.get("token_budget", 1400)),
                private=bool(body.get("private", False)),
            )
        private = bool(body.get("private", False))
        project_id = _optional_text(body.get("project_id"))
        decision = None
        if not private:
            decision = save_decision_case(decision_input, analysis, project_id=project_id)
        record_event(
            "decision.analysed",
            {
                "case_id": (decision or {}).get("case_id"),
                "project_id": project_id,
                "private": private,
                "recommendation_status": analysis["recommendation"]["status"],
                "confidence": analysis["confidence"],
                "content_stored_in_audit": False,
            },
        )
        self._send_json(
            {"ok": True, "analysis": analysis, "decision": decision, "private": private},
            status=200 if private else 201,
        )

    def _handle_model_council(self, body: dict[str, Any]) -> None:
        try:
            result = run_model_council(
                str(body.get("problem") or ""),
                context=body.get("context") if isinstance(body.get("context"), dict) else {},
                requested=bool(body.get("requested", True)),
                complexity=float(body.get("complexity", 0.8)),
                risk=str(body.get("risk") or "medium"),
                max_calls=int(body.get("max_calls", 5)),
                token_budget=int(body.get("token_budget", 1400)),
                private=bool(body.get("private", False)),
            )
        except (CouncilValidationError, TypeError, ValueError) as error:
            self._send_json({"ok": False, "error": str(error)}, status=400)
            return
        record_event(
            "model_council.completed",
            {
                "activated": result["activated"],
                "state": result["state"],
                "calls_used": result.get("calls_used", 0),
                "independent_models": result.get("independent_models", False),
                "content_stored_in_audit": False,
            },
        )
        self._send_json({"ok": True, "council": result})

    def _handle_world_model_simulation(self, body: dict[str, Any]) -> None:
        private = bool(body.get("private", False))
        project_id = _optional_text(body.get("project_id"))
        snapshot = build_world_model(project_id=project_id, private=private)
        try:
            causal_analysis = analyse_causal_intervention(
                snapshot,
                action_id=str(body.get("action_id") or ""),
                expected_snapshot_id=str(body.get("snapshot_id") or ""),
                alternative_action_id=_optional_text(body.get("alternative_action_id")),
            )
        except WorldModelValidationError as error:
            self._send_json({"ok": False, "error": str(error)}, status=409)
            return
        simulation = causal_analysis["simulation"]
        record_event(
            "world_model.simulated",
            {
                "snapshot_id": simulation["snapshot_id"],
                "simulation_id": simulation["simulation_id"],
                "causal_analysis_id": causal_analysis["analysis_id"],
                "action_type": simulation["action"]["action_type"],
                "risk_level": simulation["action"]["risk_level"],
                "executed": False,
                "content_stored_in_audit": False,
            },
        )
        self._send_json(
            {"ok": True, "simulation": simulation, "causal_analysis": causal_analysis}
        )

    def _handle_decision_outcome(self, path: str, body: dict[str, Any]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4 or not isinstance(body.get("actual_success"), bool):
            self._send_json(
                {"ok": False, "error": "A decision case and boolean actual_success are required."},
                status=400,
            )
            return
        summary = str(body.get("actual_summary") or "").strip()
        if not summary:
            self._send_json({"ok": False, "error": "An actual outcome summary is required."}, status=400)
            return
        try:
            outcome = record_decision_outcome(
                parts[2],
                actual_success=body["actual_success"],
                actual_summary=summary,
                expected_summary=str(body.get("expected_summary") or "").strip(),
                difference_summary=str(body.get("difference_summary") or "").strip(),
                root_cause=str(body.get("root_cause") or "").strip(),
                lesson=str(body.get("lesson") or "").strip(),
                confidence_update=str(body.get("confidence_update") or "unchanged"),
                observed_at=_optional_text(body.get("observed_at")),
            )
        except ValueError as error:
            self._send_json({"ok": False, "error": str(error)}, status=400)
            return
        if outcome is None:
            self._send_json({"ok": False, "error": "Decision case not found."}, status=404)
            return
        record_event(
            "decision.outcome_recorded",
            {
                "case_id": parts[2],
                "outcome_id": outcome["outcome_id"],
                "actual_success": outcome["actual_success"],
                "content_stored_in_audit": False,
            },
        )
        self._send_json(
            {
                "ok": True,
                "outcome": outcome,
                "calibration": decision_calibration_summary(),
                "outcome_learning": decision_outcome_learning_summary(),
            },
            status=201,
        )

    def _handle_memory_correction(self, path: str, body: dict[str, Any]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._send_json({"ok": False, "error": "Invalid memory correction path"}, status=404)
            return
        try:
            corrected = correct_memory(
                parts[2],
                content=str(body.get("content", "")),
                reason=str(body.get("reason", "")),
                category=_optional_text(body.get("category")),
                project_id=_optional_text(body.get("project_id")),
                subject_key=_optional_text(body.get("subject_key")),
                structured_data=body.get("structured_data"),
                sensitivity=_optional_text(body.get("sensitivity")),
                confidence_score=body.get("confidence_score", 1.0),
                valid_until=_optional_text(body.get("valid_until")),
                environment=_optional_text(body.get("environment")),
            )
        except MemoryValidationError as error:
            self._send_json({"ok": False, "error": str(error)}, status=400)
            return
        try:
            semantic_index = index_memory(corrected["memory"]["memory_id"])
        except RuntimeError as error:
            semantic_index = {"ok": False, "error": str(error)}
        record_event(
            "memory.corrected",
            {
                "memory_id": corrected["memory"]["memory_id"],
                "superseded_memory_id": corrected["superseded_memory_id"],
                "content_stored_in_audit": False,
            },
        )
        self._send_json({"ok": True, **corrected, "semantic_index": semantic_index})

    def _handle_memory_conflict_resolution(self, path: str, body: dict[str, Any]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 5:
            self._send_json({"ok": False, "error": "Invalid memory conflict path"}, status=404)
            return
        try:
            resolved = resolve_memory_conflict(
                parts[3],
                chosen_memory_id=_optional_text(body.get("chosen_memory_id")),
                keep_both=bool(body.get("keep_both", False)),
            )
        except MemoryValidationError as error:
            self._send_json({"ok": False, "error": str(error)}, status=400)
            return
        record_event(
            "memory.conflict_resolved",
            {
                "conflict_id": parts[3],
                "resolution": resolved["conflict"]["resolution"],
                "content_stored_in_audit": False,
            },
        )
        self._send_json(resolved)

    def _handle_memory_category(self, path: str, body: dict[str, Any]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4 or not isinstance(body.get("enabled"), bool):
            self._send_json({"ok": False, "error": "A category and boolean enabled state are required"}, status=400)
            return
        try:
            categories = set_memory_category_enabled(parts[3], body["enabled"])
        except MemoryValidationError as error:
            self._send_json({"ok": False, "error": str(error)}, status=400)
            return
        record_event(
            "memory.category_changed",
            {"category": parts[3], "enabled": body["enabled"]},
        )
        self._send_json({"ok": True, "categories": categories})

    def _handle_project_root(self, body: dict[str, Any]) -> None:
        project_id = _safe_identifier(body.get("project_id"), "")
        if not project_id:
            self._send_json({"ok": False, "error": "A valid project is required."}, status=400)
            return
        requested = str(body.get("root_path") or "").strip()
        try:
            resolved = _resolve_project_root_registration(project_id, requested)
        except ValueError as error:
            self._send_json({"ok": False, "error": str(error)}, status=400)
            return
        project = set_project_root(project_id, str(resolved) if resolved else None)
        if project is None:
            self._send_json({"ok": False, "error": "Project not found."}, status=404)
            return
        record_event(
            "project.root_changed",
            {
                "project_id": project_id,
                "connected": resolved is not None,
                "root_name": resolved.name if resolved else None,
            },
        )
        self._send_json({"ok": True, "project": project})

    def _handle_approval(self, path: str, body: dict[str, Any]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4 or parts[3] not in {"approve", "reject"}:
            self._send_json({"ok": False, "error": "Invalid approval action"}, status=404)
            return
        approval_id = parts[2]
        decision = "approved" if parts[3] == "approve" else "rejected"
        try:
            approval = decide_approval(
                approval_id,
                decision,
                _bounded_approval_scope(approval_id, body.get("scope", "once")),
            )
        except ValueError as error:
            self._send_json({"ok": False, "error": str(error)}, status=400)
            return
        if approval is None:
            self._send_json({"ok": False, "error": "Approval not found"}, status=404)
            return

        task = get_task(approval["task_id"])
        if decision == "approved" and task is not None:
            result, executed_state = execute_approved_task(task)
            task_state = executed_state.value
        else:
            discarded_proposal = discard_pending_task_action(task)
            task_state = TaskState.CANCELLED.value
            result = _approval_rejection_result(task, discarded_proposal)
            from auris.workflow_engine import mark_workflow_terminal

            if task is not None and get_workflow_run(task["task_id"]) is not None:
                mark_workflow_terminal(task.get("plan") or task, TaskState.CANCELLED, result)
        update_task_state(approval["task_id"], task_state, result)
        if task is not None:
            VOICE_TURNS.finish_task({**(task.get("plan") or task), "state": task_state}, result)
        record_event(
            f"approval.{decision}",
            {
                "approval_id": approval_id,
                "task_id": approval["task_id"],
                "scope": approval["scope"],
                "task_state": task_state,
            },
        )
        self._send_json({"ok": True, "approval": approval, "task": get_task(approval["task_id"])})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'")
        self.end_headers()
        self.wfile.write(data)

    def _establish_session(self, parsed) -> bool:
        bootstrap_code = parse_qs(parsed.query).get("bootstrap_code", [""])[0]
        if bootstrap_code:
            if not BOOTSTRAP_CODES.consume(bootstrap_code):
                self._send_json({"ok": False, "error": "Invalid or expired AURIS bootstrap code."}, status=401)
                return True
            record_event("portal.bootstrap_consumed", {"single_use": True})
            self._send_session_redirect(parsed.path)
            return True

        token = parse_qs(parsed.query).get("access_token", [""])[0]
        if not token:
            return False
        if not access_token_valid(token, _portal_auth()):
            self._send_json({"ok": False, "error": "Invalid AURIS access token."}, status=401)
            return True
        self._send_session_redirect(parsed.path)
        return True

    def _send_session_redirect(self, path: str) -> None:
        self.send_response(303)
        self.send_header("Location", path or "/")
        self.send_header("Set-Cookie", session_cookie_header(_portal_auth()))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def _require_session(self) -> bool:
        if session_cookie_valid(self.headers.get("Cookie", ""), _portal_auth()):
            return True
        self._send_json(
            {
                "ok": False,
                "error": "AURIS portal authentication is required. Open AURIS with the desktop launcher.",
            },
            status=401,
        )
        return False

    def _require_csrf(self) -> bool:
        if csrf_token_valid(self.headers.get("X-AURIS-CSRF", ""), _portal_auth()):
            return True
        self._send_json({"ok": False, "error": "AURIS request token is missing or invalid."}, status=403)
        return False

    def _serve_static(self, path: str) -> None:
        requested = "index.html" if path in {"", "/"} else path.lstrip("/")
        target = (WEB_ROOT / requested).resolve()

        if not target.is_relative_to(WEB_ROOT.resolve()) or not target.exists() or target.is_dir():
            self._send_json({"ok": False, "error": "Not found"}, status=404)
            return

        data = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'")
        self.end_headers()
        self.wfile.write(data)


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    global PORTAL_AUTH, LOCAL_IPC_STATUS
    PORTAL_AUTH = initialize_portal_auth(TOKEN_PATH)
    initialize_database()
    initialize_device_identity()
    expired_repairs = cleanup_expired_test_repairs()
    record_event("repair.expired_cleanup", {"removed": expired_repairs})
    expired_codex = cleanup_expired_codex_proposals()
    record_event("codex_workspace.expired_cleanup", {"removed": expired_codex})
    recovery = recover_incomplete_workflows()
    record_event("workflow.recovery_scan", recovery)
    prime_model_engine(blocking=False, route="fast")
    prime_voice_engine(blocking=True)
    fast_configured = bool(model_status().get("fast", {}).get("configured"))
    fast_warm = wait_for_model_prime(timeout_seconds=12, route="fast")
    prime_model_engine(blocking=False, route="quality")
    quality_warm = (
        False
        if fast_configured
        else wait_for_model_prime(timeout_seconds=25, route="quality")
    )
    record_event(
        "model.startup_prime",
        {
            "fast_configured": fast_configured,
            "fast_warm": fast_warm,
            "quality_warm": quality_warm,
            "quality_priming_in_background": fast_configured,
            "parallel_with_voice": True,
        },
    )
    server = ThreadingHTTPServer((host, port), AurisHandler)
    event_engine = EventEngine(proactive_engine=ProactiveWatchEngine(notifier=lambda message: speak(message, asynchronous=True)))
    ipc_server: LocalIpcServer | None = None
    try:
        ipc_server = LocalIpcServer(PORTAL_AUTH.access_token, _dispatch_local_operation)
        ipc_server.start()
        LOCAL_IPC_STATUS = {
            "connected": True,
            "transport": "authenticated_named_pipe",
            "native_clients": "preferred",
        }
        record_event("ipc.started", {"transport": "authenticated_named_pipe"})
    except (OSError, RuntimeError) as error:
        LOCAL_IPC_STATUS = {
            "connected": False,
            "transport": "authenticated_named_pipe",
            "native_clients": "http_fallback",
            "error": str(error),
        }
        record_event("ipc.start_failed", {"error_type": type(error).__name__})
    event_engine.start()
    print(f"AURIS is running at http://{host}:{port}")
    try:
        server.serve_forever()
    finally:
        event_engine.stop()
        if ipc_server is not None:
            ipc_server.stop()
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AURIS local dashboard server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    run(host=args.host, port=args.port)


def _limit_from_query(query: str, default: int) -> int:
    value = parse_qs(query).get("limit", [str(default)])[0]
    try:
        return max(1, min(int(value), 200))
    except ValueError:
        return default


def _optional_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _platform_status() -> dict[str, Any]:
    tasks = list_tasks(limit=200)
    approvals = list_approvals(status="pending")
    device = collect_system_status()
    desktop = companion_status()
    integrations = productivity_status()
    proactive = watch_dashboard()
    browser = browser_status()
    model = model_status()
    voice = voice_status()
    trust = device_trust_status()
    cloud = cloud_channel_status()
    control = get_control_state()
    registry = capability_registry({
        "backend_online": True, "control": control, "device": trust, "model": model,
        "voice_input": voice, "voice_output": voice, "browser": browser,
        "coding": codex_cli_status(), "outlook": integrations.get("outlook", {}),
        "telephony": integrations.get("telephony", {}), "cloud": cloud,
    })
    return {
        "started_at": STARTED_AT,
        "control": control,
        "portal": {
            "authenticated": True,
            "local_only": True,
            "token_acl_hardened": _portal_auth().acl_hardened,
        },
        "local_ipc": dict(LOCAL_IPC_STATUS),
        "cloud_channel": cloud,
        "device": device,
        "device_trust": trust,
        "model": model,
        "embeddings": embedding_status(),
        "voice": voice,
        "desktop_companion": desktop,
        "integrations": integrations,
        "device_capabilities": len(device_capabilities()),
        "capability_registry": registry,
        "agents": [
            {"name": "Supervisor", "status": "online"},
            {"name": "Policy", "status": "online"},
            {"name": "Memory", "status": "online"},
            {
                "name": "Semantic Retrieval",
                "status": "online" if embedding_status()["connected"] else "not_connected",
            },
            {"name": "Verification", "status": "online"},
            {"name": "Windows Device", "status": "online"},
            {
                "name": "Desktop Companion",
                "status": "online" if desktop["online"] else "not_connected",
            },
            {
                "name": "Productivity Connectors",
                "status": (
                    "online"
                    if any(item["connected"] for item in integrations.values())
                    else "not_connected"
                ),
            },
            {
                "name": "Phone Assistant",
                "status": "online"
                if integrations.get("telephony", {}).get("connected")
                else "deployment_required",
            },
            {"name": "Vision", "status": "online" if model["connected"] else "not_connected"},
            {
                "name": "Browser Automation",
                "status": "online" if browser["runtime_available"] else "not_connected",
            },
            {"name": "File Search", "status": "online"},
            {"name": "Research", "status": "online"},
            {"name": "Proactive Watch Engine", "status": "online"},
            {"name": "Documents and Data", "status": "online"},
            {"name": "Coding Checks", "status": "online"},
            {
                "name": "Model Gateway",
                "status": "online" if model["connected"] else "not_connected",
            },
        ],
        "metrics": {
            "tasks": len(tasks),
            "active_tasks": sum(
                task["state"] in {"created", "planning", "running", "verifying", "awaiting_approval"}
                for task in tasks
            ),
            "pending_approvals": len(approvals),
            "scheduled_events": len(list_scheduled_events(status="scheduled", limit=200)),
            "proactive_watches": sum(item["enabled"] for item in proactive["watches"]),
            "proactive_alerts": len(proactive["alerts"]),
            "browser_worker_connected": bool(browser["connected"]),
        },
    }


def _dispatch_local_operation(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = _perform_local_operation(operation, payload)
    except Exception as error:
        record_event(
            "ipc.request_failed",
            {"operation": operation, "error_type": type(error).__name__},
        )
        return {"ok": False, "error": "The authenticated local operation failed safely."}
    record_event(
        "ipc.request",
        {"operation": operation, "success": bool(response.get("ok"))},
    )
    return response


def _capture_voice(mode: str, timeout_seconds: int, *, private: bool = False) -> dict[str, Any]:
    started = time.monotonic()
    capture = listen_for_wake_word if mode == "wake" else listen_once
    try:
        result = capture(timeout_seconds=timeout_seconds)
    except Exception:
        VOICE_TURNS.captured({"ok": False}, mode=mode, started=started, private=private)
        raise
    turn_id = VOICE_TURNS.captured(result, mode=mode, started=started, private=private)
    return {**result, **({"turn_id": turn_id} if turn_id else {})}


def _perform_local_operation(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    if operation == "status":
        return {"ok": True, "status": _platform_status()}
    if operation == "command":
        command = str(payload.get("command", "")).strip()
        if not command:
            return {"ok": False, "error": "Command is required"}
        context = CommandContext(
            project_id=_optional_text(payload.get("project_id")),
            mode=str(payload.get("mode", "command")),
            private=bool(payload.get("private", False)),
            conversation_id=_safe_identifier(
                payload.get("conversation_id"), "auris-desktop-overlay"
            ),
            voice_turn_id=_optional_text(payload.get("voice_turn_id")),
        )
        return process_command(command[:4000], context)
    if operation == "voice.listen":
        timeout_seconds = _bounded_int(
            payload.get("timeout_seconds"), default=8, minimum=2, maximum=20
        )
        result = _capture_voice("command", timeout_seconds, private=bool(payload.get("private", False)))
        record_event(
            "voice.listened",
            {
                "success": bool(result.get("ok")),
                "language": result.get("language"),
                "confidence": result.get("confidence"),
                "audio_signal_detected": bool(result.get("audio_signal_detected")),
                "peak_audio_level": result.get("peak_audio_level"),
                "transport": "authenticated_named_pipe",
            },
        )
        return {"ok": bool(result.get("ok")), "voice": result}
    if operation == "voice.wake":
        timeout_seconds = _bounded_int(
            payload.get("timeout_seconds"), default=5, minimum=5, maximum=30
        )
        result = _capture_voice("wake", timeout_seconds)
        record_event(
            "voice.wake_listened",
            {
                "success": bool(result.get("ok")),
                "language": result.get("language"),
                "confidence": result.get("confidence"),
                "audio_signal_detected": bool(result.get("audio_signal_detected")),
                "peak_audio_level": result.get("peak_audio_level"),
                "transport": "authenticated_named_pipe",
            },
        )
        return {"ok": bool(result.get("ok")), "voice": result}
    if operation == "voice.interrupt":
        timeout_seconds = _bounded_int(
            payload.get("timeout_seconds"), default=2, minimum=2, maximum=10
        )
        result = listen_for_interrupt(timeout_seconds=timeout_seconds)
        record_event(
            "voice.interruption_listened",
            {
                "success": bool(result.get("ok")),
                "language": result.get("language"),
                "confidence": result.get("confidence"),
                "audio_signal_detected": bool(result.get("audio_signal_detected")),
                "peak_audio_level": result.get("peak_audio_level"),
                "transport": "authenticated_named_pipe",
            },
        )
        return {"ok": bool(result.get("ok")), "voice": result}
    if operation == "voice.speak":
        text = str(payload.get("text", "")).strip()
        if not text:
            return {"ok": False, "error": "Speech text is required"}
        result = speak(
            text[:900],
            rate=_bounded_int(payload.get("rate"), default=0, minimum=-4, maximum=4),
            asynchronous=True,
            voice_turn_id=_optional_text(payload.get("voice_turn_id")),
        )
        return {"ok": bool(result.get("ok")), "voice": result}
    if operation == "voice.stop":
        result = stop_speaking()
        record_event("voice.stopped", {"stopped": result["stopped"]})
        return {"ok": True, "voice": result}
    if operation == "voice.background":
        enabled = payload.get("enabled")
        if not isinstance(enabled, bool):
            return {"ok": False, "error": "A boolean enabled value is required."}
        state = set_background_voice_state(enabled)
        record_event("voice.background_changed", {"enabled": enabled})
        return {"ok": True, "voice": {**voice_status(), **state}}
    if operation == "control.stop":
        stop_speaking()
        state = set_control_state(True, str(payload.get("reason", "Emergency stop activated"))[:300])
        record_event("control.stopped", {"reason": state["reason"]})
        return {"ok": True, "control": state}
    if operation == "control.resume":
        state = set_control_state(False, str(payload.get("reason", "Resumed by Devansh"))[:300])
        record_event("control.resumed", {"reason": state["reason"]})
        return {"ok": True, "control": state}
    if operation == "approval.decide":
        return _decide_local_approval(payload)
    return {"ok": False, "error": "The local IPC operation is not allowlisted."}


def _approval_rejection_result(
    task: dict[str, Any] | None, discarded_proposal: bool
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "message": "Request rejected. No external action ran.",
        "verification": (
            "Confirmed: rejection is persisted, the isolated coding proposal was discarded, and no source file changed."
            if discarded_proposal
            else "Confirmed: rejection is persisted and no external action was executed."
        ),
    }
    if discarded_proposal and task is not None:
        prior = (task.get("result") or {}).get("coding_action") or {}
        proposal = dict(prior.get("proposal") or {})
        proposal["status"] = "rejected"
        result["coding_action"] = {
            **prior,
            "ok": False,
            "operation": (
                "codex_change_rejected"
                if prior.get("operation") == "prepare_codex_workspace_change"
                else "repair_rejected"
            ),
            "approval_required": False,
            "proposal": proposal,
            "source_project_modified": False,
        }
    return result


def _approval_views(status: str | None) -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = []
    for approval in list_approvals(status=status):
        view = dict(approval)
        task = get_task(approval["task_id"])
        action = (task.get("result") or {}).get("coding_action") if task else None
        proposal = action.get("proposal") if isinstance(action, dict) else None
        if isinstance(proposal, dict) and proposal.get("proposal_id"):
            view["repair_proposal"] = proposal
        views.append(view)
    return views


def _bounded_approval_scope(approval_id: str, requested: Any) -> str:
    approval = get_approval(approval_id)
    task = get_task(approval["task_id"]) if approval else None
    action = (task.get("result") or {}).get("coding_action") if task else None
    proposal = action.get("proposal") if isinstance(action, dict) else None
    if isinstance(proposal, dict) and proposal.get("proposal_id"):
        return "once"
    return str(requested)


def _decide_local_approval(payload: dict[str, Any]) -> dict[str, Any]:
    approval_id = str(payload.get("approval_id", ""))
    decision = str(payload.get("decision", ""))
    if decision not in {"approved", "rejected"}:
        return {"ok": False, "error": "The approval decision is invalid."}
    try:
        approval = decide_approval(
            approval_id,
            decision,
            _bounded_approval_scope(approval_id, payload.get("scope", "once")),
        )
    except ValueError as error:
        return {"ok": False, "error": str(error)}
    if approval is None:
        return {"ok": False, "error": "Approval not found"}
    task = get_task(approval["task_id"])
    if decision == "approved" and task is not None:
        result, executed_state = execute_approved_task(task)
        task_state = executed_state.value
    else:
        discarded_proposal = discard_pending_task_action(task)
        task_state = TaskState.CANCELLED.value
        result = _approval_rejection_result(task, discarded_proposal)
        from auris.workflow_engine import mark_workflow_terminal

        if task is not None and get_workflow_run(task["task_id"]) is not None:
            mark_workflow_terminal(task.get("plan") or task, TaskState.CANCELLED, result)
    update_task_state(approval["task_id"], task_state, result)
    if task is not None:
        VOICE_TURNS.finish_task({**(task.get("plan") or task), "state": task_state}, result)
    record_event(
        f"approval.{decision}",
        {
            "approval_id": approval_id,
            "task_id": approval["task_id"],
            "scope": approval["scope"],
            "task_state": task_state,
            "transport": "authenticated_named_pipe",
        },
    )
    return {"ok": True, "approval": approval, "task": get_task(approval["task_id"])}


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(int(value), maximum))
    except (TypeError, ValueError):
        return default


def _safe_identifier(value: Any, default: str) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 120:
        return default
    return "".join(character for character in text if character.isalnum() or character in "-_:") or default


def _resolve_project_root_registration(project_id: str, requested: str) -> Path | None:
    if project_id == "auris-one":
        return ROOT
    if not requested:
        return None
    return validate_project_root(requested)


def _portal_auth() -> PortalAuth:
    if PORTAL_AUTH is None:
        raise RuntimeError("AURIS portal authentication is not initialized.")
    return PORTAL_AUTH


def _public_workflow(workflow: dict[str, Any] | None) -> dict[str, Any] | None:
    if workflow is None:
        return None
    return {key: value for key, value in workflow.items() if key != "command_text"}


if __name__ == "__main__":
    main()
