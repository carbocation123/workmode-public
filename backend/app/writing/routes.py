from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..config import get_settings
from ..transcription.ai_processing import OpenAICompatibleCompletion, TranscriptionAiError
from .history import (
    ArticleHistoryConflict,
    ArticleHistoryError,
    ArticleHistoryNotFound,
    ArticleHistoryStore,
)
from .processing import ArticleProcessor, WritingProcessingError


router = APIRouter(prefix="/api/writing", tags=["writing"])


class ProcessRequest(BaseModel):
    mode: Literal["polish", "audit"]
    input_text: str = Field(min_length=1, max_length=200_000)

    @field_validator("input_text")
    @classmethod
    def reject_blank_input(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("请先输入需要处理的文字")
        return value


_store: ArticleHistoryStore | None = None


def _history_summary(record: dict[str, object]) -> dict[str, object]:
    compact = " ".join(str(record.get("input_text") or "").split())
    preview = compact[:80] + ("…" if len(compact) > 80 else "")
    return {
        "version": record.get("version", 1),
        "id": record.get("id"),
        "created_at": record.get("created_at"),
        "mode": record.get("mode"),
        "input_preview": preview,
        "model": record.get("model"),
        "input_chars": record.get("input_chars", 0),
        "output_chars": record.get("output_chars", 0),
    }


def _deleted_summary(item: dict[str, object]) -> dict[str, object]:
    record = item.get("record")
    return {
        "version": item.get("version", 1),
        "trash_id": item.get("trash_id"),
        "deleted_at": item.get("deleted_at"),
        "record": _history_summary(record) if isinstance(record, dict) else {},
    }


def get_article_history_store() -> ArticleHistoryStore:
    global _store
    root = (get_settings().data_dir / "article-processing").resolve()
    if _store is None or _store.root != root:
        _store = ArticleHistoryStore(root)
        _store.initialize()
    return _store


def get_article_processor() -> ArticleProcessor:
    current = get_settings()
    if not current.model_base_url or not current.model_api_key:
        raise WritingProcessingError("请先在设置中配置 AI 模型地址和 API Key")
    completion = OpenAICompatibleCompletion(
        base_url=current.model_base_url,
        api_key=current.model_api_key,
        model_name=current.model_name,
        timeout_seconds=current.request_timeout_seconds,
    )
    return ArticleProcessor(completion=completion, model_name=current.model_name)


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ArticleHistoryNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ArticleHistoryConflict):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, (WritingProcessingError, TranscriptionAiError)):
        return HTTPException(status_code=502, detail=str(exc))
    if isinstance(exc, ArticleHistoryError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="文章处理内部错误")


@router.get("/status")
def writing_status() -> dict[str, object]:
    current = get_settings()
    return {
        "model_api_configured": bool(current.model_base_url and current.model_api_key),
        "model_name": current.model_name,
        "history_path": str(get_article_history_store().root),
    }


@router.post("/process")
def process_text(payload: ProcessRequest) -> dict[str, object]:
    current = get_settings()
    if not current.model_base_url or not current.model_api_key:
        raise HTTPException(status_code=503, detail="请先在设置中配置 AI 模型地址和 API Key")
    try:
        processor = get_article_processor()
        output = processor.process(mode=payload.mode, text=payload.input_text)
        record = get_article_history_store().create(
            mode=payload.mode,
            input_text=payload.input_text,
            output_text=output,
            model=processor.model_name,
        )
        return {"record": record}
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/history")
def list_history() -> dict[str, object]:
    try:
        return {"items": [_history_summary(item) for item in get_article_history_store().list()]}
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/history/{record_id}")
def get_history(record_id: str) -> dict[str, object]:
    try:
        return {"record": get_article_history_store().get(record_id)}
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.delete("/history/{record_id}")
def delete_history(record_id: str) -> dict[str, object]:
    try:
        return {"trash": get_article_history_store().delete(record_id)}
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/trash")
def list_trash() -> dict[str, object]:
    try:
        return {"items": [_deleted_summary(item) for item in get_article_history_store().list_deleted()]}
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/trash/{trash_id}/restore")
def restore_history(trash_id: str) -> dict[str, object]:
    try:
        return {"record": get_article_history_store().restore(trash_id)}
    except Exception as exc:
        raise _handle_error(exc) from exc
