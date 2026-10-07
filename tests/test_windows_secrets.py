import os
import unittest

from auris.windows_secrets import (
    DPAPI_PREFIX,
    dpapi_available,
    protect_for_current_user,
    unprotect_for_current_user,
)


@unittest.skipUnless(os.name == "nt", "Windows DPAPI test")
class WindowsSecretsTests(unittest.TestCase):
    def test_round_trip_is_user_and_purpose_bound(self):
        secret = b"AURIS test credential"

        protected = protect_for_current_user(secret, purpose="test-purpose")

        self.assertTrue(dpapi_available())
        self.assertTrue(protected.startswith(DPAPI_PREFIX))
        self.assertNotIn(secret.hex(), protected)
        self.assertEqual(
            unprotect_for_current_user(protected, purpose="test-purpose"),
            secret,
        )
        with self.assertRaises(OSError):
            unprotect_for_current_user(protected, purpose="wrong-purpose")


if __name__ == "__main__":
    unittest.main()
