from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from . import files, storage
from .config import managed_projects_dir
from .endnote_import import (
    find_endnote_libraries,
    import_endnote_library,
    inspect_endnote_library,
    scan_literature_duplicates,
)
from .literature_project import (
    LITERATURE_TOOL_SCHEMAS,
    LiteratureProjectError,
    execute_literature_tool,
    initialize_literature_project,
    is_literature_project,
    literature_paper,
    list_deleted_literature_papers,
    literature_import_event_content,
    literature_snapshot,
    register_staged_pdf,
    seed_literature_session,
    verify_literature_archive,
)
from .models import (
    LiteratureCrossRelationUpdate,
    EndNoteLibraryPath,
    LiteratureImportNotice,
    LiteratureNoteUpdate,
    LiteratureProjectCreate,
    LiteratureRecordUpdate,
)


router = APIRouter(prefix="/api/work")


def _project_root(slug: str) -> Path:
    project = storage.get_project(slug)
    root = Path(project.root_path).expanduser().resolve()
    if not is_literature_project(root):
        raise HTTPException(status_code=400, detail="当前项目不是 literature-library 项目")
    # Zero-copy compatibility migration: old registered projects stay where
    # they are while missing fixed directories/files are added in place.
    initialize_literature_project(root, name=project.name)
    return root


def _managed_storage_mode(root: Path) -> str:
    try:
        root.expanduser().resolve().relative_to(managed_projects_dir())
        return "managed"
    except ValueError:
        return "external"


def open_local_folder(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _si_folder(root: Path, paper_id: str) -> tuple[Path, str]:
    paper = literature_paper(root, paper_id)
    relative = str((paper.get("paths") or {}).get("si_folder") or "")
    if not relative:
        raise LiteratureProjectError("该文献没有 SI 文件夹")
    path = (root / relative).resolve()
    path.relative_to(root)
    path.mkdir(parents=True, exist_ok=True)
    return path, relative


def _allocate_managed_root(name: str) -> Path:
    base = managed_projects_dir()
    base.mkdir(parents=True, exist_ok=True)
    stem = storage.slugify(name)
    candidate = base / stem
    suffix = 2
    while candidate.exists():
        candidate = base / f"{stem}-{suffix}"
        suffix += 1
    candidate.mkdir()
    return candidate.resolve()


def _tool_payload(slug: str, name: str, args: dict[str, object]) -> dict[str, object]:
    result = execute_literature_tool(slug, name, args)
    try:
        payload = json.loads(result.content)
    except json.JSONDecodeError:
        payload = {"ok": result.ok, "message": result.content}
    if not result.ok:
        raise HTTPException(status_code=400, detail=str(payload.get("message") or result.content))
    return payload


@router.post("/literature-projects")
def create_literature_project(payload: LiteratureProjectCreate) -> dict[str, object]:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="文献项目名称不能为空")
    root = (
        Path(payload.root_path).expanduser().resolve()
        if payload.root_path
        else _allocate_managed_root(name)
    )
    if root.exists() and not root.is_dir():
        raise HTTPException(status_code=400, detail="文献项目路径不是文件夹")
    if root.exists() and any(root.iterdir()) and not (root / "literature-project.json").exists():
        raise HTTPException(status_code=400, detail="目标文件夹非空且不是已有文献项目")
    try:
        initialize_literature_project(root, name=name)
        project = storage.create_project(name, str(root))
        session = storage.create_session(project.slug)
        seed_literature_session(session.id)
        session = storage.get_session(session.id)
    except (storage.ValidationError, storage.ConflictError, LiteratureProjectError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "project": {
            **asdict(project),
            "project_type": "literature-library",
            "tool_profile": "literature",
            "storage_mode": _managed_storage_mode(root),
        },
        "session": asdict(session),
    }


@router.get("/projects/{slug}/literature/health")
def literature_health(slug: str) -> dict[str, object]:
    root = _project_root(slug)
    manifest = literature_snapshot(root)["manifest"]
    return {
        "ok": True,
        "project_slug": slug,
        "project_type": "literature-library",
        "schema_version": manifest.get("schema_version"),
        "tool_profile": "literature",
        "agent_tools": [item["function"]["name"] for item in LITERATURE_TOOL_SCHEMAS],
    }


