from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import storage
from .citation_styles import CitationStyleError, citation_style_options
from .literature_project import (
    LiteratureProjectError,
    initialize_literature_project,
    is_literature_project,
    literature_paper,
    literature_snapshot,
)
from .word_citations import (
    WordCitationError,
    build_citation_group_payload,
    create_word_bibliography,
    inspect_word_citations,
    insert_word_citation_group,
    refresh_word_citations,
    remove_word_citation_group,
    update_word_citation_group,
)


router = APIRouter(prefix="/api/word-addin", tags=["word-addin"])


class WordAddinStyleRequest(BaseModel):
    style_id: str = "gb-t-7714-2015-numeric"


class WordAddinCitationRequest(WordAddinStyleRequest):
    paper_ids: list[str] = Field(min_length=1, max_length=50)
    locator_label: str | None = None
    locator_value: str = ""
    prefix: str = ""
    suffix: str = ""
    suppress_author: bool = False


class WordAddinCitationUpdateRequest(WordAddinCitationRequest):
    instance_id: str = Field(min_length=1, max_length=64)


class WordAddinInstanceRequest(WordAddinStyleRequest):
    instance_id: str = Field(min_length=1, max_length=64)


def _active_literature_project() -> tuple[storage.Project, Path]:
    slug = storage.get_active_project_slug()
    if not slug:
        raise HTTPException(status_code=409, detail="请先在 Workmode 中打开一个文献项目。")
    try:
        project = storage.get_project(slug)
    except storage.NotFoundError as exc:
        raise HTTPException(status_code=409, detail="当前 Workmode 项目已经不存在。") from exc
    root = Path(project.root_path).expanduser().resolve()
    if not is_literature_project(root):
        raise HTTPException(status_code=409, detail="当前 Workmode 项目不是文献项目。")
    initialize_literature_project(root, name=project.name)
    return project, root


def _paper_summary(
    paper: dict[str, Any],
    *,
    tag_names: dict[str, str],
    group_names: dict[str, str],
) -> dict[str, Any]:
    tags = list(dict.fromkeys(
        [str(tag) for tag in paper.get("tags") or []]
        + [
            tag_names[tag_id]
            for tag_id in (str(item) for item in paper.get("tag_ids") or [])
            if tag_id in tag_names
        ]
    ))
    groups = [
        group_names[group_id]
        for group_id in (str(item) for item in paper.get("group_ids") or [])
        if group_id in group_names
    ]
    return {
        "id": str(paper.get("id") or ""),
        "title": str(paper.get("title") or "未命名文献"),
        "authors": str(paper.get("authors") or ""),
        "journal": str(paper.get("journal") or ""),
        "year": paper.get("year"),
        "doi": str(paper.get("doi") or ""),
        "tags": tags,
        "groups": groups,
    }


def _citation_payload(request: WordAddinCitationRequest) -> tuple[str, dict[str, Any]]:
    project, root = _active_literature_project()
    try:
        papers = [literature_paper(root, paper_id) for paper_id in request.paper_ids]
    except LiteratureProjectError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project.slug, build_citation_group_payload(
        project.slug,
        papers,
        locator_label=request.locator_label,
        locator_value=request.locator_value,
        prefix=request.prefix,
        suffix=request.suffix,
        suppress_author=request.suppress_author,
    )


def _word_error(exc: WordCitationError | CitationStyleError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.get("/bootstrap")
def read_word_addin_bootstrap() -> dict[str, Any]:
    project, _root = _active_literature_project()
    return {
        "project": {"slug": project.slug, "name": project.name},
        "styles": citation_style_options(),
    }


@router.get("/papers")
def search_word_addin_papers(
    query: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    _project, root = _active_literature_project()
    cleaned = query.strip().casefold()
    bounded_offset = max(int(offset), 0)
    bounded_limit = min(max(int(limit), 1), 100)
    results = []
    total = 0
    snapshot = literature_snapshot(root)
    tag_names = {
        str(tag.get("id") or ""): str(tag.get("name") or "")
        for tag in snapshot.get("tags", {}).get("tags", [])
        if tag.get("id") and tag.get("name")
    }
    raw_groups = snapshot.get("groups", {})
    group_rows = raw_groups.get("groups", []) if isinstance(raw_groups, dict) else raw_groups
    group_names = {
        str(group.get("id") or ""): str(group.get("name") or "")
        for group in group_rows
        if isinstance(group, dict) and group.get("id") and group.get("name")
    }
    for paper in snapshot.get("catalog", {}).get("papers", []):
        summary = _paper_summary(
            paper,
            tag_names=tag_names,
            group_names=group_names,
        )
        haystack = " ".join(
            [
                summary["title"],
                summary["authors"],
                summary["journal"],
                summary["doi"],
                " ".join(summary["tags"]),
                " ".join(summary["groups"]),
            ]
        ).casefold()
        if cleaned and cleaned not in haystack:
            continue
        if bounded_offset <= total < bounded_offset + bounded_limit:
            results.append(summary)
        total += 1
    return {
        "papers": results,
        "total": total,
        "offset": bounded_offset,
        "limit": bounded_limit,
    }


@router.get("/citations/inspect")
def inspect_word_addin_document() -> dict[str, Any]:
    _active_literature_project()
    try:
        return inspect_word_citations(None)
    except (WordCitationError, CitationStyleError) as exc:
        raise _word_error(exc) from exc


@router.post("/citations")
def insert_word_addin_citation(request: WordAddinCitationRequest) -> dict[str, Any]:
    _slug, payload = _citation_payload(request)
    try:
        return insert_word_citation_group(payload, None, request.style_id)
    except (WordCitationError, CitationStyleError) as exc:
        raise _word_error(exc) from exc


@router.post("/citations/update")
def update_word_addin_citation(
    request: WordAddinCitationUpdateRequest,
) -> dict[str, Any]:
    _slug, payload = _citation_payload(request)
    try:
        return update_word_citation_group(
            request.instance_id,
            payload,
            None,
            request.style_id,
        )
    except (WordCitationError, CitationStyleError) as exc:
        raise _word_error(exc) from exc


@router.post("/citations/remove")
def remove_word_addin_citation(request: WordAddinInstanceRequest) -> dict[str, Any]:
    _active_literature_project()
    try:
        return remove_word_citation_group(request.instance_id, None, request.style_id)
    except (WordCitationError, CitationStyleError) as exc:
        raise _word_error(exc) from exc


@router.post("/citations/refresh")
def refresh_word_addin_document(request: WordAddinStyleRequest) -> dict[str, Any]:
    _active_literature_project()
    try:
        return refresh_word_citations(None, request.style_id)
    except (WordCitationError, CitationStyleError) as exc:
        raise _word_error(exc) from exc


@router.post("/bibliography")
def create_word_addin_bibliography(request: WordAddinStyleRequest) -> dict[str, Any]:
    _active_literature_project()
    try:
        return create_word_bibliography(None, request.style_id)
    except (WordCitationError, CitationStyleError) as exc:
        raise _word_error(exc) from exc
