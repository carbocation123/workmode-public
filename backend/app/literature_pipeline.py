from __future__ import annotations

import json
import os
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
    normalize_journal_abbreviation,
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


def _project_relative(path: Path, root: Path) -> str:
    """Return a safe project-relative path after resolving Windows aliases.

    GitHub-hosted Windows runners may expose the same temporary directory as
    both an 8.3 short path (``RUNNER~1``) and its long path (``runneradmin``).
    Canonicalizing both operands keeps the containment check strict without
    rejecting those two spellings of the same real directory.
    """

    canonical_root = Path(os.path.realpath(os.fspath(root)))
    canonical_path = Path(os.path.realpath(os.fspath(path)))
    try:
        return canonical_path.relative_to(canonical_root).as_posix()
    except ValueError as exc:
        raise LiteraturePipelineError("文献处理输出路径越出项目目录") from exc


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


def _model_completion(
    system: str,
    user: str,
    *,
    response_format: dict[str, str] | None = None,
) -> str:
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
    if response_format is not None:
        payload["response_format"] = response_format
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


def _normalized_evidence(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _metadata_prompt(page_zero: str, fallback: str) -> str:
    return f"""请只根据下面的 PDF 首页解析文本提取元数据，不准搜索，不准根据原文件名猜测。
优先使用首页明确的 Cite This 行。若 ACS/Elsevier 页眉在正文中缺失，只可使用后附 layout.json DOI 邻近片段回退。
必须返回一个 JSON object，字段为：title, authors, first_author_surname, year, journal, journal_abbreviation, doi, paper_type, metadata_source, evidence_quote。
journal_abbreviation 必须无点无空格，例如 JACS、ACSAMI、NatCommun；不确定就返回 null。
paper_type 只能是 research、review、unknown。metadata_source 只能是 cite_this、layout_json_fallback、pending。
evidence_quote 必须逐字复制真正支持上述元数据的 Cite This 行或 layout.json DOI 邻近原文；没有直接证据就返回空字符串并把 metadata_source 设为 pending。
JSON 结构示例（只示意键名；不得复制占位值，未知字段保持 null）：
{{"title": null, "authors": null, "first_author_surname": null, "year": null, "journal": null, "journal_abbreviation": null, "doi": null, "paper_type": "unknown", "metadata_source": "pending", "evidence_quote": null}}

[PDF 首页解析文本]
{page_zero}

[layout.json 回退片段]
{fallback or '无'}
"""


def _normalize_metadata_candidate(
    raw: dict[str, Any],
    *,
    page_zero: str,
    fallback: str,
) -> dict[str, Any]:
    metadata = {
        key: raw.get(key)
        for key in (
            "title", "authors", "first_author_surname", "year", "journal",
            "journal_abbreviation", "doi", "paper_type", "metadata_source", "evidence_quote",
        )
    }
    authors = metadata.get("authors")
    if isinstance(authors, list):
        metadata["authors"] = ", ".join(str(author).strip() for author in authors if str(author).strip())
    elif authors is None:
        metadata["authors"] = ""
    else:
        metadata["authors"] = str(authors).strip()

    issues: list[str] = []
    try:
        metadata["year"] = int(metadata["year"])
        if not 1000 <= metadata["year"] <= 3000:
            raise ValueError
    except (TypeError, ValueError):
        metadata["year"] = None
        issues.append("首页年份无法确认")

    for key, label in (
        ("title", "标题"),
        ("authors", "作者"),
        ("first_author_surname", "第一作者姓氏"),
        ("journal", "期刊"),
        ("journal_abbreviation", "期刊缩写"),
    ):
        if not str(metadata.get(key) or "").strip():
            issues.append(f"缺少{label}")
    surname = str(metadata.get("first_author_surname") or "").strip()
    if surname and not re.fullmatch(r"[A-Za-z][A-Za-z'-]*", surname):
        issues.append("第一作者姓氏格式不能用于标准命名")
    abbreviation = str(metadata.get("journal_abbreviation") or "").strip()
    if abbreviation:
        try:
            metadata["journal_abbreviation"] = normalize_journal_abbreviation(abbreviation)
        except LiteratureProjectError:
            metadata["journal_abbreviation"] = None
            issues.append("期刊缩写未包含可用于标准命名的字母或数字")

    source = str(metadata.get("metadata_source") or "pending")
    quote = str(metadata.get("evidence_quote") or "").strip()
    normalized_quote = _normalized_evidence(quote)
    if source == "cite_this":
        if not normalized_quote or "cite this" not in normalized_quote:
            issues.append("Cite This 证据原文缺失")
        elif normalized_quote not in _normalized_evidence(page_zero):
            issues.append("模型返回的 Cite This 证据不在首页解析文本中")
    elif source == "layout_json_fallback":
        if not normalized_quote:
            issues.append("layout.json 证据原文缺失")
        elif normalized_quote not in _normalized_evidence(fallback):
            issues.append("模型返回的证据不在 layout.json DOI 邻近片段中")
    else:
        metadata["metadata_source"] = "pending"
        issues.append("首页元数据来源不能确认")

    if metadata.get("paper_type") not in {"research", "review"}:
        metadata["paper_type"] = "unknown"
    metadata["metadata_trust"] = "complete" if not issues else "partial"
    metadata["metadata_issue"] = "；".join(dict.fromkeys(issues))
    return metadata


def _extract_metadata(output_dir: Path) -> dict[str, Any]:
    page_zero = _collect_page_zero_text(output_dir)
    fallback = _layout_fallback(output_dir)
    prompt = _metadata_prompt(page_zero, fallback)
    system = "你是严格的学术元数据抽取器。只输出 JSON，不补猜、不搜索、不解释。"
    raw_response = _model_completion(system, prompt, response_format={"type": "json_object"})
    (output_dir / "metadata-response-raw.txt").write_text(raw_response, encoding="utf-8")
    try:
        raw_metadata = _extract_json_object(raw_response)
    except LiteraturePipelineError as first_error:
        repair_prompt = f"""把下面无法解析的模型输出修复为一个合法 JSON object。
只能修复 JSON 语法，不得新增、猜测或改写任何事实。字段必须保持为：title, authors, first_author_surname, year, journal, journal_abbreviation, doi, paper_type, metadata_source, evidence_quote。

[原始输出]
{raw_response}
"""
        repaired = _model_completion(
            "你是 JSON 语法修复器。只输出合法 JSON object。",
            repair_prompt,
            response_format={"type": "json_object"},
        )
        (output_dir / "metadata-response-repaired.json").write_text(repaired, encoding="utf-8")
        try:
            raw_metadata = _extract_json_object(repaired)
        except LiteraturePipelineError as exc:
            (output_dir / "metadata-response-error.txt").write_text(str(exc), encoding="utf-8")
            raise LiteraturePipelineError(f"模型返回的元数据 JSON 无法解析；已重试一次：{first_error}") from exc
    return _normalize_metadata_candidate(raw_metadata, page_zero=page_zero, fallback=fallback)


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

[书目信息；metadata_trust=complete 才表示已核对，partial 表示仍待人工确认]
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
        current_paths = dict(literature_paper(root, paper_id).get("paths") or {})
        existing_full_rel = str(current_paths.get("full_md") or "")
        existing_full = (root / existing_full_rel).resolve() if existing_full_rel else None
        if existing_full is not None:
            _project_relative(existing_full, root)
        if existing_full is not None and existing_full.exists() and existing_full.stat().st_size > 0:
            _set_stage(root, paper_id, stage="正在复用已有 MinerU 正文", status="parsing")
            output_dir = existing_full.parent
        else:
            _set_stage(root, paper_id, stage="MinerU 正在解析正文", status="parsing")
            output_dir = _run_mineru(root, paper_id, cancel_event)
        mineru_rel = _project_relative(output_dir, root)
        paths = dict(literature_paper(root, paper_id).get("paths") or {})
        paths.update({"mineru_dir": mineru_rel, "full_md": f"{mineru_rel}/full.md"})
        update_literature_paper(root, paper_id, paths=paths)
        changed.extend([mineru_rel, f"{mineru_rel}/full.md"])

        _check_cancel(cancel_event)
        _set_stage(root, paper_id, stage="正在核对首页元数据", status="extracting")
        current = literature_paper(root, paper_id)
        metadata_issue = ""
        if current.get("metadata_trust") == "complete":
            metadata = {
                key: current.get(key)
                for key in (
                    "title", "authors", "first_author_surname", "year", "journal",
                    "journal_abbreviation", "doi", "paper_type", "metadata_source",
                )
            }
            metadata["metadata_trust"] = "complete"
        else:
            try:
                metadata = _extract_metadata(output_dir)
                metadata_trust = str(metadata.get("metadata_trust") or "complete")
                metadata_issue = str(metadata.get("metadata_issue") or "")
                if metadata_trust == "complete":
                    apply_literature_metadata(root, paper_id, metadata)
                else:
                    candidate_updates = {
                        key: metadata.get(key)
                        for key in (
                            "title", "authors", "first_author_surname", "year", "journal",
                            "journal_abbreviation", "doi", "paper_type", "metadata_source",
                        )
                        if metadata.get(key) not in {None, ""}
                    }
                    update_literature_paper(
                        root,
                        paper_id,
                        **candidate_updates,
                        metadata_trust="partial",
                        metadata_issue=metadata_issue or "首页元数据需要人工确认",
                    )
            except Exception as exc:
                metadata_issue = str(exc)[:1000] or exc.__class__.__name__
                update_literature_paper(
                    root,
                    paper_id,
                    metadata_trust="partial",
                    metadata_issue=metadata_issue,
                )
                current = literature_paper(root, paper_id)
                metadata = {
                    key: current.get(key)
                    for key in (
                        "title", "authors", "first_author_surname", "year", "journal",
                        "journal_abbreviation", "doi", "paper_type", "metadata_source",
                    )
                }
                metadata["metadata_trust"] = "partial"
                metadata["metadata_issue"] = metadata_issue
        for artifact in (
            "metadata-response-raw.txt",
            "metadata-response-repaired.json",
            "metadata-response-error.txt",
        ):
            artifact_path = output_dir / artifact
            if artifact_path.exists():
                changed.append(_project_relative(artifact_path, root))

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
                "fact_report": _project_relative(report_path, root),
            }
        )
        update_literature_paper(
            root,
            paper_id,
            status="review",
            stage=(
                "客观事实报告已生成；首页元数据待人工确认"
                if metadata_issue or metadata.get("metadata_trust") == "partial"
                else "待讨论标签、关注点与跨文献关系"
            ),
            paths=paths,
            error=None,
        )
        changed.append(_project_relative(report_path, root))
        needs_review = bool(metadata_issue or metadata.get("metadata_trust") == "partial")
        return {
            "status": "review",
            "stage": "客观事实报告已生成",
            "metadata_needs_review": needs_review,
            "metadata_issue": metadata_issue or str(metadata.get("metadata_issue") or ""),
            "changed_files": list(dict.fromkeys(changed)),
        }
    except PipelineCancelled as exc:
        update_literature_paper(root, paper_id, status="pending", stage="处理已停止", error=str(exc))
        raise LiteratureProjectError(str(exc)) from exc
    except Exception as exc:
        message = str(exc)[:1000] or exc.__class__.__name__
        update_literature_paper(root, paper_id, status="failed", stage="处理失败", error=message)
        if isinstance(exc, LiteratureProjectError):
            raise
        raise LiteratureProjectError(message) from exc
