import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from auris.local_client import AurisClientError, AurisLocalClient
from unittest.mock import patch


class LocalPortalHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" and parse_qs(parsed.query).get("access_token") == ["A_" * 32]:
            self.send_response(200)
            self.send_header("Set-Cookie", "auris_session=test-session; Path=/; HttpOnly")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if parsed.path == "/api/session" and "auris_session=test-session" in self.headers.get("Cookie", ""):
            self._json({"ok": True, "session": {"csrf_token": "test-csrf"}})
            return
        if parsed.path == "/api/status" and "auris_session=test-session" in self.headers.get("Cookie", ""):
            self._json({"ok": True, "status": {"control": {"stopped": False}}})
            return
        self._json({"ok": False, "error": "Unauthorized"}, status=401)

    def do_POST(self):
        if self.headers.get("X-AURIS-CSRF") != "test-csrf":
            self._json({"ok": False, "error": "Invalid request token"}, status=403)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if self.path == "/api/command":
            self.server.last_command = payload
            self._json(
                {
                    "ok": True,
                    "plan": {"task_id": "task-1", "state": "completed"},
                    "result": {"message": "Done.", "verification": "Confirmed."},
                }
            )
            return
        self._json({"ok": False, "error": "Unknown endpoint"}, status=404)

    def _json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, _format, *_args):
        return


class LocalClientTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.token_path = Path(self.temp_dir.name) / "portal.token"
        self.token_path.write_text("A_" * 32, encoding="ascii")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), LocalPortalHandler)
        self.server.last_command = None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = AurisLocalClient(
            base_url=f"http://127.0.0.1:{self.server.server_port}",
            token_path=self.token_path,
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def test_authenticates_and_sends_private_command(self):
        result = self.client.command("open Notepad", private=True)

        self.assertEqual(result["result"]["message"], "Done.")
        self.assertEqual(self.server.last_command["command"], "open Notepad")
        self.assertTrue(self.server.last_command["private"])
        self.assertEqual(self.server.last_command["mode"], "private")
        self.assertIsNone(self.server.last_command["project_id"])

    def test_reads_authenticated_status(self):
        status = self.client.status()

        self.assertFalse(status["control"]["stopped"])

    def test_preserves_multiline_coding_brief(self):
        brief = 'Build a Python app.\nLogic:\n    Return "Hello, Ada!" without changing punctuation.'
        self.client.command(brief)
        self.assertEqual(self.server.last_command["command"], brief)

    def test_rejects_non_loopback_endpoint(self):
        with self.assertRaises(ValueError):
            AurisLocalClient(base_url="https://example.com", token_path=self.token_path)

    def test_rejects_invalid_portal_token(self):
        self.token_path.write_text("not-a-token", encoding="ascii")

        with self.assertRaises(AurisClientError):
            self.client.status()

    @patch("auris.local_client.LocalIpcClient.request")
    def test_default_desktop_client_prefers_named_pipe(self, request):
        request.return_value = {
            "ok": True,
            "plan": {"task_id": "pipe-task", "state": "completed"},
            "result": {"message": "Pipe completed."},
        }
        client = AurisLocalClient(token_path=self.token_path)

        result = client.command("show system health", private=True)

        self.assertEqual(result["plan"]["task_id"], "pipe-task")
        request.assert_called_once()
        operation, payload = request.call_args.args
        self.assertEqual(operation, "command")
        self.assertTrue(payload["private"])

    @patch("auris.local_client.LocalIpcClient.request")
    def test_voice_daemon_inputs_use_named_pipe_broker(self, request):
        request.return_value = {
            "ok": True,
            "voice": {"ok": True, "phrase": "stop", "input_provider": "windows_system_speech_stream"},
        }
        client = AurisLocalClient(token_path=self.token_path)

        result = client.listen_for_interrupt(timeout_seconds=2)

        self.assertEqual(result["phrase"], "stop")
        request.assert_called_once_with("voice.interrupt", {"timeout_seconds": 2})

    @patch("auris.local_client.LocalIpcClient.request")
    def test_wake_miss_is_returned_without_transport_failure(self, request):
        request.return_value = {
            "ok": False,
            "voice": {"ok": False, "error": "Wake word not heard.", "audio_stored": False},
        }
        client = AurisLocalClient(token_path=self.token_path)

        result = client.listen_for_wake_word(timeout_seconds=5)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Wake word not heard.")


if __name__ == "__main__":
    unittest.main()
