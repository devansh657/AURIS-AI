from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAX_PROJECT_FILES = 20_000
MAX_TEXT_FILE_BYTES = 2 * 1024 * 1024
SKIPPED_DIRECTORIES = {
    ".android-sdk",
    ".cloud-venv",
    ".dotnet",
    ".git",
    ".gradle",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".voice-gpu-venv",
    ".voice-venv",
    ".vscode",
    "__pycache__",
    "bin",
    "build",
    "data",
    "dist",
    "node_modules",
    "obj",
    "venv",
}
TEXT_EXTENSIONS = {
    ".cs",
    ".css",
    ".gradle",
    ".html",
    ".java",
    ".js",
    ".json",
    ".kt",
    ".kts",
    ".md",
    ".ps1",
    ".py",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
LANGUAGES = {
    ".cs": "C#",
    ".css": "CSS",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".ps1": "PowerShell",
    ".py": "Python",
    ".sql": "SQL",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
}
INSTRUCTION_NAMES = {"AGENTS.md", "CONTRIBUTING.md", "SECURITY.md", "TESTING.md"}
MANIFEST_NAMES = {
    "build.gradle",
    "build.gradle.kts",
    "Cargo.toml",
    "composer.json",
    "go.mod",
    "package.json",
    "pom.xml",
    "pyproject.toml",
    "requirements.txt",
}
SENSITIVE_FILE_NAMES = {
    ".env",
    "credentials.json",
    "secrets.json",
    "service-account.json",
}
MANAGED_PROJECT_ROOT = Path.home() / "Documents" / "AURIS Work" / "Projects"


def match_coding_command(command: str) -> str | None:
    text = _normalise(command)
    if re.search(r"\b(?:use|ask|delegate\s+to)\s+codex\b", text):
        return "codex_workspace"
    if re.fullmatch(
        r"(?:please\s+)?(?:fix|repair)\s+(?:(?:this|the)\s+)?failing\s+tests?",
        text.strip(" ."),
    ):
        return "repair_test"
    if re.search(r"\b(?:run|execute)\s+(?:the\s+)?(?:auris\s+)?tests?\b", text) or "test suite" in text:
        return "run_tests"
    if re.search(
        r"\b(?:inspect|analyze|analyse|review|map|check|summarize|summarise)\b.*"
        r"\b(?:this\s+)?(?:project|repository|repo|codebase|code)\b",
        text,
    ):
        return "analyze_project"
    if re.search(
        r"\b(?:implement|develop|refactor|debug|add|change|update|improve|complete|fix)\b.*"
        r"\b(?:in|inside|within|for)\s+(?:(?:this|my|selected|current|the(?:\s+selected)?)\s+)?"
        r"(?:project|repository|repo|codebase)\b",
        text,
    ):
        return "codex_workspace"
    return None


def execute_coding_command(
    operation: str,
    *,
    root: Path = ROOT,
    project_name: str = "AURIS One",
    trusted_execution: bool = False,
    command: str = "",
) -> dict[str, Any]:
    try:
        project_root = validate_project_root(root)
    except ValueError as error:
        return {"ok": False, "operation": operation, "error": str(error)}
    if operation == "run_tests":
        if not trusted_execution:
            return {
                "ok": False,
                "operation": operation,
                "error": "Running project code requires an explicitly trusted execution profile.",
                "verification": "Confirmed: no project command was executed.",
            }
        return _run_tests(project_root)
    if operation == "repair_test":
        from auris.repair_agent import prepare_test_repair

        return prepare_test_repair(
            command or "fix this failing test",
            root=project_root,
            project_name=project_name,
            trusted_execution=trusted_execution,
        )
    if operation == "codex_workspace":
        from auris.codex_workspace_agent import prepare_codex_workspace_change

        return prepare_codex_workspace_change(
            command,
            root=project_root,
            project_name=project_name,
            trusted_execution=trusted_execution,
        )
    if operation in {"inspect_repository", "analyze_project"}:
        return _analyze_project(project_root, project_name=project_name)
    return {"ok": False, "error": "That coding operation is not enabled."}


def is_trusted_coding_root(root: str | Path) -> bool:
    try:
        resolved = validate_project_root(root)
    except ValueError:
        return False
    if resolved == ROOT.resolve():
        return True
    try:
        managed = MANAGED_PROJECT_ROOT.resolve(strict=True)
        resolved.relative_to(managed)
    except (OSError, ValueError):
        return False
    return True


def validate_project_root(root: str | Path) -> Path:
    text = str(root).strip()
    if not text or len(text) > 500:
        raise ValueError("A bounded project directory is required.")
    candidate = Path(text).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise ValueError("The configured project directory does not exist.") from error
    if not resolved.is_dir():
        raise ValueError("The configured project root is not a directory.")
    if resolved == Path(resolved.anchor):
        raise ValueError("A drive root cannot be registered as an AURIS project.")
    home = Path.home().resolve()
    if resolved == home:
        raise ValueError("The entire user profile cannot be registered as one project.")
    blocked_parts = {".aws", ".gnupg", ".ssh", "appdata", "programdata", "windows"}
    if any(part.casefold() in blocked_parts for part in resolved.parts):
        raise ValueError("That directory is inside a protected credential or system boundary.")
    return resolved


def _run_tests(root: Path) -> dict[str, Any]:
    if root != ROOT.resolve():
        return {
            "ok": False,
            "operation": "run_tests",
            "error": "Only the locally trusted AURIS test profile is enabled.",
            "verification": "Confirmed: no untrusted project code was executed.",
        }
    started = time.monotonic()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "error": f"The AURIS test runner failed: {error}"}
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    match = re.search(r"Ran\s+(\d+)\s+tests?", output)
    test_count = int(match.group(1)) if match else None
    passed = result.returncode == 0
    return {
        "ok": passed,
        "message": (
            f"The AURIS test suite passed{f' all {test_count} tests' if test_count is not None else ''}."
            if passed
            else "The AURIS test suite reported failures."
        ),
        "verification": f"Confirmed: the fixed AURIS test process exited with code {result.returncode}.",
        "operation": "run_tests",
        "exit_code": result.returncode,
        "test_count": test_count,
        "output_tail": output[-8000:],
        "duration_ms": round((time.monotonic() - started) * 1000),
    }


