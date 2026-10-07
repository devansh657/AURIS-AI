import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from auris.local_ipc import LocalIpcClient, LocalIpcServer, LocalIpcUnavailable


@unittest.skipUnless(os.name == "nt", "Windows named-pipe test")
class LocalIpcTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.token = "ipc_test_" + "A" * 48
        self.token_path = Path(self.temp_dir.name) / "portal.token"
        self.token_path.write_text(self.token, encoding="ascii")
        self.received = []

        def dispatch(operation, payload):
            self.received.append((operation, payload))
            return {"ok": True, "operation": operation, "payload": payload}

        self.server = LocalIpcServer(self.token, dispatch)
        self.server.start()

    def tearDown(self):
        self.server.stop()
        self.temp_dir.cleanup()

    def test_authenticated_json_round_trip(self):
        response = LocalIpcClient(self.token_path).request("status", {"probe": True})

        self.assertTrue(response["ok"])
        self.assertEqual(response["operation"], "status")
        self.assertEqual(self.received, [("status", {"probe": True})])

    def test_wrong_token_cannot_reach_pipe(self):
        wrong_path = Path(self.temp_dir.name) / "wrong.token"
        wrong_path.write_text("ipc_wrong_" + "B" * 48, encoding="ascii")

        with self.assertRaises(LocalIpcUnavailable):
            LocalIpcClient(wrong_path).request("status")

        self.assertEqual(self.received, [])

    def test_shutdown_wake_does_not_wait_for_server_authentication(self):
        server = LocalIpcServer(self.token, lambda _operation, _payload: {})
        listener = server._listener = MagicMock()
        thread = server._thread = MagicMock()
        with patch("auris.local_ipc.Client") as client:
            server.stop()

        client.assert_called_once_with(server.address, family="AF_PIPE", authkey=None)
        client.return_value.close.assert_called_once()
        thread.join.assert_called_once_with(timeout=3)
        listener.close.assert_called_once()
        self.assertTrue(server._stopping.is_set())

    def test_closed_shutdown_wake_is_not_dispatched(self):
        server = LocalIpcServer(self.token, lambda _operation, _payload: self.fail("Shutdown wake dispatched"))
        listener = server._listener = MagicMock()

        def disconnected_wake():
            server._stopping.set()
            raise EOFError("Shutdown wake disconnected before authentication")

        listener.accept.side_effect = disconnected_wake
        server._serve()
        listener.accept.assert_called_once()


if __name__ == "__main__":
    unittest.main()
