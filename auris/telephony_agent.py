from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlparse
from xml.etree.ElementTree import Element, SubElement, tostring

from auris.model_gateway import generate_reply


E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
CALL_SID_PATTERN = re.compile(r"^CA[a-fA-F0-9]{32}$")
MAX_CALL_TURNS = 40
MAX_UTTERANCE_CHARS = 1_200
Responder = Callable[[list[dict[str, str]], str], str]

URGENT_TERMS = (
    "accident", "ambulance", "breach", "emergency", "fraud", "hospital", "immediately",
    "lost card", "police", "security incident", "today's deadline", "urgent",
)
SENSITIVE_TERMS = (
    "bank account", "card number", "credit card", "one time password", "otp", "passcode",
    "password", "payment", "pin number", "security code", "verification code", "wire transfer",
)
COMMITMENT_TERMS = (
    "accept the offer", "agree to", "book it", "confirm the booking", "place the order",
    "purchase", "sign the contract",
)


@dataclass(frozen=True)
class TelephonyConfig:
    provider: str = "twilio_conversation_relay"
    public_base_url: str = ""
    relay_url: str = ""
    owner_number: str = ""
    auth_token: str = ""
    language: str = "en-GB"
    tts_provider: str = "ElevenLabs"
    voice: str = ""
    connected: bool = False

    @property
    def deployable(self) -> bool:
        return not self.validation_errors()

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        public = urlparse(self.public_base_url)
        relay = urlparse(self.relay_url)
        if not _trusted_service_url(public, scheme="https", allow_path=False):
            errors.append("trusted public HTTPS endpoint")
        if not _trusted_service_url(relay, scheme="wss", allow_path=True):
            errors.append("trusted WSS conversation endpoint")
        if not E164_PATTERN.fullmatch(self.owner_number):
            errors.append("owner transfer number in E.164 format")
        if len(self.auth_token) < 20:
            errors.append("Twilio webhook authentication token")
        return errors


@dataclass
class PhoneSession:
    call_sid: str
    caller: str
    called_number: str
    started_at: str
    transcript: list[dict[str, str]] = field(default_factory=list)
    disclosure_delivered: bool = False
    transfer_requested: bool = False
    transfer_reason: str = ""
    importance: str = "routine"

    @property
    def masked_caller(self) -> str:
        digits = re.sub(r"\D", "", self.caller)
        return f"***{digits[-4:]}" if digits else "withheld"


@dataclass(frozen=True)
class PhoneTurn:
    reply: str
    importance: str
    transfer: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PhoneAssistant:
    def __init__(self, config: TelephonyConfig, *, responder: Responder | None = None) -> None:
        self.config = config
        self.responder = responder or _model_response

    def start(self, call_sid: str, caller: str, called_number: str) -> PhoneSession:
        if call_sid and not CALL_SID_PATTERN.fullmatch(call_sid):
            raise ValueError("The provider call identifier is invalid.")
        if caller and not E164_PATTERN.fullmatch(caller):
            caller = ""
        session = PhoneSession(
            call_sid=call_sid or "simulation-" + secrets.token_hex(12),
            caller=caller,
            called_number=called_number if E164_PATTERN.fullmatch(called_number) else "",
            started_at=datetime.now(timezone.utc).isoformat(),
            disclosure_delivered=True,
        )
        session.transcript.append({"role": "assistant", "content": welcome_greeting()})
        return session

    def respond(self, session: PhoneSession, utterance: str) -> PhoneTurn:
        clean = " ".join(str(utterance).split())[:MAX_UTTERANCE_CHARS]
        if not clean:
            return PhoneTurn("I did not catch that. Could you say it once more?", "routine", False, "")
        if len(session.transcript) >= MAX_CALL_TURNS * 2:
            session.transfer_requested = True
            session.transfer_reason = "conversation_turn_limit"
            return PhoneTurn(
                "This conversation has reached my safe limit. I will try to connect you to Devansh.",
                "important", True, session.transfer_reason,
            )
        session.transcript.append({"role": "caller", "content": clean})
        transfer, importance, reason = classify_call_turn(clean)
        if transfer:
            session.transfer_requested = True
            session.transfer_reason = reason
            session.importance = importance
            if reason == "emergency":
                reply = "I understand this may be urgent. If anyone is in immediate danger, contact emergency services now. I will try to connect you to Devansh."
            elif reason == "sensitive_information":
                reply = "I cannot receive payment details, passwords, or security codes. I will try to connect you to Devansh."
            elif reason == "commitment_required":
                reply = "I cannot make that commitment for Devansh. I will try to connect you to him."
            else:
                reply = "Certainly. I will try to connect you to Devansh now."
        else:
            messages = _bounded_model_context(session.transcript)
            try:
                reply = self.responder(messages, _phone_system_prompt())
            except RuntimeError:
                reply = "I can take a concise message for Devansh. Please tell me your name, the reason for calling, and the best way to reach you."
            reply = _clean_spoken_reply(reply)
            if not reply:
                reply = "Please leave a concise message for Devansh."
        session.transcript.append({"role": "assistant", "content": reply})
        return PhoneTurn(reply, importance, transfer, reason)

    def finish(self, session: PhoneSession) -> dict[str, Any]:
        summary_prompt = (
            "Create a private post-call brief for Devansh. Return strict JSON with summary, caller_request, "
            "promised_actions, urgency, and follow_up. Do not invent facts. AURIS is not permitted to make "
            "commitments, so promised_actions should normally be empty.\n\n"
            + "\n".join(f"{item['role']}: {item['content']}" for item in session.transcript[-24:])
        )
        try:
            raw = self.responder([{"role": "user", "content": summary_prompt}], _summary_system_prompt())
            parsed = _parse_summary(raw)
        except RuntimeError:
            parsed = _fallback_summary(session)
        return {
            "call_id": session.call_sid,
            "caller": session.masked_caller,
            "started_at": session.started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "turn_count": sum(item["role"] == "caller" for item in session.transcript),
            "importance": session.importance,
            "transfer_requested": session.transfer_requested,
            "transfer_reason": session.transfer_reason,
            "disclosure_delivered": session.disclosure_delivered,
            "audio_recorded": False,
            "raw_transcript_persisted": False,
            **parsed,
        }


