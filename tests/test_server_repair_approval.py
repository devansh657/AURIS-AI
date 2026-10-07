import unittest
from unittest.mock import patch

from auris.server import (
    _approval_rejection_result,
    _approval_views,
    _bounded_approval_scope,
)


class ServerRepairApprovalTests(unittest.TestCase):
    @patch("auris.server.get_task")
    @patch("auris.server.get_approval")
    def test_repair_approval_scope_is_forced_to_once(self, get_approval, get_task):
        get_approval.return_value = {"task_id": "task"}
        get_task.return_value = {
            "result": {
                "coding_action": {
                    "proposal": {"proposal_id": "signed-proposal"}
                }
            }
        }

        self.assertEqual(_bounded_approval_scope("approval", "project"), "once")

    @patch("auris.server.get_task")
    @patch("auris.server.list_approvals")
    def test_approval_view_exposes_public_diff_evidence(self, list_approvals, get_task):
        list_approvals.return_value = [{"approval_id": "approval", "task_id": "task"}]
        proposal = {
            "proposal_id": "signed-proposal",
            "diff": "--- a/app.py\n+++ b/app.py",
            "files": [{"path": "app.py"}],
        }
        get_task.return_value = {
            "result": {"coding_action": {"proposal": proposal}}
        }

        views = _approval_views("pending")

        self.assertEqual(views[0]["repair_proposal"], proposal)
        self.assertNotIn("new_content", str(views))

    def test_rejection_preserves_public_evidence_and_marks_source_unchanged(self):
        task = {
            "result": {
                "coding_action": {
                    "operation": "prepare_repair",
                    "proposal": {"proposal_id": "signed-proposal", "status": "ready"},
                }
            }
        }

        result = _approval_rejection_result(task, True)

        self.assertEqual(result["coding_action"]["proposal"]["status"], "rejected")
        self.assertFalse(result["coding_action"]["source_project_modified"])
        self.assertIn("discarded", result["verification"])


if __name__ == "__main__":
    unittest.main()
