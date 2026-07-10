from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import storage, work_state
from .config import ROOT_DIR


TUTORIAL_KIND = "workmode-public-tutorial"
TUTORIAL_MARKER = "WORKMODE_TUTORIAL.json"
TUTORIAL_FOLDER_NAME = "Workmode-Public-科研协作教程"
DEFAULT_TEMPLATE_ROOT = ROOT_DIR / "tutorial-project"


class TutorialProjectError(storage.ValidationError):
    pass


@dataclass(frozen=True)
class TutorialInstallResult:
    project: storage.Project
    session: storage.Session
    project_is_tutorial: bool = True


@dataclass(frozen=True)
class TutorialResetResult:
    project: storage.Project
    session: storage.Session
    backup_dir: Path


def _marker_payload(root: Path) -> dict[str, object] | None:
    marker = root / TUTORIAL_MARKER
    if not marker.is_file():
        return None
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def is_tutorial_root(root: str | Path) -> bool:
    payload = _marker_payload(Path(root).expanduser().resolve())
    return bool(payload and payload.get("kind") == TUTORIAL_KIND)


def _registry_file(project_slug: str) -> Path:
    return storage.work_dir() / "tutorial-projects" / f"{project_slug}.json"


def _write_registry(project: storage.Project) -> None:
    path = _registry_file(project.slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "kind": TUTORIAL_KIND,
                "project_slug": project.slug,
                "root_path": str(Path(project.root_path).resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def is_tutorial_project(project: storage.Project) -> bool:
    if not is_tutorial_root(project.root_path):
        return False
    registry = _registry_file(project.slug)
    if not registry.is_file():
        return False
    try:
        payload = json.loads(registry.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return bool(
        isinstance(payload, dict)
        and payload.get("kind") == TUTORIAL_KIND
        and payload.get("project_slug") == project.slug
        and payload.get("root_path") == str(Path(project.root_path).resolve())
    )


def _validated_template(template_root: str | Path | None) -> Path:
    root = Path(template_root or DEFAULT_TEMPLATE_ROOT).expanduser().resolve()
    if not root.is_dir() or not is_tutorial_root(root):
        raise TutorialProjectError(f"内置教程模板缺失或标识无效：{root}")
    if not (root / "WORKMODE.md").is_file():
        raise TutorialProjectError("内置教程模板缺少 WORKMODE.md")
    return root


def install_tutorial_project(
    parent_path: str,
    *,
    template_root: str | Path | None = None,
) -> TutorialInstallResult:
    template = _validated_template(template_root)
    parent = Path(parent_path).expanduser().resolve()
    if not parent.is_dir():
        raise TutorialProjectError("教程保存位置不存在或不是文件夹")
    target = parent / TUTORIAL_FOLDER_NAME
    if target.exists():
        raise TutorialProjectError(f"教程文件夹已存在：{target}；请打开现有项目或选择其它位置")

    shutil.copytree(template, target)
    project: storage.Project | None = None
    try:
        project = storage.create_project("科研协作教程", str(target), "Workmode Public 官方主持式科研协作教程")
        _write_registry(project)
        session = storage.create_session(project.slug, "从这里开始")
    except Exception:
        if project is not None:
            try:
                storage.archive_project(project.slug)
            except Exception:
                pass
        shutil.rmtree(target, ignore_errors=True)
        raise
    return TutorialInstallResult(project=project, session=session)


def _new_backup_dir(project_slug: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    return storage.work_dir() / "tutorial-backups" / project_slug / f"{stamp}-{suffix}"


def _replace_project_files(root: Path, template: Path) -> None:
    if root == template:
        raise TutorialProjectError("不能把内置教程模板本身作为可重置项目")
    for child in root.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)
    shutil.copytree(template, root, dirs_exist_ok=True)


def reset_tutorial_project(
    project_slug: str,
    *,
    template_root: str | Path | None = None,
) -> TutorialResetResult:
    template = _validated_template(template_root)
    project = storage.get_project(project_slug)
    root = Path(project.root_path).expanduser().resolve()
    if not root.is_dir() or not is_tutorial_project(project):
        raise TutorialProjectError("该项目不是 Workmode Public 官方教程，拒绝重置")

    backup_dir = _new_backup_dir(project_slug)
    backup_dir.mkdir(parents=True, exist_ok=False)
    shutil.copytree(root, backup_dir / "project-files", symlinks=True)
    project_memory = storage.read_memory(project_slug)["project"]
    (backup_dir / "project-memory.md").write_text(project_memory, encoding="utf-8")
    work_state.archive_and_clear_project_state(project_slug, backup_dir / "work-state")

    for session in storage.list_sessions(project_slug, limit=10_000):
        storage.archive_session(session.id)
    _replace_project_files(root, template)
    storage.write_project_memory(project_slug, "")
    updated = storage.update_project(project_slug)
    session = storage.create_session(project_slug, "从这里开始")
    storage.set_active_project(project_slug)
    return TutorialResetResult(project=updated, session=session, backup_dir=backup_dir)
