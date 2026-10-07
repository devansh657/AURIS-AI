from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from auris.storage import read_jsonl


class JsonlStorageTests(unittest.TestCase):
    def test_reads_latest_valid_rows_in_chronological_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text(
                "".join(json.dumps({"index": index}) + "\n" for index in range(8)),
                encoding="utf-8",
            )

            self.assertEqual(
                read_jsonl(path, limit=3),
                [{"index": 5}, {"index": 6}, {"index": 7}],
            )

    def test_skips_malformed_and_non_object_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_bytes(
                b'{"index":1}\n'
                b"not-json\n"
                b"[1,2,3]\n"
                b'{"index":2}\n'
                b'{"partial":'
            )

            self.assertEqual(
                read_jsonl(path, limit=5),
                [{"index": 1}, {"index": 2}],
            )

    def test_non_positive_limit_returns_no_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text('{"index":1}\n', encoding="utf-8")

            self.assertEqual(read_jsonl(path, limit=0), [])


if __name__ == "__main__":
    unittest.main()
