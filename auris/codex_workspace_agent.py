from __future__ import annotations

import ast
import difflib
import hashlib
import hmac
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import tomllib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4

from auris.auth import harden_private_file
from auris.database import get_control_state
from auris.repair_agent import (
    SKIPPED_DIRECTORIES,
    _atomic_write,
    _repair_key,
    _sign_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
CODEX_PROPOSAL_ROOT = ROOT / "data" / "codex-proposals"
CODEX_WORKTREE_ROOT = ROOT / "data" / "codex-worktrees"
CODEX_KEY_PATH = ROOT / "data" / "codex.key"
CODEX_RUN_ROOT = ROOT / "data" / "codex-runs"
PROPOSAL_TTL_MINUTES = 60
MAX_PROJECT_FILES = 20_000
MAX_ISOLATION_BYTES = 256 * 1024 * 1024
MAX_CHANGED_FILES = 24
MAX_CHANGED_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 512 * 1024
MAX_DIFF_LINES = 4_000
MAX_CODEX_OUTPUT_BYTES = 8 * 1024 * 1024
CODEX_TIMEOUT_SECONDS = 20 * 60
TEXT_EXTENSIONS = {
    ".cs",
    ".css",
    ".go",
    ".gradle",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".kts",
    ".md",
    ".php",
    ".ps1",
    ".py",
    ".rb",
    ".rs",
    ".sql",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
TEXT_NAMES = {
    ".editorconfig",
    ".gitignore",
    "Dockerfile",
    "Makefile",
}
PROTECTED_INSTRUCTION_NAMES = {
    "AGENTS.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
}
SENSITIVE_NAMES = {
    ".env",
    "credentials.json",
    "secrets.json",
    "service-account.json",
}
CodexExecutor = Callable[[list[str], str, Path, int], dict[str, Any]]
_STATUS_CACHE: tuple[float, dict[str, Any]] | None = None
_APPLY_LOCK = threading.Lock()
SNAPSHOT_SKIPPED_DIRECTORIES = SKIPPED_DIRECTORIES | {".codex", ".ssh", ".aws", ".gnupg"}


def _codex_executable() -> str | None:
    executable = shutil.which("codex")
    if executable:
        return executable
    local_appdata = os.environ.get("LOCALAPPDATA")
    if os.name == "nt" and local_appdata:
        directory = Path(local_appdata) / "OpenAI" / "Codex" / "bin"
        candidates = [path for path in directory.glob("*/codex.exe") if path.is_file() and not _is_reparse(path)]
        if candidates:
            return str(max(candidates, key=lambda path: path.stat().st_mtime))
    return None


def codex_cli_status(*, force: bool = False) -> dict[str, Any]:
    global _STATUS_CACHE
    if not force and _STATUS_CACHE is not None and time.monotonic() - _STATUS_CACHE[0] < 30:
        return dict(_STATUS_CACHE[1])
    executable = _codex_executable()
    authenticated = False
    detail = "Codex CLI is not installed."
    if executable:
        try:
            status = subprocess.run(
                [executable, "login", "status"],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=5,
                check=False,
            )
            authenticated = status.returncode == 0
            detail = (
                "Codex CLI is authenticated and ready for isolated missions."
                if authenticated
                else "Codex CLI is installed but requires sign-in before delegated missions can run."
            )
        except (OSError, subprocess.SubprocessError):
            detail = "Codex CLI is installed, but its login state could not be verified."
    result = {
        "available": bool(executable),
        "authenticated": authenticated,
        "ready": bool(executable and authenticated),
        "engine": "codex_cli",
        "executable": Path(executable).name if executable else None,
        "sandbox": "workspace-write",
        "approval_policy": "never_inside_isolation",
        "source_apply_policy": "signed_diff_approval_once",
        "detail": detail,
    }
    _STATUS_CACHE = (time.monotonic(), result)
    return dict(result)


def prepare_codex_workspace_change(
    objective: str,
    *,
    root: Path,
    project_name: str,
    trusted_execution: bool,
    executor: CodexExecutor | None = None,
    proposal_root: Path = CODEX_PROPOSAL_ROOT,
    worktree_root: Path = CODEX_WORKTREE_ROOT,
    key_path: Path = CODEX_KEY_PATH,
) -> dict[str, Any]:
    started = time.monotonic()
    if not trusted_execution:
        return _failed(
            "prepare_codex_workspace_change",
            "Codex workspace execution is enabled only for AURIS or an AURIS-managed project.",
            "Confirmed: Codex did not start and the selected project was unchanged.",
        )
    try:
        project_root = _validated_root(root)
    except ValueError as error:
        return _failed("prepare_codex_workspace_change", str(error))
    executable = _codex_executable()
    if not executable and executor is None:
        return _failed(
            "prepare_codex_workspace_change",
            "The Codex CLI is not installed or is not available on PATH.",
            "Confirmed: no isolated workspace was created and no source file changed.",
        )
    if executor is None:
        status = codex_cli_status(force=True)
        if not status["ready"]:
            return _failed(
                "prepare_codex_workspace_change",
                str(status["detail"]),
                "Confirmed: no isolated workspace was created and no source file changed.",
                codex_status=status,
            )
    cleanup_expired_codex_proposals(
        proposal_root=proposal_root,
        worktree_root=worktree_root,
        key_path=key_path,
    )
    proposal_id = str(uuid4())
    try:
        isolation = _create_snapshot(project_root, proposal_id, worktree_root)
    except (OSError, RuntimeError, ValueError) as error:
        return _failed(
            "prepare_codex_workspace_change",
            f"The isolated coding workspace could not be created: {error}",
        )
    isolated_root = Path(str(isolation["path"]))
    try:
        before = _inventory(isolated_root)
        prompt = _codex_prompt(objective, project_name)
        args = _codex_arguments(executable or "codex", isolated_root)
        run = (executor or _execute_codex_cli)(args, prompt, isolated_root, CODEX_TIMEOUT_SECONDS)
        if not run.get("ok"):
            return _failed(
                "prepare_codex_workspace_change",
                str(run.get("error") or "Codex did not complete the isolated coding mission."),
                "Confirmed: the failed isolated workspace was discarded and the selected project was unchanged.",
                codex_run=_public_run(run),
            )
        after = _inventory(isolated_root)
        try:
            changes = _collect_changes(before, after)
            diff, diff_stats = _build_diff(changes)
        except ValueError as error:
            return _failed(
                "prepare_codex_workspace_change",
                str(error),
                "Confirmed: the unreviewable isolated result was discarded and the selected project was unchanged.",
                codex_run=_public_run(run),
            )
        validation = _static_validation(isolated_root, changes)
        if not validation["passed"]:
            return _failed(
                "prepare_codex_workspace_change",
                "The isolated change failed independent static validation.",
                "Confirmed: invalid generated files never reached the selected project.",
                codex_run=_public_run(run),
                validation=validation,
            )
        now = datetime.now(timezone.utc)
        manifest: dict[str, Any] = {
            "schema_version": 1,
            "proposal_id": proposal_id,
            "project_root": str(project_root),
            "project_name": (project_name.strip() or project_root.name)[:120],
            "operation": "codex_workspace_change",
            "objective": objective.strip()[:4_000],
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=PROPOSAL_TTL_MINUTES)).isoformat(),
            "status": "ready",
            "isolation_kind": str(isolation.get("kind") or "private_snapshot"),
            "codex_run": _public_run(run),
            "changes": _manifest_changes(changes),
            "diff": diff,
            "diff_stats": diff_stats,
            "validation": validation,
            "test_execution_policy": "codex_sandbox_only",
            "verified_full": None,
            "snapshot_excluded_files": isolation["excluded_files"],
        }
        manifest["signature"] = _sign_manifest(manifest, _repair_key(key_path))
        _write_manifest(manifest, proposal_root)
        return {
            "ok": True,
            "operation": "prepare_codex_workspace_change",
            "engine": "codex_cli",
            "message": (
                f"Codex completed the isolated coding mission and produced a verified "
                f"{len(changes)}-file proposal. The selected project is unchanged until you approve the exact diff."
            ),
            "verification": (
                "Confirmed: Codex ran inside an isolated workspace; changed files passed bounded review"
                + " and static validation"
                + "; the signed source proposal requires one-time approval."
            ),
            "proposal": _public_manifest(manifest),
            "approval_required": True,
            "source_project_modified": False,
            "duration_ms": round((time.monotonic() - started) * 1000),
        }
    except (OSError, RuntimeError, ValueError) as error:
        return _failed(
            "prepare_codex_workspace_change",
            f"The isolated Codex mission failed safely: {error}",
        )
    finally:
        _remove_snapshot(isolated_root, worktree_root)


