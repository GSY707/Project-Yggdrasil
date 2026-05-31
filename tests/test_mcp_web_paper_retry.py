from __future__ import annotations

import io
from urllib import error as urllib_error

from yggdrasil_sdk.mcp_servers import paper_server, web_server


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_search_web_retries_on_http_429(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_urlopen(req, timeout=0):  # noqa: ANN001
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib_error.HTTPError(
                url=str(getattr(req, "full_url", "https://example.com")),
                code=429,
                msg="Too Many Requests",
                hdrs={"Retry-After": "0"},
                fp=io.BytesIO(b"rate limited"),
            )
        return _FakeResponse(b'<a class="result__a" href="https://example.com">example</a>')

    monkeypatch.setenv("YGGDRASIL_MCP_WEB_CACHE_TTL_SECONDS", "0")
    monkeypatch.setenv("YGGDRASIL_MCP_HTTP_RETRY_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("YGGDRASIL_MCP_HTTP_RETRY_BACKOFF_SECONDS", "0")
    monkeypatch.setattr(web_server.urllib_request, "urlopen", fake_urlopen)

    result = web_server._search_web({"query": "retryable web search", "maxResults": 1})
    structured = result["structuredContent"]

    assert calls["count"] == 2
    assert structured["count"] == 1
    assert structured["results"][0]["url"] == "https://example.com"


def test_search_web_degrades_gracefully_on_persistent_http_failure(monkeypatch) -> None:
    def always_rate_limited(req, timeout=0):  # noqa: ANN001
        raise urllib_error.HTTPError(
            url=str(getattr(req, "full_url", "https://example.com")),
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "0"},
            fp=io.BytesIO(b"rate limited"),
        )

    monkeypatch.setenv("YGGDRASIL_MCP_WEB_CACHE_TTL_SECONDS", "0")
    monkeypatch.setenv("YGGDRASIL_MCP_HTTP_RETRY_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("YGGDRASIL_MCP_HTTP_RETRY_BACKOFF_SECONDS", "0")
    monkeypatch.setattr(web_server.urllib_request, "urlopen", always_rate_limited)

    result = web_server._search_web({"query": "persistent rate limit"})
    structured = result["structuredContent"]

    assert structured["count"] == 0
    assert structured["providerErrors"]
    assert structured["providerErrors"][0]["provider"] == "duckduckgo-html"


def test_paper_openalex_retries_on_http_429(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_urlopen(req, timeout=0):  # noqa: ANN001
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib_error.HTTPError(
                url=str(getattr(req, "full_url", "https://api.openalex.org")),
                code=429,
                msg="Too Many Requests",
                hdrs={"Retry-After": "0"},
                fp=io.BytesIO(b"rate limited"),
            )
        return _FakeResponse(b'{"results": []}')

    monkeypatch.setenv("YGGDRASIL_MCP_HTTP_RETRY_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("YGGDRASIL_MCP_HTTP_RETRY_BACKOFF_SECONDS", "0")
    monkeypatch.setattr(paper_server.urllib_request, "urlopen", fake_urlopen)

    results = paper_server._search_openalex("representation learning", 1)

    assert calls["count"] == 2
    assert results == []
