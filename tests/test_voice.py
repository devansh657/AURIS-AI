import unittest
import threading
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import auris.voice as voice_module
from auris.speech_text import prepare_speech
from auris.voice import (
    _NeuralWorker,
    _SpeechInputWorker,
    _last_json_object,
    _speech_chunks,
    prime_voice_engine,
    speak,
    voice_status,
)


ROOT = Path(__file__).resolve().parents[1]


class VoiceTests(unittest.TestCase):
    def test_new_reply_cannot_reuse_old_first_audio_latency(self):
        voice_module._LAST_FIRST_AUDIO_MS = 2700
        voice_module._begin_speech(prepare_speech("Ready."))
        self.assertIsNone(voice_module._LAST_FIRST_AUDIO_MS)

    def test_deferred_wake_listener_does_not_hide_priority_capture(self):
        original = voice_module._INPUT_PHASE
        voice_module._INPUT_PHASE = "listening_for_command"
        voice_module._INPUT_PRIORITY_PENDING.set()
        try:
            result = voice_module.listen_for_wake_word(timeout_seconds=5)
            self.assertTrue(result["preempted"])
            self.assertEqual(voice_module._INPUT_PHASE, "listening_for_command")
        finally:
            voice_module._INPUT_PRIORITY_PENDING.clear()
            voice_module._INPUT_PHASE = original

    def test_extracts_last_json_result_from_powershell_output(self):
        payload = _last_json_object('progress\n{"ok":true,"text":"open notepad"}\n')

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["text"], "open notepad")

    def test_voice_status_identifies_single_local_neural_pipeline(self):
        with patch("auris.voice.get_background_voice_state", return_value={"enabled": True}), patch(
            "auris.voice._daemon_status", return_value={"online": True, "pid": 42}
        ), patch("auris.voice.selected_voice_provider", return_value="local_kokoro"), patch(
            "auris.voice._kokoro_assets_available", return_value=True
        ), patch.object(
            __import__("auris.voice", fromlist=["_NEURAL_WORKER"])._NEURAL_WORKER,
            "ready",
            return_value=True,
        ), patch.object(
            __import__("auris.voice", fromlist=["_NEURAL_WORKER"])._NEURAL_WORKER,
            "details",
            return_value={"pid": 77, "engine": "CUDAExecutionProvider"},
        ), patch.object(
            voice_module._SPEECH_INPUT_WORKER,
            "ready",
            return_value=True,
        ), patch.object(
            voice_module._SPEECH_INPUT_WORKER,
            "details",
            return_value={
                "pid": 88,
                "provider": "windows_system_speech_stream",
                "language": "en-GB",
            },
        ):
            status = voice_status()

        self.assertEqual(status["voice"], "AURIS Vale")
        self.assertEqual(status["provider"], "local_kokoro")
        self.assertEqual(status["output"], "Local Kokoro CUDA neural TTS")
        self.assertEqual(status["neural_execution_provider"], "CUDAExecutionProvider")
        self.assertTrue(status["streaming_input"])
        self.assertTrue(status["voice_activity_detection"])
        self.assertTrue(status["speaker_turn_detection"])
        self.assertEqual(status["input_worker_pid"], 88)
        self.assertEqual(status["input_recognizer"], None)
        self.assertEqual(status["input_audio_level"], 0)
        self.assertTrue(status["single_voice_broker"])
        self.assertTrue(status["provider_locked_for_session"])
        self.assertFalse(status["browser_voice_fallback"])
        self.assertTrue(status["spoken_markup_normalisation"])
        self.assertTrue(status["push_to_talk"])
        self.assertTrue(status["wake_word"])
        self.assertFalse(status["continuous_mode"])
        self.assertEqual(status["wake_command_mode"], "silent_two_stage")
        self.assertEqual(status["wake_acknowledgement"], "silent")
        self.assertTrue(status["natural_interruption"])
        self.assertTrue(status["background_enabled"])
        self.assertTrue(status["background_daemon_online"])
        self.assertEqual(status["background_daemon_pid"], 42)

    @patch("auris.voice._execute_speech", return_value={"ok": True, "stopped": False})
    @patch("auris.voice.selected_voice_provider", return_value="local_piper")
    def test_speak_normalises_text_before_the_only_output_engine(self, provider, execute):
        result = speak("**Verified** *result* at [status](https://example.com).", asynchronous=False)

        self.assertTrue(result["ok"])
        plan = execute.call_args.args[0]
        self.assertNotIn("*", plan.text)
        self.assertNotIn("https", plan.text)
        self.assertIn("Verified result", plan.text)
        self.assertEqual(execute.call_args.args[1], "local_piper")

    def test_browser_cannot_introduce_a_second_speech_engine(self):
        browser_source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertNotIn("speechSynthesis", browser_source)
        self.assertNotIn("SpeechSynthesisUtterance", browser_source)
        self.assertIn("input_partial_transcript", browser_source)
        self.assertIn("BARGE-IN LISTENING", browser_source)

    def test_windows_worker_rejects_background_speech_during_wake_and_interrupt(self):
        worker_source = (ROOT / "scripts" / "voice_input_worker.ps1").read_text(encoding="utf-8")
        grammar_source = (ROOT / "scripts" / "voice_grammars.ps1").read_text(encoding="utf-8")
        self.assertIn('"open Notepad"', grammar_source)
        self.assertIn("$builder.AppendDictation()", grammar_source)
        self.assertIn('$keyword.Name = "auris_wake"', grammar_source)
        self.assertIn('$background.Name = "background_speech_$Mode"', grammar_source)
        self.assertIn('$interrupt.Name = "auris_interrupt"', grammar_source)
        self.assertIn('Confidence = 0.62', grammar_source)
        self.assertIn('$grammarName -notin $grammarSet.Expected', worker_source)
        self.assertIn('Test-AurisWakePrefix -Result $recognized', worker_source)
        self.assertIn('wake_acknowledgement = "silent"', worker_source)
        self.assertIn('tentative_text = [string]$recognized.Text', worker_source)

    @patch("auris.voice._execute_speech")
    def test_passive_acknowledgement_never_enters_the_output_engine(self, execute):
        response = speak("Yes, Devansh, I am listening.")
        self.assertTrue(response["suppressed"])
        self.assertFalse(response["queued"])
        execute.assert_not_called()

    @patch("auris.voice._signal_input_cancel", return_value=True)
    @patch("auris.voice._terminate_process")
    def test_priority_input_preserves_warm_recognizer(self, terminate, signal):
        worker = _SpeechInputWorker()
        process = MagicMock()
        process.pid = 42
        worker._process = process
        worker._ready = True
        worker._active_mode = "wake"
        worker._details = {"cancel_event": "test-event"}
        self.assertTrue(worker.preempt_wake())
        signal.assert_called_once_with("test-event", 42)
        terminate.assert_not_called()
        self.assertTrue(worker._ready)

    def test_preempted_result_does_not_restart_input_worker(self):
        worker = _SpeechInputWorker()
        process = MagicMock()
        process.poll.return_value = None
        worker._process = process
        worker._ready = True
        request_id = "11111111-1111-4111-8111-111111111111"
        def response(*_args, **_kwargs):
            worker._generation += 1
            return '{"type":"result","request_id":"' + request_id + '","ok":false,"preempted":true}'
        with patch("auris.voice.uuid4", return_value=request_id), patch("auris.voice._readline_with_timeout", side_effect=response), patch.object(worker, "_stop_locked") as stop:
            with self.assertRaises(voice_module.SpeechInputPreempted):
                worker.listen("wake", 5)
            stop.assert_not_called()
        self.assertTrue(worker._ready)

    @patch("auris.voice._signal_input_cancel", return_value=True)
    @patch("auris.voice._terminate_process")
    def test_priority_cancel_targets_actual_python_child_not_venv_wrapper(self, terminate, signal):
        worker = _SpeechInputWorker()
        worker._process = MagicMock(pid=42)
        worker._active_mode = "wake"
        worker._details = {"pid": 88, "cancel_event": "child-event"}
        self.assertTrue(worker.preempt_wake())
        signal.assert_called_once_with("child-event", 88)
        terminate.assert_not_called()

    def test_local_decoder_phase_event_is_correlated_without_resetting_worker(self):
        worker = _SpeechInputWorker()
        process = MagicMock()
        process.poll.return_value = None
        worker._ready = True
        worker._process = process
        worker._details = {"provider": "local_whisper_stream"}
        request_id = "11111111-1111-4111-8111-111111111111"
        events = [
            '{"type":"phase","phase":"interpreting_speech","request_id":"' + request_id + '"}',
            '{"type":"result","request_id":"' + request_id + '","ok":true,"text":"open Notepad"}',
        ]
        partials = []
        with patch("auris.voice.uuid4", return_value=request_id), patch("auris.voice._readline_with_timeout", side_effect=events):
            result = worker.listen("command", 5, on_partial=partials.append)
        self.assertTrue(result["ok"])
        self.assertEqual(partials[0]["phase"], "interpreting_speech")
        self.assertTrue(worker._ready)

    def test_rejected_noise_phase_can_return_to_listening(self):
        worker = _SpeechInputWorker()
        process = MagicMock()
        process.poll.return_value = None
        worker._ready = True
        worker._process = process
        request_id = "11111111-1111-4111-8111-111111111111"
        events = [
            '{"type":"phase","phase":"listening","request_id":"' + request_id + '"}',
            '{"type":"result","request_id":"' + request_id + '","ok":true,"text":"open Calculator"}',
        ]
        partials = []
        with patch("auris.voice.uuid4", return_value=request_id), patch("auris.voice._readline_with_timeout", side_effect=events):
            result = worker.listen("command", 5, on_partial=partials.append)
        self.assertTrue(result["ok"])
        self.assertEqual(partials[0]["phase"], "listening")

    def test_stalled_stream_diagnostics_survive_worker_restart(self):
        worker = _SpeechInputWorker()
        process = MagicMock()
        process.poll.return_value = None
        worker._ready = True
        worker._process = process
        worker._details = {"provider": "local_whisper_stream"}
        request_id = "11111111-1111-4111-8111-111111111111"
        event = '{"type":"result","request_id":"' + request_id + '","ok":false,"restart_required":true,"error_code":"input_stalled","signal_state":"no_frames"}'
        with patch("auris.voice.uuid4", return_value=request_id), patch("auris.voice._readline_with_timeout", return_value=event):
            result = worker.listen("command", 5)
        self.assertEqual(result["error_code"], "input_stalled")
        self.assertEqual(result["input_provider"], "local_whisper_stream")
        self.assertFalse(worker._ready)

    def test_native_playback_cancellation_cannot_stop_a_newer_reply(self):
        sound = MagicMock()
        sound.SND_FILENAME, sound.SND_ASYNC, sound.SND_NODEFAULT = 0x20000, 1, 2
        prior_owner = voice_module._NATIVE_PLAYBACK_OWNER
        try:
            with patch.dict(sys.modules, {"winsound": sound}):
                first_generation = voice_module._begin_speech(prepare_speech("First."))
                first = voice_module._NativeWavePlayback(Path("first.wav"), 1, first_generation)
                second_generation = voice_module._begin_speech(prepare_speech("Second."))
                second = voice_module._NativeWavePlayback(Path("second.wav"), 1, second_generation)
                first.terminate()
                self.assertEqual(sound.PlaySound.call_count, 2)
                second.terminate()
                sound.PlaySound.assert_called_with(None, 0)
                self.assertEqual(second.wait(timeout=1), 1)
        finally:
            voice_module._NATIVE_PLAYBACK_OWNER = prior_owner

    def test_obsolete_queued_speech_is_discarded_before_synthesis(self):
        worker = _NeuralWorker()
        process = MagicMock()
        process.poll.return_value = None
        worker._ready = True
        worker._process = process
        worker._provider = "local_kokoro"

        result = worker.synthesise(
            prepare_speech("This queued response is obsolete."),
            ROOT / "data" / "voice" / "runtime" / "00000000-0000-0000-0000-000000000000.wav",
            "local_kokoro",
            should_run=lambda: False,
        )

        self.assertEqual(result, {"ok": True, "stopped": True})
        process.stdin.write.assert_not_called()

    def test_worker_status_snapshot_does_not_wait_for_synthesis_lock(self):
        worker = _NeuralWorker()
        process = MagicMock()
        process.poll.return_value = None
        worker._ready = True
        worker._process = process
        worker._details = {"pid": 42, "engine": "CUDAExecutionProvider"}
        worker._lock.acquire()
        try:
            self.assertTrue(worker.ready())
            self.assertEqual(worker.details()["pid"], 42)
        finally:
            worker._lock.release()

    def test_blocking_prime_locks_first_available_startup_provider(self):
        with patch("auris.voice.selected_voice_provider", return_value="local_kokoro"), patch(
            "auris.voice._piper_assets_available", return_value=True
        ), patch.object(
            voice_module._NEURAL_WORKER,
            "ready",
            return_value=False,
        ), patch.object(
            voice_module._NEURAL_WORKER,
            "ensure_started",
            side_effect=[RuntimeError("CUDA unavailable"), {"provider": "local_piper"}],
        ) as start_output, patch.object(
            voice_module._SPEECH_INPUT_WORKER,
            "ready",
            return_value=True,
        ):
            previous_provider = voice_module._SELECTED_PROVIDER
            try:
                prime_voice_engine(blocking=True)
                self.assertEqual(voice_module._SELECTED_PROVIDER, "local_piper")
                self.assertIsNone(voice_module._LAST_ERROR)
            finally:
                voice_module._SELECTED_PROVIDER = previous_provider

        self.assertEqual(
            [call.args[0] for call in start_output.call_args_list],
            ["local_kokoro", "local_piper"],
        )

    def test_streaming_input_worker_correlates_partial_and_final_events(self):
        worker = _SpeechInputWorker()
        process = MagicMock()
        process.poll.return_value = None
        request_id = "11111111-1111-4111-8111-111111111111"
        process.stdout.readline.side_effect = [
            f'{{"type":"audio_level","request_id":"{request_id}","level":18,"peak":18}}\n',
            f'{{"type":"partial","request_id":"{request_id}","text":"open note"}}\n',
            f'{{"type":"result","request_id":"{request_id}","ok":true,"text":"open Notepad","recognition_ms":420,"peak_audio_level":32}}\n',
        ]
        worker._ready = True
        worker._process = process
        partials = []
        levels = []
        with patch("auris.voice.uuid4", return_value=request_id):
            result = worker.listen(
                "command",
                4,
                on_partial=partials.append,
                on_audio_level=levels.append,
            )

        self.assertEqual(result["text"], "open Notepad")
        self.assertEqual(partials[0]["text"], "open note")
        self.assertEqual(levels[0]["level"], 18)
        self.assertEqual(result["peak_audio_level"], 32)
        process.stdin.flush.assert_called_once()

    def test_priority_input_can_preempt_active_wake_listener(self):
        worker = _SpeechInputWorker()
        process = MagicMock()
        process.poll.return_value = None
        worker._process = process
        worker._active_mode = "wake"

        with patch("auris.voice._terminate_process") as terminate:
            preempted = worker.preempt_wake()

        self.assertTrue(preempted)
        self.assertEqual(worker._generation, 1)
        terminate.assert_called_once_with(process)

    def test_intentional_playback_interruption_is_not_a_voice_error(self):
        plan = prepare_speech("AURIS is standing by.")
        generation = voice_module._begin_speech(plan)
        playback = MagicMock()
        playback.poll.return_value = None
        playback.returncode = 1

        def synthesise(_plan, output_path, _provider, **_kwargs):
            output_path.write_bytes(b"0" * 45)
            return {"ok": True, "duration_seconds": 2.0, "synthesis_ms": 100}

        def communicate(**_kwargs):
            voice_module.stop_speaking()
            return "", "cancelled"

        playback.communicate.side_effect = communicate
        with tempfile.TemporaryDirectory() as temporary, patch("auris.voice.VOICE_RUNTIME_DIR", Path(temporary)), patch.object(voice_module._NEURAL_WORKER, "synthesise", side_effect=synthesise), patch(
            "auris.voice._ensure_private_voice_runtime"
        ), patch("auris.voice._start_audio_playback", return_value=playback):
            result = voice_module._execute_speech(plan, "local_kokoro", generation)

        self.assertEqual(result, {"ok": True, "stopped": True})
        self.assertIsNone(voice_module._LAST_ERROR)

    def test_sentence_pipeline_prefetches_while_current_chunk_plays(self):
        text = (
            "AURIS has verified the first stage and is reporting it now with enough detail to form one bounded spoken segment. "
            "The second stage is synthesized concurrently and should be ready before this first segment finishes playing."
        )
        plan = prepare_speech(text)
        self.assertEqual(len(_speech_chunks(plan.text)), 2)
        generation = voice_module._begin_speech(plan)
        prefetched = threading.Event()
        synthesis_calls = 0

        def synthesise(_plan, output_path, _provider, **_kwargs):
            nonlocal synthesis_calls
            synthesis_calls += 1
            output_path.write_bytes(b"0" * 45)
            if synthesis_calls == 2:
                prefetched.set()
            return {"ok": True, "duration_seconds": 1.5, "synthesis_ms": 90}

        first_playback = MagicMock()
        first_playback.returncode = 0
        first_playback.communicate.side_effect = lambda **_kwargs: (
            ("", "") if prefetched.wait(timeout=1) else (_ for _ in ()).throw(AssertionError("Prefetch did not start."))
        )
        second_playback = MagicMock()
        second_playback.returncode = 0
        second_playback.communicate.return_value = ("", "")
        with tempfile.TemporaryDirectory() as temporary, patch("auris.voice.VOICE_RUNTIME_DIR", Path(temporary)), patch.object(voice_module._NEURAL_WORKER, "synthesise", side_effect=synthesise), patch(
            "auris.voice._ensure_private_voice_runtime"
        ), patch("auris.voice._start_audio_playback", side_effect=[first_playback, second_playback]) as popen:
            result = voice_module._execute_speech(plan, "local_kokoro", generation)

        self.assertTrue(result["ok"])
        self.assertEqual(result["stream_chunks"], 2)
        self.assertEqual(synthesis_calls, 2)
        self.assertEqual(popen.call_count, 2)

    def test_interruption_prevents_prefetched_chunk_playback(self):
        plan = prepare_speech(
            "This first spoken segment is intentionally long enough to stand alone before interruption. "
            "This prefetched second segment must never reach playback after the stop request is issued."
        )
        self.assertEqual(len(_speech_chunks(plan.text)), 2)
        generation = voice_module._begin_speech(plan)
        prefetched = threading.Event()

        def synthesise(_plan, output_path, _provider, **_kwargs):
            output_path.write_bytes(b"0" * 45)
            prefetched.set()
            return {"ok": True, "duration_seconds": 1.5, "synthesis_ms": 90}

        playback = MagicMock()
        playback.poll.return_value = None
        playback.returncode = 1

        def communicate(**_kwargs):
            self.assertTrue(prefetched.wait(timeout=1))
            voice_module.stop_speaking()
            return "", "cancelled"

        playback.communicate.side_effect = communicate
        with tempfile.TemporaryDirectory() as temporary, patch("auris.voice.VOICE_RUNTIME_DIR", Path(temporary)), patch.object(voice_module._NEURAL_WORKER, "synthesise", side_effect=synthesise), patch(
            "auris.voice._ensure_private_voice_runtime"
        ), patch("auris.voice._start_audio_playback", return_value=playback) as popen:
            result = voice_module._execute_speech(plan, "local_kokoro", generation)

        self.assertEqual(result, {"ok": True, "stopped": True})
        popen.assert_called_once()

    def test_speech_chunks_are_bounded_without_losing_text(self):
        text = " ".join(["AURIS maintains context, verifies evidence, and reports progress clearly."] * 12)

        chunks = _speech_chunks(text, max_characters=120)

        self.assertGreater(len(chunks), 2)
        self.assertTrue(all(0 < len(chunk) <= 120 for chunk in chunks))
        self.assertEqual(" ".join(chunks), " ".join(text.split()))


if __name__ == "__main__":
    unittest.main()
