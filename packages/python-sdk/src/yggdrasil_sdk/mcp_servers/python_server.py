from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
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
        raise ValueError("workingDirectory escapes the configured project workspace.") from exc
    return resolved


def _inspect_environment(arguments: dict[str, Any]) -> dict[str, Any]:
    cwd = _resolve_cwd(arguments.get("workingDirectory"))
    return structured_tool_result(
        {
            "pythonExecutable": sys.executable,
            "version": sys.version,
            "workingDirectory": str(cwd),
        },
        text=f"Python executable: {sys.executable}",
    )


def _run_python(arguments: dict[str, Any]) -> dict[str, Any]:
    code = str(arguments.get("code") or "")
    if not code.strip():
        raise ValueError("code is required")
    cwd = _resolve_cwd(arguments.get("workingDirectory"))
    script_fd, script_path_raw = tempfile.mkstemp(prefix="yggdrasil-python-", suffix=".py", dir=str(cwd))
    script_path = Path(script_path_raw)
    try:
        # Use a temporary script instead of `-c` to avoid Windows/Unicode quoting issues.
        with os.fdopen(script_fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(code)
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=max(int(arguments.get("timeoutMs") or 10000), 1) / 1000.0,
            check=False,
        )
    finally:
        try:
            script_path.unlink(missing_ok=True)
        except TypeError:
            if script_path.exists():
                script_path.unlink()
    return structured_tool_result(
        {
            "exitCode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
        text=f"Python finished with exit code {completed.returncode}.",
        is_error=completed.returncode != 0,
    )


def main() -> None:
    server = SimpleMCPServer("workspace-python-mcp", "0.1.0")
    server.register_tool(
        name="inspect_environment",
        description="Report the active Python interpreter and working directory used by the MCP bridge.",
        input_schema={
            "type": "object",
            "properties": {"workingDirectory": {"type": "string"}},
            "additionalProperties": False,
        },
        handler=_inspect_environment,
    )
    server.register_tool(
        name="run_python",
        description="Run a Python snippet inside the configured project workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "workingDirectory": {"type": "string"},
                "timeoutMs": {"type": "integer", "minimum": 1},
            },
            "required": ["code"],
            "additionalProperties": False,
        },
        handler=_run_python,
    )
    server.serve_stdio()


if __name__ == "__main__":
    main()