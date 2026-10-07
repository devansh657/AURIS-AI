# AURIS Project Roadmap

Planning snapshot: 2026-10-07, based on the recorded 0.8.33 evidence. This is a
work breakdown, not a fresh runtime check or a declaration of production readiness.

## Product Goal

AURIS means Autonomous Understanding and Reasoning Intelligence System.

Devansh explains a goal by voice or text. AURIS understands the request, selects
appropriate tools, performs authorized work, observes the result, recovers safely
when possible, and reports what actually happened. The cinematic interface must
show those real operations, not substitute animation for functionality.

The scope includes laptop control, browser work, coding, research, documents,
personal productivity, memory, phone handling, and cloud/mobile continuity.
Universal task coverage and a 100% future success rate are not achievable release
claims. Supported workflows must have measured acceptance and explicit boundaries.

## Evidence And Status

- `[x]` means the precisely worded task already has recorded evidence. It does not
  mean the surrounding milestone is complete or that it was retested today.
- `[ ]` means implementation, configuration, broader verification, or user
  acceptance is still required; the task text identifies which.
- A milestone passes only after its acceptance gate passes in the stated
  environment. Unit tests, fixtures, live text commands, and real speech are
  separate evidence classes.
- The [requirement baseline](AURIS_REQUIREMENT_BASELINE.md) remains authoritative.
  This roadmap does not discard requirements from the preserved specifications.
- Latest local evidence: [0.8.33 readiness](voice-action-readiness-0833.md).
  Earlier capability evidence: [implementation status](IMPLEMENTATION_STATUS.md),
  [requirement audit](MASTER_REQUIREMENT_AUDIT.md), and
  [release matrix](release-matrix.md). Historical documents contain older tests
  and providers; the newer readiness report governs the current voice baseline.

Recorded baseline: 437 Python tests passed, 13 cloud contracts passed separately,
and bounded live text-to-PC acceptance passed for Notepad opening/minimizing/
restoring and Desktop folder/note creation. Owner microphone acceptance is still
missing. Telephone and production cross-device integrations are not connected.

## Release Stages

| Stage | Milestone scope | User-visible result |
| --- | --- | --- |
| Reliable Local Alpha | M01-M04, relevant M11 UI, continuous M12 checks | Real microphone commands reliably perform the agreed basic laptop workflows |
| Productive Local Beta | M05-M08, relevant M11 UI, continuous M12 checks | Explain a coding, research, document, or personal workflow and receive a verified useful result |
| Connected Assistant | M09-M10 and their M11/M12 gates | Live disclosed-AI calls and securely enrolled mobile/cloud access |
| Hardened Release | M12 and all selected release-scope gates | Repeatable installation, recovery, security review, and sustained real-user acceptance |

The full requested specification remains incomplete while any required capability
is deferred or weakly verified, even if a narrower local release passes.

## M01 - Stable Foundation And Honest Capability Inventory

Priority: P0. Status: integrated/tested locally; broader reliability gate pending.
Dependencies: none.

- [x] M01-T01: Route dashboard, background voice, and desktop-overlay commands
  through one authenticated backend, including the shared coding-mission slot.
- [x] M01-T02: Expose bounded voice diagnostics, actual task outcomes, and signed
  action receipts without treating generated chat replies as PC execution.
- [ ] M01-T03: Build a machine-readable capability registry containing installed
  adapter, supported scope, connection state, required permission, verifier, and
  last acceptance evidence. Make planner and UI consume the same registry.
- [ ] M01-T04: Extend startup/recovery acceptance across cold launch, restart,
  sleep/resume, microphone removal, model failure, port conflicts, and backend loss.
- [ ] M01-T05: Reconcile historical status documents with the current registry;
  prevent older test results from implying current live availability.
- [ ] M01-T06: Provide actionable diagnostics and bounded cancellation for every
  stalled command; never leave an unexplained indefinite loading state.

