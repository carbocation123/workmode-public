from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.pdf_text import PdfTextExtractionError, extract_pdf_text


class PdfTextExtractionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_pdf(self, path: Path, *, text: str | None) -> None:
        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        if text is not None:
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
        with path.open("wb") as handle:
            writer.write(handle)

    def test_extracts_a_real_pdf_text_layer_with_page_markers(self) -> None:
        path = self.root / "text.pdf"
        self._write_pdf(path, text="Direct PDF evidence 42")

        result = extract_pdf_text(path)

        self.assertEqual(result.page_count, 1)
        self.assertEqual(result.pages_with_text, 1)
        self.assertIn("# Page 1", result.text)
        self.assertIn("Direct PDF evidence 42", result.text)
        self.assertFalse(result.truncated)

    def test_image_only_pdf_reports_that_ocr_is_required(self) -> None:
        path = self.root / "blank.pdf"
        self._write_pdf(path, text=None)

        with self.assertRaisesRegex(PdfTextExtractionError, "MinerU/OCR"):
            extract_pdf_text(path)


if __name__ == "__main__":
    unittest.main()
