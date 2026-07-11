from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STYLES = ROOT / "frontend" / "src" / "styles.css"
APP_SOURCE = ROOT / "frontend" / "src" / "App.tsx"
ONBOARDING_SOURCE = ROOT / "frontend" / "src" / "OnboardingUI.tsx"
THEME_SOURCE = ROOT / "frontend" / "src" / "theme.ts"
THEME_PANEL_SOURCE = ROOT / "frontend" / "src" / "ThemePanel.tsx"
NEON_HUD_SOURCE = ROOT / "frontend" / "src" / "NeonHud.tsx"
SKIN_CHROME_SOURCE = ROOT / "frontend" / "src" / "SkinChrome.tsx"
DESKTOP_SOURCE = ROOT / "frontend" / "src" / "desktop.ts"
DESKTOP_CAPABILITIES = ROOT / "desktop" / "src-tauri" / "capabilities" / "default.json"
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

    def test_deepseek_api_application_guide_is_available_in_product_ui(self) -> None:
        source = APP_SOURCE.read_text(encoding="utf-8") + ONBOARDING_SOURCE.read_text(encoding="utf-8")

        self.assertIn("如何申请 DeepSeek API", source)
        self.assertIn("创建 API Key", source)
        self.assertIn("充值与价格", source)
        self.assertIn("一键填入 V4 Pro", source)

    def test_project_directories_start_collapsed_with_file_type_icons(self) -> None:
        source = APP_SOURCE.read_text(encoding="utf-8")

        self.assertIn("setExpandedDirs(new Set())", source)
        self.assertIn("fileEntryVisual(entry", source)
        self.assertIn("tree-node-kind", source)

    def test_deepseek_links_use_scoped_system_browser_opener(self) -> None:
        desktop_source = DESKTOP_SOURCE.read_text(encoding="utf-8")
        permissions = json.loads(DESKTOP_CAPABILITIES.read_text(encoding="utf-8"))["permissions"]
        opener = next(item for item in permissions if isinstance(item, dict) and item.get("identifier") == "opener:allow-open-url")
        allowed_urls = {item["url"] for item in opener["allow"]}

        self.assertIn("openUrl(url)", desktop_source)
        self.assertEqual(allowed_urls, {
            "https://platform.deepseek.com/*",
            "https://api-docs.deepseek.com/*",
        })

    def test_skin_system_has_system_mode_accessibility_and_achievement_unlock(self) -> None:
        app_source = APP_SOURCE.read_text(encoding="utf-8")
        theme_source = THEME_SOURCE.read_text(encoding="utf-8")
        panel_source = THEME_PANEL_SOURCE.read_text(encoding="utf-8")
        css = STYLES.read_text(encoding="utf-8")

        self.assertIn("外观与皮肤", app_source)
        self.assertIn("tutorial_graduate", theme_source)
        self.assertIn("跟随系统", panel_source)
        self.assertIn("降低动效", panel_source)
        self.assertIn('[data-theme="paper"]', css)
        self.assertIn('[data-theme="origin-ring"]', css)
        self.assertIn('[data-theme="high-contrast"]', css)
        self.assertIn('[data-reduced-motion="true"]', css)

    def test_neon_space_lab_skin_binds_real_workmode_status(self) -> None:
        app_source = APP_SOURCE.read_text(encoding="utf-8")
        theme_source = THEME_SOURCE.read_text(encoding="utf-8")
        hud_source = NEON_HUD_SOURCE.read_text(encoding="utf-8")
        chrome_source = SKIN_CHROME_SOURCE.read_text(encoding="utf-8")
        css = STYLES.read_text(encoding="utf-8")

        self.assertIn("neon-space-lab", theme_source)
        self.assertIn("<SkinChrome", app_source)
        self.assertIn("<NeonHud", chrome_source)
        self.assertIn("SKIN_CHROME_REGISTRY", chrome_source)
        self.assertIn("SkinRuntimeProps", chrome_source)
        self.assertIn("layout: 'hud'", theme_source)
        self.assertIn("contextPct", app_source)
        self.assertIn("neon-context-ring", app_source)
        self.assertIn("MODEL LINK", hud_source)
        self.assertIn("ACTIVE MISSION", hud_source)
        self.assertIn('data-theme="neon-space-lab"', css)
        self.assertIn(".neon-tool-scan", css)


if __name__ == "__main__":
    unittest.main()