def classify_call_turn(text: str) -> tuple[bool, str, str]:
    lowered = text.casefold()
    if any(term in lowered for term in URGENT_TERMS):
        return True, "urgent", "emergency"
    if any(term in lowered for term in SENSITIVE_TERMS):
        return True, "important", "sensitive_information"
    if any(term in lowered for term in COMMITMENT_TERMS):
        return True, "important", "commitment_required"
    wants_human = re.search(
        r"\b(?:speak|talk|connect|transfer|put me through)\b.{0,35}\b(?:devansh|him|human|person)\b",
        lowered,
    )
    if wants_human:
        return True, "important", "caller_requested_handoff"
    important = any(term in lowered for term in ("deadline", "interview", "family", "meeting changed", "offer"))
    return False, "important" if important else "routine", "message" if important else ""


def welcome_greeting() -> str:
    return (
        "Hello. This is AURIS, Devansh's AI assistant. I can take a message or connect you to "
        "Devansh when necessary. This call is transcribed for that assistance, but audio is not "
        "recorded by AURIS. Please do not share passwords, security codes, or payment details. How may I help?"
    )


def load_telephony_config() -> TelephonyConfig:
    return TelephonyConfig(
        public_base_url=os.environ.get("AURIS_TELEPHONY_PUBLIC_URL", "").strip().rstrip("/"),
        relay_url=os.environ.get("AURIS_TELEPHONY_RELAY_URL", "").strip(),
        owner_number=os.environ.get("AURIS_TELEPHONY_OWNER_NUMBER", "").strip(),
        auth_token=os.environ.get("AURIS_TWILIO_AUTH_TOKEN", "").strip(),
        language=os.environ.get("AURIS_TELEPHONY_LANGUAGE", "en-GB").strip(),
        tts_provider=os.environ.get("AURIS_TELEPHONY_TTS_PROVIDER", "ElevenLabs").strip(),
        voice=os.environ.get("AURIS_TELEPHONY_VOICE", "").strip(),
        connected=os.environ.get("AURIS_TELEPHONY_CONNECTED", "").casefold() in {"1", "true", "yes"},
    )


def telephony_status(config: TelephonyConfig | None = None) -> dict[str, Any]:
    current = config or load_telephony_config()
    errors = current.validation_errors()
    return {
        "provider": current.provider,
        "available": not errors,
        "connected": current.connected and not errors,
        "state": "connected" if current.connected and not errors else "deployment_required" if not errors else "configuration_required",
        "missing": errors,
        "mode": "inbound_ai_relay",
        "capabilities": ["answer_inbound", "ai_disclosure", "take_message", "importance_detection", "human_handoff", "post_call_summary"],
        "permissions": ["answer_inbound", "take_message", "human_handoff", "post_call_summary"],
        "audio_recording": "disabled",
        "raw_transcript_persistence": "disabled",
        "write_requires_approval": True,
    }


def validate_twilio_signature(auth_token: str, url: str, params: dict[str, str], signature: str) -> bool:
    if len(auth_token) < 20 or not signature:
        return False
    signed = url + "".join(key + str(params[key]) for key in sorted(params))
    expected = base64.b64encode(hmac.new(auth_token.encode("utf-8"), signed.encode("utf-8"), hashlib.sha1).digest()).decode("ascii")
    return hmac.compare_digest(expected, signature)


