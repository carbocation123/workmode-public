from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .citation_styles import DEFAULT_CITATION_STYLE, render_citation_document, validate_style_id


WORD_CITATION_SCHEMA = "workmode-citation/v1"
WORD_CITATION_GROUP_SCHEMA = "workmode-citation/v2"
_CITATION_METADATA_FIELDS = (
    "title",
    "authors",
    "year",
    "publication_date",
    "journal",
    "doi",
)
_WORD_ERROR_MESSAGES = {
    "WORD_NOT_RUNNING": "请先打开 Microsoft Word 和要编辑的文档，再回到 Workmode 重试。",
    "WORD_NO_DOCUMENT": "Microsoft Word 中没有打开的文档。",
    "WORD_DOCUMENT_NOT_FOUND": "目标 Word 文档已关闭或改名，请刷新后重新选择。",
    "WORD_MISSING_CITATION": "缺少要插入的 Workmode 文献数据。",
    "WORD_CITATION_NOT_FOUND": "这个 Word 引用已经不存在，请刷新引用管理器。",
    "WORD_NO_CITATIONS": "当前 Word 文档里还没有 Workmode 引用，请先插入至少一篇文献。",
    "WORD_UNSUPPORTED_ACTION": "不支持的 Word 引用操作。",
}


class WordCitationError(RuntimeError):
    pass


def build_citation_payload(project_slug: str, paper: dict[str, Any]) -> dict[str, Any]:
    paper_id = str(paper.get("id") or "").strip()
    if not paper_id:
        raise WordCitationError("文献记录缺少稳定 ID，无法插入 Word 引用。")
    metadata = {
        key: paper[key]
        for key in _CITATION_METADATA_FIELDS
        if paper.get(key) not in (None, "")
    }
    return {
        "schema": WORD_CITATION_SCHEMA,
        "project_slug": str(project_slug).strip(),
        "paper_id": paper_id,
        "metadata": metadata,
    }


def build_citation_group_payload(
    project_slug: str,
    papers: list[dict[str, Any]],
    *,
    locator_label: str | None = None,
    locator_value: str = "",
    prefix: str = "",
    suffix: str = "",
    suppress_author: bool = False,
) -> dict[str, Any]:
    if not papers:
        raise WordCitationError("请至少选择一篇要插入的文献。")
    locator = (
        {"label": str(locator_label or "page"), "value": locator_value.strip()}
        if locator_value.strip()
        else None
    )
    items = []
    for paper in papers:
        legacy = build_citation_payload(project_slug, paper)
        items.append(
            {
                "project_slug": legacy["project_slug"],
                "paper_id": legacy["paper_id"],
                "metadata": legacy["metadata"],
                "locator": locator,
                "prefix": prefix.strip(),
                "suffix": suffix.strip(),
                "suppress_author": bool(suppress_author),
            }
        )
    return {"schema": WORD_CITATION_GROUP_SCHEMA, "items": items}


def normalize_citation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    schema = payload.get("schema")
    if schema == WORD_CITATION_GROUP_SCHEMA and isinstance(payload.get("items"), list):
        return payload
    if schema == WORD_CITATION_SCHEMA:
        return {
            "schema": WORD_CITATION_GROUP_SCHEMA,
            "items": [
                {
                    "project_slug": str(payload.get("project_slug") or ""),
                    "paper_id": str(payload.get("paper_id") or ""),
                    "metadata": dict(payload.get("metadata") or {}),
                    "locator": None,
                    "prefix": "",
                    "suffix": "",
                    "suppress_author": False,
                }
            ],
        }
    raise WordCitationError("Word 文档中的引用不是受支持的 Workmode 引用。")


def encode_field_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_field_payload(encoded: str) -> dict[str, Any]:
    padding = "=" * (-len(encoded) % 4)
    try:
        decoded = base64.urlsafe_b64decode(encoded + padding)
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WordCitationError("Word 文档中的 Workmode 引用数据已损坏。") from exc
    if not isinstance(payload, dict) or payload.get("schema") not in {
        WORD_CITATION_SCHEMA,
        WORD_CITATION_GROUP_SCHEMA,
    }:
        raise WordCitationError("Word 文档中的引用不是受支持的 Workmode 引用。")
    return payload


