#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf2md.py — 用 MinerU Precise Extract API 把 PDF 转成 Markdown、图片和结构化 JSON。

工作流:
  1) 读环境变量 MINERU_API_KEY 或本目录 mineru_config.json
  2) POST /api/v4/file-urls/batch (Bearer)            → 拿到 task_id + upload_url
  3) PUT 文件到 upload_url
  4) 轮询 GET /api/v4/extract/task/{task_id}          → done 时拿 full_zip_url
  5) 下载 ZIP → 解压到 <pdf_parent>/minerU识别结果/<stem>/
     ZIP 内含:full.md、layout.json、_content_list.json、_model.json、images/

为避免用户误把“读取本地文件”理解成“允许上传”，实际调用必须显式传入
`--yes-upload`。`--dry-run` 只显示计划，不读取密钥、不访问网络。

用法:
  py -3.11 pdf2md.py <pdf_path> --yes-upload
  py -3.11 pdf2md.py <pdf_path> --dry-run
  py -3.11 pdf2md.py <pdf_path> --force                  # 忽略缓存,重新解析
  py -3.11 pdf2md.py <pdf_path> --lang en                # 中文 PDF 用 ch
  py -3.11 pdf2md.py <pdf_path> --model vlm              # 切换到 vlm 模型(默认 pipeline)
  py -3.11 pdf2md.py <pdf_path> --ocr                    # 强制 OCR(扫描版 PDF)

