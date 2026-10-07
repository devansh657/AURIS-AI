import json
import unittest
from unittest.mock import patch

from auris.capabilities import CAPABILITIES, capabilities_for_task, capability_registry
from auris.supervisor import create_task_plan


class CapabilityRegistryTests(unittest.TestCase):
    def entry(self, capability_id, **observations):
        return next(item for item in capability_registry(observations)["capabilities"] if item["id"] == capability_id)

    def test_catalog_ids_unique_and_installed_adapters_exist(self):
        entries = capability_registry()["capabilities"]
        self.assertEqual(len({item["id"] for item in entries}), len(CAPABILITIES))
        self.assertTrue(all(item["installed"] for item in entries))
        self.assertTrue(all(item["state"] == "unknown" for item in entries if item["id"] != "outbound_calls"))

    def test_missing_adapter_does_not_claim_availability(self):
        with patch("auris.capabilities.Path.is_file", return_value=False):
            self.assertEqual(self.entry("memory", backend_online=True)["state"], "not_installed")

    def test_browser_runtime_is_not_connected_worker(self):
        self.assertEqual(self.entry("browser_workflows", browser={"runtime_available": True, "connected": False})["state"], "on_demand")
        self.assertEqual(self.entry("browser_workflows", browser={"runtime_available": False})["state"], "not_installed")

    def test_phone_config_is_not_live_acceptance(self):
        entry = self.entry("phone_assistant", telephony={"connected": True, "secret": "DO_NOT_EXPOSE"})
        self.assertEqual(entry["state"], "configured_unverified")
        self.assertNotIn("DO_NOT_EXPOSE", json.dumps(entry))
        self.assertEqual(self.entry("phone_assistant", telephony={"connected": False})["state"], "configuration_required")

    def test_input_worker_online_does_not_hide_signal_issue(self):
        observation = {"signal_state": "weak_signal", "age_seconds": 5, "mode": "command"}
        entry = self.entry("voice_input", voice_input={"input_worker_online": True, "input_observation": observation})
        self.assertEqual(entry["state"], "check_input")
        observation["age_seconds"] = 60
        self.assertEqual(self.entry("voice_input", voice_input={"input_worker_online": True, "input_observation": observation})["state"], "available")

    def test_idle_room_silence_is_not_a_microphone_fault(self):
        observation = {"signal_state": "weak_signal", "age_seconds": 5, "mode": "wake"}
        self.assertEqual(self.entry("voice_input", voice_input={"input_worker_online": True, "input_observation": observation})["state"], "available")

    def test_stopped_and_revoked_states_are_explicit(self):
        self.assertEqual(self.entry("memory", backend_online=True, control={"stopped": True})["state"], "paused")
        self.assertEqual(self.entry("windows_actions", device={"revoked": True})["state"], "blocked")

    def test_missing_scope_is_not_unrestricted_device_control(self):
        self.assertEqual(self.entry("windows_actions", device={"trust_state": "local_hmac", "permissions": ["launch_app"]})["state"], "limited")

    def test_actual_local_hmac_identity_is_available_not_disconnected(self):
        permissions = ["launch_app", "focus_app", "create_folder", "create_text_file"]
        self.assertEqual(self.entry("windows_actions", device={"trust_state": "local_hmac", "permissions": permissions, "revoked": False})["state"], "available")

    def test_coding_signin_required(self):
        self.assertEqual(self.entry("coding_build", coding={"available": True, "authenticated": False})["state"], "configuration_required")

    def test_registry_contains_permission_verifier_and_bounded_evidence(self):
        item = self.entry("windows_actions")
        self.assertTrue(item["required_permissions"])
        self.assertTrue(item["verifier"])
        self.assertIn("Live text", item["acceptance"]["scope"])
        self.assertFalse(item["acceptance"]["current_runtime_retested"])
        self.assertFalse(capability_registry()["permission_authority"])

    def test_planner_uses_catalog_scopes_and_ids(self):
        plan = create_task_plan("open Notepad").to_dict()
        self.assertEqual(plan["capability_ids"], ["windows_actions"])
        self.assertTrue(any("Capability scope [windows_actions]" in item for item in plan["success_conditions"]))
        self.assertEqual(capabilities_for_task("coding", coding_operation="codex_workspace")[0].id, "coding_build")

    def test_unknown_task_does_not_invent_adapter(self):
        self.assertEqual(capabilities_for_task("arbitrary_quantum_execution"), [])

    def test_call_plan_does_not_claim_outlook_or_inbound_can_place_calls(self):
        plan = create_task_plan("call MOM").to_dict()
        self.assertEqual(plan["capability_ids"], ["outbound_calls"])
        self.assertEqual(self.entry("outbound_calls", telephony={"connected": True})["state"], "not_connected")

    def test_spoken_capabilities_are_from_the_same_registry(self):
        from auris.runtime import _instant_response
        with patch("auris.runtime.collect_capability_observations", return_value={"backend_online": True}):
            text = _instant_response("what can you do")
        self.assertIn("Not ready", text)
        self.assertIn("Phone assistant", text)
        self.assertNotIn("Fully operational", text)


if __name__ == "__main__":
    unittest.main()
