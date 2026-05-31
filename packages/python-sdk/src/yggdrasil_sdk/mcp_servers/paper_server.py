from __future__ import annotations

from html import unescape
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


_DEFAULT_USER_AGENT = "Project-Yggdrasil-PaperTool/0.1 (+https://github.com/GSY707/Project-Yggdrasil)"


def _cache_ttl_seconds() -> int:
    return max(int(os.environ.get("YGGDRASIL_MCP_PAPER_CACHE_TTL_SECONDS") or os.environ.get("YGGDRASIL_MCP_CACHE_TTL_SECONDS") or 1800), 0)


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


def _http_get_json(url: str, *, headers: dict[str, str] | None = None, timeout_seconds: float = 12.0) -> dict[str, Any]:
    req_headers = {
        "User-Agent": _DEFAULT_USER_AGENT,
        "Accept": "application/json",
    }
    if headers:
        req_headers.update(headers)
    req = urllib_request.Request(url, headers=req_headers)
    last_error: Exception | None = None
    raw = b""
    for attempt in range(1, _http_retry_attempts() + 1):
        try:
            with urllib_request.urlopen(req, timeout=timeout_seconds) as resp:  # noqa: S310
                raw = resp.read()
            break
        except urllib_error.HTTPError as exc:
            last_error = exc
            if attempt >= _http_retry_attempts() or not _is_retryable_status(int(exc.code or 0)):
                raise
            time.sleep(_retry_delay_from_error(exc, attempt=attempt))
        except urllib_error.URLError as exc:
            last_error = exc
            if attempt >= _http_retry_attempts():
                raise
            time.sleep(_http_retry_backoff_seconds() * attempt)
    if not raw and last_error is not None:
        raise RuntimeError(f"HTTP JSON request failed for {url}: {last_error}")
    parsed = json.loads(raw.decode("utf-8", errors="replace"))
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _http_get_text(url: str, *, headers: dict[str, str] | None = None, timeout_seconds: float = 12.0) -> str:
    req_headers = {"User-Agent": _DEFAULT_USER_AGENT, "Accept": "application/atom+xml,text/xml;q=0.9,*/*;q=0.8"}
    if headers:
        req_headers.update(headers)
    req = urllib_request.Request(url, headers=req_headers)
    last_error: Exception | None = None
    raw = b""
    for attempt in range(1, _http_retry_attempts() + 1):
        try:
            with urllib_request.urlopen(req, timeout=timeout_seconds) as resp:  # noqa: S310
                raw = resp.read()
            break
        except urllib_error.HTTPError as exc:
            last_error = exc
            if attempt >= _http_retry_attempts() or not _is_retryable_status(int(exc.code or 0)):
                raise
            time.sleep(_retry_delay_from_error(exc, attempt=attempt))
        except urllib_error.URLError as exc:
            last_error = exc
            if attempt >= _http_retry_attempts():
                raise
            time.sleep(_http_retry_backoff_seconds() * attempt)
    if not raw and last_error is not None:
        raise RuntimeError(f"HTTP text request failed for {url}: {last_error}")
    return raw.decode("utf-8", errors="replace")


def _normalize_title(value: Any) -> str:
    text = re.sub(r"<[^>]+>", "", str(value or ""))
    return unescape(" ".join(text.split()))


def _search_semantic_scholar(query: str, max_results: int) -> list[dict[str, Any]]:
    encoded = urllib_parse.quote_plus(query)
    url = (
        "https://api.semanticscholar.org/graph/v1/paper/search"
        f"?query={encoded}&limit={max_results}&fields=title,year,url,venue,abstract,citationCount,authors"
    )
    payload = _http_get_json(url)
    rows = payload.get("data") if isinstance(payload.get("data"), list) else []
    items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        authors = row.get("authors") if isinstance(row.get("authors"), list) else []
        items.append(
            {
                "source": "semantic-scholar",
                "title": _normalize_title(row.get("title")),
                "year": row.get("year"),
                "url": row.get("url"),
                "venue": row.get("venue"),
                "citationCount": row.get("citationCount"),
                "authors": [str(author.get("name") or "") for author in authors if isinstance(author, dict)],
                "abstract": str(row.get("abstract") or "").strip(),
            }
        )
    return items


def _search_openalex(query: str, max_results: int) -> list[dict[str, Any]]:
    encoded = urllib_parse.quote_plus(query)
    url = f"https://api.openalex.org/works?search={encoded}&per-page={max_results}"
    headers: dict[str, str] = {}
    api_key = str(os.environ.get("OPENALEX_API_KEY") or "").strip()
    if api_key:
        headers["api-key"] = api_key
    payload = _http_get_json(url, headers=headers)
    rows = payload.get("results") if isinstance(payload.get("results"), list) else []
    items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ids = row.get("ids") if isinstance(row.get("ids"), dict) else {}
        primary_location = row.get("primary_location") if isinstance(row.get("primary_location"), dict) else {}
        source = primary_location.get("source") if isinstance(primary_location.get("source"), dict) else {}
        authorships = row.get("authorships") if isinstance(row.get("authorships"), list) else []
        items.append(
            {
                "source": "openalex",
                "title": _normalize_title(row.get("display_name")),
                "year": row.get("publication_year"),
                "url": ids.get("openalex") or row.get("id"),
                "doi": ids.get("doi"),
                "venue": source.get("display_name"),
                "citationCount": row.get("cited_by_count"),
                "authors": [
                    str((author.get("author") or {}).get("display_name") or "")
                    for author in authorships
                    if isinstance(author, dict)
                ],
                "abstract": "",
            }
        )
    return items