Gate: each failure scenario produces a truthful state and safe recovery path;
all visible controls work or are disabled with a concrete reason. Restart cannot
duplicate a write or external action. Save a repeatable acceptance report.

## M02 - Reliable Voice And Natural Conversation

Priority: P0. Status: implemented and synthetically tested; owner acceptance open.
Dependencies: M01.

- [x] M02-T01: Keep local Whisper/VAD input warm, support wake-plus-command and
  push-to-talk, and correlate accepted speech with execution and output.
- [x] M02-T02: Use one session-locked speech provider; suppress repeated wake
  acknowledgements and normalize markup before synthesis.
- [ ] M02-T03: Run Devansh's real microphone suite: wake/no-wake, normal speech,
  accent, quiet/loud delivery, background media, pauses, and command corrections.
- [ ] M02-T04: Diagnose actual capture, transcription, routing, execution, and
  output failures separately; adjust microphone/VAD/wake handling from evidence.
- [ ] M02-T05: Validate speaker audibility, natural phrasing, sentiment-sensitive
  delivery, numbers, symbols, and spoken summaries with Devansh's sign-off.
- [ ] M02-T06: Validate interruption in the real room; implement echo-aware
  full-duplex turn-taking before claiming simultaneous listening and speaking.
- [ ] M02-T07: Measure end-of-user-speech to verified result and first audible
  reply; optimize each stage without routing consequential work to a weaker model.
- [ ] M02-T08: Add stronger confirmation/re-authentication for sensitive spoken
  requests. A recognized wake phrase is not proof of speaker identity.

Gate: at least 40 agreed real spoken commands across multiple sessions, including
negative/background cases. Initial target: >=95% observed completion of supported
benign commands, no unintended device actions in the background test, and every
miss or block explained. Report sample counts, failures, p50/p95 latency, and
room conditions. Initial performance targets, not current guarantees: p95 <=3 s
from speech end to a simple local result and <=3 s to fast first audible reply.
Quality/research latency is measured separately; native playback handoff is not
audibility evidence. Do not retain raw ambient microphone audio.

## M03 - Grounded Command Understanding And Task Orchestration

Priority: P0. Status: deterministic routing and bounded workflows exist; general
goal-to-workflow execution remains incomplete. Dependencies: M01-M02.

- [x] M03-T01: Retain current typed intents, signed actions, compound bounded
  commands, and recent verified benign app follow-ups.
- [ ] M03-T02: Map natural paraphrases to registry-backed structured tools;
  validate tool arguments outside the model and reject invented capabilities.
- [ ] M03-T03: Expand contextual references to files, projects, browser tabs, and
  active tasks with explicit scope, expiry, ambiguity checks, and private isolation.
- [ ] M03-T04: Turn multi-step goals into bounded plans with preconditions,
  checkpoints, required approvals, time budgets, and success criteria.
- [ ] M03-T05: Ask one concise clarification when the intended target or action
  is genuinely ambiguous; otherwise execute supported authorized work directly.
- [ ] M03-T06: Add safe replanning from observed failures, bounded retries for
  idempotent operations, and manual review for uncertain write/external outcomes.
- [ ] M03-T07: Support pause, cancel, status, and resume with durable task state;
  do not reinterpret task-status queries as fresh device instructions.

Gate: a paraphrase and multi-step benchmark correctly routes supported commands,
clarifies ambiguity, reports unsupported work, and never claims a chat reply is
an executed action. Injected tool errors must stop unsafe later steps.

## M04 - Dependable Windows And Application Automation

Priority: P0. Status: bounded live-tested adapters, not universal desktop control.
Dependencies: M01-M03.

- [x] M04-T01: Preserve the 0.8.33 signed live Notepad open/minimize/restore and
  Desktop folder/note acceptance, including independent state/file checks.
- [ ] M04-T02: Build and run a workflow matrix for Devansh's installed apps:
  browsers, Spotify, Office, Explorer, editor, and other explicitly selected apps.
