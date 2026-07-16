from __future__ import annotations

import threading
import unittest
from unittest.mock import patch

from app.project_tools import execute_project_tool, project_tool_names
from app.web_tools import (
    WebToolResult,
    WebToolError,
    execute_web_tool,
    parse_duckduckgo_html,
    run_web_fetch,
    run_web_search,
    validate_public_web_url,
    web_tool_names,
)


PUBLIC_IP = ["93.184.216.34"]


class WebToolsTest(unittest.TestCase):
    def test_tool_names_are_fixed_loaded(self):
        self.assertEqual(web_tool_names(), {"web_search", "web_fetch"})
        self.assertTrue(web_tool_names().issubset(project_tool_names()))

    @patch("app.web_tools.run_web_search")
    def test_failed_search_result_does_not_report_success(self, mocked_search):
        mocked_search.return_value = {
            "engine": "duckduckgo-html",
            "queries": ["test"],
            "results": [],
            "errors": [{"query": "test", "error": "network unavailable"}],
        }

        result = execute_web_tool("web_search", {"queries": ["test"]})

        self.assertFalse(result.ok)

    @patch("app.project_tools.execute_web_tool", return_value=WebToolResult(ok=True, content='{"results": []}'))
    def test_web_tool_dispatch_does_not_require_a_project_lookup(self, mocked):
        result = execute_project_tool("missing-project", "web_search", {"queries": ["test"]})

        self.assertTrue(result.ok)
        mocked.assert_called_once()

    def test_public_url_validation_blocks_local_network_and_unsafe_schemes(self):
        blocked = [
            "file:///etc/passwd",
            "http://localhost/admin",
            "http://127.0.0.1:8000/health",
            "http://169.254.169.254/latest/meta-data",
            "http://198.18.0.10/",
            "https://user:pass@example.com/",
            "https://example.com:22/",
        ]
        for url in blocked:
            with self.subTest(url=url), self.assertRaises(WebToolError):
                validate_public_web_url(url)

        normalized = validate_public_web_url(
            "https://example.com/paper?q=1",
            resolver=lambda _host: PUBLIC_IP,
        )
        self.assertEqual(normalized, "https://example.com/paper?q=1")

        proxied = validate_public_web_url(
            "https://example.com/proxied",
            resolver=lambda _host: ["198.18.0.10"],
        )
        self.assertEqual(proxied, "https://example.com/proxied")

    def test_duckduckgo_parser_extracts_title_url_and_plain_snippet(self):
        source = """
        <div class="result">
          <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpaper">
            Paper &amp; Notes
          </a>
          <a class="result__snippet">A useful <b>research</b> result.</a>
        </div>
        """

        results = parse_duckduckgo_html(source, max_results=3)

        self.assertEqual(
            results,
            [{"title": "Paper & Notes", "url": "https://example.com/paper", "snippet": "A useful research result."}],
        )

    @patch("app.web_tools._duckduckgo_search_one")
    def test_default_search_provider_is_duckduckgo_html(self, mocked_search):
        mocked_search.return_value = [
            {"title": "Result", "url": "https://example.com/result", "snippet": "ok"}
        ]

        result = run_web_search(["alpha"])

        self.assertEqual(result["engine"], "duckduckgo-html")
        self.assertEqual(result["results"][0]["title"], "Result")
        mocked_search.assert_called_once_with("alpha", 5)

    def test_search_queries_run_in_parallel_and_preserve_query_order(self):
        barrier = threading.Barrier(3)

        def fake_search(query: str, _max_results: int):
            barrier.wait(timeout=2)
            return [{"title": query.upper(), "url": f"https://example.com/{query}", "snippet": query}]

        result = run_web_search(["alpha", "beta", "gamma"], search_one=fake_search)

        self.assertEqual([item["query"] for item in result["results"]], ["alpha", "beta", "gamma"])

    def test_fetch_urls_run_in_parallel(self):
        barrier = threading.Barrier(2)

        def fake_fetch(url: str, _max_chars: int):
            barrier.wait(timeout=2)
            return {"url": url, "status": 200, "content_type": "text/plain", "text": "ok", "truncated": False}

        result = run_web_fetch(
            ["https://example.com/a", "https://example.com/b"],
            fetch_one=fake_fetch,
        )

        self.assertEqual([item["url"] for item in result["documents"]], ["https://example.com/a", "https://example.com/b"])


if __name__ == "__main__":
    unittest.main()
