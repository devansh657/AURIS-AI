from __future__ import annotations

import ast
import argparse
import hashlib
import http.cookiejar
import json
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8765"
EXPECTED_VERSION = "0.8.34"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--new-project", action="store_true")
    options = parser.parse_args()
    with urlopen(f"{BASE_URL}/api/health", timeout=8) as response:
        health = json.loads(response.read())
    require(health.get("version") == EXPECTED_VERSION, "The new coding runtime is not active.")
    token = (ROOT / "data" / "portal.token").read_text(encoding="ascii").strip()
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    opener.open(f"{BASE_URL}/?access_token={quote(token)}", timeout=8).read()
    csrf = ""

    def request(path: str, body: dict | None = None) -> dict:
        headers = {"Content-Type": "application/json", "X-AURIS-CSRF": csrf} if body is not None else {}
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        with opener.open(Request(BASE_URL + path, data=payload, headers=headers), timeout=90) as response:
            return json.loads(response.read())

    csrf = request("/api/session")["session"]["csrf_token"]

    def command(text: str, project_id: str) -> dict:
        return request("/api/command", {"command": text, "project_id": project_id, "mode": "coding", "private": False, "conversation_id": "codex-live-acceptance"})

    objective = "add format_greeting(name: str) returning Hello, followed by the name and an exclamation mark. Include unit tests for Ada and an empty name, and document how to run them. Keep this project dependency-free."
    project = source = before = None
    started = time.monotonic()
    if options.new_project:
        queued = command(f"Build a Python project called AURIS Logic Acceptance {time.strftime('%Y%m%d%H%M%S')} to {objective}", "auris-one")
    else:
        created = command(f"scaffold a Python project called Codex Bridge Acceptance {time.strftime('%Y%m%d%H%M%S')}", "auris-one")
        require(created["plan"]["state"] == "completed", "The disposable starter project was not created.")
        project = created["result"]["generated_project"]
        source = Path(project["root_path"])

    def hashes() -> dict:
        return {path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in source.rglob("*") if path.is_file()}

    if not options.new_project:
        before = hashes()
        queued = command("Use Codex to " + objective, project["project_id"])
    require(queued["result"].get("background"), f"The real Codex mission did not start asynchronously: {queued}")
    task_id = queued["plan"]["task_id"]
    print(json.dumps({"phase": "running", "task_id": task_id, "new_project_from_logic": options.new_project}), flush=True)
    task = None
    while time.monotonic() - started < 1250:
        tasks = request("/api/tasks?limit=100")["tasks"]
        task = next((item for item in tasks if item["task_id"] == task_id), None)
        if task and task["state"] not in {"created", "planning", "running", "verifying", "recovering"}:
            break
        time.sleep(2)
    require(task is not None and task["state"] == "awaiting_approval", f"The mission did not reach diff review: {(task or {}).get('result')}")
    if options.new_project:
        project = task["result"]["generated_project"]
        source = Path(project["root_path"])
        manifest_path = source / "AURIS-MANIFEST.json"
        scaffold = json.loads(manifest_path.read_text(encoding="utf-8"))
        before = {item["path"]: item["sha256"] for item in scaffold["files"]}
        before["AURIS-MANIFEST.json"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    require(hashes() == before, "Source changed before approval.")
    proposal = task["result"]["coding_action"]["proposal"]
    require(proposal["validation"]["passed"], "Independent static validation failed.")
    approvals = request("/api/approvals?status=pending")["approvals"]
    approval = next((item for item in approvals if item["task_id"] == task_id), None)
    require(approval is not None, "No exact-diff approval was created.")
    applied = request(f"/api/approvals/{approval['approval_id']}/approve", {"scope": "once"})
    require((applied.get("task") or {}).get("state") == "completed", f"The exact diff was not applied: {applied}")
    after = hashes()
    for item in proposal["files"]:
        require(after.get(item["path"]) == item["new_sha256"], "Applied content differs from the reviewed signed content.")
    functions = [node.name for path in source.rglob("*.py") for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if isinstance(node, ast.FunctionDef)]
    require("format_greeting" in functions, "The requested function is absent from the applied code.")
    require(any(name.startswith("test_") for name in functions), "The requested tests are absent.")
    print(json.dumps({"ok": True, "version": health["version"], "task_id": task_id, "project": str(source), "new_project_from_logic": options.new_project, "files_changed": len(proposal["files"]), "static_checks": proposal["validation"]["passed_checks"], "source_unchanged_before_approval": True, "exact_applied_hashes_verified": True, "dynamic_tests_independently_verified": False, "duration_seconds": round(time.monotonic() - started, 1)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
