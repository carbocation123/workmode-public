from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


DEFAULT_CITATION_STYLE = "gb-t-7714-2015-numeric"
_STYLE_OPTIONS = (
    ("gb-t-7714-2015-numeric", "GB/T 7714—2015（顺序编码）", "numeric"),
    ("american-chemical-society", "ACS", "numeric"),
    ("nature", "Nature", "numeric"),
    ("apa-7th", "APA 7th", "author-date"),
    ("vancouver", "Vancouver", "numeric"),
)
_STYLE_KINDS = {style_id: kind for style_id, _label, kind in _STYLE_OPTIONS}


class CitationStyleError(RuntimeError):
    pass


def citation_style_options() -> list[dict[str, str]]:
    return [
        {"id": style_id, "label": label, "kind": kind}
        for style_id, label, kind in _STYLE_OPTIONS
    ]


def validate_style_id(style_id: str | None) -> str:
    normalized = str(style_id or DEFAULT_CITATION_STYLE).strip()
    if normalized not in _STYLE_KINDS:
        raise CitationStyleError("不支持这个引用格式，请重新选择。")
    return normalized


def _split_authors(value: Any) -> list[dict[str, str]]:
    raw = str(value or "").strip()
    if not raw:
        return []
    authors: list[dict[str, str]] = []
    for part in re.split(r"\s*;\s*|\r?\n+", raw):
        name = part.strip()
        if not name:
            continue
        if "," in name:
            family, given = (piece.strip() for piece in name.split(",", 1))
        else:
            pieces = name.split()
            family = pieces[-1]
            given = " ".join(pieces[:-1])
        author = {"family": family}
        if given:
            author["given"] = given
        authors.append(author)
    return authors


def _date_parts(metadata: dict[str, Any]) -> list[list[int]]:
    value = str(metadata.get("publication_date") or metadata.get("year") or "").strip()
    numbers = [int(part) for part in re.findall(r"\d+", value)[:3]]
    return [numbers] if numbers else []


def _reference_key(item: dict[str, Any]) -> str:
    return f"{item.get('project_slug', '')}::{item.get('paper_id', '')}"


