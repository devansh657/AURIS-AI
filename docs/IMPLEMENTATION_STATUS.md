# AURIS Implementation Status

| Capability | State | Evidence |
| --- | --- | --- |
| Text commands | Tested | Command API and browser workflow |
| Conversational model | Live tested | Three-tier local routing: deterministic instant kernel, Qwen 2.5 1.5B for allowlisted low-stakes dialogue, Gemma 3 4B for quality reasoning and vision, plus a configurable compatible gateway |
| Conversation history | Tested | Durable standard-session messages; private mode bypasses persistence |
| Private execution | Tested | Commands, results, tasks, messages, and approvals remain ephemeral; audit retains redacted event metadata only |
| Streaming speech input | Tested | One server-owned persistent Windows System.Speech worker serves push-to-talk, wake, and interruption over authenticated IPC; hypotheses and endpoint state are memory-only; a two-second priority listen completed in 2.81 seconds while preempting an active wake window |
| Native desktop companion | Tested | Standard-user Win32 tray icon and DPI-aware quick-command overlay with live heartbeat |
| Cinematic neural command centre | Live tested except screenshot | Pinned Three.js WebGL engine with 420/980/2,200-node quality modes, layered synaptic graph, GPU particle pulses, agent orbits, voice-reactive states, subsystem navigation, Ctrl+K access, full-screen focus, reduced-motion handling, FPS reporting, in-scene nonblank pixel diagnostics, explicit real/derived/decorative labels, and an eight-second boot fail-open. Authenticated asset and runtime acceptance passed; the in-app browser denied loopback screenshot automation |
| Windows telemetry twin | Live tested | Real Ryzen CPU load/model, physical memory load/capacity, RTX 3050 load/VRAM/temperature/power/clock, storage, uptime, AC/battery, local-interface, and bounded process names; unavailable metrics remain labelled unavailable |
| Global desktop controls | Tested | All three shortcuts registered; `Ctrl+Space` opened the overlay and `Ctrl+Shift+X` paused the live core; push-to-talk routes to the tested native recognizer |
| Local wake word | Tested | Singleton per-user background companion, sign-in startup, durable on/off control, live heartbeat, phonetic AURIS aliases, single-utterance wake-plus-command grammar, and explicit recognition-miss state. Authenticated extraction-to-device task `b1763e2f-cd88-484f-9a72-a442898e6a18` passed; live room-voice retest remains user-observed. |
| Spoken replies | Live latency tested | Single AURIS Vale Kokoro CUDA broker with blocking startup warm-up, bounded sentence/clause playback, one-chunk concurrent prefetch, and 1.576-second measured first audio; cancellation invalidates prefetched audio; browser speech disabled; startup-only Piper then SAPI fallback |
| Conversational response latency | Live tested | Common intents bypass models; a safety classifier permits only low-stakes dialogue onto a 2048-context fast model and keeps factual, reasoning, research, coding, medical, legal, financial, security, and emergency content on the 4096-context quality route. Both models stay resident for two hours. Private live acceptance measured 20 ms instant, 769 ms end-to-end fast dialogue, and 4.066 seconds end-to-end Gemma reasoning |
| Spoken-response interruption | Implemented | Command-dock and emergency-stop cancellation plus priority-preemptive, confidence-gated local acoustic control grammar during background replies; user phrase validation remains |
| Screen understanding | Tested | Explicit 1536x864 temporary capture, local Gemma 3 analysis, audit events, and confirmed deletion |
| Browser automation | Live tested prototype | Persistent isolated, sandbox-enabled Playwright Edge profile; HTTP(S) navigation/search; accessibility-first inspection; exact single actions; and one-time-approved three-to-five-step navigate/fill/invoke missions. Missions prevalidate all steps, bind a digest-redacted plan into a signed scope/nonce, preserve exact approved text, verify every checkpoint, and stop before later steps after failure. Project-scoped application state can safely continue only pre-control failures after approval and exact state/source revalidation; uncertain final controls require manual review. Named-browser public URL/search targeting adds DNS/private-target protection. Adaptive site planning, authenticated accounts, uploads/downloads, visual fallback, and independent adversarial-site evaluation remain pending. |
| File search | Live tested prototype | Bounded filename and on-demand literal content search across approved roots; content mode fairly budgets all roots, scans only allowlisted UTF-8 text/source formats up to 1 MB each and 20 MB per mission, skips links and root escapes, and persists only paths, match counts, and first line numbers. Live task `0385d44b-a102-4f31-b5ad-3fb4cccf7c43` found the exact Documents acceptance note after five-root scanning without persisting matched text. Persistent indexing and editing existing files remain pending. |
| Bounded file creation | Live tested prototype | Signed folder and UTF-8 TXT/Markdown note creation in approved roots or one existing non-link direct child folder; exact paths and content digests are verified, traversal/deeper nesting is refused, and different existing files are never overwritten. Nested AURIS 0.8.16 task `5f437ac9-c8b3-4540-8ce1-0378200899e0` passed continuous-utterance extraction, signed authorization, nonce claim, and exact nested-path observation on the real Desktop. |
| Controlled note append | Live tested prototype | Existing direct-child UTF-8 TXT/Markdown notes only; signed preimage and append digests, 1 MB/1,000-character limits, protected-data refusal, duplicate-final-line suppression, atomic mode-preserving replacement, exact read-back, and automatic preimage rollback. Live task `46d5e484-a31b-4b10-a184-e1ed259e6af7` verified the exact final line and idempotent duplicate suppression through AURIS 0.8.14. |
| OneDrive local sync | Tested | One authorised synced root detected and searched read-only; provider API access and remote-only files remain pending |
| Document and data reading | Tested | Read-only bounded TXT/MD/JSON/CSV/DOCX/PDF/XLSX extraction and local summarisation |
| Project workspaces | Tested | Eight project contexts with task, completion, memory, event, activity, active-context state, and durable optional local-root registration; AURIS root is fixed to the running installation |
| Registered-project opening | Tested | Selected or uniquely named projects resolve to one registered root, traverse the signed local command fabric, revalidate against current registration, launch through a fixed PowerShell argument list, and require exact File Explorer observation; live authenticated-IPC acceptance passed on 0.8.2 |
| Research Intelligence workspace | Tested | Real campaign/source/claim metrics, source provenance, claim status and evidence links, counterevidence and duplicate counts, branch coverage, definition-of-done state, and preserved source URLs |
| Engineering workspace | Tested | Selected registered root, reproducible snapshot ID, extension/component maps, structured manifest details, instruction and test discovery, review signals, verified run ledger, and explicit execution boundary |
| Document workspace | Tested | Supported extraction fabric, real operation history, filename launcher, preserved-original status, and disabled unconnected write worker |
| Daily Command Centre | Tested | Primary and supporting objectives, ranked priorities, reminders, approvals, connector and device state, deadlines, risks, evidence-backed opportunities, suggested action, and explicit unloaded external context |
| Personal operations intelligence | Live-tested local prototype | Bounded graph across projects, tasks, approvals, reminders, temporal-memory subjects, agents, observed documents, applications, and the device; deterministic six-level attention with four delivery classes; Focus Mode batching; opportunity radar; evening debrief; provenance and evidence IDs; restart-safe predictive watches; local spoken notification; sensitive-memory masking and Private Session suppression. External communications, travel, finance, contracts, external-signal watches, and remote notification delivery remain unconnected |
| Decision intelligence | Live-tested prototype | Deterministic hypothesis evaluation with evidence/provenance, epistemic states, weighted options, four-case scenario utility, counterfactual deltas, recommendation withholding, a budget-aware Solver A/Solver B/Critic/Judge/Evidence Verifier council, structured expected-versus-actual outcomes, root cause and lessons, sample-gated calibration, a reproducible operational world model, and bounded `do(action)` intervention analysis. The responsive council is role-separated on one fast model and explicitly does not claim independent-model consensus; downstream causal effects remain non-identified and learned/domain simulation adapters remain unconnected |
| Predictive intelligence | Live-tested prototype | Seven evidence-bound project forecast families over durable tasks, events, approvals, assignments, and outcomes. Operational indicators are deterministic scores, not probabilities; mission-failure probability requires at least 20 terminal outcomes and includes a Wilson 95% interval. Every signal is advisory-only with provenance, evidence IDs, method, and uncertainty; private mode suppresses forecasts and no automatic action is permitted. External predictors, learned forecasting, calibration across independent domains, and autonomous intervention remain unconnected |
| Proactive watch engine | Live-tested prototype | Voice-, text-, and dashboard-managed metric watches persist across restarts, evaluate no faster than once per minute, require evidence before alerting, deduplicate active conditions, enforce cooldowns, retain an inspectable alert ledger, and suppress state in Private Session. Alerts are local and advisory-only; no tool execution authority is attached. External-signal monitors, mobile delivery, and long-horizon policy evaluation remain unconnected |
| Coding worker | Tested prototype | Bounded symlink-safe selected-project analysis plus trusted AURIS Python unittest repair: reproduce first, bounded two-attempt diagnosis/patch loop, Git worktree or content-snapshot isolation, targeted/full tests, signed exact diff, one-time approval, preimage validation, atomic apply, post-apply tests/hashes, and exact rollback. Arbitrary registered-project execution and unrestricted editing remain disabled |
| Installed-app discovery | Tested | Start Menu, registry app paths, and known user installs; 111 apps found on the development laptop |
| Application control | Live tested prototype | Open, close, focus, minimize, maximize, and restore intents for discovered apps; general public destination/search launch in an exact named installed browser; post-launch process/window verification; Win32 window-state observation; and protected-process/private-network deny rules. Live 0.8.27 acceptance observed Brave opening YouTube, a public domain, and an exact YouTube search. |
| Approved Windows UI Automation | Tested | Exact benign named controls only, one-time approval, signed app/control digest, protected-app and consequential-control refusal, fixed stdin-only helper, approved UIA patterns, and bounded memory-only UIA state observation; live Notepad acceptance passed on 0.8.3 |
| Signed local device envelopes | Tested | Exact typed envelope schema, stable device identity, per-user HMAC key, twenty-five fixed permission scopes including bounded app/window, file, UI-control, browser single actions, and digest-bound browser missions, 5-120 second expiry, durable nonce claims, tamper rejection, wrong-device rejection, revocation, and live replay rejection |
| Native authenticated IPC | Tested | Tray/client operations prefer a Windows named pipe with secret-derived transport authentication, strict size-bounded JSON, exact operation allowlist, concurrent requests, and HTTP recovery fallback; live command passed with HTTP auth deliberately disabled |
| Device credential protection | Tested | Device command key migrated from plaintext hex to current-user Windows DPAPI wrapping plus a Devansh-only file ACL; key material is never exposed by status or audit APIs |
| User-folder access | Live tested prototype | Home plus approved Desktop, Documents, Downloads, Pictures, Music, Videos, and AURIS workspace roots; create/rename/copy/move support roots or one existing direct child, recycle remains direct-child bounded, and regular-file transfer is limited to 100 MB with hash verification and no overwrite. Live 0.8.17 nested create/copy/rename/move acceptance passed with signatures, nonces, scopes, exact content, and hashes verified. |
| Recoverable file removal | Live tested prototype | One direct-child allowlisted document/media file up to 100 MB can be sent to the Windows Recycle Bin only after one-time approval. The signed envelope binds the exact path and preimage hash; links, executables, stale preimages, arbitrary paths, folders, and permanent deletion are refused. Live task `a5b3365f-8df7-4c1b-9b61-10ca0f074203` paused for approve-once authority, consumed a signed nonce, invoked `Microsoft.VisualBasic.FileIO.RecycleBin`, and observed the exact source path absent. |
| Safe file opening | Live tested prototype | Allowlisted document/image/audio/video files can open from one approved root; executables, scripts, links, nested paths, and arbitrary locations are refused, and completion requires an exact filename match in a visible window title. When the Windows `.txt` association proved incomplete, AURIS switched to a fixed Notepad argument list; live task `f6817564-85a2-4ad2-861c-2514a31a8b22` then observed the exact acceptance filename in a visible window. |
| Media control | Live tested prototype | Fixed Windows volume/playback key events plus Spotify-specific launch/focus-before-media behavior. Window focus and key emission are observed; actual remote playback-session state remains unavailable and is not claimed. |
| Call command routing | Live tested safety path | Normal-phone and WhatsApp audio-call intents route to Communications, require exact contact/channel approval, re-resolve after approval, and fail with `call_started: false` when the provider/app is unavailable. Live provider number and WhatsApp Desktop are not configured. |
| Inbound AI phone assistant | Tested contract | AI disclosure, authenticated Twilio webhook/WSS relay, bounded conversation, urgency/protected-data/human handoff, configured-number-only transfer, masked caller identity, and summary-only persistence pass locally. No purchased AURIS number or production public endpoint is connected. |
| Supervisor and policy | Tested | Unit suite and mission UI |
| Durable workflow ledger | Tested | Per-step checkpoints, bounded attempt budgets, content-minimised evidence, inspectable Mission Control states, and terminal workflow history |
| Workflow retry and restart recovery | Tested | Read-only failures retry at most once; forced restart recovery resumes only read-only work and marks sensitive/write interruptions for manual review without replay |
| Deterministic verification reports | Tested | Policy, execution outcome, evidence presence, replay safety, attempt count, recovery flag, and unresolved limits attached to mission results |
| Memory | Live tested prototype | Ten typed classes, local semantic index/retrieval, project/environment scope, structured decisions, source/confidence/sensitivity/expiry metadata, stale state, category controls, explicit contradiction resolution, correction/supersession history, inspectable export without embeddings, secret rejection, delete cascade, and private mode |
| Approvals | Tested | Sensitive-action gate, decision audit, dashboard controls, and native overlay approve-once/reject controls |
| Emergency stop | Tested | Dashboard, tray, overlay, and global shortcut paths; new commands return HTTP 423 until resumed |
| Local portal authentication | Tested | Per-install secret, derived HttpOnly SameSite session, CSRF token, loopback binding, restricted token ACL, 30-second one-time browser bootstrap, and replay rejection |
| Durable reminders | Tested | Timezone-aware local scheduling, restart persistence, atomic due-event claim, spoken delivery, audit, and cancellation UI |
| Outlook mailbox search | Tested | Authorised classic Outlook profile; live private probe scanned 500 recent Inbox items read-only with no mutation or persistence |
| Outlook calendar | Tested | Live private bounded calendar read completed without creating or changing events |
| Outlook contacts | Implemented | Bounded read-only classic Outlook contact lookup by name, company, or email; result items remain ephemeral and are removed from durable task/workflow records; live account-content probe requires an explicit user query |
| Outlook drafts and send | Implemented | Exact recipient/subject/body parser, stdin-only connector payload, verified draft EntryID, and approve-once send continuation; no live external message was sent during validation |
| Inbound phone assistant | Tested contract | Provider-neutral call brain plus Twilio ConversationRelay HTTPS/WSS adapter; signed webhook validation, AI/transcription disclosure, protected-data and commitment refusal, importance detection, caller-requested and urgent handoff, configured-number-only dial, masked caller identity, no audio recording, and summary-only records. A real number and public deployment are not configured |
| Approval-resumed Windows input | Tested prototype | Exact text and named app approval, signed content digest, foreground verification, Unicode SendInput, one-time decision, and secret-data denylist |
| Windows shell packaging | Tested | Per-user launcher, sign-in startup, hidden portal/voice/tray processes, verified port owner, singleton discovery with stale-PID recovery, registered tray icon, and verified three-process stop script |
| Cloud model router | Implemented | Compatible endpoint adapter; external provider credentials not configured |
| Cloud outbound command contract | Tested | FastAPI API plus HTTPS-only edge client; one-time enrolment, pinned Ed25519 device certificates, device-signed poll/ack requests, cloud-signed typed envelopes, durable leases/nonces, nine permission scopes, revocation, and 13 passing command/telephony end-to-end security tests |
| Production cloud deployment | Not configured | No cloud account, domain, trusted TLS/mTLS certificates, PostgreSQL service, secret vault, or production ingress is available; UI remains NOT CONNECTED |
| Research worker | Tested prototype | Rapid/deep/exhaustive/continuous budgets, explicit branches and counterevidence cycles, bounded concurrent HTTPS retrieval, SSRF blocking, canonical/content deduplication, provenance, primary-source classification, validated claim IDs and statuses, and a completion-gating coverage ledger; specialist databases and durable watches remain pending |
| Signed Windows service | Designed | Local signed-envelope foundation is tested; the current device agent still runs in the user session without a device certificate or remote channel |
| Android companion | Build verified | Compose command, mission, approval, voice-input, camera, emergency-stop, and secure-pairing surfaces; 3 unit tests pass, lint reports 0 errors, and the API 36 debug APK has a verified v2 debug signature. No Android device is attached, no production signing key exists, and enrolment transport remains disconnected |

