from __future__ import annotations

import os
import re
import shutil
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    import winreg
except ImportError:  # pragma: no cover - AURIS targets Windows, tests may not.
    winreg = None


@dataclass(frozen=True)
class InstalledApplication:
    name: str
    launch_target: str
    source: str
    aliases: tuple[str, ...] = ()
    process_names: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


COMMON_ALIASES = {
    "brave": ("brave browser",),
    "microsoft edge": ("edge", "edge browser"),
    "visual studio code": ("vs code", "vscode", "code"),
    "microsoft visual studio code": ("vs code", "vscode", "code"),
    "microsoft word": ("word",),
    "microsoft excel": ("excel",),
    "microsoft powerpoint": ("powerpoint", "power point"),
    "microsoft outlook": ("outlook",),
    "windows media player": ("media player",),
    "windows terminal": ("terminal",),
    "command prompt": ("cmd",),
    "file explorer": ("explorer", "files"),
    "microsoft store": ("store",),
    "microsoft teams": ("teams",),
}

KNOWN_PROCESSES = {
    "brave": ("brave.exe",),
    "spotify": ("spotify.exe",),
    "discord": ("discord.exe",),
    "visual studio code": ("code.exe",),
    "microsoft visual studio code": ("code.exe",),
    "microsoft edge": ("msedge.exe",),
    "google chrome": ("chrome.exe",),
    "firefox": ("firefox.exe",),
    "word": ("winword.exe",),
    "microsoft word": ("winword.exe",),
    "excel": ("excel.exe",),
    "microsoft excel": ("excel.exe",),
    "powerpoint": ("powerpnt.exe",),
    "microsoft powerpoint": ("powerpnt.exe",),
    "outlook": ("outlook.exe", "olk.exe"),
    "microsoft outlook": ("outlook.exe", "olk.exe"),
    "teams": ("ms-teams.exe", "teams.exe"),
    "microsoft teams": ("ms-teams.exe", "teams.exe"),
    "notepad": ("notepad.exe",),
    "calculator": ("calculatorapp.exe", "calc.exe"),
    "paint": ("mspaint.exe",),
    "file explorer": ("explorer.exe",),
    "task manager": ("taskmgr.exe",),
    "windows terminal": ("windowsterminal.exe",),
}

STATIC_APPLICATIONS = (
    InstalledApplication("Notepad", "notepad.exe", "windows", process_names=("notepad.exe",)),
    InstalledApplication(
        "Calculator",
        "calc.exe",
        "windows",
        process_names=("calculatorapp.exe", "calc.exe"),
    ),
    InstalledApplication(
        "File Explorer",
        "explorer.exe",
        "windows",
        aliases=("Explorer", "Files"),
        process_names=("explorer.exe",),
    ),
    InstalledApplication("Paint", "mspaint.exe", "windows", process_names=("mspaint.exe",)),
    InstalledApplication("Settings", "ms-settings:", "windows", process_names=("systemsettings.exe",)),
    InstalledApplication("Task Manager", "taskmgr.exe", "windows", process_names=("taskmgr.exe",)),
    InstalledApplication(
        "Command Prompt",
        "cmd.exe",
        "windows",
        aliases=("CMD",),
        process_names=("cmd.exe",),
    ),
    InstalledApplication(
        "Windows PowerShell",
        "powershell.exe",
        "windows",
        aliases=("PowerShell",),
        process_names=("powershell.exe",),
    ),
)

EXCLUDED_SHORTCUT_TERMS = (
    "uninstall",
    "readme",
    "release notes",
    "documentation",
    "license",
    "website",
    "update helper",
)


def normalise_app_name(value: str) -> str:
    value = value.casefold().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def discover_installed_applications(force_refresh: bool = False) -> list[InstalledApplication]:
    if force_refresh:
        _cached_applications.cache_clear()
    return list(_cached_applications())


@lru_cache(maxsize=1)
def _cached_applications() -> tuple[InstalledApplication, ...]:
    applications: dict[str, InstalledApplication] = {}
    for app in STATIC_APPLICATIONS:
        _merge_application(applications, app)
    for app in _known_user_applications():
        _merge_application(applications, app)
    for app in _start_menu_applications():
        _merge_application(applications, app)
    for app in _registry_applications():
        _merge_application(applications, app)
    return tuple(sorted(applications.values(), key=lambda app: app.name.casefold()))


def resolve_application(
    requested_name: str,
    applications: list[InstalledApplication] | tuple[InstalledApplication, ...] | None = None,
) -> InstalledApplication | None:
    requested = _clean_requested_name(requested_name)
    if not requested:
        return None

    apps = applications if applications is not None else discover_installed_applications()
    exact: dict[str, InstalledApplication] = {}
    for app in apps:
        for alias in _all_aliases(app):
            exact.setdefault(normalise_app_name(alias), app)
    if requested in exact:
        return exact[requested]

    prefix_matches = {
        app
        for alias, app in exact.items()
        if len(requested) >= 4 and alias.startswith(requested)
    }
    return next(iter(prefix_matches)) if len(prefix_matches) == 1 else None


def application_suggestions(
    requested_name: str,
    applications: list[InstalledApplication] | None = None,
    limit: int = 4,
) -> list[str]:
    requested = _clean_requested_name(requested_name)
    apps = applications if applications is not None else discover_installed_applications()
    tokens = set(requested.split())
    ranked: list[tuple[int, str]] = []
    for app in apps:
        app_tokens = set(normalise_app_name(app.name).split())
        score = len(tokens & app_tokens)
        if score:
            ranked.append((score, app.name))
    ranked.sort(key=lambda item: (-item[0], item[1].casefold()))
    return [name for _, name in ranked[:limit]]


