import unittest
from unittest.mock import patch

from auris.browser_agent import (
    BrowserAction,
    BrowserStep,
    WORKER_SCRIPT,
    build_browser_device_action,
    contains_sensitive_browser_data,
    execute_browser_action,
    is_browser_interaction_intent,
    match_browser_command,
)
from auris.policy import classify_command
from auris.schemas import RiskLevel


class BrowserAgentTests(unittest.TestCase):
    def test_worker_resolves_hosts_and_blocks_private_addresses(self):
        source = WORKER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('from "node:dns/promises"', source)
        self.assertIn("isPrivateAddress", source)
        self.assertIn("addresses.every", source)
        self.assertIn("await allowedUrl(route.request().url())", source)
        self.assertIn("exactText", source)
        self.assertIn("performWorkflow", source)
        self.assertIn("chromiumSandbox: true", source)
        self.assertIn("SENSITIVE_URL_KEY", source)
        self.assertIn("safeUrl", source)
        self.assertIn('url_query_values: "sha256_redacted"', source)

    def test_matches_navigation_search_and_inspection(self):
        navigation = match_browser_command("AURIS, open github.com/openai")
        search = match_browser_command("search the web for local voice assistants")
        inspect = match_browser_command("inspect the current browser page")

        self.assertEqual(navigation.kind, "navigate")
        self.assertEqual(navigation.url, "https://github.com/openai")
        self.assertEqual(search.kind, "navigate")
        self.assertIn("local+voice+assistants", search.url)
        self.assertEqual(inspect.kind, "inspect")

    def test_matches_exact_fill_and_click_with_approval_policy(self):
        fill = match_browser_command('fill "Acceptance note" with "Hello Devansh" in the browser')
        click = match_browser_command('click "Apply Preview" button in the browser')

        self.assertEqual((fill.kind, fill.accessible_name, fill.value), ("fill", "Acceptance note", "Hello Devansh"))
        self.assertEqual((click.kind, click.accessible_name), ("click", "Apply Preview"))
        self.assertTrue(is_browser_interaction_intent('click "Apply Preview" in the browser'))
        self.assertEqual(classify_command('click "Apply Preview" in the browser').risk_level, RiskLevel.SENSITIVE)
        self.assertTrue(classify_command('click "Apply Preview" in the browser').requires_approval)

        exact_spaces = match_browser_command('fill "Acceptance note" with "two  spaces" in the browser')
        self.assertEqual(exact_spaces.value, "two  spaces")

    def test_matches_quoted_multi_fill_and_spoken_browser_missions(self):
        quoted = match_browser_command(
            'run browser mission open "https://example.com/form" '
            'then fill "First name" with "Devansh" '
            'then fill "Reference" with "AURIS 825" '
            'then click "Apply Preview"'
        )
        spoken = match_browser_command(
            "AURIS, run browser mission open example.com/form then fill Acceptance note "
            "with Hello Devansh then click Apply Preview button"
        )

        self.assertEqual(quoted.kind, "workflow")
        self.assertEqual([step.kind for step in quoted.steps], ["navigate", "fill", "fill", "click"])
        self.assertEqual(quoted.steps[2].value, "AURIS 825")
        self.assertEqual(spoken.kind, "workflow")
        self.assertEqual(spoken.steps[1].accessible_name, "Acceptance note")
        self.assertEqual(spoken.steps[-1].accessible_name, "Apply Preview")
        self.assertEqual(
            classify_command("run browser mission open example.com/form then fill Acceptance note with Hello Devansh then click Apply Preview").risk_level,
            RiskLevel.SENSITIVE,
        )

    def test_browser_mission_redacts_values_and_binds_one_signed_scope(self):
        action = match_browser_command(
            'run browser mission open "https://example.com/form" '
            'then fill "Reference" with "Private draft" then click "Apply Preview"'
        )
        public = action.to_dict()
        device = build_browser_device_action(action)

        self.assertNotIn("Private draft", str(public))
        self.assertEqual(public["steps"][1]["value_length"], 13)
        self.assertIn("value_sha256", public["steps"][1])
        self.assertEqual(device.kind, "browser_workflow")
        self.assertNotIn("Private draft", device.target)

    def test_browser_mission_rejects_any_secret_or_consequential_step(self):
        secret = 'run browser mission open "https://example.com" then fill "Note" with "secret token" then click "Preview"'
        purchase = 'run browser mission open "https://example.com" then fill "Note" with "Draft" then click "Purchase now"'

        self.assertTrue(contains_sensitive_browser_data(secret))
        self.assertTrue(contains_sensitive_browser_data(purchase))
        self.assertEqual(classify_command(secret).risk_level, RiskLevel.PROHIBITED)
        self.assertEqual(classify_command(purchase).risk_level, RiskLevel.PROHIBITED)

    def test_browser_navigation_and_mission_reject_secret_bearing_urls(self):
        navigation = "open https://example.com/form?access_token=private"
        mission = 'run browser mission open "https://example.com/form?api_key=private" then fill "Note" with "Draft" then click "Preview"'

        self.assertTrue(contains_sensitive_browser_data(navigation))
        self.assertTrue(contains_sensitive_browser_data(mission))
        self.assertEqual(classify_command(navigation).risk_level, RiskLevel.PROHIBITED)
        self.assertEqual(classify_command(mission).risk_level, RiskLevel.PROHIBITED)

    def test_rejects_secret_values_and_consequential_controls(self):
        secret = 'fill "Account" with "my password is swordfish" in the browser'
        purchase = 'click "Purchase now" in the browser'

        self.assertTrue(contains_sensitive_browser_data(secret))
        self.assertTrue(contains_sensitive_browser_data(purchase))
        self.assertEqual(classify_command(secret).risk_level, RiskLevel.PROHIBITED)
        self.assertEqual(classify_command(purchase).risk_level, RiskLevel.PROHIBITED)

    def test_action_serialization_redacts_field_value_and_binds_signed_scope(self):
        action = match_browser_command('fill "Acceptance note" with "Private draft" in the browser')
        public = action.to_dict()
        device = build_browser_device_action(action)

        self.assertNotIn("value", public)
        self.assertIn("value_sha256", public)
        self.assertNotIn("Private draft", str(public))
        self.assertEqual(device.kind, "browser_fill")
        self.assertIn("value=", device.target)
        self.assertNotIn("Private draft", device.target)

    def test_rejects_non_web_schemes(self):
        self.assertIsNone(match_browser_command("open file:///C:/Windows/System32"))
        self.assertIsNone(match_browser_command("open javascript:alert(1)"))

    @patch("auris.browser_agent._WORKER.request")
    def test_navigation_reports_page_level_verification(self, request):
        request.return_value = {
            "ok": True,
            "operation": "navigate",
            "http_status": 200,
            "page": {"url": "https://example.com/", "title": "Example Domain", "controls": []},
        }

        result = execute_browser_action(match_browser_command("visit example.com"))

        self.assertTrue(result["ok"])
        self.assertEqual(result["http_status"], 200)
        self.assertIn("HTTP 200", result["verification"])
        self.assertIn("Example Domain", result["verification"])

    @patch("auris.browser_agent._WORKER.request")
    def test_click_without_observed_state_change_is_failure(self, request):
        request.return_value = {
            "ok": False,
            "operation": "click",
            "state_changed": False,
            "page": {"url": "https://example.com/", "title": "Example", "controls": []},
        }

        result = execute_browser_action(match_browser_command('click "Continue" in the browser'))

        self.assertFalse(result["ok"])
        self.assertFalse(result["state_changed"])
        self.assertIn("not treated as task completion", result["verification"])

    @patch("auris.browser_agent._WORKER.request")
    def test_browser_mission_reports_step_checkpoints_without_values(self, request):
        request.return_value = {
            "ok": True,
            "operation": "workflow",
            "completed_steps": 3,
            "failed_step": None,
            "steps": [
                {"index": 1, "kind": "navigate", "ok": True},
                {"index": 2, "kind": "fill", "ok": True, "observed_length": 8, "value_sha256": "a" * 64},
                {"index": 3, "kind": "click", "ok": True, "state_changed": True},
            ],
            "page": {"url": "https://example.com/done", "title": "Done", "controls": []},
        }
        action = BrowserAction(
            "workflow", "Mission", steps=(
                BrowserStep("navigate", url="https://example.com/form"),
                BrowserStep("fill", accessible_name="Note", value="Approved"),
                BrowserStep("click", accessible_name="Preview"),
            ),
        )

        result = execute_browser_action(action)

        self.assertTrue(result["ok"])
        self.assertEqual(result["completed_steps"], 3)
        self.assertNotIn("Approved", str(result))
        self.assertIn("every exact field read-back", result["verification"])


if __name__ == "__main__":
    unittest.main()
