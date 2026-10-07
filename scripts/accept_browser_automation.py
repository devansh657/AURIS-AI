from __future__ import annotations

import http.cookiejar
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.database import delete_application_state


BASE_URL = "http://127.0.0.1:8765"
EXPECTED_VERSION = "0.8.34"
FIXTURE_URL = f"{BASE_URL}/browser-acceptance.html"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def request_json(opener, path: str, *, method: str = "GET", body: dict | None = None, csrf: str = "") -> dict:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if payload else {}
    if method not in {"GET", "HEAD"}:
        headers["X-AURIS-CSRF"] = csrf
    request = Request(f"{BASE_URL}{path}", data=payload, headers=headers, method=method)
    with opener.open(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def command(opener, csrf: str, text: str, *, private: bool = False) -> dict:
    return request_json(
        opener,
        "/api/command",
        method="POST",
        csrf=csrf,
        body={
            "command": text,
            "project_id": "auris-one",
            "mode": "private" if private else "command",
            "private": private,
            "conversation_id": "browser-live-acceptance",
        },
    )


def approve_once(opener, csrf: str, response: dict) -> dict:
    approval = response.get("approval") or {}
    approval_id = approval.get("approval_id")
    require(bool(approval_id), "The browser mutation did not create an approval record.")
    return request_json(
        opener,
        f"/api/approvals/{quote(approval_id)}/approve",
        method="POST",
        csrf=csrf,
        body={"scope": "once"},
    )


def require_fabric(result: dict, scope: str) -> None:
    fabric = result["browser_action"]["command_fabric"]
    require(fabric.get("permission_scope") == scope, f"Expected signed scope {scope}.")
    require(fabric.get("signature_verified") is True, "Browser command signature was not verified.")
    require(fabric.get("nonce_claimed") is True, "Browser command nonce was not claimed.")


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
    required_ids = {
        "browserMetrics", "browserNavigateForm", "browserUrl", "browserInspect",
        "browserFillForm", "browserFieldName", "browserFieldValue",
        "browserClickForm", "browserControlName", "browserPageView",
        "browserMissionForm", "browserMissionUrl", "browserMissionField",
        "browserMissionValue", "browserMissionControl", "browserStateView",
        "browserStateShow", "browserStateContinue",
    }
    require(all(f'id="{item}"' in html for item in required_ids), "Browser workspace UI is incomplete.")

    navigated = command(opener, csrf, f"open {FIXTURE_URL}")
    require(navigated["plan"]["task_type"] == "browser_workflow", "Navigation was misrouted.")
    require(navigated["plan"]["state"] == "completed", "Browser navigation did not complete.")
    nav_result = navigated["result"]
    require(nav_result["browser_action"]["page"]["title"] == "AURIS Browser Acceptance", "Page title was not observed.")
    require(nav_result["browser_action"]["page"]["content_trust"] == "untrusted_web_content", "Page trust label is missing.")
    require_fabric(nav_result, "browser_navigate")

    inspected = command(opener, csrf, "inspect the current browser page")
    require(inspected["plan"]["state"] == "completed", "Browser inspection did not complete.")
    inspect_result = inspected["result"]
    controls = inspect_result["browser_action"]["page"]["controls"]
    control_names = {item["name"] for item in controls}
    require({"Acceptance note", "Apply Preview"}.issubset(control_names), "Accessibility controls were not discovered.")
    require_fabric(inspect_result, "browser_inspect")

    approved_text = "browser acceptance 824"
    fill = command(opener, csrf, f'fill "Acceptance note" with "{approved_text}" in the browser')
    require(fill["plan"]["state"] == "awaiting_approval", "Browser fill did not pause for approval.")
    require(approved_text not in fill["approval"]["data_summary"], "Approval summary exposed the field value.")
    filled = approve_once(opener, csrf, fill)
    fill_task = filled["task"]
    require(fill_task["state"] == "completed", "Approved browser fill did not complete.")
    fill_result = fill_task["result"]
    require(fill_result["browser_action"]["ok"] is True, "Exact field read-back failed.")
    require(fill_result["browser_action"]["action"].get("value") is None, "Browser result exposed the field value.")
    require(fill_result["browser_action"]["action"].get("value_sha256"), "Browser result omitted the value digest.")
    require_fabric(fill_result, "browser_fill")

    click = command(opener, csrf, 'click "Apply Preview" button in the browser')
    require(click["plan"]["state"] == "awaiting_approval", "Browser click did not pause for approval.")
    clicked = approve_once(opener, csrf, click)
    click_task = clicked["task"]
    require(click_task["state"] == "completed", "Approved browser click did not complete.")
    click_result = click_task["result"]
    require(click_result["browser_action"]["ok"] is True, "The resulting page state did not change.")
    click_query = parse_qs(urlparse(click_result["browser_action"]["page"]["url"]).query, keep_blank_values=True)
    expected_note_digest = "sha256:" + hashlib.sha256(approved_text.encode()).hexdigest()[:16]
    require(click_query.get("note") == [expected_note_digest], "The expected redacted form outcome was not observed.")
    require_fabric(click_result, "browser_click")

    mission_note = "browser mission 825"
    mission_tag = "mission tag 825"
    mission = command(
        opener,
        csrf,
        f'run browser mission open "{FIXTURE_URL}" '
        f'then fill "Acceptance note" with "{mission_note}" '
        f'then fill "Mission tag" with "{mission_tag}" '
        'then click "Apply Preview"',
    )
    require(mission["plan"]["state"] == "awaiting_approval", "Browser mission did not pause for one-time approval.")
    require(mission_note not in mission["approval"]["data_summary"], "Mission approval exposed the first field value.")
    require(mission_tag not in mission["approval"]["data_summary"], "Mission approval exposed the second field value.")
    mission_approved = approve_once(opener, csrf, mission)
    mission_task = mission_approved["task"]
    require(mission_task["state"] == "completed", "Approved browser mission did not complete.")
    mission_result = mission_task["result"]
    mission_action = mission_result["browser_action"]
    require(mission_action["completed_steps"] == 4 and mission_action["failed_step"] is None, "Browser mission checkpoints are incomplete.")
    require([step["kind"] for step in mission_action["steps"]] == ["navigate", "fill", "fill", "click"], "Browser mission step order changed.")
    require(all(step["ok"] for step in mission_action["steps"]), "A browser mission checkpoint was not verified.")
    require(mission_note not in json.dumps(mission_action) and mission_tag not in json.dumps(mission_action), "Browser mission result exposed approved values.")
    mission_query = parse_qs(urlparse(mission_action["page"]["url"]).query)
    require(mission_query.get("note") == ["sha256:" + hashlib.sha256(mission_note.encode()).hexdigest()[:16]], "Mission note outcome digest was not observed.")
    require(mission_query.get("tag") == ["sha256:" + hashlib.sha256(mission_tag.encode()).hexdigest()[:16]], "Mission tag outcome digest was not observed.")
    require_fabric(mission_result, "browser_workflow")
    completed_state = mission_result["application_state"]
    require(completed_state["status"] == "completed", "Completed mission state was not recorded.")

    failed_mission = command(
        opener,
        csrf,
        f'run browser mission open "{FIXTURE_URL}" '
        'then fill "Acceptance note" with "first checkpoint" '
        'then fill "Missing field" with "must not continue" '
        'then click "Apply Preview"',
    )
    failed_approved = approve_once(opener, csrf, failed_mission)
    failed_result = failed_approved["task"]["result"]
    failed_action = failed_result["browser_action"]
    failed_state = failed_result["application_state"]
    require(failed_approved["task"]["state"] == "failed", "A mission with a missing field did not fail closed.")
    require(failed_action["completed_steps"] == 2 and failed_action["failed_step"] == 3, "The failed mission checkpoint is incorrect.")
    require(len(failed_action["steps"]) == 2, "A later browser mission step executed after failure.")
    require(urlparse(failed_action["page"]["url"]).query == "", "The final click executed after an earlier mission failure.")
    require(failed_state["status"] == "resumable", "The pre-control failure was not marked resumable.")
    require(failed_state["checkpoint"]["safe_to_retry"] is True, "The retry-safety checkpoint is missing.")
    require("must not continue" not in json.dumps(failed_state), "Application state exposed an approved field value.")

    state_api = request_json(opener, "/api/application-state?project_id=auris-one&private=false")["application_state"]
    require(state_api["active"]["state_id"] == failed_state["state_id"], "The active project checkpoint is incorrect.")
    require(len(state_api["active"]["completed"]) == 2, "Completed checkpoint count is incorrect.")
    require(len(state_api["active"]["remaining"]) == 2, "Remaining checkpoint count is incorrect.")

    shown = command(opener, csrf, "show active browser mission")
    require(shown["plan"]["task_type"] == "application_state", "Application state command was misrouted.")
    require(shown["plan"]["state"] == "completed", "Application state inspection did not complete.")
    require(shown["result"]["application_state"]["active"]["state_id"] == failed_state["state_id"], "State inspection returned a different checkpoint.")

    continuation = command(opener, csrf, "continue browser mission")
    require(continuation["plan"]["state"] == "awaiting_approval", "Continuation did not pause for approval.")
    reference = continuation["result"]["application_state_reference"]
    require(reference["state_id"] == failed_state["state_id"], "Approval did not bind the exact checkpoint.")
    require("must not continue" not in continuation["approval"]["data_summary"], "Continuation approval exposed a field value.")
    continued = approve_once(opener, csrf, continuation)
    continued_task = continued["task"]
    continued_result = continued_task["result"]
    require(continued_task["state"] == "failed", "The known missing field unexpectedly completed on retry.")
    require(continued_result["continued_from"]["state_id"] == failed_state["state_id"], "Continuation lost its source-state binding.")
    require(continued_result["browser_action"]["failed_step"] == 3, "Continuation did not stop at the same verified checkpoint.")
    require(len(continued_result["browser_action"]["steps"]) == 2, "Continuation ran the final control after failure.")
    require_fabric(continued_result, "browser_workflow")
    continued_state = continued_result["application_state"]
    require(continued_state["status"] == "resumable", "Retried failure did not produce a new resumable state.")

    private_state = request_json(opener, "/api/application-state?project_id=auris-one&private=true")["application_state"]
    require(private_state["private_mode"] is True and private_state["states"] == [], "Private Session exposed durable application state.")

    secret = command(opener, csrf, 'fill "Acceptance note" with "password secret token" in the browser')
    require(secret["plan"]["state"] == "blocked", "Protected browser data was not blocked.")
    purchase = command(opener, csrf, 'click "Purchase now" button in the browser')
    require(purchase["plan"]["state"] == "blocked", "Consequential browser control was not blocked.")
    private_network = command(opener, csrf, f"open {BASE_URL}/")
    require(private_network["plan"]["state"] == "failed", "A non-fixture private-network page was not blocked.")
    private = command(opener, csrf, "inspect the current browser page", private=True)
    require(private["plan"]["state"] == "failed", "Private Session incorrectly used the persistent browser profile.")

    status = request_json(opener, "/api/browser/status")["browser"]
    require(status.get("runtime_available") is True and status.get("connected") is True, "Browser worker status is not live.")
    for state in (completed_state, failed_state, continued_state):
        delete_application_state(state["state_id"])
    print(json.dumps({
        "ok": True,
        "version": health["version"],
        "provider": status.get("provider"),
        "navigation_http_status": nav_result["browser_action"].get("http_status"),
        "accessibility_controls": sorted(control_names),
        "fill_verified_length": fill_result["browser_action"].get("observed_length"),
        "click_state_changed": click_result["browser_action"].get("state_changed"),
        "mission_completed_steps": mission_action["completed_steps"],
        "mission_values_redacted": True,
        "mission_fail_closed_step": failed_action["failed_step"],
        "application_state_inspected": True,
        "continuation_approval_bound": True,
        "continuation_fail_closed_step": continued_result["browser_action"]["failed_step"],
        "private_state_suppressed": True,
        "signed_scopes": ["browser_navigate", "browser_inspect", "browser_fill", "browser_click", "browser_workflow"],
        "protected_data_blocked": True,
        "consequential_control_blocked": True,
        "private_network_blocked": True,
        "private_profile_refused": True,
        "ui_contracts": sorted(required_ids),
    }, indent=2))


if __name__ == "__main__":
    main()
