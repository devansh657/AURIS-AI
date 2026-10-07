from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_VERSION = 1


@dataclass(frozen=True)
class Capability:
    id: str
    label: str
    adapter: str
    task_types: tuple[str, ...]
    scope: str
    required_permissions: tuple[str, ...]
    verifier: str
    limitations: tuple[str, ...]
    probe: str
    evidence: str | None = None
    evidence_scope: str | None = None


CAPABILITIES = (
    Capability("conversation", "Conversation", "model_gateway", ("general_assistance",),
               "Local or explicitly configured model replies; replies do not execute PC actions.",
               ("policy:read_only",), "Model response and route, not real-world factual correctness",
               ("Model availability does not prove answer accuracy.",), "model"),
    Capability("voice_input", "Voice input", "speech_input_worker", (),
               "Offline wake-plus-command and push-to-talk with memory-only audio.",
               ("microphone:consent",), "Capture signal, accepted transcript, and correlated voice turn",
               ("Owner room-speech acceptance is pending.", "Wake recognition is not speaker authentication."),
               "voice_input", "docs/voice-action-readiness-0833.md", "Synthetic acoustics; owner speech unverified"),
    Capability("voice_output", "Spoken replies", "voice", (),
               "One session-locked output provider, normalized markup, and cancelable playback.",
               ("audio:playback",), "Native playback handoff; owner confirms audibility and naturalness",
               ("Full-duplex echo cancellation is not implemented.",), "voice_output",
               "docs/voice-action-readiness-0833.md", "Suppression and native handoff; not owner naturalness sign-off"),
    Capability("windows_actions", "Windows apps and files", "device_agent", ("computer_operation", "project_operation"),
               "Discovered app/window control and bounded files in approved roots or one direct child.",
               ("launch_app", "focus_app", "create_folder", "create_text_file"),
               "Signed nonce-claimed action plus exact window/path/content observation",
               ("Not arbitrary application or unrestricted filesystem control.", "No silent overwrite or permanent deletion.",
                "Media-key emission does not verify a requested song played."), "device",
               "docs/voice-action-readiness-0833.md", "Live text: Notepad open/minimize/restore and Desktop folder/note"),
    Capability("windows_interaction", "Approved app interaction", "ui_automation", ("computer_interaction",),
               "Exact approved benign UI controls or disclosed text in a named application.",
               ("type_text", "invoke_control", "approval:exact_action"), "Foreground/control and post-action observation",
               ("Protected apps, secret text, and consequential controls are refused.",), "device"),
    Capability("screen_context", "Screen understanding", "screen_context", ("screen_understanding",),
               "Explicit temporary screen capture analyzed by the configured multimodal model.",
               ("screen:explicit_consent",), "Capture cleanup and model observation",
               ("Model connection alone does not prove visual accuracy or model vision support.",), "model"),
    Capability("browser_workflows", "Isolated browser workflows", "browser_agent", ("browser_workflow", "application_state"),
               "Public navigation, accessibility inspection, exact approved fields/controls and bounded missions.",
               ("browser_navigate", "browser_inspect", "browser_fill", "browser_click", "browser_workflow"),
               "Per-step read-back/page observation and signed mission checkpoints",
               ("Authenticated accounts, uploads/downloads, and general site adaptation remain incomplete.",
                "An installed runtime is not a connected worker or tested website."), "browser"),
    Capability("file_search", "File search", "file_agent", ("file_workflow",),
               "Bounded read-only filename and literal-content searches in approved locations.",
               ("policy:read_only",), "Observed matching paths; content is not retained",
               ("Not a persistent index or unrestricted document editing engine.",), "local"),
    Capability("documents", "Document reading", "document_agent", ("document_workflow",),
               "Bounded supported-format extraction and summarization.", ("policy:read_only",),
               "Extractor results and source-file identity",
               ("Generated summaries require content-quality evaluation.",), "model"),
    Capability("work_products", "Projects and office artifacts", "work_product_agent", ("work_product",),
               "Create code and office work products under managed roots without overwriting existing items.",
               ("policy:controlled_write",), "Hashes, package/static checks, and signed diff when delegated",
               ("Package validity is not visual layout or behavioral acceptance.",
                "Generated project code is not silently executed."), "local"),
    Capability("coding_analysis", "Project analysis and trusted checks", "coding_agent", ("coding",),
               "Bounded registered-root analysis and explicitly trusted AURIS test profiles.",
               ("policy:registered_root",), "Snapshot evidence or fixed-profile process exit",
               ("Arbitrary registered-project execution is disabled.",), "local"),
    Capability("coding_build", "Coding missions", "codex_workspace_agent", (),
               "Codex operates in filtered isolation; exact signed source diffs require one-time approval.",
               ("policy:managed_root", "approval:signed_diff"), "Independent static/preimage/hash checks; worker tests labelled separately",
               ("Requires installed authenticated Codex and an authorized project root.",
                "Independent general-project dynamic verification is pending."), "coding"),
    Capability("research", "Sourced research", "research_agent", ("research",),
               "Bounded public-web evidence gathering, counterevidence, claims and coverage ledger.",
               ("network:public_only",), "Validated source IDs, provenance and coverage checks",
               ("Citation structure does not prove every claim is true; external retrieval may fail.",), "model"),
    Capability("memory", "Scoped memory", "memory_service", ("memory",),
               "Typed project-scoped memories, correction, expiry, export and deletion; private mode isolated.",
               ("policy:scoped_memory",), "Stored versions and retrieval provenance",
               ("Long-horizon retrieval quality and cross-device synchronization are pending.",), "local"),
    Capability("local_productivity", "Reminders and local intelligence", "event_engine",
               ("reminder", "proactive_watch", "daily_brief", "operations_intelligence", "decision_analysis"),
               "Durable local reminders and evidence-backed advisory attention/decision workflows.",
               ("policy:local_workflow",), "Durable events, evidence IDs and deduplicated delivery",
               ("Advisory predictions do not authorize automatic PC or external actions.",), "local"),
    Capability("outlook", "Outlook operations", "communications_agent", ("communications",),
               "Authorized classic Outlook read/draft operations and exact approval-gated sends.",
               ("account:authorization", "approval:external_send"), "Provider item/draft state; remote delivery not independently verified",
               ("Installed Outlook does not establish an authorized working profile.",), "outlook"),
    Capability("phone_assistant", "Phone assistant", "telephony_agent", (),
               "Disclosed-AI inbound call contract, configured owner handoff and summary-only records.",
               ("account:telephony", "deployment:trusted_https_wss"), "Live provider call and transfer state",
               ("Local contracts do not provision a public phone number or prove live calls.",
                "Consumer WhatsApp audio calling is a separate unavailable integration."), "telephony"),
    Capability("outbound_calls", "Outbound phone and WhatsApp calls", "communications_agent", (),
               "Recognize exact contact/channel call requests and report unavailable execution honestly.",
               ("account:communications", "approval:exact_recipient"), "Observed live call state, not a generated reply",
               ("Outbound normal-phone and WhatsApp call adapters are not enabled.",), "outbound_calls"),
    Capability("cloud_access", "Cloud and mobile continuity", "cloud_channel", (),
               "Signed outbound cloud-command contracts and Android companion build.",
               ("device:enrollment", "deployment:production_identity"), "Live enrolled device and remote acknowledgment",
               ("Android build is not installation/enrollment; production deployment is pending.",), "cloud"),
    Capability("system_status", "System diagnostics", "system_status", ("system_status", "control"),
               "Local health, policy stop/resume and explicit unavailable metrics.", ("policy:read_only",),
               "Actual system observations and control state", ("No automatic administrator privilege.",), "local"),
)


