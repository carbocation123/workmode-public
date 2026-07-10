from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections.abc import AsyncIterator
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from . import files, storage, tutorial_project
from .chat_runs import ChatAlreadyRunningError, chat_runs
from .config import APP_VERSION, get_settings, update_env_file
from .llm import stream_openai_compatible
from .models import (
    ActiveProjectUpdate,
    ChatRequest,
    CompactRequest,
    FileWriteRequest,
    MemoryUpdate,
    ModelSettingsUpdate,
    ProjectCreate,
    ProjectUpdate,
    SessionCreate,
    SessionUpdate,
    TutorialProjectInstall,
)
from .prompt import build_llm_messages
from .session_compactor import CompactionError, compact_session, compaction_payload
from .turn_recorder import TurnRecorder


router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def _project_payload(project: storage.Project) -> dict[str, object]:
    payload: dict[str, object] = asdict(project)
    payload["is_tutorial"] = tutorial_project.is_tutorial_project(project)
    return payload


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, storage.NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, CompactionError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ChatAlreadyRunningError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, (storage.ValidationError, storage.ConflictError)):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="内部错误")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": "workmode-public", "version": APP_VERSION}


@router.get("/version")
def version() -> dict[str, str]:
    return {"app": "workmode-public", "version": APP_VERSION}


def _settings_payload() -> dict[str, object]:
    current = get_settings()
    return {
        "data_dir": str(current.data_dir),
        "env_file": str(current.env_file),
        "host": current.host,
        "port": current.port,
        "model_base_url": current.model_base_url,
        "model_name": current.model_name,
        "model_api_key_set": bool(current.model_api_key),
        "context_budget_tokens": current.context_budget_tokens,
        "request_timeout_seconds": current.request_timeout_seconds,
    }


@router.get("/settings")
def read_settings() -> dict[str, object]:
    return {"settings": _settings_payload()}


@router.put("/settings/model")
def update_model_settings(payload: ModelSettingsUpdate) -> dict[str, object]:
    updates: dict[str, str] = {}
    if payload.model_base_url is not None:
        updates["WORKMODE_MODEL_BASE_URL"] = payload.model_base_url.strip().rstrip("/")
    if payload.model_name is not None:
        updates["WORKMODE_MODEL_NAME"] = payload.model_name.strip()
    if payload.clear_api_key:
        updates["WORKMODE_MODEL_API_KEY"] = ""
    elif payload.model_api_key is not None and payload.model_api_key.strip():
        updates["WORKMODE_MODEL_API_KEY"] = payload.model_api_key.strip()
    if payload.context_budget_tokens is not None:
        updates["WORKMODE_CONTEXT_BUDGET_TOKENS"] = str(payload.context_budget_tokens)
    if payload.request_timeout_seconds is not None:
        updates["WORKMODE_REQUEST_TIMEOUT_SECONDS"] = str(payload.request_timeout_seconds)

    if "WORKMODE_MODEL_BASE_URL" in updates and not updates["WORKMODE_MODEL_BASE_URL"]:
        raise HTTPException(status_code=400, detail="模型 Base URL 不能为空")
    if "WORKMODE_MODEL_NAME" in updates and not updates["WORKMODE_MODEL_NAME"]:
        raise HTTPException(status_code=400, detail="模型名称不能为空")

    update_env_file(updates)
    return {"settings": _settings_payload()}


@router.get("/work/projects")
def list_projects() -> dict[str, object]:
    active = storage.get_active_project_slug()
    return {"projects": [_project_payload(item) for item in storage.list_projects()], "active_slug": active}


@router.post("/work/tutorial-project")
def install_tutorial(payload: TutorialProjectInstall) -> dict[str, object]:
    try:
        result = tutorial_project.install_tutorial_project(payload.parent_path)
        return {"project": _project_payload(result.project), "session": asdict(result.session)}
    except Exception as exc:
        raise _handle_error(exc)


@router.post("/work/projects")
def create_project(payload: ProjectCreate) -> dict[str, object]:
    try:
        project = storage.create_project(payload.name, payload.root_path, payload.description)
        session = storage.create_session(project.slug)
        return {"project": _project_payload(project), "session": asdict(session)}
    except Exception as exc:
        raise _handle_error(exc)


@router.patch("/work/projects/{slug}")
def update_project(slug: str, payload: ProjectUpdate) -> dict[str, object]:
    try:
        return {"project": _project_payload(storage.update_project(slug, name=payload.name, description=payload.description))}
    except Exception as exc:
        raise _handle_error(exc)


