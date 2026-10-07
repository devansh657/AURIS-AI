from __future__ import annotations

import http.cookiejar
import json
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8765"
EXPECTED_VERSION = "0.8.34"
WORK_ROOT = (Path.home() / "Documents" / "AURIS Work").resolve()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def request_json(opener, path: str, *, method: str = "GET", body: dict | None = None, csrf: str = "") -> dict:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if payload else {}
    if method not in {"GET", "HEAD"}:
        headers["X-AURIS-CSRF"] = csrf
    request = Request(f"{BASE_URL}{path}", data=payload, headers=headers, method=method)
    with opener.open(request, timeout=240) as response:
        return json.loads(response.read().decode("utf-8"))


def command(opener, csrf: str, text: str) -> dict:
    return request_json(
        opener,
        "/api/command",
        method="POST",
        csrf=csrf,
        body={
            "command": text,
            "project_id": "auris-one",
            "mode": "coding",
            "private": False,
            "conversation_id": "work-product-live-acceptance",
        },
    )


def verified_artifact(response: dict, kind: str) -> dict:
    require(response["plan"]["task_type"] == "work_product", f"{kind} request was misrouted.")
    require(response["plan"]["state"] == "completed", f"{kind} request did not complete.")
    action = response["result"]["artifact_action"]
    require(action.get("ok") is True, f"{kind} action was not successful.")
    artifact = action["artifact"]
    path = Path(artifact["path"]).resolve(strict=True)
    require(path == WORK_ROOT or WORK_ROOT in path.parents, f"{kind} escaped the managed work root.")
    require(artifact.get("sha256") or artifact.get("manifest_sha256"), f"{kind} has no recorded hash.")
    require(all(check.get("passed") for check in artifact.get("checks", [])), f"{kind} static checks failed.")
    return artifact


def main() -> None:
    with urlopen(f"{BASE_URL}/api/health", timeout=8) as response:
        health = json.loads(response.read().decode("utf-8"))
    require(health.get("version") == EXPECTED_VERSION, f"Expected AURIS {EXPECTED_VERSION}.")

    token = (ROOT / "data" / "portal.token").read_text(encoding="ascii").strip()
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    opener.open(f"{BASE_URL}/?access_token={quote(token)}", timeout=8).read()
    csrf = request_json(opener, "/api/session")["session"]["csrf_token"]

    started = time.monotonic()
    project_response = command(
        opener,
        csrf,
        "AURIS, scaffold a Python project called AURIS Acceptance Demo",
    )
    project_duration_ms = round((time.monotonic() - started) * 1000)
    project = verified_artifact(project_response, "code_project")
    require(project.get("generated_code_executed") is False, "Generated code was represented as executed.")
    require(Path(project["manifest_path"]).is_file(), "The project manifest is missing.")

    started = time.monotonic()
    document_response = command(
        opener,
        csrf,
        "AURIS, create a Word document titled AURIS Capability Report about verified PC automation and work products",
    )
    document_duration_ms = round((time.monotonic() - started) * 1000)
    document = verified_artifact(document_response, "document")
    require(document.get("format") == "docx", "The requested Word output is not DOCX.")
    require(document.get("paragraphs", 0) >= 2, "The Word document did not reopen with content.")

    print(
        json.dumps(
            {
                "ok": True,
                "version": health["version"],
                "managed_root": str(WORK_ROOT),
                "project": {
                    "path": project["path"],
                    "files": len(project.get("files", [])),
                    "manifest_sha256": project["manifest_sha256"],
                    "generated_code_executed": project["generated_code_executed"],
                    "duration_ms": project_duration_ms,
                },
                "document": {
                    "path": document["path"],
                    "paragraphs": document["paragraphs"],
                    "sha256": document["sha256"],
                    "duration_ms": document_duration_ms,
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
