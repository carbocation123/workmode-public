from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STYLES = ROOT / "frontend" / "src" / "styles.css"
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


if __name__ == "__main__":
    unittest.main()
