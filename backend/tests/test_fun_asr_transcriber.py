from __future__ import annotations

import unittest
from pathlib import Path

from app.transcription.dashscope_fun_asr import DashScopeFunAsrTranscriber, MODEL


RAW_TRANSCRIPTS = [
    {
        "transcripts": [
            {
                "sentences": [
                    {"begin_time": 0, "end_time": 900, "speaker_id": 2, "text": "你好"},
                ]
            }
        ]
    }
]


class FunAsrTranscriberTests(unittest.TestCase):
    def test_model_is_fun_asr_and_new_task_persists_remote_id(self) -> None:
        calls: list[tuple] = []
        remote_ids: list[str] = []

        transcriber = DashScopeFunAsrTranscriber(
            api_key_provider=lambda: "secret",
            uploader=lambda key, path: calls.append(("upload", key, path)) or "https://signed.invalid/audio",
            submitter=lambda key, url, count: calls.append(("submit", key, url, count)) or "task-123",
            waiter=lambda key, task_id: calls.append(("wait", key, task_id)) or {
                "task_status": "SUCCEEDED",
                "results": [{"transcription_url": "x"}],
            },
            transcript_fetcher=lambda output: calls.append(("fetch", output["task_status"])) or RAW_TRANSCRIPTS,
        )

        result = transcriber.transcribe(Path("meeting.m4a"), on_remote_task_id=remote_ids.append)

        self.assertEqual(MODEL, "fun-asr")
        self.assertEqual(transcriber.model, "fun-asr")
        self.assertEqual(remote_ids, ["task-123"])
        self.assertEqual([call[0] for call in calls], ["upload", "submit", "wait", "fetch"])
        self.assertEqual(result.segments[0].text, "你好")
        self.assertEqual(result.raw_transcripts, RAW_TRANSCRIPTS)

    def test_resume_skips_upload_and_submit(self) -> None:
        def unexpected(*_args):
            raise AssertionError("恢复任务不能重新上传")

        transcriber = DashScopeFunAsrTranscriber(
            api_key_provider=lambda: "secret",
            uploader=unexpected,
            submitter=unexpected,
            waiter=lambda _key, task_id: {
                "task_status": "SUCCEEDED",
                "task_id": task_id,
                "results": [{"transcription_url": "x"}],
            },
            transcript_fetcher=lambda _output: RAW_TRANSCRIPTS,
        )

        result = transcriber.transcribe(Path("meeting.m4a"), remote_task_id="existing-task")

        self.assertEqual(result.segments[0].text, "你好")

    def test_missing_api_key_fails_before_external_calls(self) -> None:
        transcriber = DashScopeFunAsrTranscriber(api_key_provider=lambda: "")

        with self.assertRaisesRegex(RuntimeError, "DashScope API Key"):
            transcriber.transcribe(Path("meeting.m4a"))


if __name__ == "__main__":
    unittest.main()
