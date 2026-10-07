import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auris.database import get_task, get_workflow_run, save_task, update_workflow_state
from auris.runtime import recover_incomplete_workflows
from auris.schemas import TaskState
from auris.supervisor import create_task_plan
from auris.workflow_engine import execute_workflow, prepare_workflow


class WorkflowEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "auris-workflow-test.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("auris.workflow_engine.record_event")
    def test_verified_repair_proposal_pauses_then_uses_second_attempt_for_apply(self, _record):
        plan = create_task_plan("AURIS, fix this failing test").to_dict()
        save_task(plan, path=self.database_path)
        prepared = prepare_workflow(
            plan, "AURIS, fix this failing test", path=self.database_path
        )

        proposal_result = {
            "message": "Verified proposal ready.",
            "verification": "Isolated targeted and complete tests passed.",
            "coding_action": {
                "operation": "prepare_repair",
                "source_project_modified": False,
                "proposal": {"proposal_id": "proposal"},
            },
        }
        result, state = execute_workflow(
            plan,
            lambda: (proposal_result, TaskState.AWAITING_APPROVAL),
            path=self.database_path,
        )
        waiting = get_workflow_run(plan["task_id"], path=self.database_path)

        self.assertEqual(state, TaskState.AWAITING_APPROVAL)
        self.assertNotIn("verification_report", result)
        self.assertEqual(waiting["attempts"], 1)
        self.assertEqual(waiting["max_attempts"], 2)
        self.assertEqual(waiting["state"], TaskState.AWAITING_APPROVAL.value)
        self.assertEqual(waiting["checkpoints"][1]["state"], "awaiting_approval")
        self.assertEqual(get_task(plan["task_id"], path=self.database_path)["state"], "awaiting_approval")

        applied_result = {
            "message": "Applied.",
            "verification": "Targeted and complete post-apply tests passed.",
            "coding_action": {"operation": "apply_repair", "ok": True},
        }
        result, state = execute_workflow(
            plan,
            lambda: (applied_result, TaskState.COMPLETED),
            path=self.database_path,
        )
        completed = get_workflow_run(plan["task_id"], path=self.database_path)

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(completed["attempts"], 2)
        self.assertEqual(completed["state"], TaskState.COMPLETED.value)
        self.assertEqual(result["verification_report"]["status"], "verified")

    @patch("auris.workflow_engine.record_event")
    def test_codex_diff_can_use_second_workflow_attempt_after_approval(self, _record):
        command = "Use Codex to implement a status endpoint in this project"
        plan = create_task_plan(command).to_dict()
        save_task(plan, path=self.database_path)
        workflow = prepare_workflow(plan, command, path=self.database_path)
        self.assertEqual(workflow["max_attempts"], 2)
        execute_workflow(plan, lambda: ({"message": "Diff ready"}, TaskState.AWAITING_APPROVAL), path=self.database_path)
        result, state = execute_workflow(
            plan, lambda: ({"message": "Applied", "verification": "Confirmed: exact diff and hashes passed."}, TaskState.COMPLETED),
            path=self.database_path,
        )
        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(get_workflow_run(plan["task_id"], path=self.database_path)["attempts"], 2)

    @patch("auris.workflow_engine.record_event")
    def test_read_only_failure_retries_and_records_evidence_without_content(self, _record):
        plan = create_task_plan("AURIS, show system health").to_dict()
        save_task(plan, path=self.database_path)
        prepare_workflow(plan, "AURIS, show system health", path=self.database_path)
        calls = 0

        def executor():
            nonlocal calls
            calls += 1
            if calls == 1:
                return (
                    {
                        "message": "Temporary worker failure",
                        "verification": "No result verified.",
                        "retryable": True,
                    },
                    TaskState.FAILED,
                )
            return (
                {
                    "message": "Healthy.",
                    "verification": "Confirmed: device status was collected.",
                    "system_action": {"items": [{"secret": "not persisted"}]},
                },
                TaskState.COMPLETED,
            )

        result, state = execute_workflow(plan, executor, path=self.database_path)
        workflow = get_workflow_run(plan["task_id"], path=self.database_path)
        execution = workflow["checkpoints"][1]

        self.assertEqual(calls, 2)
        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(workflow["attempts"], 2)
        self.assertEqual(len(execution["evidence"]["attempt_history"]), 2)
        self.assertNotIn("secret", str(execution["evidence"]))
        self.assertEqual(result["verification_report"]["status"], "verified")
        self.assertEqual(get_task(plan["task_id"], path=self.database_path)["state"], "completed")

    @patch("auris.runtime.record_event")
    @patch("auris.runtime._execute_supported")
    def test_restart_does_not_replay_sensitive_workflow(self, execute, _record):
        plan = create_task_plan(
            "send email to person@example.com subject Update saying Body"
        ).to_dict()
        save_task(plan, path=self.database_path)
        prepare_workflow(plan, plan["objective"], path=self.database_path)
        update_workflow_state(plan["task_id"], "running", path=self.database_path)

        summary = recover_incomplete_workflows(path=self.database_path)
        task = get_task(plan["task_id"], path=self.database_path)

        execute.assert_not_called()
        self.assertEqual(summary, {"recovered": 0, "interrupted": 1})
        self.assertEqual(task["state"], TaskState.INTERRUPTED.value)
        self.assertIn("no sensitive or write operation was replayed", task["result"]["verification"])

    @patch("auris.workflow_engine.record_event")
    @patch("auris.runtime.record_event")
    @patch("auris.runtime._execute_supported")
    def test_restart_recovers_read_only_workflow_once(self, execute, _runtime_record, _workflow_record):
        plan = create_task_plan("AURIS, show system health").to_dict()
        save_task(plan, path=self.database_path)
        prepare_workflow(plan, "AURIS, show system health", path=self.database_path)
        update_workflow_state(plan["task_id"], "running", path=self.database_path)
        execute.return_value = (
            {
                "message": "Healthy.",
                "verification": "Confirmed: device status was collected.",
            },
            TaskState.COMPLETED,
        )

        summary = recover_incomplete_workflows(path=self.database_path)
        workflow = get_workflow_run(plan["task_id"], path=self.database_path)

        self.assertEqual(summary, {"recovered": 1, "interrupted": 0})
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(workflow["recovery_count"], 1)
        self.assertEqual(workflow["state"], TaskState.COMPLETED.value)


if __name__ == "__main__":
    unittest.main()
