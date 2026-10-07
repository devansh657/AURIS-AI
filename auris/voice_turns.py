from __future__ import annotations

import hashlib
import re
import threading
import time
from copy import deepcopy
from uuid import uuid4
from typing import Any


def _command_key(text: str) -> str:
    text = re.sub(r"^\s*(?:(?:hey|okay|ok)\s+)?(?:auris|oris|iris|horace)\b[\s,.:;!-]*", "", text, flags=re.I)
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _safe_text(text: str, private: bool) -> str:
    if private or re.search(
        r"password|passcode|secret|token|api[_ -]?key|bearer|\b\d[\d +()-]{8,}\d\b|\S+@\S+|https?://\S+",
        text, re.I,
    ):
        return "[private or sensitive transcript hidden]"
    return text[:500]


class VoiceTurnStore:
    """Short-lived diagnostics, never audio or a durable transcript archive."""

    def __init__(self, *, capacity: int = 40, ttl_seconds: int = 900, clock=time.monotonic):
        self._capacity = capacity
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._turns: dict[str, dict[str, Any]] = {}

    def _prune(self) -> None:
        now = self._clock()
        self._turns = {key: value for key, value in self._turns.items() if now - value["_started"] < self._ttl}
        while len(self._turns) > self._capacity:
            del self._turns[next(iter(self._turns))]

    def captured(self, result: dict[str, Any], *, mode: str, started: float, private: bool = False) -> str | None:
        if result.get("preempted") or mode == "interrupt":
            return None
        if mode == "wake" and not result.get("ok") and not result.get("audio_signal_detected") and not result.get("error_code") in {"input_too_quiet", "input_stalled", "input_overflow"}:
            return None
        text = str(result.get("recognized_as") or result.get("text") or "") if result.get("ok") else ""
        now = self._clock()
        turn_id = str(uuid4())
        wake_only = bool(text and mode == "wake" and _command_key(text) == _command_key(""))
        turn = {
            "turn_id": turn_id, "source": "wake" if mode == "wake" else "command_capture",
            "heard": _safe_text(text, private) if text else "", "private": private,
            "stage": "wake_detected" if wake_only else "recognized" if text else "not_understood",
            "outcome": "wake_detected" if wake_only else "pending" if text else "recognition_failed",
            "input_provider": str(result.get("input_provider") or "unknown")[:80],
            "audio_stored": False, "peak_audio_level": result.get("peak_audio_level"),
            "signal_state": result.get("signal_state"), "peak_dbfs": result.get("peak_dbfs"),
            "sampled_frames": result.get("sampled_frames"), "error_code": result.get("error_code"),
            "decoder_score": result.get("confidence"),
            "score_kind": str(result.get("confidence_kind") or "uncalibrated_recognizer_score")[:80],
            "capture_ms": max(0, round((now - started) * 1000)), "decode_ms": result.get("decode_ms"),
            "command_ms": None, "first_audio_ms": None, "recognition_to_audio_ms": None,
            "interpretation_ms": None,
            "capture_to_audio_ms": None, "speech_state": "not_requested", "actions": [],
            "task_id": None, "task_type": None, "verification": "not_run",
            "failure_stage": None if text else "recognition",
            "miss_count": 0 if text else 1,
            "_last_observed": now,
            "_started": started, "_recognized": now, "_key": _command_key(text), "_claimed": False,
        }
        with self._lock:
            self._prune()
            if mode == "wake" and not text:
                previous = next((value for value in reversed(list(self._turns.values()))
                                 if value["source"] == "wake" and value["outcome"] == "recognition_failed"
                                 and value["input_provider"] == turn["input_provider"]
                                 and value.get("error_code") == turn["error_code"]), None)
                if previous:
                    previous["miss_count"] += 1
                    previous["capture_ms"] = turn["capture_ms"]
                    previous["peak_audio_level"] = turn["peak_audio_level"]
                    previous["_last_observed"] = now
                    for key in ("signal_state", "peak_dbfs", "sampled_frames", "error_code"):
                        previous[key] = turn[key]
                    return previous["turn_id"]
            self._turns[turn_id] = turn
            self._prune()
        return turn_id

    def claim(self, turn_id: str, command: str, *, private: bool) -> bool:
        with self._lock:
            self._prune()
            turn = self._turns.get(turn_id)
            if not turn or turn["_claimed"] or turn["stage"] != "recognized" or turn["_key"] != _command_key(command):
                return False
            if private:
                turn["private"] = True
                turn["heard"] = "[private or sensitive transcript hidden]"
            turn.update(_claimed=True, _command_started=self._clock(), stage="executing")
            return True

    def finished(self, turn_id: str | None, response: dict[str, Any]) -> None:
        with self._lock:
            turn = self._turns.get(turn_id)
            if not turn or not turn["_claimed"]:
                return
            plan = response.get("plan") or {}
            result = response.get("result") or {}
            state = str(plan.get("state") or "failed")
            if state == "running" and turn["task_id"] == plan.get("task_id") and turn["outcome"] not in {"pending", "running"}:
                return
            report = result.get("verification_report") or {}
            actions = result.get("device_actions") or ([result["device_action"]] if result.get("device_action") else [])
            # Only device-returned observations and fabric receipts can describe a PC action.
            receipts = []
            for action in actions[:4]:
                fabric = action.get("command_fabric") or {}
                receipts.append({
                    "kind": str((action.get("action") or {}).get("kind") or "device_action")[:80],
                    "ok": bool(action.get("ok")), "signed": bool(fabric.get("signature_verified")),
                    "nonce_claimed": bool(fabric.get("nonce_claimed")),
                })
            outcome = state
            if state == "completed":
                outcome = "reply_generated" if plan.get("task_type") == "general_assistance" else "verified" if report.get("status") == "verified" else "completed_unverified"
            failure_stage = None
            if state == "blocked":
                failure_stage = "authorization"
            elif state in {"failed", "partially_completed"}:
                failure_stage = "verification" if any(not receipt["ok"] and receipt["signed"] for receipt in receipts) else "execution"
            turn.update(
                stage="execution_finished", outcome=outcome, task_id=plan.get("task_id") or turn["task_id"], task_type=plan.get("task_type") or turn["task_type"],
                verification=str(report.get("status") or "not_reported"), actions=receipts,
                command_ms=max(0, round((self._clock() - turn["_command_started"]) * 1000)),
                failure_stage=failure_stage,
            )

    def planned(self, turn_id: str | None, plan: dict[str, Any]) -> None:
        with self._lock:
            turn = self._turns.get(turn_id)
            if turn and turn["_claimed"]:
                turn.update(task_id=plan.get("task_id"), task_type=plan.get("task_type"),
                            interpretation_ms=max(0, round((self._clock() - turn["_command_started"]) * 1000)))

    def finish_task(self, plan: dict[str, Any], result: dict[str, Any]) -> None:
        with self._lock:
            ids = [key for key, value in self._turns.items() if value["task_id"] == plan.get("task_id")]
        for key in ids:
            self.finished(key, {"plan": plan, "result": result})

    def speech_queued(self, turn_id: str | None, *, suppressed: bool = False) -> None:
        with self._lock:
            turn = self._turns.get(turn_id)
            if turn and turn["_claimed"]:
                turn.update(speech_state="suppressed" if suppressed else "queued", _speech_started=self._clock())

    def audio_started(self, turn_id: str | None) -> None:
        with self._lock:
            turn = self._turns.get(turn_id)
            if not turn or "_speech_started" not in turn or turn["first_audio_ms"] is not None:
                return
            now = self._clock()
            turn.update(
                speech_state="playing", first_audio_ms=max(0, round((now - turn["_speech_started"]) * 1000)),
                recognition_to_audio_ms=max(0, round((now - turn["_recognized"]) * 1000)),
                capture_to_audio_ms=max(0, round((now - turn["_started"]) * 1000)),
            )

    def speech_finished(self, turn_id: str | None, outcome: dict[str, Any]) -> None:
        with self._lock:
            turn = self._turns.get(turn_id)
            if turn and turn["_claimed"]:
                turn["speech_state"] = "failed" if not outcome.get("ok") else "cancelled" if outcome.get("stopped") else "completed"
                if not outcome.get("ok"):
                    turn["failure_stage"] = "speech_output"

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            self._prune()
            turns = sorted(reversed(list(self._turns.values())), key=lambda turn: turn["_last_observed"], reverse=True)
            return [deepcopy({**{key: value for key, value in turn.items() if not key.startswith("_")},
                              "age_seconds": round(max(0, self._clock() - turn["_last_observed"]), 1)}) for turn in turns]


VOICE_TURNS = VoiceTurnStore()
