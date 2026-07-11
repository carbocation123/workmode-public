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


class SessionCreate(BaseModel):
    title: str = Field(default="新对话", max_length=80)


class SessionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


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


class Message(BaseModel):
    id: str
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    ts: str
    meta: dict[str, Any] = Field(default_factory=dict)
