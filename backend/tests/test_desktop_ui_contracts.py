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

    def test_desktop_icon_source_is_the_requested_origin_ring_logo(self) -> None:
        self.assertTrue(ICON_SOURCE.is_file())
        digest = hashlib.sha256(ICON_SOURCE.read_bytes()).hexdigest()
        self.assertEqual(
            digest,
            "babe8653fed220c5b4c51c69a45a4649be4298e40380c82d82c4e37af232ec58",
        )


if __name__ == "__main__":
    unittest.main()
