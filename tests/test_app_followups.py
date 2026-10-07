import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from auris.device_agent import contextual_device_command
from auris.runtime import _resolve_app_followup


class AppFollowupTests(unittest.TestCase):
    def setUp(self):
        self.message = {"role": "assistant", "created_at": datetime.now(timezone.utc).isoformat(), "metadata": {"task_id": "task-1"}}
        self.task = {"task_id": "task-1", "project_id": "auris-one", "state": "completed", "result": {
            "device_action": {"ok": True, "action": {"kind": "launch_app", "target": "Notepad"}, "command_fabric": {"signature_verified": True, "nonce_claimed": True}},
        }}

    def resolve(self, command="minimize it", *, private=False):
        with patch("auris.runtime.list_messages", return_value=[self.message]) as messages, patch("auris.runtime.get_task", return_value=self.task):
            result = _resolve_app_followup(command, "my-chat", "auris-one", private=private)
        return result, messages

    def test_recent_signed_app_is_resolved(self):
        result, messages = self.resolve()
        self.assertEqual(result, ("minimize Notepad", "task-1"))
        messages.assert_called_once_with("my-chat", limit=1)
        self.assertEqual(self.resolve("Hey AURIS restore the window")[0], ("restore Notepad", "task-1"))

    def test_explicit_application_does_not_query_history(self):
        result, messages = self.resolve("open Spotify")
        self.assertEqual(result, ("open Spotify", None))
        messages.assert_not_called()

    def test_private_commands_do_not_read_shared_app_context(self):
        result, messages = self.resolve(private=True)
        self.assertEqual(result, ("minimize it", None))
        messages.assert_not_called()

    def test_stale_different_project_or_failed_task_is_not_reused(self):
        self.message["created_at"] = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
        self.assertEqual(self.resolve()[0], ("minimize it", None))
        self.message["created_at"] = datetime.now(timezone.utc).isoformat()
        self.task["project_id"] = "other-project"
        self.assertEqual(self.resolve()[0], ("minimize it", None))
        self.task["project_id"] = "auris-one"
        self.task["state"] = "partially_completed"
        self.assertEqual(self.resolve()[0], ("minimize it", None))

    def test_unverified_app_or_non_app_action_is_not_reused(self):
        outcome = self.task["result"]["device_action"]
        outcome["command_fabric"]["nonce_claimed"] = False
        self.assertEqual(self.resolve()[0], ("minimize it", None))
        outcome["command_fabric"]["nonce_claimed"] = True
        outcome["action"]["kind"] = "create_folder"
        self.assertEqual(self.resolve()[0], ("minimize it", None))

    def test_latest_unfinished_user_turn_blocks_old_context(self):
        self.message["role"] = "user"
        self.assertEqual(self.resolve()[0], ("minimize it", None))

    def test_sensitive_and_ambiguous_followups_are_never_expanded(self):
        for command in ["close it", "delete it", "move it", "minimize it and send my email", "change it"]:
            self.assertEqual(contextual_device_command(command, "Notepad"), command)


if __name__ == "__main__":
    unittest.main()
