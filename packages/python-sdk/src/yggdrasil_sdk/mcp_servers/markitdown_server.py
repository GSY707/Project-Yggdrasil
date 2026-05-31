from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import os
from pathlib import Path
import re
from typing import Any
from urllib import request as urllib_request

from .base import SimpleMCPServer, structured_tool_result
from .local_cache import cached_call


_DEFAULT_USER_AGENT = "Project-Yggdrasil-MarkItDownTool/0.1 (+https://github.com/GSY707/Project-Yggdrasil)"


def _cache_ttl_seconds() -> int:
    return max(int(os.environ.get("YGGDRASIL_MCP_MARKITDOWN_CACHE_TTL_SECONDS") or os.environ.get("YGGDRASIL_MCP_CACHE_TTL_SECONDS") or 86400), 0)


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


def _workspace_root() -> Path:
    return Path(os.environ.get("YGGDRASIL_MCP_WORKSPACE") or Path.cwd()).resolve()


def _resolve_path(raw_path: str) -> Path:
    workspace_root = _workspace_root()
    candidate = Path(raw_path).expanduser()
    resolved = candidate.resolve() if candidate.is_absolute() else (workspace_root / candidate).resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError("Path escapes the configured project workspace.") from exc
    return resolved


def _http_get(url: str, *, timeout_seconds: float = 20.0) -> str:
    req = urllib_request.Request(url, headers={"User-Agent": _DEFAULT_USER_AGENT})
    with urllib_request.urlopen(req, timeout=timeout_seconds) as resp:  # noqa: S310
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def _fallback_markdown_from_html(html: str) -> str:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    title = unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip() if title_match else ""
    parser = _TextExtractor()
    parser.feed(html)
    content = parser.text().strip()
    if title:
        return f"# {title}\n\n{content}".strip()
    return content


def _convert_via_markitdown(source: str) -> str | None:
    try:
        from markitdown import MarkItDown  # type: ignore
    except Exception:
        return None
    try:
        converter = MarkItDown()
        result = converter.convert(source)
        text_content = getattr(result, "text_content", None)
        if isinstance(text_content, str) and text_content.strip():
            return text_content
    except Exception:
        return None
    return None


def _convert_to_markdown(arguments: dict[str, Any]) -> dict[str, Any]:
    source = str(arguments.get("source") or arguments.get("url") or arguments.get("path") or "").strip()
    if not source:
        raise ValueError("source is required")

    def _loader() -> dict[str, Any]:
        converted = _convert_via_markitdown(source)
        if converted:
            return {
                "source": source,
                "markdown": converted,
                "engine": "markitdown",
            }

        if source.startswith("http://") or source.startswith("https://"):
            html = _http_get(source)
            markdown = _fallback_markdown_from_html(html)
            return {
                "source": source,
                "markdown": markdown,
                "engine": "fallback-html-parser",
            }

        file_path = _resolve_path(source)
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(str(file_path))

        suffix = file_path.suffix.lower()
        if suffix in {".md", ".markdown", ".txt"}:
            markdown = file_path.read_text(encoding="utf-8", errors="replace")
        elif suffix in {".html", ".htm"}:
            html = file_path.read_text(encoding="utf-8", errors="replace")
            markdown = _fallback_markdown_from_html(html)
        else:
            markdown = (
                f"# Unsupported format fallback\n\n"
                f"File {file_path.name} has extension '{suffix}' which fallback parser does not fully support.\n"
                f"Install python package markitdown for richer conversion."
            )
        return {
            "source": str(file_path),
            "markdown": markdown,
            "engine": "fallback-file-parser",
        }

    payload, cache_meta = cached_call(
        namespace="markitdown-convert",
        cache_key=f"source={source}",
        ttl_seconds=_cache_ttl_seconds(),
        loader=_loader,
    )
    if isinstance(payload, dict):
        payload["cache"] = cache_meta
    else:
        payload = {"source": source, "markdown": str(payload), "engine": "unknown", "cache": cache_meta}

    return structured_tool_result(
        payload,
        text=f"Converted source to markdown: {source}",
    )


def main() -> None:
    server = SimpleMCPServer("workspace-markitdown-mcp", "0.1.0")
    server.register_tool(
        name="convert_to_markdown",
        description="Convert a URL or local file into markdown text (uses markitdown when available).",
        input_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "url": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["source"],
            "additionalProperties": False,
        },
        handler=_convert_to_markdown,
    )
    server.serve_stdio()


if __name__ == "__main__":
    main()
