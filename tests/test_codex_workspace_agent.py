import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auris.codex_workspace_agent import (
    apply_codex_workspace_change,
    codex_cli_status,
    cleanup_expired_codex_proposals,
    discard_codex_workspace_change,
    prepare_codex_workspace_change,
)


ROOT = Path(__file__).resolve().parents[1]


class CodexWorkspaceAgentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.proposals = self.base / "proposals"
        self.worktrees = self.base / "worktrees"
        self.key = self.base / "codex.key"
        self.project.mkdir()
        (self.project / "app.py").write_text(
            "def greeting(name):\n    return f'Hello {name}'\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _successful_executor(args, prompt, cwd, _timeout):
        source = cwd / "app.py"
        source.write_text(
            "def greeting(name):\n    return f'Hello, {name}!'\n",
            encoding="utf-8",
        )
        (cwd / "README.md").write_text(
            "# Greeting\n\nReturns a friendly greeting.\n",
            encoding="utf-8",
        )
        return {
            "ok": True,
            "exit_code": 0,
            "duration_ms": 25,
            "event_count": 4,
            "last_message": "Implemented and checked the greeting change.",
        }

    def _prepare(self, executor=None):
        return prepare_codex_workspace_change(
            "Use Codex to improve the greeting in this project",
            root=self.project,
            project_name="Greeting",
            trusted_execution=True,
            executor=executor or self._successful_executor,
            proposal_root=self.proposals,
            worktree_root=self.worktrees,
            key_path=self.key,
        )

    def test_isolated_codex_result_requires_signed_approval_before_source_change(self):
        original = (self.project / "app.py").read_text(encoding="utf-8")
        captured = {}

        def executor(args, prompt, cwd, timeout):
            captured.update(args=args, prompt=prompt, cwd=cwd, timeout=timeout)
            return self._successful_executor(args, prompt, cwd, timeout)

        outcome = self._prepare(executor)

        self.assertTrue(outcome["ok"], outcome)
        self.assertTrue(outcome["approval_required"])
        self.assertFalse(outcome["source_project_modified"])
        self.assertEqual((self.project / "app.py").read_text(encoding="utf-8"), original)
        self.assertFalse((self.project / "README.md").exists())
        self.assertEqual(outcome["proposal"]["engine"], "codex_cli")
        self.assertEqual(outcome["proposal"]["validation"]["passed_checks"], 2)
        self.assertIn("app.py", outcome["proposal"]["diff"])
        self.assertIn("workspace-write", captured["args"])
        self.assertIn("never", captured["args"])
        self.assertTrue(any("trust_level=\"trusted\"" in argument for argument in captured["args"]))
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", captured["args"])
        self.assertIn("isolated copy", captured["prompt"])
        self.assertFalse(any(self.worktrees.iterdir()))

    def test_approved_proposal_applies_existing_and_new_files_once(self):
        outcome = self._prepare()
        proposal_id = outcome["proposal"]["proposal_id"]

        applied = apply_codex_workspace_change(
            proposal_id,
            root=self.project,
            trusted_execution=True,
            proposal_root=self.proposals,
            key_path=self.key,
        )

        self.assertTrue(applied["ok"], applied)
        self.assertIn("Hello, {name}!", (self.project / "app.py").read_text(encoding="utf-8"))
        self.assertTrue((self.project / "README.md").is_file())
        self.assertEqual(applied["applied_files"], ["README.md", "app.py"])
        replay = apply_codex_workspace_change(
            proposal_id,
            root=self.project,
            trusted_execution=True,
            proposal_root=self.proposals,
            key_path=self.key,
        )
        self.assertFalse(replay["ok"])
        self.assertIn("not ready", replay["error"])

    def test_changed_preimage_and_tampered_signature_are_rejected(self):
        outcome = self._prepare()
        proposal_id = outcome["proposal"]["proposal_id"]
        (self.project / "app.py").write_text("user_change = True\n", encoding="utf-8")

        rejected = apply_codex_workspace_change(
            proposal_id,
            root=self.project,
            trusted_execution=True,
            proposal_root=self.proposals,
            key_path=self.key,
        )

        self.assertFalse(rejected["ok"])
        self.assertIn("changed after proposal", rejected["error"])
        manifest_path = self.proposals / f"{proposal_id}.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["objective"] = "tampered"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        tampered = apply_codex_workspace_change(
            proposal_id,
            root=self.project,
            trusted_execution=True,
            proposal_root=self.proposals,
            key_path=self.key,
        )
        self.assertFalse(tampered["ok"])
        self.assertIn("signature", tampered["error"])

    def test_deletion_credentials_and_untrusted_projects_fail_closed(self):
        def delete_executor(_args, _prompt, cwd, _timeout):
            (cwd / "app.py").unlink()
            return {"ok": True, "exit_code": 0, "duration_ms": 1, "event_count": 1}

        deleted = self._prepare(delete_executor)
        self.assertFalse(deleted["ok"])
        self.assertIn("refuses file deletion", deleted["error"])
        self.assertTrue((self.project / "app.py").is_file())

        def secret_executor(_args, _prompt, cwd, _timeout):
            (cwd / ".env").write_text("API_KEY='abcdefghijklmnop'\n", encoding="utf-8")
            return {"ok": True, "exit_code": 0, "duration_ms": 1, "event_count": 1}

        secret = self._prepare(secret_executor)
        self.assertFalse(secret["ok"])
        self.assertIn("protected or unsupported", secret["error"])
        self.assertFalse((self.project / ".env").exists())

        untrusted = prepare_codex_workspace_change(
            "Use Codex to change this project",
            root=self.project,
            project_name="Untrusted",
            trusted_execution=False,
            executor=self._successful_executor,
            proposal_root=self.proposals,
            worktree_root=self.worktrees,
            key_path=self.key,
        )
        self.assertFalse(untrusted["ok"])
        self.assertIn("AURIS-managed", untrusted["error"])

    def test_failed_final_validation_rolls_back_modifications_and_new_files(self):
        outcome = self._prepare()
        proposal_id = outcome["proposal"]["proposal_id"]
        original = (self.project / "app.py").read_text(encoding="utf-8")

        with patch(
            "auris.codex_workspace_agent._static_validation",
            return_value={"passed": False, "checks": [], "passed_checks": 0, "total_checks": 0},
        ):
            failed = apply_codex_workspace_change(
                proposal_id,
                root=self.project,
                trusted_execution=True,
                proposal_root=self.proposals,
                key_path=self.key,
            )

        self.assertFalse(failed["ok"])
        self.assertTrue(failed["rolled_back"])
        self.assertEqual((self.project / "app.py").read_text(encoding="utf-8"), original)
        self.assertFalse((self.project / "README.md").exists())

    def test_rejected_proposal_is_discarded(self):
        outcome = self._prepare()
        proposal_id = outcome["proposal"]["proposal_id"]

        self.assertTrue(
            discard_codex_workspace_change(
                proposal_id,
                proposal_root=self.proposals,
                key_path=self.key,
            )
        )
        self.assertFalse((self.proposals / f"{proposal_id}.json").exists())

    def test_rollback_restores_exact_crlf_bytes(self):
        original = b"def greeting(name):\r\n    return f'Hello {name}'\r\n"
        (self.project / "app.py").write_bytes(original)
        outcome = self._prepare()
        self.assertTrue(outcome["ok"], outcome)
        with patch("auris.codex_workspace_agent._static_validation", return_value={"passed": False}):
            failed = apply_codex_workspace_change(
                outcome["proposal"]["proposal_id"], root=self.project, trusted_execution=True,
                proposal_root=self.proposals, key_path=self.key,
            )
        self.assertTrue(failed["rolled_back"], failed)
        self.assertEqual((self.project / "app.py").read_bytes(), original)

    def test_snapshot_omits_credentials_and_preserves_dirty_project_changes(self):
        (self.project / ".env").write_text("TOKEN=secret-value", encoding="utf-8")
        (self.project / "local_config.py").write_text("API_KEY='abcdefghijklmnop'", encoding="utf-8")
        (self.project / ".codex").mkdir()
        (self.project / ".codex" / "config.toml").write_text("sandbox_mode='danger-full-access'", encoding="utf-8")
        (self.project / ".git").mkdir()
        captured = {}

        def executor(args, prompt, cwd, timeout):
            captured["files"] = {path.relative_to(cwd).as_posix() for path in cwd.rglob("*") if path.is_file()}
            return self._successful_executor(args, prompt, cwd, timeout)

        outcome = self._prepare(executor)
        self.assertTrue(outcome["ok"], outcome)
        self.assertEqual(captured["files"], {"app.py"})
        self.assertTrue((self.project / ".env").is_file())

    def test_expiry_cleanup_does_not_delete_another_live_snapshot(self):
        def executor(args, prompt, cwd, timeout):
            cleanup_expired_codex_proposals(
                proposal_root=self.proposals, worktree_root=self.worktrees, key_path=self.key,
            )
            self.assertTrue(cwd.is_dir())
            return self._successful_executor(args, prompt, cwd, timeout)
        self.assertTrue(self._prepare(executor)["ok"])

    def test_independent_validation_never_executes_generated_tests(self):
        tests = self.project / "tests"
        tests.mkdir()
        (tests / "test_example.py").write_text("raise RuntimeError('must not execute')\n", encoding="utf-8")
        outcome = self._prepare()
        self.assertTrue(outcome["ok"], outcome)
        self.assertIsNone(outcome["proposal"]["verified_full"])
        self.assertFalse(outcome["proposal"]["validation"]["dynamic_tests_independently_verified"])

    def test_status_reports_the_bounded_harness(self):
        status = codex_cli_status()
        self.assertEqual(status["engine"], "codex_cli")
        self.assertEqual(status["sandbox"], "workspace-write")
        self.assertEqual(status["source_apply_policy"], "signed_diff_approval_once")


if __name__ == "__main__":
    unittest.main()