## Voice Acceptance Evidence

- Fresh process startup reached voice-ready state in 10.642 seconds, before the daemon and desktop companion were launched.
- The first reply immediately after that clean startup dispatched audio in 1.273 seconds with Kokoro on `CUDAExecutionProvider`; persistent input and neural output workers were both online.
- A 13.696-second response completed across two prefetched chunks with 1.446-second warm first-audio latency.
- Live interruption stopped a multi-chunk response, returned the broker to idle with no error, and left zero temporary WAV files.

## Project Analysis Acceptance Evidence

- The exact live command `AURIS, analyse this project` routed to the coding worker as a read-only mission and completed one durable workflow attempt with verifier status `verified`.
- Snapshot `fa664f77302cc259d936` mapped 803 workspace files, 29,607 text lines, 10 components, 35 test files, six manifests, one project instruction file, and two bounded review signals without truncation or project-code execution.
- The mission result and selected Engineering workspace reported the same snapshot ID; `modified_files` remained zero.
- A second project root was registered through the authenticated and CSRF-protected API, analysed under that selected context, and disconnected again; untrusted project-code execution remained disabled.
- The 0.8.7 discovered suite passes 218 tests, with 13 cloud-only tests skipped by design in the lightweight environment. The final gate passed 173 local security contracts, 13 cloud command/telephony tests, seven .NET Windows service tests, both frontend module syntax checks, and Android APK v2 signature verification on 2026-09-06.
- Automated visual inspection of the loopback portal was denied by the in-app browser security policy. Authenticated live assets, 158 unique DOM IDs, responsive source contracts, pinned Three.js integrity, in-scene WebGL pixel diagnostics, factual telemetry, API data, and runtime behavior were verified, but a fresh automated screenshot acceptance is not claimed.

