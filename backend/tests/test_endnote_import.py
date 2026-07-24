from __future__ import annotations

import json
import sqlite3
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path


def _group_spec(name: str, type_code: int = 3, color: str | None = None) -> bytes:
    rules = f"<rule>TYPE;{type_code}</rule>"
    if color:
        rules += f"<rule>COLOR;{color}</rule>"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<group version=\"1\"><ids><id>{name}-uuid</id><name>{name}</name></ids>"
        f"<rules>{rules}</rules></group>"
    ).encode("utf-8")


def _group_members(*reference_ids: int) -> bytes:
    return (
        struct.pack(">I", 2)
        + struct.pack("<I", len(reference_ids))
        + b"".join(struct.pack("<I", reference_id) for reference_id in reference_ids)
    )


def _write_pdf(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"%PDF-1.4\n% {label}\n".encode("utf-8"))


class EndNoteImportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.library = self.base / "Source Library.enl"
        self.data_root = self.base / "Source Library.Data"
        self.project_root = self.base / "workmode-project"
        self._create_endnote_library(self.library, self.data_root)

        from app.literature_project import initialize_literature_project

        initialize_literature_project(self.project_root, name="Imported library")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _create_endnote_library(self, database: Path, data_root: Path) -> None:
        connection = sqlite3.connect(database)
        try:
            connection.executescript(
                """
                CREATE TABLE refs(
                    id INTEGER PRIMARY KEY,
                    trash_state INTEGER NOT NULL DEFAULT 0,
                    reference_type INTEGER NOT NULL DEFAULT 0,
                    author TEXT NOT NULL DEFAULT '',
                    year TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    secondary_title TEXT NOT NULL DEFAULT '',
                    electronic_resource_number TEXT NOT NULL DEFAULT '',
                    date TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE file_res(
                    refs_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type INTEGER NOT NULL DEFAULT 1,
                    file_pos INTEGER NOT NULL
                );
                CREATE TABLE groups(
                    group_id INTEGER PRIMARY KEY,
                    recs_stamp INTEGER NOT NULL DEFAULT 0,
                    spec BLOB NOT NULL,
                    members BLOB NOT NULL
                );
                CREATE TABLE tag_groups(
                    group_id INTEGER PRIMARY KEY,
                    spec BLOB NOT NULL
                );
                CREATE TABLE tag_members_content(
                    id INTEGER PRIMARY KEY,
                    c0 TEXT
                );
                CREATE TABLE misc(
                    code INTEGER NOT NULL,
                    subcode INTEGER NOT NULL,
                    value BLOB NOT NULL,
                    PRIMARY KEY(code, subcode)
                );
                """
            )
            connection.executemany(
                """
                INSERT INTO refs(
                    id, trash_state, reference_type, author, year, title,
                    secondary_title, electronic_resource_number, date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        1,
                        0,
                        0,
                        "Li, Wen\rZhang, Ming",
                        "2024",
                        "Catalysis with complete attachments",
                        "Journal of Catalysis",
                        "10.1000/main",
                        "2024-03-18",
                    ),
                    (
                        2,
                        0,
                        0,
                        "NoPDF, Alice",
                        "2023",
                        "Record without a PDF",
                        "No PDF Journal",
                        "10.1000/no-pdf",
                        "2023",
                    ),
                    (
                        3,
                        0,
                        0,
                        "Wang, Bo",
                        "2022",
                        "Second importable record",
                        "Chemistry Letters",
                        "10.1000/second",
                        "March 2022",
                    ),
                ],
            )
            connection.executemany(
                "INSERT INTO file_res(refs_id, file_path, file_type, file_pos) VALUES (?, ?, 1, ?)",
                [
                    (1, "1000/cover-letter.docx", 0),
                    (1, "1001/main-article.PDF", 1),
                    (1, "1002/raw-data.xlsx", 2),
                    (1, "1003/supporting-information.pdf", 3),
                    (2, "2000/only-notes.docx", 0),
                    (3, "3000/second-main.pdf", 0),
                ],
            )
            connection.executemany(
                "INSERT INTO groups(group_id, spec, members) VALUES (?, ?, ?)",
                [
                    (1, _group_spec("Catalysis"), _group_members(1, 3)),
                    (2, _group_spec("Discarded smart group", type_code=8), _group_members(1)),
                ],
            )
            connection.executemany(
                "INSERT INTO tag_groups(group_id, spec) VALUES (?, ?)",
                [
                    (1, _group_spec("XPS", type_code=10, color="de3131")),
                    (2, _group_spec("Operando", type_code=10, color="f6a33a")),
                ],
            )
            connection.executemany(
                "INSERT INTO tag_members_content(id, c0) VALUES (?, ?)",
                [(1, "1 2"), (2, ""), (3, "2")],
            )
            connection.execute(
                "INSERT INTO misc(code, subcode, value) VALUES (17, 1, ?)",
                (
                    (
                        '<?xml version="1.0" encoding="UTF-8"?>'
                        "<groupset version=\"1\"><ids><id>research-uuid</id>"
                        "<name>Research</name></ids><members complex=\"true\">"
                        "<member>Catalysis-uuid</member></members></groupset>"
                    ).encode("utf-8"),
                ),
            )
            connection.commit()
        finally:
            connection.close()

        files = {
            "1000/cover-letter.docx": b"word attachment",
            "1002/raw-data.xlsx": b"excel attachment",
            "2000/only-notes.docx": b"no pdf here",
        }
        for relative, content in files.items():
            target = data_root / "PDF" / Path(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        _write_pdf(data_root / "PDF/1001/main-article.PDF", "main")
        _write_pdf(data_root / "PDF/1003/supporting-information.pdf", "si")
        _write_pdf(data_root / "PDF/3000/second-main.pdf", "second")

    def test_project_schema_v2_migrates_existing_catalog_and_tag_categories(self) -> None:
        from app.literature_project import initialize_literature_project

        legacy_root = self.base / "legacy-project"
        legacy_root.mkdir()
        (legacy_root / "literature-project.json").write_text(
            json.dumps(
                {
                    "project_type": "literature-library",
                    "schema_version": 1,
                    "tool_profile": "literature",
                    "frontend_projection": "literature-library",
                }
            ),
            encoding="utf-8",
        )
        (legacy_root / "catalog.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "papers": [
                        {
                            "id": "legacy-paper",
                            "title": "Legacy",
                            "tag_ids": ["xps"],
                            "paths": {"pdf": "papers/unprocessed/pdf/legacy.pdf"},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (legacy_root / "tags.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "tags": [
                        {
                            "id": "xps",
                            "name": "XPS",
                            "aliases": [],
                            "category": "characterization",
                            "status": "confirmed",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        initialize_literature_project(legacy_root, name="Legacy")

        manifest = json.loads((legacy_root / "literature-project.json").read_text(encoding="utf-8"))
        catalog = json.loads((legacy_root / "catalog.json").read_text(encoding="utf-8"))
        tags = json.loads((legacy_root / "tags.json").read_text(encoding="utf-8"))
        groups = json.loads((legacy_root / "groups.json").read_text(encoding="utf-8"))
        paper = catalog["papers"][0]

        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(catalog["schema_version"], 2)
        self.assertEqual(tags["schema_version"], 2)
        self.assertEqual(groups, {"schema_version": 1, "groups": []})
        self.assertEqual(paper["publication_date"], "")
        self.assertEqual(paper["group_ids"], [])
        self.assertEqual(paper["paths"]["si_folder"], "papers/unprocessed/SI/legacy-paper")
        self.assertEqual(tags["tags"][0]["group_id"], "ungrouped")
        self.assertNotIn("category", tags["tags"][0])
        self.assertTrue(
            any(group["id"] == "ungrouped" and group["color"] for group in tags["groups"])
        )
        self.assertFalse(
            {"characterization", "material", "mechanism", "performance", "uncategorized"}
            .intersection(group["id"] for group in tags["groups"])
        )

    def test_inspection_and_import_preserve_groups_tags_colors_and_si_files(self) -> None:
        from app.endnote_import import import_endnote_library, inspect_endnote_library

        preview = inspect_endnote_library(self.library)
        self.assertEqual(preview["reference_count"], 3)
        self.assertEqual(preview["attachment_count"], 6)
        self.assertEqual(preview["manual_group_count"], 1)
        self.assertEqual(preview["tag_count"], 2)
        self.assertEqual(preview["importable_count"], 2)
        self.assertEqual(preview["failed_count"], 1)

        result = import_endnote_library(self.project_root, self.library)

        self.assertEqual(result["imported_count"], 2)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(result["group_count"], 1)
        self.assertEqual(result["tag_count"], 2)
        self.assertEqual(result["failures"][0]["endnote_record_id"], 2)
        self.assertIn("有效 PDF", result["failures"][0]["reason"])

        catalog = json.loads((self.project_root / "catalog.json").read_text(encoding="utf-8"))
        tags = json.loads((self.project_root / "tags.json").read_text(encoding="utf-8"))
        groups = json.loads((self.project_root / "groups.json").read_text(encoding="utf-8"))
        imported = {paper["doi"]: paper for paper in catalog["papers"]}

        first = imported["10.1000/main"]
        self.assertEqual(first["publication_date"], "2024-03-18")
        self.assertEqual(first["paper_type"], "unknown")
        self.assertEqual(first["group_ids"], [groups["groups"][0]["id"]])
        self.assertEqual(groups["groups"][0]["name"], "Research - Catalysis")
        self.assertEqual(len(first["tag_ids"]), 2)
        self.assertTrue(first["paths"]["pdf"].endswith("main-article.PDF"))
        self.assertTrue((self.project_root / first["paths"]["pdf"]).exists())

        si_dir = self.project_root / first["paths"]["si_folder"]
        self.assertEqual(
            {path.name for path in si_dir.iterdir()},
            {"cover-letter.docx", "raw-data.xlsx", "supporting-information.pdf"},
        )
        self.assertEqual({group["color"] for group in tags["groups"] if group["id"].startswith("endnote-")}, {"#DE3131", "#F6A33A"})
        self.assertEqual({tag["name"] for tag in tags["tags"]}, {"XPS", "Operando"})

    def test_enlx_uses_the_first_valid_pdf_even_when_a_non_pdf_attachment_comes_first(self) -> None:
        from app.endnote_import import import_endnote_library

        archive = self.base / "Source Library.enlx"
        with zipfile.ZipFile(archive, "w", allowZip64=True) as bundle:
            bundle.write(self.library, "sdb/sdb.eni")
            for source in (self.data_root / "PDF").rglob("*"):
                if source.is_file():
                    bundle.write(source, f"PDF/{source.relative_to(self.data_root / 'PDF').as_posix()}")

        second_project = self.base / "enlx-project"
        from app.literature_project import initialize_literature_project

        initialize_literature_project(second_project, name="ENLX")
        result = import_endnote_library(second_project, archive)
        catalog = json.loads((second_project / "catalog.json").read_text(encoding="utf-8"))
        first = next(paper for paper in catalog["papers"] if paper["doi"] == "10.1000/main")

        self.assertEqual(result["imported_count"], 2)
        self.assertTrue(first["paths"]["pdf"].endswith("main-article.PDF"))
        self.assertTrue((second_project / first["paths"]["si_folder"] / "cover-letter.docx").exists())

    def test_auto_search_and_post_import_duplicate_scan(self) -> None:
        from app.endnote_import import find_endnote_libraries, scan_literature_duplicates

        nested = self.base / "search-root" / "endnote"
        nested.mkdir(parents=True)
        candidate = nested / "My References.enl"
        candidate.write_bytes(self.library.read_bytes())
        (nested / "Ignored.Data").mkdir()

        found = find_endnote_libraries([self.base / "search-root"])
        self.assertEqual([item["path"] for item in found], [str(candidate.resolve())])

        catalog_path = self.project_root / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["papers"] = [
            {
                "id": "a",
                "title": "Same title",
                "authors": "Li, Wen",
                "year": 2024,
                "doi": "10.1000/SAME",
                "content_sha256": "abc",
                "paths": {"pdf": "", "si_folder": "papers/unprocessed/SI/a"},
            },
            {
                "id": "b",
                "title": "Same title",
                "authors": "Li, W.",
                "year": 2024,
                "doi": "https://doi.org/10.1000/same",
                "content_sha256": "def",
                "paths": {"pdf": "", "si_folder": "papers/unprocessed/SI/b"},
            },
            {
                "id": "c",
                "title": "Different title",
                "authors": "Other, A.",
                "year": 2020,
                "doi": "",
                "content_sha256": "abc",
                "paths": {"pdf": "", "si_folder": "papers/unprocessed/SI/c"},
            },
        ]
        catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

        result = scan_literature_duplicates(self.project_root)
        pairs = {(item["paper_ids"][0], item["paper_ids"][1]): set(item["reasons"]) for item in result["groups"]}

        self.assertIn(("a", "b"), pairs)
        self.assertIn("doi", pairs[("a", "b")])
        self.assertIn(("a", "c"), pairs)
        self.assertIn("main_pdf_sha256", pairs[("a", "c")])


if __name__ == "__main__":
    unittest.main()
