from __future__ import annotations

import math
import re
from typing import Any


MAX_OPTIONS = 8
MAX_CRITERIA = 12
MAX_HYPOTHESES = 12
MAX_EVIDENCE = 48
MAX_SCENARIOS_PER_OPTION = 4

EVIDENCE_WEIGHTS = {"low": 1.0, "medium": 2.0, "high": 3.0}
SCENARIO_NAMES = {"best", "expected", "adverse", "extreme"}


class DecisionValidationError(ValueError):
    pass


def match_decision_command(command: str) -> dict[str, Any] | None:
    text = _normalise_command(command)
    patterns = (
        (r"(?:compare|evaluate)\s+(.+?)\s+(?:versus|vs\.?|against)\s+(.+)", "comparison"),
        (r"should i\s+(.+?)\s+or\s+(.+)", "choice"),
        (r"what (?:would happen|happens) if\s+(.+?)\s+instead of\s+(.+)", "counterfactual"),
    )
    for pattern, mode in patterns:
        matched = re.fullmatch(pattern, text, flags=re.IGNORECASE)
        if matched:
            first = _clean_text(matched.group(1), 180)
            second = _clean_text(matched.group(2), 180)
            if first and second:
                return {
                    "objective": _clean_text(text, 800),
                    "mode": mode,
                    "options": [{"name": first}, {"name": second}],
                }
    if re.search(
        r"\b(decision analysis|analyse (?:this )?decision|analyze (?:this )?decision|"
        r"scenario analysis|test (?:this )?hypothesis)\b",
        text,
        flags=re.IGNORECASE,
    ):
        return {"objective": _clean_text(text, 800), "mode": "analysis", "options": []}
    return None


