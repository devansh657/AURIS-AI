from __future__ import annotations

import re

from auris.capabilities import capabilities_for_task
from auris.application_state import match_application_state_command
from auris.browser_agent import is_browser_command
from auris.coding_agent import match_coding_command
from auris.communications_agent import match_communication_command
from auris.device_agent import is_device_command, is_named_browser_command
from auris.decision_intelligence import match_decision_command
from auris.document_agent import match_document_command
from auris.event_engine import parse_reminder
from auris.proactive_agent import parse_watch_command
from auris.interaction_agent import is_typing_intent
from auris.file_agent import match_file_search
from auris.policy import classify_command
from auris.project_agent import match_project_open_command
from auris.schemas import RiskLevel, TaskPlan, TaskState, TaskStep, new_id
from auris.screen_context import is_screen_command
from auris.ui_automation import is_ui_control_intent
from auris.work_product_agent import match_work_product_command


def create_task_plan(command: str) -> TaskPlan:
    decision = classify_command(command)
    task_type = _infer_task_type(command)
    communication = match_communication_command(command)
    capabilities = capabilities_for_task(task_type, coding_operation=match_coding_command(command),
                                        communication_operation=communication.kind if communication else None)
    required_agents = _agents_for(task_type, decision.risk_level)
    approval_points = _approval_points(decision)
    if task_type == "coding" and match_coding_command(command) == "repair_test":
        approval_points.append(
            "Require one-time approval only after a signed diff passes targeted and complete isolated tests."
        )
    if task_type == "coding" and match_coding_command(command) == "codex_workspace":
        approval_points.append(
            "Require one-time approval only after Codex finishes in isolation and the exact signed diff passes independent validation."
        )

    if not decision.allowed_to_plan:
        state = TaskState.BLOCKED
    elif decision.requires_approval:
        state = TaskState.AWAITING_APPROVAL
    else:
        state = TaskState.CREATED
    steps = [] if not decision.allowed_to_plan else _steps_for(command, task_type, required_agents)

    return TaskPlan(
        task_id=new_id(),
        objective=_clean_objective(command),
        task_type=task_type,
        risk_level=decision.risk_level,
        required_agents=required_agents,
        steps=steps,
        approval_points=approval_points,
        success_conditions=_success_conditions(task_type, decision.risk_level, command)
        + [f"Capability scope [{item.id}]: {item.scope}" for item in capabilities],
        state=state,
        capability_ids=[item.id for item in capabilities],
    )


def _clean_objective(command: str) -> str:
    cleaned = command.strip()
    prefixes = ("auris,", "auris", "hey auris,", "hey auris")
    lowered = cleaned.lower()
    for prefix in prefixes:
        if lowered.startswith(prefix):
            return cleaned[len(prefix) :].strip(" ,")
    return cleaned


def _infer_task_type(command: str) -> str:
    text = command.lower()
    clean = " ".join(text.replace(",", " ").split())
    for prefix in ("hey auris ", "auris "):
        if clean.startswith(prefix):
            clean = clean[len(prefix) :]
            break
    if clean.strip(" .") in {"stop", "emergency stop", "resume", "resume operations", "resume auris"}:
        return "control"
    if re.fullmatch(
        r"(?:prepare|show|give me|generate)?\s*(?:(?:my|the)\s+)?"
        r"(?:(?:morning|daily)\s+brief(?:ing)?|evening\s+debrief)",
        clean.strip(" ."),
    ):
        return "daily_brief"
    if match_coding_command(command) == "codex_workspace":
        return "coding"
    if match_application_state_command(command) is not None:
        return "application_state"
    if _contains_any(
        clean,
        (
            "needs my attention",
            "attention radar",
            "operations graph",
            "operations intelligence",
            "everything related to",
            "everything connected to",
            "opportunity radar",
            "show opportunities",
        ),
    ):
        return "operations_intelligence"
    if match_decision_command(command) is not None:
        return "decision_analysis"
    if match_communication_command(command) is not None:
        return "communications"
    if match_project_open_command(command) is not None:
        return "project_operation"
    if is_screen_command(command):
        return "screen_understanding"
    if match_file_search(command) is not None:
        return "file_workflow"
    if match_work_product_command(command) is not None:
        return "work_product"
    if is_named_browser_command(command):
        return "computer_operation"
    if is_browser_command(command):
        return "browser_workflow"
    if match_coding_command(command) is not None:
        return "coding"
    if match_document_command(command) is not None:
        return "document_workflow"
    if parse_watch_command(command) is not None:
        return "proactive_watch"
    if parse_reminder(command) is not None:
        return "reminder"
    if is_typing_intent(command) or is_ui_control_intent(command):
        return "computer_interaction"
    if is_device_command(command):
        return "computer_operation"
    if _contains_any(text, ("research", "source", "citation", "evidence")):
        return "research"
    if _contains_any(text, ("remember", "memory", "forget", "recall", "record decision")):
        return "memory"
    if _contains_any(text, ("code", "test", "tests", "test suite", "bug", "repository", "repo", "fix")):
        return "coding"
    if _contains_any(text, ("file", "document", "folder", "organise", "organize")):
        return "file_workflow"
    if _contains_any(text, ("browser", "website", "link", "portfolio")):
        return "browser_workflow"
    if _contains_any(text, ("email", "message", "calendar", "meeting")):
        return "communications"
    if _contains_any(text, ("job", "career", "cv", "resume", "application")):
        return "career_workflow"
    if _contains_any(text, ("dissertation", "module", "assignment", "academic")):
        return "academic_workflow"
    if _contains_any(text, ("health", "active task", "system")):
        return "system_status"
    return "general_assistance"


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)