def _known_user_applications() -> list[InstalledApplication]:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    roaming = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    program_files = Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
    program_files_x86 = Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"))
    candidates = (
        ("Spotify", roaming / "Spotify" / "Spotify.exe", ("spotify.exe",)),
        ("Brave", local / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe", ("brave.exe",)),
        ("Brave", program_files / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe", ("brave.exe",)),
        ("Brave", program_files_x86 / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe", ("brave.exe",)),
        ("Visual Studio Code", local / "Programs" / "Microsoft VS Code" / "Code.exe", ("code.exe",)),
        ("Discord", local / "Discord" / "Update.exe", ("discord.exe",)),
        ("Google Chrome", program_files / "Google" / "Chrome" / "Application" / "chrome.exe", ("chrome.exe",)),
        ("Google Chrome", program_files_x86 / "Google" / "Chrome" / "Application" / "chrome.exe", ("chrome.exe",)),
        ("Microsoft Edge", program_files_x86 / "Microsoft" / "Edge" / "Application" / "msedge.exe", ("msedge.exe",)),
    )
    return [
        InstalledApplication(name, str(path), "known_install", process_names=processes)
        for name, path, processes in candidates
        if _path_exists(path)
    ]


def _start_menu_applications() -> list[InstalledApplication]:
    roots = (
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    )
    applications: list[InstalledApplication] = []
    for root in roots:
        if not _path_exists(root):
            continue
        try:
            paths = root.rglob("*")
            paths = list(paths)
        except OSError:
            continue
        for path in paths:
            try:
                is_file = path.is_file()
            except OSError:
                continue
            if not is_file or path.suffix.casefold() not in {".lnk", ".url", ".appref-ms"}:
                continue
            name = _clean_shortcut_name(path.stem)
            normalised = normalise_app_name(name)
            if not normalised or any(term in normalised for term in EXCLUDED_SHORTCUT_TERMS):
                continue
            applications.append(
                InstalledApplication(
                    name=name,
                    launch_target=str(path),
                    source="start_menu",
                    aliases=_aliases_for(name),
                    process_names=_processes_for(name, path),
                )
            )
    return applications


def _registry_applications() -> list[InstalledApplication]:
    if winreg is None:
        return []
    applications: list[InstalledApplication] = []
    roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
    access_modes = (winreg.KEY_READ, winreg.KEY_READ | getattr(winreg, "KEY_WOW64_32KEY", 0))
    key_path = r"Software\Microsoft\Windows\CurrentVersion\App Paths"
    for root in roots:
        for access in access_modes:
            try:
                with winreg.OpenKey(root, key_path, 0, access) as parent:
                    count = winreg.QueryInfoKey(parent)[0]
                    for index in range(count):
                        subkey_name = winreg.EnumKey(parent, index)
                        try:
                            with winreg.OpenKey(parent, subkey_name) as child:
                                target = str(winreg.QueryValue(child, None)).strip('"')
                        except OSError:
                            continue
                        if not target or not _path_exists(Path(target)):
                            continue
                        name = Path(subkey_name).stem
                        applications.append(
                            InstalledApplication(
                                name=name,
                                launch_target=target,
                                source="registry",
                                aliases=_aliases_for(name),
                                process_names=(Path(target).name.casefold(),),
                            )
                        )
            except OSError:
                continue
    return applications


def _merge_application(
    applications: dict[str, InstalledApplication],
    incoming: InstalledApplication,
) -> None:
    key = normalise_app_name(incoming.name)
    existing = applications.get(key)
    if existing is None:
        applications[key] = incoming
        return

    existing_is_link = Path(existing.launch_target).suffix.casefold() in {".lnk", ".url", ".appref-ms"}
    incoming_is_executable = Path(incoming.launch_target).suffix.casefold() == ".exe"
    target_owner = incoming if existing_is_link and incoming_is_executable else existing
    applications[key] = InstalledApplication(
        name=existing.name,
        launch_target=target_owner.launch_target,
        source=target_owner.source,
        aliases=tuple(sorted(set((*existing.aliases, *incoming.aliases)), key=str.casefold)),
        process_names=tuple(
            sorted(set((*existing.process_names, *incoming.process_names)), key=str.casefold)
        ),
    )


def _clean_requested_name(value: str) -> str:
    cleaned = normalise_app_name(value)
    for prefix in ("the ", "my "):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
    for suffix in (" application", " app", " software", " program"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
    return cleaned.strip()


def _clean_shortcut_name(name: str) -> str:
    return re.sub(r"\s*\((?:x64|x86|64-bit|32-bit)\)\s*$", "", name, flags=re.IGNORECASE).strip()


def _aliases_for(name: str) -> tuple[str, ...]:
    normalised = normalise_app_name(name)
    aliases = set(COMMON_ALIASES.get(normalised, ()))
    if normalised.startswith("microsoft "):
        aliases.add(normalised.removeprefix("microsoft "))
    return tuple(sorted(aliases, key=str.casefold))


def _processes_for(name: str, path: Path) -> tuple[str, ...]:
    normalised = normalise_app_name(name)
    processes = set(KNOWN_PROCESSES.get(normalised, ()))
    if path.suffix.casefold() == ".exe":
        processes.add(path.name.casefold())
    return tuple(sorted(processes))


def _all_aliases(app: InstalledApplication) -> tuple[str, ...]:
    aliases = {app.name, *app.aliases}
    normalised = normalise_app_name(app.name)
    aliases.update(COMMON_ALIASES.get(normalised, ()))
    return tuple(aliases)


def _path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False
