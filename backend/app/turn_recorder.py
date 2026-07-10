from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import storage


AppendMessage = Callable[..., dict[str, Any]]


class TurnRecorder:
    """Persist one streamed turn without losing text/tool interleaving."""

    def __init__(
        self,
        session_id: str,
        model_name: str,
        *,
        append_message: AppendMessage = storage.append_message,
    ) -> None:
        self._session_id = session_id
        self._model_name = model_name
        self._append_message = append_message
        self._text_parts: list[str] = []
        self._assistant_segments = 0
        self._tool_messages = 0
        self._pending_tools: dict[str, str] = {}
        self._finalized = False

    def append_text(self, content: str) -> None:
        if self._finalized:
            return
        self._text_parts.append(content)

    def flush_text(self, *, interrupted: bool = False) -> dict[str, Any] | None:
        if not self._text_parts:
            return None
        content = "".join(self._text_parts)
        self._text_parts.clear()
        self._assistant_segments += 1
        return self._append_message(
            self._session_id,
            role="assistant",
            content=content,
            meta={
                "model": self._model_name,
                "interrupted": interrupted,
                "segment_index": self._assistant_segments,
            },
        )

    def start_tool(self, event: dict[str, Any]) -> dict[str, Any]:
        self.flush_text()
        call_id = str(event.get("id") or f"call_pending_{self._tool_messages + 1}")
        tool_name = str(event.get("name") or "unknown")
        self._pending_tools[call_id] = tool_name
        self._tool_messages += 1
        return self._append_message(
            self._session_id,
            role="tool",
            content=f"调用 {tool_name}",
            meta={
                "event": "tool_call_start",
                "tool_call_id": call_id,
                "tool_name": tool_name,
                "args": event.get("input") or {},
                "status": "running",
            },
        )

    def finish_tool(self, event: dict[str, Any]) -> dict[str, Any]:
        call_id = str(event.get("id") or "")
        tool_name = str(event.get("name") or self._pending_tools.get(call_id) or "unknown")
        self._pending_tools.pop(call_id, None)
        self._tool_messages += 1
        ok = bool(event.get("ok"))
        return self._append_message(
            self._session_id,
            role="tool",
            content=str(event.get("result") or ""),
            meta={
                "event": "tool_result",
                "tool_call_id": call_id,
                "tool_name": tool_name,
                "status": "done" if ok else "error",
                "ok": ok,
                "changed_paths": event.get("changed_paths") or [],
            },
        )

    def finalize(self, *, interrupted: bool) -> list[dict[str, Any]]:
        if self._finalized:
            return []
        self._finalized = True
        had_activity = bool(
            self._text_parts
            or self._assistant_segments
            or self._tool_messages
            or self._pending_tools
        )
        persisted: list[dict[str, Any]] = []
        assistant = self.flush_text(interrupted=interrupted)
        if assistant is not None:
            persisted.append(assistant)

        pending_status = "cancelled" if interrupted else "error"
        pending_content = (
            "工具调用已由用户停止。"
            if interrupted
            else "工具调用在返回结果前意外结束。"
        )
        for call_id, tool_name in list(self._pending_tools.items()):
            persisted.append(
                self._append_message(
                    self._session_id,
                    role="tool",
                    content=pending_content,
                    meta={
                        "event": "tool_result",
                        "tool_call_id": call_id,
                        "tool_name": tool_name,
                        "status": pending_status,
                        "ok": False,
                        "changed_paths": [],
                    },
                )
            )
            self._tool_messages += 1
        self._pending_tools.clear()

        if interrupted and not had_activity:
            persisted.append(
                self._append_message(
                    self._session_id,
                    role="system",
                    content="本轮生成已由用户停止。",
                    meta={"event": "generation_stopped", "interrupted": True},
                )
            )
        return persisted
