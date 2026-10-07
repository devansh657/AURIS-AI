from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


EXPECTED_VERSION = "0.8.34"


def main() -> None:
    with urlopen("http://127.0.0.1:8765/api/health", timeout=8) as response:
        health = json.loads(response.read().decode("utf-8"))
    if health.get("version") != EXPECTED_VERSION:
        raise SystemExit(f"Expected AURIS {EXPECTED_VERSION}, received {health.get('version') or 'unknown'}.")

    client = AurisLocalClient()
    status = client.status()
    local_ipc = status.get("local_ipc") or {}
    if not local_ipc.get("connected"):
        raise SystemExit("Authenticated native IPC is not connected.")

    response = client.command(
        "AURIS, research deeply whether passkeys reduce phishing risk compared with passwords",
        conversation_id="auris-live-deep-research-acceptance",
    )
    plan = response.get("plan") or {}
    action = (response.get("result") or {}).get("research_action") or {}
    ledger = action.get("coverage_ledger") or {}
    sources = action.get("sources") or []
    claims = action.get("claims") or []
    source_ids = {source.get("source_id") for source in sources}
    claim_source_ids = {
        source_id
        for claim in claims
        for source_id in (claim.get("source_ids") or []) + (claim.get("counterevidence_source_ids") or [])
    }
    checks = {
        "mission_completed": plan.get("state") == "completed",
        "deep_mode": action.get("mode") == "deep",
        "definition_of_done": action.get("definition_of_done_met") is True,
        "source_threshold": len(sources) >= 4,
        "origin_diversity": ledger.get("origin_count", 0) >= 3,
        "primary_source": ledger.get("primary_source_count", 0) >= 1,
        "claim_threshold": len(claims) >= 2,
        "counterevidence_cycles": ledger.get("counterevidence_queries", 0) >= 2,
        "coverage_ledger": ledger.get("ledger_complete") is True,
        "validated_claim_sources": bool(claim_source_ids) and claim_source_ids <= source_ids,
        "no_excerpts_persisted": all("excerpt" not in source for source in sources),
    }
    evidence = {
        "ok": all(checks.values()),
        "version": health.get("version"),
        "transport": local_ipc.get("transport"),
        "task_id": plan.get("task_id"),
        "mission_state": plan.get("state"),
        "mode": action.get("mode"),
        "source_count": len(sources),
        "origin_count": ledger.get("origin_count"),
        "primary_source_count": ledger.get("primary_source_count"),
        "claim_count": len(claims),
        "branch_coverage_percent": ledger.get("branch_coverage_percent"),
        "duplicate_count": ledger.get("duplicate_count"),
        "checks": checks,
    }
    print(json.dumps(evidence, ensure_ascii=True, sort_keys=True))
    if not evidence["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
