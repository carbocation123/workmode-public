from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class LiteratureModeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("WORKMODE_PUBLIC_DATA_DIR")
        os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.tmp.name

        from app import config, storage

        storage.settings = config.reload_settings()
        self.storage = storage
        self.root = Path(self.tmp.name) / "library"

        from app.literature_project import initialize_literature_project

        initialize_literature_project(self.root, name="Catalysis library")
        self.project = storage.create_project("Catalysis library", str(self.root))

    def tearDown(self) -> None:
        if self.old_data_dir is None:
            os.environ.pop("WORKMODE_PUBLIC_DATA_DIR", None)
        else:
            os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.old_data_dir
        self.tmp.cleanup()

    def test_manifest_selects_only_literature_domain_tools(self) -> None:
        from app.project_tools import project_tool_names, project_tool_schemas

        expected = {
            "literature_search",
            "literature_tag_list",
            "literature_read",
            "literature_import",
            "literature_process",
            "literature_update_record",
            "literature_update_cross_relation",
            "literature_archive",
            "literature_note_search",
            "literature_note_read",
            "literature_note_upsert",
            "literature_note_export",
        }

        self.assertEqual(project_tool_names(self.project.slug), expected)
        self.assertEqual(
            {item["function"]["name"] for item in project_tool_schemas(self.project.slug)},
            expected,
        )
        self.assertNotIn("project_bash", project_tool_names(self.project.slug))
        self.assertNotIn("project_write", project_tool_names(self.project.slug))
        self.assertNotIn("memory_write", project_tool_names(self.project.slug))
        self.assertNotIn("web_search", project_tool_names(self.project.slug))

        schemas = {
            item["function"]["name"]: item["function"]
            for item in project_tool_schemas(self.project.slug)
        }
        self.assertIn("before assigning tags", schemas["literature_tag_list"]["description"])
        self.assertIn("literature_tag_list", schemas["literature_update_record"]["description"])

    def test_record_update_executes_directly_without_approval_or_selection(self) -> None:
        from app.literature_project import execute_literature_tool

        catalog_path = self.root / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["papers"].append(
            {
                "id": "paper-1",
                "title": "Test paper",
                "original_filename": "source.pdf",
                "status": "review",
                "tag_ids": [],
                "focus": "",
                "summary": "",
                "paths": {},
            }
        )
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = execute_literature_tool(
            self.project.slug,
            "literature_update_record",
            {
                "paper_id": "paper-1",
                "tags": [{"name": "EPR", "category": "characterization"}],
                "focus": "缺陷电子结构",
                "summary": "讨论 EPR 证据链。",
            },
        )

        self.assertTrue(result.ok, result.content)
        payload = json.loads(result.content)
        self.assertEqual(payload["operation"], "literature_update_record")
        self.assertEqual(payload["paper_id"], "paper-1")
        self.assertNotIn("proposal_id", payload)
        self.assertNotIn("confirmed", payload)
        updated = json.loads(catalog_path.read_text(encoding="utf-8"))["papers"][0]
        self.assertEqual(updated["focus"], "缺陷电子结构")
        self.assertEqual(updated["tag_ids"], ["epr"])

        tag_result = execute_literature_tool(
            self.project.slug,
            "literature_tag_list",
            {"query": "epr", "category": "characterization"},
        )
        self.assertTrue(tag_result.ok, tag_result.content)
        tag_payload = json.loads(tag_result.content)
        self.assertEqual(tag_payload["operation"], "literature_tag_list")
        self.assertEqual(tag_payload["count"], 1)
        self.assertEqual(
            tag_payload["tags"][0],
            {
                "id": "epr",
                "name": "EPR",
                "aliases": [],
                "category": "characterization",
                "status": "provisional",
                "usage_count": 1,
            },
        )

    def test_system_prompt_and_budget_use_literature_tool_profile(self) -> None:
        from app.prompt import build_system_prompt

        prompt, usage = build_system_prompt(self.project)

        self.assertIn("文献库特化模式", prompt)
        self.assertNotIn("project_bash", prompt)
        self.assertEqual(usage["tool_profile"], "literature")
        self.assertEqual(usage["tool_count"], 12)

    def test_projection_route_updates_without_confirmed_flag(self) -> None:
        from app.main import app
        from fastapi.testclient import TestClient

        catalog_path = self.root / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["papers"].append(
            {
                "id": "paper-route",
                "title": "Route paper",
                "original_filename": "route.pdf",
                "status": "review",
                "tag_ids": [],
                "focus": "",
                "summary": "",
                "paths": {},
            }
        )
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        client = TestClient(app)
        health = client.get(f"/api/work/projects/{self.project.slug}/literature/health")
        updated = client.patch(
            f"/api/work/projects/{self.project.slug}/literature/papers/paper-route",
            json={"focus": "direct write"},
        )

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["tool_profile"], "literature")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["focus"], "direct write")

    def test_chat_persists_active_context_as_message_metadata(self) -> None:
        from app.main import app
        from fastapi.testclient import TestClient

        session = self.storage.create_session(self.project.slug)

        async def no_model_events(*_args, **_kwargs):
            if False:
                yield {}

        with patch("app.routes.stream_openai_compatible", no_model_events):
            response = TestClient(app).post(
                f"/api/work/sessions/{session.id}/chat/stream",
                json={
                    "content": "讨论这篇文章",
                    "active_context": [{"kind": "paper", "id": "paper-1"}],
                },
            )

        self.assertEqual(response.status_code, 200)
        message = self.storage.read_messages(session.id, limit=0)[0]
        self.assertEqual(message["meta"]["active_context"], [{"kind": "paper", "id": "paper-1"}])

    def test_confirmed_import_is_an_invisible_system_context_event(self) -> None:
        from app.main import app
        from app.prompt import build_llm_messages
        from fastapi.testclient import TestClient

        catalog_path = self.root / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["papers"].append(
            {
                "id": "paper-imported",
                "title": "Imported paper",
                "original_filename": "source.pdf",
                "status": "pending",
                "tag_ids": [],
                "focus": "",
                "summary": "",
                "paths": {"pdf": "papers/unprocessed/pdf/paper-imported.pdf"},
            }
        )
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        session = self.storage.create_session(self.project.slug)

        response = TestClient(app).post(
            f"/api/work/projects/{self.project.slug}/literature/sessions/{session.id}/imports",
            json={"paper_ids": ["paper-imported"]},
        )

        self.assertEqual(response.status_code, 200)
        stored = self.storage.read_messages(session.id, limit=0)
        self.assertEqual(stored[-1]["role"], "system")
        self.assertEqual(stored[-1]["meta"]["event"], "literature_import_confirmed")
        messages, _usage = build_llm_messages(self.project, session.id)
        injected = [item["content"] for item in messages if item["role"] == "system"]
        self.assertTrue(any("<LITERATURE_IMPORT_EVENT>" in item for item in injected))
        self.assertTrue(any("source.pdf" in item for item in injected))

    def test_generic_markdown_editor_cannot_mutate_managed_literature_files(self) -> None:
        from app import files

        with self.assertRaises(self.storage.ValidationError):
            files.write_markdown_file(self.project.slug, "LITERATURE_PROJECT.md", "changed", None)

        note = self.root / "notes" / "discussion.md"
        note.write_text("# Discussion\n", encoding="utf-8")
        written = files.write_markdown_file(self.project.slug, "notes/discussion.md", "# Updated\n", None)
        self.assertEqual(written["content"].splitlines(), ["# Updated"])

    def test_process_tool_uses_project_pipeline_and_updates_catalog(self) -> None:
        from app.literature_project import execute_literature_tool, register_staged_pdf

        staged = self.root / "papers" / "unprocessed" / "pdf" / ".incoming-test.pdf"
        staged.write_bytes(b"%PDF-1.7\nfixture")
        imported = register_staged_pdf(self.root, staged, original_filename="source.pdf")
        paper_id = imported["paper"]["id"]
        output = self.root / "papers" / "unprocessed" / "extracted" / paper_id
        output.mkdir(parents=True)
        (output / "full.md").write_text("# Full paper\n", encoding="utf-8")

        metadata = {
            "title": "A real title",
            "authors": "Zhang, A.; Li, B.",
            "first_author_surname": "Zhang",
            "year": 2024,
            "journal": "Journal of Tests",
            "journal_abbreviation": "JTest",
            "doi": "10.1000/test",
            "paper_type": "research",
            "metadata_source": "cite_this",
        }
        report = "\n".join(
            [
                "## 1. Basic information",
                "## 2. Instruments and samples",
                "## 3. Phenomena and data",
                "## 4. Authors' claims",
                "## 5. Evidence summary",
                "## 6. Cross-literature relations",
                "⟨待主对话讨论后增补⟩",
            ]
        )
        with (
            patch("app.literature_pipeline._run_mineru", return_value=output),
            patch("app.literature_pipeline._extract_metadata", return_value=metadata),
            patch("app.literature_pipeline._extract_facts", return_value=report),
        ):
            result = execute_literature_tool(self.project.slug, "literature_process", {"paper_id": paper_id})

        self.assertTrue(result.ok, result.content)
        paper = json.loads((self.root / "catalog.json").read_text(encoding="utf-8"))["papers"][0]
        self.assertEqual(paper["status"], "review")
        self.assertEqual(paper["archive_filename"], "Zhang_2024_JTest.pdf")
        self.assertTrue((self.root / paper["paths"]["fact_report"]).exists())

    def test_pipeline_relative_path_canonicalizes_windows_path_aliases(self) -> None:
        from app.literature_pipeline import _project_relative

        alias_root = Path("RUNNER~1") / "temp" / "library"
        alias_output = alias_root / "papers" / "unprocessed" / "extracted" / "paper-1"
        canonical_root = Path("runneradmin") / "temp" / "library"
        canonical_output = canonical_root / "papers" / "unprocessed" / "extracted" / "paper-1"
        aliases = {
            os.fspath(alias_root): os.fspath(canonical_root),
            os.fspath(alias_output): os.fspath(canonical_output),
        }

        with patch(
            "app.literature_pipeline.os.path.realpath",
            side_effect=lambda value: aliases.get(os.fspath(value), os.fspath(value)),
        ):
            self.assertEqual(
                _project_relative(alias_output, alias_root),
                "papers/unprocessed/extracted/paper-1",
            )

    def test_full_text_read_falls_back_to_the_pdf_text_layer_without_mineru(self) -> None:
        from app.literature_project import execute_literature_tool

        pdf = self.root / "papers" / "unprocessed" / "pdf" / "fallback.pdf"
        pdf.write_bytes(b"%PDF-1.7\nfixture")
        empty_full_md = self.root / "papers" / "unprocessed" / "extracted" / "paper-fallback" / "full.md"
        empty_full_md.parent.mkdir(parents=True)
        empty_full_md.write_text("", encoding="utf-8")
        catalog_path = self.root / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["papers"].append(
            {
                "id": "paper-fallback",
                "title": "Fallback paper",
                "original_filename": "fallback.pdf",
                "status": "pending",
                "tag_ids": [],
                "focus": "",
                "summary": "",
                "paths": {
                    "pdf": "papers/unprocessed/pdf/fallback.pdf",
                    "full_md": "papers/unprocessed/extracted/paper-fallback/full.md",
                },
            }
        )
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        extraction = SimpleNamespace(
            text="# Page 1\n\nDirect PDF text.\n\n# Page 2\n\nMore evidence.",
            page_count=2,
            pages_with_text=2,
            truncated=False,
            warnings=[],
        )
        with patch("app.literature_project.extract_pdf_text", return_value=extraction) as extractor:
            result = execute_literature_tool(
                self.project.slug,
                "literature_read",
                {"paper_id": "paper-fallback", "part": "full_text", "offset": 0, "limit": 20},
            )

        self.assertTrue(result.ok, result.content)
        payload = json.loads(result.content)
        self.assertEqual(payload["source"], "pdf_text_layer")
        self.assertEqual(payload["page_count"], 2)
        self.assertIn("Direct PDF text", payload["content"])
        self.assertIn("MinerU", payload["warning"])
        extractor.assert_called_once_with(pdf.resolve(), cancel_event=None)

    def test_archive_preflights_every_destination_before_moving_pdf(self) -> None:
        from app.literature_project import execute_literature_tool, register_staged_pdf

        staged = self.root / "papers" / "unprocessed" / "pdf" / ".incoming-archive.pdf"
        staged.write_bytes(b"%PDF-1.7\nfixture")
        imported = register_staged_pdf(self.root, staged, original_filename="archive-source.pdf")
        paper_id = imported["paper"]["id"]
        extraction = self.root / "papers" / "unprocessed" / "extracted" / paper_id
        extraction.mkdir(parents=True)
        (extraction / "full.md").write_text("# Full paper\n", encoding="utf-8")
        (extraction / "objective-facts.md").write_text(
            "## 6. Cross-literature relations\n\nDiscussion complete.\n",
            encoding="utf-8",
        )
        catalog_path = self.root / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        paper = catalog["papers"][0]
        paper.update(
            {
                "title": "Archive test",
                "authors": "Zhang, A.",
                "first_author_surname": "Zhang",
                "year": 2024,
                "journal_abbreviation": "JTest",
                "archive_filename": "Zhang_2024_JTest.pdf",
                "paths": {
                    "pdf": paper["paths"]["pdf"],
                    "mineru_dir": extraction.relative_to(self.root).as_posix(),
                    "full_md": (extraction / "full.md").relative_to(self.root).as_posix(),
                    "fact_report": (extraction / "objective-facts.md").relative_to(self.root).as_posix(),
                },
            }
        )
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        source_pdf = self.root / paper["paths"]["pdf"]
        collision = self.root / "papers" / "processed" / "extracted" / paper_id
        collision.mkdir(parents=True)

        result = execute_literature_tool(self.project.slug, "literature_archive", {"paper_id": paper_id})

        self.assertFalse(result.ok)
        self.assertIn("Archive extraction target already exists", result.content)
        self.assertTrue(source_pdf.exists())
        self.assertFalse((self.root / "papers" / "processed" / "pdf" / "Zhang_2024_JTest.pdf").exists())


if __name__ == "__main__":
    unittest.main()
