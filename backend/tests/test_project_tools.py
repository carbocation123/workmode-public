from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from app.project_tools import execute_project_tool_at_root


class ProjectToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_tool(self, name: str, **args):
        return execute_project_tool_at_root(self.root, name, args)

    def test_project_read_supports_line_window_and_rejects_escape(self):
        (self.root / "notes.md").write_text("a\nb\nc\nd\n", encoding="utf-8")

        result = self.run_tool("project_read", path="notes.md", offset=1, limit=2)

        self.assertTrue(result.ok)
        self.assertIn("2\tb", result.content)
        self.assertIn("3\tc", result.content)

        escaped = self.run_tool("project_read", path="../outside.txt")
        self.assertFalse(escaped.ok)
        self.assertIn("路径越界", escaped.content)

    def test_project_edit_requires_unique_match_unless_replace_all(self):
        target = self.root / "src.py"
        target.write_text("print('x')\nprint('x')\n", encoding="utf-8")

        result = self.run_tool(
            "project_edit",
            path="src.py",
            old_string="print('x')",
            new_string="print('y')",
        )
        self.assertFalse(result.ok)
        self.assertIn("非唯一", result.content)

        replaced = self.run_tool(
            "project_edit",
            path="src.py",
            old_string="print('x')",
            new_string="print('y')",
            replace_all=True,
        )
        self.assertTrue(replaced.ok)
        self.assertEqual(target.read_text(encoding="utf-8"), "print('y')\nprint('y')\n")
        self.assertEqual(replaced.changed_paths, ["src.py"])

    def test_project_write_rejects_secret_env_files(self):
        result = self.run_tool("project_write", path=".env", content="SECRET=1\n")

        self.assertFalse(result.ok)
        self.assertFalse((self.root / ".env").exists())
        self.assertIn("敏感配置文件", result.content)

    def test_project_grep_finds_text_and_skips_binary(self):
        (self.root / "src").mkdir()
        (self.root / "src" / "main.py").write_text("def target():\n    return 1\n", encoding="utf-8")
        (self.root / "blob.bin").write_bytes(b"\x00target\x00")

        result = self.run_tool(
            "project_grep",
            pattern="target",
            path="src",
            output_mode="content",
        )

        self.assertTrue(result.ok)
        self.assertIn("src/main.py:1", result.content)
        self.assertNotIn("blob.bin", result.content)

    def test_project_bash_runs_in_project_root_and_blocks_dangerous_commands(self):
        result = self.run_tool("project_bash", command="git reset --hard")
        self.assertFalse(result.ok)
        self.assertIn("黑名单", result.content)

        safe = self.run_tool("project_bash", command="echo hello")
        self.assertTrue(safe.ok)
        self.assertIn("exit_code: 0", safe.content)
        self.assertIn("hello", safe.content)

    def test_project_python_runs_in_project_root(self):
        result = self.run_tool(
            "project_python",
            code="from pathlib import Path\nPath('made_by_python.txt').write_text('ok', encoding='utf-8')\nprint(Path.cwd().name)",
        )

        self.assertTrue(result.ok)
        self.assertIn("exit_code: 0", result.content)
        self.assertEqual((self.root / "made_by_python.txt").read_text(encoding="utf-8"), "ok")

    def test_project_python_file_runs_project_script_with_bundled_interpreter(self):
        script = self.root / "tools" / "runner.py"
        script.parent.mkdir()
        script.write_text(
            "from pathlib import Path\n"
            "import sys\n"
            "Path('script-args.txt').write_text('|'.join(sys.argv[1:]), encoding='utf-8')\n"
            "print(Path.cwd().name)\n",
            encoding="utf-8",
        )

        result = self.run_tool(
            "project_python_file",
            path="tools/runner.py",
            args=["first value", "第二项"],
        )

        self.assertTrue(result.ok)
        self.assertIn("exit_code: 0", result.content)
        self.assertEqual(
            (self.root / "script-args.txt").read_text(encoding="utf-8"),
            "first value|第二项",
        )

        escaped = self.run_tool("project_python_file", path="../outside.py")
        self.assertFalse(escaped.ok)
        self.assertIn("路径越界", escaped.content)

    def test_project_python_can_be_cancelled_while_running(self):
        cancel_event = threading.Event()

        def cancel_soon() -> None:
            time.sleep(0.2)
            cancel_event.set()

        threading.Thread(target=cancel_soon, daemon=True).start()
        started = time.monotonic()
        result = execute_project_tool_at_root(
            self.root,
            "project_python",
            {"code": "import time\ntime.sleep(10)\nprint('too late')", "timeout": 15},
            cancel_event=cancel_event,
        )

        self.assertFalse(result.ok)
        self.assertIn("停止", result.content)
        self.assertLess(time.monotonic() - started, 3)


if __name__ == "__main__":
    unittest.main()
