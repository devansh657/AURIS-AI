# AURIS One

**AURIS** means **Autonomous Understanding and Reasoning Intelligence System**.

AURIS One is a supervised Windows personal-AI operating-system foundation for Devansh. This repository contains the current **0.8.34 development source**, not a finished or production-ready assistant. Dashboard, background voice, and desktop-overlay commands share an authenticated backend. The latest changes add a deterministic capability inventory and more precise microphone diagnostics. New projects can be delegated to the installed, authenticated Codex engine in filtered isolated snapshots, with exact signed diffs and one-time approval before application. Phone and cloud contracts still need live deployment.

## Current Readiness

- Real text-to-PC acceptance on 2026-10-07 passed Notepad opening, minimizing, and restoring, plus Desktop folder and exact-content note creation, using signed action receipts and independent state/file checks.
- **Owner voice acceptance is failing.** The spoken request `Hey AURIS, open Notepad` has not been successfully accepted and executed in the current room tests. Audio reaches the recognizer, but recent attempts failed recognition or wake-name checks. Automated speech tests do not prove the owner's microphone path works.
- `/api/capabilities` and the planner/UI share bounded capability definitions. An installed adapter or available connection is not an acceptance result or permission grant.
- General PC/browser automation, real-room interruption, production calls, cloud/mobile enrolment, and broad autonomous coding quality still have open acceptance gates.
- Historical implementation and readiness documents describe their recorded versions; do not treat older passing tests as current availability.

See the [source snapshot](docs/SOURCE_SNAPSHOT_0834.md), [setup boundaries](docs/SETUP.md), and [project roadmap](docs/PROJECT_ROADMAP.md). Local credentials, histories, device keys, recordings, generated documents, model weights, and downloaded runtimes are excluded from Git.

## Implementation Inventory

The following describes implemented code paths and their boundaries, not a claim that every feature has passed owner acceptance.

