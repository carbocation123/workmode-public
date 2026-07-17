from __future__ import annotations

import tempfile
import unittest
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.transcription.dashscope_fun_asr import Segment, TranscriptionResult
from app.transcription.workspace import TranscriptionWorkspace


class _Runner:
    def __init__(self) -> None:
        self.submitted: list[str] = []

    def submit(self, job_id: str) -> None:
        self.submitted.append(job_id)


class _Transcriber:
    model = "fun-asr"

    def transcribe(self, audio_path: Path, **_kwargs) -> TranscriptionResult:
        return TranscriptionResult(
            raw_transcripts=[],
            segments=[Segment(seq=0, speaker_id=1, start_ms=0, end_ms=1000, text="原始转写")],
        )


class _AiProcessor:
    model_name = "test-model"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def generate(self, *, kind: str, title: str, transcript: str) -> str:
        self.calls.append((kind, title, transcript))
        return "# AI 润色稿\n" if kind == "polish" else "# 会议总结\n"


class TranscriptionApiTests(unittest.TestCase):
    def setUp(self) -> None:
        from app.main import app
        from fastapi.testclient import TestClient

        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "workspace"
        self.workspace = TranscriptionWorkspace(self.root, transcriber=_Transcriber())
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

    def test_ai_results_can_be_generated_read_downloaded_and_cleared(self) -> None:
        job = self.workspace.create_job(filename="meeting.wav", source=io.BytesIO(b"audio"), start=False)
        self.workspace.run_job(job["id"])
        processor = _AiProcessor()
        settings = SimpleNamespace(
            model_base_url="https://model.example/v1",
            model_api_key="configured",
            model_name="test-model",
        )
        with (
            patch("app.transcription.routes.get_transcription_workspace", return_value=self.workspace),
            patch("app.transcription.routes.get_transcription_ai_processor", return_value=processor),
            patch("app.transcription.routes.get_settings", return_value=settings),
        ):
            polished = self.client.post(f"/api/transcription/jobs/{job['id']}/ai/polish")
            summarized = self.client.post(f"/api/transcription/jobs/{job['id']}/ai/summary")
            loaded = self.client.get(f"/api/transcription/jobs/{job['id']}/ai")
            downloaded = self.client.get(f"/api/transcription/jobs/{job['id']}/files/summary")
            cleared = self.client.delete(f"/api/transcription/jobs/{job['id']}/ai/polish")
            self.workspace.retry_job(job["id"], start=False)
            stale_download = self.client.get(f"/api/transcription/jobs/{job['id']}/files/summary")

        self.assertEqual(polished.status_code, 200, polished.text)
        self.assertEqual(summarized.status_code, 200, summarized.text)
        self.assertEqual(loaded.json()["polished"], "# AI 润色稿\n")
        self.assertEqual(loaded.json()["summary"], "# 会议总结\n")
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(stale_download.status_code, 409)
        self.assertEqual(cleared.json()["polished"], None)
        self.assertEqual([call[0] for call in processor.calls], ["polish", "summary"])
        self.assertIn("原始转写", processor.calls[0][2])

    def test_ai_generation_requires_a_completed_job_and_model_settings(self) -> None:
        job = self.workspace.create_job(filename="meeting.wav", source=io.BytesIO(b"audio"), start=False)
        configured = SimpleNamespace(
            model_base_url="https://model.example/v1",
            model_api_key="configured",
            model_name="test-model",
        )
        missing = SimpleNamespace(model_base_url="", model_api_key=None, model_name="test-model")
        with (
            patch("app.transcription.routes.get_transcription_workspace", return_value=self.workspace),
            patch("app.transcription.routes.get_transcription_ai_processor", return_value=_AiProcessor()),
            patch("app.transcription.routes.get_settings", return_value=configured),
        ):
            incomplete = self.client.post(f"/api/transcription/jobs/{job['id']}/ai/summary")
        with (
            patch("app.transcription.routes.get_transcription_workspace", return_value=self.workspace),
            patch("app.transcription.routes.get_settings", return_value=missing),
        ):
            unconfigured = self.client.post(f"/api/transcription/jobs/{job['id']}/ai/summary")

        self.assertEqual(incomplete.status_code, 409)
        self.assertEqual(unconfigured.status_code, 503)
        self.assertFalse((self.root / job["output_path"] / "ai-summary.md").exists())


if __name__ == "__main__":
    unittest.main()
