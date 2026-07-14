from __future__ import annotations

import re
import shutil
import os
import uuid
from pathlib import Path
from typing import Any

from .literature_demo_store import LiteratureDemoStore


REQUIRED_REPORT_SECTIONS = (
    "基本信息",
    "仪器与样品",
    "现象与数据",
    "作者观点",
    "证据汇总",
    "跨文献关系",
)
_CITATION_RE = re.compile(
    r"\((?:Fig\.|Table\.|Eq\.)[^)]*p\.?\s*(?:idx[._])?\d+[^)]*\)|\(p\.?\s*(?:idx[._])?\d+[^)]*\)",
    re.IGNORECASE,
)
_NUMERIC_RE = re.compile(r"(?<![#\w])(?:\d+(?:\.\d+)?|\d+\s*%|\d+\s*(?:K|eV|nm|cm|mT|G|Hz|MHz|GHz))", re.IGNORECASE)


class LiteratureArchiveError(RuntimeError):
    def __init__(self, issues: list[str]):
        super().__init__("；".join(issues))
        self.issues = issues


def verify_paper_archive(store: LiteratureDemoStore, paper_id: str) -> dict[str, Any]:
    paper = store.get_paper(paper_id)
    issues: list[str] = []
    if not paper.get("archive_filename") or paper.get("metadata_trust") != "complete":
        issues.append("首页元数据和标准档名尚未确认")
    if paper.get("status") != "ready":
        issues.append("标签、关注点和摘要尚未由用户确认")
    if not paper.get("tags"):
        issues.append("至少需要一个已登记标签")
    if not str(paper.get("focus") or "").strip():
        issues.append("用户关注点为空")
    if not str(paper.get("summary") or "").strip():
        issues.append("笔记摘要为空")

    output_value = paper.get("mineru_output_path")
    output_dir = (store.root / str(output_value)).resolve() if output_value else None
    if not output_dir or store.root not in output_dir.parents or not output_dir.is_dir():
        issues.append("MinerU 产物目录不存在")
    else:
        if not (output_dir / "full.md").is_file():
            issues.append("MinerU 产物缺少 full.md")
        if not (output_dir / "layout.json").is_file():
            issues.append("MinerU 产物缺少 layout.json")
        if not (output_dir / "images").is_dir():
            issues.append("MinerU 产物缺少 images/ 目录")
        if not list(output_dir.glob("*_content_list.json")):
            issues.append("MinerU 产物缺少 *_content_list.json")

    try:
        report_path = store.report_path(paper_id)
        report = report_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        report_path = None
        report = ""
        issues.append("客观事实抽取报告不存在")
    if report:
        for section in REQUIRED_REPORT_SECTIONS:
            if section not in report:
                issues.append(f"客观事实报告缺少“{section}”段")
        if "待主对话讨论后增补" in report or "⟨待主对话" in report:
            issues.append("跨文献关系仍是待主对话占位")
        uncited_lines: list[int] = []
        for number, line in enumerate(report.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("|") and set(stripped) <= {"|", "-", ":", " "}:
                continue
            if _NUMERIC_RE.search(stripped) and not _CITATION_RE.search(stripped):
                uncited_lines.append(number)
        if uncited_lines:
            preview = ", ".join(str(item) for item in uncited_lines[:8])
            suffix = "…" if len(uncited_lines) > 8 else ""
            issues.append(f"含数值但缺少页码/图表定位的行：{preview}{suffix}")

    return {
        "ok": not issues,
        "paper_id": paper_id,
        "issues": issues,
        "checked": {
            "metadata": True,
            "review": True,
            "mineru_artifacts": True,
            "report_sections": True,
            "citations": True,
        },
    }


def _write_processed_index(store: LiteratureDemoStore) -> None:
    processed = [
        paper for paper in store.list_papers() if paper.get("archive_location") == "文献/已处理"
    ]
    lines = [
        "# 处理结果索引",
        "",
        "> 该文件由文献归档流程根据 catalog.json 重建；修改文献记录后必须同步更新。",
        "",
        "| 标准档名 | 标题 | 年份 | 标签 | 用户关注点 |",
        "|---|---|---:|---|---|",
    ]
    tag_names = {str(tag["id"]): str(tag["name"]) for tag in store.list_tags()}
    for paper in sorted(processed, key=lambda item: str(item.get("archive_filename") or "").lower()):
        values = [
            str(paper.get("archive_filename") or ""),
            str(paper.get("title") or "").replace("|", "\\|"),
            str(paper.get("year") or ""),
            ", ".join(tag_names.get(str(tag), str(tag)) for tag in paper.get("tags", [])),
            str(paper.get("focus") or "").replace("|", "\\|"),
        ]
        lines.append("| " + " | ".join(values) + " |")
    temp = store.index_path.with_name(f".{store.index_path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    os.replace(temp, store.index_path)


def archive_paper(store: LiteratureDemoStore, paper_id: str) -> dict[str, Any]:
    verification = verify_paper_archive(store, paper_id)
    if not verification["ok"]:
        store.update_paper(paper_id, verification_status="needs_fix", stage="归档校验未通过")
        raise LiteratureArchiveError(verification["issues"])

    paper = store.get_paper(paper_id)
    if paper.get("archive_location") == "文献/已处理":
        _write_processed_index(store)
        archived = store.update_paper(
            paper_id,
            verification_status="passed",
            stage="已重新同步处理结果索引",
        )
        return {"paper": archived, "verification": verification, "index_path": str(store.index_path)}
    source_pdf = store.pdf_path(paper_id)
    source_output = (store.root / str(paper["mineru_output_path"])).resolve()
    archive_filename = str(paper["archive_filename"])
    destination_pdf = store.processed_dir / archive_filename
    destination_output = store.processed_dir / "minerU识别结果" / Path(archive_filename).stem
    if destination_pdf.exists() or destination_output.exists():
        raise LiteratureArchiveError(["已处理目录存在同名产物，拒绝覆盖"])
    destination_pdf.parent.mkdir(parents=True, exist_ok=True)
    destination_output.parent.mkdir(parents=True, exist_ok=True)

    moved_pdf = False
    moved_output = False
    try:
        shutil.move(str(source_pdf), str(destination_pdf))
        moved_pdf = True
        shutil.move(str(source_output), str(destination_output))
        moved_output = True
    except Exception:
        if moved_output and destination_output.exists() and not source_output.exists():
            shutil.move(str(destination_output), str(source_output))
        if moved_pdf and destination_pdf.exists() and not source_pdf.exists():
            shutil.move(str(destination_pdf), str(source_pdf))
        raise

    report_name = Path(str(paper["fact_report_path"])).name
    archived = store.update_paper(
        paper_id,
        archive_location="文献/已处理",
        relative_pdf_path=destination_pdf.relative_to(store.root).as_posix(),
        mineru_output_path=destination_output.relative_to(store.root).as_posix(),
        fact_report_path=(destination_output / report_name).relative_to(store.root).as_posix(),
        verification_status="passed",
        status="ready",
        stage="归档完成并已同步处理结果索引",
    )
    try:
        _write_processed_index(store)
    except Exception:
        store.update_paper(
            paper_id,
            verification_status="needs_fix",
            stage="文件已归档，但处理结果索引同步失败；可重试归档以修复",
        )
        raise
    return {"paper": archived, "verification": verification, "index_path": str(store.index_path)}
