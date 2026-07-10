from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class ProjectSessionManagementTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("WORKMODE_PUBLIC_DATA_DIR")
        os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.tmp.name

        from app import config, storage

        storage.settings = config.reload_settings()
        self.storage = storage
        self.workspace = Path(self.tmp.name) / "workspace"
        self.workspace.mkdir()

    def tearDown(self) -> None:
        if self.old_data_dir is None:
            os.environ.pop("WORKMODE_PUBLIC_DATA_DIR", None)
        else:
            os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.old_data_dir
        self.tmp.cleanup()

    def test_child_project_is_nested_below_nearest_registered_parent(self):
        parent_root = self.workspace / "research"
        child_root = parent_root / "paper-a"
        sibling_root = self.workspace / "standalone"
        child_root.mkdir(parents=True)
        sibling_root.mkdir()

        parent = self.storage.create_project("Research", str(parent_root))
        sibling = self.storage.create_project("Standalone", str(sibling_root))
        child = self.storage.create_project("Paper A", str(child_root))

        projects = self.storage.list_projects()
        slugs = [project.slug for project in projects]

        self.assertEqual(child.parent_slug, parent.slug)
        self.assertLess(slugs.index(parent.slug), slugs.index(child.slug))
        self.assertIn(sibling.slug, slugs)

    def test_session_can_be_renamed_and_manual_title_is_persisted(self):
        project = self.storage.create_project("Research", str(self.workspace))
        session = self.storage.create_session(project.slug)

        renamed = self.storage.update_session(session.id, title="实验记录整理")

        self.assertEqual(renamed.title, "实验记录整理")
        self.assertEqual(self.storage.get_session(session.id).title, "实验记录整理")

    def test_archiving_session_hides_it_without_deleting_jsonl(self):
        project = self.storage.create_project("Research", str(self.workspace))
        session = self.storage.create_session(project.slug)
        self.storage.append_message(session.id, role="user", content="保留这条消息")

        archived = self.storage.archive_session(session.id)

        self.assertIsNotNone(archived.deleted_at)
        self.assertEqual(self.storage.list_sessions(project.slug), [])
        jsonl_path = self.storage.sessions_dir() / project.slug / f"{session.id}.jsonl"
        self.assertTrue(jsonl_path.exists())
        self.assertIn("保留这条消息", jsonl_path.read_text(encoding="utf-8"))

    def test_archiving_project_preserves_local_folder_and_promotes_children(self):
        parent_root = self.workspace / "research"
        child_root = parent_root / "paper-a"
        child_root.mkdir(parents=True)
        marker = parent_root / "do-not-delete.txt"
        marker.write_text("user data", encoding="utf-8")
        parent = self.storage.create_project("Research", str(parent_root))
        child = self.storage.create_project("Paper A", str(child_root))

        archived = self.storage.archive_project(parent.slug)
        visible = self.storage.list_projects()
        visible_child = next(item for item in visible if item.slug == child.slug)

        self.assertIsNotNone(archived.archived_at)
        self.assertNotIn(parent.slug, [item.slug for item in visible])
        self.assertIsNone(visible_child.parent_slug)
        self.assertEqual(marker.read_text(encoding="utf-8"), "user data")


class ChatRunRegistryTest(unittest.TestCase):
    def test_cancel_marks_active_run_and_registry_rejects_duplicate(self):
        from app.chat_runs import ChatAlreadyRunningError, ChatRunRegistry

        registry = ChatRunRegistry()
        first = registry.register("session-1")

        with self.assertRaises(ChatAlreadyRunningError):
            registry.register("session-1")

        self.assertTrue(registry.cancel("session-1"))
        self.assertTrue(first.cancelled())
        self.assertFalse(registry.cancel("missing"))

        registry.unregister("session-1", first)
        second = registry.register("session-1")
        self.assertIsNot(first, second)


class ManagementApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("WORKMODE_PUBLIC_DATA_DIR")
        os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.tmp.name
        from app import config, storage
        from app.main import app
        from fastapi.testclient import TestClient

        storage.settings = config.reload_settings()
        self.client = TestClient(app)
        self.root = Path(self.tmp.name) / "api-project"
        self.root.mkdir()

    def tearDown(self) -> None:
        if self.old_data_dir is None:
            os.environ.pop("WORKMODE_PUBLIC_DATA_DIR", None)
        else:
            os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.old_data_dir
        self.tmp.cleanup()

    def create_project(self) -> dict:
        response = self.client.post(
            "/api/work/projects",
            json={"name": "API project", "root_path": str(self.root), "description": ""},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_session_patch_and_delete_contract(self):
        created = self.create_project()
        session_id = created["session"]["id"]

        renamed = self.client.patch(
            f"/api/work/sessions/{session_id}",
            json={"title": "新的会话名称"},
        )
        deleted = self.client.delete(f"/api/work/sessions/{session_id}")
        listed = self.client.get(f"/api/work/projects/{created['project']['slug']}/sessions")

        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["session"]["title"], "新的会话名称")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(listed.json()["sessions"], [])

    def test_project_delete_contract_never_deletes_local_root(self):
        created = self.create_project()
        marker = self.root / "keep.txt"
        marker.write_text("keep", encoding="utf-8")

        deleted = self.client.delete(f"/api/work/projects/{created['project']['slug']}")

        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(deleted.json()["local_files_deleted"])
        self.assertTrue(marker.exists())


if __name__ == "__main__":
    unittest.main()
