"""Unit tests for AI Session Hub core logic (no external deps)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCategorize(unittest.TestCase):
    def test_fhir_detection(self):
        from core.categorize import categorize_text
        cat, conf, kws = categorize_text(
            "Build a FHIR developer portal for our EHR with USCDI and ECR support")
        self.assertEqual(cat, "FHIR")
        self.assertGreater(conf, 0)
        self.assertTrue(any("fhir" in k for k in kws))

    def test_web_detection(self):
        from core.categorize import categorize_text
        cat, _, _ = categorize_text("Create a React website with tailwind and a dashboard UI")
        self.assertEqual(cat, "web-app")

    def test_general_fallback(self):
        from core.categorize import categorize_text
        cat, _, _ = categorize_text("just a quick hello")
        self.assertEqual(cat, "general")

    def test_title_build(self):
        from core.categorize import build_title
        t = build_title({"project_path": "C:\\Users\\dev\\healthcare-portal"},
                        "please build a fhir search parameter mapping for uscdi v3")
        self.assertTrue(isinstance(t, str) and len(t) > 0)


class TestMasterPrompt(unittest.TestCase):
    def test_build_with_empty_db(self):
        # Build against the real DB; if empty, still returns a prompt or not-found
        from core.master_prompt import build_master_prompt
        out = build_master_prompt("nonexistent-session-id")
        self.assertIn("Session not found", out)


class TestExport(unittest.TestCase):
    def test_markdown_export(self):
        from core.export import export_session
        # Exporting a nonexistent session returns an error gracefully
        res = export_session("nonexistent", "claude_code")
        self.assertEqual(res["status"], "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
