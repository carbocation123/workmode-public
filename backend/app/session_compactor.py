from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from . import storage
from .config import get_settings


logger = logging.getLogger(__name__)

SUMMARY_PREFIX = "<CONTEXT_SUMMARY>\n\n"
DEFAULT_KEEP_RECENT = 6
MIN_KEEP_RECENT = 2
MAX_KEEP_RECENT = 30
MIN_MESSAGES_TO_COMPACT = 4

Summarizer = Callable[[list[dict[str, Any]], str], Awaitable[str]]


COMPACT_SYSTEM_PROMPT = """你是会话上下文压缩器。下面是一段科研工作助手的对话历史。请把它压缩成结构化中文摘要，作为续接对话时的背景。

按以下 8 个 section 输出，每节都要写；无内容写“无”：

## 1. 主要请求与意图
用户在这段对话里的核心目标、明确要求、关键决策点。

## 2. 关键技术概念
涉及的技术、协议、框架、设计原则或重要约束。

## 3. 文件与代码段
列出被读取、修改、创建的文件路径，并说明关键改动；必要时引用小段代码。

## 4. 错误与修复
遇到的错误、诊断过程和修复方式。

## 5. 问题解决过程
核心思考路径、方案取舍和原因。

## 6. 所有用户消息
按时间顺序列出用户的指令性/提问性消息原文；可省略“好的”这类纯确认。

## 7. 待办与未完成
仍未完成、被阻塞或需要用户确认的事项。

## 8. 当前工作与下一步
- 当前工作：压缩前对话末尾正在做什么
- 下一步：最合理的接续动作

输出规则：
- 客观第三人称口吻，用“用户 / 助手 / 该 session”指代，不要使用“我 / 你”。
- 这是系统层归档摘要，不要伪装成助手自己的记忆。
- 每节用 `## ` 开头。
- 不要解释你在做什么，直接输出摘要。
- 摘要应高度浓缩，避免原样复刻长工具结果。"""


class CompactionError(Exception):
    pass


@dataclass(frozen=True)
class CompactionResult:
    session_id: str
    project_slug: str
    original_message_count: int
    kept_recent: int
    summarized_count: int
    summary_chars: int
    new_message_count: int
    compaction_seq: int


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_summary_marker(message: dict[str, Any]) -> bool:
    content = message.get("content")
    return (
        message.get("role") == "system"
        and isinstance(content, str)
        and content.startswith(SUMMARY_PREFIX)
    )


def find_last_marker_idx(messages: list[dict[str, Any]]) -> int:
    for index in range(len(messages) - 1, -1, -1):
        if is_summary_marker(messages[index]):
            return index
    return -1


def messages_visible_to_llm(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index = find_last_marker_idx(messages)
    if index < 0:
        return list(messages)
    return list(messages[index:])


def _is_context_message(message: dict[str, Any]) -> bool:
    if is_summary_marker(message):
        return True
    return message.get("role") in {"user", "assistant", "tool"}


def _complete_turn_start(messages: list[dict[str, Any]], requested_start: int) -> int:
    if not messages:
        return 0
    start = max(0, min(int(requested_start), len(messages) - 1))
    for index in range(start, -1, -1):
        if messages[index].get("role") == "user":
            return index
    return 0


def _format_tool_message(message: dict[str, Any]) -> str:
    meta = message.get("meta") or {}
    event = meta.get("event")
    name = meta.get("tool_name") or "project_tool"
    if event == "tool_call_start":
        args = json.dumps(meta.get("args") or {}, ensure_ascii=False)
        return f"## 助手调用工具\n{name}({args[:600]})"
    if event == "tool_result":
        content = str(message.get("content") or "")
        preview = content[:800] + ("…" if len(content) > 800 else "")
        return f"## 工具结果\n{name} → {preview}"
    content = str(message.get("content") or "")
    preview = content[:800] + ("…" if len(content) > 800 else "")
    return f"## 工具事件\n{preview}"


def _format_for_summary(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for message in messages:
        role = message.get("role")
        content = str(message.get("content") or "").strip()
        if role == "user":
            parts.append(f"## 用户\n{content}")
        elif role == "assistant":
            parts.append(f"## 助手\n{content}")
        elif role == "tool":
            parts.append(_format_tool_message(message))
        elif is_summary_marker(message):
            stripped = content[len(SUMMARY_PREFIX) :]
            preview = stripped[:1200] + ("…" if len(stripped) > 1200 else "")
            parts.append(f"## 之前的摘要\n{preview}")
        elif role == "system":
            parts.append(f"## 系统\n{content[:400]}")
    return "\n\n".join(part for part in parts if part.strip())


async def _summarize_with_model(messages: list[dict[str, Any]], extra_instruction: str = "") -> str:
    settings = get_settings()
    if not settings.model_base_url or not settings.model_api_key:
        raise CompactionError("模型未配置，无法压缩上下文。")

    system = COMPACT_SYSTEM_PROMPT
    if extra_instruction.strip():
        system += "\n\n## 额外压缩指引\n" + extra_instruction.strip()

    payload = {
        "model": settings.model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _format_for_summary(messages)},
        ],
        "stream": False,
        "temperature": 0.2,
    }
    url = f"{settings.model_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.model_api_key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(settings.request_timeout_seconds, read=None)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                body = response.text[:1000]
                raise CompactionError(f"模型请求失败：HTTP {response.status_code} {body}")
            data = response.json()
    except httpx.HTTPError as exc:
        raise CompactionError(f"模型连接失败：{exc}") from exc

    text = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
    if not text:
        raise CompactionError("模型返回空摘要。")
    return text


