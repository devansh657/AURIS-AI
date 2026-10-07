# AURIS Master Requirement Audit

This audit applies the evidence rules in `AURIS_REQUIREMENT_BASELINE.md` to the two preserved source directives. It does not redefine the requested scope. A generation is complete only when every required capability in that generation satisfies the product definition of done.

## Generation Status

| Generation | Current state | Evidence proved | Required work still missing |
| --- | --- | --- | --- |
| GEN 0 Foundation | INTEGRATED | Local architecture, database, configuration boundaries, portal authentication, threat model, security gate | Production identity, managed secrets, production database, CI service evidence |
| GEN 1 Core AURIS | TESTED | Text command path, supervisor, task lifecycle, success contracts, durable workflows, verification, audit, local/cloud-compatible model router | Deployed cloud core, distributed event bus, remote durable worker ownership |
| GEN 2 Voice and Personality | TESTED | One session-locked Vale voice, persistent input broker, wake word, transcript, cancellation, interruption, sentiment pacing, markup cleanup | Human acoustic sign-off for naturalness, echo cancellation, true simultaneous full duplex |
| GEN 3 Memory | LIVE TESTED prototype | Ten memory classes, local semantic retrieval, source/confidence/sensitivity/validity metadata, temporal staleness, explicit conflict resolution, structured decisions, correction history, category controls, export, deletion cascade, private mode, and authenticated live API acceptance | Independent long-horizon retrieval-quality and privacy-leakage evaluation, production encrypted backup/recovery, and cross-device synchronisation |
| GEN 4 Research | LIVE TESTED prototype | Deterministic mode budgets, branch/counterevidence query cycles, bounded public HTTPS retrieval, SSRF defense, URL/content deduplication, source provenance and primary classification, validated claim graph, contradiction states, complete coverage ledger, and live 0.8.4 named-pipe acceptance | Specialist databases, multilingual retrieval, durable continuous watches, and independent answer-quality evaluation |
| GEN 5 Coding | TESTED prototype | Registered-root analysis plus trusted AURIS unittest execution; reproduce-first failure loop; bounded two-attempt model patching; Git-worktree or content-snapshot isolation; blocked test/manifest/credential/link and dangerous-primitive changes; targeted/full isolated verification; DPAPI-keyed signed exact diff; one-time approval; preimage revalidation; post-apply tests/hashes; exact rollback; adversarial and deterministic fixture acceptance | General untrusted-project execution sandbox, non-Python test profiles, independent verifier process, multi-agent feature development, and live clean-Git worktree acceptance |
| GEN 6 Guardian | SECURITY_REVIEWED locally | Deterministic risk classes, approval, private boundary, DPAPI keys, signed commands and repair proposals, nonce replay defense, revocation, emergency stop, expanded 0.8.7 security gate | Independent penetration test, production identity/re-authentication, external security review |
| GEN 7 Windows | LIVE TESTED prototype | App discovery/open/close/focus, focus-bound Spotify media, named-browser public URL/search targeting, bounded file operations, projects, screen context, signed exact-text input, approval-gated benign UI Automation, isolated accessibility-first browser automation, bounded multi-step missions, durable browser checkpoints, and safe continuation | General multi-application desktop planning, broader nested/general file workflows, richer screen checkpoints, authenticated-site workflows, independent playback observation, broader self-healing recovery, signed installed service |
| GEN 8 Productivity | TESTED prototype | Classic Outlook mail/calendar/contacts/drafts/send gate, local OneDrive, documents/data reading, reminders, daily brief | Provider APIs, meeting copilot, artifact write/render loop, full data-analysis studio, remote-only cloud files |
| GEN 9 External Action | TESTED contract plus live routing safety | Disclosed AI phone identity, signed Twilio webhooks/WebSocket, bounded call agent, importance and protected-data policy, configured-number handoff, masked caller identity, no autonomous commitments, summary-only persistence, and exact approval-gated outbound call intent routing that cannot fall through to chat | Purchased AURIS number, provider credentials/onboarding, trusted public deployment, WhatsApp Desktop linking and verified call adapter, live acoustic call, notification delivery, takeover UX, and promise tracking |
| GEN 10 Anticipation | LIVE TESTED local prototype | Bounded evidence-backed operations graph, six-level attention model, four delivery classes, deadline/risk scoring, Focus Mode batching, advisory opportunity radar, richer daily intelligence, evidence-only evening debrief, graph/memory privacy masking, and restart-safe proactive metric watches with local notification and authenticated voice/text/UI control | Durable email/call/meeting ingestion, explicit strategic goal portfolio, external-signal watches, remote notification delivery, travel/weather/finance/contract connectors, and long-horizon prioritisation evaluation |
| GEN 11 Advanced Cognition | LIVE TESTED prototype | Bounded hypothesis lab, evidence and epistemic states, weighted decisions, scenario utility, counterfactual deltas, five-role council, structured outcomes, sample-gated metrics, a factual operational world model, and direct-action causal interventions with `do(action)`, mediators, confounders, no-action/alternative comparison, downstream non-identifiability, stale rejection, privacy suppression, and non-executing UI | Truly independent provider/model council acceptance, learned world models, empirically identified downstream causal graphs, domain simulation adapters, skill compiler, domain calibration datasets, and long-horizon outcome evaluation |
| GEN 12 Mobile and Ambient | BUILD VERIFIED prototype | Android Compose debug build, tests, camera/voice/approval/emergency surfaces, APK v2 debug signature | Release signing, physical device installation, secure enrolment, live cross-device continuity, location, multi-screen and ambient acceptance |

