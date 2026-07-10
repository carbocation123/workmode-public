from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from .context_imports import count_text_tokens


Message = dict[str, Any]
TokenCounter = Callable[[str], int]
MessageTokenCounter = Callable[[Message], int]


@dataclass(frozen=True)
class ContextWindowResult:
    messages: list[Message]
    usage: dict[str, int | float | bool | str]


def count_message_tokens(message: Message) -> int:
    payload = {key: value for key, value in message.items() if key not in {"id", "ts"}}
    return count_text_tokens(json.dumps(payload, ensure_ascii=False)) + 4


def _is_summary_marker(message: Message, summary_prefix: str) -> bool:
    content = message.get("content")
    return (
        message.get("role") == "system"
        and isinstance(content, str)
        and content.startswith(summary_prefix)
    )


def _is_valid_start(message: Message) -> bool:
    """OpenAI-compatible history should not start from a bare tool result."""
    return message.get("role") in {"user", "system"}


def _fit_recent_suffix(
    messages: list[Message],
    token_budget: int,
    message_token_counter: MessageTokenCounter,
) -> list[Message]:
    if not messages:
        return []

    running_tokens = 0
    best_start: int | None = None
    for index in range(len(messages) - 1, -1, -1):
        running_tokens += max(0, int(message_token_counter(messages[index])))
        if running_tokens > token_budget:
            break
        if _is_valid_start(messages[index]):
            best_start = index

    if best_start is not None:
        return list(messages[best_start:])

    for index in range(len(messages) - 1, -1, -1):
        if _is_valid_start(messages[index]):
            return list(messages[index:])
    return []


def _select_history(
    messages: list[Message],
    token_budget: int,
    message_token_counter: MessageTokenCounter,
    summary_prefix: str,
) -> list[Message]:
    marker_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if _is_summary_marker(messages[index], summary_prefix)
        ),
        -1,
    )
    if marker_index < 0:
        return _fit_recent_suffix(messages, token_budget, message_token_counter)

    marker = messages[marker_index]
    marker_tokens = max(0, int(message_token_counter(marker)))
    recent = _fit_recent_suffix(
        messages[marker_index + 1 :],
        max(0, token_budget - marker_tokens),
        message_token_counter,
    )
    return [marker, *recent]


def build_context_window(
    *,
    system_prompt: str,
    tool_schemas: list[dict[str, Any]] | None,
    messages: list[Message],
    total_budget_tokens: int,
    summary_prefix: str,
    text_token_counter: TokenCounter = count_text_tokens,
    message_token_counter: MessageTokenCounter = count_message_tokens,
) -> ContextWindowResult:
    budget = max(1, int(total_budget_tokens))
    system_tokens = max(0, int(text_token_counter(system_prompt or "")))
    tool_tokens = 0
    if tool_schemas:
        tool_tokens = max(0, int(text_token_counter(json.dumps(tool_schemas, ensure_ascii=False))))
    history_budget = max(0, budget - system_tokens - tool_tokens)
    selected = _select_history(messages, history_budget, message_token_counter, summary_prefix)
    history_tokens = sum(max(0, int(message_token_counter(message))) for message in selected)
    estimated_prompt_tokens = system_tokens + tool_tokens + history_tokens

    usage: dict[str, int | float | bool | str] = {
        "budget_tokens": budget,
        "system_tokens": system_tokens,
        "tool_tokens": tool_tokens,
        "history_budget_tokens": history_budget,
        "history_tokens": history_tokens,
        "estimated_prompt_tokens": estimated_prompt_tokens,
        "prompt_tokens_estimate": estimated_prompt_tokens,
        "total_tokens_estimate": estimated_prompt_tokens,
        "usage_ratio": estimated_prompt_tokens / budget,
        "history_messages_total": len(messages),
        "history_messages_included": len(selected),
        "history_messages_dropped": max(0, len(messages) - len(selected)),
        "history_message_count": len(selected),
        "truncated": len(selected) < len(messages),
        "has_summary": any(_is_summary_marker(message, summary_prefix) for message in selected),
        "over_budget": estimated_prompt_tokens > budget,
        "estimator": "workmode-public-approx",
    }
    return ContextWindowResult(messages=selected, usage=usage)

