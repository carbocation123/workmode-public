from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pdf_text import PdfTextExtractionError, extract_pdf_text
from .project_tools import ProjectToolResult


MANIFEST_FILENAME = "literature-project.json"
PROJECT_TYPE = "literature-library"
TOOL_PROFILE = "literature"
SCHEMA_VERSION = 1
MAX_TEXT_RESULT_CHARS = 120_000

FIXED_DIRECTORIES = (
    "papers/unprocessed/pdf",
    "papers/unprocessed/extracted",
    "papers/processed/pdf",
    "papers/processed/extracted",
    "notes",
    "exports",
)

LITERATURE_PROTOCOL = """# Literature library collaboration protocol

This is a specialized Workmode literature-library project. The project folder is the
source of truth; the literature interface is a projection of these files. Formal
Workmode sessions, JSONL tool events, context budgeting, compaction and cancellation
remain the conversation kernel.

## Fixed structure

- `catalog.json`: authoritative paper records and project-relative paths.
- `tags.json`: the semi-open tag registry. Paper records store tag IDs.
- `papers/unprocessed/pdf/`: imported PDFs awaiting discussion or archival checks.
- `papers/unprocessed/extracted/<paper-id>/`: MinerU text, layout, images and facts.
- `papers/processed/`: archived PDF and extraction trees.
- `notes/*.md`: project notes that may be searched and discussed.
- `exports/`: generated Markdown or PDF note exports.

Do not create parallel catalogs, hidden metadata stores or extra root directories.

## Tool boundary

Only literature-domain tools are available in this mode. There is no shell, Python,
generic file editor, web search, generic memory tool or plan tool. A literature tool
call is an executable request: it does not require a second proposal/approval tool or
a `confirmed` boolean. The backend still validates the project root, paper IDs, fixed
paths, JSON schemas and atomic writes.

The papers or notes selected in the interface are current context, like an editor's
current file. Selection is never permission. A domain tool may operate on any real
paper ID in the current project.

Before assigning or replacing paper tags, call `literature_tag_list` and inspect the
canonical registry. Reuse existing names or aliases whenever possible; create a new
provisional tag only when no existing tag expresses the same concept.

## Evidence discipline

Facts, numeric values, phenomena and author claims must keep their source locations.
Objective fact reports contain source facts only. Cross-paper interpretation belongs
in the explicit cross-literature section or project notes and must not masquerade as
paper facts. Metadata comes from the PDF first page `Cite This` line, with existing
`layout.json` header blocks as fallback; do not infer it from filenames or search
snippets.

When MinerU Markdown is absent or unavailable, `literature_read(part="full_text")`
automatically reads the PDF text layer. Use the returned `source` and `warning` fields:
the fallback preserves readable text but does not recover scanned pages, figures,
tables or layout as reliably as MinerU.
"""


