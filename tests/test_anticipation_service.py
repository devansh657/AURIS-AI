from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from auris.anticipation_service import build_operations_intelligence
from auris.database import create_approval, create_scheduled_event, save_task, update_task_state
from auris.memory_service import store_memory
from auris.supervisor import create_task_plan


class AnticipationServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "auris-anticipation.db"
        self.system = patch(
            "auris.anticipation_service.collect_system_status",
            return_value={
                "machine": "TEST-LAPTOP",
                "disk": {"free_gb": 120},
                "memory": {"utilization_percent": 30},
                "gpu": {"temperature_c": 50},
            },
        )
        self.integrations = patch(
            "auris.anticipation_service.productivity_status",
            return_value={
                "outlook": {"state": "connected", "connected": True},
                "onedrive": {"state": "local_sync_connected", "connected": True},
                "telephony": {"state": "connected", "connected": True},
            },
        )
        self.system.start()
        self.integrations.start()

    def tearDown(self):
        self.integrations.stop()
        self.system.stop()
        self.temp_dir.cleanup()

    def test_overdue_event_interrupts_with_durable_evidence(self):
        now = datetime(2030, 1, 2, 12, 0, tzinfo=timezone.utc)
        event = create_scheduled_event(
            "Submit security report",
            (now - timedelta(hours=1)).isoformat(),
            project_id="auris-one",
            path=self.database_path,
        )

        intelligence = build_operations_intelligence(
            project_id="auris-one", now=now, path=self.database_path
        )

        signal = next(
            item for item in intelligence["attention"]["items"] if item["id"] == f"event:{event['event_id']}"
        )
        self.assertEqual(signal["level"], "CRITICAL")
        self.assertEqual(signal["delivery"], "INTERRUPT NOW")
        self.assertEqual(signal["evidence_ids"], [event["event_id"]])
        self.assertTrue(signal["advisory_only"])

    def test_focus_mode_batches_low_value_connector_signals(self):
        self.integrations.stop()
        with patch(
            "auris.anticipation_service.productivity_status",
            return_value={
                "outlook": {"state": "oauth_required", "connected": False},
                "onedrive": {"state": "not_configured", "connected": False},
                "telephony": {"state": "configuration_required", "connected": False},
            },
        ):
            intelligence = build_operations_intelligence(
                focus_mode=True, path=self.database_path
            )
        self.integrations.start()

        connectors = [
            item for item in intelligence["attention"]["items"] if item["kind"] == "capability_gap"
        ]
        self.assertEqual(len(connectors), 3)
        self.assertTrue(all(item["delivery"] == "LOG ONLY" for item in connectors))
        self.assertTrue(all(item["batched_by_focus"] for item in connectors))

    def test_graph_links_real_entities_and_masks_sensitive_memory(self):
        plan = create_task_plan("AURIS, research Northstar Labs").to_dict()
        save_task(plan, project_id="auris-one", path=self.database_path)
        company = store_memory(
            "Northstar Labs is a project stakeholder.",
            category="relationship",
            project_id="auris-one",
            subject_key="Northstar Labs",
            structured_data={"entity_type": "company", "name": "Northstar Labs"},
            path=self.database_path,
        )["memory"]
        protected = store_memory(
            "Private acquisition discussion",
            category="relationship",
            project_id="auris-one",
            subject_key="Confidential counterparty",
            sensitivity="sensitive",
            path=self.database_path,
        )["memory"]

        graph = build_operations_intelligence(
            project_id="auris-one", query="Northstar Labs", path=self.database_path
        )["graph"]
        company_node = next(item for item in graph["nodes"] if item["id"] == f"memory:{company['memory_id']}")
        self.assertEqual(company_node["type"], "organisation")
        self.assertIn(f"memory:{company['memory_id']}", graph["matched_node_ids"])
        self.assertTrue(
            any(
                edge["source"] == f"memory:{company['memory_id']}" and edge["relation"] == "context_for"
                for edge in graph["edges"]
            )
        )

        full_graph = build_operations_intelligence(
            project_id="auris-one", path=self.database_path
        )["graph"]
        protected_node = next(
            item for item in full_graph["nodes"] if item["id"] == f"memory:{protected['memory_id']}"
        )
        self.assertEqual(protected_node["label"], "Protected relationship memory")
        self.assertNotIn("acquisition", str(protected_node).casefold())
        self.assertNotIn("counterparty", str(protected_node).casefold())

    def test_private_session_suppresses_operational_detail(self):
        plan = create_task_plan("AURIS, research private roadmap").to_dict()
        save_task(plan, project_id="auris-one", path=self.database_path)

        intelligence = build_operations_intelligence(
            project_id="auris-one",
            query="roadmap",
            private=True,
            path=self.database_path,
        )

        self.assertEqual(intelligence["graph"]["nodes"], [])
        self.assertTrue(intelligence["graph"]["private_mode"])
        self.assertEqual(intelligence["daily"]["primary_objective"], "Private Session is active")
        self.assertEqual(intelligence["daily"]["schedule"], [])

    def test_evening_debrief_uses_recorded_failure_reason(self):
        completed = create_task_plan("AURIS, show system health").to_dict()
        failed = create_task_plan("AURIS, research unavailable source").to_dict()
        save_task(completed, project_id="auris-one", path=self.database_path)
        save_task(failed, project_id="auris-one", path=self.database_path)
        update_task_state(
            completed["task_id"], "completed", {"ok": True}, path=self.database_path
        )
        update_task_state(
            failed["task_id"],
            "failed",
            {"research_action": {"error": "Primary source timed out"}},
            path=self.database_path,
        )

        evening = build_operations_intelligence(
            project_id="auris-one", path=self.database_path
        )["evening"]

        self.assertTrue(any(item["task_id"] == completed["task_id"] for item in evening["completed"]))
        reason = next(item for item in evening["delay_reasons"] if item["task_id"] == failed["task_id"])
        self.assertEqual(reason["reason"], "Primary source timed out")
        self.assertTrue(any(item["source"] == "task_failure_evidence" for item in evening["lessons"]))

    def test_pending_sensitive_approval_is_ranked_from_risk_and_age(self):
        plan = create_task_plan("AURIS, send an email to person@example.com subject Test saying Hello").to_dict()
        save_task(plan, project_id="auris-one", path=self.database_path)
        approval = create_approval(
            plan["task_id"],
            "Send email",
            "person@example.com",
            "Draft body omitted",
            "sensitive",
            True,
            path=self.database_path,
        )

        attention = build_operations_intelligence(
            project_id="auris-one", path=self.database_path
        )["attention"]
        signal = next(item for item in attention["items"] if item["id"] == f"approval:{approval['approval_id']}")
        self.assertIn(signal["level"], {"IMPORTANT", "URGENT", "CRITICAL"})
        self.assertEqual(signal["source"], "approvals")
        self.assertIn(plan["task_id"], signal["evidence_ids"])


if __name__ == "__main__":
    unittest.main()
