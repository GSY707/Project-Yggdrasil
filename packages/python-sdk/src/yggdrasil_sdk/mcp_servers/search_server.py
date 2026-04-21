from __future__ import annotations

import fnmatch
import os
from pathlib import Path
import re
from typing import Any

from .base import SimpleMCPServer, structured_tool_result


IGNORED_DIRS = {".git", ".next", ".venv", ".yggdrasil", "node_modules", "__pycache__", "dist", "build", "coverage"}


def _workspace_root() -> Path:
    return Path(os.environ.get("YGGDRASIL_MCP_WORKSPACE") or Path.cwd()).resolve()


def _iter_workspace_files(root: Path):
    for path in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def _find_files(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_root = _workspace_root()
    pattern = str(arguments.get("glob") or "**/*")
    matches = [
        str(path)
        for path in _iter_workspace_files(workspace_root)
        if fnmatch.fnmatch(path.relative_to(workspace_root).as_posix(), pattern)
    ]
    return structured_tool_result({"glob": pattern, "matches": matches[: int(arguments.get("maxResults") or 200)]}, text=f"Matched {len(matches)} file(s).")


def _search_text(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_root = _workspace_root()
    query = str(arguments.get("query") or "")
    if not query:
        raise ValueError("query is required")
    glob_pattern = str(arguments.get("glob") or "**/*")
    is_regex = bool(arguments.get("isRegex", False))
    max_results = max(int(arguments.get("maxResults") or 50), 1)
    matcher = re.compile(query, re.IGNORECASE) if is_regex else None
    matches: list[dict[str, Any]] = []
    for path in _iter_workspace_files(workspace_root):
        relative = path.relative_to(workspace_root).as_posix()
        if not fnmatch.fnmatch(relative, glob_pattern):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for index, line in enumerate(lines, start=1):
            matched = bool(matcher.search(line)) if matcher is not None else query.lower() in line.lower()
            if not matched:
                continue
            matches.append({"path": str(path), "line": index, "content": line})
            if len(matches) >= max_results:
                return structured_tool_result({"query": query, "matches": matches}, text=f"Found {len(matches)} match(es).")
    return structured_tool_result({"query": query, "matches": matches}, text=f"Found {len(matches)} match(es).")


def main() -> None:
    server = SimpleMCPServer("workspace-search-mcp", "0.1.0")
    server.register_tool(
        name="find_files",
        description="Find files in the configured project workspace by glob.",
        input_schema={
            "type": "object",
            "properties": {
                "glob": {"type": "string"},
                "maxResults": {"type": "integer", "minimum": 1},
            },
            "required": ["glob"],
            "additionalProperties": False,
        },
        handler=_find_files,
    )
    server.register_tool(
        name="search_text",
        description="Search text inside files in the configured project workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "glob": {"type": "string"},
                "isRegex": {"type": "boolean"},
                "maxResults": {"type": "integer", "minimum": 1},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=_search_text,
    )
    server.serve_stdio()


if __name__ == "__main__":
    main()