## Required Vertical Slices

| Slice | State | Authoritative evidence |
| --- | --- | --- |
| Authenticated command to supervisor, verifier and audit | INTEGRATED locally | Authenticated portal/native IPC, durable task/workflow records, verification reports and audit tests; deployed cloud path remains absent |
| Analyse this project | TESTED | Live registered-root snapshot, architecture/test/instruction evidence, zero project modifications |
| Fix this failing test | TESTED prototype | Release 0.8.5 deterministic failing fixture passed reproduction, isolated targeted/full tests, unchanged source before approval, signed exact diff, one-time apply, post-apply targeted/full tests, terminal replacement-body redaction, and replay rejection; workflow/runtime/approval/rollback adversarial contracts pass |
| Open my project | TESTED | Live 0.8.2 signed command over authenticated IPC with exact File Explorer root observation |
| Deep research | LIVE TESTED prototype | Live 0.8.4 mission passed with four sources, three origins, one heuristic primary source, three validated claims, two counterevidence cycles, 100% branch coverage, 36 duplicates resolved, and no excerpts persisted |
| Remember and correct this | LIVE TESTED prototype | Live 0.8.6 authenticated API preserved a contradiction, required explicit selection, linked a correction with four versions, exported without embeddings, and removed test records |
| Call restaurant | TESTED contract | Inbound answering, disclosed AI conversation, safe handoff, summary contracts, and outbound intent/approval routing pass locally; no real provider number or live call is connected |

## Current Release Blockers

- The active Windows agent is not an Authenticode-signed installed service.
- No production cloud account, domain, vault, PostgreSQL, trusted TLS/mTLS ingress, or identity provider is configured.
- No Android release key, attached device, production installation, or live enrolment exists.
- Independent penetration testing and real multi-device recovery exercises are incomplete.
- Voice still requires Devansh's real-room acoustic acceptance for naturalness and full-duplex expectations.
- General-project sandboxing and the real deployed/acoustic phone-call slice remain incomplete as stated above.

The overall AURIS goal remains active until these missing requirements are implemented and directly evidenced.

## Call Routing Acceptance Evidence

- Live AURIS `0.8.28` routed both `call MOM` and `make a WhatsApp audio call to MOM` to `communications` with `sensitive` risk and `awaiting_approval` state instead of `general_assistance`.
- Each approval bound only the exact `MOM` contact label and requested channel. Both acceptance approvals were rejected, and no call or message was attempted.
- `show AURIS phone status` returned `configuration_required`, accurately reflecting that no dedicated provider number, credentials, or trusted public HTTPS/WSS relay is configured.
- The discovered suite passed 350 tests. The release gate passed 301 local contracts, 13 cloud/telephony contracts, seven .NET service tests, frontend/browser-worker syntax, and Android APK v2 signature verification.

## Browser Automation Acceptance Evidence

- Live AURIS `0.8.24` navigated a fixed local acceptance fixture in a visible isolated Edge profile, observed HTTP 200/title/content trust, and discovered its field and button through accessibility semantics.
- Fill and click paused for one-time approval, re-resolved the exact visible target, traversed fixed signed scopes with claimed nonces, and verified exact input read-back plus the resulting URL/body-state change.
- Protected data, consequential controls, arbitrary private-network destinations, downloads, and Private Session use of the persistent profile remain blocked.
- The 322-test discovered suite passed with 13 skips. The security gate passed 273 local, 13 cloud, and seven .NET contracts plus frontend/browser-worker syntax and Android v2 signature checks.

## Browser Mission Acceptance Evidence

- Live AURIS `0.8.25` completed and independently verified a four-step navigation/two-field/final-control mission through one approval and one digest-bound signed `browser_workflow` command.
- Exact approved values were preserved into Edge but omitted from approval and browser evidence; field digests and digest-redacted URL query values proved the expected outcome without returning the values.
- A deliberately missing field failed at checkpoint 3 after two verified steps, and the final control was not invoked. Private-network, credential-URL, protected-data, consequential-control, download, and Private Session boundaries remained closed.
- The 329-test discovered suite passed with 13 skips. The security gate passed 280 local, 13 cloud, and seven .NET contracts plus frontend/browser-worker syntax and Android v2 signature checks.

