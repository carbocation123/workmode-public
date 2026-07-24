from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterable

from .endnote_import import (
    _available_target,
    _default_search_roots,
    _first_author_surname,
    _safe_filename,
    _unique_id,
    _year,
)
from .literature_project import (
    LiteratureProjectError,
    _catalog,
    _catalog_lock,
    _groups,
    _normalize_metadata_quality,
    _tags,
    _write_catalog,
    _write_groups,
    _write_tags,
    is_literature_project,
    utc_now,
)


_PDF_HEADER = b"%PDF-"
_REQUIRED_TABLES = {
    "collections",
    "collectionItems",
    "creators",
    "creatorTypes",
    "deletedItems",
    "fields",
    "itemAttachments",
    "itemCreators",
    "itemData",
    "itemDataValues",
    "items",
    "itemTags",
    "itemTypes",
    "libraries",
    "syncedSettings",
    "tags",
}


def _source_paths(source: Path) -> tuple[Path, Path]:
    resolved = Path(source).expanduser().resolve()
    if resolved.is_dir():
        data_directory = resolved
        database = resolved / "zotero.sqlite"
    else:
        database = resolved
        data_directory = resolved.parent
    if database.name.casefold() != "zotero.sqlite":
        raise LiteratureProjectError("请选择 Zotero 数据目录或其中的 zotero.sqlite")
    if not database.is_file():
        raise LiteratureProjectError(f"找不到 Zotero 数据库：{database}")
    return data_directory, database


