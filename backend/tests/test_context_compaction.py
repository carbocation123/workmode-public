from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path


class ContextWindowTest(unittest.TestCase):
    def test_window_starts_from_legal_user_and_keeps_tool_pair_suffix(self):
        from app.context_window import build_context_window
        from app.session_compactor import SUMMARY_PREFIX

        messages = [
            {"role": "user", "content": "old user"},
            {"role": "assistant", "content": "old assistant"},
            {"role": "user", "content": "run tool"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call-1"}]},
            {"role": "tool", "tool_call_id": "call-1", "content": "tool result"},
            {"role": "user", "content": "latest"},
        ]

        window = build_context_window(
            system_prompt="system",
            tool_schemas=[],
            messages=messages,
            total_budget_tokens=45,
            summary_prefix=SUMMARY_PREFIX,
            text_token_counter=lambda _text: 1,
            message_token_counter=lambda _message: 10,
        )

        self.assertEqual(window.messages[0]["role"], "user")
        self.assertEqual(window.messages[0]["content"], "run tool")
        self.assertEqual(window.messages[2]["role"], "tool")
        self.assertTrue(window.usage["truncated"])
        self.assertEqual(window.usage["history_messages_included"], 4)


class SessionCompactorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("WORKMODE_PUBLIC_DATA_DIR")
        os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.tmp.name

        from app import config, storage

        storage.settings = config.reload_settings()
        self.storage = storage
        self.project_root = Path(self.tmp.name) / "project"
        self.project_root.mkdir()
        self.project = storage.create_project("demo", str(self.project_root))
        self.session = storage.create_session(self.project.slug)

    def tearDown(self) -> None:
        if self.old_data_dir is None:
            os.environ.pop("WORKMODE_PUBLIC_DATA_DIR", None)
        else:
            os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.old_data_dir
        self.tmp.cleanup()

    def test_compact_inserts_marker_without_deleting_history(self):
        from app.session_compactor import SUMMARY_PREFIX, compact_session, messages_visible_to_llm

        for index in range(1, 6):
            self.storage.append_message(self.session.id, role="user", content=f"用户请求 {index}")
            self.storage.append_message(self.session.id, role="assistant", content=f"助手回复 {index}")
        self.storage.append_message(
            self.session.id,
            role="tool",
            content="调用 project_read…",
            meta={
                "event": "tool_call_start",
                "tool_call_id": "call-read",
                "tool_name": "project_read",
                "args": {"path": "README.md"},
            },
        )
        self.storage.append_message(
            self.session.id,
            role="tool",
            content="README 内容预览",
            meta={
                "event": "tool_result",
                "tool_call_id": "call-read",
                "tool_name": "project_read",
                "ok": True,
            },
        )
        original = self.storage.read_messages(self.session.id, limit=0)

        async def fake_summarizer(_messages, _extra_instruction):
            return "## 1. 主要请求与意图\n用户在测试压缩。\n\n## 8. 当前工作与下一步\n继续测试。"

        result = asyncio.run(compact_session(self.session.id, keep_recent=4, summarizer=fake_summarizer))
        rows = self.storage.read_messages(self.session.id, limit=0)
        visible = messages_visible_to_llm(rows)

        self.assertEqual(result.original_message_count, len(original))
        self.assertEqual(len(rows), len(original) + 1)
        self.assertEqual(visible[0]["role"], "system")
        self.assertTrue(visible[0]["content"].startswith(SUMMARY_PREFIX))
        self.assertIn("用户在测试压缩", visible[0]["content"])
        self.assertTrue(any(row["content"] == "用户请求 1" for row in rows))


if __name__ == "__main__":
    unittest.main()