def capabilities_for_task(task_type: str, *, coding_operation: str | None = None, communication_operation: str | None = None) -> list[Capability]:
    if task_type == "coding" and coding_operation == "codex_workspace":
        return [item for item in CAPABILITIES if item.id == "coding_build"]
    if task_type == "communications" and communication_operation in {"start_call", "phone_status"}:
        wanted = "outbound_calls" if communication_operation == "start_call" else "phone_assistant"
        return [item for item in CAPABILITIES if item.id == wanted]
    return [item for item in CAPABILITIES if task_type in item.task_types]


def _availability(item: Capability, observations: dict[str, Any]) -> tuple[str, str]:
    if not (ROOT / "auris" / f"{item.adapter}.py").is_file():
        return "not_installed", "The declared adapter is missing."
    if item.probe == "outbound_calls":
        return "not_connected", "Call intents are recognized, but no outbound call executor is enabled."
    if item.probe == "local":
        if observations.get("backend_online") is True:
            return "available", "Adapter is installed; the exact request still requires validation and verification."
        return "unknown", "Backend availability has not been observed."
    probe = observations.get(item.probe)
    if not isinstance(probe, dict):
        return "unknown", "No current connection observation is available."
    if item.probe == "device":
        if probe.get("revoked") is True:
            return "blocked", "Device authorization is revoked."
        if probe.get("trust_state") != "local_hmac":
            return "not_connected", "A trusted local device identity is required."
        needed = {p for p in item.required_permissions if ":" not in p}
        permissions = probe.get("permissions")
        if not isinstance(permissions, list) or not needed.issubset(set(permissions)):
            return "limited", "Some required device scopes are unavailable."
        return "available", "Trusted local action fabric; exact targets and results must still be observed."
    if item.probe == "voice_input":
        if probe.get("input_worker_online") is not True:
            return "not_connected", "Speech worker is not online."
        health = probe.get("input_observation") or {}
        age = health.get("age_seconds")
        if isinstance(age, (int, float)) and 0 <= age <= 30 and (health.get("signal_state") in {"no_frames", "overflow"} or (health.get("signal_state") == "weak_signal" and health.get("mode") == "command")):
            return "check_input", "Recent capture has weak, stalled, or overflowing input; microphone acceptance is required."
        return "available", "Speech worker is online; this is not proof it understands the owner's voice."
    if item.probe == "voice_output":
        if probe.get("provider") in {"local_kokoro", "local_piper"}:
            return ("available", "One neural provider is online; physical audibility still needs confirmation.") if probe.get("neural_worker_online") is True else ("not_connected", "The selected neural output worker is not online.")
        return "limited", "Only a declared operating-system voice fallback is selected."
    if item.probe == "browser":
        if probe.get("runtime_available") is not True:
            return "not_installed", "The isolated browser runtime is unavailable."
        return ("available", "Browser worker is connected within its bounded scope.") if probe.get("connected") is True else ("on_demand", "Runtime is installed; the browser worker is not connected yet.")
    if item.probe == "coding":
        if probe.get("available") is not True:
            return "not_installed", "Coding engine is not installed."
        return ("available", "Coding engine sign-in verified; project authorization remains required.") if probe.get("authenticated") is True else ("configuration_required", "Coding engine sign-in is required.")
    if item.probe in {"telephony", "cloud"}:
        return ("configured_unverified", "Connection is reported, but live end-to-end acceptance is still required.") if probe.get("connected") is True else ("configuration_required", "No live provider/device deployment is connected.")
    if probe.get("connected") is True:
        return "available", "Connection is reported; exact requests and outputs require verification."
    return "not_connected", "The required model or authorized account is not connected."


