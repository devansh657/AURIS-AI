from __future__ import annotations

import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


INSTANT_LIMIT_MS = 1200
FAST_MODEL_LIMIT_MS = 1600
WARM_MODEL_LIMIT_MS = 8000
FIRST_AUDIO_LIMIT_MS = 2500


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def timed_command(client: AurisLocalClient, command: str) -> tuple[dict, int]:
    started = time.perf_counter()
    response = client.command(
        command,
        private=True,
        conversation_id="auris-private-latency-acceptance",
    )
    return response, round((time.perf_counter() - started) * 1000)


def main() -> None:
    client = AurisLocalClient()
    status = client.status()
    model = status.get("model") or {}
    voice = status.get("voice") or {}
    require(
        (model.get("fast") or {}).get("warm") is True,
        "The fast local model was not warm at AURIS readiness.",
    )
    require(voice.get("neural_worker_online") is True, "The neural voice worker is offline.")

    instant, instant_ms = timed_command(client, "AURIS, are you ready")
    instant_intelligence = (instant.get("result") or {}).get("intelligence") or {}
    require(
        instant_intelligence.get("provider") == "auris_instant_kernel",
        "The greeting did not use the instant conversational kernel.",
    )
    require(instant_ms <= INSTANT_LIMIT_MS, f"Instant response took {instant_ms} ms.")

    fast_response, fast_ms = timed_command(client, "AURIS, tell me a joke")
    fast_intelligence = (fast_response.get("result") or {}).get("intelligence") or {}
    require(fast_intelligence.get("route") == "fast", "The casual probe did not use the fast route.")
    require(fast_ms <= FAST_MODEL_LIMIT_MS, f"Fast model response took {fast_ms} ms.")

    quality_deadline = time.monotonic() + 30
    while time.monotonic() < quality_deadline:
        if (client.status().get("model") or {}).get("warm") is True:
            break
        time.sleep(0.2)
    require(
        (client.status().get("model") or {}).get("warm") is True,
        "The quality model did not finish its background prime.",
    )

    model_response, model_ms = timed_command(
        client,
        "AURIS, in one sentence, explain why a compass points north",
    )
    model_intelligence = (model_response.get("result") or {}).get("intelligence") or {}
    require(model_intelligence.get("provider") == "ollama", "The model probe did not use Ollama.")
    require(model_intelligence.get("route") == "quality", "The reasoning probe did not use the quality route.")
    require(model_ms <= WARM_MODEL_LIMIT_MS, f"Warm model response took {model_ms} ms.")

    spoken = client.speak("Response systems online.")
    require(spoken.get("ok") is True, "The neural voice broker rejected the latency phrase.")
    deadline = time.monotonic() + 15
    first_audio_ms = None
    while time.monotonic() < deadline:
        voice = (client.status().get("voice") or {})
        first_audio_ms = voice.get("last_first_audio_ms")
        if first_audio_ms is not None:
            break
        time.sleep(0.15)
    require(first_audio_ms is not None, "The voice broker did not report first-audio latency.")
    require(
        int(first_audio_ms) <= FIRST_AUDIO_LIMIT_MS,
        f"Neural first audio took {first_audio_ms} ms.",
    )

    print(
        json.dumps(
            {
                "ok": True,
                "private_session": True,
                "instant": {
                    "elapsed_ms": instant_ms,
                    "limit_ms": INSTANT_LIMIT_MS,
                    "reply": (instant.get("result") or {}).get("message"),
                },
                "warmed_model": {
                    "elapsed_ms": model_ms,
                    "generation_ms": model_intelligence.get("duration_ms"),
                    "limit_ms": WARM_MODEL_LIMIT_MS,
                    "model": model_intelligence.get("model"),
                },
                "fast_model": {
                    "elapsed_ms": fast_ms,
                    "generation_ms": fast_intelligence.get("duration_ms"),
                    "limit_ms": FAST_MODEL_LIMIT_MS,
                    "model": fast_intelligence.get("model"),
                },
                "voice": {
                    "first_audio_ms": first_audio_ms,
                    "limit_ms": FIRST_AUDIO_LIMIT_MS,
                    "provider": voice.get("provider"),
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