def _connect_database(database: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(
            f"{database.as_uri()}?mode=ro",
            uri=True,
            timeout=0.5,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        connection.execute("SELECT 1").fetchone()
        return connection
    except sqlite3.Error as exc:
        raise LiteratureProjectError(
            "无法读取 Zotero 数据库。请先关闭 Zotero，再重新导入。"
        ) from exc


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


def _metadata_by_item(connection: sqlite3.Connection) -> dict[int, dict[str, str]]:
    result: dict[int, dict[str, str]] = {}
    for row in connection.execute(
        """
        SELECT data.itemID, fields.fieldName, values_.value
        FROM itemData AS data
        JOIN fields ON fields.fieldID = data.fieldID
        JOIN itemDataValues AS values_ ON values_.valueID = data.valueID
        """
    ):
        result.setdefault(int(row["itemID"]), {})[str(row["fieldName"])] = str(
            row["value"] or ""
        )
    return result


def _authors_by_item(connection: sqlite3.Connection) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    rows = connection.execute(
        """
        SELECT
            itemCreators.itemID,
            creators.firstName,
            creators.lastName,
            creators.fieldMode
        FROM itemCreators
        JOIN creators ON creators.creatorID = itemCreators.creatorID
        JOIN creatorTypes
          ON creatorTypes.creatorTypeID = itemCreators.creatorTypeID
        WHERE creatorTypes.creatorType = 'author'
        ORDER BY itemCreators.itemID, itemCreators.orderIndex
        """
    ).fetchall()
    for row in rows:
        first_name = str(row["firstName"] or "").strip()
        last_name = str(row["lastName"] or "").strip()
        if int(row["fieldMode"] or 0) == 1:
            name = last_name or first_name
        elif last_name and first_name:
            name = f"{last_name}, {first_name}"
        else:
            name = last_name or first_name
        if name:
            result.setdefault(int(row["itemID"]), []).append(name)
    return result


def _collection_paths(connection: sqlite3.Connection) -> tuple[list[dict[str, Any]], dict[int, list[int]]]:
    collections = {
        int(row["collectionID"]): {
            "id": int(row["collectionID"]),
            "name": str(row["collectionName"] or "").strip(),
            "parent_id": (
                int(row["parentCollectionID"])
                if row["parentCollectionID"] is not None
                else None
            ),
        }
        for row in connection.execute(
            "SELECT collectionID, collectionName, parentCollectionID FROM collections"
        )
    }

    def flattened_name(collection_id: int) -> str:
        labels: list[str] = []
        visited: set[int] = set()
        current: int | None = collection_id
        while current is not None and current in collections and current not in visited:
            visited.add(current)
            label = str(collections[current]["name"]).strip()
            if label:
                labels.append(label)
            current = collections[current]["parent_id"]
        return " - ".join(reversed(labels))

    memberships: dict[int, list[int]] = {}
    for row in connection.execute(
        "SELECT collectionID, itemID FROM collectionItems ORDER BY collectionID, orderIndex"
    ):
        memberships.setdefault(int(row["itemID"]), []).append(int(row["collectionID"]))
    source_groups = [
        {
            "zotero_id": collection_id,
            "name": flattened_name(collection_id),
            "member_ids": [
                item_id
                for item_id, collection_ids in memberships.items()
                if collection_id in collection_ids
            ],
        }
        for collection_id in collections
        if flattened_name(collection_id)
    ]
    return source_groups, memberships


def _tag_colors(connection: sqlite3.Connection) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in connection.execute(
        "SELECT value FROM syncedSettings WHERE setting = 'tagColors'"
    ):
        try:
            entries = json.loads(str(row["value"] or "[]"))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "").strip()
            color = str(entry.get("color") or "").strip().upper()
            if name and re.fullmatch(r"#[0-9A-F]{6}", color):
                result[name.casefold()] = color
    return result


def _tags_and_memberships(
    connection: sqlite3.Connection,
) -> tuple[list[dict[str, Any]], dict[int, list[int]]]:
    colors = _tag_colors(connection)
    memberships: dict[int, list[int]] = {}
    membership_types: dict[int, set[int]] = {}
    for row in connection.execute(
        "SELECT itemID, tagID, type FROM itemTags ORDER BY itemID, tagID"
    ):
        item_id = int(row["itemID"])
        tag_id = int(row["tagID"])
        memberships.setdefault(item_id, []).append(tag_id)
        membership_types.setdefault(tag_id, set()).add(int(row["type"] or 0))
    tags = [
        {
            "zotero_id": int(row["tagID"]),
            "name": str(row["name"] or "").strip(),
            "color": colors.get(str(row["name"] or "").strip().casefold(), ""),
            "automatic": membership_types.get(int(row["tagID"]), {0}) == {1},
        }
        for row in connection.execute("SELECT tagID, name FROM tags ORDER BY tagID")
        if str(row["name"] or "").strip()
    ]
    return tags, memberships


def _inside(path: Path, folder: Path) -> bool:
    try:
        path.relative_to(folder)
        return True
    except ValueError:
        return False


def _attachment_source(
    data_directory: Path,
    *,
    item_key: str,
    link_mode: int,
    stored_path: str,
) -> Path | None:
    raw = str(stored_path or "").strip()
    if not raw:
        return None
    if raw.casefold().startswith("storage:"):
        relative = raw.split(":", 1)[1].replace("\\", "/").lstrip("/")
        if not re.fullmatch(r"[A-Z0-9]{8}", item_key, flags=re.IGNORECASE):
            return None
        try:
            storage_root = (data_directory / "storage").resolve()
            storage_folder = (storage_root / item_key).resolve()
            if not _inside(storage_folder, storage_root):
                return None
            candidate = (storage_folder / relative).resolve()
        except (OSError, RuntimeError, ValueError):
            return None
        return candidate if _inside(candidate, storage_folder) else None
    if link_mode == 2:
        try:
            candidate = Path(raw).expanduser()
            if candidate.is_absolute():
                return candidate.resolve()
        except (OSError, RuntimeError, ValueError):
            return None
    return None


def _valid_pdf(path: Path | None) -> bool:
    if path is None or path.suffix.casefold() != ".pdf" or not path.is_file():
        return False
    try:
        with path.open("rb") as handle:
            return handle.read(len(_PDF_HEADER)) == _PDF_HEADER
    except OSError:
        return False


def _attachments_by_parent(
    connection: sqlite3.Connection,
    data_directory: Path,
) -> dict[int, list[dict[str, Any]]]:
    deleted = {
        int(row["itemID"])
        for row in connection.execute("SELECT itemID FROM deletedItems")
    }
    result: dict[int, list[dict[str, Any]]] = {}
    rows = connection.execute(
        """
        SELECT
            attachments.itemID,
            attachments.parentItemID,
            attachments.linkMode,
            attachments.contentType,
            attachments.path,
            items.key
        FROM itemAttachments AS attachments
        JOIN items ON items.itemID = attachments.itemID
        WHERE attachments.parentItemID IS NOT NULL
        ORDER BY attachments.parentItemID, attachments.itemID
        """
    )
    for row in rows:
        item_id = int(row["itemID"])
        parent_id = int(row["parentItemID"])
        if item_id in deleted or parent_id in deleted:
            continue
        source = _attachment_source(
            data_directory,
            item_key=str(row["key"] or ""),
            link_mode=int(row["linkMode"] or 0),
            stored_path=str(row["path"] or ""),
        )
        result.setdefault(parent_id, []).append(
            {
                "item_id": item_id,
                "path": str(row["path"] or ""),
                "source_path": source,
                "content_type": str(row["contentType"] or ""),
                "exists": bool(source and source.is_file()),
                "valid_pdf": _valid_pdf(source),
            }
        )
    return result


def _read_library(data_directory: Path, database: Path) -> dict[str, Any]:
    connection = _connect_database(database)
    try:
        missing = _REQUIRED_TABLES - _table_names(connection)
        if missing:
            raise LiteratureProjectError(
                "Zotero 数据库结构无法识别，缺少：" + ", ".join(sorted(missing))
            )
        metadata = _metadata_by_item(connection)
        authors = _authors_by_item(connection)
        source_groups, collection_memberships = _collection_paths(connection)
        source_tags, tag_memberships = _tags_and_memberships(connection)
        attachments = _attachments_by_parent(connection, data_directory)
        deleted = {
            int(row["itemID"])
            for row in connection.execute("SELECT itemID FROM deletedItems")
        }
        references: list[dict[str, Any]] = []
        for row in connection.execute(
            """
            SELECT items.itemID, items.key, itemTypes.typeName
            FROM items
            JOIN itemTypes ON itemTypes.itemTypeID = items.itemTypeID
            ORDER BY items.itemID
            """
        ):
            item_id = int(row["itemID"])
            if item_id in deleted or str(row["typeName"]) in {
                "annotation",
                "attachment",
                "note",
            }:
                continue
            values = metadata.get(item_id, {})
            item_attachments = attachments.get(item_id, [])
            references.append(
                {
                    "id": item_id,
                    "key": str(row["key"] or ""),
                    "item_type": str(row["typeName"] or ""),
                    "title": values.get("title", ""),
                    "author": "\n".join(authors.get(item_id, [])),
                    "year": values.get("date", ""),
                    "date": values.get("date", ""),
                    "secondary_title": values.get("publicationTitle", ""),
                    "journal_abbreviation": values.get("journalAbbreviation", ""),
                    "electronic_resource_number": values.get("DOI", ""),
                    "attachments": item_attachments,
                    "main_attachment_index": next(
                        (
                            index
                            for index, attachment in enumerate(item_attachments)
                            if attachment["valid_pdf"]
                        ),
                        None,
                    ),
                    "zotero_collection_ids": collection_memberships.get(item_id, []),
                    "zotero_tag_ids": tag_memberships.get(item_id, []),
                }
            )
        return {
            "references": references,
            "groups": source_groups,
            "tags": source_tags,
            "attachment_count": sum(len(items) for items in attachments.values()),
        }
    except sqlite3.Error as exc:
        raise LiteratureProjectError(
            "无法读取 Zotero 数据库。请先关闭 Zotero，再重新导入。"
        ) from exc
    finally:
        connection.close()


def _preview_payload(
    data_directory: Path,
    database: Path,
    library: dict[str, Any],
) -> dict[str, Any]:
    failures = [
        {
            "zotero_item_id": int(reference["id"]),
            "title": str(reference.get("title") or "").strip(),
            "reason": "没有找到有效 PDF；该记录不会导入",
        }
        for reference in library["references"]
        if reference["main_attachment_index"] is None
    ]
    return {
        "source_path": str(data_directory),
        "data_directory": str(data_directory),
        "database_path": str(database),
        "reference_count": len(library["references"]),
        "attachment_count": int(library["attachment_count"]),
        "collection_count": len(library["groups"]),
        "tag_count": len(library["tags"]),
        "importable_count": len(library["references"]) - len(failures),
        "failed_count": len(failures),
        "failures": failures,
    }


def inspect_zotero_library(source: Path) -> dict[str, Any]:
    data_directory, database = _source_paths(source)
    return _preview_payload(
        data_directory,
        database,
        _read_library(data_directory, database),
    )


def _scan_volume_for_zotero_libraries(root: Path) -> list[Path]:
    found: list[Path] = []
    pending = [root]
    skipped_directories = {"storage"}
    while pending:
        folder = pending.pop()
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name.casefold() in skipped_directories:
                                continue
                            pending.append(Path(entry.path))
                        elif (
                            entry.is_file(follow_symlinks=False)
                            and entry.name.casefold() == "zotero.sqlite"
                        ):
                            found.append(Path(entry.path).resolve())
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def find_zotero_libraries(
    search_roots: Iterable[Path] | None = None,
) -> list[dict[str, Any]]:
    roots = list(search_roots) if search_roots is not None else _default_search_roots()
    normalized: dict[str, Path] = {}
    for raw_root in roots:
        root = Path(raw_root).expanduser().resolve()
        if root.exists() and root.is_dir():
            normalized[os.path.normcase(str(root))] = root
    databases: dict[str, Path] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(len(normalized), 4))) as executor:
        for candidates in executor.map(
            _scan_volume_for_zotero_libraries,
            normalized.values(),
        ):
            for database in candidates:
                databases[os.path.normcase(str(database))] = database
    result: list[dict[str, Any]] = []
    for database in databases.values():
        try:
            stat = database.stat()
        except OSError:
            continue
        data_directory = database.parent.resolve()
        result.append(
            {
                "path": str(data_directory),
                "name": data_directory.name or "Zotero",
                "database_path": str(database),
                "has_storage": (data_directory / "storage").is_dir(),
                "size": stat.st_size,
                "modified_at": stat.st_mtime,
            }
        )
    result.sort(
        key=lambda item: (
            0 if item["has_storage"] else 1,
            -float(item["modified_at"]),
            str(item["path"]).casefold(),
        )
    )
    return result