- Say `Hey AURIS, open Notepad` as one utterance, or say the wake phrase and then your command. Local Whisper tiny.en uses WebRTC voice activity detection, a 600 ms speech endpoint, and paired transcription with competing names to distinguish the wake name from background speech. Only the final accepted transcript is executed; decoder scores are explicitly uncalibrated, not identity verification. Wake detection and repeated wake-only phrases produce no spoken acknowledgement; passive "Yes Devansh, I am listening" boilerplate is suppressed at the shared output engine. Physical-room accuracy still depends on your microphone, pronunciation, and environment and is not guaranteed by synthetic tests.
- Push-to-talk and interruption signal a local cancellation event instead of reloading the recognizer. Speech uses native cancelable Windows WAV playback, with one locked voice provider, inherited owner-only temporary-directory permissions, and per-reply latency measurements. Microphone audio is not uploaded or stored.
- `Build a Python app called Budget that tracks expenses and exports CSV` creates a managed project and, when Codex is signed in, automatically delegates its full brief to the real coding engine. `Scaffold a Python project` requests only a starter. Without Codex sign-in, a custom build is explicitly partial, not complete.
- `Use Codex to add CSV export in this project` works on the selected AURIS or AURIS-managed root. Long missions return promptly, continue in the background, and publish their outcome in Missions and the exact diff in Approvals. Applying a proposal revalidates source preimages, checks final hashes, and restores exact original bytes if validation fails. Existing edits are copied rather than reset; credential-named files and detected hard-coded secrets are omitted from snapshots.
- Coding uses the installed, authenticated Codex engine rather than copying this chat's model weights. No sandbox bypass, dependency installation permission, unrestricted PC control, or guarantee of arbitrary-task success is implied. Codex account usage applies. Browser/file/voice operations retain their existing bounded policies.
- Compound PC directives such as `open Spotify and play music` or `open YouTube in Brave then maximize Brave` resolve only when every clause is a supported bounded action. Each step is separately signed and verified, and execution stops after the first failure.
- Explicit build directives create real managed artifacts: code-project directories, Word documents, PDFs, Markdown files, PowerPoint decks, Excel workbooks, and sourced research reports. AURIS records paths, package/static checks, sizes, and SHA-256 hashes; generated project code is not silently executed.
- Normal-phone and WhatsApp audio-call language routes to the Communications agent, binds only the exact contact label and channel into one-time approval, re-resolves the request after approval, and refuses to report success unless a call state is observed. On this laptop WhatsApp Desktop and live telephony are currently unconfigured, so real calls remain unavailable rather than simulated.
- The inbound phone-assistant contract identifies itself as AI, converses through an authenticated Twilio ConversationRelay adapter, detects urgency/protected data/human requests, hands off only to a configured owner number, and retains a summary rather than raw audio or transcript. A dedicated provider number and production HTTPS/WSS deployment are still required.
- Durable project-scoped browser application state records completed and remaining redacted checkpoints, supports approval-bound continuation only before a final control, revalidates the exact state and source task after approval, and sends uncertain final-control outcomes to manual review instead of replaying them.
- Explicit named-browser commands can open validated public HTTP(S) destinations and run Google or YouTube searches in an installed browser. DNS is rechecked immediately before launch; local/private targets, credentials, sensitive URL keys, and nonstandard ports are blocked.
- Targeted Spotify playback launches or focuses Spotify before emitting the Windows play/pause media key. The focus and key event are verified, but the remote playback session is not independently observed and is never claimed as such.
- Isolated Microsoft Edge browser automation for HTTP(S) navigation, search, accessibility-first page inspection, approved exact-field filling, approved exact-control invocation, and one-time-approved three-to-five-step missions. Every mission is prevalidated before navigation, binds its redacted step plan into one signed scope, verifies exact field read-back and final page-state change, and fails closed before later steps. Page content is labelled untrusted; private/DNS-resolved local targets, credential-bearing URLs, secrets, downloads, and consequential controls are refused; Chromium sandboxing remains enabled.
- Voice-, text-, and dashboard-controlled proactive watches for seven predictive metrics, with durable evaluation state, transition deduplication, cooldowns, evidence-bound local alerts, an inspectable alert ledger, private-mode suppression, and no automatic action authority.
- Project-scoped predictive intelligence with seven required metrics, durable evidence IDs, explicit uncertainty, private-mode suppression, no automatic action, and empirical mission-failure probability gated behind 20 terminal outcomes.
- Reproducible operational world-model snapshots with factual provenance, privacy suppression, bounded impact tracing, stale-state rejection, explicit preconditions/unknowns, and what-if transitions that always report `executed: false`.
- Causal intervention reports with a small explicit DAG, direct transition identification, mediator paths, confounders, action/no-action/alternative counterfactuals, and downstream effects withheld when they are not identifiable.
- Evidence-bound decision analysis with weighted alternatives, traceable supporting/opposing evidence, hypothesis status, explicit unknowns, four-case scenario utility, counterfactual comparison, recommendation withholding, durable case/outcome records, and empirical Brier scoring that does not claim calibration before 20 observed forecasts.
- Optional five-role council for difficult decisions: Solver A, Solver B, Critic, Judge, and Evidence Verifier. It uses a fixed five-call budget, degrades without replacing deterministic analysis, labels role separation separately from true model independence, and withholds unsupported judge recommendations.
- Structured outcome learning records expected and actual results, their difference, root cause, lesson, and confidence change. Option success rates remain hidden until five observations and never change security policy or model weights automatically.