async def compact_session(
    session_id: str,
    *,
    keep_recent: int = DEFAULT_KEEP_RECENT,
    extra_instruction: str = "",
    summarizer: Summarizer | None = None,
) -> CompactionResult:
    effective_keep = max(MIN_KEEP_RECENT, min(MAX_KEEP_RECENT, keep_recent))
    session = storage.get_session(session_id)
    messages = storage.read_messages(session_id, limit=0)

    last_marker_idx = find_last_marker_idx(messages)
    pending_start = last_marker_idx + 1
    pending = messages[pending_start:]

    ua_count = sum(1 for message in pending if message.get("role") in {"user", "assistant"})
    if ua_count < MIN_MESSAGES_TO_COMPACT:
        raise CompactionError(
            f"待压缩部分仅 {ua_count} 条 user/assistant 消息（< {MIN_MESSAGES_TO_COMPACT}），不值得压缩。"
        )

    context_indices = [
        index
        for index, message in enumerate(pending)
        if _is_context_message(message)
    ]
    if len(context_indices) <= effective_keep:
        raise CompactionError(
            f"待压缩部分上下文消息 {len(context_indices)} ≤ keep_recent={effective_keep}，没有可压缩部分。"
        )

    recent_start = _complete_turn_start(pending, context_indices[-effective_keep])
    to_summarize = pending[:recent_start]
    recent = pending[recent_start:]
    if not to_summarize:
        raise CompactionError("没有可压缩的早期消息。")

    summarize = summarizer or _summarize_with_model
    summary_text = await summarize(to_summarize, extra_instruction)
    summary_text = summary_text.strip()
    if not summary_text:
        raise CompactionError("压缩摘要为空。")

    compaction_seq = sum(1 for message in messages if is_summary_marker(message)) + 1
    marker = {
        "id": uuid.uuid4().hex,
        "role": "system",
        "content": SUMMARY_PREFIX + summary_text,
        "ts": utc_now(),
        "meta": {
            "event": "context_summary",
            "compaction_seq": compaction_seq,
            "summarized_message_count": len(to_summarize),
            "keep_recent": effective_keep,
        },
    }

    boundary = pending_start + recent_start
    next_messages = messages[:boundary] + [marker] + recent
    storage.replace_messages(session_id, next_messages)

    return CompactionResult(
        session_id=session_id,
        project_slug=session.project_slug,
        original_message_count=len(messages),
        kept_recent=effective_keep,
        summarized_count=len(to_summarize),
        summary_chars=len(summary_text),
        new_message_count=len(next_messages),
        compaction_seq=compaction_seq,
    )


def compaction_payload(result: CompactionResult) -> dict[str, Any]:
    return asdict(result)

