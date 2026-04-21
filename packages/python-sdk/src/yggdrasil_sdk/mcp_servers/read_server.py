from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import SimpleMCPServer, structured_tool_result


def _workspace_root() -> Path:
    return Path(os.environ.get("YGGDRASIL_MCP_WORKSPACE") or Path.cwd()).resolve()


def _resolve_path(raw_path: str | None) -> Path:
    workspace_root = _workspace_root()
    candidate = Path(raw_path or ".").expanduser()
    resolved = candidate.resolve() if candidate.is_absolute() else (workspace_root / candidate).resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError("Path escapes the configured project workspace.") from exc
    return resolved


def _list_directory(arguments: dict[str, Any]) -> dict[str, Any]:
    directory = _resolve_path(arguments.get("path"))
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(str(directory))
    entries = []
    for child in sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        entries.append({
            "name": child.name,
            "path": str(child),
            "kind": "directory" if child.is_dir() else "file",
        })
    return structured_tool_result({"path": str(directory), "entries": entries}, text=f"Listed {len(entries)} item(s) in {directory}.")


def _read_file(arguments: dict[str, Any]) -> dict[str, Any]:
    file_path = _resolve_path(arguments.get("path"))
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(str(file_path))
    encoding = str(arguments.get("encoding") or "utf-8")
    start_line = max(int(arguments.get("startLine") or 1), 1)
    lines = file_path.read_text(encoding=encoding).splitlines()
    end_line = int(arguments.get("endLine") or len(lines))
    selected = lines[start_line - 1 : max(end_line, start_line - 1)]
    return structured_tool_result(
        {
            "path": str(file_path),
            "startLine": start_line,
            "endLine": end_line,
            "totalLines": len(lines),
            "content": "\n".join(selected),
        },
        text=f"Read {len(selected)} line(s) from {file_path}.",
    )


def main() -> None:
    server = SimpleMCPServer("workspace-read-mcp", "0.1.0")
    server.register_tool(
        name="list_directory",
        description="List files and folders inside the configured project workspace.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "additionalProperties": False,
        },
        handler=_list_directory,
    )
    server.register_tool(
        name="read_file",
        description="Read a text file from the configured project workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "startLine": {"type": "integer", "minimum": 1},
                "endLine": {"type": "integer", "minimum": 1},
                "encoding": {"type": "string"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=_read_file,
    )
    server.serve_stdio()


if __name__ == "__main__":
    main()