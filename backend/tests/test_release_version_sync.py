from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "sync-version.ps1"
BUILD_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build-desktop.ps1"
WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release-windows.yml"


class ReleaseVersionSyncTest(unittest.TestCase):
    def test_release_workflow_pins_the_lockfile_npm_version(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("npm install --global npm@10.9.4", workflow)
        self.assertLess(
            workflow.index("npm install --global npm@10.9.4"),
            workflow.index("npm ci --prefix frontend"),
        )

    def test_release_workflow_stops_immediately_when_dependency_install_fails(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertRegex(
            workflow,
            r"npm ci --prefix frontend\s+if \(\$LASTEXITCODE -ne 0\)",
        )
        self.assertRegex(
            workflow,
            r"npm ci --prefix desktop\s+if \(\$LASTEXITCODE -ne 0\)",
        )

    def test_release_workflow_only_commits_real_staged_version_changes(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertNotIn("if (git status --porcelain)", workflow)
        self.assertIn("$stagedVersionFiles = @(git diff --cached --name-only)", workflow)
        self.assertIn("if ($stagedVersionFiles.Count -gt 0)", workflow)

    def test_release_workflow_can_publish_from_a_semver_tag_without_rewriting_it(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("push:", workflow)
        self.assertIn("tags:", workflow)
        self.assertIn("- 'v*.*.*'", workflow)
        self.assertIn("github.event_name", workflow)
        self.assertIn("Tag release version does not match committed version files", workflow)
        self.assertIn("steps.version.outputs.version", workflow)

    def test_release_workflow_uses_official_rust_and_pip_caches(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("uses: actions/cache@v5", workflow)
        self.assertIn("desktop/src-tauri/target", workflow)
        self.assertIn("~/.cargo/registry", workflow)
        self.assertIn("cache: pip", workflow)
        self.assertIn("cache-dependency-path: backend/requirements.txt", workflow)

    def test_release_tests_use_the_release_profile_for_tauri_build_reuse(self):
        script = BUILD_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("& npm test", script)
        self.assertIn("& $cargo test --release", script)
        self.assertIn("Rust release-profile tests completed in", script)

    def test_release_stages_the_initial_tutorial_project(self):
        script = BUILD_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('Join-Path $Root "tutorial-project"', script)
        self.assertIn('Join-Path $Resources "tutorial-project"', script)
        self.assertIn('tutorial-project\\WORKMODE_TUTORIAL.json', script)

    def test_release_publishes_only_application_artifacts_and_never_skin_packages(self):
        script = BUILD_SCRIPT.read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertNotIn("official-skins", script)
        self.assertNotIn("publishedSkinRoot", script)
        self.assertNotIn(".workmode-skin", script)
        self.assertNotIn('official-skin-ed25519.pem', script)
        self.assertIn('Get-ChildItem "release/desktop-$version" -File', workflow)
        self.assertNotIn('-Recurse', workflow)
        self.assertNotIn('skin-library', workflow)
        self.assertNotIn('local-reference', workflow)

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
