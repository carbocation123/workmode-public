from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from .unicode_scripts import normalize_unicode_scripts
from .skill_loader import load_writing_skill


WritingMode = Literal["polish", "audit"]
Completion = Callable[[str, str], str]


class WritingProcessingError(Exception):
    """A safe failure that can be shown directly in the article tool."""


def _clean_result(value: str) -> str:
    cleaned = normalize_unicode_scripts(value.strip())
    if not cleaned:
        raise WritingProcessingError("AI 模型返回了空结果，请稍后重试")
    return cleaned + "\n"


def _plain_chunks(text: str, max_chars: int) -> list[str]:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not paragraphs:
        return []
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        pieces = [paragraph[index:index + max_chars] for index in range(0, len(paragraph), max_chars)]
        for piece in pieces:
            candidate = f"{current}\n\n{piece}" if current else piece
            if current and len(candidate) > max_chars:
                chunks.append(current)
                current = piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def _numbered_chunks(text: str, max_chars: int) -> list[str]:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not paragraphs:
        return []
    numbered: list[str] = []
    for index, paragraph in enumerate(paragraphs, start=1):
        pieces = [paragraph[offset:offset + max_chars] for offset in range(0, len(paragraph), max_chars)]
        for piece_index, piece in enumerate(pieces, start=1):
            suffix = f"（续 {piece_index}）" if len(pieces) > 1 else ""
            numbered.append(f"P{index}{suffix}\n{piece}")

    chunks: list[str] = []
    current = ""
    for paragraph in numbered:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


class ArticleProcessor:
    def __init__(
        self,
        *,
        completion: Completion,
        model_name: str,
        chunk_chars: int = 12_000,
    ):
        self.completion = completion
        self.model_name = model_name
        self.chunk_chars = max(100, int(chunk_chars))

    def process(self, *, mode: WritingMode, text: str) -> str:
        if mode not in {"polish", "audit"}:
            raise WritingProcessingError("不支持的文章处理功能")
        if not text.strip():
            raise WritingProcessingError("请先输入需要处理的文字")
        if mode == "polish":
            return self._polish(text)
        return self._audit(text)

    def _polish(self, text: str) -> str:
        chunks = _plain_chunks(text, self.chunk_chars)
        system = (
            "你是严谨的学术文字编辑。只润色用户提供的文字，不得新增、删除或改变事实、数字、"
            "专有名词、引用关系、因果方向、结论强度或作者立场。无法确定的内容保持原样。"
            "改善语法、措辞、简洁度和逻辑衔接，但不要解释修改过程。"
            "化学式、数学指数、单位和变量下标优先使用可直接粘贴到 Word 的 Unicode 上下标字符，"
            "例如 H₂O、CO₂、10⁻³ mol·L⁻¹、R²、xᵢ；不要输出 HTML、LaTeX 或 SUP/SUB 标记。"
            "方括号引用编号不是数学上标，不要改变。只输出润色后的正文。"
            "\n\n" + load_writing_skill("polish")
        )
        results: list[str] = []
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            user = (
                f"这是待润色文字的第 {index}/{total} 段。保持原意和段落结构，直接输出润色稿。\n\n"
                f"{chunk}"
            )
            results.append(_clean_result(self.completion(system, user)).strip())
        return _clean_result("\n\n".join(results))

    def _audit(self, text: str) -> str:
        chunks = _numbered_chunks(text, self.chunk_chars)
        system = (
            "你是科研文章内部审查员。只能依据用户提供的文章检查，不得联网补充证据，不得假装核验了"
            "外部文献，也不得凭常识补写作者没有提供的事实。重点查找：主张与证据不匹配、结论强于证据、"
            "逻辑跳跃、前后矛盾、概念或术语混用、缩写不一致、数字/单位/符号不一致。引用具体位置时使用"
            "输入中的 P 编号。化学式、指数、单位和变量下标使用 H₂O、10⁻³、R²、xᵢ 这样的 Unicode 字符。"
            "\n\n" + load_writing_skill("audit")
        )
        if len(chunks) == 1:
            user = (
                "核查下面全文。输出固定 Markdown 结构：# 文章漏洞核查、## 总体判断、## 证据链、"
                "## 表述一致性、## 数字与单位、## 待作者确认。每个问题写明位置、原文、问题和建议；"
                "没有发现的问题明确写“未发现明确问题”。不要重写全文。\n\n"
                f"{chunks[0]}"
            )
            return _clean_result(self.completion(system, user))

        partials: list[str] = []
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            user = (
                f"这是全文的第 {index}/{total} 个分块。提取可供最终汇总的局部核查记录：逐项保留 P 编号、"
                "原文要点、证据链问题、表述/术语不一致、数字或单位问题。不要下全文结论。\n\n"
                f"{chunk}"
            )
            partials.append(_clean_result(self.completion(system, user)).strip())

        joined = "\n\n".join(
            f"### 分块 {index}\n{partial}" for index, partial in enumerate(partials, start=1)
        )
        final_user = (
            "下面是按全文段落编号生成的局部核查记录。请跨分块合并重复问题，并检查证据链与表述一致性。"
            "输出固定 Markdown 结构：# 文章漏洞核查、## 总体判断、## 证据链、## 表述一致性、"
            "## 数字与单位、## 待作者确认。每个问题保留 P 编号，说明问题与修改建议；不要编造原文或"
            "外部证据，不要重写全文。\n\n"
            f"{joined}"
        )
        return _clean_result(self.completion(system, final_user))
