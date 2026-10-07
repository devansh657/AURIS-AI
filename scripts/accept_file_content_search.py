from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


EXPECTED_VERSION = "0.8.34"
EXPECTED_FILE = str(Path.home() / "Documents" / "AURIS 089 Acceptance.txt")


def main() -> int:
    with urlopen("http://127.0.0.1:8765/api/health", timeout=8) as response:
        health = json.loads(response.read().decode("utf-8"))
    response = AurisLocalClient().command(
        "AURIS, find phrase verified note creation in my files",
        conversation_id="accept-file-content-search",
    )
    plan = response.get("plan") or {}
    result = response.get("result") or {}
    action = result.get("file_action") or {}
    items = action.get("items") or []
    matched = next((item for item in items if item.get("path") == EXPECTED_FILE), None)
    checks = {
        "release": health.get("version") == EXPECTED_VERSION,
        "mission_completed": plan.get("state") == "completed",
        "file_workflow": plan.get("task_type") == "file_workflow",
        "content_mode": action.get("mode") == "content",
        "expected_file": matched is not None,
        "line_number": bool(matched and matched.get("first_matching_line") == 1),
        "match_count": bool(matched and matched.get("match_count") == 1),
        "no_content_persisted": all(
            set(item) <= {"name", "path", "size_bytes", "modified_at", "match_count", "first_matching_line"}
            for item in items
        ),
        "byte_budget": 0 < int(action.get("inspected_bytes") or 0) <= 20 * 1024 * 1024,
    }
    report = {
        "ok": all(checks.values()),
        "task_id": plan.get("task_id"),
        "message": result.get("message"),
        "verification": result.get("verification"),
        "matched_path": matched.get("path") if matched else None,
        "checks": checks,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
