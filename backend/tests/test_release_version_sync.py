from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "sync-version.ps1"


class ReleaseVersionSyncTest(unittest.TestCase):
    def test_sync_updates_every_release_version_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "frontend").mkdir()
            (root / "desktop" / "src-tauri").mkdir(parents=True)
            (root / "VERSION").write_text("0.2.0\n", encoding="utf-8")
            for path in (root / "frontend" / "package.json", root / "desktop" / "package.json"):
                path.write_text('{"name":"fixture","version":"0.2.0"}\n', encoding="utf-8")
            for path in (root / "frontend" / "package-lock.json", root / "desktop" / "package-lock.json"):
                path.write_text(
                    '{"name":"fixture","version":"0.2.0","lockfileVersion":3,"packages":{"":{"version":"0.2.0"}}}\n',
                    encoding="utf-8",
                )
            (root / "desktop" / "src-tauri" / "tauri.conf.json").write_text(
                '{"productName":"Fixture","version":"0.2.0"}\n', encoding="utf-8"
            )
            (root / "desktop" / "src-tauri" / "Cargo.toml").write_text(
                '[package]\nname = "workmode-public"\nversion = "0.2.0"\n\n[dependencies]\n', encoding="utf-8"
            )
            (root / "desktop" / "src-tauri" / "Cargo.lock").write_text(
                '[[package]]\nname = "workmode-public"\nversion = "0.2.0"\n', encoding="utf-8"
            )

            process = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(SCRIPT),
                    "-Root",
                    str(root),
                    "-Version",
                    "1.2.3",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            self.assertEqual((root / "VERSION").read_text(encoding="utf-8").strip(), "1.2.3")
            self.assertEqual(json.loads((root / "frontend" / "package.json").read_text())["version"], "1.2.3")
            self.assertEqual(json.loads((root / "desktop" / "package-lock.json").read_text())["packages"][""]["version"], "1.2.3")
            self.assertEqual(json.loads((root / "desktop" / "src-tauri" / "tauri.conf.json").read_text())["version"], "1.2.3")
            self.assertIn('version = "1.2.3"', (root / "desktop" / "src-tauri" / "Cargo.toml").read_text())
            self.assertIn('version = "1.2.3"', (root / "desktop" / "src-tauri" / "Cargo.lock").read_text())

    def test_sync_rejects_non_semver_input_without_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.2.0\n", encoding="utf-8")

            process = subprocess.run(
                ["powershell", "-NoProfile", "-File", str(SCRIPT), "-Root", str(root), "-Version", "latest"],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(process.returncode, 0)
            self.assertEqual((root / "VERSION").read_text(encoding="utf-8"), "0.2.0\n")


if __name__ == "__main__":
    unittest.main()
