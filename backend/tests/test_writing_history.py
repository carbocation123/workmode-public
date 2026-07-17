from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.writing.history import ArticleHistoryNotFound, ArticleHistoryStore


class ArticleHistoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ArticleHistoryStore(Path(self.tmp.name) / "article-processing")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_history_records_input_mode_options_output_and_model(self) -> None:
        record = self.store.create(
            mode="polish",
            input_text="H2O 是水。",
            output_text="H₂O 是水。\n",
            model="test-model",
        )

        loaded = self.store.get(record["id"])
        self.assertEqual(loaded["input_text"], "H2O 是水。")
        self.assertEqual(loaded["output_text"], "H₂O 是水。\n")
        self.assertEqual(loaded["mode"], "polish")
        self.assertEqual(loaded["options"], {"unicode_superscript_subscript": True})
        self.assertEqual(loaded["model"], "test-model")
        self.assertEqual([item["id"] for item in self.store.list()], [record["id"]])

    def test_delete_is_recoverable_and_restore_never_overwrites_an_active_record(self) -> None:
        record = self.store.create(
            mode="audit",
            input_text="待核查正文",
            output_text="# 文章漏洞核查\n",
            model="test-model",
        )

        deleted = self.store.delete(record["id"])
        self.assertEqual(self.store.list(), [])
        self.assertEqual(self.store.list_deleted()[0]["record"]["id"], record["id"])
        with self.assertRaises(ArticleHistoryNotFound):
            self.store.get(record["id"])

        restored = self.store.restore(deleted["trash_id"])
        self.assertEqual(restored["id"], record["id"])
        self.assertEqual(self.store.list_deleted(), [])
        self.assertEqual(self.store.get(record["id"])["output_text"], "# 文章漏洞核查\n")


if __name__ == "__main__":
    unittest.main()
