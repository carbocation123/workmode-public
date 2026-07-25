from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError

from .literature_project import (
    LiteratureProjectError,
    literature_paper,
    normalize_journal_abbreviation,
    update_literature_paper,
)


CROSSREF_API_BASE = "https://api.crossref.org"
CROSSREF_TIMEOUT_SECONDS = 6
MAX_METADATA_PAGES = 2
MAX_METADATA_TEXT_CHARS = 80_000
CORE_METADATA_FIELDS = ("title", "authors", "year", "journal")
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")


class PdfMetadataError(RuntimeError):
    pass


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_title(value: Any) -> str:
    decoded = html.unescape(str(value or ""))
    title = _clean_text(re.sub(r"<[^>]+>", "", decoded))
    if not title:
        return ""
    generic = {
        "document",
        "microsoft word",
        "microsoft word - document",
        "paper",
        "untitled",
    }
    return "" if title.casefold() in generic else title


def _normalized_match_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE).casefold()


def _normalize_doi(value: Any) -> str:
    raw = html.unescape(str(value or "")).strip()
    raw = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)", "", raw, flags=re.IGNORECASE)
    match = DOI_PATTERN.search(raw)
    if not match:
        return ""
    return match.group(0).rstrip(".,;:)]}>").casefold()


def _first_author_surname(authors: Any) -> str:
    raw = _clean_text(authors)
    if not raw:
        return ""
    first = re.split(r"\s*(?:;|\band\b|\n)\s*", raw, maxsplit=1, flags=re.IGNORECASE)[0]
    if "," in first:
        candidate = first.split(",", 1)[0].strip()
    else:
        tokens = re.findall(r"[A-Za-z][A-Za-z'-]*", first)
        candidate = tokens[-1] if tokens else ""
    return candidate if re.fullmatch(r"[A-Za-z][A-Za-z'-]*", candidate) else ""


def _metadata_year(value: Any) -> int | None:
    match = YEAR_PATTERN.search(str(value or ""))
    if not match:
        return None
    year = int(match.group(0))
    current_year = datetime.now(timezone.utc).year
    return year if 1800 <= year <= current_year + 2 else None


