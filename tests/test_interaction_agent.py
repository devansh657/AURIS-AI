import unittest
from unittest.mock import patch

from auris.interaction_agent import (
    build_typing_device_action,
    contains_sensitive_typing_data,
    execute_typing_request,
    match_typing_command,
)
from auris.windows_apps import InstalledApplication


class InteractionAgentTests(unittest.TestCase):
    def test_parses_exact_text_and_target(self):
        request = match_typing_command('AURIS, type "Hello Devansh" into Notepad')

        self.assertEqual(request.text, "Hello Devansh")
        self.assertEqual(request.application_name, "Notepad")
        self.assertTrue(contains_sensitive_typing_data('type "my password is 123" into Notepad'))
        self.assertIsNone(match_typing_command('type "my password is 123" into Notepad'))

    @patch("auris.interaction_agent.resolve_application")
    def test_typing_action_binds_text_digest_to_signed_scope(self, resolve):
        resolve.return_value = InstalledApplication(
            "Notepad", "notepad.exe", "test", process_names=("notepad.exe",)
        )
        request = match_typing_command('type "Hello" into Notepad')

        action, error = build_typing_device_action(request)

        self.assertIsNone(error)
        self.assertEqual(action.kind, "type_text")
        self.assertIn("text_sha256=", action.target)
        self.assertNotIn("Hello", action.target)

    @patch("auris.interaction_agent._send_unicode_text", return_value=5)
    @patch("auris.interaction_agent.execute_device_action")
    @patch("auris.interaction_agent.match_device_command")
    @patch("auris.interaction_agent.resolve_application")
    def test_execution_focuses_resolved_app_before_input(self, resolve, match_action, execute, send):
        resolve.return_value = InstalledApplication(
            "Notepad", "notepad.exe", "test", process_names=("notepad.exe",)
        )
        match_action.return_value = object()
        execute.return_value = {"ok": True, "verification": "focused"}

        result = execute_typing_request(match_typing_command('type "Hello" into Notepad'))

        self.assertTrue(result["ok"])
        match_action.assert_called_once_with("focus Notepad")
        send.assert_called_once_with("Hello")


if __name__ == "__main__":
    unittest.main()
