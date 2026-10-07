from __future__ import annotations

import http.cookiejar
import json
import time
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8765"
EXPECTED_VERSION = "0.8.34"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def request_json(opener, path: str, *, method: str = "GET", body: dict | None = None, csrf: str = "") -> dict:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if payload else {}
    if method not in {"GET", "HEAD"}:
        headers["X-AURIS-CSRF"] = csrf
    request = Request(f"{BASE_URL}{path}", data=payload, headers=headers, method=method)
    with opener.open(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    with urlopen(f"{BASE_URL}/api/health", timeout=8) as response:
        health = json.loads(response.read().decode("utf-8"))
    require(health.get("version") == EXPECTED_VERSION, f"Expected AURIS {EXPECTED_VERSION}.")

    token = (ROOT / "data" / "portal.token").read_text(encoding="ascii").strip()
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with opener.open(f"{BASE_URL}/?access_token={quote(token)}", timeout=8) as response:
        html = response.read().decode("utf-8")
    session = request_json(opener, "/api/session")
    csrf = session["session"]["csrf_token"]
    required_ids = {"watchForm", "watchMetric", "watchThreshold", "watchesView", "watchAlertsView"}
    require(all(f'id="{item}"' in html for item in required_ids), "Proactive watch UI is incomplete.")

    predictions = request_json(
        opener, "/api/predictions?" + urlencode({"project_id": "auris-one", "private": "false"})
    )["predictive_intelligence"]
    signal = next((item for item in predictions["forecasts"] if item["evidence_ids"]), None)
    require(signal is not None, "No evidence-backed predictive signal is available for live acceptance.")
    created = request_json(
        opener,
        "/api/watches",
        method="POST",
        csrf=csrf,
        body={
            "project_id": "auris-one",
            "metric": signal["metric"],
            "operator": "gte",
            "threshold": signal["score"],
            "interval_seconds": 60,
            "cooldown_seconds": 300,
            "private": False,
        },
    )["watch"]
    watch_id = created["watch_id"]
    alert = None
    try:
        for _ in range(8):
            dashboard = request_json(
                opener, "/api/watches?" + urlencode({"project_id": "auris-one", "private": "false"})
            )["proactive"]
            alert = next((item for item in dashboard["alerts"] if item["watch_id"] == watch_id), None)
            if alert:
                break
            time.sleep(1)
        require(alert is not None, "The live background engine did not deliver the threshold transition.")
        require(alert["advisory_only"] is True, "The alert crossed the advisory boundary.")
        require(alert["automatic_action"] is False, "The alert claimed automatic execution authority.")
        require(alert["evidence_ids"], "The alert has no durable evidence IDs.")
        require(dashboard["policy"]["automatic_action"] is False, "Watch policy enabled automatic action.")
        private = request_json(
            opener, "/api/watches?" + urlencode({"project_id": "auris-one", "private": "true"})
        )["proactive"]
        require(private["watches"] == [] and private["alerts"] == [], "Private Session exposed watch state.")
    finally:
        request_json(opener, f"/api/watches/{quote(watch_id)}", method="DELETE", csrf=csrf)

    voice_path = request_json(
        opener,
        "/api/command",
        method="POST",
        csrf=csrf,
        body={
            "command": "AURIS, watch workload pressure above 100 every 15 minutes",
            "project_id": "auris-one",
            "mode": "command",
            "private": False,
            "conversation_id": "proactive-live-acceptance",
        },
    )
    require(voice_path["plan"]["task_type"] == "proactive_watch", "Natural watch command was misrouted.")
    require(voice_path["plan"]["state"] == "completed", "Natural watch command did not complete.")
    command_watch = voice_path["result"]["proactive_action"]["watch"]
    cancel_path = request_json(
        opener,
        "/api/command",
        method="POST",
        csrf=csrf,
        body={
            "command": "AURIS, stop the workload pressure watch",
            "project_id": "auris-one",
            "mode": "command",
            "private": False,
            "conversation_id": "proactive-live-acceptance",
        },
    )
    require(cancel_path["result"]["proactive_action"]["watch"]["enabled"] is False, "Natural cancel did not disable the watch.")
    request_json(opener, f"/api/watches/{quote(command_watch['watch_id'])}", method="DELETE", csrf=csrf)

    print(json.dumps({
        "ok": True,
        "version": health["version"],
        "watch_id": watch_id,
        "metric": alert["metric"],
        "observed_value": alert["observed_value"],
        "threshold": alert["threshold"],
        "evidence_count": len(alert["evidence_ids"]),
        "advisory_only": alert["advisory_only"],
        "automatic_action": alert["automatic_action"],
        "private_watches": len(private["watches"]),
        "ui_contracts": sorted(required_ids),
        "cleanup": "watch_and_alert_deleted",
        "natural_command_task": voice_path["plan"]["task_type"],
        "natural_cancel_enabled": cancel_path["result"]["proactive_action"]["watch"]["enabled"],
    }, indent=2))


if __name__ == "__main__":
    main()