## Failing-Test Repair Acceptance Evidence

- `scripts/accept_test_repair.py` created a real failing Python unittest fixture, reproduced the failure, and generated a one-file signed repair in a bounded content snapshot.
- The targeted test and complete isolated suite passed before approval while the registered source hash remained unchanged; the public task result contained the review diff and hashes but no full replacement body.
- One-time application revalidated signature, expiry, root, profile, and preimage, then passed targeted and complete post-apply tests plus final source hashes. Replay was rejected.
- Adversarial contracts cover model-output traversal, test edits, dangerous execution primitives, untrusted execution, signature tampering, expiry, changed preimages, private-mode refusal, rejection cleanup, one-time scope, complete-suite regression, and exact rollback.
- Live named-pipe task `e1ad00a4-486f-4d8d-9dae-d61379ffd708` completed after all 189 tests in its isolated snapshot passed, correctly reported `no_repair_needed`, and left the registered source unchanged. The subsequent orphan-cleanup regression brought the final suite to 190 tests and removes unreferenced UUID content snapshots while preserving active proposals, unrelated directories, links, and Git worktrees.
- This is a trusted AURIS Python unittest prototype, not a general OS sandbox, independent verifier process, or permission for arbitrary registered-project execution.

## Project Opening Acceptance Evidence