def _ensure_tag_mappings(
    registry: dict[str, Any],
    source_tags: list[dict[str, Any]],
) -> dict[int, str]:
    groups = registry["groups"]
    tags = registry["tags"]
    used_group_ids = {str(group.get("id")) for group in groups}
    used_tag_ids = {str(tag.get("id")) for tag in tags}

    def ensure_group(name: str, color: str) -> str:
        existing = next(
            (
                group
                for group in groups
                if str(group.get("name") or "").casefold() == name.casefold()
                or (
                    color
                    and str(group.get("color") or "").casefold() == color.casefold()
                )
            ),
            None,
        )
        if existing is not None:
            return str(existing["id"])
        group_id = _unique_id(name, used_group_ids)
        groups.append(
            {
                "id": group_id,
                "name": name,
                "color": color,
                "order": len(groups) + 1,
            }
        )
        return group_id

    tag_map: dict[int, str] = {}
    for source_tag in source_tags:
        color = str(source_tag.get("color") or "").upper()
        if color:
            group_id = ensure_group(f"Zotero {color} 标签组", color)
        elif source_tag.get("automatic"):
            group_id = ensure_group("Zotero 自动标签", "#8C96A6")
        else:
            group_id = ensure_group("Zotero 标签", "#3AAFC6")
        name = str(source_tag["name"]).strip()
        existing = next(
            (
                tag
                for tag in tags
                if name.casefold()
                in {
                    str(tag.get("name") or "").casefold(),
                    *(str(alias).casefold() for alias in tag.get("aliases") or []),
                }
            ),
            None,
        )
        if existing is None:
            existing = {
                "id": _unique_id(name, used_tag_ids),
                "name": name,
                "aliases": [],
                "group_id": group_id,
                "status": "confirmed",
            }
            tags.append(existing)
        tag_map[int(source_tag["zotero_id"])] = str(existing["id"])
    return tag_map


