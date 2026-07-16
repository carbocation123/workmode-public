from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..config import get_settings
from .dashscope_fun_asr import DashScopeFunAsrTranscriber
from .workspace import (
    SUPPORTED_EXTENSIONS,
    TranscriptionRunner,
    TranscriptionWorkspace,
    WorkspaceConflict,
    WorkspaceError,
    WorkspaceNotFound,
)


router = APIRouter(prefix="/api/transcription", tags=["transcription"])


class JobUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


_workspace: TranscriptionWorkspace | None = None
_runner: TranscriptionRunner | None = None


def get_transcription_workspace() -> TranscriptionWorkspace:
    global _workspace, _runner
    root = get_settings().transcription_workspace_dir.expanduser().resolve()
    if _workspace is None or _workspace.root != root:
        transcriber = DashScopeFunAsrTranscriber(
            api_key_provider=lambda: get_settings().dashscope_api_key or ""
        )
        _workspace = TranscriptionWorkspace(root, transcriber=transcriber)
        _workspace.initialize()
        _runner = None
    return _workspace


def get_transcription_runner() -> TranscriptionRunner:
    global _runner
    workspace = get_transcription_workspace()
    if _runner is None or _runner.workspace is not workspace:
        _runner = TranscriptionRunner(workspace)
    return _runner


def recover_transcription_jobs() -> None:
    get_transcription_runner().recover()


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, WorkspaceNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, WorkspaceConflict):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, WorkspaceError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="会议转写内部错误")


def _public_job(workspace: TranscriptionWorkspace, job: dict[str, Any]) -> dict[str, Any]:
    output_directory = (workspace.root / str(job["output_path"])).resolve()
    return {
        **job,
        "workspace_path": str(workspace.root),
        "output_directory": str(output_directory),
        "reveal_path": str(output_directory / "meta.json"),
    }


@router.get("/workspace")
def workspace_info() -> dict[str, object]:
    workspace = get_transcription_workspace()
    return {
        "path": str(workspace.root),
        "dashscope_api_key_set": bool(get_settings().dashscope_api_key),
        "model": "fun-asr",
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
    }


@router.get("/jobs")
def list_jobs() -> dict[str, object]:
    workspace = get_transcription_workspace()
    return {"jobs": [_public_job(workspace, job) for job in workspace.list_jobs()]}


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    workspace = get_transcription_workspace()
    try:
        return {"job": _public_job(workspace, workspace.get_job(job_id))}
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/jobs")
async def upload_job(
    request: Request,
    filename: str = Query(min_length=1, max_length=500),
    title: str | None = Query(default=None, max_length=200),
) -> dict[str, object]:
    if not get_settings().dashscope_api_key:
        raise HTTPException(status_code=503, detail="请先在设置中配置 DashScope API Key")
    workspace = get_transcription_workspace()
    workspace.initialize()
    extension = Path(filename).suffix.lower()
    staged = workspace.input_dir / f".incoming-{uuid.uuid4().hex}{extension}"
    try:
        with staged.open("wb") as handle:
            async for chunk in request.stream():
                handle.write(chunk)
        job = workspace.create_job_from_staged(filename=filename, staged_path=staged, title=title)
        get_transcription_runner().submit(str(job["id"]))
        return {"job": _public_job(workspace, job)}
    except Exception as exc:
        raise _handle_error(exc) from exc
    finally:
        staged.unlink(missing_ok=True)


@router.patch("/jobs/{job_id}")
def update_job(job_id: str, payload: JobUpdate) -> dict[str, object]:
    workspace = get_transcription_workspace()
    try:
        return {"job": _public_job(workspace, workspace.rename_job(job_id, payload.title))}
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str) -> dict[str, object]:
    if not get_settings().dashscope_api_key:
        raise HTTPException(status_code=503, detail="请先在设置中配置 DashScope API Key")
    workspace = get_transcription_workspace()
    try:
        job = workspace.retry_job(job_id, start=False)
        get_transcription_runner().submit(job_id)
        return {"job": _public_job(workspace, job)}
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/jobs/{job_id}/transcript")
def read_transcript(job_id: str) -> dict[str, object]:
    workspace = get_transcription_workspace()
    try:
        job = workspace.get_job(job_id)
        output_dir = workspace.root / str(job["output_path"])
        transcript_path = output_dir / "transcript.json"
        if not transcript_path.is_file():
            raise WorkspaceNotFound("转写结果尚未生成")
        return {
            "job": _public_job(workspace, job),
            "segments": json.loads(transcript_path.read_text(encoding="utf-8")),
            "markdown": (output_dir / "transcript.md").read_text(encoding="utf-8"),
            "text": (output_dir / "transcript.txt").read_text(encoding="utf-8"),
        }
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/jobs/{job_id}/files/{kind}")
def download_transcript(job_id: str, kind: str):
    workspace = get_transcription_workspace()
    filenames = {"text": "transcript.txt", "markdown": "transcript.md", "json": "transcript.json"}
    if kind not in filenames:
        raise HTTPException(status_code=404, detail="不支持的转写文件类型")
    try:
        job = workspace.get_job(job_id)
        path = workspace.root / str(job["output_path"]) / filenames[kind]
        if not path.is_file():
            raise WorkspaceNotFound("转写结果尚未生成")
        return FileResponse(path, filename=f"{job['title']}.{path.suffix.lstrip('.')}")
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str) -> dict[str, object]:
    workspace = get_transcription_workspace()
    try:
        return {"trash": workspace.delete_job(job_id)}
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/trash")
def list_trash() -> dict[str, object]:
    return {"items": get_transcription_workspace().list_deleted()}


@router.post("/trash/{trash_id}/restore")
def restore_job(trash_id: str) -> dict[str, object]:
    workspace = get_transcription_workspace()
    try:
        return {"job": _public_job(workspace, workspace.restore_job(trash_id))}
    except Exception as exc:
        raise _handle_error(exc) from exc
