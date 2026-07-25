from __future__ import annotations

import unittest


class CitationStyleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.groups = [
            {
                "instance_id": "group-a",
                "items": [
                    {
                        "project_slug": "library",
                        "paper_id": "paper-a",
                        "metadata": {
                            "title": "Catalyst Study",
                            "authors": "Zhang, San; Li, Si",
                            "year": 2026,
                            "journal": "ACS Catalysis",
                            "doi": "10.1000/a",
                        },
                        "locator": {"label": "page", "value": "12-14"},
                        "prefix": "参见",
                        "suffix": "",
                        "suppress_author": False,
                    },
                    {
                        "project_slug": "library",
                        "paper_id": "paper-b",
                        "metadata": {
                            "title": "Second Study",
                            "authors": "Wang, Wu",
                            "year": 2025,
                            "journal": "Nature",
                        },
                        "locator": None,
                        "prefix": "",
                        "suffix": "及其补充材料",
                        "suppress_author": False,
                    },
                ],
            }
        ]

    def test_lists_the_five_supported_csl_profiles(self) -> None:
        from app.citation_styles import citation_style_options

        self.assertEqual(
            [item["id"] for item in citation_style_options()],
            [
                "gb-t-7714-2015-numeric",
                "american-chemical-society",
                "nature",
                "apa-7th",
                "vancouver",
            ],
        )

    def test_renders_grouped_citations_and_bibliographies_for_every_style(self) -> None:
        from app.citation_styles import render_citation_document

        for style_id in (
            "gb-t-7714-2015-numeric",
            "american-chemical-society",
            "nature",
            "apa-7th",
            "vancouver",
        ):
            with self.subTest(style=style_id):
                rendered = render_citation_document(self.groups, style_id)
                self.assertEqual(set(rendered["citation_texts"]), {"group-a"})
                self.assertIn("12-14", rendered["citation_texts"]["group-a"])
                self.assertIn("参见", rendered["citation_texts"]["group-a"])
                self.assertIn("及其补充材料", rendered["citation_texts"]["group-a"])
                self.assertEqual(len(rendered["bibliography_entries"]), 2)
                self.assertTrue(all(entry.strip() for entry in rendered["bibliography_entries"]))

    def test_apa_suppress_author_keeps_year_and_locator(self) -> None:
        from app.citation_styles import render_citation_document

        self.groups[0]["items"] = [dict(self.groups[0]["items"][0], suppress_author=True)]
        text = render_citation_document(self.groups, "apa-7th")["citation_texts"]["group-a"]

        self.assertIn("2026", text)
        self.assertIn("12-14", text)
        self.assertNotIn("Zhang", text)


if __name__ == "__main__":
    unittest.main()