@router.get("/projects/{slug}/literature/papers")
def list_papers(slug: str) -> list[dict[str, object]]:
    return literature_snapshot(_project_root(slug))["catalog"]["papers"]


@router.get("/projects/{slug}/literature/trash/papers")
def list_deleted_papers(slug: str) -> dict[str, object]:
    try:
        return {"papers": list_deleted_literature_papers(_project_root(slug))}
    except LiteratureProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/literature/trash/papers/{trash_id}/restore")
def restore_deleted_paper(slug: str, trash_id: str) -> dict[str, object]:
    result = _tool_payload(slug, "literature_restore", {"trash_id": trash_id})
    return {"paper": result["paper"], "result": result}


@router.get("/projects/{slug}/literature/tags")
def list_tags(slug: str) -> list[dict[str, object]]:
    return literature_snapshot(_project_root(slug))["tags"]["tags"]


@router.get("/projects/{slug}/literature/tag-registry")
def read_tag_registry(slug: str) -> dict[str, object]:
    return literature_snapshot(_project_root(slug))["tags"]


@router.get("/projects/{slug}/literature/groups")
def list_groups(slug: str) -> list[dict[str, object]]:
    return literature_snapshot(_project_root(slug))["groups"]["groups"]


@router.get("/projects/{slug}/literature/fields")
def list_literature_fields(slug: str) -> list[dict[str, object]]:
    return literature_snapshot(_project_root(slug))["fields"]


@router.get("/projects/{slug}/literature/endnote/libraries")
def search_endnote_libraries(slug: str) -> dict[str, object]:
    _project_root(slug)
    return {"libraries": find_endnote_libraries()}


@router.post("/projects/{slug}/literature/endnote/preview")
def preview_endnote_library(slug: str, payload: EndNoteLibraryPath) -> dict[str, object]:
    _project_root(slug)
    try:
        return inspect_endnote_library(Path(payload.path))
    except LiteratureProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/literature/endnote/import")
def import_endnote(slug: str, payload: EndNoteLibraryPath) -> dict[str, object]:
    try:
        return import_endnote_library(_project_root(slug), Path(payload.path))
    except LiteratureProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/literature/duplicates/scan")
def scan_duplicates(slug: str) -> dict[str, object]:
    try:
        return scan_literature_duplicates(_project_root(slug))
    except LiteratureProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{slug}/literature/notes")
def list_notes(slug: str) -> list[dict[str, object]]:
    return literature_snapshot(_project_root(slug))["notes"]


@router.get("/projects/{slug}/literature/papers/{paper_id}")
def read_paper(slug: str, paper_id: str) -> dict[str, object]:
    try:
        return literature_paper(_project_root(slug), paper_id)
    except LiteratureProjectError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{slug}/literature/papers/{paper_id}/facts")
def read_facts(slug: str, paper_id: str) -> PlainTextResponse:
    root = _project_root(slug)
    try:
        paper = literature_paper(root, paper_id)
        rel = str((paper.get("paths") or {}).get("fact_report") or "")
        if not rel:
            raise LiteratureProjectError("客观事实报告尚未生成")
        path = files.resolve_project_path(slug, rel)
        if not path.exists() or not path.is_file():
            raise LiteratureProjectError("客观事实报告路径不存在")
        return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8")
    except LiteratureProjectError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{slug}/literature/papers/{paper_id}/pdf")
def read_pdf(slug: str, paper_id: str):
    root = _project_root(slug)
    try:
        paper = literature_paper(root, paper_id)
        rel = str((paper.get("paths") or {}).get("pdf") or "")
        if not rel:
            raise LiteratureProjectError("原始 PDF 路径不存在")
        return files.media_response(slug, rel)
    except LiteratureProjectError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{slug}/literature/papers/{paper_id}/si-folder")
