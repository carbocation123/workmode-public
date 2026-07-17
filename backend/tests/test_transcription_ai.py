from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.transcription.ai_processing import (
    TranscriptionAiError,
    TranscriptionAiProcessor,
    build_transcription_ai_processor,
)


class _CompletionRecorder:
    def __init__(self, responses: list[str]):
        self.responses = iter(responses)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return next(self.responses)


class TranscriptionAiProcessorTests(unittest.TestCase):
    def test_polish_preserves_the_source_and_forbids_inventing_facts(self) -> None:
        completion = _CompletionRecorder(["# 润色稿\n\n**Speaker 1**：项目周五交付。"])
        processor = TranscriptionAiProcessor(
            completion=completion,
            model_name="test-model",
            chunk_chars=500,
        )
        source = "**Speaker 1** `00:00–00:03`\n\n嗯，项目，项目周五交付。"

        result = processor.generate(kind="polish", title="项目周会", transcript=source)

        self.assertEqual(result, "# 润色稿\n\n**Speaker 1**：项目周五交付。\n")
        self.assertEqual(len(completion.calls), 1)
        prompts = "\n".join(completion.calls[0])
        self.assertIn("严禁编造", prompts)
        self.assertIn("保留说话人", prompts)
        self.assertIn(source, prompts)

    def test_long_summary_uses_chunk_summaries_then_one_final_reduction(self) -> None:
        source = "\n\n".join(
            [
                "**Speaker 1** `00:00–00:10`\n\n" + "第一部分讨论。" * 12,
                "**Speaker 2** `00:10–00:20`\n\n" + "第二部分讨论。" * 12,
            ]
        )
        completion = _CompletionRecorder(["片段摘要一", "片段摘要二", "# 会议总结\n\n最终摘要"])
        processor = TranscriptionAiProcessor(
            completion=completion,
            model_name="test-model",
            chunk_chars=120,
        )

        result = processor.generate(kind="summary", title="长会议", transcript=source)

        self.assertEqual(result, "# 会议总结\n\n最终摘要\n")
        self.assertEqual(len(completion.calls), 3)
        final_prompt = completion.calls[-1][1]
        self.assertIn("片段摘要一", final_prompt)
        self.assertIn("片段摘要二", final_prompt)
        self.assertIn("核心结论", final_prompt)
        self.assertIn("决定事项", final_prompt)
        self.assertIn("行动项", final_prompt)
        self.assertIn("待确认问题", final_prompt)
        self.assertIn("未明确提及", final_prompt)

    def test_empty_model_configuration_is_rejected_before_any_network_call(self) -> None:
        settings = SimpleNamespace(
            model_base_url="",
            model_api_key=None,
            model_name="test-model",
            request_timeout_seconds=120,
        )

        with self.assertRaisesRegex(TranscriptionAiError, "设置"):
            build_transcription_ai_processor(settings)


if __name__ == "__main__":
    unittest.main()