def _subject_bibliography(subject: str) -> tuple[str, int | None]:
    cleaned = _clean_text(subject)
    if not cleaned or len(cleaned) > 240:
        return "", None
    match = re.match(
        r"^(?P<journal>[A-Za-z][A-Za-z0-9 &:/.'’()\-]{1,150}?)"
        r"\s*[,;]?\s+(?P<year>(?:19|20)\d{2})"
        r"(?=$|[.;,:]\s*\d|\s+(?:vol(?:ume)?|issue)\b)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if not match:
        return "", None
    journal = _clean_text(match.group("journal")).rstrip(".,;:")
    if len(journal.split()) > 16 or any(
        word in journal.casefold()
        for word in ("abstract", "copyright", "downloaded", "manuscript")
    ):
        return "", None
    return journal, int(match.group("year"))


def _read_pdf_source(path: Path) -> tuple[dict[str, str], str]:
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise PdfMetadataError("PDF 文件不存在")
    with resolved.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise PdfMetadataError("PDF 文件头校验失败")
    try:
        reader = PdfReader(str(resolved), strict=False)
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise PdfMetadataError("PDF 已加密，无法自动读取元数据")
        raw_metadata = reader.metadata or {}
        embedded = {
            "title": _clean_text(raw_metadata.get("/Title")),
            "authors": _clean_text(raw_metadata.get("/Author")),
            "subject": _clean_text(raw_metadata.get("/Subject")),
            "keywords": _clean_text(raw_metadata.get("/Keywords")),
        }
        chunks: list[str] = []
        total = 0
        for page in reader.pages[:MAX_METADATA_PAGES]:
            if "/Contents" not in page:
                continue
            try:
                text = page.extract_text(extraction_mode="layout") or ""
            except (KeyError, TypeError, ValueError):
                text = page.extract_text() or ""
            text = text.strip()
            if not text:
                continue
            remaining = MAX_METADATA_TEXT_CHARS - total
            if remaining <= 0:
                break
            chunks.append(text[:remaining])
            total += min(len(text), remaining)
        return embedded, "\n\n".join(chunks)
    except PdfMetadataError:
        raise
    except (FileNotDecryptedError, PdfReadError, OSError, ValueError) as exc:
        raise PdfMetadataError(f"PDF 无法打开：{exc}") from exc


def _quality(metadata: dict[str, Any]) -> tuple[str, str]:
    missing = [
        label
        for key, label in (
            ("title", "标题"),
            ("authors", "作者"),
            ("year", "发表年份"),
            ("journal", "期刊"),
        )
        if metadata.get(key) in {None, ""}
    ]
    if not missing:
        return "complete", ""
    return "partial", f"自动元数据仍缺少：{'、'.join(missing)}"


def extract_local_pdf_metadata(path: Path) -> dict[str, Any]:
    """Read bounded, local-only PDF metadata without any network or model call."""
    embedded, first_pages = _read_pdf_source(path)
    journal, subject_year = _subject_bibliography(embedded["subject"])
    searchable = "\n".join(
        (
            embedded["title"],
            embedded["authors"],
            embedded["subject"],
            embedded["keywords"],
            first_pages,
        )
    )
    doi = _normalize_doi(searchable)
    authors = embedded["authors"]
    abbreviation = ""
    if journal and len(journal.split()) == 1:
        try:
            abbreviation = normalize_journal_abbreviation(journal)
        except LiteratureProjectError:
            abbreviation = ""
    metadata: dict[str, Any] = {
        "title": _clean_title(embedded["title"]),
        "authors": authors,
        "first_author_surname": _first_author_surname(authors),
        "year": subject_year,
        "publication_date": "",
        "journal": journal,
        "journal_abbreviation": abbreviation,
        "doi": doi,
        "paper_type": "unknown",
        "metadata_source": "pdf_metadata",
    }
    trust, issue = _quality(metadata)
    metadata["metadata_trust"] = trust
    metadata["metadata_issue"] = issue
    return metadata


def _crossref_date(message: dict[str, Any]) -> tuple[int | None, str]:
    for key in ("published-print", "published", "published-online", "issued"):
        value = message.get(key)
        parts = value.get("date-parts") if isinstance(value, dict) else None
        first = parts[0] if isinstance(parts, list) and parts else None
        if not isinstance(first, list) or not first:
            continue
        try:
            numbers = [int(item) for item in first[:3]]
        except (TypeError, ValueError):
            continue
        if not 1800 <= numbers[0] <= datetime.now(timezone.utc).year + 2:
            continue
        publication_date = "-".join(
            f"{number:02d}" if index else str(number)
            for index, number in enumerate(numbers)
        )
        return numbers[0], publication_date
    return None, ""


def _metadata_from_crossref_message(message: dict[str, Any]) -> dict[str, Any]:
    titles = message.get("title")
    title = _clean_title(titles[0] if isinstance(titles, list) and titles else "")
    author_records = message.get("author")
    author_names: list[str] = []
    first_surname = ""
    if isinstance(author_records, list):
        for index, author in enumerate(author_records):
            if not isinstance(author, dict):
                continue
            family = _clean_text(author.get("family"))
            given = _clean_text(author.get("given"))
            literal = _clean_text(author.get("literal"))
            name = _clean_text(" ".join(part for part in (given, family) if part)) or literal
            if name:
                author_names.append(name)
            if index == 0 and family:
                first_surname = family if re.fullmatch(r"[A-Za-z][A-Za-z'-]*", family) else ""
    containers = message.get("container-title")
    journal = _clean_text(containers[0] if isinstance(containers, list) and containers else "")
    short_containers = message.get("short-container-title")
    abbreviation_raw = _clean_text(
        short_containers[0] if isinstance(short_containers, list) and short_containers else ""
    )
    try:
        abbreviation = normalize_journal_abbreviation(abbreviation_raw)
    except LiteratureProjectError:
        abbreviation = ""
    year, publication_date = _crossref_date(message)
    subtype = str(message.get("subtype") or "").casefold()
    title_hint = title.casefold()
    paper_type = "review" if "review" in subtype or title_hint.startswith("review") else "research"
    metadata: dict[str, Any] = {
        "title": title,
        "authors": ", ".join(author_names),
        "first_author_surname": first_surname or _first_author_surname(", ".join(author_names)),
        "year": year,
        "publication_date": publication_date,
        "journal": journal,
        "journal_abbreviation": abbreviation,
        "doi": _normalize_doi(message.get("DOI")),
        "paper_type": paper_type,
        "metadata_source": "crossref",
    }
    trust, issue = _quality(metadata)
    metadata["metadata_trust"] = trust
    metadata["metadata_issue"] = issue
    return metadata


def resolve_crossref_metadata(candidate: dict[str, Any]) -> dict[str, Any]:
    """Resolve an exact DOI or conservative exact-title match through Crossref."""
    doi = _normalize_doi(candidate.get("doi"))
    title = _clean_title(candidate.get("title"))
    if not doi and not title:
        return {}
    headers = {
        "Accept": "application/json",
        "User-Agent": "Workmode-Public/metadata-import (https://github.com/carbocation123/workmode-public)",
    }
    timeout = httpx.Timeout(CROSSREF_TIMEOUT_SECONDS, connect=CROSSREF_TIMEOUT_SECONDS)
    try:
        with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
            if doi:
                response = client.get(f"{CROSSREF_API_BASE}/works/{quote(doi, safe='')}")
                if response.status_code != 200:
                    return {}
                message = response.json().get("message")
                return _metadata_from_crossref_message(message) if isinstance(message, dict) else {}

            params: dict[str, str | int] = {
                "query.bibliographic": title,
                "rows": 3,
            }
            year = candidate.get("year")
            if isinstance(year, int):
                params["filter"] = (
                    f"from-pub-date:{year}-01-01,until-pub-date:{year}-12-31"
                )
            response = client.get(f"{CROSSREF_API_BASE}/works", params=params)
            if response.status_code != 200:
                return {}
            payload = response.json().get("message")
            items = payload.get("items") if isinstance(payload, dict) else None
            expected = _normalized_match_text(title)
            if not expected or not isinstance(items, list):
                return {}
            for item in items:
                if not isinstance(item, dict):
                    continue
                titles = item.get("title")
                found = titles[0] if isinstance(titles, list) and titles else ""
                if _normalized_match_text(found) == expected:
                    return _metadata_from_crossref_message(item)
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return {}
    return {}


def _evidence_is_present(evidence: Any, source_text: str) -> bool:
    quote_text = _clean_text(evidence)
    if not quote_text:
        return False
    return _normalized_match_text(quote_text) in _normalized_match_text(source_text)


def extract_ai_pdf_metadata(path: Path, current: dict[str, Any]) -> dict[str, Any]:
    """Use the configured model only for metadata still missing after deterministic lookup."""
    _embedded, first_pages = _read_pdf_source(path)
    if not first_pages:
        return {}
    from .literature_pipeline import _extract_json_object, _model_completion

    prompt = f"""只根据下面 PDF 前两页的文字，补齐尚缺少的书目信息。不得联网，不得根据文件名猜测。
返回一个 JSON object，字段固定为：
title, authors, year, journal, journal_abbreviation, doi, paper_type, evidence。
paper_type 只能是 research、review、unknown。
evidence 必须是一个 object，分别为 title、authors、year、journal、journal_abbreviation、doi 提供逐字摘自下方 PDF 文字的短证据；没有证据的字段返回 null。
未知字段返回 null，不解释。

[已有自动识别结果]
{json.dumps(current, ensure_ascii=False)}

[PDF 前两页文字]
{first_pages}
"""
    raw_response = _model_completion(
        "你是严格的学术元数据抽取器。只输出有逐字证据支持的 JSON，不补猜。",
        prompt,
        response_format={"type": "json_object"},
        timeout_seconds=60,
    )
    raw = _extract_json_object(raw_response)
    evidence = raw.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    result: dict[str, Any] = {}
    for key in ("title", "authors", "journal"):
        value = _clean_text(raw.get(key))
        if value and _evidence_is_present(evidence.get(key), first_pages):
            result[key] = _clean_title(value) if key == "title" else value
    year = _metadata_year(raw.get("year"))
    if year is not None and _evidence_is_present(evidence.get("year"), first_pages):
        result["year"] = year
    doi = _normalize_doi(raw.get("doi"))
    if doi and _evidence_is_present(evidence.get("doi"), first_pages):
        result["doi"] = doi
    abbreviation_raw = _clean_text(raw.get("journal_abbreviation"))
    if abbreviation_raw and _evidence_is_present(
        evidence.get("journal_abbreviation"),
        first_pages,
    ):
        try:
            result["journal_abbreviation"] = normalize_journal_abbreviation(abbreviation_raw)
        except LiteratureProjectError:
            pass
    authors = str(result.get("authors") or "")
    if authors:
        result["first_author_surname"] = _first_author_surname(authors)
    paper_type = str(raw.get("paper_type") or "unknown")
    result["paper_type"] = paper_type if paper_type in {"research", "review"} else "unknown"
    result["publication_date"] = ""
    result["metadata_source"] = "ai_pdf"
    if not any(result.get(key) not in {None, ""} for key in CORE_METADATA_FIELDS):
        return {}
    trust, issue = _quality(result)
    result["metadata_trust"] = trust
    result["metadata_issue"] = issue
    return result


def _merge_nonempty(
    base: dict[str, Any],
    update: dict[str, Any],
    *,
    overwrite: bool,
) -> tuple[dict[str, Any], bool]:
    merged = dict(base)
    changed = False
    for key in (
        "title",
        "authors",
        "first_author_surname",
        "year",
        "publication_date",
        "journal",
        "journal_abbreviation",
        "doi",
        "paper_type",
    ):
        value = update.get(key)
        if value in {None, ""}:
            continue
        if overwrite or merged.get(key) in {None, "", "unknown"}:
            if merged.get(key) != value:
                merged[key] = value
                changed = True
    if changed and update.get("metadata_source"):
        merged["metadata_source"] = update["metadata_source"]
    return merged, changed


def enrich_imported_pdf_metadata(root: Path, paper_id: str) -> dict[str, Any]:
    """Run local metadata, Crossref and finally AI fallback for one imported PDF."""
    root = root.expanduser().resolve()
    paper = literature_paper(root, paper_id)
    paths = paper.get("paths") or {}
    pdf_rel = str(paths.get("pdf") or "")
    pdf_path = (root / pdf_rel).resolve()
    try:
        pdf_path.relative_to(root)
    except ValueError as exc:
        raise PdfMetadataError("文献 PDF 路径越出项目目录") from exc

    current = {
        key: paper.get(key)
        for key in (
            "title",
            "authors",
            "first_author_surname",
            "year",
            "publication_date",
            "journal",
            "journal_abbreviation",
            "doi",
            "paper_type",
            "metadata_source",
        )
    }
    errors: list[str] = []
    try:
        local = extract_local_pdf_metadata(pdf_path)
        current, _changed = _merge_nonempty(current, local, overwrite=False)
    except Exception as exc:
        errors.append(f"PDF 本地元数据读取失败：{str(exc)[:240] or exc.__class__.__name__}")

    trust, issue = _quality(current)
    if trust != "complete":
        try:
            crossref = resolve_crossref_metadata(current)
            current, _changed = _merge_nonempty(current, crossref, overwrite=True)
        except Exception as exc:
            errors.append(f"Crossref 查询失败：{str(exc)[:240] or exc.__class__.__name__}")

    trust, issue = _quality(current)
    if trust != "complete":
        try:
            ai_metadata = extract_ai_pdf_metadata(pdf_path, current)
            current, _changed = _merge_nonempty(current, ai_metadata, overwrite=False)
        except Exception as exc:
            errors.append(f"AI 元数据补充未完成：{str(exc)[:240] or exc.__class__.__name__}")

    if not current.get("first_author_surname"):
        current["first_author_surname"] = _first_author_surname(current.get("authors"))
    trust, issue = _quality(current)
    issue_parts = [part for part in (issue, *errors) if part]
    updates = {
        key: current.get(key)
        for key in (
            "title",
            "authors",
            "first_author_surname",
            "year",
            "publication_date",
            "journal",
            "journal_abbreviation",
            "doi",
            "paper_type",
            "metadata_source",
        )
        if current.get(key) not in {None, ""}
    }
    updates.update(
        {
            "metadata_trust": trust,
            "metadata_issue": "；".join(dict.fromkeys(issue_parts)),
            "stage": "元数据已自动识别" if trust == "complete" else "元数据待补充",
        }
    )
    return update_literature_paper(root, paper_id, **updates)
