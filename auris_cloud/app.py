from __future__ import annotations

import asyncio
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, status

from auris.telephony_agent import (
    PhoneAssistant,
    PhoneSession,
    Responder,
    TelephonyConfig,
    build_goodbye_twiml,
    build_incoming_twiml,
    build_transfer_twiml,
    validate_twilio_signature,
)

from auris_cloud.config import CloudSettings
from auris_cloud.crypto import (
    CloudSigner,
    certificate_details,
    request_proof_bytes,
    verify_device_request,
)
from auris_cloud.schemas import (
    DeviceCommandAck,
    DeviceCommandRequest,
    DeviceRegistrationRequest,
    EnrolmentRequest,
)
from auris_cloud.store import CloudStore


NONCE_PATTERN = re.compile(r"[A-Za-z0-9_-]{32,160}")


def create_app(
    settings: CloudSettings | None = None,
    *,
    store: CloudStore | None = None,
    signer: CloudSigner | None = None,
    phone_responder: Responder | None = None,
) -> FastAPI:
    configuration = settings or CloudSettings.from_environment()
    command_store = store or CloudStore(configuration.database_path)
    command_signer = signer or CloudSigner.from_pem_path(configuration.signing_private_key_path)
    app = FastAPI(
        title="AURIS Cloud Command Core",
        version="0.2.0",
        docs_url=None if configuration.environment == "production" else "/docs",
        redoc_url=None,
    )
    app.state.settings = configuration
    app.state.store = command_store
    app.state.signer = command_signer
    phone_config = _telephony_config(configuration)
    phone_assistant = PhoneAssistant(phone_config, responder=phone_responder)
    active_calls: dict[str, PhoneSession] = {}
    app.state.phone_config = phone_config
    app.state.active_calls = active_calls

    async def require_admin(
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
    ) -> None:
        _require_secure_transport(request, configuration)
        expected = f"Bearer {configuration.admin_token}"
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin authentication failed.")

    async def require_device(
        request: Request,
        x_auris_device_id: Annotated[str | None, Header()] = None,
        x_auris_timestamp: Annotated[str | None, Header()] = None,
        x_auris_nonce: Annotated[str | None, Header()] = None,
        x_auris_signature: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        _require_secure_transport(request, configuration)
        device_id = str(x_auris_device_id or "")
        try:
            device_id = str(UUID(device_id))
        except ValueError as error:
            raise HTTPException(status_code=401, detail="The device identity is invalid.") from error
        timestamp = _parse_timestamp(x_auris_timestamp)
        now = datetime.now(timezone.utc)
        if timestamp is None or abs((now - timestamp).total_seconds()) > 30:
            raise HTTPException(status_code=401, detail="The device request timestamp is invalid or expired.")
        nonce = str(x_auris_nonce or "")
        if not NONCE_PATTERN.fullmatch(nonce):
            raise HTTPException(status_code=401, detail="The device request nonce is invalid.")
        device = command_store.get_device(device_id)
        if device is None or device.get("revoked"):
            raise HTTPException(status_code=403, detail="The device is not trusted.")
        if device["certificate_expires_at"] <= now.isoformat():
            raise HTTPException(status_code=403, detail="The device certificate has expired.")
        body = await request.body()
        proof = request_proof_bytes(
            request.method,
            request.url.path,
            device_id,
            str(x_auris_timestamp),
            nonce,
            body,
        )
        if not verify_device_request(
            device["certificate_pem"], str(x_auris_signature or ""), proof
        ):
            raise HTTPException(status_code=401, detail="The device request signature is invalid.")
        if not command_store.claim_auth_nonce(
            device_id, nonce, (now + timedelta(seconds=60)).isoformat()
        ):
            raise HTTPException(status_code=409, detail="The device request was already consumed.")
        command_store.touch_device(device_id)
        return device

    async def validated_twilio_form(request: Request) -> dict[str, str]:
        _require_secure_transport(request, configuration)
        if not configuration.telephony_enabled or not phone_config.deployable:
            raise HTTPException(status_code=503, detail="The phone assistant is not deployed.")
        body = await request.body()
        if len(body) > 64 * 1024:
            raise HTTPException(status_code=413, detail="The provider webhook is too large.")
        try:
            from urllib.parse import parse_qsl

            params = dict(parse_qsl(body.decode("utf-8"), keep_blank_values=True))
        except UnicodeError as error:
            raise HTTPException(status_code=400, detail="The provider webhook body is invalid.") from error
        signature = request.headers.get("X-Twilio-Signature", "")
        signed_url = phone_config.public_base_url + request.url.path
        if not validate_twilio_signature(phone_config.auth_token, signed_url, params, signature):
            raise HTTPException(status_code=401, detail="The telephony webhook signature is invalid.")
        return params

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "AURIS Cloud Command Core",
            "version": "0.2.0",
            "environment": configuration.environment,
            "device_authentication": "pinned_certificate_proof",
            "command_signing": "ed25519",
            "mtls": "external_deployment_gate",
            "telephony": "deployable" if configuration.telephony_enabled and phone_config.deployable else "not_connected",
        }

    @app.post("/v1/telephony/incoming", response_class=Response)
    async def incoming_call(request: Request) -> Response:
        params = await validated_twilio_form(request)
        call_sid = str(params.get("CallSid") or "")
        if not re.fullmatch(r"CA[a-fA-F0-9]{32}", call_sid):
            raise HTTPException(status_code=400, detail="The provider call identifier is invalid.")
        command_store.audit("telephony.call_received", metadata={"direction": "inbound"})
        xml = build_incoming_twiml(phone_config, secrets.token_urlsafe(24))
        return Response(content=xml, media_type="application/xml")

    @app.websocket("/v1/telephony/relay")
    async def conversation_relay(websocket: WebSocket) -> None:
        signature = websocket.headers.get("X-Twilio-Signature", "")
        if (
            not configuration.telephony_enabled
            or not phone_config.deployable
            or not validate_twilio_signature(phone_config.auth_token, phone_config.relay_url, {}, signature)
        ):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        session: PhoneSession | None = None
        try:
            while True:
                encoded = await websocket.receive_text()
                if len(encoded) > 16_384:
                    await websocket.close(code=1009)
                    return
                payload = json.loads(encoded)
                if not isinstance(payload, dict):
                    await websocket.close(code=1003)
                    return
                message_type = payload.get("type")
                if message_type == "setup":
                    if session is not None:
                        await websocket.close(code=1008)
                        return
                    session = phone_assistant.start(
                        str(payload.get("callSid") or ""),
                        str(payload.get("from") or ""),
                        str(payload.get("to") or ""),
                    )
                    active_calls[session.call_sid] = session
                elif message_type == "prompt" and payload.get("last") is True and session is not None:
                    turn = await asyncio.to_thread(
                        phone_assistant.respond, session, str(payload.get("voicePrompt") or "")
                    )
                    await websocket.send_json(
                        {
                            "type": "text",
                            "token": turn.reply,
                            "last": True,
                            "interruptible": True,
                            "preemptible": True,
                        }
                    )
                    if turn.transfer:
                        await websocket.send_json(
                            {
                                "type": "end",
                                "handoffData": json.dumps(
                                    {"reasonCode": "live-agent-handoff", "reason": turn.reason},
                                    separators=(",", ":"),
                                ),
                            }
                        )
                        return
                elif message_type not in {"interrupt", "dtmf"}:
                    await websocket.close(code=1003)
                    return
        except (WebSocketDisconnect, json.JSONDecodeError, ValueError):
            pass
        finally:
            if session is not None:
                summary = await asyncio.to_thread(phone_assistant.finish, session)
                command_store.save_phone_call_summary(summary)
                active_calls.pop(session.call_sid, None)

    @app.post("/v1/telephony/handoff", response_class=Response)
    async def call_handoff(request: Request) -> Response:
        params = await validated_twilio_form(request)
        handoff = str(params.get("HandoffData") or "")
        try:
            details = json.loads(handoff) if handoff else {}
        except json.JSONDecodeError:
            details = {}
        transfer = isinstance(details, dict) and details.get("reasonCode") == "live-agent-handoff"
        xml = build_transfer_twiml(phone_config) if transfer else build_goodbye_twiml()
        command_store.audit("telephony.handoff", metadata={"transfer_requested": transfer})
        return Response(content=xml, media_type="application/xml")

    @app.post("/v1/telephony/status", response_class=Response)
    async def call_status(request: Request) -> Response:
        params = await validated_twilio_form(request)
        provider_state = str(params.get("CallStatus") or "unknown")[:40]
        command_store.audit("telephony.provider_status", metadata={"state": provider_state})
        return Response(content='<?xml version="1.0" encoding="UTF-8"?><Response />', media_type="application/xml")

    @app.get("/v1/telephony/calls", dependencies=[Depends(require_admin)])
    def list_phone_calls(limit: int = 50) -> dict[str, Any]:
        return {"ok": True, "calls": command_store.list_phone_call_summaries(limit)}

    @app.post("/v1/enrolments", status_code=201, dependencies=[Depends(require_admin)])
    def create_enrolment(body: EnrolmentRequest) -> dict[str, Any]:
        enrolment = command_store.create_enrolment(
            list(body.permissions), body.expires_in_seconds
        )
        return {"ok": True, "enrolment": enrolment}

    @app.post("/v1/devices/register", status_code=201)
    def register_device(body: DeviceRegistrationRequest, request: Request) -> dict[str, Any]:
        _require_secure_transport(request, configuration)
        device_id = str(body.device_id)
        try:
            certificate = certificate_details(body.certificate_pem, device_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        permissions = command_store.consume_enrolment(body.enrolment_code)
        if permissions is None:
            raise HTTPException(status_code=401, detail="The enrolment code is invalid, expired, or consumed.")
        try:
            device = command_store.register_device(
                device_id=device_id,
                display_name=body.display_name,
                platform=body.platform,
                certificate_pem=body.certificate_pem,
                certificate_fingerprint=certificate["fingerprint"],
                certificate_expires_at=certificate["expires_at"],
                permissions=permissions,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"ok": True, "device": device}

    @app.get("/v1/devices", dependencies=[Depends(require_admin)])
    def list_devices() -> dict[str, Any]:
        return {"ok": True, "devices": command_store.list_devices()}

    @app.post("/v1/devices/{device_id}/revoke", dependencies=[Depends(require_admin)])
    def revoke_device(device_id: UUID) -> dict[str, Any]:
        device = command_store.revoke_device(str(device_id))
        if device is None:
            raise HTTPException(status_code=404, detail="The active device was not found.")
        return {"ok": True, "device": device}

    @app.get("/v1/security/signing-key", dependencies=[Depends(require_admin)])
    def signing_key() -> dict[str, Any]:
        return {
            "ok": True,
            "signing_key": {
                "algorithm": "Ed25519",
                "public_key": command_signer.public_key_b64,
                "fingerprint": command_signer.fingerprint,
            },
        }

    @app.post(
        "/v1/devices/{device_id}/commands",
        status_code=201,
        dependencies=[Depends(require_admin)],
    )
    def create_command(device_id: UUID, body: DeviceCommandRequest) -> dict[str, Any]:
        device = command_store.get_device(str(device_id))
        if device is None or device.get("revoked"):
            raise HTTPException(status_code=404, detail="The active device was not found.")
        if body.kind not in device["permissions"]:
            raise HTTPException(status_code=403, detail="The device permission scope is denied.")
        now = datetime.now(timezone.utc)
        ttl = body.ttl_seconds or configuration.command_ttl_seconds
        envelope: dict[str, Any] = {
            "command_id": str(uuid4()),
            "device_id": str(device_id),
            "tool": "windows.device_action",
            "parameters": {
                "action_id": body.action_id,
                "kind": body.kind,
                "target": body.target,
            },
            "permission_scope": body.kind,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=ttl)).isoformat(),
            "nonce": secrets.token_urlsafe(32),
        }
        envelope["signature"] = command_signer.sign_envelope(envelope)
        command = command_store.enqueue_command(str(device_id), envelope)
        return {"ok": True, "command": _public_command(command)}

    @app.get("/v1/device/commands/next", response_model=None)
    def next_command(
        device: dict[str, Any] = Depends(require_device),
    ) -> Any:
        command = command_store.lease_next_command(
            device["device_id"], configuration.lease_seconds
        )
        if command is None:
            return Response(status_code=204)
        return {
            "ok": True,
            "command": command["envelope"],
            "lease_expires_at": command["lease_expires_at"],
        }

    @app.post("/v1/device/commands/{command_id}/ack")
    def acknowledge_command(
        command_id: UUID,
        body: DeviceCommandAck,
        device: dict[str, Any] = Depends(require_device),
    ) -> dict[str, Any]:
        command = command_store.acknowledge_command(
            device["device_id"], command_id=str(command_id), acknowledgement=body.model_dump()
        )
        if command is None:
            raise HTTPException(status_code=409, detail="The leased command could not be acknowledged.")
        return {"ok": True, "command": _public_command(command)}

    @app.get("/v1/commands", dependencies=[Depends(require_admin)])
    def list_commands(limit: int = 100) -> dict[str, Any]:
        return {"ok": True, "commands": [_public_command(item) for item in command_store.list_commands(limit)]}

    return app


def _public_command(command: dict[str, Any]) -> dict[str, Any]:
    return {
        "command_id": command["command_id"],
        "device_id": command["device_id"],
        "state": command["state"],
        "created_at": command["created_at"],
        "leased_at": command["leased_at"],
        "lease_expires_at": command["lease_expires_at"],
        "acknowledged_at": command["acknowledged_at"],
        "acknowledgement": command["acknowledgement"],
        "envelope": command["envelope"],
    }


def _require_secure_transport(request: Request, settings: CloudSettings) -> None:
    if settings.require_https and request.url.scheme != "https":
        raise HTTPException(status_code=400, detail="HTTPS is required.")


def _parse_timestamp(value: str | None) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _telephony_config(settings: CloudSettings) -> TelephonyConfig:
    return TelephonyConfig(
        public_base_url=settings.telephony_public_base_url.rstrip("/"),
        relay_url=settings.telephony_relay_url,
        owner_number=settings.telephony_owner_number,
        auth_token=settings.twilio_auth_token,
        language=settings.telephony_language,
        tts_provider=settings.telephony_tts_provider,
        voice=settings.telephony_voice,
        connected=settings.telephony_enabled,
    )
