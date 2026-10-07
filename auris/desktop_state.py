from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COMPANION_STATUS_PATH = ROOT / "data" / "desktop-companion-status.json"


def write_companion_status(
    state: str,
    *,
    path: Path = COMPANION_STATUS_PATH,
    **details: Any,
) -> None:
    payload = {
        "pid": os.getpid(),
        "state": state,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **details,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=True), encoding="ascii")
    temporary.replace(path)


def companion_status(
    *,
    path: Path = COMPANION_STATUS_PATH,
    maximum_age_seconds: int = 30,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="ascii"))
        updated = datetime.fromisoformat(payload["updated_at"])
        age = (datetime.now(timezone.utc) - updated).total_seconds()
        return {**payload, "online": age < maximum_age_seconds}
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return {"online": False, "state": "offline"}
