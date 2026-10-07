from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auris.repair_agent import apply_test_repair, prepare_test_repair


BROKEN_SOURCE = "def total(left, right):\n    return left - right\n"
FIXED_SOURCE = "def total(left, right):\n    return left + right\n"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT / "data") as temporary:
        base = Path(temporary)
        project = base / "project"
        proposals = base / "proposals"
        worktrees = base / "worktrees"
        key = base / "repair.key"
        tests = project / "tests"
        tests.mkdir(parents=True)
        source = project / "calculator.py"
        source.write_text(BROKEN_SOURCE, encoding="utf-8")
        (tests / "test_calculator.py").write_text(
            "import unittest\n"
            "from calculator import total\n\n"
            "class CalculatorTests(unittest.TestCase):\n"
            "    def test_total(self):\n"
            "        self.assertEqual(total(7, 5), 12)\n",
            encoding="utf-8",
        )
        original_hash = sha256_text(source.read_text(encoding="utf-8"))

        def responder(_prompt: str) -> str:
            return json.dumps(
                {
                    "diagnosis": (
                        "calculator.total subtracts the right operand, while the reproduced test "
                        "requires arithmetic addition."
                    ),
                    "changes": [
                        {"path": "calculator.py", "new_content": FIXED_SOURCE}
                    ],
                }
            )

        proposal = prepare_test_repair(
            "AURIS, fix this failing test",
            root=project,
            project_name="AURIS repair acceptance fixture",
            trusted_execution=True,
            responder=responder,
            proposal_root=proposals,
            worktree_root=worktrees,
            key_path=key,
        )
        if not proposal.get("ok"):
            raise SystemExit(f"Repair proposal failed: {proposal}")
        public = proposal["proposal"]
        if sha256_text(source.read_text(encoding="utf-8")) != original_hash:
            raise SystemExit("The registered source changed before approval.")
        if not public["verified_targeted"]["passed"] or not public["verified_full"]["passed"]:
            raise SystemExit("The isolated targeted or complete test gate did not pass.")
        if FIXED_SOURCE in json.dumps(proposal):
            raise SystemExit("Full replacement source leaked into the public proposal.")

        applied = apply_test_repair(
            public["proposal_id"],
            root=project,
            trusted_execution=True,
            proposal_root=proposals,
            key_path=key,
        )
        if not applied.get("ok") or applied.get("rolled_back"):
            raise SystemExit(f"Approved repair failed: {applied}")
        if source.read_text(encoding="utf-8") != FIXED_SOURCE:
            raise SystemExit("The signed replacement did not match the final source.")
        if not applied["targeted_test"]["passed"] or not applied["full_test"]["passed"]:
            raise SystemExit("Post-apply targeted or complete verification failed.")

        replay = apply_test_repair(
            public["proposal_id"],
            root=project,
            trusted_execution=True,
            proposal_root=proposals,
            key_path=key,
        )
        if replay.get("ok"):
            raise SystemExit("The one-time signed proposal was replayed.")

        print(
            json.dumps(
                {
                    "ok": True,
                    "release": "0.8.5",
                    "proposal_id": public["proposal_id"],
                    "isolation_kind": public["isolation_kind"],
                    "files_changed": public["diff_stats"]["files_changed"],
                    "targeted_isolated": public["verified_targeted"]["passed"],
                    "full_isolated": public["verified_full"]["passed"],
                    "source_unchanged_before_approval": True,
                    "targeted_post_apply": applied["targeted_test"]["passed"],
                    "full_post_apply": applied["full_test"]["passed"],
                    "one_time_replay_rejected": True,
                    "full_source_in_public_result": False,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
