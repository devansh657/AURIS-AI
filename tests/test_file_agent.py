import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from auris.file_agent import execute_file_search, match_file_search


class FileAgentTests(unittest.TestCase):
    def test_matches_filename_search_without_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            search = match_file_search("AURIS, find file blueprint", roots=[Path(folder)])

        self.assertEqual(search.query, "blueprint")
        self.assertEqual(search.mode, "filename")
        self.assertEqual(match_file_search("find files named blueprint", roots=[Path(folder)]).mode, "filename")
        self.assertIsNone(match_file_search("find file C:\\Windows\\secret.txt"))

    def test_matches_explicit_content_search_separately_from_filename_search(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            content = match_file_search(
                'AURIS, find phrase "quantum migration" in my files', roots=[root]
            )
            filename = match_file_search("search my files for quantum migration", roots=[root])

        self.assertEqual(content.query, "quantum migration")
        self.assertEqual(content.mode, "content")
        self.assertEqual(filename.mode, "filename")

    def test_search_is_bounded_and_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "auris-blueprint.txt").write_text("unchanged", encoding="ascii")
            (root / "other.txt").write_text("other", encoding="ascii")
            search = match_file_search("search my files for blueprint", roots=[root])
            with patch("auris.file_agent._approved_root", return_value=True):
                result = execute_file_search(search)

            self.assertEqual(len(result["items"]), 1)
            self.assertEqual((root / "auris-blueprint.txt").read_text(encoding="ascii"), "unchanged")
            self.assertEqual(result["inspected_files"], 2)

    def test_overlapping_roots_do_not_duplicate_results(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            nested = root / "nested"
            nested.mkdir()
            (nested / "blueprint.txt").write_text("unchanged", encoding="ascii")
            search = match_file_search("find file blueprint", roots=[root, nested])
            with patch("auris.file_agent._approved_root", return_value=True):
                result = execute_file_search(search)

            self.assertEqual(len(result["items"]), 1)

    def test_onedrive_intent_uses_only_synced_roots(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch("auris.file_agent.onedrive_roots", return_value=(root,)):
                search = match_file_search("find dissertation in my OneDrive")

            self.assertEqual(search.query, "dissertation")
            self.assertEqual(search.roots, (root.resolve(),))

    def test_content_search_is_bounded_and_persists_no_matching_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            matching = root / "notes.md"
            matching.write_text(
                "First line\nQuantum migration needs planning.\nAnother quantum migration item.",
                encoding="utf-8",
            )
            (root / "ignored.exe").write_text("quantum migration", encoding="utf-8")
            search = match_file_search("search file contents for quantum migration", roots=[root])
            with patch("auris.file_agent._approved_root", return_value=True):
                result = execute_file_search(search)

            self.assertEqual(result["mode"], "content")
            self.assertEqual(len(result["items"]), 1)
            self.assertEqual(result["items"][0]["name"], "notes.md")
            self.assertEqual(result["items"][0]["match_count"], 2)
            self.assertEqual(result["items"][0]["first_matching_line"], 2)
            self.assertNotIn("Quantum migration needs planning", str(result))
            self.assertGreater(result["inspected_bytes"], 0)

    def test_content_search_skips_oversized_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "large.txt").write_text("needle", encoding="utf-8")
            search = match_file_search("find text needle in files", roots=[root])
            with (
                patch("auris.file_agent._approved_root", return_value=True),
                patch("auris.file_agent.MAX_CONTENT_FILE_BYTES", 1),
            ):
                result = execute_file_search(search)

            self.assertEqual(result["items"], [])
            self.assertEqual(result["inspected_bytes"], 0)

    def test_slow_earlier_root_cannot_starve_later_root(self):
        from auris.file_agent import _match_file_content

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            slow = root / "Desktop"
            later = root / "Documents"
            slow.mkdir()
            later.mkdir()
            for index in range(20):
                (slow / f"item-{index:02}.txt").write_text("unrelated", encoding="utf-8")
            expected = later / "AURIS-result.txt"
            expected.write_text("fair search target", encoding="utf-8")

            def delayed_match(path, query):
                if path.parent == slow:
                    time.sleep(0.03)
                return _match_file_content(path, query)

            search = match_file_search("search file contents for fair search target", roots=[slow, later])
            with (
                patch("auris.file_agent._approved_root", return_value=True),
                patch("auris.file_agent._match_file_content", side_effect=delayed_match),
            ):
                result = execute_file_search(search, timeout_seconds=0.5)

            self.assertTrue(any(item["path"] == str(expected.resolve()) for item in result["items"]))
            self.assertTrue(result["limited"])


if __name__ == "__main__":
    unittest.main()
