import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from auris.database import revoke_device
from auris.device_agent import DeviceAction
from auris.device_fabric import (
    initialize_device_identity,
    issue_device_command,
    verify_and_claim_device_command,
)


class DeviceFabricTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.key_path = root / "device.key"
        self.identity_path = root / "device-identity.json"
        self.database_path = root / "auris-device.db"
        self.action = DeviceAction("open_test", "launch_app", "Open Test", "Test")

    def tearDown(self):
        self.temp_dir.cleanup()

    def issue(self, **kwargs):
        return issue_device_command(
            self.action,
            key_path=self.key_path,
            identity_path=self.identity_path,
            database_path=self.database_path,
            **kwargs,
        )

    def verify(self, envelope, **kwargs):
        return verify_and_claim_device_command(
            envelope,
            key_path=self.key_path,
            identity_path=self.identity_path,
            database_path=self.database_path,
            **kwargs,
        )

    def test_signed_command_is_claimed_once(self):
        envelope = self.issue()

        accepted = self.verify(envelope)
        replayed = self.verify(envelope)

        self.assertTrue(accepted.ok)
        self.assertTrue(accepted.signature_verified)
        self.assertTrue(accepted.nonce_claimed)
        self.assertFalse(replayed.ok)
        self.assertIn("already consumed", replayed.error)

    def test_tampered_expired_and_wrong_device_commands_are_rejected(self):
        tampered = self.issue()
        tampered["parameters"]["target"] = "Changed"
        expired = self.issue(ttl_seconds=5)
        wrong_device = self.issue()
        wrong_device["device_id"] = "00000000-0000-0000-0000-000000000000"

        self.assertIn("signature", self.verify(tampered).error)
        self.assertIn(
            "expired",
            self.verify(expired, now=datetime.now(timezone.utc) + timedelta(seconds=6)).error,
        )
        self.assertIn("wrong device", self.verify(wrong_device).error)

    def test_revoked_device_rejects_new_command(self):
        identity = initialize_device_identity(
            key_path=self.key_path,
            identity_path=self.identity_path,
            database_path=self.database_path,
        )
        envelope = self.issue()
        revoke_device(identity["device_id"], path=self.database_path)

        decision = self.verify(envelope)

        self.assertFalse(decision.ok)
        self.assertIn("revoked", decision.error)

    def test_signed_ui_interaction_permission_is_allowlisted(self):
        self.action = DeviceAction(
            "invoke_notepad_file",
            "invoke_control",
            "Invoke File in Notepad",
            "app=notepad;control_sha256=1234567890abcdef1234567890abcdef",
        )

        decision = self.verify(self.issue())

        self.assertTrue(decision.ok)
        self.assertTrue(decision.signature_verified)

    def test_signed_browser_interaction_permission_is_allowlisted(self):
        self.action = DeviceAction(
            "browser_fill_deadbeef",
            "browser_fill",
            "Fill approved browser field",
            "name=Acceptance note;value=" + "a" * 32,
        )

        decision = self.verify(self.issue())

        self.assertTrue(decision.ok)
        self.assertTrue(decision.nonce_claimed)

    def test_signed_browser_workflow_permission_is_allowlisted(self):
        self.action = DeviceAction(
            "browser_workflow_deadbeef",
            "browser_workflow",
            "Run approved browser mission",
            "steps=3;digest=" + "a" * 32,
        )

        decision = self.verify(self.issue())

        self.assertTrue(decision.ok)
        self.assertTrue(decision.signature_verified)
        self.assertTrue(decision.nonce_claimed)

    def test_signed_folder_creation_permission_is_allowlisted(self):
        self.action = DeviceAction(
            "create_folder_desktop_don",
            "create_folder",
            "Create folder DON",
            str(Path.home() / "Desktop" / "DON"),
        )

        decision = self.verify(self.issue())

        self.assertTrue(decision.ok)
        self.assertTrue(decision.nonce_claimed)

    def test_signed_text_file_creation_permission_is_allowlisted(self):
        self.action = DeviceAction(
            "create_note_desktop_status_txt",
            "create_text_file",
            "Create note Status.txt",
            "path=C:\\Users\\Devansh\\Desktop\\Status.txt;content_sha256=" + "a" * 64,
        )

        decision = self.verify(self.issue())

        self.assertTrue(decision.ok)
        self.assertTrue(decision.signature_verified)

    def test_signed_text_append_permission_is_allowlisted(self):
        self.action = DeviceAction(
            "append_note_documents_status_txt",
            "append_text_file",
            "Append to note Status.txt",
            "path=C:\\Users\\Devansh\\Documents\\Status.txt;pre=" + "a" * 32 + ";append=" + "b" * 32,
        )

        decision = self.verify(self.issue())

        self.assertTrue(decision.ok)
        self.assertTrue(decision.nonce_claimed)

    def test_signed_transfer_permissions_are_allowlisted(self):
        for kind in ("rename_path", "copy_file", "move_file"):
            with self.subTest(kind=kind):
                self.action = DeviceAction(
                    f"{kind}_report_final",
                    kind,
                    f"{kind} report",
                    "source=C:\\Users\\Devansh\\Documents\\Report.txt;"
                    "destination=C:\\Users\\Devansh\\Desktop\\Final.txt",
                )
                decision = self.verify(self.issue())
                self.assertTrue(decision.ok)
                self.assertTrue(decision.nonce_claimed)

    def test_signed_recycle_permission_is_allowlisted(self):
        self.action = DeviceAction(
            "recycle_file_documents_old_txt",
            "recycle_file",
            "Move Old.txt to Recycle Bin",
            "path=C:\\Users\\Devansh\\Documents\\Old.txt;pre=" + "a" * 32,
        )

        decision = self.verify(self.issue())

        self.assertTrue(decision.ok)
        self.assertTrue(decision.signature_verified)
        self.assertTrue(decision.nonce_claimed)

    def test_signed_open_file_permission_is_allowlisted(self):
        self.action = DeviceAction(
            "open_file_documents_report_pdf",
            "open_file",
            "Open file Report.pdf",
            "C:\\Users\\Devansh\\Documents\\Report.pdf",
        )

        decision = self.verify(self.issue())

        self.assertTrue(decision.ok)
        self.assertTrue(decision.signature_verified)

    def test_signed_window_state_permissions_are_allowlisted(self):
        for kind in ("minimize_app", "maximize_app", "restore_app"):
            with self.subTest(kind=kind):
                self.action = DeviceAction(
                    f"{kind}_spotify",
                    kind,
                    f"{kind} Spotify",
                    "Spotify",
                )
                decision = self.verify(self.issue())
                self.assertTrue(decision.ok)
                self.assertTrue(decision.signature_verified)


    def test_signed_targeted_media_permission_is_allowlisted(self):
        self.action = DeviceAction(
            "play_spotify",
            "app_media",
            "Play media in Spotify",
            "Spotify",
            process_names=("spotify.exe",),
            key_code=0xB3,
        )

        decision = self.verify(self.issue())

        self.assertTrue(decision.ok)
        self.assertTrue(decision.signature_verified)


if __name__ == "__main__":
    unittest.main()
