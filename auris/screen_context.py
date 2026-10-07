from __future__ import annotations

import json
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from auris.model_gateway import analyse_image


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_SCRIPT = ROOT / "scripts" / "capture_screen.ps1"
CAPTURE_ROOT = ROOT / "data" / "captures"

SCREEN_PATTERNS = (
    r"\b(?:what(?:'s| is)|tell me what(?:'s| is)) on (?:my|the) screen\b",
    r"\b(?:describe|read|inspect|analyse|analyze|look at) (?:my|the) screen\b",
    r"\bwhat can you see (?:on (?:my|the) screen)?\b",
)


def is_screen_command(command: str) -> bool:
    text = _normalise(command)
    return any(re.search(pattern, text) for pattern in SCREEN_PATTERNS)


def analyse_current_screen(prompt: str) -> dict[str, Any]:
    capture = capture_screen()
    if not capture.get("ok"):
        return capture

    path = Path(str(capture["path"]))
    try:
        reply = analyse_image(
            path,
            prompt=(
                "Describe the visible Windows desktop and answer the user's request. "
                "Be concise, distinguish visible evidence from inference, and never claim to have "
                "clicked or changed anything. User request: " + prompt[:2000]
            ),
        )
        return {
            "ok": True,
            "message": reply.text,
            "verification": (
                f"Confirmed: AURIS captured the visible {capture['width']}x{capture['height']} "
                f"desktop across {capture['monitors']} monitor(s), analysed it locally with "
                f"{reply.model}, and deleted the temporary image."
            ),
            "capture": {
                "width": capture["width"],
                "height": capture["height"],
                "monitors": capture["monitors"],
                "temporary": True,
                "deleted_after_analysis": True,
            },
            "intelligence": reply.to_dict(),
        }
    except RuntimeError as error:
        return {
            "ok": False,
            "error": str(error),
            "verification": "The screen image was captured temporarily, but visual analysis did not complete.",
        }
    finally:
        path.unlink(missing_ok=True)


def capture_screen() -> dict[str, Any]:
    CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
    output_path = (CAPTURE_ROOT / f"screen-{uuid.uuid4().hex}.png").resolve()
    if not output_path.is_relative_to(CAPTURE_ROOT.resolve()):
        return {"ok": False, "error": "The temporary capture path was rejected."}

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(CAPTURE_SCRIPT),
                "-OutputPath",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        output_path.unlink(missing_ok=True)
        return {"ok": False, "error": f"Windows screen capture failed: {error}"}
    if result.returncode != 0:
        output_path.unlink(missing_ok=True)
        detail = (result.stderr or result.stdout or "Windows screen capture failed.").strip()
        return {"ok": False, "error": detail[:500]}
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        output_path.unlink(missing_ok=True)
        return {"ok": False, "error": "Windows returned an invalid screen-capture result."}
    if not payload.get("ok") or not output_path.exists():
        output_path.unlink(missing_ok=True)
        return {"ok": False, "error": "Windows did not produce the temporary screen image."}
    return {
        "ok": True,
        "path": str(output_path),
        "width": int(payload.get("width", 0)),
        "height": int(payload.get("height", 0)),
        "monitors": int(payload.get("monitors", 1)),
    }


def _normalise(command: str) -> str:
    text = " ".join(command.casefold().strip().replace(",", " ").split())
    for prefix in ("hey auris ", "auris "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.strip(" .")
