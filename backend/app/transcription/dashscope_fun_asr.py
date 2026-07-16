"""DashScope Fun-ASR file transcription adapter.

The signed upload URL stays in the call stack and is never written to the
workspace.  Durable task metadata stores only the provider task id and the
fixed model name so interrupted polling can resume after restart.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx


logger = logging.getLogger(__name__)

MODEL = "fun-asr"
TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks"


@dataclass(frozen=True)
class Segment:
    seq: int
    speaker_id: int | str
    start_ms: int
    end_ms: int
    text: str
    is_overlap: bool = False


@dataclass(frozen=True)
class TranscriptionResult:
    raw_transcripts: list[dict[str, Any]]
    segments: list[Segment]


def parse_dashscope_segments(raw_transcripts: list[dict[str, Any]]) -> list[Segment]:
    parsed: list[Segment] = []
    for bundle in raw_transcripts:
        if "error" in bundle:
            continue
        transcript_list = bundle.get("transcripts") or [bundle]
        for transcript in transcript_list:
            if not isinstance(transcript, dict):
                continue
            for sentence in transcript.get("sentences") or []:
                if not isinstance(sentence, dict):
                    continue
                text = str(sentence.get("text") or "").strip()
                if not text:
                    continue
                speaker_id = sentence.get("speaker_id")
                if speaker_id is None:
                    speaker_id = "?"
                start_ms = int(sentence.get("begin_time") or sentence.get("start_time") or 0)
                end_ms = int(sentence.get("end_time") or start_ms)
                parsed.append(
                    Segment(
                        seq=len(parsed),
                        speaker_id=speaker_id,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        text=text,
                    )
                )

    result: list[Segment] = []
    for index, segment in enumerate(parsed):
        overlaps_previous = index > 0 and segment.start_ms < parsed[index - 1].end_ms
        result.append(
            Segment(
                seq=segment.seq,
                speaker_id=segment.speaker_id,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=segment.text,
                is_overlap=overlaps_previous,
            )
        )
    return result


def _response_output(response: Any) -> dict[str, Any]:
    output = getattr(response, "output", None)
    if hasattr(output, "to_dict"):
        output = output.to_dict()
    if not isinstance(output, dict):
        raise RuntimeError(f"DashScope 返回缺少 output: {response!r}")
    return output


def upload_audio(api_key: str, audio_path: Path) -> str:
    try:
        from dashscope import Files
    except ImportError as exc:
        raise RuntimeError("当前运行环境缺少 dashscope 依赖，请重新安装或更新 Workmode Public") from exc

    response = Files.upload(file_path=str(audio_path), purpose="inference", api_key=api_key)
    if getattr(response, "status_code", None) != 200:
        raise RuntimeError(
            "DashScope 文件上传失败: "
            f"{getattr(response, 'code', '')} {getattr(response, 'message', '')}".strip()
        )
    uploaded = _response_output(response).get("uploaded_files") or []
    file_id = uploaded[0].get("file_id") if uploaded and isinstance(uploaded[0], dict) else None
    if not file_id:
        raise RuntimeError("DashScope 文件上传成功响应中没有 file_id")

    response = Files.get(file_id, api_key=api_key)
    if getattr(response, "status_code", None) != 200:
        raise RuntimeError(
            "DashScope 文件地址读取失败: "
            f"{getattr(response, 'code', '')} {getattr(response, 'message', '')}".strip()
        )
    signed_url = _response_output(response).get("url")
    if not isinstance(signed_url, str) or not signed_url.strip():
        raise RuntimeError("DashScope 文件地址响应中没有签名 URL")
    logger.info("meeting audio uploaded: file_id=%s (signed URL omitted)", file_id)
    return signed_url.strip()


def submit_transcription(api_key: str, signed_url: str, speaker_count: int | None) -> str:
    try:
        from dashscope.audio.asr import Transcription
    except ImportError as exc:
        raise RuntimeError("当前运行环境缺少 dashscope 依赖，请重新安装或更新 Workmode Public") from exc

    kwargs: dict[str, Any] = {
        "model": MODEL,
        "file_urls": [signed_url],
        "api_key": api_key,
        "diarization_enabled": True,
    }
    if speaker_count:
        kwargs["speaker_count"] = speaker_count
    response = Transcription.async_call(**kwargs)
    if getattr(response, "status_code", None) != 200:
        raise RuntimeError(
            f"DashScope 转写任务提交失败: {getattr(response, 'status_code', '')} "
            f"{getattr(response, 'message', '')}".strip()
        )
    output = getattr(response, "output", None)
    task_id = getattr(output, "task_id", None)
    if not task_id and hasattr(output, "get"):
        task_id = output.get("task_id")
    if not task_id:
        raise RuntimeError("DashScope 转写任务响应中没有 task_id")
    logger.info("Fun-ASR task submitted: task_id=%s", task_id)
    return str(task_id)


def _query_task(api_key: str, task_id: str, request_timeout: float = 30) -> dict[str, Any]:
    response = httpx.get(
        f"{TASK_URL}/{task_id}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=request_timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("DashScope 任务查询返回的不是 JSON object")
    if payload.get("code"):
        raise RuntimeError(
            f"DashScope 任务查询失败: {payload.get('code')} {payload.get('message', '')}".strip()
        )
    output = payload.get("output", payload)
    if not isinstance(output, dict):
        raise RuntimeError("DashScope 任务查询缺少 output")
    return output


def wait_for_transcription(
    api_key: str,
    task_id: str,
    *,
    poll_interval: float = 5,
    timeout: float = 7200,
    request_timeout: float = 30,
) -> dict[str, Any]:
    started = time.monotonic()
    last_status: str | None = None
    while True:
        if time.monotonic() - started >= timeout:
            raise TimeoutError(f"等待任务 {task_id} 超过 {timeout:.0f}s；任务编号已保存，可重启后继续")
        try:
            output = _query_task(api_key, task_id, request_timeout)
        except httpx.HTTPError as exc:
            logger.warning("Fun-ASR task query failed temporarily: %s", exc)
            time.sleep(poll_interval)
            continue

        status = str(output.get("task_status") or "").upper()
        if status != last_status:
            logger.info("Fun-ASR task %s status: %s", task_id, status or "<missing>")
            last_status = status
        if status == "SUCCEEDED":
            return output
        if status in {"FAILED", "CANCELED", "CANCELLED", "UNKNOWN"}:
            detail = output.get("message") or output.get("code") or output
            raise RuntimeError(f"任务 {task_id} {status}: {detail}")
        if status not in {"PENDING", "RUNNING"}:
            raise RuntimeError(f"任务 {task_id} 返回未知状态: {status or output!r}")
        time.sleep(poll_interval)


def fetch_transcripts(output: dict[str, Any]) -> list[dict[str, Any]]:
    results = output.get("results") or []
    if not results:
        raise RuntimeError("DashScope 转写任务输出中没有 results")
    fetched: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        status = item.get("subtask_status")
        if status and status != "SUCCEEDED":
            fetched.append({"error": f"subtask_status={status}"})
            continue
        url = item.get("transcription_url")
        if not url:
            fetched.append({"error": "no transcription_url"})
            continue
        response = httpx.get(str(url), timeout=120)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("DashScope transcription_url 返回的不是 JSON object")
        fetched.append(payload)
    return fetched


class DashScopeFunAsrTranscriber:
    model = MODEL

    def __init__(
        self,
        *,
        api_key_provider: Callable[[], str],
        speaker_count: int | None = None,
        uploader: Callable[[str, Path], str] = upload_audio,
        submitter: Callable[[str, str, int | None], str] = submit_transcription,
        waiter: Callable[[str, str], dict[str, Any]] = wait_for_transcription,
        transcript_fetcher: Callable[[dict[str, Any]], list[dict[str, Any]]] = fetch_transcripts,
    ):
        self.api_key_provider = api_key_provider
        self.speaker_count = speaker_count
        self.uploader = uploader
        self.submitter = submitter
        self.waiter = waiter
        self.transcript_fetcher = transcript_fetcher

    def transcribe(
        self,
        audio_path: Path,
        *,
        remote_task_id: str | None = None,
        on_remote_task_id: Callable[[str], None] | None = None,
    ) -> TranscriptionResult:
        api_key = self.api_key_provider().strip()
        if not api_key:
            raise RuntimeError("未配置 DashScope API Key")

        task_id = remote_task_id
        if not task_id:
            signed_url = self.uploader(api_key, audio_path)
            task_id = self.submitter(api_key, signed_url, self.speaker_count)
            if on_remote_task_id:
                on_remote_task_id(task_id)

        output = self.waiter(api_key, task_id)
        raw_transcripts = self.transcript_fetcher(output)
        segments = parse_dashscope_segments(raw_transcripts)
        if not segments:
            raise RuntimeError("DashScope 返回成功，但没有可用的转写片段")
        return TranscriptionResult(raw_transcripts=raw_transcripts, segments=segments)
