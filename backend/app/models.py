from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    root_path: str = Field(min_length=1)
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None


class ActiveProjectUpdate(BaseModel):
    slug: str


class TutorialProjectInstall(BaseModel):
    parent_path: str = Field(min_length=1)


class LiteratureProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    # Kept optional for compatibility with old clients that explicitly chose a
    # folder. New clients omit it and use the app-managed project root.
    root_path: str | None = Field(default=None, min_length=1)


class LiteratureRecordUpdate(BaseModel):
    tags: list[dict[str, Any]] | None = None
    focus: str | None = Field(default=None, max_length=20000)
    summary: str | None = Field(default=None, max_length=50000)
    title: str | None = Field(default=None, max_length=2000)
    authors: str | None = Field(default=None, max_length=10000)
    first_author_surname: str | None = Field(default=None, max_length=500)
    year: int | None = Field(default=None, ge=1000, le=3000)
    publication_date: str | None = Field(default=None, max_length=500)
    journal: str | None = Field(default=None, max_length=2000)
    journal_abbreviation: str | None = Field(default=None, max_length=200)
    doi: str | None = Field(default=None, max_length=1000)
    paper_type: Literal["research", "review", "unknown"] | None = None
    metadata_source: Literal["cite_this", "layout_json", "manual", "pending"] | None = None


class EndNoteLibraryPath(BaseModel):
    path: str = Field(min_length=1, max_length=32000)


class LiteratureCrossRelationUpdate(BaseModel):
    markdown: str = Field(max_length=2_000_000)


class LiteratureNoteUpdate(BaseModel):
    markdown: str = Field(max_length=2_000_000)


class LiteratureImportNotice(BaseModel):
    paper_ids: list[str] = Field(min_length=1, max_length=100)


class SessionCreate(BaseModel):
    title: str = Field(default="新对话", max_length=80)


class SessionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class ActiveContextItem(BaseModel):
    kind: Literal["paper", "note"]
    id: str = Field(min_length=1, max_length=500)


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    active_context: list[ActiveContextItem] = Field(default_factory=list, max_length=100)


class CompactRequest(BaseModel):
    keep_recent: int = Field(default=6, ge=2, le=30)
    extra_instruction: str = Field(default="", max_length=4000)


class MemoryUpdate(BaseModel):
    content: str = Field(default="", max_length=2_000_000)


class FileWriteRequest(BaseModel):
    content: str = Field(max_length=2_000_000)
    version: str | None = None


class ModelSettingsUpdate(BaseModel):
    model_base_url: str | None = Field(default=None, max_length=500)
    model_name: str | None = Field(default=None, max_length=120)
    model_api_key: str | None = Field(default=None, max_length=10000)
    clear_api_key: bool = False
    context_budget_tokens: int | None = Field(default=None, ge=1000, le=5_000_000)
    request_timeout_seconds: float | None = Field(default=None, ge=5, le=600)


class ModelConnectionTest(BaseModel):
    model_base_url: str | None = Field(default=None, max_length=500)
    model_name: str | None = Field(default=None, max_length=120)
    model_api_key: str | None = Field(default=None, max_length=10000)


class MineruSettingsUpdate(BaseModel):
    mineru_api_key: str | None = Field(default=None, max_length=10000)
    clear_api_key: bool = False
    mineru_model_version: Literal["pipeline", "vlm"] | None = None
    mineru_language: Literal["ch", "en", "ch_server", "japan"] | None = None
    mineru_timeout_seconds: int | None = Field(default=None, ge=60, le=1800)


class DashscopeSettingsUpdate(BaseModel):
    dashscope_api_key: str | None = Field(default=None, max_length=10000)
    clear_api_key: bool = False


class Message(BaseModel):
    id: str
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    ts: str
    meta: dict[str, Any] = Field(default_factory=dict)
