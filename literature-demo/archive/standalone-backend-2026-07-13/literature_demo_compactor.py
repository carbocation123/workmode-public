from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .config import get_settings
from .literature_demo_store import LiteratureDemoStore


class LiteratureCompactionError(RuntimeError):
    pass


def messages_visible_after_summary(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    marker_index = -1
    for index, message in enumerate(messages):
        if (message.get("meta") or {}).get("kind") == "context_summary":
            marker_index = index
    return messages[marker_index:] if marker_index >= 0 else messages


def _extract_json(text: str) -> dict[str, Any]:
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise LiteratureCompactionError("压缩模型没有返回 JSON") from None
        try:
            value = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LiteratureCompactionError("压缩模型返回的 JSON 无法解析") from exc
    if not isinstance(value, dict):
        raise LiteratureCompactionError("压缩结果不是 JSON object")
    return value


def _summarize_session(messages: list[dict[str, Any]]) -> dict[str, str | None]:
    settings = get_settings()
    if not settings.model_base_url or not settings.model_api_key:
        raise LiteratureCompactionError("模型未配置，无法生成上下文续接摘要")
    transcript = [
        {
            "role": item.get("role"),
            "content": item.get("content"),
            "paper_ids": item.get("paper_ids", []),
            "note_ids": item.get("note_ids", []),
        }
        for item in messages
        if item.get("role") in {"user", "assistant", "system"} and item.get("content")
    ]
    payload = {
        "model": settings.model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是文献项目会话压缩器。只总结已经发生的事实、用户决定、证据边界、"
                    "选中文献/笔记和未完成事项，不补推断。返回 JSON object：summary 为完整续接摘要；"
                    "memory_candidate 为值得跨会话长期保存的新纪律或稳定偏好，没有则为 null。"
                ),
            },
            {"role": "user", "content": json.dumps(transcript, ensure_ascii=False)},
        ],
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.model_api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(max(settings.request_timeout_seconds, 600), connect=30)) as client:
            response = client.post(
                f"{settings.model_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise LiteratureCompactionError(f"压缩模型连接失败：{exc.__class__.__name__}") from exc
    if response.status_code >= 400:
        raise LiteratureCompactionError(f"压缩模型请求失败：HTTP {response.status_code}")
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LiteratureCompactionError("压缩模型响应缺少正文") from exc
    result = _extract_json(str(content))
    summary = str(result.get("summary") or "").strip()
    if not summary:
        raise LiteratureCompactionError("压缩摘要为空")
    candidate_value = result.get("memory_candidate")
    candidate = str(candidate_value).strip() if candidate_value else None
    return {"summary": summary, "memory_candidate": candidate}


def compact_literature_session(store: LiteratureDemoStore, session_id: str) -> dict[str, Any]:
    session = store.get_session(session_id)
    visible = messages_visible_after_summary(list(session.get("messages") or []))
    if not visible:
        raise LiteratureCompactionError("当前会话没有可压缩消息")
    result = _summarize_session(visible)
    marker = {
        "role": "system",
        "content": f"<CONTEXT_SUMMARY>\n{result['summary']}\n</CONTEXT_SUMMARY>",
        "meta": {
            "kind": "context_summary",
            "summarized_message_count": len(visible),
        },
    }
    next_session = store.append_message(session_id, marker)
    next_session = store.set_memory_candidate(session_id, result["memory_candidate"])
    return {
        "session": next_session,
        "summary": result["summary"],
        "memory_candidate": result["memory_candidate"],
        "summarized_message_count": len(visible),
        "total_message_count": len(next_session["messages"]),
    }
