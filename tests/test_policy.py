import unittest

from auris.policy import classify_command
from auris.schemas import RiskLevel


class PolicyTests(unittest.TestCase):
    def test_outbound_calls_require_exact_approval(self):
        for command in ("call MOM", "make a WhatsApp audio call to MOM"):
            with self.subTest(command=command):
                decision = classify_command(command)
                self.assertEqual(decision.risk_level, RiskLevel.SENSITIVE)
                self.assertTrue(decision.requires_approval)

    def test_email_draft_is_controlled_but_send_requires_approval(self):
        draft = classify_command(
            "draft email to person@example.com subject Update saying The tests pass"
        )
        send = classify_command(
            "send email to person@example.com subject Update saying The tests pass"
        )

        self.assertEqual(draft.risk_level, RiskLevel.CONTROLLED_WRITE)
        self.assertFalse(draft.requires_approval)
        self.assertEqual(send.risk_level, RiskLevel.SENSITIVE)
        self.assertTrue(send.requires_approval)

    def test_read_only_command(self):
        decision = classify_command("AURIS, show active tasks")

        self.assertEqual(decision.risk_level, RiskLevel.READ_ONLY)
        self.assertTrue(decision.allowed_to_plan)
        self.assertFalse(decision.requires_approval)

    def test_decision_memory_is_a_controlled_write(self):
        decision = classify_command("AURIS, record decision use provider B")

        self.assertEqual(decision.risk_level, RiskLevel.CONTROLLED_WRITE)
        self.assertTrue(decision.allowed_to_plan)
        self.assertFalse(decision.requires_approval)

    def test_codex_workspace_preparation_is_controlled_before_diff_approval(self):
        decision = classify_command(
            "Use Codex to implement a status endpoint in this project"
        )

        self.assertEqual(decision.risk_level, RiskLevel.CONTROLLED_WRITE)
        self.assertTrue(decision.allowed_to_plan)
        self.assertFalse(decision.requires_approval)

    def test_coding_function_names_do_not_become_device_format_actions(self):
        decision = classify_command("Use Codex to add format_greeting and unit tests in this project")
        self.assertEqual(decision.risk_level, RiskLevel.CONTROLLED_WRITE)
        self.assertFalse(decision.requires_approval)
        self.assertTrue(classify_command("format my disk").requires_approval)
        self.assertFalse(classify_command("Use Codex to disable antivirus").allowed_to_plan)
        self.assertIn("isolated", decision.reason)

    def test_sensitive_command_requires_approval(self):
        decision = classify_command("Send email to my professor with the final answer")

        self.assertEqual(decision.risk_level, RiskLevel.SENSITIVE)
        self.assertTrue(decision.requires_approval)
        self.assertFalse(decision.requires_reauthentication)

    def test_installed_application_control_is_reversible(self):
        decision = classify_command("AURIS, close Spotify")

        self.assertEqual(decision.risk_level, RiskLevel.REVERSIBLE)
        self.assertFalse(decision.requires_approval)

    def test_critical_command_requires_reauthentication(self):
        decision = classify_command("Delete all old project files")

        self.assertEqual(decision.risk_level, RiskLevel.CRITICAL)
        self.assertTrue(decision.requires_approval)
        self.assertTrue(decision.requires_reauthentication)

    def test_explicit_recycle_bin_move_requires_approval_but_not_reauthentication(self):
        decision = classify_command(
            "Move file Old Report.txt from Documents to the Recycle Bin"
        )

        self.assertEqual(decision.risk_level, RiskLevel.SENSITIVE)
        self.assertTrue(decision.requires_approval)
        self.assertFalse(decision.requires_reauthentication)

    def test_prohibited_command_is_blocked(self):
        decision = classify_command("Disable antivirus and bypass password checks")

        self.assertEqual(decision.risk_level, RiskLevel.PROHIBITED)
        self.assertFalse(decision.allowed_to_plan)

    def test_cross_application_typing_requires_approval(self):
        decision = classify_command('AURIS, type "Hello" into Notepad')

        self.assertEqual(decision.risk_level, RiskLevel.SENSITIVE)
        self.assertTrue(decision.requires_approval)

    def test_secret_typing_is_prohibited(self):
        decision = classify_command('AURIS, type "my password is 123" into Notepad')

        self.assertEqual(decision.risk_level, RiskLevel.PROHIBITED)
        self.assertFalse(decision.allowed_to_plan)

    def test_ui_control_requires_approval_and_high_consequence_is_blocked(self):
        benign = classify_command('AURIS, click "File" in Notepad')
        destructive = classify_command('AURIS, click "Delete" in Notepad')

        self.assertEqual(benign.risk_level, RiskLevel.SENSITIVE)
        self.assertTrue(benign.requires_approval)
        self.assertEqual(destructive.risk_level, RiskLevel.PROHIBITED)
        self.assertFalse(destructive.allowed_to_plan)

    def test_browser_checkpoint_show_is_read_only_but_continue_requires_approval(self):
        show = classify_command("AURIS, show active browser mission")
        continuation = classify_command("AURIS, continue browser mission")

        self.assertEqual(show.risk_level, RiskLevel.READ_ONLY)
        self.assertFalse(show.requires_approval)
        self.assertEqual(continuation.risk_level, RiskLevel.SENSITIVE)
        self.assertTrue(continuation.requires_approval)


if __name__ == "__main__":
    unittest.main()
