# AURIS Source Setup

This is the 0.8.34 development source. It is not a standalone installer or a
production-ready release. The current deployment is a Windows laptop with Codex
bundled Python/Node runtimes, local Ollama models, and separately provisioned
speech environments. The Windows launch scripts locate those bundled runtimes
under the current user's profile, not a checked-in runtime directory.

## Repository Contents

- `auris/`: local authenticated backend, voice broker, supervisor, policies,
  typed Windows/browser/file adapters, coding bridge, and verification.
- `auris_cloud/`: optional cloud command and inbound telephony contracts.
- `web/`: cinematic interface, Three.js scene, and vendored Three.js license.
- `windows/`: optional .NET device-service source and tests.
- `android/`: Android companion source and Gradle wrapper.
- `scripts/`: launch, setup, build, security, and explicitly scoped acceptance tools.
- `tests/` and `docs/`: contract tests, requirements, roadmap, and historical evidence.

## Local Prerequisites

Use Windows and Python 3.11 or newer. The existing launch scripts require the
Codex bundled Python runtime. Browser acceptance also requires Node and Microsoft
Edge. Optional components need their own dependencies; they are not silently
installed by starting the portal.

Install the Node dependencies with `npm ci` for browser-worker and Playwright
checks. The local core has no mandatory pip dependencies; optional cloud packages
are declared in `pyproject.toml` as `cloud` and `cloud-test` extras. Speech packages
are pinned in `requirements-speech.txt`, `requirements-voice.txt`, and
`requirements-voice-gpu.txt` and installed in isolated environments by the
corresponding setup scripts.

The existing launcher defaults to local Ollama models `qwen2.5:1.5b`, `gemma3:4b`,
and `nomic-embed-text`. Provision the configured models before expecting the
corresponding conversation, vision, or memory routes. Coding delegation separately
requires an installed, authenticated Codex CLI. Do not put credentials into files
that are committed to this repository.

## Speech And Launch

Setup requires network access for packages and verified model assets. It does not
upload microphone audio. GPU speech setup is optional and hardware-dependent;
Piper and Windows speech are startup fallbacks.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_speech.ps1 -PythonPath python
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_voice.ps1 -PythonPath python
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\launch_auris.ps1
```

Read `scripts/setup_voice_gpu.ps1` before provisioning GPU speech. Do not run
service installation, startup installation, cloud enrolment, or phone setup as
part of a basic source checkout unless those integrations are explicitly wanted.
The cloud, Android, and Windows directories contain their own component notes.

On first local start AURIS initializes its own `data/` state and authentication.
Never reuse another installation's portal token or signed device keys. The portal
is bound to loopback at `http://127.0.0.1:8765/`; an authenticated launcher or local
client establishes the session. Merely opening that URL is not an authentication
bypass.

## Verification

```powershell
python -m unittest discover -s tests -v
node --check web/app.js
node --check web/neural-core.js
```

Cloud tests require the optional cloud environment. .NET, Android, model-backed,
and live-PC checks require their separately provisioned dependencies. Acceptance
scripts are not all read-only: some deliberately open apps, create test files,
play speech, or operate approved browser controls. Inspect a script's scope before
running it; unit tests alone do not prove microphone or real-PC acceptance.

## Not Included In Git

`data/`, `dist/`, virtual environments, downloaded SDKs/models, `node_modules/`,
local `.env` files, certificates, tokens, private keys, logs, private databases,
browser profiles, generated documents, and build outputs remain local. Recreate
dependencies using the setup/build tools rather than copying private state.
