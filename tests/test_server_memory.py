import unittest
from unittest.mock import patch

from auris.memory_service import MemoryValidationError
from auris.server import AurisHandler


class _HandlerDouble:
    def __init__(self):
        self.payload = None
        self.status = None

    def _send_json(self, payload, status=200):
        self.payload = payload
        self.status = status


class ServerMemoryTests(unittest.TestCase):
    @patch("auris.server.record_event")
    @patch("auris.server.index_memory", return_value={"ok": True})
    @patch("auris.server.store_memory")
    def test_dashboard_creation_fixes_user_provenance_and_audit_minimises_content(
        self, store, _index, record_event
    ):
        store.return_value = {
            "ok": True,
            "memory": {
                "memory_id": "memory-id",
                "category": "decision",
                "project_id": "auris-one",
            },
            "duplicate": False,
            "conflicts": [],
            "requires_resolution": False,
        }
        handler = _HandlerDouble()

        AurisHandler._handle_memory(
            handler,
            {
                "content": "Use provider B",
                "category": "decision",
                "source_type": "external_unverified",
                "project_id": "auris-one",
            },
        )

        self.assertEqual(handler.status, 201)
        self.assertEqual(store.call_args.kwargs["source_type"], "user_confirmed")
        self.assertNotIn("content", record_event.call_args.args[1])
        self.assertFalse(record_event.call_args.args[1]["content_stored_in_audit"])

    @patch("auris.server.store_memory", side_effect=MemoryValidationError("Secret rejected."))
    def test_dashboard_validation_failure_returns_400(self, _store):
        handler = _HandlerDouble()

        AurisHandler._handle_memory(handler, {"content": "password is secret"})

        self.assertEqual(handler.status, 400)
        self.assertFalse(handler.payload["ok"])
        self.assertEqual(handler.payload["error"], "Secret rejected.")

    @patch("auris.server.record_event")
    @patch("auris.server.index_memory", return_value={"ok": True})
    @patch("auris.server.correct_memory")
    def test_correction_endpoint_indexes_replacement_and_audits_ids_only(
        self, correct, index, record_event
    ):
        correct.return_value = {
            "ok": True,
            "memory": {"memory_id": "new-memory"},
            "superseded_memory_id": "old-memory",
        }
        handler = _HandlerDouble()

        AurisHandler._handle_memory_correction(
            handler,
            "/api/memories/old-memory/correct",
            {"content": "Corrected", "reason": "Changed by Devansh"},
        )

        self.assertEqual(handler.status, 200)
        index.assert_called_once_with("new-memory")
        self.assertNotIn("content", record_event.call_args.args[1])

    @patch("auris.server.record_event")
    @patch("auris.server.resolve_memory_conflict")
    def test_conflict_endpoint_binds_explicit_chosen_memory(self, resolve, record_event):
        resolve.return_value = {
            "ok": True,
            "conflict": {"resolution": "selected_current"},
            "memories": [],
        }
        handler = _HandlerDouble()

        AurisHandler._handle_memory_conflict_resolution(
            handler,
            "/api/memory/conflicts/conflict-id/resolve",
            {"chosen_memory_id": "chosen-memory"},
        )

        resolve.assert_called_once_with(
            "conflict-id", chosen_memory_id="chosen-memory", keep_both=False
        )
        self.assertTrue(handler.payload["ok"])
        self.assertNotIn("content", record_event.call_args.args[1])

    @patch("auris.server.record_event")
    @patch("auris.server.set_memory_category_enabled")
    def test_category_endpoint_requires_real_boolean(self, set_enabled, _record_event):
        invalid = _HandlerDouble()
        AurisHandler._handle_memory_category(
            invalid,
            "/api/memory/categories/research",
            {"enabled": "false"},
        )
        self.assertEqual(invalid.status, 400)
        set_enabled.assert_not_called()

        valid = _HandlerDouble()
        set_enabled.return_value = {"research": False}
        AurisHandler._handle_memory_category(
            valid,
            "/api/memory/categories/research",
            {"enabled": False},
        )
        set_enabled.assert_called_once_with("research", False)
        self.assertFalse(valid.payload["categories"]["research"])


if __name__ == "__main__":
    unittest.main()
