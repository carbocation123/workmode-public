from __future__ import annotations

import html
import ipaddress
import json
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

import httpx


MAX_QUERIES = 5
MAX_RESULTS_PER_QUERY = 8
MAX_FETCH_URLS = 4
DEFAULT_FETCH_CHARS = 12_000
MAX_FETCH_CHARS = 20_000
MAX_HTTP_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
WEB_TIMEOUT_SECONDS = 20
USER_AGENT = "WorkmodePublic/0.2 (+https://github.com/carbocation123/workmode-public)"
SYNTHETIC_PROXY_NETWORK = ipaddress.ip_network("198.18.0.0/15")


class WebToolError(Exception):
    pass


@dataclass(frozen=True)
class WebToolResult:
    ok: bool
    content: str


WEB_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "并行搜索公开网页。一次可提交 1–5 个检索式，返回标题、URL、摘要和对应 query。适合文献调研的多组关键词检索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": MAX_QUERIES,
                        "description": "并行执行的检索式，建议针对同一问题写 2–4 种表达",
                    },
                    "max_results_per_query": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_RESULTS_PER_QUERY,
                        "default": 5,
                    },
                },
                "required": ["queries"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "并行读取 1–4 个公开 HTTP(S) 网页并提取正文文本。拒绝 localhost、私网、云元数据地址、非标准端口和非文本响应。",
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": MAX_FETCH_URLS,
                    },
                    "max_chars_per_url": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": MAX_FETCH_CHARS,
                        "default": DEFAULT_FETCH_CHARS,
                    },
                },
                "required": ["urls"],
            },
        },
    },
]


def web_tool_names() -> set[str]:
    return {item["function"]["name"] for item in WEB_TOOL_SCHEMAS}


def execute_web_tool(
    name: str,
    args: dict[str, Any],
    *,
    cancel_event: threading.Event | None = None,
) -> WebToolResult:
    try:
        _raise_if_cancelled(cancel_event)
        if name == "web_search":
            queries = _string_list(args, "queries", MAX_QUERIES)
            max_results = _bounded_int(args, "max_results_per_query", 5, 1, MAX_RESULTS_PER_QUERY)
            payload = run_web_search(queries, max_results_per_query=max_results, cancel_event=cancel_event)
        elif name == "web_fetch":
            urls = _string_list(args, "urls", MAX_FETCH_URLS)
            max_chars = _bounded_int(args, "max_chars_per_url", DEFAULT_FETCH_CHARS, 1000, MAX_FETCH_CHARS)
            payload = run_web_fetch(urls, max_chars_per_url=max_chars, cancel_event=cancel_event)
        else:
            raise WebToolError(f"未知网络工具：{name}")
        ok = not payload.get("errors") and any(
            item.get("ok", True) for item in payload.get("documents", payload.get("results", []))
        )
        return WebToolResult(ok=ok, content=json.dumps(payload, ensure_ascii=False, indent=2))
    except WebToolError as exc:
        return WebToolResult(ok=False, content=f"ERROR: {exc}")
    except Exception as exc:
        return WebToolResult(ok=False, content=f"ERROR: 网络工具执行失败：{exc}")


