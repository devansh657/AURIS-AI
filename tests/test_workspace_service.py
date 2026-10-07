import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auris.database import save_task, update_task_state
from auris.supervisor import create_task_plan
from auris.workspace_service import _engineering_workspace, workspace_snapshot


class WorkspaceServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "auris-workspaces.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("auris.workspace_service.codex_cli_status", return_value={"ready": True})
    @patch("auris.workspace_service.execute_coding_command", return_value={"ok": True})
    def test_new_project_coding_run_belongs_to_generated_project(self, _inspect, _status):
        tasks = [{
            "task_id": "logic-task",
            "task_type": "work_product",
            "project_id": "auris-one",
            "state": "completed",
            "result": {
                "generated_project": {"project_id": "work-budget"},
                "coding_action": {
                    "operation": "apply_codex_workspace_change",
                    "ok": True,
                    "applied_files": ["main.py"],
                },
            },
        }]
        created = _engineering_workspace(tasks, {"project_id": "work-budget", "root_path": "budget"})
        original = _engineering_workspace(tasks, {"project_id": "auris-one", "root_path": "auris"})
        self.assertEqual(created["recent_runs"][0]["task_id"], "logic-task")
        self.assertEqual(created["recent_runs"][0]["proposal_status"], "applied")
        self.assertEqual(original["recent_runs"], [])

    @patch("auris.workspace_service.collect_system_status")
    @patch("auris.workspace_service.productivity_status")
    @patch("auris.workspace_service.execute_coding_command")
    def test_snapshot_uses_real_task_evidence_and_declares_unconnected_inputs(
        self, inspect_repository, productivity, system_status
    ):
        inspect_repository.return_value = {
            "ok": True,
            "root": "workspace",
            "file_count": 10,
            "text_line_count": 200,
            "extensions": {".py": 6, ".js": 4},
            "largest_files": [],
        }
        productivity.return_value = {
            "outlook": {"state": "connected"},
            "onedrive": {"state": "local_sync_connected"},
        }
        system_status.return_value = {"disk": {"free_gb": 100}}
        plan = create_task_plan("AURIS, research workflow recovery").to_dict()
        save_task(plan, project_id="auris-one", path=self.database_path)
        update_task_state(
            plan["task_id"],
            "completed",
            {
                "research_action": {
                    "query": "workflow recovery",
                    "citations_present": True,
                    "sources": [
                        {"source_id": "S1", "title": "Primary", "url": "https://example.com"}
                    ],
                },
                "verification_report": {"status": "verified"},
            },
            path=self.database_path,
        )

        snapshot = workspace_snapshot(path=self.database_path)

        self.assertEqual(snapshot["research"]["metrics"]["sources_processed"], 1)
        self.assertEqual(snapshot["engineering"]["repository"]["file_count"], 10)
        self.assertEqual(snapshot["daily"]["live_weather"], "not_connected")
        self.assertFalse(snapshot["daily"]["mailbox_loaded"])
        self.assertEqual(len(snapshot["projects"]["items"]), 8)


if __name__ == "__main__":
    unittest.main()
