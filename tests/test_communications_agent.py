import json
import subprocess
import unittest
from unittest.mock import patch

from auris.communications_agent import (
    CommunicationRequest,
    communication_approval_details,
    execute_communication_request,
    match_communication_command,
    productivity_status,
)


class CommunicationsAgentTests(unittest.TestCase):
    def test_parses_bounded_mail_calendar_and_send_requests(self):
        search = match_communication_command("AURIS, search my email for dissertation feedback")
        calendar = match_communication_command("show my calendar for the next 10 days")
        contacts = match_communication_command("AURIS, find my contact named Ada Lovelace")
        send = match_communication_command(
            "send email to person@example.com subject Project update saying The tests pass."
        )

        self.assertEqual(search.kind, "search_mail")
        self.assertEqual(search.query, "dissertation feedback")
        self.assertEqual(calendar.kind, "calendar")
        self.assertEqual(calendar.days, 10)
        self.assertEqual(contacts.kind, "search_contacts")
        self.assertEqual(contacts.query, "Ada Lovelace")
        self.assertEqual(send.kind, "send")
        self.assertEqual(send.recipient, "person@example.com")
        self.assertIsNone(match_communication_command("send an email to my professor"))

    def test_parses_phone_status_and_outbound_call_without_falling_through_to_chat(self):
        status = match_communication_command("show AURIS phone status")
        phone = match_communication_command("call MOM")
        whatsapp = match_communication_command("make a WhatsApp audio call to MOM")

        self.assertEqual(status.kind, "phone_status")
        self.assertEqual(phone.kind, "start_call")
        self.assertEqual(phone.channel, "phone")
        self.assertEqual(phone.contact, "MOM")
        self.assertEqual(whatsapp.kind, "start_call")
        self.assertEqual(whatsapp.channel, "whatsapp")
        self.assertEqual(whatsapp.contact, "MOM")

    def test_outbound_call_approval_discloses_only_contact_and_channel(self):
        target, summary = communication_approval_details("make a WhatsApp audio call to MOM")

        self.assertEqual(target, "MOM")
        self.assertIn("whatsapp audio call", summary)
        self.assertNotIn("+44", summary)
        self.assertNotIn("+91", summary)

    @patch("auris.communications_agent.discover_installed_applications", return_value=[])
    def test_missing_whatsapp_fails_without_claiming_call_started(self, applications):
        result = execute_communication_request(
            CommunicationRequest("start_call", channel="whatsapp", contact="MOM")
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["connector_state"], "application_required")
        self.assertFalse(result["call_started"])
        self.assertIn("no WhatsApp call was started", result["verification"])

    def test_send_approval_discloses_recipient_subject_and_body(self):
        target, summary = communication_approval_details(
            "send email to person@example.com subject Project update saying The tests pass."
        )

        self.assertEqual(target, "person@example.com")
        self.assertIn("SUBJECT: Project update", summary)
        self.assertIn("BODY: The tests pass.", summary)

    @patch("auris.communications_agent.subprocess.run")
    def test_outlook_payload_uses_stdin_not_process_arguments(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"ok":true,"operation":"draft","entry_id":"draft-1"}\n',
            stderr="",
        )
        request = CommunicationRequest(
            "draft",
            recipient="person@example.com",
            subject="Confidential subject",
            body="Private body",
        )

        outcome = execute_communication_request(request)

        self.assertTrue(outcome["ok"])
        arguments = run.call_args.args[0]
        self.assertNotIn("Confidential subject", " ".join(arguments))
        payload = json.loads(run.call_args.kwargs["input"])
        self.assertEqual(payload["body"], "Private body")

    @patch("auris.communications_agent._classic_outlook_profile_exists", return_value=False)
    @patch("auris.communications_agent._classic_outlook_available", return_value=True)
    @patch("auris.communications_agent.onedrive_roots", return_value=())
    @patch("auris.communications_agent.discover_installed_applications", return_value=[])
    def test_status_reports_missing_authorization_honestly(
        self, applications, roots, classic_available, profile_exists
    ):
        status = productivity_status()

        self.assertFalse(status["outlook"]["connected"])
        self.assertEqual(status["outlook"]["state"], "profile_required")
        self.assertIn("search_contacts", status["outlook"]["permissions"])
        self.assertFalse(status["onedrive"]["connected"])

    @patch("auris.communications_agent._invoke_outlook")
    def test_contact_lookup_is_read_only_and_content_minimised_for_audit(self, invoke):
        invoke.return_value = {
            "ok": True,
            "operation": "search_contacts",
            "scanned": 14,
            "items": [{"name": "Ada Lovelace", "email": "ada@example.com"}],
        }

        result = execute_communication_request(
            CommunicationRequest("search_contacts", query="Ada Lovelace")
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["items"][0]["name"], "Ada Lovelace")
        self.assertIn("scanned read-only", result["verification"])
        self.assertIn("not added to durable task history", result["verification"])


if __name__ == "__main__":
    unittest.main()
