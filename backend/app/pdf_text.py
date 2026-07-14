from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError


MAX_DIRECT_PDF_BYTES = 64 * 1024 * 1024
MAX_DIRECT_PDF_PAGES = 600
MAX_DIRECT_PDF_CHARS = 4_000_000


class PdfTextExtractionError(RuntimeError):
    pass


@dataclass(frozen=True)
class PdfTextExtraction:
    text: str
    page_count: int
    pages_with_text: int
    truncated: bool
    warnings: list[str]


def _check_cancel(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise PdfTextExtractionError("The user stopped PDF text extraction.")


def extract_pdf_text(
    path: Path,
    *,
    cancel_event: threading.Event | None = None,
) -> PdfTextExtraction:
    """Extract a bounded text-layer view without OCR or external services."""
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise PdfTextExtractionError("The PDF file does not exist.")
    if resolved.stat().st_size > MAX_DIRECT_PDF_BYTES:
        raise PdfTextExtractionError(
            "The PDF is too large for direct text-layer reading; use MinerU or a smaller PDF."
        )
    with resolved.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise PdfTextExtractionError("The file does not have a valid PDF header.")

    _check_cancel(cancel_event)
    try:
        reader = PdfReader(str(resolved), strict=False)
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise PdfTextExtractionError(
                "The PDF is password protected; unlock it before asking the AI to read it."
            )
        page_count = len(reader.pages)
    except PdfTextExtractionError:
        raise
    except (FileNotDecryptedError, PdfReadError, OSError, ValueError) as exc:
        raise PdfTextExtractionError(f"The PDF cannot be opened: {exc}") from exc

    warnings: list[str] = []
    truncated = page_count > MAX_DIRECT_PDF_PAGES
    if truncated:
        warnings.append(
            f"Only the first {MAX_DIRECT_PDF_PAGES} of {page_count} pages were read."
        )

    chunks: list[str] = []
    total_chars = 0
    pages_with_text = 0
    for index, page in enumerate(reader.pages[:MAX_DIRECT_PDF_PAGES]):
        _check_cancel(cancel_event)
        if "/Contents" not in page:
            continue
        try:
            text = page.extract_text(extraction_mode="layout") or ""
        except (TypeError, ValueError):
            text = page.extract_text() or ""
        text = text.strip()
        if not text:
            continue
        pages_with_text += 1
        chunk = f"# Page {index + 1}\n\n{text}"
        remaining = MAX_DIRECT_PDF_CHARS - total_chars
        if remaining <= 0:
            truncated = True
            break
        if len(chunk) > remaining:
            chunk = chunk[:remaining]
            truncated = True
        chunks.append(chunk)
        total_chars += len(chunk)
        if total_chars >= MAX_DIRECT_PDF_CHARS:
            break

    if truncated and total_chars >= MAX_DIRECT_PDF_CHARS:
        warnings.append(
            f"Direct text output was limited to {MAX_DIRECT_PDF_CHARS:,} characters."
        )
    if not chunks:
        raise PdfTextExtractionError(
            "No readable text layer was found. This is probably a scanned or image-only PDF; "
            "run MinerU/OCR before asking the AI to read the full text."
        )

    return PdfTextExtraction(
        text="\n\n".join(chunks),
        page_count=page_count,
        pages_with_text=pages_with_text,
        truncated=truncated,
        warnings=warnings,
    )