def _ensure_group_mappings(
    registry: dict[str, Any],
    source_groups: list[dict[str, Any]],
) -> dict[int, str]:
    groups = registry["groups"]
    used = {str(group.get("id")) for group in groups}
    result: dict[int, str] = {}
    for source_group in source_groups:
        name = str(source_group["name"]).strip()
        existing = next(
            (
                group
                for group in groups
                if str(group.get("name") or "").casefold() == name.casefold()
            ),
            None,
        )
        if existing is None:
            existing = {"id": _unique_id(name, used), "name": name}
            groups.append(existing)
        result[int(source_group["zotero_id"])] = str(existing["id"])
    return result


def _copy_source(source: Path, target: Path) -> str:
    digest = hashlib.sha256()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with source.open("rb") as input_stream, target.open("wb") as output_stream:
            while True:
                chunk = input_stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                output_stream.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return digest.hexdigest()


def _new_record(
    reference: dict[str, Any],
    *,
    paper_id: str,
    digest: str,
    pdf_relative: str,
    si_relative: str,
    group_ids: list[str],
    tag_ids: list[str],
) -> dict[str, Any]:
    authors = ", ".join(
        part.strip()
        for part in str(reference.get("author") or "").splitlines()
        if part.strip()
    )
    main_attachment = reference["attachments"][reference["main_attachment_index"]]
    now = utc_now()
    return _normalize_metadata_quality(
        {
            "id": paper_id,
            "content_sha256": digest,
            "title": str(reference.get("title") or "").strip(),
            "authors": authors,
            "first_author_surname": _first_author_surname(authors),
            "year": _year(reference.get("year")),
            "publication_date": str(reference.get("date") or "").strip(),
            "journal": str(reference.get("secondary_title") or "").strip(),
            "journal_abbreviation": str(
                reference.get("journal_abbreviation") or ""
            ).strip(),
            "doi": str(reference.get("electronic_resource_number") or "").strip(),
            "paper_type": "unknown",
            "status": "pending",
            "archive_location": "papers/unprocessed",
            "original_filename": _safe_filename(
                str(main_attachment["source_path"]),
                f"{paper_id}.pdf",
            ),
            "archive_filename": None,
            "metadata_source": "manual",
            "metadata_trust": "complete",
            "metadata_issue": "",
            "tag_ids": tag_ids,
            "group_ids": group_ids,
            "focus": "",
            "summary": "",
            "paths": {
                "pdf": pdf_relative,
                "si_folder": si_relative,
                "mineru_dir": "",
                "full_md": "",
                "fact_report": "",
            },
            "verification_status": "pending",
            "created_at": now,
            "updated_at": now,
        }
    )


