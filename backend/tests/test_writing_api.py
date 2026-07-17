from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.writing.history import ArticleHistoryStore


class _Processor:
    model_name = "test-model"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def process(self, *, mode: str, text: str) -> str:
        self.calls.append((mode, text))
        return "H₂O 是水。\n" if mode == "polish" else "# 文章漏洞核查\n"


class WritingApiTests(unittest.TestCase):
    def setUp(self) -> None:
        from app.main import app
        from fastapi.testclient import TestClient

        self.tmp = tempfile.TemporaryDirectory()
        self.store = ArticleHistoryStore(Path(self.tmp.name) / "article-processing")
        self.processor = _Processor()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_process_creates_history_that_can_be_loaded_deleted_and_restored(self) -> None:
        configured = SimpleNamespace(
            model_base_url="https://model.example/v1",
            model_api_key="configured",
            model_name="test-model",
        )
        with (
            patch("app.writing.routes.get_article_history_store", return_value=self.store),
            patch("app.writing.routes.get_article_processor", return_value=self.processor),
            patch("app.writing.routes.get_settings", return_value=configured),
        ):
            created = self.client.post(
                "/api/writing/process",
                json={"mode": "polish", "input_text": "H2O是水。"},
            )
            record = created.json()["record"]
            listed = self.client.get("/api/writing/history")
            loaded = self.client.get(f"/api/writing/history/{record['id']}")
            deleted = self.client.delete(f"/api/writing/history/{record['id']}")
            trash_id = deleted.json()["trash"]["trash_id"]
            restored = self.client.post(f"/api/writing/trash/{trash_id}/restore")

        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(record["output_text"], "H₂O 是水。\n")
        self.assertEqual(record["options"]["unicode_superscript_subscript"], True)
        self.assertEqual(listed.json()["items"][0]["id"], record["id"])
        self.assertEqual(listed.json()["items"][0]["input_preview"], "H2O是水。")
        self.assertNotIn("input_text", listed.json()["items"][0])
        self.assertNotIn("output_text", listed.json()["items"][0])
        self.assertEqual(loaded.json()["record"]["input_text"], "H2O是水。")
        self.assertEqual(restored.json()["record"]["id"], record["id"])
        self.assertEqual(self.processor.calls, [("polish", "H2O是水。")])

    def test_missing_model_settings_and_blank_input_do_not_create_history(self) -> None:
        missing = SimpleNamespace(model_base_url="", model_api_key=None, model_name="test-model")
        with (
            patch("app.writing.routes.get_article_history_store", return_value=self.store),
            patch("app.writing.routes.get_article_processor", return_value=self.processor),
            patch("app.writing.routes.get_settings", return_value=missing),
        ):
            unconfigured = self.client.post(
                "/api/writing/process",
                json={"mode": "polish", "input_text": "正文"},
            )
            blank = self.client.post(
                "/api/writing/process",
                json={"mode": "audit", "input_text": "   "},
            )

        self.assertEqual(unconfigured.status_code, 503)
        self.assertEqual(blank.status_code, 422)
        self.assertEqual(self.store.list(), [])


if __name__ == "__main__":
    unittest.main()