def run_web_search(
    queries: list[str],
    *,
    max_results_per_query: int = 5,
    search_one: Callable[[str, int], list[dict[str, str]]] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    cleaned = _clean_items(queries, MAX_QUERIES, "queries")
    max_results = min(max(1, int(max_results_per_query)), MAX_RESULTS_PER_QUERY)
    worker = search_one or _duckduckgo_search_one
    results: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    def execute(query: str) -> tuple[str, list[dict[str, str]], str | None]:
        _raise_if_cancelled(cancel_event)
        try:
            return query, worker(query, max_results), None
        except Exception as exc:
            return query, [], str(exc)

    with ThreadPoolExecutor(max_workers=min(4, len(cleaned)), thread_name_prefix="web-search") as pool:
        for query, items, error in pool.map(execute, cleaned):
            _raise_if_cancelled(cancel_event)
            if error:
                errors.append({"query": query, "error": error[:500]})
                continue
            for item in items[:max_results]:
                results.append({"query": query, **item})
    return {"queries": cleaned, "results": results, "errors": errors}


def run_web_fetch(
    urls: list[str],
    *,
    max_chars_per_url: int = DEFAULT_FETCH_CHARS,
    fetch_one: Callable[[str, int], dict[str, Any]] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    cleaned = _clean_items(urls, MAX_FETCH_URLS, "urls")
    max_chars = min(max(1000, int(max_chars_per_url)), MAX_FETCH_CHARS)
    worker = fetch_one or _fetch_one_url
    documents: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    def execute(url: str) -> tuple[str, dict[str, Any] | None, str | None]:
        _raise_if_cancelled(cancel_event)
        try:
            return url, worker(url, max_chars), None
        except Exception as exc:
            return url, None, str(exc)

    with ThreadPoolExecutor(max_workers=min(4, len(cleaned)), thread_name_prefix="web-fetch") as pool:
        for url, document, error in pool.map(execute, cleaned):
            _raise_if_cancelled(cancel_event)
            if error:
                errors.append({"url": url, "error": error[:500]})
                documents.append({"url": url, "ok": False, "error": error[:500]})
            elif document is not None:
                documents.append({"ok": True, **document})
    return {"documents": documents, "errors": errors}


def validate_public_web_url(
    url: str,
    *,
    resolver: Callable[[str], list[str]] | None = None,
) -> str:
    if not isinstance(url, str) or not url.strip():
        raise WebToolError("URL 不能为空")
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except ValueError as exc:
        raise WebToolError(f"URL 无效：{exc}") from exc
    if parsed.scheme.lower() not in {"http", "https"}:
        raise WebToolError("只允许 http/https URL")
    if parsed.username or parsed.password:
        raise WebToolError("URL 不允许携带用户名或密码")
    if not parsed.hostname:
        raise WebToolError("URL 缺少主机名")
    if port is not None and port not in {80, 443}:
        raise WebToolError("只允许标准 Web 端口 80/443")

    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise WebToolError("禁止访问 localhost")
    try:
        direct_ip = ipaddress.ip_address(host)
    except ValueError:
        direct_ip = None
    addresses = [str(direct_ip)] if direct_ip is not None else (resolver or _resolve_host_ips)(host)
    if not addresses:
        raise WebToolError("主机名没有可用地址")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise WebToolError(f"DNS 返回无效地址：{address}") from exc
        # Clash/TUN and managed sandboxes commonly map public domains into the
        # RFC 2544 benchmarking range, then route them through a proxy. Keep
        # literal 198.18/15 URLs blocked; allow only DNS results for a domain.
        if not ip.is_global and not (direct_ip is None and ip in SYNTHETIC_PROXY_NETWORK):
            raise WebToolError(f"禁止访问非公网地址：{address}")

    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, ""))


def parse_duckduckgo_html(source: str, *, max_results: int) -> list[dict[str, str]]:
    parser = _DuckDuckGoParser()
    parser.feed(source)
    results: list[dict[str, str]] = []
    for raw in parser.raw_results:
        title = _collapse(raw["title"])
        snippet = _collapse(raw["snippet"])
        url = _decode_duckduckgo_url(raw["url"])
        parsed = urlsplit(url)
        if not title or parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        results.append({"title": html.unescape(title), "url": url, "snippet": html.unescape(snippet)})
        if len(results) >= max_results:
            break
    return results


