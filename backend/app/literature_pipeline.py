from __future__ import annotations

import json
import re
import shutil
import threading
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from .config import get_settings
from .literature_project import (
    LiteratureProjectError,
    apply_literature_metadata,
    literature_paper,
    update_literature_paper,
)
from .web_tools import WebToolError, validate_public_web_url


MINERU_API_BASE = "https://mineru.net/api/v4"
MAX_MINERU_ZIP_BYTES = 1024 * 1024 * 1024
MAX_EXTRACTED_BYTES = 2 * 1024 * 1024 * 1024
MAX_ZIP_MEMBERS = 10_000
SUCCESS_STATES = {"done", "completed", "success", "finished"}
FAILURE_STATES = {"failed", "error"}


class LiteraturePipelineError(RuntimeError):
    pass


class PipelineCancelled(LiteraturePipelineError):
    pass


def _check_cancel(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise PipelineCancelled("用户停止了文献处理")


def _set_stage(root: Path, paper_id: str, *, stage: str, status: str) -> None:
    update_literature_paper(root, paper_id, status=status, stage=stage, error=None)


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise LiteraturePipelineError("模型没有返回可解析的元数据 JSON") from None
        try:
            value = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LiteraturePipelineError("模型返回的元数据 JSON 无法解析") from exc
    if not isinstance(value, dict):
        raise LiteraturePipelineError("模型返回的元数据不是 JSON object")
    return value


def _model_completion(system: str, user: str) -> str:
    settings = get_settings()
    if not settings.model_base_url or not settings.model_api_key:
        raise LiteraturePipelineError("模型未配置：请先在 Workmode 设置中配置 OpenAI-compatible 模型")
    headers = {
        "Authorization": f"Bearer {settings.model_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    timeout = httpx.Timeout(max(settings.request_timeout_seconds, 600), connect=30)
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{settings.model_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise LiteraturePipelineError(f"模型连接失败：{exc.__class__.__name__}") from exc
    if response.status_code >= 400:
        raise LiteraturePipelineError(f"模型请求失败：HTTP {response.status_code}")
    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LiteraturePipelineError("模型响应缺少正文") from exc
    if not isinstance(content, str) or not content.strip():
        raise LiteraturePipelineError("模型返回了空正文")
    return content.strip()


def _mineru_api_key() -> str:
    return (get_settings().mineru_api_key or "").strip()


def _mineru_timeout_seconds() -> int:
    return min(max(get_settings().mineru_timeout_seconds, 60), 1800)


def _safe_download_url(url: str) -> str:
    if urlsplit(url).scheme.lower() != "https":
        raise LiteraturePipelineError("MinerU 返回了非 HTTPS 地址")
    try:
        validate_public_web_url(url)
    except WebToolError as exc:
        raise LiteraturePipelineError("MinerU 返回的地址未通过公网安全校验") from exc
    return url


def _secure_extract_zip(zip_path: Path, destination: Path) -> None:
    staging = destination.parent / f".{destination.name}.extract-{uuid.uuid4().hex}"
    staging.mkdir(parents=True, exist_ok=False)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.infolist()
            if len(members) > MAX_ZIP_MEMBERS:
                raise LiteraturePipelineError("MinerU ZIP 文件条目过多")
            total = sum(member.file_size for member in members)
            if total > MAX_EXTRACTED_BYTES:
                raise LiteraturePipelineError("MinerU 解压后内容超过 2 GB 安全上限")
            for member in members:
                name = member.filename.replace("\\", "/")
                if not name or name.startswith("/") or ".." in Path(name).parts:
                    raise LiteraturePipelineError("MinerU ZIP 包含危险路径")
                target = (staging / name).resolve()
                if staging.resolve() not in target.parents and target != staging.resolve():
                    raise LiteraturePipelineError("MinerU ZIP 路径越界")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
        if destination.exists():
            recovery = destination.with_name(f"{destination.name}.previous-{int(time.time())}")
            destination.rename(recovery)
        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _run_mineru(root: Path, paper_id: str, cancel_event: threading.Event | None) -> Path:
    api_key = _mineru_api_key()
    if not api_key:
        raise LiteraturePipelineError("MinerU 未配置：请设置 WORKMODE_MINERU_API_KEY")
    paper = literature_paper(root, paper_id)
    pdf_rel = str((paper.get("paths") or {}).get("pdf") or "")
    pdf_path = (root / pdf_rel).resolve()
    if root not in pdf_path.parents or not pdf_path.exists():
        raise LiteraturePipelineError("文献 PDF 路径无效或文件不存在")
    output_dir = root / "papers/unprocessed/extracted" / paper_id
    cached = output_dir / "full.md"
    if cached.exists() and cached.stat().st_mtime >= pdf_path.stat().st_mtime:
        return output_dir

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "files": [{"name": pdf_path.name, "is_ocr": False}],
        "model_version": get_settings().mineru_model_version,
        "enable_formula": True,
        "enable_table": True,
        "language": get_settings().mineru_language,
    }
    timeout_seconds = _mineru_timeout_seconds()
    timeout = httpx.Timeout(timeout_seconds, connect=30)
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        response = client.post(f"{MINERU_API_BASE}/file-urls/batch", headers=headers, json=payload)
        if response.status_code >= 400:
            raise LiteraturePipelineError(f"MinerU 创建任务失败：HTTP {response.status_code}")
        try:
            response_data = response.json()
            data = response_data.get("data", response_data)
            urls = data.get("file_urls") or data.get("fileUrls") or []
            batch_id = data.get("batch_id") or data.get("batchId")
            upload_url = _safe_download_url(str(urls[0]))
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise LiteraturePipelineError("MinerU 创建任务响应缺少上传地址") from exc

        _check_cancel(cancel_event)
        with pdf_path.open("rb") as source:
            upload = client.put(upload_url, content=source)
        if upload.status_code >= 400:
            raise LiteraturePipelineError(f"MinerU 上传失败：HTTP {upload.status_code}")

        deadline = time.monotonic() + timeout_seconds
        result: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            _check_cancel(cancel_event)
            poll = client.get(f"{MINERU_API_BASE}/extract-results/batch/{batch_id}", headers=headers)
            if poll.status_code >= 400:
                raise LiteraturePipelineError(f"MinerU 查询任务失败：HTTP {poll.status_code}")
            try:
                poll_data = poll.json()
                batch_data = poll_data.get("data", poll_data)
                results = (
                    batch_data.get("extract_result")
                    or batch_data.get("extractResult")
                    or batch_data.get("results")
                    or batch_data.get("files")
                    or []
                )
                entry = results[0] if results else batch_data
                state = str(entry.get("state") or entry.get("status") or "").lower()
            except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
                raise LiteraturePipelineError("MinerU 查询任务响应格式异常") from exc
            if state in SUCCESS_STATES:
                result = entry
                break
            if state in FAILURE_STATES:
                raise LiteraturePipelineError("MinerU 解析失败")
            time.sleep(4)
        if result is None:
            raise LiteraturePipelineError(f"MinerU 解析等待超过 {timeout_seconds} 秒")
        zip_url = result.get("full_zip_url") or result.get("fullZipUrl") or result.get("zip_url") or result.get("zipUrl")
        if not isinstance(zip_url, str) or not zip_url:
            raise LiteraturePipelineError("MinerU 完成但没有返回 ZIP 地址")

    zip_url = _safe_download_url(zip_url)
    zip_path = root / "papers/unprocessed/extracted" / f".mineru-{paper_id}-{uuid.uuid4().hex}.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout_seconds, connect=30), follow_redirects=True) as client:
            with client.stream("GET", zip_url) as response:
                if response.status_code >= 400:
                    raise LiteraturePipelineError(f"MinerU 结果下载失败：HTTP {response.status_code}")
                with zip_path.open("wb") as target:
                    for chunk in response.iter_bytes(1024 * 1024):
                        _check_cancel(cancel_event)
                        downloaded += len(chunk)
                        if downloaded > MAX_MINERU_ZIP_BYTES:
                            raise LiteraturePipelineError("MinerU ZIP 超过 1 GB 安全上限")
                        target.write(chunk)
        _secure_extract_zip(zip_path, output_dir)
    finally:
        zip_path.unlink(missing_ok=True)

    full_md = output_dir / "full.md"
    if not full_md.exists():
        alternatives = sorted(output_dir.glob("*.md"))
        if not alternatives:
            raise LiteraturePipelineError("MinerU 结果中没有 Markdown 正文")
        shutil.copyfile(alternatives[0], full_md)
    return output_dir


def _collect_page_zero_text(output_dir: Path) -> str:
    candidates = sorted(output_dir.glob("*_content_list.json")) + sorted(output_dir.glob("*content_list*.json"))
    for path in candidates:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        chunks: list[str] = []

        def visit(item: Any, page: int | None = None) -> None:
            if isinstance(item, dict):
                current_page = item.get("page_idx", item.get("page_index", page))
                if current_page in {0, "0"}:
                    for key in ("text", "content", "caption", "title"):
                        text = item.get(key)
                        if isinstance(text, str) and text.strip():
                            chunks.append(text.strip())
                for child in item.values():
                    if isinstance(child, (dict, list)):
                        visit(child, current_page)
            elif isinstance(item, list):
                for child in item:
                    visit(child, page)

        visit(value)
        if chunks:
            return "\n".join(chunks)
    return (output_dir / "full.md").read_text(encoding="utf-8", errors="replace")[:40_000]


def _layout_fallback(output_dir: Path) -> str:
    layout = output_dir / "layout.json"
    if not layout.exists():
        return ""
    text = layout.read_text(encoding="utf-8", errors="replace")
    snippets: list[str] = []
    for pattern in (r"10\.1021/[^\s\"']+", r"10\.1016/[^\s\"']+"):
        for match in re.finditer(pattern, text, re.IGNORECASE):
            snippets.append(text[max(0, match.start() - 500) : match.end() + 500])
    return "\n---\n".join(snippets[:8])


def _extract_metadata(output_dir: Path) -> dict[str, Any]:
    page_zero = _collect_page_zero_text(output_dir)
    fallback = _layout_fallback(output_dir)
    prompt = f"""请只根据下面的 PDF 首页解析文本提取元数据，不准搜索，不准根据原文件名猜测。
优先使用首页明确的 Cite This 行。若 ACS/Elsevier 页眉在正文中缺失，只可使用后附 layout.json DOI 邻近片段回退。
返回一个 JSON object，字段必须是：title, authors, first_author_surname, year, journal, journal_abbreviation, doi, paper_type, metadata_source。
journal_abbreviation 必须无点无空格，例如 JACS、ACSAMI、NatCommun；不确定就返回 null。
paper_type 只能是 research、review、unknown。metadata_source 只能是 cite_this、layout_json_fallback、pending。

[PDF 首页解析文本]
{page_zero}

[layout.json 回退片段]
{fallback or '无'}
"""
    metadata = _extract_json_object(
        _model_completion(
            "你是严格的学术元数据抽取器。只输出 JSON，不补猜、不搜索、不解释。",
            prompt,
        )
    )
    required = ("title", "first_author_surname", "year", "journal_abbreviation")
    if any(metadata.get(key) in {None, ""} for key in required):
        raise LiteraturePipelineError("首页元数据不完整，需要人工补充后才能标准命名")
    try:
        metadata["year"] = int(metadata["year"])
    except (TypeError, ValueError) as exc:
        raise LiteraturePipelineError("首页年份无法确认") from exc
    source = metadata.get("metadata_source")
    if source == "cite_this" and "cite this" not in page_zero.lower():
        raise LiteraturePipelineError("模型声称使用 Cite This，但首页解析文本中没有该证据")
    if source == "layout_json_fallback" and not fallback:
        raise LiteraturePipelineError("模型声称使用 layout.json 回退，但没有 DOI 邻近片段")
    if source not in {"cite_this", "layout_json_fallback"}:
        raise LiteraturePipelineError("首页元数据来源不能确认，需要人工补充")
    authors = metadata.get("authors")
    if isinstance(authors, list):
        metadata["authors"] = ", ".join(str(author).strip() for author in authors if str(author).strip())
    elif authors is None:
        metadata["authors"] = ""
    else:
        metadata["authors"] = str(authors)
    if metadata.get("paper_type") not in {"research", "review"}:
        metadata["paper_type"] = "research"
    return metadata


def _extract_facts(output_dir: Path, metadata: dict[str, Any]) -> str:
    full_md = (output_dir / "full.md").read_text(encoding="utf-8", errors="replace")
    content_lists = sorted(output_dir.glob("*_content_list.json")) + sorted(output_dir.glob("*content_list*.json"))
    page_index_source = content_lists[0].read_text(encoding="utf-8", errors="replace") if content_lists else ""
    prompt = f"""根据下列 MinerU Markdown 正文制作完整客观事实抽取报告。

硬性纪律：
1. 只写原文直接陈述的事实、实测数据、实验条件、原文归属和明确论证链；禁止 AI 推理、延伸或跨文献判断。
2. 所有关键数据、现象、观点、g 值和数值必须附原文出处：(Fig.X, p.Y)、(Table.X, p.Y)、(Eq.X, p.Y) 或 (p.Y)。p.Y 以 content_list 的 page_idx 为准。无法支持精确定位时标记“需核对 page_idx”，不得编造。
3. 必须严格使用以下六个 Markdown 二级标题，标题文字不得改动：
   ## 1. Basic information
   ## 2. Instruments and samples
   ## 3. Phenomena and data
   ## 4. Authors' claims
   ## 5. Evidence summary
   ## 6. Cross-literature relations
4. 前五段由抽取器完整填写；第六段只写：⟨待主对话讨论后增补⟩。
5. 第 3 段按技术分类并保留实验条件、数值和作者归属；第 5 段使用 Markdown 表格。
6. 输出完整 Markdown，不要输出 JSON，不要写过程说明。

[已核对元数据]
{json.dumps(metadata, ensure_ascii=False)}

[MinerU full.md]
{full_md}

[MinerU content_list.json]
{page_index_source or '缺失：不能定位的内容必须标记需核对 page_idx'}
"""
    report = _model_completion(
        "你是科研文献的客观事实抽取器。事实与解释严格分层，跨文献判断留给主对话。",
        prompt,
    )
    required = (
        "## 1. Basic information",
        "## 2. Instruments and samples",
        "## 3. Phenomena and data",
        "## 4. Authors' claims",
        "## 5. Evidence summary",
        "## 6. Cross-literature relations",
    )
    missing = [heading for heading in required if heading not in report]
    if missing:
        raise LiteraturePipelineError(f"客观事实报告结构不完整：缺少 {', '.join(missing)}")
    return report


def run_literature_pipeline(
    root: Path,
    paper_id: str,
    *,
    cancel_event: threading.Event | None,
) -> dict[str, Any]:
    changed: list[str] = []
    try:
        _check_cancel(cancel_event)
        _set_stage(root, paper_id, stage="MinerU 正在解析正文", status="parsing")
        output_dir = _run_mineru(root, paper_id, cancel_event)
        mineru_rel = output_dir.relative_to(root).as_posix()
        paths = dict(literature_paper(root, paper_id).get("paths") or {})
        paths.update({"mineru_dir": mineru_rel, "full_md": f"{mineru_rel}/full.md"})
        update_literature_paper(root, paper_id, paths=paths)
        changed.extend([mineru_rel, f"{mineru_rel}/full.md"])

        _check_cancel(cancel_event)
        _set_stage(root, paper_id, stage="正在核对首页元数据", status="extracting")
        current = literature_paper(root, paper_id)
        if current.get("metadata_trust") == "complete":
            metadata = {
                key: current.get(key)
                for key in (
                    "title", "authors", "first_author_surname", "year", "journal",
                    "journal_abbreviation", "doi", "paper_type", "metadata_source",
                )
            }
        else:
            metadata = _extract_metadata(output_dir)
            apply_literature_metadata(root, paper_id, metadata)

        _check_cancel(cancel_event)
        _set_stage(root, paper_id, stage="正在抽取客观事实", status="extracting")
        report = _extract_facts(output_dir, metadata)
        report_path = output_dir / "objective-facts.md"
        report_path.write_text(report.rstrip() + "\n", encoding="utf-8")
        paths = dict(literature_paper(root, paper_id).get("paths") or {})
        paths.update(
            {
                "mineru_dir": mineru_rel,
                "full_md": f"{mineru_rel}/full.md",
                "fact_report": report_path.relative_to(root).as_posix(),
            }
        )
        update_literature_paper(
            root,
            paper_id,
            status="review",
            stage="待讨论标签、关注点与跨文献关系",
            paths=paths,
            error=None,
        )
        changed.append(report_path.relative_to(root).as_posix())
        return {"status": "review", "stage": "客观事实报告已生成", "changed_files": changed}
    except PipelineCancelled as exc:
        update_literature_paper(root, paper_id, status="pending", stage="处理已停止", error=str(exc))
        raise LiteratureProjectError(str(exc)) from exc
    except Exception as exc:
        message = str(exc)[:1000] or exc.__class__.__name__
        update_literature_paper(root, paper_id, status="failed", stage="处理失败", error=message)
        if isinstance(exc, LiteratureProjectError):
            raise
        raise LiteratureProjectError(message) from exc
