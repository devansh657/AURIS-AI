from __future__ import annotations

import http.cookiejar
import json
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8765"
EXPECTED_VERSION = "0.8.34"
EXPECTED_METRICS = {
    "project_delay_risk",
    "deadline_risk",
    "workload_pressure",
    "resource_conflicts",
    "follow_up_likelihood",
    "mission_failure_probability",
    "opportunity_relevance",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def request_json(opener, path: str) -> dict:
    request = Request(f"{BASE_URL}{path}")
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
    request_json(opener, "/api/session")

    required_ids = {"predictiveMetrics", "predictiveSignals"}
    require(all(f'id="{item}"' in html for item in required_ids), "Predictive UI is incomplete.")
    intelligence = request_json(
        opener,
        "/api/predictions?" + urlencode({"project_id": "auris-one", "private": "false"}),
    )["predictive_intelligence"]
    forecasts = intelligence["forecasts"]
    require({item["metric"] for item in forecasts} == EXPECTED_METRICS, "Predictive metric coverage is incomplete.")
    require(all(item["advisory_only"] for item in forecasts), "A forecast crossed the advisory boundary.")
    require(all(item["provenance"] == "real_durable_state" for item in forecasts), "Forecast provenance is missing.")
    require(all(item["uncertainty"] for item in forecasts), "Forecast uncertainty is missing.")
    require(intelligence["method"]["automatic_action"] is False, "Prediction enabled automatic action.")

    failure = next(item for item in forecasts if item["metric"] == "mission_failure_probability")
    if failure["sample_sufficient"]:
        require(failure["sample_size"] >= failure["minimum_sample_size"], "Failure sample gate is inconsistent.")
        require(failure["probability"] is not None and len(failure["interval"]) == 2, "Empirical uncertainty interval is missing.")
    else:
        require(failure["probability"] is None, "Failure probability was emitted below the sample gate.")
    require(
        all(item["probability"] is None for item in forecasts if item["metric"] != "mission_failure_probability"),
        "A heuristic operational score was mislabeled as probability.",
    )

    private = request_json(
        opener,
        "/api/predictions?" + urlencode({"project_id": "auris-one", "private": "true"}),
    )["predictive_intelligence"]
    require(private["forecasts"] == [], "Private Session exposed predictive state.")

    print(
        json.dumps(
            {
                "ok": True,
                "version": health["version"],
                "metrics": sorted(EXPECTED_METRICS),
                "top_signal": intelligence["top_signal"],
                "failure_forecast": failure,
                "private_forecasts": len(private["forecasts"]),
                "ui_contracts": sorted(required_ids),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
