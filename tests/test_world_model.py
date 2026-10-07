from __future__ import annotations

import unittest
from unittest.mock import patch

from auris.world_model import (
    WorldModelValidationError,
    analyse_causal_intervention,
    build_world_model,
    simulate_world_action,
)
from auris.server import AurisHandler


GRAPH = {
    "nodes": [
        {
            "id": "project:auris-one",
            "type": "project",
            "label": "AURIS One",
            "status": "current",
            "source": "projects",
            "provenance": "real_durable_state",
            "project_id": "auris-one",
            "metadata": {},
        },
        {
            "id": "task:42",
            "type": "task",
            "label": "Verify voice startup",
            "status": "running",
            "source": "tasks",
            "provenance": "real_durable_state",
            "project_id": "auris-one",
            "metadata": {"risk_level": "read_only"},
        },
        {
            "id": "approval:7",
            "type": "approval",
            "label": "Send report",
            "status": "pending",
            "source": "approvals",
            "provenance": "real_durable_state",
            "project_id": "auris-one",
            "metadata": {},
        },
    ],
    "edges": [
        {
            "id": "task:42|belongs_to|project:auris-one",
            "source": "task:42",
            "target": "project:auris-one",
            "relation": "belongs_to",
            "evidence_source": "tasks.project_id",
            "provenance": "real_durable_state",
        }
    ],
    "coverage": {"present_types": ["approval", "project", "task"]},
    "truncated": False,
}


class WorldModelTests(unittest.TestCase):
    @patch("auris.world_model.build_operations_graph", return_value=GRAPH)
    def test_snapshot_is_reproducible_and_grounded(self, _graph):
        first = build_world_model(project_id="auris-one")
        second = build_world_model(project_id="auris-one")

        self.assertEqual(first["snapshot_id"], second["snapshot_id"])
        self.assertFalse(first["learned_model"])
        self.assertEqual(first["provenance"], "real_durable_state")
        self.assertEqual(len(first["entities"]), 3)
        self.assertTrue(all(not item["executable"] for item in first["possible_actions"]))

    @patch("auris.world_model.build_operations_graph", return_value=GRAPH)
    def test_simulation_models_transition_without_execution(self, _graph):
        snapshot = build_world_model(project_id="auris-one")
        action = next(
            item for item in snapshot["possible_actions"] if item["action_type"] == "pause_task"
        )

        result = simulate_world_action(
            snapshot,
            action_id=action["action_id"],
            expected_snapshot_id=snapshot["snapshot_id"],
        )

        self.assertEqual(result["before"]["state"], "running")
        self.assertEqual(result["after"]["state"], "paused")
        self.assertIn("project:auris-one", result["impacted_entity_ids"])
        self.assertFalse(result["executed"])
        self.assertFalse(result["approval_requested"])
        self.assertTrue(result["advisory_only"])

    @patch("auris.world_model.build_operations_graph", return_value=GRAPH)
    def test_sensitive_transition_preserves_human_authority(self, _graph):
        snapshot = build_world_model(project_id="auris-one")
        action = next(
            item for item in snapshot["possible_actions"] if item["action_type"] == "approve_action"
        )

        self.assertTrue(action["approval_required"])
        self.assertEqual(action["risk_level"], "sensitive")
        self.assertFalse(action["executable"])

    @patch("auris.world_model.build_operations_graph", return_value=GRAPH)
    def test_stale_snapshot_is_rejected(self, _graph):
        snapshot = build_world_model(project_id="auris-one")

        with self.assertRaises(WorldModelValidationError):
            simulate_world_action(
                snapshot,
                action_id=snapshot["possible_actions"][0]["action_id"],
                expected_snapshot_id="obsolete-snapshot",
            )

    @patch(
        "auris.world_model.build_operations_graph",
        return_value={"nodes": [], "edges": [], "private_mode": True},
    )
    def test_private_mode_suppresses_world_state(self, _graph):
        snapshot = build_world_model(private=True)

        self.assertTrue(snapshot["private_mode"])
        self.assertEqual(snapshot["entities"], [])
        self.assertEqual(snapshot["possible_actions"], [])

    @patch("auris.world_model.build_operations_graph", return_value=GRAPH)
    def test_causal_intervention_separates_direct_effect_from_association(self, _graph):
        snapshot = build_world_model(project_id="auris-one")
        pause = next(item for item in snapshot["possible_actions"] if item["action_type"] == "pause_task")
        inspect = next(item for item in snapshot["possible_actions"] if item["action_type"] == "inspect_task")

        analysis = analyse_causal_intervention(
            snapshot,
            action_id=pause["action_id"],
            alternative_action_id=inspect["action_id"],
            expected_snapshot_id=snapshot["snapshot_id"],
        )

        self.assertEqual(analysis["intervention"]["notation"], "do(pause_task)")
        self.assertEqual(analysis["counterfactual"]["no_action_state"], "running")
        self.assertEqual(analysis["counterfactual"]["intervention_state"], "paused")
        self.assertEqual(analysis["counterfactual"]["alternative_state"], "running")
        self.assertEqual(analysis["identifiability"]["downstream_outcomes"], "not_identified")
        self.assertEqual(analysis["downstream_causal_effects"], [])
        self.assertFalse(analysis["correlation_treated_as_causation"])
        self.assertFalse(analysis["executed"])

    @patch("auris.world_model.build_operations_graph", return_value=GRAPH)
    def test_same_action_cannot_be_its_own_counterfactual(self, _graph):
        snapshot = build_world_model(project_id="auris-one")
        action_id = snapshot["possible_actions"][0]["action_id"]

        with self.assertRaises(WorldModelValidationError):
            analyse_causal_intervention(
                snapshot,
                action_id=action_id,
                alternative_action_id=action_id,
                expected_snapshot_id=snapshot["snapshot_id"],
            )