def _duckduckgo_search_one(query: str, max_results: int) -> list[dict[str, str]]:
    with httpx.Client(timeout=WEB_TIMEOUT_SECONDS, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get("https://html.duckduckgo.com/html/", params={"q": query})
        response.raise_for_status()
        if len(response.content) > MAX_HTTP_BYTES:
            raise WebToolError("搜索响应超过 2MB 上限")
        return parse_duckduckgo_html(response.text, max_results=max_results)


def _fetch_one_url(url: str, max_chars: int) -> dict[str, Any]:
    current = url
    with httpx.Client(timeout=WEB_TIMEOUT_SECONDS, follow_redirects=False, headers={"User-Agent": USER_AGENT}) as client:
        for _hop in range(MAX_REDIRECTS + 1):
            current = validate_public_web_url(current)
            with client.stream("GET", current, headers={"Accept": "text/html,text/plain,application/json,application/xml;q=0.9,*/*;q=0.1"}) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise WebToolError("重定向缺少 Location")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if not _is_text_content_type(content_type):
                    raise WebToolError(f"不支持的响应类型：{content_type or 'unknown'}")
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_HTTP_BYTES:
                        raise WebToolError("网页响应超过 2MB 上限")
                    chunks.append(chunk)
                encoding = response.encoding or "utf-8"
                text = b"".join(chunks).decode(encoding, errors="replace")
                if content_type in {"text/html", "application/xhtml+xml"}:
                    text = _html_to_text(text)
                else:
                    text = text.strip()
                truncated = len(text) > max_chars
                return {
                    "url": url,
                    "final_url": current,
                    "status": response.status_code,
                    "content_type": content_type,
                    "text": text[:max_chars] + ("…[截断]" if truncated else ""),
                    "truncated": truncated,
                }
    raise WebToolError(f"重定向超过 {MAX_REDIRECTS} 次")


def _resolve_host_ips(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise WebToolError(f"DNS 解析失败：{host}") from exc
    return sorted({str(item[4][0]) for item in infos})


def _is_text_content_type(content_type: str) -> bool:
    return content_type.startswith("text/") or content_type in {
        "application/json",
        "application/ld+json",
        "application/xml",
        "application/xhtml+xml",
        "application/rss+xml",
        "application/atom+xml",
    }


def _string_list(args: dict[str, Any], key: str, maximum: int) -> list[str]:
    value = args.get(key)
    if not isinstance(value, list):
        raise WebToolError(f"{key} 必须是数组")
    return _clean_items(value, maximum, key)


def _clean_items(items: list[Any], maximum: int, label: str) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise WebToolError(f"{label} 只能包含非空字符串")
        value = item.strip()
        if len(value) > 1000:
            raise WebToolError(f"{label} 单项超过 1000 字符")
        if value not in cleaned:
            cleaned.append(value)
    if not cleaned or len(cleaned) > maximum:
        raise WebToolError(f"{label} 数量必须为 1–{maximum}")
    return cleaned


def _bounded_int(args: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
    raw = args.get(key, default)
    if isinstance(raw, bool):
        raise WebToolError(f"{key} 必须是整数")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise WebToolError(f"{key} 必须是整数") from exc
    if value < minimum or value > maximum:
        raise WebToolError(f"{key} 必须在 {minimum}–{maximum} 之间")
    return value


def _raise_if_cancelled(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise WebToolError("用户已停止本轮对话")


def _decode_duckduckgo_url(raw: str) -> str:
    url = html.unescape(raw.strip())
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlsplit(url)
    if parsed.hostname and parsed.hostname.endswith("duckduckgo.com"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    return url


def _collapse(value: str) -> str:
    return " ".join(value.split())


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.raw_results: list[dict[str, str]] = []
        self._capture: str | None = None
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        classes = set(values.get("class", "").split())
        if "result__a" in classes:
            self.raw_results.append({"title": "", "url": values.get("href", ""), "snippet": ""})
            self._capture = "title"
            self._depth = 1
        elif "result__snippet" in classes and self.raw_results:
            self._capture = "snippet"
            self._depth = 1
        elif self._capture:
            self._depth += 1

    def handle_endtag(self, _tag: str) -> None:
        if self._capture:
            self._depth -= 1
            if self._depth <= 0:
                self._capture = None

    def handle_data(self, data: str) -> None:
        if self._capture and self.raw_results:
            self.raw_results[-1][self._capture] += data


class _VisibleTextParser(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "svg", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.parts.append(data)


def _html_to_text(source: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(source)
    return _collapse(" ".join(parser.parts))
