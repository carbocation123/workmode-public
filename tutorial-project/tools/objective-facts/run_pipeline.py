#!/usr/bin/env python3
"""Run the portable objective-facts pipeline for one PDF.

Stages:
1. Upload the PDF to MinerU and download structured parsing results.
2. Convert MinerU content blocks into page-tagged model input.
3. Send that text to an OpenAI-compatible model with the six-section prompt.

Both external transfers require separate explicit command-line consent flags.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOL_DIR.parent.parent
PROMPT_FILE = TOOL_DIR / "prompts" / "literature_summary_6sections.txt"


def run(command: list[str]) -> None:
    print("\n[RUN]", subprocess.list2cmdline(command))
    subprocess.run(command, check=True)


def find_content_list(directory: Path) -> Path | None:
    candidates = sorted(directory.glob("*_content_list.json"))
    non_v2 = [path for path in candidates if "_v2" not in path.name]
    return (non_v2 or candidates or [None])[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF 客观事实提取：MinerU → 页码预处理 → 六段式报告")
    parser.add_argument("pdf", type=Path, help="待处理 PDF")
    parser.add_argument("--output-dir", type=Path, help="输出目录；默认 papers/extracted/<pdf-stem>")
    parser.add_argument("--mineru-config", type=Path, default=TOOL_DIR / "mineru_config.json")
    parser.add_argument("--model-config", type=Path, default=TOOL_DIR / "deepseek_config.json")
    parser.add_argument("--model", help="模型名；默认读取模型配置")
    parser.add_argument("--lang", default="en", help="MinerU 文档语言，默认 en")
    parser.add_argument("--ocr", action="store_true", help="强制 MinerU OCR")
    parser.add_argument("--force", action="store_true", help="忽略已有 MinerU 缓存")
    parser.add_argument("--skip-mineru", action="store_true", help="复用 output-dir 中已有 MinerU 结果")
    parser.add_argument("--allow-mineru-upload", action="store_true",
                        help="确认把原始 PDF 上传到 MinerU")
    parser.add_argument("--allow-model-send", action="store_true",
                        help="确认把页码化文献文本发送到模型服务")
    parser.add_argument("--dry-run", action="store_true", help="只显示计划，不读取密钥、不访问网络")
    args = parser.parse_args()

    pdf = args.pdf.resolve()
    if not pdf.is_file():
        parser.error(f"PDF 不存在: {pdf}")
    output_dir = (args.output_dir or (
        PROJECT_ROOT / "papers" / "extracted" / pdf.stem
    )).resolve()
    prepared = output_dir / f"{pdf.stem}_prepared.txt"
    report = output_dir / f"{pdf.stem}_客观事实抽取报告_v2.md"
    manifest = output_dir / "batch_manifest.json"

    print("客观事实提取计划")
    print(f"  PDF:      {pdf}")
    print(f"  输出目录: {output_dir}")
    print(f"  页码输入: {prepared}")
    print(f"  最终报告: {report}")
    print(f"  MinerU:   {'复用已有结果' if args.skip_mineru else '上传并解析'}")
    print("  模型服务: 发送页码化文本，使用六段式提示词")

    if args.dry_run:
        print("\n[DRY] 未读取配置、未上传 PDF、未发送文献文本。")
        return 0
    if not args.skip_mineru and not args.allow_mineru_upload:
        parser.error("需要 --allow-mineru-upload 才能把 PDF 上传到 MinerU")
    if not args.allow_model_send:
        parser.error("需要 --allow-model-send 才能把文献文本发送到模型服务")

    output_dir.mkdir(parents=True, exist_ok=True)
    if not args.skip_mineru:
        command = [
            sys.executable, str(TOOL_DIR / "pdf2md.py"), str(pdf),
            "--output-dir", str(output_dir),
            "--config", str(args.mineru_config),
            "--lang", args.lang,
            "--yes-upload",
        ]
        if args.ocr:
            command.append("--ocr")
        if args.force:
            command.append("--force")
        run(command)

    if not find_content_list(output_dir):
        raise SystemExit(f"未找到 MinerU *_content_list.json: {output_dir}")

    run([
        sys.executable, str(TOOL_DIR / "prep_paper_for_deepseek.py"),
        str(output_dir), "-o", str(prepared),
    ])

    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    job = [{
        "id": pdf.stem,
        "prompt": prompt,
        "input_file": str(prepared),
        "output_file": str(report),
    }]
    with tempfile.TemporaryDirectory(prefix="workmode-objective-facts-") as temp_dir:
        jobs_file = Path(temp_dir) / "job.json"
        jobs_file.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        command = [
            sys.executable, str(TOOL_DIR / "deepseek_batch.py"),
            "--jobs", str(jobs_file),
            "--output-dir", str(output_dir),
            "--manifest", str(manifest),
            "--config", str(args.model_config),
            "--concurrency", "1",
            "--yes-send",
        ]
        if args.model:
            command.extend(["--model", args.model])
        run(command)

    print("\n[DONE]")
    print(f"  报告: {report}")
    print(f"  记录: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