def apply_codex_workspace_change(
    proposal_id: str,
    *,
    root: Path,
    trusted_execution: bool,
    proposal_root: Path = CODEX_PROPOSAL_ROOT,
    key_path: Path = CODEX_KEY_PATH,
) -> dict[str, Any]:
    with _APPLY_LOCK:
        return _apply_codex_workspace_change(
            proposal_id, root=root, trusted_execution=trusted_execution,
            proposal_root=proposal_root, key_path=key_path,
        )


def _apply_codex_workspace_change(
    proposal_id: str, *, root: Path, trusted_execution: bool,
    proposal_root: Path, key_path: Path,
) -> dict[str, Any]:
    if not trusted_execution:
        return _failed(
            "apply_codex_workspace_change",
            "The selected project is not trusted for a Codex workspace change.",
        )
    try:
        project_root = _validated_root(root)
        manifest = _read_manifest(proposal_id, proposal_root, key_path)
        _validate_manifest(manifest, project_root)
        originals = _load_preimages(project_root, manifest["changes"])
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        return _failed(
            "apply_codex_workspace_change",
            f"The approved Codex proposal could not be safely revalidated: {error}",
            "Confirmed: no source file was changed.",
        )

    changed_paths: list[Path] = []
    try:
        for change in manifest["changes"]:
            path = _bound_path(project_root, str(change["path"]))
            _atomic_write(
                path,
                str(change["new_content"]),
                require_existing=not bool(change["is_new"]),
            )
            changed_paths.append(path)
        validation = _static_validation(project_root, manifest["changes"])
        if not validation["passed"]:
            raise RuntimeError("Final static validation failed.")
        for change in manifest["changes"]:
            path = _bound_path(project_root, str(change["path"]))
            if _sha256_file(path) != change["new_sha256"]:
                raise RuntimeError(f"Final file hash verification failed for {change['path']}.")
        _finish_manifest(manifest, "applied", proposal_root, key_path)
    except (OSError, RuntimeError, UnicodeError, ValueError) as error:
        rollback_ok = _rollback(originals)
        _finish_manifest(
            manifest,
            "rolled_back" if rollback_ok else "rollback_failed",
            proposal_root,
            key_path,
        )
        return {
            "ok": False,
            "operation": "apply_codex_workspace_change",
            "engine": "codex_cli",
            "error": f"The approved Codex change failed final verification: {error}",
            "verification": (
                "Confirmed: modified files were restored and newly created files were removed."
                if rollback_ok
                else "Critical: exact rollback could not be fully verified. Manual recovery is required."
            ),
            "proposal_id": proposal_id,
            "rolled_back": rollback_ok,
        }

    return {
        "ok": True,
        "operation": "apply_codex_workspace_change",
        "engine": "codex_cli",
        "message": (
            f"The approved Codex change was applied to {len(changed_paths)} file"
            f"{'s' if len(changed_paths) != 1 else ''} and passed final verification."
        ),
        "verification": (
            "Confirmed: signature, expiry, project binding, source preimages, static checks, "
            "and final hashes passed. Generated code was not executed by AURIS."
        ),
        "proposal_id": proposal_id,
        "applied_files": [path.relative_to(project_root).as_posix() for path in changed_paths],
        "diff": manifest["diff"],
        "diff_stats": dict(manifest["diff_stats"]),
        "validation": validation,
        "full_test": None,
        "rolled_back": False,
    }