- [ ] M04-T03: Expand practical nested file workflows under explicitly authorized
  roots, including search, organize, edit, rename, copy, move, and recoverable removal.
  Preserve preimage checks, no silent overwrite, and rollback where applicable.
- [ ] M04-T04: Expand UI Automation and explicit screen observation into
  multi-application workflows with verified focus and post-action state.
- [ ] M04-T05: Add approved visual fallback when accessibility data is absent;
  never guess a consequential control from screen coordinates alone.
- [ ] M04-T06: Add independently observed media state where supported. A Spotify
  focus plus media key must not be represented as proof the requested song played.
- [ ] M04-T07: Exercise missing apps, multiple windows, minimized apps, stale
  focus, protected paths, permission denials, and interrupted writes.

Gate: an agreed set of at least 20 real laptop workflows has observable results
and explicit failure handling. Include folder/note work, app/window control, a
real requested media workflow, and a multi-app task; no fixture-only acceptance.

## M05 - Browser And Internet Task Execution

Priority: P1. Status: bounded isolated browser prototype and named-browser launch.
Dependencies: M03-M04.

- [ ] M05-T01: Revalidate current public navigation, search, exact-field filling,
  approved control invocation, checkpoints, and stop-on-failure behavior.
- [ ] M05-T02: Add adaptive page plans using accessibility observations, stable
  targets, bounded visual fallback, and per-step result verification.
- [ ] M05-T03: Design explicitly authorized account sessions; keep credentials
  out of model context, summaries, screenshots, and durable task history.
- [ ] M05-T04: Add controlled download/upload workflows with approved paths,
  file validation, scope-bound disclosures, and observable completion.
- [ ] M05-T05: Handle redirects, popups, changed layouts, expired sessions,
  MFA/CAPTCHA handoff, and partial submissions without bypassing protections.
- [ ] M05-T06: Retain exact previews and approvals for messages, submissions,
  purchases, and other consequential actions; uncertain outcomes are not replayed.
- [ ] M05-T07: Independently test prompt injection, private-network requests,
  malicious pages, and secret leakage across the expanded browser capabilities.

Gate: complete agreed read-only and benign form workflows on actual chosen sites,
not only the local acceptance page; demonstrate recovery and refusal paths.
Authenticated-site actions require explicit account authorization and a separate gate.

## M06 - Autonomous Coding From Explained Logic

Priority: P1. Status: real Codex bridge exists; broad project-quality gate open.
Dependencies: M03 and M12 sandbox/security work.

- [x] M06-T01: Delegate managed project briefs to the authenticated coding engine
  in filtered snapshots, show signed diffs, require exact one-time apply approval,
  revalidate source hashes, and preserve existing user edits.
- [ ] M06-T02: Improve brief extraction: behavior, inputs/outputs, constraints,
  target platform, acceptance tests, and only necessary clarifications.
- [ ] M06-T03: Complete requirements -> implementation -> test -> repair ->
  review -> authorized apply -> launch/handoff for selected supported stacks.
- [ ] M06-T04: Provision independently verified isolated build/test profiles for
  broader projects; do not execute arbitrary generated shell on the main laptop.
- [ ] M06-T05: Handle approved dependency installation, test budgets, logs,
  cancellation, conflicts, secrets, and reproducible environment setup.
- [ ] M06-T06: Add an independent acceptance verifier that checks the user's
  requested behavior, not just the coding worker's self-written tests.
- [ ] M06-T07: Benchmark a new Python utility, a working web app, and a change
  to an existing project, including a deliberately failing test and safe rollback.

Gate: Devansh explains the logic and gets a runnable, tested project with a clear
location/launch path and limitations. Existing-project work preserves unrelated
edits. Worker-reported tests and independent tests are labelled separately.
This is tool-enabled engineering, not copying model weights or retraining AURIS.

## M07 - Research, Documents, And Data Work Products

Priority: P1. Status: bounded research, extraction, and artifact generation exist;
end-to-end quality acceptance remains open. Dependencies: M03, M05 where needed.

