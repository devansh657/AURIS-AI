# AURIS One Architecture

## Product Decision

AURIS means **Autonomous Understanding and Reasoning Intelligence System**.

The supplied specifications describe a personal AI operating system, not a single chatbot. The durable design is therefore split into a private cloud intelligence plane and permission-controlled device agents.

```text
Voice / Text / Mobile / Web
             |
             v
Private AURIS Portal
             |
             v
Cloud Intelligence Core
  - Gateway and identity
  - Supervisor and model router
  - Research and specialist agents
  - Project memory and durable workflows
  - Policy, verification, audit, observability
             |
       Signed command fabric
             |
     +-------+--------+
     v       v        v
 Windows   Android   Browser
  Agent     Agent     Worker
```

The production Windows agent will use a standard-permission service, outbound encrypted communication, device certificates, signed commands, allowlisted tools, explicit capture indicators, and local emergency stop. It will not expose a public inbound port. A desktop shell will communicate with the service through authenticated local IPC such as Windows named pipes.

## Current Vertical Slice

Release 0.8.7 is a working local-first vertical slice of the future split control plane. The authenticated loopback portal uses a pinned Three.js neural matrix as its primary navigation and state visualization, with factual Windows telemetry explicitly separated from derived and decorative graphics. A deterministic anticipation service derives a bounded personal operations graph from durable projects, tasks, approvals, reminders, typed temporal-memory subjects, assigned agents, observed documents, connector state, and the local device. It scores attention from importance, urgency, consequence, current focus, deadlines, and interruption cost; opportunities remain advisory-only, and Private Session suppresses operational detail. Typed temporal memory tracks ten classes, structured decisions, provenance, confidence, sensitivity, validity, explicit conflicts, and correction history. A standard-user desktop companion supplies the tray, global shortcuts, quick-command overlay, and session-local controls. One server-owned persistent speech-input worker arbitrates bounded microphone sessions for push-to-talk, wake detection, and interruption. Startup does not report ready until input and the selected output provider are warm. A session-locked Kokoro CUDA worker owns neural speech synthesis and pipelines one bounded chunk ahead of playback. Research missions cannot complete until their claim/evidence coverage ledger passes. The coding worker can reproduce one trusted AURIS unittest failure, validate a bounded patch in an isolated worktree or snapshot, and pause on an exact signed diff before source application. The cloud package includes a signed inbound-phone contract whose conversation state is ephemeral and whose durable output is summary-only. Windows project opening and UI Automation retain signed, approval, and observation boundaries.

Implemented now:

- Text commands, native push-to-talk, background wake recognition, and spoken replies.
- Win32 tray presence, global shortcuts, and a DPI-aware command overlay.
- Deterministic action classification outside the conversational layer.
- Structured task plans with dependencies, agents, and success conditions.
- Persistent SQLite tasks, conversations, projects, semantic memory, reminders, approvals, and control state.
- Ten typed temporal memory classes with project/environment scope, explicit contradiction resolution, correction history, sensitivity, expiry, category controls, export, and a private mode that disables persistence.
- Interactive neural subsystem navigation, adaptive GPU particle quality, full-screen focus, Ctrl+K access, and factual CPU/RAM/GPU/storage/power telemetry.
- Evidence-backed operations graph, attention and interruption model, Focus Mode batching, opportunity radar, daily intelligence, and evening debrief, all without autonomous commitments or silent external-context retrieval.
- Three-tier response routing across deterministic instant intents, a low-stakes Qwen 2.5 1.5B conversational model, and the Gemma 3 4B quality and multimodal model. The fast route and neural voice warm before readiness while the quality route primes in the background; both use bounded contexts and two-hour residency.
- Sensitive-action approval records and critical-action reauthentication flags.
- Emergency stop that blocks new commands.
- Installed-app discovery and verified open, close, focus, media, folder, registered-project, browser, exact-text typing, and approved benign named-control actions.
- A local authenticated command fabric with stable device identity, per-user HMAC key, typed short-lived envelopes, fixed permission scopes, durable nonce claims, revocation, and replay rejection.
- Authenticated Windows named-pipe IPC for native clients using a purpose-derived transport key and size-bounded JSON messages; loopback HTTP remains only for the browser portal and native recovery.
- Current-user Windows DPAPI wrapping plus a per-user ACL for the local device command key.
- A tested FastAPI cloud command contract with one-time enrolment, pinned Ed25519 device certificates, device-signed outbound polling and acknowledgements, cloud-signed typed envelopes, durable leasing, and replay protection.
- Read-only file, document, data, screen, selected-project analysis, and multi-cycle public-web research workers.
- Trusted AURIS Python unittest repair with isolated validation, exact signed diff approval, source-preimage binding, post-apply verification, and rollback.
- A provider-neutral call policy plus Twilio ConversationRelay adapter for disclosed AI answering, safe message handling, configured-number handoff, and summary-only call records.
- Verification statements and append-only JSONL audit events.
- Visible task, device, agent, memory, approval, event, and audit views.
- Per-install portal secret, CSRF protection, single-use browser bootstrap, and hardened local token ACL.

Not represented as complete:

- Production cloud deployment, identity-aware portal login, mutual TLS, PostgreSQL, or a managed remote queue. The cloud command API and HTTPS edge contract are tested locally with temporary certificates, but no external endpoint or credential is configured.
- General cloud connectors. Classic Outlook mailbox/calendar/contact and locally synced OneDrive read paths are implemented on this laptop; provider APIs and remote-only files remain unavailable.
- Live telephony. The webhook, WebSocket, handoff, and summary contracts pass against a test cloud service, but no provider account, purchased number, compliance profile, public TLS/WSS endpoint, secret, or owner transfer number is configured.
- Durable distributed workflow engine and encrypted device command queue.
- The local foundation now persists workflow attempts and checkpoints, recovers interrupted read-only work after restart, and refuses automatic replay for sensitive or write operations. Distributed queue ownership and cross-device recovery remain production gates.
- Production-signed Windows service installation, Android release signing/enrolment, and live mobile approvals. The .NET service boundary, foreground health gate, Android companion build, and native named-pipe contract are tested, but the active laptop agent still runs in the standard-user portal process and no mobile device is paired.
- General browser DOM/form automation, a general untrusted-project execution sandbox, autonomous multi-file feature development, and independent remote verification. Registered project analysis does not imply permission to execute or modify that project's code; repair remains limited to the trusted AURIS Python unittest profile and one exact approved diff.
- Echo-aware simultaneous capture/playback and true full-duplex conversation. Persistent streaming input, hypothesis reporting, endpointing, priority wake preemption, and sentence-streamed output with bounded prefetch are implemented.

## Security Invariants

1. The policy classifier runs before task execution.
2. Prohibited work is blocked before tools run.
3. Sensitive work pauses for explicit approval.
4. Critical work requires approval and reauthentication.
5. Unavailable workers never report false success.
6. Secrets are not stored in task, memory, or audit records.
7. The emergency stop prevents new commands until explicitly resumed.
8. P3 and P4 capabilities stay disabled until the security and evaluation gates exist.

## Production Path

The preferred first production topology is a managed private cloud deployment: identity-aware access, containerized API and worker services, PostgreSQL, object storage, a durable queue, a secret vault, and either an IoT-style device channel or private WebSocket gateway. The local database maps cleanly to PostgreSQL tables, while the current runtime boundary maps to durable workflow workers.
