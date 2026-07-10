from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_settings


MAX_MEMORY_CONTENT_CHARS = 500_000
MAX_MEMORY_DESCRIPTION_CHARS = 1_000
MAX_PLAN_STEPS = 40
MAX_CONTEXT_CHARS = 30_000
NAME_RE = re.compile(r"^[0-9A-Za-z\u4e00-\u9fff][0-9A-Za-z\u4e00-\u9fff _.-]{0,79}$")
TYPE_RE = re.compile(r"^[0-9A-Za-z_-]{1,40}$")
VALID_SCOPES = {"project", "global"}


@dataclass(frozen=True)
class MemoryEntry:
    name: str
    description: str
    type: str
    content: str
    scope: str
    project_slug: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class PlanStep:
    idx: int
    content: str
    status: str = "pending"
    note: str = ""


@dataclass(frozen=True)
class WorkPlan:
    title: str
    steps: list[PlanStep]
    created_at: str
    updated_at: str


class WorkStateError(Exception):
    pass


def memory_write(
    project_slug: str,
    *,
    name: str,
    description: str,
    type: str,
    content: str,
    scope: str = "project",
) -> str:
    try:
        scope_name = _validate_scope(scope)
        safe_name = _validate_name(name)
        memory_type = _validate_type(type)
        if len(description) > MAX_MEMORY_DESCRIPTION_CHARS:
            raise WorkStateError("description 超过 1000 字符上限")
        if len(content) > MAX_MEMORY_CONTENT_CHARS:
            raise WorkStateError("content 超过 500k 字符上限")
        path = _memory_file(scope_name, project_slug, safe_name)
        now = _utc_now()
        created_at = now
        if path.exists():
            try:
                created_at = _read_json(path).get("created_at") or now
            except Exception:
                created_at = now
        entry = MemoryEntry(
            name=safe_name,
            description=description.strip(),
            type=memory_type,
            content=content,
            scope=scope_name,
            project_slug=project_slug if scope_name == "project" else None,
            created_at=created_at,
            updated_at=now,
        )
        _write_json(path, asdict(entry))
        return f"✓ 已写入{_scope_label(scope_name, project_slug)} memory：{safe_name}（type={memory_type}）"
    except WorkStateError as exc:
        return f"ERROR: {exc}"


def memory_read(project_slug: str, *, name: str, scope: str = "project") -> str:
    try:
        scope_name = _validate_scope(scope)
        safe_name = _validate_name(name)
        path = _memory_file(scope_name, project_slug, safe_name)
        if not path.exists():
            raise WorkStateError(f"memory 不存在：{safe_name}")
        entry = MemoryEntry(**_read_json(path))
        return (
            f"# {entry.name}\n"
            f"- scope: {entry.scope}\n"
            f"- type: {entry.type}\n"
            f"- description: {entry.description}\n"
            f"- created_at: {entry.created_at}\n"
            f"- updated_at: {entry.updated_at}\n"
            "\n---\n\n"
            f"{entry.content}"
        )
    except WorkStateError as exc:
        return f"ERROR: {exc}"


def memory_list(project_slug: str, *, scope: str = "project") -> str:
    try:
        scope_name = _validate_scope(scope)
        entries = _list_memory_entries(scope_name, project_slug)
        label = _scope_label(scope_name, project_slug)
        if not entries:
            return f"（{label} memory 为空）"
        lines = [f"# {label} memory 索引"]
        for entry in entries:
            lines.append(f"- {entry.name} ({entry.type})：{entry.description or '（无描述）'} · updated {entry.updated_at[:19]}")
        return "\n".join(lines)
    except WorkStateError as exc:
        return f"ERROR: {exc}"


