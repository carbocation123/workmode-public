from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class WordAddinApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.previous_data_dir = os.environ.get("WORKMODE_PUBLIC_DATA_DIR")
        os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.tmp.name

        from app import config, storage
        from app.literature_project import initialize_literature_project

        storage.settings = config.reload_settings()
        self.storage = storage
        self.root = Path(self.tmp.name) / "library"
        initialize_literature_project(self.root, name="Catalysis library")
        self.project = storage.create_project("Catalysis library", str(self.root))
        catalog_path = self.root / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["papers"] = [
            {
                "id": "paper-rutile",
                "title": "Rutile catalyst",
                "authors": "Zhang, San",
                "journal": "ACS Catalysis",
                "year": 2026,
                "tags": ["TiO2-rutile"],
                "tag_ids": [],
                "group_ids": [],
                "paths": {},
            },
            {
                "id": "paper-anatase",
                "title": "Anatase support",
                "authors": "Li, Si",
                "journal": "Nature",
                "year": 2025,
                "tags": ["TiO2-anatase"],
                "tag_ids": [],
                "group_ids": [],
                "paths": {},
            },
        ]
        catalog_path.write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        if self.previous_data_dir is None:
            os.environ.pop("WORKMODE_PUBLIC_DATA_DIR", None)
        else:
            os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.previous_data_dir
        self.tmp.cleanup()

    def test_bootstrap_and_search_use_the_active_literature_project(self) -> None:
        from app.word_addin import read_word_addin_bootstrap, search_word_addin_papers

        bootstrap = read_word_addin_bootstrap()
        papers = search_word_addin_papers(query="rutile", limit=10)

        self.assertEqual(bootstrap["project"]["slug"], self.project.slug)
        self.assertEqual(bootstrap["project"]["name"], "Catalysis library")
        self.assertEqual(len(bootstrap["styles"]), 5)
        self.assertEqual([paper["id"] for paper in papers["papers"]], ["paper-rutile"])

    def test_insert_and_refresh_target_the_active_word_document(self) -> None:
        from app.word_addin import (
            WordAddinCitationRequest,
            WordAddinStyleRequest,
            insert_word_addin_citation,
            refresh_word_addin_document,
        )

        request = WordAddinCitationRequest(
            paper_ids=["paper-rutile"],
            style_id="nature",
            prefix="see",
            suffix="",
            locator_label="page",
            locator_value="12",
            suppress_author=False,
        )
        with patch(
            "app.word_addin.insert_word_citation_group",
            return_value={"ok": True, "document_name": "draft.docx"},
        ) as insert:
            result = insert_word_addin_citation(request)
        self.assertEqual(result["document_name"], "draft.docx")
        self.assertEqual(insert.call_args.args[1], None)
        self.assertEqual(insert.call_args.args[2], "nature")
        self.assertEqual(insert.call_args.args[0]["items"][0]["paper_id"], "paper-rutile")

        with patch(
            "app.word_addin.refresh_word_citations",
            return_value={"ok": True, "citation_count": 1},
        ) as refresh:
            result = refresh_word_addin_document(WordAddinStyleRequest(style_id="nature"))
        self.assertEqual(result["citation_count"], 1)
        refresh.assert_called_once_with(None, "nature")

    def test_inspection_update_remove_and_bibliography_keep_existing_storage(self) -> None:
        from app.word_addin import (
            WordAddinCitationUpdateRequest,
            WordAddinInstanceRequest,
            WordAddinStyleRequest,
            create_word_addin_bibliography,
            inspect_word_addin_document,
            remove_word_addin_citation,
            update_word_addin_citation,
        )

        with patch(
            "app.word_addin.inspect_word_citations",
            return_value={"citation_groups": [], "style_id": "nature"},
        ) as inspect:
            self.assertEqual(inspect_word_addin_document()["style_id"], "nature")
        inspect.assert_called_once_with(None)

        update_request = WordAddinCitationUpdateRequest(
            instance_id="abc",
            paper_ids=["paper-anatase"],
            style_id="apa-7th",
        )
        with patch(
            "app.word_addin.update_word_citation_group",
            return_value={"ok": True},
        ) as update:
            update_word_addin_citation(update_request)
        self.assertEqual(update.call_args.args[2], None)

        with patch(
            "app.word_addin.remove_word_citation_group",
            return_value={"ok": True},
        ) as remove:
            remove_word_addin_citation(
                WordAddinInstanceRequest(instance_id="abc", style_id="apa-7th")
            )
        remove.assert_called_once_with("abc", None, "apa-7th")

        with patch(
            "app.word_addin.create_word_bibliography",
            return_value={"ok": True},
        ) as bibliography:
            create_word_addin_bibliography(WordAddinStyleRequest(style_id="apa-7th"))
        bibliography.assert_called_once_with(None, "apa-7th")


if __name__ == "__main__":
    unittest.main()