def discard_codex_workspace_change(
    proposal_id: str,
    *,
    proposal_root: Path = CODEX_PROPOSAL_ROOT,
    key_path: Path = CODEX_KEY_PATH,
) -> bool:
    try:
        manifest = _read_manifest(proposal_id, proposal_root, key_path)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
        return False
    if manifest.get("status") != "ready":
        return False
    path = _manifest_path(proposal_id, proposal_root)
    path.unlink()
    return not path.exists()


def cleanup_expired_codex_proposals(
    *,
    proposal_root: Path = CODEX_PROPOSAL_ROOT,
    worktree_root: Path = CODEX_WORKTREE_ROOT,
    key_path: Path = CODEX_KEY_PATH,
) -> int:
    removed = 0
    if proposal_root.is_dir() and key_path.exists():
        for path in sorted(proposal_root.glob("*.json"))[:100]:
            try:
                manifest = _read_manifest(path.stem, proposal_root, key_path)
                expiry = datetime.fromisoformat(str(manifest.get("expires_at", "")))
                if manifest.get("status") == "ready" and expiry.tzinfo and expiry <= datetime.now(timezone.utc):
                    path.unlink()
                    removed += int(not path.exists())
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
                continue
    # Snapshots are owned by their live worker; another mission must never remove them.
    return removed


