import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auris.document_agent import match_document_command, run_document_request
from auris.model_gateway import ModelReply


class DocumentAgentTests(unittest.TestCase):
    def test_matches_supported_document_intent(self):
        request = match_document_command("AURIS, summarize document project-notes.md")

        self.assertEqual(request.operation, "summarize")
        self.assertEqual(request.filename, "project-notes.md")
        self.assertIsNone(match_document_command("read C:\\Windows\\secret.txt"))

    @patch("auris.document_agent.generate_reply")
    @patch("auris.file_agent._approved_root", return_value=True)
    def test_summarises_without_modifying_file(self, _approved, generate):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "project-notes.md"
            original = "AURIS uses verified, policy-checked local operations."
            path.write_text(original, encoding="ascii")
            generate.return_value = ModelReply("AURIS uses verified local operations.", "ollama", "gemma3:4b", 10)

            result = run_document_request(
                match_document_command("summarize project-notes.md"),
                roots=[Path(folder)],
            )

            self.assertTrue(result["ok"])
            self.assertEqual(path.read_text(encoding="ascii"), original)
            self.assertEqual(result["document"]["format"], "MD")


if __name__ == "__main__":
    unittest.main()
