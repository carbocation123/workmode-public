from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STYLES = ROOT / "frontend" / "src" / "styles.css"
APP_SOURCE = ROOT / "frontend" / "src" / "App.tsx"
ONBOARDING_SOURCE = ROOT / "frontend" / "src" / "OnboardingUI.tsx"
ICON_SOURCE = ROOT / "desktop" / "src-tauri" / "icons" / "icon-source.png"


class DesktopUiContractTest(unittest.TestCase):
    def test_pdf_preview_fills_the_available_file_panel_height(self) -> None:
        css = STYLES.read_text(encoding="utf-8")
        rule = re.search(r"\.media\.pdf\s*\{(?P<body>[^}]*)\}", css)

        self.assertIsNotNone(rule)
        self.assertRegex(rule.group("body"), r"height\s*:\s*100%\s*;")
        self.assertNotRegex(rule.group("body"), r"height\s*:\s*\d+vh\s*;")

    def test_desktop_icon_source_is_the_requested_release_logo(self) -> None:
        self.assertTrue(ICON_SOURCE.is_file())
        digest = hashlib.sha256(ICON_SOURCE.read_bytes()).hexdigest()
        self.assertEqual(
            digest,
            "4746ca99a772b049209450d7d1d7f14fa947173f6cbe677fad258aa0e7a27ecf",
        )

    def test_token_bar_marks_loaded_project_prompt(self) -> None:
        source = APP_SOURCE.read_text(encoding="utf-8")

        self.assertIn("context.project_prompt_file", source)
        self.assertIn("项目提示词", source)

    def test_assistant_markdown_tables_have_readable_overflow_styles(self) -> None:
        css = STYLES.read_text(encoding="utf-8")

        self.assertRegex(css, r"\.markdown-table-scroll\s*\{[^}]*overflow-x\s*:\s*auto")
        self.assertRegex(css, r"\.message \.bubble table,[^}]*border-collapse\s*:\s*collapse")
        self.assertRegex(css, r"\.message \.bubble th,[^}]*border-(?:right|bottom)\s*:")

    def test_tutorial_projects_expose_install_and_reset_actions(self) -> None:
        source = APP_SOURCE.read_text(encoding="utf-8")

        self.assertIn("创建教程项目", source)
        self.assertIn("重置教程", source)
        self.assertIn("activeProject?.is_tutorial", source)

    def test_first_run_guidance_and_achievements_have_replayable_ui(self) -> None:
        source = APP_SOURCE.read_text(encoding="utf-8") + ONBOARDING_SOURCE.read_text(encoding="utf-8")
        css = STYLES.read_text(encoding="utf-8")

        self.assertIn("重新播放新手引导", source)
        self.assertIn("科研协作教程", source)
        self.assertIn('data-guide="projects"', source)
        self.assertIn('data-guide="files"', source)
        self.assertIn('data-guide="chat"', source)
        self.assertIn('data-guide="context"', source)
        self.assertIn('data-guide="viewer"', source)
        self.assertRegex(css, r"\.onboarding-overlay\s*\{")
        self.assertRegex(css, r"\.achievement-toast\s*\{")


if __name__ == "__main__":
    unittest.main()