- `AURIS, open this project` and uniquely named project commands route to the computer and verification agents as reversible device work.
- The resolver permits only a current registered root, rejects missing or ambiguous projects, validates protected boundaries, and places the exact resolved path inside the short-lived signed envelope.
- Execution rechecks that exact path against current project registrations, invokes a fixed local script with an argument list, and reports success only when Windows File Explorer exposes the same resolved location.
- Focused project/device/runtime/fabric coverage passes, including tamper, expiry, wrong-device, revocation, and nonce replay rejection; the complete discovered suite remains green at 190 tests.
- Live command `b2ae557e-06aa-4f18-8fb6-574e51039f36` completed over authenticated named-pipe IPC on AURIS 0.8.2. Signature and nonce checks passed, and File Explorer reported the exact registered root `C:\Users\dmodi\Documents\Codex\2026-08-05\what\work\auris-one`.

## UI Automation Acceptance Evidence

- `click "File" in Notepad` routes to `computer_interaction`, pauses in `awaiting_approval`, and discloses the exact application and control.
- The approved action binds the app and control digest to `invoke_control`; exact-text typing separately binds its text digest to `type_text`.
- PowerShell receives a strict three-field JSON payload through stdin, resolves one exact enabled visible control, permits only bounded UIA patterns, and stores no screenshot, UI text, or state digest.
- Protected shell/security/credential/registry/task-manager targets and consequential control labels fail closed before execution.
- Final integrated command `9bcc4db6-1c43-4108-84ee-c3335940115a` completed over authenticated named-pipe IPC on the restarted AURIS 0.8.3 build. It confirmed AURIS Vale on `CUDAExecutionProvider`, the persistent input worker, background voice daemon, and desktop companion online; then opened Notepad, paused for one-time approval, signature-verified and nonce-claimed `invoke_control`, observed `ExpandCollapsePattern` change for the exact `File` menu item, completed the mission, and closed Notepad.
- The 218-test discovered suite and 0.8.7 cross-runtime security gate pass. The report remains correctly `production_ready: false` because Authenticode signing, production cloud/telephony identity and infrastructure, Android release enrolment, and independent penetration testing are absent.