def import_zotero_library(project_root: Path, source: Path) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    if not is_literature_project(root):
        raise LiteratureProjectError("当前项目不是 literature-library 项目")
    data_directory, database = _source_paths(source)
    library = _read_library(data_directory, database)
    preview = _preview_payload(data_directory, database, library)
    failures = list(preview["failures"])
    created_paths: list[Path] = []
    imported_ids: list[str] = []
    changed_files: list[str] = []
    with _catalog_lock(root):
        catalog = _catalog(root)
        tags = _tags(root)
        groups = _groups(root)
        original_catalog = copy.deepcopy(catalog)
        original_tags = copy.deepcopy(tags)
        original_groups = copy.deepcopy(groups)
        tag_map = _ensure_tag_mappings(tags, library["tags"])
        group_map = _ensure_group_mappings(groups, library["groups"])
        try:
            for reference in library["references"]:
                main_index = reference["main_attachment_index"]
                if main_index is None:
                    continue
                paper_id = f"paper-{uuid.uuid4().hex[:24]}"
                main_attachment = reference["attachments"][main_index]
                source_pdf = Path(main_attachment["source_path"])
                pdf_folder = root / "papers/unprocessed/pdf"
                pdf_folder.mkdir(parents=True, exist_ok=True)
                pdf_target = _available_target(
                    pdf_folder,
                    _safe_filename(str(source_pdf), f"{paper_id}.pdf"),
                )
                digest = _copy_source(source_pdf, pdf_target)
                created_paths.append(pdf_target)
                si_folder = root / "papers/unprocessed/SI" / paper_id
                si_folder.mkdir(parents=True, exist_ok=False)
                created_paths.append(si_folder)
                for index, attachment in enumerate(reference["attachments"]):
                    if index == main_index or not attachment["exists"]:
                        continue
                    source_attachment = Path(attachment["source_path"])
                    si_target = _available_target(
                        si_folder,
                        _safe_filename(
                            str(source_attachment),
                            f"attachment-{index + 1}",
                        ),
                    )
                    _copy_source(source_attachment, si_target)
                record = _new_record(
                    reference,
                    paper_id=paper_id,
                    digest=digest,
                    pdf_relative=pdf_target.relative_to(root).as_posix(),
                    si_relative=si_folder.relative_to(root).as_posix(),
                    group_ids=list(
                        dict.fromkeys(
                            group_map[group_id]
                            for group_id in reference["zotero_collection_ids"]
                            if group_id in group_map
                        )
                    ),
                    tag_ids=list(
                        dict.fromkeys(
                            tag_map[tag_id]
                            for tag_id in reference["zotero_tag_ids"]
                            if tag_id in tag_map
                        )
                    ),
                )
                catalog["papers"].append(record)
                imported_ids.append(paper_id)
                changed_files.extend(
                    [record["paths"]["pdf"], record["paths"]["si_folder"]]
                )
            _write_catalog(root, catalog)
            _write_tags(root, tags)
            _write_groups(root, groups)
        except Exception as exc:
            catalog.clear()
            catalog.update(original_catalog)
            tags.clear()
            tags.update(original_tags)
            groups.clear()
            groups.update(original_groups)
            try:
                _write_catalog(root, catalog)
                _write_tags(root, tags)
                _write_groups(root, groups)
            except Exception:
                pass
            for path in reversed(created_paths):
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink(missing_ok=True)
            if isinstance(exc, LiteratureProjectError):
                raise
            raise LiteratureProjectError(f"导入 Zotero 文献库失败：{exc}") from exc
    return {
        "ok": True,
        "source_path": str(data_directory),
        "database_path": str(database),
        "imported_count": len(imported_ids),
        "failed_count": len(failures),
        "group_count": len(library["groups"]),
        "tag_count": len(library["tags"]),
        "paper_ids": imported_ids,
        "failures": failures,
        "changed_files": ["catalog.json", "tags.json", "groups.json", *changed_files],
    }
