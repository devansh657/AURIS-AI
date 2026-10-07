import unittest
from unittest.mock import patch

from auris.voice_turns import VoiceTurnStore
from auris.runtime import CommandContext, process_command
from auris.server import _capture_voice, _perform_local_operation


class VoiceTurnTests(unittest.TestCase):
    def test_weak_capture_is_recorded_without_tentative_audio_or_text(self):
        from auris.voice_turns import VoiceTurnStore
        store = VoiceTurnStore(clock=lambda: 10)
        store.captured({"ok": False, "audio_signal_detected": False, "error_code": "input_too_quiet",
                        "signal_state": "weak_signal", "peak_dbfs": -80, "sampled_frames": 250,
                        "tentative_text": "must not appear"}, mode="wake", started=5)
        turn = store.snapshot()[0]
        self.assertEqual(turn["signal_state"], "weak_signal")
        self.assertEqual(turn["peak_dbfs"], -80)
        self.assertEqual(turn["heard"], "")
        self.assertNotIn("tentative_text", turn)

    def test_ambient_weak_input_does_not_overwrite_wake_rejection_evidence(self):
        from auris.voice_turns import VoiceTurnStore
        store = VoiceTurnStore(clock=lambda: 10)
        for code, detected in [("input_too_quiet", False), ("wake_phrase_missing", True), ("input_too_quiet", False)]:
            store.captured({"ok": False, "audio_signal_detected": detected, "error_code": code}, mode="wake", started=5)
        turns = store.snapshot()
        self.assertEqual(len(turns), 2)
        self.assertEqual({turn["error_code"] for turn in turns}, {"input_too_quiet", "wake_phrase_missing"})

    def setUp(self):
        self.now = 1.0
        self.store = VoiceTurnStore(capacity=3, ttl_seconds=900, clock=lambda: self.now)

    def capture(self, text="open Notepad", **kwargs):
        return self.store.captured({"ok": True, "text": text, "confidence": .82, "confidence_kind": "uncalibrated_decoder_score"}, mode="command", started=0, **kwargs)

    def response(self, *, state="completed", task_type="computer_operation", status="verified"):
        return {"ok": True, "plan": {"task_id": "task-1", "state": state, "task_type": task_type}, "result": {"verification_report": {"status": status}}}

    def test_same_captured_command_can_execute_only_once(self):
        turn = self.capture("Hey AURIS, open Notepad")
        self.assertFalse(self.store.claim(turn, "open Spotify", private=False))
        self.assertTrue(self.store.claim(turn, "open Notepad", private=False))
        self.assertFalse(self.store.claim(turn, "open Notepad", private=False))

    def test_command_binding_preserves_case_punctuation_and_code(self):
        turn = self.capture('Build an app.\nReturn "Hello!"')
        self.assertFalse(self.store.claim(turn, 'Build an app.\nReturn "hello!"', private=False))
        self.assertTrue(self.store.claim(turn, 'Build an app.\nReturn "Hello!"', private=False))

    def test_private_and_sensitive_transcripts_are_hidden(self):
        for text, private in [("open Notepad", True), ("my API key is abc", False), ("call 12345678901", False)]:
            self.capture(text, private=private)
        for turn in self.store.snapshot():
            self.assertIn("hidden", turn["heard"])
            self.assertFalse(turn["audio_stored"])
            self.assertFalse(any(key.startswith("_") for key in turn))

    def test_private_dispatch_redacts_an_ordinary_capture(self):
        turn = self.capture()
        self.store.claim(turn, "open Notepad", private=True)
        self.assertIn("hidden", self.store.snapshot()[0]["heard"])

    def test_rejected_tentative_speech_is_never_stored(self):
        self.store.captured({"ok": False, "tentative_text": "my password is secret", "audio_signal_detected": True}, mode="wake", started=0)
        turn = self.store.snapshot()[0]
        self.assertEqual(turn["heard"], "")
        self.assertEqual(turn["failure_stage"], "recognition")

    def test_silence_preemption_and_interrupts_do_not_evict_commands(self):
        self.capture()
        for _ in range(10):
            self.assertIsNone(self.store.captured({"ok": False}, mode="wake", started=0))
            self.assertIsNone(self.store.captured({"ok": False, "preempted": True}, mode="command", started=0))
            self.assertIsNone(self.store.captured({"ok": True, "phrase": "stop"}, mode="interrupt", started=0))
        self.assertEqual(len(self.store.snapshot()), 1)

    def test_repeated_background_misses_are_aggregated(self):
        self.capture()
        for _ in range(10):
            self.store.captured({"ok": False, "audio_signal_detected": True}, mode="wake", started=0)
        self.assertEqual(len(self.store.snapshot()), 2)
        self.assertEqual(self.store.snapshot()[0]["miss_count"], 10)

    def test_bare_wake_is_not_a_pending_pc_command(self):
        turn = self.store.captured({"ok": True, "recognized_as": "Hey AURIS"}, mode="wake", started=0)
        self.assertEqual(self.store.snapshot()[0]["outcome"], "wake_detected")
        self.assertFalse(self.store.claim(turn, "open Notepad", private=False))
        self.capture()
        self.assertEqual(self.store.snapshot()[0]["source"], "command_capture")

    def test_capacity_expiry_and_snapshot_isolation(self):
        for _ in range(5):
            self.capture()
        self.assertEqual(len(self.store.snapshot()), 3)
        snapshot = self.store.snapshot()
        snapshot[0]["heard"] = "changed"
        self.assertNotEqual(self.store.snapshot()[0]["heard"], "changed")
        self.now = 901
        self.assertEqual(self.store.snapshot(), [])

    def test_generated_reply_is_not_a_verified_pc_action(self):
        turn = self.capture()
        self.store.claim(turn, "open Notepad", private=False)
        self.store.finished(turn, self.response(task_type="general_assistance"))
        self.assertEqual(self.store.snapshot()[0]["outcome"], "reply_generated")
        self.assertEqual(self.store.snapshot()[0]["actions"], [])

    def test_failed_signed_action_identifies_verification_stage(self):
        turn = self.capture()
        self.store.claim(turn, "open Notepad", private=False)
        response = self.response(state="failed", status="failed")
        response["result"]["device_action"] = {"ok": False, "command_fabric": {"signature_verified": True}}
        self.store.finished(turn, response)
        self.assertEqual(self.store.snapshot()[0]["failure_stage"], "verification")

    def test_partial_approval_and_running_do_not_report_success(self):
        for state in ["partially_completed", "awaiting_approval", "running", "failed", "blocked"]:
            turn = self.capture()
            self.store.claim(turn, "open Notepad", private=False)
            self.store.finished(turn, self.response(state=state))
            self.assertEqual(self.store.snapshot()[0]["outcome"], state)

    def test_signed_device_receipt_and_audio_timings(self):
        turn = self.capture()
        self.store.claim(turn, "open Notepad", private=False)
        response = self.response()
        response["result"]["device_action"] = {"ok": True, "action": {"kind": "launch_application"}, "command_fabric": {"signature_verified": True, "nonce_claimed": True}}
        self.now = 1.25
        self.store.finished(turn, response)
        self.store.speech_queued(turn)
        self.now = 1.75
        self.store.audio_started(turn)
        self.store.speech_finished(turn, {"ok": True})
        trace = self.store.snapshot()[0]
        self.assertEqual(trace["command_ms"], 250)
        self.assertEqual(trace["first_audio_ms"], 500)
        self.assertEqual(trace["recognition_to_audio_ms"], 750)
        self.assertEqual(trace["capture_to_audio_ms"], 1750)
        self.assertTrue(trace["actions"][0]["signed"])
        self.assertEqual(trace["speech_state"], "completed")

    def test_speech_failure_does_not_erase_verified_action(self):
        turn = self.capture()
        self.store.claim(turn, "open Notepad", private=False)
        self.store.finished(turn, self.response())
        self.store.speech_queued(turn)
        self.store.speech_finished(turn, {"ok": False, "error": "secret data"})
        trace = self.store.snapshot()[0]
        self.assertEqual(trace["outcome"], "verified")
        self.assertEqual(trace["failure_stage"], "speech_output")
        self.assertNotIn("secret data", str(trace))

    def test_speech_cancelled_has_no_fake_audio_time(self):
        turn = self.capture()
        self.store.claim(turn, "open Notepad", private=False)
        self.store.speech_queued(turn)
        self.store.speech_finished(turn, {"ok": True, "stopped": True})
        trace = self.store.snapshot()[0]
        self.assertEqual(trace["speech_state"], "cancelled")
        self.assertIsNone(trace["first_audio_ms"])

    def test_background_completion_updates_the_original_voice_turn(self):
        turn = self.capture()
        self.store.claim(turn, "open Notepad", private=False)
        self.store.finished(turn, self.response(state="running"))
        response = self.response(state="awaiting_approval")
        self.store.finish_task(response["plan"], response["result"])
        self.store.finished(turn, self.response(state="running"))
        self.assertEqual(self.store.snapshot()[0]["outcome"], "awaiting_approval")

    @patch("auris.runtime._process_command")
    def test_runtime_rejects_mismatch_and_replay_before_execution(self, execute):
        with patch("auris.runtime.VOICE_TURNS", self.store):
            turn = self.capture()
            context = CommandContext(voice_turn_id=turn)
            self.assertFalse(process_command("open Spotify", context)["ok"])
            execute.assert_not_called()
            execute.return_value = self.response()
            self.assertTrue(process_command("open Notepad", context)["ok"])
            self.assertFalse(process_command("open Notepad", context)["ok"])
            execute.assert_called_once()

    @patch("auris.runtime._process_command", side_effect=RuntimeError("secret"))
    def test_runtime_exception_is_traced_without_its_text(self, execute):
        with patch("auris.runtime.VOICE_TURNS", self.store):
            turn = self.capture()
            with self.assertRaises(RuntimeError):
                process_command("open Notepad", CommandContext(voice_turn_id=turn))
        self.assertEqual(self.store.snapshot()[0]["failure_stage"], "execution")

    @patch("auris.server.listen_once", return_value={"ok": True, "text": "open Notepad"})
    def test_capture_and_ipc_context_share_turn_id(self, listen):
        with patch("auris.server.VOICE_TURNS", self.store):
            captured = _capture_voice("command", 9, private=True)
        with patch("auris.server.process_command", return_value={"ok": True}) as process:
            _perform_local_operation("command", {"command": "open Notepad", "voice_turn_id": captured["turn_id"]})
        self.assertEqual(process.call_args.args[1].voice_turn_id, captured["turn_id"])
        self.assertIn("hidden", self.store.snapshot()[0]["heard"])


if __name__ == "__main__":
    unittest.main()
