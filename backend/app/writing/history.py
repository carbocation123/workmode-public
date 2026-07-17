from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class ArticleHistoryError(Exception):
    pass


class ArticleHistoryNotFound(ArticleHistoryError):
    pass


class ArticleHistoryConflict(ArticleHistoryError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validated_id(value: str, *, label: str) -> str:
    if not _ID_RE.fullmatch(value):
        raise ArticleHistoryNotFound(f"{label}不存在")
    return value


class ArticleHistoryStore:
    """Immutable successful runs with recoverable local deletion."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.history_dir = self.root / "history"
        self.trash_dir = self.root / ".trash"
        self._lock = threading.RLock()

    def initialize(self) -> None:
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.trash_dir.mkdir(parents=True, exist_ok=True)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        staged = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
        try:
            staged.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            staged.replace(path)
        finally:
            staged.unlink(missing_ok=True)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ArticleHistoryError(f"处理历史读取失败：{path.name}") from exc
        if not isinstance(payload, dict):
            raise ArticleHistoryError(f"处理历史格式无效：{path.name}")
        return payload

    def create(
        self,
        *,
        mode: str,
        input_text: str,
        output_text: str,
        model: str,
    ) -> dict[str, Any]:
        if mode not in {"polish", "audit"}:
            raise ArticleHistoryError("不支持的文章处理功能")
        self.initialize()
        record_id = uuid.uuid4().hex
        record = {
            "version": 1,
            "id": record_id,
            "created_at": _utc_now(),
            "mode": mode,
            "input_text": input_text,
            "output_text": output_text,
            "options": {"unicode_superscript_subscript": True},
            "model": model,
            "input_chars": len(input_text),
            "output_chars": len(output_text),
        }
        with self._lock:
            self._write_json(self.history_dir / f"{record_id}.json", record)
        return record

    def list(self) -> list[dict[str, Any]]:
        self.initialize()
        with self._lock:
            items = [self._read_json(path) for path in self.history_dir.glob("*.json")]
        return sorted(items, key=lambda item: str(item.get("created_at") or ""), reverse=True)

    def get(self, record_id: str) -> dict[str, Any]:
        safe_id = _validated_id(record_id, label="处理历史")
        self.initialize()
        path = self.history_dir / f"{safe_id}.json"
        with self._lock:
            if not path.is_file():
                raise ArticleHistoryNotFound("处理历史不存在")
            return self._read_json(path)

    def delete(self, record_id: str) -> dict[str, Any]:
        record = self.get(record_id)
        trash_id = uuid.uuid4().hex
        deleted = {
            "version": 1,
            "trash_id": trash_id,
            "deleted_at": _utc_now(),
            "record": record,
        }
        source = self.history_dir / f"{record_id}.json"
        target = self.trash_dir / f"{trash_id}.json"
        with self._lock:
            if not source.is_file():
                raise ArticleHistoryNotFound("处理历史不存在")
            self._write_json(target, deleted)
            source.unlink()
        return deleted

    def list_deleted(self) -> list[dict[str, Any]]:
        self.initialize()
        with self._lock:
            items = [self._read_json(path) for path in self.trash_dir.glob("*.json")]
        return sorted(items, key=lambda item: str(item.get("deleted_at") or ""), reverse=True)

    def restore(self, trash_id: str) -> dict[str, Any]:
        safe_id = _validated_id(trash_id, label="已删除记录")
        self.initialize()
        source = self.trash_dir / f"{safe_id}.json"
        with self._lock:
            if not source.is_file():
                raise ArticleHistoryNotFound("已删除记录不存在")
            deleted = self._read_json(source)
            record = deleted.get("record")
            if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                raise ArticleHistoryError("已删除记录格式无效")
            record_id = _validated_id(record["id"], label="处理历史")
            target = self.history_dir / f"{record_id}.json"
            if target.exists():
                raise ArticleHistoryConflict("同一条处理历史已经存在，未覆盖现有记录")
            self._write_json(target, record)
            source.unlink()
            return record