def build_memory_context(project_slug: str) -> str:
    index_rows: list[str] = []
    body_sections: list[str] = []
    for scope in ("global", "project"):
        try:
            entries = _list_memory_entries(scope, project_slug)
        except Exception:
            entries = []
        for entry in entries:
            index_rows.append(
                f"- [{scope}] {entry.name} ({entry.type})：{entry.description or '（无描述）'}；"
                f"需要正文时调用 memory_read(name={entry.name!r}, scope={scope!r})"
            )
            body_sections.append(
                f"### [{scope}] {entry.name}\n"
                f"- type: {entry.type}\n"
                f"- description: {entry.description or '（无描述）'}\n"
                f"- updated_at: {entry.updated_at}\n\n"
                f"{entry.content.strip() or '（空正文）'}"
            )
    if not index_rows:
        return ""
    text = (
        "## 工作记忆索引（固定注入）\n"
        + "\n".join(index_rows)
        + "\n\n## 工作记忆正文（固定注入；需要逐字引用时仍可 memory_read 重读）\n"
        + "\n\n".join(body_sections)
    )
    return _truncate_context(text)


def build_memory_index_context(project_slug: str) -> str:
    """Backward-compatible alias; memory bodies are now fixed-injected too."""
    return build_memory_context(project_slug)


def plan_my_steps(project_slug: str, *, steps: list[Any], title: str = "当前计划") -> str:
    try:
        if not isinstance(steps, list) or not steps:
            raise WorkStateError("steps 必须是非空数组")
        if len(steps) > MAX_PLAN_STEPS:
            raise WorkStateError(f"steps 超过 {MAX_PLAN_STEPS} 条上限")
        normalized: list[PlanStep] = []
        for index, item in enumerate(steps, start=1):
            if isinstance(item, dict):
                content = str(item.get("content") or "").strip()
                note = str(item.get("note") or "").strip()
            else:
                content = str(item).strip()
                note = ""
            if not content:
                raise WorkStateError(f"第 {index} 条 step 为空")
            normalized.append(PlanStep(idx=index, content=content[:500], note=note[:500]))
        now = _utc_now()
        plan = WorkPlan(title=(title.strip() or "当前计划")[:120], steps=normalized, created_at=now, updated_at=now)
        _write_json(_plan_file(project_slug), _plan_to_payload(plan))
        return f"✓ 已创建计划：{plan.title}（{len(plan.steps)} 步）"
    except WorkStateError as exc:
        return f"ERROR: {exc}"


def mark_step_done(project_slug: str, *, idx: int, note: str = "") -> str:
    try:
        plan = _read_plan(project_slug)
        if idx < 1 or idx > len(plan.steps):
            raise WorkStateError(f"idx 超出范围：1..{len(plan.steps)}")
        steps = []
        for step in plan.steps:
            if step.idx == idx:
                steps.append(PlanStep(idx=step.idx, content=step.content, status="done", note=note.strip()[:500] or step.note))
            else:
                steps.append(step)
        updated = WorkPlan(title=plan.title, steps=steps, created_at=plan.created_at, updated_at=_utc_now())
        _write_json(_plan_file(project_slug), _plan_to_payload(updated))
        return f"✓ 已完成第 {idx} 步：{steps[idx - 1].content}"
    except WorkStateError as exc:
        return f"ERROR: {exc}"


def build_plan_context(project_slug: str) -> str:
    try:
        plan = _read_plan(project_slug)
    except WorkStateError:
        return ""
    lines = [f"## 当前计划（固定注入）", f"- 标题：{plan.title}", f"- updated_at：{plan.updated_at}"]
    for step in plan.steps:
        marker = "☑" if step.status == "done" else "☐"
        suffix = f"（{step.note}）" if step.note else ""
        lines.append(f"{marker} {step.idx}. {step.content}{suffix}")
    return _truncate_context("\n".join(lines))


def execute_state_tool(project_slug: str, name: str, args: dict[str, Any]) -> str:
    if name == "memory_write":
        return memory_write(
            project_slug,
            name=str(args.get("name") or ""),
            description=str(args.get("description") or ""),
            type=str(args.get("type") or "note"),
            content=str(args.get("content") or ""),
            scope=str(args.get("scope") or "project"),
        )
    if name == "memory_read":
        return memory_read(
            project_slug,
            name=str(args.get("name") or ""),
            scope=str(args.get("scope") or "project"),
        )
    if name == "memory_list":
        return memory_list(project_slug, scope=str(args.get("scope") or "project"))
    if name == "plan_my_steps":
        return plan_my_steps(
            project_slug,
            steps=args.get("steps") if isinstance(args.get("steps"), list) else [],
            title=str(args.get("title") or "当前计划"),
        )
    if name == "mark_step_done":
        try:
            idx = int(args.get("idx"))
        except (TypeError, ValueError):
            return "ERROR: idx 必须是整数"
        return mark_step_done(project_slug, idx=idx, note=str(args.get("note") or ""))
    return f"ERROR: 未知状态工具：{name}"


