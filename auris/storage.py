from __future__ import annotations

import json
from pathlib import Path
from typing import Any


TASKS_PATH = Path("data/tasks/tasks.jsonl")


def append_jsonl(path: Path, record: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    return path


def read_jsonl(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    if not path.exists() or limit <= 0:
        return []

    newest_first: list[dict[str, Any]] = []
    buffer = b""
    with path.open("rb") as handle:
        handle.seek(0, 2)
        position = handle.tell()
        while position > 0 and len(newest_first) < limit:
            block_size = min(64 * 1024, position)
            position -= block_size
            handle.seek(position)
            buffer = handle.read(block_size) + buffer
            lines = buffer.split(b"\n")
            buffer = lines[0]
            for raw_line in reversed(lines[1:]):
                parsed = _decode_jsonl_line(raw_line)
                if parsed is not None:
                    newest_first.append(parsed)
                    if len(newest_first) >= limit:
                        break
        if position == 0 and len(newest_first) < limit:
            parsed = _decode_jsonl_line(buffer)
            if parsed is not None:
                newest_first.append(parsed)
    return list(reversed(newest_first[:limit]))


def _decode_jsonl_line(raw_line: bytes) -> dict[str, Any] | None:
    if not raw_line.strip():
        return None
    try:
        parsed = json.loads(raw_line)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def save_task(task: dict[str, Any]) -> Path:
    return append_jsonl(TASKS_PATH, task)


def recent_tasks(limit: int = 20) -> list[dict[str, Any]]:
    return read_jsonl(TASKS_PATH, limit=limit)
