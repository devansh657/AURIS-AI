from __future__ import annotations

import http.cookiejar
import json
from pathlib import Path
from urllib.error import HTTPError
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

    required_ids = {"worldModelMetrics", "worldActionForm", "worldActionSelect", "worldAlternativeSelect", "worldSimulation"}
    require(all(f'id="{item}"' in html for item in required_ids), "World-model UI is incomplete.")

    model = request_json(
        opener,
        "/api/world-model?" + urlencode({"project_id": "auris-one", "private": "false"}),
    )["world_model"]
    require(bool(model["snapshot_id"]), "World-model snapshot is missing.")
    require(len(model["entities"]) > 0, "World model contains no real entities.")
    require(len(model["relationships"]) > 0, "World model contains no real relationships.")
    require(model["learned_model"] is False, "Deterministic model was mislabeled as learned.")
    require(all(not action["executable"] for action in model["possible_actions"]), "A simulated action was marked executable.")
    action = next(
        item for item in model["possible_actions"] if item["risk_level"] == "read_only"
    )

    response = request_json(
        opener,
        "/api/world-model/simulate",
        csrf=csrf,
        body={
            "snapshot_id": model["snapshot_id"],
            "action_id": action["action_id"],
            "project_id": "auris-one",
            "private": False,
        },
    )
    simulation = response["simulation"]
    causal = response["causal_analysis"]
    require(simulation["executed"] is False, "Simulation claimed real execution.")
    require(simulation["approval_requested"] is False, "Simulation created an approval.")
    require(simulation["advisory_only"] is True, "Simulation lost its advisory boundary.")
    require(causal["intervention"]["notation"].startswith("do("), "Causal intervention notation is missing.")
    require(causal["identifiability"]["downstream_outcomes"] == "not_identified", "Downstream causality was overclaimed.")
    require(causal["downstream_causal_effects"] == [], "Graph association was mislabeled as causal effect.")
    require(causal["correlation_treated_as_causation"] is False, "Correlation was mislabeled as causation.")

    try:
        request_json(
            opener,
            "/api/world-model/simulate",
            csrf=csrf,
            body={
                "snapshot_id": "obsolete",
                "action_id": action["action_id"],
                "project_id": "auris-one",
            },
        )
    except HTTPError as error:
        require(error.code == 409, "Stale simulation returned the wrong status.")
    else:
        raise SystemExit("Stale world-model snapshot was accepted.")

    private = request_json(
        opener,
        "/api/world-model?" + urlencode({"project_id": "auris-one", "private": "true"}),
    )["world_model"]
    require(private["private_mode"] is True, "Private world model was not marked private.")
    require(private["entities"] == [], "Private world model exposed entities.")

    print(
        json.dumps(
            {
                "ok": True,
                "version": health["version"],
                "snapshot_id": model["snapshot_id"],
                "entities": len(model["entities"]),
                "relationships": len(model["relationships"]),
                "events": len(model["events"]),
                "possible_actions": len(model["possible_actions"]),
                "simulation_id": simulation["simulation_id"],
                "causal_analysis_id": causal["analysis_id"],
                "intervention": causal["intervention"]["notation"],
                "downstream_identifiability": causal["identifiability"]["downstream_outcomes"],
                "simulated_action": simulation["action"]["action_type"],
                "executed": simulation["executed"],
                "private_entities": len(private["entities"]),
                "ui_contracts": sorted(required_ids),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