def _search_arxiv(query: str, max_results: int) -> list[dict[str, Any]]:
    encoded = urllib_parse.quote_plus(query)
    url = f"https://export.arxiv.org/api/query?search_query=all:{encoded}&start=0&max_results={max_results}"
    xml_text = _http_get_text(url)
    entries = re.findall(r"<entry>(.*?)</entry>", xml_text, flags=re.DOTALL | re.IGNORECASE)
    items: list[dict[str, Any]] = []
    for entry in entries:
        title_match = re.search(r"<title>(.*?)</title>", entry, flags=re.DOTALL | re.IGNORECASE)
        summary_match = re.search(r"<summary>(.*?)</summary>", entry, flags=re.DOTALL | re.IGNORECASE)
        published_match = re.search(r"<published>(.*?)</published>", entry, flags=re.DOTALL | re.IGNORECASE)
        id_match = re.search(r"<id>(.*?)</id>", entry, flags=re.DOTALL | re.IGNORECASE)
        authors = re.findall(r"<name>(.*?)</name>", entry, flags=re.DOTALL | re.IGNORECASE)
        year = None
        if published_match:
            published = str(published_match.group(1)).strip()
            year = int(published[:4]) if len(published) >= 4 and published[:4].isdigit() else None
        items.append(
            {
                "source": "arxiv",
                "title": _normalize_title(title_match.group(1) if title_match else ""),
                "year": year,
                "url": str(id_match.group(1)).strip() if id_match else None,
                "venue": "arXiv",
                "citationCount": None,
                "authors": [_normalize_title(author) for author in authors],
                "abstract": _normalize_title(summary_match.group(1) if summary_match else ""),
            }
        )
    return items


def _search_papers(arguments: dict[str, Any]) -> dict[str, Any]:
    query = str(arguments.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    max_results = max(1, min(int(arguments.get("maxResults") or 8), 20))

    providers = arguments.get("providers")
    if isinstance(providers, list):
        selected = {str(item).strip().lower() for item in providers if str(item).strip()}
    else:
        selected = {"semantic", "openalex", "arxiv"}

    def _loader() -> dict[str, Any]:
        all_results: list[dict[str, Any]] = []
        provider_errors: list[dict[str, str]] = []

        if "semantic" in selected or "semanticscholar" in selected:
            try:
                all_results.extend(_search_semantic_scholar(query, max_results))
            except Exception as exc:  # noqa: BLE001
                provider_errors.append({"provider": "semantic-scholar", "error": str(exc)})

        if "openalex" in selected:
            try:
                all_results.extend(_search_openalex(query, max_results))
            except Exception as exc:  # noqa: BLE001
                provider_errors.append({"provider": "openalex", "error": str(exc)})

        if "arxiv" in selected:
            try:
                all_results.extend(_search_arxiv(query, max_results))
            except Exception as exc:  # noqa: BLE001
                provider_errors.append({"provider": "arxiv", "error": str(exc)})
        return {
            "allResults": all_results,
            "providerErrors": provider_errors,
        }

    loaded, cache_meta = cached_call(
        namespace="paper-search",
        cache_key=f"query={query}|maxResults={max_results}|providers={','.join(sorted(selected))}",
        ttl_seconds=_cache_ttl_seconds(),
        loader=_loader,
    )
    all_results = loaded.get("allResults") if isinstance(loaded.get("allResults"), list) else []
    provider_errors = loaded.get("providerErrors") if isinstance(loaded.get("providerErrors"), list) else []

    deduped: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for row in all_results:
        title = str(row.get("title") or "").strip().lower()
        url = str(row.get("url") or "").strip().lower()
        key = f"{title}|{url}"
        if not title and not url:
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(row)
        if len(deduped) >= max_results:
            break

    payload = {
        "query": query,
        "count": len(deduped),
        "results": deduped,
        "providerErrors": provider_errors,
        "providersTried": sorted(selected),
        "cache": cache_meta,
    }
    return structured_tool_result(payload, text=f"Found {len(deduped)} paper result(s) for query: {query}")


def main() -> None:
    server = SimpleMCPServer("workspace-paper-mcp", "0.1.0")
    server.register_tool(
        name="search_papers",
        description="Search scholarly papers from Semantic Scholar, OpenAlex, and arXiv.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "maxResults": {"type": "integer", "minimum": 1, "maximum": 20},
                "providers": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["semantic", "openalex", "arxiv"]},
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=_search_papers,
    )
    server.serve_stdio()


if __name__ == "__main__":
    main()