环境:Python 3.11+ 标准库(urllib + zipfile + json + argparse)。无需 pip 包。
"""

import sys
import os
import json
import time
import argparse
import zipfile
import io
from pathlib import Path
from urllib import request, error


DEFAULT_API_BASE = "https://mineru.net/api/v4"
TOOL_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILE = TOOL_DIR / "mineru_config.json"
POLL_INTERVAL = 5
POLL_TIMEOUT = 900   # 15 min - Precise 模型解析较慢


def load_config(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    env_key = os.environ.get("MINERU_API_KEY") or os.environ.get("WORKMODE_MINERU_API_KEY")
    if env_key:
        cfg["api_key"] = env_key
    env_base = os.environ.get("MINERU_API_BASE") or os.environ.get("WORKMODE_MINERU_API_BASE")
    if env_base:
        cfg["api_base"] = env_base
    key = cfg.get("api_key", "")
    if not key or key.startswith("<"):
        sys.exit(
            "未找到 MinerU API key。请复制 mineru_config.example.json 为 "
            "mineru_config.json 并仅在本机填写，或设置 MINERU_API_KEY。"
        )
    return cfg


def _http(method: str, url: str, headers: dict, payload=None, timeout=60, retries=3) -> dict:
    """HTTP 请求 + 轻量重试 (瞬时网络超时 / 连接重置时退避重试)。"""
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8") if isinstance(payload, dict) else payload
    last_exc = None
    for attempt in range(retries):
        req = request.Request(url, data=data, method=method, headers=headers)
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                return json.loads(body.decode("utf-8")) if body else {}
        except error.HTTPError as e:
            # 4xx/5xx: 服务端明确返回了状态码 → 不重试 (是协议错, 不是网络抖动)
            msg = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {url} → HTTP {e.code}\n{msg}") from None
        except (error.URLError, TimeoutError, ConnectionError) as e:
            # 网络层错误 (DNS / TCP 超时 / 重置): 退避重试
            last_exc = e
            if attempt < retries - 1:
                sleep_s = 2 ** attempt   # 1, 2, 4 秒
                print(f"        [retry {attempt+1}/{retries-1}] {method} 网络错误 ({e}), {sleep_s}s 后重试")
                time.sleep(sleep_s)
                continue
            raise RuntimeError(f"{method} {url} → 网络重试 {retries} 次仍失败: {last_exc}") from None
    raise RuntimeError(f"{method} {url} → 不可达")  # unreachable


def _pick(d: dict, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return d[k]
    return default


def _drill(d, *path, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur if cur not in (None, "", []) else default


def _put_unsigned(url: str, pdf_path: Path) -> int:
    """PUT to OSS 预签名 URL。不能加 Content-Type (签名按空 CT 算的)。"""
    with open(pdf_path, "rb") as f:
        data = f.read()
    req = request.Request(url, data=data, method="PUT")
    req.add_unredirected_header("Content-Type", "")
    try:
        with request.urlopen(req, timeout=300) as resp:
            return resp.status
    except error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"PUT {url[:80]}… → HTTP {e.code}\n{msg}") from None


def process(pdf_path: Path, cfg: dict, force: bool = False, lang: str = None,
            model: str = None, ocr: bool = None,
            output_dir: Path | None = None) -> Path:
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    size_mb = pdf_path.stat().st_size / 1024 / 1024
    if size_mb > 200:
        raise RuntimeError(f"PDF {size_mb:.1f} MB > Precise API 200 MB 上限")

    out_dir = output_dir or (pdf_path.parent / "minerU识别结果" / pdf_path.stem)
    out_dir = out_dir.resolve()
    cache_md = out_dir / "full.md"

    if not force and cache_md.exists() and cache_md.stat().st_mtime > pdf_path.stat().st_mtime:
        print(f"[CACHED] {cache_md}")
        return cache_md

    api_base = str(cfg.get("api_base", DEFAULT_API_BASE)).rstrip("/")
    auth_headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    json_headers = {**auth_headers, "Content-Type": "application/json", "Accept": "application/json"}

    # 1) 申请上传 URL
    print(f"[1/5] Request upload URL  ({pdf_path.name}, {size_mb:.2f} MB)")
    payload = {
        "files": [
            {
                "name": pdf_path.name,
                "is_ocr": ocr if ocr is not None else cfg.get("is_ocr", False),
            }
        ],
        "model_version": model or cfg.get("model_version", "pipeline"),
        "enable_formula": cfg.get("enable_formula", True),
        "enable_table": cfg.get("enable_table", True),
        "language": lang or cfg.get("language", "en"),
    }
    resp = _http("POST", f"{api_base}/file-urls/batch", json_headers, payload)
    if resp.get("code") not in (0, None):
        raise RuntimeError(f"API 错误:\n{json.dumps(resp, ensure_ascii=False, indent=2)}")

    # 兼容不同字段位置
    data = resp.get("data", resp)
    file_urls = _pick(data, "file_urls", "fileUrls") or []
    batch_id = _pick(data, "batch_id", "batchId")

    if not file_urls or not batch_id:
        raise RuntimeError(f"无 file_urls/batch_id:\n{json.dumps(resp, ensure_ascii=False, indent=2)}")

    upload_url = file_urls[0]
    print(f"        batch_id={batch_id}")

    # 2) 上传
    print(f"[2/5] Upload  {pdf_path.name}")
    status = _put_unsigned(upload_url, pdf_path)
    print(f"        HTTP {status}")

    # 3) 轮询 batch 状态 (单文件 batch,等单文件 done)
    print(f"[3/5] Poll    batch_id={batch_id} (interval={POLL_INTERVAL}s, timeout={POLL_TIMEOUT}s)")
    deadline = time.time() + POLL_TIMEOUT
    last_state = None
    file_result = None
    # 用 batch results 端点
    poll_url = f"{api_base}/extract-results/batch/{batch_id}"
    while True:
        if time.time() >= deadline:
            raise TimeoutError(f"轮询超时 ({POLL_TIMEOUT}s)")
        r = _http("GET", poll_url, auth_headers)
        rdata = r.get("data", r)
        # batch 返回 extract_result 数组(每文件一条)
        results = _pick(rdata, "extract_result", "extractResult", "results", "files") or []
        if results:
            entry = results[0]   # 单文件 batch,取第一条
            state = (entry.get("state") or entry.get("status") or "").lower()
        else:
            # 也可能整 batch 一个 state
            state = (rdata.get("state") or rdata.get("status") or "").lower()
            entry = None
        if state != last_state:
            print(f"        state = {state}")
            last_state = state
        if state in ("done", "completed", "success", "finished"):
            file_result = entry if entry else rdata
            break
        if state in ("failed", "error"):
            err = (entry or rdata).get("err_msg") or (entry or rdata).get("errMsg") or ""
            raise RuntimeError(f"解析失败 ({err}):\n{json.dumps(r, ensure_ascii=False, indent=2)}")
        time.sleep(POLL_INTERVAL)

    # 4) 下载 ZIP
    zip_url = _pick(file_result, "full_zip_url", "fullZipUrl", "zip_url", "zipUrl")
    if not zip_url:
        raise RuntimeError(f"无 full_zip_url:\n{json.dumps(file_result, ensure_ascii=False, indent=2)}")
    print(f"[4/5] Download ZIP  ({zip_url[:80]}…)")
    with request.urlopen(zip_url, timeout=300) as resp:
        zip_bytes = resp.read()
    print(f"        {len(zip_bytes)} bytes")

    # 5) 解压
    print(f"[5/5] Extract  → {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        # 防御:不允许 zip slip
        resolved_out = out_dir.resolve()
        for member in z.namelist():
            target = (out_dir / member).resolve()
            if not target.is_relative_to(resolved_out):
                raise RuntimeError(f"危险路径: {member}")
        z.extractall(out_dir)

    # 保存 meta
    meta = out_dir / "_mineru_meta.json"
    meta.write_text(
        json.dumps(
            {
                "pdf_name": pdf_path.name,
                "batch_id": batch_id,
                "model_version": payload["model_version"],
                "language": payload["language"],
                "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "service": api_base,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if not cache_md.exists():
        # 有些版本 full.md 可能命名为别的,找一下
        alt = list(out_dir.glob("*.md"))
        if alt:
            print(f"        [WARN] full.md 缺,但找到 {alt[0].name}")
        else:
            print(f"        [WARN] 解压完没找到任何 .md")

    print(f"[DONE]  {cache_md}")
    return cache_md


def main():
    ap = argparse.ArgumentParser(description="PDF → Markdown + images via MinerU Precise API")
    ap.add_argument("pdf", help="PDF 路径")
    ap.add_argument("--output-dir", type=Path, help="解析结果目录；默认写到 PDF 同层 minerU识别结果/<stem>")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG_FILE,
                    help=f"本地配置文件（默认 {DEFAULT_CONFIG_FILE.name}）")
    ap.add_argument("--force", action="store_true", help="忽略缓存重新解析")
    ap.add_argument("--lang", help="语言 (en / ch),默认从 config 读")
    ap.add_argument("--model", help="model_version (pipeline / vlm / MinerU-HTML),默认从 config 读")
    ap.add_argument("--ocr", action="store_true", help="强制 OCR(扫描版 PDF)")
    ap.add_argument("--yes-upload", action="store_true",
                    help="确认把该 PDF 上传到 MinerU；缺少此参数时拒绝联网")
    ap.add_argument("--dry-run", action="store_true", help="仅显示上传计划，不读取密钥、不访问网络")
    args = ap.parse_args()

    pdf_path = Path(args.pdf).resolve()
    out_dir = args.output_dir.resolve() if args.output_dir else (
        pdf_path.parent / "minerU识别结果" / pdf_path.stem
    )
    if not pdf_path.is_file():
        sys.exit(f"PDF 不存在: {pdf_path}")
    if args.dry_run:
        print(f"[DRY] service={DEFAULT_API_BASE}")
        print(f"[DRY] upload={pdf_path}")
        print(f"[DRY] output={out_dir}")
        return
    if not args.yes_upload:
        sys.exit(
            "拒绝上传：本命令会把 PDF 发送到 MinerU。确认后重新运行并加入 --yes-upload。"
        )

    cfg = load_config(args.config)
    out = process(
        pdf_path,
        cfg,
        force=args.force,
        lang=args.lang,
        model=args.model,
        ocr=args.ocr if args.ocr else None,
        output_dir=out_dir,
    )
    print(str(out))


if __name__ == "__main__":
    main()
