from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from auris.audit import record_event
from auris.database import claim_due_events, create_scheduled_event
from auris.proactive_agent import ProactiveWatchEngine
from auris.voice import speak


@dataclass(frozen=True)
class ReminderRequest:
    title: str
    due_at: datetime


def parse_reminder(command: str, *, now: datetime | None = None) -> ReminderRequest | None:
    current = now or datetime.now().astimezone()
    text = _normalise(command)
    relative = re.fullmatch(
        r"remind me in\s+(\d{1,5})\s+(minutes?|hours?)\s+to\s+(.+)", text
    )
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2)
        if amount < 1 or (unit.startswith("hour") and amount > 720) or (unit.startswith("minute") and amount > 43200):
            return None
        delta = timedelta(hours=amount) if unit.startswith("hour") else timedelta(minutes=amount)
        return ReminderRequest(relative.group(3).strip(" .")[:500], current + delta)

    absolute = re.fullmatch(
        r"remind me\s+(tomorrow\s+)?at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+to\s+(.+)",
        text,
    )
    if not absolute:
        return None
    hour = int(absolute.group(2))
    minute = int(absolute.group(3) or 0)
    meridiem = absolute.group(4)
    if minute > 59 or hour > (12 if meridiem else 23) or hour < (1 if meridiem else 0):
        return None
    if meridiem:
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
    due = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if absolute.group(1):
        due += timedelta(days=1)
    elif due <= current:
        due += timedelta(days=1)
    return ReminderRequest(absolute.group(5).strip(" .")[:500], due)


def schedule_reminder(request: ReminderRequest, *, project_id: str | None) -> dict:
    event = create_scheduled_event(
        request.title,
        request.due_at.astimezone(timezone.utc).isoformat(),
        source="voice_or_text_command",
        project_id=project_id,
    )
    record_event("reminder.scheduled", {"event_id": event["event_id"], "due_at": event["due_at"]})
    return event


class EventEngine:
    def __init__(
        self,
        *,
        interval_seconds: float = 5,
        notifier: Callable[[str], None] | None = None,
        proactive_engine: ProactiveWatchEngine | None = None,
    ) -> None:
        self.interval_seconds = interval_seconds
        self.notifier = notifier or _speak_notification
        self.proactive_engine = proactive_engine
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="auris-event-engine", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=max(2, self.interval_seconds + 1))

    def poll_once(self) -> list[dict]:
        events = claim_due_events(datetime.now(timezone.utc).isoformat())
        for event in events:
            self.notifier(event["title"])
            record_event("reminder.delivered", {"event_id": event["event_id"]})
        if self.proactive_engine is not None:
            self.proactive_engine.poll_once()
        return events

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                self.poll_once()
            except Exception as error:
                record_event("event_engine.error", {"error": str(error)[:300]})


def _speak_notification(title: str) -> None:
    speak(f"Reminder, Devansh. {title}", asynchronous=True)


def _normalise(command: str) -> str:
    text = " ".join(command.casefold().strip().replace(",", " ").split())
    for prefix in ("hey auris ", "auris "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.strip(" .")
