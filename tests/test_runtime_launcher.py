from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RuntimeLauncherContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.launch = (ROOT / "scripts" / "launch_auris.ps1").read_text(encoding="utf-8")
        cls.start = (ROOT / "scripts" / "start_auris.ps1").read_text(encoding="utf-8")

    def test_launch_always_reconciles_process_trio(self):
        self.assertNotIn("if (-not $health) {", self.launch)
        self.assertEqual(self.launch.count('"start_auris.ps1"'), 1)
        self.assertIn("Reconcile every AURIS process", self.launch)

    def test_start_verifies_voice_and_companion_survive(self):
        self.assertIn("function Assert-AurisModuleProcess", self.start)
        self.assertIn("Get-Process -Id $ProcessId", self.start)
        self.assertIn(
            'Assert-AurisModuleProcess -ProcessId $voiceProcess.ProcessId -ModuleName "auris.voice_daemon"',
            self.start,
        )
        self.assertIn(
            'Assert-AurisModuleProcess -ProcessId $companionProcess.ProcessId -ModuleName "auris.desktop_companion"',
            self.start,
        )

    def test_outer_launcher_propagates_reconciliation_failure(self):
        self.assertIn("if ($LASTEXITCODE -ne 0)", self.launch)
        self.assertIn("AURIS process reconciliation failed", self.launch)


if __name__ == "__main__":
    unittest.main()