def analyse_decision(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise DecisionValidationError("Decision input must be a JSON object.")
    objective = _required_text(payload.get("objective"), "objective", 1000)
    criteria = _normalise_criteria(payload.get("criteria", []))
    options = _normalise_options(payload.get("options", []), criteria)
    hypotheses = _normalise_hypotheses(payload.get("hypotheses", []))
    evidence = _normalise_evidence(payload.get("evidence", []), hypotheses)
    assumptions = _text_list(payload.get("assumptions", []), "assumptions", 16, 300)
    unknowns = _text_list(payload.get("unknowns", []), "unknowns", 16, 300)

    hypothesis_results = [
        _evaluate_hypothesis(hypothesis, evidence) for hypothesis in hypotheses
    ]
    option_results = [_evaluate_option(option, criteria) for option in options]
    counterfactuals = _counterfactuals(option_results)
    recommendation = _recommend(option_results, hypothesis_results, unknowns)
    confidence = _confidence_state(recommendation, hypothesis_results, evidence, unknowns)
    missing_evidence = _missing_evidence(
        criteria, option_results, hypotheses, hypothesis_results, unknowns
    )
    checks = {
        "objective_present": True,
        "two_or_more_options": len(options) >= 2,
        "criteria_declared": bool(criteria),
        "option_scores_complete": bool(option_results)
        and all(item["score_complete"] for item in option_results),
        "score_provenance_present": bool(option_results)
        and all(not item["scores"] or bool(item["score_source"]) for item in option_results),
        "hypotheses_tested": bool(hypothesis_results),
        "counterevidence_considered": any(
            item["stance"] == "oppose" for item in evidence
        ),
        "scenario_probabilities_valid": bool(option_results)
        and all(item["scenario_analysis"]["valid"] for item in option_results),
        "recommendation_supported": recommendation["status"] == "supported",
    }
    return {
        "objective": objective,
        "mode": _clean_text(payload.get("mode") or "decision", 40),
        "epistemic_status": _epistemic_status(hypothesis_results, evidence, option_results),
        "confidence": confidence,
        "recommendation": recommendation,
        "options": option_results,
        "hypotheses": hypothesis_results,
        "evidence": evidence,
        "counterfactuals": counterfactuals,
        "assumptions": assumptions,
        "unknowns": unknowns,
        "missing_evidence": missing_evidence,
        "quality_checks": checks,
        "model_council": {
            "activated": False,
            "state": "not_connected",
            "reason": "This analysis used the deterministic evidence evaluator; no independent model council was invoked.",
        },
        "method": {
            "criterion_scale": "0 to 5; higher is better",
            "criterion_score": "weighted arithmetic mean over user-supplied scores",
            "evidence_score": "support minus opposition using low=1, medium=2, high=3 reliability weights",
            "scenario_utility": "impact - 0.4*cost - 0.2*time + 0.2*reversibility - risk",
            "probabilities": "AURIS never invents missing scenario or success probabilities.",
        },
        "verification": (
            "The analysis is reproducible from the returned inputs and method. No external action was executed, "
            "no hidden chain-of-thought is exposed, and missing evidence remains explicit."
        ),
    }


def _normalise_command(command: str) -> str:
    text = " ".join(str(command).strip().split()).strip(" .")
    text = re.sub(r"^(?:hey\s+)?auris\s*[,;:]?\s*", "", text, flags=re.IGNORECASE)
    return text


def _normalise_criteria(value: Any) -> list[dict[str, Any]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > MAX_CRITERIA:
        raise DecisionValidationError(f"criteria must be a list of at most {MAX_CRITERIA} items.")
    criteria: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DecisionValidationError(f"criteria[{index}] must be an object.")
        name = _required_text(item.get("name"), f"criteria[{index}].name", 80)
        key = name.casefold()
        if key in names:
            raise DecisionValidationError(f"Duplicate criterion: {name}.")
        names.add(key)
        criteria.append({"name": name, "weight": _number(item.get("weight", 1), 0.1, 10, f"criteria[{index}].weight")})
    return criteria


def _normalise_options(value: Any, criteria: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > MAX_OPTIONS:
        raise DecisionValidationError(f"options must be a list of at most {MAX_OPTIONS} items.")
    options: list[dict[str, Any]] = []
    names: set[str] = set()
    criterion_names = {item["name"] for item in criteria}
    for index, raw in enumerate(value):
        item = {"name": raw} if isinstance(raw, str) else raw
        if not isinstance(item, dict):
            raise DecisionValidationError(f"options[{index}] must be text or an object.")
        name = _required_text(item.get("name"), f"options[{index}].name", 180)
        if name.casefold() in names:
            raise DecisionValidationError(f"Duplicate option: {name}.")
        names.add(name.casefold())
        raw_scores = item.get("scores", {})
        if not isinstance(raw_scores, dict):
            raise DecisionValidationError(f"options[{index}].scores must be an object.")
        unknown_scores = set(raw_scores) - criterion_names
        if unknown_scores:
            raise DecisionValidationError(f"Unknown criteria for {name}: {', '.join(sorted(unknown_scores))}.")
        scores = {
            criterion: _number(score, 0, 5, f"options[{index}].scores.{criterion}")
            for criterion, score in raw_scores.items()
        }
        score_source = (
            _required_text(item.get("score_source"), f"options[{index}].score_source", 300)
            if scores
            else None
        )
        probability = item.get("success_probability")
        if probability is not None:
            probability = _number(probability, 0, 1, f"options[{index}].success_probability")
            probability_source = _required_text(
                item.get("probability_source"), f"options[{index}].probability_source", 300
            )
        else:
            probability_source = None
        options.append(
            {
                "name": name,
                "scores": scores,
                "score_source": score_source,
                "success_probability": probability,
                "probability_source": probability_source,
                "scenarios": _normalise_scenarios(item.get("scenarios", []), index),
            }
        )
    return options


def _normalise_scenarios(value: Any, option_index: int) -> list[dict[str, Any]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > MAX_SCENARIOS_PER_OPTION:
        raise DecisionValidationError(
            f"options[{option_index}].scenarios must contain at most {MAX_SCENARIOS_PER_OPTION} items."
        )
    scenarios: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DecisionValidationError(f"options[{option_index}].scenarios[{index}] must be an object.")
        name = _required_text(item.get("name"), "scenario.name", 20).casefold()
        if name not in SCENARIO_NAMES or name in names:
            raise DecisionValidationError("Scenario names must be unique best, expected, adverse, or extreme values.")
        names.add(name)
        scenarios.append(
            {
                "name": name,
                "probability": _number(item.get("probability"), 0, 1, "scenario.probability"),
                "impact": _number(item.get("impact"), -5, 5, "scenario.impact"),
                "cost": _number(item.get("cost", 0), 0, 5, "scenario.cost"),
                "time": _number(item.get("time", 0), 0, 5, "scenario.time"),
                "reversibility": _number(item.get("reversibility", 0), 0, 5, "scenario.reversibility"),
                "risk": _number(item.get("risk", 0), 0, 5, "scenario.risk"),
                "assumptions": _text_list(item.get("assumptions", []), "scenario.assumptions", 8, 200),
            }
        )
    return scenarios


def _normalise_hypotheses(value: Any) -> list[dict[str, Any]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > MAX_HYPOTHESES:
        raise DecisionValidationError(f"hypotheses must be a list of at most {MAX_HYPOTHESES} items.")
    hypotheses: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DecisionValidationError(f"hypotheses[{index}] must be an object.")
        hypothesis_id = _identifier(item.get("id") or f"H{index + 1}", f"hypotheses[{index}].id")
        if hypothesis_id in ids:
            raise DecisionValidationError(f"Duplicate hypothesis id: {hypothesis_id}.")
        ids.add(hypothesis_id)
        hypotheses.append(
            {
                "id": hypothesis_id,
                "statement": _required_text(item.get("statement"), f"hypotheses[{index}].statement", 500),
                "expected_evidence": _text_list(item.get("expected_evidence", []), "expected_evidence", 8, 250),
            }
        )
    return hypotheses


def _normalise_evidence(value: Any, hypotheses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > MAX_EVIDENCE:
        raise DecisionValidationError(f"evidence must be a list of at most {MAX_EVIDENCE} items.")
    hypothesis_ids = {item["id"] for item in hypotheses}
    evidence: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DecisionValidationError(f"evidence[{index}] must be an object.")
        evidence_id = _identifier(item.get("id") or f"E{index + 1}", f"evidence[{index}].id")
        hypothesis_id = _identifier(item.get("hypothesis_id"), f"evidence[{index}].hypothesis_id")
        if evidence_id in ids or hypothesis_id not in hypothesis_ids:
            raise DecisionValidationError(f"Evidence {evidence_id} has a duplicate id or unknown hypothesis.")
        ids.add(evidence_id)
        stance = _required_text(item.get("stance"), f"evidence[{index}].stance", 12).casefold()
        reliability = _required_text(item.get("reliability"), f"evidence[{index}].reliability", 12).casefold()
        if stance not in {"support", "oppose"} or reliability not in EVIDENCE_WEIGHTS:
            raise DecisionValidationError("Evidence stance must be support/oppose and reliability low/medium/high.")
        evidence.append(
            {
                "id": evidence_id,
                "hypothesis_id": hypothesis_id,
                "statement": _required_text(item.get("statement"), f"evidence[{index}].statement", 500),
                "stance": stance,
                "reliability": reliability,
                "source": _required_text(item.get("source"), f"evidence[{index}].source", 300),
                "provenance": _required_text(item.get("provenance"), f"evidence[{index}].provenance", 300),
            }
        )
    return evidence


def _evaluate_hypothesis(hypothesis: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    linked = [item for item in evidence if item["hypothesis_id"] == hypothesis["id"]]
    support = sum(EVIDENCE_WEIGHTS[item["reliability"]] for item in linked if item["stance"] == "support")
    oppose = sum(EVIDENCE_WEIGHTS[item["reliability"]] for item in linked if item["stance"] == "oppose")
    if support >= 3 and oppose >= 3:
        status = "disputed"
    elif support - oppose >= 3:
        status = "supported"
    elif oppose - support >= 3:
        status = "rejected"
    else:
        status = "uncertain"
    balance = abs(support - oppose)
    confidence = "high" if len(linked) >= 3 and balance >= 5 else "medium" if len(linked) >= 2 and balance >= 2 else "low"
    return {
        **hypothesis,
        "status": status,
        "confidence": confidence,
        "support_weight": support,
        "opposition_weight": oppose,
        "evidence_ids": [item["id"] for item in linked],
        "counterevidence_present": any(item["stance"] == "oppose" for item in linked),
    }


def _evaluate_option(option: dict[str, Any], criteria: list[dict[str, Any]]) -> dict[str, Any]:
    weights = {item["name"]: item["weight"] for item in criteria}
    available_weight = sum(weights[name] for name in option["scores"])
    total_weight = sum(weights.values())
    weighted_score = None
    if available_weight:
        weighted_score = sum(option["scores"][name] * weights[name] for name in option["scores"]) / available_weight
    scenario_analysis = _evaluate_scenarios(option["scenarios"])
    return {
        **option,
        "weighted_score": round(weighted_score, 4) if weighted_score is not None else None,
        "score_coverage": round(available_weight / total_weight, 4) if total_weight else 0.0,
        "score_complete": bool(total_weight) and math.isclose(available_weight, total_weight),
        "scenario_analysis": scenario_analysis,
    }


def _evaluate_scenarios(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    if not scenarios:
        return {"valid": False, "complete": False, "probability_sum": 0.0, "expected_utility": None, "items": []}
    items = []
    for scenario in scenarios:
        utility = (
            scenario["impact"]
            - 0.4 * scenario["cost"]
            - 0.2 * scenario["time"]
            + 0.2 * scenario["reversibility"]
            - scenario["risk"]
        )
        items.append({**scenario, "utility": round(utility, 4)})
    probability_sum = sum(item["probability"] for item in items)
    valid = math.isclose(probability_sum, 1.0, abs_tol=0.01)
    expected_utility = sum(item["probability"] * item["utility"] for item in items) if valid else None
    return {
        "valid": valid,
        "complete": {item["name"] for item in items} == SCENARIO_NAMES,
        "probability_sum": round(probability_sum, 4),
        "expected_utility": round(expected_utility, 4) if expected_utility is not None else None,
        "items": items,
    }


def _counterfactuals(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for baseline in options:
        for alternative in options:
            if baseline["name"] == alternative["name"]:
                continue
            score_delta = None
            if baseline["weighted_score"] is not None and alternative["weighted_score"] is not None:
                score_delta = round(alternative["weighted_score"] - baseline["weighted_score"], 4)
            scenario_delta = None
            left = baseline["scenario_analysis"]["expected_utility"]
            right = alternative["scenario_analysis"]["expected_utility"]
            if left is not None and right is not None:
                scenario_delta = round(right - left, 4)
            results.append(
                {
                    "baseline": baseline["name"],
                    "alternative": alternative["name"],
                    "criterion_score_delta": score_delta,
                    "expected_scenario_utility_delta": scenario_delta,
                    "changed_assumptions": sorted(
                        {
                            assumption
                            for item in alternative["scenario_analysis"]["items"]
                            for assumption in item["assumptions"]
                        }
                    ),
                }
            )
    return results


def _recommend(options: list[dict[str, Any]], hypotheses: list[dict[str, Any]], unknowns: list[str]) -> dict[str, Any]:
    ranked = [item for item in options if item["score_complete"] and item["weighted_score"] is not None]
    ranked.sort(key=lambda item: item["weighted_score"], reverse=True)
    if len(ranked) < 2:
        return {"status": "inconclusive", "option": None, "reason": "At least two completely scored options are required.", "forecast_probability": None, "probability_source": None}
    gap = ranked[0]["weighted_score"] - ranked[1]["weighted_score"]
    disputed = any(item["status"] == "disputed" for item in hypotheses)
    if gap < 0.25 or disputed or unknowns:
        reasons = []
        if gap < 0.25:
            reasons.append("the leading score margin is below 0.25")
        if disputed:
            reasons.append("material evidence is disputed")
        if unknowns:
            reasons.append("declared unknowns remain")
        return {"status": "inconclusive", "option": None, "reason": "; ".join(reasons).capitalize() + ".", "forecast_probability": None, "probability_source": None}
    winner = ranked[0]
    return {
        "status": "supported",
        "option": winner["name"],
        "reason": f"It leads the complete weighted criteria by {gap:.2f} points.",
        "forecast_probability": winner["success_probability"],
        "probability_source": winner["probability_source"],
    }


def _confidence_state(recommendation: dict[str, Any], hypotheses: list[dict[str, Any]], evidence: list[dict[str, Any]], unknowns: list[str]) -> str:
    if recommendation["status"] != "supported" or unknowns:
        return "low"
    if hypotheses and all(item["confidence"] == "high" and item["status"] in {"supported", "rejected"} for item in hypotheses) and len(evidence) >= 4:
        return "high"
    return "medium"


def _epistemic_status(
    hypotheses: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    options: list[dict[str, Any]],
) -> str:
    if not evidence:
        if options and all(item["score_complete"] for item in options):
            return "inferred"
        return "hypothesis" if hypotheses else "unknown"
    statuses = {item["status"] for item in hypotheses}
    if "disputed" in statuses:
        return "disputed"
    if statuses and statuses <= {"supported", "rejected"}:
        return "supported"
    return "inferred"


def _missing_evidence(criteria: list[dict[str, Any]], options: list[dict[str, Any]], hypotheses: list[dict[str, Any]], results: list[dict[str, Any]], unknowns: list[str]) -> list[str]:
    missing = list(unknowns)
    if len(options) < 2:
        missing.append("Define at least two alternatives.")
    if not criteria:
        missing.append("Define weighted decision criteria.")
    for option in options:
        if not option["score_complete"]:
            missing.append(f"Complete criterion scores for {option['name']}.")
        if not option["scenario_analysis"]["valid"]:
            missing.append(f"Provide scenario probabilities totalling 1.0 for {option['name']}.")
    linked = {item["id"]: result for item, result in zip(hypotheses, results)}
    for hypothesis in hypotheses:
        result = linked[hypothesis["id"]]
        if not result["evidence_ids"]:
            missing.append(f"Provide traceable evidence for hypothesis {hypothesis['id']}.")
        if not result["counterevidence_present"]:
            missing.append(f"Search for counterevidence against hypothesis {hypothesis['id']}.")
    return list(dict.fromkeys(missing))[:40]


def _text_list(value: Any, field: str, maximum_items: int, maximum_length: int) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > maximum_items:
        raise DecisionValidationError(f"{field} must be a list of at most {maximum_items} items.")
    return [_required_text(item, f"{field}[{index}]", maximum_length) for index, item in enumerate(value)]


def _identifier(value: Any, field: str) -> str:
    text = _required_text(value, field, 40)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,39}", text):
        raise DecisionValidationError(f"{field} contains unsupported characters.")
    return text


def _required_text(value: Any, field: str, limit: int) -> str:
    text = _clean_text(value, limit)
    if not text:
        raise DecisionValidationError(f"{field} is required.")
    return text


def _clean_text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").replace("\x00", " ").split())[:limit].strip()


def _number(value: Any, minimum: float, maximum: float, field: str) -> float:
    if isinstance(value, bool):
        raise DecisionValidationError(f"{field} must be a number between {minimum} and {maximum}.")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise DecisionValidationError(f"{field} must be a number between {minimum} and {maximum}.") from error
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise DecisionValidationError(f"{field} must be a number between {minimum} and {maximum}.")
    return number
