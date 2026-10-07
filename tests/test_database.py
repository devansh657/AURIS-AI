import tempfile
import unittest
from pathlib import Path

from auris.database import (
    append_message,
    create_approval,
    create_memory,
    create_workflow_run,
    decide_approval,
    delete_memory,
    ensure_conversation,
    get_project,
    get_background_voice_state,
    get_control_state,
    get_workflow_run,
    initialize_database,
    list_memories,
    list_messages,
    list_projects,
    list_tasks,
    register_managed_project,
    save_task,
    begin_workflow_attempt,
    set_control_state,
    set_background_voice_state,
    set_project_root,
    update_workflow_checkpoint,
)
from auris.supervisor import create_task_plan


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "auris-test.db"
        initialize_database(self.database_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_seeds_projects_and_persists_tasks(self):
        projects = list_projects(path=self.database_path)
        plan = create_task_plan("AURIS, show system health").to_dict()
        save_task(plan, project_id="auris-one", path=self.database_path)

        self.assertEqual(len(projects), 8)
        self.assertEqual(list_tasks(path=self.database_path)[0]["task_id"], plan["task_id"])

    def test_project_root_registration_is_durable(self):
        configured = set_project_root(
            "career", "C:\\Projects\\Career", path=self.database_path
        )

        self.assertEqual(configured["root_path"], "C:\\Projects\\Career")
        self.assertEqual(
            get_project("career", path=self.database_path)["root_path"],
            "C:\\Projects\\Career",
        )

    def test_managed_project_registration_is_bound_and_idempotent(self):
        boundary = Path(self.temp_dir.name) / "Projects"
        root = boundary / "Demo"
        root.mkdir(parents=True)
        first = register_managed_project(root, "Demo", path=self.database_path, managed_root=boundary)
        second = register_managed_project(root, "Demo", path=self.database_path, managed_root=boundary)
        self.assertEqual(first["project_id"], second["project_id"])
        self.assertEqual(first["root_path"], str(root.resolve()))
        with self.assertRaises(ValueError):
            register_managed_project(Path(self.temp_dir.name), "Outside", path=self.database_path, managed_root=boundary)

    def test_memory_can_be_created_searched_and_deleted(self):
        memory = create_memory(
            "Devansh prefers concise status updates",
            project_id="auris-one",
            path=self.database_path,
        )

        matches = list_memories(query="concise", path=self.database_path)
        self.assertEqual(matches[0]["memory_id"], memory["memory_id"])
        self.assertTrue(delete_memory(memory["memory_id"], path=self.database_path))
        self.assertEqual(list_memories(path=self.database_path), [])

    def test_approval_and_kill_switch_are_durable(self):
        plan = create_task_plan("Send email to my professor").to_dict()
        save_task(plan, path=self.database_path)
        approval = create_approval(
            plan["task_id"],
            plan["objective"],
            "email service",
            "draft and recipient",
            plan["risk_level"],
            True,
            path=self.database_path,
        )
        decided = decide_approval(approval["approval_id"], "rejected", path=self.database_path)
        state = set_control_state(True, "test stop", path=self.database_path)

        self.assertEqual(decided["status"], "rejected")
        self.assertIsNone(
            decide_approval(approval["approval_id"], "rejected", path=self.database_path)
        )
        self.assertTrue(state["stopped"])
        self.assertTrue(get_control_state(path=self.database_path)["stopped"])

    def test_background_voice_preference_is_durable(self):
        self.assertTrue(get_background_voice_state(path=self.database_path)["enabled"])

        state = set_background_voice_state(False, path=self.database_path)

        self.assertFalse(state["enabled"])
        self.assertFalse(get_background_voice_state(path=self.database_path)["enabled"])

    def test_conversation_messages_are_durable(self):
        ensure_conversation(
            "test-conversation",
            project_id="auris-one",
            mode="command",
            path=self.database_path,
        )
        append_message(
            "test-conversation",
            "user",
            "Hello AURIS",
            source="test",
            path=self.database_path,
        )
        append_message(
            "test-conversation",
            "assistant",
            "Online.",
            source="test",
            path=self.database_path,
        )

        messages = list_messages("test-conversation", path=self.database_path)

        self.assertEqual([item["role"] for item in messages], ["user", "assistant"])
        self.assertEqual(messages[0]["content"], "Hello AURIS")

    def test_workflow_attempts_and_checkpoints_are_durable(self):
        plan = create_task_plan("AURIS, show system health").to_dict()
        save_task(plan, path=self.database_path)

        workflow = create_workflow_run(
            plan,
            "AURIS, show system health",
            max_attempts=2,
            path=self.database_path,
        )
        first = begin_workflow_attempt(plan["task_id"], path=self.database_path)
        second = begin_workflow_attempt(plan["task_id"], path=self.database_path)
        exhausted = begin_workflow_attempt(plan["task_id"], path=self.database_path)
        execution = workflow["checkpoints"][1]
        update_workflow_checkpoint(
            plan["task_id"],
            execution["step_id"],
            "completed",
            evidence={"content_stored": False, "item_count": 3},
            increment_attempt=True,
            path=self.database_path,
        )

        persisted = get_workflow_run(plan["task_id"], path=self.database_path)

        self.assertEqual(len(persisted["checkpoints"]), 3)
        self.assertEqual(first["attempts"], 1)
        self.assertEqual(second["attempts"], 2)
        self.assertIsNone(exhausted)
        self.assertEqual(persisted["checkpoints"][1]["evidence"]["item_count"], 3)


if __name__ == "__main__":
    unittest.main()
