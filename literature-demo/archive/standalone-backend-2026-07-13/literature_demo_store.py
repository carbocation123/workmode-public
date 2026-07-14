from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

from .config import get_settings


MAX_PDF_BYTES = 200 * 1024 * 1024
_JOURNAL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_TAG_CATEGORIES = {"characterization", "material", "mechanism", "performance", "uncategorized"}
_LOCK = threading.RLock()
DEFAULT_PROJECT_MEMORY = """# 文献项目固定协作纪律

- 主干目录和关键文件必须有说明；文件结构、索引和正文保持双向一致。
- 修改文献记录、笔记或归档状态时检查受影响的索引、引用和关联材料，避免只改一处。
- 严格区分论文客观事实、作者解释与项目推断；关键事实保留文献及页码、图表或表格定位。
- 笔记允许 AI 自主检索和读取；只有用户明确要求或确认后才能创建、更新或改写。
- 客观事实报告第 1–5 段由抽取流水线填写；第 6 段跨文献关系只由主对话讨论后增补。
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_display_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name.strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).rstrip(". ")
    return name[:240] or "paper.pdf"


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


class LiteratureDemoStore:
    """File-backed data boundary for the isolated literature vertical slice."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.catalog_path = self.root / "catalog.json"
        self.tasks_path = self.root / "tasks.json"
        self.tags_path = self.root / "tags.json"
        self.notes_index_path = self.root / "notes-index.json"
        self.index_path = self.root / "处理结果索引.md"
        self.incoming_dir = self.root / "文献" / "未处理" / "_incoming"
        self.unprocessed_dir = self.root / "文献" / "未处理"
        self.processed_dir = self.root / "文献" / "已处理"
        self.sessions_dir = self.root / "sessions"
        self.notes_dir = self.root / "notes"
        self.memory_path = self.root / "project-memory.md"
        for path in (
            self.incoming_dir,
            self.unprocessed_dir,
            self.processed_dir,
            self.sessions_dir,
            self.notes_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        if not self.memory_path.exists():
            self.memory_path.write_text(DEFAULT_PROJECT_MEMORY, encoding="utf-8")
        self._recover_interrupted_write_proposals()

    def _recover_interrupted_write_proposals(self) -> None:
        """Do not retry an ambiguous domain write after the backend stopped mid-flight."""
        with _LOCK:
            for path in self.sessions_dir.glob("*.json"):
                session = _read_json(path, None)
                if not isinstance(session, dict):
                    continue
                proposals = list(session.get("write_proposals") or [])
                changed = False
                for index, proposal in enumerate(proposals):
                    if proposal.get("status") != "executing":
                        continue
                    proposals[index] = {
                        **proposal,
                        "status": "failed",
                        "error": "后端在写入执行期间中断；请检查目标数据后重新创建提案，系统不会自动重试。",
                        "resolved_at": _now(),
                    }
                    changed = True
                if changed:
                    _atomic_json(
                        path,
                        {**session, "write_proposals": proposals, "updated_at": _now()},
                    )

    def list_papers(self) -> list[dict[str, Any]]:
        with _LOCK:
            papers = _read_json(self.catalog_path, [])
            return sorted(papers, key=lambda item: item.get("created_at", ""), reverse=True)

    def get_paper(self, paper_id: str) -> dict[str, Any]:
        for paper in self.list_papers():
            if paper.get("id") == paper_id:
                return paper
        raise KeyError(paper_id)

    def _save_papers(self, papers: list[dict[str, Any]]) -> None:
        _atomic_json(self.catalog_path, papers)

    def import_pdf_bytes(self, filename: str, data: bytes) -> tuple[dict[str, Any], bool]:
        if len(data) > MAX_PDF_BYTES:
            raise ValueError("PDF exceeds 200 MB")
        staging = self.root / f".upload-{uuid.uuid4().hex}.tmp"
        staging.parent.mkdir(parents=True, exist_ok=True)
        staging.write_bytes(data)
        try:
            return self.import_pdf_path(filename, staging)
        finally:
            staging.unlink(missing_ok=True)

    def import_pdf_stream(self, filename: str, source: BinaryIO) -> tuple[dict[str, Any], bool]:
        staging = self.root / f".upload-{uuid.uuid4().hex}.tmp"
        digest = hashlib.sha256()
        total = 0
        first = b""
        with staging.open("wb") as target:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                if not first:
                    first = chunk[:8]
                total += len(chunk)
                if total > MAX_PDF_BYTES:
                    target.close()
                    staging.unlink(missing_ok=True)
                    raise ValueError("PDF exceeds 200 MB")
                digest.update(chunk)
                target.write(chunk)
        try:
            return self.import_pdf_path(
                filename,
                staging,
                known_hash=digest.hexdigest(),
                known_size=total,
                known_magic=first,
            )
        finally:
            staging.unlink(missing_ok=True)

    def import_pdf_path(
        self,
        filename: str,
        staging: Path,
        *,
        known_hash: str | None = None,
        known_size: int | None = None,
        known_magic: bytes | None = None,
    ) -> tuple[dict[str, Any], bool]:
        display_name = _safe_display_filename(filename)
        if not display_name.lower().endswith(".pdf"):
            raise TypeError("Only .pdf files are accepted")
        size = staging.stat().st_size if known_size is None else known_size
        if size > MAX_PDF_BYTES:
            raise ValueError("PDF exceeds 200 MB")
        magic = staging.read_bytes()[:8] if known_magic is None else known_magic
        if not magic.startswith(b"%PDF-"):
            raise TypeError("File content is not a PDF")
        digest = known_hash or hashlib.sha256(staging.read_bytes()).hexdigest()

        with _LOCK:
            papers = _read_json(self.catalog_path, [])
            existing = next((item for item in papers if item.get("sha256") == digest), None)
            if existing:
                return dict(existing), True

            paper_id = uuid.uuid4().hex
            destination = self.incoming_dir / f"{paper_id}.pdf"
            shutil.copyfile(staging, destination)
            now = _now()
            paper = {
                "id": paper_id,
                "original_filename": display_name,
                "filename": display_name,
                "archive_filename": None,
                "archive_location": "文献/未处理",
                "relative_pdf_path": destination.relative_to(self.root).as_posix(),
                "sha256": digest,
                "size_bytes": size,
                "title": display_name[:-4],
                "authors": "",
                "first_author_surname": None,
                "year": None,
                "journal": "",
                "journal_abbreviation": None,
                "doi": None,
                "paper_type": "unknown",
                "metadata_source": "pending",
                "metadata_trust": "unknown",
                "status": "pending",
                "stage": "等待处理",
                "error": None,
                "tags": [],
                "focus": "",
                "summary": "",
                "mineru_output_path": None,
                "fact_report_path": None,
                "verification_status": "pending",
                "created_at": now,
                "updated_at": now,
            }
            papers.append(paper)
            self._save_papers(papers)
            return dict(paper), False

    def update_paper(self, paper_id: str, **updates: Any) -> dict[str, Any]:
        with _LOCK:
            papers = _read_json(self.catalog_path, [])
            for index, paper in enumerate(papers):
                if paper.get("id") == paper_id:
                    next_paper = {**paper, **updates, "updated_at": _now()}
                    papers[index] = next_paper
                    self._save_papers(papers)
                    return dict(next_paper)
        raise KeyError(paper_id)

    def list_tags(self) -> list[dict[str, Any]]:
        with _LOCK:
            tags = _read_json(self.tags_path, [])
            return sorted(tags, key=lambda item: (item.get("category", ""), item.get("name", "")))

    @staticmethod
    def _normalize_tag(value: str) -> str:
        return re.sub(r"[\s_-]+", "", value.strip().lower())

    @staticmethod
    def _tag_id(name: str, existing: set[str]) -> str:
        base = re.sub(r"[^\w]+", "_", name.strip().lower(), flags=re.UNICODE).strip("_") or "tag"
        candidate = base
        sequence = 2
        while candidate in existing:
            candidate = f"{base}_{sequence}"
            sequence += 1
        return candidate

    def confirm_paper_review(
        self,
        paper_id: str,
        *,
        tags: list[dict[str, Any]],
        focus: str,
        summary: str,
        confirmed: bool,
    ) -> dict[str, Any]:
        if not confirmed:
            raise PermissionError("Paper review writes require explicit user confirmation")
        focus = focus.strip()
        summary = summary.strip()
        if not focus or not summary:
            raise ValueError("Focus and summary must not be empty")
        if not tags:
            raise ValueError("At least one tag is required")
        if self.get_paper(paper_id).get("archive_location") == "文献/已处理":
            raise ValueError("Processed paper records require an explicit reopen workflow")

        with _LOCK:
            registry = _read_json(self.tags_path, [])
            occupied_ids = {str(item.get("id")) for item in registry}
            selected_ids: list[str] = []
            for suggestion in tags:
                name = str(suggestion.get("name") or "").strip()
                if not name:
                    continue
                normalized = self._normalize_tag(name)
                existing = next(
                    (
                        item
                        for item in registry
                        if self._normalize_tag(str(item.get("name") or "")) == normalized
                        or any(
                            self._normalize_tag(str(alias)) == normalized
                            for alias in item.get("aliases", [])
                        )
                    ),
                    None,
                )
                if existing:
                    selected_ids.append(str(existing["id"]))
                    continue
                category = str(suggestion.get("category") or "uncategorized")
                if category not in _TAG_CATEGORIES:
                    category = "uncategorized"
                tag_id = self._tag_id(name, occupied_ids)
                occupied_ids.add(tag_id)
                registry.append(
                    {
                        "id": tag_id,
                        "name": name,
                        "aliases": [],
                        "category": category,
                        "status": "provisional",
                        "created_at": _now(),
                    }
                )
                selected_ids.append(tag_id)
            selected_ids = list(dict.fromkeys(selected_ids))
            if not selected_ids:
                raise ValueError("At least one valid tag is required")
            _atomic_json(self.tags_path, registry)

        return self.update_paper(
            paper_id,
            tags=selected_ids,
            focus=focus,
            summary=summary,
            status="ready",
            stage="记录已确认，等待补齐跨文献关系并归档",
        )

    def update_cross_literature(self, paper_id: str, markdown: str, *, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise PermissionError("Cross-literature writes require explicit user confirmation")
        content = markdown.strip()
        if not content or "待主对话讨论后增补" in content:
            raise ValueError("Cross-literature section must contain confirmed discussion")
        if self.get_paper(paper_id).get("archive_location") == "文献/已处理":
            raise ValueError("Processed reports require an explicit reopen workflow")
        report_path = self.report_path(paper_id)
        report = report_path.read_text(encoding="utf-8")
        heading_match = re.search(r"(?mi)^(#{1,3})\s+[^\n]*跨文献关系[^\n]*$", report)
        if heading_match:
            level = len(heading_match.group(1))
            following = report[heading_match.end() :]
            next_heading = re.search(rf"(?m)^#{{1,{level}}}\s+", following)
            end = heading_match.end() + (next_heading.start() if next_heading else len(following))
            replacement = f"{heading_match.group(0)}\n\n{content}\n"
            next_report = report[: heading_match.start()] + replacement + report[end:]
        else:
            next_report = report.rstrip() + f"\n\n## 6. 跨文献关系与系列归属\n\n{content}\n"
        temp = report_path.with_name(f".{report_path.name}.{uuid.uuid4().hex}.tmp")
        temp.write_text(next_report, encoding="utf-8")
        os.replace(temp, report_path)
        return self.update_paper(paper_id, stage="跨文献关系已确认，等待归档校验")

    def apply_metadata(self, paper_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        surname = str(metadata.get("first_author_surname") or "").strip()
        year = metadata.get("year")
        journal_abbreviation = str(metadata.get("journal_abbreviation") or "").strip()
        if not surname or not all(char.isalpha() or char in "'-" for char in surname):
            raise ValueError("First-author surname is incomplete")
        if not isinstance(year, int) or year < 1800 or year > 2100:
            raise ValueError("Publication year is incomplete")
        if not _JOURNAL_RE.fullmatch(journal_abbreviation):
            raise ValueError("Journal abbreviation must be CamelCase without punctuation")

        with _LOCK:
            papers = _read_json(self.catalog_path, [])
            target_index = next(
                (index for index, item in enumerate(papers) if item.get("id") == paper_id),
                None,
            )
            if target_index is None:
                raise KeyError(paper_id)
            paper = papers[target_index]
            candidate = f"{surname}_{year}_{journal_abbreviation}.pdf"
            occupied = {
                str(item.get("archive_filename") or "").lower()
                for item in papers
                if item.get("id") != paper_id
            }
            sequence = 2
            stem = candidate[:-4]
            while candidate.lower() in occupied:
                candidate = f"{stem}_{sequence}.pdf"
                sequence += 1

            source = self.root / str(paper["relative_pdf_path"])
            destination = self.unprocessed_dir / candidate
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.resolve() != destination.resolve():
                shutil.move(str(source), str(destination))
            next_paper = {
                **paper,
                **metadata,
                "archive_filename": candidate,
                "filename": candidate,
                "relative_pdf_path": destination.relative_to(self.root).as_posix(),
                "metadata_trust": "complete",
                "updated_at": _now(),
            }
            papers[target_index] = next_paper
            self._save_papers(papers)
            return dict(next_paper)

    def pdf_path(self, paper_id: str) -> Path:
        paper = self.get_paper(paper_id)
        path = (self.root / str(paper["relative_pdf_path"])).resolve()
        if self.root not in path.parents or not path.is_file():
            raise FileNotFoundError(paper_id)
        return path

    def report_path(self, paper_id: str) -> Path:
        paper = self.get_paper(paper_id)
        relative = paper.get("fact_report_path")
        if not relative:
            raise FileNotFoundError(paper_id)
        path = (self.root / str(relative)).resolve()
        if self.root not in path.parents or not path.is_file():
            raise FileNotFoundError(paper_id)
        return path

    def create_task(self, paper_id: str) -> dict[str, Any]:
        self.get_paper(paper_id)
        with _LOCK:
            tasks = _read_json(self.tasks_path, [])
            active = next(
                (
                    item
                    for item in tasks
                    if item.get("paper_id") == paper_id
                    and item.get("status") in {"queued", "running", "cancelling"}
                ),
                None,
            )
            if active:
                return dict(active)
            task = {
                "id": uuid.uuid4().hex,
                "paper_id": paper_id,
                "status": "queued",
                "stage": "等待流水线",
                "progress": 0,
                "cancel_requested": False,
                "error": None,
                "created_at": _now(),
                "updated_at": _now(),
            }
            tasks.append(task)
            _atomic_json(self.tasks_path, tasks)
            return dict(task)

    def get_task(self, task_id: str) -> dict[str, Any]:
        tasks = _read_json(self.tasks_path, [])
        for task in tasks:
            if task.get("id") == task_id:
                return task
        raise KeyError(task_id)

    def update_task(self, task_id: str, **updates: Any) -> dict[str, Any]:
        with _LOCK:
            tasks = _read_json(self.tasks_path, [])
            for index, task in enumerate(tasks):
                if task.get("id") == task_id:
                    next_task = {**task, **updates, "updated_at": _now()}
                    tasks[index] = next_task
                    _atomic_json(self.tasks_path, tasks)
                    return dict(next_task)
        raise KeyError(task_id)

    def request_cancel(self, task_id: str) -> dict[str, Any]:
        task = self.get_task(task_id)
        if task.get("status") in {"completed", "failed", "cancelled", "awaiting_configuration"}:
            return task
        return self.update_task(task_id, cancel_requested=True, status="cancelling", stage="正在停止")

    def recover_interrupted_tasks(self) -> list[dict[str, Any]]:
        """Return persisted active tasks that should resume after backend restart."""
        with _LOCK:
            tasks = _read_json(self.tasks_path, [])
            recoverable: list[dict[str, Any]] = []
            changed = False
            for index, task in enumerate(tasks):
                status = task.get("status")
                if status == "cancelling" or task.get("cancel_requested"):
                    tasks[index] = {
                        **task,
                        "status": "cancelled",
                        "stage": "后端重启后确认停止",
                        "updated_at": _now(),
                    }
                    changed = True
                elif status in {"queued", "running"}:
                    resumed = {
                        **task,
                        "status": "queued",
                        "stage": "后端重启后恢复任务",
                        "updated_at": _now(),
                    }
                    tasks[index] = resumed
                    recoverable.append(dict(resumed))
                    changed = True
            if changed:
                _atomic_json(self.tasks_path, tasks)
            return recoverable

    def create_session(self, name: str) -> dict[str, Any]:
        session = {
            "id": uuid.uuid4().hex,
            "name": name.strip() or "新对话",
            "messages": [],
            "attached_paper_ids": [],
            "attached_note_ids": [],
            "memory_candidate": None,
            "write_proposals": [],
            "created_at": _now(),
            "updated_at": _now(),
        }
        _atomic_json(self.sessions_dir / f"{session['id']}.json", session)
        return session

    def list_sessions(self) -> list[dict[str, Any]]:
        sessions = [_read_json(path, {}) for path in self.sessions_dir.glob("*.json")]
        return sorted((item for item in sessions if item), key=lambda item: item["updated_at"], reverse=True)

    def get_session(self, session_id: str) -> dict[str, Any]:
        path = self.sessions_dir / f"{session_id}.json"
        session = _read_json(path, None)
        if not isinstance(session, dict):
            raise KeyError(session_id)
        session.setdefault("write_proposals", [])
        return session

    def create_write_proposal(
        self,
        session_id: str,
        *,
        operation: str,
        payload: dict[str, Any],
        summary: str,
        source_user_content: str,
    ) -> dict[str, Any]:
        proposal = {
            "id": uuid.uuid4().hex,
            "operation": operation,
            "payload": payload,
            "summary": summary.strip(),
            "source_user_content": source_user_content.strip(),
            "status": "pending",
            "result": None,
            "error": None,
            "created_at": _now(),
            "started_at": None,
            "resolved_at": None,
        }
        with _LOCK:
            session = self.get_session(session_id)
            proposals = list(session.get("write_proposals") or [])
            duplicate = next(
                (
                    item
                    for item in proposals
                    if item.get("status") == "pending"
                    and item.get("operation") == operation
                    and item.get("payload") == payload
                    and str(item.get("source_user_content") or "").strip()
                    == source_user_content.strip()
                ),
                None,
            )
            if duplicate:
                return dict(duplicate)
            proposals.append(proposal)
            session = {**session, "write_proposals": proposals, "updated_at": _now()}
            _atomic_json(self.sessions_dir / f"{session_id}.json", session)
        return dict(proposal)

    def get_write_proposal(self, session_id: str, proposal_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        for proposal in session.get("write_proposals") or []:
            if proposal.get("id") == proposal_id:
                return dict(proposal)
        raise KeyError(proposal_id)

    def claim_write_proposal(self, session_id: str, proposal_id: str) -> dict[str, Any]:
        """Atomically claim a pending proposal before performing its domain write."""
        with _LOCK:
            session = self.get_session(session_id)
            proposals = list(session.get("write_proposals") or [])
            for index, proposal in enumerate(proposals):
                if proposal.get("id") != proposal_id:
                    continue
                if proposal.get("status") != "pending":
                    raise ValueError("Write proposal is no longer pending")
                claimed = {
                    **proposal,
                    "status": "executing",
                    "started_at": _now(),
                }
                proposals[index] = claimed
                session = {**session, "write_proposals": proposals, "updated_at": _now()}
                _atomic_json(self.sessions_dir / f"{session_id}.json", session)
                return dict(claimed)
        raise KeyError(proposal_id)

    def resolve_write_proposal(
        self,
        session_id: str,
        proposal_id: str,
        *,
        status: str,
        result: Any = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        if status not in {"confirmed", "rejected", "failed"}:
            raise ValueError("Invalid write proposal resolution")
        with _LOCK:
            session = self.get_session(session_id)
            proposals = list(session.get("write_proposals") or [])
            for index, proposal in enumerate(proposals):
                if proposal.get("id") != proposal_id:
                    continue
                current_status = proposal.get("status")
                expected_status = "pending" if status == "rejected" else "executing"
                if current_status != expected_status:
                    raise ValueError("Write proposal is no longer pending")
                resolved = {
                    **proposal,
                    "status": status,
                    "result": result,
                    "error": error,
                    "resolved_at": _now(),
                }
                proposals[index] = resolved
                session = {**session, "write_proposals": proposals, "updated_at": _now()}
                _atomic_json(self.sessions_dir / f"{session_id}.json", session)
                return dict(resolved)
        raise KeyError(proposal_id)

    def append_message(self, session_id: str, message: dict[str, Any]) -> dict[str, Any]:
        with _LOCK:
            session = self.get_session(session_id)
            messages = list(session.get("messages") or [])
            messages.append({"id": uuid.uuid4().hex, **message, "created_at": _now()})
            session = {**session, "messages": messages, "updated_at": _now()}
            _atomic_json(self.sessions_dir / f"{session_id}.json", session)
            return session

    def update_session_context(
        self,
        session_id: str,
        *,
        paper_ids: list[str],
        note_ids: list[str],
    ) -> dict[str, Any]:
        valid_papers = {paper["id"] for paper in self.list_papers()}
        valid_notes = {note["filename"] for note in self.list_notes()}
        cleaned_papers = list(dict.fromkeys(item for item in paper_ids if item in valid_papers))
        cleaned_notes = list(dict.fromkeys(item for item in note_ids if item in valid_notes))
        with _LOCK:
            session = self.get_session(session_id)
            session = {
                **session,
                "attached_paper_ids": cleaned_papers,
                "attached_note_ids": cleaned_notes,
                "updated_at": _now(),
            }
            _atomic_json(self.sessions_dir / f"{session_id}.json", session)
            return session

    def set_memory_candidate(self, session_id: str, candidate: str | None) -> dict[str, Any]:
        with _LOCK:
            session = self.get_session(session_id)
            session = {**session, "memory_candidate": candidate, "updated_at": _now()}
            _atomic_json(self.sessions_dir / f"{session_id}.json", session)
            return session

    def resolve_memory_candidate(
        self,
        session_id: str,
        *,
        accept: bool,
        confirmed: bool,
    ) -> dict[str, Any]:
        if not confirmed:
            raise PermissionError("Memory candidate resolution requires explicit user confirmation")
        session = self.get_session(session_id)
        candidate = str(session.get("memory_candidate") or "").strip()
        if accept and candidate:
            memory = self.read_memory().rstrip()
            addition = f"\n\n## 会话提炼\n\n- {candidate}\n"
            self.write_memory(memory + addition, confirmed=True)
        self.set_memory_candidate(session_id, None)
        return self.append_message(
            session_id,
            {
                "role": "system",
                "content": "项目记忆候选已确认写入。" if accept and candidate else "项目记忆候选未写入。",
                "meta": {"kind": "memory_candidate_resolution", "accepted": bool(accept and candidate)},
            },
        )

    def list_notes(self) -> list[dict[str, Any]]:
        metadata = _read_json(self.notes_index_path, {})
        return [
            {
                "id": path.name,
                "filename": path.name,
                "title": path.stem,
                "markdown": path.read_text(encoding="utf-8"),
                "source_paper_ids": metadata.get(path.name, {}).get("source_paper_ids", []),
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            }
            for path in sorted(self.notes_dir.glob("*.md"))
        ]

    def upsert_note(
        self,
        filename: str,
        markdown: str,
        *,
        confirmed: bool,
        source_paper_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if not confirmed:
            raise PermissionError("Note writes require explicit user confirmation")
        safe = _safe_display_filename(filename)
        if not safe.lower().endswith(".md"):
            safe = f"{Path(safe).stem}.md"
        path = self.notes_dir / safe
        temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temp.write_text(markdown, encoding="utf-8")
        os.replace(temp, path)
        note_index = _read_json(self.notes_index_path, {})
        note_index[path.name] = {
            "source_paper_ids": list(dict.fromkeys(source_paper_ids or [])),
            "updated_at": _now(),
        }
        _atomic_json(self.notes_index_path, note_index)
        return {
            "id": path.name,
            "filename": path.name,
            "title": path.stem,
            "markdown": markdown,
            "source_paper_ids": note_index[path.name]["source_paper_ids"],
        }

    def read_memory(self) -> str:
        return self.memory_path.read_text(encoding="utf-8") if self.memory_path.exists() else ""

    def write_memory(self, markdown: str, *, confirmed: bool) -> str:
        if not confirmed:
            raise PermissionError("Memory writes require explicit user confirmation")
        temp = self.memory_path.with_name(f".{self.memory_path.name}.{uuid.uuid4().hex}.tmp")
        temp.write_text(markdown, encoding="utf-8")
        os.replace(temp, self.memory_path)
        return markdown


_DEFAULT_STORE: LiteratureDemoStore | None = None
_DEFAULT_ROOT: Path | None = None


def get_literature_demo_store() -> LiteratureDemoStore:
    global _DEFAULT_ROOT, _DEFAULT_STORE
    root = (get_settings().data_dir / "literature-demo").resolve()
    if _DEFAULT_STORE is None or _DEFAULT_ROOT != root:
        _DEFAULT_ROOT = root
        _DEFAULT_STORE = LiteratureDemoStore(root)
    return _DEFAULT_STORE


def reset_literature_demo_store() -> None:
    global _DEFAULT_ROOT, _DEFAULT_STORE
    _DEFAULT_ROOT = None
    _DEFAULT_STORE = None
