from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from fastapi.responses import FileResponse

from .storage import ValidationError, get_project


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
MEDIA_TYPES = {
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".webp": "image/webp",
}
SKIP_DIRS = frozenset({".git", ".venv", "__pycache__", "node_modules", "dist", "build", ".pytest_cache", ".idea", ".vscode"})
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_PDF_BYTES = 256 * 1024 * 1024


def project_root(slug: str) -> Path:
    project = get_project(slug)
    root = Path(project.root_path).resolve()
    if not root.exists() or not root.is_dir():
        raise ValidationError("项目根目录已不存在")
    return root


def resolve_project_path(slug: str, rel_path: str) -> Path:
    if not rel_path:
        raise ValidationError("缺少文件路径")
    raw = Path(rel_path)
    if raw.is_absolute():
        raise ValidationError("只允许项目内相对路径")
    root = project_root(slug)
    target = (root / raw).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValidationError("路径越界") from exc
    return target


def display_path(slug: str, path: Path) -> str:
    return path.resolve().relative_to(project_root(slug)).as_posix()


def is_text_path(path: Path) -> bool:
    name = path.name.lower()
    return path.suffix.lower() in TEXT_EXTENSIONS or name in TEXT_FILENAMES


def is_markdown_path(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".markdown"}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def list_tree(slug: str, *, max_entries: int = 1000) -> list[dict[str, Any]]:
    root = project_root(slug)
    entries: list[dict[str, Any]] = []

    def visible_children(folder: Path) -> list[Path]:
        try:
            children = sorted(folder.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        except OSError:
            return []
        return [
            child
            for child in children
            if child.name not in SKIP_DIRS
            and child.name.lower() not in SKIP_FILES
            and not child.is_symlink()
        ]

    pending = list(reversed(visible_children(root)))
    while pending and len(entries) < max_entries:
        child = pending.pop()
        try:
            rel = child.relative_to(root).as_posix()
            is_dir = child.is_dir()
            stat = child.stat()
        except OSError:
            continue
        entries.append(
            {
                "path": rel,
                "name": child.name,
                "kind": "dir" if is_dir else "file",
                "size": 0 if is_dir else stat.st_size,
                "preview": "media" if child.suffix.lower() in MEDIA_TYPES else ("text" if is_text_path(child) else "unsupported"),
            }
        )
        if is_dir:
            pending.extend(reversed(visible_children(child)))
    return entries


def read_text_file(slug: str, rel_path: str) -> dict[str, Any]:
    path = resolve_project_path(slug, rel_path)
    if not path.exists() or not path.is_file():
        raise ValidationError("文件不存在")
    if not is_text_path(path):
        raise ValidationError("该文件不在文本预览白名单中")
    size = path.stat().st_size
    if size > MAX_TEXT_BYTES:
        raise ValidationError("文本文件超过 2MB 预览上限")
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise ValidationError("疑似二进制文件")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("文件不是有效 UTF-8 文本") from exc
    return {
        "path": display_path(slug, path),
        "content": content,
        "version": sha256_text(content),
        "size": size,
        "markdown": is_markdown_path(path),
    }


def write_markdown_file(slug: str, rel_path: str, content: str, version: str | None) -> dict[str, Any]:
    path = resolve_project_path(slug, rel_path)
    from .literature_project import is_literature_project

    if is_literature_project(project_root(slug)):
        relative = display_path(slug, path)
        if not relative.startswith("notes/") or Path(relative).name.casefold() == "readme.md":
            raise ValidationError("文献模式只允许在通用编辑器中修改 notes/*.md；其他文件由文献领域服务维护")
    if not path.exists() or not path.is_file():
        raise ValidationError("只能编辑已存在的 Markdown 文件")
    if not is_markdown_path(path):
        raise ValidationError("当前分发版只允许在右侧编辑 .md/.markdown 文件")
    current = read_text_file(slug, rel_path)
    if version and version != current["version"]:
        raise ValidationError("文件已被外部修改，请重新加载后再保存")
    tmp = path.with_name(f".{path.name}.workmode-public.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
    return read_text_file(slug, rel_path)


def media_response(slug: str, rel_path: str) -> FileResponse:
    path = resolve_project_path(slug, rel_path)
    if not path.exists() or not path.is_file():
        raise ValidationError("文件不存在")
    suffix = path.suffix.lower()
    media_type = MEDIA_TYPES.get(suffix)
    if media_type is None:
        raise ValidationError("该文件不在 PDF/图片预览白名单中")
    size = path.stat().st_size
    if suffix == ".pdf" and size > MAX_PDF_BYTES:
        raise ValidationError("PDF 超过 256MB 预览上限")
    if suffix != ".pdf" and size > MAX_IMAGE_BYTES:
        raise ValidationError("图片超过 64MB 预览上限")
    with path.open("rb") as handle:
        magic = handle.read(16)
    if suffix == ".pdf" and not magic.startswith(b"%PDF"):
        raise ValidationError("PDF 文件头校验失败")
    if suffix == ".png" and not magic.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValidationError("PNG 文件头校验失败")
    if suffix in {".jpg", ".jpeg"} and not magic.startswith(b"\xff\xd8\xff"):
        raise ValidationError("JPEG 文件头校验失败")
    response = FileResponse(path, media_type=media_type, filename=path.name)
    response.headers["Content-Disposition"] = f'inline; filename="{path.name}"'
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response
