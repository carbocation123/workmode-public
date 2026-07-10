#!/usr/bin/env python3
"""prep_paper_for_deepseek.py

把一个 MinerU 解析结果文件夹合并成单个 DeepSeek 友好的输入文本：
- 顺序遍历 `*_content_list.json`
- 用 `page_number` block 建立 page_idx → 印刷页码 的映射
- 每个 text/list/image/table 前缀 `[p.PRINTED]` 引用标签
- 图表带 caption / footnote，跳过实际图像；表格保留 caption + 简化的 HTML body
- 丢弃 header / footer / page_number / aside_text 噪音

用法：
    py -3.11 prep_paper_for_deepseek.py <mineru_dir> [-o <out.txt>]

或批量：
    py -3.11 prep_paper_for_deepseek.py --batch <papers_dir> -o <out_dir>

批量模式：扫描 papers_dir 下每个子目录，找含 `*_content_list.json` 的，输出
`<out_dir>/<stem>.txt`。

输出文件可直接喂给 `deepseek_batch.py --inputs ...`。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional


def find_content_list(mineru_dir: Path) -> Optional[Path]:
    candidates = list(mineru_dir.glob("*_content_list.json"))
    # 优先非 _v2 版本（v2 偶尔结构略不同）
    non_v2 = [c for c in candidates if "_v2" not in c.name]
    return (non_v2 or candidates or [None])[0]


def build_page_map(blocks: list[dict]) -> dict[int, str]:
    """page_idx → 印刷页码字符串。若该页未识别出印刷页码，留空。"""
    pm: dict[int, str] = {}
    for b in blocks:
        if b.get("type") != "page_number":
            continue
        txt = (b.get("text") or "").strip()
        # 印刷页码通常就是 1-5 位数字，偶尔带 'S' 等前缀
        m = re.match(r"^[A-Za-z]?\d{1,5}$", txt)
        if m:
            pm[b["page_idx"]] = txt
    return pm


def page_tag(page_idx: int, page_map: dict[int, str]) -> str:
    printed = page_map.get(page_idx)
    if printed:
        return f"[p.{printed}]"
    # fallback: 物理页号 + 1（PDF 第一页 = page1）
    return f"[p_idx.{page_idx + 1}]"


def caption_text(cap) -> str:
    if isinstance(cap, list):
        return " ".join(str(x) for x in cap if x).strip()
    return (cap or "").strip() if isinstance(cap, str) else ""


def render_block(b: dict, page_map: dict[int, str]) -> Optional[str]:
    t = b.get("type")
    pidx = b.get("page_idx", 0)
    tag = page_tag(pidx, page_map)

    # 首页 header/footer/aside 常含期刊名、卷、年、页、DOI — 保留并明确标记
    # 后续页的多为 running head / 版权声明，丢弃
    if t in ("header", "footer", "aside_text") and pidx == 0:
        text = (b.get("text") or "").strip()
        if text:
            kind = t.upper().replace("ASIDE_TEXT", "ASIDE")
            return f"{tag} [META-{kind}] {text}"
        return None

    if t in ("header", "footer", "page_number", "aside_text"):
        return None

    if t in ("text", "list"):
        text = (b.get("text") or "").strip()
        if not text:
            return None
        level = b.get("text_level")
        if level:
            # 标题块：用 markdown # 标记，便于 LLM 识别小节边界
            return f"{tag} {'#' * min(level, 6)} {text}"
        return f"{tag} {text}"

    if t == "image":
        cap = caption_text(b.get("image_caption"))
        fn = caption_text(b.get("image_footnote"))
        parts = [f"{tag} [IMAGE]"]
        if cap:
            parts.append(f"caption: {cap}")
        if fn:
            parts.append(f"footnote: {fn}")
        return " ".join(parts) if (cap or fn) else f"{tag} [IMAGE: 未识别 caption]"

    if t == "table":
        cap = caption_text(b.get("table_caption"))
        fn = caption_text(b.get("table_footnote"))
        body = (b.get("table_body") or "").strip()
        parts = [f"{tag} [TABLE]"]
        if cap:
            parts.append(f"caption: {cap}")
        if fn:
            parts.append(f"footnote: {fn}")
        if body:
            # 保留原始 HTML 给 LLM —— DeepSeek 能识别简单 HTML 表
            parts.append(f"body:\n{body}")
        return "\n".join(parts)

    if t == "chart":
        cap = caption_text(b.get("image_caption")) or caption_text(b.get("caption"))
        return f"{tag} [CHART] caption: {cap}" if cap else f"{tag} [CHART]"

    if t == "equation":
        text = (b.get("text") or "").strip()
        return f"{tag} [EQ] {text}" if text else None

    # 未知类型 —— 保留 text 字段
    text = (b.get("text") or "").strip()
    if text:
        return f"{tag} [{t}] {text}"
    return None


def process_paper(mineru_dir: Path, parser_label: str = "MinerU Precise") -> str:
    cl = find_content_list(mineru_dir)
    if not cl:
        raise FileNotFoundError(f"未找到 *_content_list.json: {mineru_dir}")

    with cl.open(encoding="utf-8") as f:
        blocks = json.load(f)

    page_map = build_page_map(blocks)
    n_pages = max((b.get("page_idx", 0) for b in blocks), default=-1) + 1

    header_lines = [
        f"# 文献来源标识: {mineru_dir.name}",
        f"# 解析来源: {parser_label}; 共 {n_pages} 页, {len(blocks)} 个 block",
        f"# 页码映射 (page_idx -> 印刷页码): {page_map}" if page_map else "# 警告: 未识别印刷页码, 使用 p_idx 编号",
        "",
    ]
    body_lines: list[str] = []
    for b in blocks:
        rendered = render_block(b, page_map)
        if rendered:
            body_lines.append(rendered)
    return "\n".join(header_lines + body_lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mineru_dir", nargs="?", help="单个 MinerU 输出目录")
    ap.add_argument("--batch", help="批量模式: 此目录下每个含 _content_list.json 的子目录都处理")
    ap.add_argument("-o", "--output", help="单文件模式: 输出路径; 批量模式: 输出目录")
    ap.add_argument("--parser-label", default="MinerU Precise",
                    help="写入输出头的解析来源标签；教学快照必须明确标注非 API 结果")
    args = ap.parse_args()

    if args.batch:
        batch_dir = Path(args.batch)
        if not batch_dir.is_dir():
            print(f"错误: {batch_dir} 不是目录", file=sys.stderr)
            return 2
        out_dir = Path(args.output or (batch_dir / "_deepseek_inputs"))
        out_dir.mkdir(parents=True, exist_ok=True)

        # 找所有含 *_content_list.json 的子目录
        targets: list[Path] = []
        for sub in sorted(batch_dir.iterdir()):
            if sub.is_dir() and find_content_list(sub):
                targets.append(sub)

        print(f"批量: 共 {len(targets)} 个文献待处理", file=sys.stderr)
        ok = 0
        for sub in targets:
            try:
                text = process_paper(sub, parser_label=args.parser_label)
                out = out_dir / f"{sub.name}.txt"
                out.write_text(text, encoding="utf-8")
                size_kb = out.stat().st_size / 1024
                print(f"  [OK] {sub.name} -> {out.name} ({size_kb:.1f} KB)", file=sys.stderr)
                ok += 1
            except Exception as e:
                print(f"  [FAIL] {sub.name}: {e}", file=sys.stderr)
        print(f"完成: {ok}/{len(targets)} 成功; 输出 -> {out_dir}", file=sys.stderr)
        return 0 if ok == len(targets) else 1

    if not args.mineru_dir:
        ap.print_help()
        return 2

    mineru_dir = Path(args.mineru_dir)
    if not mineru_dir.is_dir():
        print(f"错误: {mineru_dir} 不是目录", file=sys.stderr)
        return 2

    text = process_paper(mineru_dir, parser_label=args.parser_label)
    if args.output:
        out = Path(args.output)
        out.write_text(text, encoding="utf-8")
        print(f"写入: {out} ({out.stat().st_size / 1024:.1f} KB)", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
