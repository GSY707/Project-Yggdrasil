from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import json
import os
import re
import time
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from .base import SimpleMCPServer, structured_tool_result
from .local_cache import cached_call


_DEFAULT_USER_AGENT = "Project-Yggdrasil-WebTool/0.1 (+https://github.com/GSY707/Project-Yggdrasil)"


def _cache_ttl_seconds() -> int:
    return max(int(os.environ.get("YGGDRASIL_MCP_WEB_CACHE_TTL_SECONDS") or os.environ.get("YGGDRASIL_MCP_CACHE_TTL_SECONDS") or 1800), 0)


def _http_retry_attempts() -> int:
    return max(int(os.environ.get("YGGDRASIL_MCP_HTTP_RETRY_MAX_ATTEMPTS") or 3), 1)


def _http_retry_backoff_seconds() -> float:
    return max(float(os.environ.get("YGGDRASIL_MCP_HTTP_RETRY_BACKOFF_SECONDS") or 0.5), 0.0)


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def _retry_delay_from_error(exc: urllib_error.HTTPError, *, attempt: int) -> float:
    retry_after = str(exc.headers.get("Retry-After") or "").strip() if exc.headers else ""
    if retry_after:
        try:
            return max(float(retry_after), 0.0)
        except ValueError:
            pass
    return _http_retry_backoff_seconds() * attempt


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        text = str(data or "").strip()
        if text:
            self._chunks.append(text)

    def text(self) -> str:
        return "\n".join(self._chunks)


def _http_get(url: str, *, timeout_seconds: float = 12.0) -> str:
    req = urllib_request.Request(
        url,
        headers={
            "User-Agent": _DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        },
    )
    last_error: Exception | None = None
    for attempt in range(1, _http_retry_attempts() + 1):
        try:
            with urllib_request.urlopen(req, timeout=timeout_seconds) as resp:  # noqa: S310
                raw = resp.read()
            return raw.decode("utf-8", errors="replace")
        except urllib_error.HTTPError as exc:
            last_error = exc
            if attempt >= _http_retry_attempts() or not _is_retryable_status(int(exc.code or 0)):
                break
            time.sleep(_retry_delay_from_error(exc, attempt=attempt))
        except urllib_error.URLError as exc:
            last_error = exc
            if attempt >= _http_retry_attempts():
                break
            time.sleep(_http_retry_backoff_seconds() * attempt)
    raise RuntimeError(f"HTTP GET failed for {url}: {last_error}")


def _search_web(arguments: dict[str, Any]) -> dict[str, Any]:
    query = str(arguments.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    max_results = max(1, min(int(arguments.get("maxResults") or 8), 20))

    encoded = urllib_parse.quote_plus(query)

    def _loader() -> str:
        # DuckDuckGo HTML endpoint does not require an API key and is suitable for lightweight retrieval.
        return _http_get(f"https://duckduckgo.com/html/?q={encoded}")

    try:
        html, cache_meta = cached_call(
            namespace="web-search",
            cache_key=f"query={query}|maxResults={max_results}",
            ttl_seconds=_cache_ttl_seconds(),
            loader=_loader,
        )
    except Exception as exc:  # noqa: BLE001
        return structured_tool_result(
            {
                "query": query,
                "count": 0,
                "results": [],
                "providerErrors": [{"provider": "duckduckgo-html", "error": str(exc)}],
                "cache": {"enabled": False, "hit": False, "ttlSeconds": _cache_ttl_seconds()},
            },
            text=f"Found 0 web result(s) for query: {query} (temporary retrieval failure)",
        )

    pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    snippet_pattern = re.compile(r'<a[^>]*class="result__snippet"[^>]*>(?P<snippet>.*?)</a>', re.IGNORECASE | re.DOTALL)

    title_matches = list(pattern.finditer(html))
    snippet_matches = list(snippet_pattern.finditer(html))

    items: list[dict[str, Any]] = []
    for index, title_match in enumerate(title_matches[:max_results]):
        href = unescape(title_match.group("href"))
        title = re.sub(r"<[^>]+>", "", title_match.group("title"))
        snippet_raw = snippet_matches[index].group("snippet") if index < len(snippet_matches) else ""
        snippet = re.sub(r"<[^>]+>", "", snippet_raw)
        items.append(
            {
                "rank": index + 1,
                "title": unescape(title).strip(),
                "url": href.strip(),
                "snippet": unescape(snippet).strip(),
                "source": "duckduckgo-html",
            }
        )

    return structured_tool_result(
        {
            "query": query,
            "count": len(items),
            "results": items,
            "cache": cache_meta,
        },
        text=f"Found {len(items)} web result(s) for query: {query}",
    )


def _fetch_webpage(arguments: dict[str, Any]) -> dict[str, Any]:
    url = str(arguments.get("url") or "").strip()
    if not url:
        raise ValueError("url is required")
    max_chars = max(500, min(int(arguments.get("maxChars") or 12000), 120000))

    html, cache_meta = cached_call(
        namespace="web-fetch",
        cache_key=f"url={url}",
        ttl_seconds=_cache_ttl_seconds(),
        loader=lambda: _http_get(url),
    )
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    title = unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip() if title_match else ""

    extractor = _TextExtractor()
    extractor.feed(html)
    text = extractor.text()
    normalized = re.sub(r"\n{3,}", "\n\n", text).strip()
    excerpt = normalized[:max_chars]

    payload = {
        "url": url,
        "title": title,
        "content": excerpt,
        "truncated": len(normalized) > len(excerpt),
        "contentLength": len(normalized),
        "cache": cache_meta,
    }
    return structured_tool_result(payload, text=f"Fetched webpage: {url}")


def _search_web_json(arguments: dict[str, Any]) -> dict[str, Any]:
    # Convenience wrapper for workflows that want compact machine-readable output.
    result = _search_web(arguments)
    structured = result.get("structuredContent") if isinstance(result.get("structuredContent"), dict) else {}
    return structured_tool_result(
        {
            "query": structured.get("query"),
            "results": structured.get("results") or [],
            "json": json.dumps(structured, ensure_ascii=False),
        },
        text="Web search JSON payload generated.",
    )


def main() -> None:
    server = SimpleMCPServer("workspace-web-mcp", "0.1.0")
    server.register_tool(
        name="search_web",
        description="Search the public web and return ranked results.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "maxResults": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=_search_web,
    )
    server.register_tool(
        name="fetch_webpage",
        description="Fetch webpage content and return extracted text.",
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "maxChars": {"type": "integer", "minimum": 500, "maximum": 120000},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        handler=_fetch_webpage,
    )
    server.register_tool(
        name="search_web_json",
        description="Search the public web and return JSON text output for downstream parsing.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "maxResults": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=_search_web_json,
    )
    server.serve_stdio()


if __name__ == "__main__":
    main()