def _clean_doi(value: Any) -> str:
    doi = str(value or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            return doi[len(prefix) :].strip()
    return doi


def format_reference(number: int, metadata: dict[str, Any]) -> str:
    parts: list[str] = []
    authors = str(metadata.get("authors") or "").strip()
    title = str(metadata.get("title") or "").strip()
    journal = str(metadata.get("journal") or "").strip()
    date = str(metadata.get("publication_date") or metadata.get("year") or "").strip()
    doi = _clean_doi(metadata.get("doi"))

    if authors:
        parts.append(f"{authors}.")
    if title:
        parts.append(f"{title}.")
    if journal and date:
        parts.append(f"{journal}, {date}.")
    elif journal:
        parts.append(f"{journal}.")
    elif date:
        parts.append(f"{date}.")
    if doi:
        parts.append(f"DOI: {doi}.")
    if not parts:
        parts.append("未命名文献。")
    return f"[{number}] {' '.join(parts)}"


def _run_word_action(
    action: str,
    field_payload: str | None = None,
    document_id: str | None = None,
    action_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if sys.platform != "win32":
        raise WordCitationError("Word 引用功能目前仅支持 Windows 桌面版 Microsoft Word。")
    script = Path(__file__).with_name("word_automation.ps1")
    if not script.is_file():
        raise WordCitationError("Word 引用组件不完整，请重新安装 Workmode。")

    request = {"action": action}
    if field_payload:
        request["field_payload"] = field_payload
    if document_id:
        request["document_id"] = document_id
    if action_payload:
        request.update(action_payload)

    with tempfile.TemporaryDirectory(prefix="workmode-word-") as temp_dir:
        request_path = Path(temp_dir) / "request.json"
        result_path = Path(temp_dir) / "result.json"
        request_path.write_text(
            json.dumps(request, ensure_ascii=False),
            encoding="utf-8",
        )
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                    "-InputPath",
                    str(request_path),
                    "-OutputPath",
                    str(result_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                creationflags=creation_flags,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WordCitationError(f"无法连接 Microsoft Word：{exc}") from exc

        result: dict[str, Any] = {}
        if result_path.is_file():
            try:
                result = json.loads(result_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                result = {}
        if completed.returncode != 0 or not result.get("ok"):
            message = str(result.get("error") or completed.stderr or "").strip()
            raise WordCitationError(
                _WORD_ERROR_MESSAGES.get(message, message or "Microsoft Word 没有完成引用操作。")
            )
        return result


def list_word_documents() -> dict[str, Any]:
    return _run_word_action("list_documents")


def insert_word_citation(
    payload: dict[str, Any],
    document_id: str | None = None,
) -> dict[str, Any]:
    return _run_word_action(
        "insert_citation",
        encode_field_payload(payload),
        document_id,
    )


def insert_word_bibliography(document_id: str | None = None) -> dict[str, Any]:
    return _run_word_action("insert_bibliography", None, document_id)


def inspect_word_citations(document_id: str) -> dict[str, Any]:
    result = _run_word_action("inspect_document", None, document_id)
    groups = []
    for raw in list(result.get("citation_groups") or []):
        payload = normalize_citation_payload(decode_field_payload(str(raw["field_payload"])))
        groups.append(
            {
                "instance_id": str(raw["instance_id"]),
                "text": str(raw.get("text") or ""),
                "items": payload["items"],
            }
        )
    return {
        **result,
        "style_id": str(result.get("style_id") or DEFAULT_CITATION_STYLE),
        "citation_groups": groups,
    }


def refresh_word_citations(
    document_id: str,
    style_id: str = DEFAULT_CITATION_STYLE,
) -> dict[str, Any]:
    inspected = inspect_word_citations(document_id)
    rendered = render_citation_document(inspected["citation_groups"], style_id)
    for group in inspected["citation_groups"]:
        group["text"] = rendered["citation_texts"].get(group["instance_id"], group["text"])
    result = _run_word_action(
        "apply_formatting",
        None,
        document_id,
        {
            "style_id": rendered["style_id"],
            "citation_texts": rendered["citation_texts"],
            "bibliography_entries": rendered["bibliography_entries"],
        },
    )
    return {
        **result,
        "style_id": rendered["style_id"],
        "citation_groups": inspected["citation_groups"],
        "reference_count": rendered["reference_count"],
    }


def insert_word_citation_group(
    payload: dict[str, Any],
    document_id: str,
    style_id: str = DEFAULT_CITATION_STYLE,
) -> dict[str, Any]:
    validate_style_id(style_id)
    _run_word_action("insert_citation", encode_field_payload(payload), document_id)
    return refresh_word_citations(document_id, style_id)


def create_word_bibliography(
    document_id: str,
    style_id: str = DEFAULT_CITATION_STYLE,
) -> dict[str, Any]:
    validate_style_id(style_id)
    _run_word_action("insert_bibliography", None, document_id)
    return refresh_word_citations(document_id, style_id)


def update_word_citation_group(
    instance_id: str,
    payload: dict[str, Any],
    document_id: str,
    style_id: str = DEFAULT_CITATION_STYLE,
) -> dict[str, Any]:
    validate_style_id(style_id)
    _run_word_action(
        "update_citation",
        encode_field_payload(payload),
        document_id,
        {"instance_id": instance_id},
    )
    return refresh_word_citations(document_id, style_id)


def remove_word_citation_group(
    instance_id: str,
    document_id: str,
    style_id: str = DEFAULT_CITATION_STYLE,
) -> dict[str, Any]:
    validate_style_id(style_id)
    _run_word_action(
        "remove_citation",
        None,
        document_id,
        {"instance_id": instance_id},
    )
    return refresh_word_citations(document_id, style_id)