def _csl_record(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    record: dict[str, Any] = {
        "id": _reference_key(item),
        "type": "article-journal",
        "title": str(metadata.get("title") or "Untitled reference"),
    }
    authors = _split_authors(metadata.get("authors"))
    if authors:
        record["author"] = authors
    dates = _date_parts(metadata)
    if dates:
        record["issued"] = {"date-parts": dates}
    journal = str(metadata.get("journal") or "").strip()
    if journal:
        record["container-title"] = journal
    doi = str(metadata.get("doi") or "").strip()
    if doi:
        record["DOI"] = re.sub(r"^(?:https?://doi\.org/|doi:\s*)", "", doi, flags=re.I)
    return record


def _style_xml(style_id: str) -> str:
    style_id = validate_style_id(style_id)
    if style_id == "gb-t-7714-2015-numeric":
        name = '<name name-as-sort-order="all" sort-separator=" " initialize-with="" delimiter=", " and="text" text-case="uppercase"/>'
        bibliography_layout = """
      <text variable="citation-number" suffix=". "/><text macro="author" suffix=". "/>
      <text variable="title" suffix="[J]. "/><text variable="container-title"/>
      <text macro="year" prefix=", " suffix=". "/><text variable="DOI" prefix="DOI: "/>"""
    elif style_id == "american-chemical-society":
        name = '<name name-as-sort-order="all" sort-separator=", " initialize-with=". " delimiter="; " and="text"/>'
        bibliography_layout = """
      <text variable="citation-number" suffix=". "/><text macro="author" suffix=". "/>
      <text variable="title" suffix=". "/><text variable="container-title" font-style="italic"/>
      <text macro="year" prefix=" " suffix=". "/><text variable="DOI" prefix="https://doi.org/"/>"""
    elif style_id == "nature":
        name = '<name name-as-sort-order="all" sort-separator=", " initialize-with=". " delimiter=", " and="symbol"/>'
        bibliography_layout = """
      <text variable="citation-number" suffix=". "/><text macro="author" suffix=". "/>
      <text variable="title" suffix=". "/><text variable="container-title" font-style="italic" suffix=" "/>
      <text macro="year" prefix="(" suffix="). "/><text variable="DOI" prefix="https://doi.org/"/>"""
    elif style_id == "vancouver":
        name = '<name name-as-sort-order="all" sort-separator=" " initialize-with="" delimiter=", " and="text"/>'
        bibliography_layout = """
      <text variable="citation-number" suffix=". "/><text macro="author" suffix=". "/>
      <text variable="title" suffix=". "/><text variable="container-title" suffix=". "/>
      <text macro="year" suffix=". "/><text variable="DOI" prefix="doi: "/>"""
    else:
        name = '<name name-as-sort-order="all" sort-separator=", " initialize-with=". " delimiter=", " and="text"/>'
        bibliography_layout = """
      <text macro="author"/><text macro="year" prefix=" (" suffix="). "/>
      <text variable="title" suffix=". "/><text variable="container-title" font-style="italic" suffix=". "/>
      <text variable="DOI" prefix="https://doi.org/"/>"""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" version="1.0.2" class="in-text">
  <info>
    <title>Workmode {escape(style_id)}</title>
    <id>https://workmode.local/styles/{escape(style_id)}</id>
    <updated>2026-07-25T00:00:00+00:00</updated>
  </info>
  <macro name="author">
    <names variable="author">
      {name}
      <substitute><text variable="title"/></substitute>
    </names>
  </macro>
  <macro name="year">
    <date variable="issued"><date-part name="year"/></date>
  </macro>
  <citation>
    <layout prefix="(" suffix=")" delimiter="; ">
      <group delimiter=", "><text macro="author"/><text macro="year"/></group>
    </layout>
  </citation>
  <bibliography et-al-min="8" et-al-use-first="6">
    <layout>
      {bibliography_layout}
    </layout>
  </bibliography>
</style>
"""


def _clean_rendered(value: Any) -> str:
    text = "".join(value) if isinstance(value, (list, tuple)) else str(value)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    return text


def _render_bibliography(items: list[dict[str, Any]], style_id: str) -> list[str]:
    try:
        from citeproc import Citation, CitationItem, CitationStylesBibliography
        from citeproc import CitationStylesStyle, formatter
        from citeproc.source.json import CiteProcJSON
    except ImportError as exc:
        raise CitationStyleError("CSL 引用组件缺失，请重新安装 Workmode。") from exc

    records = [_csl_record(item) for item in items]
    source = CiteProcJSON(records)
    with tempfile.TemporaryDirectory(prefix="workmode-csl-") as temp_dir:
        style_path = Path(temp_dir) / "style.csl"
        style_path.write_text(_style_xml(style_id), encoding="utf-8")
        style = CitationStylesStyle(str(style_path), validate=False)
        bibliography = CitationStylesBibliography(style, source, formatter.plain)
        for item in items:
            bibliography.register(Citation([CitationItem(_reference_key(item))]))
        return [_clean_rendered(entry) for entry in bibliography.bibliography()]


def _author_label(metadata: dict[str, Any]) -> str:
    authors = _split_authors(metadata.get("authors"))
    if not authors:
        return str(metadata.get("title") or "未命名文献")
    families = [author["family"] for author in authors]
    if len(families) == 1:
        return families[0]
    if len(families) == 2:
        return f"{families[0]} & {families[1]}"
    return f"{families[0]} et al."


def _year_label(metadata: dict[str, Any]) -> str:
    value = str(metadata.get("year") or metadata.get("publication_date") or "").strip()
    match = re.search(r"\d{4}", value)
    return match.group(0) if match else value or "n.d."


def _locator_text(item: dict[str, Any]) -> str:
    locator = item.get("locator")
    if not isinstance(locator, dict) or not str(locator.get("value") or "").strip():
        return ""
    labels = {
        "page": "p.",
        "chapter": "chap.",
        "figure": "fig.",
        "section": "sec.",
        "paragraph": "para.",
        "volume": "vol.",
    }
    label = labels.get(str(locator.get("label") or ""), str(locator.get("label") or ""))
    return f"{label} {str(locator['value']).strip()}".strip()


def _collapse_numbers(numbers: list[int]) -> str:
    ordered = sorted(set(numbers))
    ranges: list[str] = []
    start = previous = ordered[0]
    for number in ordered[1:] + [ordered[-1] + 2]:
        if number == previous + 1:
            previous = number
            continue
        ranges.append(str(start) if start == previous else f"{start}–{previous}")
        start = previous = number
    return ",".join(ranges)


def _render_group(
    items: list[dict[str, Any]],
    style_id: str,
    numbers: dict[str, int],
) -> str:
    prefix = next((str(item.get("prefix") or "").strip() for item in items if item.get("prefix")), "")
    suffix = next((str(item.get("suffix") or "").strip() for item in items if item.get("suffix")), "")
    locator = next((_locator_text(item) for item in items if _locator_text(item)), "")
    if style_id == "apa-7th":
        cites = []
        for item in items:
            metadata = dict(item.get("metadata") or {})
            year = _year_label(metadata)
            author = "" if item.get("suppress_author") else f"{_author_label(metadata)}, "
            item_locator = _locator_text(item)
            cites.append(f"{author}{year}{f', {item_locator}' if item_locator else ''}")
        core = f"({'; '.join(cites)})"
    else:
        collapsed = _collapse_numbers([numbers[_reference_key(item)] for item in items])
        if style_id == "nature":
            core = collapsed
        elif style_id in {"american-chemical-society", "vancouver"}:
            core = f"({collapsed})"
        else:
            core = f"[{collapsed}]"
        if locator:
            core = f"{core}, {locator}"
    return " ".join(part for part in (prefix, core, suffix) if part)


def render_citation_document(
    groups: list[dict[str, Any]],
    style_id: str,
) -> dict[str, Any]:
    style_id = validate_style_id(style_id)
    unique_items: list[dict[str, Any]] = []
    numbers: dict[str, int] = {}
    for group in groups:
        for item in list(group.get("items") or []):
            key = _reference_key(item)
            if key not in numbers:
                numbers[key] = len(unique_items) + 1
                unique_items.append(item)
    citation_texts = {
        str(group["instance_id"]): _render_group(list(group.get("items") or []), style_id, numbers)
        for group in groups
        if group.get("instance_id") and group.get("items")
    }
    return {
        "style_id": style_id,
        "citation_texts": citation_texts,
        "bibliography_entries": _render_bibliography(unique_items, style_id) if unique_items else [],
        "reference_count": len(unique_items),
    }
