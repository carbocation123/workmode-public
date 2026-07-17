from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STYLES = ROOT / "frontend" / "src" / "styles.css"
SKIN_RUNTIME_STYLES = ROOT / "frontend" / "src" / "skinRuntime.css"
SKIN_PROTOCOL_SOURCE = ROOT / "frontend" / "src" / "skinProtocol.ts"
SKIN_LIBRARY_SOURCE = ROOT / "frontend" / "src" / "skinLibrary.ts"
SKIN_PACKAGE_SOURCE = ROOT / "frontend" / "src" / "skinPackage.ts"
OFFICIAL_SKIN_KEYS_SOURCE = ROOT / "frontend" / "src" / "officialSkinKeys.ts"
OFFICIAL_SKIN_SIGNER = ROOT / "scripts" / "official-skin.mjs"
OFFICIAL_SKIN_BUILDER = ROOT / "scripts" / "build-skin-library.ps1"
PRIVATE_REWARD_SKIN_ROOT = ROOT / "local-reference" / "reward-skin-library"
SKIN_SOURCE_DIR = PRIVATE_REWARD_SKIN_ROOT / "sources"
PIXEL_SKIN_DIR = SKIN_SOURCE_DIR / "pixel-night-shift"
LEGACY_SKIN_EXAMPLE_DIR = PRIVATE_REWARD_SKIN_ROOT / "legacy-examples"
PRIVATE_REWARD_SKINS_AVAILABLE = SKIN_SOURCE_DIR.is_dir()
PRIVATE_LEGACY_EXAMPLES_AVAILABLE = LEGACY_SKIN_EXAMPLE_DIR.is_dir()
APP_SOURCE = ROOT / "frontend" / "src" / "App.tsx"
BUG_REPORT_SOURCE = ROOT / "frontend" / "src" / "bugReport.ts"
BUG_REPORT_DIALOG_SOURCE = ROOT / "frontend" / "src" / "BugReportDialog.tsx"
SUPPORT_QR_SOURCE = ROOT / "frontend" / "src" / "assets" / "support-public-account-qr.jpg"
ONBOARDING_SOURCE = ROOT / "frontend" / "src" / "OnboardingUI.tsx"
THEME_SOURCE = ROOT / "frontend" / "src" / "theme.ts"
THEME_PANEL_SOURCE = ROOT / "frontend" / "src" / "ThemePanel.tsx"
NEON_HUD_SOURCE = ROOT / "frontend" / "src" / "NeonHud.tsx"
SKIN_CHROME_SOURCE = ROOT / "frontend" / "src" / "SkinChrome.tsx"
PRESET_CHROME_SOURCE = ROOT / "frontend" / "src" / "PresetChrome.tsx"
NEON_ASSET_DIR = ROOT / "frontend" / "src" / "assets" / "neon"
CREAM_SKIN_EXAMPLE = LEGACY_SKIN_EXAMPLE_DIR / "cream-puff.workmode-skin.json"
GREEN_SKIN_EXAMPLE = LEGACY_SKIN_EXAMPLE_DIR / "green-phosphor.workmode-skin.json"
AMETHYST_SKIN_EXAMPLE = LEGACY_SKIN_EXAMPLE_DIR / "amethyst-observatory.workmode-skin.json"
CONSOLE_SKIN_EXAMPLE = LEGACY_SKIN_EXAMPLE_DIR / "midnight-console.workmode-skin.json"
GEM_TECH_SKIN_EXAMPLE = LEGACY_SKIN_EXAMPLE_DIR / "cryo-gem-tech.workmode-skin.json"
DESKTOP_SOURCE = ROOT / "frontend" / "src" / "desktop.ts"
DESKTOP_LIB_SOURCE = ROOT / "desktop" / "src-tauri" / "src" / "lib.rs"
DESKTOP_CAPABILITIES = ROOT / "desktop" / "src-tauri" / "capabilities" / "default.json"
TAURI_CONFIG = ROOT / "desktop" / "src-tauri" / "tauri.conf.json"
ICON_SOURCE = ROOT / "desktop" / "src-tauri" / "icons" / "icon-source.png"
FRONTEND_PACKAGE = ROOT / "frontend" / "package.json"
FRONTEND_VITE_CONFIG = ROOT / "frontend" / "vite.config.ts"
LITERATURE_HTML = ROOT / "frontend" / "literature" / "index.html"
LITERATURE_APP_SOURCE = ROOT / "frontend" / "src" / "literature" / "LiteratureApp.tsx"
LITERATURE_API_SOURCE = ROOT / "frontend" / "src" / "literature" / "literatureApi.ts"
LITERATURE_STYLES = ROOT / "frontend" / "src" / "literature" / "styles.css"
LITERATURE_NAVIGATION_SOURCE = ROOT / "frontend" / "src" / "literatureNavigation.ts"
LITERATURE_LAUNCHER_SOURCE = ROOT / "frontend" / "src" / "literatureLauncher.ts"
PDF_VIEWER_SOURCE = ROOT / "frontend" / "src" / "PdfViewer.tsx"
APPLICATION_HOME_SOURCE = ROOT / "frontend" / "src" / "ApplicationHome.tsx"
APPLICATION_HOME_STYLES = ROOT / "frontend" / "src" / "applicationHome.css"
FRONTEND_MAIN_SOURCE = ROOT / "frontend" / "src" / "main.tsx"
BACKEND_MAIN_SOURCE = ROOT / "backend" / "app" / "main.py"
BACKEND_ROUTES_SOURCE = ROOT / "backend" / "app" / "routes.py"
SOURCE_LAUNCHER = ROOT / "scripts" / "one-click-start.ps1"


