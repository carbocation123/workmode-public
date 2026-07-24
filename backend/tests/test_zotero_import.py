from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


def _write_pdf(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"%PDF-1.4\n% {label}\n".encode("utf-8"))


class ZoteroImportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.data_root = self.base / "Zotero"
        self.database = self.data_root / "zotero.sqlite"
        self.project_root = self.base / "workmode-project"
        self.linked_note = self.base / "linked" / "cover-letter.docx"
        self._create_zotero_library()

        from app.literature_project import initialize_literature_project

        initialize_literature_project(self.project_root, name="Imported Zotero library")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _create_zotero_library(self) -> None:
        self.data_root.mkdir(parents=True)
        self.linked_note.parent.mkdir(parents=True)
        self.linked_note.write_bytes(b"linked Word attachment")
        connection = sqlite3.connect(self.database)
        try:
            connection.executescript(
                """
                CREATE TABLE version(schema TEXT PRIMARY KEY, version INTEGER NOT NULL);
                CREATE TABLE libraries(
                    libraryID INTEGER PRIMARY KEY,
                    type TEXT NOT NULL,
                    editable INTEGER NOT NULL,
                    filesEditable INTEGER NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    storageVersion INTEGER NOT NULL DEFAULT 0,
                    lastSync INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 0,
                    isAdmin INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE itemTypes(itemTypeID INTEGER PRIMARY KEY, typeName TEXT NOT NULL);
                CREATE TABLE fields(fieldID INTEGER PRIMARY KEY, fieldName TEXT NOT NULL);
                CREATE TABLE items(
                    itemID INTEGER PRIMARY KEY,
                    itemTypeID INTEGER NOT NULL,
                    dateAdded TEXT NOT NULL,
                    dateModified TEXT NOT NULL,
                    clientDateModified TEXT NOT NULL,
                    libraryID INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    synced INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE itemDataValues(valueID INTEGER PRIMARY KEY, value TEXT UNIQUE);
                CREATE TABLE itemData(
                    itemID INTEGER NOT NULL,
                    fieldID INTEGER NOT NULL,
                    valueID INTEGER NOT NULL,
                    PRIMARY KEY(itemID, fieldID)
                );
                CREATE TABLE creatorTypes(
                    creatorTypeID INTEGER PRIMARY KEY,
                    creatorType TEXT NOT NULL
                );
                CREATE TABLE creators(
                    creatorID INTEGER PRIMARY KEY,
                    firstName TEXT,
                    lastName TEXT,
                    fieldMode INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE itemCreators(
                    itemID INTEGER NOT NULL,
                    creatorID INTEGER NOT NULL,
                    creatorTypeID INTEGER NOT NULL,
                    orderIndex INTEGER NOT NULL,
                    PRIMARY KEY(itemID, creatorID, creatorTypeID, orderIndex)
                );
                CREATE TABLE collections(
                    collectionID INTEGER PRIMARY KEY,
                    collectionName TEXT NOT NULL,
                    parentCollectionID INTEGER,
                    clientDateModified TEXT NOT NULL,
                    libraryID INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    synced INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE collectionItems(
                    collectionID INTEGER NOT NULL,
                    itemID INTEGER NOT NULL,
                    orderIndex INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(collectionID, itemID)
                );
                CREATE TABLE tags(tagID INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
                CREATE TABLE itemTags(
                    itemID INTEGER NOT NULL,
                    tagID INTEGER NOT NULL,
                    type INTEGER NOT NULL,
                    PRIMARY KEY(itemID, tagID)
                );
                CREATE TABLE itemAttachments(
                    itemID INTEGER PRIMARY KEY,
                    parentItemID INTEGER,
                    linkMode INTEGER NOT NULL,
                    contentType TEXT,
                    charsetID INTEGER,
                    path TEXT,
                    syncState INTEGER DEFAULT 0,
                    storageModTime INTEGER,
                    storageHash TEXT,
                    lastProcessedModificationTime INTEGER,
                    lastRead INTEGER
                );
                CREATE TABLE deletedItems(
                    itemID INTEGER PRIMARY KEY,
                    dateDeleted TEXT NOT NULL
                );
                CREATE TABLE syncedSettings(
                    setting TEXT NOT NULL,
                    libraryID INTEGER NOT NULL,
                    value TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    synced INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(setting, libraryID)
                );
                """
            )
            connection.execute("INSERT INTO version(schema, version) VALUES ('userdata', 107)")
            connection.execute(
                "INSERT INTO libraries(libraryID, type, editable, filesEditable) "
                "VALUES (1, 'user', 1, 1)"
            )
            connection.executemany(
                "INSERT INTO itemTypes(itemTypeID, typeName) VALUES (?, ?)",
                [(1, "journalArticle"), (14, "attachment")],
            )
            connection.executemany(
                "INSERT INTO fields(fieldID, fieldName) VALUES (?, ?)",
                [
                    (1, "title"),
                    (2, "date"),
                    (3, "publicationTitle"),
                    (4, "journalAbbreviation"),
                    (5, "DOI"),
                ],
            )
            connection.execute(
                "INSERT INTO creatorTypes(creatorTypeID, creatorType) VALUES (1, 'author')"
            )
            items = [
                (1, 1, "PAPER001"),
                (2, 1, "NOPDF01"),
                (10, 14, "COVER001"),
                (11, 14, "MAIN0001"),
                (12, 14, "DATA0001"),
                (13, 14, "SI000001"),
                (20, 14, "ONLYDOC1"),
            ]
            connection.executemany(
                """
                INSERT INTO items(
                    itemID, itemTypeID, dateAdded, dateModified,
                    clientDateModified, libraryID, key
                ) VALUES (?, ?, '2026-01-01', '2026-01-01', '2026-01-01', 1, ?)
                """,
                items,
            )

            metadata = {
                1: {
                    "title": "Catalysis from Zotero",
                    "date": "2024-03-18",
                    "publicationTitle": "Journal of Catalysis",
                    "journalAbbreviation": "J Catal",
                    "DOI": "10.1000/zotero-main",
                },
                2: {
                    "title": "Metadata only record",
                    "date": "2023",
                    "publicationTitle": "No PDF Journal",
                    "DOI": "10.1000/zotero-no-pdf",
                },
            }
            field_ids = {
                row[1]: row[0]
                for row in connection.execute("SELECT fieldID, fieldName FROM fields")
            }
            value_id = 1
            for item_id, values in metadata.items():
                for field_name, value in values.items():
                    connection.execute(
                        "INSERT INTO itemDataValues(valueID, value) VALUES (?, ?)",
                        (value_id, value),
                    )
                    connection.execute(
                        "INSERT INTO itemData(itemID, fieldID, valueID) VALUES (?, ?, ?)",
                        (item_id, field_ids[field_name], value_id),
                    )
                    value_id += 1

            connection.executemany(
                "INSERT INTO creators(creatorID, firstName, lastName, fieldMode) VALUES (?, ?, ?, ?)",
                [
                    (1, "Wen", "Li", 0),
                    (2, "", "Catalysis Consortium", 1),
                    (3, "Alice", "NoPDF", 0),
                ],
            )
            connection.executemany(
                """
                INSERT INTO itemCreators(
                    itemID, creatorID, creatorTypeID, orderIndex
                ) VALUES (?, ?, 1, ?)
                """,
                [(1, 1, 0), (1, 2, 1), (2, 3, 0)],
            )
            connection.executemany(
                """
                INSERT INTO collections(
                    collectionID, collectionName, parentCollectionID,
                    clientDateModified, libraryID, key
                ) VALUES (?, ?, ?, '2026-01-01', 1, ?)
                """,
                [
                    (1, "Doctoral Research", None, "COLL0001"),
                    (2, "Catalysis", 1, "COLL0002"),
                    (3, "To Read", None, "COLL0003"),
                ],
            )
            connection.executemany(
                "INSERT INTO collectionItems(collectionID, itemID) VALUES (?, ?)",
                [(2, 1), (3, 1), (3, 2)],
            )
            connection.executemany(
                "INSERT INTO tags(tagID, name) VALUES (?, ?)",
                [(1, "XPS"), (2, "Operando"), (3, "Imported keyword")],
            )
            connection.executemany(
                "INSERT INTO itemTags(itemID, tagID, type) VALUES (?, ?, ?)",
                [(1, 1, 0), (1, 2, 0), (1, 3, 1), (2, 3, 1)],
            )
            connection.execute(
                """
                INSERT INTO syncedSettings(setting, libraryID, value)
                VALUES ('tagColors', 1, ?)
                """,
                (json.dumps([{"name": "Operando", "color": "#F6A33A"}]),),
            )
            connection.executemany(
                """
                INSERT INTO itemAttachments(
                    itemID, parentItemID, linkMode, contentType, path
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (10, 1, 2, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", str(self.linked_note)),
                    (11, 1, 0, "application/pdf", "storage:main-article.pdf"),
                    (12, 1, 0, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "storage:raw-data.xlsx"),
                    (13, 1, 0, "application/pdf", "storage:supporting-information.pdf"),
                    (20, 2, 0, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "storage:only-notes.docx"),
                ],
            )
            connection.commit()
        finally:
            connection.close()

        _write_pdf(self.data_root / "storage/MAIN0001/main-article.pdf", "main")
        _write_pdf(
            self.data_root / "storage/SI000001/supporting-information.pdf",
            "supporting information",
        )
        spreadsheet = self.data_root / "storage/DATA0001/raw-data.xlsx"
        spreadsheet.parent.mkdir(parents=True)
        spreadsheet.write_bytes(b"spreadsheet")
        only_note = self.data_root / "storage/ONLYDOC1/only-notes.docx"
        only_note.parent.mkdir(parents=True)
        only_note.write_bytes(b"no PDF")

    def test_inspection_and_import_preserve_metadata_collections_tags_and_attachments(self) -> None:
        from app.zotero_import import import_zotero_library, inspect_zotero_library

        preview = inspect_zotero_library(self.data_root)

        self.assertEqual(preview["reference_count"], 2)
        self.assertEqual(preview["attachment_count"], 5)
        self.assertEqual(preview["collection_count"], 3)
        self.assertEqual(preview["tag_count"], 3)
        self.assertEqual(preview["importable_count"], 1)
        self.assertEqual(preview["failed_count"], 1)

        result = import_zotero_library(self.project_root, self.data_root)

        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(result["group_count"], 3)
        self.assertEqual(result["tag_count"], 3)
        self.assertEqual(result["failures"][0]["zotero_item_id"], 2)
        self.assertIn("有效 PDF", result["failures"][0]["reason"])

        catalog = json.loads((self.project_root / "catalog.json").read_text(encoding="utf-8"))
        tags = json.loads((self.project_root / "tags.json").read_text(encoding="utf-8"))
        groups = json.loads((self.project_root / "groups.json").read_text(encoding="utf-8"))
        paper = catalog["papers"][0]

        self.assertEqual(paper["title"], "Catalysis from Zotero")
        self.assertEqual(paper["authors"], "Li, Wen, Catalysis Consortium")
        self.assertEqual(paper["first_author_surname"], "Li")
        self.assertEqual(paper["year"], 2024)
        self.assertEqual(paper["publication_date"], "2024-03-18")
        self.assertEqual(paper["journal"], "Journal of Catalysis")
        self.assertEqual(paper["journal_abbreviation"], "J Catal")
        self.assertEqual(paper["doi"], "10.1000/zotero-main")
        self.assertEqual(
            {group["name"] for group in groups["groups"] if group["id"] in paper["group_ids"]},
            {"Doctoral Research - Catalysis", "To Read"},
        )
        self.assertEqual(
            {tag["name"] for tag in tags["tags"] if tag["id"] in paper["tag_ids"]},
            {"XPS", "Operando", "Imported keyword"},
        )
        self.assertTrue(
            any(
                group["color"] == "#F6A33A"
                and group["id"]
                == next(tag["group_id"] for tag in tags["tags"] if tag["name"] == "Operando")
                for group in tags["groups"]
            )
        )
        self.assertTrue(
            any(
                group["name"] == "Zotero 自动标签"
                and group["id"]
                == next(
                    tag["group_id"]
                    for tag in tags["tags"]
                    if tag["name"] == "Imported keyword"
                )
                for group in tags["groups"]
            )
        )
        self.assertTrue((self.project_root / paper["paths"]["pdf"]).exists())
        self.assertTrue(paper["paths"]["pdf"].endswith("main-article.pdf"))
        self.assertEqual(
            {
                path.name
                for path in (self.project_root / paper["paths"]["si_folder"]).iterdir()
            },
            {"cover-letter.docx", "raw-data.xlsx", "supporting-information.pdf"},
        )

    def test_auto_search_finds_data_directories_and_skips_storage_trees(self) -> None:
        from app.zotero_import import find_zotero_libraries

        false_positive = (
            self.data_root / "storage/MAIN0001/nested/Zotero/zotero.sqlite"
        )
        false_positive.parent.mkdir(parents=True)
        false_positive.write_bytes(b"not a database")

        found = find_zotero_libraries([self.base])

        self.assertEqual([item["path"] for item in found], [str(self.data_root.resolve())])
        self.assertTrue(found[0]["has_storage"])
        self.assertEqual(found[0]["database_path"], str(self.database.resolve()))

    def test_file_selection_accepts_data_directory_or_database_path(self) -> None:
        from app.zotero_import import inspect_zotero_library

        by_directory = inspect_zotero_library(self.data_root)
        by_database = inspect_zotero_library(self.database)

        self.assertEqual(by_directory["database_path"], by_database["database_path"])
        self.assertEqual(by_directory["data_directory"], by_database["data_directory"])

    def test_storage_attachment_key_cannot_escape_the_zotero_storage_directory(self) -> None:
        from app.zotero_import import _attachment_source

        escaped = _attachment_source(
            self.data_root,
            item_key="../../outside",
            link_mode=0,
            stored_path="storage:secret.pdf",
        )

        self.assertIsNone(escaped)


if __name__ == "__main__":
    unittest.main()
