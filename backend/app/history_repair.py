from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HistoryRepairReport:
    scanned_files: int
    repaired_files: int
    inserted_results: int
    failed_files: int
    backup_dir: Path | None


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _event_meta(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("meta")
    return meta if isinstance(meta, dict) else {}


def _cancelled_result(start: dict[str, Any], call_id: str) -> dict[str, Any]:
    meta = _event_meta(start)
    return {
        "id": uuid.uuid4().hex,
        "role": "tool",
        "content": "旧工具调用没有保存返回结果，已在历史修复中标记为取消。",
        "ts": start.get("ts") or datetime.now(timezone.utc).isoformat(),
        "meta": {
            "event": "tool_result",
            "tool_call_id": call_id,
            "tool_name": str(meta.get("tool_name") or "unknown"),
            "status": "cancelled",
            "ok": False,
            "changed_paths": [],
            "repaired_history": True,
        },
    }


def _write_rows_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.repair.tmp")
    try:
        temp.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _update_message_count(meta_path: Path, message_count: int) -> None:
    if not meta_path.is_file():
        return
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    payload["message_count"] = message_count
    temp = meta_path.with_name(f".{meta_path.name}.{uuid.uuid4().hex}.repair.tmp")
    try:
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp.replace(meta_path)
    finally:
        temp.unlink(missing_ok=True)


def repair_stale_tool_runs(sessions_root: Path, backup_root: Path) -> HistoryRepairReport:
    """Close historical tool starts that never received a result.

    Original JSONL and metadata files are copied to one timestamped backup batch
    before an in-place atomic rewrite. Completed calls and message text are left
    unchanged. Re-running the repair is idempotent.
    """

    sessions_root = sessions_root.resolve()
    backup_root = backup_root.resolve()
    history_files = sorted(sessions_root.rglob("*.jsonl")) if sessions_root.exists() else []
    repaired_files = 0
    inserted_results = 0
    failed_files = 0
    batch_dir: Path | None = None

    for history_path in history_files:
        try:
            rows = _read_rows(history_path)
            completed_ids = {
                str(_event_meta(row).get("tool_call_id"))
                for row in rows
                if _event_meta(row).get("event") == "tool_result"
                and _event_meta(row).get("tool_call_id")
            }
            inserted_ids: set[str] = set()
            next_rows: list[dict[str, Any]] = []
            for row in rows:
                next_rows.append(row)
                meta = _event_meta(row)
                call_id = str(meta.get("tool_call_id") or "")
                if (
                    meta.get("event") == "tool_call_start"
                    and call_id
                    and call_id not in completed_ids
                    and call_id not in inserted_ids
                ):
                    next_rows.append(_cancelled_result(row, call_id))
                    inserted_ids.add(call_id)

            if not inserted_ids:
                continue
            if batch_dir is None:
                batch_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                batch_dir = backup_root / f"{batch_name}-{uuid.uuid4().hex[:8]}"
            relative = history_path.resolve().relative_to(sessions_root)
            backup_history = batch_dir / relative
            backup_history.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(history_path, backup_history)

            meta_path = history_path.with_suffix(".meta.json")
            if meta_path.is_file():
                backup_meta = backup_history.with_suffix(".meta.json")
                shutil.copy2(meta_path, backup_meta)

            _write_rows_atomic(history_path, next_rows)
            _update_message_count(meta_path, len(next_rows))
            repaired_files += 1
            inserted_results += len(inserted_ids)
        except Exception:
            failed_files += 1

    return HistoryRepairReport(
        scanned_files=len(history_files),
        repaired_files=repaired_files,
        inserted_results=inserted_results,
        failed_files=failed_files,
        backup_dir=batch_dir,
    )
