from __future__ import annotations

import hashlib
import asyncio
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from .literature_demo_pipeline import run_literature_pipeline
from .literature_demo_chat import (
    LITERATURE_AGENT_CONTRACT_VERSION,
    LITERATURE_TOOLS,
    LiteratureChatError,
    run_literature_chat,
)
from .literature_demo_archive import LiteratureArchiveError, archive_paper, verify_paper_archive
from .literature_demo_compactor import LiteratureCompactionError, compact_literature_session
from .literature_demo_store import MAX_PDF_BYTES, get_literature_demo_store


router = APIRouter(prefix="/api/literature-demo", tags=["literature-demo"])


class SessionCreate(BaseModel):
    name: str = Field(default="新对话", max_length=120)


class MessageCreate(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1, max_length=500_000)
    paper_ids: list[str] = Field(default_factory=list, max_length=50)
    note_ids: list[str] = Field(default_factory=list, max_length=50)


class SessionContextUpdate(BaseModel):
    paper_ids: list[str] = Field(default_factory=list, max_length=50)
    note_ids: list[str] = Field(default_factory=list, max_length=50)


class ConfirmedMarkdownWrite(BaseModel):
    markdown: str = Field(max_length=2_000_000)
    confirmed: bool = False


class NoteWrite(ConfirmedMarkdownWrite):
    source_paper_ids: list[str] = Field(default_factory=list, max_length=50)


class TagSuggestion(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="uncategorized", max_length=40)


class PaperReviewWrite(BaseModel):
    tags: list[TagSuggestion] = Field(min_length=1, max_length=50)
    focus: str = Field(min_length=1, max_length=20_000)
    summary: str = Field(min_length=1, max_length=100_000)
    confirmed: bool = False


class MemoryCandidateResolution(BaseModel):
    accept: bool
    confirmed: bool = False


class ConfirmedMetadata(BaseModel):
    title: str = Field(min_length=1, max_length=1000)
    authors: str = Field(default="", max_length=4000)
    first_author_surname: str = Field(min_length=1, max_length=120)
    year: int = Field(ge=1800, le=2100)
    journal: str = Field(default="", max_length=500)
    journal_abbreviation: str = Field(min_length=1, max_length=80)
    doi: str | None = Field(default=None, max_length=300)
    paper_type: str = Field(default="unknown", pattern="^(research|review|unknown)$")
    confirmed: bool = False


@router.get("/health")
def literature_health() -> dict[str, Any]:
    store = get_literature_demo_store()
    return {
        "ok": True,
        "data_root": str(store.root),
        "mode": "isolated-test-library",
        "agent_contract_version": LITERATURE_AGENT_CONTRACT_VERSION,
        "agent_tools": [item["function"]["name"] for item in LITERATURE_TOOLS],
    }


@router.get("/papers")
def list_papers() -> list[dict[str, Any]]:
    return get_literature_demo_store().list_papers()


@router.get("/tags")
def list_tags() -> list[dict[str, Any]]:
    return get_literature_demo_store().list_tags()


@router.get("/papers/{paper_id}")
def get_paper(paper_id: str) -> dict[str, Any]:
    try:
        return get_literature_demo_store().get_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="文献不存在") from exc


@router.post("/papers/import", status_code=201)
async def import_paper(
    request: Request,
    background_tasks: BackgroundTasks,
    filename: str = Query(min_length=1, max_length=240),
    process: bool = Query(default=True),
) -> dict[str, Any]:
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="只接受 PDF 文件")
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_PDF_BYTES:
                raise HTTPException(status_code=413, detail="PDF 不能超过 200 MB")
        except ValueError:
            raise HTTPException(status_code=400, detail="Content-Length 无效") from None

    store = get_literature_demo_store()
    staging = store.root / f".upload-{uuid.uuid4().hex}.tmp"
    digest = hashlib.sha256()
    total = 0
    first = b""
    try:
        with staging.open("wb") as target:
            async for chunk in request.stream():
                if not chunk:
                    continue
                if not first:
                    first = chunk[:8]
                total += len(chunk)
                if total > MAX_PDF_BYTES:
                    raise HTTPException(status_code=413, detail="PDF 不能超过 200 MB")
                digest.update(chunk)
                target.write(chunk)
        try:
            paper, duplicate = store.import_pdf_path(
                filename,
                staging,
                known_hash=digest.hexdigest(),
                known_size=total,
                known_magic=first,
            )
        except TypeError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
    finally:
        staging.unlink(missing_ok=True)

    task = None
    if process and not duplicate:
        task = store.create_task(paper["id"])
        background_tasks.add_task(run_literature_pipeline, store, task["id"])
    return {"paper": paper, "duplicate": duplicate, "task": task}


@router.post("/papers/{paper_id}/process", status_code=202)
def process_paper(paper_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    store = get_literature_demo_store()
    try:
        task = store.create_task(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="文献不存在") from exc
    if task["status"] == "queued":
        background_tasks.add_task(run_literature_pipeline, store, task["id"])
    return task


@router.patch("/papers/{paper_id}/metadata")
def confirm_paper_metadata(paper_id: str, payload: ConfirmedMetadata) -> dict[str, Any]:
    if not payload.confirmed:
        raise HTTPException(status_code=409, detail="元数据写入需要用户明确确认")
    values = payload.model_dump(exclude={"confirmed"})
    values["metadata_source"] = "manual_review"
    try:
        return get_literature_demo_store().apply_metadata(paper_id, values)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="文献不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/papers/{paper_id}/review")
