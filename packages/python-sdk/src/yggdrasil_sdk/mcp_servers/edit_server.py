from __future__ import annotations

import json
import os
import re
from pathlib import Path
import string
from typing import Any

from .base import SimpleMCPServer, structured_tool_result


_RAW_PATH_FIELD_RE = re.compile(r'("path"\s*:\s*")([^"]*)(")')


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


def _allowed_edit_paths() -> set[str] | None:
    raw = str(os.environ.get("YGGDRASIL_MCP_EDIT_ALLOWED_PATHS") or "").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("YGGDRASIL_MCP_EDIT_ALLOWED_PATHS must be valid JSON.") from exc
    if not isinstance(payload, list):
        raise ValueError("YGGDRASIL_MCP_EDIT_ALLOWED_PATHS must be a JSON array.")
    normalized = {
        Path(str(item)).as_posix().lstrip("./")
        for item in payload
        if str(item).strip()
    }
    return normalized or None


def _assert_edit_allowed(file_path: Path) -> None:
    allowed_paths = _allowed_edit_paths()
    if allowed_paths is None:
        return
    workspace_root = _workspace_root()
    relative_path = file_path.relative_to(workspace_root).as_posix()
    if relative_path not in allowed_paths:
        raise PermissionError(f"Path is outside the allowed edit set: {relative_path}")


def _is_unescaped_json_quote(raw_text: str, index: int) -> bool:
    backslash_count = 0
    cursor = index - 1
    while cursor >= 0 and raw_text[cursor] == "\\":
        backslash_count += 1
        cursor -= 1
    return backslash_count % 2 == 0


def _escape_invalid_json_string_escapes(raw_text: str) -> str:
    repaired: list[str] = []
    in_string = False
    index = 0
    valid_escape_chars = {'"', "\\", "/", "b", "f", "n", "r", "t"}

    while index < len(raw_text):
        ch = raw_text[index]
        if ch == '"' and _is_unescaped_json_quote(raw_text, index):
            in_string = not in_string
            repaired.append(ch)
            index += 1
            continue
        if in_string and ch == "\\":
            next_char = raw_text[index + 1] if index + 1 < len(raw_text) else ""
            if next_char == "u":
                unicode_chunk = raw_text[index + 2 : index + 6]
                if len(unicode_chunk) == 4 and all(char in string.hexdigits for char in unicode_chunk):
                    repaired.append(raw_text[index : index + 6])
                    index += 6
                else:
                    repaired.append("\\\\")
                    index += 1
            elif next_char in valid_escape_chars:
                repaired.append(raw_text[index : index + 2])
                index += 2
            else:
                repaired.append("\\\\")
                index += 1
            continue
        repaired.append(ch)
        index += 1
    return "".join(repaired)


def _extract_ordered_raw_fields(raw_text: str, field_order: tuple[str, ...]) -> dict[str, Any] | None:
    extracted: dict[str, Any] = {}
    cursor = 0
    for index, field_name in enumerate(field_order):
        marker = f'"{field_name}": "'
        start = raw_text.find(marker, cursor)
        if start < 0:
            return None
        value_start = start + len(marker)
        if index + 1 < len(field_order):
            next_marker = f'", "{field_order[index + 1]}": "'
            value_end = raw_text.find(next_marker, value_start)
            if value_end < 0:
                return None
            extracted[field_name] = raw_text[value_start:value_end]
            cursor = value_end + 1
            continue
        value_end = raw_text.rfind('"}')
        if value_end < value_start:
            return None
        extracted[field_name] = raw_text[value_start:value_end]
    return extracted


def _parse_edit_tool_raw_arguments(raw_text: str) -> dict[str, Any] | None:
    for field_order in (
        ("path", "content", "encoding"),
        ("path", "oldText", "newText", "encoding"),
        ("path", "content"),
        ("path", "oldText", "newText"),
    ):
        extracted = _extract_ordered_raw_fields(raw_text, field_order)
        if extracted is not None:
            return extracted
    return None


def _coerce_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        return {}
    if "path" in arguments or "_raw" not in arguments:
        return arguments
    raw_arguments = str(arguments.get("_raw") or "").strip()
    if not raw_arguments:
        return arguments
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError:
        repaired = _RAW_PATH_FIELD_RE.sub(
            lambda match: f'{match.group(1)}{match.group(2).replace("\\", "\\\\")}{match.group(3)}',
            raw_arguments,
            count=1,
        )
        repaired = _escape_invalid_json_string_escapes(repaired)
        if repaired == raw_arguments:
            parsed = _parse_edit_tool_raw_arguments(raw_arguments)
            return parsed if parsed is not None else arguments
        try:
            parsed = json.loads(repaired)
        except json.JSONDecodeError:
            parsed = _parse_edit_tool_raw_arguments(raw_arguments)
            return parsed if parsed is not None else arguments
    return parsed if isinstance(parsed, dict) else arguments


def _write_file(arguments: dict[str, Any]) -> dict[str, Any]:
    arguments = _coerce_arguments(arguments)
    file_path = _resolve_path(str(arguments.get("path") or ""))
    _assert_edit_allowed(file_path)
    content = str(arguments.get("content") or "")
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding=str(arguments.get("encoding") or "utf-8"))
    return structured_tool_result({"path": str(file_path), "bytes": len(content.encode("utf-8"))}, text=f"Wrote {file_path}.")


def _replace_text(arguments: dict[str, Any]) -> dict[str, Any]:
    arguments = _coerce_arguments(arguments)
    file_path = _resolve_path(str(arguments.get("path") or ""))
    _assert_edit_allowed(file_path)
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