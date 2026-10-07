import json
import subprocess
import unittest
from unittest.mock import patch

from auris.ui_automation import (
    build_ui_control_action,
    execute_ui_control_request,
    is_ui_control_intent,
    match_ui_control_command,
    ui_control_refusal,
)
from auris.windows_apps import InstalledApplication


NOTEPAD = InstalledApplication(
    "Notepad",
    "notepad.exe",
    "test",
    process_names=("notepad.exe",),
)


class UiAutomationTests(unittest.TestCase):
    def test_parses_quoted_and_typed_control_requests(self):
        quoted = match_ui_control_command('AURIS, click "File" in Notepad')
        typed = match_ui_control_command("press the Play button in Spotify")

        self.assertEqual(quoted.control_name, "File")
        self.assertEqual(quoted.application_name, "Notepad")
        self.assertEqual(typed.control_name, "Play")
        self.assertEqual(typed.application_name, "Spotify")
        self.assertTrue(is_ui_control_intent('activate "Settings" inside Calculator'))

    def test_blocks_protected_apps_and_consequential_controls(self):
        self.assertIsNone(match_ui_control_command('click "Run" in PowerShell'))
        self.assertIn("does not automate", ui_control_refusal('click "Run" in PowerShell'))
        self.assertIsNone(match_ui_control_command('click "Delete" in Notepad'))
        self.assertIn("consequential", ui_control_refusal('click "Delete" in Notepad'))

    def test_builds_exact_signed_action_without_plain_control_text(self):
        request = match_ui_control_command('click "File" in Notepad')

        action, error = build_ui_control_action(request, [NOTEPAD])

        self.assertIsNone(error)
        self.assertEqual(action.kind, "invoke_control")
        self.assertIn("control_sha256=", action.target)
        self.assertNotIn("File", action.target)
        self.assertEqual(action.process_names, ("notepad.exe",))

    @patch("auris.ui_automation.subprocess.run")
    @patch("auris.ui_automation.resolve_application", return_value=NOTEPAD)
    def test_executor_uses_stdin_and_requires_observation(self, _resolve, run):
        run.return_value = subprocess.CompletedProcess(
            [],
            0,
            json.dumps(
                {
                    "ok": True,
                    "invoked": True,
                    "observed": True,
                    "control_type": "MenuItem",
                    "automation_pattern": "InvokePattern",
                    "observation": "control_region_changed",
                    "memory_only_automation_observation": True,
                }
            ),
            "",
        )

        result = execute_ui_control_request(
            match_ui_control_command('click "File" in Notepad')
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["observed"])
        self.assertTrue(result["memory_only_automation_observation"])
        self.assertFalse(result["temporary_capture_persisted"])
        command = run.call_args.args[0]
        self.assertNotIn("File", command)
        payload = json.loads(run.call_args.kwargs["input"])
        self.assertEqual(payload["control_name"], "File")


if __name__ == "__main__":
    unittest.main()
