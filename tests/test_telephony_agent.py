import base64
import hashlib
import hmac
import json
import unittest

from auris.telephony_agent import (
    PhoneAssistant,
    TelephonyConfig,
    build_incoming_twiml,
    build_transfer_twiml,
    classify_call_turn,
    simulate_call,
    telephony_status,
    validate_twilio_signature,
)


class TelephonyAgentTests(unittest.TestCase):
    def setUp(self):
        self.config = TelephonyConfig(
            public_base_url="https://phone.auris.example",
            relay_url="wss://phone.auris.example/v1/telephony/relay",
            owner_number="+447700900001",
            auth_token="twilio-test-token-that-is-long-enough",
        )

    def test_call_policy_transfers_urgent_sensitive_and_requested_calls(self):
        self.assertEqual(classify_call_turn("This is an emergency at the hospital"), (True, "urgent", "emergency"))
        self.assertEqual(classify_call_turn("I need to give you my verification code"), (True, "important", "sensitive_information"))
        self.assertEqual(classify_call_turn("Please connect me to Devansh"), (True, "important", "caller_requested_handoff"))
        self.assertEqual(classify_call_turn("Please tell him the meeting is at four"), (False, "routine", ""))

    def test_twilio_signature_validation_rejects_tampering(self):
        url = "https://phone.auris.example/v1/telephony/incoming"
        params = {"CallSid": "CA" + "1" * 32, "From": "+447700900002"}
        signed = url + "".join(key + params[key] for key in sorted(params))
        signature = base64.b64encode(
            hmac.new(self.config.auth_token.encode(), signed.encode(), hashlib.sha1).digest()
        ).decode()

        self.assertTrue(validate_twilio_signature(self.config.auth_token, url, params, signature))
        self.assertFalse(validate_twilio_signature(self.config.auth_token, url, {**params, "From": "+447700900099"}, signature))

    def test_twiml_discloses_ai_and_uses_wss_with_handoff(self):
        incoming = build_incoming_twiml(self.config, "opaque-call-reference")
        transfer = build_transfer_twiml(self.config)

        self.assertIn("Devansh's AI assistant", incoming)
        self.assertIn("wss://phone.auris.example/v1/telephony/relay", incoming)
        self.assertIn("/v1/telephony/handoff", incoming)
        self.assertIn("ConversationRelay", incoming)
        self.assertIn("<Dial", transfer)
        self.assertIn("+447700900001", transfer)
        self.assertNotIn(self.config.auth_token, incoming)

    def test_simulation_transfers_and_persists_summary_only(self):
        def responder(messages, _system):
            if "private post-call brief" in messages[-1]["content"]:
                return json.dumps(
                    {
                        "summary": "The caller reported an urgent schedule change.",
                        "caller_request": "Speak to Devansh.",
                        "promised_actions": ["Untrusted model promise"],
                        "urgency": "urgent",
                        "follow_up": "Call back promptly.",
                    }
                )
            return "*Certainly.* I can take a message."

        result = simulate_call(
            ["My name is Alex.", "This is urgent, please connect me to Devansh."],
            responder=responder,
        )

        summary = result["summary"]
        self.assertTrue(result["turns"][-1]["transfer"])
        self.assertEqual(summary["caller"], "***0002")
        self.assertTrue(summary["disclosure_delivered"])
        self.assertFalse(summary["audio_recorded"])
        self.assertFalse(summary["raw_transcript_persisted"])
        self.assertEqual(summary["promised_actions"], [])
        self.assertNotIn("transcript", summary)

    def test_spoken_reply_removes_markup(self):
        assistant = PhoneAssistant(self.config, responder=lambda _messages, _system: "**Of course.** I can help with that.")
        session = assistant.start("CA" + "a" * 32, "+447700900002", "+447700900003")

        turn = assistant.respond(session, "Can I leave a message?")

        self.assertNotIn("*", turn.reply)
        self.assertIn("Of course", turn.reply)

    def test_status_never_exposes_numbers_or_credentials(self):
        status = telephony_status(self.config)

        serialized = json.dumps(status)
        self.assertTrue(status["available"])
        self.assertFalse(status["connected"])
        self.assertNotIn(self.config.owner_number, serialized)
        self.assertNotIn(self.config.auth_token, serialized)

    def test_deployment_rejects_loopback_credentials_and_untrusted_schemes(self):
        unsafe = TelephonyConfig(
            public_base_url="https://localhost:9000",
            relay_url="ws://user:secret@localhost/relay",
            owner_number="07700900001",
            auth_token="short",
        )

        self.assertFalse(unsafe.deployable)
        self.assertEqual(len(unsafe.validation_errors()), 4)


if __name__ == "__main__":
    unittest.main()
