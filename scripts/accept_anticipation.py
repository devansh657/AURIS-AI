from __future__ import annotations

import http.cookiejar
import json
import re
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import HTTPCookieProcessor, build_opener, urlopen


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8765"
EXPECTED_VERSION = "0.8.34"
DELIVERY_CLASSES = {
    "INTERRUPT NOW",
    "NEXT BRIEFING",
    "PASSIVE NOTIFICATION",
    "LOG ONLY",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def read_json(opener, path: str) -> dict:
    with opener.open(f"{BASE_URL}{path}", timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    with urlopen(f"{BASE_URL}/api/health", timeout=8) as response:
        health = json.loads(response.read().decode("utf-8"))
    require(health.get("version") == EXPECTED_VERSION, f"Expected AURIS {EXPECTED_VERSION}.")

    token = (ROOT / "data" / "portal.token").read_text(encoding="ascii").strip()
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with opener.open(f"{BASE_URL}/?access_token={quote(token)}", timeout=8) as response:
        html = response.read().decode("utf-8")
    with opener.open(f"{BASE_URL}/app.js", timeout=8) as response:
        app = response.read().decode("utf-8")
    with opener.open(f"{BASE_URL}/styles.css", timeout=8) as response:
        styles = response.read().decode("utf-8")

    ids = set(re.findall(r'id="([^"]+)"', html))
    required_ids = {
        "attentionMetrics",
        "dailyAttention",
        "dailyOpportunities",
        "operationsQueryForm",
        "operationsGraph",
        "eveningDebrief",
    }
    require(required_ids <= ids, "The live Daily Command Centre is missing anticipation controls.")
    require("renderOperationsIntelligence" in app, "The live portal does not render operations intelligence.")
    require(".operations-grid" in styles and ".attention-signal" in styles, "Anticipation styling is absent.")

    query = urlencode({"project_id": "auris-one", "q": "AURIS One"})
    operations = read_json(opener, f"/api/anticipation?{query}")["operations"]
    graph = operations["graph"]
    attention = operations["attention"]
    daily = operations["daily"]
    evening = operations["evening"]
    require(graph.get("provenance") == "real_durable_state", "Graph provenance is not explicit.")
    require(graph.get("nodes"), "The live project graph is empty.")
    require(graph.get("matched_node_ids"), "The live graph query did not match AURIS One.")
    require(
        all(item.get("provenance") == "real_durable_state" for item in attention.get("items", [])),
        "An attention signal lacks durable provenance.",
    )
    require(
        all(item.get("delivery") in DELIVERY_CLASSES for item in attention.get("items", [])),
        "An attention signal used an unsupported delivery class.",
    )
    require(
        all(item.get("advisory_only") is True for item in attention.get("items", [])),
        "An anticipation signal is not marked advisory-only.",
    )
    require(daily.get("mailbox_loaded") is False, "Daily intelligence silently loaded mailbox context.")
    require(daily.get("external_calendar_loaded") is False, "Daily intelligence silently loaded an external calendar.")
    require(evening.get("kind") == "evening", "The evening debrief contract is absent.")

    private_query = urlencode(
        {"project_id": "auris-one", "q": "AURIS One", "private": "true"}
    )
    private = read_json(opener, f"/api/anticipation?{private_query}")["operations"]
    require(private["graph"]["nodes"] == [], "Private Session exposed operations graph nodes.")
    require(private["graph"]["edges"] == [], "Private Session exposed operations graph edges.")
    require(private["daily"]["schedule"] == [], "Private Session exposed scheduled detail.")

    print(
        json.dumps(
            {
                "ok": True,
                "version": health["version"],
                "ui_contracts": sorted(required_ids),
                "attention_signals": len(attention.get("items", [])),
                "delivery_counts": attention.get("delivery_counts"),
                "graph": {
                    "nodes": len(graph["nodes"]),
                    "edges": len(graph["edges"]),
                    "matches": len(graph["matched_node_ids"]),
                    "provenance": graph["provenance"],
                },
                "daily_external_context": {
                    "mailbox_loaded": daily["mailbox_loaded"],
                    "external_calendar_loaded": daily["external_calendar_loaded"],
                    "live_weather": daily["live_weather"],
                },
                "private_graph": "suppressed",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
