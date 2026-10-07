# AURIS 0.8.33 Voice-to-Action Readiness

## Implemented

- Background wake commands now use the same authenticated central backend as dashboard and desktop-overlay commands. Model routing, conversation state, and the single coding-mission slot are no longer duplicated in the voice daemon.
- Push-to-talk, continuous wake commands, and overlay speech carry a correlated turn ID through recognition, dispatch, verification, and speech output. A changed, expired, or already-dispatched voice turn cannot execute again under that ID.
- Activity contains a voice diagnostic ledger. It distinguishes recognition failures, policy blocks, execution failures, unsuccessful signed device observations, pending approvals, partial outcomes, generated replies, and speech-output failures.
- Diagnostics are bounded to 40 turns and 15 minutes in RAM. Private and potentially sensitive transcript text is hidden. Rejected tentative speech and microphone audio are not added to this ledger. Repeated background misses are aggregated.
- Decoder scores are explicitly uncalibrated, never displayed as a percentage probability of understanding.
- After a recent completed, signed app operation in the same conversation and project, benign follow-ups such as "minimize it" and "restore the window" resolve the application. Context expires after five minutes; private sessions do not read shared context. Sensitive actions such as closing, deleting, or sending are not inferred from pronouns.
- Startup enables authenticated controls before optional workspace hydration completes. Optional refreshes are coalesced, status polling cannot overlap itself, and metadata requests have bounded waits. Completed voice commands no longer wait for every optional panel refresh.
- Wake acknowledgements remain silent. "Yes, Devansh, I am listening" remains suppressed before synthesis. One local voice broker and one output provider are used.

## Verified So Far

- Full Python discovery: 450 tests, 437 passed and 13 cloud-runtime skips. The 13 cloud contracts passed separately in their configured environment.
- Release gate: local security contracts, seven Windows-service tests, frontend syntax, eight Windows fallback grammar cases, all 26 synthetic acoustic cases, and Android APK signature checks passed. Production readiness remains false.
- Live authenticated PC acceptance opened Notepad, minimized it using a conversational follow-up, restored it using another follow-up, created a unique Desktop folder, and wrote a nested note. Every step returned a signature-verified, nonce-claimed device receipt. Directory existence, note bytes, and the note SHA-256 were checked independently.
- These five text-to-action probes took 519-1,228 ms each in that run. This is not microphone-to-reply latency and not a performance guarantee under other load.
- Local Whisper and the Realtek microphone array were online; background wake was enabled and Kokoro was selected for output.
- Desktop (1440 x 1000) and mobile (390 x 844) Playwright captures passed. The Three.js scene was nonblank and moving, and 3D/2D/schematic controls changed projection. No JavaScript errors, horizontal overflow, or clipped dock controls were found in those checks.
- Voice diagnostic layout fixtures passed with expanded details, long labels, hidden private text, and distinct generated-reply/partial/approval labels. These fixture captures are explicitly UI tests, not evidence of microphone or device execution.
- With project metadata deliberately held back, authenticated controls became ready in 649 ms on desktop and 448 ms on mobile in one run. This verifies progressive startup, not a universal startup-time guarantee.
- The passive acknowledgement was suppressed; priority microphone listening retained the same warm recognizer process.
- Final private latency samples: instant reply 45 ms; fast Qwen reply 941 ms; quality Gemma reply 5,093 ms; Kokoro first-audio handoff 1,847 ms after text submission. Quality-model replies remain slower than the requested instant experience.

## Measurement Boundaries

Capture time includes waiting for speech. Decode time covers transcription. Command time includes dispatch and execution. First-audio time is measured from speech submission to native playback handoff. Recognition-to-audio time starts at accepted transcription, not at the end of the user's sentence. These values must not be substituted for one another or described as proven audible sound from the speakers.

## Still Unverified or Limited

- The owner's own live speech, accent, microphone gain, and room-noise accuracy need a physical acceptance test. Synthetic speech cases do not establish that accuracy or a 100% success rate.
- AURIS does not have unrestricted support for every PC application or arbitrary internet task. Typed adapters, allowlists, and truthful unsupported outcomes remain in place.
- Full-duplex echo cancellation and speaker-identity authentication are not implemented.
- The existing Codex bridge is retained, not a newly trained model. Generated tests run in the Codex sandbox; independent arbitrary-code execution is not implied.
- Actual telephone answering, a public AURIS phone number, and WhatsApp audio calling are not enabled by these changes. Provider credentials, number provisioning, trusted public endpoints, and relevant service support are still required.
- Destructive operations, sensitive external actions, and reviewed coding diffs keep their deterministic permission and approval requirements.

## Repeatable Checks

```powershell
& .\scripts\start_auris.ps1
& 'C:\Users\dmodi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\scripts\accept_command_followups.py
& .\scripts\security_release_gate.ps1
```

The follow-up acceptance creates a uniquely named Desktop folder and note and leaves them available for inspection. It does not claim those text probes were spoken through the microphone.
