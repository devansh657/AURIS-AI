import tempfile
import unittest
from pathlib import Path

from auris.project_agent import match_project_open_command, resolve_project_open_action


ROOT = Path(__file__).resolve().parents[1]


class ProjectAgentTests(unittest.TestCase):
    def test_matches_selected_and_named_project_commands(self):
        selected = match_project_open_command("AURIS, open this project")
        named = match_project_open_command("open my InfraGuard project")

        self.assertTrue(selected.use_selected_project)
        self.assertEqual(named.requested_name, "infraguard")
        self.assertFalse(named.use_selected_project)
        self.assertIsNone(match_project_open_command("open Project Gutenberg"))

    def test_resolves_one_registered_root_to_typed_device_action(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            projects = [
                {
                    "project_id": "infraguard-ai",
                    "name": "InfraGuard AI",
                    "root_path": folder,
                }
            ]
            request = match_project_open_command("open my InfraGuard project")

            action, project, error = resolve_project_open_action(
                request,
                selected_project_id=None,
                projects=projects,
            )

        self.assertIsNone(error)
        self.assertEqual(project["project_id"], "infraguard-ai")
        self.assertEqual(action.kind, "open_folder")
        self.assertEqual(action.source, "registered_project")
        self.assertEqual(action.target, str(Path(folder).resolve()))

    def test_refuses_unregistered_or_ambiguous_project(self):
        projects = [
            {"project_id": "career", "name": "Career", "root_path": None},
            {"project_id": "career-two", "name": "Career", "root_path": None},
        ]
        unregistered = resolve_project_open_action(
            match_project_open_command("open this project"),
            selected_project_id="career",
            projects=projects,
        )
        ambiguous = resolve_project_open_action(
            match_project_open_command("open my career project"),
            selected_project_id=None,
            projects=projects,
        )

        self.assertIsNone(unregistered[0])
        self.assertIn("registered local root", unregistered[2])
        self.assertIsNone(ambiguous[0])
        self.assertIn("could not resolve", ambiguous[2].casefold())


if __name__ == "__main__":
    unittest.main()