def state_tool_names() -> set[str]:
    return {"memory_read", "memory_write", "memory_list", "plan_my_steps", "mark_step_done"}


def archive_and_clear_project_state(project_slug: str, backup_dir: Path) -> None:
    """Archive and remove project-scoped structured memory and its active plan."""
    memory_folder = _memory_dir("project", project_slug)
    plan_path = _plan_file(project_slug)
    backup_dir.mkdir(parents=True, exist_ok=True)
    if memory_folder.exists():
        shutil.copytree(memory_folder, backup_dir / "structured-memory")
        shutil.rmtree(memory_folder)
    if plan_path.exists():
        shutil.copy2(plan_path, backup_dir / "plan.json")
        plan_path.unlink()


def _state_root() -> Path:
    override = os.getenv("WORKMODE_PUBLIC_DATA_DIR")
    base = Path(override).expanduser().resolve() if override else get_settings().data_dir
    return base / "work" / "state"


def _memory_dir(scope: str, project_slug: str) -> Path:
    if scope == "global":
        return _state_root() / "memory" / "global"
    return _state_root() / "memory" / "projects" / project_slug


def _memory_file(scope: str, project_slug: str, name: str) -> Path:
    return _memory_dir(scope, project_slug) / f"{name}.json"


def _plan_file(project_slug: str) -> Path:
    return _state_root() / "plans" / f"{project_slug}.json"


def _list_memory_entries(scope: str, project_slug: str) -> list[MemoryEntry]:
    folder = _memory_dir(scope, project_slug)
    if not folder.exists():
        return []
    entries: list[MemoryEntry] = []
    for path in sorted(folder.glob("*.json")):
        try:
            entries.append(MemoryEntry(**_read_json(path)))
        except Exception:
            continue
    entries.sort(key=lambda item: item.updated_at, reverse=True)
    return entries


def _read_plan(project_slug: str) -> WorkPlan:
    path = _plan_file(project_slug)
    if not path.exists():
        raise WorkStateError("当前没有计划；先调用 plan_my_steps")
    payload = _read_json(path)
    return WorkPlan(
        title=str(payload.get("title") or "当前计划"),
        steps=[PlanStep(**item) for item in payload.get("steps", [])],
        created_at=str(payload.get("created_at") or ""),
        updated_at=str(payload.get("updated_at") or ""),
    )


def _plan_to_payload(plan: WorkPlan) -> dict[str, Any]:
    return {
        "title": plan.title,
        "steps": [asdict(step) for step in plan.steps],
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _validate_scope(scope: str) -> str:
    if scope not in VALID_SCOPES:
        raise WorkStateError("scope 必须是 project 或 global")
    return scope


def _validate_name(name: str) -> str:
    cleaned = name.strip()
    if not NAME_RE.match(cleaned):
        raise WorkStateError("name 只能包含中英文、数字、空格、点、下划线和短横线，且不能包含路径分隔符")
    return cleaned


def _validate_type(type_name: str) -> str:
    cleaned = type_name.strip() or "note"
    if not TYPE_RE.match(cleaned):
        raise WorkStateError("type 只能包含英数字、下划线和短横线")
    return cleaned


def _scope_label(scope: str, project_slug: str) -> str:
    return "全局" if scope == "global" else f"项目「{project_slug}」"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate_context(text: str) -> str:
    if len(text) <= MAX_CONTEXT_CHARS:
        return text
    return text[:MAX_CONTEXT_CHARS] + "\n…[工作状态上下文已截断]"
