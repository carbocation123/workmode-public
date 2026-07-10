from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Literal

from .web_tools import WEB_TOOL_SCHEMAS, execute_web_tool, web_tool_names


TEXT_EXTENSIONS = frozenset(
    {
        ".bash",
        ".bat",
        ".bib",
        ".c",
        ".cc",
        ".cfg",
        ".cjs",
        ".cmd",
        ".conf",
        ".cpp",
        ".css",
        ".csv",
        ".cxx",
        ".dat",
        ".dockerignore",
        ".gradle",
        ".go",
        ".h",
        ".hpp",
        ".htm",
        ".html",
        ".ini",
        ".ipynb",
        ".java",
        ".js",
        ".json",
        ".jsonl",
        ".jsx",
        ".kt",
        ".kts",
        ".less",
        ".lock",
        ".log",
        ".markdown",
        ".md",
        ".mjs",
        ".php",
        ".pl",
        ".properties",
        ".ps1",
        ".py",
        ".r",
        ".rb",
        ".rs",
        ".sass",
        ".scss",
        ".sh",
        ".sql",
        ".svelte",
        ".swift",
        ".tex",
        ".toml",
        ".ts",
        ".tsv",
        ".tsx",
        ".txt",
        ".vue",
        ".xhtml",
        ".xml",
        ".yaml",
        ".yml",
        ".zsh",
    }
)
TEXT_FILENAMES = frozenset({".editorconfig", ".gitattributes", ".gitignore", "dockerfile", "license", "makefile", "readme"})
SKIP_FILES = frozenset({".env", ".env.local", ".env.production", ".env.development"})
SKIP_DIRS = frozenset({".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build", ".pytest_cache", ".idea", ".vscode"})

MAX_READ_BYTES = 5 * 1024 * 1024
MAX_WRITE_CHARS = 5 * 1024 * 1024
MAX_RESULT_CHARS = 30_000
DEFAULT_COMMAND_TIMEOUT = 30
MAX_COMMAND_TIMEOUT = 300
DEFAULT_READ_LIMIT = 2000
MAX_READ_LIMIT = 5000
DEFAULT_HEAD_LIMIT = 200
MAX_HEAD_LIMIT = 1000
LINE_TRUNCATE = 2000

OutputMode = Literal["content", "files_with_matches", "count"]


@dataclass(frozen=True)
class ProjectToolResult:
    ok: bool
    content: str
    changed_paths: list[str] = field(default_factory=list)


class ProjectToolError(Exception):
    pass


BLACKLIST_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\brm\s+-[a-zA-Z]*[rR][a-zA-Z]*[fF]"), "rm -rf 类递归强删"),
    (re.compile(r"\brm\s+-[a-zA-Z]*[fF][a-zA-Z]*[rR]"), "rm -fr 类递归强删"),
    (re.compile(r"\bgit\s+push\s+.*(--force|-f)\b"), "git push --force"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard"),
    (re.compile(r"\bgit\s+clean\s+-[a-zA-Z]*[fF]"), "git clean -f"),
    (re.compile(r"\bgit\s+branch\s+-[a-zA-Z]*[DD]"), "git branch -D"),
    (re.compile(r"--no-verify\b"), "--no-verify"),
    (re.compile(r"\bsudo\b"), "sudo 提权"),
    (re.compile(r"\bmkfs\.|\bdd\s+if=|\bshred\b"), "磁盘/低层操作"),
]


