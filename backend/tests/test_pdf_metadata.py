from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


class PdfMetadataTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_pdf(
        self,
        path: Path,
        *,
        title: str = "",
        author: str = "",
        subject: str = "",
        keywords: str = "",
        text: str = "",
    ) -> None:
        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        if text:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
            )
            stream = DecodedStreamObject()
            escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii"))
            page[NameObject("/Contents")] = writer._add_object(stream)
        metadata = {
            key: value
            for key, value in {
                "/Title": title,
                "/Author": author,
                "/Subject": subject,
                "/Keywords": keywords,
            }.items()
            if value
        }
        if metadata:
            writer.add_metadata(metadata)
        with path.open("wb") as handle:
            writer.write(handle)

    def test_extracts_embedded_pdf_metadata_and_doi_without_ai(self) -> None:
        from app.pdf_metadata import extract_local_pdf_metadata

        path = self.root / "paper.pdf"
        self._write_pdf(
            path,
            title="A deterministic catalyst study",
            author="Alice Smith; Bob Jones",
            subject="Journal of Testing 2024.12:1-5",
            keywords="catalysis; doi:10.1234/TEST.5678",
        )

        metadata = extract_local_pdf_metadata(path)

        self.assertEqual(metadata["title"], "A deterministic catalyst study")
        self.assertEqual(metadata["authors"], "Alice Smith; Bob Jones")
        self.assertEqual(metadata["first_author_surname"], "Smith")
        self.assertEqual(metadata["year"], 2024)
        self.assertEqual(metadata["journal"], "Journal of Testing")
        self.assertEqual(metadata["doi"], "10.1234/test.5678")
        self.assertEqual(metadata["metadata_source"], "pdf_metadata")

    def test_crossref_title_lookup_accepts_only_an_exact_normalized_title(self) -> None:
        from app.pdf_metadata import resolve_crossref_metadata

        expected_title = "CO2 conversion over FeMn@Si"
        real_client = httpx.Client

        def client_factory(**kwargs):
            def handler(request: httpx.Request) -> httpx.Response:
                self.assertEqual(
                    request.url.params["query.bibliographic"],
                    expected_title,
                )
                return httpx.Response(
                    200,
                    request=request,
                    json={
                        "message": {
                            "items": [
                                {
                                    "title": ["CO<sub>2</sub> conversion over FeMn@Si"],
                                    "author": [
                                        {"given": "Alice", "family": "Smith"},
                                        {"given": "Bob", "family": "Jones"},
                                    ],
                                    "container-title": ["Journal of Testing"],
                                    "short-container-title": ["J Test"],
                                    "published": {"date-parts": [[2024, 3, 2]]},
                                    "DOI": "10.1234/TEST.5678",
                                    "type": "journal-article",
                                }
                            ]
                        }
                    },
                )

            return real_client(
                transport=httpx.MockTransport(handler),
                headers=kwargs.get("headers"),
                follow_redirects=kwargs.get("follow_redirects", False),
                timeout=kwargs.get("timeout"),
            )

        with patch("app.pdf_metadata.httpx.Client", side_effect=client_factory):
            metadata = resolve_crossref_metadata({"title": expected_title})

        self.assertEqual(metadata["title"], expected_title)
        self.assertEqual(metadata["authors"], "Alice Smith, Bob Jones")
        self.assertEqual(metadata["first_author_surname"], "Smith")
        self.assertEqual(metadata["year"], 2024)
        self.assertEqual(metadata["journal_abbreviation"], "JTest")
        self.assertEqual(metadata["doi"], "10.1234/test.5678")
        self.assertEqual(metadata["metadata_trust"], "complete")

    def test_complete_crossref_metadata_skips_ai_fallback(self) -> None:
        from app.literature_project import (
            initialize_literature_project,
            literature_paper,
            register_staged_pdf,
        )
        from app.pdf_metadata import enrich_imported_pdf_metadata

        initialize_literature_project(self.root, name="Library")
        staged = self.root / "incoming.pdf"
        self._write_pdf(staged, title="A deterministic catalyst study")
        imported = register_staged_pdf(
            self.root,
            staged,
            original_filename="incoming.pdf",
        )
        paper_id = imported["paper"]["id"]
        resolved = {
            "title": "A deterministic catalyst study",
            "authors": "Alice Smith, Bob Jones",
            "first_author_surname": "Smith",
            "year": 2024,
            "publication_date": "2024-03-02",
            "journal": "Journal of Testing",
            "journal_abbreviation": "JTest",
            "doi": "10.1234/test.5678",
            "paper_type": "research",
            "metadata_source": "crossref",
        }

        with (
            patch("app.pdf_metadata.resolve_crossref_metadata", return_value=resolved),
            patch(
                "app.pdf_metadata.extract_ai_pdf_metadata",
                side_effect=AssertionError("AI must not run for complete deterministic metadata"),
            ) as ai_extract,
        ):
            result = enrich_imported_pdf_metadata(self.root, paper_id)

        ai_extract.assert_not_called()
        self.assertEqual(result["metadata_trust"], "complete")
        stored = literature_paper(self.root, paper_id)
        self.assertEqual(stored["title"], resolved["title"])
        self.assertEqual(stored["authors"], resolved["authors"])
        self.assertEqual(stored["doi"], resolved["doi"])
        self.assertEqual(stored["metadata_source"], "crossref")

    def test_incomplete_deterministic_metadata_uses_ai_fallback(self) -> None:
        from app.literature_project import (
            initialize_literature_project,
            literature_paper,
            register_staged_pdf,
        )
        from app.pdf_metadata import enrich_imported_pdf_metadata

        initialize_literature_project(self.root, name="Library")
        staged = self.root / "incoming.pdf"
        self._write_pdf(staged, title="Sparse PDF")
        imported = register_staged_pdf(
            self.root,
            staged,
            original_filename="incoming.pdf",
        )
        paper_id = imported["paper"]["id"]
        ai_metadata = {
            "title": "Sparse PDF",
            "authors": "Alice Smith",
            "first_author_surname": "Smith",
            "year": 2025,
            "publication_date": "",
            "journal": "Journal of Testing",
            "journal_abbreviation": "JTest",
            "doi": "",
            "paper_type": "research",
            "metadata_source": "ai_pdf",
        }

        with (
            patch("app.pdf_metadata.resolve_crossref_metadata", return_value={}),
            patch("app.pdf_metadata.extract_ai_pdf_metadata", return_value=ai_metadata) as ai_extract,
        ):
            result = enrich_imported_pdf_metadata(self.root, paper_id)

        ai_extract.assert_called_once()
        self.assertEqual(result["metadata_trust"], "complete")
        stored = literature_paper(self.root, paper_id)
        self.assertEqual(stored["authors"], "Alice Smith")
        self.assertEqual(stored["metadata_source"], "ai_pdf")


if __name__ == "__main__":
    unittest.main()
