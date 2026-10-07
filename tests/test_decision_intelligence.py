from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auris.database import (
    decision_calibration_summary,
    decision_outcome_learning_summary,
    get_decision_case,
    record_decision_outcome,
    save_decision_case,
)
from auris.decision_intelligence import (
    DecisionValidationError,
    analyse_decision,
    match_decision_command,
)
from auris.runtime import _execute_supported
from auris.schemas import TaskState
from auris.server import AurisHandler
from auris.supervisor import create_task_plan


def _scenarios(shift: float = 0.0) -> list[dict]:
    return [
        {"name": "best", "probability": 0.15, "impact": 5 + shift, "cost": 1, "time": 1, "reversibility": 4, "risk": 1},
        {"name": "expected", "probability": 0.55, "impact": 3 + shift, "cost": 2, "time": 2, "reversibility": 3, "risk": 1},
        {"name": "adverse", "probability": 0.25, "impact": 0 + shift, "cost": 3, "time": 3, "reversibility": 2, "risk": 3},
        {"name": "extreme", "probability": 0.05, "impact": -4 + shift, "cost": 5, "time": 5, "reversibility": 1, "risk": 5},
    ]


def _complete_input() -> dict:
    return {
        "objective": "Choose the safer deployment strategy",
        "criteria": [
            {"name": "reliability", "weight": 3},
            {"name": "speed", "weight": 1},
        ],
        "options": [
            {
                "name": "Blue-green",
                "scores": {"reliability": 5, "speed": 3},
                "score_source": "Architecture review",
                "success_probability": 0.82,
                "probability_source": "Observed internal deployment history",
                "scenarios": _scenarios(0),
            },
            {
                "name": "In-place",
                "scores": {"reliability": 2, "speed": 5},
                "score_source": "Architecture review",
                "success_probability": 0.60,
                "probability_source": "Observed internal deployment history",
                "scenarios": _scenarios(-0.5),
            },
        ],
        "hypotheses": [
            {
                "id": "H1",
                "statement": "Blue-green reduces rollback risk",
                "expected_evidence": ["Rollback duration records"],
            }
        ],
        "evidence": [
            {
                "id": "E1",
                "hypothesis_id": "H1",
                "statement": "Past blue-green rollback completed in two minutes",
                "stance": "support",
                "reliability": "high",
                "source": "deployment ledger",
                "provenance": "run-42",
            },
            {
                "id": "E2",
                "hypothesis_id": "H1",
                "statement": "A second rollback completed without data loss",
                "stance": "support",
                "reliability": "medium",
                "source": "incident review",
                "provenance": "incident-17",
            },
            {
                "id": "E3",
                "hypothesis_id": "H1",
                "statement": "One cutover briefly doubled database load",
                "stance": "oppose",
                "reliability": "low",
                "source": "metrics archive",
                "provenance": "metrics-9",
            },
        ],
    }


class DecisionIntelligenceTests(unittest.TestCase):
    def test_complete_evidence_produces_reproducible_recommendation(self):
        analysis = analyse_decision(_complete_input())

        self.assertEqual(analysis["recommendation"]["status"], "supported")
        self.assertEqual(analysis["recommendation"]["option"], "Blue-green")
        self.assertEqual(analysis["recommendation"]["forecast_probability"], 0.82)
        self.assertEqual(analysis["epistemic_status"], "supported")
        self.assertEqual(analysis["hypotheses"][0]["status"], "supported")
        self.assertTrue(analysis["hypotheses"][0]["counterevidence_present"])
        self.assertTrue(analysis["quality_checks"]["scenario_probabilities_valid"])
        self.assertGreater(analysis["counterfactuals"][0]["criterion_score_delta"], -5)
        self.assertFalse(analysis["model_council"]["activated"])

    def test_natural_comparison_withholds_unsupported_recommendation(self):
        payload = match_decision_command("AURIS, compare option A versus option B")
        analysis = analyse_decision(payload)

        self.assertEqual([item["name"] for item in analysis["options"]], ["option A", "option B"])
        self.assertEqual(analysis["recommendation"]["status"], "inconclusive")
        self.assertIsNone(analysis["recommendation"]["forecast_probability"])
        self.assertIn("Define weighted decision criteria.", analysis["missing_evidence"])

    def test_probability_requires_provenance(self):
        payload = _complete_input()
        payload["options"][0].pop("probability_source")

        with self.assertRaises(DecisionValidationError):
            analyse_decision(payload)

    def test_invalid_scenario_probability_is_explicit_not_normalised(self):
        payload = _complete_input()
        payload["options"][0]["scenarios"][0]["probability"] = 0.50

        analysis = analyse_decision(payload)

        self.assertFalse(analysis["options"][0]["scenario_analysis"]["valid"])
        self.assertIsNone(analysis["options"][0]["scenario_analysis"]["expected_utility"])


class DecisionPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "decision.db"

    def tearDown(self):
        self.temp.cleanup()

    def test_outcome_scoring_is_empirical_and_sample_gated(self):
        decision_input = _complete_input()
        analysis = analyse_decision(decision_input)
        decision = save_decision_case(decision_input, analysis, project_id="auris-one", path=self.path)

        outcome = record_decision_outcome(
            decision["case_id"],
            actual_success=True,
            actual_summary="Deployment passed all health checks.",
            expected_summary="Healthy deployment",
            difference_summary="No material variance",
            root_cause="Staged traffic shift",
            lesson="Preserve staged verification",
            confidence_update="increased",
            path=self.path,
        )
        reloaded = get_decision_case(decision["case_id"], path=self.path)
        calibration = decision_calibration_summary(path=self.path)
        learning = decision_outcome_learning_summary(path=self.path)

        self.assertTrue(outcome["actual_success"])
        self.assertEqual(reloaded["status"], "observed")
        self.assertEqual(len(reloaded["outcomes"]), 1)
        self.assertEqual(calibration["probabilistic_forecasts_scored"], 1)
        self.assertAlmostEqual(calibration["brier_score"], (0.82 - 1) ** 2)
        self.assertFalse(calibration["calibrated"])
        self.assertEqual(outcome["lesson"], "Preserve staged verification")
        self.assertEqual(learning["recent_lessons"], ["Preserve staged verification"])
        self.assertFalse(learning["option_performance"][0]["sample_sufficient"])
        self.assertIsNone(learning["option_performance"][0]["observed_success_rate"])
        self.assertFalse(learning["automatic_policy_changes"])

    def test_outcome_learning_releases_rate_only_after_five_observations(self):
        analysis = analyse_decision(_complete_input())
        decision = save_decision_case(_complete_input(), analysis, path=self.path)
        for index in range(5):
            record_decision_outcome(
                decision["case_id"],
                actual_success=index < 4,
                actual_summary=f"Observation {index}",
                confidence_update="unchanged",
                path=self.path,
            )

        learning = decision_outcome_learning_summary(path=self.path)

        self.assertTrue(learning["option_performance"][0]["sample_sufficient"])
        self.assertEqual(learning["option_performance"][0]["observed_success_rate"], 0.8)

    def test_invalid_confidence_update_is_rejected(self):
        analysis = analyse_decision(_complete_input())
        decision = save_decision_case(_complete_input(), analysis, path=self.path)

        with self.assertRaises(ValueError):
            record_decision_outcome(
                decision["case_id"],
                actual_success=True,
                actual_summary="Observed",
                confidence_update="rewrite-security-policy",
                path=self.path,
            )


class DecisionRoutingTests(unittest.TestCase):
    def test_supervisor_routes_counterfactual_to_decision_agent(self):
        plan = create_task_plan("AURIS, what happens if I choose B instead of A")

        self.assertEqual(plan.task_type, "decision_analysis")
        self.assertIn("decision_agent", plan.required_agents)
        self.assertTrue(any("probability" in item for item in plan.success_conditions))

    @patch("auris.runtime.record_event")
    @patch("auris.runtime.save_decision_case")
    def test_voice_style_comparison_creates_partial_case_without_guessing(self, save_case, _event):
        save_case.return_value = {"case_id": "case-1"}

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "decision_analysis"},
            "AURIS, compare option A versus option B",
            "auris-one",
            False,
            "command",
            "conversation",
        )

        self.assertEqual(state, TaskState.PARTIALLY_COMPLETED)
        self.assertEqual(result["decision_case"]["case_id"], "case-1")
        self.assertIsNone(result["decision_analysis"]["recommendation"]["option"])


class _HandlerDouble:
    def __init__(self):
        self.payload = None
        self.status = None

    def _send_json(self, payload, status=200):
        self.payload = payload
        self.status = status


class DecisionServerTests(unittest.TestCase):
    @patch("auris.server.record_event")
    @patch("auris.server.save_decision_case")
    def test_private_analysis_is_ephemeral(self, save_case, _event):
        handler = _HandlerDouble()

        AurisHandler._handle_decision_analysis(
            handler,
            {"objective": "Compare private alternatives", "options": ["A", "B"], "private": True},
        )

        self.assertEqual(handler.status, 200)
        self.assertTrue(handler.payload["private"])
        self.assertIsNone(handler.payload["decision"])
        save_case.assert_not_called()

    def test_invalid_decision_returns_400(self):
        handler = _HandlerDouble()

        AurisHandler._handle_decision_analysis(handler, {"objective": ""})

        self.assertEqual(handler.status, 400)
        self.assertFalse(handler.payload["ok"])

    @patch("auris.server.record_event")
    @patch("auris.server.decision_outcome_learning_summary", return_value={"observations": 1})
    @patch("auris.server.decision_calibration_summary", return_value={"calibrated": False})
    @patch("auris.server.record_decision_outcome")
    def test_outcome_endpoint_requires_boolean_and_records_content_only_in_case_store(
        self, record_outcome, _calibration, _learning, record_event
    ):
        record_outcome.return_value = {
            "outcome_id": "outcome-1",
            "case_id": "case-1",
            "actual_success": True,
        }
        handler = _HandlerDouble()

        AurisHandler._handle_decision_outcome(
            handler,
            "/api/decisions/case-1/outcomes",
            {"actual_success": True, "actual_summary": "Observed result"},
        )

        self.assertEqual(handler.status, 201)
        self.assertTrue(handler.payload["ok"])
        self.assertNotIn("actual_summary", record_event.call_args.args[1])
        self.assertEqual(handler.payload["outcome_learning"]["observations"], 1)

        invalid = _HandlerDouble()
        AurisHandler._handle_decision_outcome(
            invalid,
            "/api/decisions/case-1/outcomes",
            {"actual_success": "true", "actual_summary": "Observed result"},
        )
        self.assertEqual(invalid.status, 400)


if __name__ == "__main__":
    unittest.main()