def capability_registry(observations: dict[str, Any] | None = None) -> dict[str, Any]:
    observations = observations or {}
    entries = []
    for item in CAPABILITIES:
        state, reason = _availability(item, observations)
        if (observations.get("control") or {}).get("stopped") is True and item.id != "system_status":
            state, reason = "paused", "Emergency stop is active; no new command may execute."
        entry = asdict(item)
        entry.pop("probe")
        entry.update(state=state, reason=reason, installed=(ROOT / "auris" / f"{item.adapter}.py").is_file(),
                     acceptance={"record": item.evidence, "scope": item.evidence_scope,
                                 "kind": "recorded_bounded_acceptance" if item.evidence else "see_capability_audit",
                                 "current_runtime_retested": False})
        entry.pop("evidence")
        entry.pop("evidence_scope")
        entries.append(entry)
    return {"schema_version": REGISTRY_VERSION, "source": "deterministic_adapter_registry",
            "availability_is_acceptance": False, "permission_authority": False,
            "capabilities": entries}


def capability_summary(registry: dict[str, Any]) -> str:
    entries = registry["capabilities"]
    available = [item["label"] for item in entries if item["state"] == "available"]
    unavailable = [item["label"] for item in entries if item["state"] not in {"available", "on_demand"}]
    parts = ["Available within bounded scopes: " + ", ".join(available) + "."] if available else ["No capabilities have current available-state evidence."]
    if unavailable:
        parts.append("Not ready or still requires checks: " + ", ".join(unavailable) + ".")
    parts.append("Availability is not proof every task succeeds; actions still require policy checks and result verification.")
    return " ".join(parts)


def collect_capability_observations() -> dict[str, Any]:
    from auris.browser_agent import browser_status
    from auris.cloud_channel import cloud_channel_status
    from auris.codex_workspace_agent import codex_cli_status
    from auris.communications_agent import productivity_status
    from auris.database import get_control_state
    from auris.device_fabric import device_trust_status
    from auris.model_gateway import model_status
    from auris.voice import voice_status

    integrations = productivity_status()
    voice = voice_status()
    return {"backend_online": True, "control": get_control_state(), "model": model_status(),
            "device": device_trust_status() if os.name == "nt" else {},
            "voice_input": voice, "voice_output": voice, "browser": browser_status(),
            "coding": codex_cli_status(), "outlook": integrations.get("outlook", {}),
            "telephony": integrations.get("telephony", {}), "cloud": cloud_channel_status()}
