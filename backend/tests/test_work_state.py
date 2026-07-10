from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class WorkStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("WORKMODE_PUBLIC_DATA_DIR")
        os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.tmp.name

    def tearDown(self) -> None:
        if self.old_data_dir is None:
            os.environ.pop("WORKMODE_PUBLIC_DATA_DIR", None)
        else:
            os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.old_data_dir
        self.tmp.cleanup()

    def test_memory_write_list_read_and_fixed_index_context(self):
        from app.work_state import build_memory_context, memory_list, memory_read, memory_write

        written = memory_write(
            "demo",
            name="coding-rules",
            description="项目编码约定",
            type="protocol",
            content="使用 UTF-8；修改前先读文件。",
            scope="project",
        )
        self.assertIn("已写入", written)

        listed = memory_list("demo", scope="project")
        self.assertIn("coding-rules", listed)
        self.assertIn("项目编码约定", listed)

        read = memory_read("demo", name="coding-rules", scope="project")
        self.assertIn("使用 UTF-8", read)

        context = build_memory_context("demo")
        self.assertIn("工作记忆索引", context)
        self.assertIn("coding-rules", context)
        self.assertIn("项目编码约定", context)
        self.assertIn("工作记忆正文", context)
        self.assertIn("使用 UTF-8", context)

    def test_memory_name_rejects_path_traversal(self):
        from app.work_state import memory_write

        result = memory_write(
            "demo",
            name="../secret",
            description="bad",
            type="note",
            content="bad",
            scope="project",
        )

        self.assertIn("ERROR", result)
        self.assertFalse((Path(self.tmp.name) / "secret.json").exists())

    def test_plan_lifecycle_and_context(self):
        from app.work_state import build_plan_context, mark_step_done, plan_my_steps

        created = plan_my_steps("demo", steps=["读代码", "补工具", "跑测试"], title="工具补齐")
        self.assertIn("已创建计划", created)

        done = mark_step_done("demo", idx=2, note="project tools expanded")
        self.assertIn("已完成", done)

        context = build_plan_context("demo")
        self.assertIn("工具补齐", context)
        self.assertIn("☑ 2. 补工具", context)
        self.assertIn("☐ 3. 跑测试", context)


if __name__ == "__main__":
    unittest.main()
