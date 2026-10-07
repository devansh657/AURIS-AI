import json
import tempfile
import unittest
from pathlib import Path

from auris.desktop_state import companion_status, write_companion_status


class DesktopStateTests(unittest.TestCase):
    def test_companion_heartbeat_reports_online(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "status.json"

            write_companion_status("ready", path=path, hotkeys=["Ctrl+Space"])
            status = companion_status(path=path)

            self.assertTrue(status["online"])
            self.assertEqual(status["state"], "ready")
            self.assertEqual(status["hotkeys"], ["Ctrl+Space"])

    def test_stale_heartbeat_reports_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "status.json"
            path.write_text(
                json.dumps(
                    {
                        "pid": 10,
                        "state": "ready",
                        "updated_at": "2020-01-01T00:00:00+00:00",
                    }
                ),
                encoding="ascii",
            )

            status = companion_status(path=path)

            self.assertFalse(status["online"])


if __name__ == "__main__":
    unittest.main()
