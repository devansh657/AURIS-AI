import unittest
from unittest.mock import patch

from auris.model_gateway import ModelReply
from auris.screen_context import analyse_current_screen, is_screen_command


class ScreenContextTests(unittest.TestCase):
    def test_screen_intent_is_explicit(self):
        self.assertTrue(is_screen_command("AURIS, what is on my screen?"))
        self.assertTrue(is_screen_command("describe my screen"))
        self.assertFalse(is_screen_command("describe the project"))

    @patch("auris.screen_context.Path.unlink")
    @patch("auris.screen_context.analyse_image")
    @patch("auris.screen_context.capture_screen")
    def test_analysis_deletes_temporary_capture(self, capture, analyse, unlink):
        capture.return_value = {
            "ok": True,
            "path": "temporary-screen.png",
            "width": 1920,
            "height": 1080,
            "monitors": 1,
        }
        analyse.return_value = ModelReply("AURIS is visible.", "ollama", "gemma3:4b", 20)

        result = analyse_current_screen("describe my screen")

        self.assertTrue(result["ok"])
        self.assertTrue(result["capture"]["deleted_after_analysis"])
        unlink.assert_called_once_with(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
