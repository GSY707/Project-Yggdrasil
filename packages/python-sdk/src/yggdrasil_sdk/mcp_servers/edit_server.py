from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import SimpleMCPServer, structured_tool_result


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


def _write_file(arguments: dict[str, Any]) -> dict[str, Any]:
    file_path = _resolve_path(str(arguments.get("path") or ""))
    content = str(arguments.get("content") or "")
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding=str(arguments.get("encoding") or "utf-8"))
    return structured_tool_result({"path": str(file_path), "bytes": len(content.encode("utf-8"))}, text=f"Wrote {file_path}.")


def _replace_text(arguments: dict[str, Any]) -> dict[str, Any]:
    file_path = _resolve_path(str(arguments.get("path") or ""))
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(str(file_path))
    old_text = str(arguments.get("oldText") or "")
    new_text = str(arguments.get("newText") or "")
    content = file_path.read_text(encoding=str(arguments.get("encoding") or "utf-8"))
    if old_text not in content:
        raise ValueError("oldText was not found in the target file.")
    updated = content.replace(old_text, new_text)
    file_path.write_text(updated, encoding=str(arguments.get("encoding") or "utf-8"))
    return structured_tool_result({"path": str(file_path), "replaced": True}, text=f"Updated {file_path}.")


def main() -> None:
    server = SimpleMCPServer("workspace-edit-mcp", "0.1.0")
    server.register_tool(
        name="write_file",
        description="Create or overwrite a file inside the configured project workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "encoding": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        handler=_write_file,
    )
    server.register_tool(
        name="replace_text",
        description="Replace an exact text fragment inside a file in the configured project workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "oldText": {"type": "string"},
                "newText": {"type": "string"},
                "encoding": {"type": "string"},
            },
            "required": ["path", "oldText", "newText"],
            "additionalProperties": False,
        },
        handler=_replace_text,
    )
    server.serve_stdio()


if __name__ == "__main__":
    main()