import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auris.server import ROOT, _perform_local_operation, _resolve_project_root_registration


class ServerLocalOperationTests(unittest.TestCase):
    def test_project_root_registration_is_bounded_and_auris_root_is_fixed(self):
        self.assertEqual(
            _resolve_project_root_registration("auris-one", "C:\\Wrong"), ROOT
        )
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            self.assertEqual(
                _resolve_project_root_registration("career", folder),
                Path(folder).resolve(),
            )
        self.assertIsNone(_resolve_project_root_registration("career", ""))

    @patch("auris.server.process_command")
    def test_private_command_is_routed_with_bounded_context(self, process):
        process.return_value = {"ok": True, "plan": {"state": "completed"}}

        result = _perform_local_operation(
            "command",
            {
                "command": "show system health",
                "project_id": None,
                "mode": "private",
                "private": True,
                "conversation_id": "ipc-test",
            },
        )

        self.assertTrue(result["ok"])
        command, context = process.call_args.args
        self.assertEqual(command, "show system health")
        self.assertTrue(context.private)
        self.assertEqual(context.conversation_id, "ipc-test")

    def test_unknown_operation_is_blocked(self):
        result = _perform_local_operation("shell.execute", {"command": "whoami"})

        self.assertFalse(result["ok"])
        self.assertIn("not allowlisted", result["error"])

    def test_background_voice_requires_boolean(self):
        result = _perform_local_operation("voice.background", {"enabled": "yes"})

        self.assertFalse(result["ok"])
        self.assertIn("boolean", result["error"])

    @patch("auris.server.listen_for_interrupt")
    def test_interruption_listening_is_allowlisted_on_local_broker(self, listen):
        listen.return_value = {
            "ok": True,
            "phrase": "stop",
            "confidence": 0.91,
            "input_provider": "windows_system_speech_stream",
        }

        result = _perform_local_operation("voice.interrupt", {"timeout_seconds": 2})

        self.assertTrue(result["ok"])
        self.assertEqual(result["voice"]["phrase"], "stop")
        listen.assert_called_once_with(timeout_seconds=2)


if __name__ == "__main__":
    unittest.main()
