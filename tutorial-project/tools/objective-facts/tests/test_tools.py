from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TOOL_DIR.parent.parent


def run_script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL_DIR / name), *args],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def load_prep_module():
    path = TOOL_DIR / "prep_paper_for_deepseek.py"
    spec = importlib.util.spec_from_file_location("prep_paper_for_deepseek", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ObjectiveFactsToolTests(unittest.TestCase):
    def test_bundled_precomputed_snapshot_is_offline_and_reproducible(self) -> None:
        prep = load_prep_module()
        extracted = PROJECT_ROOT / "papers" / "extracted" / "s41467-019-13638-9"
        manifest = json.loads((extracted / "batch_manifest.json").read_text(encoding="utf-8"))
        mineru_meta = json.loads((extracted / "_mineru_meta.json").read_text(encoding="utf-8"))
        regenerated = prep.process_paper(
            extracted,
            parser_label="Tutorial precomputed snapshot (no API call)",
        )
        bundled = (extracted / "s41467-019-13638-9_prepared.txt").read_text(encoding="utf-8")
        report = (extracted / "s41467-019-13638-9_客观事实抽取报告_v2.md").read_text(encoding="utf-8")
        self.assertEqual(manifest["network_calls"], 0)
        self.assertFalse(mineru_meta["network_upload_performed"])
        self.assertEqual(regenerated, bundled)
        for section in range(1, 7):
            self.assertIn(f"## {section}.", report)

    def test_preprocessor_keeps_page_tags_and_structured_blocks(self) -> None:
        prep = load_prep_module()
        blocks = [
            {"type": "header", "page_idx": 0, "text": "Nature Communications"},
            {"type": "page_number", "page_idx": 0, "text": "101"},
            {"type": "text", "page_idx": 0, "text": "Results", "text_level": 1},
            {"type": "text", "page_idx": 0, "text": "Observed value 7.1%."},
            {"type": "image", "page_idx": 0, "image_caption": ["Figure 1. Test"]},
            {
                "type": "table",
                "page_idx": 0,
                "table_caption": ["Table 1. Conditions"],
                "table_body": "<table><tr><td>300 C</td></tr></table>",
            },
        ]
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "paper_content_list.json").write_text(
                json.dumps(blocks), encoding="utf-8"
            )
            result = prep.process_paper(directory, parser_label="Tutorial snapshot; no API")
        self.assertIn("解析来源: Tutorial snapshot; no API", result)
        self.assertIn("[p.101] [META-HEADER] Nature Communications", result)
        self.assertIn("[p.101] # Results", result)
        self.assertIn("[p.101] Observed value 7.1%.", result)
        self.assertIn("Figure 1. Test", result)
        self.assertIn("<td>300 C</td>", result)

    def test_pdf2md_dry_run_needs_no_key_and_does_not_upload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "paper.pdf"
            pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
            result = run_script("pdf2md.py", str(pdf), "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[DRY] upload=", result.stdout)

    def test_pdf2md_refuses_upload_without_explicit_consent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "paper.pdf"
            pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
            result = run_script("pdf2md.py", str(pdf))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("拒绝上传", result.stderr + result.stdout)

    def test_model_batch_dry_run_needs_no_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prompt = root / "prompt.txt"
            paper = root / "paper.txt"
            prompt.write_text("Read:\n{INPUT}", encoding="utf-8")
            paper.write_text("objective content", encoding="utf-8")
            result = run_script(
                "deepseek_batch.py",
                "--prompt-file", str(prompt),
                "--inputs", str(paper),
                "--output-dir", str(root / "out"),
                "--dry-run",
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dry-run 不实际调用 API", result.stdout)

    def test_model_batch_refuses_send_without_explicit_consent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prompt = root / "prompt.txt"
            paper = root / "paper.txt"
            prompt.write_text("{INPUT}", encoding="utf-8")
            paper.write_text("objective content", encoding="utf-8")
            result = run_script(
                "deepseek_batch.py",
                "--prompt-file", str(prompt),
                "--inputs", str(paper),
                "--output-dir", str(root / "out"),
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("拒绝发送", result.stderr + result.stdout)

    def test_pipeline_dry_run_needs_no_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "paper.pdf"
            pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
            result = run_script("run_pipeline.py", str(pdf), "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("未上传 PDF、未发送文献文本", result.stdout)


if __name__ == "__main__":
    unittest.main()