def codex_approval_details(outcome: dict[str, Any]) -> tuple[str, str]:
    proposal = outcome.get("proposal") if isinstance(outcome.get("proposal"), dict) else {}
    files = [item.get("path") for item in proposal.get("files", []) if isinstance(item, dict)]
    stats = proposal.get("diff_stats") if isinstance(proposal.get("diff_stats"), dict) else {}
    validation = proposal.get("validation") if isinstance(proposal.get("validation"), dict) else {}
    target = str(proposal.get("project_name") or "registered project")[:200]
    summary = (
        f"Codex proposal {proposal.get('proposal_id')}; files: {', '.join(str(item) for item in files) or 'none'}; "
        f"+{stats.get('added_lines', 0)} -{stats.get('removed_lines', 0)} lines; "
        f"{validation.get('passed_checks', 0)} independent checks passed; approval applies this signed diff once."
    )
    return target, summary[:2_000]


def _codex_arguments(executable: str, root: Path) -> list[str]:
    return [
        executable,
        "--no-daemon",
        "--ask-for-approval",
        "never",
        "--sandbox",
        "workspace-write",
        "-C",
        str(root),
        "exec",
        "--ignore-user-config",
        "--ignore-rules",
        "-c",
        f"projects.{json.dumps(str(root))}.trust_level=\"trusted\"",
        "-c",
        'sandbox_mode="workspace-write"',
        "-c",
        'windows.sandbox="elevated"',
        "-c",
        "sandbox_workspace_write.network_access=false",
        "-c",
        "sandbox_workspace_write.exclude_tmpdir_env_var=true",
        "-c",
        "sandbox_workspace_write.exclude_slash_tmp=true",
        "-c",
        'shell_environment_policy.inherit="core"',
        "-c",
        "allow_login_shell=false",
        "--json",
        "--ephemeral",
        "--color",
        "never",
        "--skip-git-repo-check",
        "-",
    ]


def _codex_prompt(objective: str, project_name: str) -> str:
    cleaned = objective.strip()
    if not cleaned or len(cleaned) > 4_000:
        raise ValueError("A bounded coding objective is required.")
    return f"""You are the coding engine for AURIS, working in an isolated copy of {project_name[:120]}.

Objective:
{cleaned}

Operating contract:
- Inspect the repository and its instruction files before editing.
- Implement the requested outcome completely, keeping changes tightly scoped.
- Use apply_patch for edits. Do not delete files.
- Do not edit AGENTS.md, security policy files, credentials, secrets, or CI workflow files.
- Do not install dependencies, access private data, or use the network.
- Add or update appropriate tests when the project already has a test surface.
- Run relevant existing checks when safe, inspect failures, and repair your change before finishing.
- Never claim success based only on generated text. The resulting filesystem and independent checks are authoritative.

Finish with a concise summary of changed files, checks run, and any remaining limitation.
"""


def _execute_codex_cli(
    args: list[str], prompt: str, cwd: Path, timeout_seconds: int
) -> dict[str, Any]:
    CODEX_RUN_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid4())
    stdout_path = CODEX_RUN_ROOT / f"{run_id}.jsonl"
    stderr_path = CODEX_RUN_ROOT / f"{run_id}.stderr"
    started = time.monotonic()
    process: subprocess.Popen[str] | None = None
    stopped_reason = ""
    try:
        with stdout_path.open("x", encoding="utf-8", newline="") as stdout_handle, stderr_path.open(
            "x", encoding="utf-8", newline=""
        ) as stderr_handle:
            harden_private_file(stdout_path)
            harden_private_file(stderr_path)
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            process = subprocess.Popen(
                args,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                creationflags=creationflags,
                start_new_session=os.name != "nt",
            )
            if process.stdin is None:
                raise RuntimeError("Codex stdin was unavailable.")
            process.stdin.write(prompt)
            process.stdin.close()
            while process.poll() is None:
                elapsed = time.monotonic() - started
                if elapsed > timeout_seconds:
                    stopped_reason = "The isolated Codex mission exceeded its time limit."
                elif get_control_state().get("stopped"):
                    stopped_reason = "AURIS emergency stop interrupted the isolated Codex mission."
                elif (
                    stdout_path.stat().st_size + stderr_path.stat().st_size
                    > MAX_CODEX_OUTPUT_BYTES
                ):
                    stopped_reason = "The isolated Codex mission exceeded its output limit."
                if stopped_reason:
                    _stop_process_tree(process)
                    break
                time.sleep(0.25)
            process.wait(timeout=10)
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
        events = _json_events(stdout)
        exit_code = int(process.returncode if process and process.returncode is not None else 1)
        return {
            "ok": not stopped_reason and exit_code == 0,
            "exit_code": exit_code,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "event_count": len(events),
            "last_message": _last_agent_message(events),
            "error": stopped_reason or (_clean_output(stderr)[-2_000:] if exit_code else ""),
        }
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        if process is not None and process.poll() is None:
            _stop_process_tree(process)
            process.wait(timeout=10)
        return {
            "ok": False,
            "exit_code": None,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "event_count": 0,
            "last_message": "",
            "error": f"Codex could not run: {error}",
        }
    finally:
        stdout_path.unlink(missing_ok=True)
        stderr_path.unlink(missing_ok=True)


