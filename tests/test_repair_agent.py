import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from auris.repair_agent import (
    _repair_key,
    _sign_manifest,
    apply_test_repair,
    cleanup_expired_test_repairs,
    discard_test_repair,
    prepare_test_repair,
)


ROOT = Path(__file__).resolve().parents[1]
BROKEN_SOURCE = "def add(left, right):\n    return left - right\n"
FIXED_SOURCE = "def add(left, right):\n    return left + right\n"


class RepairAgentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.proposals = self.base / "proposals"
        self.worktrees = self.base / "worktrees"
        self.key = self.base / "repair.key"
        (self.project / "tests").mkdir(parents=True)
        (self.project / "app.py").write_text(BROKEN_SOURCE, encoding="utf-8")
        (self.project / ".gradle-dist").mkdir()
        (self.project / ".gradle-dist" / "generated.bin").write_bytes(b"generated")
        (self.project / ".tmp-runtime.zip").write_bytes(b"generated archive")
        (self.project / "tests" / "test_app.py").write_text(
            "import unittest\n"
            "from app import add\n\n"
            "class CalculatorTests(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def _fixed_response(self, _prompt):
        return json.dumps(
            {
                "diagnosis": "app.add subtracts its second operand although the failing contract requires addition.",
                "changes": [{"path": "app.py", "new_content": FIXED_SOURCE}],
            }
        )

    def _prepare(self, responder=None):
        return prepare_test_repair(
            "AURIS, fix this failing test",
            root=self.project,
            project_name="Fixture",
            trusted_execution=True,
            responder=responder or self._fixed_response,
            proposal_root=self.proposals,
            worktree_root=self.worktrees,
            key_path=self.key,
        )

    def _manifest_path(self, outcome):
        return self.proposals / f"{outcome['proposal']['proposal_id']}.json"

    def _resign(self, path, mutate):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        mutate(manifest)
        manifest["signature"] = _sign_manifest(manifest, _repair_key(self.key))
        path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_verified_proposal_does_not_touch_source_until_one_time_approval(self):
        outcome = self._prepare()

        self.assertTrue(outcome["ok"], outcome)
        self.assertTrue(outcome["approval_required"])
        self.assertFalse(outcome["source_project_modified"])
        self.assertEqual((self.project / "app.py").read_text(encoding="utf-8"), BROKEN_SOURCE)
        self.assertEqual(outcome["proposal"]["isolation_kind"], "content_snapshot")
        self.assertTrue(outcome["proposal"]["verified_targeted"]["passed"])
        self.assertTrue(outcome["proposal"]["verified_full"]["passed"])
        isolated_root = self.worktrees / outcome["proposal"]["proposal_id"]
        self.assertFalse((isolated_root / ".gradle-dist").exists())
        self.assertFalse((isolated_root / ".tmp-runtime.zip").exists())
        public_json = json.dumps(outcome)
        self.assertNotIn(FIXED_SOURCE, public_json)
        self.assertIn("return left + right", outcome["proposal"]["diff"])

        proposal_id = outcome["proposal"]["proposal_id"]
        applied = apply_test_repair(
            proposal_id,
            root=self.project,
            trusted_execution=True,
            proposal_root=self.proposals,
            key_path=self.key,
        )

        self.assertTrue(applied["ok"], applied)
        self.assertEqual((self.project / "app.py").read_text(encoding="utf-8"), FIXED_SOURCE)
        self.assertFalse(applied["rolled_back"])
        self.assertFalse((self.worktrees / proposal_id).exists())
        archived_manifest = self.proposals / f"{proposal_id}.json"
        archived_text = archived_manifest.read_text(encoding="utf-8")
        self.assertNotIn("new_content", archived_text)
        self.assertNotIn(FIXED_SOURCE, archived_text)
        replay = apply_test_repair(
            proposal_id,
            root=self.project,
            trusted_execution=True,
            proposal_root=self.proposals,
            key_path=self.key,
        )
        self.assertFalse(replay["ok"])
        self.assertIn("one-time", replay["error"])

    def test_green_suite_completes_without_model_or_source_change(self):
        (self.project / "app.py").write_text(FIXED_SOURCE, encoding="utf-8")

        def responder(_prompt):
            self.fail("The model must not run when the trusted suite is already green.")

        outcome = self._prepare(responder)

        self.assertTrue(outcome["ok"])
        self.assertTrue(outcome["no_repair_needed"])
        self.assertTrue(outcome["reproduction"]["passed"])
        self.assertEqual(outcome["reproduction"]["test_count"], 1)
        self.assertFalse(outcome["source_project_modified"])
        self.assertEqual((self.project / "app.py").read_text(encoding="utf-8"), FIXED_SOURCE)
        self.assertFalse(any(self.worktrees.glob("*")))

    def test_cleanup_removes_only_unreferenced_content_snapshots(self):
        outcome = self._prepare()
        active_id = outcome["proposal"]["proposal_id"]
        orphan = self.worktrees / str(uuid4())
        orphan.mkdir()
        (orphan / "source.py").write_text("value = 1\n", encoding="utf-8")
        unrelated = self.worktrees / "operator-notes"
        unrelated.mkdir()

        removed = cleanup_expired_test_repairs(
            proposal_root=self.proposals,
            worktree_root=self.worktrees,
            key_path=self.key,
        )

        self.assertEqual(removed, 1)
        self.assertFalse(orphan.exists())
        self.assertTrue((self.worktrees / active_id).exists())
        self.assertTrue(unrelated.exists())

    def test_tampered_signature_and_changed_preimage_are_rejected(self):
        tampered = self._prepare()
        manifest_path = self._manifest_path(tampered)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["diagnosis"] = "tampered"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        rejected = apply_test_repair(
            tampered["proposal"]["proposal_id"],
            root=self.project,
            trusted_execution=True,
            proposal_root=self.proposals,
            key_path=self.key,
        )
        self.assertFalse(rejected["ok"])
        self.assertIn("signature", rejected["error"])
        self.assertEqual((self.project / "app.py").read_text(encoding="utf-8"), BROKEN_SOURCE)

        manifest_path.unlink()
        second = self._prepare()
        user_change = "def add(left, right):\n    return 99\n"
        (self.project / "app.py").write_text(user_change, encoding="utf-8")
        rejected = apply_test_repair(
            second["proposal"]["proposal_id"],
            root=self.project,
            trusted_execution=True,
            proposal_root=self.proposals,
            key_path=self.key,
        )
        self.assertFalse(rejected["ok"])
        self.assertIn("changed after proposal", rejected["error"])
        self.assertEqual((self.project / "app.py").read_text(encoding="utf-8"), user_change)

    def test_expired_proposal_is_rejected_without_source_change(self):
        outcome = self._prepare()
        manifest_path = self._manifest_path(outcome)
        self._resign(
            manifest_path,
            lambda manifest: manifest.update(
                {"expires_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}
            ),
        )

        rejected = apply_test_repair(
            outcome["proposal"]["proposal_id"],
            root=self.project,
            trusted_execution=True,
            proposal_root=self.proposals,
            key_path=self.key,
        )

        self.assertFalse(rejected["ok"])
        self.assertIn("expired", rejected["error"])
        self.assertEqual((self.project / "app.py").read_text(encoding="utf-8"), BROKEN_SOURCE)
        self.assertFalse(manifest_path.exists())

    def test_test_edits_and_new_execution_primitives_are_rejected(self):
        def test_edit(_prompt):
            return json.dumps(
                {
                    "diagnosis": "invalid test weakening",
                    "changes": [
                        {
                            "path": "tests/test_app.py",
                            "new_content": "import unittest\n",
                        }
                    ],
                }
            )

        rejected = self._prepare(test_edit)
        self.assertFalse(rejected["ok"])
        self.assertIn("could not produce", rejected["error"])

        dangerous_source = "import os\n\ndef add(left, right):\n    os.system('whoami')\n    return left + right\n"

        def dangerous(_prompt):
            return json.dumps(
                {
                    "diagnosis": "invalid execution introduction",
                    "changes": [{"path": "app.py", "new_content": dangerous_source}],
                }
            )

        rejected = self._prepare(dangerous)
        self.assertFalse(rejected["ok"])
        self.assertIn("could not produce", rejected["error"])
        self.assertEqual((self.project / "app.py").read_text(encoding="utf-8"), BROKEN_SOURCE)

    def test_untrusted_execution_and_path_traversal_fail_closed(self):
        untrusted = prepare_test_repair(
            "AURIS, fix this failing test",
            root=self.project,
            project_name="Fixture",
            trusted_execution=False,
            responder=self._fixed_response,
            proposal_root=self.proposals,
            worktree_root=self.worktrees,
            key_path=self.key,
        )
        self.assertFalse(untrusted["ok"])
        self.assertIn("trusted", untrusted["error"])
        self.assertFalse(self.proposals.exists())

        def traversal(_prompt):
            return json.dumps(
                {
                    "diagnosis": "invalid traversal",
                    "changes": [{"path": "../outside.py", "new_content": FIXED_SOURCE}],
                }
            )

        rejected = self._prepare(traversal)
        self.assertFalse(rejected["ok"])
        self.assertFalse((self.base / "outside.py").exists())
        self.assertEqual((self.project / "app.py").read_text(encoding="utf-8"), BROKEN_SOURCE)

    def test_post_approval_suite_failure_rolls_back_exact_preimage(self):
        outcome = self._prepare()
        (self.project / "tests" / "test_regression.py").write_text(
            "import unittest\n\n"
            "class RegressionTests(unittest.TestCase):\n"
            "    def test_late_regression(self):\n"
            "        self.fail('late full-suite failure')\n",
            encoding="utf-8",
        )

        result = apply_test_repair(
            outcome["proposal"]["proposal_id"],
            root=self.project,
            trusted_execution=True,
            proposal_root=self.proposals,
            key_path=self.key,
        )

        self.assertFalse(result["ok"])
        self.assertTrue(result["rolled_back"])
        self.assertTrue(result["targeted_test"]["passed"])
        self.assertFalse(result["full_test"]["passed"])
        self.assertEqual((self.project / "app.py").read_text(encoding="utf-8"), BROKEN_SOURCE)

    def test_rejection_discards_isolation_and_cannot_be_replayed(self):
        outcome = self._prepare()
        proposal_id = outcome["proposal"]["proposal_id"]

        self.assertTrue(
            discard_test_repair(
                proposal_id, proposal_root=self.proposals, key_path=self.key
            )
        )
        self.assertFalse((self.worktrees / proposal_id).exists())
        self.assertFalse((self.proposals / f"{proposal_id}.json").exists())
        self.assertFalse(
            discard_test_repair(
                proposal_id, proposal_root=self.proposals, key_path=self.key
            )
        )


if __name__ == "__main__":
    unittest.main()
