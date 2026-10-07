# AURIS Security Release Gate

Run the cross-runtime release evaluation with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\security_release_gate.ps1
```

The gate exercises portal authentication, CSRF/session isolation, deterministic policy, approval behavior, private-mode persistence boundaries, device signatures, permission scopes, nonce replay defense, revocation, named-pipe authentication, Windows secret protection, screen cleanup, file boundaries, registered-project root validation, deterministic project-open resolution, exact-text binding, UI Automation protected-target refusal and observation contracts, symlink-safe bounded analysis, untrusted project-code execution refusal, reproduce-first repair isolation, model-patch path and primitive refusal, DPAPI-keyed proposal integrity, expiry/preimage checks, exact-diff one-time approval, post-apply verification and rollback, research source/claim/coverage integrity, telephony signature/disclosure/handoff/privacy controls, communication controls, speech-input correlation and priority arbitration, voice-output arbitration, the cloud command and telephony contracts, the .NET service validator, frontend syntax, and the Android APK signature.

A passing evaluation means the implemented controls behaved as tested. It does not mean AURIS is production ready. The generated `dist/security-release-gate.json` keeps `production_ready` false until trusted Windows and Android signing, production cloud infrastructure, physical-device enrolment, and independent security evaluation are evidenced.
