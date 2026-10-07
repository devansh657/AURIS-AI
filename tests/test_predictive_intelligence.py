from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from auris.predictive_intelligence import build_predictive_intelligence


NOW = datetime(2030, 1, 10, 12, 0, tzinfo=timezone.utc)


def _task(index: int, state: str, *, updated_at: datetime | None = None) -> dict:
    return {
        "task_id": f"task-{index}",
        "project_id": "auris-one",
        "state": state,
        "updated_at": (updated_at or NOW).isoformat(),
        "required_agents": ["research_agent"],
    }


class PredictiveIntelligenceTests(unittest.TestCase):
    def _build(self, tasks, events=None, approvals=None):
        with (
            patch(
                "auris.predictive_intelligence.list_projects",
                return_value=[{"project_id": "auris-one", "name": "AURIS One"}],
            ),
            patch("auris.predictive_intelligence.list_tasks", return_value=tasks),
            patch("auris.predictive_intelligence.list_scheduled_events", return_value=events or []),
            patch("auris.predictive_intelligence.list_approvals", return_value=approvals or []),
        ):
            return build_predictive_intelligence(project_id="auris-one", now=NOW)

    def test_probability_is_withheld_below_empirical_sample_gate(self):
        result = self._build([_task(index, "completed") for index in range(19)])
        forecast = next(
            item for item in result["forecasts"] if item["metric"] == "mission_failure_probability"
        )

        self.assertFalse(forecast["sample_sufficient"])
        self.assertIsNone(forecast["probability"])
        self.assertIsNone(forecast["interval"])

    def test_observed_failure_probability_includes_wilson_uncertainty(self):
        tasks = [_task(index, "failed" if index < 5 else "completed") for index in range(20)]
        result = self._build(tasks)
        forecast = next(
            item for item in result["forecasts"] if item["metric"] == "mission_failure_probability"
        )

        self.assertEqual(forecast["probability"], 0.25)
        self.assertEqual(forecast["score"], 25)
        self.assertLess(forecast["interval"][0], 0.25)
        self.assertGreater(forecast["interval"][1], 0.25)
        self.assertIn("does not establish causation", forecast["uncertainty"])

    def test_operational_risk_scores_are_not_probabilities(self):
        tasks = [
            _task(index, "running", updated_at=NOW - timedelta(days=10))
            for index in range(4)
        ]
        events = [
            {
                "event_id": "overdue-1",
                "project_id": "auris-one",
                "status": "scheduled",
                "due_at": (NOW - timedelta(hours=1)).isoformat(),
            },
            {
                "event_id": "due-1",
                "project_id": "auris-one",
                "status": "scheduled",
                "due_at": (NOW + timedelta(minutes=30)).isoformat(),
            },
        ]
        approvals = [{"approval_id": "approval-1", "task_id": "task-0"}]

        result = self._build(tasks, events, approvals)
        deadline = next(item for item in result["forecasts"] if item["metric"] == "deadline_risk")
        workload = next(item for item in result["forecasts"] if item["metric"] == "workload_pressure")

        self.assertGreater(deadline["score"], 0)
        self.assertGreater(workload["score"], 0)
        self.assertIsNone(deadline["probability"])
        self.assertIn("not a calibrated probability", deadline["uncertainty"])
        self.assertTrue(all(item["advisory_only"] for item in result["forecasts"]))
        self.assertTrue(all(item["provenance"] == "real_durable_state" for item in result["forecasts"]))
        self.assertFalse(result["method"]["automatic_action"])

    @patch("auris.predictive_intelligence.list_projects")
    def test_private_mode_suppresses_forecasts_before_loading_state(self, projects):
        result = build_predictive_intelligence(private=True, now=NOW)

        self.assertEqual(result["forecasts"], [])
        self.assertTrue(result["private_mode"])
        projects.assert_not_called()


if __name__ == "__main__":
    unittest.main()