- [ ] M07-T01: Expand research planning with primary-source validation, date and
  claim checking, counterevidence, citation integrity, and explicit uncertainty.
- [ ] M07-T02: Evaluate actual answer quality and coverage independently; add
  authorized specialist sources, multilingual retrieval, and durable research watches.
- [ ] M07-T03: Complete DOCX/PDF/PPTX/XLSX creation and revision workflows;
  preserve originals and respect user templates and output locations.
- [ ] M07-T04: Add render-inspect-repair loops, spreadsheet recalculation, page
  layout checks, and exact output verification beyond package validity and hashes.
- [ ] M07-T05: Build useful data-analysis workflows with provenance, validated
  calculations, charts, and clear assumptions rather than model-only arithmetic.
- [ ] M07-T06: Benchmark a sourced research report, polished Word report/PDF,
  presentation, and recalculated workbook from Devansh's spoken or typed brief.

Gate: open each real output, inspect its contents/layout/calculations, validate
citations against supporting sources, and obtain user acceptance. A generated
filename or correct ZIP container alone cannot pass this milestone.

## M08 - Memory, Personal Productivity, And Proactive Workflows

Priority: P1. Status: local memory/reminders/operations prototypes exist; external
connectors and long-horizon evaluation are partial. Dependencies: M03, M07.

- [ ] M08-T01: Evaluate project-scoped retrieval, preferences, corrections,
  expiry, contradictions, export/deletion, and private-mode leakage over time.
- [ ] M08-T02: Improve durable recurring workflows and reminders with timezones,
  restart recovery, deduplication, and explicit delegated authority.
- [ ] M08-T03: Connect only authorized email/calendar/contact/cloud-file accounts;
  verify actual provider state and keep exact preview/approval for external sends.
- [ ] M08-T04: Add meeting-note and follow-up workflows with explicit consent,
  reliable source association, and verified calendar/document results.
- [ ] M08-T05: Expand daily briefs, priorities, goal portfolio, and quiet
  evidence-backed proactive alerts; no repeated irrelevant spoken notifications.
- [ ] M08-T06: Evaluate outcome learning and prioritization without automatically
  changing model weights, granting permissions, or asserting unsupported confidence.
- [ ] M08-T07: Add secure backup/restore for approved durable memory and workflows.

Gate: agreed routines survive restart and timezone changes without duplicate
actions; remembered preferences improve later work; private sessions do not leak
into retrieval; every connected account is explicitly authorized and live tested.

## M09 - Calls And Personal Communications

Priority: P2; provider/deployment dependent. Status: local contracts tested, no live
AURIS line. Dependencies: M02-M03, M10 public deployment, M12 security review.

- [ ] M09-T01: Select and provision the dedicated AURIS provider number; verify
  account eligibility, onboarding, costs, region, and supported transfer behavior.
- [ ] M09-T02: Deploy authenticated public HTTPS/WSS endpoints, managed secrets,
  callback validation, health monitoring, and abuse/rate/cost limits.
- [ ] M09-T03: Configure and verify the owner transfer destination privately.
  Previously supplied personal numbers are not themselves a live AURIS number.
- [ ] M09-T04: Live test answering with AI disclosure, concise natural dialogue,
  caller-requested importance, human requests, urgent cases, and transfer.
- [ ] M09-T05: Handle busy/no-answer/disconnected transfer, fallback messaging,
  manual takeover, summary-only persistence, and owner notification delivery.
- [ ] M09-T06: Evaluate outbound calling with exact recipient and purpose approval;
  confirm actual call state rather than claiming success from model text.
- [ ] M09-T07: Evaluate WhatsApp calling separately against currently supported
  services and an authorized linked device. Report unavailable if unsupported;
  do not assume normal telephony enables consumer WhatsApp audio calls.
- [ ] M09-T08: Review applicable disclosure/consent/privacy obligations for the
  chosen jurisdictions; no raw call recording by default or autonomous commitments.

