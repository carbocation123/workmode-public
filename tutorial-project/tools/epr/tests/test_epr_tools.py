from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TOOL_DIR.parent.parent


def load_module(name: str):
    path = TOOL_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EprToolTests(unittest.TestCase):
    def test_bundled_demo_matches_manifest_and_precomputed_asc(self) -> None:
        converter = load_module("bruker_spc2asc")
        raw = PROJECT_ROOT / "data" / "raw" / "epr"
        processed = PROJECT_ROOT / "data" / "processed" / "epr"
        manifest = json.loads((raw / "demo_epr_generation.json").read_text(encoding="utf-8"))
        for name, metadata in manifest["files"].items():
            digest = hashlib.sha256((raw / name).read_bytes()).hexdigest()
            self.assertEqual(digest, metadata["sha256"])
        with tempfile.TemporaryDirectory() as temp:
            generated = converter.convert_one(
                raw / "demo_epr.par",
                asc_out=Path(temp) / "demo_epr.asc",
                par_source_override="data/raw/epr/demo_epr.par",
            )
            ok, message = converter.verify_asc(generated, processed / "demo_epr.asc")
        self.assertTrue(ok, message)

    def test_generated_spc_converts_to_1024_point_asc(self) -> None:
        generator = load_module("generate_demo_epr")
        converter = load_module("bruker_spc2asc")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            par, spc, manifest = generator.write_demo(root, "demo")
            asc = converter.convert_one(par)
            metadata = json.loads(manifest.read_text(encoding="utf-8"))
            parsed = converter.parse_par(par)
            fields = converter.build_field_axis(parsed)
            values = converter.read_spc(spc, parsed["ANZ"])
            lines = [line for line in asc.read_text(encoding="utf-8").splitlines() if line.strip()]
            spc_size = spc.stat().st_size
        self.assertEqual(spc_size, 4096)
        self.assertTrue(metadata["simulated"])
        self.assertEqual(len(fields), 1024)
        self.assertEqual(len(values), 1024)
        self.assertAlmostEqual(fields[0], 3100.0, places=5)
        self.assertAlmostEqual(fields[-1], 3900.0, places=5)
        self.assertIn("Filename:\tdemo.par", lines[0])
        self.assertEqual(lines[1], "X [G]\tIntensity")
        self.assertEqual(len(lines[2:]), 1024)

    def test_scan_reports_both_simulated_signal_windows_above_noise(self) -> None:
        generator = load_module("generate_demo_epr")
        converter = load_module("bruker_spc2asc")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            par, _, _ = generator.write_demo(root, "demo")
            processed = root / "processed"
            processed.mkdir()
            asc = converter.convert_one(par, asc_out=processed / "demo.asc")
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL_DIR / "epr_scan.py"),
                    str(asc),
                    "--par", str(par),
                    "--noise-window", "1.94", "1.955",
                ],
                text=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Signal A 窗", result.stdout)
        self.assertIn("Signal B 窗", result.stdout)
        self.assertIn("3× 门限", result.stdout)

    def test_converter_rejects_spc_size_mismatch(self) -> None:
        converter = load_module("bruker_spc2asc")
        with tempfile.TemporaryDirectory() as temp:
            spc = Path(temp) / "bad.spc"
            spc.write_bytes(b"short")
            with self.assertRaisesRegex(ValueError, "文件大小不符"):
                converter.read_spc(spc, 1024)


if __name__ == "__main__":
    unittest.main()