class _HandlerDouble:
    def __init__(self):
        self.payload = None
        self.status = None

    def _send_json(self, payload, status=200):
        self.payload = payload
        self.status = status


class WorldModelServerTests(unittest.TestCase):
    @patch("auris.server.record_event")
    @patch("auris.server.analyse_causal_intervention")
    @patch("auris.server.build_world_model", return_value={"snapshot_id": "snapshot-1"})
    def test_simulation_endpoint_audits_metadata_without_claiming_execution(
        self, _build, analyse, record_event
    ):
        analyse.return_value = {
            "analysis_id": "causal-1",
            "simulation": {
                "snapshot_id": "snapshot-1",
                "simulation_id": "simulation-1",
                "action": {"action_type": "pause_task", "risk_level": "controlled_write"},
                "executed": False,
            },
        }
        handler = _HandlerDouble()

        AurisHandler._handle_world_model_simulation(
            handler,
            {
                "snapshot_id": "snapshot-1",
                "action_id": "action:task:42:pause_task",
                "project_id": "auris-one",
            },
        )

        self.assertEqual(handler.status, 200)
        self.assertFalse(handler.payload["simulation"]["executed"])
        self.assertEqual(handler.payload["causal_analysis"]["analysis_id"], "causal-1")
        audit_payload = record_event.call_args.args[1]
        self.assertFalse(audit_payload["executed"])
        self.assertFalse(audit_payload["content_stored_in_audit"])

    @patch(
        "auris.server.analyse_causal_intervention",
        side_effect=WorldModelValidationError("The world-model snapshot changed."),
    )
    @patch("auris.server.build_world_model", return_value={"snapshot_id": "new"})
    def test_stale_simulation_endpoint_returns_conflict(self, _build, _analyse):
        handler = _HandlerDouble()

        AurisHandler._handle_world_model_simulation(
            handler,
            {"snapshot_id": "old", "action_id": "unknown"},
        )

        self.assertEqual(handler.status, 409)
        self.assertFalse(handler.payload["ok"])


if __name__ == "__main__":
    unittest.main()