Gate: real consented callers can reach a published configured AURIS number,
converse, request handoff, and receive the configured outcome; Devansh receives
an accurate summary. Include live failed-transfer and abuse-limit exercises.
Credential configuration and number purchase require Devansh's account access.

## M10 - Cloud Core And Cross-Device Continuity

Priority: P2; infrastructure/device dependent. Status: cloud security contracts
and Android debug build tested, production endpoints/devices disconnected.
Dependencies: M01-M03 and continuous M12 checks.

- [ ] M10-T01: Deploy private portal/authentication, model gateway, durable jobs,
  memory, events, verification, policy, and audit as supported cloud services.
- [ ] M10-T02: Configure production datastore, managed secrets, certificates,
  backups, monitoring, cost budgets, and bounded worker ownership/leases.
- [ ] M10-T03: Enroll the laptop through authenticated outbound transport with
  device identity, revocation, replay defense, and least-privilege commands.
- [ ] M10-T04: Keep local voice/basic PC capabilities available during cloud loss;
  reconcile state without duplicating previously uncertain actions.
- [ ] M10-T05: Production-sign, install, and securely enroll the Android companion
  on an actual authorized device; verify voice, camera, approvals, and notifications.
- [ ] M10-T06: Validate cross-device task status, memory privacy, handoff, remote
  emergency stop, offline recovery, and lost-device revocation.
- [ ] M10-T07: Add ambient/location/multi-screen features only with explicit
  consent, bounded collection, and device-specific acceptance.

Gate: an enrolled phone can initiate an authorized task that the laptop executes
and verifies, with status/approval continuity and safe network-loss recovery.
No public unauthenticated laptop-control endpoint or automatic administrator access.

## M11 - Cinematic But Operational User Interface

Priority: P0-P2 alongside the corresponding capability, not a cosmetic final pass.
Status: moving responsive Three.js interface tested; workflow completeness open.
Dependencies: each screen's real backend milestone.

- [x] M11-T01: Preserve nonblank animated desktop/mobile neural scenes, projection
  controls, responsive dock, and real/derived/decorative distinctions.
- [ ] M11-T02: Map the four supplied reference directions into a coherent UI:
  cognitive lattice, neural core, synaptic command map, and thinking-array views.
- [ ] M11-T03: Bind listening, interpreting, planning, acting, verifying,
  speaking, approval, partial, offline, and failed states to real events.
- [ ] M11-T04: Connect every mission, research, coding, document, device, memory,
  call, and settings control or disable it with the exact unmet prerequisite.
- [ ] M11-T05: Prioritize the microphone, directive entry, current task, result,
  approval, and emergency stop; keep decorative graphics from obscuring work.
- [ ] M11-T06: Add meaningful progress, action evidence, output links, recovery
  choices, microphone settings, and visible latency/connection diagnostics.
- [ ] M11-T07: Verify desktop/tablet/mobile, keyboard access, long text, contrast,
  reduced motion, GPU resource budgets, screenshots, and canvas-pixel checks.

Gate: Devansh can complete each supported workflow from the interface, recognize
why blocked work is blocked, inspect evidence, and reach outputs. No inert buttons,
fabricated agent counts/telemetry, misleading online status, or stuck boot overlay.

## M12 - Security, Reliability, Evaluation, And Release

Priority: P0 throughout; final release gate after the selected milestone scope.
Status: local security checks pass; production readiness remains false.
Dependencies: all capabilities included in a release.

- [x] M12-T01: Preserve deterministic policy, signed/replay-resistant device
  actions, exact approvals, private mode, authenticated IPC, and emergency stop.
- [ ] M12-T02: Extend threat models and adversarial tests for every new adapter:
  prompt injection, authorization errors, secret leakage, stale state, and replay.
- [ ] M12-T03: Add independent evaluators for command correctness, research
  quality, coding behavior, document quality, voice latency, and failure honesty.
