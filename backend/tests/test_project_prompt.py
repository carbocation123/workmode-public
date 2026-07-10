from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class ProjectPromptTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("WORKMODE_PUBLIC_DATA_DIR")
        os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.tmp.name

        from app import config, storage

        storage.settings = config.reload_settings()
        self.storage = storage
        self.root = Path(self.tmp.name) / "tutorial"
        self.root.mkdir()
        self.project = storage.create_project("Tutorial", str(self.root))

    def tearDown(self) -> None:
        if self.old_data_dir is None:
            os.environ.pop("WORKMODE_PUBLIC_DATA_DIR", None)
        else:
            os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.old_data_dir
        self.tmp.cleanup()

    def test_workmode_file_is_a_project_only_system_prompt(self):
        from app.prompt import SYSTEM_BASE, build_system_prompt

        guide = self.root / "TUTORIAL_AI_GUIDE.md"
        guide.write_text("工作不是目的，演示才是目的。", encoding="utf-8")
        (self.root / "WORKMODE.md").write_text(
            "# 教程项目主持要求\n@TUTORIAL_AI_GUIDE.md\n",
            encoding="utf-8",
        )

        prompt, usage = build_system_prompt(self.project)

        self.assertNotIn("工作不是目的，演示才是目的", SYSTEM_BASE)
        self.assertIn("## 项目级提示词（仅当前项目）", prompt)
        self.assertIn("# 教程项目主持要求", prompt)
        self.assertIn("工作不是目的，演示才是目的", prompt)
        self.assertEqual(usage["project_prompt_file"], "WORKMODE.md")
        self.assertGreater(usage["project_prompt_tokens"], 0)
        self.assertGreater(usage["project_prompt_total_tokens"], usage["project_prompt_tokens"])
        self.assertEqual(
            [item["path"] for item in usage["project_prompt_imported_files"]],
            ["TUTORIAL_AI_GUIDE.md"],
        )
        self.assertIn(
            "TUTORIAL_AI_GUIDE.md",
            [item["path"] for item in usage["imported_files"]],
        )

    def test_project_without_workmode_file_has_no_project_prompt(self):
        from app.prompt import build_system_prompt

        prompt, usage = build_system_prompt(self.project)

        self.assertNotIn("## 项目级提示词（仅当前项目）", prompt)
        self.assertIsNone(usage["project_prompt_file"])
        self.assertEqual(usage["project_prompt_tokens"], 0)
        self.assertEqual(usage["project_prompt_imported_files"], [])


if __name__ == "__main__":
    unittest.main()
