from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings


_LOCK = threading.RLock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def data_dir() -> Path:
    return settings.data_dir


def work_dir() -> Path:
    return data_dir() / "work"


def projects_dir() -> Path:
    return work_dir() / "projects"


def sessions_dir() -> Path:
    return work_dir() / "sessions"


def memory_dir() -> Path:
    return work_dir() / "memory"


def active_file() -> Path:
    return work_dir() / "active.json"


def ensure_data_dirs() -> None:
    for path in (projects_dir(), sessions_dir(), memory_dir() / "projects"):
        path.mkdir(parents=True, exist_ok=True)
    global_memory_file().touch(exist_ok=True)


@dataclass(frozen=True)
class Project:
    slug: str
    name: str
    root_path: str
    description: str
    created_at: str
    updated_at: str
    parent_slug: str | None = None
    archived_at: str | None = None


@dataclass(frozen=True)
class Session:
    id: str
    title: str
    project_slug: str
    created_at: str
    updated_at: str
    message_count: int
    deleted_at: str | None = None


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class ValidationError(Exception):
    pass


def slugify(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", value.strip()).strip("-_")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:64] or f"project-{uuid.uuid4().hex[:8]}"


def _project_file(slug: str) -> Path:
    return projects_dir() / f"{slug}.json"


def _session_dir(project_slug: str) -> Path:
    return sessions_dir() / project_slug


def _session_meta_file(project_slug: str, session_id: str) -> Path:
    return _session_dir(project_slug) / f"{session_id}.meta.json"


def _session_jsonl_file(project_slug: str, session_id: str) -> Path:
    return _session_dir(project_slug) / f"{session_id}.jsonl"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _project_from_payload(payload: dict[str, Any]) -> Project:
    return Project(
        slug=str(payload["slug"]),
        name=str(payload["name"]),
        root_path=str(payload["root_path"]),
        description=str(payload.get("description") or ""),
        created_at=str(payload["created_at"]),
        updated_at=str(payload["updated_at"]),
        parent_slug=payload.get("parent_slug") or None,
        archived_at=payload.get("archived_at") or None,
    )


def _session_from_payload(payload: dict[str, Any]) -> Session:
    return Session(
        id=str(payload["id"]),
        title=str(payload["title"]),
        project_slug=str(payload["project_slug"]),
        created_at=str(payload["created_at"]),
        updated_at=str(payload["updated_at"]),
        message_count=int(payload.get("message_count") or 0),
        deleted_at=payload.get("deleted_at") or None,
    )


def _ordered_project_tree(projects: list[Project]) -> list[Project]:
    visible_slugs = {project.slug for project in projects}
    normalized = [
        replace(project, parent_slug=None)
        if project.parent_slug not in visible_slugs or project.parent_slug == project.slug
        else project
        for project in projects
    ]
    children: dict[str | None, list[Project]] = {}
    for project in normalized:
        children.setdefault(project.parent_slug, []).append(project)
    for siblings in children.values():
        siblings.sort(key=lambda item: (item.name.casefold(), item.created_at, item.slug))

    ordered: list[Project] = []
    visited: set[str] = set()

    def visit(project: Project) -> None:
        if project.slug in visited:
            return
        visited.add(project.slug)
        ordered.append(project)
        for child in children.get(project.slug, []):
            visit(child)

    for root in children.get(None, []):
        visit(root)
    for project in normalized:
        visit(project)
    return ordered


def list_projects(*, include_archived: bool = False) -> list[Project]:
    ensure_data_dirs()
    with _LOCK:
        projects: list[Project] = []
        for path in sorted(projects_dir().glob("*.json")):
            project = _project_from_payload(_read_json(path))
            if include_archived or project.archived_at is None:
                projects.append(project)
        return _ordered_project_tree(projects)


def get_project(slug: str, *, include_archived: bool = False) -> Project:
    ensure_data_dirs()
    path = _project_file(slug)
    if not path.exists():
        raise NotFoundError(f"项目不存在：{slug}")
    project = _project_from_payload(_read_json(path))
    if project.archived_at is not None and not include_archived:
        raise NotFoundError(f"项目不存在：{slug}")
    return project


def _nearest_parent_slug(root: Path) -> str | None:
    candidates: list[tuple[int, str]] = []
    for project in list_projects():
        candidate_root = Path(project.root_path).expanduser().resolve()
        if candidate_root == root:
            continue
        try:
            root.relative_to(candidate_root)
        except ValueError:
            continue
        candidates.append((len(candidate_root.parts), project.slug))
    return max(candidates, default=(0, None))[1]


def create_project(name: str, root_path: str, description: str = "") -> Project:
    ensure_data_dirs()
    root = Path(root_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValidationError("项目根目录不存在或不是文件夹")
    base_slug = slugify(name)
    slug = base_slug
    with _LOCK:
        index = 2
        while _project_file(slug).exists():
            slug = f"{base_slug}-{index}"
            index += 1
        now = utc_now()
        project = Project(
            slug=slug,
            name=name.strip(),
            root_path=str(root),
            description=description.strip(),
            created_at=now,
            updated_at=now,
            parent_slug=_nearest_parent_slug(root),
        )
        _write_json(_project_file(slug), asdict(project))
        set_active_project(slug)
        return project


def update_project(slug: str, *, name: str | None = None, description: str | None = None) -> Project:
    with _LOCK:
        project = get_project(slug)
        updated = Project(
            slug=project.slug,
            name=(name.strip() if name is not None else project.name),
            root_path=project.root_path,
            description=(description.strip() if description is not None else project.description),
            created_at=project.created_at,
            updated_at=utc_now(),
            parent_slug=project.parent_slug,
            archived_at=project.archived_at,
        )
        _write_json(_project_file(slug), asdict(updated))
        return updated


def get_active_project_slug() -> str | None:
    ensure_data_dirs()
    path = active_file()
    if not path.exists():
        return None
    try:
        slug = _read_json(path).get("slug")
    except Exception:
        return None
    if not isinstance(slug, str):
        return None
    try:
        get_project(slug)
    except NotFoundError:
        return None
    return slug


def set_active_project(slug: str) -> None:
    get_project(slug)
    _write_json(active_file(), {"slug": slug})


def archive_project(slug: str) -> Project:
    """Hide a project from the app without touching its local root directory."""
    with _LOCK:
        project = get_project(slug)
        was_active = get_active_project_slug() == slug
        now = utc_now()
        archived = replace(project, archived_at=now, updated_at=now)
        _write_json(_project_file(slug), asdict(archived))

        for child in list_projects(include_archived=True):
            if child.archived_at is not None or child.parent_slug != slug:
                continue
            promoted = replace(child, parent_slug=project.parent_slug, updated_at=now)
            _write_json(_project_file(child.slug), asdict(promoted))

        if was_active:
            remaining = list_projects()
            if remaining:
                _write_json(active_file(), {"slug": remaining[0].slug})
            elif active_file().exists():
                active_file().unlink()
        return archived


def create_session(project_slug: str, title: str = "新对话") -> Session:
    get_project(project_slug)
    now = utc_now()
    session_id = uuid.uuid4().hex
    session = Session(
        id=session_id,
        title=title.strip() or "新对话",
        project_slug=project_slug,
        created_at=now,
        updated_at=now,
        message_count=0,
        deleted_at=None,
    )
    with _LOCK:
        _session_dir(project_slug).mkdir(parents=True, exist_ok=True)
        _write_json(_session_meta_file(project_slug, session_id), asdict(session))
        _session_jsonl_file(project_slug, session_id).touch()
    return session


def _find_session_meta(session_id: str, *, include_deleted: bool = False) -> tuple[Session, Path]:
    ensure_data_dirs()
    for path in sessions_dir().glob(f"*/{session_id}.meta.json"):
        session = _session_from_payload(_read_json(path))
        if session.deleted_at is not None and not include_deleted:
            break
        return session, path
    raise NotFoundError(f"会话不存在：{session_id}")


def get_session(session_id: str) -> Session:
    return _find_session_meta(session_id)[0]


def list_sessions(project_slug: str, *, limit: int = 60) -> list[Session]:
    get_project(project_slug)
    folder = _session_dir(project_slug)
    if not folder.exists():
        return []
    sessions = [
        _session_from_payload(_read_json(path))
        for path in folder.glob("*.meta.json")
    ]
    sessions = [session for session in sessions if session.deleted_at is None]
    sessions.sort(key=lambda item: item.updated_at, reverse=True)
    return sessions[:limit]


def update_session(session_id: str, *, title: str) -> Session:
    cleaned = title.strip()
    if not cleaned:
        raise ValidationError("会话名称不能为空")
    if len(cleaned) > 80:
        raise ValidationError("会话名称不能超过 80 个字符")
    with _LOCK:
        session, meta_path = _find_session_meta(session_id)
        updated = replace(session, title=cleaned, updated_at=utc_now())
        _write_json(meta_path, asdict(updated))
        return updated


def archive_session(session_id: str) -> Session:
    """Soft-delete a session while preserving its metadata and JSONL archive."""
    with _LOCK:
        session, meta_path = _find_session_meta(session_id, include_deleted=True)
        if session.deleted_at is not None:
            return session
        now = utc_now()
        archived = replace(session, deleted_at=now, updated_at=now)
        _write_json(meta_path, asdict(archived))
        return archived


def append_message(
    session_id: str,
    *,
    role: str,
    content: str,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with _LOCK:
        session, meta_path = _find_session_meta(session_id)
        now = utc_now()
        message = {
            "id": uuid.uuid4().hex,
            "role": role,
            "content": content,
            "ts": now,
            "meta": meta or {},
        }
        jsonl_path = _session_jsonl_file(session.project_slug, session_id)
        with jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(message, ensure_ascii=False) + "\n")
        updated = Session(
            id=session.id,
            title=session.title,
            project_slug=session.project_slug,
            created_at=session.created_at,
            updated_at=now,
            message_count=session.message_count + 1,
            deleted_at=session.deleted_at,
        )
        _write_json(meta_path, asdict(updated))
        return message


def replace_messages(session_id: str, messages: list[dict[str, Any]]) -> None:
    """Replace a session JSONL file with already-normalized message rows."""
    with _LOCK:
        session, meta_path = _find_session_meta(session_id)
        now = utc_now()
        jsonl_path = _session_jsonl_file(session.project_slug, session_id)
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(message, ensure_ascii=False) for message in messages]
        jsonl_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        updated = Session(
            id=session.id,
            title=session.title,
            project_slug=session.project_slug,
            created_at=session.created_at,
            updated_at=now,
            message_count=len(messages),
            deleted_at=session.deleted_at,
        )
        _write_json(meta_path, asdict(updated))


def read_messages(session_id: str, *, limit: int = 60) -> list[dict[str, Any]]:
    session = get_session(session_id)
    path = _session_jsonl_file(session.project_slug, session_id)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows[-limit:] if limit > 0 else rows


def global_memory_file() -> Path:
    return memory_dir() / "global.md"


def project_memory_file(slug: str) -> Path:
    return memory_dir() / "projects" / f"{slug}.md"


def read_memory(slug: str) -> dict[str, str]:
    get_project(slug)
    ensure_data_dirs()
    project_path = project_memory_file(slug)
    project_path.parent.mkdir(parents=True, exist_ok=True)
    project_path.touch(exist_ok=True)
    return {
        "global": global_memory_file().read_text(encoding="utf-8"),
        "project": project_path.read_text(encoding="utf-8"),
    }


def write_project_memory(slug: str, content: str) -> str:
    get_project(slug)
    ensure_data_dirs()
    path = project_memory_file(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return content
