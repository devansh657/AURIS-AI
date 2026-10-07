from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auris.local_client import AurisLocalClient


EXPECTED_VERSION = "0.8.34"
THREE_SHA256 = "86BCEE248B64F44BCFC23C331AE74619061957D59CAB040171DCB6FB5900BEB6"
THREE_CORE_SHA256 = "05B2609338C76CD65DAF74F3AC515BC9A5045E1B3B33EDC07D8C9BD55250FA90"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    with urlopen("http://127.0.0.1:8765/api/health", timeout=8) as response:
        health = json.loads(response.read().decode("utf-8"))
    require(
        health.get("version") == EXPECTED_VERSION,
        f"The live AURIS release is not {EXPECTED_VERSION}.",
    )

    token = (ROOT / "data" / "portal.token").read_text(encoding="ascii").strip()
    require(bool(token), "The protected portal token is unavailable.")
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    opener.open(f"http://127.0.0.1:8765/?access_token={quote(token)}", timeout=8).read()
    with opener.open("http://127.0.0.1:8765/api/session", timeout=8) as response:
        session = json.loads(response.read().decode("utf-8"))["session"]
    authenticated_headers = {
        "Content-Type": "application/json",
        "X-AURIS-CSRF": session["csrf_token"],
    }

    assets = {}
    for path in (
        "/", "/styles.css", "/app.js", "/neural-core.js",
        "/vendor/three.module.min.js", "/vendor/three.core.min.js",
    ):
        with opener.open(f"http://127.0.0.1:8765{path}", timeout=8) as response:
            assets[path] = {
                "content_type": response.headers.get_content_type(),
                "body": response.read(),
            }
    require(assets["/app.js"]["content_type"] in {"text/javascript", "application/javascript"}, "App module MIME type is invalid.")
    require(assets["/neural-core.js"]["content_type"] in {"text/javascript", "application/javascript"}, "Neural module MIME type is invalid.")
    require(hashlib.sha256(assets["/vendor/three.module.min.js"]["body"]).hexdigest().upper() == THREE_SHA256, "Vendored Three.js hash changed.")
    require(hashlib.sha256(assets["/vendor/three.core.min.js"]["body"]).hexdigest().upper() == THREE_CORE_SHA256, "Vendored Three.js core hash changed.")

    html = assets["/"]["body"].decode("utf-8")
    styles = assets["/styles.css"]["body"].decode("utf-8")
    app = assets["/app.js"]["body"].decode("utf-8")
    neural = assets["/neural-core.js"]["body"].decode("utf-8")
    ids = re.findall(r'id="([^"]+)"', html)
    require(len(ids) == len(set(ids)), "The live portal contains duplicate element IDs.")
    for required_id in (
        "aurisCore", "commandCpuUsage", "commandRamUsage", "commandGpuUsage",
        "commandAgentList", "commandTimeline", "commandPalette", "toggleFocusMode",
        "attentionMetrics", "operationsGraph", "eveningDebrief", "responseRouteReadout",
    ):
        require(required_id in ids, f"The live cinematic UI is missing #{required_id}.")
    require("createAurisNeuralCore" in app and "THREE.WebGLRenderer" in neural, "The live app is not using the Three.js neural engine.")
    require('import("/neural-core.js?v=' in app, "The neural renderer is not loaded through the resilient asynchronous path.")
    require(not app.lstrip().startswith("import "), "A static neural import can still prevent backend controls from starting.")
    require("Promise.allSettled" in app and "/api/client/ready" in app, "Resilient backend startup contracts are absent.")
    require("gl.readPixels" in neural and "pixelCheckComplete" in neural, "WebGL nonblank pixel diagnostics are absent.")
    require("@media (max-width: 700px)" in styles and "prefers-reduced-motion" in styles, "Responsive or reduced-motion contracts are absent.")
    require("boot-failsafe" in styles and "8s forwards" in styles, "The boot layer does not fail open.")
    require("REAL DATA" in html and "DECORATIVE" in html and "DERIVED" in html, "Data provenance labels are incomplete.")

    ready_request = Request(
        "http://127.0.0.1:8765/api/client/ready",
        data=json.dumps(
            {"ui_version": "0.8.34.0", "renderer": "acceptance-http-client"}
        ).encode("utf-8"),
        headers=authenticated_headers,
        method="POST",
    )
    with opener.open(ready_request, timeout=8) as response:
        ready = json.loads(response.read().decode("utf-8"))
    require(
        ready == {"ok": True, "backend": "online", "version": EXPECTED_VERSION},
        "The authenticated browser readiness handshake failed.",
    )

    status = AurisLocalClient().status()
    stopped = bool((status.get("control") or {}).get("stopped"))
    command_provider = "blocked_by_emergency_stop"
    command_reply = "Safety latch preserved; no acceptance command was issued."
    if not stopped:
        command_request = Request(
            "http://127.0.0.1:8765/api/command",
            data=json.dumps(
                {
                    "command": "AURIS, are you ready",
                    "project_id": None,
                    "mode": "private",
                    "private": True,
                    "conversation_id": "auris-ui-acceptance",
                }
            ).encode("utf-8"),
            headers=authenticated_headers,
            method="POST",
        )
        with opener.open(command_request, timeout=8) as response:
            command = json.loads(response.read().decode("utf-8"))
        intelligence = (command.get("result") or {}).get("intelligence") or {}
        require(command.get("ok") is True, "The browser command route rejected a harmless directive.")
        require(
            intelligence.get("provider") == "auris_instant_kernel",
            "The browser command route did not reach the AURIS intelligence core.",
        )
        command_provider = intelligence["provider"]
        command_reply = (command.get("result") or {}).get("message")
    device = status.get("device") or {}
    require((status.get("local_ipc") or {}).get("connected") is True, "Authenticated named-pipe IPC is offline.")
    require((device.get("memory") or {}).get("total_gb", 0) > 0, "Live memory telemetry is unavailable.")
    require((device.get("gpu") or {}).get("name"), "Live GPU telemetry is unavailable.")
    require((status.get("voice") or {}).get("neural_worker_online") is True, "The AURIS neural voice worker is offline.")
    require((status.get("model") or {}).get("fast", {}).get("warm") is True, "The fast neural route is not warm.")

    print(
        json.dumps(
            {
                "ok": True,
                "version": health["version"],
                "authenticated_assets": {path: len(item["body"]) for path, item in assets.items()},
                "three_sha256": THREE_SHA256,
                "unique_dom_ids": len(ids),
                "responsive_contracts": ["desktop", "tablet", "mobile", "reduced_motion"],
                "webgl_pixel_diagnostic": "wired",
                "browser_backend_path": {
                    "authenticated_session": True,
                    "csrf_protected_ready": ready["backend"],
                    "control_stopped": stopped,
                    "command_provider": command_provider,
                    "reply": command_reply,
                },
                "telemetry": {
                    "cpu": (device.get("cpu") or {}).get("model"),
                    "memory_total_gb": (device.get("memory") or {}).get("total_gb"),
                    "gpu": (device.get("gpu") or {}).get("name"),
                },
                "visual_screenshot": "blocked_by_in_app_browser_loopback_policy",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
