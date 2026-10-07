from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.capabilities import CAPABILITIES
from auris.local_client import AurisLocalClient


def main() -> int:
    client = AurisLocalClient()
    checks = []
    try:
        with urlopen("http://127.0.0.1:8765/api/capabilities", timeout=5) as response:
            unauthorized = response.status in {401, 403}
    except HTTPError as error:
        unauthorized = error.code in {401, 403}
    checks.append({"name": "unauthenticated_registry_refused", "ok": unauthorized})
    timings = []
    registry = {}
    for _ in range(5):
        started = time.perf_counter()
        registry = client._request("/api/capabilities", timeout=20)["registry"]
        timings.append(round((time.perf_counter() - started) * 1000))
    entries = {item["id"]: item for item in registry["capabilities"]}
    checks.append({"name": "catalog_matches_authenticated_api", "ok": set(entries) == {item.id for item in CAPABILITIES}})
    checks.append({"name": "availability_does_not_grant_authority_or_acceptance",
                   "ok": registry["permission_authority"] is False and registry["availability_is_acceptance"] is False})
    checks.append({"name": "outbound_calls_honestly_unavailable", "ok": entries["outbound_calls"]["state"] == "not_connected"})
    checks.append({"name": "exact_scope_permissions_and_verifiers_present",
                   "ok": all(item["scope"] and item["required_permissions"] and item["verifier"] and item["limitations"] for item in entries.values())})
    status = client.status()
    trust = status.get("device_trust") or {}
    checks.append({"name": "actual_local_device_trust_is_mapped_correctly",
                   "ok": trust.get("trust_state") == "local_hmac" and not trust.get("revoked") and entries["windows_actions"]["state"] == "available"})
    checks.append({"name": "status_and_capability_api_share_catalog",
                   "ok": {item["id"] for item in status["capability_registry"]["capabilities"]} == set(entries)})
    reply = client.command("what can you do", private=True, allow_failure=True)
    checks.append({"name": "spoken_help_uses_current_registry_limits",
                   "ok": "Not ready" in reply.get("result", {}).get("message", "") and "Phone assistant" in reply.get("result", {}).get("message", "")})
    report = {"ok": all(item["ok"] for item in checks), "kind": "live_authenticated_registry_acceptance",
              "physical_speech_tested": False, "device_actions_executed": False,
              "api_duration_ms": timings, "checks": checks,
              "states": {key: item["state"] for key, item in entries.items()}}
    output = ROOT / "data" / "acceptance" / "foundation-registry-0834.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
