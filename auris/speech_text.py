from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any


MAX_SPOKEN_CHARACTERS = 1200

_FENCED_CODE = re.compile(r"```(?:[^\n`]*)\n?.*?```", re.DOTALL)
_MARKDOWN_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((?:https?://|mailto:)[^)]*\)")
_RAW_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_INLINE_CODE = re.compile(r"`([^`]+)`")
_NUMERIC_CITATION = re.compile(r"\[(?:\d+(?:\s*[-,]\s*\d+)*)\]")
_LIST_PREFIX = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+", re.MULTILINE)
_HEADING_PREFIX = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_BLOCKQUOTE_PREFIX = re.compile(r"^\s*>+\s?", re.MULTILINE)
_TABLE_RULE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*$", re.MULTILINE)
_SPACE = re.compile(r"\s+")
_MULTIPLY = re.compile(r"(?<=\d)\s*\*\s*(?=\d)")
_PASSIVE_ACK = re.compile(
    r"^\s*(?:(?:yes|okay|ok)[,\s]+)?(?:devansh[,.\s]+)?"
    r"(?:i\s+am|i['\u2019]m|im)\s+listening(?:[,\s]+devansh)?\s*"
    r"(?:[.!?;:]+\s*|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SpeechPlan:
    text: str
    sentiment: str
    confidence: float
    signals: tuple[str, ...]
    speed: float
    energy: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def prepare_speech(text: str, *, requested_rate: int = 0) -> SpeechPlan:
    spoken = normalise_spoken_text(text)
    sentiment, confidence, signals = infer_speech_sentiment(spoken)
    base_speed = {
        "urgent": 0.98,
        "concerned": 0.92,
        "reassuring": 0.94,
        "positive": 0.98,
        "neutral": 0.95,
    }[sentiment]
    speed = max(0.84, min(base_speed + max(-4, min(int(requested_rate), 4)) * 0.035, 1.12))
    energy = {
        "urgent": "firm",
        "concerned": "measured",
        "reassuring": "calm",
        "positive": "warm",
        "neutral": "composed",
    }[sentiment]
    return SpeechPlan(spoken, sentiment, confidence, tuple(signals), round(speed, 3), energy)


def normalise_spoken_text(value: str) -> str:
    text = html.unescape(str(value or "")).replace("\r\n", "\n").replace("\r", "\n")
    had_code = bool(_FENCED_CODE.search(text))
    text = _FENCED_CODE.sub(" ", text)
    text = _MARKDOWN_IMAGE.sub(lambda match: f" {match.group(1)} " if match.group(1).strip() else " ", text)
    text = _MARKDOWN_LINK.sub(lambda match: f" {match.group(1)} ", text)
    text = _RAW_URL.sub(" the linked page ", text)
    text = _INLINE_CODE.sub(lambda match: f" {match.group(1)} ", text)
    text = _NUMERIC_CITATION.sub(" ", text)
    text = _TABLE_RULE.sub(" ", text)
    text = _HEADING_PREFIX.sub("", text)
    text = _BLOCKQUOTE_PREFIX.sub("", text)
    text = _LIST_PREFIX.sub("", text)
    text = text.replace("|", ". ")
    text = _MULTIPLY.sub(" times ", text)
    text = text.replace("&", " and ").replace("%", " percent ")
    text = text.replace("+", " plus ").replace("=", " equals ")
    text = text.replace("@", " at ").replace("\\", " ")
    text = re.sub(r"[*_~`#<>\[\]{}^]+", "", text)
    text = _remove_decorative_symbols(text)
    text = re.sub(r"\s*/\s*", " or ", text)
    text = re.sub(r"\s*[-\u2013\u2014]{2,}\s*", ". ", text)
    text = _apply_pronunciations(text)
    text = _SPACE.sub(" ", text).strip(" ,;:-")
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([.!?]){2,}", r"\1", text)
    while _PASSIVE_ACK.match(text):
        text = _PASSIVE_ACK.sub("", text, count=1).strip()
    if had_code and len(text) < 80:
        text = f"{text}. The code is available in the transcript." if text else "The code is available in the transcript."
    return _truncate_at_sentence(text, MAX_SPOKEN_CHARACTERS)


def infer_speech_sentiment(text: str) -> tuple[str, float, list[str]]:
    lowered = text.casefold()
    groups = (
        (
            "urgent",
            0.88,
            (
                ("emergency", "emergency language"),
                ("critical", "critical condition"),
                ("danger", "danger signal"),
                ("security breach", "security incident"),
                ("stop immediately", "immediate stop"),
            ),
        ),
        (
            "concerned",
            0.76,
            (
                ("failed", "failure reported"),
                ("failure", "failure reported"),
                ("could not", "blocked outcome"),
                ("cannot", "blocked outcome"),
                ("warning", "warning reported"),
                ("risk", "risk identified"),
                ("recommend against", "adverse recommendation"),
                ("approval required", "authority checkpoint"),
            ),
        ),
        (
            "reassuring",
            0.68,
            (
                ("under control", "stability assurance"),
                ("standing by", "readiness statement"),
                ("i am listening", "attention acknowledgement"),
                ("i have isolated", "fault isolated"),
            ),
        ),
        (
            "positive",
            0.72,
            (
                ("verified", "verified outcome"),
                ("completed", "completion reported"),
                ("successful", "successful outcome"),
                ("resolved", "resolution reported"),
                ("healthy", "healthy state"),
                ("ready", "readiness reported"),
            ),
        ),
    )
    for sentiment, confidence, candidates in groups:
        signals = [label for phrase, label in candidates if phrase in lowered]
        if signals:
            adjusted = min(0.96, confidence + 0.03 * (len(signals) - 1))
            return sentiment, round(adjusted, 2), signals
    return "neutral", 0.5, ["no strong deterministic sentiment signal"]


def _apply_pronunciations(text: str) -> str:
    replacements = {
        "AURIS": "Auris",
        "API": "A P I",
        "CPU": "C P U",
        "GPU": "G P U",
        "HTTP": "H T T P",
        "HTTPS": "H T T P S",
        "JSON": "J S O N",
        "MCP": "M C P",
        "SQL": "S Q L",
        "UI": "U I",
        "URL": "U R L",
    }
    for source, target in replacements.items():
        text = re.sub(rf"\b{source}\b", target, text, flags=re.IGNORECASE)
    return text


def _remove_decorative_symbols(text: str) -> str:
    kept: list[str] = []
    for character in text:
        category = unicodedata.category(character)
        if category in {"So", "Sk", "Co", "Cs"}:
            kept.append(" ")
        else:
            kept.append(character)
    return "".join(kept)


def _truncate_at_sentence(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    candidate = text[:limit]
    boundary = max(candidate.rfind(". "), candidate.rfind("? "), candidate.rfind("! "))
    if boundary >= int(limit * 0.6):
        candidate = candidate[: boundary + 1]
    else:
        word = candidate.rfind(" ")
        if word > 0:
            candidate = candidate[:word]
    return candidate.rstrip(" ,;:-") + "."
