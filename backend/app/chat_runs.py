from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field


class ChatAlreadyRunningError(Exception):
    pass


@dataclass
class ChatRun:
    session_id: str
    cancel_event: threading.Event = field(default_factory=threading.Event)
    task: asyncio.Task[object] | None = None
    loop: asyncio.AbstractEventLoop | None = None

    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def request_cancel(self) -> None:
        self.cancel_event.set()
        if self.task is None or self.task.done():
            return
        if self.loop is not None and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.task.cancel)
        else:
            self.task.cancel()


class ChatRunRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._runs: dict[str, ChatRun] = {}

    def register(
        self,
        session_id: str,
        *,
        task: asyncio.Task[object] | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> ChatRun:
        with self._lock:
            if session_id in self._runs:
                raise ChatAlreadyRunningError("该会话正在生成，请先停止当前回复")
            run = ChatRun(session_id=session_id, task=task, loop=loop)
            self._runs[session_id] = run
            return run

    def unregister(self, session_id: str, run: ChatRun) -> None:
        with self._lock:
            if self._runs.get(session_id) is run:
                self._runs.pop(session_id, None)

    def cancel(self, session_id: str) -> bool:
        with self._lock:
            run = self._runs.get(session_id)
        if run is None:
            return False
        run.request_cancel()
        return True

    def is_running(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._runs


chat_runs = ChatRunRegistry()
