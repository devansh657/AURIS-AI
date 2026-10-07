# AURIS 0.8.32 Voice Readiness

## Changes

- Replaced the default Windows recognizer with a persistent offline Whisper tiny.en CPU/int8 worker in `.speech-venv`. Model files are pinned and verified at setup and worker startup; runtime model downloads are disabled.
- WebRTC VAD operates on 20 ms PCM frames, retains at most 300 ms of preroll, and finishes normal utterances after 600 ms of silence. Microphone audio remains in bounded RAM, is never uploaded or written to disk, and is discarded after each request. Commands longer than 30 seconds are rejected rather than truncated and executed.
- Wake recognition first checks unbiased transcription. Candidate phonetic spellings receive a second transcription with competing names; only a final leading AURIS/Oris prefix is accepted. These decoder scores are uncalibrated and do not identify the speaker. This is not a guarantee against every false wake or adversarial sound.
- A whole wake-plus-command sentence routes immediately. A bare wake opens a silent command window. Repeated wake-only phrases and leading passive listening boilerplate produce no audio, including `Yes Devansh, I am listening.` Actual result text following the boilerplate is preserved.
- Priority input cancels the current wake window through a local Windows event addressed to the actual worker child, without reloading the model. Correlated generations prevent an older capture from clearing the newer capture's state.
- Neural output uses native cancelable Windows WAV playback, one voice provider locked at startup, inherited owner-only temporary-directory permissions, generation-safe prefetch, and fresh latency metrics for each reply.
- The existing cinematic interface is preserved. It now displays real speech/command interpretation state and READY instead of the dormant label. Provider, microphone, fallback, and input errors are available in voice diagnostics.

## Verified Evidence

- 26/26 synthetic spoken-audio cases passed across Microsoft Hazel and David, including whole wake commands, explicit listening, stop interruption, similar-name rejection, and background conversation. Silence was rejected. These checks do not execute device actions or use the room microphone.
- Synthetic spoken `Hey AURIS, open Notepad` passed through the actual decoder and command-extraction path into the live authenticated backend. The signed launch action completed, claimed its one-use nonce, and independently observed a matching Notepad process/window.
- The real Realtek microphone stream opened and shut down cleanly. Live priority listening retained the same worker PID and took 2,056 ms for a requested 2,000 ms window, without fallback or an input error.
- Measured private-session samples: deterministic response 36 ms; resident fast-model response 661 ms; resident quality-model response 4,255 ms; first Kokoro audio 630 ms after speech text was submitted. These are separate stages, not an end-to-end voice latency promise.
- Security gate passed 376 local, 13 cloud, and 7 Windows/.NET contracts; frontend syntax, eight Windows fallback grammar routing cases, the 26 acoustic cases, and Android APK v2 signature verification passed. The production-ready flag remains false.
- The full discovered suite completed 421 tests: 408 passed and 13 cloud-runtime tests were skipped in the base environment. The separate cloud environment passed its 13 contracts.
- Desktop 1440x1000 and mobile 390x844 screenshots showed an online backend, nonblank Three.js rendering, no script/network failures, no horizontal overflow, and unclipped dock controls.

## Remaining Limits

Your own voice, accent, room noise, and microphone placement still need a physical acceptance check. The synthetic suite is not a measured real-world recognition rate. English is the configured speech language, there is no speaker authentication or acoustic echo cancellation, and full-duplex conversation is not claimed. Unsupported PC tasks, sensitive actions, unavailable integrations, and approval requirements retain their existing honest failure boundaries.

Say `Hey AURIS, open Notepad` in one sentence with Wake enabled. To isolate wake recognition from dictation, press Listen and say `open Notepad`. AURIS should act and report the outcome, without a preliminary listening announcement.

## Repeat Checks

```powershell
.\.speech-venv\Scripts\python.exe scripts\accept_local_speech.py
.\.speech-venv\Scripts\python.exe scripts\accept_speech_action.py
python scripts\accept_fast_voice.py
python scripts\accept_response_latency.py
```

The speech-action check opens Notepad but does not edit or close documents. The latency check plays a short test reply. The acoustic test runs entirely in memory and does not save the synthetic WAV/PCM data.
