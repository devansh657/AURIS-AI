import unittest

from auris.privacy import minimise_persisted_result


class PrivacyTests(unittest.TestCase):
    def test_read_only_account_items_are_removed_from_durable_results(self):
        live = {
            "message": "Found one contact.",
            "communications_action": {
                "operation": "search_contacts",
                "items": [{"name": "Private Person", "email": "private@example.com"}],
            },
        }

        durable = minimise_persisted_result(live)

        self.assertEqual(len(live["communications_action"]["items"]), 1)
        self.assertNotIn("items", durable["communications_action"])
        self.assertEqual(durable["communications_action"]["item_count"], 1)
        self.assertFalse(durable["communications_action"]["content_persisted"])

    def test_write_receipts_remain_available_for_audit(self):
        live = {
            "communications_action": {
                "operation": "draft",
                "entry_id": "draft-id",
                "items": [],
            }
        }

        self.assertEqual(minimise_persisted_result(live), live)


if __name__ == "__main__":
    unittest.main()