def _json_events(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in raw.splitlines()[:20_000]:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def _last_agent_message(events: list[dict[str, Any]]) -> str:
    for event in reversed(events):
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") in {"agent_message", "message"}:
            text = item.get("text") or item.get("content")
            if isinstance(text, str) and text.strip():
                return _clean_output(text)[-2_000:]
        message = event.get("message")
        if isinstance(message, str) and message.strip():
            return _clean_output(message)[-2_000:]
    return ""


def _stop_process_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True, timeout=15, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        os.killpg(process.pid, signal.SIGKILL)
    if process.poll() is None:
        process.kill()


def _is_reparse(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)


def _bound_path(root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.drive:
        raise ValueError("A coding path escaped the project root.")
    candidate = root / relative
    candidate.resolve(strict=False).relative_to(root.resolve(strict=True))
    current = root
    for part in relative.parts:
        current = current / part
        if (current.exists() or current.is_symlink()) and _is_reparse(current):
            raise ValueError("Filesystem links are forbidden in coding paths.")
    return candidate


def _create_snapshot(project_root: Path, proposal_id: str, worktree_root: Path) -> dict[str, Any]:
    UUID(proposal_id)
    root = worktree_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / proposal_id
    if target.exists() or target.parent != root:
        raise ValueError("The coding snapshot path is not a new private directory.")
    target.mkdir()
    count = total = excluded = 0
    try:
        for current, directories, names in os.walk(project_root, topdown=True, followlinks=False):
            current_path = Path(current)
            retained = []
            for name in directories:
                if name.casefold() in SNAPSHOT_SKIPPED_DIRECTORIES or name.startswith(".tmp-"):
                    continue
                if _is_reparse(current_path / name):
                    raise ValueError("Filesystem links are forbidden in coding snapshots.")
                retained.append(name)
            directories[:] = retained
            for name in names:
                source = current_path / name
                if _is_reparse(source) or not source.is_file():
                    raise ValueError("Filesystem links are forbidden in coding snapshots.")
                size = source.stat().st_size
                count += 1
                total += size
                if count > MAX_PROJECT_FILES or total > MAX_ISOLATION_BYTES:
                    raise ValueError("The project exceeds the bounded coding snapshot limits.")
                if _is_sensitive_name(name.casefold()) or source.suffix.casefold() in {
                    ".pem", ".key", ".pfx", ".p12", ".db", ".sqlite", ".sqlite3", ".log",
                }:
                    excluded += 1
                    continue
                if _is_text_path(source) and size <= MAX_FILE_BYTES:
                    try:
                        content = source.read_bytes().decode("utf-8")
                    except UnicodeError:
                        content = ""
                    if _content_safety_finding(name, content) or "-----BEGIN PRIVATE KEY-----" in content:
                        excluded += 1
                        continue
                destination = _bound_path(target, source.relative_to(project_root).as_posix())
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        return {"kind": "filtered_content_snapshot", "path": str(target), "excluded_files": excluded}
    except Exception:
        _remove_snapshot(target, root)
        raise


def _remove_snapshot(target: Path, worktree_root: Path) -> None:
    root = worktree_root.resolve()
    UUID(target.name)
    if target.parent.resolve() != root or _is_reparse(target) or target.resolve() == root:
        raise ValueError("The coding snapshot cleanup target escaped its private store.")
    shutil.rmtree(target)


def _inventory(root: Path) -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    total_bytes = 0
    for current, directories, names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        retained: list[str] = []
        for name in directories:
            candidate = current_path / name
            if _is_reparse(candidate):
                raise ValueError("Filesystem links are forbidden in coding workspaces.")
            if name.casefold() in SKIPPED_DIRECTORIES:
                continue
            retained.append(name)
        directories[:] = retained
        for name in names:
            path = current_path / name
            relative = path.relative_to(root)
            if any(part.casefold() in SKIPPED_DIRECTORIES for part in relative.parts):
                continue
            if _is_reparse(path) or not path.is_file():
                raise ValueError(f"Unsupported filesystem object in coding workspace: {relative.as_posix()}")
            size = path.stat().st_size
            total_bytes += size
            if len(inventory) >= MAX_PROJECT_FILES or total_bytes > MAX_ISOLATION_BYTES:
                raise ValueError("The coding workspace exceeds its bounded scan limits.")
            content = None
            if _is_text_path(relative) and size <= MAX_FILE_BYTES:
                try:
                    content = path.read_bytes().decode("utf-8")
                except (OSError, UnicodeError):
                    content = None
            inventory[relative.as_posix()] = {
                "path": relative.as_posix(),
                "sha256": _sha256_file(path),
                "size": size,
                "content": content,
            }
    return inventory


def _collect_changes(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    deleted = sorted(set(before) - set(after))
    if deleted:
        raise ValueError("The first Codex workspace release refuses file deletion; no proposal was retained.")
    changed_names = sorted(
        name for name, item in after.items() if name not in before or item["sha256"] != before[name]["sha256"]
    )
    if not changed_names:
        raise ValueError("Codex completed without producing a filesystem change.")
    if len(changed_names) > MAX_CHANGED_FILES:
        raise ValueError("The Codex result changed too many files for one reviewable proposal.")
    changes: list[dict[str, Any]] = []
    total_bytes = 0
    for name in changed_names:
        relative = Path(name)
        if not _is_allowed_change_path(relative):
            raise ValueError(f"Codex changed a protected or unsupported path: {name}.")
        new = after[name]
        old = before.get(name)
        if new.get("content") is None or (old is not None and old.get("content") is None):
            raise ValueError(f"Codex changed a binary, oversized, or non-UTF-8 file: {name}.")
        new_content = str(new["content"])
        total_bytes += len(new_content.encode("utf-8"))
        if total_bytes > MAX_CHANGED_BYTES:
            raise ValueError("The Codex result exceeds the signed changed-content budget.")
        finding = _content_safety_finding(name, new_content)
        if finding:
            raise ValueError(finding)
        changes.append(
            {
                "path": name,
                "old_sha256": old.get("sha256") if old else None,
                "new_sha256": new["sha256"],
                "old_content": str(old.get("content") or "") if old else "",
                "new_content": new_content,
                "is_new": old is None,
            }
        )
    return changes


def _is_text_path(relative: Path) -> bool:
    return relative.suffix.casefold() in TEXT_EXTENSIONS or relative.name in TEXT_NAMES


def _is_allowed_change_path(relative: Path) -> bool:
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        return False
    lowered_parts = [part.casefold() for part in relative.parts]
    name = relative.name
    lowered_name = name.casefold()
    if any(part in {".git", ".codex"} for part in lowered_parts):
        return False
    if len(lowered_parts) >= 2 and lowered_parts[0] == ".github" and lowered_parts[1] == "workflows":
        return False
    if name in PROTECTED_INSTRUCTION_NAMES or _is_sensitive_name(lowered_name):
        return False
    return _is_text_path(relative)


def _is_sensitive_name(lowered_name: str) -> bool:
    return bool(
        lowered_name in SENSITIVE_NAMES
        or lowered_name.startswith(".env.")
        or re.search(r"(?:^|[._-])(?:credential|secret|token|private[-_]?key)(?:[._-]|$)", lowered_name)
    )


def _content_safety_finding(path: str, content: str) -> str | None:
    if "\x00" in content:
        return f"Codex produced invalid text content in {path}."
    if re.search(
        r"(?:api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*['\"][A-Za-z0-9_\-/+=]{12,}['\"]",
        content,
        re.IGNORECASE,
    ):
        return f"Codex appears to have introduced a hard-coded credential in {path}."
    return None


def _static_validation(root: Path, changes: list[dict[str, Any]]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for change in changes:
        relative = str(change["path"])
        path = _bound_path(root, relative)
        try:
            content = path.read_bytes().decode("utf-8")
            if _sha256(content) != str(change["new_sha256"]):
                raise ValueError("content hash differs from the proposed file")
            if re.search(r"^(?:<<<<<<<|=======|>>>>>>>)", content, re.MULTILINE):
                raise ValueError("unresolved merge-conflict marker detected")
            suffix = path.suffix.casefold()
            if suffix == ".py":
                ast.parse(content, filename=relative)
            elif suffix == ".json":
                json.loads(content)
            elif suffix == ".toml":
                tomllib.loads(content)
            elif suffix == ".xml":
                ET.fromstring(content)
        except (OSError, UnicodeError, SyntaxError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError, ET.ParseError) as error:
            checks.append({"path": relative, "passed": False, "detail": str(error)[:300]})
        else:
            checks.append({"path": relative, "passed": True, "detail": "hash and static syntax accepted"})
    passed = bool(checks) and all(item["passed"] for item in checks)
    return {
        "passed": passed,
        "validation_level": "static",
        "dynamic_tests_independently_verified": False,
        "passed_checks": sum(bool(item["passed"]) for item in checks),
        "total_checks": len(checks),
        "checks": checks,
    }


def _build_diff(changes: list[dict[str, Any]]) -> tuple[str, dict[str, int]]:
    lines: list[str] = []
    added = 0
    removed = 0
    for change in changes:
        old_content = str(change["old_content"])
        new_content = str(change["new_content"])
        current = list(
            difflib.unified_diff(
                old_content.splitlines(),
                new_content.splitlines(),
                fromfile="/dev/null" if change["is_new"] else f"a/{change['path']}",
                tofile=f"b/{change['path']}",
                lineterm="",
                n=3,
            )
        )
        for line in current:
            if line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1
        lines.extend(current)
    if not lines:
        raise ValueError("The Codex result produced no reviewable diff.")
    if len(lines) > MAX_DIFF_LINES:
        raise ValueError("The Codex diff exceeds the reviewable line limit.")
    return "\n".join(lines), {
        "files_changed": len(changes),
        "added_lines": added,
        "removed_lines": removed,
        "diff_lines": len(lines),
    }


def _manifest_changes(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "path": str(change["path"]),
            "old_sha256": change["old_sha256"],
            "new_sha256": str(change["new_sha256"]),
            "new_content": str(change["new_content"]),
            "is_new": bool(change["is_new"]),
        }
        for change in changes
    ]


def _public_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": manifest["schema_version"],
        "proposal_id": manifest["proposal_id"],
        "project_name": manifest["project_name"],
        "operation": manifest["operation"],
        "objective": manifest["objective"],
        "created_at": manifest["created_at"],
        "expires_at": manifest["expires_at"],
        "status": manifest["status"],
        "isolation_kind": manifest["isolation_kind"],
        "engine": "codex_cli",
        "diagnosis": str((manifest.get("codex_run") or {}).get("last_message") or "Codex completed the requested isolated implementation.")[:2_000],
        "files": [
            {
                "path": item["path"],
                "old_sha256": item["old_sha256"],
                "new_sha256": item["new_sha256"],
                "is_new": item["is_new"],
            }
            for item in manifest["changes"]
        ],
        "diff": manifest["diff"],
        "diff_stats": dict(manifest["diff_stats"]),
        "validation": dict(manifest["validation"]),
        "verified_full": manifest.get("verified_full"),
        "codex_run": dict(manifest["codex_run"]),
        "source_project_modified": False,
        "full_source_in_task_store": False,
    }


def _public_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "exit_code": run.get("exit_code"),
        "duration_ms": run.get("duration_ms"),
        "event_count": run.get("event_count", 0),
        "last_message": str(run.get("last_message") or "")[:2_000],
    }


def _write_manifest(manifest: dict[str, Any], proposal_root: Path) -> None:
    proposal_id = str(manifest.get("proposal_id", ""))
    path = _manifest_path(proposal_id, proposal_root)
    proposal_root.mkdir(parents=True, exist_ok=True)
    content = json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if len(content.encode("utf-8")) > 6 * 1024 * 1024:
        raise ValueError("The private Codex proposal exceeds its storage limit.")
    _atomic_write(path, content, require_existing=False)
    harden_private_file(path)


def _manifest_path(proposal_id: str, proposal_root: Path) -> Path:
    UUID(proposal_id)
    root = proposal_root.resolve()
    path = (root / f"{proposal_id}.json").resolve()
    if path.parent != root:
        raise ValueError("The Codex proposal path escaped its private store.")
    return path


def _read_manifest(
    proposal_id: str, proposal_root: Path, key_path: Path
) -> dict[str, Any]:
    path = _manifest_path(proposal_id, proposal_root)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 6 * 1024 * 1024:
        raise ValueError("The signed Codex proposal does not exist or is invalid.")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("proposal_id") != proposal_id:
        raise ValueError("The Codex proposal identity is invalid.")
    signature = str(manifest.get("signature") or "")
    expected = _sign_manifest(manifest, _repair_key(key_path))
    if not signature or not hmac.compare_digest(signature, expected):
        raise ValueError("The Codex proposal signature is invalid.")
    return manifest


def _validate_manifest(manifest: dict[str, Any], project_root: Path) -> None:
    if manifest.get("operation") != "codex_workspace_change" or manifest.get("status") != "ready":
        raise ValueError("The Codex proposal is not ready for one-time application.")
    if manifest.get("schema_version") != 1:
        raise ValueError("The Codex proposal schema is invalid.")
    bound_root = Path(str(manifest.get("project_root") or "")).resolve(strict=True)
    if bound_root != project_root:
        raise ValueError("The Codex proposal is bound to a different project root.")
    expires_at = datetime.fromisoformat(str(manifest.get("expires_at") or ""))
    if expires_at.tzinfo is None or expires_at <= datetime.now(timezone.utc):
        raise ValueError("The Codex proposal expired before approval.")
    changes = manifest.get("changes")
    if not isinstance(changes, list) or not 1 <= len(changes) <= MAX_CHANGED_FILES:
        raise ValueError("The Codex proposal has an invalid change count.")
    total_bytes = 0
    seen: set[str] = set()
    for change in changes:
        if not isinstance(change, dict) or set(change) != {
            "path", "old_sha256", "new_sha256", "new_content", "is_new"
        }:
            raise ValueError("The Codex proposal contains an invalid file change.")
        relative = Path(str(change["path"]))
        if not _is_allowed_change_path(relative) or relative.as_posix() in seen:
            raise ValueError("The Codex proposal contains a repeated or forbidden path.")
        seen.add(relative.as_posix())
        content = change["new_content"]
        if not isinstance(content, str) or _sha256(content) != change["new_sha256"]:
            raise ValueError("Proposed source does not match its signed hash.")
        if bool(change["is_new"]) != (change["old_sha256"] is None):
            raise ValueError("The Codex proposal has an invalid source preimage binding.")
        if change["old_sha256"] is not None and not re.fullmatch(r"[0-9a-f]{64}", str(change["old_sha256"])):
            raise ValueError("A Codex source preimage hash is invalid.")
        total_bytes += len(content.encode("utf-8"))
    if total_bytes > MAX_CHANGED_BYTES:
        raise ValueError("The Codex proposal exceeds the signed byte limit.")
    diff = manifest.get("diff")
    if not isinstance(diff, str) or len(diff.splitlines()) > MAX_DIFF_LINES:
        raise ValueError("The signed Codex diff is invalid.")


def _load_preimages(
    root: Path, changes: list[dict[str, Any]]
) -> dict[Path, bytes | None]:
    originals: dict[Path, bytes | None] = {}
    for change in changes:
        path = _bound_path(root, str(change["path"]))
        if change["is_new"]:
            if path.exists():
                raise ValueError(f"A proposed new file now exists: {change['path']}.")
            originals[path] = None
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"A source target is no longer a regular file: {change['path']}.")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != change["old_sha256"]:
            raise ValueError(f"The source file changed after proposal verification: {change['path']}.")
        originals[path] = content
    return originals


