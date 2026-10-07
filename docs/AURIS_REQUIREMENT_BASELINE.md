# AURIS Requirement Baseline

## Authority

The current AURIS product requirements are the union of:

1. `docs/AURIS_PRIME_DIRECTIVE.md`, preserved byte-for-byte from the supplied Prime Directive.
2. `docs/AURIS_MASTER_SPEC.md`, preserved byte-for-byte from the supplied Master Build Directive.
3. Explicit corrections and acceptance findings supplied by Devansh during testing.

The product name is always **AURIS**. References to another assistant name in older imported material are naming mistakes. Later explicit user corrections take precedence over older wording. Security invariants cannot be weakened by a model, webpage, document, or inferred preference.

## Product Standard

AURIS is a supervised personal intelligence operating system, not a themed chatbot. Every substantial capability must connect perception, context, planning, deterministic authority, execution, observation, verification, recovery, reporting, memory, and audit where those stages apply.

Capability labels use this progression:

```text
NOT_DESIGNED
DESIGNED
SCAFFOLDED
IMPLEMENTED
INTEGRATED
TESTED
SECURITY_REVIEWED
PRODUCTION_READY
```

No status may imply a stronger state than current evidence proves.

## Definition Of Done

A feature is complete only when its implementation, connected UI and backend, permission checks, validation, error handling, audit events, verification evidence, tests, passing test results, security analysis, documentation, and truthful runtime status are all present. External integrations without credentials must say that implementation exists but credentials or deployment are still required.

The overall AURIS objective is not complete while any requirement in the two source directives is missing, contradicted, weakly verified, or represented by placeholder state.

## Voice Release Gate

Voice is accepted only when all of the following are evidenced:

- one authoritative AURIS output broker owns speech across portal, desktop overlay, wake daemon, reminders, and recovery paths;
- one declared AURIS voice persona is used for a session, with no browser or operating-system voice silently joining or replacing it;
- Markdown emphasis, stage-direction markers, citation syntax, raw URLs, code fences, and decorative symbols are converted to natural spoken text rather than pronounced literally;
- sentence punctuation and deterministic emotional context control pace and delivery without claiming human emotion;
- the response style is calm, composed, concise, strategically confident, and capable of respectful disagreement;
- wake word, push-to-talk, transcript, cancellation, acoustic interruption, and emergency stop remain functional;
- ambient audio is not uploaded or persisted;
- recognition, interruption, cancellation, latency, normalization, arbitration, and failure-state tests pass;
- a real microphone and speaker acceptance session confirms the result on this laptop.

Current testing findings added on 2026-08-23:

```text
VOICE-001  Two distinguishable output voices can be heard. Release blocking.
VOICE-002  Markdown asterisks can be pronounced as "asterisk". Release blocking.
VOICE-003  Current SAPI delivery sounds synthetic and does not follow sentence sentiment closely enough. Release blocking.
```

## Non-Negotiable Safety

AURIS never combines model output with unrestricted administrator privileges, arbitrary shell execution, unrestricted file access, automatic external commitments, hidden capture, credential extraction, security-control bypass, silent payments, unrestricted permanent deletion, or self-modification of the Guardian. Consequential actions remain typed, allowlisted, visible, auditable, approval-gated where required, and independently verified where practical.

## Evidence Discipline

Tests prove only the behavior they actually exercise. Source files, green unit tests, UI labels, and manifests do not by themselves prove live hardware, cloud deployment, external delivery, telephony, mobile installation, Authenticode signing, mTLS, or production readiness. Those states require direct evidence from the relevant environment.