@router.delete("/work/projects/{slug}")
def delete_project(slug: str) -> dict[str, object]:
    try:
        for session in storage.list_sessions(slug, limit=200):
            if chat_runs.is_running(session.id):
                raise storage.ConflictError("项目中仍有正在运行的对话，请先停止后再删除")
        project = storage.archive_project(slug)
        return {
            "project": _project_payload(project),
            "active_slug": storage.get_active_project_slug(),
            "local_files_deleted": False,
        }
    except Exception as exc:
        raise _handle_error(exc)


@router.post("/work/projects/{slug}/reset-tutorial")
def reset_tutorial(slug: str) -> dict[str, object]:
    try:
        for session in storage.list_sessions(slug, limit=10_000):
            if chat_runs.is_running(session.id):
                raise storage.ConflictError("教程中仍有正在运行的对话，请先停止后再重置")
        result = tutorial_project.reset_tutorial_project(slug)
        return {
            "project": _project_payload(result.project),
            "session": asdict(result.session),
            "backup_path": str(result.backup_dir),
        }
    except Exception as exc:
        raise _handle_error(exc)


@router.get("/work/projects/active")
def active_project() -> dict[str, object]:
    slug = storage.get_active_project_slug()
    return {"slug": slug}


@router.put("/work/projects/active")
def set_active_project(payload: ActiveProjectUpdate) -> dict[str, object]:
    try:
        storage.set_active_project(payload.slug)
        return {"slug": payload.slug}
    except Exception as exc:
        raise _handle_error(exc)


@router.get("/work/projects/{slug}/sessions")
def list_sessions(slug: str, limit: int = Query(default=60, ge=1, le=200)) -> dict[str, object]:
    try:
        return {"sessions": [asdict(item) for item in storage.list_sessions(slug, limit=limit)]}
    except Exception as exc:
        raise _handle_error(exc)


@router.post("/work/projects/{slug}/sessions")
def create_session(slug: str, payload: SessionCreate) -> dict[str, object]:
    try:
        return {"session": asdict(storage.create_session(slug, payload.title))}
    except Exception as exc:
        raise _handle_error(exc)


@router.patch("/work/sessions/{session_id}")
def update_session(session_id: str, payload: SessionUpdate) -> dict[str, object]:
    try:
        return {"session": asdict(storage.update_session(session_id, title=payload.title))}
    except Exception as exc:
        raise _handle_error(exc)


