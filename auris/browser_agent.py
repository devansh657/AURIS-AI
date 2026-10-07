from __future__ import annotations

import atexit
import hashlib
import json
import queue
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import parse_qsl, quote_plus, urlparse
from uuid import uuid4

from auris.device_agent import DeviceAction


ROOT = Path(__file__).resolve().parents[1]
NODE_EXE = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe"
WORKER_SCRIPT = ROOT / "scripts" / "browser_worker.mjs"
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
SENSITIVE_VALUE_TERMS = (
    "api key", "card number", "credit card", "cvv", "passcode", "password",
    "private key", "secret", "security code", "token",
)
SENSITIVE_URL_KEYS = {"access_token", "api_key", "apikey", "auth", "key", "password", "secret", "token"}
BLOCKED_CONTROL_TERMS = (
    "buy", "purchase", "checkout", "pay", "place order", "transfer", "send",
    "publish", "post", "submit application", "delete", "remove", "password",
    "security", "sign in", "log in", "book", "reserve",
)
SEARCH_PATTERNS = (
    r"^(?:search the web|search online)\s+(?:for\s+)?(.+)$",
    r"^(?:search|google)\s+(?:for\s+)?(.+)$",
    r"^(?:look up)\s+(.+)\s+(?:online|on the web)$",
)
NAVIGATION_PATTERNS = (
    r"^(?:open|visit|go to|navigate to)\s+(?:the\s+)?(?:website\s+)?(https?://\S+|[a-z0-9][a-z0-9.-]+\.[a-z]{2,}(?:/\S*)?)$",
)
INSPECT_PATTERN = re.compile(r"^(?:inspect|read|describe|show)(?: the)? (?:current )?(?:browser )?page$", re.IGNORECASE)
FILL_PATTERN = re.compile(
    r'^fill(?: the)? ["\'](.{1,120})["\'] (?:field )?with ["\'](.{1,500})["\'](?: in the browser)?$',
    re.IGNORECASE,
)
CLICK_PATTERN = re.compile(
    r'^click(?: the)? ["\'](.{1,120})["\'](?: (?:button|link|control))?(?: in the browser)?$',
    re.IGNORECASE,
)
WORKFLOW_PATTERN = re.compile(
    r'^(?:run|execute|start)\s+(?:a\s+)?browser\s+(?:workflow|mission)\s+open\s+"([^"\r\n]{1,500})"\s+(.+)\s+then\s+click\s+"([^"\r\n]{1,120})"(?:\s+(?:button|link|control))?$',
    re.IGNORECASE,
)
WORKFLOW_FILL_PATTERN = re.compile(
    r'then\s+fill\s+"([^"\r\n]{1,120})"\s+with\s+"([^"\r\n]{1,500})"',
    re.IGNORECASE,
)
SPOKEN_WORKFLOW_PATTERN = re.compile(
    r'^(?:run|execute|start)\s+(?:a\s+)?browser\s+(?:workflow|mission)\s+open\s+(\S+)\s+then\s+fill\s+(.{1,120}?)\s+with\s+(.{1,500}?)\s+then\s+click\s+(.{1,140})$',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BrowserStep:
    kind: str
    url: str = ""
    accessible_name: str = ""
    value: str = ""

    def to_dict(self, *, include_value: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "kind": self.kind,
            "url": self.url,
            "accessible_name": self.accessible_name,
        }
        if self.value:
            if include_value:
                data["value"] = self.value
            else:
                data["value_sha256"] = hashlib.sha256(self.value.encode("utf-8")).hexdigest()
                data["value_length"] = len(self.value)
        return data


@dataclass(frozen=True)
class BrowserAction:
    kind: str
    label: str
    url: str = ""
    query: str | None = None
    accessible_name: str = ""
    value: str = ""
    steps: tuple[BrowserStep, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "kind": self.kind,
            "label": self.label,
            "url": self.url,
            "query": self.query,
            "accessible_name": self.accessible_name,
            "steps": [step.to_dict() for step in self.steps],
        }
        if self.value:
            data["value_sha256"] = hashlib.sha256(self.value.encode("utf-8")).hexdigest()
            data["value_length"] = len(self.value)
        return data


class _BrowserWorker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._ready: dict[str, Any] = {}

    def request(self, action: BrowserAction) -> dict[str, Any]:
        with self._lock:
            if not self._process or self._process.poll() is not None:
                self._start_locked()
            process = self._process
            if process is None or process.stdin is None or process.stdout is None:
                raise RuntimeError("The AURIS browser worker is unavailable.")
            request_id = str(uuid4())
            payload: dict[str, Any] = {"operation": action.kind, "request_id": request_id}
            if action.kind == "navigate":
                payload["url"] = action.url
            elif action.kind == "fill":
                payload.update({"accessible_name": action.accessible_name, "value": action.value})
            elif action.kind == "click":
                payload["accessible_name"] = action.accessible_name
            elif action.kind == "workflow":
                payload["steps"] = [step.to_dict(include_value=True) for step in action.steps]
            try:
                process.stdin.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n")
                process.stdin.flush()
                response = json.loads(_readline_with_timeout(
                    process.stdout, timeout_seconds=60 if action.kind == "workflow" else 30
                ))
            except (BrokenPipeError, OSError, TimeoutError, json.JSONDecodeError) as error:
                self._stop_locked()
                raise RuntimeError("The isolated AURIS browser worker failed safely.") from error
            if response.get("request_id") != request_id:
                self._stop_locked()
                raise RuntimeError("The isolated AURIS browser worker returned an invalid response.")
            return response

    def status(self) -> dict[str, Any]:
        with self._lock:
            online = bool(self._process and self._process.poll() is None and self._ready)
            return {"connected": online, **self._ready} if online else {
                "connected": False,
                "provider": "playwright_edge" if _runtime_available() else "not_configured",
            }

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def _start_locked(self) -> None:
        self._stop_locked()
        if not _runtime_available():
            raise RuntimeError("The Playwright Edge browser runtime is not installed.")
        process = subprocess.Popen(
            [str(NODE_EXE), str(WORKER_SCRIPT)], cwd=ROOT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._process = process
        try:
            ready = json.loads(_readline_with_timeout(process.stdout, timeout_seconds=20))
        except (TimeoutError, json.JSONDecodeError, RuntimeError) as error:
            self._stop_locked()
            raise RuntimeError("The Playwright Edge browser worker did not become ready.") from error
        if process.poll() is not None or ready.get("type") != "ready":
            self._stop_locked()
            raise RuntimeError(str(ready.get("error") or "The browser worker exited during startup."))
        self._ready = {**ready, "connected": True}

    def _stop_locked(self) -> None:
        process = self._process
        self._process = None
        self._ready = {}
        if process is None or process.poll() is not None:
            return
        try:
            if process.stdin:
                process.stdin.write('{"operation":"shutdown"}\n')
                process.stdin.flush()
            process.wait(timeout=3)
        except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
            process.kill()


_WORKER = _BrowserWorker()


def is_browser_command(command: str) -> bool:
    return match_browser_command(command) is not None


def is_browser_interaction_intent(command: str) -> bool:
    action = match_browser_command(command)
    return bool(action and action.kind in {"click", "fill", "workflow"})


def contains_sensitive_browser_data(command: str) -> bool:
    action = match_browser_command(command)
    if action is None:
        return False
    return _action_contains_sensitive_data(action)


def match_browser_command(command: str) -> BrowserAction | None:
    text = _normalise(command)
    workflow = _match_browser_workflow(text)
    if workflow is not None:
        return workflow
    if INSPECT_PATTERN.fullmatch(text):
        return BrowserAction("inspect", "Inspect the current browser page")
    fill = FILL_PATTERN.fullmatch(text)
    if fill:
        name, value = (item.strip() for item in fill.groups())
        if name and value:
            return BrowserAction("fill", f"Fill {name}", accessible_name=name, value=value)
    click = CLICK_PATTERN.fullmatch(text)
    if click:
        name = click.group(1).strip()
        if name:
            return BrowserAction("click", f"Click {name}", accessible_name=name)
    for pattern in SEARCH_PATTERNS:
        match = re.fullmatch(pattern, text, flags=re.IGNORECASE)
        if match:
            query = match.group(1).strip(" .")[:500]
            if query:
                return BrowserAction(
                    "navigate", f"Search the web for {query}",
                    f"https://www.google.com/search?q={quote_plus(query)}", query=query,
                )
    for pattern in NAVIGATION_PATTERNS:
        match = re.fullmatch(pattern, text, flags=re.IGNORECASE)
        if match:
            raw_url = match.group(1).strip().rstrip(".")
            url = raw_url if raw_url.startswith(("http://", "https://")) else f"https://{raw_url}"
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                return None
            return BrowserAction("navigate", f"Open {parsed.hostname}", url)
    return None


def browser_approval_details(command: str) -> tuple[str, str]:
    action = match_browser_command(command)
    if action is None:
        return "isolated browser session", "No browser field or control will be changed unless the exact request resolves again after approval."
    if action.kind == "fill":
        digest = hashlib.sha256(action.value.encode("utf-8")).hexdigest()[:16]
        return action.accessible_name, f"Fill the exact visible field once with approved text digest {digest}; the text is not stored in the approval summary."
    if action.kind == "workflow":
        host = urlparse(action.steps[0].url).hostname or "approved website"
        fills = [step for step in action.steps if step.kind == "fill"]
        control = action.steps[-1].accessible_name
        digests = ", ".join(hashlib.sha256(step.value.encode("utf-8")).hexdigest()[:12] for step in fills)
        return (
            host,
            f"Run one exact {len(action.steps)}-step browser mission: navigate, fill {len(fills)} named field(s) using approved text digest(s) {digests}, then invoke the exact visible control {control}. Stop on the first unverified checkpoint.",
        )
    return action.accessible_name, "Invoke the exact visible browser control once and verify a resulting page-state change."


def build_browser_device_action(action: BrowserAction) -> DeviceAction:
    if action.kind == "workflow":
        public_steps = json.dumps([step.to_dict() for step in action.steps], ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        target = f"steps={len(action.steps)};digest={hashlib.sha256(public_steps.encode()).hexdigest()[:32]}"
    else:
        value_digest = hashlib.sha256(action.value.encode("utf-8")).hexdigest()[:32] if action.value else "none"
        target = f"name={action.accessible_name[:100] or urlparse(action.url).hostname or 'current_page'};value={value_digest}"
    return DeviceAction(
        action_id=f"browser_{action.kind}_{hashlib.sha256(target.encode()).hexdigest()[:16]}",
        kind=f"browser_{action.kind}", label=action.label, target=target[:200],
        source="isolated_playwright_edge",
    )


def execute_browser_action(action: BrowserAction) -> dict[str, Any]:
    if action.kind in {"click", "fill", "workflow"} and _action_contains_sensitive_data(action):
        return {
            "ok": False,
            "error": "The browser request contains protected data or a consequential control.",
            "verification": "Confirmed: the isolated browser worker was not invoked.",
            "action": action.to_dict(),
        }
    try:
        response = _WORKER.request(action)
    except RuntimeError as error:
        return {"ok": False, "error": str(error), "verification": "The browser action was not completed.", "action": action.to_dict()}
    page = response.get("page") or {}
    ok = bool(response.get("ok"))
    if action.kind == "navigate":
        message = (
            f"Opened {urlparse(str(page.get('url') or action.url)).hostname} in the isolated AURIS browser."
            if ok else "The isolated browser did not load a successful page response."
        )
        verification = (
            f"Confirmed: Edge loaded HTTP {response.get('http_status')} at {page.get('url')} with title {page.get('title') or 'untitled'}."
            if ok else f"Edge returned HTTP {response.get('http_status')} and the navigation was not treated as complete."
        )
    elif action.kind == "inspect":
        message = f"The current page is {page.get('title') or 'untitled'} with {len(page.get('controls') or [])} visible named controls."
        verification = "Confirmed: title, URL, headings, and visible accessibility controls were read as untrusted web content; no page action executed."
    elif action.kind == "fill":
        message = f"Filled the approved {action.accessible_name} field in the isolated browser." if ok else "The browser field value could not be independently verified."
        verification = f"Confirmed: exact field read-back matched {response.get('observed_length', 0)} approved characters; only its digest is returned." if ok else "The exact field value was not observed after filling."
    elif action.kind == "click":
        message = f"Invoked the approved {action.accessible_name} control and observed a page-state change." if ok else "The control was invoked, but no verifiable page-state change followed."
        verification = "Confirmed: URL, title, status, alert, or body-state digest changed after the exact accessibility control was invoked." if ok else "The click itself was not treated as task completion because no resulting page-state change was observed."
    else:
        completed = int(response.get("completed_steps") or 0)
        message = f"Completed and verified all {completed} steps in the approved browser mission." if ok else f"The browser mission stopped after {completed} verified step(s)."
        verification = (
            "Confirmed: navigation, every exact field read-back, and the final resulting page-state change were independently observed."
            if ok else f"The mission failed closed at step {response.get('failed_step', completed + 1)}; no later step executed."
        )
    evidence = {
        key: response[key]
        for key in ("http_status", "observed_length", "state_changed", "value_sha256", "before", "steps", "completed_steps", "failed_step")
        if key in response
    }
    return {
        "ok": ok, "message": message,
        "error": None if ok else response.get("error") or message,
        "verification": verification, "action": action.to_dict(), "page": page,
        "worker": {"provider": "playwright_edge", "isolated_profile": True},
        **evidence,
    }


def browser_status() -> dict[str, Any]:
    return {**_WORKER.status(), "runtime_available": _runtime_available(), "edge_path": str(EDGE_EXE) if EDGE_EXE.exists() else None}


def _runtime_available() -> bool:
    return NODE_EXE.is_file() and WORKER_SCRIPT.is_file() and EDGE_EXE.is_file() and (ROOT / "node_modules" / "playwright-core").is_dir()


def _command_for_action(action: BrowserAction) -> str:
    if action.kind == "fill":
        return f'fill "{action.accessible_name}" with "{action.value}" in the browser'
    if action.kind == "click":
        return f'click "{action.accessible_name}" in the browser'
    return action.label


def _match_browser_workflow(text: str) -> BrowserAction | None:
    match = WORKFLOW_PATTERN.fullmatch(text)
    if match:
        raw_url, middle, control = (item.strip() for item in match.groups())
        fills = [(name.strip(), value) for name, value in WORKFLOW_FILL_PATTERN.findall(middle)]
        canonical = " ".join(f'then fill "{name}" with "{value}"' for name, value in fills)
        if not 1 <= len(fills) <= 3 or canonical.casefold() != " ".join(middle.split()).casefold():
            return None
        return _workflow_action(raw_url, fills, control)
    spoken = SPOKEN_WORKFLOW_PATTERN.fullmatch(text)
    if spoken:
        raw_url, name, value, control = (item.strip() for item in spoken.groups())
        control = re.sub(r"\s+(?:button|link|control)$", "", control, flags=re.IGNORECASE).strip()
        return _workflow_action(raw_url, [(name, value)], control)
    return None


def _workflow_action(raw_url: str, fills: list[tuple[str, str]], control: str) -> BrowserAction | None:
    url = _browser_url(raw_url)
    if url is None or not control or any(not name or not value for name, value in fills):
        return None
    steps = [BrowserStep("navigate", url=url)]
    steps.extend(BrowserStep("fill", accessible_name=name, value=value) for name, value in fills)
    steps.append(BrowserStep("click", accessible_name=control))
    host = urlparse(url).hostname or "website"
    return BrowserAction("workflow", f"Run verified browser mission on {host}", steps=tuple(steps))


def _browser_url(raw_url: str) -> str | None:
    candidate = raw_url.strip().rstrip(".")
    url = candidate if candidate.casefold().startswith(("http://", "https://")) else f"https://{candidate}"
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} and parsed.hostname else None


def _action_contains_sensitive_data(action: BrowserAction) -> bool:
    checks = action.steps if action.kind == "workflow" else (
        BrowserStep(action.kind, url=action.url, accessible_name=action.accessible_name, value=action.value),
    )
    for step in checks:
        if step.kind == "navigate" and _url_contains_sensitive_data(step.url):
            return True
        if step.kind == "fill" and any(term in step.value.casefold() for term in SENSITIVE_VALUE_TERMS):
            return True
        if step.kind == "click":
            lowered = step.accessible_name.casefold()
            if any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in BLOCKED_CONTROL_TERMS):
                return True
    return False


def _url_contains_sensitive_data(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.username or parsed.password:
        return True
    query_keys = {key.casefold() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    fragment = parsed.fragment.casefold()
    return bool(query_keys & SENSITIVE_URL_KEYS) or any(f"{key}=" in fragment for key in SENSITIVE_URL_KEYS)


def _normalise(command: str) -> str:
    text = command.strip()
    lowered = text.casefold()
    for prefix in ("hey auris, ", "hey auris ", "auris, ", "auris "):
        if lowered.startswith(prefix):
            text = text[len(prefix):]
            break
    return text.strip(" .")


def _readline_with_timeout(stream: TextIO | None, *, timeout_seconds: int) -> str:
    if stream is None:
        raise RuntimeError("The browser worker stream is unavailable.")
    result: queue.Queue[str] = queue.Queue(maxsize=1)
    thread = threading.Thread(target=lambda: result.put(stream.readline()), name="auris-browser-worker-read", daemon=True)
    thread.start()
    try:
        line = result.get(timeout=timeout_seconds)
    except queue.Empty as error:
        raise TimeoutError("The browser worker timed out.") from error
    if not line:
        raise RuntimeError("The browser worker closed its output stream.")
    return line


atexit.register(_WORKER.stop)
