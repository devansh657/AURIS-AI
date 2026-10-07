import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from auris.database import (
    cancel_scheduled_event,
    claim_due_events,
    create_scheduled_event,
)
from auris.event_engine import EventEngine, parse_reminder


class EventEngineTests(unittest.TestCase):
    def test_parses_relative_and_absolute_reminders(self):
        now = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
        relative = parse_reminder("AURIS, remind me in 10 minutes to stretch", now=now)
        absolute = parse_reminder("remind me tomorrow at 9:30 am to review the brief", now=now)

        self.assertEqual(relative.due_at, now + timedelta(minutes=10))
        self.assertEqual(relative.title, "stretch")
        self.assertEqual(absolute.due_at, datetime(2026, 8, 6, 9, 30, tzinfo=timezone.utc))

    def test_due_event_is_claimed_once_and_can_be_cancelled(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "auris.db"
            due = create_scheduled_event("Due now", "2026-08-05T10:00:00+00:00", path=path)
            future = create_scheduled_event("Later", "2026-08-06T10:00:00+00:00", path=path)

            first = claim_due_events("2026-08-05T11:00:00+00:00", path=path)
            second = claim_due_events("2026-08-05T11:00:00+00:00", path=path)
            cancelled = cancel_scheduled_event(future["event_id"], path=path)

            self.assertEqual([item["event_id"] for item in first], [due["event_id"]])
            self.assertEqual(second, [])
            self.assertEqual(cancelled["status"], "cancelled")

    @patch("auris.event_engine.record_event")
    @patch("auris.event_engine.claim_due_events")
    def test_poll_notifies_each_claimed_event(self, claim, record_event):
        claim.return_value = [{"event_id": "event-1", "title": "Stand up"}]
        notified = []
        engine = EventEngine(notifier=notified.append)

        events = engine.poll_once()

        self.assertEqual(len(events), 1)
        self.assertEqual(notified, ["Stand up"])
        record_event.assert_called_once_with("reminder.delivered", {"event_id": "event-1"})


if __name__ == "__main__":
    unittest.main()