## Neural Interface And Memory Acceptance Evidence

- The authenticated live UI acceptance loaded the HTML, CSS, app module, neural-core module, and pinned Three.js module from AURIS 0.8.6 with correct JavaScript MIME types and the expected Three.js SHA-256.
- The portal exposes separate factual, derived, and decorative labels; 149 DOM IDs are unique; desktop, tablet, mobile, and reduced-motion contracts are present; the neural renderer reports FPS/node count and performs a centre-frame WebGL nonblank pixel sample.
- Live telemetry reported the AMD Ryzen 5 4600H, 7.42 GB physical RAM, NVIDIA GeForce RTX 3050 Laptop GPU, storage, uptime, and power state without substituting simulated values.
- A live authenticated memory exercise preserved two conflicting port assertions, applied one explicit user selection, linked a correction with four temporal versions, verified export without embeddings, and removed every acceptance record afterward.
- A separate disposable-database exercise passed secret rejection, disabled-category retrieval blocking, conflict history, correction history, and export checks without touching the live store.

## Anticipation, Startup, And Latency Acceptance Evidence

- Authenticated AURIS 0.8.7 acceptance returned 12 current attention signals using only the four allowed delivery classes, a project query spanning 89 real nodes and 253 evidence links, explicit `real_durable_state` provenance, unloaded mailbox/calendar/weather flags, and complete operations-graph suppression in Private Session.
- The startup failure was traced to obsolete AURIS 0.8.6 PID `22516` retaining port 8765 while the new launcher PID exited. Both launch paths now compare the health release to 0.8.7, stop only a command-line-verified obsolete AURIS runtime, and restart server, voice daemon, and desktop companion together.
- A CSS-level eight-second fail-open independently removes the cinematic boot layer even if JavaScript initialization or browser cache state is delayed. The visible skip control and ordinary 2.8-second JavaScript dismissal remain.
- Before optimisation, live greetings measured 20.681 seconds cold and 5.403 seconds warm. The deterministic instant kernel now answers supported common intents without a model call; the latest private acceptance measured 20 ms.
- Qwen 2.5 1.5B is restricted to low-stakes conversational patterns after separate factual and reasoning benchmarks. It warms before dashboard readiness and measured 750 ms generation and 769 ms end-to-end; Gemma 3 4B primes in the background and measured 4.047 seconds generation and 4.066 seconds end-to-end on the quality reasoning probe.
- Ollama confirmed both route-specific runners resident together: Qwen at 2048 context and Gemma at 4096 context. The same live acceptance measured AURIS Vale neural first audio at 913 ms using one voice broker and a private non-persistent command session.
- Live command `c6725435-8cf0-4e89-8427-5800bf0a4390` opened the installed Spotify client in 500 ms through the signed local device fabric, verified PID `11184`, validated the signature, and durably claimed the nonce.