@router.delete("/work/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, object]:
    try:
        if chat_runs.is_running(session_id):
            raise storage.ConflictError("该对话仍在运行，请先停止后再删除")
        return {"session": asdict(storage.archive_session(session_id))}
    except Exception as exc:
        raise _handle_error(exc)


@router.get("/work/sessions/{session_id}/messages")
def read_messages(session_id: str, limit: int = Query(default=60, ge=1, le=200)) -> dict[str, object]:
    try:
        return {"messages": storage.read_messages(session_id, limit=limit)}
    except Exception as exc:
        raise _handle_error(exc)


@router.get("/work/sessions/{session_id}/context")
def context_usage(session_id: str) -> dict[str, object]:
    try:
        session = storage.get_session(session_id)
        project = storage.get_project(session.project_slug)
        _, usage = build_llm_messages(project, session_id)
        return {"context": usage}
    except Exception as exc:
        raise _handle_error(exc)


@router.post("/work/sessions/{session_id}/compact")
async def compact_context(session_id: str, payload: CompactRequest) -> dict[str, object]:
    try:
        result = await compact_session(
            session_id,
            keep_recent=payload.keep_recent,
            extra_instruction=payload.extra_instruction,
        )
        session = storage.get_session(session_id)
        project = storage.get_project(session.project_slug)
        _, usage = build_llm_messages(project, session_id)
        return {"compaction": compaction_payload(result), "context": usage}
    except Exception as exc:
        raise _handle_error(exc)


@router.post("/work/sessions/{session_id}/chat/stream")
async def chat_stream(session_id: str, payload: ChatRequest) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        run = None
        recorder: TurnRecorder | None = None

        try:
            task = asyncio.current_task()
            run = chat_runs.register(
                session_id,
                task=task,
                loop=asyncio.get_running_loop(),
            )
            session = storage.get_session(session_id)
            project = storage.get_project(session.project_slug)
            user_message = storage.append_message(session_id, role="user", content=payload.content)
            recorder = TurnRecorder(session_id, get_settings().model_name)
            messages, usage = build_llm_messages(project, session_id)
            yield _sse({"type": "user_message", "message": user_message})
            yield _sse({"type": "context_usage", "context": usage})
            interrupted = False
            async for event in stream_openai_compatible(
                messages,
                project_slug=project.slug,
                cancel_event=run.cancel_event,
            ):
                if event["type"] == "text_delta":
                    recorder.append_text(str(event["content"]))
                elif event["type"] == "cancelled":
                    interrupted = True
                    break
                elif event["type"] == "tool_call_start":
                    tool_message = recorder.start_tool(event)
                    yield _sse({**event, "message": tool_message})
                    continue
                elif event["type"] == "tool_result":
                    tool_message = recorder.finish_tool(event)
                    yield _sse({**event, "message": tool_message})
                    continue
                yield _sse(event)
            interrupted = interrupted or run.cancelled()
            final_messages = recorder.finalize(interrupted=interrupted)
            for message in final_messages:
                if message.get("role") == "assistant":
                    yield _sse({"type": "assistant_message", "message": message})
            if interrupted:
                yield _sse({"type": "cancelled"})
            yield _sse({"type": "done"})
        except asyncio.CancelledError:
            if run is not None:
                run.cancel_event.set()
            if recorder is not None:
                try:
                    recorder.finalize(interrupted=True)
                except Exception:
                    logger.exception("failed to persist interrupted turn")
            raise
        except Exception as exc:
            if recorder is not None:
                try:
                    recorder.finalize(interrupted=True)
                except Exception:
                    logger.exception("failed to persist failed turn")
            yield _sse({"type": "error", "message": str(exc)})
        finally:
            if run is not None:
                chat_runs.unregister(session_id, run)

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/work/sessions/{session_id}/stop")
async def stop_chat(session_id: str) -> dict[str, object]:
    storage.get_session(session_id)
    return {"session_id": session_id, "stopping": chat_runs.cancel(session_id)}


def _sse(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/work/pick-directory")
def pick_directory() -> dict[str, str | None]:
    """Open a native directory picker and return an absolute path.

    This endpoint is intentionally local-desktop oriented. It is still protected
    by the app-level token middleware when WORKMODE_PUBLIC_TOKEN is configured.
    """
    try:
        import tkinter
        from tkinter import filedialog
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"tkinter 不可用：{exc}（可以手动输入路径）") from exc

    root = None
    try:
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        if sys.platform == "darwin":
            root.update()
        path = filedialog.askdirectory(title="选择项目文件夹")
        return {"path": path if path else None}
    except Exception as exc:
        logger.exception("pick-directory failed")
        raise HTTPException(status_code=503, detail=f"原生对话框失败（后端可能没 GUI 环境）：{exc}") from exc
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass


@router.get("/work/projects/{slug}/memory")
def read_memory(slug: str) -> dict[str, object]:
    try:
        return storage.read_memory(slug)
    except Exception as exc:
        raise _handle_error(exc)


@router.put("/work/projects/{slug}/memory")
def write_memory(slug: str, payload: MemoryUpdate) -> dict[str, object]:
    try:
        return {"project": storage.write_project_memory(slug, payload.content)}
    except Exception as exc:
        raise _handle_error(exc)


@router.get("/work/projects/{slug}/tree")
def tree(slug: str, max_entries: int = Query(default=1000, ge=1, le=5000)) -> dict[str, object]:
    try:
        return {"entries": files.list_tree(slug, max_entries=max_entries)}
    except Exception as exc:
        raise _handle_error(exc)


@router.get("/work/projects/{slug}/fs/content")
def read_file(slug: str, path: str) -> dict[str, object]:
    try:
        return files.read_text_file(slug, path)
    except Exception as exc:
        raise _handle_error(exc)


@router.put("/work/projects/{slug}/fs/content")
def write_file(slug: str, path: str, payload: FileWriteRequest) -> dict[str, object]:
    try:
        return files.write_markdown_file(slug, path, payload.content, payload.version)
    except Exception as exc:
        raise _handle_error(exc)


@router.get("/work/projects/{slug}/fs/media")
def media(slug: str, path: str):
    try:
        return files.media_response(slug, path)
    except Exception as exc:
        raise _handle_error(exc)
