import unittest
from unittest.mock import patch

from auris.schemas import RiskLevel, TaskState
from auris.supervisor import create_task_plan


class SupervisorTests(unittest.TestCase):
    def test_call_commands_route_to_communications_instead_of_general_assistance(self):
        for command in ("call MOM", "make a WhatsApp audio call to MOM"):
            with self.subTest(command=command):
                plan = create_task_plan(command)
                self.assertEqual(plan.task_type, "communications")
                self.assertEqual(plan.state, TaskState.AWAITING_APPROVAL)

    def test_failing_test_repair_plans_signed_post_verification_approval(self):
        plan = create_task_plan("AURIS, fix this failing test")

        self.assertEqual(plan.task_type, "coding")
        self.assertEqual(plan.risk_level, RiskLevel.CONTROLLED_WRITE)
        self.assertEqual(plan.state, TaskState.CREATED)
        self.assertIn("security_agent", plan.required_agents)
        self.assertTrue(any("signed diff" in item for item in plan.approval_points))

    def test_codex_workspace_plan_requires_isolation_and_exact_diff_approval(self):
        plan = create_task_plan(
            "Use Codex to implement a status endpoint in this project"
        )

        self.assertEqual(plan.task_type, "coding")
        self.assertEqual(plan.risk_level, RiskLevel.CONTROLLED_WRITE)
        self.assertIn("coding_agent", plan.required_agents)
        self.assertIn("security_agent", plan.required_agents)
        self.assertTrue(any("Codex" in item for item in plan.approval_points))
        self.assertTrue(any("isolated" in item for item in plan.success_conditions))
        self.assertTrue(any("exact rollback" in item for item in plan.success_conditions))

    def test_creates_research_plan(self):
        plan = create_task_plan("AURIS, conduct deep research on anomaly detection")

        self.assertEqual(plan.task_type, "research")
        self.assertIn("research_agent", plan.required_agents)
        self.assertIn("verification_agent", plan.required_agents)
        self.assertEqual(len(plan.steps), 3)
        self.assertTrue(any("coverage ledger" in item for item in plan.success_conditions))
        self.assertTrue(any("Counterevidence" in item for item in plan.success_conditions))

    def test_sensitive_plan_adds_security_and_approval(self):
        plan = create_task_plan("AURIS, apply for this job")

        self.assertEqual(plan.risk_level, RiskLevel.SENSITIVE)
        self.assertIn("security_agent", plan.required_agents)
        self.assertTrue(plan.approval_points)
        self.assertEqual(plan.state, TaskState.AWAITING_APPROVAL)

    def test_memory_command_uses_memory_agent(self):
        plan = create_task_plan("AURIS, remember that I prefer concise reports")

        self.assertEqual(plan.task_type, "memory")
        self.assertIn("memory_agent", plan.required_agents)

        decision = create_task_plan("AURIS, record decision use provider B")
        recall = create_task_plan("AURIS, recall the hosting decision")
        self.assertEqual(decision.task_type, "memory")
        self.assertEqual(recall.task_type, "memory")

    def test_device_command_uses_computer_agent(self):
        plan = create_task_plan("AURIS, open Spotify")

        self.assertEqual(plan.task_type, "computer_operation")
        self.assertIn("computer_agent", plan.required_agents)

    def test_folder_creation_uses_signed_computer_operation(self):
        plan = create_task_plan("AURIS, create a folder named DON on Desktop")

        self.assertEqual(plan.task_type, "computer_operation")
        self.assertEqual(plan.risk_level, RiskLevel.REVERSIBLE)
        self.assertIn("computer_agent", plan.required_agents)

        unsafe = create_task_plan("AURIS, create folder DON in C:\\Windows")
        self.assertEqual(unsafe.task_type, "computer_operation")

    def test_note_creation_uses_controlled_signed_computer_operation(self):
        plan = create_task_plan(
            "AURIS, create a note named Status on Desktop saying AURIS is ready"
        )

        self.assertEqual(plan.task_type, "computer_operation")
        self.assertEqual(plan.risk_level, RiskLevel.CONTROLLED_WRITE)

    def test_note_append_uses_controlled_signed_computer_operation(self):
        plan = create_task_plan(
            'AURIS, append "Next verified state" to note Status.txt in Documents'
        )

        self.assertEqual(plan.task_type, "computer_operation")
        self.assertEqual(plan.risk_level, RiskLevel.CONTROLLED_WRITE)

    def test_bounded_file_transfers_use_reversible_computer_operation(self):
        commands = (
            "rename file Report.txt in Documents to Final.txt",
            "copy file Report.txt from Documents to Desktop",
            "move file Report.txt from Desktop to Downloads",
        )

        for command in commands:
            with self.subTest(command=command):
                plan = create_task_plan(command)
                self.assertEqual(plan.task_type, "computer_operation")
                self.assertEqual(plan.risk_level, RiskLevel.REVERSIBLE)

    def test_safe_file_open_uses_reversible_computer_operation(self):
        plan = create_task_plan("AURIS, open Report.pdf from Documents")

        self.assertEqual(plan.task_type, "computer_operation")
        self.assertEqual(plan.risk_level, RiskLevel.REVERSIBLE)

    def test_window_state_commands_use_reversible_computer_operation(self):
        for command in ("minimize Spotify", "maximize Notepad", "restore Edge"):
            with self.subTest(command=command):
                plan = create_task_plan(command)
                self.assertEqual(plan.task_type, "computer_operation")
                self.assertEqual(plan.risk_level, RiskLevel.REVERSIBLE)

    def test_screen_command_uses_vision_agent(self):
        plan = create_task_plan("AURIS, describe my screen")

        self.assertEqual(plan.task_type, "screen_understanding")
        self.assertIn("vision_agent", plan.required_agents)

    def test_browser_navigation_uses_computer_agent(self):
        plan = create_task_plan("AURIS, open github.com/openai")

        self.assertEqual(plan.task_type, "browser_workflow")
        self.assertIn("computer_agent", plan.required_agents)

    def test_named_browser_search_routes_to_device_instead_of_isolated_browser(self):
        with patch("auris.supervisor.is_named_browser_command", return_value=True):
            plan = create_task_plan("AURIS, search YouTube for AURIS demos in Brave")

        self.assertEqual(plan.task_type, "computer_operation")
        self.assertEqual(plan.risk_level, RiskLevel.REVERSIBLE)

    def test_application_state_routing_distinguishes_resume_from_career_content(self):
        show = create_task_plan("AURIS, show active browser mission")
        continuation = create_task_plan("AURIS, continue browser mission")

        self.assertEqual(show.task_type, "application_state")
        self.assertEqual(show.state, TaskState.CREATED)
        self.assertEqual(continuation.task_type, "application_state")
        self.assertEqual(continuation.state, TaskState.AWAITING_APPROVAL)
        self.assertTrue(any("final control" in item for item in continuation.success_conditions))

    def test_filename_search_uses_file_agent(self):
        plan = create_task_plan("AURIS, find file blueprint")

        self.assertEqual(plan.task_type, "file_workflow")
        self.assertIn("file_agent", plan.required_agents)

        content = create_task_plan("AURIS, search file contents for quantum migration")
        self.assertEqual(content.task_type, "file_workflow")
        self.assertEqual(content.risk_level, RiskLevel.READ_ONLY)

    def test_document_summary_uses_document_agent(self):
        plan = create_task_plan("AURIS, summarize document blueprint-notes.md")

        self.assertEqual(plan.task_type, "document_workflow")
        self.assertIn("document_agent", plan.required_agents)

    def test_work_product_commands_use_artifact_agent_and_controlled_write(self):
        commands = (
            "AURIS, make a chatbot for me fully functional",
            "create a Word document about renewable energy",
            "research edge AI and create a Word report",
            "create a PowerPoint presentation about edge AI",
            "build an Excel tracker for project milestones",
            "create a PDF report about energy storage",
        )
        for command in commands:
            with self.subTest(command=command):
                plan = create_task_plan(command)
                self.assertEqual(plan.task_type, "work_product")
                self.assertEqual(plan.risk_level, RiskLevel.CONTROLLED_WRITE)
                self.assertIn("artifact_agent", plan.required_agents)
                self.assertTrue(any("hashes" in item for item in plan.success_conditions))

    def test_test_command_uses_coding_agent(self):
        plan = create_task_plan("AURIS, run the tests")

        self.assertEqual(plan.task_type, "coding")
        self.assertIn("coding_agent", plan.required_agents)

    def test_project_analysis_has_repository_specific_success_contract(self):
        plan = create_task_plan("AURIS, analyse this project")

        self.assertEqual(plan.task_type, "coding")
        self.assertTrue(any("Repository structure" in item for item in plan.success_conditions))
        self.assertTrue(any("modifies no project file" in item for item in plan.success_conditions))

    def test_open_project_uses_computer_agent_and_observation_contract(self):
        plan = create_task_plan("AURIS, open my InfraGuard project")

        self.assertEqual(plan.task_type, "project_operation")
        self.assertEqual(plan.risk_level.value, "reversible")
        self.assertIn("computer_agent", plan.required_agents)
        self.assertTrue(any("File Explorer location is observed" in item for item in plan.success_conditions))

    def test_reminder_uses_event_agent(self):
        plan = create_task_plan("AURIS, remind me in 10 minutes to stretch")

        self.assertEqual(plan.task_type, "reminder")
        self.assertIn("event_agent", plan.required_agents)

    def test_email_search_and_send_use_communications_agent(self):
        search = create_task_plan("AURIS, search my email for dissertation feedback")
        send = create_task_plan(
            "AURIS, send email to person@example.com subject Update saying The tests pass"
        )

        self.assertEqual(search.task_type, "communications")
        self.assertIn("communications_agent", search.required_agents)
        self.assertEqual(send.task_type, "communications")
        self.assertEqual(send.state, TaskState.AWAITING_APPROVAL)

    def test_contact_lookup_uses_communications_agent(self):
        plan = create_task_plan("AURIS, find my contact named Ada Lovelace")

        self.assertEqual(plan.task_type, "communications")
        self.assertIn("communications_agent", plan.required_agents)
        self.assertFalse(plan.approval_points)

    def test_daily_brief_uses_operational_agents(self):
        plan = create_task_plan("AURIS, prepare my daily briefing")

        self.assertEqual(plan.task_type, "daily_brief")
        self.assertIn("event_agent", plan.required_agents)
        self.assertIn("communications_agent", plan.required_agents)

    def test_typing_command_pauses_for_approval(self):
        plan = create_task_plan('AURIS, type "Hello" into Notepad')

        self.assertEqual(plan.task_type, "computer_interaction")
        self.assertEqual(plan.state, TaskState.AWAITING_APPROVAL)
        self.assertIn("security_agent", plan.required_agents)

    def test_ui_control_uses_approval_and_observation_contract(self):
        plan = create_task_plan('AURIS, click "File" in Notepad')

        self.assertEqual(plan.task_type, "computer_interaction")
        self.assertEqual(plan.state, TaskState.AWAITING_APPROVAL)
        self.assertTrue(any("signed device permission" in item for item in plan.success_conditions))
        self.assertTrue(any("post-action Windows observation" in item for item in plan.success_conditions))

    def test_substrings_do_not_trigger_specialist_routing(self):
        plan = create_task_plan("My temporary codename is Orion")

        self.assertEqual(plan.task_type, "general_assistance")
        self.assertNotIn("coding_agent", plan.required_agents)

    def test_prohibited_plan_is_blocked(self):
        plan = create_task_plan("AURIS, run as administrator and disable firewall")

        self.assertEqual(plan.risk_level, RiskLevel.PROHIBITED)
        self.assertEqual(plan.state, TaskState.BLOCKED)
        self.assertEqual(plan.steps, [])


if __name__ == "__main__":
    unittest.main()
