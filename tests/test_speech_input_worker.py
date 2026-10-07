import math
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from auris.speech_input_worker import FRAME_BYTES, InputSignal, LocalSpeechInput, SpeechTurn, route_transcript


class LocalSpeechInputTests(unittest.TestCase):
    def route(self, text, mode="wake", **scores):
        return route_transcript(text, mode, avg_logprob=scores.get("avg_logprob", -0.2), no_speech_prob=scores.get("no_speech_prob", 0.01))

    def test_wake_and_command_are_canonicalized_without_announcement(self):
        result = self.route("Hey Oris, open Notepad.")
        self.assertTrue(result["ok"])
        self.assertEqual(result["recognized_as"], "AURIS open Notepad.")
        self.assertEqual(result["confidence_kind"], "uncalibrated_decoder_score")

    def test_background_and_similar_names_are_not_wake_phrases(self):
        for text in ["Boris open Notepad", "Iris open Notepad", "I spoke to Auris yesterday", "Notepad is open", "AURISnotepad"]:
            with self.subTest(text=text):
                self.assertFalse(self.route(text)["ok"])

    def test_unclear_speech_never_reaches_command_routing(self):
        for scores in [{"avg_logprob": -1}, {"no_speech_prob": 0.7}, {"avg_logprob": math.nan}, {"no_speech_prob": math.inf}]:
            self.assertFalse(self.route("AURIS open Notepad", **scores)["ok"])

    def test_push_to_talk_does_not_require_wake_word(self):
        self.assertTrue(self.route("Create a folder named Reports", mode="command")["ok"])

    def test_interrupt_requires_exact_allowlisted_phrase(self):
        self.assertEqual(self.route("AURIS stop!", mode="interrupt")["phrase"], "stop")
        for phrase in ["cancel response", "cancel that", "take no further action", "continue", "repeat that", "explain what you're doing"]:
            with self.subTest(phrase=phrase):
                self.assertTrue(self.route(phrase, mode="interrupt")["ok"])
        self.assertFalse(self.route("stop by the store tomorrow", mode="interrupt")["ok"])

    def test_silence_retains_only_bounded_preroll_and_never_completes(self):
        turn = SpeechTurn()
        for _ in range(2000):
            self.assertEqual(turn.feed(bytes(FRAME_BYTES), False), "waiting")
        self.assertEqual(len(turn.preroll), 15)
        self.assertEqual(turn.frames, [])

    def test_clicks_and_brief_noise_do_not_make_a_command(self):
        turn = SpeechTurn(end_silence_frames=3)
        turn.feed(bytes(FRAME_BYTES), True)
        for _ in range(3):
            state = turn.feed(bytes(FRAME_BYTES), False)
        self.assertEqual(state, "waiting")
        self.assertEqual(turn.voiced_frames, 0)

    def test_speech_endpoint_preserves_whole_utterance(self):
        turn = SpeechTurn(end_silence_frames=3)
        for _ in range(6):
            self.assertEqual(turn.feed(bytes(FRAME_BYTES), True), "speaking")
        for _ in range(3):
            state = turn.feed(bytes(FRAME_BYTES), False)
        self.assertEqual(state, "complete")
        self.assertEqual(len(turn.pcm()), 9 * FRAME_BYTES)

    def test_long_utterance_is_rejected_not_silently_truncated(self):
        turn = SpeechTurn()
        for _ in range(1500):
            state = turn.feed(bytes(FRAME_BYTES), True)
        self.assertEqual(state, "too_long")
        with self.assertRaises(ValueError):
            turn.feed(b"bad", True)

    def decoder(self, responses):
        listener = LocalSpeechInput.__new__(LocalSpeechInput)
        listener.np = MagicMock()
        listener.model = MagicMock()
        listener.model.transcribe.side_effect = [(iter([SimpleNamespace(text=text, avg_logprob=-0.2, no_speech_prob=0.01)]), None) for text in responses]
        return listener

    def test_vocabulary_cannot_rewrite_iris_into_a_wake_command(self):
        decoder = self.decoder(["Iris open Notepad.", "Auris open Notepad."])
        self.assertFalse(decoder.decode(bytes(FRAME_BYTES), "wake")["ok"])
        self.assertEqual(decoder.model.transcribe.call_count, 1)
        self.assertIsNone(decoder.model.transcribe.call_args.kwargs["initial_prompt"])

    def test_boris_is_rejected_when_competing_vocabulary_confirms_boris(self):
        decoder = self.decoder(["Boris open Notepad.", "Boris open Notepad."])
        self.assertFalse(decoder.decode(bytes(FRAME_BYTES), "wake")["ok"])
        self.assertEqual(decoder.model.transcribe.call_count, 2)

    def test_phonetic_candidate_requires_independent_name_confirmation(self):
        decoder = self.decoder(["or ease open Notepad.", "Auris open Notepad."])
        self.assertTrue(decoder.decode(bytes(FRAME_BYTES), "wake")["ok"])
        self.assertEqual(decoder.model.transcribe.call_count, 2)

    def test_unconfirmed_phonetic_candidate_is_rejected(self):
        decoder = self.decoder(["or ease open Notepad.", "Boris open Notepad."])
        self.assertFalse(decoder.decode(bytes(FRAME_BYTES), "wake")["ok"])

    def test_captured_web_rtc_turn_does_not_run_a_second_speech_filter(self):
        decoder = self.decoder(["Open Calculator."])
        self.assertTrue(decoder.decode(bytes(FRAME_BYTES), "command", already_segmented=True)["ok"])
        self.assertFalse(decoder.model.transcribe.call_args.kwargs["vad_filter"])

    def test_standalone_audio_still_uses_library_speech_filter(self):
        decoder = self.decoder(["Open Calculator."])
        decoder.decode(bytes(FRAME_BYTES), "command")
        self.assertTrue(decoder.model.transcribe.call_args.kwargs["vad_filter"])

    def test_priority_cancel_does_not_decode_or_store_microphone_audio(self):
        listener = LocalSpeechInput.__new__(LocalSpeechInput)
        listener.cancel = MagicMock()
        listener.cancel.signaled.return_value = True
        listener.capture = threading.Event()
        listener.frames = queue.Queue()
        listener.overflow = threading.Event()
        listener.decode = MagicMock()
        listener.stream = SimpleNamespace(active=True)
        result = listener.listen({"mode": "wake", "timeout_seconds": 5, "request_id": "11111111-1111-4111-8111-111111111111"})
        self.assertTrue(result["preempted"])
        self.assertFalse(listener.capture.is_set())
        listener.cancel.reset.assert_not_called()
        listener.decode.assert_not_called()

    def test_invalid_request_is_rejected_before_opening_capture(self):
        listener = LocalSpeechInput.__new__(LocalSpeechInput)
        with self.assertRaises(ValueError):
            listener.listen({"mode": "command", "request_id": "untrusted"})

    def test_signal_distinguishes_stalled_stream_from_quiet_audio(self):
        signal = InputSignal()
        self.assertEqual(signal.details()["signal_state"], "no_frames")
        for _ in range(6):
            signal.observe(4, True)
        self.assertEqual(signal.details()["signal_state"], "weak_signal")
        self.assertFalse(signal.details()["audio_signal_detected"])
        self.assertLess(signal.details()["peak_dbfs"], -65)

    def test_log_meter_preserves_soft_input_and_is_not_confidence(self):
        signal = InputSignal()
        level, dbfs = signal.observe(100, True)
        self.assertGreater(level, 0)
        self.assertLess(dbfs, 0)
        self.assertEqual(signal.details()["audio_level_kind"], "dbfs_scaled_meter")

    def capture_listener(self):
        listener = LocalSpeechInput.__new__(LocalSpeechInput)
        listener.cancel = MagicMock()
        listener.cancel.signaled.return_value = False
        listener.capture = threading.Event()
        listener.frames = MagicMock()
        listener.frames.empty.return_value = True
        listener.overflow = threading.Event()
        listener.stream = SimpleNamespace(active=True)
        listener.np = MagicMock()
        listener.np.sqrt.return_value = 1000
        listener.vad = MagicMock()
        listener.vad.is_speech.return_value = True
        listener.decode = MagicMock()
        return listener

    def test_rejected_early_noise_does_not_consume_command_window(self):
        listener = self.capture_listener()
        listener.frames.get.return_value = bytes(FRAME_BYTES)
        listener.decode.side_effect = [{"ok": False, "error": "No speech was recognized."}, {"ok": True, "text": "open Calculator"}]
        turn = MagicMock()
        turn.feed.return_value = "complete"
        turn.pcm.return_value = bytes(FRAME_BYTES)
        with patch("auris.speech_input_worker.SpeechTurn", return_value=turn), patch("auris.speech_input_worker.emit"):
            result = listener.listen({"mode": "command", "timeout_seconds": 2, "request_id": "11111111-1111-4111-8111-111111111111"})
        self.assertTrue(result["ok"])
        self.assertEqual(listener.decode.call_count, 2)
        self.assertFalse(listener.capture.is_set())

    def test_no_callbacks_returns_restartable_stall_not_generic_silence(self):
        listener = self.capture_listener()
        listener.frames.get.side_effect = queue.Empty
        tick = iter([i / 10 for i in range(100)])
        with patch("auris.speech_input_worker.time.perf_counter", side_effect=lambda: next(tick)):
            result = listener.listen({"mode": "command", "timeout_seconds": 5, "request_id": "11111111-1111-4111-8111-111111111111"})
        self.assertEqual(result["error_code"], "input_stalled")
        self.assertTrue(result["restart_required"])
        listener.decode.assert_not_called()

    def test_stopped_audio_stream_is_restarted_before_capture(self):
        listener = LocalSpeechInput.__new__(LocalSpeechInput)
        listener.stream = MagicMock(active=False)
        listener.ensure_capture_active()
        listener.stream.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