class DesktopUiContractTest(unittest.TestCase):
    def test_literature_workbench_is_a_packaged_multi_page_frontend(self) -> None:
        app = APP_SOURCE.read_text(encoding="utf-8")
        vite = FRONTEND_VITE_CONFIG.read_text(encoding="utf-8")
        literature_html = LITERATURE_HTML.read_text(encoding="utf-8")
        literature_app = LITERATURE_APP_SOURCE.read_text(encoding="utf-8")
        literature_api = LITERATURE_API_SOURCE.read_text(encoding="utf-8")
        literature_navigation = LITERATURE_NAVIGATION_SOURCE.read_text(encoding="utf-8")
        literature_launcher = LITERATURE_LAUNCHER_SOURCE.read_text(encoding="utf-8")
        pdf_viewer = PDF_VIEWER_SOURCE.read_text(encoding="utf-8")
        application_home = APPLICATION_HOME_SOURCE.read_text(encoding="utf-8")
        application_home_styles = APPLICATION_HOME_STYLES.read_text(encoding="utf-8")
        frontend_main = FRONTEND_MAIN_SOURCE.read_text(encoding="utf-8")
        backend_main = BACKEND_MAIN_SOURCE.read_text(encoding="utf-8")

        self.assertNotIn("openLiteratureWorkbench", app)
        self.assertNotIn('title="文献智库"', app)
        self.assertIn("title={activePanel === 'settings'", app)
        self.assertNotIn("createLiteratureProject", literature_launcher)
        self.assertNotIn("pickDirectory", literature_launcher)
        self.assertNotIn("root_path:", literature_launcher)
        self.assertIn("科研工作台", application_home)
        self.assertIn("文献智库", application_home)
        self.assertNotIn("今天想怎么和 AI 一起工作？", application_home)
        self.assertNotIn("完整工作台保留全部自由度", application_home)
        self.assertIn("定制你自己的AI工作流", application_home)
        self.assertIn("文献特化模块 ·", application_home)
        self.assertNotIn("首个特化模块 ·", application_home)
        self.assertIn(".mode-hub-shell > .mode-hub-grid { grid-row: 2 / 4; }", application_home_styles)
        self.assertIn(".mode-hub-shell > .mode-hub-footer { grid-row: 4; }", application_home_styles)
        self.assertIn("align-self: center;", application_home_styles)
        self.assertIn("height: min(520px, calc(100% - 48px));", application_home_styles)
        self.assertIn("resolveApplicationSurface", frontend_main)
        self.assertIn("<ApplicationHome themeId={initialThemeId}", frontend_main)
        self.assertIn("literature/index.html", vite)
        self.assertIn("/src/literature/main.tsx", literature_html)
        self.assertIn("功能大厅", literature_app)
        self.assertIn("workbenchSettingsUrl", literature_app)
        self.assertIn("打开全局设置", literature_app)
        self.assertNotIn("和文献一起讨论", literature_app)
        self.assertIn('data-skin-slot="literature-shell"', literature_app)
        self.assertIn('className="activity-bar"', literature_app)
        self.assertIn('data-skin-slot="activity-navigation"', literature_app)
        self.assertIn('className="activity-bar-top"', literature_app)
        self.assertIn('className="activity-bar-bottom"', literature_app)
        self.assertNotIn("return-workbench-button", literature_app)
        self.assertNotIn("literature-settings-button", literature_app)
        self.assertNotIn("Workmode 文献项目已连接", literature_app)
        self.assertNotIn("SPECIALIZED · LITERATURE", literature_app)
        self.assertGreaterEqual(literature_app.count('className="modal-backdrop centered-dialog-backdrop"'), 3)
        self.assertIn("<PdfViewer", app)
        self.assertIn("<PdfViewer", literature_app)
        self.assertIn("media pdf", pdf_viewer)
        self.assertIn("fetch(src", pdf_viewer)
        self.assertIn("URL.createObjectURL", pdf_viewer)
        self.assertIn("URL.revokeObjectURL", pdf_viewer)
        self.assertIn("api.mediaUrl(activeProject.slug, pdfPath)", literature_api)
        self.assertIn("RUNTIME_API_BASE_KEY", literature_api)
        self.assertIn("LITERATURE_PROJECT_KEY", literature_api)
        self.assertIn("workmode-public-api-base", literature_navigation)
        self.assertIn("workmode-public-literature-project", literature_navigation)
        self.assertIn('target / "index.html"', backend_main)
        self.assertIn("createBackendLiteratureProject", literature_app)
        self.assertIn("removeBackendProject", literature_app)
        self.assertIn("新建文献项目", literature_app)
        self.assertIn("deleteBackendNote", literature_app)
        self.assertIn("删除笔记", literature_app)

    def test_literature_pdf_drop_requires_confirmation_without_fake_chat_messages(self) -> None:
        literature_app = LITERATURE_APP_SOURCE.read_text(encoding="utf-8")
        tauri_config = json.loads(TAURI_CONFIG.read_text(encoding="utf-8"))

        self.assertIn("pendingImportFiles", literature_app)
        self.assertIn("确认入库", literature_app)
        self.assertIn("confirmPendingImport", literature_app)
        self.assertFalse(
            tauri_config["app"]["windows"][0]["dragDropEnabled"],
            "Windows desktop must leave file drops to the HTML5 FileList handler",
        )
        self.assertNotIn("准备入库 ${pdfFiles.length} 篇 PDF", literature_app)
        self.assertNotIn("我会逐篇写入当前固定结构文献项目", literature_app)
        self.assertNotIn("篇文献已经进入当前 Workmode 文献项目", literature_app)

    def test_literature_overlays_are_not_forced_into_the_app_grid(self) -> None:
        styles = LITERATURE_STYLES.read_text(encoding="utf-8")

        shell_children = re.search(
            r"\.app-shell\s*>\s*:not\(\.skin-background-layer\)(?P<selector>[^\{]+)\{",
            styles,
        )
        self.assertIsNotNone(shell_children)
        self.assertIn(":not(.modal-backdrop)", shell_children.group("selector"))
        self.assertIn(":not(.drop-overlay)", shell_children.group("selector"))

        backdrop = re.search(r"\.modal-backdrop\s*\{(?P<body>[^}]*)\}", styles)
        self.assertIsNotNone(backdrop)
        self.assertRegex(backdrop.group("body"), r"position\s*:\s*fixed\s*;")
        self.assertRegex(backdrop.group("body"), r"place-items\s*:\s*center\s*;")

    def test_source_launcher_rejects_an_old_backend_on_the_fixed_port(self) -> None:
        launcher = SOURCE_LAUNCHER.read_text(encoding="utf-8")
        routes = BACKEND_ROUTES_SOURCE.read_text(encoding="utf-8")

        self.assertIn("ExpectedLiteratureContractVersion", launcher)
        self.assertIn("literature_project_contract_version", launcher)
        self.assertIn("ConvertFrom-Json", launcher)
        self.assertIn("incompatible Workmode backend", launcher)
        self.assertIn("$ExpectedLiteratureContractVersion = 5", launcher)
        self.assertIn('"literature_project_contract_version": 5', routes)

    def test_source_launcher_returns_only_the_backend_python_path(self) -> None:
        launcher = SOURCE_LAUNCHER.read_text(encoding="utf-8")

        self.assertIn("function Test-PythonInterpreter", launcher)
        self.assertIn("-PathType Leaf", launcher)
        self.assertIn("pip install --upgrade pip | Out-Host", launcher)
        self.assertIn("pip install -r $requirements | Out-Host", launcher)
        self.assertIn("Backend Python is not executable", launcher)
        self.assertIn("function Normalize-ProcessPathEnvironment", launcher)
        self.assertIn('SetEnvironmentVariable("PATH", $null, "Process")', launcher)

    def test_frontend_build_toolchain_is_not_a_runtime_dependency(self) -> None:
        package = json.loads(FRONTEND_PACKAGE.read_text(encoding="utf-8"))

        for dependency in ("@vitejs/plugin-react", "typescript", "vite"):
            self.assertNotIn(dependency, package["dependencies"])
            self.assertIn(dependency, package["devDependencies"])

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

    def test_assistant_markdown_list_markers_stay_inside_chat_bubbles(self) -> None:
        css = STYLES.read_text(encoding="utf-8")
        rule = re.search(r"\.message \.bubble ul,\s*\.message \.bubble ol\s*\{(?P<body>[^}]*)\}", css)

        self.assertIsNotNone(rule)
        self.assertRegex(rule.group("body"), r"padding-left\s*:\s*1\.5[45]em")
        self.assertRegex(rule.group("body"), r"margin\s*:")

    def test_tutorial_projects_expose_install_and_reset_actions(self) -> None:
        source = APP_SOURCE.read_text(encoding="utf-8")

        self.assertIn("创建教程项目", source)
        self.assertIn("重置教程", source)
        self.assertIn("activeProject?.is_tutorial", source)

    def test_first_run_guidance_and_achievements_have_replayable_ui(self) -> None:
        source = APP_SOURCE.read_text(encoding="utf-8") + ONBOARDING_SOURCE.read_text(encoding="utf-8")
        css = STYLES.read_text(encoding="utf-8")

        self.assertIn("重新播放工作台引导", source)
        self.assertIn("重新播放文献模式引导", source)
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

    def test_official_setup_links_use_scoped_system_browser_opener(self) -> None:
        desktop_source = DESKTOP_SOURCE.read_text(encoding="utf-8")
        permissions = json.loads(DESKTOP_CAPABILITIES.read_text(encoding="utf-8"))["permissions"]
        opener = next(item for item in permissions if isinstance(item, dict) and item.get("identifier") == "opener:allow-open-url")
        allowed_urls = {item["url"] for item in opener["allow"]}

        self.assertIn("openUrl(url)", desktop_source)
        self.assertEqual(allowed_urls, {
            "https://platform.deepseek.com/*",
            "https://api-docs.deepseek.com/*",
            "https://mineru.net/*",
            "https://bailian.console.aliyun.com/*",
            "https://help.aliyun.com/*",
            "mailto:*",
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

    def test_neon_space_lab_hud_uses_original_holographic_material_assets(self) -> None:
        css = STYLES.read_text(encoding="utf-8")

        self.assertTrue((NEON_ASSET_DIR / "glass-reflection.svg").is_file())
        self.assertTrue((NEON_ASSET_DIR / "surface-noise.svg").is_file())
        self.assertIn("--neon-material-glass", css)
        self.assertIn("--neon-hologram-edge", css)
        self.assertIn(".neon-hud-rail", css)
        self.assertNotIn("neon-corner-fastener", css)
        self.assertNotIn(".run/", css)
        self.assertNotIn("rainmeter", css.lower())

    def test_neon_space_lab_workspace_shares_holographic_material_tokens(self) -> None:
        css = STYLES.read_text(encoding="utf-8")

        self.assertIn("--neon-panel-glass", css)
        self.assertIn("--neon-panel-edge", css)
        self.assertIn("--neon-panel-highlight", css)
        self.assertIn("--neon-line-width: 2px", css)
        self.assertIn("--neon-content-radius: 4px", css)
        self.assertIn("background-color: var(--neon-panel-glass)", css)
        self.assertIn('data-theme="neon-space-lab"] .ai-panel-messages-shell', css)
        self.assertIn('data-theme="neon-space-lab"] .chat-input-box', css)
        self.assertIn('data-theme="neon-space-lab"] .file-view-panel', css)
        self.assertIn("--neon-bubble-shape", css)
        self.assertIn("clip-path: var(--neon-bubble-shape)", css)
        self.assertIn("--neon-panel-shape", css)
        self.assertIn("clip-path: var(--neon-panel-shape)", css)

    def test_settings_use_full_workspace_and_safe_declarative_skin_import(self) -> None:
        app_source = APP_SOURCE.read_text(encoding="utf-8")
        theme_panel = THEME_PANEL_SOURCE.read_text(encoding="utf-8")
        css = STYLES.read_text(encoding="utf-8")

        self.assertIn("settings-open", app_source)
        self.assertIn("settings-section-model", app_source)
        self.assertIn("customSkin={customSkin}", app_source)
        self.assertIn("parseSkinImportFile", theme_panel)
        self.assertIn("replaceOfficialSkinAssets", theme_panel)
        self.assertIn(".workmode-skin", theme_panel)
        self.assertIn(".settings-open .side-panel", css)
        self.assertIn("grid-column: 2 / -1", css)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", css)
        self.assertIn(".settings-open .achievement-grid", css)
        self.assertRegex(
            app_source,
            r'settings-section-memory[\s\S]+在聊天顶部显示工作记忆[\s\S]+</section>',
        )
        self.assertIn(".custom-skin-loader", css)
        self.assertIn("customSkin={customSkin}", app_source)
        self.assertIn("skinUsesChrome", app_source)
        self.assertIn('data-custom-skin-panel="continuous"', css)
        self.assertIn('data-custom-skin-bubble="continuous"', css)
        self.assertIn("var(--custom-skin-line-width, var(--neon-line-width, 1px))", css)

    def test_local_skin_library_supports_multi_import_and_persistent_dropdown_switching(self) -> None:
        app_source = APP_SOURCE.read_text(encoding="utf-8")
        theme_panel = THEME_PANEL_SOURCE.read_text(encoding="utf-8")
        skin_library_source = SKIN_LIBRARY_SOURCE.read_text(encoding="utf-8")

        self.assertIn("parseCustomSkinLibraryState", app_source)
        self.assertIn("customSkinLibrary={customSkinLibrary}", app_source)
        self.assertIn("multiple", theme_panel)
        self.assertIn("custom-skin-select", theme_panel)
        self.assertIn("activeSkinId", theme_panel)
        self.assertIn("version: 4", skin_library_source)
        self.assertIn("persisted.version !== 4", skin_library_source)
        self.assertIn("receipts", skin_library_source)
        self.assertIn("upsertOfficialSkins", skin_library_source)

    def test_skin_import_is_officially_signed_and_exposes_stable_content_slots(self) -> None:
        package = SKIN_PACKAGE_SOURCE.read_text(encoding="utf-8")
        library = SKIN_LIBRARY_SOURCE.read_text(encoding="utf-8")
        panel = THEME_PANEL_SOURCE.read_text(encoding="utf-8")
        app = APP_SOURCE.read_text(encoding="utf-8")
        signer = OFFICIAL_SKIN_SIGNER.read_text(encoding="utf-8")
        keys = OFFICIAL_SKIN_KEYS_SOURCE.read_text(encoding="utf-8")

        self.assertIn("workmode-skin-signature/v1", package)
        self.assertIn("crypto.subtle.verify", package)
        self.assertLess(package.index("verifyOfficialSignature"), package.index("parseDeclarativeSkin(strFromU8(manifestBytes))"))
        self.assertIn("layout.css", package)
        self.assertIn("visual.css", package)
        self.assertNotIn('accept=".json', panel)
        self.assertIn('accept=".workmode-skin', panel)
        self.assertIn("LEGACY_CUSTOM_SKIN_STORAGE_KEY", library)
        self.assertIn("generateKeyPairSync('ed25519')", signer)
        self.assertNotIn("PRIVATE KEY", keys)
        self.assertIn("workmode-official-2026-01", keys)
        for slot in (
            "app-shell", "app-chrome", "activity-navigation", "project-list", "file-tree",
            "session-list", "chat-workspace", "chat-header", "context-meter", "message-stream",
            "composer", "file-viewer", "status-bar", "settings-content",
        ):
            source = app + PRESET_CHROME_SOURCE.read_text(encoding="utf-8") + NEON_HUD_SOURCE.read_text(encoding="utf-8")
            self.assertIn(f'data-skin-slot="{slot}"', source)
        builder = OFFICIAL_SKIN_BUILDER.read_text(encoding="utf-8")
        self.assertIn("local-reference\\reward-skin-library", builder)
        self.assertIn("[string]$SourceRoot", builder)
        self.assertIn("[string]$PackageRoot", builder)
        self.assertNotIn('"skin-library\\sources"', builder)

    def test_reward_skin_maintenance_assets_stay_out_of_public_source_tree(self) -> None:
        self.assertFalse((ROOT / "skin-library" / "sources").exists())
        self.assertFalse((ROOT / "design" / "skin-lab").exists())
        self.assertFalse((ROOT / "examples" / "skins").exists())

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_green_phosphor_keeps_terminal_content_readable_and_role_aligned(self) -> None:
        layout = (SKIN_SOURCE_DIR / "green-phosphor" / "layout.css").read_text(encoding="utf-8")
        visual = (SKIN_SOURCE_DIR / "green-phosphor" / "visual.css").read_text(encoding="utf-8")

        self.assertIn('grid-template-columns: 42px minmax(0, 1fr) 42px', visual)
        self.assertIn('[data-skin-slot="message"].user::before', visual)
        self.assertIn('grid-column: 3', visual)
        self.assertIn('.message.user .bubble', visual)
        self.assertIn('grid-column: 2', visual)
        self.assertIn('justify-self: end', visual)
        self.assertIn('height: 24px', visual)
        self.assertIn('white-space: nowrap', visual)
        self.assertIn('text-overflow: ellipsis', visual)
        self.assertIn('.file-view-markdown', visual)
        self.assertIn('padding: 18px 20px', visual)
        self.assertIn('.file-view-markdown hr', visual)
        self.assertIn('border-top: 2px solid var(--phosphor-dim)', visual)
        self.assertIn('.tool-card-dot', visual)
        self.assertIn('flex-basis: 38px', visual)
        self.assertIn('textarea::placeholder', visual)
        self.assertIn('color: var(--phosphor-dim)', visual)
        self.assertIn('.ai-panel-header-top', visual)
        self.assertIn('grid-template-columns: minmax(0, 1fr) auto auto', visual)
        self.assertIn('.neon-context-copy', visual)
        self.assertIn('grid-template-columns: auto auto auto', visual)
        self.assertIn('minmax(450px, 1fr)', layout)
        self.assertIn('minmax(340px, 400px);', layout)
        self.assertNotIn('minmax(340px, 400px) !important', layout)

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_cream_puff_has_independent_soft_layout_without_demo_copy(self) -> None:
        layout = (SKIN_SOURCE_DIR / "cream-puff" / "layout.css").read_text(encoding="utf-8")
        visual = (SKIN_SOURCE_DIR / "cream-puff" / "visual.css").read_text(encoding="utf-8")
        manifest = json.loads((SKIN_SOURCE_DIR / "cream-puff" / "manifest.json").read_text(encoding="utf-8"))

        self.assertIn('gap: 10px', layout)
        self.assertIn('padding: 12px', layout)
        self.assertEqual(manifest["components"]["chrome"], "hud")
        self.assertIn('[data-skin-slot="app-chrome"]', layout)
        self.assertIn('grid-row: 1', layout)
        self.assertIn('[data-skin-slot="file-viewer"]', layout)
        self.assertIn('grid-column: 5', layout)
        self.assertIn('[data-skin-slot="settings"]', layout)
        self.assertIn('grid-column: 2 / -1', layout)
        self.assertIn('--cream: #fff8e9', visual)
        self.assertIn('border-radius: 24px', visual)
        self.assertIn('.activity-btn.active', visual)
        self.assertIn('.project-switcher', visual)
        self.assertIn('.message.assistant::before', visual)
        self.assertIn('content: "🐰"', visual)
        self.assertIn('.side-panel-title::before', visual)
        self.assertIn('content: "RESEARCH GARDEN"', visual)
        self.assertIn('.side-panel-title::after', visual)
        self.assertIn('content: "我的研究花园"', visual)
        self.assertIn('.neon-hud', visual)
        self.assertIn('display: flex', visual)
        self.assertIn('.neon-brand-ring', visual)
        self.assertIn('data:image/svg+xml', visual)
        self.assertIn('viewBox=%220%200%2048%2048%22', visual)
        self.assertIn('.neon-brand-ring::before,', visual)
        self.assertIn('.neon-brand-ring::after', visual)
        self.assertIn('content: "CREAM PUFF LAB"', visual)
        self.assertIn('.neon-mission span', visual)
        self.assertIn('display: none', visual)
        self.assertIn('.neon-mission small::before', visual)
        self.assertIn('.neon-context-cluster', visual)
        self.assertIn('grid-template-columns: auto minmax(0, 1fr) auto auto auto', visual)
        self.assertIn('max-width: 220px', visual)
        self.assertIn('.ai-panel-token-bar', visual)
        self.assertIn('display: none', visual)
        self.assertIn('.ai-panel::before', visual)
        self.assertIn('.editor-tabs::after', visual)
        self.assertIn('content: "♡"', visual)
        self.assertIn('.tool-card', visual)
        self.assertIn('.chat-input-wrap', visual)
        self.assertIn('.file-view-markdown', visual)
        self.assertIn('.ai-panel-token-bar', visual)
        self.assertIn('box-shadow:', visual)
        self.assertNotIn('MY LITTLE LAB', visual.upper())

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_neon_ice_has_independent_glass_hud_and_draggable_viewer(self) -> None:
        layout = (SKIN_SOURCE_DIR / "neon-ice" / "layout.css").read_text(encoding="utf-8")
        visual = (SKIN_SOURCE_DIR / "neon-ice" / "visual.css").read_text(encoding="utf-8")

        self.assertIn('[data-skin-slot="app-chrome"]', layout)
        self.assertIn('grid-row: 1', layout)
        self.assertIn('[data-skin-slot="file-viewer"]', layout)
        self.assertIn('grid-column: 5', layout)
        self.assertIn('minmax(340px, 420px);', layout)
        self.assertNotIn('minmax(340px, 420px) !important', layout)
        self.assertIn('--neon-ice: #66e8ff', visual)
        self.assertIn('.neon-hud', visual)
        self.assertIn('backdrop-filter: blur(18px)', visual)
        self.assertIn('border: 2px solid', visual)
        self.assertIn('.neon-context-cluster', visual)
        self.assertIn('.message.assistant .bubble', visual)
        self.assertIn('clip-path: none', visual)
        self.assertIn('.tool-card', visual)
        self.assertIn('.chat-input-wrap', visual)
        self.assertIn('.file-view-markdown', visual)
        self.assertNotIn('battery', visual.lower())
        self.assertNotIn('temperature', visual.lower())

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_cryo_gem_tech_has_independent_instrument_workbench(self) -> None:
        layout = (SKIN_SOURCE_DIR / "cryo-gem-tech" / "layout.css").read_text(encoding="utf-8")
        visual = (SKIN_SOURCE_DIR / "cryo-gem-tech" / "visual.css").read_text(encoding="utf-8")

        self.assertIn('grid-template-rows: 62px minmax(0, 1fr) 28px', layout)
        self.assertIn('[data-skin-slot="file-viewer"]', layout)
        self.assertIn('minmax(340px, 420px);', layout)
        self.assertNotIn('minmax(340px, 420px) !important', layout)
        self.assertIn('--cryo-cyan: #54dcff', visual)
        self.assertIn('.preset-chrome-gem-tech', visual)
        self.assertIn('.preset-chrome-emblem::before', visual)
        self.assertIn('.neon-context-cluster', visual)
        self.assertIn('.message.assistant .bubble', visual)
        self.assertIn('.tool-card', visual)
        self.assertIn('.file-view-markdown', visual)
        self.assertIn('backdrop-filter: blur(16px)', visual)
        self.assertIn('.message .bubble code,', visual)
        self.assertIn('color: #e8f7ff', visual)

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_midnight_console_has_independent_city_terminal_language(self) -> None:
        layout = (SKIN_SOURCE_DIR / "midnight-console" / "layout.css").read_text(encoding="utf-8")
        visual = (SKIN_SOURCE_DIR / "midnight-console" / "visual.css").read_text(encoding="utf-8")

        self.assertIn('grid-template-rows: 58px minmax(0, 1fr) 28px', layout)
        self.assertIn('[data-skin-slot="file-viewer"]', layout)
        self.assertIn('minmax(340px, 400px);', layout)
        self.assertNotIn('minmax(340px, 400px) !important', layout)
        self.assertIn('--midnight-coral: #eb6e70', visual)
        self.assertIn('.preset-chrome-console', visual)
        self.assertIn('.preset-chrome-emblem::after', visual)
        self.assertIn('.neon-context-cluster', visual)
        self.assertIn('.message.assistant::before', visual)
        self.assertIn('.tool-card', visual)
        self.assertIn('.chat-input-wrap', visual)
        self.assertIn('.file-view-markdown', visual)
        self.assertIn('.message .bubble code,', visual)
        self.assertIn('color: #f5e9d3', visual)

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_green_phosphor_reserves_space_for_terminal_file_and_session_ids(self) -> None:
        visual = (SKIN_SOURCE_DIR / "green-phosphor" / "visual.css").read_text(encoding="utf-8")

        self.assertIn('.tree-node-icon {', visual)
        self.assertIn('flex: 0 0 24px', visual)
        self.assertIn('.session-row-icon {', visual)
        self.assertIn('gap: 8px', visual)

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_cream_puff_hides_fallback_glyphs_behind_enamel_badges(self) -> None:
        visual = (SKIN_SOURCE_DIR / "cream-puff" / "visual.css").read_text(encoding="utf-8")

        self.assertIn(':is(.activity-icon, .tree-node-icon, .session-row-icon) {', visual)
        self.assertIn('font-size: 0 !important', visual)
        self.assertIn('.activity-bar-top .activity-icon::before', visual)
        self.assertIn('.activity-bar-bottom .activity-icon::before', visual)
        self.assertIn('.activity-bar-bottom .activity-btn.active .activity-icon::before', visual)
        self.assertIn('.mode-card-icon::before', visual)
        self.assertIn('.mode-card-literature .mode-card-icon::before', visual)

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_cryo_gem_tech_keeps_markdown_code_blocks_high_contrast(self) -> None:
        visual = (SKIN_SOURCE_DIR / "cryo-gem-tech" / "visual.css").read_text(encoding="utf-8")

        self.assertIn('.message-block.assistant .message-bubble pre', visual)
        self.assertIn('.message-block.user .message-bubble pre', visual)
        self.assertIn('.message-block.system .message-bubble pre', visual)
        self.assertIn('color: #e8f7ff', visual)
        self.assertIn('background: #071426', visual)
        self.assertIn('.message-block .message-bubble pre code', visual)
        self.assertIn('background: transparent', visual)

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_amethyst_observatory_has_independent_arcane_archive(self) -> None:
        layout = (SKIN_SOURCE_DIR / "amethyst-observatory" / "layout.css").read_text(encoding="utf-8")
        visual = (SKIN_SOURCE_DIR / "amethyst-observatory" / "visual.css").read_text(encoding="utf-8")

        self.assertIn('grid-template-rows: 62px minmax(0, 1fr) 28px', layout)
        self.assertIn('[data-skin-slot="file-viewer"]', layout)
        self.assertIn('minmax(350px, 430px);', layout)
        self.assertNotIn('minmax(350px, 430px) !important', layout)
        self.assertIn('--amethyst: #a766e8', visual)
        self.assertIn('.preset-chrome-observatory', visual)
        self.assertIn('.preset-chrome-emblem::after', visual)
        self.assertIn('.neon-context-cluster', visual)
        self.assertIn('.message .bubble', visual)
        self.assertIn('.tool-card', visual)
        self.assertIn('.file-view-markdown', visual)
        self.assertIn('radial-gradient(circle at 50% 50%', visual)

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_pixel_night_shift_uses_current_signed_skin_structure(self) -> None:
        layout = (PIXEL_SKIN_DIR / "layout.css").read_text(encoding="utf-8")
        visual = (PIXEL_SKIN_DIR / "visual.css").read_text(encoding="utf-8")
        manifest = json.loads((PIXEL_SKIN_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["id"], "pixel-night-shift")
        self.assertEqual(manifest["version"], "3.3.0")
        self.assertEqual(manifest["components"]["chrome"], "console")
        self.assertIn('grid-template-rows: 58px minmax(0, 1fr) 28px', layout)
        self.assertIn('--pixel-magenta: #ff4fa3', visual)
        self.assertIn('.preset-chrome-console', visual)
        self.assertIn('.message.assistant .bubble', visual)
        self.assertIn('clip-path: none', visual)
        self.assertIn('content: attr(data-tool-label)', visual)
        self.assertIn('grid-template-columns: minmax(0, 1fr) auto auto', visual)
        self.assertIn('.ai-panel-title,', visual)
        self.assertIn('width: 100%', visual)
        self.assertIn('display: flex', visual)
        self.assertIn('margin-left: auto', visual)
        self.assertIn('top: 50%', visual)
        self.assertIn('transform: translateY(-50%)', visual)
        self.assertIn('.activity-icon[data-skin-icon="project"]::before', visual)
        self.assertIn('.activity-icon[data-skin-icon="settings"]::before', visual)
        self.assertIn('.tree-node-icon[data-skin-icon="folder"]::before', visual)
        self.assertIn('.tree-node-icon[data-skin-icon="markdown"]::before', visual)
        self.assertIn('button[title="打开文件夹"]::before', visual)
        self.assertIn('button[title="刷新"]::before', visual)
        self.assertIn('/* Opposed refresh arrows */', visual)
        self.assertIn('/* Pixel waste-bin */', visual)
        self.assertIn('button[title="重命名"]::before', visual)
        self.assertIn('image-rendering: pixelated', visual)
        self.assertIn('.tool-card', visual)
        self.assertIn('.file-view-markdown', visual)

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_inkburst_lab_is_a_three_surface_native_skin(self) -> None:
        source = SKIN_SOURCE_DIR / "inkburst-lab"
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        layout = (source / "layout.css").read_text(encoding="utf-8")
        visual = (source / "visual.css").read_text(encoding="utf-8")

        self.assertEqual(manifest["id"], "inkburst-lab")
        self.assertEqual(manifest["version"], "1.0.2")
        self.assertEqual(manifest["foundation"], "light")
        self.assertEqual(manifest["components"]["chrome"], "console")
        self.assertEqual(manifest["palette"]["accent"], "#ff5fae")
        self.assertEqual(manifest["palette"]["accentAlt"], "#42d9c0")

        for slot in (
            "app-shell", "app-chrome", "activity-navigation", "workspace-sidebar",
            "chat-workspace", "file-viewer", "status-bar", "settings",
            "feature-hub", "feature-card", "literature-shell", "literature-workspace",
            "literature-library", "literature-conversation", "literature-paper",
            "literature-detail", "literature-memory", "literature-notes",
        ):
            self.assertIn(f'[data-skin-slot="{slot}"]', layout + visual)

        for selector in (
            ".mode-card", ".mode-hub-intro", ".preset-chrome-console",
            ".message.assistant .bubble", ".tool-card", ".file-view-markdown",
            ".paper-row", ".message-block.assistant .message-bubble",
            ".tool-event-card", ".paper-detail-modal", ".notes-workspace-modal",
        ):
            self.assertIn(selector, visual)

        self.assertIn("--inkburst-ink: #171427", visual)
        self.assertIn("--inkburst-hard-shadow: 7px 7px 0", visual)
        self.assertIn("@media (max-width: 1120px)", layout)
        self.assertNotIn("http://", layout + visual)
        self.assertNotIn("https://", layout + visual)
        self.assertNotIn("ACTIVE", visual)
        self.assertNotIn("TODAY · DISCUSSION ROUND", visual)

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_inkburst_lab_keeps_navigation_and_context_labels_legible(self) -> None:
        visual = (SKIN_SOURCE_DIR / "inkburst-lab" / "visual.css").read_text(encoding="utf-8")

        self.assertIn(".mode-card-literature:hover", visual)
        self.assertIn("background: var(--inkburst-aqua);", visual)
        self.assertIn("grid-template-columns: max-content minmax(180px, 1fr) minmax(470px, 560px) max-content max-content;", visual)
        self.assertIn('.activity-icon[data-skin-icon="settings"] {', visual)
        self.assertIn("font-size: 0 !important;", visual)
        self.assertRegex(
            visual,
            r"(?s)\.ai-panel-token-bar\s*\{[^}]*height:\s*22px;",
        )
        self.assertRegex(
            visual,
            r"(?s)\.context-meter\s*\{[^}]*padding:\s*6px 9px 7px;",
        )
        self.assertRegex(
            visual,
            r"(?s)\.message-block\.user\s*\{[^}]*margin-left:\s*auto;[^}]*margin-right:\s*0;",
        )

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_pixel_night_shift_is_a_three_surface_native_skin(self) -> None:
        source = SKIN_SOURCE_DIR / "pixel-night-shift"
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        layout = (source / "layout.css").read_text(encoding="utf-8")
        visual = (source / "visual.css").read_text(encoding="utf-8")

        self.assertEqual(manifest["id"], "pixel-night-shift")
        self.assertEqual(manifest["version"], "3.3.0")
        self.assertEqual(manifest["typography"]["preset"], "pixel")
        self.assertEqual(manifest["components"]["messages"], "pixel")

        for slot in (
            "feature-hub", "feature-card", "app-shell", "app-chrome",
            "activity-navigation", "workspace-sidebar", "chat-workspace",
            "file-viewer", "status-bar", "settings", "literature-shell",
            "literature-workspace", "literature-library", "literature-conversation",
            "literature-paper", "literature-detail", "literature-memory", "literature-notes",
        ):
            self.assertIn(f'[data-skin-slot="{slot}"]', layout + visual)

        for selector in (
            ".mode-hub-intro", ".mode-card", ".mode-card-literature",
            ".paper-row", ".conversation-header", ".context-meter",
            ".message-block.user", ".message-block.assistant .message-bubble",
            ".tool-event-card", ".composer", ".paper-detail-modal",
            ".memory-popover", ".notes-workspace-modal", ".pdf-viewer-shell",
        ):
            self.assertIn(selector, visual)

        self.assertRegex(
            visual,
            r"(?s)\.message-block\.user\s*\{[^}]*margin-left:\s*auto;[^}]*margin-right:\s*0;",
        )
        self.assertIn("@media (max-width: 1340px)", layout)
        self.assertNotIn("http://", layout + visual)
        self.assertNotIn("https://", layout + visual)

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_green_phosphor_is_a_three_surface_native_skin(self) -> None:
        source = SKIN_SOURCE_DIR / "green-phosphor"
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        layout = (source / "layout.css").read_text(encoding="utf-8")
        visual = (source / "visual.css").read_text(encoding="utf-8")

        self.assertEqual(manifest["id"], "green-phosphor-terminal")
        self.assertEqual(manifest["version"], "4.2.1")
        self.assertEqual(manifest["material"]["preset"], "crt")
        self.assertEqual(manifest["components"]["messages"], "log")

        for slot in (
            "feature-hub", "feature-card", "app-shell", "app-chrome",
            "activity-navigation", "workspace-sidebar", "chat-workspace",
            "file-viewer", "status-bar", "settings", "literature-shell",
            "literature-workspace", "literature-library", "literature-conversation",
            "literature-paper", "literature-detail", "literature-memory", "literature-notes",
        ):
            self.assertIn(f'[data-skin-slot="{slot}"]', layout + visual)

        for selector in (
            ".mode-hub-intro", ".mode-card", ".mode-card-literature",
            ".paper-row", ".conversation-header", ".context-meter",
            ".message-block.user", ".message-block.assistant .message-bubble",
            ".tool-event-card", ".composer", ".paper-detail-modal",
            ".memory-popover", ".notes-workspace-modal", ".pdf-viewer-shell",
        ):
            self.assertIn(selector, visual)

        self.assertRegex(
            visual,
            r"(?s)\.message-block\.user\s*\{[^}]*margin-left:\s*auto;[^}]*margin-right:\s*0;",
        )
        self.assertIn('[data-skin-slot="chat-workspace"] [data-skin-slot="message"]', visual)
        self.assertIn('[data-skin-slot="chat-workspace"] [data-skin-slot="composer"]', visual)
        self.assertIn('[data-skin-slot="literature-conversation"] > [data-skin-slot="message-stream"]', visual)
        self.assertIn('[data-skin-slot="literature-conversation"] .message-block', visual)
        self.assertIn("@media (max-width: 1320px)", layout)
        self.assertNotIn("http://", layout + visual)
        self.assertNotIn("https://", layout + visual)

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_parallel_reward_skin_migrations_cover_all_three_surfaces(self) -> None:
        expected = {
            "amethyst-observatory": ("amethyst-observatory", "3.3.0"),
            "cream-puff": ("cream-puff-v3", "3.4.1"),
            "cryo-gem-tech": ("cryo-gem-tech", "3.3.1"),
            "midnight-console": ("midnight-console", "3.3.0"),
            "neon-ice": ("neon-ice-v3", "3.3.0"),
        }
        required_slots = (
            "feature-hub", "feature-card", "app-shell", "app-chrome",
            "activity-navigation", "workspace-sidebar", "chat-workspace",
            "file-viewer", "status-bar", "settings", "literature-shell",
            "literature-workspace", "literature-library", "literature-conversation",
            "literature-paper", "literature-detail", "literature-memory", "literature-notes",
        )
        required_selectors = (
            ".mode-hub-intro", ".mode-card", ".mode-card-literature",
            ".paper-row", ".conversation-header", ".context-meter",
            ".message-block.user", ".message-block.assistant .message-bubble",
            ".tool-event-card", ".composer", ".paper-detail-modal",
            ".memory-popover", ".notes-workspace-modal", ".pdf-viewer-shell",
        )

        for source_name, (skin_id, version) in expected.items():
            with self.subTest(skin=source_name):
                source = SKIN_SOURCE_DIR / source_name
                manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
                layout = (source / "layout.css").read_text(encoding="utf-8")
                visual = (source / "visual.css").read_text(encoding="utf-8")
                css = layout + visual

                self.assertEqual(manifest["id"], skin_id)
                self.assertEqual(manifest["version"], version)
                for slot in required_slots:
                    self.assertIn(f'[data-skin-slot="{slot}"]', css)
                for selector in required_selectors:
                    self.assertIn(selector, visual)
                self.assertRegex(
                    visual,
                    r"(?s)\.message-block\.user\s*\{[^}]*margin-left:\s*auto;[^}]*margin-right:\s*0;",
                )
                self.assertNotRegex(css, r"(?i)url\(\s*['\"]?https?://")
                self.assertNotRegex(css, r"(?i)@import\s+.*https?://")

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_every_reward_skin_has_theme_specific_navigation_file_and_control_icons(self) -> None:
        expected_versions = {
            "amethyst-observatory": "3.3.0",
            "cream-puff": "3.4.1",
            "cryo-gem-tech": "3.3.1",
            "green-phosphor": "4.2.1",
            "inkburst-lab": "1.0.2",
            "midnight-console": "3.3.0",
            "neon-ice": "3.3.0",
            "pixel-night-shift": "3.3.0",
        }
        required_selectors = (
            '.activity-icon[data-skin-icon="project"]::before',
            '.activity-icon[data-skin-icon="settings"]::before',
            '.tree-node-icon[data-skin-icon="folder"]::before',
            '.tree-node-icon[data-skin-icon="markdown"]::before',
            'button[title="打开文件夹"]::before',
            'button[title="刷新"]::before',
            'button[title="重命名"]::before',
        )

        for directory, version in expected_versions.items():
            with self.subTest(skin=directory):
                source = SKIN_SOURCE_DIR / directory
                manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
                visual = (source / "visual.css").read_text(encoding="utf-8")
                self.assertEqual(manifest["version"], version)
                for selector in required_selectors:
                    self.assertIn(selector, visual)

    @unittest.skipUnless(PRIVATE_REWARD_SKINS_AVAILABLE, "private reward skin library is not present")
    def test_every_reward_skin_reserves_file_and_session_icon_slots(self) -> None:
        for source in sorted(SKIN_SOURCE_DIR.iterdir()):
            if not source.is_dir():
                continue
            with self.subTest(skin=source.name):
                visual = (source / "visual.css").read_text(encoding="utf-8")
                self.assertRegex(
                    visual,
                    r'(?s)\.tree-node-icon\s*\{[^}]*flex:\s*0 0 24px;',
                )
                self.assertRegex(
                    visual,
                    r'(?s)\.session-row-icon\s*\{[^}]*flex:\s*0 0 24px;',
                )
                self.assertRegex(
                    visual,
                    r'(?s)\.tree-node,\s*\n[^{}]*\.session-row\s*\{[^}]*gap:\s*8px;',
                )

    def test_v2_skin_material_engine_uses_bounded_presets(self) -> None:
        custom_skin_source = SKIN_PROTOCOL_SOURCE.read_text(encoding="utf-8")
        css = STYLES.read_text(encoding="utf-8")

        self.assertIn("workmode-skin/v1", custom_skin_source)
        self.assertIn("workmode-skin/v2", custom_skin_source)
        self.assertIn("soft-cream", custom_skin_source)
        self.assertIn("notebook", custom_skin_source)
        self.assertIn('data-custom-skin-material="soft-cream"', css)
        self.assertIn('data-custom-skin-decoration="notebook"', css)
        self.assertIn("--custom-skin-shadow-alpha", css)
        self.assertIn("border-radius: var(--custom-skin-panel-radius", css)
        self.assertIn("border-radius: var(--custom-skin-bubble-radius", css)
        self.assertIn("border-radius: var(--custom-skin-button-radius", css)
        self.assertNotIn("data:text/css", css)

    def test_v3_skin_engine_keeps_assets_local_and_declarative(self) -> None:
        protocol = SKIN_PROTOCOL_SOURCE.read_text(encoding="utf-8")
        package = SKIN_PACKAGE_SOURCE.read_text(encoding="utf-8")
        runtime_css = SKIN_RUNTIME_STYLES.read_text(encoding="utf-8")
        theme_panel = THEME_PANEL_SOURCE.read_text(encoding="utf-8")
        tauri = json.loads(TAURI_CONFIG.read_text(encoding="utf-8"))

        self.assertIn("workmode-skin/v3", protocol)
        self.assertIn("isSafeSkinAssetPath", protocol)
        self.assertIn("unzipSync", package)
        self.assertIn("SKIN_PACKAGE_MAX_UNCOMPRESSED_BYTES", package)
        self.assertIn("文件签名", package)
        self.assertIn("replaceOfficialSkinAssets", theme_panel)
        self.assertIn('data-skin-material="obsidian"', runtime_css)
        self.assertIn('data-skin-icons="terminal"', runtime_css)
        self.assertIn('data-skin-effect-glow="true"', runtime_css)
        self.assertIn('data-skin-effect-crt="true"', runtime_css)
        self.assertIn('data-skin-effect-stars="true"', runtime_css)
        self.assertIn('data-skin-effect-paper="true"', runtime_css)
        self.assertIn('data-skin-edge-profile="beveled"', runtime_css)
        self.assertIn('data-skin-edge-profile="stepped"', runtime_css)
        self.assertIn("corner-shape: bevel", runtime_css)
        self.assertIn("corner-shape: notch", runtime_css)
        self.assertIn("clip-path: polygon", runtime_css)
        self.assertNotIn("--skin-clip-path", runtime_css)
        self.assertIn("--skin-background-image", runtime_css)
        self.assertIn("--skin-decoration-overlay-image", runtime_css)
        self.assertIn('className="skin-decoration-overlay"', APP_SOURCE.read_text(encoding="utf-8"))
        self.assertRegex(runtime_css, r"\.skin-decoration-overlay\s*\{[^}]*pointer-events:\s*none")
        self.assertIn("font-src 'self' data: blob:", tauri["app"]["security"]["csp"])

    def test_every_structural_skin_keeps_the_workspace_in_the_middle_grid_row(self) -> None:
        css = SKIN_RUNTIME_STYLES.read_text(encoding="utf-8")

        self.assertRegex(
            css,
            r"\.ide-shell\.hud-layout\s*>\s*\.preset-chrome\s*\{[^}]*grid-row\s*:\s*1",
        )
        for selector in ("activity-bar", "side-panel", "ai-panel", "resize-handle", "file-view-panel"):
            self.assertRegex(
                css,
                rf"\.ide-shell\.hud-layout\s*>[^{{]*\.{selector}[^{{]*\{{[^}}]*grid-row\s*:\s*2",
            )
        self.assertRegex(
            css,
            r"\.ide-shell\.hud-layout\s*>\s*\.status-bar\s*\{[^}]*grid-row\s*:\s*3",
        )

    def test_v3_semantic_icon_slots_are_wired_to_live_ui(self) -> None:
        app = APP_SOURCE.read_text(encoding="utf-8")
        protocol = SKIN_PROTOCOL_SOURCE.read_text(encoding="utf-8")
        runtime_css = SKIN_RUNTIME_STYLES.read_text(encoding="utf-8")

        for slot in ("session", "tool-running", "tool-done", "tool-error"):
            self.assertIn(f"'{slot}'", protocol)
            self.assertIn(f'data-skin-icon-{slot}="asset"', runtime_css)
            self.assertRegex(
                runtime_css,
                rf'data-skin-icon-{slot}="asset"\] \.skin-icon\[data-skin-icon="{slot}"\]\s*\{{',
            )

        self.assertIn('data-skin-icon="session"', app)
        self.assertIn("data-skin-icon={toolIconSlot}", app)
        self.assertIn("data-tool-label={toolLabel}", app)
        self.assertIn("toolStatusSkinIcon(item.status)", app)
        self.assertIn('.tool-card.cancelled .skin-icon[data-skin-icon="tool-error"]::before', runtime_css)

    def test_console_and_gem_chrome_use_only_real_runtime_status(self) -> None:
        protocol = SKIN_PROTOCOL_SOURCE.read_text(encoding="utf-8")
        registry = SKIN_CHROME_SOURCE.read_text(encoding="utf-8")
        renderer = PRESET_CHROME_SOURCE.read_text(encoding="utf-8")
        runtime_css = SKIN_RUNTIME_STYLES.read_text(encoding="utf-8")

        for preset in ("console", "gem-tech"):
            self.assertIn(f"'{preset}'", protocol)
            self.assertIn(f"'{preset}'", registry)
            self.assertIn(f"'{preset}'", renderer)
            self.assertIn(f".preset-chrome-{preset}", runtime_css)

        for runtime_field in ("projectName", "projectPath", "modelName", "streaming", "status"):
            self.assertIn(runtime_field, renderer)
        for fake_telemetry in ("battery", "temperature", "signalStrength", "cpuUsage", "uptime"):
            self.assertNotIn(fake_telemetry, renderer)

    def test_instrument_context_and_indexed_recipes_keep_real_ui_data(self) -> None:
        protocol = SKIN_PROTOCOL_SOURCE.read_text(encoding="utf-8")
        runtime_css = SKIN_RUNTIME_STYLES.read_text(encoding="utf-8")
        app = APP_SOURCE.read_text(encoding="utf-8")

        for preset in ("instrument", "signal", "gem", "indexed"):
            self.assertIn(f"'{preset}'", protocol)
        for selector in (
            'data-skin-tools="instrument"',
            'data-skin-context="signal"',
            'data-skin-context="gem"',
            'data-skin-file-tree="indexed"',
        ):
            self.assertIn(selector, runtime_css)
        self.assertIn("--context-pct", app)
        self.assertIn("contextPct", app)
        self.assertIn("entry.name", app)
        self.assertIn("entry.path", app)

    def test_quick_bug_report_uses_local_qr_and_sanitized_email_channel(self) -> None:
        app = APP_SOURCE.read_text(encoding="utf-8")
        report = BUG_REPORT_SOURCE.read_text(encoding="utf-8")
        dialog = BUG_REPORT_DIALOG_SOURCE.read_text(encoding="utf-8")
        capabilities = json.loads(DESKTOP_CAPABILITIES.read_text(encoding="utf-8"))

        self.assertTrue(SUPPORT_QR_SOURCE.read_bytes().startswith(b"\xff\xd8\xff"))
        self.assertGreater(SUPPORT_QR_SOURCE.stat().st_size, 1_000)
        self.assertIn("BugReportDialog", app)
        self.assertIn("support-public-account-qr.jpg", dialog)
        self.assertIn("yantianxue_skye@qq.com", report)
        self.assertNotIn("root_path", report)
        self.assertNotIn("model_api_key", report)

        opener = next(
            item for item in capabilities["permissions"]
            if isinstance(item, dict) and item.get("identifier") == "opener:allow-open-url"
        )
        allowed_urls = [item["url"] for item in opener["allow"]]
        self.assertIn("mailto:*", allowed_urls)

    def test_bug_report_generates_a_local_zip_and_reveals_it_without_uploading(self) -> None:
        desktop = DESKTOP_SOURCE.read_text(encoding="utf-8")
        desktop_lib = DESKTOP_LIB_SOURCE.read_text(encoding="utf-8")
        dialog = BUG_REPORT_DIALOG_SOURCE.read_text(encoding="utf-8")
        capabilities = json.loads(DESKTOP_CAPABILITIES.read_text(encoding="utf-8"))

        self.assertIn("desktop_generate_bug_report", desktop)
        self.assertIn("desktop_generate_bug_report", desktop_lib)
        self.assertIn("revealItemInDir", desktop)
        self.assertIn("一键生成错误报告", dialog)
        self.assertIn("opener:allow-reveal-item-in-dir", capabilities["permissions"])
        self.assertNotIn("fetch(", dialog)
        self.assertNotIn("upload", dialog.lower())

    @unittest.skipUnless(PRIVATE_LEGACY_EXAMPLES_AVAILABLE, "private legacy skin fixtures are not present")
    def test_skin_lab_representative_examples_keep_their_baseline_recipes(self) -> None:
        cream = json.loads(CREAM_SKIN_EXAMPLE.read_text(encoding="utf-8"))
        green = json.loads(GREEN_SKIN_EXAMPLE.read_text(encoding="utf-8"))
        amethyst = json.loads(AMETHYST_SKIN_EXAMPLE.read_text(encoding="utf-8"))

        self.assertEqual(
            (cream["schema"], cream["material"]["preset"]),
            ("workmode-skin/v2", "soft-cream"),
        )
        self.assertEqual(
            green["components"],
            {"chrome": "terminal", "messages": "log", "tools": "terminal", "context": "bar", "fileTree": "terminal"},
        )
        self.assertEqual(
            amethyst["components"],
            {"chrome": "observatory", "messages": "manuscript", "tools": "ritual", "context": "dial", "fileTree": "archive"},
        )



if __name__ == "__main__":
    unittest.main()