def _analyze_project(root: Path, *, project_name: str) -> dict[str, Any]:
    started = time.monotonic()
    files, truncated, skipped_symlinks = _project_files(root)
    extensions: Counter[str] = Counter()
    languages: Counter[str] = Counter()
    component_files: Counter[str] = Counter()
    component_lines: Counter[str] = Counter()
    line_count = 0
    todo_count = 0
    oversized_text_files = 0
    sensitive_text_files = 0
    test_files: list[str] = []
    instructions: list[str] = []
    manifests: list[str] = []
    entry_points: list[str] = []
    largest: list[tuple[int, Path]] = []
    fingerprint = hashlib.sha256()

    for path in files:
        relative = path.relative_to(root)
        relative_text = relative.as_posix()
        try:
            stat = path.stat()
        except OSError:
            continue
        suffix = path.suffix.casefold() or "[no extension]"
        extensions[suffix] += 1
        if path.suffix.casefold() in LANGUAGES:
            languages[LANGUAGES[path.suffix.casefold()]] += 1
        component = relative.parts[0] if len(relative.parts) > 1 else "[root]"
        component_files[component] += 1
        largest.append((stat.st_size, path))
        fingerprint.update(f"{relative_text}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode("utf-8"))

        if path.name in INSTRUCTION_NAMES:
            instructions.append(relative_text)
        if path.name in MANIFEST_NAMES or path.suffix.casefold() in {".sln", ".slnx", ".csproj"}:
            manifests.append(relative_text)
        if _is_test_file(relative):
            test_files.append(relative_text)
        if _is_entry_point(relative):
            entry_points.append(relative_text)

        if path.suffix.casefold() not in TEXT_EXTENSIONS:
            continue
        if _is_sensitive_file_name(path.name):
            sensitive_text_files += 1
            continue
        if stat.st_size > MAX_TEXT_FILE_BYTES:
            oversized_text_files += 1
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        file_lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        line_count += file_lines
        component_lines[component] += file_lines
        todo_count += len(re.findall(r"\b(?:TODO|FIXME|HACK)\b", content, flags=re.IGNORECASE))

    version_control = _git_state(root)
    risks = _analysis_signals(
        truncated=truncated,
        skipped_symlinks=skipped_symlinks,
        oversized_text_files=oversized_text_files,
        sensitive_text_files=sensitive_text_files,
        instructions=instructions,
        test_files=test_files,
        todo_count=todo_count,
        version_control=version_control,
    )
    test_commands = _discover_test_commands(root, manifests, bool(test_files))
    manifest_details = _read_manifest_details(root, manifests)
    component_rows = [
        {
            "name": name,
            "file_count": count,
            "text_line_count": component_lines[name],
            "kind": "directory" if name != "[root]" else "root_files",
        }
        for name, count in component_files.most_common(16)
    ]
    snapshot_id = fingerprint.hexdigest()[:20]
    project_label = project_name.strip()[:120] or root.name
    return {
        "ok": True,
        "message": (
            f"I analysed {project_label}: {len(files)} workspace files across "
            f"{len(component_files)} components, {len(test_files)} test files, and {len(risks)} review signals."
        ),
        "verification": (
            f"Confirmed: read-only project snapshot {snapshot_id} was produced from the registered root; "
            "no source file or project command was modified or executed."
        ),
        "operation": "analyze_project",
        "project_name": project_label,
        "root": str(root),
        "snapshot_id": snapshot_id,
        "read_only": True,
        "modified_files": 0,
        "file_count": len(files),
        "text_line_count": line_count,
        "extensions": dict(extensions.most_common()),
        "languages": [
            {"name": name, "file_count": count} for name, count in languages.most_common()
        ],
        "components": component_rows,
        "largest_files": [
            {"path": str(path.relative_to(root)), "size_bytes": size}
            for size, path in sorted(largest, reverse=True)[:8]
        ],
        "instructions": sorted(instructions)[:30],
        "manifests": sorted(manifests)[:40],
        "manifest_details": manifest_details,
        "entry_points": sorted(entry_points)[:30],
        "tests": {
            "file_count": len(test_files),
            "files": sorted(test_files)[:80],
            "commands": test_commands,
            "executed": False,
        },
        "version_control": version_control,
        "risks": risks,
        "scan": {
            "truncated": truncated,
            "file_limit": MAX_PROJECT_FILES,
            "oversized_text_files": oversized_text_files,
            "sensitive_text_files_skipped": sensitive_text_files,
            "skipped_symlinks": skipped_symlinks,
        },
        "duration_ms": round((time.monotonic() - started) * 1000),
    }


def _project_files(root: Path) -> tuple[list[Path], bool, int]:
    files: list[Path] = []
    skipped_symlinks = 0
    for current, directories, names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        retained = []
        for name in directories:
            candidate = current_path / name
            if name.casefold() in SKIPPED_DIRECTORIES or candidate.is_symlink():
                skipped_symlinks += int(candidate.is_symlink())
                continue
            retained.append(name)
        directories[:] = retained
        for name in names:
            path = current_path / name
            if path.is_symlink():
                skipped_symlinks += 1
                continue
            files.append(path)
            if len(files) >= MAX_PROJECT_FILES:
                return files, True, skipped_symlinks
    return files, False, skipped_symlinks


def _is_test_file(relative: Path) -> bool:
    parts = {part.casefold() for part in relative.parts[:-1]}
    name = relative.name.casefold()
    return bool(
        parts.intersection({"test", "tests", "__tests__"})
        or name.startswith("test_")
        or name.endswith(("_test.py", ".test.js", ".spec.js", ".test.ts", ".spec.ts", "tests.cs"))
    )


def _is_entry_point(relative: Path) -> bool:
    name = relative.name.casefold()
    return name in {
        "__main__.py",
        "app.py",
        "index.html",
        "index.js",
        "main.py",
        "main.ts",
        "mainactivity.kt",
        "program.cs",
        "server.py",
    }


def _is_sensitive_file_name(name: str) -> bool:
    lowered = name.casefold()
    return bool(
        lowered in SENSITIVE_FILE_NAMES
        or lowered.startswith(".env.")
        or re.search(r"(?:^|[._-])(?:credential|secret|token|private[-_]?key)(?:[._-]|$)", lowered)
    )


def _discover_test_commands(root: Path, manifests: list[str], has_tests: bool) -> list[str]:
    commands: list[str] = []
    manifest_names = {Path(item).name for item in manifests}
    if "pyproject.toml" in manifest_names and has_tests:
        commands.append(f'"{sys.executable}" -m unittest discover -s tests')
    package_path = root / "package.json"
    if package_path.exists():
        try:
            package = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            package = {}
        scripts = package.get("scripts") if isinstance(package, dict) else {}
        if isinstance(scripts, dict) and "test" in scripts:
            commands.append("npm test")
    if any(Path(item).suffix.casefold() in {".sln", ".slnx"} for item in manifests):
        commands.append("dotnet test")
    if "build.gradle" in manifest_names or "build.gradle.kts" in manifest_names:
        commands.append("gradlew test")
    return commands[:8]


def _read_manifest_details(root: Path, manifests: list[str]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for relative in sorted(manifests)[:30]:
        path = root / relative
        item: dict[str, Any] = {"path": relative, "kind": path.name}
        try:
            if path.name == "pyproject.toml":
                payload = tomllib.loads(path.read_text(encoding="utf-8"))
                project = payload.get("project") if isinstance(payload, dict) else {}
                project = project if isinstance(project, dict) else {}
                item.update(
                    {
                        "name": project.get("name"),
                        "runtime": project.get("requires-python"),
                        "dependency_count": len(project.get("dependencies") or []),
                        "tools": sorted((payload.get("tool") or {}).keys())[:12],
                    }
                )
            elif path.name == "package.json":
                payload = json.loads(path.read_text(encoding="utf-8"))
                item.update(
                    {
                        "name": payload.get("name"),
                        "dependency_count": len(payload.get("dependencies") or {}),
                        "dev_dependency_count": len(payload.get("devDependencies") or {}),
                        "scripts": sorted((payload.get("scripts") or {}).keys())[:12],
                    }
                )
            elif path.suffix.casefold() == ".csproj":
                tree = ET.parse(path)
                frameworks = [
                    element.text
                    for element in tree.getroot().iter()
                    if element.tag.rsplit("}", 1)[-1] in {"TargetFramework", "TargetFrameworks"}
                    and element.text
                ]
                item["runtime"] = ", ".join(frameworks) or None
                item["dependency_count"] = sum(
                    element.tag.rsplit("}", 1)[-1] == "PackageReference"
                    for element in tree.getroot().iter()
                )
        except (OSError, ValueError, tomllib.TOMLDecodeError, ET.ParseError):
            item["parse_state"] = "unreadable"
        else:
            item["parse_state"] = "parsed"
        details.append(item)
    return details


def _git_state(root: Path) -> dict[str, Any]:
    git = shutil.which("git")
    if not git or not (root / ".git").exists():
        return {"detected": False, "state": "not_configured", "branch": None, "changed_files": 0}
    try:
        result = subprocess.run(
            [git, "-C", str(root), "status", "--porcelain=v1", "--branch"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"detected": True, "state": "status_unavailable", "branch": None, "changed_files": 0}
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    branch = lines[0][3:].split("...", 1)[0] if lines and lines[0].startswith("## ") else None
    changed = sum(not line.startswith("## ") for line in lines)
    return {
        "detected": result.returncode == 0,
        "state": "dirty" if changed else "clean",
        "branch": branch,
        "changed_files": changed,
    }


def _analysis_signals(
    *,
    truncated: bool,
    skipped_symlinks: int,
    oversized_text_files: int,
    sensitive_text_files: int,
    instructions: list[str],
    test_files: list[str],
    todo_count: int,
    version_control: dict[str, Any],
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    if truncated:
        signals.append({"severity": "amber", "code": "SCAN_LIMIT", "message": "The project exceeded the bounded file scan limit."})
    if not instructions:
        signals.append({"severity": "amber", "code": "NO_INSTRUCTIONS", "message": "No project engineering or security instruction file was found."})
    if not test_files:
        signals.append({"severity": "amber", "code": "NO_TESTS", "message": "No test files were detected."})
    if not version_control.get("detected"):
        signals.append({"severity": "amber", "code": "NO_VERSION_CONTROL", "message": "No readable Git worktree was detected."})
    elif version_control.get("state") == "dirty":
        signals.append({"severity": "info", "code": "WORKTREE_DIRTY", "message": f"Git reports {version_control.get('changed_files', 0)} changed files."})
    if todo_count:
        signals.append({"severity": "info", "code": "OPEN_MARKERS", "message": f"Detected {todo_count} TODO, FIXME, or HACK markers."})
    if oversized_text_files:
        signals.append({"severity": "info", "code": "LARGE_TEXT", "message": f"Skipped content counting for {oversized_text_files} oversized text files."})
    if sensitive_text_files:
        signals.append({"severity": "info", "code": "SENSITIVE_CONTENT_SKIPPED", "message": f"Excluded content from {sensitive_text_files} credential-shaped files."})
    if skipped_symlinks:
        signals.append({"severity": "info", "code": "SYMLINKS_SKIPPED", "message": f"Skipped {skipped_symlinks} symbolic links or linked directories."})
    return signals


def _normalise(command: str) -> str:
    text = " ".join(command.casefold().strip().replace(",", " ").split())
    for prefix in ("hey auris ", "auris "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.strip(" .")
