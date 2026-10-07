import json
import base64
import hashlib
import hmac
import secrets
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from auris.cloud_channel import CloudChannelClient, verify_remote_command
from auris.database import upsert_device
from auris_cloud.config import CloudSettings
from auris_cloud.crypto import (
    CloudSigner,
    create_test_device_certificate,
    request_proof_bytes,
    sign_device_request,
)
from auris_cloud.store import CloudStore


@unittest.skipIf(TestClient is None, "FastAPI cloud test dependencies are not installed")
class CloudCommandApiTests(unittest.TestCase):
    def setUp(self):
        from auris_cloud.app import create_app

        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.admin_token = "admin_" + "A" * 56
        self.settings = CloudSettings(
            environment="test",
            admin_token=self.admin_token,
            signing_private_key_path=root / "unused.pem",
            database_path=root / "cloud.db",
            require_https=False,
            lease_seconds=30,
            telephony_enabled=True,
            telephony_public_base_url="https://phone.auris.test",
            telephony_relay_url="wss://phone.auris.test/v1/telephony/relay",
            telephony_owner_number="+447700900001",
            twilio_auth_token="twilio-test-token-that-is-long-enough",
        )
        self.store = CloudStore(self.settings.database_path)
        self.cloud_signer = CloudSigner(Ed25519PrivateKey.generate())
        def phone_responder(messages, _system):
            if "private post-call brief" in messages[-1]["content"]:
                return json.dumps(
                    {
                        "summary": "An urgent caller requested Devansh.",
                        "caller_request": "Speak with Devansh.",
                        "promised_actions": [],
                        "urgency": "urgent",
                        "follow_up": "Review the transferred call.",
                    }
                )
            return "I can take a message for Devansh."

        self.client = TestClient(
            create_app(
                self.settings,
                store=self.store,
                signer=self.cloud_signer,
                phone_responder=phone_responder,
            )
        )
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.device_id = str(uuid4())
        self.device_key = Ed25519PrivateKey.generate()
        self.certificate_pem = create_test_device_certificate(
            self.device_key, self.device_id
        )
        enrolment = self.client.post(
            "/v1/enrolments",
            headers=self.admin_headers,
            json={"permissions": ["list_folder", "launch_app"]},
        )
        self.assertEqual(enrolment.status_code, 201)
        self.enrolment_code = enrolment.json()["enrolment"]["code"]
        registration = self.client.post(
            "/v1/devices/register",
            json={
                "enrolment_code": self.enrolment_code,
                "device_id": self.device_id,
                "display_name": "Devansh Laptop",
                "platform": "Windows 11",
                "certificate_pem": self.certificate_pem,
            },
        )
        self.assertEqual(registration.status_code, 201, registration.text)

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    def test_enrolment_schema_accepts_all_bounded_device_permissions(self):
        permissions = [
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

        response = self.client.post(
            "/v1/enrolments",
            headers=self.admin_headers,
            json={"permissions": permissions},
        )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["enrolment"]["permissions"], permissions)

    def device_headers(
        self,
        method,
        path,
        *,
        body=b"",
        timestamp=None,
        nonce=None,
        private_key=None,
        device_id=None,
    ):
        request_device_id = device_id or self.device_id
        issued_at = timestamp or datetime.now(timezone.utc).isoformat()
        request_nonce = nonce or secrets.token_urlsafe(32)
        proof = request_proof_bytes(
            method,
            path,
            request_device_id,
            issued_at,
            request_nonce,
            body,
        )
        return {
            "X-AURIS-Device-ID": request_device_id,
            "X-AURIS-Timestamp": issued_at,
            "X-AURIS-Nonce": request_nonce,
            "X-AURIS-Signature": sign_device_request(
                private_key or self.device_key, proof
            ),
        }

    def queue_command(self, kind="list_folder"):
        response = self.client.post(
            f"/v1/devices/{self.device_id}/commands",
            headers=self.admin_headers,
            json={
                "action_id": "list_auris_workspace",
                "kind": kind,
                "target": "AURIS Workspace",
            },
        )
        return response

    def twilio_signature(self, url, params):
        signed = url + "".join(key + str(params[key]) for key in sorted(params))
        return base64.b64encode(
            hmac.new(
                self.settings.twilio_auth_token.encode(),
                signed.encode(),
                hashlib.sha1,
            ).digest()
        ).decode()

    def test_signed_incoming_call_webhook_returns_disclosed_conversation_relay(self):
        params = {
            "CallSid": "CA" + "a" * 32,
            "From": "+447700900002",
            "To": "+447700900003",
        }
        url = self.settings.telephony_public_base_url + "/v1/telephony/incoming"

        rejected = self.client.post("/v1/telephony/incoming", data=params)
        accepted = self.client.post(
            "/v1/telephony/incoming",
            data=params,
            headers={"X-Twilio-Signature": self.twilio_signature(url, params)},
        )

        self.assertEqual(rejected.status_code, 401)
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertIn("ConversationRelay", accepted.text)
        self.assertIn("AI assistant", accepted.text)
        self.assertIn("wss://phone.auris.test/v1/telephony/relay", accepted.text)

    def test_phone_relay_transfers_urgent_call_and_keeps_summary_only(self):
        relay_headers = {
            "X-Twilio-Signature": self.twilio_signature(
                self.settings.telephony_relay_url, {}
            )
        }
        call_sid = "CA" + "b" * 32
        with self.client.websocket_connect(
            "/v1/telephony/relay", headers=relay_headers
        ) as websocket:
            websocket.send_json(
                {
                    "type": "setup",
                    "callSid": call_sid,
                    "from": "+447700900002",
                    "to": "+447700900003",
                }
            )
            websocket.send_json(
                {
                    "type": "prompt",
                    "voicePrompt": "This is urgent. Please connect me to Devansh.",
                    "last": True,
                }
            )
            spoken = websocket.receive_json()
            handoff = websocket.receive_json()

        calls = self.client.get(
            "/v1/telephony/calls", headers=self.admin_headers
        ).json()["calls"]

        self.assertEqual(spoken["type"], "text")
        self.assertEqual(handoff["type"], "end")
        self.assertIn("live-agent-handoff", handoff["handoffData"])
        self.assertEqual(calls[0]["call_id"], call_sid)
        self.assertEqual(calls[0]["caller"], "***0002")
        self.assertTrue(calls[0]["transfer_requested"])
        self.assertFalse(calls[0]["audio_recorded"])
        self.assertFalse(calls[0]["raw_transcript_persisted"])
        self.assertNotIn("transcript", calls[0])

    def test_signed_handoff_dials_only_configured_owner_number(self):
        details = json.dumps(
            {"reasonCode": "live-agent-handoff", "reason": "caller_requested_handoff"},
            separators=(",", ":"),
        )
        params = {"CallSid": "CA" + "c" * 32, "HandoffData": details}
        url = self.settings.telephony_public_base_url + "/v1/telephony/handoff"

        response = self.client.post(
            "/v1/telephony/handoff",
            data=params,
            headers={"X-Twilio-Signature": self.twilio_signature(url, params)},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("<Dial", response.text)
        self.assertIn(self.settings.telephony_owner_number, response.text)

    def test_signed_command_lifecycle_and_nonce_replay_rejection(self):
        queued = self.queue_command()

        self.assertEqual(queued.status_code, 201, queued.text)
        envelope = queued.json()["command"]["envelope"]
        self.assertEqual(
            set(envelope),
            {
                "command_id",
                "device_id",
                "tool",
                "parameters",
                "permission_scope",
                "issued_at",
                "expires_at",
                "nonce",
                "signature",
            },
        )
        self.assertTrue(self.cloud_signer.verify_envelope(envelope))

        poll_path = "/v1/device/commands/next"
        poll_headers = self.device_headers("GET", poll_path)
        polled = self.client.get(poll_path, headers=poll_headers)
        replayed = self.client.get(poll_path, headers=poll_headers)

        self.assertEqual(polled.status_code, 200, polled.text)
        self.assertEqual(polled.json()["command"]["command_id"], envelope["command_id"])
        self.assertEqual(replayed.status_code, 409)

        ack_path = f"/v1/device/commands/{envelope['command_id']}/ack"
        ack_body = json.dumps(
            {"state": "completed", "verification_summary": "Read-only listing verified."},
            separators=(",", ":"),
        ).encode("utf-8")
        ack_headers = {
            **self.device_headers("POST", ack_path, body=ack_body),
            "Content-Type": "application/json",
        }
        acknowledged = self.client.post(ack_path, headers=ack_headers, content=ack_body)

        self.assertEqual(acknowledged.status_code, 200, acknowledged.text)
        self.assertEqual(acknowledged.json()["command"]["state"], "completed")

    def test_outbound_device_client_polls_verifies_and_acknowledges(self):
        queued = self.queue_command()
        self.assertEqual(queued.status_code, 201)
        edge_database = Path(self.temp_dir.name) / "edge.db"
        upsert_device(
            {
                "device_id": self.device_id,
                "display_name": "Devansh Laptop",
                "machine_name": "DEVANSH-LAPTOP",
                "platform": "Windows 11",
                "trust_state": "pinned_certificate",
                "permissions": ["list_folder", "launch_app"],
                "key_fingerprint": "f" * 64,
                "certificate_state": "pinned",
            },
            path=edge_database,
        )

        def transport(method, path, body, headers):
            response = self.client.request(method, path, content=body, headers=headers)
            return response.status_code, response.content

        device_client = CloudChannelClient(
            endpoint="https://auris.test",
            device_id=self.device_id,
            device_private_key=self.device_key,
            transport=transport,
        )

        envelope = device_client.poll()
        accepted = verify_remote_command(
            envelope,
            cloud_public_key_b64=self.cloud_signer.public_key_b64,
            expected_device_id=self.device_id,
            database_path=edge_database,
        )
        replayed = verify_remote_command(
            envelope,
            cloud_public_key_b64=self.cloud_signer.public_key_b64,
            expected_device_id=self.device_id,
            database_path=edge_database,
        )
        acknowledged = device_client.acknowledge(
            envelope["command_id"],
            state="completed",
            verification_summary="Signed envelope verified; no Windows mutation in contract test.",
        )

        self.assertTrue(accepted.ok)
        self.assertTrue(accepted.signature_verified)
        self.assertTrue(accepted.nonce_claimed)
        self.assertFalse(replayed.ok)
        self.assertIn("already consumed", replayed.error)
        self.assertEqual(acknowledged["command"]["state"], "completed")

    def test_outbound_client_refuses_non_https_endpoint(self):
        with self.assertRaises(ValueError):
            CloudChannelClient(
                endpoint="http://auris.test",
                device_id=self.device_id,
                device_private_key=self.device_key,
            )

    def test_consumed_enrolment_code_cannot_register_another_device(self):
        second_id = str(uuid4())
        second_key = Ed25519PrivateKey.generate()

        response = self.client.post(
            "/v1/devices/register",
            json={
                "enrolment_code": self.enrolment_code,
                "device_id": second_id,
                "display_name": "Second Device",
                "platform": "Windows 11",
                "certificate_pem": create_test_device_certificate(second_key, second_id),
            },
        )

        self.assertEqual(response.status_code, 401)

    def test_certificate_identity_mismatch_is_rejected_without_consuming_code(self):
        enrolment = self.client.post(
            "/v1/enrolments",
            headers=self.admin_headers,
            json={"permissions": ["list_folder"]},
        ).json()["enrolment"]
        requested_id = str(uuid4())
        certificate_id = str(uuid4())

        response = self.client.post(
            "/v1/devices/register",
            json={
                "enrolment_code": enrolment["code"],
                "device_id": requested_id,
                "display_name": "Mismatched Device",
                "platform": "Windows 11",
                "certificate_pem": create_test_device_certificate(
                    Ed25519PrivateKey.generate(), certificate_id
                ),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("does not match", response.json()["detail"])

    def test_bad_and_expired_device_proofs_are_rejected(self):
        path = "/v1/device/commands/next"
        bad_signature = self.client.get(
            path,
            headers=self.device_headers(
                "GET", path, private_key=Ed25519PrivateKey.generate()
            ),
        )
        expired = self.client.get(
            path,
            headers=self.device_headers(
                "GET",
                path,
                timestamp=(datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
            ),
        )

        self.assertEqual(bad_signature.status_code, 401)
        self.assertEqual(expired.status_code, 401)

    def test_permission_scope_is_enforced_before_queueing(self):
        response = self.queue_command(kind="media_key")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.store.list_commands(), [])

    def test_revoked_device_cannot_poll(self):
        revoked = self.client.post(
            f"/v1/devices/{self.device_id}/revoke", headers=self.admin_headers
        )
        path = "/v1/device/commands/next"

        response = self.client.get(path, headers=self.device_headers("GET", path))

        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(response.status_code, 403)

    def test_admin_endpoints_require_bearer_secret(self):
        response = self.client.get("/v1/devices")

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
