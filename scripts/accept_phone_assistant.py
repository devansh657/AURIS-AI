from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient
from auris.telephony_agent import simulate_call


EXPECTED_VERSION = "0.8.34"


def _responder(messages, _system):
    if "private post-call brief" in messages[-1]["content"]:
        return json.dumps(
            {
                "summary": "A caller reported an urgent meeting change and requested Devansh.",
                "caller_request": "Speak with Devansh.",
                "promised_actions": [],
                "urgency": "urgent",
                "follow_up": "Review the transferred call.",
            }
        )
    return "I can take a concise message for Devansh."


def main() -> None:
    with urlopen("http://127.0.0.1:8765/api/health", timeout=8) as response:
        health = json.loads(response.read().decode("utf-8"))
    if health.get("version") != EXPECTED_VERSION:
        raise SystemExit(f"Expected AURIS {EXPECTED_VERSION}, received {health.get('version') or 'unknown'}.")

    status = AurisLocalClient().status()
    telephony = (status.get("integrations") or {}).get("telephony") or {}
    result = simulate_call(
        ["My name is Alex.", "This is urgent. Please connect me to Devansh."],
        responder=_responder,
    )
    summary = result.get("summary") or {}
    turns = result.get("turns") or []
    checks = {
        "simulation_completed": result.get("ok") is True,
        "urgent_handoff": bool(turns) and turns[-1].get("transfer") is True,
        "ai_disclosure": summary.get("disclosure_delivered") is True,
        "caller_masked": summary.get("caller") == "***0002",
        "summary_generated": bool(summary.get("summary")),
        "no_audio_recording": summary.get("audio_recorded") is False,
        "no_raw_transcript": summary.get("raw_transcript_persisted") is False and "transcript" not in summary,
        "no_model_commitments": summary.get("promised_actions") == [],
        "provider_truthful": telephony.get("connected") is not True,
    }
    evidence = {
        "ok": all(checks.values()),
        "version": health.get("version"),
        "provider": telephony.get("provider"),
        "provider_state": telephony.get("state"),
        "simulation": "local_policy_and_handoff_contract",
        "checks": checks,
    }
    print(json.dumps(evidence, ensure_ascii=True, sort_keys=True))
    if not evidence["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
