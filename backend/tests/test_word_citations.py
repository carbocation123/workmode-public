from __future__ import annotations

import unittest
from unittest.mock import patch


class WordCitationModelTest(unittest.TestCase):
    def test_field_payload_round_trips_stable_identity_and_metadata_snapshot(self) -> None:
        from app.word_citations import (
            build_citation_payload,
            decode_field_payload,
            encode_field_payload,
        )

        payload = build_citation_payload(
            "catalysis-library",
            {
                "id": "paper-rutile-1",
                "title": "A stable citation",
                "authors": "Zhang, San; Li, Si",
                "year": 2026,
                "publication_date": "2026-07-24",
                "journal": "Journal of Useful Tests",
                "doi": "10.1000/workmode.1",
                "focus": "must not leak into bibliography metadata",
                "paths": {"pdf": "papers/paper.pdf"},
            },
        )

        self.assertEqual(payload["schema"], "workmode-citation/v1")
        self.assertEqual(payload["project_slug"], "catalysis-library")
        self.assertEqual(payload["paper_id"], "paper-rutile-1")
        self.assertEqual(
            payload["metadata"],
            {
                "title": "A stable citation",
                "authors": "Zhang, San; Li, Si",
                "year": 2026,
                "publication_date": "2026-07-24",
                "journal": "Journal of Useful Tests",
                "doi": "10.1000/workmode.1",
            },
        )
        self.assertEqual(decode_field_payload(encode_field_payload(payload)), payload)

    def test_simple_reference_is_deterministic_and_handles_missing_fields(self) -> None:
        from app.word_citations import format_reference

        self.assertEqual(
            format_reference(
                2,
                {
                    "authors": "Zhang, San; Li, Si",
                    "title": "A stable citation",
                    "journal": "Journal of Useful Tests",
                    "year": 2026,
                    "doi": "https://doi.org/10.1000/workmode.1",
                },
            ),
            "[2] Zhang, San; Li, Si. A stable citation. Journal of Useful Tests, 2026. "
            "DOI: 10.1000/workmode.1.",
        )
        self.assertEqual(format_reference(1, {"title": "Only a title"}), "[1] Only a title.")

    def test_word_actions_forward_the_selected_document(self) -> None:
        from app.word_citations import (
            insert_word_bibliography,
            insert_word_citation,
            list_word_documents,
        )

        with patch(
            "app.word_citations._run_word_action",
            return_value={"ok": True, "documents": []},
        ) as run_action:
            self.assertEqual(list_word_documents()["documents"], [])
            run_action.assert_called_once_with("list_documents")

        payload = {
            "schema": "workmode-citation/v1",
            "project_slug": "library",
            "paper_id": "paper-1",
            "metadata": {"title": "Targeted citation"},
        }
        with patch(
            "app.word_citations._run_word_action",
            return_value={"ok": True},
        ) as run_action:
            insert_word_citation(payload, "C:\\Papers\\draft.docx")
            run_action.assert_called_once_with(
                "insert_citation",
                encode_field_payload(payload),
                "C:\\Papers\\draft.docx",
            )

        with patch(
            "app.word_citations._run_word_action",
            return_value={"ok": True},
        ) as run_action:
            insert_word_bibliography("unsaved::Document1")
            run_action.assert_called_once_with(
                "insert_bibliography",
                None,
                "unsaved::Document1",
            )


if __name__ == "__main__":
    unittest.main()
