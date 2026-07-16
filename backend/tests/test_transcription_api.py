from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.transcription.workspace import TranscriptionWorkspace


class _Runner:
    def __init__(self) -> None:
        self.submitted: list[str] = []

    def submit(self, job_id: str) -> None:
        self.submitted.append(job_id)


class TranscriptionApiTests(unittest.TestCase):
    def setUp(self) -> None:
        from app.main import app
        from fastapi.testclient import TestClient

        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "workspace"
        self.workspace = TranscriptionWorkspace(self.root, transcriber=None)
        self.workspace.initialize()
        self.runner = _Runner()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _patches(self):
        return (
            patch("app.transcription.routes.get_transcription_workspace", return_value=self.workspace),
            patch("app.transcription.routes.get_transcription_runner", return_value=self.runner),
            patch("app.transcription.routes.get_settings"),
        )

    def test_upload_list_rename_delete_and_restore_are_sessionless(self) -> None:
        workspace_patch, runner_patch, settings_patch = self._patches()
        with workspace_patch, runner_patch, settings_patch as get_settings:
            get_settings.return_value.dashscope_api_key = "configured"
            uploaded = self.client.post(
                "/api/transcription/jobs?filename=meeting.m4a",
                content=b"audio",
                headers={"Content-Type": "audio/mp4"},
            )

            self.assertEqual(uploaded.status_code, 200, uploaded.text)
            job = uploaded.json()["job"]
            self.assertEqual(self.runner.submitted, [job["id"]])

            (self.root / "WORKMODE.md").write_text("later workbench file", encoding="utf-8")
            listed = self.client.get("/api/transcription/jobs")
            self.assertEqual([item["id"] for item in listed.json()["jobs"]], [job["id"]])

            renamed = self.client.patch(
                f"/api/transcription/jobs/{job['id']}",
                json={"title": "周会新标题"},
            )
            self.assertEqual(renamed.json()["job"]["title"], "周会新标题")

            deleted = self.client.delete(f"/api/transcription/jobs/{job['id']}")
            trash_id = deleted.json()["trash"]["trash_id"]
            self.assertEqual(self.client.get("/api/transcription/jobs").json()["jobs"], [])
            self.assertTrue((self.root / "WORKMODE.md").exists())

            restored = self.client.post(f"/api/transcription/trash/{trash_id}/restore")
            self.assertEqual(restored.json()["job"]["id"], job["id"])
            self.assertTrue((self.root / "WORKMODE.md").exists())

    def test_upload_rejects_missing_dashscope_key_before_writing_input(self) -> None:
        workspace_patch, runner_patch, settings_patch = self._patches()
        with workspace_patch, runner_patch, settings_patch as get_settings:
            get_settings.return_value.dashscope_api_key = None
            response = self.client.post(
                "/api/transcription/jobs?filename=meeting.m4a",
                content=b"audio",
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.workspace.list_jobs(), [])


if __name__ == "__main__":
    unittest.main()
