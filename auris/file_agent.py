from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from auris.communications_agent import onedrive_roots


ROOT = Path(__file__).resolve().parents[1]
USER_HOME = Path.home()
DEFAULT_SEARCH_ROOTS = (
    USER_HOME / "Desktop",
    USER_HOME / "Documents",
    USER_HOME / "Downloads",
    ROOT,
    *onedrive_roots(),
)
SKIPPED_DIRECTORIES = {
    ".git",
    ".idea",
    ".venv",
    ".vscode",
    "__pycache__",
    "appdata",
    "node_modules",
    "venv",
}
FIND_PATTERNS = (
    r"^(?:find|locate)\s+(?:a\s+)?files?\s+(?:named\s+|called\s+)?(.+)$",
    r"^search\s+(?:my\s+)?files\s+for\s+(.+)$",
    r"^find\s+(.+?)\s+(?:in\s+my\s+files|on\s+my\s+laptop)$",
    r"^find\s+(.+?)\s+in\s+(?:my\s+)?onedrive$",
    r"^search\s+(?:my\s+)?onedrive\s+for\s+(.+)$",
)
CONTENT_PATTERNS = (
    r"^search\s+(?:my\s+)?file\s+contents\s+for\s+(.+)$",
    r"^find\s+(?:the\s+)?(?:text|phrase)\s+(.+?)\s+in\s+(?:my\s+)?files$",
    r"^search\s+(?:my\s+)?(?:documents|files)\s+for\s+(?:the\s+)?(?:text|phrase)\s+(.+)$",
)
CONTENT_EXTENSIONS = {
    ".css", ".csv", ".html", ".ini", ".js", ".json", ".jsx", ".log",
    ".md", ".py", ".toml", ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml",
}
MAX_CONTENT_FILE_BYTES = 1024 * 1024
MAX_CONTENT_SCAN_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class FileSearch:
    query: str
    roots: tuple[Path, ...]
    mode: str = "filename"


def match_file_search(command: str, roots: Iterable[Path] | None = None) -> FileSearch | None:
    text = _normalise(command)
    for mode, patterns in (("content", CONTENT_PATTERNS), ("filename", FIND_PATTERNS)):
        for pattern in patterns:
            match = re.fullmatch(pattern, text)
            if not match:
                continue
            query = match.group(1).strip(" .\"")[:200]
            if len(query) < 2 or any(character in query for character in "\\/:"):
                return None
            requested_roots = roots or (
                onedrive_roots() if "onedrive" in text else DEFAULT_SEARCH_ROOTS
            )
            selected = tuple(path.resolve() for path in requested_roots if path.exists())
            return FileSearch(query, selected, mode=mode)
    return None


def execute_file_search(search: FileSearch, *, limit: int = 30, timeout_seconds: float = 5) -> dict[str, Any]:
    started = time.monotonic()
    matches: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    inspected = 0
    inspected_bytes = 0
    limited = False
    content_budget_exhausted = False
    query = search.query.casefold()
    deadline = started + max(0.1, timeout_seconds)

    for root_index, root in enumerate(search.roots):
        now = time.monotonic()
        if now >= deadline:
            limited = True
            break
        if not _approved_root(root):
            continue
        remaining_roots = max(1, len(search.roots) - root_index)
        root_deadline = now + ((deadline - now) / remaining_roots)
        resolved_root = root.resolve()
        for directory, names, files in os.walk(root, topdown=True, onerror=lambda _: None):
            names[:] = [name for name in names if name.casefold() not in SKIPPED_DIRECTORIES and not name.startswith(".")]
            for name in files:
                if time.monotonic() >= root_deadline:
                    limited = True
                    break
                inspected += 1
                path = Path(directory) / name
                try:
                    if path.is_symlink():
                        continue
                    resolved_path = path.resolve(strict=True)
                    if not resolved_path.is_relative_to(resolved_root) or resolved_path in seen_paths:
                        continue
                    stat = resolved_path.stat()
                except OSError:
                    continue
                item: dict[str, Any] | None = None
                if search.mode == "filename" and query in name.casefold():
                    item = _file_result(resolved_path, stat)
                elif search.mode == "content":
                    if resolved_path.suffix.casefold() not in CONTENT_EXTENSIONS:
                        continue
                    if stat.st_size > MAX_CONTENT_FILE_BYTES:
                        continue
                    if inspected_bytes + stat.st_size > MAX_CONTENT_SCAN_BYTES:
                        limited = True
                        content_budget_exhausted = True
                        break
                    inspected_bytes += stat.st_size
                    content_match = _match_file_content(resolved_path, query)
                    if content_match is not None:
                        item = {
                            **_file_result(resolved_path, stat),
                            **content_match,
                        }
                if item is not None:
                    seen_paths.add(resolved_path)
                    matches.append(item)
                    if len(matches) >= limit:
                        break
            if len(matches) >= limit or content_budget_exhausted or time.monotonic() >= root_deadline:
                limited = True
                break
        if len(matches) >= limit or content_budget_exhausted:
            break

    return {
        "ok": True,
        "message": (
            f"I found {len(matches)} file match{'es' if len(matches) != 1 else ''} for {search.query}."
        ),
        "verification": (
            f"Confirmed: AURIS inspected {inspected} files across {len(search.roots)} approved "
            + (
                f"root(s), read at most {inspected_bytes} bytes of allowlisted local text, and persisted no matched content."
                if search.mode == "content"
                else "root(s) without opening or changing file contents."
            )
        ),
        "query": search.query,
        "mode": search.mode,
        "items": matches,
        "inspected_files": inspected,
        "inspected_bytes": inspected_bytes,
        "limited": limited or len(matches) >= limit,
        "duration_ms": round((time.monotonic() - started) * 1000),
    }


def _file_result(path: Path, stat: os.stat_result) -> dict[str, Any]:
    return {
        "name": path.name,
        "path": str(path),
        "size_bytes": stat.st_size,
        "modified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)),
    }


def _match_file_content(path: Path, query: str) -> dict[str, int] | None:
    matches = 0
    first_line = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            for line_number, line in enumerate(stream, start=1):
                count = line.casefold().count(query)
                if not count:
                    continue
                matches += count
                if first_line == 0:
                    first_line = line_number
    except OSError:
        return None
    if matches == 0:
        return None
    return {"match_count": matches, "first_matching_line": first_line}


def _approved_root(path: Path) -> bool:
    resolved = path.resolve()
    return resolved == ROOT.resolve() or resolved.is_relative_to(USER_HOME.resolve())


def _normalise(command: str) -> str:
    text = " ".join(command.casefold().strip().replace(",", " ").split())
    for prefix in ("hey auris ", "auris "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.strip(" .")
