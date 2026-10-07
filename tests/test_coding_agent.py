import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auris.coding_agent import execute_coding_command, match_coding_command


class CodingAgentTests(unittest.TestCase):
    def test_matches_bounded_coding_commands(self):
        self.assertEqual(match_coding_command("AURIS, run the tests"), "run_tests")
        self.assertEqual(
            match_coding_command("AURIS, analyse this project"), "analyze_project"
        )
        self.assertEqual(
            match_coding_command("inspect the AURIS repository"), "analyze_project"
        )
        self.assertEqual(
            match_coding_command("AURIS, fix this failing test"), "repair_test"
        )
        self.assertEqual(
            match_coding_command("Use Codex to implement dark mode in this project"),
            "codex_workspace",
        )
        self.assertEqual(
            match_coding_command("refactor the API client in the selected repository"),
            "codex_workspace",
        )
        self.assertIsNone(match_coding_command("fix all code automatically"))
        self.assertEqual(match_coding_command("Use Codex to improve the test suite in this project"), "codex_workspace")

    @patch("auris.coding_agent.subprocess.run")
    def test_test_runner_uses_fixed_argument_list_and_explicit_trust(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "Ran 43 tests in 1.0s\nOK")

        result = execute_coding_command("run_tests", trusted_execution=True)

        self.assertTrue(result["ok"])
        self.assertEqual(result["test_count"], 43)
        args, kwargs = run.call_args
        self.assertIsInstance(args[0], list)
        self.assertFalse(kwargs["check"])

    @patch("auris.coding_agent.subprocess.run")
    def test_untrusted_project_test_execution_is_refused(self, run):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            result = execute_coding_command("run_tests", root=Path(folder))

        self.assertFalse(result["ok"])
        self.assertIn("trusted execution profile", result["error"])
        run.assert_not_called()

    def test_project_analysis_maps_structure_without_modifying_or_executing(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root = Path(folder)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / ".venv").mkdir()
            source = root / "src" / "main.py"
            source.write_text("def ready():\n    return True\n", encoding="ascii")
            (root / "tests" / "test_main.py").write_text(
                "def test_ready():\n    assert True\n", encoding="ascii"
            )
            (root / "AGENTS.md").write_text("# Project rules\n", encoding="ascii")
            (root / "pyproject.toml").write_text(
                '[project]\nname = "sample"\nversion = "1.0"\n', encoding="ascii"
            )
            (root / "secrets.json").write_text(
                '{"token":"TODO must never enter analysis"}\n', encoding="ascii"
            )
            (root / ".venv" / "generated.py").write_text("ignored = True\n", encoding="ascii")
            before = source.read_bytes()

            result = execute_coding_command(
                "analyze_project", root=root, project_name="Sample"
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["file_count"], 5)
            self.assertEqual(result["tests"]["file_count"], 1)
            self.assertEqual(result["instructions"], ["AGENTS.md"])
            self.assertIn("src", [item["name"] for item in result["components"]])
            self.assertEqual(len(result["snapshot_id"]), 20)
            self.assertTrue(result["read_only"])
            self.assertEqual(result["modified_files"], 0)
            self.assertEqual(result["scan"]["sensitive_text_files_skipped"], 1)
            self.assertTrue(
                any(item["code"] == "SENSITIVE_CONTENT_SKIPPED" for item in result["risks"])
            )
            self.assertEqual(source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
