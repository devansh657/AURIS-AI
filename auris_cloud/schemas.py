from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


PermissionScope = Literal[
    "launch_app",
    "close_app",
    "focus_app",
    "open_folder",
    "open_url",
    "list_folder",
    "media_key",
    "type_text",
    "invoke_control",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EnrolmentRequest(StrictModel):
    permissions: list[PermissionScope] = Field(min_length=1, max_length=9)
    expires_in_seconds: int = Field(default=300, ge=60, le=900)

    @field_validator("permissions")
    @classmethod
    def unique_permissions(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("permissions must be unique")
        return value


class DeviceRegistrationRequest(StrictModel):
    enrolment_code: str = Field(min_length=40, max_length=256)
    device_id: UUID
    display_name: str = Field(min_length=1, max_length=120)
    platform: str = Field(min_length=1, max_length=200)
    certificate_pem: str = Field(min_length=200, max_length=12000)


class DeviceCommandRequest(StrictModel):
    action_id: str = Field(pattern=r"^[a-z0-9_]{2,120}$")
    kind: PermissionScope
    target: str = Field(min_length=1, max_length=200)
    ttl_seconds: int | None = Field(default=None, ge=5, le=120)


class DeviceCommandAck(StrictModel):
    state: Literal["completed", "failed", "rejected"]
    verification_summary: str = Field(min_length=1, max_length=500)