## Model Council And Outcome Acceptance Evidence

- Live AURIS `0.8.19` completed Solver A, Solver B, Critic, Judge, and Evidence Verifier through the authenticated Decision Lab API under the fixed five-call budget.
- The interactive route used resident Qwen for responsiveness and reported `independent_models: false`; configured Gemma availability was not misrepresented as actual multi-model consensus.
- Startup contention now returns a bounded `warming` state instead of allowing a council request to collide with background quality-model priming.
- The same live case retained expected outcome, actual outcome, difference, root cause, lesson, and confidence update. Option success rate remained withheld at three observations against the five-observation gate.
- The discovered suite passed 291 tests with 13 environment-dependent skips. The release gate passed 242 local security contracts, 13 cloud contracts, seven .NET service tests, frontend syntax, and Android APK v2 signature verification.

## Runtime Trio Recovery Evidence

- Launch now invokes the idempotent runtime reconciler even when the `0.8.19` backend is already healthy, so missing voice or tray processes are restored instead of merely reopening the dashboard.
- Live recovery restored PID `18300` as `auris.voice_daemon` and PID `24796` as `auris.desktop_companion` while preserving server PID `24868` as `auris.server`.
- Startup establishes module identity from an exact existing command line or fixed launch arguments, verifies PID survival, and fails visibly before UI launch if either native process exits immediately.

## Operational World Model Acceptance Evidence

- Live AURIS `0.8.20` produced reproducible snapshot `7e96e9290cab22a807ae33c3` from 160 real entities, 320 evidenced relationships, and 120 bounded possible actions in the selected AURIS project.
- The authenticated simulator accepted one read-only action and returned simulation `39e08b4340fc9012ac13ba28` with `executed: false`, `approval_requested: false`, explicit unknowns, and ordinary policy/verification still required.
- An obsolete snapshot was rejected with HTTP 409, and Private Session returned zero entities and zero actions.
- The discovered suite passed 300 tests with 13 environment-dependent skips. The release gate passed 250 local security contracts, 13 cloud contracts, seven .NET service tests, frontend syntax, and Android APK v2 signature verification.

## Causal Intervention Acceptance Evidence

- Live AURIS `0.8.21` produced snapshot `9af74638aa66898918c5ba41` from 162 entities and 320 evidenced relationships.
- Intervention analysis `11565e35227603832d78b222` represented the selected action as `do(inspect_context)`, preserved observed/no-action state comparison, and returned downstream identifiability as `not_identified`.
- Graph neighbors remained associations, `downstream_causal_effects` remained empty, no probability was invented, and simulation `fa591e5188c175d068ad0b8f` returned `executed: false`.
- Private Session again returned zero entities. The discovered suite passed 302 tests with 13 skips; the release gate passed 252 local, 13 cloud, and seven .NET contracts plus frontend and Android signature checks.

## Predictive Intelligence Acceptance Evidence

- Live AURIS `0.8.22` returned all seven project forecast families through its authenticated API: project delay, deadline, workload pressure, resource conflicts, follow-up likelihood, mission failure, and opportunity relevance.
- Operational indicators remained deterministic scores rather than mislabeled probabilities. Mission-failure probability was emitted only because 138 durable terminal outcomes exceeded the 20-sample gate; the observed estimate was `0.057971` with Wilson 95% interval `[0.029664, 0.11022]`.
- Every signal retained real durable-state provenance, evidence IDs, method, uncertainty, and `advisory_only: true`; the response declared automatic action disabled. Private Session returned zero forecasts.
- The discovered suite passed 307 tests with 13 skips. The release gate passed 256 local, 13 cloud, and seven .NET contracts plus frontend syntax and Android v2 signature checks.
- Live health reported `0.8.22`; server PID `11692`, voice-daemon PID `26548`, and desktop-companion PID `28448` were independently confirmed running after activation.

## Proactive Watch Acceptance Evidence

- Live AURIS `0.8.23` created a temporary `project_delay_risk` watch through the authenticated portal, and the real background event engine delivered its threshold transition at score `100` with twelve durable evidence IDs.
- The alert and dashboard policy both reported `advisory_only: true` and `automatic_action: false`; Private Session returned zero watches and alerts.
- The ordinary natural command path classified and completed “watch workload pressure above 100 every 15 minutes,” then classified “stop the workload pressure watch” and durably disabled it. This is the same command path used by recognized voice input.
- The acceptance cleanup deleted both temporary watches and their alert records. The discovered suite passed 313 tests with 13 skips; the gate passed 261 local, 13 cloud, and seven .NET contracts plus frontend syntax and Android v2 signature checks.