def _agents_for(task_type: str, risk_level: RiskLevel) -> list[str]:
    agents_by_type = {
        "research": ["research_agent", "verification_agent"],
        "memory": ["memory_agent", "verification_agent"],
        "computer_operation": ["computer_agent", "verification_agent"],
        "project_operation": ["computer_agent", "verification_agent"],
        "computer_interaction": ["computer_agent", "security_agent", "verification_agent"],
        "screen_understanding": ["vision_agent", "verification_agent"],
        "control": ["supervisor_agent", "security_agent", "verification_agent"],
        "reminder": ["event_agent", "verification_agent"],
        "proactive_watch": ["event_agent", "decision_agent", "verification_agent"],
        "coding": ["coding_agent", "verification_agent"],
        "file_workflow": ["file_agent", "verification_agent"],
        "document_workflow": ["document_agent", "verification_agent"],
        "work_product": ["artifact_agent", "verification_agent"],
        "browser_workflow": ["computer_agent", "verification_agent"],
        "application_state": ["computer_agent", "verification_agent"],
        "communications": ["communications_agent", "verification_agent"],
        "daily_brief": ["supervisor_agent", "event_agent", "communications_agent", "verification_agent"],
        "operations_intelligence": ["supervisor_agent", "memory_agent", "event_agent", "verification_agent"],
        "decision_analysis": ["decision_agent", "research_agent", "verification_agent"],
        "career_workflow": ["career_agent", "research_agent", "verification_agent"],
        "academic_workflow": ["academic_agent", "verification_agent"],
        "system_status": ["system_agent", "verification_agent"],
        "general_assistance": ["supervisor_agent", "verification_agent"],
    }
    agents = agents_by_type.get(task_type, agents_by_type["general_assistance"]).copy()
    if task_type == "coding" and risk_level == RiskLevel.CONTROLLED_WRITE:
        agents.append("security_agent")
    if risk_level in {RiskLevel.SENSITIVE, RiskLevel.CRITICAL, RiskLevel.PROHIBITED}:
        agents.append("security_agent")
    return list(dict.fromkeys(agents))


def _approval_points(decision) -> list[str]:
    if decision.risk_level == RiskLevel.PROHIBITED:
        return ["Request blocked by policy before planning."]
    if decision.requires_reauthentication:
        return ["Require approval and reauthentication before execution."]
    if decision.requires_approval:
        return ["Require approval before any external or sensitive action."]
    return []


def _steps_for(command: str, task_type: str, agents: list[str]) -> list[TaskStep]:
    first_agent = agents[0]
    verify_dep = new_id()
    plan_step = TaskStep(
        step_id=new_id(),
        title="Interpret objective and retrieve relevant context",
        agent="supervisor_agent",
        success_condition="The objective, task type, and constraints are explicit.",
    )
    execution_step = TaskStep(
        step_id=verify_dep,
        title=_execution_title(task_type),
        agent=first_agent,
        success_condition="The requested work is completed inside current permission limits.",
        depends_on=[plan_step.step_id],
    )
    verification_step = TaskStep(
        step_id=new_id(),
        title="Verify result and produce final explanation",
        agent="verification_agent",
        success_condition="The output matches the original command and unresolved limits are reported.",
        depends_on=[execution_step.step_id],
    )
    return [plan_step, execution_step, verification_step]