- Persistent local Windows speech-input broker for push-to-talk, wake detection, live hypotheses, endpointing, and priority interruption without storing or uploading microphone audio.
- Standard-user Windows tray companion with microphone, privacy, automation, command-centre, and emergency controls.
- Global quick-command overlay with text execution, push-to-talk, verification evidence, and approval/rejection controls.
- Global `Ctrl+Space` overlay, `Ctrl+Shift+J` push-to-talk, and `Ctrl+Shift+X` emergency-stop shortcuts.
- Optional local wake mode for "AURIS", "Hey AURIS", "Okay AURIS", and "OK AURIS" phrases in a per-user background companion that remains active when the dashboard is closed. The verified local speech model runs offline in an isolated environment; microphone audio stays in bounded memory and is discarded after each request. Windows System.Speech remains an explicitly reported fallback if local model startup fails. A valid wake opens a silent command window without the repeated spoken acknowledgement.
- Spoken responses through one persistent local AURIS Vale Kokoro CUDA voice, with sentiment-aware pacing and pauses, spoken-markup cleanup, interruption, and no browser voice fallback.
- Common voice exchanges answer through a deterministic instant kernel; low-stakes conversation uses a resident Qwen 2.5 1.5B fast route, while reasoning, research, coding, factual, and consequential work remains on Gemma 3 4B. Both local models stay resident for two hours and the interface identifies the route and generation time.
- Long spoken responses use bounded sentence and clause chunks; the next chunk is synthesized while the current one plays, reducing first-audio latency without allowing prefetched speech after cancellation.
- Startup now blocks readiness until the selected voice, persistent input worker, and fast conversational model are warm; the stronger reasoning model primes in the background. Kokoro, Piper, and SAPI are evaluated only at startup, and the first available voice provider is locked for the session.
- Spoken-response cancellation from the command dock or emergency stop, plus local acoustic "stop", "AURIS stop", "be quiet", and "cancel response" phrases during background voice replies.
- Private local conversation through the same safety-routed Ollama models without durable history or retrieved memory.
- Durable conversation history for standard sessions; private mode does not persist messages.
- Local semantic memory indexing and project-scoped retrieval using `nomic-embed-text`.
- Provider-independent gateway for Ollama or an explicitly configured compatible endpoint.
- Discover installed applications from the Windows Start Menu, registry app paths, and known user installs.
- Authenticate every supported Windows action through a short-lived signed local device envelope with fixed permissions, expiry, durable nonce claims, revocation, and replay rejection.
- Route native tray and voice operations over authenticated Windows named-pipe IPC with strict JSON messages and a loopback recovery path.
- Protect the device command key at rest with current-user Windows DPAPI and a Devansh-only file ACL.
- Open, close, and focus discovered applications by voice or text, including Spotify, Office, Edge, Discord, and VS Code when installed.
- Invoke one exact visible benign control in a named application after one-time approval, using Windows UI Automation and a bounded memory-only UIA state observer; protected applications and consequential controls are blocked.
- User-folder access for Desktop, Documents, Downloads, Pictures, Music, Videos, home, and the AURIS workspace, plus signed creation directly in those roots or inside one existing direct child folder.
- Create new UTF-8 TXT or Markdown notes in approved roots or one existing direct child folder with content-digest binding, exact post-write verification, and no overwrite of different existing content.
- Append one bounded, non-secret line to an existing UTF-8 TXT or Markdown note with signed preimage/text binding, duplicate suppression, atomic replacement, exact read-back, and automatic rollback on verification failure.
- Rename bounded files or folders, and copy or move regular files up to 100 MB between approved roots or one existing direct child folder, with exact signed paths, SHA-256 verification, link/depth refusal, and no destination overwrite.
- Move one exact allowlisted document or media file up to 100 MB from an approved user location to the Windows Recycle Bin after one-time approval, with signed preimage binding and original-path observation; permanent deletion remains blocked.
- Open named documents, images, audio, and video from approved user locations; executable and script formats are blocked, and completion requires a visible window title containing the exact filename.
- Minimize, maximize, and restore discovered application windows by voice or text, with completion determined from the observed Win32 iconic, zoomed, or visible state.
- Windows volume and media playback controls.
- Explicit screen understanding through a temporary desktop capture analysed by the local multimodal model and deleted immediately afterward.
- Safe HTTPS navigation and web-search handoff to the visible default browser.
- Bounded, read-only filename and literal content search across approved user folders and the AURIS workspace; content scanning skips links, unsupported formats, and files over 1 MB, caps each mission at 20 MB, and persists no matched text.
- Rapid, deep, exhaustive, and continuous research planning with bounded public-web retrieval, SSRF protections, URL/content deduplication, primary-source classification, counterevidence queries, validated claim citations, provenance, and a definition-of-done coverage ledger.
- Inbound AI phone-assistant core with explicit identity/transcription disclosure, natural bounded replies, importance detection, caller-requested or safety-triggered handoff, masked caller identity, and summary-only persistence. Signed Twilio HTTPS/WebSocket contracts pass locally; a real number remains deployment-gated.
- Read-only local summarisation for text, Markdown, JSON, CSV, DOCX, PDF, and XLSX documents, with structured extractors and size limits.
- Selected-project analysis with registered local roots, generated-directory pruning, symlink refusal, bounded source mapping, structured manifest parsing, instruction/test discovery, reproducible snapshot IDs, and review signals without executing project code.
- Selected or uniquely named registered projects can be opened through the signed local command fabric; success requires File Explorer to report the exact resolved root.
- Explicitly trusted AURIS test execution with a fixed argument list, captured output, and verified process exit codes; arbitrary registered projects cannot silently execute code.
- Supervised `fix this failing test` repair for the trusted AURIS Python unittest profile: reproduce first, diagnose from bounded evidence, try at most two model patches in a Git worktree or content snapshot, block tests/manifests/credentials/links and newly introduced execution primitives, pass targeted and complete isolated tests, show an exact signed diff, pause for one-time approval, then pass post-apply tests and hashes or restore exact preimages.
- Durable local reminders with timezone-aware parsing, restart persistence, proactive spoken delivery, audit events, and cancellation controls.
- Authorised classic Outlook mailbox, calendar, and contact lookup with bounded read-only scans; returned account items are omitted from durable task history and private sessions remain fully ephemeral.
- Outlook draft creation plus approval-gated sending with exact recipient, subject, and body disclosure; remote delivery is never claimed as independently verified.
- Read-only filename search across locally synced OneDrive roots.
- Approval-resumed Unicode typing into a named, running Windows app, with exact-text disclosure, target focus verification, one-time execution, and secret-data blocking.
- Read-only folder listing and Windows system telemetry.
- Structured supervisor missions, deterministic policy, approvals, verification, audit, memory, private mode, and emergency stop.
- Durable mission checkpoints with bounded retries, restart recovery for read-only work, non-replay guarantees for interrupted writes, and deterministic verification reports.
- Per-install local portal authentication, HttpOnly SameSite session cookies, CSRF protection, and 30-second single-use browser bootstrap codes with replay rejection.
- AURIS Spatial Intelligence interface with live core states, transcript, mission control, device topology, context, and responsive layouts.
- Version-aware launch recovery replaces an obsolete AURIS runtime before opening the portal, and the cinematic boot layer independently fails open after eight seconds if browser JavaScript is delayed.
- Operational Daily, Projects, Research, Engineering, and Documents workspaces with live task evidence and explicit connection boundaries.
- Personal operations intelligence connecting current projects, missions, approvals, reminders, temporal-memory subjects, assigned agents, observed documents, applications, and the local device without inventing missing email, call, calendar, travel, or financial data.
- Deterministic six-level attention scoring with four delivery classes, evidence IDs, advisory-only opportunity detection, Focus Mode batching, and separate daily and evening evidence briefs.
- Tested cloud command-plane and outbound edge contracts with one-time enrolment, pinned Ed25519 certificates, signed polling, typed signed commands, durable leasing, acknowledgements, revocation, and replay protection; no external endpoint is configured.

