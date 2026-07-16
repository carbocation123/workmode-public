"""Fixed-folder storage and single-worker execution for meeting transcription."""
from __future__ import annotations

import json
import logging
import queue
import re
import shutil
import threading
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Protocol

from .dashscope_fun_asr import Segment, TranscriptionResult


logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".m4a", ".mp3", ".wav", ".ogg", ".flac", ".aac", ".webm", ".mp4"}
_JOB_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{4}$")
_TRASH_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9]{8}-[0-9]{6}-[0-9a-f]{4}$")
_INVALID_WINDOWS_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class WorkspaceError(Exception):
    pass


class WorkspaceNotFound(WorkspaceError):
    pass


class WorkspaceConflict(WorkspaceError):
    pass


class FileTranscriber(Protocol):
    model: str

    def transcribe(
        self,
        audio_path: Path,
        *,
        remote_task_id: str | None = None,
        on_remote_task_id=None,
    ) -> TranscriptionResult: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_title(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise WorkspaceError("标题不能为空")
    if len(cleaned) > 200:
        raise WorkspaceError("标题不能超过 200 个字符")
    return cleaned


def _safe_original_name(filename: str) -> str:
    name = Path(filename).name.strip()
    if not name or name in {".", ".."}:
        raise WorkspaceError("音频文件名无效")
    if len(name) > 500:
        raise WorkspaceError("音频文件名过长")
    return name


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _atomic_json(path: Path, payload: Any) -> None:
    _atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _timestamp(milliseconds: int) -> str:
    total_seconds = max(0, milliseconds) // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def _speaker_names(segments: list[Segment]) -> dict[int | str, str]:
    names: dict[int | str, str] = {}
    for segment in segments:
        if segment.speaker_id not in names:
            names[segment.speaker_id] = f"Speaker {len(names) + 1}"
    return names


def _turns(segments: list[Segment]) -> list[dict[str, Any]]:
    names = _speaker_names(segments)
    turns: list[dict[str, Any]] = []
    for segment in segments:
        speaker = names[segment.speaker_id]
        if turns and turns[-1]["speaker"] == speaker:
            turns[-1]["end_ms"] = max(turns[-1]["end_ms"], segment.end_ms)
            turns[-1]["text"] += segment.text
            turns[-1]["is_overlap"] = turns[-1]["is_overlap"] or segment.is_overlap
        else:
            turns.append(
                {
                    "speaker": speaker,
                    "start_ms": segment.start_ms,
                    "end_ms": segment.end_ms,
                    "text": segment.text,
                    "is_overlap": segment.is_overlap,
                }
            )
    return turns


def _render_plain(segments: list[Segment]) -> str:
    return "\n\n".join(f"{turn['speaker']}：{turn['text']}" for turn in _turns(segments)) + (
        "\n" if segments else ""
    )


def _render_markdown(segments: list[Segment], title: str) -> str:
    lines = [f"# {title}", "", "> 由 Workmode Public 使用 Fun-ASR 转写。Speaker 编号仅在本次录音内有效。", ""]
    for turn in _turns(segments):
        overlap = " ⚠️ 重叠发言" if turn["is_overlap"] else ""
        lines.extend(
            [
                f"**{turn['speaker']}** `{_timestamp(turn['start_ms'])}–{_timestamp(turn['end_ms'])}`{overlap}",
                "",
                str(turn["text"]),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _transcript_payload(segments: list[Segment]) -> list[dict[str, Any]]:
    names = _speaker_names(segments)
    payload: list[dict[str, Any]] = []
    for segment in segments:
        item = asdict(segment)
        item["raw_speaker_id"] = item.pop("speaker_id")
        item["speaker"] = names[segment.speaker_id]
        payload.append(item)
    return payload


class TranscriptionWorkspace:
    """Owns only ``tools/``, ``input/`` and ``output/`` below one root.

    Listing deliberately scans only ``output/<job-id>/meta.json``. Files added
    by the generic Workmode project view are outside this allowlist and cannot
    become transcription state.
    """

    def __init__(self, root: Path, *, transcriber: FileTranscriber | None):
        self.root = root.expanduser().resolve()
        self.transcriber = transcriber
        self._lock = threading.RLock()

    @property
    def tools_dir(self) -> Path:
        return self.root / "tools"

    @property
    def input_dir(self) -> Path:
        return self.root / "input"

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def trash_dir(self) -> Path:
        return self.output_dir / ".trash"

    def initialize(self) -> None:
        for path in (self.tools_dir, self.input_dir, self.output_dir, self.trash_dir):
            path.mkdir(parents=True, exist_ok=True)
        readme = self.tools_dir / "README.md"
        if not readme.exists():
            _atomic_text(
                readme,
                "# 会议录音转文字\n\n"
                "本目录由 Workmode Public 管理。转写模块只读取同级 `input/` 与 `output/`；"
                "根目录中的其他文件由通用工作台自由使用，不参与转写扫描。\n",
            )

    def _job_id(self) -> str:
        return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"

    def _validate_job_id(self, job_id: str) -> str:
        if not _JOB_ID.fullmatch(job_id):
            raise WorkspaceNotFound(f"转写任务不存在：{job_id}")
        return job_id

    def _meta_path(self, job_id: str) -> Path:
        return self.output_dir / self._validate_job_id(job_id) / "meta.json"

    def _load_meta_path(self, path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return self._validate_job_payload(payload, expected_job_id=path.parent.name, source=path)

    def _validate_job_payload(
        self,
        payload: Any,
        *,
        expected_job_id: str,
        source: Path,
    ) -> dict[str, Any]:
        required = {
            "id",
            "title",
            "original_name",
            "status",
            "model",
            "input_path",
            "output_path",
            "created_at",
            "updated_at",
        }
        if not isinstance(payload, dict) or not required.issubset(payload):
            raise WorkspaceError(f"转写任务元数据损坏：{source}")
        job_id = str(payload["id"])
        if job_id != expected_job_id or not _JOB_ID.fullmatch(job_id):
            raise WorkspaceError(f"转写任务目录与 ID 不一致：{source}")
        input_path = str(payload["input_path"])
        extension = Path(input_path).suffix.lower()
        expected_input = f"input/{job_id}/recording{extension}"
        expected_output = f"output/{job_id}"
        if extension not in SUPPORTED_EXTENSIONS or input_path != expected_input:
            raise WorkspaceError(f"转写任务输入路径越出固定目录：{source}")
        if str(payload["output_path"]) != expected_output:
            raise WorkspaceError(f"转写任务输出路径越出固定目录：{source}")
        return payload

    def get_job(self, job_id: str) -> dict[str, Any]:
        self.initialize()
        path = self._meta_path(job_id)
        if not path.exists():
            raise WorkspaceNotFound(f"转写任务不存在：{job_id}")
        with self._lock:
            try:
                return self._load_meta_path(path)
            except (OSError, ValueError, TypeError, WorkspaceError) as exc:
                raise WorkspaceError(f"转写任务元数据无法读取：{job_id}") from exc

    def _save_job(self, job: dict[str, Any]) -> dict[str, Any]:
        _atomic_json(self._meta_path(str(job["id"])), job)
        return job

    def list_jobs(self, *, limit: int = 500) -> list[dict[str, Any]]:
        self.initialize()
        jobs: list[dict[str, Any]] = []
        with self._lock:
            for directory in self.output_dir.iterdir():
                if not directory.is_dir() or directory.name.startswith(".") or not _JOB_ID.fullmatch(directory.name):
                    continue
                meta_path = directory / "meta.json"
                if not meta_path.is_file():
                    continue
                try:
                    jobs.append(self._load_meta_path(meta_path))
                except (OSError, ValueError, TypeError, WorkspaceError):
                    logger.warning("ignored invalid transcription metadata: %s", meta_path)
        jobs.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return jobs[: max(0, min(limit, 2000))]

    def create_job(
        self,
        *,
        filename: str,
        source: BinaryIO,
        title: str | None = None,
        start: bool = False,
    ) -> dict[str, Any]:
        self.initialize()
        original_name = _safe_original_name(filename)
        extension = Path(original_name).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise WorkspaceError(f"不支持的音频格式：{extension or '<无扩展名>'}")
        job_id = self._job_id()
        input_job_dir = self.input_dir / job_id
        output_job_dir = self.output_dir / job_id
        input_job_dir.mkdir(parents=False)
        output_job_dir.mkdir(parents=False)
        recording = input_job_dir / f"recording{extension}"
        temporary = input_job_dir / f".recording{extension}.tmp"
        try:
            with temporary.open("wb") as handle:
                shutil.copyfileobj(source, handle, length=1024 * 1024)
            if not temporary.stat().st_size:
                raise WorkspaceError("音频文件为空")
            temporary.replace(recording)
            timestamp = _now()
            display_title = _safe_title(title or Path(original_name).stem)
            job = {
                "id": job_id,
                "title": display_title,
                "original_name": original_name,
                "status": "queued",
                "model": getattr(self.transcriber, "model", "fun-asr"),
                "input_path": recording.relative_to(self.root).as_posix(),
                "output_path": output_job_dir.relative_to(self.root).as_posix(),
                "remote_task_id": None,
                "duration_ms": None,
                "error": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            self._save_job(job)
        except Exception:
            shutil.rmtree(input_job_dir, ignore_errors=True)
            shutil.rmtree(output_job_dir, ignore_errors=True)
            raise
        if start:
            threading.Thread(target=self.run_job, args=(job_id,), daemon=True).start()
        return job

    def create_job_from_staged(
        self,
        *,
        filename: str,
        staged_path: Path,
        title: str | None = None,
    ) -> dict[str, Any]:
        with staged_path.open("rb") as source:
            return self.create_job(filename=filename, source=source, title=title, start=False)

    def _write_outputs(self, job: dict[str, Any], result: TranscriptionResult) -> None:
        output_dir = self.root / str(job["output_path"])
        _atomic_json(output_dir / "asr-result.json", result.raw_transcripts)
        _atomic_json(output_dir / "transcript.json", _transcript_payload(result.segments))
        _atomic_text(output_dir / "transcript.txt", _render_plain(result.segments))
        _atomic_text(output_dir / "transcript.md", _render_markdown(result.segments, str(job["title"])))

    def run_job(self, job_id: str) -> dict[str, Any]:
        if self.transcriber is None:
            raise WorkspaceError("转写服务尚未初始化")
        with self._lock:
            current = self.get_job(job_id)
            running = {
                **current,
                "status": "transcribing",
                "error": None,
                "updated_at": _now(),
            }
            self._save_job(running)

        def remember_remote_task(remote_task_id: str) -> None:
            with self._lock:
                latest = self.get_job(job_id)
                self._save_job({**latest, "remote_task_id": remote_task_id, "updated_at": _now()})

        try:
            result = self.transcriber.transcribe(
                (self.root / str(running["input_path"])).resolve(),
                remote_task_id=running.get("remote_task_id"),
                on_remote_task_id=remember_remote_task,
            )
            with self._lock:
                latest = self.get_job(job_id)
                self._write_outputs(latest, result)
                completed = {
                    **latest,
                    "status": "completed",
                    "duration_ms": max(segment.end_ms for segment in result.segments),
                    "error": None,
                    "updated_at": _now(),
                }
                return self._save_job(completed)
        except Exception as exc:
            logger.exception("meeting transcription job failed: %s", job_id)
            with self._lock:
                latest = self.get_job(job_id)
                return self._save_job(
                    {
                        **latest,
                        "status": "failed",
                        "error": str(exc),
                        "updated_at": _now(),
                    }
                )

    def rename_job(self, job_id: str, title: str) -> dict[str, Any]:
        with self._lock:
            job = self.get_job(job_id)
            return self._save_job({**job, "title": _safe_title(title), "updated_at": _now()})

    def retry_job(self, job_id: str, *, start: bool = False) -> dict[str, Any]:
        with self._lock:
            job = self.get_job(job_id)
            if job["status"] == "transcribing":
                raise WorkspaceConflict("任务正在转写，不能重复提交")
            queued = {
                **job,
                "status": "queued",
                "remote_task_id": None,
                "error": None,
                "updated_at": _now(),
            }
            self._save_job(queued)
        if start:
            threading.Thread(target=self.run_job, args=(job_id,), daemon=True).start()
        return queued

    def delete_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self.get_job(job_id)
            if job["status"] == "transcribing":
                raise WorkspaceConflict("任务正在转写，请完成后再删除")
            input_source = self.root / str(job["input_path"])
            output_source = self.root / str(job["output_path"])
            trash_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{job_id}"
            trash_root = self.trash_dir / trash_id
            if trash_root.exists():
                raise WorkspaceConflict(f"回收站条目已存在：{trash_id}")
            trash_root.mkdir(parents=True)
            manifest = {
                "trash_id": trash_id,
                "job_id": job_id,
                "deleted_at": _now(),
                "job": job,
            }
            _atomic_json(trash_root / "trash.json", manifest)
            moved_input = False
            try:
                if input_source.exists():
                    input_source.replace(trash_root / "input")
                    moved_input = True
                output_source.replace(trash_root / "output")
            except Exception:
                if moved_input and (trash_root / "input").exists() and not input_source.exists():
                    (trash_root / "input").replace(input_source)
                shutil.rmtree(trash_root, ignore_errors=True)
                raise
            return manifest

    def list_deleted(self) -> list[dict[str, Any]]:
        self.initialize()
        deleted: list[dict[str, Any]] = []
        for directory in self.trash_dir.iterdir():
            manifest_path = directory / "trash.json"
            if not directory.is_dir() or not manifest_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if isinstance(manifest, dict) and manifest.get("trash_id") == directory.name:
                    deleted.append(manifest)
            except (OSError, ValueError, TypeError):
                logger.warning("ignored invalid transcription trash entry: %s", manifest_path)
        deleted.sort(key=lambda item: str(item.get("deleted_at") or ""), reverse=True)
        return deleted

    def restore_job(self, trash_id: str) -> dict[str, Any]:
        if not _TRASH_ID.fullmatch(trash_id):
            raise WorkspaceNotFound("回收站条目不存在")
        with self._lock:
            trash_root = self.trash_dir / trash_id
            manifest_path = trash_root / "trash.json"
            if not manifest_path.is_file():
                raise WorkspaceNotFound(f"回收站条目不存在：{trash_id}")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            job = manifest.get("job") if isinstance(manifest, dict) else None
            if not isinstance(manifest, dict) or manifest.get("trash_id") != trash_id or not isinstance(job, dict):
                raise WorkspaceError("回收站条目损坏")
            job = self._validate_job_payload(
                job,
                expected_job_id=str(manifest.get("job_id") or ""),
                source=manifest_path,
            )
            input_target = self.root / str(job["input_path"])
            output_target = self.root / str(job["output_path"])
            if input_target.exists() or output_target.exists():
                raise WorkspaceConflict("原位置已有同 ID 任务，恢复已取消")
            input_target.parent.mkdir(parents=True, exist_ok=True)
            output_target.parent.mkdir(parents=True, exist_ok=True)
            moved_input = False
            try:
                if (trash_root / "input").exists():
                    (trash_root / "input").replace(input_target)
                    moved_input = True
                (trash_root / "output").replace(output_target)
            except Exception:
                if moved_input and input_target.exists() and not (trash_root / "input").exists():
                    input_target.replace(trash_root / "input")
                raise
            shutil.rmtree(trash_root)
            return self.get_job(str(job["id"]))


class TranscriptionRunner:
    """A persistent single-worker queue reconstructed from ``meta.json`` files."""

    def __init__(self, workspace: TranscriptionWorkspace):
        self.workspace = workspace
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._pending: set[str] = set()
        self._lock = threading.RLock()
        self._worker: threading.Thread | None = None

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(target=self._worker_loop, name="workmode-fun-asr", daemon=True)
            self._worker.start()

    def _worker_loop(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                if job_id is None:
                    return
                try:
                    self.workspace.run_job(job_id)
                except WorkspaceNotFound:
                    logger.info("skipped removed transcription job: %s", job_id)
            finally:
                if job_id is not None:
                    with self._lock:
                        self._pending.discard(job_id)
                self._queue.task_done()

    def submit(self, job_id: str) -> None:
        with self._lock:
            if job_id in self._pending:
                return
            self._pending.add(job_id)
            self._ensure_worker()
            self._queue.put(job_id)

    def recover(self) -> None:
        for job in self.workspace.list_jobs(limit=2000):
            if job.get("status") in {"queued", "transcribing"}:
                self.submit(str(job["id"]))
