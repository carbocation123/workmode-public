from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TutorialProjectTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("WORKMODE_PUBLIC_DATA_DIR")
        os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.tmp.name

        from app import config, storage

        storage.settings = config.reload_settings()
        self.storage = storage
        self.parent = Path(self.tmp.name) / "workspace"
        self.parent.mkdir()
        self.template = Path(self.tmp.name) / "template"
        (self.template / "notes").mkdir(parents=True)
        (self.template / "WORKMODE_TUTORIAL.json").write_text(
            json.dumps({"kind": "workmode-public-tutorial", "template_version": 1}),
            encoding="utf-8",
        )
        (self.template / "WORKMODE.md").write_text("@notes/demo-state.md\n", encoding="utf-8")
        (self.template / "notes" / "demo-state.md").write_text("- [ ] 0.1 项目地图\n", encoding="utf-8")
        (self.template / "draft.md").write_text("initial\n", encoding="utf-8")

    def tearDown(self) -> None:
        if self.old_data_dir is None:
            os.environ.pop("WORKMODE_PUBLIC_DATA_DIR", None)
        else:
            os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.old_data_dir
        self.tmp.cleanup()

    def test_install_and_reset_restore_template_while_archiving_state(self):
        from app import work_state
        from app.tutorial_project import install_tutorial_project, reset_tutorial_project

        installed = install_tutorial_project(str(self.parent), template_root=self.template)
        root = Path(installed.project.root_path)
        original_session = installed.session

        self.assertTrue(installed.project_is_tutorial)
        self.assertEqual((root / "draft.md").read_text(encoding="utf-8"), "initial\n")

        (root / "draft.md").write_text("changed\n", encoding="utf-8")
        (root / "generated.txt").write_text("generated\n", encoding="utf-8")
        self.storage.write_project_memory(installed.project.slug, "temporary memory")
        work_state.memory_write(
            installed.project.slug,
            name="tutorial-note",
            description="test",
            type="note",
            content="temporary structured memory",
        )
        work_state.plan_my_steps(installed.project.slug, title="tutorial plan", steps=["step one"])
        self.storage.append_message(original_session.id, role="user", content="start")

        reset = reset_tutorial_project(installed.project.slug, template_root=self.template)

        self.assertEqual((root / "draft.md").read_text(encoding="utf-8"), "initial\n")
        self.assertFalse((root / "generated.txt").exists())
        self.assertEqual(self.storage.read_memory(installed.project.slug)["project"], "")
        self.assertEqual(work_state.build_memory_context(installed.project.slug), "")
        self.assertEqual(work_state.build_plan_context(installed.project.slug), "")
        self.assertEqual([item.id for item in self.storage.list_sessions(installed.project.slug)], [reset.session.id])
        archived_jsonl = self.storage.sessions_dir() / installed.project.slug / f"{original_session.id}.jsonl"
        self.assertTrue(archived_jsonl.exists())
        self.assertIn("start", archived_jsonl.read_text(encoding="utf-8"))
        self.assertEqual((reset.backup_dir / "project-files" / "draft.md").read_text(encoding="utf-8"), "changed\n")
        self.assertEqual((reset.backup_dir / "project-memory.md").read_text(encoding="utf-8"), "temporary memory")

    def test_reset_rejects_an_ordinary_project(self):
        from app.tutorial_project import TutorialProjectError, reset_tutorial_project

        root = self.parent / "ordinary"
        root.mkdir()
        (root / "WORKMODE_TUTORIAL.json").write_text(
            json.dumps({"kind": "workmode-public-tutorial", "template_version": 1}),
            encoding="utf-8",
        )
        project = self.storage.create_project("Ordinary", str(root))

        with self.assertRaises(TutorialProjectError):
            reset_tutorial_project(project.slug, template_root=self.template)

    def test_tutorial_api_installs_and_resets_only_marked_project(self):
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        with patch("app.tutorial_project.DEFAULT_TEMPLATE_ROOT", self.template):
            installed = client.post("/api/work/tutorial-project", json={"parent_path": str(self.parent)})

            self.assertEqual(installed.status_code, 200, installed.text)
            project = installed.json()["project"]
            self.assertTrue(project["is_tutorial"])
            root = Path(project["root_path"])
            (root / "draft.md").write_text("changed through api\n", encoding="utf-8")

            reset = client.post(f"/api/work/projects/{project['slug']}/reset-tutorial")

        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertEqual((root / "draft.md").read_text(encoding="utf-8"), "initial\n")
        self.assertEqual(reset.json()["session"]["message_count"], 0)
        self.assertTrue(Path(reset.json()["backup_path"]).is_dir())


if __name__ == "__main__":
    unittest.main()