## Predictive Intelligence Acceptance Evidence

- Live AURIS `0.8.22` returned all seven required project forecast metrics with durable-state provenance and advisory-only semantics. Private mode returned no forecasts and the API exposed no automatic-action route.
- Mission-failure probability was supported by 138 terminal outcomes: observed rate `5.7971%`, Wilson 95% interval `2.9664%-11.022%`. Other operational indicators retained `probability: null`.
- The full suite passed 307 tests with 13 expected skips. The release gate passed 256 local security tests, 13 cloud contracts, seven .NET tests, frontend syntax, and Android APK v2 signature verification.
- Post-activation health reported `0.8.22`; the server, voice daemon, and desktop companion were all independently alive.

## Proactive Watch Acceptance Evidence

- Live AURIS `0.8.23` delivered one real background threshold alert at score `100` with twelve evidence IDs, advisory-only semantics, and automatic action disabled. Private mode exposed no watch state.
- Authenticated natural commands created and disabled a workload-pressure watch through task type `proactive_watch`; dashboard controls expose create, enable, disable, delete, and alert history.
- Acceptance removed its temporary durable records. The full suite passed 313 tests with 13 expected skips; the release gate passed 261 local, 13 cloud, seven .NET, frontend, and Android v2 signature checks.

## Bounded Filesystem Acceptance Evidence

