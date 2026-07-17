from __future__ import annotations

from pathlib import Path
from typing import Literal

from ..context_imports import expand_project_imports_detailed


WritingSkillMode = Literal["polish", "audit"]
SKILLS_ROOT = Path(__file__).resolve().parent / "skills"
SKILL_MANIFESTS: dict[WritingSkillMode, str] = {
    "polish": "polish.md",
    "audit": "audit.md",
}


class WritingSkillError(Exception):
    pass


def load_writing_skill(mode: WritingSkillMode) -> str:
    """Expand the selected trusted manifest using the shared ``@file`` syntax."""
    manifest_name = SKILL_MANIFESTS.get(mode)
    if not manifest_name:
        raise WritingSkillError("不支持的文章处理 Skill")
    manifest = SKILLS_ROOT / manifest_name
    try:
        source = manifest.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise WritingSkillError(f"文章处理 Skill 读取失败：{manifest_name}") from exc
    expanded = expand_project_imports_detailed(source, project_root=SKILLS_ROOT, max_depth=3)
    if expanded.errors:
        raise WritingSkillError("文章处理 Skill 导入失败：" + "；".join(expanded.errors))
    if not expanded.text.strip():
        raise WritingSkillError(f"文章处理 Skill 为空：{manifest_name}")
    return expanded.text.strip()
