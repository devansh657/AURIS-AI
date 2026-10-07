import tempfile
import unittest
from pathlib import Path

from auris.application_state import (
    application_state_dashboard,
    match_application_state_command,
    record_browser_application_state,
    resolve_browser_continuation,
)
from auris.browser_agent import BrowserAction, BrowserStep
from auris.database import initialize_database, save_task
from auris.supervisor import create_task_plan


class ApplicationStateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "auris-test.db"
        initialize_database(self.database_path)
        self.plan = create_task_plan(
            'run browser mission open "https://example.com/form" '
            'then fill "Reference" with "Private value" then click "Preview"'
        ).to_dict()
        save_task(self.plan, project_id="auris-one", path=self.database_path)
        self.action = BrowserAction(
            "workflow",
            "Browser mission",
            steps=(
                BrowserStep("navigate", url="https://example.com/form"),
                BrowserStep("fill", accessible_name="Reference", value="Private value"),
                BrowserStep("click", accessible_name="Preview"),
            ),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_matches_show_and_continue_commands(self):
        self.assertEqual(match_application_state_command("AURIS, show active browser mission"), "show")
        self.assertEqual(match_application_state_command("continue"), "continue")
        self.assertEqual(match_application_state_command("retry failed browser mission"), "continue")
        self.assertIsNone(match_application_state_command("continue the music"))

    def test_failed_pre_control_checkpoint_is_redacted_and_resumable(self):
        state = record_browser_application_state(
            self.plan["task_id"],
            "auris-one",
            self.action,
            {
                "ok": False,
                "completed_steps": 1,
                "failed_step": 2,
                "page": {"url": "https://example.com/form", "title": "Form"},
            },
            path=self.database_path,
        )

        self.assertEqual(state["status"], "resumable")
        self.assertTrue(state["checkpoint"]["safe_to_retry"])
        self.assertNotIn("Private value", str(state))
        self.assertEqual(state["remaining"][0]["target"], "Reference")
        resolved, source, error = resolve_browser_continuation(
            "auris-one", path=self.database_path
        )
        self.assertIsNone(error)
        self.assertEqual(resolved["state_id"], state["state_id"])
        self.assertEqual(source["task_id"], self.plan["task_id"])

    def test_uncertain_final_control_requires_manual_review(self):
        state = record_browser_application_state(
            self.plan["task_id"],
            "auris-one",
            self.action,
            {"ok": False, "completed_steps": 2, "failed_step": 3, "page": {}},
            path=self.database_path,
        )

        self.assertEqual(state["status"], "manual_review")
        resolved, source, error = resolve_browser_continuation(
            "auris-one", path=self.database_path
        )
        self.assertEqual(resolved["state_id"], state["state_id"])
        self.assertIsNone(source)
        self.assertIn("manual review", error)

    def test_dashboard_is_project_scoped_and_none_never_means_all_projects(self):
        record_browser_application_state(
            self.plan["task_id"],
            "auris-one",
            self.action,
            {"ok": False, "completed_steps": 1, "failed_step": 2, "page": {}},
            path=self.database_path,
        )

        self.assertIsNotNone(application_state_dashboard("auris-one", path=self.database_path)["active"])
        self.assertEqual(application_state_dashboard("career", path=self.database_path)["states"], [])
        self.assertEqual(application_state_dashboard(None, path=self.database_path)["states"], [])


if __name__ == "__main__":
    unittest.main()