def _rollback(originals: dict[Path, bytes | None]) -> bool:
    try:
        for path, content in reversed(list(originals.items())):
            if content is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, content.decode("utf-8"))
        return all(
            (not path.exists()) if content is None else (
                path.is_file() and not _is_reparse(path) and _sha256_file(path) == hashlib.sha256(content).hexdigest()
            )
            for path, content in originals.items()
        )
    except (OSError, UnicodeError, ValueError):
        return False


def _finish_manifest(
    manifest: dict[str, Any], status: str, proposal_root: Path, key_path: Path
) -> None:
    manifest["status"] = status
    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    for change in manifest.get("changes", []):
        if isinstance(change, dict):
            change.pop("new_content", None)
    manifest["replacement_content_retained"] = False
    manifest["signature"] = _sign_manifest(manifest, _repair_key(key_path))
    _write_manifest(manifest, proposal_root)


def _validated_root(root: Path) -> Path:
    text = str(root).strip()
    if not text or len(text) > 500:
        raise ValueError("A bounded project directory is required.")
    try:
        resolved = Path(text).expanduser().resolve(strict=True)
    except OSError as error:
        raise ValueError("The configured project directory does not exist.") from error
    if not resolved.is_dir() or resolved == Path(resolved.anchor) or resolved == Path.home().resolve():
        raise ValueError("The project root must be an existing directory below the user profile or drive root.")
    blocked = {".aws", ".gnupg", ".ssh", "appdata", "programdata", "windows"}
    if any(part.casefold() in blocked for part in resolved.parts):
        raise ValueError("That directory is inside a protected credential or system boundary.")
    return resolved


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean_output(value: str) -> str:
    without_ansi = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value)
    return "".join(char for char in without_ansi if char in "\n\r\t" or ord(char) >= 32)


def _failed(
    operation: str,
    error: str,
    verification: str = "Confirmed: the selected project was unchanged.",
    **details: Any,
) -> dict[str, Any]:
    return {
        "ok": False,
        "operation": operation,
        "engine": "codex_cli",
        "error": error,
        "verification": verification,
        "source_project_modified": False,
        **details,
    }