- [ ] M12-T04: Exercise backup/restore, crashes, resource exhaustion, offline
  operation, interrupted writes, partial external actions, and version migration.
- [ ] M12-T05: Produce repeatable installer/update/uninstall and rollback paths;
  obtain production signing/identity required by the full specification.
- [ ] M12-T06: Complete independent security review and real cross-device recovery
  exercises before declaring production cloud/device readiness.
- [ ] M12-T07: Run a seven-day local acceptance period with at least 30 agreed
  mixed workflows, record regressions and measured success/latency, and resolve
  release-blocking silent failures, false-success reports, and unsafe behavior.
- [ ] M12-T08: Publish supported capabilities, verified environments, limitations,
  costs, recovery instructions, and evidence; obtain Devansh's release sign-off.

Gate: the release-scope suites and real user workflows pass; no critical safety,
privacy, silent-failure, or fabricated-success issue remains. Report observed
success rates and uncertainty, never a universal future guarantee.

## Advanced Research Track

The requested learning levels describe enabling disciplines, not 13 finished
product modules. Track them against deliverables rather than claiming that listing
algorithms, neural networks, RAG, or agents makes AURIS capable.

| Requested levels | Main delivery milestones |
| --- | --- |
| 1: Python, algorithms, data structures, APIs, databases, Git | M01, M06, M12 |
| 2-3: ML, deep learning, transformers, LLMs, inference, quantization | M02-M03, M06; benchmark improvements before adoption |
| 4-5: RAG, hybrid/graph retrieval, memory, structured outputs, tools | M03, M07-M08 |
| 6: planning, orchestration, MCP, workflows, events | M03, M06, M08, M10 |
| 7: vision, speech, computer use, browser automation | M02, M04-M05, M09-M11 |
| 8: distributed/cloud/cross-device/realtime systems | M09-M10 |
| 9-10: security, evaluation, verification, calibrated uncertainty | Every milestone, led by M12 |
| 11-12: causal reasoning, simulations, outcome learning, councils, prediction | M08 plus the research tasks below |
| 13: novel architectures and quantum integration | Research tasks below; no current quantum capability claimed |

- [ ] R01: Compare independent model/provider councils against a single model on
  fixed tasks, measuring quality, independence, cost, and latency.
- [ ] R02: Evaluate learned forecasting and world/domain models with real held-out
  outcomes; distinguish causal identification from suggestive correlations.
- [ ] R03: Prototype evidence-backed reusable skills and simulation adapters
  without allowing self-generated skills to bypass policy or approval.
- [ ] R04: Explore novel architectures only with reproducible baselines and
  measurable gains in user tasks, not branding claims.
- [ ] R05: Assess a justified quantum-related task and an actual backend/service
  if relevant; do not imply quantum hardware makes general assistance superior.

These tasks do not block a useful local alpha/beta, but deferred required research
capabilities remain visibly incomplete in the full-specification audit.

## Next Execution Batch

1. M01-T03/M01-T04: establish the current capability truth and failure/recovery matrix.
2. M02-T03/M02-T04: run Devansh's real microphone commands and fix observed failures.
3. M03-T02/M03-T04: connect natural language goals to validated tools and checkpoints.
4. M04-T02/M04-T03: accept real app/file workflows, not only synthetic/text fixtures.
5. M11-T03/M11-T04: expose those real states and functional controls as each lands.
6. M12-T02/M12-T03: run regression/security/independent checks for the same batch.

Next advance through M05-M08 for useful work products. Prepare M09/M10 only as
credentials, infrastructure, and devices become available; their absence must not
delay fixing local voice-to-PC behavior. M11 and M12 remain continuous workstreams.

## Task Completion Record

For each task, record: task ID, scope, implementation location, acceptance command
or procedure, environment/device, observed result, evidence location, limitations,
security checks, and user acceptance when required. Change the checklist only
when that precisely stated work is evidenced. Do not infer delivery dates from
the milestone numbering; estimate each batch after its dependencies are verified.