def read_si_folder(slug: str, paper_id: str) -> dict[str, object]:
    root = _project_root(slug)
    try:
        path, relative = _si_folder(root, paper_id)
        return {"path": str(path), "relative_path": relative}
    except (LiteratureProjectError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{slug}/literature/papers/{paper_id}/si-folder/open")
def open_si_folder(slug: str, paper_id: str) -> dict[str, object]:
    root = _project_root(slug)
    try:
        path, _relative = _si_folder(root, paper_id)
        open_local_folder(path)
        return {"opened": True, "path": str(path)}
    except (LiteratureProjectError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"系统无法打开 SI 文件夹：{exc}") from exc


@router.post("/projects/{slug}/literature/papers/import")
async def import_pdf(
    slug: str,
    request: Request,
    filename: str = Query(min_length=1, max_length=500),
) -> dict[str, object]:
    root = _project_root(slug)
    incoming_dir = root / "papers/unprocessed/pdf"
    incoming_dir.mkdir(parents=True, exist_ok=True)
    staged = incoming_dir / f".incoming-{uuid.uuid4().hex}.pdf"
    try:
        with staged.open("wb") as handle:
            async for chunk in request.stream():
                handle.write(chunk)
        result = register_staged_pdf(root, staged, original_filename=filename)
        return {**result, "task": None}
    except LiteratureProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        staged.unlink(missing_ok=True)


@router.post("/projects/{slug}/literature/sessions/{session_id}/imports")
def record_confirmed_imports(slug: str, session_id: str, payload: LiteratureImportNotice) -> dict[str, object]:
    root = _project_root(slug)
    try:
        session = storage.get_session(session_id)
        if session.project_slug != slug:
            raise LiteratureProjectError("Session does not belong to the current literature project")
        paper_ids = list(dict.fromkeys(payload.paper_ids))
        papers = [literature_paper(root, paper_id) for paper_id in paper_ids]
        message = storage.append_message(
            session_id,
            role="system",
            content=literature_import_event_content(root, paper_ids),
            meta={
                "event": "literature_import_confirmed",
                "paper_ids": paper_ids,
            },
        )
        return {"message": message, "papers": papers}
    except (storage.ValidationError, LiteratureProjectError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/projects/{slug}/literature/papers/{paper_id}")
def update_record(slug: str, paper_id: str, payload: LiteratureRecordUpdate) -> dict[str, object]:
    args = {"paper_id": paper_id, **payload.model_dump(exclude_none=True)}
    _tool_payload(slug, "literature_update_record", args)
    return literature_paper(_project_root(slug), paper_id)


@router.delete("/projects/{slug}/literature/papers/{paper_id}")
def delete_paper(slug: str, paper_id: str) -> dict[str, object]:
    result = _tool_payload(slug, "literature_delete", {"paper_id": paper_id})
    return {"result": result}


@router.put("/projects/{slug}/literature/papers/{paper_id}/cross-literature")
def update_cross_relation(slug: str, paper_id: str, payload: LiteratureCrossRelationUpdate) -> dict[str, object]:
    _tool_payload(slug, "literature_update_cross_relation", {"paper_id": paper_id, "markdown": payload.markdown})
    return literature_paper(_project_root(slug), paper_id)


@router.post("/projects/{slug}/literature/papers/{paper_id}/archive")
def archive_paper(slug: str, paper_id: str) -> dict[str, object]:
    result = _tool_payload(slug, "literature_archive", {"paper_id": paper_id})
    return {"paper": literature_paper(_project_root(slug), paper_id), "result": result}


@router.get("/projects/{slug}/literature/papers/{paper_id}/verify")
def verify_archive(slug: str, paper_id: str) -> dict[str, object]:
    try:
        return verify_literature_archive(_project_root(slug), paper_id)
    except LiteratureProjectError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/projects/{slug}/literature/notes/{filename}")
def save_note(slug: str, filename: str, payload: LiteratureNoteUpdate) -> dict[str, object]:
    result = _tool_payload(slug, "literature_note_upsert", {"filename": filename, "markdown": payload.markdown})
    note = next(
        (item for item in literature_snapshot(_project_root(slug))["notes"] if item["filename"] == filename),
        None,
    )
    return {"note": note, "result": result}


@router.delete("/projects/{slug}/literature/notes/{filename}")
def delete_note(slug: str, filename: str) -> dict[str, object]:
    result = _tool_payload(slug, "literature_note_delete", {"filename": filename})
    return {"result": result}