PROJECT_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "project_read",
            "description": (
                "带行号读取当前项目内 UTF-8 文本文件。路径必须是项目根目录内相对路径。"
                "默认前 2000 行；大文件用 offset+limit 分段续读。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "项目相对路径"},
                    "offset": {"type": "integer", "description": "起始行号，0-based，默认 0", "default": 0},
                    "limit": {"type": "integer", "description": "最多读取行数，默认 2000，上限 5000", "default": DEFAULT_READ_LIMIT},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "project_write",
            "description": (
                "写入当前项目内 UTF-8 文本文件，可新建父目录。用于新建文件或整体重写；"
                "局部修改优先用 project_edit。拒绝 .env 等敏感配置文件。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "项目相对路径"},
                    "content": {"type": "string", "description": "完整文件内容，UTF-8 文本，上限 5MB"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "project_edit",
            "description": (
                "对当前项目内已有 UTF-8 文本文件做精确字符串替换。old_string 默认必须唯一匹配；"
                "多处替换需显式传 replace_all=true。修改前通常先 project_read。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "项目相对路径"},
                    "old_string": {"type": "string", "description": "要替换的精确文本，包含必要空白和上下文"},
                    "new_string": {"type": "string", "description": "替换后的文本"},
                    "replace_all": {"type": "boolean", "description": "是否全部替换，默认 false", "default": False},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "project_list_dir",
            "description": "列出当前项目内某个目录的一层子目录和文件。path 默认 '.'。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "项目相对目录，默认 '.'", "default": "."},
                    "head_limit": {"type": "integer", "description": "最多返回条数，默认 200，上限 1000", "default": DEFAULT_HEAD_LIMIT},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "project_glob",
            "description": "按 pathlib glob pattern 递归查找当前项目内文件，自动跳过 .git/node_modules/.venv/dist/build 等目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "例如 '**/*.py'、'src/**/*.tsx'"},
                    "head_limit": {"type": "integer", "description": "最多返回条数，默认 200，上限 1000", "default": DEFAULT_HEAD_LIMIT},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "project_grep",
            "description": (
                "在当前项目内按 Python re 正则搜索 UTF-8 文本文件内容。"
                "output_mode: files_with_matches / content / count。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Python re 正则"},
                    "path": {"type": "string", "description": "搜索子目录或文件，项目相对路径；不填为项目根"},
                    "glob": {"type": "string", "description": "文件名 fnmatch 过滤，例如 '*.py'"},
                    "output_mode": {
                        "type": "string",
                        "enum": ["content", "files_with_matches", "count"],
                        "description": "输出模式，默认 files_with_matches",
                        "default": "files_with_matches",
                    },
                    "case_insensitive": {"type": "boolean", "default": False},
                    "head_limit": {"type": "integer", "description": "最多返回条数，默认 200，上限 1000", "default": DEFAULT_HEAD_LIMIT},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "project_bash",
            "description": (
                "在当前项目根目录运行 shell 命令，返回 exit_code/stdout/stderr。"
                "用于跑测试、git status/diff、构建检查等。命中破坏性命令黑名单会拒绝。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "shell 命令字符串"},
                    "timeout": {"type": "integer", "description": "超时秒数，默认 30，上限 300", "default": DEFAULT_COMMAND_TIMEOUT},
                    "description": {"type": "string", "description": "一句话说明这条命令要做什么"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "project_python",
            "description": "在当前项目根目录运行一段 Python 代码，返回 exit_code/stdout/stderr。适合小规模数据处理和验证脚本。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python 代码，多行可用"},
                    "timeout": {"type": "integer", "description": "超时秒数，默认 30，上限 300", "default": DEFAULT_COMMAND_TIMEOUT},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "project_python_file",
            "description": (
                "用 Workmode Public 自带的 Python 运行当前项目内已有的 .py 脚本，"
                "不依赖用户安装 Python。参数按数组传入，不经过 shell。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "项目内 .py 脚本的相对路径"},
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "传给脚本的参数数组，不包含 Python 命令和脚本路径",
                        "default": [],
                    },
                    "timeout": {"type": "integer", "description": "超时秒数，默认 30，上限 300", "default": DEFAULT_COMMAND_TIMEOUT},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_write",
            "description": "写入或覆盖工作记忆条目。记忆索引会固定注入上下文，正文按需用 memory_read 读取。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "记忆名，只能用中英文、数字、空格、点、下划线、短横线"},
                    "description": {"type": "string", "description": "简短描述，会进入固定上下文索引"},
                    "type": {"type": "string", "description": "类型，如 protocol/note/decision/reference"},
                    "content": {"type": "string", "description": "记忆正文"},
                    "scope": {"type": "string", "enum": ["project", "global"], "description": "project=当前项目，global=所有项目共享", "default": "project"},
                },
                "required": ["name", "description", "type", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_read",
            "description": "读取一条工作记忆的完整正文。先看固定注入的工作记忆索引，再按 name/scope 读取。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "记忆名"},
                    "scope": {"type": "string", "enum": ["project", "global"], "default": "project"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_list",
            "description": "列出 project 或 global 工作记忆索引。",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["project", "global"], "default": "project"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_my_steps",
            "description": "创建或重置当前项目的多步计划。适合复杂工程任务开始时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "计划标题"},
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "步骤列表，按执行顺序排列",
                    },
                },
                "required": ["steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_step_done",
            "description": "把当前计划中的某一步标记为完成。",
            "parameters": {
                "type": "object",
                "properties": {
                    "idx": {"type": "integer", "description": "步骤编号，1-based"},
                    "note": {"type": "string", "description": "完成说明，可选"},
                },
                "required": ["idx"],
            },
        },
    },
]
PROJECT_TOOL_SCHEMAS.extend(WEB_TOOL_SCHEMAS)


def execute_project_tool(
    project_slug: str,
    name: str,
    args: dict[str, Any],
    *,
    cancel_event: threading.Event | None = None,
) -> ProjectToolResult:
    from .storage import get_project
    from .work_state import execute_state_tool, state_tool_names

    if cancel_event is not None and cancel_event.is_set():
        return ProjectToolResult(ok=False, content="ERROR: 用户已停止本轮对话")
    if name in web_tool_names():
        result = execute_web_tool(name, args, cancel_event=cancel_event)
        return ProjectToolResult(ok=result.ok, content=result.content)
    if name in state_tool_names():
        result = execute_state_tool(project_slug, name, args)
        return ProjectToolResult(ok=not result.startswith("ERROR:"), content=result)
    project = get_project(project_slug)
    return execute_project_tool_at_root(Path(project.root_path), name, args, cancel_event=cancel_event)


def execute_project_tool_at_root(
    root: Path,
    name: str,
    args: dict[str, Any],
    *,
    cancel_event: threading.Event | None = None,
) -> ProjectToolResult:
    try:
        _raise_if_cancelled(cancel_event)
        project_root = root.expanduser().resolve()
        if not project_root.exists() or not project_root.is_dir():
            raise ProjectToolError("项目根目录不存在或不是文件夹")

        if name == "project_read":
            return _project_read(project_root, args)
        if name == "project_write":
            return _project_write(project_root, args)
        if name == "project_edit":
            return _project_edit(project_root, args)
        if name == "project_list_dir":
            return _project_list_dir(project_root, args)
        if name == "project_glob":
            return _project_glob(project_root, args, cancel_event=cancel_event)
        if name == "project_grep":
            return _project_grep(project_root, args, cancel_event=cancel_event)
        if name == "project_bash":
            return _project_bash(project_root, args, cancel_event=cancel_event)
        if name == "project_python":
            return _project_python(project_root, args, cancel_event=cancel_event)
        if name == "project_python_file":
            return _project_python_file(project_root, args, cancel_event=cancel_event)
        raise ProjectToolError(f"未知项目工具：{name}")
    except ProjectToolError as exc:
        return ProjectToolResult(ok=False, content=f"ERROR: {exc}")
    except Exception as exc:
        return ProjectToolResult(ok=False, content=f"ERROR: 工具执行失败：{exc}")


def project_tool_names() -> set[str]:
    return {item["function"]["name"] for item in PROJECT_TOOL_SCHEMAS}


def _project_read(root: Path, args: dict[str, Any]) -> ProjectToolResult:
    path = _resolve_project_path(root, _require_string(args, "path"))
    if not path.exists():
        raise ProjectToolError(f"文件不存在：{_display_path(root, path)}")
    if not path.is_file():
        raise ProjectToolError(f"不是文件：{_display_path(root, path)}（目录请用 project_list_dir）")

    text = _read_utf8_text(path)
    lines = text.splitlines()
    total = len(lines)
    offset = max(0, _optional_int(args, "offset", 0))
    limit = min(max(1, _optional_int(args, "limit", DEFAULT_READ_LIMIT)), MAX_READ_LIMIT)
    selected = lines[offset : offset + limit]

    body: list[str] = []
    for line_no, line in enumerate(selected, start=offset + 1):
        if len(line) > LINE_TRUNCATE:
            line = line[:LINE_TRUNCATE] + "…[截断]"
        body.append(f"{line_no}\t{line}")

    end = offset + len(selected)
    header = f"# {_display_path(root, path)}（显示第 {offset + 1}–{end} 行 / 总 {total} 行）"
    if end < total:
        body.append(f"\n…（剩余 {total - end} 行未显示，传 offset={end} 续读）")
    return _ok(header + "\n" + "\n".join(body))


def _project_write(root: Path, args: dict[str, Any]) -> ProjectToolResult:
    path = _resolve_project_path(root, _require_string(args, "path"), must_exist=False)
    content = _require_string(args, "content")
    if len(content) > MAX_WRITE_CHARS:
        raise ProjectToolError("content 超过 5MB 上限")
    if not _is_text_path(path):
        raise ProjectToolError("只允许写入文本/代码/Markdown 白名单文件")
    if path.exists() and path.is_dir():
        raise ProjectToolError("目标路径是目录，不能覆盖为文件")

    path.parent.mkdir(parents=True, exist_ok=True)
    _write_utf8_text_atomic(path, content)
    rel = _display_path(root, path)
    return _ok(f"ok · 写入 {rel} · {len(content)} 字符", changed_paths=[rel])


def _project_edit(root: Path, args: dict[str, Any]) -> ProjectToolResult:
    path = _resolve_project_path(root, _require_string(args, "path"))
    old_string = _require_string(args, "old_string")
    new_string = _require_string(args, "new_string")
    replace_all = bool(args.get("replace_all", False))

    if not old_string:
        raise ProjectToolError("old_string 不能为空")
    if old_string == new_string:
        raise ProjectToolError("old_string == new_string，无替换")
    if not path.exists() or not path.is_file():
        raise ProjectToolError(f"文件不存在：{_display_path(root, path)}")

    text = _read_utf8_text(path)
    occurrences = text.count(old_string)
    if occurrences == 0:
        raise ProjectToolError("old_string 找不到；请先 project_read 确认空白、缩进和行尾")
    if occurrences > 1 and not replace_all:
        raise ProjectToolError(f"old_string 出现 {occurrences} 次（非唯一）；扩大上下文或传 replace_all=true")

    updated = text.replace(old_string, new_string) if replace_all else text.replace(old_string, new_string, 1)
    _write_utf8_text_atomic(path, updated)
    rel = _display_path(root, path)
    changed = occurrences if replace_all else 1
    return _ok(f"ok · 替换 {changed} 处 · {rel}", changed_paths=[rel])


def _project_list_dir(root: Path, args: dict[str, Any]) -> ProjectToolResult:
    path_value = str(args.get("path") or ".")
    path = _resolve_project_path(root, path_value)
    if not path.exists():
        raise ProjectToolError(f"目录不存在：{_display_path(root, path)}")
    if not path.is_dir():
        raise ProjectToolError(f"不是目录：{_display_path(root, path)}")

    limit = min(max(1, _optional_int(args, "head_limit", DEFAULT_HEAD_LIMIT)), MAX_HEAD_LIMIT)
    rows: list[str] = []
    try:
        children = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
    except OSError as exc:
        raise ProjectToolError(f"列目录失败：{exc}") from exc

    skipped = 0
    for child in children:
        if _is_skipped(child, root):
            skipped += 1
            continue
        rel = _display_path(root, child)
        kind = "dir " if child.is_dir() else "file"
        size = 0 if child.is_dir() else _safe_size(child)
        rows.append(f"{kind}\t{size:>10}\t{rel}")
        if len(rows) >= limit:
            break
    suffix = ""
    if len(rows) >= limit:
        suffix = f"\n…（已达 head_limit={limit}，可能还有更多）"
    if skipped:
        suffix += f"\n（已隐藏 {skipped} 个受保护/缓存项）"
    return _ok("\n".join(rows) + suffix if rows else "（目录为空或只有受保护/缓存项）")


def _project_glob(
    root: Path,
    args: dict[str, Any],
    *,
    cancel_event: threading.Event | None = None,
) -> ProjectToolResult:
    pattern = _require_string(args, "pattern")
    _validate_glob_pattern(pattern)
    limit = min(max(1, _optional_int(args, "head_limit", DEFAULT_HEAD_LIMIT)), MAX_HEAD_LIMIT)

    matches: list[Path] = []
    for candidate in root.glob(pattern):
        _raise_if_cancelled(cancel_event)
        try:
            candidate.resolve().relative_to(root)
        except ValueError:
            continue
        if not candidate.is_file() or _is_skipped(candidate, root):
            continue
        matches.append(candidate)

    matches.sort(key=lambda item: _safe_mtime(item), reverse=True)
    lines = [
        f"{_display_path(root, path)}\t{_safe_size(path)} bytes"
        for path in matches[:limit]
    ]
    if len(matches) > limit:
        lines.append(f"…（共 {len(matches)} 个匹配，已达 head_limit={limit}）")
    return _ok("\n".join(lines) if lines else "（无匹配文件）")


def _project_grep(
    root: Path,
    args: dict[str, Any],
    *,
    cancel_event: threading.Event | None = None,
) -> ProjectToolResult:
    pattern = _require_string(args, "pattern")
    output_mode = str(args.get("output_mode") or "files_with_matches")
    if output_mode not in {"content", "files_with_matches", "count"}:
        raise ProjectToolError("output_mode 必须是 content / files_with_matches / count")

    try:
        flags = re.IGNORECASE if bool(args.get("case_insensitive", False)) else 0
        regex = re.compile(pattern, flags)
    except re.error as exc:
        raise ProjectToolError(f"正则编译失败：{exc}") from exc

    search_root = _resolve_project_path(root, str(args["path"])) if args.get("path") else root
    if not search_root.exists():
        raise ProjectToolError(f"搜索路径不存在：{_display_path(root, search_root)}")

    glob_pattern = args.get("glob")
    if glob_pattern is not None and not isinstance(glob_pattern, str):
        raise ProjectToolError("glob 必须是字符串")
    limit = min(max(1, _optional_int(args, "head_limit", DEFAULT_HEAD_LIMIT)), MAX_HEAD_LIMIT)

    searched = 0
    content_rows: list[str] = []
    file_rows: list[str] = []
    count_rows: list[str] = []

    for file_path in _iter_search_files(root, search_root, glob_pattern):
        _raise_if_cancelled(cancel_event)
        searched += 1
        try:
            text = _read_utf8_text(file_path, max_bytes=MAX_READ_BYTES)
        except ProjectToolError:
            continue
        rel = _display_path(root, file_path)
        if output_mode == "content":
            for line_no, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    if len(line) > LINE_TRUNCATE:
                        line = line[:LINE_TRUNCATE] + "…[截断]"
                    content_rows.append(f"{rel}:{line_no}: {line}")
                    if len(content_rows) >= limit:
                        return _ok("\n".join(content_rows) + f"\n…（已达 head_limit={limit}，扫描 {searched} 个文件）")
        elif output_mode == "files_with_matches":
            if regex.search(text):
                file_rows.append(rel)
                if len(file_rows) >= limit:
                    return _ok("\n".join(file_rows) + f"\n…（已达 head_limit={limit}，扫描 {searched} 个文件）")
        else:
            count = sum(1 for _ in regex.finditer(text))
            if count:
                count_rows.append(f"{rel}:{count}")
                if len(count_rows) >= limit:
                    return _ok("\n".join(count_rows) + f"\n…（已达 head_limit={limit}，扫描 {searched} 个文件）")

    rows = content_rows if output_mode == "content" else file_rows if output_mode == "files_with_matches" else count_rows
    return _ok("\n".join(rows) if rows else f"（无匹配 · 扫描了 {searched} 个文件）")


def _project_bash(
    root: Path,
    args: dict[str, Any],
    *,
    cancel_event: threading.Event | None = None,
) -> ProjectToolResult:
    command = _require_string(args, "command")
    if not command.strip():
        raise ProjectToolError("command 为空")
    blocked = _check_blacklist(command)
    if blocked:
        raise ProjectToolError(f"命令命中黑名单被拒：{blocked}。如果确实需要，请让用户手动执行后把结果贴回。")
    timeout = min(max(1, _optional_int(args, "timeout", DEFAULT_COMMAND_TIMEOUT)), MAX_COMMAND_TIMEOUT)
    shell_args, use_shell, shell_label = _resolve_shell(command)
    completed = _run_cancellable_process(
        shell_args,
        cwd=root,
        timeout=timeout,
        cancel_event=cancel_event,
        shell=use_shell,
        timeout_message=f"命令超时（{timeout}s 内未结束）",
        start_error_prefix="命令启动失败",
    )
    ok = completed.returncode == 0
    content = _format_process_output(
        exit_code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        label=f"shell: {shell_label}",
    )
    return ProjectToolResult(ok=ok, content=_truncate_result(content))


def _project_python(
    root: Path,
    args: dict[str, Any],
    *,
    cancel_event: threading.Event | None = None,
) -> ProjectToolResult:
    code = _require_string(args, "code")
    if not code.strip():
        raise ProjectToolError("code 为空")
    timeout = min(max(1, _optional_int(args, "timeout", DEFAULT_COMMAND_TIMEOUT)), MAX_COMMAND_TIMEOUT)
    prelude = (
        "import sys, io\n"
        "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')\n"
        "sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')\n"
    )
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=str(root), encoding="utf-8", newline="") as handle:
            handle.write(prelude)
            handle.write(code)
            tmp_path = Path(handle.name)
        completed = _run_cancellable_process(
            [sys.executable, str(tmp_path)],
            cwd=root,
            timeout=timeout,
            cancel_event=cancel_event,
            shell=False,
            timeout_message=f"python 超时（{timeout}s 内未结束）",
            start_error_prefix="python 启动失败",
        )
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
    ok = completed.returncode == 0
    content = _format_process_output(
        exit_code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        label=f"python: {Path(sys.executable).name}",
    )
    return ProjectToolResult(ok=ok, content=_truncate_result(content))


def _project_python_file(
    root: Path,
    args: dict[str, Any],
    *,
    cancel_event: threading.Event | None = None,
) -> ProjectToolResult:
    path = _resolve_project_path(root, _require_string(args, "path"))
    if not path.exists():
        raise ProjectToolError(f"脚本不存在：{_display_path(root, path)}")
    if not path.is_file() or path.suffix.lower() != ".py":
        raise ProjectToolError("project_python_file 只允许运行项目内已有的 .py 文件")

    raw_argv = args.get("args", [])
    if not isinstance(raw_argv, list) or not all(isinstance(item, str) for item in raw_argv):
        raise ProjectToolError("args 必须是字符串数组")
    if len(raw_argv) > 100:
        raise ProjectToolError("args 最多 100 项")
    if any("\x00" in item for item in raw_argv):
        raise ProjectToolError("args 不允许包含 NUL 字符")

    timeout = min(max(1, _optional_int(args, "timeout", DEFAULT_COMMAND_TIMEOUT)), MAX_COMMAND_TIMEOUT)
    completed = _run_cancellable_process(
        [sys.executable, str(path), *raw_argv],
        cwd=root,
        timeout=timeout,
        cancel_event=cancel_event,
        shell=False,
        timeout_message=f"python 脚本超时（{timeout}s 内未结束）",
        start_error_prefix="python 脚本启动失败",
    )
    ok = completed.returncode == 0
    content = _format_process_output(
        exit_code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        label=f"python-file: {_display_path(root, path)}",
    )
    return ProjectToolResult(ok=ok, content=_truncate_result(content))


def _raise_if_cancelled(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise ProjectToolError("用户已停止本轮对话")


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                timeout=3,
                check=False,
            )
            if process.poll() is None:
                process.kill()
        else:
            os.killpg(process.pid, 15)
    except Exception:
        try:
            process.kill()
        except OSError:
            pass


def _run_cancellable_process(
    args: list[str] | str,
    *,
    cwd: Path,
    timeout: int,
    cancel_event: threading.Event | None,
    shell: bool,
    timeout_message: str,
    start_error_prefix: str,
) -> subprocess.CompletedProcess[str]:
    _raise_if_cancelled(cancel_event)
    popen_kwargs: dict[str, Any] = {}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(
            args,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=shell,
            text=True,
            encoding="utf-8",
            errors="replace",
            **popen_kwargs,
        )
    except OSError as exc:
        raise ProjectToolError(f"{start_error_prefix}：{exc}") from exc

    deadline = time.monotonic() + timeout
    while True:
        if cancel_event is not None and cancel_event.is_set():
            _terminate_process_tree(process)
            process.communicate()
            raise ProjectToolError("用户已停止本轮对话")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _terminate_process_tree(process)
            process.communicate()
            raise ProjectToolError(timeout_message)
        try:
            stdout, stderr = process.communicate(timeout=min(0.2, remaining))
            return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            continue


def _resolve_project_path(root: Path, rel_path: str, *, must_exist: bool = True) -> Path:
    if not rel_path:
        raise ProjectToolError("缺少 path")
    raw = Path(rel_path)
    if raw.is_absolute():
        raise ProjectToolError("只允许项目内相对路径")
    target = (root / raw).resolve()
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise ProjectToolError("路径越界") from exc

    parts = [part.lower() for part in relative.parts]
    if any(part in SKIP_DIRS for part in parts):
        raise ProjectToolError("该路径位于受保护/缓存目录中")
    if target.name.lower() in SKIP_FILES:
        raise ProjectToolError("敏感配置文件不允许通过项目工具读写")
    if must_exist and target.exists() and _is_skipped(target, root):
        raise ProjectToolError("该路径位于受保护/缓存目录中")
    return target


def _check_blacklist(command: str) -> str | None:
    for pattern, reason in BLACKLIST_PATTERNS:
        if pattern.search(command):
            return reason
    return None


def _resolve_shell(command: str) -> tuple[list[str] | str, bool, str]:
    if sys.platform == "win32":
        bash_path = shutil.which("bash") or shutil.which("bash.exe")
        if bash_path:
            return [bash_path, "-c", command], False, f"win/{bash_path}"
        return command, True, "win/cmd"
    return ["sh", "-c", command], False, "posix/sh"


def _format_process_output(*, exit_code: int, stdout: str, stderr: str, label: str) -> str:
    parts = [f"exit_code: {exit_code} · {label}"]
    stdout = stdout.rstrip()
    stderr = stderr.rstrip()
    if stdout:
        parts.extend(["\n--- stdout ---", stdout])
    if stderr:
        parts.extend(["\n--- stderr ---", stderr])
    if not stdout and not stderr:
        parts.append("\n（无 stdout / stderr）")
    return "\n".join(parts)


def _truncate_result(text: str) -> str:
    if len(text) <= MAX_RESULT_CHARS:
        return text
    return text[: MAX_RESULT_CHARS - 80] + f"\n…[已截断 · 总长 {len(text)} 字符]"


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.name


def _is_text_path(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name.lower() in TEXT_FILENAMES


def _is_skipped(path: Path, root: Path) -> bool:
    try:
        rel = path.resolve().relative_to(root)
    except ValueError:
        return True
    parts = [part.lower() for part in rel.parts]
    return any(part in SKIP_DIRS for part in parts) or path.name.lower() in SKIP_FILES


def _read_utf8_text(path: Path, *, max_bytes: int = MAX_READ_BYTES) -> str:
    if not _is_text_path(path):
        raise ProjectToolError("该文件不在文本白名单中")
    size = _safe_size(path)
    if size > max_bytes:
        raise ProjectToolError(f"文本文件超过 {max_bytes // 1024 // 1024}MB 上限")
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise ProjectToolError("疑似二进制文件")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProjectToolError("文件不是有效 UTF-8 文本") from exc


def _write_utf8_text_atomic(path: Path, content: str) -> None:
    tmp = path.with_name(f".{path.name}.workmode-public.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        handle.write(content)
    os.replace(tmp, path)


def _iter_search_files(root: Path, search_root: Path, glob_pattern: str | None):
    if search_root.is_file():
        candidates = [search_root]
    else:
        candidates = search_root.rglob("*")
    for candidate in candidates:
        if not candidate.is_file() or _is_skipped(candidate, root):
            continue
        if glob_pattern and not fnmatch(candidate.name, glob_pattern):
            continue
        if not _is_text_path(candidate):
            continue
        yield candidate


def _validate_glob_pattern(pattern: str) -> None:
    raw = Path(pattern)
    if raw.is_absolute():
        raise ProjectToolError("glob pattern 不能是绝对路径")
    if any(part == ".." for part in raw.parts):
        raise ProjectToolError("glob pattern 不能包含 ..")


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _require_string(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str):
        raise ProjectToolError(f"{key} 必须是字符串")
    return value


def _optional_int(args: dict[str, Any], key: str, default: int) -> int:
    value = args.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ProjectToolError(f"{key} 必须是整数") from exc


def _ok(content: str, *, changed_paths: list[str] | None = None) -> ProjectToolResult:
    if len(content) > MAX_RESULT_CHARS:
        content = content[:MAX_RESULT_CHARS] + "\n…[工具结果已截断]"
    return ProjectToolResult(ok=True, content=content, changed_paths=changed_paths or [])
