import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from auris.model_gateway import ModelReply
from auris.work_product_agent import execute_work_product, match_work_product_command


class WorkProductAgentTests(unittest.TestCase):
    def test_coding_brief_preserves_punctuation_multiline_logic_and_full_length(self):
        command = 'AURIS, build a Python app called "How to Greet" that returns "Hello, Ada!".\nLogic:\n    Keep spaces, punctuation, and commas.\n' + "Additional details. " * 50
        request = match_work_product_command(command)
        self.assertEqual(request.kind, "code_project")
        self.assertEqual(request.requested_name, "How to Greet")
        self.assertIn('"Hello, Ada!"', request.brief)
        self.assertIn("\n    Keep spaces, punctuation, and commas.", request.brief)
        self.assertGreater(len(request.brief), 600)
        self.assertEqual(match_work_product_command("build a Python project called Budget to track expenses").requested_name, "Budget")

    def test_matches_projects_documents_and_research_reports(self):
        project = match_work_product_command("AURIS, make a chatbot for me fully functional")
        polite_project = match_work_product_command("AURIS, could you please build a web app for me")
        document = match_work_product_command("create a Word document about renewable energy")
        research = match_work_product_command(
            "research quantum error correction and create a Word report"
        )
        presentation = match_work_product_command("create a PowerPoint presentation about edge AI")
        spreadsheet = match_work_product_command("build an Excel tracker for project milestones")
        pdf = match_work_product_command("create a PDF report about energy storage")
        titled = match_work_product_command(
            "create a Word document titled AURIS Capability Report about verified automation"
        )

        self.assertEqual(project.kind, "code_project")
        self.assertEqual(polite_project.kind, "code_project")
        self.assertEqual(document.kind, "document")
        self.assertEqual(document.brief, "renewable energy")
        self.assertEqual(research.kind, "research_report")
        self.assertEqual(research.brief, "quantum error correction")
        self.assertEqual(presentation.kind, "presentation")
        self.assertEqual(spreadsheet.kind, "spreadsheet")
        self.assertEqual(pdf.output_format, "pdf")
        self.assertEqual(titled.requested_name, "AURIS Capability Report")
        self.assertEqual(titled.brief, "verified automation")
        self.assertIsNone(match_work_product_command("open Spotify"))
        self.assertIsNone(match_work_product_command("create a folder named Reports on Desktop"))

    def test_creates_and_statically_verifies_project_without_execution(self):
        payload = {
            "name": "Focus Timer",
            "summary": "A small timer.",
            "files": [
                {"path": "README.md", "content": "# Focus Timer\n\nRun python main.py.\n"},
                {"path": "main.py", "content": "def ready():\n    return True\n"},
                {"path": "settings.json", "content": '{"minutes": 25}\n'},
            ],
        }
        reply = ModelReply(json.dumps(payload), "test", "fixture", 1)
        with tempfile.TemporaryDirectory() as folder:
            result = execute_work_product(
                match_work_product_command("build a Python project called Focus Timer"),
                root=Path(folder),
                model_generator=lambda *args, **kwargs: reply,
            )

            artifact = result["artifact"]
            self.assertTrue(result["ok"])
            self.assertFalse(artifact["generated_code_executed"])
            self.assertTrue(Path(artifact["path"], "main.py").is_file())
            self.assertTrue(Path(artifact["manifest_path"]).is_file())
            self.assertTrue(all(check["passed"] for check in artifact["checks"]))

    def test_rejects_unsafe_manifest_and_uses_bounded_fallback(self):
        payload = {
            "name": "Unsafe",
            "summary": "Unsafe",
            "files": [{"path": "../outside.py", "content": "print('bad')\n"}],
        }
        reply = ModelReply(json.dumps(payload), "test", "fixture", 1)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            result = execute_work_product(
                match_work_product_command("build a Python project called Safe Result"),
                root=root,
                model_generator=lambda *args, **kwargs: reply,
            )

            self.assertTrue(result["ok"])
            self.assertFalse((root.parent / "outside.py").exists())
            self.assertIn("Unsafe or unsupported", result["generation"]["fallback_reason"])

    @patch("auris.work_product_agent.generate_reply")
    def test_default_project_creation_is_immediate_verified_scaffold(self, generate):
        with tempfile.TemporaryDirectory() as folder:
            result = execute_work_product(
                match_work_product_command("build a chatbot called Quick Assistant"),
                root=Path(folder),
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["generation"]["provider"], "auris_template_engine")
            self.assertIn("latency-first", result["generation"]["fallback_reason"])
            self.assertTrue(Path(result["artifact"]["path"], "app.py").is_file())
            generate.assert_not_called()

    def test_creates_unique_verified_word_documents(self):
        payload = {
            "title": "Renewable Energy",
            "summary": "A practical overview.",
            "sections": [
                {
                    "heading": "Options",
                    "paragraphs": ["Solar and wind are established renewable sources."],
                    "bullets": ["Compare lifecycle cost", "Assess grid constraints"],
                }
            ],
        }
        reply = ModelReply(json.dumps(payload), "test", "fixture", 1)
        with tempfile.TemporaryDirectory() as folder:
            request = match_work_product_command("create a Word document about renewable energy")
            first = execute_work_product(
                request, root=Path(folder), model_generator=lambda *args, **kwargs: reply
            )
            second = execute_work_product(
                request, root=Path(folder), model_generator=lambda *args, **kwargs: reply
            )

            first_path = Path(first["artifact"]["path"])
            second_path = Path(second["artifact"]["path"])
            self.assertTrue(first["ok"])
            self.assertNotEqual(first_path, second_path)
            with zipfile.ZipFile(first_path) as archive:
                self.assertIn("word/document.xml", archive.namelist())

    def test_research_report_preserves_evidence_and_partial_status(self):
        research = {
            "ok": True,
            "message": "The evidence supports the main claim [S1].",
            "mode": "rapid",
            "sources": [{"source_id": "S1", "title": "Source", "url": "https://example.com"}],
            "claims": [{"claim_id": "C1", "text": "Main claim", "source_ids": ["S1"], "status": "supported"}],
            "remaining_questions": ["What changes next?"],
            "definition_of_done_met": False,
            "verification": "Partial research coverage.",
        }
        with tempfile.TemporaryDirectory() as folder:
            result = execute_work_product(
                match_work_product_command("research edge AI and create a Word report"),
                root=Path(folder),
                research_runner=lambda command: research,
            )

            self.assertTrue(result["ok"])
            self.assertFalse(result["complete"])
            self.assertEqual(result["research_action"]["sources"][0]["source_id"], "S1")
            self.assertTrue(Path(result["artifact"]["path"]).is_file())

    def test_creates_and_reopens_pdf_presentation_and_workbook(self):
        replies = {
            "presentation": ModelReply(
                json.dumps(
                    {
                        "title": "Edge AI",
                        "subtitle": "Practical overview",
                        "slides": [
                            {"title": "Context", "bullets": ["Local inference", "Lower latency"]},
                            {"title": "Plan", "bullets": ["Choose hardware", "Measure outcomes"]},
                        ],
                    }
                ),
                "test",
                "fixture",
                1,
            ),
            "spreadsheet": ModelReply(
                json.dumps(
                    {
                        "title": "Milestones",
                        "headers": ["Milestone", "Status", "Owner"],
                        "rows": [["Prototype", "Active", "Devansh"], ["Launch", "Planned", ""]],
                    }
                ),
                "test",
                "fixture",
                1,
            ),
            "document": ModelReply(
                json.dumps(
                    {
                        "title": "Energy Storage",
                        "summary": "A concise evidence-neutral overview.",
                        "sections": [
                            {"heading": "Scope", "paragraphs": ["Compare available storage approaches."], "bullets": ["Cost", "Capacity"]}
                        ],
                    }
                ),
                "test",
                "fixture",
                1,
            ),
        }
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            presentation = execute_work_product(
                match_work_product_command("create a PowerPoint presentation about edge AI"),
                root=root,
                model_generator=lambda *args, **kwargs: replies["presentation"],
            )
            spreadsheet = execute_work_product(
                match_work_product_command("build an Excel tracker for project milestones"),
                root=root,
                model_generator=lambda *args, **kwargs: replies["spreadsheet"],
            )
            pdf = execute_work_product(
                match_work_product_command("create a PDF report about energy storage"),
                root=root,
                model_generator=lambda *args, **kwargs: replies["document"],
            )

            self.assertTrue(presentation["ok"])
            self.assertGreaterEqual(presentation["artifact"]["slides"], 3)
            self.assertTrue(spreadsheet["ok"])
            self.assertEqual(spreadsheet["artifact"]["columns"], 3)
            self.assertTrue(pdf["ok"])
            self.assertGreaterEqual(pdf["artifact"]["pages"], 1)


if __name__ == "__main__":
    unittest.main()
