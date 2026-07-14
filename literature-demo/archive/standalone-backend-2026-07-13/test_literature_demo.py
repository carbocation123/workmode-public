from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


class LiteratureDemoStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        from app.literature_demo_store import LiteratureDemoStore

        self.store = LiteratureDemoStore(Path(self.tmp.name))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_import_is_content_deduplicated_and_keeps_original_name(self) -> None:
        first, duplicate = self.store.import_pdf_bytes("raw paper.pdf", PDF_BYTES)
        same, was_duplicate = self.store.import_pdf_bytes("renamed.pdf", PDF_BYTES)

        self.assertFalse(duplicate)
        self.assertTrue(was_duplicate)
        self.assertEqual(first["id"], same["id"])
        self.assertEqual(first["original_filename"], "raw paper.pdf")
        self.assertEqual(first["status"], "pending")
        self.assertTrue(self.store.pdf_path(first["id"]).is_file())

    def test_standard_names_use_case_insensitive_collision_suffixes(self) -> None:
        first, _ = self.store.import_pdf_bytes("one.pdf", PDF_BYTES)
        second, _ = self.store.import_pdf_bytes("two.pdf", PDF_BYTES + b"% second")

        first = self.store.apply_metadata(
            first["id"],
            {
                "title": "First paper",
                "first_author_surname": "Ren",
                "year": 2026,
                "journal_abbreviation": "JACS",
                "metadata_source": "cite_this",
            },
        )
        second = self.store.apply_metadata(
            second["id"],
            {
                "title": "Second paper",
                "first_author_surname": "ren",
                "year": 2026,
                "journal_abbreviation": "JACS",
                "metadata_source": "cite_this",
            },
        )

        self.assertEqual(first["archive_filename"], "Ren_2026_JACS.pdf")
        self.assertEqual(second["archive_filename"], "ren_2026_JACS_2.pdf")
        self.assertTrue(self.store.pdf_path(second["id"]).name.endswith("_2.pdf"))

    def test_sessions_are_isolated_but_notes_and_memory_are_project_shared(self) -> None:
        one = self.store.create_session("Session A")
        two = self.store.create_session("Session B")
        paper, _ = self.store.import_pdf_bytes("context.pdf", PDF_BYTES)
        self.store.append_message(one["id"], {"role": "user", "content": "A only"})
        self.store.upsert_note("evidence.md", "# Evidence", confirmed=True)
        self.store.write_memory("Keep facts separate.", confirmed=True)
        self.store.update_session_context(
            one["id"],
            paper_ids=[paper["id"], "missing"],
            note_ids=["evidence.md", "missing.md"],
        )

        self.assertEqual(len(self.store.get_session(one["id"])["messages"]), 1)
        self.assertEqual(self.store.get_session(two["id"])["messages"], [])
        self.assertEqual(len(self.store.list_notes()), 1)
        self.assertIn("Keep facts separate.", self.store.read_memory())
        self.assertEqual(self.store.get_session(one["id"])["attached_paper_ids"], [paper["id"]])
        self.assertEqual(self.store.get_session(one["id"])["attached_note_ids"], ["evidence.md"])

        with self.assertRaises(PermissionError):
            self.store.upsert_note("silent.md", "forbidden", confirmed=False)

    def test_interrupted_tasks_are_resumable_and_cancel_requests_stay_cancelled(self) -> None:
        paper, _ = self.store.import_pdf_bytes("paper.pdf", PDF_BYTES)
        running = self.store.create_task(paper["id"])
        self.store.update_task(running["id"], status="running", stage="MinerU")

        resumed = self.store.recover_interrupted_tasks()
        self.assertEqual([item["id"] for item in resumed], [running["id"]])
        self.assertEqual(self.store.get_task(running["id"])["status"], "queued")

        self.store.request_cancel(running["id"])
        self.assertEqual(self.store.recover_interrupted_tasks(), [])
        self.assertEqual(self.store.get_task(running["id"])["status"], "cancelled")

    def test_real_chat_persists_messages_and_read_tools_cannot_write_notes(self) -> None:
        from app.literature_demo_chat import execute_read_tool, run_literature_chat

        paper, _ = self.store.import_pdf_bytes("paper.pdf", PDF_BYTES)
        session = self.store.create_session("Discussion")
        self.store.upsert_note("evidence.md", "# Evidence\nEPR control", confirmed=True)

        searched = execute_read_tool(self.store, "notes_search", {"query": "EPR"})
        self.assertIn("evidence.md", searched)
        self.assertIn("未知文献工具", execute_read_tool(self.store, "notes_write", {}))

        with patch(
            "app.literature_demo_chat._request_model",
            return_value={"role": "assistant", "content": "根据所选材料，目前正文尚未生成。"},
        ):
            result = run_literature_chat(
                self.store,
                session["id"],
                "先说我们能确认什么",
                [paper["id"]],
                [],
            )

        self.assertEqual([item["role"] for item in result["session"]["messages"]], ["user", "assistant"])
        self.assertIn("正文尚未生成", result["message"]["content"])

    def test_ai_pipeline_tool_only_processes_selected_papers_and_returns_task(self) -> None:
        from app.literature_demo_chat import LITERATURE_TOOLS, execute_literature_tool

        selected, _ = self.store.import_pdf_bytes("selected.pdf", PDF_BYTES)
        other, _ = self.store.import_pdf_bytes("other.pdf", PDF_BYTES + b"% other")
        started: list[str] = []

        denied = execute_literature_tool(
            self.store,
            "literature_process",
            {"paper_id": other["id"]},
            selected_paper_ids=[selected["id"]],
            pipeline_starter=lambda _store, task_id: started.append(task_id),
        )
        self.assertIn("未选中", denied)
        self.assertEqual(started, [])

        accepted = execute_literature_tool(
            self.store,
            "literature_process",
            {"paper_id": selected["id"]},
            selected_paper_ids=[selected["id"]],
            pipeline_starter=lambda _store, task_id: started.append(task_id),
        )
        payload = __import__("json").loads(accepted)
        self.assertEqual(payload["paper_id"], selected["id"])
        self.assertEqual(payload["status"], "queued")
        self.assertEqual(started, [payload["task_id"]])
        self.assertIn(
            "literature_process",
            {item["function"]["name"] for item in LITERATURE_TOOLS},
        )

    def test_real_chat_returns_pipeline_tasks_started_by_the_model(self) -> None:
        from app.literature_demo_chat import run_literature_chat

        paper, _ = self.store.import_pdf_bytes("retry.pdf", PDF_BYTES)
        session = self.store.create_session("Process discussion")
        tool_call = {
            "id": "call-process",
            "type": "function",
            "function": {
                "name": "literature_process",
                "arguments": __import__("json").dumps({"paper_id": paper["id"]}),
            },
        }
        with (
            patch(
                "app.literature_demo_chat._request_model",
                side_effect=[
                    {"role": "assistant", "content": None, "tool_calls": [tool_call]},
                    {"role": "assistant", "content": "已启动这篇文献的 MinerU 流水线。"},
                ],
            ),
            patch("app.literature_demo_chat.run_literature_pipeline"),
        ):
            result = run_literature_chat(
                self.store,
                session["id"],
                "请重新跑这篇文献的 MinerU",
                [paper["id"]],
                [],
            )

        self.assertEqual(len(result["started_tasks"]), 1)
        self.assertEqual(result["started_tasks"][0]["paper_id"], paper["id"])
        self.assertIn("已启动", result["message"]["content"])
        tool_events = [
            item for item in result["session"]["messages"] if item["role"] == "tool"
        ]
        self.assertEqual(len(tool_events), 1)
        self.assertEqual(tool_events[0]["tool_name"], "literature_process")
        self.assertEqual(tool_events[0]["tool_args"]["paper_id"], paper["id"])
        self.assertEqual(tool_events[0]["tool_status"], "completed")
        self.assertIn("task_id", tool_events[0]["content"])

    def test_ai_write_proposal_requires_confirm_tool_call_not_text_regex(self) -> None:
        from app.literature_demo_chat import execute_literature_tool

        paper, _ = self.store.import_pdf_bytes("note-source.pdf", PDF_BYTES)
        session = self.store.create_session("Writing")
        proposed = json.loads(
            execute_literature_tool(
                self.store,
                "notes_upsert_propose",
                {
                    "filename": "证据整理.md",
                    "markdown": "# 证据整理\n\n- 等待确认的内容。",
                    "source_paper_ids": [paper["id"]],
                },
                selected_paper_ids=[paper["id"]],
                session_id=session["id"],
                current_user_content="请先整理一份笔记草稿",
            )
        )
        self.assertEqual(proposed["status"], "pending")
        self.assertEqual(self.store.list_notes(), [])
        self.assertEqual(
            self.store.get_session(session["id"])["write_proposals"][0]["status"],
            "pending",
        )

        confirmed = json.loads(
            execute_literature_tool(
                self.store,
                "literature_write_confirm",
                {"proposal_id": proposed["proposal_id"]},
                selected_paper_ids=[paper["id"]],
                session_id=session["id"],
                current_user_content="任意自然语言由模型负责判断",
            )
        )
        self.assertEqual(confirmed["status"], "confirmed")
        self.assertEqual(self.store.list_notes()[0]["filename"], "证据整理.md")

    def test_ai_record_proposal_uses_domain_write_and_selected_paper_boundary(self) -> None:
        from app.literature_demo_chat import execute_literature_tool

        selected, _ = self.store.import_pdf_bytes("selected-record.pdf", PDF_BYTES)
        other, _ = self.store.import_pdf_bytes("other-record.pdf", PDF_BYTES + b"% other record")
        session = self.store.create_session("Record writing")
        args = {
            "paper_id": other["id"],
            "tags": [{"name": "EPR", "category": "characterization"}],
            "focus": "核对 EPR 证据。",
            "summary": "等待确认的摘要。",
        }
        denied = execute_literature_tool(
            self.store,
            "literature_record_propose",
            args,
            selected_paper_ids=[selected["id"]],
            session_id=session["id"],
            current_user_content="整理这篇文献",
        )
        self.assertIn("未选中", denied)

        args["paper_id"] = selected["id"]
        proposal = json.loads(
            execute_literature_tool(
                self.store,
                "literature_record_propose",
                args,
                selected_paper_ids=[selected["id"]],
                session_id=session["id"],
                current_user_content="整理这篇文献",
            )
        )
        result = json.loads(
            execute_literature_tool(
                self.store,
                "literature_write_confirm",
                {"proposal_id": proposal["proposal_id"]},
                selected_paper_ids=[selected["id"]],
                session_id=session["id"],
                current_user_content="就按这个写入",
            )
        )
        self.assertEqual(result["status"], "confirmed")
        updated = self.store.get_paper(selected["id"])
        self.assertEqual(updated["status"], "ready")
        self.assertEqual(updated["focus"], "核对 EPR 证据。")

    def test_ai_write_tools_expose_all_controlled_operations(self) -> None:
        from app.literature_demo_chat import LITERATURE_TOOLS

        names = {item["function"]["name"] for item in LITERATURE_TOOLS}
        self.assertTrue(
            {
                "literature_record_propose",
                "notes_upsert_propose",
                "literature_cross_propose",
                "project_memory_append_propose",
                "literature_archive_propose",
                "literature_write_confirm",
                "literature_write_reject",
            }.issubset(names)
        )

    def test_ai_memory_confirm_and_reject_tools_do_not_parse_user_text(self) -> None:
        from app.literature_demo_chat import execute_literature_tool

        session = self.store.create_session("Memory writing")
        source_message = "记住以后优先核对 EPR 对照实验"
        proposal = json.loads(
            execute_literature_tool(
                self.store,
                "project_memory_append_propose",
                {"markdown": "- 优先核对 EPR 对照实验。"},
                selected_paper_ids=[],
                session_id=session["id"],
                current_user_content=source_message,
            )
        )
        confirmed = json.loads(
            execute_literature_tool(
                self.store,
                "literature_write_confirm",
                {"proposal_id": proposal["proposal_id"]},
                selected_paper_ids=[],
                session_id=session["id"],
                current_user_content=source_message,
            )
        )
        self.assertEqual(confirmed["status"], "confirmed")
        self.assertIn("优先核对 EPR", self.store.read_memory())

        rejected_proposal = json.loads(
            execute_literature_tool(
                self.store,
                "project_memory_append_propose",
                {"markdown": "- 不写入的候选。"},
                selected_paper_ids=[],
                session_id=session["id"],
                current_user_content="再拟一条",
            )
        )
        rejected = json.loads(
            execute_literature_tool(
                self.store,
                "literature_write_reject",
                {"proposal_id": rejected_proposal["proposal_id"]},
                selected_paper_ids=[],
                session_id=session["id"],
                current_user_content="文本内容不参与后端判定",
            )
        )
        self.assertEqual(rejected["status"], "rejected")
        self.assertNotIn("不写入的候选", self.store.read_memory())

    def test_ai_write_proposal_is_claimed_once_under_concurrent_confirmation(self) -> None:
        from app.literature_demo_chat import execute_literature_tool

        session = self.store.create_session("Concurrent writing")
        proposal = json.loads(
            execute_literature_tool(
                self.store,
                "project_memory_append_propose",
                {"markdown": "- 并发确认只执行一次。"},
                selected_paper_ids=[],
                session_id=session["id"],
                current_user_content="请先拟定一条项目记忆",
            )
        )
        entered = threading.Event()
        release = threading.Event()
        calls: list[str] = []
        responses: list[str] = []
        errors: list[BaseException] = []

        def fake_execute(_store, claimed):
            calls.append(claimed["id"])
            if len(calls) == 1:
                entered.set()
                release.wait(timeout=2)
            return {"written": True}

        def confirm() -> None:
            try:
                responses.append(
                    execute_literature_tool(
                        self.store,
                        "literature_write_confirm",
                        {"proposal_id": proposal["proposal_id"]},
                        selected_paper_ids=[],
                        session_id=session["id"],
                        current_user_content="确认写入这个提案",
                    )
                )
            except BaseException as exc:  # pragma: no cover - assertion records thread failure
                errors.append(exc)

        with patch("app.literature_demo_chat._execute_write_proposal", side_effect=fake_execute):
            first = threading.Thread(target=confirm)
            second = threading.Thread(target=confirm)
            first.start()
            self.assertTrue(entered.wait(timeout=2))
            second.start()
            second.join(timeout=1)
            release.set()
            first.join(timeout=2)
            second.join(timeout=2)

        self.assertEqual(calls, [proposal["proposal_id"]])
        self.assertEqual(errors, [])
        self.assertEqual(len(responses), 2)
        self.assertTrue(any('"status": "confirmed"' in item for item in responses))
        self.assertTrue(any("正在执行" in item or "已经处理" in item for item in responses))

    def test_ai_write_proposals_reject_malformed_structured_arguments(self) -> None:
        from app.literature_demo_chat import execute_literature_tool

        paper, _ = self.store.import_pdf_bytes("malformed.pdf", PDF_BYTES)
        session = self.store.create_session("Malformed writing")
        malformed_tags = execute_literature_tool(
            self.store,
            "literature_record_propose",
            {
                "paper_id": paper["id"],
                "tags": ["EPR"],
                "focus": "核对证据",
                "summary": "短摘要",
            },
            selected_paper_ids=[paper["id"]],
            session_id=session["id"],
            current_user_content="整理文献",
        )
        malformed_sources = execute_literature_tool(
            self.store,
            "notes_upsert_propose",
            {
                "filename": "notes.md",
                "markdown": "# Notes",
                "source_paper_ids": paper["id"],
            },
            selected_paper_ids=[paper["id"]],
            session_id=session["id"],
            current_user_content="整理笔记",
        )

        self.assertIn("tags 格式", malformed_tags)
        self.assertIn("source_paper_ids 格式", malformed_sources)
        self.assertEqual(self.store.get_session(session["id"])["write_proposals"], [])

    def test_interrupted_executing_write_proposal_recovers_as_failed(self) -> None:
        from app.literature_demo_store import LiteratureDemoStore

        session = self.store.create_session("Interrupted writing")
        proposal = self.store.create_write_proposal(
            session["id"],
            operation="project_memory_append",
            payload={"markdown": "- Test"},
            summary="追加项目固定记忆",
            source_user_content="先拟定",
        )
        self.store.claim_write_proposal(session["id"], proposal["id"])

        restarted = LiteratureDemoStore(Path(self.tmp.name))
        recovered = restarted.get_write_proposal(session["id"], proposal["id"])

        self.assertEqual(recovered["status"], "failed")
        self.assertIn("中断", recovered["error"])

    def test_identical_pending_write_proposal_is_deduplicated(self) -> None:
        from app.literature_demo_chat import execute_literature_tool

        session = self.store.create_session("Deduplicated writing")
        kwargs = {
            "selected_paper_ids": [],
            "session_id": session["id"],
            "current_user_content": "请拟定一条记忆",
        }
        first = json.loads(
            execute_literature_tool(
                self.store,
                "project_memory_append_propose",
                {"markdown": "- 同一轮只保留一份。"},
                **kwargs,
            )
        )
        second = json.loads(
            execute_literature_tool(
                self.store,
                "project_memory_append_propose",
                {"markdown": "- 同一轮只保留一份。"},
                **kwargs,
            )
        )

        self.assertEqual(first["proposal_id"], second["proposal_id"])
        self.assertEqual(len(self.store.get_session(session["id"])["write_proposals"]), 1)

    def test_review_confirmation_registers_tags_and_requires_user_authority(self) -> None:
        paper, _ = self.store.import_pdf_bytes("paper.pdf", PDF_BYTES)
        with self.assertRaises(PermissionError):
            self.store.confirm_paper_review(
                paper["id"],
                tags=[{"name": "EPR", "category": "characterization"}],
                focus="重点核对原位 EPR 证据。",
                summary="客观事实已抽取，等待跨文献讨论。",
                confirmed=False,
            )

        reviewed = self.store.confirm_paper_review(
            paper["id"],
            tags=[
                {"name": "EPR", "category": "characterization"},
                {"name": "氧空位", "category": "material"},
            ],
            focus="重点核对原位 EPR 证据。",
            summary="客观事实已抽取，等待跨文献讨论。",
            confirmed=True,
        )

        self.assertEqual(reviewed["status"], "ready")
        self.assertEqual(len(reviewed["tags"]), 2)
        registry = self.store.list_tags()
        self.assertEqual({item["name"] for item in registry}, {"EPR", "氧空位"})
        self.assertTrue(all(item["status"] == "provisional" for item in registry))

    def test_archive_requires_cross_literature_section_then_moves_all_assets_and_updates_index(self) -> None:
        from app.literature_demo_archive import archive_paper, verify_paper_archive

        paper, _ = self.store.import_pdf_bytes("paper.pdf", PDF_BYTES)
        paper = self.store.apply_metadata(
            paper["id"],
            {
                "title": "EPR evidence",
                "authors": "A. Ren",
                "first_author_surname": "Ren",
                "year": 2026,
                "journal": "JACS",
                "journal_abbreviation": "JACS",
                "metadata_source": "manual_review",
                "paper_type": "research",
            },
        )
        output = self.store.unprocessed_dir / "minerU识别结果" / "Ren_2026_JACS"
        (output / "images").mkdir(parents=True)
        (output / "full.md").write_text("# Full text", encoding="utf-8")
        (output / "layout.json").write_text("{}", encoding="utf-8")
        (output / "paper_content_list.json").write_text("[]", encoding="utf-8")
        report = output / "_客观事实抽取报告.md"
        report.write_text(
            "# 客观事实抽取报告\n\n"
            "## 1. 基本信息\n已核对。\n\n"
            "## 2. 仪器与样品\nEPR 测试条件见原文 (p.3)。\n\n"
            "## 3. 现象与数据\n信号发生变化 (Fig.2, p.5)。\n\n"
            "## 4. 作者观点\n作者归属见讨论 (p.6)。\n\n"
            "## 5. 证据汇总\n|证据|数据|结论|\n|---|---|---|\n|EPR|变化 (Fig.2, p.5)|作者归属|\n\n"
            "## 6. 跨文献关系与系列归属\n⟨待主对话讨论后增补⟩\n",
            encoding="utf-8",
        )
        self.store.update_paper(
            paper["id"],
            mineru_output_path=output.relative_to(self.store.root).as_posix(),
            fact_report_path=report.relative_to(self.store.root).as_posix(),
            status="review",
        )
        self.store.confirm_paper_review(
            paper["id"],
            tags=[{"name": "EPR", "category": "characterization"}],
            focus="核对 EPR 证据链。",
            summary="该文献提供 EPR 证据。",
            confirmed=True,
        )

        blocked = verify_paper_archive(self.store, paper["id"])
        self.assertFalse(blocked["ok"])
        self.assertTrue(any("跨文献" in issue for issue in blocked["issues"]))

        self.store.update_cross_literature(
            paper["id"],
            "本项目将其归入 EPR 直接证据系列；该判断来自当前主对话。",
            confirmed=True,
        )
        result = archive_paper(self.store, paper["id"])

        self.assertTrue(result["verification"]["ok"])
        archived = result["paper"]
        self.assertEqual(archived["archive_location"], "文献/已处理")
        self.assertEqual(archived["verification_status"], "passed")
        self.assertIn("文献/已处理", archived["relative_pdf_path"])
        self.assertTrue(self.store.pdf_path(paper["id"]).is_file())
        self.assertIn("Ren_2026_JACS.pdf", self.store.index_path.read_text(encoding="utf-8"))

    def test_compaction_appends_marker_preserves_history_and_requires_memory_confirmation(self) -> None:
        from app.literature_demo_compactor import compact_literature_session

        session = self.store.create_session("Long discussion")
        self.store.append_message(session["id"], {"role": "user", "content": "问题 A"})
        self.store.append_message(session["id"], {"role": "assistant", "content": "回答 A"})
        with patch(
            "app.literature_demo_compactor._summarize_session",
            return_value={
                "summary": "已讨论问题 A，尚待核对 EPR 对照。",
                "memory_candidate": "本项目优先核对 EPR 对照实验。",
            },
        ):
            compacted = compact_literature_session(self.store, session["id"])

        self.assertEqual(len(compacted["session"]["messages"]), 3)
        marker = compacted["session"]["messages"][-1]
        self.assertEqual(marker["meta"]["kind"], "context_summary")
        self.assertIn("EPR", compacted["memory_candidate"])

        with self.assertRaises(PermissionError):
            self.store.resolve_memory_candidate(session["id"], accept=True, confirmed=False)
        accepted = self.store.resolve_memory_candidate(session["id"], accept=True, confirmed=True)
        self.assertIsNone(accepted["memory_candidate"])
        self.assertIn("优先核对 EPR", self.store.read_memory())


class LiteratureDemoApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("WORKMODE_PUBLIC_DATA_DIR")
        os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.tmp.name

        from app import config, storage
        from app.literature_demo_store import reset_literature_demo_store

        storage.settings = config.reload_settings()
        reset_literature_demo_store()
        from app.main import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self.old_data_dir is None:
            os.environ.pop("WORKMODE_PUBLIC_DATA_DIR", None)
        else:
            os.environ["WORKMODE_PUBLIC_DATA_DIR"] = self.old_data_dir
        self.tmp.cleanup()

    def test_health_exposes_agent_contract_and_actual_tool_names(self) -> None:
        health = self.client.get("/api/literature-demo/health")

        self.assertEqual(health.status_code, 200)
        payload = health.json()
        self.assertGreaterEqual(payload["agent_contract_version"], 2)
        self.assertIn("literature_record_propose", payload["agent_tools"])
        self.assertIn("notes_upsert_propose", payload["agent_tools"])
        self.assertIn("literature_write_confirm", payload["agent_tools"])

    def test_upload_list_and_inline_preview(self) -> None:
        response = self.client.post(
            "/api/literature-demo/papers/import",
            params={"filename": "sample.pdf", "process": "false"},
            content=PDF_BYTES,
            headers={"Content-Type": "application/pdf"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        paper = response.json()["paper"]

        listed = self.client.get("/api/literature-demo/papers").json()
        self.assertEqual([item["id"] for item in listed], [paper["id"]])

        preview = self.client.get(f"/api/literature-demo/papers/{paper['id']}/pdf")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.headers["content-type"], "application/pdf")
        self.assertTrue(preview.headers["content-disposition"].startswith("inline;"))
        self.assertNotEqual(preview.headers.get("x-frame-options"), "DENY")

    def test_upload_rejects_extension_magic_and_oversized_content_length(self) -> None:
        wrong_extension = self.client.post(
            "/api/literature-demo/papers/import",
            params={"filename": "sample.txt", "process": "false"},
            content=PDF_BYTES,
            headers={"Content-Type": "application/pdf"},
        )
        self.assertEqual(wrong_extension.status_code, 415)

        wrong_magic = self.client.post(
            "/api/literature-demo/papers/import",
            params={"filename": "sample.pdf", "process": "false"},
            content=b"not a pdf",
            headers={"Content-Type": "application/pdf"},
        )
        self.assertEqual(wrong_magic.status_code, 415)

        too_large = self.client.post(
            "/api/literature-demo/papers/import",
            params={"filename": "sample.pdf", "process": "false"},
            content=PDF_BYTES,
            headers={"Content-Type": "application/pdf", "Content-Length": str(200 * 1024 * 1024 + 1)},
        )
        self.assertEqual(too_large.status_code, 413)

    def test_manual_metadata_requires_confirmation_and_uses_standard_name(self) -> None:
        imported = self.client.post(
            "/api/literature-demo/papers/import",
            params={"filename": "unknown.pdf", "process": "false"},
            content=PDF_BYTES,
            headers={"Content-Type": "application/pdf"},
        ).json()["paper"]
        metadata = {
            "title": "Confirmed title",
            "authors": "A. Ren, B. Li",
            "first_author_surname": "Ren",
            "year": 2026,
            "journal": "Journal of the American Chemical Society",
            "journal_abbreviation": "JACS",
            "doi": "10.0000/example",
            "paper_type": "research",
            "confirmed": False,
        }
        rejected = self.client.patch(
            f"/api/literature-demo/papers/{imported['id']}/metadata",
            json=metadata,
        )
        self.assertEqual(rejected.status_code, 409)

        metadata["confirmed"] = True
        confirmed = self.client.patch(
            f"/api/literature-demo/papers/{imported['id']}/metadata",
            json=metadata,
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["archive_filename"], "Ren_2026_JACS.pdf")
        self.assertEqual(confirmed.json()["metadata_source"], "manual_review")

    def test_review_note_and_session_context_are_real_confirmed_api_writes(self) -> None:
        paper = self.client.post(
            "/api/literature-demo/papers/import",
            params={"filename": "record.pdf", "process": "false"},
            content=PDF_BYTES,
            headers={"Content-Type": "application/pdf"},
        ).json()["paper"]
        review = {
            "tags": [{"name": "EPR", "category": "characterization"}],
            "focus": "核对 EPR 对照。",
            "summary": "记录 EPR 事实。",
            "confirmed": False,
        }
        rejected = self.client.patch(
            f"/api/literature-demo/papers/{paper['id']}/review",
            json=review,
        )
        self.assertEqual(rejected.status_code, 409)
        review["confirmed"] = True
        confirmed = self.client.patch(
            f"/api/literature-demo/papers/{paper['id']}/review",
            json=review,
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["status"], "ready")

        note = self.client.put(
            "/api/literature-demo/notes/evidence.md",
            json={
                "markdown": "# Evidence",
                "source_paper_ids": [paper["id"]],
                "confirmed": True,
            },
        )
        self.assertEqual(note.status_code, 200, note.text)
        self.assertEqual(note.json()["source_paper_ids"], [paper["id"]])

        session = self.client.post("/api/literature-demo/sessions", json={"name": "API"}).json()
        context = self.client.patch(
            f"/api/literature-demo/sessions/{session['id']}/context",
            json={"paper_ids": [paper["id"]], "note_ids": ["evidence.md"]},
        )
        self.assertEqual(context.status_code, 200, context.text)
        self.assertEqual(context.json()["attached_paper_ids"], [paper["id"]])
        self.assertEqual(context.json()["attached_note_ids"], ["evidence.md"])


if __name__ == "__main__":
    unittest.main()