LITERATURE_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "literature_search",
            "description": "Search the current literature project's catalog by title, author, journal, DOI, tags, focus, summary or status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Free-text query; empty returns recent records."},
                    "tag_ids": {"type": "array", "items": {"type": "string"}, "default": []},
                    "status": {"type": "string", "description": "Optional exact paper status."},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "literature_tag_list",
            "description": "List the canonical semi-open tag registry before assigning tags. Returns tag IDs, names, aliases, categories, status and usage counts so existing tags can be reused instead of duplicated.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Optional text matched against tag ID, name, aliases and category."},
                    "category": {"type": "string", "description": "Optional exact category filter."},
                    "status": {"type": "string", "description": "Optional exact status filter, such as confirmed or provisional."},
                    "limit": {"type": "integer", "default": 200, "minimum": 1, "maximum": 500},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "literature_read",
            "description": "Read one paper record, its objective fact report, or full text. Full text prefers MinerU Markdown and automatically falls back to the PDF text layer. Use offset and limit for long content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_id": {"type": "string"},
                    "part": {"type": "string", "enum": ["record", "facts", "full_text"], "default": "record"},
                    "offset": {"type": "integer", "default": 0, "minimum": 0},
                    "limit": {"type": "integer", "default": 400, "minimum": 1, "maximum": 3000},
                },
                "required": ["paper_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "literature_import",
            "description": "Import an existing project-relative PDF into the fixed literature library. Metadata is left pending rather than guessed.",
            "parameters": {
                "type": "object",
                "properties": {"source_path": {"type": "string", "description": "Project-relative path to a PDF."}},
                "required": ["source_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "literature_process",
            "description": "Start or retry the configured MinerU and objective-fact pipeline for a real paper ID.",
            "parameters": {
                "type": "object",
                "properties": {"paper_id": {"type": "string"}},
                "required": ["paper_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "literature_update_record",
            "description": "Directly update tags, user focus, short summary or bibliographic fields for a paper. Call literature_tag_list before assigning tags and reuse canonical names/aliases whenever possible. No proposal or confirmation step is required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_id": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "category": {"type": "string"},
                                "aliases": {"type": "array", "items": {"type": "string"}, "default": []},
                            },
                            "required": ["name", "category"],
                        },
                    },
                    "focus": {"type": "string"},
                    "summary": {"type": "string"},
                    "title": {"type": "string"},
                    "authors": {"type": "string"},
                    "first_author_surname": {"type": "string"},
                    "year": {"type": "integer"},
                    "journal": {"type": "string"},
                    "journal_abbreviation": {"type": "string"},
                    "doi": {"type": "string"},
                    "paper_type": {"type": "string", "enum": ["research", "review"]},
                    "metadata_source": {"type": "string", "enum": ["cite_this", "layout_json", "manual", "pending"]},
                },
                "required": ["paper_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "literature_update_cross_relation",
            "description": "Directly write the explicitly separated cross-literature discussion section of a paper's fact report.",
            "parameters": {
                "type": "object",
                "properties": {"paper_id": {"type": "string"}, "markdown": {"type": "string"}},
                "required": ["paper_id", "markdown"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "literature_archive",
            "description": "Validate and move a complete paper plus extracted artifacts from unprocessed to processed, then rebuild the readable index.",
            "parameters": {"type": "object", "properties": {"paper_id": {"type": "string"}}, "required": ["paper_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "literature_note_search",
            "description": "Search project notes by filename, title or Markdown content.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "literature_note_read",
            "description": "Read a project note by notes-relative filename, with line-range pagination.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "offset": {"type": "integer", "default": 0, "minimum": 0},
                    "limit": {"type": "integer", "default": 1000, "minimum": 1, "maximum": 3000},
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "literature_note_upsert",
            "description": "Directly create or replace one Markdown note under notes/. No approval flag is used.",
            "parameters": {
                "type": "object",
                "properties": {"filename": {"type": "string"}, "markdown": {"type": "string"}},
                "required": ["filename", "markdown"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "literature_note_export",
            "description": "Export a project note to exports/ as Markdown. PDF export will only succeed when the local renderer is configured.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "format": {"type": "string", "enum": ["md", "pdf"], "default": "md"},
                    "output_name": {"type": "string"},
                },
                "required": ["filename"],
            },
        },
    },
]


class LiteratureProjectError(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialize_literature_project(root: Path, *, name: str) -> None:
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    for rel in FIXED_DIRECTORIES:
        (root / rel).mkdir(parents=True, exist_ok=True)

    defaults: dict[str, str] = {
        MANIFEST_FILENAME: json.dumps(
            {
                "project_type": PROJECT_TYPE,
                "schema_version": SCHEMA_VERSION,
                "tool_profile": TOOL_PROFILE,
                "frontend_projection": "literature-library",
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        "WORKMODE.md": "# Literature library Workmode project\n\n@LITERATURE_PROJECT.md\n",
        "LITERATURE_PROJECT.md": LITERATURE_PROTOCOL.rstrip() + "\n",
        "README.md": f"# {name}\n\nThis folder is a fixed-structure Workmode literature library.\n",
        "catalog.json": json.dumps({"schema_version": SCHEMA_VERSION, "papers": []}, ensure_ascii=False, indent=2) + "\n",
        "tags.json": json.dumps({"schema_version": SCHEMA_VERSION, "tags": []}, ensure_ascii=False, indent=2) + "\n",
        "processed-index.md": "# Processed literature index\n\nNo processed papers yet.\n",
        "papers/README.md": "# Papers\n\nPDF and extraction trees are maintained by literature-domain services.\n",
        "notes/README.md": "# Notes\n\nProject-level Markdown notes. Keep citations and distinguish facts from discussion.\n",
    }
    for rel, content in defaults.items():
        target = root / rel
        if not target.exists():
            _atomic_write_text(target, content)


def load_manifest(root: Path) -> dict[str, Any] | None:
    path = root.expanduser().resolve() / MANIFEST_FILENAME
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LiteratureProjectError(f"Invalid {MANIFEST_FILENAME}: {exc}") from exc
    if not isinstance(payload, dict):
        raise LiteratureProjectError(f"Invalid {MANIFEST_FILENAME}: root must be an object")
    return payload


def is_literature_project(root: Path) -> bool:
    manifest = load_manifest(root)
    return bool(manifest and manifest.get("project_type") == PROJECT_TYPE)


def project_type(root: Path) -> str:
    manifest = load_manifest(root)
    return str(manifest.get("project_type")) if manifest and manifest.get("project_type") else "workmode"


def tool_profile(root: Path) -> str:
    return TOOL_PROFILE if is_literature_project(root) else "workmode"


def describe_active_context(root: Path, items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    catalog = _catalog(root)
    paper_by_id = {str(item["id"]): item for item in catalog["papers"]}
    rows: list[dict[str, Any]] = []
    for item in items:
        kind = str(item.get("kind") or "")
        reference = str(item.get("id") or "")
        if kind == "paper":
            paper = paper_by_id.get(reference)
            rows.append(
                {
                    "kind": "paper",
                    "id": reference,
                    "exists": paper is not None,
                    "record": _paper_summary(paper) if paper else None,
                }
            )
        elif kind == "note":
            try:
                note = _note_path(root, reference)
            except LiteratureProjectError:
                rows.append({"kind": "note", "id": reference, "exists": False})
            else:
                rows.append(
                    {
                        "kind": "note",
                        "id": reference,
                        "exists": note.exists(),
                        "path": note.relative_to(root).as_posix(),
                    }
                )
    if not rows:
        return ""
    return (
        "<CURRENT_LITERATURE_CONTEXT>\n"
        "The user selected these current references for this turn. Selection prioritizes context and is not permission.\n"
        + json.dumps(rows, ensure_ascii=False, indent=2)
        + "\n</CURRENT_LITERATURE_CONTEXT>"
    )


def describe_imported_papers(root: Path, paper_ids: list[str]) -> str:
    catalog = _catalog(root)
    paper_by_id = {str(item["id"]): item for item in catalog["papers"]}
    records = [
        _paper_summary(paper_by_id[paper_id])
        for paper_id in dict.fromkeys(str(item) for item in paper_ids)
        if paper_id in paper_by_id
    ]
    if not records:
        return ""
    return (
        "<LITERATURE_IMPORT_EVENT>\n"
        "The user explicitly confirmed these PDFs for import into the current literature library. "
        "They are already registered records; do not ask for local paths or call literature_import again. "
        "When the user says to continue, use the paper IDs below and call literature_process if processing is still needed.\n"
        + json.dumps(records, ensure_ascii=False, indent=2)
        + "\n</LITERATURE_IMPORT_EVENT>"
    )


def literature_snapshot(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if not is_literature_project(root):
        raise LiteratureProjectError("Current project is not a literature-library project")
    return {
        "manifest": load_manifest(root),
        "catalog": _catalog(root),
        "tags": _tags(root),
        "notes": list_literature_notes(root),
    }


def literature_paper(root: Path, paper_id: str) -> dict[str, Any]:
    return _paper(root.expanduser().resolve(), paper_id)


def update_literature_paper(root: Path, paper_id: str, **updates: Any) -> dict[str, Any]:
    allowed = {
        "title", "authors", "first_author_surname", "year", "journal",
        "journal_abbreviation", "doi", "paper_type", "status", "archive_location",
        "archive_filename", "metadata_source", "metadata_trust", "tag_ids", "focus",
        "summary", "paths", "verification_status", "stage", "error",
    }
    unexpected = set(updates) - allowed
    if unexpected:
        raise LiteratureProjectError(f"Unsupported paper fields: {', '.join(sorted(unexpected))}")
    catalog = _catalog(root)
    paper = _find_paper(catalog, paper_id)
    paper.update(updates)
    paper["updated_at"] = utc_now()
    _write_catalog(root, catalog)
    return paper


def apply_literature_metadata(root: Path, paper_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    catalog = _catalog(root)
    paper = _find_paper(catalog, paper_id)
    surname = str(metadata.get("first_author_surname") or "").strip()
    abbreviation = str(metadata.get("journal_abbreviation") or "").strip()
    year = metadata.get("year")
    if not surname or not re.fullmatch(r"[A-Za-z][A-Za-z'-]*", surname):
        raise LiteratureProjectError("Cannot build standard filename: invalid first author surname")
    if not isinstance(year, int) or not (1000 <= year <= 3000):
        raise LiteratureProjectError("Cannot build standard filename: invalid year")
    if not abbreviation or not re.fullmatch(r"[A-Za-z0-9]+", abbreviation):
        raise LiteratureProjectError("Cannot build standard filename: journal abbreviation must contain only letters and digits")
    base = f"{surname}_{year}_{abbreviation}"
    used = {
        str(item.get("archive_filename") or "").casefold()
        for item in catalog["papers"]
        if item.get("id") != paper_id
    }
    filename = f"{base}.pdf"
    suffix = 2
    while filename.casefold() in used:
        filename = f"{base}_{suffix}.pdf"
        suffix += 1

    paths = dict(paper.get("paths") or {})
    current_rel = str(paths.get("pdf") or "")
    if not current_rel:
        raise LiteratureProjectError("Paper PDF path is missing")
    current = _resolve(root, current_rel)
    target = root / "papers/unprocessed/pdf" / filename
    if current.resolve() != target.resolve():
        if target.exists():
            raise LiteratureProjectError(f"Standard PDF target already exists: {target.relative_to(root).as_posix()}")
        current.replace(target)
    paths["pdf"] = target.relative_to(root).as_posix()
    normalized_source = "layout_json" if metadata.get("metadata_source") == "layout_json_fallback" else metadata.get("metadata_source")
    for key in (
        "title", "authors", "first_author_surname", "year", "journal",
        "journal_abbreviation", "doi", "paper_type",
    ):
        paper[key] = metadata.get(key) if metadata.get(key) is not None else ""
    paper["archive_filename"] = filename
    paper["metadata_source"] = normalized_source or "pending"
    paper["metadata_trust"] = "complete"
    paper["paths"] = paths
    paper["updated_at"] = utc_now()
    _write_catalog(root, catalog)
    return paper


def verify_literature_archive(root: Path, paper_id: str) -> dict[str, Any]:
    root = root.expanduser().resolve()
    paper = _paper(root, paper_id)
    issues: list[str] = []
    paths = paper.get("paths") or {}
    for key, label in (("pdf", "source PDF"), ("full_md", "MinerU full.md"), ("fact_report", "objective fact report")):
        rel = str(paths.get(key) or "")
        if not rel or not _resolve(root, rel).exists():
            issues.append(f"Missing {label}")
    for key, label in (
        ("title", "title"),
        ("authors", "authors"),
        ("first_author_surname", "first author surname"),
        ("year", "year"),
        ("journal_abbreviation", "journal abbreviation"),
        ("archive_filename", "standard archive filename"),
    ):
        if not paper.get(key):
            issues.append(f"Missing {label}")
    fact_rel = str(paths.get("fact_report") or "")
    if fact_rel and _resolve(root, fact_rel).exists():
        report = _resolve(root, fact_rel).read_text(encoding="utf-8")
        if "## 6. Cross-literature relations" not in report:
            issues.append("Missing cross-literature relations section")
    return {"ok": not issues, "paper_id": paper_id, "issues": issues}


def list_literature_notes(root: Path) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for path in sorted((root / "notes").glob("*.md")):
        if path.name.casefold() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8")
        title = next((line.removeprefix("# ").strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
        notes.append(
            {
                "id": path.name,
                "filename": path.name,
                "title": title,
                "markdown": text,
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            }
        )
    return notes


def register_staged_pdf(root: Path, staged_path: Path, *, original_filename: str) -> dict[str, Any]:
    root = root.expanduser().resolve()
    staged_path = staged_path.resolve()
    if not is_literature_project(root):
        raise LiteratureProjectError("Current project is not a literature-library project")
    if not staged_path.exists() or not staged_path.is_file():
        raise LiteratureProjectError("Staged PDF does not exist")
    with staged_path.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise LiteratureProjectError("PDF file header validation failed")
    filename = Path(original_filename).name
    if filename != original_filename or not filename.lower().endswith(".pdf"):
        raise LiteratureProjectError("Upload filename must be one PDF basename")
    digest = _sha256_file(staged_path)
    catalog = _catalog(root)
    for paper in catalog["papers"]:
        if paper.get("content_sha256") == digest:
            staged_path.unlink(missing_ok=True)
            return {"paper": paper, "duplicate": True, "changed_files": []}

    paper_id = digest[:24]
    target_dir = root / "papers/unprocessed/pdf"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    suffix = 2
    while target.exists() and target.resolve() != staged_path:
        target = target_dir / f"{Path(filename).stem}_{suffix}.pdf"
        suffix += 1
    if target.resolve() != staged_path:
        staged_path.replace(target)
    rel = target.relative_to(root).as_posix()
    now = utc_now()
    paper = {
        "id": paper_id,
        "content_sha256": digest,
        "title": "",
        "authors": "",
        "first_author_surname": "",
        "year": None,
        "journal": "",
        "journal_abbreviation": "",
        "doi": "",
        "paper_type": "research",
        "status": "pending",
        "archive_location": "papers/unprocessed",
        "original_filename": filename,
        "archive_filename": None,
        "metadata_source": "pending",
        "metadata_trust": "pending",
        "tag_ids": [],
        "focus": "",
        "summary": "",
        "paths": {"pdf": rel, "mineru_dir": "", "full_md": "", "fact_report": ""},
        "verification_status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    catalog["papers"].append(paper)
    _write_catalog(root, catalog)
    return {"paper": paper, "duplicate": False, "changed_files": ["catalog.json", rel]}


def execute_literature_tool(
    project_slug: str,
    name: str,
    args: dict[str, Any],
    *,
    cancel_event: threading.Event | None = None,
) -> ProjectToolResult:
    from .storage import get_project

    if cancel_event is not None and cancel_event.is_set():
        return ProjectToolResult(ok=False, content=_error_payload("CANCELLED", "The user stopped this turn."))
    project = get_project(project_slug)
    root = Path(project.root_path).expanduser().resolve()
    try:
        if not is_literature_project(root):
            raise LiteratureProjectError("Current project is not a literature-library project")
        handlers = {
            "literature_search": _search,
            "literature_tag_list": _tag_list,
            "literature_read": _read,
            "literature_import": _import_pdf,
            "literature_update_record": _update_record,
            "literature_update_cross_relation": _update_cross_relation,
            "literature_archive": _archive,
            "literature_note_search": _note_search,
            "literature_note_read": _note_read,
            "literature_note_upsert": _note_upsert,
            "literature_note_export": _note_export,
        }
        if name == "literature_process":
            return _process(root, args, cancel_event=cancel_event)
        if name == "literature_read":
            return _read(root, args, cancel_event=cancel_event)
        handler = handlers.get(name)
        if handler is None:
            raise LiteratureProjectError(f"Unknown literature tool: {name}")
        return handler(root, args)
    except LiteratureProjectError as exc:
        return ProjectToolResult(ok=False, content=_error_payload("VALIDATION_ERROR", str(exc)))
    except Exception as exc:
        return ProjectToolResult(ok=False, content=_error_payload("INTERNAL_ERROR", str(exc)))


def _search(root: Path, args: dict[str, Any]) -> ProjectToolResult:
    query = str(args.get("query") or "").strip().casefold()
    requested_tags = {str(item) for item in (args.get("tag_ids") or [])}
    status = str(args.get("status") or "").strip()
    limit = min(max(int(args.get("limit") or 20), 1), 100)
    papers = _catalog(root)["papers"]
    tags_by_id = {item["id"]: item for item in _tags(root)["tags"]}
    matches: list[dict[str, Any]] = []
    for paper in reversed(papers):
        tag_ids = {str(item) for item in paper.get("tag_ids") or []}
        if requested_tags and not requested_tags.issubset(tag_ids):
            continue
        if status and str(paper.get("status") or "") != status:
            continue
        haystack = "\n".join(
            str(paper.get(key) or "")
            for key in ("title", "authors", "journal", "doi", "focus", "summary", "original_filename", "archive_filename")
        )
        haystack += "\n" + " ".join(
            str(tags_by_id.get(tag_id, {}).get("name") or tag_id) for tag_id in tag_ids
        )
        if query and query not in haystack.casefold():
            continue
        matches.append(_paper_summary(paper))
        if len(matches) >= limit:
            break
    return _json_result({"ok": True, "operation": "literature_search", "count": len(matches), "papers": matches})


def _tag_list(root: Path, args: dict[str, Any]) -> ProjectToolResult:
    query = str(args.get("query") or "").strip().casefold()
    requested_category = str(args.get("category") or "").strip().casefold()
    requested_status = str(args.get("status") or "").strip().casefold()
    limit = min(max(int(args.get("limit") or 200), 1), 500)

    registry = _tags(root)["tags"]
    usage_counts: dict[str, int] = {}
    for paper in _catalog(root)["papers"]:
        for tag_id in set(str(item) for item in (paper.get("tag_ids") or [])):
            usage_counts[tag_id] = usage_counts.get(tag_id, 0) + 1

    category_counts: dict[str, int] = {}
    matched: list[dict[str, Any]] = []
    for raw_tag in registry:
        if not isinstance(raw_tag, dict) or not isinstance(raw_tag.get("id"), str):
            raise LiteratureProjectError("tags.json contains an invalid tag record")
        tag_id = str(raw_tag["id"])
        name = str(raw_tag.get("name") or tag_id)
        aliases = [str(item) for item in (raw_tag.get("aliases") or [])]
        category = str(raw_tag.get("category") or "uncategorized")
        status = str(raw_tag.get("status") or "confirmed")
        category_counts[category] = category_counts.get(category, 0) + 1
        if requested_category and category.casefold() != requested_category:
            continue
        if requested_status and status.casefold() != requested_status:
            continue
        haystack = "\n".join([tag_id, name, category, *aliases]).casefold()
        if query and query not in haystack:
            continue
        matched.append(
            {
                "id": tag_id,
                "name": name,
                "aliases": aliases,
                "category": category,
                "status": status,
                "usage_count": usage_counts.get(tag_id, 0),
            }
        )

    matched.sort(key=lambda item: (item["category"].casefold(), item["name"].casefold(), item["id"].casefold()))
    visible = matched[:limit]
    categories = [
        {"id": category, "tag_count": count}
        for category, count in sorted(category_counts.items(), key=lambda item: item[0].casefold())
    ]
    return _json_result(
        {
            "ok": True,
            "operation": "literature_tag_list",
            "registry_count": len(registry),
            "matched_count": len(matched),
            "count": len(visible),
            "truncated": len(visible) < len(matched),
            "categories": categories,
            "tags": visible,
        }
    )


def _read(
    root: Path,
    args: dict[str, Any],
    *,
    cancel_event: threading.Event | None = None,
) -> ProjectToolResult:
    paper = _paper(root, _require_string(args, "paper_id"))
    part = str(args.get("part") or "record")
    if part == "record":
        return _json_result({"ok": True, "operation": "literature_read", "paper": paper})
    key = "fact_report" if part == "facts" else "full_md" if part == "full_text" else None
    if key is None:
        raise LiteratureProjectError("part must be record, facts or full_text")
    offset = max(int(args.get("offset") or 0), 0)
    limit = min(max(int(args.get("limit") or 400), 1), 3000)
    rel = str((paper.get("paths") or {}).get(key) or "")
    path = _resolve(root, rel) if rel else None
    source = "mineru_markdown" if part == "full_text" else "objective_fact_report"
    extra: dict[str, Any] = {}

    if (
        path is not None
        and path.exists()
        and path.is_file()
        and (part != "full_text" or path.stat().st_size > 0)
    ):
        text = path.read_text(encoding="utf-8")
    elif part == "full_text":
        pdf_rel = str((paper.get("paths") or {}).get("pdf") or "")
        if not pdf_rel:
            raise LiteratureProjectError("Paper has no PDF path")
        pdf_path = _resolve(root, pdf_rel)
        try:
            extraction = extract_pdf_text(pdf_path, cancel_event=cancel_event)
        except PdfTextExtractionError as exc:
            raise LiteratureProjectError(str(exc)) from exc
        text = extraction.text
        rel = pdf_rel
        source = "pdf_text_layer"
        warning_parts = [
            "MinerU Markdown is unavailable, so this content came from the PDF text layer. "
            "Scanned pages, figures, tables, formulas and multi-column order may be incomplete."
        ]
        warning_parts.extend(extraction.warnings)
        extra = {
            "page_count": extraction.page_count,
            "pages_with_text": extraction.pages_with_text,
            "truncated": extraction.truncated,
            "warning": " ".join(warning_parts),
            "warnings": warning_parts,
        }
    else:
        if not rel:
            raise LiteratureProjectError(f"Paper has no {key} path")
        raise LiteratureProjectError(f"Referenced file does not exist: {rel}")

    lines = text.splitlines()
    selected = lines[offset : offset + limit]
    return _json_result(
        {
            "ok": True,
            "operation": "literature_read",
            "paper_id": paper["id"],
            "part": part,
            "path": rel,
            "source": source,
            "offset": offset,
            "next_offset": offset + len(selected) if offset + len(selected) < len(lines) else None,
            "total_lines": len(lines),
            "content": "\n".join(selected),
            **extra,
        }
    )


def _import_pdf(root: Path, args: dict[str, Any]) -> ProjectToolResult:
    source_rel = _require_string(args, "source_path")
    source = _resolve(root, source_rel)
    if not source.exists() or not source.is_file() or source.suffix.lower() != ".pdf":
        raise LiteratureProjectError("source_path must point to an existing project PDF")
    with source.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise LiteratureProjectError("PDF file header validation failed")
    digest = _sha256_file(source)
    catalog = _catalog(root)
    for paper in catalog["papers"]:
        if paper.get("content_sha256") == digest:
            return _json_result(
                {"ok": True, "operation": "literature_import", "paper_id": paper["id"], "duplicate": True, "changed_files": []}
            )
    paper_id = digest[:24]
    target_dir = root / "papers/unprocessed/pdf"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if target.exists() and target.resolve() != source.resolve():
        target = target_dir / f"{source.stem}_{paper_id[:8]}.pdf"
    if target.resolve() != source.resolve():
        shutil.copy2(source, target)
    rel = target.relative_to(root).as_posix()
    now = utc_now()
    catalog["papers"].append(
        {
            "id": paper_id,
            "content_sha256": digest,
            "title": "",
            "authors": "",
            "first_author_surname": "",
            "year": None,
            "journal": "",
            "journal_abbreviation": "",
            "doi": "",
            "paper_type": "research",
            "status": "pending",
            "archive_location": "papers/unprocessed",
            "original_filename": source.name,
            "archive_filename": None,
            "metadata_source": "pending",
            "metadata_trust": "pending",
            "tag_ids": [],
            "focus": "",
            "summary": "",
            "paths": {"pdf": rel, "mineru_dir": "", "full_md": "", "fact_report": ""},
            "verification_status": "pending",
            "created_at": now,
            "updated_at": now,
        }
    )
    _write_catalog(root, catalog)
    return _json_result(
        {"ok": True, "operation": "literature_import", "paper_id": paper_id, "duplicate": False, "changed_files": ["catalog.json", rel]},
        changed_paths=["catalog.json", rel],
    )


def _process(
    root: Path,
    args: dict[str, Any],
    *,
    cancel_event: threading.Event | None,
) -> ProjectToolResult:
    from .literature_pipeline import run_literature_pipeline

    paper_id = _require_string(args, "paper_id")
    _paper(root, paper_id)
    result = run_literature_pipeline(root, paper_id, cancel_event=cancel_event)
    changed = ["catalog.json", *result.get("changed_files", [])]
    return _json_result(
        {"ok": True, "operation": "literature_process", "paper_id": paper_id, **result},
        changed_paths=list(dict.fromkeys(changed)),
    )


def _update_record(root: Path, args: dict[str, Any]) -> ProjectToolResult:
    paper_id = _require_string(args, "paper_id")
    catalog = _catalog(root)
    paper = _find_paper(catalog, paper_id)
    changed_fields: list[str] = []
    changed_paths = ["catalog.json"]

    scalar_fields = (
        "focus",
        "summary",
        "title",
        "authors",
        "first_author_surname",
        "year",
        "journal",
        "journal_abbreviation",
        "doi",
        "paper_type",
        "metadata_source",
    )
    for key in scalar_fields:
        if key in args and args[key] is not None:
            paper[key] = args[key]
            changed_fields.append(key)

    if "tags" in args:
        raw_tags = args.get("tags")
        if not isinstance(raw_tags, list):
            raise LiteratureProjectError("tags must be an array")
        registry = _tags(root)
        tag_ids: list[str] = []
        for raw_tag in raw_tags:
            if not isinstance(raw_tag, dict):
                raise LiteratureProjectError("each tag must be an object")
            tag_ids.append(_upsert_tag(registry, raw_tag))
        paper["tag_ids"] = list(dict.fromkeys(tag_ids))
        paper["updated_at"] = utc_now()
        _write_tags(root, registry)
        changed_fields.append("tag_ids")
        changed_paths.append("tags.json")

    if not changed_fields:
        raise LiteratureProjectError("No writable record fields were supplied")
    paper["updated_at"] = utc_now()
    _write_catalog(root, catalog)
    return _json_result(
        {
            "ok": True,
            "operation": "literature_update_record",
            "paper_id": paper_id,
            "changed_files": changed_paths,
            "updated_fields": changed_fields,
        },
        changed_paths=changed_paths,
    )


def _update_cross_relation(root: Path, args: dict[str, Any]) -> ProjectToolResult:
    paper_id = _require_string(args, "paper_id")
    markdown = _require_string(args, "markdown").strip()
    paper = _paper(root, paper_id)
    rel = str((paper.get("paths") or {}).get("fact_report") or "")
    if not rel:
        raise LiteratureProjectError("Paper has no objective fact report")
    path = _resolve(root, rel)
    if not path.exists():
        raise LiteratureProjectError(f"Objective fact report does not exist: {rel}")
    text = path.read_text(encoding="utf-8")
    heading = "## 6. Cross-literature relations"
    pattern = re.compile(r"(?ms)^## 6\. Cross-literature relations\s*$.*?(?=^## |\Z)")
    section = f"{heading}\n\n{markdown}\n"
    updated = pattern.sub(section, text).rstrip() + "\n" if pattern.search(text) else text.rstrip() + f"\n\n{section}"
    _atomic_write_text(path, updated)
    return _json_result(
        {"ok": True, "operation": "literature_update_cross_relation", "paper_id": paper_id, "changed_files": [rel]},
        changed_paths=[rel],
    )


def _archive(root: Path, args: dict[str, Any]) -> ProjectToolResult:
    paper_id = _require_string(args, "paper_id")
    catalog = _catalog(root)
    paper = _find_paper(catalog, paper_id)
    if paper.get("archive_location") == "papers/processed":
        return _json_result({"ok": True, "operation": "literature_archive", "paper_id": paper_id, "already_processed": True, "changed_files": []})
    verification = verify_literature_archive(root, paper_id)
    if not verification["ok"]:
        raise LiteratureProjectError("Archive blocked: " + "; ".join(verification["issues"]))
    paths = paper.get("paths") or {}
    pdf_rel = str(paths.get("pdf") or "")
    fact_rel = str(paths.get("fact_report") or "")
    full_rel = str(paths.get("full_md") or "")
    source_pdf = _resolve(root, pdf_rel)
    target_pdf = root / "papers/processed/pdf" / str(paper["archive_filename"])
    target_pdf.parent.mkdir(parents=True, exist_ok=True)
    if target_pdf.exists() and target_pdf.resolve() != source_pdf.resolve():
        raise LiteratureProjectError(f"Archive target already exists: {target_pdf.relative_to(root).as_posix()}")

    source_extract_rel = str(paths.get("mineru_dir") or "")
    source_extract = _resolve(root, source_extract_rel) if source_extract_rel else None
    target_extract = root / "papers/processed/extracted" / paper_id
    if source_extract and source_extract.exists() and target_extract.exists():
        raise LiteratureProjectError(f"Archive extraction target already exists: {target_extract.relative_to(root).as_posix()}")

    # Validate every destination before moving either tree.  A collision in the
    # extraction directory must never leave the PDF stranded in processed/ while
    # catalog.json still points at unprocessed/.
    source_pdf.replace(target_pdf)
    if source_extract and source_extract.exists():
        target_extract.parent.mkdir(parents=True, exist_ok=True)
        source_extract.replace(target_extract)
        paths["mineru_dir"] = target_extract.relative_to(root).as_posix()
        for key, filename in (("full_md", "full.md"), ("fact_report", "objective-facts.md")):
            candidate = target_extract / filename
            if candidate.exists():
                paths[key] = candidate.relative_to(root).as_posix()
    paths["pdf"] = target_pdf.relative_to(root).as_posix()
    paper["archive_location"] = "papers/processed"
    paper["status"] = "ready"
    paper["verification_status"] = "verified"
    paper["updated_at"] = utc_now()
    _write_catalog(root, catalog)
    _rebuild_processed_index(root, catalog)
    changed = ["catalog.json", "processed-index.md", paths["pdf"]]
    return _json_result(
        {"ok": True, "operation": "literature_archive", "paper_id": paper_id, "changed_files": changed},
        changed_paths=changed,
    )


def _note_search(root: Path, args: dict[str, Any]) -> ProjectToolResult:
    query = _require_string(args, "query").casefold()
    limit = min(max(int(args.get("limit") or 20), 1), 100)
    matches: list[dict[str, Any]] = []
    for path in sorted((root / "notes").glob("*.md")):
        if path.name.casefold() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8")
        if query not in f"{path.name}\n{text}".casefold():
            continue
        title = next((line.removeprefix("# ").strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
        matches.append({"filename": path.name, "title": title, "preview": text[:500]})
        if len(matches) >= limit:
            break
    return _json_result({"ok": True, "operation": "literature_note_search", "count": len(matches), "notes": matches})


def _note_read(root: Path, args: dict[str, Any]) -> ProjectToolResult:
    path = _note_path(root, _require_string(args, "filename"))
    if not path.exists():
        raise LiteratureProjectError(f"Note does not exist: {path.name}")
    lines = path.read_text(encoding="utf-8").splitlines()
    offset = max(int(args.get("offset") or 0), 0)
    limit = min(max(int(args.get("limit") or 1000), 1), 3000)
    selected = lines[offset : offset + limit]
    return _json_result(
        {
            "ok": True,
            "operation": "literature_note_read",
            "filename": path.name,
            "offset": offset,
            "next_offset": offset + len(selected) if offset + len(selected) < len(lines) else None,
            "total_lines": len(lines),
            "content": "\n".join(selected),
        }
    )


def _note_upsert(root: Path, args: dict[str, Any]) -> ProjectToolResult:
    path = _note_path(root, _require_string(args, "filename"))
    markdown = _require_string(args, "markdown")
    _atomic_write_text(path, markdown.rstrip() + "\n")
    rel = path.relative_to(root).as_posix()
    return _json_result(
        {"ok": True, "operation": "literature_note_upsert", "changed_files": [rel]},
        changed_paths=[rel],
    )


def _note_export(root: Path, args: dict[str, Any]) -> ProjectToolResult:
    source = _note_path(root, _require_string(args, "filename"))
    if not source.exists():
        raise LiteratureProjectError(f"Note does not exist: {source.name}")
    export_format = str(args.get("format") or "md")
    if export_format == "pdf":
        return ProjectToolResult(
            ok=False,
            content=_error_payload("PDF_RENDERER_NOT_CONFIGURED", "The controlled PDF note renderer is not connected yet."),
        )
    output_name = str(args.get("output_name") or source.name).strip()
    if not output_name.lower().endswith(".md"):
        output_name += ".md"
    target = _safe_child(root / "exports", output_name)
    shutil.copy2(source, target)
    rel = target.relative_to(root).as_posix()
    return _json_result(
        {"ok": True, "operation": "literature_note_export", "format": "md", "changed_files": [rel]},
        changed_paths=[rel],
    )


def _catalog(root: Path) -> dict[str, Any]:
    payload = _read_json(root / "catalog.json")
    if payload.get("schema_version") != SCHEMA_VERSION or not isinstance(payload.get("papers"), list):
        raise LiteratureProjectError("catalog.json does not match schema version 1")
    for paper in payload["papers"]:
        if not isinstance(paper, dict) or not isinstance(paper.get("id"), str):
            raise LiteratureProjectError("catalog.json contains an invalid paper record")
    return payload


def _tags(root: Path) -> dict[str, Any]:
    payload = _read_json(root / "tags.json")
    if payload.get("schema_version") != SCHEMA_VERSION or not isinstance(payload.get("tags"), list):
        raise LiteratureProjectError("tags.json does not match schema version 1")
    return payload


def _write_catalog(root: Path, payload: dict[str, Any]) -> None:
    _atomic_write_json(root / "catalog.json", payload)


def _write_tags(root: Path, payload: dict[str, Any]) -> None:
    _atomic_write_json(root / "tags.json", payload)


def _paper(root: Path, paper_id: str) -> dict[str, Any]:
    return _find_paper(_catalog(root), paper_id)


def _find_paper(catalog: dict[str, Any], paper_id: str) -> dict[str, Any]:
    for paper in catalog["papers"]:
        if paper.get("id") == paper_id:
            return paper
    raise LiteratureProjectError(f"Unknown paper_id: {paper_id}")


def _paper_summary(paper: dict[str, Any]) -> dict[str, Any]:
    return {
        key: paper.get(key)
        for key in (
            "id", "title", "authors", "year", "journal", "doi", "status", "tag_ids",
            "focus", "summary", "original_filename", "archive_filename", "archive_location", "paths",
        )
    }


def _upsert_tag(registry: dict[str, Any], raw: dict[str, Any]) -> str:
    name = str(raw.get("name") or "").strip()
    category = str(raw.get("category") or "").strip()
    aliases = [str(item).strip() for item in (raw.get("aliases") or []) if str(item).strip()]
    if not name or not category:
        raise LiteratureProjectError("tag name and category are required")
    wanted = {name.casefold(), *(item.casefold() for item in aliases)}
    for tag in registry["tags"]:
        existing = {str(tag.get("name") or "").casefold(), *(str(item).casefold() for item in tag.get("aliases") or [])}
        if wanted & existing:
            return str(tag["id"])
    tag_id = _slug(name)
    used = {str(item.get("id")) for item in registry["tags"]}
    base = tag_id
    suffix = 2
    while tag_id in used:
        tag_id = f"{base}-{suffix}"
        suffix += 1
    registry["tags"].append(
        {"id": tag_id, "name": name, "aliases": aliases, "category": category, "status": "provisional"}
    )
    return tag_id


def _rebuild_processed_index(root: Path, catalog: dict[str, Any]) -> None:
    lines = ["# Processed literature index", ""]
    for paper in catalog["papers"]:
        if paper.get("archive_location") != "papers/processed":
            continue
        lines.append(f"- **{paper.get('title') or paper.get('archive_filename') or paper['id']}**")
        lines.append(f"  - ID: `{paper['id']}`")
        if paper.get("doi"):
            lines.append(f"  - DOI: `{paper['doi']}`")
        lines.append(f"  - PDF: `{(paper.get('paths') or {}).get('pdf', '')}`")
    if len(lines) == 2:
        lines.append("No processed papers yet.")
    _atomic_write_text(root / "processed-index.md", "\n".join(lines).rstrip() + "\n")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LiteratureProjectError(f"Required project file is missing: {path.name}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LiteratureProjectError(f"Cannot read {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise LiteratureProjectError(f"{path.name} root must be a JSON object")
    return payload


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.workmode.tmp")
    temporary.write_text(content, encoding="utf-8", newline="")
    os.replace(temporary, path)


def _resolve(root: Path, rel_path: str) -> Path:
    raw = Path(rel_path)
    if raw.is_absolute():
        raise LiteratureProjectError("Only project-relative paths are allowed")
    target = (root / raw).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise LiteratureProjectError("Path escapes the literature project") from exc
    return target


def _note_path(root: Path, filename: str) -> Path:
    if Path(filename).name != filename or not filename.lower().endswith(".md"):
        raise LiteratureProjectError("Note filename must be one .md basename")
    return _safe_child(root / "notes", filename)


def _safe_child(folder: Path, filename: str) -> Path:
    target = (folder / filename).resolve()
    try:
        target.relative_to(folder.resolve())
    except ValueError as exc:
        raise LiteratureProjectError("Output path escapes its fixed directory") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _require_string(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LiteratureProjectError(f"{key} must be a non-empty string")
    return value.strip()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or f"tag-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:8]}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _json_result(payload: dict[str, Any], *, changed_paths: list[str] | None = None) -> ProjectToolResult:
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(content) > MAX_TEXT_RESULT_CHARS:
        content = content[:MAX_TEXT_RESULT_CHARS] + "\n…[result truncated]"
    return ProjectToolResult(ok=bool(payload.get("ok", True)), content=content, changed_paths=changed_paths or [])


def _error_payload(code: str, message: str) -> str:
    return json.dumps({"ok": False, "error_code": code, "message": message, "changed_files": []}, ensure_ascii=False, indent=2)
