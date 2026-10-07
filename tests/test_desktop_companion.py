import unittest
from unittest.mock import MagicMock

from auris.desktop_companion import DesktopCompanion, hotkey_action


class DesktopCompanionTests(unittest.TestCase):
    def test_global_hotkeys_route_to_bounded_desktop_actions(self):
        self.assertEqual(hotkey_action(1), "toggle_overlay")
        self.assertEqual(hotkey_action(2), "push_to_talk")
        self.assertEqual(hotkey_action(3), "emergency_stop")
        self.assertIsNone(hotkey_action(99))

    def test_voice_overlay_passes_trace_id_without_fake_confidence(self):
        companion = MagicMock()
        DesktopCompanion._voice_finished(companion, {"ok": True, "text": "open Notepad", "turn_id": "turn-1", "confidence": .83, "input_provider": "local_whisper_stream"})
        companion.execute_command.assert_called_once_with(from_voice=True, voice_turn_id="turn-1")
        self.assertNotIn("83%", str(companion._append_transcript.call_args))

    def test_overlay_command_uses_central_trace_and_private_context(self):
        companion = MagicMock()
        companion._busy = False
        companion.control_stopped = False
        companion.command_input.get.return_value = "open Notepad"
        companion.private_mode.get.return_value = True
        DesktopCompanion.execute_command(companion, from_voice=True, voice_turn_id="turn-1")
        operation, callback = companion._run_async.call_args.args
        operation()
        companion.client.command.assert_called_once_with("open Notepad", private=True, voice_turn_id="turn-1", allow_failure=True)
        callback({"ok": True})
        companion._command_finished.assert_called_once_with({"ok": True}, from_voice=True, voice_turn_id="turn-1")

    def test_private_listening_is_marked_private_before_capture(self):
        companion = MagicMock()
        companion._busy = False
        companion.control_stopped = False
        companion.private_mode.get.return_value = True
        companion.client.status.return_value = {"voice": {"background_enabled": False}}
        DesktopCompanion.push_to_talk(companion)
        operation = companion._run_async.call_args.args[0]
        operation()
        companion.client.listen.assert_called_once_with(timeout_seconds=10, private=True)


if __name__ == "__main__":
    unittest.main()