def _execution_title(task_type: str) -> str:
    titles = {
        "research": "Run evidence-driven research workflow",
        "memory": "Update memory within the selected project and privacy mode",
        "computer_operation": "Execute the resolved Windows device action",
        "project_operation": "Resolve and open the registered project root",
        "computer_interaction": "Execute the exact approved Windows interaction",
        "screen_understanding": "Capture, inspect, and discard the visible desktop image",
        "control": "Apply the requested global control state immediately",
        "reminder": "Persist the local reminder for proactive delivery",
        "coding": "Inspect code, run safe checks, and prepare proposed changes",
        "file_workflow": "Inspect and organise approved files",
        "document_workflow": "Extract and analyse an approved local document",
        "work_product": "Create and verify the requested managed work product",
        "browser_workflow": "Operate approved browser workflow with verification",
        "application_state": "Inspect or safely continue the exact browser checkpoint",
        "communications": "Execute the bounded communication or report connector readiness",
        "daily_brief": "Assemble the current operational briefing from authorised local state",
        "operations_intelligence": "Rank current attention signals and map related operational evidence",
        "decision_analysis": "Evaluate hypotheses, scenarios, counterfactuals, and uncertainty",
        "career_workflow": "Analyse career materials and prepare outputs",
        "academic_workflow": "Review academic material against requirements",
        "system_status": "Collect local system and task status",
        "general_assistance": "Answer or assist within available context",
    }
    return titles.get(task_type, titles["general_assistance"])


def _success_conditions(
    task_type: str, risk_level: RiskLevel, command: str = ""
) -> list[str]:
    conditions = [
        "All actions are evaluated by policy before execution.",
        "AURIS records an audit event for the task.",
        "A verification step checks the result against the original objective.",
    ]
    if risk_level in {RiskLevel.SENSITIVE, RiskLevel.CRITICAL}:
        conditions.append("No sensitive action executes before required approval.")
    if risk_level == RiskLevel.PROHIBITED:
        conditions.append("The prohibited request is blocked without tool execution.")
    if task_type == "coding":
        coding_operation = match_coding_command(command)
        if coding_operation == "repair_test":
            conditions.extend(
                [
                    "The failing test is reproduced before root-cause diagnosis begins.",
                    "At most two bounded repair attempts run in an isolated worktree or content snapshot.",
                    "Tests, manifests, credentials, links, and dangerous execution primitives are not modified.",
                    "Targeted and complete isolated tests pass before an exact signed diff is shown for approval.",
                    "The registered project remains unchanged until one-time approval, then post-apply tests and hashes pass or exact rollback is verified.",
                ]
            )
        elif coding_operation == "codex_workspace":
            conditions.extend(
                [
                    "The installed Codex CLI works only in an isolated worktree or private content snapshot.",
                    "Codex receives no dangerous sandbox bypass, no automatic approval, and no permission to delete files or alter credentials and instruction policy.",
                    "Every changed path, byte budget, source hash, and static check is independently verified after Codex exits; dynamic checks run only inside the Codex sandbox and are not claimed as independently verified.",
                    "The registered project remains unchanged until one-time approval of the exact signed diff.",
                    "Application revalidates source preimages and final checks, with exact rollback of modified and newly created files on failure.",
                ]
            )
        else:
            conditions.extend(
                [
                    "The registered project root is resolved without following links outside it.",
                    "Repository structure, instructions, test surface, and review signals are reported.",
                    "Read-only analysis modifies no project file and executes no project code.",
                ]
            )
    if task_type == "research":
        conditions.extend(
            [
                "The topic is decomposed into explicit research branches and bounded query cycles.",
                "Primary sources are identified and every retained claim cites validated source IDs.",
                "Counterevidence is searched, duplicate evidence is resolved, and contradictions are surfaced.",
                "A complete coverage ledger passes before the mission is reported as completed.",
            ]
        )
    if task_type == "work_product":
        conditions.extend(
            [
                "Every artifact is created under the AURIS managed work root without overwriting an existing item.",
                "Generated paths, file types, sizes, and content are validated before any project file is written.",
                "Word documents must reopen as valid DOCX packages and generated projects must pass static checks.",
                "AURIS records file hashes and never claims generated code was executed when only static verification occurred.",
            ]
        )
    if task_type == "decision_analysis":
        conditions.extend(
            [
                "Assumptions, unknowns, supporting evidence, and counterevidence remain explicit.",
                "A recommendation is withheld unless at least two options have complete weighted scores.",
                "No probability, model-council result, or real-world outcome is fabricated.",
                "The decision case is reproducible and future outcomes can be scored for calibration.",
            ]
        )
    if task_type == "project_operation":
        conditions.extend(
            [
                "The intended AURIS project resolves to one registered local root.",
                "The exact root is authorized through the signed Windows device fabric.",
                "The resulting File Explorer location is observed before success is reported.",
            ]
        )
    if task_type == "computer_interaction":
        conditions.extend(
            [
                "The exact application and interaction payload are bound to a signed device permission.",
                "One-time approval is recorded before Windows input or UI Automation begins.",
                "A post-action Windows observation is required before completion is reported.",
            ]
        )
    if task_type == "application_state":
        conditions.extend(
            [
                "The checkpoint lookup remains scoped to the selected project.",
                "A mission is replayed only when evidence proves its final control did not run.",
                "Continuation re-resolves the exact checkpoint after one-time approval.",
            ]
        )
    return conditions
