from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .config import get_settings
from .project_tools import PROJECT_TOOL_SCHEMAS, execute_project_tool, project_tool_names


class ModelProbeError(RuntimeError):
    pass


async def probe_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model_name: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Run one tiny, non-streaming request without persisting the draft settings."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "stream": False,
        "max_tokens": 8,
    }
    timeout = httpx.Timeout(min(timeout_seconds, 30.0), connect=min(timeout_seconds, 10.0))
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise ModelProbeError("模型连接超时，请检查 Base URL、网络或代理设置") from exc
    except httpx.HTTPError as exc:
        raise ModelProbeError(f"无法连接模型服务：{exc.__class__.__name__}") from exc

    if response.status_code in {401, 403}:
        raise ModelProbeError("API Key 无效，或当前账号没有访问该模型的权限")
    if response.status_code == 404:
        raise ModelProbeError("Base URL 或模型名称不存在，请检查地址是否包含正确的 /v1 路径")
    if response.status_code == 429:
        raise ModelProbeError("模型服务限流、余额不足或配额已用完")
    if response.status_code >= 500:
        raise ModelProbeError(f"模型服务暂时不可用（HTTP {response.status_code}）")
    if response.status_code >= 400:
        raise ModelProbeError(f"模型服务拒绝请求（HTTP {response.status_code}）")

    try:
        data = response.json()
    except ValueError as exc:
        raise ModelProbeError("服务返回的不是 OpenAI-compatible JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("choices"), list):
        raise ModelProbeError("服务响应缺少 choices，可能不兼容 OpenAI Chat Completions API")

    return {
        "ok": True,
        "message": "模型连接成功",
        "model": str(data.get("model") or model_name),
        "latency_ms": max(1, round((time.perf_counter() - started) * 1000)),
    }


async def stream_openai_compatible(
    messages: list[dict[str, Any]],
    *,
    project_slug: str | None = None,
    cancel_event: threading.Event | None = None,
) -> AsyncIterator[dict[str, Any]]:
    settings = get_settings()
    if not settings.model_base_url or not settings.model_api_key:
        yield {
            "type": "error",
            "message": "模型未配置。请设置 WORKMODE_MODEL_BASE_URL、WORKMODE_MODEL_API_KEY 和 WORKMODE_MODEL_NAME。",
        }
        return

    url = f"{settings.model_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.model_api_key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(settings.request_timeout_seconds, read=None)
    working_messages: list[dict[str, Any]] = [dict(message) for message in messages]
    tool_names = project_tool_names()

    async with httpx.AsyncClient(timeout=timeout) as client:
        round_index = 1
        while True:
            if cancel_event is not None and cancel_event.is_set():
                yield {"type": "cancelled"}
                return
            payload: dict[str, Any] = {
                "model": settings.model_name,
                "messages": working_messages,
                "stream": True,
            }
            if project_slug:
                payload["tools"] = PROJECT_TOOL_SCHEMAS
                payload["tool_choice"] = "auto"

            round_text: list[str] = []
            tool_calls: dict[int, dict[str, Any]] = {}
            failed = False

            try:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code >= 400:
                        body = (await response.aread()).decode("utf-8", errors="replace")[:1000]
                        yield {"type": "error", "message": f"模型请求失败：HTTP {response.status_code} {body}"}
                        return
                    async for line in response.aiter_lines():
                        if cancel_event is not None and cancel_event.is_set():
                            yield {"type": "cancelled"}
                            return
                        if not line.startswith("data:"):
                            continue
                        data = line.removeprefix("data:").strip()
                        if not data or data == "[DONE]":
                            continue
                        try:
                            item = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        delta = item.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            round_text.append(content)
                            yield {"type": "text_delta", "content": content}
                        _merge_tool_call_deltas(tool_calls, delta.get("tool_calls") or [])
            except httpx.HTTPError as exc:
                failed = True
                yield {"type": "error", "message": f"模型连接失败：{exc}"}

            if failed:
                return
            if not tool_calls:
                return

            ordered_calls = [_normalize_tool_call(tool_calls[index], index) for index in sorted(tool_calls)]
            working_messages.append(
                {
                    "role": "assistant",
                    "content": "".join(round_text) or None,
                    "tool_calls": ordered_calls,
                }
            )

            for call in ordered_calls:
                if cancel_event is not None and cancel_event.is_set():
                    yield {"type": "cancelled"}
                    return
                call_id = call.get("id") or f"call_{round_index}_{len(working_messages)}"
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                raw_args = str(function.get("arguments") or "{}")
                try:
                    args = json.loads(raw_args) if raw_args.strip() else {}
                    if not isinstance(args, dict):
                        raise ValueError("工具参数必须是 JSON object")
                except Exception as exc:
                    args = {}
                    result_content = f"ERROR: 工具参数 JSON 解析失败：{exc}; raw={raw_args[:1000]}"
                    ok = False
                    changed_paths: list[str] = []
                else:
                    yield {"type": "tool_call_start", "id": call_id, "name": name, "input": args}
                    if project_slug and name in tool_names:
                        result = await asyncio.to_thread(
                            execute_project_tool,
                            project_slug,
                            name,
                            args,
                            cancel_event=cancel_event,
                        )
                        result_content = result.content
                        ok = result.ok
                        changed_paths = result.changed_paths
                    else:
                        result_content = f"ERROR: 未启用或未知工具：{name}"
                        ok = False
                        changed_paths = []

                yield {
                    "type": "tool_result",
                    "id": call_id,
                    "name": name,
                    "result": result_content,
                    "ok": ok,
                    "changed_paths": changed_paths,
                }
                working_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": result_content,
                    }
                )

            yield {"type": "loop_continue", "round": round_index + 1}
            round_index += 1


def _merge_tool_call_deltas(tool_calls: dict[int, dict[str, Any]], deltas: list[dict[str, Any]]) -> None:
    for delta in deltas:
        index = int(delta.get("index", len(tool_calls)))
        current = tool_calls.setdefault(
            index,
            {
                "id": "",
                "type": "function",
                "function": {"name": "", "arguments": ""},
            },
        )
        if delta.get("id"):
            current["id"] = delta["id"]
        if delta.get("type"):
            current["type"] = delta["type"]
        function_delta = delta.get("function") or {}
        function = current.setdefault("function", {"name": "", "arguments": ""})
        if function_delta.get("name"):
            function["name"] = function_delta["name"]
        if function_delta.get("arguments"):
            function["arguments"] = str(function.get("arguments") or "") + function_delta["arguments"]


def _normalize_tool_call(call: dict[str, Any], index: int) -> dict[str, Any]:
    function = call.get("function") or {}
    return {
        "id": call.get("id") or f"call_{index}",
        "type": call.get("type") or "function",
        "function": {
            "name": function.get("name") or "",
            "arguments": function.get("arguments") or "{}",
        },
    }
