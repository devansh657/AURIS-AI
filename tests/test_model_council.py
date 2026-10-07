from __future__ import annotations

import unittest
from unittest.mock import patch

from auris.model_council import (
    CouncilValidationError,
    council_activation,
    run_model_council,
)


def _generator(role: str, _prompt: str, _latency_tier: str) -> dict:
    if role == "evidence_verifier":
        return {
            "summary": "The recommendation is supported by supplied evidence.",
            "recommendation": "",
            "assumptions": [],
            "evidence_gaps": [],
            "dissent": [],
            "confidence": "medium",
            "verdict": "supported",
            "model": "fixture-model",
        }
    return {
        "summary": f"{role} summary",
        "recommendation": "Use the reversible staged option.",
        "assumptions": ["The supplied scores are accurate"],
        "evidence_gaps": [],
        "dissent": ["Direct release remains faster"] if role == "judge" else [],
        "confidence": "medium",
        "verdict": "supported",
        "model": "fixture-model",
    }


class ModelCouncilTests(unittest.TestCase):
    def test_budget_blocks_council_before_any_model_call(self):
        decision = council_activation(
            requested=True, complexity=1.0, risk="critical", max_calls=4, token_budget=1400
        )

        self.assertFalse(decision["activate"])

    @patch(
        "auris.model_council.council_status",
        return_value={
            "available": True,
            "quality_model": "quality-model",
            "fast_model": "fast-model",
            "distinct_model_count": 2,
            "independent_models": True,
            "quality_warm": False,
            "quality_priming": True,
            "fast_warm": True,
            "warning": "Role separation only.",
        },
    )
    def test_startup_priming_returns_warming_without_model_call(self, _status):
        result = run_model_council(
            "Choose a reversible deployment strategy",
            requested=True,
        )

        self.assertFalse(result["activated"])
        self.assertEqual(result["state"], "warming")
        self.assertIn("retry", result["reason"].casefold())

    @patch(
        "auris.model_council.council_status",
        return_value={
            "available": True,
            "quality_model": "fixture-model",
            "fast_model": None,
            "distinct_model_count": 1,
            "independent_models": False,
            "warning": "Role separation only.",
        },
    )
    def test_five_role_council_reports_non_independence_and_verified_result(self, _status):
        result = run_model_council(
            "Choose a reversible deployment strategy",
            requested=True,
            generator=_generator,
        )

        self.assertTrue(result["activated"])
        self.assertEqual(result["calls_used"], 5)
        self.assertEqual(set(result["roles"]), {
            "solver_a", "solver_b", "critic", "judge", "evidence_verifier"
        })
        self.assertEqual(result["final"]["status"], "supported")
        self.assertFalse(result["independent_models"])
        self.assertFalse(result["security_policy_modified"])

    @patch(
        "auris.model_council.council_status",
        return_value={
            "available": True,
            "quality_model": "fixture-model",
            "fast_model": None,
            "distinct_model_count": 1,
            "independent_models": False,
            "warning": "Role separation only.",
        },
    )
    def test_verifier_withholds_unsupported_judge_recommendation(self, _status):
        def uncertain(role: str, prompt: str, tier: str) -> dict:
            value = _generator(role, prompt, tier)
            if role == "evidence_verifier":
                value["verdict"] = "uncertain"
                value["evidence_gaps"] = ["Independent deployment history"]
            return value

        result = run_model_council(
            "Choose a deployment strategy", requested=True, generator=uncertain
        )

        self.assertEqual(result["final"]["status"], "withheld")
        self.assertIsNone(result["final"]["recommendation"])

    def test_short_problem_is_rejected(self):
        with self.assertRaises(CouncilValidationError):
            run_model_council("why")


if __name__ == "__main__":
    unittest.main()
