from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


def _message(
    message_id: str,
    role: str,
    content: str,
    *,
    meta: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "id": message_id,
        "role": role,
        "content": content,
        "ts": "2026-07-10T10:00:00+00:00",
        "meta": meta or {},
    }


class HistoryRepairTest(unittest.TestCase):
    def test_repair_backs_up_and_closes_only_dangling_tool_starts(self) -> None:
        from app.history_repair import repair_stale_tool_runs

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sessions_root = root / "sessions"
            project_dir = sessions_root / "project-a"
            project_dir.mkdir(parents=True)
            history_path = project_dir / "session-1.jsonl"
            meta_path = project_dir / "session-1.meta.json"
            rows = [
                _message("u1", "user", "research"),
                _message(
                    "t1",
                    "tool",
                    "calling web_search",
                    meta={
                        "event": "tool_call_start",
                        "tool_call_id": "dangling-call",
                        "tool_name": "web_search",
                        "status": "running",
                    },
                ),
                _message("a1", "assistant", "legacy combined text"),
                _message(
                    "t2",
                    "tool",
                    "calling web_fetch",
                    meta={
                        "event": "tool_call_start",
                        "tool_call_id": "completed-call",
                        "tool_name": "web_fetch",
                        "status": "running",
                    },
                ),
                _message(
                    "t3",
                    "tool",
                    "fetched",
                    meta={
                        "event": "tool_result",
                        "tool_call_id": "completed-call",
                        "tool_name": "web_fetch",
                        "status": "done",
                        "ok": True,
                    },
                ),
            ]
            original_text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
            history_path.write_text(original_text, encoding="utf-8")
            meta_path.write_text(
                json.dumps({"id": "session-1", "message_count": len(rows)}, ensure_ascii=False),
                encoding="utf-8",
            )

            report = repair_stale_tool_runs(sessions_root, root / "backups")

            repaired = [
                json.loads(line)
                for line in history_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(report.scanned_files, 1)
            self.assertEqual(report.repaired_files, 1)
            self.assertEqual(report.inserted_results, 1)
            self.assertEqual(repaired[1]["meta"]["tool_call_id"], "dangling-call")
            self.assertEqual(repaired[2]["meta"]["status"], "cancelled")
            self.assertTrue(repaired[2]["meta"]["repaired_history"])
            self.assertEqual(repaired[3]["content"], "legacy combined text")
            self.assertEqual(json.loads(meta_path.read_text(encoding="utf-8"))["message_count"], 6)

            backup_history = next((root / "backups").rglob("session-1.jsonl"))
            self.assertEqual(backup_history.read_text(encoding="utf-8"), original_text)
            self.assertTrue(any((root / "backups").rglob("session-1.meta.json")))

            second_report = repair_stale_tool_runs(sessions_root, root / "backups")
            self.assertEqual(second_report.repaired_files, 0)
            self.assertEqual(second_report.inserted_results, 0)
            self.assertEqual(len(history_path.read_text(encoding="utf-8").splitlines()), 6)


if __name__ == "__main__":
    unittest.main()
