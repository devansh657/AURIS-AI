from __future__ import annotations

from dataclasses import dataclass

from auris.application_state import match_application_state_command
from auris.communications_agent import match_communication_command
from auris.device_agent import is_device_command
from auris.browser_agent import contains_sensitive_browser_data, is_browser_interaction_intent
from auris.coding_agent import match_coding_command
from auris.interaction_agent import contains_sensitive_typing_data, is_typing_intent
from auris.schemas import RiskLevel
from auris.ui_automation import is_ui_control_intent, ui_control_refusal
from auris.work_product_agent import match_work_product_command


@dataclass(frozen=True)
class PolicyDecision:
    risk_level: RiskLevel
    allowed_to_plan: bool
    requires_approval: bool
    requires_reauthentication: bool
    reason: str


PROHIBITED_TERMS = (
    "disable antivirus",
    "disable firewall",
    "bypass password",
    "privilege escalation",
    "run as administrator",
    "steal",
)

CRITICAL_TERMS = (
    "delete",
    "remove permanently",
    "wipe",
    "format",
    "payment",
    "pay ",
    "change password",
    "reset password",
)

SENSITIVE_TERMS = (
    "send email",
    "send message",
    "submit",
    "publish",
    "post to",
    "apply for",
    "login",
    "recycle bin",
    "recycle file",
)

CONTROLLED_WRITE_TERMS = (
    "draft email",
    "edit",
    "modify",
    "write file",
    "create file",
    "create note",
    "create a note",
    "create text file",
    "create a text file",
    "make note",
    "make a note",
    "write note",
    "write a note",
    "append",
    "add to note",
    "remember",
    "save to memory",
    "record decision",
    "run test",
    "fix code",
    "prepare fix",
    "fix this failing test",
    "fix the failing test",
    "fix failing test",
    "repair this failing test",
    "repair the failing test",
    "repair failing test",
    "remind me",
)

REVERSIBLE_TERMS = (
    "draft",
    "copy",
    "rename",
    "move file",
    "organise",
    "organize",
    "create folder",
    "open notepad",
    "open calculator",
    "open file explorer",
    "open paint",
    "open documents",
    "open downloads",
    "open auris",
    "summarise into",
    "summarize into",
)


def classify_command(command: str) -> PolicyDecision:
    text = command.lower()

    communication = match_communication_command(command)
    if communication is not None and communication.kind == "start_call":
        return PolicyDecision(
            risk_level=RiskLevel.SENSITIVE,
            allowed_to_plan=True,
            requires_approval=True,
            requires_reauthentication=False,
            reason="Starting an external audio call requires approval for the exact contact and channel.",
        )

    if contains_sensitive_typing_data(command):
        return PolicyDecision(
            risk_level=RiskLevel.PROHIBITED,
            allowed_to_plan=False,
            requires_approval=False,
            requires_reauthentication=False,
            reason="AURIS will not type passwords, tokens, payment data, or other secret material.",
        )

    if contains_sensitive_browser_data(command):
        return PolicyDecision(
            risk_level=RiskLevel.PROHIBITED,
            allowed_to_plan=False,
            requires_approval=False,
            requires_reauthentication=False,
            reason="AURIS will not enter protected data or invoke consequential browser controls.",
        )

    ui_refusal = ui_control_refusal(command)
    if ui_refusal:
        return PolicyDecision(
            risk_level=RiskLevel.PROHIBITED,
            allowed_to_plan=False,
            requires_approval=False,
            requires_reauthentication=False,
            reason=ui_refusal,
        )

    application_state_operation = match_application_state_command(command)
    if application_state_operation == "continue":
        return PolicyDecision(
            risk_level=RiskLevel.SENSITIVE,
            allowed_to_plan=True,
            requires_approval=True,
            requires_reauthentication=False,
            reason="Continuing a browser mission requires approval for the exact durable checkpoint before any page action is replayed.",
        )

    if _contains_any(text, PROHIBITED_TERMS):
        return PolicyDecision(
            risk_level=RiskLevel.PROHIBITED,
            allowed_to_plan=False,
            requires_approval=False,
            requires_reauthentication=False,
            reason="The command appears to request a prohibited security or abuse-related action.",
        )

    product = match_work_product_command(command)
    if match_coding_command(command) == "codex_workspace" or product is not None and product.kind == "code_project":
        return PolicyDecision(
            risk_level=RiskLevel.CONTROLLED_WRITE,
            allowed_to_plan=True,
            requires_approval=False,
            requires_reauthentication=False,
            reason="A coding brief authorizes only an isolated implementation, not its described external actions; applying an exact signed diff requires later approval.",
        )

    if _contains_any(text, CRITICAL_TERMS):
        return PolicyDecision(
            risk_level=RiskLevel.CRITICAL,
            allowed_to_plan=True,
            requires_approval=True,
            requires_reauthentication=True,
            reason="Critical actions require explicit approval and reauthentication before execution.",
        )

    if _contains_any(text, SENSITIVE_TERMS):
        return PolicyDecision(
            risk_level=RiskLevel.SENSITIVE,
            allowed_to_plan=True,
            requires_approval=True,
            requires_reauthentication=False,
            reason="Sensitive external actions require approval before execution.",
        )

    if is_typing_intent(command):
        return PolicyDecision(
            risk_level=RiskLevel.SENSITIVE,
            allowed_to_plan=True,
            requires_approval=True,
            requires_reauthentication=False,
            reason="Typing into another application requires explicit approval for the exact text and target.",
        )

    if is_browser_interaction_intent(command):
        return PolicyDecision(
            risk_level=RiskLevel.SENSITIVE,
            allowed_to_plan=True,
            requires_approval=True,
            requires_reauthentication=False,
            reason="Changing browser state, including an exact multi-step mission, requires one-time approval.",
        )

    if is_ui_control_intent(command):
        return PolicyDecision(
            risk_level=RiskLevel.SENSITIVE,
            allowed_to_plan=True,
            requires_approval=True,
            requires_reauthentication=False,
            reason="Invoking a visible application control requires approval for the exact app and control.",
        )

    if match_work_product_command(command) is not None:
        return PolicyDecision(
            risk_level=RiskLevel.CONTROLLED_WRITE,
            allowed_to_plan=True,
            requires_approval=False,
            requires_reauthentication=False,
            reason="AURIS may create a new, non-overwriting artifact only inside its managed work directory.",
        )

    if _contains_any(text, CONTROLLED_WRITE_TERMS):
        return PolicyDecision(
            risk_level=RiskLevel.CONTROLLED_WRITE,
            allowed_to_plan=True,
            requires_approval=False,
            requires_reauthentication=False,
            reason="Controlled workspace writes are allowed only inside approved project paths.",
        )

    if is_device_command(command):
        return PolicyDecision(
            risk_level=RiskLevel.REVERSIBLE,
            allowed_to_plan=True,
            requires_approval=False,
            requires_reauthentication=False,
            reason="The command is a bounded Windows device action and remains auditable.",
        )

    if _contains_any(text, REVERSIBLE_TERMS):
        return PolicyDecision(
            risk_level=RiskLevel.REVERSIBLE,
            allowed_to_plan=True,
            requires_approval=False,
            requires_reauthentication=False,
            reason="The command appears reversible and should still be logged.",
        )

    return PolicyDecision(
        risk_level=RiskLevel.READ_ONLY,
        allowed_to_plan=True,
        requires_approval=False,
        requires_reauthentication=False,
        reason="The command appears read-only or informational.",
    )


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)