def build_incoming_twiml(config: TelephonyConfig, call_reference: str) -> str:
    if not config.deployable:
        raise ValueError("Telephony is not configured for a trusted deployment.")
    response = Element("Response")
    connect = SubElement(response, "Connect", {"action": f"{config.public_base_url}/v1/telephony/handoff", "method": "POST"})
    attributes = {
        "url": config.relay_url,
        "welcomeGreeting": welcome_greeting(),
        "welcomeGreetingInterruptible": "speech",
        "language": config.language,
        "ttsProvider": config.tts_provider,
        "transcriptionProvider": "Deepgram",
    }
    if config.voice:
        attributes["voice"] = config.voice
    relay = SubElement(connect, "ConversationRelay", attributes)
    SubElement(relay, "Parameter", {"name": "callReference", "value": call_reference[:120]})
    return _xml(response)


def build_transfer_twiml(config: TelephonyConfig) -> str:
    if not E164_PATTERN.fullmatch(config.owner_number):
        raise ValueError("A valid owner transfer number is required.")
    response = Element("Response")
    dial = SubElement(response, "Dial", {"answerOnBridge": "true", "timeout": "25"})
    dial.text = config.owner_number
    SubElement(response, "Say").text = "Devansh was unavailable. I have kept a summary of your message for him. Goodbye."
    return _xml(response)


def build_goodbye_twiml() -> str:
    response = Element("Response")
    SubElement(response, "Say").text = "Thank you. I will pass your message to Devansh. Goodbye."
    return _xml(response)


def simulate_call(utterances: list[str], *, responder: Responder | None = None) -> dict[str, Any]:
    config = TelephonyConfig(owner_number="+447700900001")
    assistant = PhoneAssistant(config, responder=responder)
    session = assistant.start("", "+447700900002", "+447700900003")
    turns: list[dict[str, Any]] = []
    for utterance in utterances[:MAX_CALL_TURNS]:
        turn = assistant.respond(session, utterance)
        turns.append(turn.to_dict())
        if turn.transfer:
            break
    return {"ok": True, "turns": turns, "summary": assistant.finish(session)}


def _model_response(messages: list[dict[str, str]], system_prompt: str) -> str:
    reply = generate_reply(
        [{"role": "system", "content": system_prompt}, *messages],
        mode="discussion", project_name="AURIS Phone Assistant", project_instructions="", memories=[],
    )
    return reply.text


def _phone_system_prompt() -> str:
    return (
        "You are AURIS, Devansh's disclosed AI phone assistant. Sound calm, natural, concise, and warm. "
        "Never claim to be human. Do not accept payments, credentials, verification codes, legal terms, "
        "medical decisions, bookings, purchases, or commitments for Devansh. Do not reveal private data. "
        "For ordinary calls, answer only general questions or collect the caller's name, reason, callback "
        "details, and preferred time. Never say an action happened unless the call system confirms it."
    )


def _summary_system_prompt() -> str:
    return "You create factual, concise private call summaries for Devansh. Return JSON only and do not invent facts."


def _bounded_model_context(transcript: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {"role": "user" if item["role"] == "caller" else "assistant", "content": item["content"][:MAX_UTTERANCE_CHARS]}
        for item in transcript[-16:]
    ]


def _clean_spoken_reply(value: str) -> str:
    text = re.sub(r"[*_`#>]", "", str(value))
    text = re.sub(r"\[[^\]]{0,80}\]", "", text)
    return " ".join(text.split())[:900]


def _parse_summary(value: str) -> dict[str, Any]:
    text = str(value).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError("The call summary was not valid JSON.") from error
    if not isinstance(payload, dict):
        raise RuntimeError("The call summary was not an object.")
    return {
        "summary": str(payload.get("summary") or "No reliable summary was generated.")[:2_000],
        "caller_request": str(payload.get("caller_request") or "")[:1_000],
        "promised_actions": [],
        "urgency": str(payload.get("urgency") or "routine")[:40],
        "follow_up": str(payload.get("follow_up") or "Review the call summary.")[:1_000],
    }


def _fallback_summary(session: PhoneSession) -> dict[str, Any]:
    caller_turns = [item["content"] for item in session.transcript if item["role"] == "caller"]
    message = " ".join(caller_turns[-3:])[:1_500]
    return {
        "summary": message or "The caller left no usable message.",
        "caller_request": caller_turns[-1][:1_000] if caller_turns else "",
        "promised_actions": [],
        "urgency": session.importance,
        "follow_up": "Contact the caller if the message requires a response." if caller_turns else "No follow-up identified.",
    }


def _xml(root: Element) -> str:
    return '<?xml version="1.0" encoding="UTF-8"?>' + tostring(root, encoding="unicode", short_empty_elements=True)


def _trusted_service_url(parsed, *, scheme: str, allow_path: bool) -> bool:
    if (
        parsed.scheme != scheme
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or (not allow_path and parsed.path not in {"", "/"})
    ):
        return False
    host = parsed.hostname.casefold()
    if host == "localhost" or host.endswith((".localhost", ".local")):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return "." in host
