from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class RiskLevel(StrEnum):
    READ_ONLY = "read_only"
    REVERSIBLE = "reversible"
    CONTROLLED_WRITE = "controlled_write"
    SENSITIVE = "sensitive"
    CRITICAL = "critical"
    PROHIBITED = "prohibited"


class TaskState(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class TaskStep:
    step_id: str
    title: str
    agent: str
    success_condition: str
    depends_on: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskPlan:
    task_id: str
    objective: str
    task_type: str
    risk_level: RiskLevel
    required_agents: list[str]
    steps: list[TaskStep]
    approval_points: list[str]
    success_conditions: list[str]
    state: TaskState = TaskState.CREATED
    capability_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["risk_level"] = self.risk_level.value
        data["state"] = self.state.value
        data["steps"] = [step.to_dict() for step in self.steps]
        return data


def new_id() -> str:
    return str(uuid4())
