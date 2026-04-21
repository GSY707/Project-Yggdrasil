from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Any

from .base import SimpleMCPServer, structured_tool_result


def _workspace_root() -> Path:
    return Path(os.environ.get("YGGDRASIL_MCP_WORKSPACE") or Path.cwd()).resolve()


def _resolve_cwd(raw_path: str | None) -> Path:
    workspace_root = _workspace_root()
    if not raw_path:
        return workspace_root
    candidate = Path(raw_path).expanduser()
    resolved = candidate.resolve() if candidate.is_absolute() else (workspace_root / candidate).resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError("cwd escapes the configured project workspace.") from exc
    return resolved


def _run_command(arguments: dict[str, Any]) -> dict[str, Any]:
    command = str(arguments.get("command") or "").strip()
    if not command:
        raise ValueError("command is required")
    completed = subprocess.run(
        command,
        cwd=_resolve_cwd(arguments.get("cwd")),
        shell=True,
        capture_output=True,
        text=True,
        timeout=max(int(arguments.get("timeoutMs") or 10000), 1) / 1000.0,
        check=False,
    )
    return structured_tool_result(
        {
            "command": command,
            "cwd": str(_resolve_cwd(arguments.get("cwd"))),
            "exitCode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
        text=f"Command finished with exit code {completed.returncode}.",
        is_error=completed.returncode != 0,
    )


def main() -> None:
    server = SimpleMCPServer("workspace-execute-mcp", "0.1.0")
    server.register_tool(
        name="run_command",
        description="Run a shell command inside the configured project workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string"},
                "timeoutMs": {"type": "integer", "minimum": 1},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        handler=_run_command,
    )
    server.serve_stdio()


if __name__ == "__main__":
    main()