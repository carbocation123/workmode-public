from __future__ import annotations

import unittest

from app.writing.processing import ArticleProcessor, WritingProcessingError


class _CompletionRecorder:
    def __init__(self, responses: list[str]):
        self.responses = iter(responses)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return next(self.responses)


class ArticleProcessorTests(unittest.TestCase):
    def test_polish_preserves_claims_and_normalizes_common_unicode_scripts(self) -> None:
        completion = _CompletionRecorder([
            "H<sub>2</sub>O 浓度为 10^{-3} mol·L^{-1}，模型的 R^{2} 为 0.92。",
        ])
        processor = ArticleProcessor(
            completion=completion,
            model_name="test-model",
            chunk_chars=500,
        )
        source = "H2O浓度是10^-3 mol/L，模型R2为0.92。"

        result = processor.process(mode="polish", text=source)

        self.assertEqual(result, "H₂O 浓度为 10⁻³ mol·L⁻¹，模型的 R² 为 0.92。\n")
        prompts = "\n".join(completion.calls[0])
        self.assertIn("不得新增、删除或改变事实", prompts)
        self.assertIn("Unicode", prompts)
        self.assertIn("H₂O", prompts)
        self.assertIn(source, prompts)

    def test_long_audit_maps_chunks_then_synthesizes_cross_document_findings(self) -> None:
        source = "\n\n".join([
            "第一段提出该方法适用于所有场景。" + "甲" * 90,
            "第二段只报告了一个数据集的实验结果。" + "乙" * 90,
        ])
        completion = _CompletionRecorder([
            "P1：存在普适性主张。",
            "P2：证据只覆盖一个数据集。",
            "# 文章漏洞核查\n\n普适性主张的证据不足。",
        ])
        processor = ArticleProcessor(
            completion=completion,
            model_name="test-model",
            chunk_chars=120,
        )

        result = processor.process(mode="audit", text=source)

        self.assertEqual(result, "# 文章漏洞核查\n\n普适性主张的证据不足。\n")
        self.assertEqual(len(completion.calls), 3)
        self.assertIn("P1", completion.calls[0][1])
        self.assertIn("P2", completion.calls[1][1])
        final_prompt = completion.calls[-1][1]
        self.assertIn("P1：存在普适性主张", final_prompt)
        self.assertIn("P2：证据只覆盖一个数据集", final_prompt)
        self.assertIn("证据链", final_prompt)
        self.assertIn("表述一致性", final_prompt)
        self.assertIn("不得联网补充证据", "\n".join(completion.calls[-1]))

    def test_empty_text_and_unknown_mode_are_rejected_without_model_calls(self) -> None:
        completion = _CompletionRecorder([])
        processor = ArticleProcessor(completion=completion, model_name="test-model")

        with self.assertRaisesRegex(WritingProcessingError, "文字"):
            processor.process(mode="polish", text="   ")
        with self.assertRaisesRegex(WritingProcessingError, "功能"):
            processor.process(mode="summary", text="正文")  # type: ignore[arg-type]

        self.assertEqual(completion.calls, [])


if __name__ == "__main__":
    unittest.main()
