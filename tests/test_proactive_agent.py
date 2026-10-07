import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from auris.database import list_proactive_alerts, list_proactive_watches
from auris.proactive_agent import (
    ProactiveWatchEngine,
    ProactiveWatchValidationError,
    create_watch,
    parse_watch_command,
    watch_dashboard,
)


class ProactiveAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "auris.db"
        self.now = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp_dir.cleanup()

    def predictor(self, **kwargs):
        return {
            "forecasts": [{
                "metric": "deadline_risk",
                "score": self.score,
                "classification": "high" if self.score >= 75 else "low",
                "evidence_ids": ["event-1"],
                "advisory_only": True,
            }]
        }

    def test_voice_grammar_is_bounded(self):
        create = parse_watch_command("AURIS, notify me when deadline risk is above 70 every 15 minutes")
        cancel = parse_watch_command("stop the deadline risk watch")
        listing = parse_watch_command("show my proactive watches")

        self.assertEqual((create.action, create.metric, create.operator), ("create", "deadline_risk", "gte"))
        self.assertEqual(create.interval_seconds, 900)
        self.assertEqual((cancel.action, cancel.metric), ("cancel", "deadline_risk"))
        self.assertEqual(listing.action, "list")
        self.assertIsNone(parse_watch_command("watch bank balance above 10"))
        self.assertIsNone(parse_watch_command("watch deadline risk above 101"))

    def test_watch_persists_and_rejects_unsafe_configuration(self):
        watch = create_watch(
            project_id="auris-one", metric="deadline_risk", operator="gte",
            threshold=70, interval_seconds=300, path=self.path,
        )

        self.assertEqual(list_proactive_watches(path=self.path)[0]["watch_id"], watch["watch_id"])
        with self.assertRaises(ProactiveWatchValidationError):
            create_watch(
                project_id="auris-one", metric="shell_command", operator="gte",
                threshold=1, interval_seconds=300, path=self.path,
            )
        with self.assertRaises(ProactiveWatchValidationError):
            create_watch(
                project_id="auris-one", metric="deadline_risk", operator="gte",
                threshold=70, interval_seconds=1, path=self.path,
            )

    @patch("auris.proactive_agent.record_event")
    def test_alerts_only_on_transition_and_preserve_no_action_boundary(self, _record):
        create_watch(
            project_id="auris-one", metric="deadline_risk", operator="gte",
            threshold=70, interval_seconds=60, cooldown_seconds=300, path=self.path,
        )
        notified = []
        engine = ProactiveWatchEngine(notifier=notified.append, path=self.path, predictor=self.predictor)
        self.score = 80

        first = engine.poll_once(now=self.now)
        duplicate = engine.poll_once(now=self.now + timedelta(seconds=60))
        self.score = 20
        reset = engine.poll_once(now=self.now + timedelta(seconds=120))
        self.score = 90
        cooling = engine.poll_once(now=self.now + timedelta(seconds=180))
        after_cooldown = engine.poll_once(now=self.now + timedelta(seconds=301))

        self.assertEqual(len(first), 1)
        self.assertEqual(duplicate, [])
        self.assertEqual(reset, [])
        self.assertEqual(cooling, [])
        self.assertEqual(len(after_cooldown), 1)
        self.assertEqual(len(notified), 2)
        alerts = list_proactive_alerts(path=self.path)
        self.assertEqual(len(alerts), 2)
        self.assertTrue(all(item["advisory_only"] for item in alerts))
        self.assertTrue(all(item["automatic_action"] is False for item in alerts))

    def test_dashboard_declares_policy_boundary(self):
        dashboard = watch_dashboard(project_id="auris-one", path=self.path)

        self.assertTrue(dashboard["policy"]["advisory_only"])
        self.assertFalse(dashboard["policy"]["automatic_action"])
        self.assertEqual(dashboard["policy"]["trigger"], "inactive_to_active_threshold_transition")

    @patch("auris.proactive_agent.record_event")
    def test_threshold_without_evidence_does_not_alert(self, _record):
        create_watch(
            project_id="auris-one", metric="deadline_risk", operator="gte",
            threshold=0, interval_seconds=60, path=self.path,
        )
        self.score = 0

        def unsupported_predictor(**kwargs):
            result = self.predictor(**kwargs)
            result["forecasts"][0]["evidence_ids"] = []
            return result

        engine = ProactiveWatchEngine(path=self.path, predictor=unsupported_predictor)

        self.assertEqual(engine.poll_once(now=self.now), [])
        self.assertEqual(list_proactive_alerts(path=self.path), [])


if __name__ == "__main__":
    unittest.main()
