# AURIS Foundation Threat Model

The local portal requires a per-install secret bootstrap, derives a separate HttpOnly SameSite session cookie and CSRF token, and binds only to loopback. The launcher reads the restricted token file and removes the secret from the visible URL through an immediate redirect.

## Protected Assets

User files, device control, microphone access, memories, approvals, call summaries, audit evidence, and future credentials.

## Trust Boundaries

- User directives are trusted instructions but still pass deterministic policy.
- Webpages, documents, emails, retrieved text, and model output are untrusted content.
- Caller speech, caller identity, telephony webhook fields, and call-model output are untrusted content.
- The local device agent accepts only typed commands matched by code.
- Secrets must remain outside conversations, memories, screenshots, and audit payloads.

## Foundation Controls

- No administrator privileges or privilege escalation.
- No arbitrary shell command execution.
- Exact-name resolution against the locally discovered application catalog, protected-process blocking, and user-profile folder boundaries.
- Approved roots are resolved before filesystem access.
- Project roots must be explicitly registered, cannot be a drive or entire user-profile root, and reject known credential and system boundaries. Repository analysis is file-count bounded, does not follow symlinks, excludes credential-shaped file contents, and cannot execute project code. Opening a project signs the exact resolved registered root, revalidates it immediately before execution, and requires an exact File Explorer location observation before success.
- Failing-test repair executes only for the explicitly trusted AURIS Python unittest profile. It reproduces before patching, copies into a bounded symlink-refusing snapshot or clean Git worktree, treats model output as strict untrusted JSON, permits at most three existing implementation files and two attempts, blocks tests/manifests/credentials/traversal and newly introduced execution/network/privilege primitives, and requires targeted plus complete isolated tests.
- A repair proposal is bound to root, test profile, expiry, exact preimage/new hashes, files, and diff by a separate current-user DPAPI-protected HMAC key. Source remains unchanged until one-time approval. Apply revalidates every binding, writes atomically, reruns targeted and complete tests, checks final hashes, and restores exact preimages on failure. Rejected/expired proposals are deleted; terminal archives retain hashes/diff but redact replacement bodies.
- Sensitive external actions pause for approval.
- Critical and prohibited terms are blocked or require reauthentication.
- Emergency stop persists and blocks new commands.
- Device results include verification evidence and audit events.
- Native tray and voice clients prefer an authenticated Windows named pipe carrying size-bounded JSON only; the pipe key is purpose-derived from the restricted per-install secret.
- One server-owned speech-input worker attaches the default microphone only during bounded listen requests, emits memory-only hypotheses, detaches input before returning, and allows priority requests to preempt wake capture without starting a second recognizer.
- The device command key is encrypted at rest with current-user Windows DPAPI and additionally restricted by a per-user file ACL.
- Device commands use an exact typed schema, fixed permission scopes, short expiry, signature verification, durable nonce claims, revocation, and replay rejection before Windows execution.
- Exact-text typing and benign named-control invocation use separate signed permission scopes bound to content digests. UI Automation requires one-time approval, refuses security/shell/registry/task-manager targets and consequential control labels, passes its bounded payload through stdin, and persists no screenshot or UI text.
- The disconnected cloud contract requires device-certificate possession proofs for every poll/ack and a separately pinned Ed25519 cloud signature for every command; tests cover bad signatures, expiry, replay, permission denial, certificate mismatch, and revocation.
- Telephony accepts only provider-signed HTTPS callbacks and a provider-signed WSS relay, discloses AI and transcription, refuses secrets/payment/commitment handling, dials only one configured E.164 owner number, records no audio, and persists only a masked-caller summary without raw transcript.

## Known Risks

- The browser portal remains loopback HTTP for the local web interface. Native tray and voice operations use the authenticated named-pipe channel, with loopback retained as a recovery path.
- The device process is not yet a signed Windows service.
- The cloud contract is not deployed and mutual TLS is not configured; app-layer certificate proof does not replace the production mTLS gate.
- Telephony is not deployed. Provider onboarding, local call-recording and AI-disclosure law review, trusted public TLS/WSS ingress, rate limits, abuse monitoring, secret-vault storage, and real acoustic acceptance remain mandatory production gates.
- Provider speech-to-text and text-to-speech process call audio when live telephony is enabled even though AURIS does not record audio. The disclosure and data-processing configuration require jurisdiction-specific review before activation.
- Speech recognition quality depends on the configured Windows recognizer and microphone.
- Neural speech is generated locally into an ACL-restricted temporary WAV and deleted after playback. Browser speech output is disabled, and synthesis output paths are restricted to the AURIS voice runtime directory.
- Standard-session project analysis persists bounded path metadata and a snapshot ID in the task ledger. Private mode avoids task persistence; neither mode stores scanned source contents in the analysis result.
- The repair test runner executes trusted project code as the signed-in standard user; it is not an OS sandbox. Repair is therefore restricted to the fixed AURIS project registration. Private mode refuses repair before tests or model access. General registered-project execution, non-Python profiles, package installation, new-file creation, and unrestricted autonomous changes remain disabled.
- UI Automation builds a bounded memory-only digest from at most 600 controls in the owning application's accessibility tree. It stores only the observation class, never UI text or the digest, and refuses to report completion when no post-action control state, window state, or UIA tree change is observed.

These risks block production-ready status but not the bounded local Foundation release.
