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


def request_json(opener, path: str, *, csrf: str = "", body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if csrf:
        headers["X-AURIS-CSRF"] = csrf
    request = Request(f"{BASE_URL}{path}", data=data, headers=headers)
    with opener.open(request, timeout=180) as response:
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

    council_status = request_json(opener, "/api/council/status")["council"]
    deadline = time.monotonic() + 120
    while council_status.get("quality_priming") and time.monotonic() < deadline:
        time.sleep(2)
        council_status = request_json(opener, "/api/council/status")["council"]
    require(not council_status.get("quality_priming"), "Quality model did not finish startup priming.")

    required_ids = {
        "decisionForm",
        "decisionMetrics",
        "decisionRecommendation",
        "decisionEvidence",
        "decisionOutcomeForm",
        "decisionLearning",
        "decisionRootCause",
        "decisionLesson",
        "decisionCases",
    }
    require(all(f'id="{item}"' in html for item in required_ids), "Decision Lab UI is incomplete.")

    payload = {
        "objective": "AURIS 0.8.27 acceptance deployment choice",
        "criteria": [{"name": "verification", "weight": 2}],
        "options": [
            {
                "name": "Verified staged release",
                "scores": {"verification": 5},
                "score_source": "AURIS acceptance fixture",
                "success_probability": 0.9,
                "probability_source": "AURIS acceptance fixture",
            },
            {
                "name": "Unverified direct release",
                "scores": {"verification": 1},
                "score_source": "AURIS acceptance fixture",
                "success_probability": 0.4,
                "probability_source": "AURIS acceptance fixture",
            },
        ],
    }
    created = request_json(
        opener,
        "/api/decisions/analyse",
        csrf=csrf,
        body={
            "decision": payload,
            "project_id": "auris-one",
            "private": False,
            "council": {
                "requested": True,
                "complexity": 0.8,
                "risk": "medium",
                "max_calls": 5,
                "token_budget": 1400,
            },
        },
    )
    require(created["analysis"]["recommendation"]["option"] == "Verified staged release", "Expected option was not selected.")
    require(created["analysis"]["recommendation"]["forecast_probability"] == 0.9, "Forecast provenance was not retained.")
    require(created["analysis"]["model_council"]["activated"] is True, "Model council was not activated.")
    require(created["analysis"]["model_council"]["state"] == "completed", "Model council did not complete.")
    require(len(created["analysis"]["model_council"]["roles"]) == 5, "Five council roles did not complete.")
    case_id = created["decision"]["case_id"]

    listed = request_json(
        opener,
        "/api/decisions?" + urlencode({"project_id": "auris-one"}),
    )
    require(any(item["case_id"] == case_id for item in listed["decisions"]), "Decision case was not persisted.")

    outcome = request_json(
        opener,
        f"/api/decisions/{case_id}/outcomes",
        csrf=csrf,
        body={
            "actual_success": True,
            "expected_summary": "The staged release passes verification.",
            "actual_summary": "Acceptance checks passed.",
            "difference_summary": "No material variance.",
            "root_cause": "Bounded staged verification.",
            "lesson": "Preserve verifier-gated staged release checks.",
            "confidence_update": "increased",
        },
    )
    require(outcome["outcome"]["actual_success"] is True, "Observed outcome was not recorded.")
    require(outcome["calibration"]["probabilistic_forecasts_scored"] >= 1, "Forecast was not scored.")
    require(outcome["calibration"]["calibrated"] is False, "AURIS claimed calibration before the sample gate.")
    require(outcome["outcome"]["confidence_update"] == "increased", "Confidence update was not retained.")
    require(outcome["outcome_learning"]["automatic_policy_changes"] is False, "Outcome learning crossed the policy boundary.")

    natural = request_json(
        opener,
        "/api/command",
        csrf=csrf,
        body={
            "command": "AURIS, compare staged verification versus direct release",
            "project_id": "auris-one",
            "mode": "command",
            "conversation_id": "accept-decision-intelligence",
        },
    )
    require(natural["plan"]["task_type"] == "decision_analysis", "Natural comparison missed decision routing.")
    require(natural["plan"]["state"] == "partially_completed", "Unscored natural comparison should remain partial.")
    require(natural["result"]["decision_analysis"]["recommendation"]["option"] is None, "Natural comparison invented a recommendation.")

    print(
        json.dumps(
            {
                "ok": True,
                "version": health["version"],
                "case_id": case_id,
                "recommendation": created["analysis"]["recommendation"],
                "epistemic_status": created["analysis"]["epistemic_status"],
                "model_council": {
                    "state": created["analysis"]["model_council"]["state"],
                    "calls_used": created["analysis"]["model_council"]["calls_used"],
                    "independent_models": created["analysis"]["model_council"]["independent_models"],
                },
                "outcome_id": outcome["outcome"]["outcome_id"],
                "outcome_learning": outcome["outcome_learning"],
                "natural_command_task_id": natural["plan"]["task_id"],
                "calibration": outcome["calibration"],
                "ui_contracts": sorted(required_ids),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
