# AURIS 0.8.34 Source Snapshot

Date: 2026-10-07. This document records a development-source publication, not
production readiness or completion of the full requested specification.

## Included Work

The repository preserves the local backend, cinematic UI, voice broker and daemon,
typed signed Windows operations, isolated browser workflows, file/work-product
adapters, coding bridge, memory and workflow services, optional cloud/telephony
contracts, .NET service, Android source, tests, setup tools, and requirement history.

The latest foundation work adds:

- A deterministic, authenticated capability registry shared by planner and UI,
  including scope, permissions, connection state, verifier, and historical evidence.
- Microphone signal/frame diagnostics that distinguish weak input, stalled input,
  overflow, and recognition failure without storing raw audio.
- Recovery for stopped capture streams, bounded retry after rejected early noise,
  and removal of a second VAD filter for already segmented captured utterances.
- More precise voice-turn failure reporting while retaining exact one-time claims,
  private transcript hiding, silent wake acknowledgement, and one output voice.
- A pre-publication named-pipe shutdown fix: the internal wake connection no longer
  waits for authentication after the serving loop exits, and a disconnected wake
  cannot reach the command dispatcher. Ordinary requests still require authentication.

## Live Evidence And Open Failure

On 2026-10-07, text commands performed five real signed Windows operations:
Notepad open/minimize/restore, creation of a uniquely named Desktop test folder,
and creation of a note with independently verified exact content and hash.
This is text-to-PC acceptance, not owner speech acceptance.

The owner's speech path remains unresolved. Recent microphone tests received
audio but did not accept and execute the intended command. Diagnostics include
`speech_unclear`, `no_usable_speech`, and `wake_phrase_missing`. No device action
was executed from those failed turns. The temporary higher microphone volume
used during diagnosis was restored to its original level.

The larger pre-existing English speech model was inspected but has not been
integrated or accepted. No recognition threshold was lowered to force an action.

Live telephony, production cloud/mobile enrolment, general autonomous PC workflows,
full-duplex voice, and broad coding-project acceptance remain incomplete. See the
roadmap for the full task list. Historical reports retain their own test dates and
versions; installed capability and connection states are not acceptance evidence.

## Publication Boundary

Pre-publication verification completed on this source:

- Local Python discovery: 478 tests run, 465 passed, 13 optional cloud tests skipped,
  no failures or errors. The initially stalled IPC run was stopped, its shutdown
  race was fixed with regression coverage, and the complete suite was rerun.
- Isolated cloud environment: all 13 cloud/telephony security contract tests passed.
- JavaScript syntax checks passed for the interface and Three.js scene.
- Desktop (1440x1000) and mobile (390x844) browser checks passed on a separate
  rerun after the unit suite: authenticated backend, nonblank moving WebGL canvas,
  all three projection controls, unclipped dock controls, no horizontal overflow,
  and no browser errors. The first concurrent run had transient connection errors
  and premature render sampling; it was not counted as a pass.
- The staged source scan found no private-path artifacts, matching live portal
  token, apparent real credential patterns, private phone numbers, or oversized files.

These are code/contract checks, not successful owner microphone acceptance or a
production deployment. .NET and Android build/signing gates were not rerun for this
source publication; their historical evidence remains version-specific.

The existing GitHub history and license are preserved. The upload contains source,
required source assets, tests, and documentation. Per-install credentials, private
databases and transcripts, generated work products, model weights, SDKs, build
outputs, and caches are excluded. No live account configuration is published.
