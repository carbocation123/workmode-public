"""Manual AI polishing and summarization for completed transcripts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Protocol

import httpx


AiKind = Literal["polish", "summary"]
Completion = Callable[[str, str], str]


class TranscriptionAiError(Exception):
    """A safe, user-facing failure raised by transcription AI processing."""


class ModelSettings(Protocol):
    model_base_url: str
    model_api_key: str | None
    model_name: str
    request_timeout_seconds: float


def _clean_completion(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise TranscriptionAiError("AI 模型返回了空结果，请稍后重试")
    return cleaned + "\n"


def _chunk_text(text: str, max_chars: int) -> list[str]:
    """Split at transcript paragraph boundaries, then hard-wrap oversized paragraphs."""
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not paragraphs:
        return []
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        pieces = [paragraph[index:index + max_chars] for index in range(0, len(paragraph), max_chars)]
        for piece in pieces:
            candidate = f"{current}\n\n{piece}" if current else piece
            if current and len(candidate) > max_chars:
                chunks.append(current)
                current = piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


@dataclass
class OpenAICompatibleCompletion:
    base_url: str
    api_key: str
    model_name: str
    timeout_seconds: float

    def __call__(self, system_prompt: str, user_prompt: str) -> str:
        timeout = httpx.Timeout(max(float(self.timeout_seconds), 600.0), connect=30.0)
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "stream": False,
                    },
                )
                response.raise_for_status()
                payload: Any = response.json()
        except httpx.TimeoutException as exc:
            raise TranscriptionAiError("AI 模型响应超时，请稍后重试") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise TranscriptionAiError(f"AI 模型请求失败（HTTP {status}），请检查模型设置或余额") from exc
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise TranscriptionAiError("AI 模型连接失败，请检查模型地址与网络后重试") from exc

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TranscriptionAiError("AI 模型返回格式无法识别") from exc
        if not isinstance(content, str):
            raise TranscriptionAiError("AI 模型返回格式无法识别")
        return content


class TranscriptionAiProcessor:
    def __init__(
        self,
        *,
        completion: Completion,
        model_name: str,
        chunk_chars: int = 12_000,
    ):
        self.completion = completion
        self.model_name = model_name
        self.chunk_chars = max(100, int(chunk_chars))

    def generate(self, *, kind: AiKind, title: str, transcript: str) -> str:
        if kind not in {"polish", "summary"}:
            raise TranscriptionAiError("不支持的 AI 处理类型")
        chunks = _chunk_text(transcript, self.chunk_chars)
        if not chunks:
            raise TranscriptionAiError("转写正文为空，无法进行 AI 处理")
        if kind == "polish":
            return self._polish(title=title, chunks=chunks)
        return self._summarize(title=title, chunks=chunks)

    def _polish(self, *, title: str, chunks: list[str]) -> str:
        system = (
            "你是会议逐字稿编辑。只允许整理用户提供的转写：删除无意义口头重复，修复明显的断句和错别字。"
            "严禁编造原文没有的事实、数字、姓名、结论或行动项；无法确定时保留原文或明确标注【听不清】。"
            "保留说话人、时间信息和原有发言顺序，不要把推测写成事实。输出 Markdown，不解释你的工作过程。"
        )
        polished: list[str] = []
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            user = (
                f"会议标题：{title}\n"
                f"这是第 {index}/{total} 段。请润色下面的转写内容；严禁编造，并保留说话人和时间信息。\n\n"
                f"{chunk}"
            )
            polished.append(_clean_completion(self.completion(system, user)).strip())
        return _clean_completion("\n\n".join(polished))

    def _summarize(self, *, title: str, chunks: list[str]) -> str:
        system = (
            "你是忠实的会议纪要助手。只能依据输入内容提炼信息，严禁编造或补齐原文没有的事实。"
            "不得擅自猜测负责人、期限、结论或因果关系；不确定内容必须放入待确认问题。输出 Markdown。"
        )
        final_instruction = (
            "请整理为以下固定结构：# 会议总结、## 核心结论、## 决定事项、## 行动项、## 待确认问题。"
            "每一项都必须可追溯到原文；某一栏没有明确内容时写“未明确提及”。"
        )
        if len(chunks) == 1:
            user = f"会议标题：{title}\n{final_instruction}\n\n完整转写：\n{chunks[0]}"
            return _clean_completion(self.completion(system, user))

        partials: list[str] = []
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            user = (
                f"会议标题：{title}\n这是第 {index}/{total} 段转写。"
                "请只提取本段明确出现的结论、决定、行动项和待确认问题；严禁编造。\n\n"
                f"{chunk}"
            )
            partials.append(_clean_completion(self.completion(system, user)).strip())
        joined = "\n\n".join(
            f"### 片段 {index}\n{partial}" for index, partial in enumerate(partials, start=1)
        )
        user = (
            f"会议标题：{title}\n{final_instruction}\n"
            "下面是按原转写顺序生成的片段摘要。请去重合并，但不要添加片段摘要中没有的信息。\n\n"
            f"{joined}"
        )
        return _clean_completion(self.completion(system, user))


def build_transcription_ai_processor(settings: ModelSettings) -> TranscriptionAiProcessor:
    if not settings.model_base_url or not settings.model_api_key:
        raise TranscriptionAiError("请先在设置中配置 AI 模型地址和 API Key")
    completion = OpenAICompatibleCompletion(
        base_url=settings.model_base_url,
        api_key=settings.model_api_key,
        model_name=settings.model_name,
        timeout_seconds=settings.request_timeout_seconds,
    )
    return TranscriptionAiProcessor(completion=completion, model_name=settings.model_name)
