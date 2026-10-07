from __future__ import annotations

import http.cookiejar
import json
import sys
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


BASE_URL = "http://127.0.0.1:8765"


def request(opener, path: str, *, method: str = "GET", csrf: str = "", body=None):
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if csrf:
        headers["X-AURIS-CSRF"] = csrf
    with opener.open(Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method), timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    token = (ROOT / "data" / "portal.token").read_text(encoding="ascii").strip()
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    opener.open(f"{BASE_URL}/?access_token={quote(token)}", timeout=8).read()
    session = request(opener, "/api/session")
    csrf = session["session"]["csrf_token"]
    marker = f"live-memory-acceptance-{uuid4()}"
    created_ids: list[str] = []
    evidence: dict[str, object] = {"ok": False, "marker": marker}
    try:
        first = request(
            opener,
            "/api/memories",
            method="POST",
            csrf=csrf,
            body={
                "content": "Acceptance service port is 8100",
                "category": "project",
                "project_id": "auris-one",
                "subject_key": marker,
                "environment": "acceptance",
            },
        )
        first_id = first["memory"]["memory_id"]
        created_ids.append(first_id)
        second = request(
            opener,
            "/api/memories",
            method="POST",
            csrf=csrf,
            body={
                "content": "Acceptance service port is 8101",
                "category": "project",
                "project_id": "auris-one",
                "subject_key": marker,
                "environment": "acceptance",
            },
        )
        second_id = second["memory"]["memory_id"]
        created_ids.append(second_id)
        require(second["requires_resolution"] is True, "Live API did not preserve the contradiction.")
        conflict_id = second["conflicts"][0]["conflict_id"]
        resolved = request(
            opener,
            f"/api/memory/conflicts/{quote(conflict_id)}/resolve",
            method="POST",
            csrf=csrf,
            body={"chosen_memory_id": second_id, "keep_both": False},
        )
        require(resolved["conflict"]["resolution"] == "selected_current", "Live conflict selection failed.")

        corrected = request(
            opener,
            f"/api/memories/{quote(second_id)}/correct",
            method="POST",
            csrf=csrf,
            body={
                "content": "Acceptance service port is 8102",
                "reason": "Live release acceptance correction.",
                "project_id": "auris-one",
                "subject_key": marker,
                "environment": "acceptance",
            },
        )
        corrected_id = corrected["memory"]["memory_id"]
        created_ids.append(corrected_id)
        history = request(opener, f"/api/memories/{quote(second_id)}/history")["history"]
        require(len(history["versions"]) >= 3, "Live history did not retain the temporal chain.")
        archive = request(opener, "/api/memories/export?project_id=auris-one")["archive"]
        require(corrected_id in {item["memory_id"] for item in archive["memories"]}, "Live export omitted the correction.")
        require("embedding" not in json.dumps(archive).casefold(), "Live export exposed embeddings.")
        evidence.update(
            {
                "ok": True,
                "conflict": "preserved_and_selected",
                "correction": "supersession_linked",
                "history_versions": len(history["versions"]),
                "export": "verified_without_embeddings",
            }
        )
    finally:
        for memory_id in reversed(created_ids):
            try:
                request(opener, f"/api/memories/{quote(memory_id)}", method="DELETE", csrf=csrf)
            except Exception:
                pass
        query = urlencode({"q": marker, "limit": 20})
        remaining = request(opener, f"/api/memories?{query}")
        evidence["cleanup"] = "complete" if not remaining["memories"] else "failed"

    require(evidence.get("cleanup") == "complete", "Live acceptance memories were not cleaned up.")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
