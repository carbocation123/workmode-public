from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class FileBrowserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("WORKMODE_PUBLIC_DATA_DIR")
        os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.tmp.name

        from app import config, files, storage

        storage.settings = config.reload_settings()
        self.files = files
        self.storage = storage
        self.root = Path(self.tmp.name) / "workspace"
        self.root.mkdir()
        self.project = storage.create_project("Files", str(self.root))

    def tearDown(self) -> None:
        if self.old_data_dir is None:
            os.environ.pop("WORKMODE_PUBLIC_DATA_DIR", None)
        else:
            os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.old_data_dir
        self.tmp.cleanup()

    def test_tree_is_depth_first_with_each_directory_followed_by_its_children(self):
        (self.root / "alpha").mkdir()
        (self.root / "alpha" / "a.txt").write_text("a", encoding="utf-8")
        (self.root / "beta").mkdir()
        (self.root / "beta" / "b.txt").write_text("b", encoding="utf-8")
        (self.root / "root.txt").write_text("root", encoding="utf-8")

        entries = self.files.list_tree(self.project.slug)

        self.assertEqual(
            [entry["path"] for entry in entries],
            ["alpha", "alpha/a.txt", "beta", "beta/b.txt", "root.txt"],
        )

    def test_pdf_media_response_can_be_embedded_by_the_desktop_file_view(self):
        from app.main import app
        from fastapi.testclient import TestClient

        (self.root / "paper.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
        response = TestClient(app).get(
            f"/api/work/projects/{self.project.slug}/fs/media",
            params={"path": "paper.pdf"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.headers["content-disposition"].startswith("inline;"))
        self.assertNotEqual(response.headers.get("x-frame-options"), "DENY")
        self.assertIn("frame-ancestors", response.headers.get("content-security-policy", ""))


if __name__ == "__main__":
    unittest.main()
