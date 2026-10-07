from __future__ import annotations

import http.cookiejar
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8765"
EXPECTED_VERSION = "0.8.34"


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


def command(opener, csrf: str, text: str) -> dict:
    return request_json(
        opener,
        "/api/command",
        method="POST",
        csrf=csrf,
        body={
            "command": text,
            "project_id": "auris-one",
            "mode": "command",
            "private": False,
            "conversation_id": "composite-device-live-acceptance",
        },
    )


def require_fabric(result: dict, scope: str) -> None:
    fabric = result["device_action"]["command_fabric"]
    require(fabric.get("permission_scope") == scope, f"Expected signed scope {scope}.")
    require(fabric.get("signature_verified") is True, "Device command signature was not verified.")
    require(fabric.get("nonce_claimed") is True, "Device command nonce was not claimed.")


def main() -> None:
    with urlopen(f"{BASE_URL}/api/health", timeout=8) as response:
        health = json.loads(response.read().decode("utf-8"))
    require(health.get("version") == EXPECTED_VERSION, f"Expected AURIS {EXPECTED_VERSION}.")

    token = (ROOT / "data" / "portal.token").read_text(encoding="ascii").strip()
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with opener.open(f"{BASE_URL}/?access_token={quote(token)}", timeout=8) as response:
        response.read()
    csrf = request_json(opener, "/api/session")["session"]["csrf_token"]

    youtube = command(opener, csrf, "AURIS, open YouTube on Brave")
    require(youtube["plan"]["task_type"] == "computer_operation", "YouTube in Brave was misrouted.")
    require(youtube["plan"]["state"] == "completed", "YouTube did not open in Brave.")
    youtube_action = youtube["result"]["device_action"]
    require(youtube_action["action"]["arguments"] == ["https://www.youtube.com/"], "The fixed YouTube destination was not bound.")
    require(youtube_action["action"]["executable"].casefold().endswith("brave.exe"), "The selected browser was not Brave.")
    require(youtube_action.get("verified_process_ids"), "A running Brave process was not observed.")
    require_fabric(youtube["result"], "launch_app")

    public_site = command(opener, csrf, "AURIS, open example.com in Brave")
    require(public_site["plan"]["state"] == "completed", "A general public domain did not open in Brave.")
    public_action = public_site["result"]["device_action"]
    require(public_action["action"]["arguments"] == ["https://example.com"], "The public domain was not normalized to HTTPS.")
    require("url_sha256=" in public_action["action"]["target"], "The destination URL was not digest-bound.")
    require_fabric(public_site["result"], "launch_app")

    web_search = command(opener, csrf, "AURIS, search YouTube for AURIS demos in Brave")
    require(web_search["plan"]["state"] == "completed", "A named-browser YouTube search did not complete.")
    search_url = web_search["result"]["device_action"]["action"]["arguments"][0]
    require("youtube.com/results?search_query=AURIS+demos" in search_url, "The exact YouTube search query was not preserved.")
    require_fabric(web_search["result"], "launch_app")

    spotify_first = command(opener, csrf, "AURIS, play songs on Spotify")
    require(spotify_first["plan"]["task_type"] == "computer_operation", "Spotify playback was misrouted.")
    require(spotify_first["plan"]["state"] == "completed", "Spotify did not receive the first play command.")
    first_action = spotify_first["result"]["device_action"]
    require(first_action.get("application_focused") is True, "Spotify was not confirmed in the foreground.")
    require(first_action.get("media_key_emitted") is True, "Spotify did not receive the media key.")
    require_fabric(spotify_first["result"], "app_media")

    spotify_restore = command(opener, csrf, "AURIS, play songs on Spotify")
    require(spotify_restore["plan"]["state"] == "completed", "Spotify playback state could not be restored.")
    require(spotify_restore["result"]["device_action"].get("media_key_emitted") is True, "The restoring media key was not emitted.")
    require_fabric(spotify_restore["result"], "app_media")

    print(json.dumps({
        "ok": True,
        "version": health["version"],
        "youtube_browser": "Brave",
        "youtube_url": "https://www.youtube.com/",
        "youtube_process_observed": True,
        "general_public_domain_opened": True,
        "named_browser_search_preserved": True,
        "url_digest_bound": True,
        "spotify_focused_before_media_key": True,
        "spotify_media_key_emitted": True,
        "spotify_toggle_restored": True,
        "signed_scopes": ["launch_app", "app_media"],
        "playback_session_observed": False,
    }, indent=2))


if __name__ == "__main__":
    main()
