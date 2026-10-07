import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auris.auth import (
    BootstrapCodeStore,
    access_token_valid,
    csrf_token_valid,
    initialize_portal_auth,
    harden_private_directory,
    session_cookie_header,
    session_cookie_valid,
)


class AuthTests(unittest.TestCase):
    @patch("auris.auth._harden_windows_acl", return_value=True)
    def test_private_directory_children_inherit_owner_only_acl(self, acl):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertTrue(harden_private_directory(root))
            acl.assert_called_once_with(root, inherit_children=True)

    @patch("auris.auth._harden_windows_acl", return_value=False)
    def test_private_directory_acl_failure_is_reported(self, acl):
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(harden_private_directory(Path(folder)))

    def test_bootstrap_codes_are_short_lived_and_single_use(self):
        store = BootstrapCodeStore(ttl_seconds=30)
        code = store.issue()["code"]

        self.assertTrue(store.consume(code))
        self.assertFalse(store.consume(code))

    @patch("auris.auth._harden_windows_acl", return_value=True)
    def test_portal_secret_is_persistent_and_tokens_are_derived(self, _acl):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "portal.token"
            first = initialize_portal_auth(path)
            second = initialize_portal_auth(path)

            self.assertEqual(first.access_token, second.access_token)
            self.assertNotEqual(first.access_token, first.session_token)
            self.assertNotEqual(first.session_token, first.csrf_token)
            self.assertTrue(access_token_valid(first.access_token, first))
            self.assertTrue(csrf_token_valid(first.csrf_token, first))

    @patch("auris.auth._harden_windows_acl", return_value=True)
    def test_session_cookie_is_http_only_and_validated(self, _acl):
        with tempfile.TemporaryDirectory() as folder:
            auth = initialize_portal_auth(Path(folder) / "portal.token")
            header = session_cookie_header(auth)

            self.assertIn("HttpOnly", header)
            self.assertIn("SameSite=Strict", header)
            self.assertTrue(session_cookie_valid(f"auris_session={auth.session_token}", auth))
            self.assertFalse(session_cookie_valid("auris_session=wrong", auth))


if __name__ == "__main__":
    unittest.main()
