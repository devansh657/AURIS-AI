import unittest
import time
from unittest.mock import MagicMock, patch

import auris.voice_daemon as voice_daemon
from auris.voice_daemon import _command_after_wake, _monitor_spoken_response, _process_with_heartbeat, _run_cycle


class VoiceDaemonTests(unittest.TestCase):
    def setUp(self):
        voice_daemon._IDLE_GUARD_STATE = None

    @patch("auris.voice_daemon.write_daemon_status")
    def test_processes_voice_command_with_durable_context(self, write_status):
        client = MagicMock()
        def delayed_result(*_args, **_kwargs):
            time.sleep(0.02)
            return {"ok": True, "result": {"message": "Done."}}

        client.command.side_effect = delayed_result

        result = _process_with_heartbeat("open Spotify", client=client, voice_turn_id="turn-1")

        self.assertTrue(result["ok"])
        client.command.assert_called_once_with(
            "open Spotify", private=False, conversation_id="auris-background-voice",
            voice_turn_id="turn-1", allow_failure=True,
        )
        write_status.assert_called()

    def test_extracts_command_from_continuous_wake_utterance(self):
        self.assertEqual(
            _command_after_wake("Hey Oris create a folder called Reports on my Desktop"),
            "create a folder called Reports on my Desktop",
        )
        self.assertEqual(_command_after_wake("AURIS"), "")
        self.assertEqual(_command_after_wake("create a folder"), "")

    @patch("auris.voice_daemon._monitor_spoken_response")
    @patch("auris.voice_daemon._process_with_heartbeat")
    @patch("auris.voice_daemon.record_event")
    @patch("auris.voice_daemon.write_daemon_status")
    @patch("auris.voice_daemon.get_background_voice_state", return_value={"enabled": True})
    @patch("auris.voice_daemon.get_control_state", return_value={"stopped": False})
    def test_continuous_wake_command_executes_without_second_listen(
        self, get_control, get_voice, write_status, record_event, process, monitor
    ):
        client = MagicMock()
        client.listen_for_wake_word.return_value = {
            "ok": True,
            "recognized_as": "AURIS create a folder called Reports on Desktop",
            "confidence": 0.83,
            "language": "en-GB",
        }
        process.return_value = {
            "ok": True,
            "plan": {"task_id": "task-1", "state": "completed"},
            "result": {"message": "Created."},
        }
        client.speak.return_value = {"ok": True}

        _run_cycle(client)

        process.assert_called_once_with("create a folder called Reports on Desktop", client=client, voice_turn_id=None)
        client.listen.assert_not_called()
        client.speak.assert_called_once_with("Created.")
        monitor.assert_called_once_with(client)

    @patch("auris.voice_daemon._monitor_spoken_response")
    @patch("auris.voice_daemon._process_with_heartbeat")
    @patch("auris.voice_daemon.record_event")
    @patch("auris.voice_daemon.write_daemon_status")
    @patch("auris.voice_daemon.get_background_voice_state", return_value={"enabled": True})
    @patch("auris.voice_daemon.get_control_state", return_value={"stopped": False})
    def test_wake_only_opens_silent_command_window(
        self, get_control, get_voice, write_status, record_event, process, monitor
    ):
        client = MagicMock()
        client.listen_for_wake_word.return_value = {
            "ok": True,
            "recognized_as": "AURIS",
            "confidence": 0.91,
            "language": "en-GB",
        }
        client.listen.return_value = {
            "ok": True,
            "text": "open Notepad",
            "confidence": 0.86,
            "language": "en-GB",
        }
        process.return_value = {
            "ok": True,
            "plan": {"task_id": "task-2", "state": "completed"},
            "result": {"message": "Opened Notepad."},
        }
        client.speak.return_value = {"ok": True}

        _run_cycle(client)

        client.listen.assert_called_once_with(timeout_seconds=12)
        process.assert_called_once_with("open Notepad", client=client, voice_turn_id=None)
        client.speak.assert_called_once_with("Opened Notepad.")
        self.assertNotIn("Yes, Devansh", str(client.mock_calls))
        write_status.assert_any_call(
            "listening_for_command", enabled=True, acknowledgement="silent"
        )

    @patch("auris.voice_daemon.record_event")
    @patch("auris.voice_daemon._voice_allowed", return_value=True)
    def test_spoken_response_can_be_interrupted(self, voice_allowed, record_event):
        client = MagicMock()
        client.status.return_value = {"voice": {"speaking": True}}
        client.listen_for_interrupt.return_value = {"ok": True, "phrase": "stop", "confidence": 0.9}
        client.stop_speaking.return_value = {"ok": True, "stopped": True}

        _monitor_spoken_response(client)

        client.stop_speaking.assert_called_once()
        client.listen_for_interrupt.assert_called_once_with(timeout_seconds=2)
        record_event.assert_called_once()

    @patch("auris.voice_daemon.time.sleep")
    @patch("auris.voice_daemon.write_daemon_status")
    @patch("auris.voice_daemon.get_background_voice_state", return_value={"enabled": True})
    @patch("auris.voice_daemon.get_control_state", return_value={"stopped": False})
    def test_idle_cycle_refreshes_heartbeat_without_persisting_audio(
        self, get_control, get_voice, write_status, sleep
    ):
        client = MagicMock()
        client.listen_for_wake_word.return_value = {"ok": False}

        _run_cycle(client)

        write_status.assert_called_once_with(
            "listening_for_wake_word", enabled=True, accepts_continuous_command=True
        )
        client.listen_for_wake_word.assert_called_once_with(timeout_seconds=5)

    @patch("auris.voice_daemon._process_with_heartbeat")
    @patch("auris.voice_daemon.record_event")
    @patch("auris.voice_daemon.write_daemon_status")
    @patch("auris.voice_daemon.get_background_voice_state", return_value={"enabled": True})
    @patch("auris.voice_daemon.get_control_state", return_value={"stopped": False})
    def test_repeated_wake_only_does_not_create_or_speak_a_reply(self, _control, _voice, _status, _audit, process):
        client = MagicMock()
        client.listen_for_wake_word.return_value = {"ok": True, "recognized_as": "AURIS"}
        client.listen.return_value = {"ok": True, "text": "Hey AURIS"}
        _run_cycle(client)
        process.assert_not_called()
        client.speak.assert_not_called()

    @patch("auris.voice_daemon.time.sleep")
    @patch("auris.voice_daemon.write_daemon_status")
    @patch("auris.voice_daemon.get_background_voice_state", return_value={"enabled": False})
    @patch("auris.voice_daemon.get_control_state", return_value={"stopped": False})
    def test_disabled_cycle_stops_broker_only_on_state_transition(
        self, get_control, get_voice, write_status, sleep
    ):
        client = MagicMock()

        _run_cycle(client)
        _run_cycle(client)

        client.stop_speaking.assert_called_once()
        self.assertEqual(write_status.call_count, 2)


if __name__ == "__main__":
    unittest.main()
