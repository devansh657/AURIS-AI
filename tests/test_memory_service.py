import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from auris.database import (
    create_memory,
    delete_memory,
    get_memory,
    list_memory_embeddings,
    list_memory_versions,
    update_memory,
    upsert_memory_embedding,
)
from auris.memory_service import (
    MEMORY_CATEGORIES,
    MemoryValidationError,
    correct_memory,
    effective_memories,
    enrich_memory,
    memory_context_lines,
    memory_dashboard,
    resolve_memory_conflict,
    semantic_search_memories,
    set_memory_category_enabled,
    store_memory,
)


class MemoryServiceTests(unittest.TestCase):
    @patch("auris.memory_service.generate_embeddings")
    def test_semantic_search_ranks_related_memory(self, generate):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "auris.db"
            report = create_memory("Devansh prefers concise technical reports", project_id="auris-one", path=path)
            fitness = create_memory("Weekly strength training is on Monday", project_id="auris-one", path=path)
            upsert_memory_embedding(report["memory_id"], "nomic-embed-text", [1.0, 0.0], path=path)
            upsert_memory_embedding(fitness["memory_id"], "nomic-embed-text", [0.0, 1.0], path=path)
            generate.return_value = ([[1.0, 0.0]], "nomic-embed-text", 2)

            results = semantic_search_memories(
                "How should my technical report be written?",
                project_id="auris-one",
                path=path,
            )

            self.assertEqual(results[0]["memory_id"], report["memory_id"])
            self.assertGreater(results[0]["similarity"], results[1]["similarity"])
            self.assertEqual(results[1]["memory_id"], fitness["memory_id"])

    def test_deleting_memory_cascades_embedding(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "auris.db"
            memory = create_memory("Temporary fact", path=path)
            upsert_memory_embedding(memory["memory_id"], "test-model", [1.0, 0.0], path=path)

            self.assertTrue(delete_memory(memory["memory_id"], path=path))
            self.assertEqual(list_memory_embeddings([memory["memory_id"]], path=path), {})

    def test_all_memory_classes_and_decision_fields_are_structured(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "auris.db"
            created = []
            for category in MEMORY_CATEGORIES:
                result = store_memory(
                    f"A distinct {category} assertion",
                    category=category,
                    project_id="auris-one",
                    subject_key=f"subject-{category}",
                    structured_data={
                        "alternatives": ["Option B"],
                        "evidence": ["Observed result"],
                        "assumptions": ["Capacity remains available"],
                        "risks": ["Delay"],
                        "reason": "Best verified option",
                    }
                    if category == "decision"
                    else {},
                    path=path,
                )
                created.append(result["memory"])

            dashboard = memory_dashboard(project_id="auris-one", path=path)
            decision = next(item for item in created if item["category"] == "decision")

            self.assertEqual({item["category"] for item in created}, set(MEMORY_CATEGORIES))
            self.assertEqual(decision["structured_data"]["alternatives"], ["Option B"])
            self.assertEqual(decision["structured_data"]["outcome"], None)
            self.assertEqual(dashboard["summary"]["total"], len(MEMORY_CATEGORIES))
            self.assertTrue(all(dashboard["categories"].values()))

    def test_conflict_is_explicit_and_user_choice_supersedes_loser(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "auris.db"
            first = store_memory(
                "Development backend port is 8000",
                category="project",
                project_id="auris-one",
                subject_key="development backend port",
                environment="development",
                path=path,
            )["memory"]
            second_result = store_memory(
                "Development backend port is 8001",
                category="project",
                project_id="auris-one",
                subject_key="development backend port",
                environment="development",
                path=path,
            )
            second = second_result["memory"]

            self.assertTrue(second_result["requires_resolution"])
            self.assertEqual(get_memory(first["memory_id"], path=path)["status"], "active")
            self.assertEqual(get_memory(second["memory_id"], path=path)["status"], "conflicted")
            conflict = memory_dashboard(project_id="auris-one", path=path)["conflicts"][0]
            self.assertFalse(conflict["analysis"]["automatic_resolution"])
            self.assertEqual(conflict["analysis"]["required_action"], "ask_user")
            verified_before_resolution = second["verified_at"]

            resolved = resolve_memory_conflict(
                conflict["conflict_id"],
                chosen_memory_id=second["memory_id"],
                path=path,
            )

            self.assertTrue(resolved["ok"])
            self.assertEqual(get_memory(first["memory_id"], path=path)["status"], "superseded")
            current = get_memory(second["memory_id"], path=path)
            self.assertEqual(current["status"], "active")
            self.assertEqual(current["conflict_state"], "clear")
            self.assertGreaterEqual(current["verified_at"], verified_before_resolution)
            self.assertEqual(memory_dashboard(project_id="auris-one", path=path)["conflicts"], [])

    def test_correction_preserves_temporal_history_and_exact_supersession(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "auris.db"
            original = store_memory(
                "Preferred briefing time is 08:00",
                category="preference",
                subject_key="preferred briefing time",
                path=path,
            )["memory"]

            corrected = correct_memory(
                original["memory_id"],
                content="Preferred briefing time is 07:30",
                reason="Devansh changed the daily schedule.",
                path=path,
            )["memory"]

            previous = get_memory(original["memory_id"], path=path)
            self.assertEqual(previous["status"], "superseded")
            self.assertEqual(corrected["supersedes"], original["memory_id"])
            self.assertEqual(corrected["status"], "active")
            history = list_memory_versions(original["memory_id"], path=path)
            self.assertEqual([item["operation"] for item in history], ["superseded", "created"])

    def test_stale_memory_is_flagged_and_ranked_below_fresh_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "auris.db"
            stale = store_memory(
                "The deployment host is legacy.example",
                category="device",
                project_id="auris-one",
                subject_key="deployment host",
                path=path,
            )["memory"]
            old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
            update_memory(stale["memory_id"], {"verified_at": old}, path=path)

            self.assertEqual(
                enrich_memory(get_memory(stale["memory_id"], path=path))["temporal_state"],
                "stale",
            )

    def test_secrets_and_disabled_categories_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "auris.db"
            with self.assertRaisesRegex(MemoryValidationError, "cannot be stored"):
                store_memory("My API key is sk-abcdefghijklmnop1234", path=path)
            with self.assertRaisesRegex(MemoryValidationError, "structured data"):
                store_memory(
                    "Deployment credential reference",
                    structured_data={"access_token": "access token: abcdefghijklmnop"},
                    path=path,
                )

            existing = store_memory(
                "Alex is an authorised contact",
                category="relationship",
                subject_key="alex",
                path=path,
            )["memory"]

            categories = set_memory_category_enabled("relationship", False, path=path)
            self.assertFalse(categories["relationship"])
            self.assertNotIn(
                existing["memory_id"],
                {item["memory_id"] for item in effective_memories(project_id=None, path=path)},
            )
            with self.assertRaisesRegex(MemoryValidationError, "disabled"):
                store_memory(
                    "Context about an authorised contact",
                    category="relationship",
                    subject_key="contact",
                    path=path,
                )

    @patch("auris.memory_service.semantic_search_memories")
    def test_non_normal_memory_only_enters_loopback_model_context(self, search):
        search.return_value = [
            {
                "memory_id": "personal-1",
                "category": "profile",
                "content": "A private personal detail",
                "sensitivity": "personal",
                "environment": None,
                "requires_resolution": False,
                "temporal_state": "current",
            }
        ]
        remote_environment = {
            "AURIS_MODEL_PROVIDER": "openai_compatible",
            "AURIS_MODEL_ENDPOINT": "https://models.example.test/v1/chat/completions",
            "AURIS_MODEL_NAME": "remote-model",
        }
        with patch.dict("os.environ", remote_environment, clear=True):
            self.assertEqual(memory_context_lines("detail", project_id=None), [])

        local_environment = {
            "AURIS_MODEL_PROVIDER": "ollama",
            "AURIS_MODEL_ENDPOINT": "http://127.0.0.1:11434",
            "AURIS_MODEL_NAME": "gemma3",
        }
        with patch.dict("os.environ", local_environment, clear=True):
            self.assertEqual(
                memory_context_lines("detail", project_id=None),
                ["profile memory: A private personal detail"],
            )


if __name__ == "__main__":
    unittest.main()
