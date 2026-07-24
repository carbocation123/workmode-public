from __future__ import annotations

import copy
import ctypes
import hashlib
import os
import re
import shutil
import sqlite3
import struct
import tempfile
import unicodedata
import urllib.parse
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, BinaryIO, Iterable
from xml.etree import ElementTree

from .literature_project import (
    LiteratureProjectError,
    _catalog,
    _catalog_lock,
    _groups,
    _normalize_metadata_quality,
    _slug,
    _tags,
    _write_catalog,
    _write_groups,
    _write_tags,
    is_literature_project,
    utc_now,
)


_ENDNOTE_DATABASE_ENTRY = "sdb/sdb.eni"
_PDF_HEADER = b"%PDF-"


def _normalize_attachment_path(value: Any) -> str:
    raw = urllib.parse.unquote(str(value or "")).replace("\\", "/").strip()
    raw = re.sub(r"^internal-pdf:/+", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"^file:/+", "", raw, flags=re.IGNORECASE)
    raw = raw.lstrip("/")
    if raw.casefold().startswith("pdf/"):
        raw = raw[4:]
    parts = [part for part in raw.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        return ""
    return "/".join(parts)


def _decoded_zip_name(info: zipfile.ZipInfo) -> str:
    name = info.filename.replace("\\", "/")
    if not (info.flag_bits & 0x800):
        try:
            return name.encode("cp437").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return name


class _EndNoteBundle(AbstractContextManager["_EndNoteBundle"]):
    def __init__(self, source: Path):
        self.source = source.expanduser().resolve()
        self.database_path: Path | None = None
        self._data_pdf_root: Path | None = None
        self._archive: zipfile.ZipFile | None = None
        self._archive_entries: dict[str, zipfile.ZipInfo] = {}
        self._temporary: tempfile.TemporaryDirectory[str] | None = None

    def __enter__(self) -> "_EndNoteBundle":
        if not self.source.exists() or not self.source.is_file():
            raise LiteratureProjectError(f"EndNote 文件不存在：{self.source}")
        suffix = self.source.suffix.casefold()
        if suffix == ".enl":
            self.database_path = self.source
            self._data_pdf_root = self.source.with_suffix(".Data") / "PDF"
            return self
        if suffix != ".enlx":
            raise LiteratureProjectError("请选择 .enl 或 .enlx EndNote 文献库")

        try:
            self._archive = zipfile.ZipFile(self.source)
        except (OSError, zipfile.BadZipFile) as exc:
            raise LiteratureProjectError(f"无法打开 EndNote 压缩文献库：{exc}") from exc
        for info in self._archive.infolist():
            normalized = _decoded_zip_name(info).lstrip("/")
            self._archive_entries[normalized.casefold()] = info
        database_info = self._archive_entries.get(_ENDNOTE_DATABASE_ENTRY)
        if database_info is None:
            self.close()
            raise LiteratureProjectError("ENLX 中缺少 sdb/sdb.eni 数据库")
        self._temporary = tempfile.TemporaryDirectory(prefix="workmode-endnote-")
        self.database_path = Path(self._temporary.name) / "sdb.eni"
        try:
            with self._archive.open(database_info) as source, self.database_path.open("wb") as target:
                shutil.copyfileobj(source, target)
        except (OSError, KeyError) as exc:
            self.close()
            raise LiteratureProjectError(f"无法读取 ENLX 数据库：{exc}") from exc
        return self

    def close(self) -> None:
        if self._archive is not None:
            self._archive.close()
            self._archive = None
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def open_attachment(self, relative_path: str) -> BinaryIO:
        normalized = _normalize_attachment_path(relative_path)
        if not normalized:
            raise FileNotFoundError(relative_path)
        if self._archive is not None:
            info = self._archive_entries.get(f"pdf/{normalized}".casefold())
            if info is None:
                raise FileNotFoundError(relative_path)
            return self._archive.open(info)
        if self._data_pdf_root is None:
            raise FileNotFoundError(relative_path)
        target = (self._data_pdf_root / Path(normalized)).resolve()
        try:
            target.relative_to(self._data_pdf_root.resolve())
        except ValueError as exc:
            raise FileNotFoundError(relative_path) from exc
        return target.open("rb")

    def attachment_exists(self, relative_path: str) -> bool:
        try:
            with self.open_attachment(relative_path):
                return True
        except (FileNotFoundError, KeyError, OSError):
            return False

    def attachment_is_valid_pdf(self, relative_path: str) -> bool:
        if Path(_normalize_attachment_path(relative_path)).suffix.casefold() != ".pdf":
            return False
        try:
            with self.open_attachment(relative_path) as handle:
                return handle.read(len(_PDF_HEADER)) == _PDF_HEADER
        except (FileNotFoundError, KeyError, OSError):
            return False


def _connect_database(path: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection
    except sqlite3.Error as exc:
        raise LiteratureProjectError(f"无法读取 EndNote 数据库：{exc}") from exc


def _decode_xml_spec(raw: Any) -> tuple[str, str, list[str]]:
    if isinstance(raw, memoryview):
        raw = raw.tobytes()
    if isinstance(raw, bytes):
        content = raw
    else:
        content = str(raw or "").encode("utf-8", errors="replace")
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return "", "", []
    identifier = str(root.findtext("./ids/id") or "").strip()
    name = str(root.findtext("./ids/name") or root.findtext(".//name") or "").strip()
    rules = [str(node.text or "").strip() for node in root.findall(".//rule")]
    return identifier, name, rules


def _decode_group_sets(rows: Iterable[dict[str, Any]]) -> dict[str, str]:
    group_set_by_member: dict[str, str] = {}
    for row in rows:
        raw = row.get("value")
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        if not isinstance(raw, bytes):
            raw = str(raw or "").encode("utf-8", errors="replace")
        try:
            root = ElementTree.fromstring(raw)
        except ElementTree.ParseError:
            continue
        name = str(root.findtext("./ids/name") or "").strip()
        if not name:
            continue
        for member in root.findall("./members/member"):
            member_id = str(member.text or "").strip().casefold()
            if member_id:
                group_set_by_member[member_id] = name
    return group_set_by_member


def _rule_value(rules: Iterable[str], key: str) -> str:
    prefix = f"{key};"
    for rule in rules:
        if rule.upper().startswith(prefix):
            return rule[len(prefix) :].strip()
    return ""


def _decode_group_members(raw: Any) -> list[int]:
    if isinstance(raw, memoryview):
        raw = raw.tobytes()
    if not isinstance(raw, bytes) or len(raw) < 8:
        return []
    count = struct.unpack_from("<I", raw, 4)[0]
    if count > 10_000_000 or len(raw) < 8 + (count * 4):
        return []
    return list(struct.unpack_from(f"<{count}I", raw, 8)) if count else []


def _read_library(bundle: _EndNoteBundle) -> dict[str, Any]:
    assert bundle.database_path is not None
    connection = _connect_database(bundle.database_path)
    try:
        references = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, trash_state, author, year, title, secondary_title,
                       electronic_resource_number, date
                FROM refs
                ORDER BY id
                """
            )
            if int(row["trash_state"] or 0) == 0
        ]
        attachment_rows = [
            dict(row)
            for row in connection.execute(
                "SELECT refs_id, file_path, file_pos FROM file_res ORDER BY refs_id, file_pos, rowid"
            )
        ]
        group_rows = [dict(row) for row in connection.execute("SELECT group_id, spec, members FROM groups")]
        tag_rows = [dict(row) for row in connection.execute("SELECT group_id, spec FROM tag_groups")]
        tag_member_rows = [
            dict(row) for row in connection.execute("SELECT id, c0 FROM tag_members_content")
        ]
        has_misc = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'misc'"
        ).fetchone()
        group_set_rows = (
            [dict(row) for row in connection.execute("SELECT value FROM misc WHERE code = 17")]
            if has_misc
            else []
        )
    except sqlite3.Error as exc:
        raise LiteratureProjectError(f"EndNote 数据库结构无法识别：{exc}") from exc
    finally:
        connection.close()

    attachments_by_reference: dict[int, list[dict[str, Any]]] = {}
    for row in attachment_rows:
        reference_id = int(row["refs_id"])
        normalized = _normalize_attachment_path(row["file_path"])
        attachments_by_reference.setdefault(reference_id, []).append(
            {
                "path": normalized,
                "file_pos": int(row["file_pos"] or 0),
                "exists": bool(normalized and bundle.attachment_exists(normalized)),
                "valid_pdf": bool(normalized and bundle.attachment_is_valid_pdf(normalized)),
            }
        )

    group_set_by_member = _decode_group_sets(group_set_rows)
    manual_groups: list[dict[str, Any]] = []
    for row in group_rows:
        identifier, name, rules = _decode_xml_spec(row["spec"])
        if _rule_value(rules, "TYPE") != "3" or not name:
            continue
        group_set_name = group_set_by_member.get(identifier.casefold())
        flattened_name = f"{group_set_name} - {name}" if group_set_name else name
        manual_groups.append(
            {
                "endnote_id": int(row["group_id"]),
                "name": flattened_name,
                "member_ids": _decode_group_members(row["members"]),
            }
        )

    tags: list[dict[str, Any]] = []
    for row in tag_rows:
        _, name, rules = _decode_xml_spec(row["spec"])
        if _rule_value(rules, "TYPE") != "10" or not name:
            continue
        raw_color = re.sub(r"[^0-9A-Fa-f]", "", _rule_value(rules, "COLOR"))
        color = f"#{raw_color[:6].upper()}" if len(raw_color) >= 6 else "#94A3B8"
        tags.append({"endnote_id": int(row["group_id"]), "name": name, "color": color})

    tag_memberships: dict[int, list[int]] = {}
    for row in tag_member_rows:
        raw_tokens = re.findall(r"[0-9A-Fa-f]+", str(row["c0"] or ""))
        tag_ids: list[int] = []
        for token in raw_tokens:
            try:
                tag_ids.append(int(token, 16))
            except ValueError:
                continue
        tag_memberships[int(row["id"])] = tag_ids

    for reference in references:
        reference_id = int(reference["id"])
        attachments = attachments_by_reference.get(reference_id, [])
        reference["attachments"] = attachments
        reference["main_attachment_index"] = next(
            (index for index, item in enumerate(attachments) if item["valid_pdf"]),
            None,
        )
        reference["endnote_tag_ids"] = tag_memberships.get(reference_id, [])
    return {
        "references": references,
        "attachments": attachment_rows,
        "groups": manual_groups,
        "tags": tags,
    }


def _preview_payload(source: Path, library: dict[str, Any]) -> dict[str, Any]:
    references = library["references"]
    failures = [
        {
            "endnote_record_id": int(reference["id"]),
            "title": str(reference.get("title") or ""),
            "reason": "未找到有效 PDF；该条文献不会导入",
        }
        for reference in references
        if reference["main_attachment_index"] is None
    ]
    return {
        "source_path": str(source.expanduser().resolve()),
        "source_type": source.suffix.casefold().lstrip("."),
        "reference_count": len(references),
        "attachment_count": len(library["attachments"]),
        "manual_group_count": len(library["groups"]),
        "tag_count": len(library["tags"]),
        "importable_count": len(references) - len(failures),
        "failed_count": len(failures),
        "failures": failures,
    }


def inspect_endnote_library(source: Path) -> dict[str, Any]:
    source = Path(source).expanduser().resolve()
    with _EndNoteBundle(source) as bundle:
        return _preview_payload(source, _read_library(bundle))


def _local_volume_roots() -> list[Path]:
    if os.name != "nt":
        return [Path("/")]
    try:
        bitmask = int(ctypes.windll.kernel32.GetLogicalDrives())
        get_drive_type = ctypes.windll.kernel32.GetDriveTypeW
    except (AttributeError, OSError, TypeError, ValueError):
        bitmask = 0
        get_drive_type = None
    roots: list[Path] = []
    for index in range(26):
        if bitmask and not (bitmask & (1 << index)):
            continue
        root = Path(f"{chr(ord('A') + index)}:/")
        if not root.exists():
            continue
        if get_drive_type is not None:
            try:
                drive_type = int(get_drive_type(str(root)))
            except (OSError, TypeError, ValueError):
                continue
            if drive_type not in {2, 3}:  # removable or fixed local volume
                continue
        roots.append(root)
    return roots


def _default_search_roots() -> list[Path]:
    return _local_volume_roots()


def _scan_volume_for_endnote_libraries(root: Path) -> list[Path]:
    found: list[Path] = []
    pending = [root]
    while pending:
        folder = pending.pop()
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name.casefold().endswith(".data"):
                                continue
                            pending.append(Path(entry.path))
                            continue
                        if (
                            entry.is_file(follow_symlinks=False)
                            and Path(entry.name).suffix.casefold() in {".enl", ".enlx"}
                        ):
                            found.append(Path(entry.path).resolve())
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def _matching_data_folder(library: Path) -> Path | None:
    expected_name = f"{library.stem}.Data".casefold()
    try:
        for child in library.parent.iterdir():
            if child.is_dir() and child.name.casefold() == expected_name:
                return child.resolve()
    except OSError:
        pass
    return None


def find_endnote_libraries(search_roots: Iterable[Path] | None = None) -> list[dict[str, Any]]:
    roots = list(search_roots) if search_roots is not None else _default_search_roots()
    normalized_roots: dict[str, Path] = {}
    for raw_root in roots:
        root = Path(raw_root).expanduser().resolve()
        if root.exists() and root.is_dir():
            normalized_roots[os.path.normcase(str(root))] = root

    found: dict[str, Path] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(len(normalized_roots), 4))) as executor:
        for candidates in executor.map(
            _scan_volume_for_endnote_libraries,
            normalized_roots.values(),
        ):
            for candidate in candidates:
                found[os.path.normcase(str(candidate))] = candidate

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for path in found.values():
        try:
            stats = path.stat()
        except OSError:
            continue
        variant = {
                "path": str(path.resolve()),
                "name": path.name,
                "type": path.suffix.casefold().lstrip("."),
                "size": stats.st_size,
                "modified_at": stats.st_mtime,
        }
        key = (os.path.normcase(str(path.parent.resolve())), path.stem.casefold())
        grouped.setdefault(key, []).append(variant)

    result: list[dict[str, Any]] = []
    for variants in grouped.values():
        variants.sort(
            key=lambda item: (
                0 if item["type"] == "enl" else 1,
                -float(item["modified_at"]),
                str(item["path"]).casefold(),
            )
        )
        enl_variants = [item for item in variants if item["type"] == "enl"]
        enlx_variants = [item for item in variants if item["type"] == "enlx"]
        complete_enl = next(
            (
                item
                for item in enl_variants
                if _matching_data_folder(Path(str(item["path"]))) is not None
            ),
            None,
        )
        if complete_enl is not None:
            recommended = complete_enl
            reason = "complete_working_library"
            has_data_folder = True
            rank = 0
        elif enlx_variants:
            recommended = enlx_variants[0]
            reason = "compressed_library"
            has_data_folder = False
            rank = 1
        else:
            recommended = enl_variants[0]
            reason = "library_without_data_folder"
            has_data_folder = False
            rank = 2
        result.append(
            {
                **recommended,
                "has_data_folder": has_data_folder,
                "recommended_reason": reason,
                "variants": variants,
                "_rank": rank,
            }
        )

    result.sort(
        key=lambda item: (
            int(item["_rank"]),
            -float(item["modified_at"]),
            str(item["path"]).casefold(),
        )
    )
    for item in result:
        item.pop("_rank", None)
    return result


def _safe_filename(relative_path: str, fallback: str) -> str:
    name = Path(_normalize_attachment_path(relative_path)).name.strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name or fallback


def _available_target(folder: Path, filename: str) -> Path:
    candidate = folder / filename
    suffix = candidate.suffix
    stem = candidate.stem
    index = 2
    while candidate.exists():
        candidate = folder / f"{stem}_{index}{suffix}"
        index += 1
    return candidate


def _copy_attachment(bundle: _EndNoteBundle, relative_path: str, target: Path) -> str:
    digest = hashlib.sha256()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with bundle.open_attachment(relative_path) as source, target.open("wb") as destination:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                destination.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return digest.hexdigest()


def _normalized_authors(value: Any) -> str:
    return ", ".join(part.strip() for part in re.split(r"[\r\n]+", str(value or "")) if part.strip())


def _year(value: Any) -> int | None:
    match = re.search(r"\b(1[5-9]\d{2}|20\d{2}|21\d{2})\b", str(value or ""))
    return int(match.group(1)) if match else None


def _first_author_surname(authors: str) -> str:
    first = authors.split(", ", 1)[0].strip()
    if "," in first:
        first = first.split(",", 1)[0]
    return first


def _unique_id(base: str, used: set[str]) -> str:
    candidate = _slug(base) or "item"
    stem = candidate
    suffix = 2
    while candidate in used:
        candidate = f"{stem}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _ensure_tag_mappings(
    registry: dict[str, Any],
    source_tags: list[dict[str, Any]],
) -> tuple[dict[int, str], int]:
    groups = registry["groups"]
    tags = registry["tags"]
    used_group_ids = {str(group.get("id")) for group in groups}
    used_tag_ids = {str(tag.get("id")) for tag in tags}
    group_by_color = {
        str(group.get("color") or "").upper(): str(group.get("id"))
        for group in groups
        if group.get("id") and group.get("color")
    }
    tag_map: dict[int, str] = {}
    created_count = 0
    for source_tag in source_tags:
        color = str(source_tag["color"]).upper()
        group_id = group_by_color.get(color)
        if group_id is None:
            group_id = _unique_id(f"endnote-{color.lstrip('#').lower()}", used_group_ids)
            groups.append(
                {
                    "id": group_id,
                    "name": f"EndNote {color} 标签组",
                    "color": color,
                    "order": len(groups) + 1,
                }
            )
            group_by_color[color] = group_id
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
            tag_id = _unique_id(name, used_tag_ids)
            existing = {
                "id": tag_id,
                "name": name,
                "aliases": [],
                "group_id": group_id,
                "status": "confirmed",
            }
            tags.append(existing)
            created_count += 1
        tag_map[int(source_tag["endnote_id"])] = str(existing["id"])
    return tag_map, created_count


def _ensure_group_mappings(
    registry: dict[str, Any],
    source_groups: list[dict[str, Any]],
) -> dict[int, str]:
    groups = registry["groups"]
    used = {str(group.get("id")) for group in groups}
    group_map: dict[int, str] = {}
    for source_group in source_groups:
        name = str(source_group["name"]).strip()
        existing = next(
            (group for group in groups if str(group.get("name") or "").casefold() == name.casefold()),
            None,
        )
        if existing is None:
            existing = {"id": _unique_id(name, used), "name": name}
            groups.append(existing)
        group_map[int(source_group["endnote_id"])] = str(existing["id"])
    return group_map


def _reference_group_ids(
    reference_id: int,
    source_groups: list[dict[str, Any]],
    group_map: dict[int, str],
) -> list[str]:
    return [
        group_map[int(group["endnote_id"])]
        for group in source_groups
        if reference_id in group["member_ids"]
    ]


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
    authors = _normalized_authors(reference.get("author"))
    now = utc_now()
    main_attachment = reference["attachments"][reference["main_attachment_index"]]
    return _normalize_metadata_quality({
        "id": paper_id,
        "content_sha256": digest,
        "title": str(reference.get("title") or "").strip(),
        "authors": authors,
        "first_author_surname": _first_author_surname(authors),
        "year": _year(reference.get("year")),
        "publication_date": str(reference.get("date") or "").strip(),
        "journal": str(reference.get("secondary_title") or "").strip(),
        "journal_abbreviation": "",
        "doi": str(reference.get("electronic_resource_number") or "").strip(),
        "paper_type": "unknown",
        "status": "pending",
        "archive_location": "papers/unprocessed",
        "original_filename": _safe_filename(main_attachment["path"], f"{paper_id}.pdf"),
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
    })


def import_endnote_library(project_root: Path, source: Path) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    source = Path(source).expanduser().resolve()
    if not is_literature_project(root):
        raise LiteratureProjectError("当前项目不是 literature-library 项目")

    with _EndNoteBundle(source) as bundle:
        library = _read_library(bundle)
        preview = _preview_payload(source, library)
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
            tag_map, _ = _ensure_tag_mappings(tags, library["tags"])
            group_map = _ensure_group_mappings(groups, library["groups"])
            try:
                for reference in library["references"]:
                    main_index = reference["main_attachment_index"]
                    if main_index is None:
                        continue
                    paper_id = f"paper-{uuid.uuid4().hex[:24]}"
                    main_attachment = reference["attachments"][main_index]
                    pdf_folder = root / "papers/unprocessed/pdf"
                    pdf_folder.mkdir(parents=True, exist_ok=True)
                    pdf_target = _available_target(
                        pdf_folder,
                        _safe_filename(main_attachment["path"], f"{paper_id}.pdf"),
                    )
                    digest = _copy_attachment(bundle, main_attachment["path"], pdf_target)
                    created_paths.append(pdf_target)
                    si_folder = root / "papers/unprocessed/SI" / paper_id
                    si_folder.mkdir(parents=True, exist_ok=False)
                    created_paths.append(si_folder)
                    for index, attachment in enumerate(reference["attachments"]):
                        if index == main_index or not attachment["exists"]:
                            continue
                        si_target = _available_target(
                            si_folder,
                            _safe_filename(attachment["path"], f"attachment-{index + 1}"),
                        )
                        _copy_attachment(bundle, attachment["path"], si_target)
                    reference_id = int(reference["id"])
                    record = _new_record(
                        reference,
                        paper_id=paper_id,
                        digest=digest,
                        pdf_relative=pdf_target.relative_to(root).as_posix(),
                        si_relative=si_folder.relative_to(root).as_posix(),
                        group_ids=_reference_group_ids(
                            reference_id,
                            library["groups"],
                            group_map,
                        ),
                        tag_ids=list(
                            dict.fromkeys(
                                tag_map[tag_id]
                                for tag_id in reference["endnote_tag_ids"]
                                if tag_id in tag_map
                            )
                        ),
                    )
                    catalog["papers"].append(record)
                    imported_ids.append(paper_id)
                    changed_files.extend(
                        [
                            record["paths"]["pdf"],
                            record["paths"]["si_folder"],
                        ]
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
                raise LiteratureProjectError(f"导入 EndNote 文献库失败：{exc}") from exc

    return {
        "ok": True,
        "source_path": str(source),
        "imported_count": len(imported_ids),
        "failed_count": len(failures),
        "group_count": len(library["groups"]),
        "tag_count": len(library["tags"]),
        "paper_ids": imported_ids,
        "failures": failures,
        "changed_files": ["catalog.json", "tags.json", "groups.json", *changed_files],
    }


def _normalized_doi(value: Any) -> str:
    doi = str(value or "").strip().casefold()
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi)
    return doi.strip()


def _normalized_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"\W+", "", text, flags=re.UNICODE)


def _first_author_key(value: Any) -> str:
    authors = str(value or "").splitlines()[0].strip()
    if not authors:
        return ""
    if "," in authors:
        authors = authors.split(",", 1)[0]
    else:
        authors = authors.split(";", 1)[0].split(" and ", 1)[0].split()[-1]
    return _normalized_text(authors)


def scan_literature_duplicates(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    papers = _catalog(root)["papers"]
    groups: list[dict[str, Any]] = []
    for left_index, left in enumerate(papers):
        for right in papers[left_index + 1 :]:
            reasons: list[str] = []
            left_doi = _normalized_doi(left.get("doi"))
            right_doi = _normalized_doi(right.get("doi"))
            if left_doi and left_doi == right_doi:
                reasons.append("doi")
            left_hash = str(left.get("content_sha256") or "").strip().casefold()
            right_hash = str(right.get("content_sha256") or "").strip().casefold()
            if left_hash and left_hash == right_hash:
                reasons.append("main_pdf_sha256")
            left_fingerprint = (
                _normalized_text(left.get("title")),
                left.get("year"),
                _first_author_key(left.get("authors")),
            )
            right_fingerprint = (
                _normalized_text(right.get("title")),
                right.get("year"),
                _first_author_key(right.get("authors")),
            )
            if (
                all(value not in {"", None} for value in left_fingerprint)
                and left_fingerprint == right_fingerprint
            ):
                reasons.append("title_year_first_author")
            if reasons:
                groups.append(
                    {
                        "paper_ids": [str(left["id"]), str(right["id"])],
                        "reasons": reasons,
                        "confidence": (
                            "exact"
                            if {"doi", "main_pdf_sha256"}.intersection(reasons)
                            else "possible"
                        ),
                    }
                )
    return {"ok": True, "group_count": len(groups), "groups": groups}
