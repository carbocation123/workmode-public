from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_MAX_DEPTH = 5


@dataclass(frozen=True)
class ImportedFile:
    path: str
    char_count: int
    token_count: int


@dataclass(frozen=True)
class ExpansionResult:
    text: str
    files: tuple[ImportedFile, ...]
    errors: tuple[str, ...]


@dataclass
class _ExpansionState:
    root: Path
    max_depth: int
    stack: list[Path] = field(default_factory=list)
    files: list[ImportedFile] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def count_text_tokens(text: str) -> int:
    # Conservative approximate counter. Good enough for context budgeting without
    # coupling this standalone app to one provider's tokenizer.
    if not text:
        return 0
    ascii_chars = sum(1 for ch in text if ord(ch) < 128)
    non_ascii_chars = len(text) - ascii_chars
    return max(1, ascii_chars // 4 + non_ascii_chars // 2)


def _record_warning(state: _ExpansionState, path: str, reason: str) -> str:
    warning = f"【固定导入失败：{path} — {reason}】"
    state.errors.append(warning)
    return warning


def _directive_path(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("@") or stripped.startswith("@@"):
        return None
    path = stripped[1:].strip()
    return path or None


def _resolve_import(raw_path: str, *, base_dir: Path, state: _ExpansionState) -> tuple[Path | None, str | None]:
    candidate_path = Path(raw_path)
    if candidate_path.is_absolute():
        return None, "只允许项目内相对路径"
    candidate = (base_dir / candidate_path).resolve()
    try:
        candidate.relative_to(state.root)
    except ValueError:
        return None, "路径越界"
    return candidate, None


def _display_path(path: Path, state: _ExpansionState) -> str:
    return path.relative_to(state.root).as_posix()


def _expand_file(raw_path: str, *, base_dir: Path, depth: int, state: _ExpansionState) -> str:
    if depth > state.max_depth:
        return _record_warning(state, raw_path, f"超过最大嵌套层数 {state.max_depth}")

    path, error = _resolve_import(raw_path, base_dir=base_dir, state=state)
    if error or path is None:
        return _record_warning(state, raw_path, error or "路径无效")

    display = _display_path(path, state)
    if path in state.stack:
        chain = " → ".join([_display_path(item, state) for item in state.stack] + [display])
        return _record_warning(state, display, f"循环引用：{chain}")
    if not path.exists():
        return _record_warning(state, display, "文件不存在")
    if not path.is_file():
        return _record_warning(state, display, "目标不是文件")

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return _record_warning(state, display, "不是 UTF-8 文本文件")
    except OSError:
        return _record_warning(state, display, "读取失败")

    if "\x00" in content:
        return _record_warning(state, display, "疑似二进制文件")

    state.files.append(
        ImportedFile(path=display, char_count=len(content), token_count=count_text_tokens(content))
    )
    state.stack.append(path)
    try:
        expanded = _expand_text(content, base_dir=path.parent, depth=depth, state=state)
    finally:
        state.stack.pop()
    return "\n".join(
        part
        for part in (f"【固定导入：{display}】", expanded.rstrip(), f"【固定导入结束：{display}】")
        if part
    )


def _expand_text(text: str, *, base_dir: Path, depth: int, state: _ExpansionState) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        raw_path = _directive_path(line)
        if raw_path is None:
            lines.append(line)
        else:
            lines.append(_expand_file(raw_path, base_dir=base_dir, depth=depth + 1, state=state))
    return "\n".join(lines)


def expand_project_imports_detailed(
    text: str,
    *,
    project_root: str | Path,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> ExpansionResult:
    root = Path(project_root).resolve()
    state = _ExpansionState(root=root, max_depth=max(1, max_depth))
    expanded = _expand_text(text, base_dir=root, depth=0, state=state)
    return ExpansionResult(text=expanded, files=tuple(state.files), errors=tuple(state.errors))