def confirm_paper_review(paper_id: str, payload: PaperReviewWrite) -> dict[str, Any]:
    try:
        return get_literature_demo_store().confirm_paper_review(
            paper_id,
            tags=[item.model_dump() for item in payload.tags],
            focus=payload.focus,
            summary=payload.summary,
            confirmed=payload.confirmed,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="文献不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/papers/{paper_id}/cross-literature")
def write_cross_literature(paper_id: str, payload: ConfirmedMarkdownWrite) -> dict[str, Any]:
    try:
        return get_literature_demo_store().update_cross_literature(
            paper_id,
            payload.markdown,
            confirmed=payload.confirmed,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="文献或客观事实报告不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/papers/{paper_id}/verify")
def verify_archive(paper_id: str) -> dict[str, Any]:
    try:
        return verify_paper_archive(get_literature_demo_store(), paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="文献不存在") from exc


@router.post("/papers/{paper_id}/archive")
def finish_archive(paper_id: str) -> dict[str, Any]:
    try:
        return archive_paper(get_literature_demo_store(), paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="文献不存在") from exc
    except LiteratureArchiveError as exc:
        raise HTTPException(status_code=409, detail={"message": "归档校验未通过", "issues": exc.issues}) from exc


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, Any]:
    try:
        return get_literature_demo_store().get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str) -> dict[str, Any]:
    try:
        return get_literature_demo_store().request_cancel(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc


@router.get("/papers/{paper_id}/pdf")
def paper_pdf(paper_id: str):
    store = get_literature_demo_store()
    try:
        paper = store.get_paper(paper_id)
        path = store.pdf_path(paper_id)
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="PDF 不存在") from exc
    filename = str(paper.get("archive_filename") or paper.get("original_filename") or "paper.pdf")
    return FileResponse(path, media_type="application/pdf", filename=filename, content_disposition_type="inline")


@router.get("/papers/{paper_id}/facts", response_class=PlainTextResponse)
def paper_facts(paper_id: str) -> str:
    try:
        path = get_literature_demo_store().report_path(paper_id)
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="客观事实报告尚未生成") from exc
    return path.read_text(encoding="utf-8")


@router.get("/sessions")
def list_sessions() -> list[dict[str, Any]]:
    return get_literature_demo_store().list_sessions()


@router.post("/sessions", status_code=201)
def create_session(payload: SessionCreate) -> dict[str, Any]:
    return get_literature_demo_store().create_session(payload.name)


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    try:
        return get_literature_demo_store().get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="对话不存在") from exc


@router.patch("/sessions/{session_id}/context")
def update_session_context(session_id: str, payload: SessionContextUpdate) -> dict[str, Any]:
    try:
        return get_literature_demo_store().update_session_context(
            session_id,
            paper_ids=payload.paper_ids,
            note_ids=payload.note_ids,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="对话不存在") from exc


@router.post("/sessions/{session_id}/messages", status_code=201)
def append_message(session_id: str, payload: MessageCreate) -> dict[str, Any]:
    try:
        return get_literature_demo_store().append_message(session_id, payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="对话不存在") from exc


@router.post("/sessions/{session_id}/chat")
async def chat(session_id: str, payload: MessageCreate) -> dict[str, Any]:
    if payload.role != "user":
        raise HTTPException(status_code=422, detail="聊天入口只接受 user 消息")
    store = get_literature_demo_store()
    try:
        return await asyncio.to_thread(
            run_literature_chat,
            store,
            session_id,
            payload.content,
            payload.paper_ids,
            payload.note_ids,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="对话或选中文献不存在") from exc
    except LiteratureChatError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/compact")
async def compact_session(session_id: str) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            compact_literature_session,
            get_literature_demo_store(),
            session_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="对话不存在") from exc
    except LiteratureCompactionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/memory-candidate")
def resolve_memory_candidate(session_id: str, payload: MemoryCandidateResolution) -> dict[str, Any]:
    try:
        return get_literature_demo_store().resolve_memory_candidate(
            session_id,
            accept=payload.accept,
            confirmed=payload.confirmed,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="对话不存在") from exc


@router.get("/notes")
def list_notes() -> list[dict[str, Any]]:
    return get_literature_demo_store().list_notes()


@router.put("/notes/{filename}")
def write_note(filename: str, payload: NoteWrite) -> dict[str, Any]:
    try:
        return get_literature_demo_store().upsert_note(
            filename,
            payload.markdown,
            confirmed=payload.confirmed,
            source_paper_ids=payload.source_paper_ids,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/memory", response_class=PlainTextResponse)
def read_memory() -> str:
    return get_literature_demo_store().read_memory()


@router.put("/memory", response_class=PlainTextResponse)
def write_memory(payload: ConfirmedMarkdownWrite) -> str:
    try:
        return get_literature_demo_store().write_memory(payload.markdown, confirmed=payload.confirmed)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