- AURIS 0.8.9 created and independently observed `C:\Users\dmodi\Desktop\DON`, then created a UTF-8 Documents note with its exact content digest bound to the signed command.
- AURIS 0.8.10 completed four authenticated missions that created a note, renamed it in Documents, copied it to Desktop, and moved the copy to Downloads. Each action validated its dedicated permission scope, signature, and one-time nonce; SHA-256 proved the final Documents and Downloads files retained the requested content, and the moved Desktop source was absent.
- The 240-test discovered suite passes with 13 environment-dependent tests skipped. The expanded security gate passes 192 local security contracts, 13 cloud command contracts, seven .NET Windows-service tests, frontend syntax checks, and Android APK v2 signature verification.
- The gate remains truthfully `production_ready: false`: the Windows service is not Authenticode-signed, and production cloud, telephony, mobile enrolment, and independent penetration-test evidence are absent.

## Deep Research Acceptance Evidence

- Live command `2e36cd27-082c-458a-b248-c37677bbf034` completed over authenticated named-pipe IPC on the restarted AURIS 0.8.4 runtime for `research deeply whether passkeys reduce phishing risk compared with passwords`.
- The mission preserved four deduplicated source records from three origins, identified one primary source heuristically, validated three claim nodes against retained source IDs, ran two explicit counterevidence cycles, covered all five planned branches, and resolved 36 duplicate search results.
- Every definition-of-done check passed: branches, primary source, claim citations, contradiction search, deduplication, coverage-ledger schema, source threshold, and origin diversity. No source excerpt was persisted.
- The first live attempt correctly stopped at `partially_completed` when malformed small-model JSON yielded only one safely parsed claim. The bounded repair for curly JSON delimiters and grouped citations is regression-tested; the repeated mission then passed without weakening source-ID validation.

