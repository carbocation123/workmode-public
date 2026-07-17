from __future__ import annotations

import json
import os
import tempfile
import threading
import time
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
            "literature_delete",
            "literature_restore",
            "literature_note_search",
            "literature_note_read",
            "literature_note_upsert",
            "literature_note_delete",
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
        self.assertIn("除非用户明确要求展开", prompt)
        self.assertIn("实验现象", prompt)
        self.assertIn("研究手段", prompt)
        self.assertIn("关键证据", prompt)
        self.assertIn("说明什么问题", prompt)
        self.assertIn('literature_read(part="full_text")', prompt)
        self.assertIn("不得仅因为文献刚刚入库或被选中就调用 literature_process", prompt)
        self.assertIn("精读某一篇", prompt)
        self.assertIn("默认逐图讲解", prompt)
        self.assertIn("图注或图像信息不足", prompt)
        self.assertIn("不得猜测", prompt)
        self.assertNotIn("project_bash", prompt)
        self.assertEqual(usage["tool_profile"], "literature")
        self.assertEqual(usage["tool_count"], 15)

        schemas = {
            item["function"]["name"]: item["function"]
            for item in self._project_tool_schemas()
        }
        self.assertIn("paper_ids", schemas["literature_read"]["parameters"]["properties"])

    def _project_tool_schemas(self) -> list[dict[str, object]]:
        from app.project_tools import project_tool_schemas

        return project_tool_schemas(self.project.slug)

    def test_new_literature_session_starts_with_default_assistant_introduction(self) -> None:
        from app.main import app
        from fastapi.testclient import TestClient

        response = TestClient(app).post(
            f"/api/work/projects/{self.project.slug}/sessions",
            json={"title": "阅读讨论"},
        )

        self.assertEqual(response.status_code, 200)
        session_id = response.json()["session"]["id"]
        messages = self.storage.read_messages(session_id, limit=0)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "assistant")
        self.assertIn("我可以帮你简洁概括", messages[0]["content"])
        self.assertIn("项目笔记", messages[0]["content"])
        self.assertIn("MinerU API", messages[0]["content"])
        self.assertIn("精读这篇", messages[0]["content"])
        self.assertIn("默认逐图讲解", messages[0]["content"])
        self.assertIn("现在，我能帮你什么", messages[0]["content"])

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
        message = next(
            item for item in self.storage.read_messages(session.id, limit=0)
            if item["role"] == "user"
        )
        self.assertEqual(message["meta"]["active_context"], [{"kind": "paper", "id": "paper-1"}])

    def test_confirmed_import_is_a_short_persistent_system_context_event(self) -> None:
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
        self.assertEqual(stored[-1]["content"], "用户刚刚导入了以下文献：\n- source.pdf")
        messages, _usage = build_llm_messages(self.project, session.id)
        injected = [item["content"] for item in messages if item["role"] == "system"]
        self.assertTrue(any("用户刚刚导入了以下文献" in item for item in injected))
        self.assertTrue(any("source.pdf" in item for item in injected))
        self.assertFalse(any("call literature_process" in item for item in injected))
        self.assertFalse(any("When the user says to continue" in item for item in injected))

    def test_selected_papers_are_persisted_as_system_events_before_user_messages(self) -> None:
        from app.main import app
        from fastapi.testclient import TestClient

        catalog_path = self.root / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["papers"].append(
            {
                "id": "paper-selected",
                "title": "Selected paper",
                "original_filename": "selected.pdf",
                "status": "pending",
                "tag_ids": [],
                "focus": "",
                "summary": "",
                "paths": {"pdf": "papers/unprocessed/pdf/selected.pdf"},
            }
        )
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        session = self.storage.create_session(self.project.slug)

        async def no_model_events(*_args, **_kwargs):
            if False:
                yield {}

        client = TestClient(app)
        with patch("app.routes.stream_openai_compatible", no_model_events):
            first = client.post(
                f"/api/work/sessions/{session.id}/chat/stream",
                json={
                    "content": "介绍一下",
                    "active_context": [{"kind": "paper", "id": "paper-selected"}],
                },
            )
            second = client.post(
                f"/api/work/sessions/{session.id}/chat/stream",
                json={
                    "content": "再说一句",
                    "active_context": [{"kind": "paper", "id": "paper-selected"}],
                },
            )
            cleared = client.post(
                f"/api/work/sessions/{session.id}/chat/stream",
                json={"content": "不看它了", "active_context": []},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(cleared.status_code, 200)
        stored = self.storage.read_messages(session.id, limit=0)
        selection_events = [
            item for item in stored
            if item["role"] == "system" and item["meta"].get("event") == "literature_selection_changed"
        ]
        self.assertEqual(len(selection_events), 2)
        self.assertEqual(
            selection_events[0]["content"],
            "用户当前选择了以下文献：\n- selected.pdf",
        )
        self.assertEqual(selection_events[0]["meta"]["paper_ids"], ["paper-selected"])
        self.assertEqual(selection_events[1]["content"], "用户已取消当前文献选择。")
        first_event_index = stored.index(selection_events[0])
        self.assertEqual(stored[first_event_index + 1]["role"], "user")

    def test_literature_read_accepts_multiple_paper_ids_in_one_call(self) -> None:
        from app.literature_project import execute_literature_tool

        catalog_path = self.root / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        for index in range(2):
            catalog["papers"].append(
                {
                    "id": f"paper-batch-{index}",
                    "title": f"Batch paper {index}",
                    "original_filename": f"batch-{index}.pdf",
                    "status": "pending",
                    "tag_ids": [],
                    "focus": "",
                    "summary": "",
                    "paths": {},
                }
            )
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = execute_literature_tool(
            self.project.slug,
            "literature_read",
            {"paper_ids": ["paper-batch-0", "paper-batch-1"], "part": "record"},
        )

        self.assertTrue(result.ok, result.content)
        payload = json.loads(result.content)
        self.assertEqual(payload["operation"], "literature_read")
        self.assertEqual(payload["paper_ids"], ["paper-batch-0", "paper-batch-1"])
        self.assertEqual(payload["succeeded_count"], 2)
        self.assertEqual([item["paper_id"] for item in payload["results"]], ["paper-batch-0", "paper-batch-1"])

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

    def test_process_keeps_fact_report_when_metadata_needs_review(self) -> None:
        from app.literature_pipeline import LiteraturePipelineError
        from app.literature_project import execute_literature_tool, register_staged_pdf

        staged = self.root / "papers" / "unprocessed" / "pdf" / ".incoming-partial.pdf"
        staged.write_bytes(b"%PDF-1.7\npartial metadata fixture")
        imported = register_staged_pdf(self.root, staged, original_filename="partial.pdf")
        paper_id = imported["paper"]["id"]
        output = self.root / "papers" / "unprocessed" / "extracted" / paper_id
        output.mkdir(parents=True)
        (output / "full.md").write_text("# Full paper\n", encoding="utf-8")
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
            patch(
                "app.literature_pipeline._extract_metadata",
                side_effect=LiteraturePipelineError("模型返回的元数据 JSON 无法解析"),
            ),
            patch("app.literature_pipeline._extract_facts", return_value=report),
        ):
            result = execute_literature_tool(self.project.slug, "literature_process", {"paper_id": paper_id})

        self.assertTrue(result.ok, result.content)
        payload = json.loads(result.content)
        self.assertTrue(payload["metadata_needs_review"])
        paper = json.loads((self.root / "catalog.json").read_text(encoding="utf-8"))["papers"][0]
        self.assertEqual(paper["status"], "review")
        self.assertEqual(paper["metadata_trust"], "partial")
        self.assertIn("JSON", paper["metadata_issue"])
        self.assertTrue((self.root / paper["paths"]["fact_report"]).exists())

    def test_process_batch_runs_at_most_three_papers_concurrently(self) -> None:
        from app.literature_project import execute_literature_tool, register_staged_pdf

        paper_ids: list[str] = []
        for index in range(5):
            staged = self.root / "papers" / "unprocessed" / "pdf" / f".incoming-batch-{index}.pdf"
            staged.write_bytes(f"%PDF-1.7\nbatch fixture {index}".encode())
            imported = register_staged_pdf(self.root, staged, original_filename=f"batch-{index}.pdf")
            paper_ids.append(imported["paper"]["id"])

        guard = threading.Lock()
        active = 0
        peak = 0

        def fake_pipeline(_root: Path, paper_id: str, *, cancel_event: threading.Event | None):
            nonlocal active, peak
            with guard:
                active += 1
                peak = max(peak, active)
            time.sleep(0.04)
            with guard:
                active -= 1
            return {"status": "review", "stage": "done", "changed_files": [f"out/{paper_id}.md"]}

        with patch("app.literature_pipeline.run_literature_pipeline", side_effect=fake_pipeline):
            result = execute_literature_tool(
                self.project.slug,
                "literature_process",
                {"paper_ids": paper_ids},
            )

        self.assertTrue(result.ok, result.content)
        payload = json.loads(result.content)
        self.assertEqual(payload["succeeded_count"], 5)
        self.assertEqual(payload["failed_count"], 0)
        self.assertEqual(len(payload["results"]), 5)
        self.assertEqual(peak, 3)

    def test_manual_metadata_completion_finishes_standard_naming(self) -> None:
        from app.literature_project import execute_literature_tool, register_staged_pdf

        staged = self.root / "papers" / "unprocessed" / "pdf" / ".incoming-manual.pdf"
        staged.write_bytes(b"%PDF-1.7\nmanual metadata fixture")
        imported = register_staged_pdf(self.root, staged, original_filename="manual.pdf")
        paper_id = imported["paper"]["id"]

        result = execute_literature_tool(
            self.project.slug,
            "literature_update_record",
            {
                "paper_id": paper_id,
                "title": "Manually verified title",
                "authors": "Zhang, A.; Li, B.",
                "first_author_surname": "Zhang",
                "year": 2025,
                "journal": "Journal of Manual Checks",
                "journal_abbreviation": "JMC",
                "doi": "10.1000/manual",
                "paper_type": "research",
                "metadata_source": "manual",
            },
        )

        self.assertTrue(result.ok, result.content)
        paper = json.loads((self.root / "catalog.json").read_text(encoding="utf-8"))["papers"][0]
        self.assertEqual(paper["metadata_trust"], "complete")
        self.assertEqual(paper["archive_filename"], "Zhang_2025_JMC.pdf")
        self.assertEqual(paper["metadata_issue"], "")
        self.assertTrue((self.root / "papers/unprocessed/pdf/Zhang_2025_JMC.pdf").exists())

    def test_manual_metadata_normalizes_human_journal_abbreviation(self) -> None:
        from app.literature_project import execute_literature_tool, register_staged_pdf

        staged = self.root / "papers" / "unprocessed" / "pdf" / ".incoming-normalized.pdf"
        staged.write_bytes(b"%PDF-1.7\nnormalized journal fixture")
        imported = register_staged_pdf(self.root, staged, original_filename="normalized.pdf")
        paper_id = imported["paper"]["id"]

        result = execute_literature_tool(
            self.project.slug,
            "literature_update_record",
            {
                "paper_id": paper_id,
                "title": "Normalized journal title",
                "authors": "Wang, A.; Li, B.",
                "first_author_surname": "Wang",
                "year": 2026,
                "journal": "Angewandte Chemie International Edition",
                "journal_abbreviation": "Angew. Chem. Int. Ed.",
                "doi": "10.1000/normalized",
                "paper_type": "research",
                "metadata_source": "manual",
            },
        )

        self.assertTrue(result.ok, result.content)
        paper = json.loads((self.root / "catalog.json").read_text(encoding="utf-8"))["papers"][0]
        self.assertEqual(paper["journal_abbreviation"], "AngewChemIntEd")
        self.assertEqual(paper["archive_filename"], "Wang_2026_AngewChemIntEd.pdf")
        self.assertTrue((self.root / "papers/unprocessed/pdf/Wang_2026_AngewChemIntEd.pdf").exists())

    def test_partial_record_accepts_spaced_journal_abbreviation_without_retry(self) -> None:
        from app.literature_project import execute_literature_tool, register_staged_pdf

        staged = self.root / "papers" / "unprocessed" / "pdf" / ".incoming-partial-abbreviation.pdf"
        staged.write_bytes(b"%PDF-1.7\npartial journal fixture")
        imported = register_staged_pdf(self.root, staged, original_filename="partial.pdf")
        paper_id = imported["paper"]["id"]

        result = execute_literature_tool(
            self.project.slug,
            "literature_update_record",
            {"paper_id": paper_id, "journal_abbreviation": "J Mol Catal A Chem"},
        )

        self.assertTrue(result.ok, result.content)
        paper = json.loads((self.root / "catalog.json").read_text(encoding="utf-8"))["papers"][0]
        self.assertEqual(paper["journal_abbreviation"], "JMolCatalAChem")
        self.assertEqual(paper["metadata_trust"], "partial")

    def test_invalid_journal_abbreviation_fails_before_catalog_write(self) -> None:
        from app.literature_project import execute_literature_tool, register_staged_pdf

        staged = self.root / "papers" / "unprocessed" / "pdf" / ".incoming-invalid-abbreviation.pdf"
        staged.write_bytes(b"%PDF-1.7\ninvalid journal fixture")
        imported = register_staged_pdf(self.root, staged, original_filename="invalid.pdf")
        paper_id = imported["paper"]["id"]

        result = execute_literature_tool(
            self.project.slug,
            "literature_update_record",
            {"paper_id": paper_id, "journal_abbreviation": "... / ..."},
        )

        self.assertFalse(result.ok)
        paper = json.loads((self.root / "catalog.json").read_text(encoding="utf-8"))["papers"][0]
        self.assertEqual(paper["journal_abbreviation"], "")

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

    def test_paper_delete_and_restore_move_the_record_and_materials_as_one_unit(self) -> None:
        from app.literature_project import execute_literature_tool, list_deleted_literature_papers, register_staged_pdf

        staged = self.root / "papers" / "unprocessed" / "pdf" / ".incoming-delete.pdf"
        staged.write_bytes(b"%PDF-1.7\nrecoverable fixture")
        imported = register_staged_pdf(self.root, staged, original_filename="recoverable.pdf")
        paper_id = imported["paper"]["id"]
        extraction = self.root / "papers" / "unprocessed" / "extracted" / paper_id
        extraction.mkdir(parents=True)
        (extraction / "full.md").write_text("# Full text\n", encoding="utf-8")
        (extraction / "objective-facts.md").write_text("# Facts\n", encoding="utf-8")
        (extraction / "images").mkdir()
        (extraction / "images" / "figure.png").write_bytes(b"image")
        catalog_path = self.root / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        paper = catalog["papers"][0]
        original_pdf_rel = paper["paths"]["pdf"]
        paper["paths"].update(
            {
                "mineru_dir": extraction.relative_to(self.root).as_posix(),
                "full_md": (extraction / "full.md").relative_to(self.root).as_posix(),
                "fact_report": (extraction / "objective-facts.md").relative_to(self.root).as_posix(),
            }
        )
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        deleted = execute_literature_tool(self.project.slug, "literature_delete", {"paper_id": paper_id})

        self.assertTrue(deleted.ok, deleted.content)
        delete_payload = json.loads(deleted.content)
        self.assertEqual(delete_payload["operation"], "literature_delete")
        self.assertEqual(json.loads(catalog_path.read_text(encoding="utf-8"))["papers"], [])
        self.assertFalse((self.root / original_pdf_rel).exists())
        self.assertFalse(extraction.exists())
        deleted_entries = list_deleted_literature_papers(self.root)
        self.assertEqual(len(deleted_entries), 1)
        self.assertEqual(deleted_entries[0]["trash_id"], delete_payload["trash_id"])
        self.assertEqual(deleted_entries[0]["paper"]["id"], paper_id)
        manifest_path = self.root / delete_payload["trash_path"] / "manifest.json"
        self.assertTrue(manifest_path.exists())
        self.assertTrue((manifest_path.parent / "files" / original_pdf_rel).exists())
        self.assertTrue((manifest_path.parent / "files" / extraction.relative_to(self.root) / "images" / "figure.png").exists())

        restored = execute_literature_tool(
            self.project.slug,
            "literature_restore",
            {"trash_id": delete_payload["trash_id"]},
        )

        self.assertTrue(restored.ok, restored.content)
        restored_payload = json.loads(restored.content)
        self.assertEqual(restored_payload["operation"], "literature_restore")
        self.assertEqual(restored_payload["paper"]["id"], paper_id)
        self.assertTrue((self.root / original_pdf_rel).exists())
        self.assertTrue((extraction / "full.md").exists())
        self.assertEqual(len(json.loads(catalog_path.read_text(encoding="utf-8"))["papers"]), 1)
        self.assertEqual(list_deleted_literature_papers(self.root), [])

    def test_paper_delete_projection_routes_expose_recovery_without_rewriting_history(self) -> None:
        from app.main import app
        from app.literature_project import register_staged_pdf
        from fastapi.testclient import TestClient

        staged = self.root / "papers" / "unprocessed" / "pdf" / ".incoming-route-delete.pdf"
        staged.write_bytes(b"%PDF-1.7\nroute fixture")
        imported = register_staged_pdf(self.root, staged, original_filename="route-delete.pdf")
        paper_id = imported["paper"]["id"]
        client = TestClient(app)

        deleted = client.delete(f"/api/work/projects/{self.project.slug}/literature/papers/{paper_id}")
        self.assertEqual(deleted.status_code, 200, deleted.text)
        trash_id = deleted.json()["result"]["trash_id"]
        listed = client.get(f"/api/work/projects/{self.project.slug}/literature/trash/papers")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual([item["trash_id"] for item in listed.json()["papers"]], [trash_id])

        restored = client.post(
            f"/api/work/projects/{self.project.slug}/literature/trash/papers/{trash_id}/restore"
        )
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(restored.json()["paper"]["id"], paper_id)

    def test_paper_restore_never_overwrites_a_new_file_at_the_original_path(self) -> None:
        from app.literature_project import execute_literature_tool, register_staged_pdf

        staged = self.root / "papers" / "unprocessed" / "pdf" / ".incoming-restore-collision.pdf"
        staged.write_bytes(b"%PDF-1.7\noriginal")
        imported = register_staged_pdf(self.root, staged, original_filename="collision.pdf")
        paper_id = imported["paper"]["id"]
        pdf_path = self.root / imported["paper"]["paths"]["pdf"]
        deleted = execute_literature_tool(self.project.slug, "literature_delete", {"paper_id": paper_id})
        self.assertTrue(deleted.ok, deleted.content)
        trash_id = json.loads(deleted.content)["trash_id"]
        pdf_path.write_bytes(b"%PDF-1.7\nnew file")

        restored = execute_literature_tool(self.project.slug, "literature_restore", {"trash_id": trash_id})

        self.assertFalse(restored.ok)
        self.assertIn("Restore target already exists", restored.content)
        self.assertEqual(pdf_path.read_bytes(), b"%PDF-1.7\nnew file")
        self.assertEqual(json.loads((self.root / "catalog.json").read_text(encoding="utf-8"))["papers"], [])
        self.assertTrue((self.root / "papers" / ".trash" / trash_id / "manifest.json").exists())

    def test_note_delete_moves_note_to_recoverable_project_trash(self) -> None:
        from app.literature_project import execute_literature_tool

        created = execute_literature_tool(
            self.project.slug,
            "literature_note_upsert",
            {"filename": "discussion.md", "markdown": "# Discussion\n\nKeep evidence.\n"},
        )
        deleted = execute_literature_tool(
            self.project.slug,
            "literature_note_delete",
            {"filename": "discussion.md"},
        )

        self.assertTrue(created.ok, created.content)
        self.assertTrue(deleted.ok, deleted.content)
        payload = json.loads(deleted.content)
        self.assertEqual(payload["operation"], "literature_note_delete")
        self.assertFalse((self.root / "notes" / "discussion.md").exists())
        trash_path = self.root / payload["trash_path"]
        self.assertTrue(trash_path.exists())
        self.assertIn("Keep evidence", trash_path.read_text(encoding="utf-8"))

    def test_note_delete_projection_route_uses_the_same_recoverable_delete(self) -> None:
        from app.main import app
        from app.literature_project import execute_literature_tool
        from fastapi.testclient import TestClient

        execute_literature_tool(
            self.project.slug,
            "literature_note_upsert",
            {"filename": "route-note.md", "markdown": "# Route note\n"},
        )

        response = TestClient(app).delete(
            f"/api/work/projects/{self.project.slug}/literature/notes/route-note.md",
        )

        self.assertEqual(response.status_code, 200, response.text)
        trash_path = self.root / response.json()["result"]["trash_path"]
        self.assertFalse((self.root / "notes" / "route-note.md").exists())
        self.assertTrue(trash_path.exists())


class ManagedLiteratureProjectApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("WORKMODE_PUBLIC_DATA_DIR")
        self.old_managed_dir = os.environ.get("WORKMODE_MANAGED_PROJECTS_DIR")
        self.data_dir = Path(self.tmp.name) / "app-data"
        self.managed_dir = Path(self.tmp.name) / "managed"
        os.environ["WORKMODE_PUBLIC_DATA_DIR"] = str(self.data_dir)
        os.environ["WORKMODE_MANAGED_PROJECTS_DIR"] = str(self.managed_dir)

        from app import config, storage
        from app.main import app
        from fastapi.testclient import TestClient

        storage.settings = config.reload_settings()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self.old_data_dir is None:
            os.environ.pop("WORKMODE_PUBLIC_DATA_DIR", None)
        else:
            os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.old_data_dir
        if self.old_managed_dir is None:
            os.environ.pop("WORKMODE_MANAGED_PROJECTS_DIR", None)
        else:
            os.environ["WORKMODE_MANAGED_PROJECTS_DIR"] = self.old_managed_dir
        from app import config, storage

        storage.settings = config.reload_settings()
        self.tmp.cleanup()

    def test_name_only_creation_allocates_unique_managed_project_directories(self) -> None:
        first = self.client.post("/api/work/literature-projects", json={"name": "EPR 文献库"})
        second = self.client.post("/api/work/literature-projects", json={"name": "EPR 文献库"})

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        first_root = Path(first.json()["project"]["root_path"])
        second_root = Path(second.json()["project"]["root_path"])
        self.assertEqual(first_root.parent, self.managed_dir.resolve())
        self.assertEqual(second_root.parent, self.managed_dir.resolve())
        self.assertNotEqual(first_root, second_root)
        self.assertTrue((first_root / "literature-project.json").exists())
        self.assertEqual(first.json()["project"]["storage_mode"], "managed")

    def test_legacy_explicit_root_stays_in_place_and_missing_structure_is_repaired(self) -> None:
        legacy_root = Path(self.tmp.name) / "legacy-library"
        created = self.client.post(
            "/api/work/literature-projects",
            json={"name": "旧版文献库", "root_path": str(legacy_root)},
        )
        self.assertEqual(created.status_code, 200, created.text)
        slug = created.json()["project"]["slug"]
        (legacy_root / "exports").rmdir()

        health = self.client.get(f"/api/work/projects/{slug}/literature/health")

        self.assertEqual(health.status_code, 200, health.text)
        self.assertEqual(Path(created.json()["project"]["root_path"]), legacy_root.resolve())
        self.assertEqual(created.json()["project"]["storage_mode"], "external")
        self.assertTrue((legacy_root / "exports").is_dir())


if __name__ == "__main__":
    unittest.main()
