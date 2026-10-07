from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CloudSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    environment: str = "production"
    admin_token: str = Field(min_length=40, max_length=256, repr=False)
    signing_private_key_path: Path
    database_path: Path
    require_https: bool = True
    command_ttl_seconds: int = Field(default=30, ge=5, le=120)
    lease_seconds: int = Field(default=30, ge=5, le=120)
    telephony_enabled: bool = False
    telephony_public_base_url: str = ""
    telephony_relay_url: str = ""
    telephony_owner_number: str = ""
    twilio_auth_token: str = Field(default="", repr=False)
    telephony_language: str = "en-GB"
    telephony_tts_provider: str = "ElevenLabs"
    telephony_voice: str = ""

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        if value not in {"development", "test", "production"}:
            raise ValueError("environment must be development, test, or production")
        return value

    @classmethod
    def from_environment(cls) -> "CloudSettings":
        admin_token = os.environ.get("AURIS_CLOUD_ADMIN_TOKEN", "")
        signing_path = os.environ.get("AURIS_CLOUD_SIGNING_KEY_PATH", "")
        database_path = os.environ.get("AURIS_CLOUD_DATABASE_PATH", "")
        if not admin_token or not signing_path or not database_path:
            raise RuntimeError(
                "AURIS cloud requires AURIS_CLOUD_ADMIN_TOKEN, "
                "AURIS_CLOUD_SIGNING_KEY_PATH, and AURIS_CLOUD_DATABASE_PATH."
            )
        return cls(
            environment=os.environ.get("AURIS_CLOUD_ENVIRONMENT", "production"),
            admin_token=admin_token,
            signing_private_key_path=Path(signing_path),
            database_path=Path(database_path),
            require_https=_environment_bool("AURIS_CLOUD_REQUIRE_HTTPS", default=True),
            telephony_enabled=_environment_bool("AURIS_TELEPHONY_ENABLED", default=False),
            telephony_public_base_url=os.environ.get("AURIS_TELEPHONY_PUBLIC_URL", ""),
            telephony_relay_url=os.environ.get("AURIS_TELEPHONY_RELAY_URL", ""),
            telephony_owner_number=os.environ.get("AURIS_TELEPHONY_OWNER_NUMBER", ""),
            twilio_auth_token=os.environ.get("AURIS_TWILIO_AUTH_TOKEN", ""),
            telephony_language=os.environ.get("AURIS_TELEPHONY_LANGUAGE", "en-GB"),
            telephony_tts_provider=os.environ.get("AURIS_TELEPHONY_TTS_PROVIDER", "ElevenLabs"),
            telephony_voice=os.environ.get("AURIS_TELEPHONY_VOICE", ""),
        )


def _environment_bool(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    if value.casefold() in {"1", "true", "yes", "on"}:
        return True
    if value.casefold() in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be true or false.")