## Phone Assistant Contract Evidence

- Local 0.8.4 simulation passed AI/transcription disclosure, urgent handoff, masked caller identity, summary generation, zero audio recording, zero raw-transcript persistence, and zero model-created commitments while the provider remained truthfully `configuration_required`.
- Thirteen cloud contract tests include unsigned-webhook rejection, signed incoming ConversationRelay TwiML, signed WSS turn handling, urgent end-session handoff, configured-owner-number-only `<Dial>`, and summary-only durable call history.
- No real call is claimed. Twilio onboarding, a purchased number, trusted TLS/WSS deployment, consent review, Devansh's transfer number, notification delivery, and real acoustic acceptance remain production gates.

The interface must never label a designed or scaffolded capability as connected.

## Verified Browser Control Acceptance Evidence

- Live AURIS `0.8.24` opened the fixed local acceptance page in a visible isolated Edge profile with HTTP 200 and labelled its content `untrusted_web_content`.
- Accessibility inspection observed the exact `Acceptance note` field and `Apply Preview` button. An approved fill read back 22 exact characters while returning only the value digest; an approved click produced and verified the expected URL and body-state change.
- Navigate, inspect, fill, and click each traversed the signed device fabric with the corresponding fixed permission scope, verified signature, and claimed nonce.
- Secret-bearing fill text and a purchase-like control were blocked before browser execution. Private Session refused the persistent browser profile.
- The discovered suite passed 322 tests with 13 environment-dependent skips. The release gate passed 273 local security contracts, 13 cloud contracts, seven .NET service tests, frontend and browser-worker syntax, and Android APK v2 signature verification.

## Browser Mission Acceptance Evidence

- Live AURIS `0.8.25` completed a four-step mission against the fixed local fixture: HTTP 200 navigation, exact read-back of two accessibility-named fields, then an exact benign control invocation with an observed page-state change.
- The one-time approval summary and browser result exposed no approved field values. Each field checkpoint returned only length and SHA-256 evidence, and page URL query values were digest-redacted.
- The mission traversed the signed `browser_workflow` permission with a verified signature and claimed nonce. Chromium sandboxing was explicitly enabled and credential-bearing URLs remained prohibited.
- A second approved mission deliberately targeted a missing field at step 3. It returned `failed`, reported two completed checkpoints, identified step 3 as failed, and proved that the final control at step 4 did not execute.
- The discovered suite passed 329 tests with 13 environment-dependent skips. The release gate passed 280 local security contracts, 13 cloud contracts, seven .NET service tests, frontend/browser-worker syntax, and Android APK v2 signature verification.
