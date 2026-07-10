from __future__ import annotations

import unittest
from typing import Any


class TurnRecorderTest(unittest.TestCase):
    def test_interleaved_text_and_tools_keep_order_when_stopped(self) -> None:
        from app.turn_recorder import TurnRecorder

        recorded: list[dict[str, Any]] = []

        def append_message(
            session_id: str,
            *,
            role: str,
            content: str,
            meta: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            message = {
                "id": f"m{len(recorded) + 1}",
                "session_id": session_id,
                "role": role,
                "content": content,
                "meta": meta or {},
            }
            recorded.append(message)
            return message

        recorder = TurnRecorder("session-1", "test-model", append_message=append_message)
        recorder.append_text("first note")
        recorder.start_tool({"id": "call-1", "name": "web_search", "input": {"query": "a"}})
        recorder.finish_tool(
            {
                "id": "call-1",
                "name": "web_search",
                "result": "found",
                "ok": True,
                "changed_paths": [],
            }
        )
        recorder.append_text("second note")
        recorder.start_tool({"id": "call-2", "name": "web_fetch", "input": {"url": "https://example.com"}})

        recorder.finalize(interrupted=True)

        self.assertEqual(
            [(message["role"], message["meta"].get("event")) for message in recorded],
            [
                ("assistant", None),
                ("tool", "tool_call_start"),
                ("tool", "tool_result"),
                ("assistant", None),
                ("tool", "tool_call_start"),
                ("tool", "tool_result"),
            ],
        )
        self.assertEqual(recorded[0]["content"], "first note")
        self.assertEqual(recorded[3]["content"], "second note")
        self.assertEqual(recorded[-1]["meta"]["status"], "cancelled")
        self.assertFalse(recorded[-1]["meta"]["ok"])


if __name__ == "__main__":
    unittest.main()
