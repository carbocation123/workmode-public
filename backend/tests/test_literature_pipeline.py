from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class LiteratureMetadataPipelineTest(unittest.TestCase):
    def test_metadata_uses_json_response_format_and_verifies_literal_evidence(self) -> None:
        from app.literature_pipeline import _extract_metadata

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            response = json.dumps(
                {
                    "title": "Verified title",
                    "authors": ["Zhang, A.", "Li, B."],
                    "first_author_surname": "Zhang",
                    "year": 2024,
                    "journal": "Journal of Tests",
                    "journal_abbreviation": "JTest",
                    "doi": "10.1000/test",
                    "paper_type": "research",
                    "metadata_source": "cite_this",
                    "evidence_quote": "Cite This: Zhang, A. Journal of Tests 2024, 1, 1-8.",
                }
            )
            with (
                patch(
                    "app.literature_pipeline._collect_page_zero_text",
                    return_value="Header\nCite This: Zhang, A. Journal of Tests 2024, 1, 1-8.\n",
                ),
                patch("app.literature_pipeline._layout_fallback", return_value=""),
                patch("app.literature_pipeline._model_completion", return_value=response) as completion,
            ):
                metadata = _extract_metadata(output)

        self.assertEqual(metadata["metadata_trust"], "complete")
        self.assertEqual(metadata["authors"], "Zhang, A., Li, B.")
        self.assertEqual(completion.call_args.kwargs["response_format"], {"type": "json_object"})
        self.assertIn('"evidence_quote": null', completion.call_args.args[1])

    def test_metadata_retries_once_to_repair_invalid_json_and_keeps_raw_outputs(self) -> None:
        from app.literature_pipeline import _extract_metadata

        fixed = json.dumps(
            {
                "title": "Verified title",
                "authors": "Zhang, A.",
                "first_author_surname": "Zhang",
                "year": 2024,
                "journal": "Journal of Tests",
                "journal_abbreviation": "JTest",
                "doi": "10.1000/test",
                "paper_type": "research",
                "metadata_source": "cite_this",
                "evidence_quote": "Cite This: Zhang, A. Journal of Tests 2024.",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            with (
                patch(
                    "app.literature_pipeline._collect_page_zero_text",
                    return_value="Cite This: Zhang, A. Journal of Tests 2024.",
                ),
                patch("app.literature_pipeline._layout_fallback", return_value=""),
                patch("app.literature_pipeline._model_completion", side_effect=["not json", fixed]) as completion,
            ):
                metadata = _extract_metadata(output)

            self.assertEqual(metadata["metadata_trust"], "complete")
            self.assertEqual(completion.call_count, 2)
            self.assertEqual((output / "metadata-response-raw.txt").read_text(encoding="utf-8"), "not json")
            self.assertEqual((output / "metadata-response-repaired.json").read_text(encoding="utf-8"), fixed)


if __name__ == "__main__":
    unittest.main()
