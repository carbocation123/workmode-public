from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from app.transcription.dashscope_fun_asr import Segment, TranscriptionResult
from app.transcription.workspace import TranscriptionWorkspace, WorkspaceError


class _FakeTranscriber:
    model = "fun-asr"

    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[tuple[Path, str | None]] = []

    def transcribe(
        self,
        audio_path: Path,
        *,
        remote_task_id: str | None = None,
        on_remote_task_id=None,
    ) -> TranscriptionResult:
        self.calls.append((audio_path, remote_task_id))
        if self.fail:
            raise RuntimeError("模拟转写失败")
        if on_remote_task_id and not remote_task_id:
            on_remote_task_id("remote-task-1")
        raw = {
            "transcripts": [
                {
                    "sentences": [
                        {"begin_time": 0, "end_time": 1200, "speaker_id": 4, "text": "第一句。"},
                        {"begin_time": 1300, "end_time": 2500, "speaker_id": 7, "text": "第二句。"},
                    ]
                }
            ]
        }
        return TranscriptionResult(
            raw_transcripts=[raw],
            segments=[
                Segment(seq=0, speaker_id=4, start_ms=0, end_ms=1200, text="第一句。"),
                Segment(seq=1, speaker_id=7, start_ms=1300, end_ms=2500, text="第二句。"),
            ],
        )


class TranscriptionWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "meeting-transcription"
        self.transcriber = _FakeTranscriber()
        self.workspace = TranscriptionWorkspace(self.root, transcriber=self.transcriber)
        self.workspace.initialize()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_fixed_scanner_ignores_everything_outside_output_job_directories(self) -> None:
        (self.root / "WORKMODE.md").write_text("通用工作台文件", encoding="utf-8")
        (self.root / "任意资料").mkdir()
        (self.root / "任意资料" / "meta.json").write_text("{}", encoding="utf-8")
        (self.root / "output" / "broken").mkdir()
        (self.root / "output" / "broken" / "meta.json").write_text("not-json", encoding="utf-8")

        created = self.workspace.create_job(
            filename="周会.m4a",
            source=io.BytesIO(b"audio"),
            start=False,
        )

        self.assertTrue((self.root / "tools").is_dir())
        self.assertTrue((self.root / "input").is_dir())
        self.assertTrue((self.root / "output").is_dir())
        self.assertEqual([job["id"] for job in self.workspace.list_jobs()], [created["id"]])
        self.assertTrue((self.root / "WORKMODE.md").exists())
        self.assertTrue((self.root / "任意资料" / "meta.json").exists())

    def test_job_keeps_input_and_writes_fun_asr_outputs_without_secrets(self) -> None:
        job = self.workspace.create_job(
            filename="讨论：第一轮?.m4a",
            source=io.BytesIO(b"audio-bytes"),
            title="项目周会",
            start=False,
        )

        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["model"], "fun-asr")
        input_path = self.root / job["input_path"]
        self.assertEqual(input_path.read_bytes(), b"audio-bytes")

        completed = self.workspace.run_job(job["id"])

        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["remote_task_id"], "remote-task-1")
        output_dir = self.root / completed["output_path"]
        self.assertTrue((output_dir / "transcript.txt").exists())
        self.assertTrue((output_dir / "transcript.md").exists())
        self.assertTrue((output_dir / "transcript.json").exists())
        self.assertTrue((output_dir / "asr-result.json").exists())
        transcript = json.loads((output_dir / "transcript.json").read_text(encoding="utf-8"))
        self.assertEqual([item["speaker"] for item in transcript], ["Speaker 1", "Speaker 2"])
        self.assertIn("Speaker 1：第一句。", (output_dir / "transcript.txt").read_text(encoding="utf-8"))
        self.assertNotIn("api_key", json.dumps(completed).lower())

    def test_tampered_metadata_cannot_escape_the_fixed_input_and_output_folders(self) -> None:
        untouched = self.root / "workbench-note.md"
        untouched.write_text("must survive", encoding="utf-8")
        job = self.workspace.create_job(filename="meeting.wav", source=io.BytesIO(b"audio"), start=False)
        meta_path = self.root / job["output_path"] / "meta.json"
        tampered = json.loads(meta_path.read_text(encoding="utf-8"))
        tampered["input_path"] = "workbench-note.md"
        meta_path.write_text(json.dumps(tampered), encoding="utf-8")

        self.assertEqual(self.workspace.list_jobs(), [])
        with self.assertRaises(WorkspaceError):
            self.workspace.delete_job(job["id"])
        self.assertEqual(untouched.read_text(encoding="utf-8"), "must survive")

    def test_title_update_and_recoverable_delete_move_only_the_selected_job(self) -> None:
        keep = self.root / "通用工作台笔记.md"
        keep.write_text("不能受影响", encoding="utf-8")
        first = self.workspace.create_job(filename="first.wav", source=io.BytesIO(b"1"), start=False)
        second = self.workspace.create_job(filename="second.wav", source=io.BytesIO(b"2"), start=False)

        renamed = self.workspace.rename_job(first["id"], "更清楚的标题")
        self.assertEqual(renamed["title"], "更清楚的标题")

        deleted = self.workspace.delete_job(first["id"])

        self.assertEqual([job["id"] for job in self.workspace.list_jobs()], [second["id"]])
        self.assertFalse((self.root / first["input_path"]).exists())
        self.assertTrue((self.root / second["input_path"]).exists())
        self.assertEqual(self.workspace.list_deleted()[0]["trash_id"], deleted["trash_id"])
        self.assertEqual(keep.read_text(encoding="utf-8"), "不能受影响")

        restored = self.workspace.restore_job(deleted["trash_id"])

        self.assertEqual(restored["id"], first["id"])
        self.assertTrue((self.root / first["input_path"]).exists())
        self.assertEqual({job["id"] for job in self.workspace.list_jobs()}, {first["id"], second["id"]})
        self.assertEqual(keep.read_text(encoding="utf-8"), "不能受影响")

    def test_failed_job_can_be_retried_without_reuploading_input(self) -> None:
        failing = _FakeTranscriber(fail=True)
        workspace = TranscriptionWorkspace(self.root, transcriber=failing)
        job = workspace.create_job(filename="failure.mp3", source=io.BytesIO(b"audio"), start=False)

        failed = workspace.run_job(job["id"])

        self.assertEqual(failed["status"], "failed")
        self.assertIn("模拟转写失败", failed["error"])
        original_input = self.root / failed["input_path"]
        self.assertTrue(original_input.exists())

        workspace.transcriber = self.transcriber
        retried = workspace.retry_job(job["id"], start=False)
        completed = workspace.run_job(retried["id"])

        self.assertEqual(completed["status"], "completed")
        self.assertEqual(self.transcriber.calls[0][0], original_input.resolve())

    def test_ai_derivatives_are_separate_clearable_files_and_never_replace_the_transcript(self) -> None:
        job = self.workspace.create_job(filename="meeting.wav", source=io.BytesIO(b"audio"), start=False)
        completed = self.workspace.run_job(job["id"])
        output_dir = self.root / completed["output_path"]
        original = (output_dir / "transcript.md").read_text(encoding="utf-8")

        self.workspace.save_ai_result(
            job["id"],
            kind="polish",
            content="# AI 润色稿\n\n内容\n",
            model="test-model",
        )
        self.workspace.save_ai_result(
            job["id"],
            kind="summary",
            content="# 会议总结\n\n内容\n",
            model="test-model",
        )

        results = self.workspace.read_ai_results(job["id"])
        self.assertEqual(results["polished"], "# AI 润色稿\n\n内容\n")
        self.assertEqual(results["summary"], "# 会议总结\n\n内容\n")
        self.assertEqual(results["meta"]["polish"]["model"], "test-model")
        self.assertEqual((output_dir / "transcript.md").read_text(encoding="utf-8"), original)

        self.workspace.clear_ai_result(job["id"], kind="polish")

        cleared = self.workspace.read_ai_results(job["id"])
        self.assertIsNone(cleared["polished"])
        self.assertEqual(cleared["summary"], "# 会议总结\n\n内容\n")
        self.assertFalse((output_dir / "ai-polished.md").exists())
        self.assertTrue((output_dir / "ai-summary.md").exists())

    def test_successful_retranscription_invalidates_old_ai_derivatives(self) -> None:
        job = self.workspace.create_job(filename="meeting.wav", source=io.BytesIO(b"audio"), start=False)
        self.workspace.run_job(job["id"])
        self.workspace.save_ai_result(
            job["id"],
            kind="summary",
            content="# 旧总结\n",
            model="test-model",
        )

        self.workspace.retry_job(job["id"], start=False)
        self.workspace.run_job(job["id"])

        results = self.workspace.read_ai_results(job["id"])
        self.assertIsNone(results["summary"])
        self.assertIsNone(results["meta"]["summary"])


if __name__ == "__main__":
    unittest.main()