AURIS operates with the signed-in Windows user's permissions. No automatic privilege elevation, arbitrary command execution, hidden microphone capture, security modification, permanent deletion, unattended payments, or protected-process termination is enabled.

## Launch the Desktop Experience

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\launch_auris.ps1
```

This starts the local portal, voice core, and desktop companion when necessary, then opens AURIS as a standalone Microsoft Edge application window without placing the long-lived portal token in Edge's command line.

Install the per-user desktop launcher and background startup shortcut:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_windows_shell.ps1
```

Stop the verified AURIS portal, background voice, and desktop companion processes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop_auris.ps1
```

Rebuild the isolated Kokoro CUDA voice runtime and integrity-checked model assets when needed. Piper remains an offline startup fallback and has its own isolated setup script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_voice_gpu.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_voice.ps1
```

Rebuild the isolated local speech-input runtime and pinned, integrity-checked English model:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_speech.ps1
```

The setup downloads packages and model assets once. Runtime microphone audio is never uploaded. Utterances are limited to 30 seconds and longer speech is rejected rather than executing a truncated command. Background wake mode is not speaker authentication; sensitive operations retain exact one-time approvals. Live voice status identifies the actual microphone, provider, fallback reason, and interpreting phase.

Example commands:

```text
AURIS, open Notepad
AURIS, open Calculator
AURIS, open Spotify
AURIS, close Spotify
AURIS, switch to Word
AURIS, volume up
AURIS, next track
AURIS, open my Documents
AURIS, describe my screen
AURIS, open github.com/openai
AURIS, search the web for local voice assistants
AURIS, find file blueprint
AURIS, research deeply whether passkeys reduce phishing risk compared with passwords
AURIS, summarize document blueprint-notes.md
AURIS, analyse this project
AURIS, open this project
AURIS, click "File" in Notepad
AURIS, run the tests
AURIS, remind me in 10 minutes to stretch
AURIS, search my email for dissertation
AURIS, show my calendar for today
AURIS, find my contact named Ada Lovelace
AURIS, find blueprint in my OneDrive
AURIS, draft email to person@example.com subject Update saying The report is ready.
AURIS, type "Hello Devansh" into Notepad
AURIS, show system health
AURIS, remember that I prefer concise reports
AURIS, stop
AURIS, resume operations
```

## Verify

```powershell
C:\Users\dmodi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest discover -s tests -v
.\.cloud-venv\Scripts\python.exe -m unittest tests.test_cloud_command_api -v
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
```

## Model Gateway

The launcher defaults to local Ollama with `qwen2.5:1.5b` as the tightly scoped fast conversational route and `gemma3:4b` as the quality and multimodal route. A compatible cloud endpoint can be selected without storing credentials in the repository:

```powershell
$env:AURIS_MODEL_PROVIDER = "openai_compatible"
$env:AURIS_MODEL_ENDPOINT = "https://provider.example/v1/chat/completions"
$env:AURIS_MODEL_NAME = "configured-model"
$env:AURIS_MODEL_API_KEY = "set-in-the-launching-session"
```

## Current Boundary

The local core can converse, retain standard-session history, plan, stream speech input and sentence-batched output, remember, analyse and open registered local project roots, run evidence-led research, inspect an explicitly requested temporary screen capture, enforce policy, perform signed and verified Windows actions, invoke approved benign UI controls, rank evidence-backed attention, trace the local operations graph, produce daily and evening briefs, read an authorised classic Outlook mailbox/calendar, create drafts, gate email sending, and search locally synced OneDrive roots. Certificate-authenticated cloud command and signed inbound-telephony contracts are implemented and tested but remain disconnected. A real phone number requires a provider account, compliance/onboarding, trusted public TLS/WSS deployment, provider secrets, and Devansh's transfer number. The Android companion builds and tests as a verified debug APK but is not installed, production-signed, or enrolled because no Android device or cloud endpoint is connected. Production mTLS/PostgreSQL deployment, an Authenticode-signed Windows service, sandboxed source modification, remote visible-control execution, echo-aware simultaneous capture/playback, and true full-duplex conversation remain behind their respective authorization or production gates. See `docs/IMPLEMENTATION_STATUS.md` and `docs/MASTER_REQUIREMENT_AUDIT.md` for exact status.
